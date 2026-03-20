from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
import shutil
from typing import Dict
from uuid import uuid4

import pandas as pd

from .analysis import apply_standard_ordering
from .config_loader import load_model_config
from .thesis_appendix import (
    STATIC_APPENDIX_TABLE_NAMES,
    build_results_appendix_tables,
    build_stage_driver_table,
    build_static_appendix_tables,
)
from .reporting import run_grid_and_build_reports
from .types import GatingSpec, ModelConfig

DEFAULT_SENSITIVITY_N = 200
SENSITIVITY_KYC_SERVERS = (1, 2, 4, 8)
SENSITIVITY_REDEMPTION_SERVERS = (1, 2, 4, 8)
SENSITIVITY_ALLOWLIST_PASS_PROBS = (0.60, 0.75, 0.90, 0.98)


def export_thesis_tables(
    *,
    outputs_dir: str | Path = "outputs",
    n_runs: int,
    config_dir: str | Path = "config",
) -> Dict[str, Path]:
    tables_dir = Path(outputs_dir) / "tables"
    kpi_overview = _read_required_csv(tables_dir / f"kpi_overview__N{n_runs}.csv")
    route_deltas = _read_required_csv(tables_dir / f"route_deltas__N{n_runs}.csv")
    stage_time_mix = _read_required_csv(tables_dir / f"stage_time_mix__N{n_runs}.csv")
    summary_access = _read_required_csv(tables_dir / f"summary_access__N{n_runs}.csv")
    summary_gate = _read_required_csv(tables_dir / f"summary_gate__N{n_runs}.csv")
    summary_risk = _read_required_csv(tables_dir / f"summary_risk__N{n_runs}.csv")
    summary_delay_attribution = _read_required_csv(tables_dir / f"summary_delay_attribution__N{n_runs}.csv")
    model = load_model_config(config_dir)
    sensitivity_tables = _load_sensitivity_tables(tables_dir)

    tables = build_thesis_tables(
        kpi_overview=kpi_overview,
        stage_time_mix=stage_time_mix,
    )
    tables.update(build_static_appendix_tables(model))
    appendix_tables, run_count_overrides = build_results_appendix_tables(
        kpi_overview=kpi_overview,
        route_deltas=route_deltas,
        stage_time_mix=stage_time_mix,
        summary_access=summary_access,
        summary_gate=summary_gate,
        summary_risk=summary_risk,
        summary_delay_attribution=summary_delay_attribution,
        sensitivity_kyc=sensitivity_tables.get("sensitivity_kyc_servers"),
        sensitivity_redemption=sensitivity_tables.get("sensitivity_red_servers"),
        sensitivity_allowlist=sensitivity_tables.get("sensitivity_allowlist"),
    )
    tables.update(appendix_tables)
    return save_named_tables(
        tables=tables,
        outputs_dir=outputs_dir,
        n_runs=n_runs,
        run_count_overrides=run_count_overrides,
    )


def build_thesis_tables(
    *,
    kpi_overview: pd.DataFrame,
    stage_time_mix: pd.DataFrame,
) -> Dict[str, pd.DataFrame]:
    overall = _prepare_overall_table(kpi_overview)
    access = _prepare_access_table(kpi_overview)
    operational = _prepare_operational_table(kpi_overview)
    stage_drivers = build_stage_driver_table(stage_time_mix)

    return {
        "thesis_table_6_1_overall": overall,
        "thesis_table_6_2_access": access,
        "thesis_table_6_2_operational": operational,
        "thesis_table_6_3_stage_drivers": stage_drivers.copy(),
    }


