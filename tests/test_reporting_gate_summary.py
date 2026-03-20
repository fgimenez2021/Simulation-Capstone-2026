import pandas as pd

from sim.config_loader import load_model_config
from sim.reporting import run_grid_and_build_reports


def test_reporting_emits_gate_summary(local_tmp_path):
    cfg = load_model_config("config")
    paths = run_grid_and_build_reports(model=cfg, n_runs=5, outputs_dir=local_tmp_path)

    assert "gate_summary" in paths
    assert "access_summary" in paths
    assert "delay_summary" in paths
    assert "kpi_overview" in paths
    assert "headline_conclusions" in paths
    gate_path = paths["gate_summary"]
    access_path = paths["access_summary"]
    delay_path = paths["delay_summary"]
    kpi_path = paths["kpi_overview"]
    headline_path = paths["headline_conclusions"]
    assert gate_path.exists()
    assert access_path.exists()
    assert delay_path.exists()
    assert kpi_path.exists()
    assert headline_path.exists()

    df = pd.read_csv(gate_path)
    expected_cols = {
        "scenario_id",
        "asset_id",
        "route_id",
        "N_stage_rows",
        "gate_event_rate_per_stage_row",
        "unique_gate_event_ids_observed",
    }
    assert expected_cols.issubset(df.columns)

    access = pd.read_csv(access_path)
    assert {
        "N_onboarding_runs",
        "onboarding_success_rate",
        "N_transfer_attempts",
        "transfer_success_rate",
        "N_redemption_attempts",
        "redemption_allowed_rate",
    }.issubset(access.columns)

    delay = pd.read_csv(delay_path)
    assert {
        "queue_delay_hours_mean_per_run",
        "risk_delay_hours_mean_per_run",
        "exception_delay_hours_mean_per_run",
        "gate_delay_hours_mean_per_run",
    }.issubset(delay.columns)

    kpi = pd.read_csv(kpi_path)
    assert {
        "onboarding_success_rate",
        "redemption_allowed_rate",
        "queue_delay_hours_mean_per_run",
        "risk_delay_hours_mean_per_run",
        "exception_delay_hours_mean_per_run",
        "gate_delay_hours_mean_per_run",
    }.issubset(kpi.columns)

    headline = pd.read_csv(headline_path)
    assert {
        "scenario_id",
        "asset_id",
        "delta_time_to_cash_days_p50",
        "pct_change_time_to_cash_days_p50",
        "delta_total_cost_mean",
        "pct_change_total_cost_mean",
        "delta_completion_rate_pp",
        "delta_exit_frozen_rate_pp",
    }.issubset(headline.columns)
