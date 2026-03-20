from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd


def _percentiles(series: pd.Series, ps: Sequence[float]) -> Dict[str, float]:
    """
    Robust percentile calculation that ignores NaNs.
    ps should be in [0, 100], e.g. [10, 50, 90]
    """
    x = pd.to_numeric(series, errors="coerce").dropna().to_numpy()
    if len(x) == 0:
        return {f"p{int(p)}": np.nan for p in ps}
    vals = np.percentile(x, ps)
    return {f"p{int(p)}": float(v) for p, v in zip(ps, vals)}


def _safe_mean(series: pd.Series) -> float:
    x = pd.to_numeric(series, errors="coerce").dropna()
    return float(x.mean()) if len(x) else float("nan")


def _safe_rate(series_bool: pd.Series) -> float:
    x = series_bool.dropna()
    if len(x) == 0:
        return float("nan")
    return float((x == True).mean())

RUN_METRICS_DEFAULT = [
    "total_time_hours",
    "time_to_position_hours",
    "time_to_cash_hours",
    "total_explicit_cost",
    "total_implicit_cost",
    "total_approvals",
    "total_handoffs",
    "intermediaries_count",
]


def summarize_runs(
    df_runs: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
    percentiles: Sequence[float] = (10, 50, 90),
    tail_thresholds_hours: Sequence[float] = (24 * 7, 24 * 30),
) -> pd.DataFrame:
    """
    Create a summary table from run-level outputs.

    Outputs include:
    - N, completion rate, exit_frozen rate
    - mean + percentile stats for key metrics
    - tail probabilities for time_to_cash_hours exceeding thresholds
    """
    missing = [c for c in group_cols if c not in df_runs.columns]
    if missing:
        raise ValueError(f"df_runs missing required group columns: {missing}")

    out_rows: List[dict] = []

    for keys, g in df_runs.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: key for col, key in zip(group_cols, keys)}
        row["N"] = int(len(g))

        row["completion_rate"] = _safe_rate(g["completed"]) if "completed" in g.columns else float("nan")
        row["exit_frozen_rate"] = _safe_rate(g["exit_frozen"]) if "exit_frozen" in g.columns else float("nan")

        for m in RUN_METRICS_DEFAULT:
            if m not in g.columns:
                continue

            row[f"{m}_mean"] = _safe_mean(g[m])
            pmap = _percentiles(g[m], percentiles)
            for pk, pv in pmap.items():
                row[f"{m}_{pk}"] = pv

        if "time_to_cash_hours" in g.columns:
            ttc = pd.to_numeric(g["time_to_cash_hours"], errors="coerce")
            for thr in tail_thresholds_hours:
                col = f"p_time_to_cash_gt_{int(thr)}h"
                valid = ttc.dropna()
                row[col] = float((valid > thr).mean()) if len(valid) else float("nan")

        out_rows.append(row)

    return pd.DataFrame(out_rows).sort_values(list(group_cols)).reset_index(drop=True)


def summarize_transferability(
    df_stages: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
) -> pd.DataFrame:
    """
    Summarize transfer outcomes using stage-level outputs.
    Only looks at rows where stage_id == 'TRANSFERABILITY' and transfer_attempted == True.
    """
    required = list(group_cols) + ["stage_id"]
    missing = [c for c in required if c not in df_stages.columns]
    if missing:
        raise ValueError(f"df_stages missing required columns: {missing}")

    gdf = df_stages[df_stages["stage_id"] == "TRANSFERABILITY"].copy()
    if "transfer_attempted" in gdf.columns:
        gdf = gdf[gdf["transfer_attempted"] == True]

    out_rows: List[dict] = []

    for keys, g in gdf.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: key for col, key in zip(group_cols, keys)}
        row["N_transfer_attempts"] = int(len(g))

        if "transfer_success" in g.columns:
            ts = g["transfer_success"]
            row["transfer_success_rate"] = _safe_rate(ts)
        else:
            row["transfer_success_rate"] = float("nan")

        out_rows.append(row)

    if not out_rows:
        cols = list(group_cols) + ["N_transfer_attempts", "transfer_success_rate"]
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(out_rows).sort_values(list(group_cols)).reset_index(drop=True)


