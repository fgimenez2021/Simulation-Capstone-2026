"""Landing page with headline KPIs and route-delta summary."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "dashboard"))

import streamlit as st

from components.kpi_cards import render_headline_deltas, render_kpi_card
from utils.data_loader import (
    detected_n,
    load_headline_conclusions,
    load_kpi_overview,
    load_route_deltas,
)
from utils.theme import ASSET_LABELS, SCENARIO_LABELS

st.set_page_config(
    page_title="TradFi vs Tokenized Explorer",
    page_icon="\u2696\uFE0F",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    "<style>.block-container{padding-top:2rem;}</style>",
    unsafe_allow_html=True,
)

n = detected_n()
kpi = load_kpi_overview(n)
deltas = load_route_deltas(n)
headlines = load_headline_conclusions(n)

st.sidebar.markdown("### Filters")
scenarios = sorted(kpi["scenario_id"].dropna().unique())
assets = sorted(kpi["asset_id"].dropna().unique())
sel_scenario = st.sidebar.selectbox("Scenario", scenarios, format_func=lambda s: SCENARIO_LABELS.get(s, s))
sel_asset = st.sidebar.selectbox("Asset", assets, format_func=lambda a: ASSET_LABELS.get(a, a))
st.sidebar.caption(f"Showing N = {n:,} runs per cell")

st.markdown(
    "<h1 style='margin-bottom:0;'>TradFi vs Tokenized Lifecycle Explorer</h1>"
    "<p style='color:#94a3b8;margin-top:4px;font-size:15px;'>"
    "Interactive comparison of investor lifecycle outcomes across traditional and tokenized rails.</p>",
    unsafe_allow_html=True,
)

tradfi = kpi[(kpi["scenario_id"] == sel_scenario) & (kpi["asset_id"] == sel_asset) & (kpi["route_id"] == "TRADFI")]
tokenized = kpi[(kpi["scenario_id"] == sel_scenario) & (kpi["asset_id"] == sel_asset) & (kpi["route_id"] == "TOKENIZED")]

if tradfi.empty or tokenized.empty:
    st.warning("No data for this scenario/asset combination.")
    st.stop()

t = tradfi.iloc[0]
k = tokenized.iloc[0]

delta_row = deltas[(deltas["scenario_id"] == sel_scenario) & (deltas["asset_id"] == sel_asset)]
dr = delta_row.iloc[0] if not delta_row.empty else None

c1, c2, c3, c4 = st.columns(4)

with c1:
    render_kpi_card(
        "Time to Cash",
        float(t["time_to_cash_days_p50"]),
        float(k["time_to_cash_days_p50"]),
        float(dr["delta_time_to_cash_days_p50"]) if dr is not None else 0,
        float(dr["pct_change_time_to_cash_days_p50"]) if dr is not None else None,
        fmt=".1f", suffix=" d", direction="lower_better",
    )
with c2:
    render_kpi_card(
        "Total Cost",
        float(t["total_cost_mean"]),
        float(k["total_cost_mean"]),
        float(dr["delta_total_cost_mean"]) if dr is not None else 0,
        float(dr["pct_change_total_cost_mean"]) if dr is not None else None,
        fmt=".2f", direction="lower_better",
    )
with c3:
    render_kpi_card(
        "Completion Rate",
        float(t["completion_rate"]) * 100,
        float(k["completion_rate"]) * 100,
        float(dr["delta_completion_rate_pp"]) if dr is not None else 0,
        None,
        fmt=".1f", suffix="%", direction="higher_better",
    )
with c4:
    render_kpi_card(
        "Transfer Success",
        float(t.get("transfer_success_rate", 0)) * 100,
        float(k.get("transfer_success_rate", 0)) * 100,
        float(dr["delta_transfer_success_rate_pp"]) if dr is not None else 0,
        None,
        fmt=".1f", suffix="%", direction="higher_better",
    )

st.markdown("---")

st.subheader("Headline Route Deltas (Tokenized minus TradFi)")
render_headline_deltas(headlines, sel_scenario, sel_asset)

st.markdown("<br>", unsafe_allow_html=True)

st.subheader("Full Route Comparison Table")
display_cols = [
    "scenario_id", "asset_id",
    "delta_time_to_cash_days_p50", "pct_change_time_to_cash_days_p50",
    "delta_total_cost_mean", "pct_change_total_cost_mean",
    "delta_completion_rate_pp", "delta_exit_frozen_rate_pp",
    "delta_transfer_success_rate_pp",
]
available = [c for c in display_cols if c in deltas.columns]
styled = deltas[available].copy()
for c in styled.columns:
    if styled[c].dtype in ("float64", "float32"):
        styled[c] = styled[c].round(3)
st.dataframe(styled, use_container_width=True, hide_index=True)
