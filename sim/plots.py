from __future__ import annotations

from pathlib import Path
from typing import Dict
import glob

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import numpy as np
import seaborn as sns

from .analysis import ASSET_ORDER, ROUTE_ORDER, SCENARIO_ORDER, apply_standard_ordering

ROUTE_PALETTE = {
    "TRADFI": "#1f4e79",
    "TOKENIZED": "#e07a1f",
}


def _combo_order(df: pd.DataFrame) -> list[tuple[str, str]]:
    scenarios = [s for s in SCENARIO_ORDER if s in set(df["scenario_id"].astype(str))]
    scenarios += sorted([s for s in set(df["scenario_id"].astype(str)) if s not in scenarios])
    assets = [a for a in ASSET_ORDER if a in set(df["asset_id"].astype(str))]
    assets += sorted([a for a in set(df["asset_id"].astype(str)) if a not in assets])
    return [(s, a) for s in scenarios for a in assets]


def _grouped_positions(
    n_groups: int,
    routes: list[str],
    width: float = 0.34,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    base = np.arange(n_groups, dtype=float)
    n_routes = len(routes)
    offsets = np.linspace(-(n_routes - 1) / 2, (n_routes - 1) / 2, n_routes) * width
    positions = {route: base + offsets[i] for i, route in enumerate(routes)}
    return base, positions


def _setup_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        context="notebook",
        rc={
            "axes.facecolor": "#f8f9fb",
            "figure.facecolor": "#ffffff",
            "grid.color": "#d9dbe2",
            "grid.alpha": 0.35,
            "axes.edgecolor": "#c8ccd7",
            "axes.linewidth": 0.8,
            "font.size": 10.5,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "legend.fontsize": 10,
        },
    )


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(axis="y", alpha=0.3, zorder=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def generate_all_figures(
    *,
    outputs_dir: str | Path = "outputs",
    n_runs: int = 50,
) -> Dict[str, Path]:
    outputs_dir = Path(outputs_dir)
    tables_dir = outputs_dir / "tables"
    figs_dir = outputs_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    kpi_path = tables_dir / f"kpi_overview__N{n_runs}.csv"
    deltas_path = tables_dir / f"route_deltas__N{n_runs}.csv"
    stage_mix_path = tables_dir / f"stage_time_mix__N{n_runs}.csv"
    if not kpi_path.exists() or not deltas_path.exists():
        raise FileNotFoundError(
            f"Missing required analysis tables. Expected {kpi_path.name} and {deltas_path.name} in {tables_dir}."
        )

    kpi = apply_standard_ordering(pd.read_csv(kpi_path))
    deltas = apply_standard_ordering(pd.read_csv(deltas_path))
    stage_mix = (
        pd.read_csv(stage_mix_path, sep=None, engine="python")
        if stage_mix_path.exists()
        else pd.DataFrame()
    )
    stage_rows = _load_stage_rows(outputs_dir=outputs_dir, n_runs=n_runs)

    _setup_theme()

    out: Dict[str, Path] = {}
    out["fig_kpi_time_to_cash"] = _plot_time_to_cash_with_ci(kpi, figs_dir)
    out["fig_kpi_total_cost"] = _plot_total_cost(kpi, figs_dir)
    out["fig_kpi_operational_rates"] = _plot_operational_rates(kpi, figs_dir)
    out["fig_kpi_route_deltas_heatmap"] = _plot_route_deltas_heatmap(deltas, figs_dir)
    if not stage_mix.empty:
        out["fig_kpi_stage_bottleneck_mix"] = _plot_stage_bottleneck_mix(stage_mix, figs_dir)
    if not stage_rows.empty:
        out["fig_kpi_stage_time_distribution_top4"] = _plot_stage_time_distribution_top4(stage_rows, figs_dir)
        wf_paths = _plot_stage_delta_waterfalls(stage_rows, figs_dir)
        out.update(wf_paths)
        out["fig_kpi_event_composition"] = _plot_event_composition(stage_rows, figs_dir)
    return out


def _load_stage_rows(*, outputs_dir: Path, n_runs: int) -> pd.DataFrame:
    stage_files = sorted(glob.glob(str(outputs_dir / "stages" / f"stages_*__N{n_runs}.csv")))
    if not stage_files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(p) for p in stage_files], ignore_index=True)
    return apply_standard_ordering(df)


