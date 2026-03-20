"""Styled KPI metric card components."""
from __future__ import annotations

import math

import streamlit as st

from utils.theme import TRADFI_COLOR, TOKENIZED_COLOR


def render_kpi_card(
    title: str,
    tradfi_val: float,
    tokenized_val: float,
    delta: float,
    pct_change: float | None,
    fmt: str = ".2f",
    suffix: str = "",
    direction: str = "lower_better",
) -> None:
    if delta == 0:
        arrow = "equal"
        color = "#94a3b8"
    elif direction == "lower_better":
        arrow = "lower" if delta < 0 else "higher"
        color = "#10b981" if delta < 0 else "#ef4444"
    else:
        arrow = "higher" if delta > 0 else "lower"
        color = "#10b981" if delta > 0 else "#ef4444"

    sign = "+" if delta > 0 else ""
    delta_str = f"{sign}{delta:{fmt}}{suffix}"
    pct_str = f" ({sign}{pct_change:.1f}%)" if pct_change is not None and pct_change == pct_change else ""

    html = (
        '<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);'
        'border-radius:14px;padding:20px 22px;height:100%;">'
        f'<div style="font-size:12px;color:#94a3b8;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:14px;">{title}</div>'
        '<div style="display:flex;justify-content:space-between;gap:12px;">'
        '<div>'
        f'<div style="font-size:10px;color:{TRADFI_COLOR};font-weight:600;">TradFi</div>'
        f'<div style="font-size:26px;font-weight:800;color:{TRADFI_COLOR};line-height:1.1;">'
        f'{tradfi_val:{fmt}}<span style="font-size:13px;">{suffix}</span></div>'
        '</div>'
        '<div style="text-align:right;">'
        f'<div style="font-size:10px;color:{TOKENIZED_COLOR};font-weight:600;">Tokenized</div>'
        f'<div style="font-size:26px;font-weight:800;color:{TOKENIZED_COLOR};line-height:1.1;">'
        f'{tokenized_val:{fmt}}<span style="font-size:13px;">{suffix}</span></div>'
        '</div>'
        '</div>'
        f'<div style="margin-top:14px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.1);">'
        f'<span style="font-size:14px;font-weight:700;color:{color};">'
        f'{delta_str}{pct_str}'
        '</span>'
        f'<span style="font-size:11px;color:#94a3b8;margin-left:4px;">'
        f'Tokenized is {arrow}'
        '</span>'
        '</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_headline_deltas(df_headlines, scenario: str, asset: str) -> None:
    row = df_headlines[
        (df_headlines["scenario_id"] == scenario)
        & (df_headlines["asset_id"] == asset)
    ]
    if row.empty:
        st.info("No headline data for this selection.")
        return
    row = row.iloc[0]

    metrics = [
        ("Time to Cash", "delta_time_to_cash_days_p50", "pct_change_time_to_cash_days_p50", " days", "lower_better"),
        ("Total Time", "delta_total_time_days_p50", "pct_change_total_time_days_p50", " days", "lower_better"),
        ("Total Cost", "delta_total_cost_mean", "pct_change_total_cost_mean", " units", "lower_better"),
        ("Completion", "delta_completion_rate_pp", None, " pp", "higher_better"),
        ("Exit Frozen", "delta_exit_frozen_rate_pp", None, " pp", "lower_better"),
        ("Transfer Success", "delta_transfer_success_rate_pp", None, " pp", "higher_better"),
    ]

    cols = st.columns(len(metrics))
    for col, (label, delta_col, pct_col, suffix, direction) in zip(cols, metrics):
        delta = float(row.get(delta_col, 0))
        if delta == 0:
            color = "#94a3b8"
        elif direction == "lower_better":
            color = "#10b981" if delta < 0 else "#ef4444"
        else:
            color = "#10b981" if delta > 0 else "#ef4444"
        sign = "+" if delta > 0 else ""

        pct_html = ""
        if pct_col and pct_col in row.index:
            pv = row[pct_col]
            if math.isfinite(pv):
                pct_html = f'<div style="font-size:11px;color:#94a3b8;">({("+" if pv > 0 else "")}{pv:.1f}%)</div>'

        card = (
            '<div style="text-align:center;padding:12px 8px;background:rgba(255,255,255,0.04);'
            'border:1px solid rgba(255,255,255,0.08);border-radius:10px;">'
            f'<div style="font-size:11px;color:#94a3b8;font-weight:600;margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:20px;font-weight:800;color:{color};">{sign}{delta:.2f}{suffix}</div>'
            f'{pct_html}'
            '</div>'
        )
        col.markdown(card, unsafe_allow_html=True)
