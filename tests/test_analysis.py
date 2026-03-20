"""Tests for the analysis table builder."""

import pandas as pd
import numpy as np

from sim.config_loader import load_model_config
from sim.gates import InvestorProfile
from sim.hybrid import run_single_lifecycle_hybrid
from sim.runner import _flatten_run, _flatten_stages
from sim.analysis import build_analysis_tables


def _build_grid_data(n=5):
    cfg = load_model_config("config")
    run_rows, stage_rows = [], []
    for scenario_id in ["BASELINE"]:
        for asset_id in ["TBILL_MMF"]:
            for route_id in ["TRADFI", "TOKENIZED"]:
                investor = InvestorProfile(qualified_investor=False)
                for i in range(1, n + 1):
                    res = run_single_lifecycle_hybrid(
                        model=cfg, run_id=i,
                        asset_id=asset_id, route_id=route_id, scenario_id=scenario_id,
                        investor=investor,
                    )
                    run_rows.append(_flatten_run(res))
                    stage_rows.extend(_flatten_stages(res))
    return pd.DataFrame(run_rows), pd.DataFrame(stage_rows)


def test_build_analysis_tables_keys():
    df_runs, df_stages = _build_grid_data()
    tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    expected_keys = {"kpi_overview", "route_deltas", "headline_conclusions", "stage_time_mix", "kpi_glossary"}
    assert expected_keys == set(tables.keys())


def test_kpi_overview_has_both_routes():
    df_runs, df_stages = _build_grid_data()
    tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    kpi = tables["kpi_overview"]
    routes = set(kpi["route_id"].astype(str))
    assert "TRADFI" in routes
    assert "TOKENIZED" in routes


def test_route_deltas_has_delta_columns():
    df_runs, df_stages = _build_grid_data()
    tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    deltas = tables["route_deltas"]
    assert "delta_time_to_cash_days_p50" in deltas.columns
    assert "delta_total_cost_mean" in deltas.columns
    assert len(deltas) >= 1


def test_stage_time_mix_shares_sum_to_100():
    df_runs, df_stages = _build_grid_data()
    tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    mix = tables["stage_time_mix"]
    for (sc, a, r), g in mix.groupby(["scenario_id", "asset_id", "route_id"], observed=False):
        total = g["stage_time_share_pct"].sum()
        assert abs(total - 100.0) < 0.5, f"Stage shares sum to {total} for {sc}/{a}/{r}"


def test_kpi_glossary_not_empty():
    df_runs, df_stages = _build_grid_data()
    tables = build_analysis_tables(df_runs=df_runs, df_stages=df_stages)
    gloss = tables["kpi_glossary"]
    assert len(gloss) > 5
    assert "metric_name" in gloss.columns


def test_onboarding_stage_ids_match_config():
    """The onboarding_stage_ids set in analysis.py must use ELIGIBILITY_GATE."""
    from sim.analysis import _event_kpis
    cfg = load_model_config("config")
    assert "ELIGIBILITY_GATE" in cfg.stages
    run_rows, stage_rows = [], []
    for route_id in ["TRADFI", "TOKENIZED"]:
        for i in range(1, 6):
            res = run_single_lifecycle_hybrid(
                model=cfg, run_id=i,
                asset_id="PRIVATE_CREDIT", route_id=route_id, scenario_id="BASELINE",
                investor=InvestorProfile(qualified_investor=False),
            )
            run_rows.append(_flatten_run(res))
            stage_rows.extend(_flatten_stages(res))

    df_stages = pd.DataFrame(stage_rows)
    event_kpis = _event_kpis(df_stages)
    if "onboarding_success_rate" in event_kpis.columns:
        assert (event_kpis["onboarding_success_rate"] == 0.0).all(), \
            "Retail investors should always fail private credit eligibility gate"
