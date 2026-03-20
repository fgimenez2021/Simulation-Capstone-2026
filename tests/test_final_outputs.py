from __future__ import annotations

from pathlib import Path

import pandas as pd

from sim.config_loader import load_model_config
from sim.final_outputs import export_thesis_tables, run_default_sensitivity_suite
from sim.reporting import run_grid_and_build_reports


def test_export_thesis_tables_writes_expected_files(local_tmp_path):
    cfg = load_model_config("config")
    run_grid_and_build_reports(
        model=cfg,
        n_runs=5,
        outputs_dir=local_tmp_path,
        qualified_for_private_credit=True,
    )

    paths = export_thesis_tables(outputs_dir=local_tmp_path, n_runs=5)

    expected_keys = {
        "thesis_table_6_1_overall",
        "thesis_table_6_2_access",
        "thesis_table_6_2_operational",
        "thesis_table_6_3_stage_drivers",
        "appendix_table_A1_asset_mechanics",
        "appendix_table_A2_scenario_and_queue_assumptions",
        "appendix_table_A3_route_level_parameter_assumptions",
        "appendix_table_A4_risk_event_parameter_assumptions",
        "appendix_table_B1_experimental_grid_and_reporting_profile",
        "appendix_table_B2_queue_setup_under_baseline_and_stress_conditions",
        "appendix_table_C1_canonical_lifecycle_stages_used_in_the_simulation",
        "appendix_table_D1_structural_gates_and_rule_based_restrictions",
        "appendix_table_D2_stochastic_risk_events",
        "appendix_table_E1_full_kpi_overview",
        "appendix_table_E2_route_deltas_tokenized_minus_tradfi",
        "appendix_table_E3_stage_driver_breakdown",
        "appendix_table_E4_access_outcomes",
        "appendix_table_E5_gate_marker_summary",
        "appendix_table_E6_risk_event_summary",
        "appendix_table_E7_delay_attribution_summary",
        "appendix_table_G1_validation_and_reproducibility_features",
    }
    assert expected_keys == set(paths.keys())

    for path in paths.values():
        csv_path = Path(path)
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert not df.empty

    operational = pd.read_csv(paths["thesis_table_6_2_operational"])
    assert "queue_delay_hours_mean_per_run" in operational.columns
    assert operational["queue_delay_hours_mean_per_run"].notna().any()

    stage_drivers = pd.read_csv(paths["thesis_table_6_3_stage_drivers"])
    assert "Clearing and settlement (mean hours)" in stage_drivers.columns
    assert "Onboarding (mean hours)" in stage_drivers.columns

    a1 = pd.read_csv(paths["appendix_table_A1_asset_mechanics"])
    assert "Current value" in a1.columns
    assert "`daily / 0 / 1`" in set(a1["Current value"])

    a4 = pd.read_csv(paths["appendix_table_A4_risk_event_parameter_assumptions"])
    assert "`KYC_MANUAL_REVIEW.base_probability`" in set(a4["Parameter(s)"])

    e2 = pd.read_csv(paths["appendix_table_E2_route_deltas_tokenized_minus_tradfi"])
    assert "Delta time to cash (days)" in e2.columns

    assert "final_thesis_view" not in paths
    assert "final_delta_time_to_cash" not in paths
    assert "final_delta_total_time" not in paths


def test_sensitivity_suite_uses_temp_outputs_and_preserves_main_tables(local_tmp_path):
    cfg = load_model_config("config")
    paths = run_grid_and_build_reports(
        model=cfg,
        n_runs=5,
        outputs_dir=local_tmp_path,
        qualified_for_private_credit=True,
    )
    baseline_before = pd.read_csv(paths["kpi_overview"])

    sensitivity_paths = run_default_sensitivity_suite(
        config_dir="config",
        outputs_dir=local_tmp_path,
        n_runs=3,
        qualified_for_private_credit=True,
    )

    baseline_after = pd.read_csv(paths["kpi_overview"])
    pd.testing.assert_frame_equal(baseline_before, baseline_after)
    assert not (Path(local_tmp_path) / "tables" / "kpi_overview__N3.csv").exists()

    for path in sensitivity_paths.values():
        csv_path = Path(path)
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert not df.empty


def test_export_thesis_tables_includes_appendix_f_when_sensitivity_exists(local_tmp_path):
    cfg = load_model_config("config")
    run_grid_and_build_reports(
        model=cfg,
        n_runs=5,
        outputs_dir=local_tmp_path,
        qualified_for_private_credit=True,
    )
    run_default_sensitivity_suite(
        config_dir="config",
        outputs_dir=local_tmp_path,
        n_runs=3,
        qualified_for_private_credit=True,
    )

    paths = export_thesis_tables(outputs_dir=local_tmp_path, n_runs=5)

    assert "appendix_table_F1_kyc_queue_capacity_sensitivity" in paths
    assert "appendix_table_F2_tokenized_allowlist_sensitivity" in paths
    assert "appendix_table_F3_redemption_capacity_sensitivity" in paths

    f2 = pd.read_csv(paths["appendix_table_F2_tokenized_allowlist_sensitivity"])
    assert set(f2["Route"]) == {"Tokenized"}
