"""
Integration test: runs the full main.py pipeline end-to-end with a tiny N
and checks that all expected outputs (CSVs, figures, tables) are produced.
"""
from __future__ import annotations

from pathlib import Path

from sim.config_loader import load_model_config
from sim.reporting import run_grid_and_build_reports
from sim.plots import generate_all_figures

N_RUNS = 5
CONFIG_DIR = "config"


def test_full_pipeline_produces_outputs(local_tmp_path):
    cfg = load_model_config(CONFIG_DIR)
    outputs_dir = Path(local_tmp_path)

    table_paths = run_grid_and_build_reports(
        model=cfg,
        n_runs=N_RUNS,
        outputs_dir=outputs_dir,
        qualified_for_private_credit=True,
    )

    assert len(table_paths) > 0, "run_grid_and_build_reports returned no table paths"
    for name, path in table_paths.items():
        assert Path(path).exists(), f"Expected table missing: {name} -> {path}"
        assert Path(path).stat().st_size > 0, f"Table file is empty: {path}"

    runs_dir = outputs_dir / "runs"
    stages_dir = outputs_dir / "stages"
    tables_dir = outputs_dir / "tables"

    run_csvs = list(runs_dir.glob("runs_*.csv"))
    stage_csvs = list(stages_dir.glob("stages_*.csv"))

    n_scenarios = len(cfg.scenarios)
    n_assets = len(cfg.assets)
    n_routes = len(cfg.routes)
    expected_cells = n_scenarios * n_assets * n_routes

    assert len(run_csvs) == expected_cells, (
        f"Expected {expected_cells} run CSVs, found {len(run_csvs)}"
    )
    assert len(stage_csvs) == expected_cells, (
        f"Expected {expected_cells} stage CSVs, found {len(stage_csvs)}"
    )

    expected_tables = [
        f"summary_runs__N{N_RUNS}.csv",
        f"kpi_overview__N{N_RUNS}.csv",
        f"route_deltas__N{N_RUNS}.csv",
    ]
    for tbl in expected_tables:
        assert (tables_dir / tbl).exists(), f"Missing summary table: {tbl}"


def test_full_pipeline_with_figures(local_tmp_path):
    cfg = load_model_config(CONFIG_DIR)
    outputs_dir = Path(local_tmp_path)

    run_grid_and_build_reports(
        model=cfg,
        n_runs=N_RUNS,
        outputs_dir=outputs_dir,
        qualified_for_private_credit=True,
    )

    fig_paths = generate_all_figures(outputs_dir=outputs_dir, n_runs=N_RUNS)

    assert len(fig_paths) > 0, "generate_all_figures returned no figure paths"
    for name, path in fig_paths.items():
        assert Path(path).exists(), f"Expected figure missing: {name} -> {path}"
        assert Path(path).stat().st_size > 0, f"Figure file is empty: {path}"
