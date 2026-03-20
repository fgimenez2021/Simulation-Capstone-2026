import pandas as pd

from sim.config_loader import load_model_config
from sim.gates import InvestorProfile
from sim.runner import run_experiment


def test_runner_creates_expected_columns(local_tmp_path):
    cfg = load_model_config("config")

    df_runs, df_stages = run_experiment(
        model=cfg,
        n_runs=10,
        asset_id="TBILL_MMF",
        route_id="TRADFI",
        scenario_id="BASELINE",
        investor_profile=InvestorProfile(qualified_investor=False),
        outputs_dir=local_tmp_path,
    )

    run_cols = {
        "run_id", "asset_id", "route_id", "scenario_id",
        "completed", "exit_frozen", "failed_stage_id",
        "total_time_hours", "total_explicit_cost", "total_implicit_cost",
        "total_approvals", "total_handoffs", "intermediaries_count",
        "time_to_position_hours", "time_to_cash_hours",
    }
    assert run_cols.issubset(df_runs.columns), f"Missing run columns: {run_cols - set(df_runs.columns)}"
    assert len(df_runs) == 10

    stage_cols = {
        "run_id", "stage_index", "asset_id", "route_id", "scenario_id",
        "stage_id", "stage_label",
        "time_hours", "base_time_hours", "gate_delay_hours", "risk_delay_hours", "exception_delay_hours", "queue_delay_hours",
        "explicit_cost", "implicit_cost",
        "approvals", "handoffs", "intermediaries",
        "transfer_attempted", "transfer_success",
        "redemption_attempted", "redemption_success",
        "gate_events",
        "risk_events",
    }
    assert stage_cols.issubset(df_stages.columns), f"Missing stage columns: {stage_cols - set(df_stages.columns)}"
    assert len(df_stages) > 0

    runs_files = list((local_tmp_path / "runs").glob("runs_*.csv"))
    stages_files = list((local_tmp_path / "stages").glob("stages_*.csv"))
    assert len(runs_files) == 1
    assert len(stages_files) == 1

    runs_loaded = pd.read_csv(runs_files[0])
    stages_loaded = pd.read_csv(stages_files[0])
    assert len(runs_loaded) == 10
    assert len(stages_loaded) > 0
