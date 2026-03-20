"""
Deep Dive -- interactive Plotly charts for detailed analysis.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "dashboard"))

import streamlit as st

from components.charts import (
    delay_attribution_bar,
    route_delta_heatmap,
    stage_comparison_bar,
    stage_time_box,
    stage_waterfall,
    time_to_cash_bar,
    total_cost_bar,
)
from utils.data_loader import (
    detected_n,
    load_all_stages,
    load_kpi_overview,
    load_route_deltas,
    load_stage_time_mix,
)
from utils.theme import ASSET_LABELS, SCENARIO_LABELS, STAGE_META

st.set_page_config(page_title="Deep Dive", layout="wide")

st.markdown(
    "<h1>Deep Dive Analytics</h1>"
    "<p style='color:#94a3b8;font-size:15px;margin-top:-8px;'>"
    "Interactive charts -- hover, zoom, and filter to explore every dimension of the simulation.</p>",
    unsafe_allow_html=True,
)

n = detected_n()
kpi = load_kpi_overview(n)
deltas = load_route_deltas(n)
stage_mix = load_stage_time_mix(n)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Time to Cash",
    "Cost Breakdown",
    "Stage Comparison",
    "Stage Waterfall",
    "Stage Distributions",
    "Delay Attribution",
])

with tab1:
    st.plotly_chart(time_to_cash_bar(kpi), use_container_width=True)
    st.markdown("#### Route Delta Heatmap")
    st.plotly_chart(route_delta_heatmap(deltas), use_container_width=True)

with tab2:
    st.plotly_chart(total_cost_bar(kpi), use_container_width=True)

with tab3:
    scenarios = sorted(stage_mix["scenario_id"].dropna().unique())
    assets = sorted(stage_mix["asset_id"].dropna().unique())
    c1, c2 = st.columns(2)
    sel_sc = c1.selectbox("Scenario", scenarios, format_func=lambda s: SCENARIO_LABELS.get(s, s), key="sc_sc")
    sel_as = c2.selectbox("Asset", assets, format_func=lambda a: ASSET_LABELS.get(a, a), key="sc_as")
    st.plotly_chart(stage_comparison_bar(stage_mix, sel_sc, sel_as), use_container_width=True)

with tab4:
    scenarios2 = sorted(stage_mix["scenario_id"].dropna().unique())
    sel_wf = st.selectbox("Scenario", scenarios2, format_func=lambda s: SCENARIO_LABELS.get(s, s), key="wf_scenario")
    st.plotly_chart(stage_waterfall(stage_mix, sel_wf), use_container_width=True)

with tab5:
    stages_df = load_all_stages(n)
    if stages_df.empty:
        st.info("No raw stage data available.")
    else:
        useful_stages = [
            s for s in [
                "KYC_REVIEW", "CLEARING_SETTLEMENT", "TRANSFERABILITY",
                "REDEMPTION_PROCESSING", "CUSTODY_RECORDING", "ELIGIBILITY_GATE",
            ]
            if s in stages_df["stage_id"].values
        ]
        if not useful_stages:
            useful_stages = stages_df["stage_id"].unique().tolist()[:6]
        sel_stage = st.selectbox(
            "Stage", useful_stages,
            format_func=lambda s: STAGE_META.get(s, {}).get("label", s),
        )
        st.plotly_chart(stage_time_box(stages_df, sel_stage), use_container_width=True)

with tab6:
    st.plotly_chart(delay_attribution_bar(kpi), use_container_width=True)
