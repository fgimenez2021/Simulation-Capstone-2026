"""
Parameter Sandbox -- tweak parameters and re-run the simulation live.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "dashboard"))

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sim.config_loader import load_model_config
from sim.gates import InvestorProfile
from sim.hybrid import run_single_lifecycle_hybrid
from sim.queues import build_queue_wait_samplers
from sim.types import (
    GatingSpec,
    ModelConfig,
    QueueServersConfig,
    RedemptionRuleSpec,
    TransferRestrictionSpec,
)
from utils.theme import ROUTE_COLORS, ROUTE_LABELS

st.set_page_config(page_title="Parameter Sandbox", layout="wide")

st.markdown(
    "<h1>Parameter Sandbox</h1>"
    "<p style='color:#64748b;font-size:15px;margin-top:-8px;'>"
    "Adjust key parameters with the sliders, then hit <b>Run Simulation</b> to see how results change in real time.</p>",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)


def _load_base_config():
    return load_model_config(str(_ROOT / "config"))


def _scale_multipliers(original: dict, new_default: float) -> dict:
    """Scale all entries proportionally when the user changes the default."""
    old_default = float(original.get("default", 1.0))
    if old_default == 0:
        return {k: new_default for k in original}
    ratio = new_default / old_default
    return {k: float(v) * ratio for k, v in original.items()}


def _modify_config(
    cfg: ModelConfig,
    time_mult: float,
    cost_mult: float,
    risk_mult: float,
    allowlist_p: float,
    transfer_p: float,
    hold_p: float,
    reject_p: float,
    kyc_servers: int,
    red_servers: int,
) -> ModelConfig:
    stress = cfg.scenarios["STRESS"]
    new_stress = replace(
        stress,
        time_multipliers=_scale_multipliers(stress.time_multipliers, time_mult),
        cost_multipliers=_scale_multipliers(stress.cost_multipliers, cost_mult),
        risk_multipliers=_scale_multipliers(stress.risk_multipliers, risk_mult),
    )

    tokenized = cfg.routes["TOKENIZED"]
    elig = tokenized.stages["ELIGIBILITY_GATE"]
    new_elig = replace(elig, gating=GatingSpec(
        requires_allowlist=True, allowlist_pass_probability=allowlist_p,
    ))
    trans = tokenized.stages["TRANSFERABILITY"]
    new_trans = replace(trans, restrictions=TransferRestrictionSpec(
        transfers_restricted=True, transfer_pass_probability=transfer_p,
    ))
    red = tokenized.stages["REDEMPTION_PROCESSING"]
    new_red = replace(red, redemption_rules=RedemptionRuleSpec(
        redemption_hold_probability=hold_p,
        redemption_reject_probability=reject_p,
        hold_delay_hours=red.redemption_rules.hold_delay_hours if red.redemption_rules else 24.0,
        hold_delay_hours_stress=red.redemption_rules.hold_delay_hours_stress if red.redemption_rules else 72.0,
    ))
    new_tok = replace(tokenized, stages={
        **tokenized.stages,
        "ELIGIBILITY_GATE": new_elig,
        "TRANSFERABILITY": new_trans,
        "REDEMPTION_PROCESSING": new_red,
    })

    q = cfg.queues
    new_kyc = replace(q.kyc_queue, servers=QueueServersConfig(
        baseline=q.kyc_queue.servers.baseline, stress=kyc_servers,
    ))
    new_red_q = replace(q.redemption_queue, servers=QueueServersConfig(
        baseline=q.redemption_queue.servers.baseline, stress=red_servers,
    ))
    new_q = replace(q, kyc_queue=new_kyc, redemption_queue=new_red_q)

    return replace(
        cfg,
        scenarios={**cfg.scenarios, "STRESS": new_stress},
        routes={**cfg.routes, "TOKENIZED": new_tok},
        queues=new_q,
    )


def _run_quick_grid(cfg: ModelConfig, n_runs: int) -> pd.DataFrame:
    rows = []
    for scenario_id in cfg.scenarios:
        scenario = cfg.scenarios[scenario_id]
        for asset_id in cfg.assets:
            investor = InvestorProfile(
                qualified_investor=(asset_id == "PRIVATE_CREDIT"),
            )
            for route_id in cfg.routes:
                samplers = None
                if scenario.queues.enabled:
                    samplers = build_queue_wait_samplers(
                        model=cfg, scenario=scenario, route_id=route_id,
                    )
                for i in range(1, n_runs + 1):
                    res = run_single_lifecycle_hybrid(
                        model=cfg, run_id=i,
                        asset_id=asset_id, route_id=route_id, scenario_id=scenario_id,
                        investor=investor, queue_samplers=samplers,
                    )
                    rows.append({
                        "scenario_id": scenario_id, "asset_id": asset_id, "route_id": route_id,
                        "completed": res.completed, "exit_frozen": res.exit_frozen,
                        "total_time_hours": res.total_time_hours,
                        "total_explicit_cost": res.total_explicit_cost,
                        "total_implicit_cost": res.total_implicit_cost,
                        "time_to_cash_hours": res.time_to_cash_hours,
                        "transfer_success": next(
                            (s.transfer_success for s in res.stages
                             if s.stage_id == "TRANSFERABILITY" and s.transfer_attempted),
                            None,
                        ),
                    })
    return pd.DataFrame(rows)


def _summarize(df: pd.DataFrame) -> pd.DataFrame:
    def _agg(g):
        ttc = pd.to_numeric(g["time_to_cash_hours"], errors="coerce").dropna()
        ts = g["transfer_success"].dropna()
        return pd.Series({
            "N": len(g),
            "completion_rate": g["completed"].mean(),
            "time_to_cash_days_p50": float(np.nanmedian(ttc / 24)) if len(ttc) else np.nan,
            "total_cost_mean": (g["total_explicit_cost"] + g["total_implicit_cost"]).mean(),
            "transfer_success_rate": ts.mean() if len(ts) else np.nan,
            "exit_frozen_rate": g["exit_frozen"].mean(),
        })
    return df.groupby(["scenario_id", "asset_id", "route_id"]).apply(_agg, include_groups=False).reset_index()

cfg_base = _load_base_config()
stress_defaults = cfg_base.scenarios["STRESS"]
tokenized_defaults = cfg_base.routes["TOKENIZED"]
tokenized_eligibility = tokenized_defaults.stages["ELIGIBILITY_GATE"].gating
tokenized_transfer = tokenized_defaults.stages["TRANSFERABILITY"].restrictions
tokenized_redemption = tokenized_defaults.stages["REDEMPTION_PROCESSING"].redemption_rules

with st.sidebar:
    st.markdown("### Simulation Parameters")
    n_runs = st.slider("N runs per cell", 10, 300, 50, step=10,
                       help="Higher = more accurate but slower")
    st.markdown("---")
    st.markdown("**Stress Scenario Multipliers**")
    time_mult = st.slider(
        "Time multiplier", 0.5, 3.0,
        float(stress_defaults.time_multipliers.get("default", 1.0)), 0.1,
    )
    cost_mult = st.slider(
        "Cost multiplier", 0.5, 3.0,
        float(stress_defaults.cost_multipliers.get("default", 1.0)), 0.05,
    )
    risk_mult = st.slider(
        "Risk multiplier", 0.5, 5.0,
        float(stress_defaults.risk_multipliers.get("default", 1.0)), 0.1,
    )
    st.markdown("---")
    st.markdown("**Tokenized Gating**")
    allowlist_p = st.slider(
        "Allowlist pass probability", 0.50, 1.00,
        float(tokenized_eligibility.allowlist_pass_probability) if tokenized_eligibility else 1.0, 0.01,
    )
    transfer_p = st.slider(
        "Transfer pass probability", 0.50, 1.00,
        float(tokenized_transfer.transfer_pass_probability) if tokenized_transfer else 1.0, 0.01,
    )
    hold_p = st.slider(
        "Redemption hold probability", 0.00, 0.30,
        float(tokenized_redemption.redemption_hold_probability) if tokenized_redemption else 0.0, 0.01,
    )
    reject_p = st.slider(
        "Redemption reject probability", 0.00, 0.20,
        float(tokenized_redemption.redemption_reject_probability) if tokenized_redemption else 0.0, 0.01,
    )
    st.markdown("---")
    st.markdown("**Stress Queue Servers**")
    kyc_srv = st.slider("KYC reviewers (stress)", 1, 10, int(cfg_base.queues.kyc_queue.servers.stress))
    red_srv = st.slider("Redemption processors (stress)", 1, 10, int(cfg_base.queues.redemption_queue.servers.stress))

run_btn = st.button("Run Simulation", type="primary", use_container_width=True)

if run_btn:
    mod_cfg = _modify_config(
        cfg_base, time_mult, cost_mult, risk_mult,
        allowlist_p, transfer_p, hold_p, reject_p,
        kyc_srv, red_srv,
    )
    n_cells = len(mod_cfg.scenarios) * len(mod_cfg.assets) * len(mod_cfg.routes)
    with st.spinner(f"Running {n_runs} lifecycles across {n_cells} cells..."):
        raw = _run_quick_grid(mod_cfg, n_runs)
    summary = _summarize(raw)
    st.session_state["sandbox_summary"] = summary
    st.session_state["sandbox_n"] = n_runs

if "sandbox_summary" in st.session_state:
    summary = st.session_state["sandbox_summary"]
    sb_n = st.session_state["sandbox_n"]

    st.success(f"Simulation complete -- {sb_n} runs per cell.")
    st.markdown("### Results")

    fig = go.Figure()
    for route in ["TRADFI", "TOKENIZED"]:
        sub = summary[summary["route_id"] == route].copy()
        sub["cell"] = sub["scenario_id"] + " / " + sub["asset_id"]
        fig.add_trace(go.Bar(
            x=sub["cell"], y=sub["time_to_cash_days_p50"],
            name=ROUTE_LABELS[route], marker_color=ROUTE_COLORS[route],
        ))
    fig.update_layout(
        barmode="group", title="Median Time to Cash (days)",
        yaxis_title="Days", height=400,
        font_family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        plot_bgcolor="#fafbfd",
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        fig2 = go.Figure()
        for route in ["TRADFI", "TOKENIZED"]:
            sub = summary[summary["route_id"] == route].copy()
            sub["cell"] = sub["scenario_id"] + " / " + sub["asset_id"]
            fig2.add_trace(go.Bar(
                x=sub["cell"], y=sub["total_cost_mean"],
                name=ROUTE_LABELS[route], marker_color=ROUTE_COLORS[route],
            ))
        fig2.update_layout(barmode="group", title="Mean Total Cost", yaxis_title="Cost",
                           height=350, plot_bgcolor="#fafbfd")
        st.plotly_chart(fig2, use_container_width=True)

    with c2:
        fig3 = go.Figure()
        for route in ["TRADFI", "TOKENIZED"]:
            sub = summary[summary["route_id"] == route].copy()
            sub["cell"] = sub["scenario_id"] + " / " + sub["asset_id"]
            fig3.add_trace(go.Bar(
                x=sub["cell"], y=sub["completion_rate"] * 100,
                name=ROUTE_LABELS[route], marker_color=ROUTE_COLORS[route],
            ))
        fig3.update_layout(barmode="group", title="Completion Rate (%)", yaxis_title="%",
                           height=350, plot_bgcolor="#fafbfd")
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### Raw Summary Table")
    display = summary.copy()
    for c in display.select_dtypes(include="float").columns:
        display[c] = display[c].round(4)
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("Adjust sliders in the sidebar, then click **Run Simulation** to see results.")
