from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import re

import pandas as pd

try:
    from tqdm import tqdm as _tqdm
except ImportError:
    _tqdm = None

from .analysis import build_analysis_tables, save_analysis_tables
from .gates import InvestorProfile
from .hybrid import run_single_lifecycle_hybrid
from .queues import QueueWaitSamplers, build_queue_wait_samplers
from .metrics import (
    summarize_access_permissions,
    summarize_delay_attribution,
    summarize_gate_events,
    summarize_runs,
    summarize_risk_events,
    summarize_transferability,
)
from .runner import ensure_output_dirs, _flatten_run, _flatten_stages
from .types import ModelConfig


def run_grid_and_build_reports(
    *,
    model: ModelConfig,
    n_runs: int,
    outputs_dir: str | Path = "outputs",
    qualified_for_private_credit: bool = True,
) -> Dict[str, Path]:
    """
    Runs the full experiment grid:
      scenarios × assets × routes
    using the hybrid lifecycle runner.

    Produces:
      - run-level CSVs per cell
      - stage-level CSVs per cell
      - aggregated tables in outputs/tables/

    Returns paths to the main output tables.
    """
    dirs = ensure_output_dirs(outputs_dir)

    all_runs = []
    all_stages = []

    cells = [
        (scenario_id, asset_id, route_id)
        for scenario_id in model.scenarios
        for asset_id in model.assets
        for route_id in model.routes
    ]
    iterator = _tqdm(cells, desc="Running grid") if _tqdm else cells

    for scenario_id, asset_id, route_id in iterator:

        if asset_id == "PRIVATE_CREDIT" and qualified_for_private_credit:
            investor = InvestorProfile(qualified_investor=True)
        else:
            investor = InvestorProfile(qualified_investor=False)

        print(f"[RUN] scenario={scenario_id} asset={asset_id} route={route_id} N={n_runs}")

        df_runs, df_stages = _run_cell(
            model=model,
            n_runs=n_runs,
            asset_id=asset_id,
            route_id=route_id,
            scenario_id=scenario_id,
            investor=investor,
        )

        tag = f"{scenario_id}__{asset_id}__{route_id}__N{n_runs}"
        runs_path = dirs["runs"] / f"runs_{tag}.csv"
        stages_path = dirs["stages"] / f"stages_{tag}.csv"
        df_runs.to_csv(runs_path, index=False)
        df_stages.to_csv(stages_path, index=False)

        all_runs.append(df_runs)
        all_stages.append(df_stages)

    df_runs_all = pd.concat(all_runs, ignore_index=True) if all_runs else pd.DataFrame()
    df_stages_all = pd.concat(all_stages, ignore_index=True) if all_stages else pd.DataFrame()

    runs_summary = summarize_runs(df_runs_all)
    transfer_summary = summarize_transferability(df_stages_all)
    risk_summary = summarize_risk_events(df_stages_all)
    gate_summary = summarize_gate_events(df_stages_all)
    access_summary = summarize_access_permissions(df_stages_all)
    delay_summary = summarize_delay_attribution(df_stages_all)

    runs_summary_path = dirs["tables"] / f"summary_runs__N{n_runs}.csv"
    transfer_summary_path = dirs["tables"] / f"summary_transfer__N{n_runs}.csv"
    risk_summary_path = dirs["tables"] / f"summary_risk__N{n_runs}.csv"
    gate_summary_path = dirs["tables"] / f"summary_gate__N{n_runs}.csv"
    access_summary_path = dirs["tables"] / f"summary_access__N{n_runs}.csv"
    delay_summary_path = dirs["tables"] / f"summary_delay_attribution__N{n_runs}.csv"

    runs_summary.to_csv(runs_summary_path, index=False)
    transfer_summary.to_csv(transfer_summary_path, index=False)
    risk_summary.to_csv(risk_summary_path, index=False)
    gate_summary.to_csv(gate_summary_path, index=False)
    access_summary.to_csv(access_summary_path, index=False)
    delay_summary.to_csv(delay_summary_path, index=False)

    analysis_tables = build_analysis_tables(df_runs=df_runs_all, df_stages=df_stages_all)
    analysis_paths = save_analysis_tables(
        tables=analysis_tables,
        outputs_dir=outputs_dir,
        n_runs=n_runs,
    )

    out_paths: Dict[str, Path] = {
        "runs_summary": runs_summary_path,
        "transfer_summary": transfer_summary_path,
        "risk_summary": risk_summary_path,
        "gate_summary": gate_summary_path,
        "access_summary": access_summary_path,
        "delay_summary": delay_summary_path,
    }
    out_paths.update(analysis_paths)
    return out_paths