def _plot_time_to_cash_with_ci(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {
        "scenario_id",
        "asset_id",
        "route_id",
        "time_to_cash_days_p50",
        "time_to_cash_days_p50_ci95_low",
        "time_to_cash_days_p50_ci95_high",
    }
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for time-to-cash figure: {required - set(df.columns)}")

    combos = _combo_order(df)
    routes = [r for r in ROUTE_ORDER if r in set(df["route_id"].astype(str))]
    base, positions = _grouped_positions(len(combos), routes)

    fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
    for route in routes:
        y_vals = []
        err_low = []
        err_high = []
        for scenario, asset in combos:
            row = df[
                (df["scenario_id"].astype(str) == scenario)
                & (df["asset_id"].astype(str) == asset)
                & (df["route_id"].astype(str) == route)
            ]
            if row.empty:
                y_vals.append(np.nan)
                err_low.append(np.nan)
                err_high.append(np.nan)
                continue
            y = float(row["time_to_cash_days_p50"].iloc[0])
            lo = float(row["time_to_cash_days_p50_ci95_low"].iloc[0])
            hi = float(row["time_to_cash_days_p50_ci95_high"].iloc[0])
            y_vals.append(y)
            err_low.append(max(y - lo, 0.0))
            err_high.append(max(hi - y, 0.0))
        ax.bar(
            positions[route],
            y_vals,
            width=0.34,
            label=route,
            color=ROUTE_PALETTE.get(route, "#999999"),
            edgecolor="white",
            linewidth=0.6,
            zorder=2,
        )
        ax.errorbar(
            positions[route],
            y_vals,
            yerr=[err_low, err_high],
            fmt="none",
            color="#1a1a1a",
            capsize=3,
            lw=1.1,
            zorder=3,
        )

    labels = [f"{s}\n{a}" for s, a in combos]
    ax.set_xticks(base)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Median Time to Cash (days)")
    ax.set_xlabel("Scenario and Asset")
    ax.set_title("Median Time to Cash by Route with 95% Bootstrap CI (days)")
    ax.legend(title="Route", loc="upper right", frameon=False)
    _style_axes(ax)

    path = figs_dir / "fig_kpi_time_to_cash_days_ci95.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_total_cost(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {"scenario_id", "asset_id", "route_id", "total_cost_mean"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for total-cost figure: {required - set(df.columns)}")

    combos = _combo_order(df)
    routes = [r for r in ROUTE_ORDER if r in set(df["route_id"].astype(str))]
    base, positions = _grouped_positions(len(combos), routes)

    fig, ax = plt.subplots(figsize=(12, 6.2), constrained_layout=True)
    for route in routes:
        y_vals = []
        for scenario, asset in combos:
            row = df[
                (df["scenario_id"].astype(str) == scenario)
                & (df["asset_id"].astype(str) == asset)
                & (df["route_id"].astype(str) == route)
            ]
            y_vals.append(float(row["total_cost_mean"].iloc[0]) if not row.empty else np.nan)
        ax.bar(
            positions[route],
            y_vals,
            width=0.34,
            label=route,
            color=ROUTE_PALETTE.get(route, "#999999"),
            edgecolor="white",
            linewidth=0.6,
        )

    labels = [f"{s}\n{a}" for s, a in combos]
    ax.set_xticks(base)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Mean Total Cost (relative units)")
    ax.set_xlabel("Scenario and Asset")
    ax.set_title("Mean Total Lifecycle Cost by Route (relative units)")
    ax.legend(title="Route", loc="upper right", frameon=False)
    _style_axes(ax)

    path = figs_dir / "fig_kpi_total_cost_mean.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_operational_rates(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {
        "scenario_id",
        "asset_id",
        "route_id",
        "completion_rate",
        "transfer_success_rate",
        "exit_frozen_rate",
    }
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for operational-rates figure: {required - set(df.columns)}")

    combos = _combo_order(df)
    routes = [r for r in ROUTE_ORDER if r in set(df["route_id"].astype(str))]
    base, positions = _grouped_positions(len(combos), routes)

    metrics = [
        ("completion_rate", "Completion Rate (%)"),
        ("transfer_success_rate", "Transfer Success Rate (%)"),
        ("exit_frozen_rate", "Exit Frozen Rate (%)"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.8), constrained_layout=False, sharex=True)
    for ax, (metric_col, metric_label) in zip(axes, metrics):
        for route in routes:
            y_vals = []
            for scenario, asset in combos:
                row = df[
                    (df["scenario_id"].astype(str) == scenario)
                    & (df["asset_id"].astype(str) == asset)
                    & (df["route_id"].astype(str) == route)
                ]
                y = float(row[metric_col].iloc[0]) * 100.0 if not row.empty else np.nan
                y_vals.append(y)
            ax.bar(
                positions[route],
                y_vals,
                width=0.34,
                color=ROUTE_PALETTE.get(route, "#999999"),
                label=route,
                edgecolor="white",
                linewidth=0.6,
            )

        ax.set_title(metric_label)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        _style_axes(ax)
        ax.set_xticks(base)
        ax.set_xticklabels([f"{s}\n{a}" for s, a in combos], fontsize=9)
        ax.set_xlabel("Scenario and Asset")

    axes[0].set_ylabel("Rate (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        title="Route",
        loc="upper center",
        bbox_to_anchor=(0.5, 0.92),
        ncol=len(routes),
        frameon=False,
    )
    fig.suptitle("Operational Outcome Rates by Route, Scenario, and Asset", y=0.985, fontsize=13)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.80])

    path = figs_dir / "fig_kpi_operational_rates.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_route_deltas_heatmap(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {
        "scenario_id",
        "asset_id",
        "delta_time_to_cash_days_p50",
        "delta_total_time_days_p50",
        "delta_total_cost_mean",
        "delta_completion_rate_pp",
        "delta_exit_frozen_rate_pp",
        "delta_transfer_success_rate_pp",
    }
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for route-delta heatmap: {required - set(df.columns)}")

    d = apply_standard_ordering(df)
    d["cell"] = d["scenario_id"].astype(str) + " | " + d["asset_id"].astype(str)
    heat = d.set_index("cell")[
        [
            "delta_time_to_cash_days_p50",
            "delta_total_time_days_p50",
            "delta_total_cost_mean",
            "delta_completion_rate_pp",
            "delta_exit_frozen_rate_pp",
            "delta_transfer_success_rate_pp",
        ]
    ].rename(columns={
        "delta_time_to_cash_days_p50": "Delta Time to Cash (days)",
        "delta_total_time_days_p50": "Delta Total Time (days)",
        "delta_total_cost_mean": "Delta Total Cost (rel units)",
        "delta_completion_rate_pp": "Delta Completion (pp)",
        "delta_exit_frozen_rate_pp": "Delta Exit Frozen (pp)",
        "delta_transfer_success_rate_pp": "Delta Transfer Success (pp)",
    })

    fig, ax = plt.subplots(figsize=(11.5, 4.8), constrained_layout=True)
    sns.heatmap(
        heat,
        cmap="RdBu_r",
        center=0.0,
        annot=True,
        fmt=".2f",
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "Tokenized - TradFi"},
        ax=ax,
    )
    ax.set_title("Route Delta Heatmap (Tokenized - TradFi): Negative is Better for Time/Cost/Exit Frozen")
    ax.set_xlabel("Metric")
    ax.set_ylabel("Scenario | Asset")

    path = figs_dir / "fig_kpi_route_deltas_heatmap.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_stage_bottleneck_mix(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {"scenario_id", "asset_id", "route_id", "stage_id", "stage_time_share_pct"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for stage bottleneck figure: {required - set(df.columns)}")

    d = apply_standard_ordering(df)
    top_stage = (
        d.sort_values("stage_time_share_pct", ascending=False)
        .groupby(["scenario_id", "asset_id", "route_id"], as_index=False, observed=False)
        .first()[["scenario_id", "asset_id", "route_id", "stage_id", "stage_time_share_pct"]]
    )
    top_stage["cell"] = top_stage["scenario_id"].astype(str) + " | " + top_stage["asset_id"].astype(str)
    labels = list(dict.fromkeys(top_stage["cell"].tolist()))
    route_order = [r for r in ROUTE_ORDER if r in set(top_stage["route_id"].astype(str))]
    base, positions = _grouped_positions(len(labels), route_order)

    fig, ax = plt.subplots(figsize=(12, 6.6), constrained_layout=True)
    for route in route_order:
        y_vals: list[float] = []
        text_vals: list[str] = []
        for label in labels:
            row = top_stage[
                (top_stage["cell"] == label) & (top_stage["route_id"].astype(str) == route)
            ]
            if row.empty:
                y_vals.append(np.nan)
                text_vals.append("")
            else:
                y_vals.append(float(row["stage_time_share_pct"].iloc[0]))
                text_vals.append(str(row["stage_id"].iloc[0]))

        bars = ax.bar(
            positions[route],
            y_vals,
            width=0.34,
            label=route,
            color=ROUTE_PALETTE.get(route, "#999999"),
            edgecolor="white",
            linewidth=0.6,
            zorder=2,
        )
        for bar, txt in zip(bars, text_vals):
            if txt:
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    bar.get_height() + 0.8,
                    txt,
                    ha="center",
                    va="bottom",
                    fontsize=8.4,
                    rotation=90,
                    color="#2f3340",
                )

    ax.set_xticks(base)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Largest Stage Share of Lifecycle Time (%)")
    ax.set_xlabel("Scenario and Asset")
    ax.set_title("Dominant Bottleneck Stage by Route (stage label shown above each bar)")
    ax.legend(title="Route", loc="upper right", frameon=False)
    _style_axes(ax)

    path = figs_dir / "fig_kpi_stage_bottleneck_mix.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _plot_stage_time_distribution_top4(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {"stage_id", "time_hours", "route_id", "scenario_id", "asset_id"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for stage distribution figure: {required - set(df.columns)}")

    base = df.copy()
    base["time_hours"] = pd.to_numeric(base["time_hours"], errors="coerce")
    base = base.dropna(subset=["time_hours"])
    if base.empty:
        raise ValueError("No valid time_hours data found for stage distribution figure.")

    top4 = (
        base.groupby("stage_id", observed=False)["time_hours"]
        .mean()
        .sort_values(ascending=False)
        .head(4)
        .index.tolist()
    )
    sub = base[base["stage_id"].isin(top4)].copy()
    stage_order = top4
    route_order = [r for r in ROUTE_ORDER if r in set(sub["route_id"].astype(str))]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True, sharey=True)
    axes_flat = axes.flatten()
    for ax, stage in zip(axes_flat, stage_order):
        s = sub[sub["stage_id"] == stage].copy()
        sns.violinplot(
            data=s,
            x="route_id",
            y="time_hours",
            hue="scenario_id",
            order=route_order,
            hue_order=[x for x in SCENARIO_ORDER if x in set(s["scenario_id"].astype(str))],
            inner=None,
            cut=0,
            linewidth=0.8,
            ax=ax,
            palette="Set2",
        )
        sns.boxplot(
            data=s,
            x="route_id",
            y="time_hours",
            hue="scenario_id",
            order=route_order,
            hue_order=[x for x in SCENARIO_ORDER if x in set(s["scenario_id"].astype(str))],
            width=0.22,
            fliersize=0,
            dodge=True,
            boxprops={"facecolor": "white", "alpha": 0.75},
            whiskerprops={"linewidth": 1.1},
            medianprops={"color": "#1f2937", "linewidth": 1.4},
            ax=ax,
            palette="Set2",
        )

        ax.set_yscale("log")
        ax.set_title(f"{stage} (log scale)")
        ax.set_xlabel("Route")
        ax.set_ylabel("Stage Time (hours, log scale)")
        _style_axes(ax)

        if ax.get_legend() is not None:
            ax.get_legend().remove()

    handles, labels = axes_flat[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles[:2], labels[:2], title="Scenario", loc="upper center", ncol=2, frameon=False)
    fig.suptitle("Stage-Level Time Distributions for Top 4 Bottleneck Stages", y=1.02, fontsize=14)

    path = figs_dir / "fig_kpi_stage_time_distribution_top4.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path


