"""
Data Export -- browse and download all summary tables.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "dashboard"))

import pandas as pd
import streamlit as st

from utils.data_loader import (
    detected_n,
    list_table_files,
    load_kpi_glossary,
    load_kpi_overview,
    load_route_deltas,
)

st.set_page_config(page_title="Data Export", layout="wide")

st.markdown(
    "<h1>Data Export</h1>"
    "<p style='color:#64748b;font-size:15px;margin-top:-8px;'>"
    "Browse thesis-ready tables and download them as CSV.</p>",
    unsafe_allow_html=True,
)

n = detected_n()
st.sidebar.caption(f"Detected N = {n:,}")

tab_kpi, tab_deltas, tab_gloss, tab_config, tab_all = st.tabs([
    "KPI Overview",
    "Route Deltas",
    "KPI Glossary",
    "Config Snapshot",
    "All Tables",
])

with tab_kpi:
    kpi = load_kpi_overview(n)
    st.dataframe(kpi, use_container_width=True, hide_index=True, height=400)
    st.download_button(
        "Download KPI Overview CSV",
        kpi.to_csv(index=False).encode(),
        file_name=f"kpi_overview__N{n}.csv",
        mime="text/csv",
    )

with tab_deltas:
    deltas = load_route_deltas(n)
    st.dataframe(deltas, use_container_width=True, hide_index=True, height=400)
    st.download_button(
        "Download Route Deltas CSV",
        deltas.to_csv(index=False).encode(),
        file_name=f"route_deltas__N{n}.csv",
        mime="text/csv",
    )

with tab_gloss:
    gloss = load_kpi_glossary()
    st.dataframe(gloss, use_container_width=True, hide_index=True)

with tab_config:
    st.markdown("#### Current YAML Configuration")
    config_dir = _ROOT / "config"
    yamls = sorted(config_dir.glob("*.yaml"))
    for yf in yamls:
        with st.expander(yf.name):
            content = yf.read_text(encoding="utf-8")
            st.code(content, language="yaml")

with tab_all:
    st.markdown("All CSV files in `outputs/tables/`:")
    for fp in list_table_files():
        with st.expander(fp.name):
            try:
                df = pd.read_csv(fp)
                st.dataframe(df, use_container_width=True, hide_index=True, height=250)
                st.download_button(
                    f"Download {fp.name}",
                    df.to_csv(index=False).encode(),
                    file_name=fp.name,
                    mime="text/csv",
                    key=f"dl_{fp.name}",
                )
            except Exception as exc:
                st.error(f"Could not read {fp.name}: {exc}")