def run_default_sensitivity_suite(
    *,
    config_dir: str | Path = "config",
    outputs_dir: str | Path = "outputs",
    n_runs: int = DEFAULT_SENSITIVITY_N,
    qualified_for_private_credit: bool = True,
) -> Dict[str, Path]:
    base_model = load_model_config(config_dir)
    scratch_parent = Path(outputs_dir).resolve().parent

    kyc_rows = [
        _extract_sensitivity_metrics(
            _run_summary_for_model(
                _with_stress_kyc_servers(base_model, server_count),
                n_runs=n_runs,
                qualified_for_private_credit=qualified_for_private_credit,
                scratch_parent=scratch_parent,
            ),
            tag=f"KYC_stress_servers={server_count}",
        )
        for server_count in SENSITIVITY_KYC_SERVERS
    ]
    redemption_rows = [
        _extract_sensitivity_metrics(
            _run_summary_for_model(
                _with_stress_redemption_servers(base_model, server_count),
                n_runs=n_runs,
                qualified_for_private_credit=qualified_for_private_credit,
                scratch_parent=scratch_parent,
            ),
            tag=f"REDEMPTION_stress_servers={server_count}",
        )
        for server_count in SENSITIVITY_REDEMPTION_SERVERS
    ]
    allowlist_rows = [
        _extract_sensitivity_metrics(
            _run_summary_for_model(
                _with_tokenized_allowlist_probability(base_model, pass_probability),
                n_runs=n_runs,
                qualified_for_private_credit=qualified_for_private_credit,
                scratch_parent=scratch_parent,
            ),
            tag=f"ALLOWLIST_p={pass_probability}",
        )
        for pass_probability in SENSITIVITY_ALLOWLIST_PASS_PROBS
    ]

    sensitivity_kyc = pd.concat(kyc_rows, ignore_index=True)
    sensitivity_red = pd.concat(redemption_rows, ignore_index=True)
    sensitivity_allow = pd.concat(allowlist_rows, ignore_index=True)

    tables = {
        "sensitivity_kyc_servers": apply_standard_ordering(sensitivity_kyc),
        "sensitivity_red_servers": apply_standard_ordering(sensitivity_red),
        "sensitivity_allowlist": apply_standard_ordering(sensitivity_allow),
        "sensitivity_compact_kyc": _compact_sensitivity_view(sensitivity_kyc),
        "sensitivity_compact_red": _compact_sensitivity_view(sensitivity_red),
        "sensitivity_compact_allowlist": _compact_sensitivity_view(
            sensitivity_allow,
            scenario_id="BASELINE",
            route_id="TOKENIZED",
        ),
    }
    return save_named_tables(tables=tables, outputs_dir=outputs_dir, n_runs=n_runs)


def save_named_tables(
    *,
    tables: Dict[str, pd.DataFrame],
    outputs_dir: str | Path,
    n_runs: int,
    run_count_overrides: Dict[str, int] | None = None,
) -> Dict[str, Path]:
    out_dir = Path(outputs_dir) / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, Path] = {}
    run_count_overrides = run_count_overrides or {}
    for name, df in tables.items():
        if name in STATIC_APPENDIX_TABLE_NAMES:
            path = out_dir / f"{name}.csv"
        else:
            effective_n = run_count_overrides.get(name, n_runs)
            path = out_dir / f"{name}__N{effective_n}.csv"
        df.to_csv(path, index=False)
        paths[name] = path
    return paths


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required table missing: {path}")
    return pd.read_csv(path)


def _prepare_overall_table(kpi_overview: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "total_time_days_p50",
        "time_to_cash_days_p50",
        "total_cost_mean",
    ]
    out = _select_columns(kpi_overview, cols)
    out = apply_standard_ordering(out)
    out["completion_rate_pct"] = pd.to_numeric(out["completion_rate"], errors="coerce") * 100.0
    out["exit_frozen_rate_pct"] = pd.to_numeric(out["exit_frozen_rate"], errors="coerce") * 100.0
    out = out.drop(columns=["completion_rate", "exit_frozen_rate"])
    ordered = [
        "scenario_id",
        "asset_id",
        "route_id",
        "completion_rate_pct",
        "exit_frozen_rate_pct",
        "total_time_days_p50",
        "time_to_cash_days_p50",
        "total_cost_mean",
    ]
    return _round_columns(out[ordered], {col: 2 for col in ordered if col not in {"scenario_id", "asset_id", "route_id"}})


def _prepare_access_table(kpi_overview: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "onboarding_success_rate",
        "transfer_success_rate",
        "redemption_allowed_rate",
    ]
    out = _select_columns(kpi_overview, cols)
    out = apply_standard_ordering(out)
    rename_map = {
        "onboarding_success_rate": "onboarding_success_pct",
        "transfer_success_rate": "transfer_success_pct",
        "redemption_allowed_rate": "redemption_allowed_pct",
    }
    for src, dst in rename_map.items():
        out[dst] = pd.to_numeric(out[src], errors="coerce") * 100.0
    out = out.drop(columns=list(rename_map))
    ordered = ["scenario_id", "asset_id", "route_id", *rename_map.values()]
    return _round_columns(out[ordered], {col: 2 for col in rename_map.values()})


def _prepare_operational_table(kpi_overview: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "queue_delay_hours_mean_per_run",
        "risk_delay_hours_mean_per_run",
        "exception_delay_hours_mean_per_run",
        "gate_delay_hours_mean_per_run",
    ]
    out = _select_columns(kpi_overview, cols)
    out = apply_standard_ordering(out)
    round_map = {col: 2 for col in cols if col not in {"scenario_id", "asset_id", "route_id"}}
    return _round_columns(out, round_map)


def _select_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = pd.NA
    return out[cols].copy()


def _round_columns(df: pd.DataFrame, round_map: Dict[str, int]) -> pd.DataFrame:
    out = df.copy()
    for col, digits in round_map.items():
        out[col] = pd.to_numeric(out[col], errors="coerce").round(digits)
    return out


