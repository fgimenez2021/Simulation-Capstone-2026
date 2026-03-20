"""
Lifecycle Race -- animated side-by-side stage progression.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "dashboard"))

import streamlit as st

from components.race import render_race
from utils.data_loader import detected_n, load_stage_time_mix
from utils.theme import ASSET_LABELS, SCENARIO_LABELS

st.set_page_config(page_title="Lifecycle Race", layout="wide")

st.markdown(
    "<h1>Lifecycle Race</h1>"
    "<p style='color:#94a3b8;font-size:15px;margin-top:-8px;'>"
    "Watch an investor traverse every lifecycle stage on TradFi vs Tokenized rails side by side. "
    "Stage widths are proportional to mean processing time.</p>",
    unsafe_allow_html=True,
)

n = detected_n()
stage_mix = load_stage_time_mix(n)

scenarios = sorted(stage_mix["scenario_id"].dropna().unique())
assets = sorted(stage_mix["asset_id"].dropna().unique())

c1, c2 = st.columns(2)
sel_scenario = c1.selectbox("Scenario", scenarios, format_func=lambda s: SCENARIO_LABELS.get(s, s))
sel_asset = c2.selectbox("Asset", assets, format_func=lambda a: ASSET_LABELS.get(a, a))

st.markdown("---")
render_race(stage_mix, sel_scenario, sel_asset, height=480)

with st.expander("How to read this visualization"):
    st.markdown("""
- **Bar width** = proportional to mean stage processing time.
- **Color** = stage category (see legend below the animation).
- Dashed lines mark **disabled stages** (e.g., Exception Handling).
- The route that finishes first gets the **DONE** badge -- the shorter bar shows the speed advantage.
- For **Private Credit**, calendar waiting (quarterly redemption window + 30-day notice period) is excluded from the bars since it's identical for both routes and would hide all other stages. The total time including calendar wait is shown in the stats row.
- Use the speed buttons to slow down or speed up the animation.
- **Hover** over any stage segment to see its name and duration.
- After the animation finishes, a **summary row** appears showing the time advantage.
""")