def _waterfall_axes(
    ax: plt.Axes,
    x_labels: list[str],
    vals: list[float],
    ylabel: str,
    title: str,
    *,
    y_limits: tuple[float, float] | None = None,
) -> None:
    cum = np.cumsum(vals)
    starts = np.concatenate(([0.0], cum[:-1]))
    colors = ["#2a9d8f" if v < 0 else "#e76f51" for v in vals]
    bars = ax.bar(np.arange(len(vals)), vals, bottom=starts, color=colors, edgecolor="white", linewidth=0.6, zorder=3)
    ax.plot(np.arange(len(vals)), cum, color="#1f2937", marker="o", lw=1.2, zorder=4, label="Cumulative delta")
    ax.axhline(0.0, color="#111827", lw=0.9, alpha=0.7)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    ax.set_xticks(np.arange(len(vals)))
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8.3)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11.5)

    y_min, y_max = ax.get_ylim()
    pad = (y_max - y_min) * 0.018
    for bar, v in zip(bars, vals):
        if np.isnan(v):
            continue
        if v >= 0:
            y_txt = bar.get_y() + bar.get_height() + pad
            va = "bottom"
        else:
            y_txt = bar.get_y() + bar.get_height() - pad
            va = "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            y_txt,
            f"{v:+.2f}",
            ha="center",
            va=va,
            fontsize=8.0,
            color="#1f2937",
            rotation=90,
            clip_on=True,
        )

    _style_axes(ax)