def summarize_risk_events(
    df_stages: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
) -> pd.DataFrame:
    """
    Summarize risk events frequency by counting non-empty risk_events strings.
    This is a simple proxy for "how often exceptions happen".
    """
    required = list(group_cols) + ["risk_events"]
    missing = [c for c in required if c not in df_stages.columns]
    if missing:
        raise ValueError(f"df_stages missing required columns: {missing}")

    tmp = df_stages.copy()
    tmp["has_risk_event"] = tmp["risk_events"].fillna("").astype(str).str.len() > 0

    out_rows: List[dict] = []
    for keys, g in tmp.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: key for col, key in zip(group_cols, keys)}
        row["N_stage_rows"] = int(len(g))
        row["risk_event_rate_per_stage_row"] = float(g["has_risk_event"].mean()) if len(g) else float("nan")

        events = set()
        for s in g["risk_events"].fillna("").astype(str):
            if not s:
                continue
            for part in s.split(";"):
                part = part.strip()
                if part:
                    events.add(part)
        row["unique_risk_event_ids_observed"] = ";".join(sorted(events)) if events else ""

        out_rows.append(row)

    return pd.DataFrame(out_rows).sort_values(list(group_cols)).reset_index(drop=True)


def summarize_gate_events(
    df_stages: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
) -> pd.DataFrame:
    """
    Summarize logged structural gate checks separately from risk events.

    The public column name gate_event_rate_per_stage_row is kept for backward
    compatibility, but it counts any logged gate marker, including successful
    transfer/redemption checks.
    """
    required = list(group_cols) + ["gate_events"]
    missing = [c for c in required if c not in df_stages.columns]
    if missing:
        raise ValueError(f"df_stages missing required columns: {missing}")

    tmp = df_stages.copy()
    tmp["has_gate_marker"] = tmp["gate_events"].fillna("").astype(str).str.len() > 0

    out_rows: List[dict] = []
    for keys, g in tmp.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)

        row = {col: key for col, key in zip(group_cols, keys)}
        row["N_stage_rows"] = int(len(g))
        row["gate_event_rate_per_stage_row"] = float(g["has_gate_marker"].mean()) if len(g) else float("nan")

        events = set()
        for s in g["gate_events"].fillna("").astype(str):
            if not s:
                continue
            for part in s.split(";"):
                part = part.strip()
                if part:
                    events.add(part)
        row["unique_gate_event_ids_observed"] = ";".join(sorted(events)) if events else ""

        out_rows.append(row)

    return pd.DataFrame(out_rows).sort_values(list(group_cols)).reset_index(drop=True)


def summarize_access_permissions(
    df_stages: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
) -> pd.DataFrame:
    """
    Summarize access/permission outcomes:
      - onboarding success rate (gate denials in onboarding-related stages)
      - transfer success rate
      - redemption allowed rate
    """
    required = list(group_cols) + ["run_id", "stage_id", "gate_events"]
    missing = [c for c in required if c not in df_stages.columns]
    if missing:
        raise ValueError(f"df_stages missing required columns: {missing}")

    tmp = df_stages.copy()

    out = (
        tmp.groupby(list(group_cols), dropna=False)
        .size()
        .reset_index(name="_rows")
        .drop(columns=["_rows"])
    )

    onboarding_stage_ids = {"ONBOARDING", "KYC_REVIEW", "ELIGIBILITY_GATE"}
    onb = tmp[tmp["stage_id"].isin(onboarding_stage_ids)].copy()
    if onb.empty:
        onboarding = pd.DataFrame(columns=list(group_cols) + ["N_onboarding_runs", "onboarding_success_rate"])
    else:
        by_run = (
            onb.groupby(list(group_cols) + ["run_id"], dropna=False)
            .agg(
                onboarding_failed=(
                    "gate_events",
                    lambda s: s.fillna("").astype(str).str.contains("GATE_DENIED", regex=False).any(),
                ),
            )
            .reset_index()
        )
        by_run["onboarding_success"] = ~by_run["onboarding_failed"]
        onboarding = (
            by_run.groupby(list(group_cols), dropna=False)
            .agg(
                N_onboarding_runs=("run_id", "size"),
                onboarding_success_rate=("onboarding_success", "mean"),
            )
            .reset_index()
        )

    transfer = tmp[tmp["stage_id"] == "TRANSFERABILITY"].copy()
    if "transfer_attempted" in transfer.columns:
        transfer = transfer[transfer["transfer_attempted"] == True]
    if transfer.empty:
        transfer_summary = pd.DataFrame(columns=list(group_cols) + ["N_transfer_attempts", "transfer_success_rate"])
    else:
        transfer_summary = (
            transfer.groupby(list(group_cols), dropna=False)
            .agg(
                N_transfer_attempts=("transfer_attempted", "size"),
                transfer_success_rate=("transfer_success", "mean"),
            )
            .reset_index()
        )

    red = tmp[tmp["stage_id"] == "REDEMPTION_PROCESSING"].copy()
    if "redemption_attempted" in red.columns:
        red = red[red["redemption_attempted"] == True]
    if red.empty:
        red_summary = pd.DataFrame(columns=list(group_cols) + ["N_redemption_attempts", "redemption_allowed_rate"])
    else:
        red_summary = (
            red.groupby(list(group_cols), dropna=False)
            .agg(
                N_redemption_attempts=("redemption_attempted", "size"),
                redemption_allowed_rate=("redemption_success", "mean"),
            )
            .reset_index()
        )

    out = out.merge(onboarding, on=list(group_cols), how="left")
    out = out.merge(transfer_summary, on=list(group_cols), how="left")
    out = out.merge(red_summary, on=list(group_cols), how="left")
    out["N_onboarding_runs"] = pd.to_numeric(out["N_onboarding_runs"], errors="coerce").fillna(0).astype(int)
    out["N_transfer_attempts"] = pd.to_numeric(out["N_transfer_attempts"], errors="coerce").fillna(0).astype(int)
    out["N_redemption_attempts"] = pd.to_numeric(out["N_redemption_attempts"], errors="coerce").fillna(0).astype(int)
    return out.sort_values(list(group_cols)).reset_index(drop=True)


