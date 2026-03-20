"""Cached data loaders for the Streamlit dashboard."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"


def _detect_n(tables_dir: Path) -> int:
    if not tables_dir.is_dir():
        return 0
    candidates = set()
    for p in tables_dir.glob("kpi_overview__N*.csv"):
        m = re.search(r"__N(\d+)\.csv$", p.name)
        if m:
            candidates.add(int(m.group(1)))
    return max(candidates) if candidates else 0


@st.cache_data(show_spinner=False)


def detected_n() -> int:
    n = _detect_n(OUTPUTS / "tables")
    if n == 0:
        st.error(
            "No simulation outputs found. Run the simulation first:\n\n"
            "```\npython main.py --n 200\n```"
        )
        st.stop()
    return n


@st.cache_data(show_spinner=False)


def load_kpi_overview(n: Optional[int] = None) -> pd.DataFrame:
    n = n or detected_n()
    return pd.read_csv(OUTPUTS / "tables" / f"kpi_overview__N{n}.csv")


@st.cache_data(show_spinner=False)


def load_route_deltas(n: Optional[int] = None) -> pd.DataFrame:
    n = n or detected_n()
    return pd.read_csv(OUTPUTS / "tables" / f"route_deltas__N{n}.csv")


@st.cache_data(show_spinner=False)


def load_headline_conclusions(n: Optional[int] = None) -> pd.DataFrame:
    n = n or detected_n()
    return pd.read_csv(OUTPUTS / "tables" / f"headline_conclusions__N{n}.csv")


@st.cache_data(show_spinner=False)


def load_stage_time_mix(n: Optional[int] = None) -> pd.DataFrame:
    n = n or detected_n()
    return pd.read_csv(OUTPUTS / "tables" / f"stage_time_mix__N{n}.csv")


@st.cache_data(show_spinner=False)


def load_kpi_glossary() -> pd.DataFrame:
    return pd.read_csv(OUTPUTS / "tables" / "kpi_glossary.csv")


@st.cache_data(show_spinner=False)


def load_all_stages(n: Optional[int] = None) -> pd.DataFrame:
    n = n or detected_n()
    stages_dir = OUTPUTS / "stages"
    files = sorted(stages_dir.glob(f"stages_*__N{n}.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def list_table_files() -> list[Path]:
    tables_dir = OUTPUTS / "tables"
    if not tables_dir.is_dir():
        return []
    return sorted(tables_dir.glob("*.csv"))