def _waterfall_y_limits(series_list: list[list[float]], *, min_span: float = 1.0) -> tuple[float, float]:
    bounds: list[float] = [0.0]
    for vals in series_list:
        arr = np.asarray(vals, dtype=float)
        arr = arr[~np.isnan(arr)]
        if arr.size == 0:
            continue
        cum = np.cumsum(arr)
        starts = np.concatenate(([0.0], cum[:-1]))
        ends = cum
        bounds.extend(starts.tolist())
        bounds.extend(ends.tolist())
        bounds.extend(arr.tolist())

    y_min = min(bounds)
    y_max = max(bounds)
    if np.isclose(y_min, y_max):
        half = max(min_span / 2.0, abs(y_min) * 0.15, 0.5)
        return y_min - half, y_max + half

    span = max(y_max - y_min, min_span)
    pad = span * 0.12
    return y_min - pad, y_max + pad


def _plot_stage_delta_waterfalls(df: pd.DataFrame, figs_dir: Path) -> Dict[str, Path]:
    required = {"scenario_id", "asset_id", "route_id", "stage_id", "stage_index", "time_hours", "explicit_cost", "implicit_cost"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for stage delta waterfall: {required - set(df.columns)}")

    base = df.copy()
    base["time_hours"] = pd.to_numeric(base["time_hours"], errors="coerce")
    base["stage_cost"] = pd.to_numeric(base["explicit_cost"], errors="coerce").fillna(0.0) + pd.to_numeric(
        base["implicit_cost"], errors="coerce"
    ).fillna(0.0)

    agg = (
        base.groupby(["scenario_id", "route_id", "stage_id"], observed=False)
        .agg(
            mean_time_hours=("time_hours", "mean"),
            mean_stage_cost=("stage_cost", "mean"),
        )
        .reset_index()
    )
    stage_order = (
        base.groupby(["scenario_id", "stage_id"], observed=False)
        .agg(stage_index=("stage_index", "median"))
        .reset_index()
    )
    piv = agg.pivot_table(
        index=["scenario_id", "stage_id"],
        columns="route_id",
        values=["mean_time_hours", "mean_stage_cost"],
        aggfunc="first",
        observed=False,
    ).reset_index()
    flat_cols: list[str] = []
    for col in piv.columns:
        if isinstance(col, tuple):
            head = str(col[0])
            tail = str(col[1]) if len(col) > 1 else ""
            flat_cols.append(head if tail == "" else f"{head}__{tail}")
        else:
            flat_cols.append(str(col))
    piv.columns = flat_cols
    piv = piv.merge(stage_order, on=["scenario_id", "stage_id"], how="left")

    if "mean_time_hours__TRADFI" not in piv.columns or "mean_time_hours__TOKENIZED" not in piv.columns:
        return {}

    piv["mean_time_hours__TRADFI"] = piv["mean_time_hours__TRADFI"].fillna(0.0)
    piv["mean_time_hours__TOKENIZED"] = piv["mean_time_hours__TOKENIZED"].fillna(0.0)
    piv["mean_stage_cost__TRADFI"] = piv.get("mean_stage_cost__TRADFI", 0.0)
    piv["mean_stage_cost__TOKENIZED"] = piv.get("mean_stage_cost__TOKENIZED", 0.0)
    piv["mean_stage_cost__TRADFI"] = pd.to_numeric(piv["mean_stage_cost__TRADFI"], errors="coerce").fillna(0.0)
    piv["mean_stage_cost__TOKENIZED"] = pd.to_numeric(piv["mean_stage_cost__TOKENIZED"], errors="coerce").fillna(0.0)
    piv["delta_time_hours"] = piv["mean_time_hours__TOKENIZED"] - piv["mean_time_hours__TRADFI"]
    piv["delta_cost"] = piv["mean_stage_cost__TOKENIZED"] - piv["mean_stage_cost__TRADFI"]

    scenarios = [s for s in SCENARIO_ORDER if s in set(piv["scenario_id"].astype(str))]

    fig_time, axs_time = plt.subplots(1, len(scenarios), figsize=(6.8 * len(scenarios), 5.4), constrained_layout=True)
    fig_cost, axs_cost = plt.subplots(1, len(scenarios), figsize=(6.8 * len(scenarios), 5.4), constrained_layout=True)
    axs_time = np.atleast_1d(axs_time)
    axs_cost = np.atleast_1d(axs_cost)

    cost_y_limits = (-1.6, 1.0)
    time_series: list[list[float]] = []
    scenario_rows: list[tuple[str, list[str], list[float], list[float]]] = []

    for scenario in scenarios:
        sub = piv[piv["scenario_id"].astype(str) == scenario].copy()
        sub = sub.sort_values("stage_index")
        x = sub["stage_id"].astype(str).tolist()
        y_time_days = (sub["delta_time_hours"] / 24.0).tolist()
        y_cost = sub["delta_cost"].tolist()
        scenario_rows.append((scenario, x, y_time_days, y_cost))
        time_series.append(y_time_days)

    time_y_limits = _waterfall_y_limits(time_series, min_span=1.5)

    for i, (scenario, x, y_time_days, y_cost) in enumerate(scenario_rows):
        _waterfall_axes(
            axs_time[i],
            x,
            y_time_days,
            "Delta Time (days)",
            f"{scenario} (asset-aggregated)",
            y_limits=time_y_limits,
        )
        _waterfall_axes(
            axs_cost[i],
            x,
            y_cost,
            "Delta Cost (relative units)",
            f"{scenario} (asset-aggregated)",
            y_limits=cost_y_limits,
        )

    fig_time.suptitle("Waterfall Decomposition: Tokenized - TradFi Stage Contributions to Time Delta (Aggregated Across Assets)", y=1.03, fontsize=14)
    fig_cost.suptitle("Waterfall Decomposition: Tokenized - TradFi Stage Contributions to Cost Delta (Aggregated Across Assets)", y=1.03, fontsize=14)
    path_time = figs_dir / "fig_kpi_stage_delta_waterfall_time.png"
    path_cost = figs_dir / "fig_kpi_stage_delta_waterfall_cost.png"
    fig_time.savefig(path_time, dpi=320, bbox_inches="tight")
    fig_cost.savefig(path_cost, dpi=320, bbox_inches="tight")
    plt.close(fig_time)
    plt.close(fig_cost)
    return {
        "fig_kpi_stage_delta_waterfall_time": path_time,
        "fig_kpi_stage_delta_waterfall_cost": path_cost,
    }


def _plot_event_composition(df: pd.DataFrame, figs_dir: Path) -> Path:
    required = {"scenario_id", "asset_id", "route_id", "risk_events", "gate_events"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns for event composition figure: {required - set(df.columns)}")

    base = apply_standard_ordering(df.copy())
    base["cell"] = (
        base["scenario_id"].astype(str)
        + " | "
        + base["asset_id"].astype(str)
        + " | "
        + base["route_id"].astype(str)
    )
    cell_order = list(dict.fromkeys(base["cell"].tolist()))

    def _compose(event_col: str, top_n: int = 6) -> pd.DataFrame:
        tmp = base[["cell", event_col]].copy()
        tmp[event_col] = tmp[event_col].fillna("").astype(str).str.split(";")
        tmp = tmp.explode(event_col)
        tmp["event_id"] = tmp[event_col].astype(str).str.strip()
        tmp = tmp.drop(columns=[event_col])
        tmp = tmp[(tmp["event_id"] != "") & (tmp["event_id"].str.lower() != "nan")]
        if tmp.empty:
            return pd.DataFrame(columns=["cell", "event_group", "share_pct"])
        top = tmp["event_id"].value_counts().head(top_n).index
        tmp["event_group"] = np.where(tmp["event_id"].isin(top), tmp["event_id"], "OTHER")
        counts = tmp.groupby(["cell", "event_group"], observed=False).size().reset_index(name="n")
        totals = counts.groupby("cell", observed=False)["n"].sum().reset_index(name="total")
        out = counts.merge(totals, on="cell", how="left")
        out["share_pct"] = np.where(out["total"] > 0, out["n"] / out["total"] * 100.0, 0.0)
        return out

    risk = _compose("risk_events")
    gate = _compose("gate_events")

    fig, axes = plt.subplots(1, 2, figsize=(16, 8.4), constrained_layout=False, sharey=True)
    for ax, data, title in [
        (axes[0], risk, "Risk Event Composition by Event Type (%)"),
        (axes[1], gate, "Gate Event Composition by Event Type (%)"),
    ]:
        if data.empty:
            ax.text(0.5, 0.5, "No events observed", ha="center", va="center")
            ax.set_axis_off()
            continue

        pivot = data.pivot_table(index="cell", columns="event_group", values="share_pct", aggfunc="sum", fill_value=0.0, observed=False)
        for cell in cell_order:
            if cell not in pivot.index:
                pivot.loc[cell] = 0.0
        pivot = pivot.loc[cell_order]

        left = np.zeros(len(pivot), dtype=float)
        cmap = sns.color_palette("tab20", n_colors=len(pivot.columns))
        for color, col in zip(cmap, pivot.columns):
            vals = pivot[col].to_numpy(dtype=float)
            ax.barh(np.arange(len(pivot)), vals, left=left, color=color, edgecolor="white", linewidth=0.4, label=col)
            left += vals

        ax.set_yticks(np.arange(len(pivot)))
        ax.set_yticklabels(pivot.index)
        ax.set_xlim(0, 100)
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax.set_xlabel("Share of Event Occurrences (%)")
        ax.set_title(title, pad=10)
        _style_axes(ax)

    handles, labels = axes[1].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            title="Event ID",
            loc="upper center",
            bbox_to_anchor=(0.5, 0.94),
            ncol=min(3, len(labels)),
            frameon=False,
            fontsize=9,
            title_fontsize=10,
            columnspacing=1.3,
            handletextpad=0.5,
        )
    fig.suptitle("Risk and Gate Event Composition (Event-Type Level, not Aggregate Rate)", y=0.985, fontsize=14)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.79])

    path = figs_dir / "fig_kpi_event_composition_by_type.png"
    fig.savefig(path, dpi=320, bbox_inches="tight")
    plt.close(fig)
    return path
