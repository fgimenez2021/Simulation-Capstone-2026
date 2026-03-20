from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Sequence

import numpy as np
import pandas as pd

SCENARIO_ORDER = ["BASELINE", "STRESS"]
ROUTE_ORDER = ["TRADFI", "TOKENIZED"]
ASSET_ORDER = ["TBILL_MMF", "PRIVATE_CREDIT"]
GROUP_COLS = ["scenario_id", "asset_id", "route_id"]


def _ordered_categories(values: Iterable[str], preferred: Sequence[str]) -> list[str]:
    values_list = [str(v) for v in values]
    seen = set(values_list)
    ordered = [v for v in preferred if v in seen]
    tail = sorted([v for v in seen if v not in set(preferred)])
    return ordered + tail


def apply_standard_ordering(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "scenario_id" in out.columns:
        cats = _ordered_categories(out["scenario_id"].dropna().unique(), SCENARIO_ORDER)
        out["scenario_id"] = pd.Categorical(out["scenario_id"], categories=cats, ordered=True)
    if "route_id" in out.columns:
        cats = _ordered_categories(out["route_id"].dropna().unique(), ROUTE_ORDER)
        out["route_id"] = pd.Categorical(out["route_id"], categories=cats, ordered=True)
    if "asset_id" in out.columns:
        cats = _ordered_categories(out["asset_id"].dropna().unique(), ASSET_ORDER)
        out["asset_id"] = pd.Categorical(out["asset_id"], categories=cats, ordered=True)
    sort_cols = [c for c in ["scenario_id", "asset_id", "route_id"] if c in out.columns]
    return out.sort_values(sort_cols).reset_index(drop=True) if sort_cols else out


def _numeric(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)


def _percentile(series: pd.Series, p: float) -> float:
    x = _numeric(series)
    return float(np.percentile(x, p)) if len(x) else float("nan")


def _mean(series: pd.Series) -> float:
    x = _numeric(series)
    return float(np.mean(x)) if len(x) else float("nan")


def _rate(series: pd.Series) -> float:
    x = series.dropna()
    return float((x == True).mean()) if len(x) else float("nan")


def _bootstrap_ci(
    series: pd.Series,
    *,
    statistic: str = "median",
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    x = _numeric(series)
    if len(x) == 0:
        return float("nan"), float("nan")
    if len(x) == 1:
        v = float(x[0])
        return v, v
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = x[rng.integers(0, len(x), size=len(x))]
        stats[i] = np.median(sample) if statistic == "median" else float(np.mean(sample))
    lo = float(np.quantile(stats, alpha / 2))
    hi = float(np.quantile(stats, 1 - alpha / 2))
    return lo, hi


def _core_kpis(df_runs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (scenario_id, asset_id, route_id), g in df_runs.groupby(GROUP_COLS, dropna=False):
        row = {
            "scenario_id": scenario_id,
            "asset_id": asset_id,
            "route_id": route_id,
            "N_runs": int(len(g)),
            "completion_rate": _rate(g["completed"]) if "completed" in g.columns else float("nan"),
            "exit_frozen_rate": _rate(g["exit_frozen"]) if "exit_frozen" in g.columns else float("nan"),
        }

        row["total_time_hours_p10"] = _percentile(g["total_time_hours"], 10)
        row["total_time_hours_p50"] = _percentile(g["total_time_hours"], 50)
        row["total_time_hours_p90"] = _percentile(g["total_time_hours"], 90)
        row["time_to_cash_hours_p10"] = _percentile(g["time_to_cash_hours"], 10)
        row["time_to_cash_hours_p50"] = _percentile(g["time_to_cash_hours"], 50)
        row["time_to_cash_hours_p90"] = _percentile(g["time_to_cash_hours"], 90)

        row["total_explicit_cost_mean"] = _mean(g["total_explicit_cost"])
        row["total_implicit_cost_mean"] = _mean(g["total_implicit_cost"])
        row["total_cost_mean"] = row["total_explicit_cost_mean"] + row["total_implicit_cost_mean"]

        row["total_time_days_p50"] = row["total_time_hours_p50"] / 24.0
        row["time_to_cash_days_p50"] = row["time_to_cash_hours_p50"] / 24.0

        ttc_days = pd.to_numeric(g["time_to_cash_hours"], errors="coerce") / 24.0
        ttc_ci_low, ttc_ci_high = _bootstrap_ci(ttc_days, statistic="median")
        row["time_to_cash_days_p50_ci95_low"] = ttc_ci_low
        row["time_to_cash_days_p50_ci95_high"] = ttc_ci_high

        ttime_days = pd.to_numeric(g["total_time_hours"], errors="coerce") / 24.0
        ttime_ci_low, ttime_ci_high = _bootstrap_ci(ttime_days, statistic="median")
        row["total_time_days_p50_ci95_low"] = ttime_ci_low
        row["total_time_days_p50_ci95_high"] = ttime_ci_high
        rows.append(row)

    return apply_standard_ordering(pd.DataFrame(rows))


def _event_kpis(df_stages: pd.DataFrame) -> pd.DataFrame:
    if df_stages.empty:
        return pd.DataFrame(columns=GROUP_COLS + [
            "N_transfer_attempts",
            "transfer_success_rate",
            "N_redemption_attempts",
            "redemption_allowed_rate",
            "N_onboarding_runs",
            "onboarding_success_rate",
            "risk_event_rate_per_stage_row",
            "gate_event_rate_per_stage_row",
            "queue_delay_hours_mean_per_run",
            "risk_delay_hours_mean_per_run",
            "exception_delay_hours_mean_per_run",
            "gate_delay_hours_mean_per_run",
            "queue_delay_share_of_total_time_mean",
            "risk_delay_share_of_total_time_mean",
            "exception_delay_share_of_total_time_mean",
            "gate_delay_share_of_total_time_mean",
        ])

    tmp = df_stages.copy()
    tmp["has_risk_event"] = tmp["risk_events"].fillna("").astype(str).str.len() > 0
    tmp["has_gate_marker"] = tmp["gate_events"].fillna("").astype(str).str.len() > 0

    stage_rates = (
        tmp.groupby(GROUP_COLS, dropna=False)
        .agg(
            risk_event_rate_per_stage_row=("has_risk_event", "mean"),
            gate_event_rate_per_stage_row=("has_gate_marker", "mean"),
        )
        .reset_index()
    )

    transfer_rows = tmp[tmp["stage_id"] == "TRANSFERABILITY"].copy()
    transfer_rows = transfer_rows[transfer_rows["transfer_attempted"] == True]

    if transfer_rows.empty:
        transfer = pd.DataFrame(columns=GROUP_COLS + ["N_transfer_attempts", "transfer_success_rate"])
    else:
        transfer = (
            transfer_rows.groupby(GROUP_COLS, dropna=False)
            .agg(
                N_transfer_attempts=("transfer_attempted", "size"),
                transfer_success_rate=("transfer_success", "mean"),
            )
            .reset_index()
        )

    redemption_rows = tmp[tmp["stage_id"] == "REDEMPTION_PROCESSING"].copy()
    redemption_rows = redemption_rows[redemption_rows["redemption_attempted"] == True]
    if redemption_rows.empty:
        redemption = pd.DataFrame(columns=GROUP_COLS + ["N_redemption_attempts", "redemption_allowed_rate"])
    else:
        redemption = (
            redemption_rows.groupby(GROUP_COLS, dropna=False)
            .agg(
                N_redemption_attempts=("redemption_attempted", "size"),
                redemption_allowed_rate=("redemption_success", "mean"),
            )
            .reset_index()
        )

    onboarding_stage_ids = {"ONBOARDING", "KYC_REVIEW", "ELIGIBILITY_GATE"}
    onboarding_rows = tmp[tmp["stage_id"].isin(onboarding_stage_ids)].copy()
    if onboarding_rows.empty:
        onboarding = pd.DataFrame(columns=GROUP_COLS + ["N_onboarding_runs", "onboarding_success_rate"])
    else:
        by_run = (
            onboarding_rows.groupby(GROUP_COLS + ["run_id"], dropna=False)
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
            by_run.groupby(GROUP_COLS, dropna=False)
            .agg(
                N_onboarding_runs=("run_id", "size"),
                onboarding_success_rate=("onboarding_success", "mean"),
            )
            .reset_index()
        )

    for c in ["time_hours", "queue_delay_hours", "risk_delay_hours", "exception_delay_hours", "gate_delay_hours"]:
        if c not in tmp.columns:
            tmp[c] = 0.0
        tmp[c] = pd.to_numeric(tmp[c], errors="coerce").fillna(0.0)

    by_run_delay = (
        tmp.groupby(GROUP_COLS + ["run_id"], dropna=False)
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
        numer = by_run_delay[f"{comp}_hours"]
        denom = by_run_delay["total_time_hours"]
        by_run_delay[f"{comp}_share_of_total_time"] = np.where(denom > 0, numer / denom, np.nan)

    delay = (
        by_run_delay.groupby(GROUP_COLS, dropna=False)
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

    out = stage_rates.merge(transfer, on=GROUP_COLS, how="left")
    out = out.merge(redemption, on=GROUP_COLS, how="left")
    out = out.merge(onboarding, on=GROUP_COLS, how="left")
    out = out.merge(delay, on=GROUP_COLS, how="left")
    out["N_transfer_attempts"] = pd.to_numeric(out["N_transfer_attempts"], errors="coerce").fillna(0).astype(int)
    out["N_redemption_attempts"] = pd.to_numeric(out["N_redemption_attempts"], errors="coerce").fillna(0).astype(int)
    out["N_onboarding_runs"] = pd.to_numeric(out["N_onboarding_runs"], errors="coerce").fillna(0).astype(int)
    return apply_standard_ordering(out)


def _route_deltas(df_kpi_overview: pd.DataFrame) -> pd.DataFrame:
    if df_kpi_overview.empty:
        return pd.DataFrame()

    idx = ["scenario_id", "asset_id"]
    metric_cols = [
        "time_to_cash_days_p50",
        "total_time_days_p50",
        "total_cost_mean",
        "completion_rate",
        "exit_frozen_rate",
        "onboarding_success_rate",
        "transfer_success_rate",
        "redemption_allowed_rate",
        "risk_event_rate_per_stage_row",
        "gate_event_rate_per_stage_row",
        "queue_delay_hours_mean_per_run",
        "risk_delay_hours_mean_per_run",
        "exception_delay_hours_mean_per_run",
        "gate_delay_hours_mean_per_run",
    ]

    wide = df_kpi_overview[idx + ["route_id"] + metric_cols].pivot_table(
        index=idx,
        columns="route_id",
        values=metric_cols,
        aggfunc="first",
        observed=False,
    )

    rows: list[dict] = []
    for key in wide.index:
        row = {"scenario_id": key[0], "asset_id": key[1]}
        for m in metric_cols:
            trad = wide[(m, "TRADFI")] if (m, "TRADFI") in wide.columns else np.nan
            tok = wide[(m, "TOKENIZED")] if (m, "TOKENIZED") in wide.columns else np.nan
            if hasattr(trad, "loc"):
                trad = trad.loc[key]
            if hasattr(tok, "loc"):
                tok = tok.loc[key]
            row[f"tradfi_{m}"] = trad
            row[f"tokenized_{m}"] = tok
            row[f"delta_{m}"] = float(tok - trad) if pd.notna(tok) and pd.notna(trad) else float("nan")
            if pd.notna(trad) and float(trad) != 0.0 and pd.notna(tok):
                row[f"pct_change_{m}"] = float((tok - trad) / trad * 100.0)
            else:
                row[f"pct_change_{m}"] = float("nan")

        row["delta_completion_rate_pp"] = row["delta_completion_rate"] * 100.0
        row["delta_exit_frozen_rate_pp"] = row["delta_exit_frozen_rate"] * 100.0
        row["delta_onboarding_success_rate_pp"] = row["delta_onboarding_success_rate"] * 100.0
        row["delta_transfer_success_rate_pp"] = row["delta_transfer_success_rate"] * 100.0
        row["delta_redemption_allowed_rate_pp"] = row["delta_redemption_allowed_rate"] * 100.0
        row["delta_risk_event_rate_per_stage_row_pp"] = row["delta_risk_event_rate_per_stage_row"] * 100.0
        row["delta_gate_event_rate_per_stage_row_pp"] = row["delta_gate_event_rate_per_stage_row"] * 100.0
        rows.append(row)

    return apply_standard_ordering(pd.DataFrame(rows))


def _stage_time_mix(df_stages: pd.DataFrame) -> pd.DataFrame:
    if df_stages.empty:
        return pd.DataFrame()

    agg = (
        df_stages.groupby(GROUP_COLS + ["stage_id"], dropna=False)
        .agg(
            stage_time_hours_mean=("time_hours", "mean"),
            stage_time_hours_p50=("time_hours", "median"),
            stage_order_hint=("stage_index", "median"),
        )
        .reset_index()
    )

    agg["cell_total_stage_time_mean"] = agg.groupby(GROUP_COLS)["stage_time_hours_mean"].transform("sum")
    agg["stage_time_share_pct"] = np.where(
        agg["cell_total_stage_time_mean"] > 0,
        agg["stage_time_hours_mean"] / agg["cell_total_stage_time_mean"] * 100.0,
        np.nan,
    )
    out = apply_standard_ordering(agg)
    return out.sort_values(["scenario_id", "asset_id", "route_id", "stage_order_hint", "stage_id"]).reset_index(drop=True)


def _kpi_glossary() -> pd.DataFrame:
    rows = [
        ("time_to_cash_days_p50", "Median time from start to cash availability", "days", "lower_better"),
        ("total_time_days_p50", "Median total lifecycle processing time", "days", "lower_better"),
        ("total_cost_mean", "Mean explicit + implicit lifecycle cost", "relative cost units", "lower_better"),
        ("completion_rate", "Share of runs completing lifecycle", "rate [0,1]", "higher_better"),
        ("exit_frozen_rate", "Share of runs ending with frozen exit", "rate [0,1]", "lower_better"),
        ("onboarding_success_rate", "Share of runs that clear onboarding-related gates", "rate [0,1]", "higher_better"),
        ("transfer_success_rate", "Share of transfer attempts that succeed", "rate [0,1]", "higher_better"),
        ("redemption_allowed_rate", "Share of redemption attempts marked allowed", "rate [0,1]", "higher_better"),
        ("risk_event_rate_per_stage_row", "Stage-row share containing >=1 risk event", "rate [0,1]", "lower_better"),
        (
            "gate_event_rate_per_stage_row",
            "Stage-row share containing >=1 logged gate check/outcome (includes successful checks)",
            "rate [0,1]",
            "context_dependent",
        ),
        ("queue_delay_hours_mean_per_run", "Mean queue-induced delay injected into lifecycle", "hours", "lower_better"),
        ("risk_delay_hours_mean_per_run", "Mean delay caused by risk event time impacts", "hours", "lower_better"),
        ("exception_delay_hours_mean_per_run", "Mean delay from exception-handling overhead", "hours", "lower_better"),
        ("gate_delay_hours_mean_per_run", "Mean delay caused by deterministic gating rules", "hours", "lower_better"),
        ("delta_*", "Tokenized minus TradFi (same scenario and asset)", "metric-specific", "negative_better_for_time_cost_risk_freeze"),
    ]
    return pd.DataFrame(rows, columns=["metric_name", "definition", "units", "direction_when_comparing_tokenized_minus_tradfi"])


def _headline_conclusions(df_route_deltas: pd.DataFrame) -> pd.DataFrame:
    """
    Compact thesis-ready summary table with the main route deltas per cell.
    """
    if df_route_deltas.empty:
        return pd.DataFrame(
            columns=[
                "scenario_id",
                "asset_id",
                "delta_time_to_cash_days_p50",
                "pct_change_time_to_cash_days_p50",
                "delta_total_time_days_p50",
                "pct_change_total_time_days_p50",
                "delta_total_cost_mean",
                "pct_change_total_cost_mean",
                "delta_completion_rate_pp",
                "delta_exit_frozen_rate_pp",
                "delta_onboarding_success_rate_pp",
                "delta_transfer_success_rate_pp",
                "delta_redemption_allowed_rate_pp",
                "delta_risk_event_rate_per_stage_row_pp",
            ]
        )

    cols = [
        "scenario_id",
        "asset_id",
        "delta_time_to_cash_days_p50",
        "pct_change_time_to_cash_days_p50",
        "delta_total_time_days_p50",
        "pct_change_total_time_days_p50",
        "delta_total_cost_mean",
        "pct_change_total_cost_mean",
        "delta_completion_rate_pp",
        "delta_exit_frozen_rate_pp",
        "delta_onboarding_success_rate_pp",
        "delta_transfer_success_rate_pp",
        "delta_redemption_allowed_rate_pp",
        "delta_risk_event_rate_per_stage_row_pp",
    ]
    out = df_route_deltas.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    out = apply_standard_ordering(out[cols])

    numeric_cols = [c for c in cols if c not in {"scenario_id", "asset_id"}]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").round(4)
    return out


def build_analysis_tables(df_runs: pd.DataFrame, df_stages: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    core = _core_kpis(df_runs=df_runs)
    events = _event_kpis(df_stages=df_stages)
    kpi_overview = apply_standard_ordering(core.merge(events, on=GROUP_COLS, how="left"))
    route_deltas = _route_deltas(kpi_overview)
    headline_conclusions = _headline_conclusions(route_deltas)
    stage_mix = _stage_time_mix(df_stages)
    return {
        "kpi_overview": kpi_overview,
        "route_deltas": route_deltas,
        "headline_conclusions": headline_conclusions,
        "stage_time_mix": stage_mix,
        "kpi_glossary": _kpi_glossary(),
    }


def save_analysis_tables(
    *,
    tables: Dict[str, pd.DataFrame],
    outputs_dir: str | Path,
    n_runs: int,
) -> Dict[str, Path]:
    out_dir = Path(outputs_dir) / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: Dict[str, Path] = {}
    for name, df in tables.items():
        if name == "kpi_glossary":
            path = out_dir / "kpi_glossary.csv"
        else:
            path = out_dir / f"{name}__N{n_runs}.csv"
        df.to_csv(path, index=False)
        paths[name] = path
    return paths
