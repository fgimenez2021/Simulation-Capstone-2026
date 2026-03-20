from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal

import pandas as pd

from .engine import run_single_lifecycle
from .gates import InvestorProfile
from .hybrid import run_single_lifecycle_hybrid
from .queues import QueueWaitSamplers, build_queue_wait_samplers
from .types import ModelConfig, RunResult


def ensure_output_dirs(base_dir: str | Path = "outputs") -> Dict[str, Path]:
    base = Path(base_dir)
    runs_dir = base / "runs"
    stages_dir = base / "stages"
    tables_dir = base / "tables"
    figures_dir = base / "figures"

    for d in [runs_dir, stages_dir, tables_dir, figures_dir]:
        d.mkdir(parents=True, exist_ok=True)

    return {
        "base": base,
        "runs": runs_dir,
        "stages": stages_dir,
        "tables": tables_dir,
        "figures": figures_dir,
    }


def run_experiment(
    *,
    model: ModelConfig,
    n_runs: int,
    asset_id: str,
    route_id: str,
    scenario_id: str,
    investor_profile: InvestorProfile,
    outputs_dir: str | Path = "outputs",
    lifecycle_mode: Literal["hybrid", "baseline"] = "hybrid",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Runs N Monte Carlo lifecycles for a specific asset/route/scenario and returns:
      - df_runs: run-level results
      - df_stages: stage-level results
    Also writes CSVs to outputs/.
    """
    dirs = ensure_output_dirs(outputs_dir)

    run_rows: List[dict] = []
    stage_rows: List[dict] = []

    scenario = model.scenarios[scenario_id]
    queue_samplers: QueueWaitSamplers | None = None
    if lifecycle_mode == "hybrid" and scenario.queues.enabled:
        queue_samplers = build_queue_wait_samplers(
            model=model,
            scenario=scenario,
            route_id=route_id,
        )

    for i in range(1, n_runs + 1):
        if lifecycle_mode == "hybrid":
            res = run_single_lifecycle_hybrid(
                model=model,
                run_id=i,
                asset_id=asset_id,
                route_id=route_id,
                scenario_id=scenario_id,
                investor=investor_profile,
                queue_samplers=queue_samplers,
            )
        else:
            res = run_single_lifecycle(
                model=model,
                run_id=i,
                asset_id=asset_id,
                route_id=route_id,
                scenario_id=scenario_id,
                investor=investor_profile,
            )

        run_rows.append(_flatten_run(res))
        stage_rows.extend(_flatten_stages(res))

    df_runs = pd.DataFrame(run_rows)
    df_stages = pd.DataFrame(stage_rows)

    tag = f"{scenario_id}__{asset_id}__{route_id}__N{n_runs}"
    runs_path = dirs["runs"] / f"runs_{tag}.csv"
    stages_path = dirs["stages"] / f"stages_{tag}.csv"

    df_runs.to_csv(runs_path, index=False)
    df_stages.to_csv(stages_path, index=False)

    return df_runs, df_stages


def run_full_grid(
    *,
    model: ModelConfig,
    n_runs: int,
    outputs_dir: str | Path = "outputs",
    qualified_for_private_credit: bool = True,
    lifecycle_mode: Literal["hybrid", "baseline"] = "hybrid",
) -> None:
    """
    Runs the full grid:
      scenarios × assets × routes

    Notes:
      - PRIVATE_CREDIT requires qualified investor per assets.yaml.
        This function automatically uses a qualified investor profile for that asset
        if qualified_for_private_credit=True.
    """
    dirs = ensure_output_dirs(outputs_dir)

    for scenario_id in model.scenarios.keys():
        for asset_id in model.assets.keys():
            for route_id in model.routes.keys():

                if asset_id == "PRIVATE_CREDIT" and qualified_for_private_credit:
                    investor = InvestorProfile(qualified_investor=True)
                else:
                    investor = InvestorProfile(qualified_investor=False)

                print(f"Running: scenario={scenario_id}, asset={asset_id}, route={route_id}, N={n_runs}")
                run_experiment(
                    model=model,
                    n_runs=n_runs,
                    asset_id=asset_id,
                    route_id=route_id,
                    scenario_id=scenario_id,
                    investor_profile=investor,
                    outputs_dir=dirs["base"],
                    lifecycle_mode=lifecycle_mode,
                )


def _flatten_run(res: RunResult) -> dict:
    return {
        "run_id": res.run_id,
        "asset_id": res.asset_id,
        "route_id": res.route_id,
        "scenario_id": res.scenario_id,

        "completed": res.completed,
        "exit_frozen": res.exit_frozen,
        "failed_stage_id": res.failed_stage_id,

        "total_time_hours": res.total_time_hours,
        "total_explicit_cost": res.total_explicit_cost,
        "total_implicit_cost": res.total_implicit_cost,

        "total_approvals": res.total_approvals,
        "total_handoffs": res.total_handoffs,
        "intermediaries_count": len(res.intermediaries),

        "time_to_position_hours": res.time_to_position_hours,
        "time_to_cash_hours": res.time_to_cash_hours,
    }


def _flatten_stages(res: RunResult) -> List[dict]:
    rows: List[dict] = []
    for idx, s in enumerate(res.stages, start=1):
        rows.append({
            "run_id": res.run_id,
            "stage_index": idx,
            "asset_id": res.asset_id,
            "route_id": res.route_id,
            "scenario_id": res.scenario_id,

            "stage_id": s.stage_id,
            "stage_label": s.stage_label,

            "time_hours": s.time_hours,
            "base_time_hours": s.base_time_hours,
            "gate_delay_hours": s.gate_delay_hours,
            "risk_delay_hours": s.risk_delay_hours,
            "exception_delay_hours": s.exception_delay_hours,
            "queue_delay_hours": s.queue_delay_hours,
            "explicit_cost": s.explicit_cost,
            "implicit_cost": s.implicit_cost,

            "approvals": s.approvals,
            "handoffs": s.handoffs,
            "intermediaries": ";".join(sorted(list(s.intermediaries))),

            "transfer_attempted": s.transfer_attempted,
            "transfer_success": s.transfer_success,

            "redemption_attempted": s.redemption_attempted,
            "redemption_success": s.redemption_success,

            "gate_events": ";".join(s.gate_events),
            "risk_events": ";".join(s.risk_events),
        })
    return rows