def summarize_delay_attribution(
    df_stages: pd.DataFrame,
    group_cols: Sequence[str] = ("scenario_id", "asset_id", "route_id"),
) -> pd.DataFrame:
    """
    Summarize delay attribution using stage-level delay components.
    """
    required = list(group_cols) + ["run_id", "time_hours"]
    missing = [c for c in required if c not in df_stages.columns]
    if missing:
        raise ValueError(f"df_stages missing required columns: {missing}")

    tmp = df_stages.copy()
    for c in ["time_hours", "queue_delay_hours", "risk_delay_hours", "exception_delay_hours", "gate_delay_hours"]:
        if c not in tmp.columns:
            tmp[c] = 0.0
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce").fillna(0.0)

    by_run = (
        tmp.groupby(list(group_cols) + ["run_id"], dropna=False)
        .agg(
            total_time_hours=("time_hours", "sum"),
            queue_delay_hours=("queue_delay_hours", "sum"),
            risk_delay_hours=("risk_delay_hours", "sum"),
            exception_delay_hours=("exception_delay_hours", "sum"),
            gate_delay_hours=("gate_delay_hours", "sum"),
        )
        .reset_index()
    )
    for comp in ["queue_delay", "risk_delay", "exception_delay", "gate_delay"]:
        numer = by_run[f"{comp}_hours"]
        denom = by_run["total_time_hours"]
        by_run[f"{comp}_share_of_total_time"] = np.where(denom > 0, numer / denom, np.nan)

    out = (
        by_run.groupby(list(group_cols), dropna=False)
        .agg(
            queue_delay_hours_mean_per_run=("queue_delay_hours", "mean"),
            risk_delay_hours_mean_per_run=("risk_delay_hours", "mean"),
            exception_delay_hours_mean_per_run=("exception_delay_hours", "mean"),
            gate_delay_hours_mean_per_run=("gate_delay_hours", "mean"),
            queue_delay_share_of_total_time_mean=("queue_delay_share_of_total_time", "mean"),
            risk_delay_share_of_total_time_mean=("risk_delay_share_of_total_time", "mean"),
            exception_delay_share_of_total_time_mean=("exception_delay_share_of_total_time", "mean"),
            gate_delay_share_of_total_time_mean=("gate_delay_share_of_total_time", "mean"),
        )
        .reset_index()
    )
    return out.sort_values(list(group_cols)).reset_index(drop=True)


def load_outputs(
    runs_csv_path: str,
    stages_csv_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load outputs produced by sim/runner.py.
    """
    df_runs = pd.read_csv(runs_csv_path)
    df_stages = pd.read_csv(stages_csv_path)
    return df_runs, df_stages