def _run_summary_for_model(
    model: ModelConfig,
    *,
    n_runs: int,
    qualified_for_private_credit: bool,
    scratch_parent: str | Path,
) -> pd.DataFrame:
    scratch_parent = Path(scratch_parent)
    scratch_parent.mkdir(parents=True, exist_ok=True)
    scratch_dir = scratch_parent / f"sim_sensitivity_{uuid4().hex}"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir, ignore_errors=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = run_grid_and_build_reports(
            model=model,
            n_runs=n_runs,
            outputs_dir=scratch_dir,
            qualified_for_private_credit=qualified_for_private_credit,
        )
        return pd.read_csv(paths["runs_summary"])
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


def _extract_sensitivity_metrics(summary_runs: pd.DataFrame, *, tag: str) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "N",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_hours_p50",
        "total_time_hours_p50",
        "time_to_position_hours_p50",
    ]
    out = _select_columns(summary_runs, cols)
    out["tag"] = tag
    out["time_to_cash_days_p50"] = pd.to_numeric(out["time_to_cash_hours_p50"], errors="coerce") / 24.0
    out["total_time_days_p50"] = pd.to_numeric(out["total_time_hours_p50"], errors="coerce") / 24.0
    out["time_to_position_days_p50"] = pd.to_numeric(out["time_to_position_hours_p50"], errors="coerce") / 24.0
    out = out.drop(columns=["time_to_cash_hours_p50", "total_time_hours_p50", "time_to_position_hours_p50"])
    ordered = [
        "tag",
        "scenario_id",
        "asset_id",
        "route_id",
        "N",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_days_p50",
        "total_time_days_p50",
        "time_to_position_days_p50",
    ]
    return _round_columns(out[ordered], {col: 4 for col in ordered if col not in {"tag", "scenario_id", "asset_id", "route_id"}})


def _compact_sensitivity_view(
    df: pd.DataFrame,
    *,
    scenario_id: str = "STRESS",
    route_id: str | None = None,
) -> pd.DataFrame:
    out = df[df["scenario_id"] == scenario_id].copy()
    if route_id is not None:
        out = out[out["route_id"] == route_id].copy()
    ordered = [
        "tag",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_days_p50",
        "total_time_days_p50",
    ]
    return out[ordered].reset_index(drop=True)


def _load_sensitivity_tables(tables_dir: Path) -> Dict[str, pd.DataFrame]:
    sensitivity_files = {
        "sensitivity_kyc_servers": "sensitivity_kyc_servers__N*.csv",
        "sensitivity_red_servers": "sensitivity_red_servers__N*.csv",
        "sensitivity_allowlist": "sensitivity_allowlist__N*.csv",
    }
    loaded: Dict[str, pd.DataFrame] = {}
    for name, pattern in sensitivity_files.items():
        matches = sorted(tables_dir.glob(pattern), key=lambda path: path.stat().st_mtime)
        if matches:
            loaded[name] = pd.read_csv(matches[-1])
    return loaded


def _with_stress_kyc_servers(model: ModelConfig, server_count: int) -> ModelConfig:
    cfg = copy.deepcopy(model)
    new_queue = replace(
        cfg.queues.kyc_queue,
        servers=replace(cfg.queues.kyc_queue.servers, stress=int(server_count)),
    )
    new_queues = replace(cfg.queues, kyc_queue=new_queue)
    return replace(cfg, queues=new_queues)


def _with_stress_redemption_servers(model: ModelConfig, server_count: int) -> ModelConfig:
    cfg = copy.deepcopy(model)
    new_queue = replace(
        cfg.queues.redemption_queue,
        servers=replace(cfg.queues.redemption_queue.servers, stress=int(server_count)),
    )
    new_queues = replace(cfg.queues, redemption_queue=new_queue)
    return replace(cfg, queues=new_queues)


def _with_tokenized_allowlist_probability(model: ModelConfig, pass_probability: float) -> ModelConfig:
    cfg = copy.deepcopy(model)
    tokenized_route = cfg.routes["TOKENIZED"]
    eligibility_stage = tokenized_route.stages["ELIGIBILITY_GATE"]
    gating = eligibility_stage.gating or GatingSpec()
    new_stage = replace(
        eligibility_stage,
        gating=replace(gating, allowlist_pass_probability=float(pass_probability)),
    )
    new_stages = dict(tokenized_route.stages)
    new_stages["ELIGIBILITY_GATE"] = new_stage
    new_route = replace(tokenized_route, stages=new_stages)
    new_routes = dict(cfg.routes)
    new_routes["TOKENIZED"] = new_route
    return replace(cfg, routes=new_routes)
