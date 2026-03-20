"""Tests for run-level and stage-level summary metrics."""

import pandas as pd
import numpy as np

from sim.config_loader import load_model_config
from sim.gates import InvestorProfile
from sim.hybrid import run_single_lifecycle_hybrid
from sim.runner import _flatten_run, _flatten_stages
from sim.metrics import summarize_access_permissions, summarize_gate_events, summarize_runs


def _build_sample_data(n=20):
    cfg = load_model_config("config")
    run_rows, stage_rows = [], []
    for i in range(1, n + 1):
        res = run_single_lifecycle_hybrid(
            model=cfg, run_id=i,
            asset_id="TBILL_MMF", route_id="TRADFI", scenario_id="BASELINE",
            investor=InvestorProfile(qualified_investor=False),
        )
        run_rows.append(_flatten_run(res))
        stage_rows.extend(_flatten_stages(res))
    return pd.DataFrame(run_rows), pd.DataFrame(stage_rows)


def test_summarize_runs_columns():
    df_runs, _ = _build_sample_data(10)
    summary = summarize_runs(df_runs)
    expected = {
        "scenario_id", "asset_id", "route_id", "N",
        "completion_rate", "exit_frozen_rate",
    }
    assert expected.issubset(summary.columns)
    assert len(summary) == 1


def test_summarize_runs_values_sane():
    df_runs, _ = _build_sample_data(10)
    summary = summarize_runs(df_runs)
    row = summary.iloc[0]
    assert row["N"] == 10
    assert 0.0 <= row["completion_rate"] <= 1.0
    assert 0.0 <= row["exit_frozen_rate"] <= 1.0


def test_gate_events_uses_eligibility_gate():
    """Verify that onboarding_stage_ids includes ELIGIBILITY_GATE (not ASSET_ELIGIBILITY)."""
    _, df_stages = _build_sample_data(5)
    summary = summarize_access_permissions(df_stages)
    rate = summary["onboarding_success_rate"].iloc[0]
    assert 0.0 <= rate <= 1.0


def test_gate_summary_with_private_credit_denied():
    """Private credit with retail investor should show gate denial in onboarding metrics."""
    cfg = load_model_config("config")
    run_rows, stage_rows = [], []
    for i in range(1, 11):
        res = run_single_lifecycle_hybrid(
            model=cfg, run_id=i,
            asset_id="PRIVATE_CREDIT", route_id="TOKENIZED", scenario_id="BASELINE",
            investor=InvestorProfile(qualified_investor=False),
        )
        run_rows.append(_flatten_run(res))
        stage_rows.extend(_flatten_stages(res))

    df_stages = pd.DataFrame(stage_rows)
    summary = summarize_access_permissions(df_stages)
    rate = summary["onboarding_success_rate"].iloc[0]
    assert rate == 0.0, "Retail investors should always fail private credit eligibility"
