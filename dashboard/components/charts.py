"""Plotly chart builders for the Deep Dive page."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from utils.theme import (
    ASSET_LABELS,
    ROUTE_COLORS,
    ROUTE_LABELS,
    SCENARIO_LABELS,
    STAGE_META,
    STAGE_ORDER,
)

_ROUTE_PAL = ROUTE_COLORS

_LAYOUT = dict(
    font=dict(
        family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color="#cbd5e1",
        size=13,
    ),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=56, r=24, t=56, b=56),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5,
        font=dict(size=12, color="#94a3b8"), bgcolor="rgba(0,0,0,0)",
    ),
    xaxis=dict(gridcolor="rgba(71,85,105,0.4)", zerolinecolor="#475569"),
    yaxis=dict(gridcolor="rgba(71,85,105,0.4)", zerolinecolor="#475569"),
    hoverlabel=dict(bgcolor="#1e293b", font_size=12, font_color="#e2e8f0"),
)


def _cell_label(row) -> str:
    s = SCENARIO_LABELS.get(row["scenario_id"], row["scenario_id"])
    a = ASSET_LABELS.get(row["asset_id"], row["asset_id"])
    return f"{s}<br>{a}"


def time_to_cash_bar(kpi: pd.DataFrame) -> go.Figure:
    df = kpi.copy()
    df["cell"] = df.apply(_cell_label, axis=1)

    fig = go.Figure()
    for route in ["TRADFI", "TOKENIZED"]:
        sub = df[df["route_id"] == route].sort_values("cell")
        lo = (sub["time_to_cash_days_p50"] - sub["time_to_cash_days_p50_ci95_low"]).clip(lower=0)
        hi = (sub["time_to_cash_days_p50_ci95_high"] - sub["time_to_cash_days_p50"]).clip(lower=0)
        fig.add_trace(go.Bar(
            x=sub["cell"], y=sub["time_to_cash_days_p50"],
            name=ROUTE_LABELS[route], marker_color=_ROUTE_PAL[route],
            marker_line_width=0,
            error_y=dict(type="data", symmetric=False, array=hi.tolist(),
                         arrayminus=lo.tolist(), thickness=1.5, width=5, color="#94a3b8"),
            text=sub["time_to_cash_days_p50"].round(1),
            textposition="auto", textfont_size=10, textfont_color="#94a3b8",
        ))
    fig.update_layout(
        **_LAYOUT, barmode="group", height=420,
        title=dict(text="Median Time to Cash (days)", font_size=16),
        yaxis_title="Days",
        uniformtext_minsize=8, uniformtext_mode="hide",
    )
    return fig


def total_cost_bar(kpi: pd.DataFrame) -> go.Figure:
    df = kpi.copy()
    df["cell"] = df.apply(_cell_label, axis=1)

    fig = go.Figure()
    for route in ["TRADFI", "TOKENIZED"]:
        sub = df[df["route_id"] == route].sort_values("cell")
        fig.add_trace(go.Bar(
            x=sub["cell"], y=sub["total_explicit_cost_mean"],
            name=f"{ROUTE_LABELS[route]} -- Explicit",
            marker_color=_ROUTE_PAL[route], marker_line_width=0,
            legendgroup=route,
        ))
        fig.add_trace(go.Bar(
            x=sub["cell"], y=sub["total_implicit_cost_mean"],
            name=f"{ROUTE_LABELS[route]} -- Implicit",
            marker_color=_ROUTE_PAL[route], marker_line_width=0,
            opacity=0.45, legendgroup=route,
        ))
    fig.update_layout(
        **_LAYOUT, barmode="stack", height=420,
        title=dict(text="Mean Total Cost (Explicit + Implicit)", font_size=16),
        yaxis_title="Cost (relative units)",
        bargroupgap=0.08,
    )
    return fig


def stage_waterfall(stage_mix: pd.DataFrame, scenario: str) -> go.Figure:
    df = stage_mix[stage_mix["scenario_id"] == scenario].copy()
    agg = (
        df.groupby(["route_id", "stage_id"], observed=False)
        .agg(mean_time=("stage_time_hours_mean", "mean"))
        .reset_index()
    )
    piv = agg.pivot(index="stage_id", columns="route_id", values="mean_time").reindex(STAGE_ORDER).fillna(0)
    if "TRADFI" not in piv.columns or "TOKENIZED" not in piv.columns:
        return go.Figure()

    piv["delta_h"] = piv["TOKENIZED"] - piv["TRADFI"]
    labels = [STAGE_META.get(s, {}).get("label", s) for s in piv.index]

    fig = go.Figure(go.Waterfall(
        x=labels, y=piv["delta_h"].tolist(),
        connector_line_color="rgba(148,163,184,0.3)",
        increasing_marker_color="#ef4444",
        decreasing_marker_color="#10b981",
        totals_marker_color="#3b82f6",
        textposition="auto",
        text=[f"{v:+.1f}h" for v in piv["delta_h"]],
        textfont=dict(size=9, color="#94a3b8"),
    ))
    fig.update_layout(
        **_LAYOUT, height=480, showlegend=False,
        title=dict(
            text=(f"Stage Time Delta: Tokenized - TradFi ({SCENARIO_LABELS.get(scenario, scenario)})"
                  "<br><sup style='color:#94a3b8'>"
                  "<span style='color:#10b981'>\u25a0 Tokenized faster</span>"
                  "    "
                  "<span style='color:#ef4444'>\u25a0 TradFi faster</span>"
                  "</sup>"),
            font_size=16,
        ),
        yaxis_title="Delta (hours)",
        xaxis_tickangle=-45,
        uniformtext_minsize=8, uniformtext_mode="hide",
    )
    fig.update_layout(margin_t=80)
    return fig


def stage_time_box(stages_df: pd.DataFrame, stage_id: str) -> go.Figure:
    df = stages_df[stages_df["stage_id"] == stage_id].copy()
    df["time_hours"] = pd.to_numeric(df["time_hours"], errors="coerce")
    df = df.dropna(subset=["time_hours"])
    df = df[df["time_hours"] > 0]

    label = STAGE_META.get(stage_id, {}).get("label", stage_id)
    fig = go.Figure()

    for scenario in ["BASELINE", "STRESS"]:
        for route in ["TRADFI", "TOKENIZED"]:
            sub = df[(df["scenario_id"] == scenario) & (df["route_id"] == route)]
            if sub.empty:
                continue
            color = _ROUTE_PAL[route]
            fig.add_trace(go.Box(
                y=sub["time_hours"],
                name=f"{ROUTE_LABELS[route]} {SCENARIO_LABELS.get(scenario, scenario)}",
                marker_color=color,
                line=dict(color=color, width=1.5 if scenario == "BASELINE" else 1.0),
                boxmean="sd",
                opacity=0.55 if scenario == "STRESS" else 0.9,
            ))

    fig.update_layout(
        **_LAYOUT, height=440, boxmode="group",
        title=dict(text=f"Time Distribution: {label}", font_size=16),
        yaxis_title="Time (hours)",
        yaxis_type="log",
    )
    return fig


def route_delta_heatmap(deltas: pd.DataFrame) -> go.Figure:
    metrics = {
        "delta_time_to_cash_days_p50": "Time to Cash (d)",
        "delta_total_time_days_p50": "Total Time (d)",
        "delta_total_cost_mean": "Cost",
        "delta_completion_rate_pp": "Completion (pp)",
        "delta_exit_frozen_rate_pp": "Exit Frozen (pp)",
        "delta_transfer_success_rate_pp": "Transfer (pp)",
    }
    avail = {k: v for k, v in metrics.items() if k in deltas.columns}
    if not avail:
        return go.Figure()

    df = deltas.copy()
    df["cell"] = df["scenario_id"].map(SCENARIO_LABELS) + " | " + df["asset_id"].map(ASSET_LABELS)
    vals = df.set_index("cell")[list(avail.keys())].rename(columns=avail)

    fig = go.Figure(go.Heatmap(
        z=vals.values, x=list(vals.columns), y=list(vals.index),
        colorscale=[[0, "#10b981"], [0.5, "#1e293b"], [1, "#ef4444"]],
        zmid=0,
        text=np.round(vals.values, 2), texttemplate="%{text}",
        textfont=dict(size=13, color="#e2e8f0"),
        colorbar=dict(title=dict(text="Tok-TradFi", font=dict(color="#94a3b8")),
                      tickfont=dict(color="#94a3b8")),
        hovertemplate="%{y}<br>%{x}: <b>%{z:.3f}</b><extra></extra>",
        xgap=3, ygap=3,
    ))
    fig.update_layout(
        **_LAYOUT, height=320,
        title=dict(text="Route Delta Heatmap (Tokenized - TradFi)", font_size=16),
    )
    fig.update_xaxes(side="bottom", tickfont_size=11)
    fig.update_yaxes(tickfont_size=12)
    return fig


def delay_attribution_bar(kpi: pd.DataFrame) -> go.Figure:
    delay_cols = {
        "queue_delay_hours_mean_per_run": "Queue",
        "risk_delay_hours_mean_per_run": "Risk",
        "exception_delay_hours_mean_per_run": "Exception",
        "gate_delay_hours_mean_per_run": "Gate",
    }
    avail = {k: v for k, v in delay_cols.items() if k in kpi.columns}
    if not avail:
        return go.Figure()

    df = kpi.copy()
    df["cell"] = (
        df["scenario_id"].map(SCENARIO_LABELS) + " | "
        + df["asset_id"].map(ASSET_LABELS) + "<br>"
        + df["route_id"].map(ROUTE_LABELS)
    )
    df["route_color"] = df["route_id"].map(_ROUTE_PAL)

    palette = {"Queue": "#06b6d4", "Risk": "#f59e0b", "Exception": "#a78bfa", "Gate": "#f87171"}
    fig = go.Figure()
    for col, label in avail.items():
        fig.add_trace(go.Bar(
            y=df["cell"], x=df[col], name=label,
            orientation="h", marker_color=palette.get(label, "#94a3b8"),
            marker_line_width=0,
        ))
    fig.update_layout(
        **_LAYOUT, barmode="stack", height=420,
        title=dict(text="Delay Attribution per Run", font_size=16),
        xaxis_title="Mean Delay (hours)",
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def stage_comparison_bar(stage_mix: pd.DataFrame, scenario: str, asset: str) -> go.Figure:
    df = stage_mix[
        (stage_mix["scenario_id"] == scenario) & (stage_mix["asset_id"] == asset)
    ].copy()

    if asset == "PRIVATE_CREDIT":
        df = df[df["stage_id"] != "EXIT_INITIATION"]

    df = df[df["stage_time_hours_mean"] > 0.01]
    stage_order_rev = [s for s in reversed(STAGE_ORDER) if s in df["stage_id"].values]
    df["label"] = df["stage_id"].map(lambda s: STAGE_META.get(s, {}).get("label", s))

    fig = go.Figure()
    for route in ["TRADFI", "TOKENIZED"]:
        sub = df[df["route_id"] == route]
        sub = sub.set_index("stage_id").reindex(stage_order_rev).dropna(subset=["stage_time_hours_mean"])
        fig.add_trace(go.Bar(
            y=[STAGE_META.get(s, {}).get("label", s) for s in sub.index],
            x=sub["stage_time_hours_mean"],
            name=ROUTE_LABELS[route], orientation="h",
            marker_color=_ROUTE_PAL[route], marker_line_width=0,
            text=sub["stage_time_hours_mean"].apply(lambda v: f"{v:.1f}h" if v >= 1 else f"{v:.2f}h"),
            textposition="auto", textfont=dict(size=9, color="#94a3b8"),
        ))
    fig.update_layout(
        **_LAYOUT, barmode="group", height=480,
        title=dict(
            text=f"Stage Time Comparison ({SCENARIO_LABELS.get(scenario, scenario)}, "
                 f"{ASSET_LABELS.get(asset, asset)})",
            font_size=16,
        ),
        xaxis_title="Mean Time (hours)",
        xaxis_type="log",
        bargap=0.15,
        uniformtext_minsize=7, uniformtext_mode="hide",
    )
    return fig