def smoke_check_analysis_outputs(
    *,
    outputs_dir: str | Path = "outputs",
    n_runs: int | None = None,
) -> Dict[str, Path]:
    """
    Post-simulation smoke check:
      1) loads sample run/stage outputs from outputs/runs and outputs/stages
      2) regenerates main analysis tables
      3) regenerates figures
      4) confirms expected files exist
    """
    outputs_dir = Path(outputs_dir)
    runs_dir = outputs_dir / "runs"
    stages_dir = outputs_dir / "stages"
    if not runs_dir.exists() or not stages_dir.exists():
        raise FileNotFoundError("Missing outputs/runs or outputs/stages directory.")

    run_files = sorted(runs_dir.glob("runs_*__N*.csv"))
    stage_files = sorted(stages_dir.glob("stages_*__N*.csv"))
    if not run_files or not stage_files:
        raise FileNotFoundError("No run/stage CSV files found for smoke check.")

    def _extract_n(path: Path) -> int | None:
        m = re.search(r"__N(\d+)\.csv$", path.name)
        return int(m.group(1)) if m else None

    detected_n = n_runs
    if detected_n is None:
        candidates = [n for n in (_extract_n(p) for p in run_files) if n is not None]
        if not candidates:
            raise ValueError("Could not infer N from runs filenames.")
        detected_n = max(candidates)

    run_files = [p for p in run_files if _extract_n(p) == detected_n]
    stage_files = [p for p in stage_files if _extract_n(p) == detected_n]
    if not run_files or not stage_files:
        raise FileNotFoundError(f"No matching run/stage CSV files for N={detected_n}.")

    df_runs = pd.concat([pd.read_csv(p) for p in run_files], ignore_index=True)
    df_stages = pd.concat([pd.read_csv(p) for p in stage_files], ignore_index=True)

    analysis_tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    table_paths = save_analysis_tables(
        tables=analysis_tables,
        outputs_dir=outputs_dir,
        n_runs=detected_n,
    )

    from .plots import generate_all_figures

    fig_paths = generate_all_figures(outputs_dir=outputs_dir, n_runs=detected_n)
    all_paths: Dict[str, Path] = {}
    all_paths.update(table_paths)
    all_paths.update(fig_paths)

    missing = [str(p) for p in all_paths.values() if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(f"Smoke check failed; missing outputs: {missing}")
    return all_paths


def _run_cell(
    *,
    model: ModelConfig,
    n_runs: int,
    asset_id: str,
    route_id: str,
    scenario_id: str,
    investor: InvestorProfile,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run one grid cell (scenario × asset × route) with n_runs.
    Returns (df_runs, df_stages).
    """
    run_rows = []
    stage_rows = []
    scenario = model.scenarios[scenario_id]
    queue_samplers: QueueWaitSamplers | None = None
    if scenario.queues.enabled:
        queue_samplers = build_queue_wait_samplers(
            model=model,
            scenario=scenario,
            route_id=route_id,
        )

    for i in range(1, n_runs + 1):
        res = run_single_lifecycle_hybrid(
            model=model,
            run_id=i,
            asset_id=asset_id,
            route_id=route_id,
            scenario_id=scenario_id,
            investor=investor,
            queue_samplers=queue_samplers,
        )

        run_rows.append(_flatten_run(res))
        stage_rows.extend(_flatten_stages(res))

    return pd.DataFrame(run_rows), pd.DataFrame(stage_rows)
