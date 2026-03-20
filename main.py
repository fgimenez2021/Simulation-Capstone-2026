from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from sim.config_loader import load_model_config
from sim.final_outputs import DEFAULT_SENSITIVITY_N, export_thesis_tables, run_default_sensitivity_suite
from sim.reporting import run_grid_and_build_reports
from sim.plots import generate_all_figures


def _clean_outputs_dir(outputs_dir: Path) -> None:
    if not outputs_dir.exists():
        return
    try:
        shutil.rmtree(outputs_dir)
        return
    except OSError as exc:
        print(f"Warning: full outputs cleanup failed ({exc}). Removing generated subdirectories instead.")

    for name in ("runs", "stages", "tables", "figures"):
        target = outputs_dir / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TradFi vs Tokenized lifecycle simulation (baseline + stress)."
    )
    p.add_argument(
        "--n",
        type=int,
        default=1000,
        help="Number of Monte Carlo runs per (scenario, asset, route) cell.",
    )
    p.add_argument(
        "--outputs",
        type=str,
        default="outputs",
        help="Output directory (default: outputs).",
    )
    p.add_argument(
        "--config",
        type=str,
        default="config",
        help="Config directory (default: config).",
    )
    p.add_argument(
        "--no-plots",
        action="store_true",
        help="If set, do not generate figures.",
    )
    p.add_argument(
        "--clean",
        action="store_true",
        help="If set, delete the output directory before rebuilding outputs.",
    )
    p.add_argument(
        "--no-thesis-exports",
        action="store_false",
        dest="thesis_exports",
        help="Skip thesis-ready and appendix table exports.",
    )
    p.add_argument(
        "--with-sensitivity",
        action="store_true",
        help="Run the default sensitivity suite and export sensitivity tables.",
    )
    p.add_argument(
        "--sensitivity-n",
        type=int,
        default=DEFAULT_SENSITIVITY_N,
        help="Runs per cell for the sensitivity suite (default: 200).",
    )
    p.add_argument(
        "--qualified-private-credit",
        action="store_true",
        help="Use a qualified investor profile for PRIVATE_CREDIT runs (recommended).",
    )
    p.add_argument(
        "--no-qualified-private-credit",
        action="store_false",
        dest="qualified_private_credit",
        help="Use a non-qualified investor profile for PRIVATE_CREDIT runs.",
    )
    p.set_defaults(qualified_private_credit=True)
    p.set_defaults(thesis_exports=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    cfg = load_model_config(args.config)

    outputs_dir = Path(args.outputs)
    if args.clean and outputs_dir.exists():
        print(f"Cleaning existing outputs at {outputs_dir} ...")
        _clean_outputs_dir(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running full grid with N={args.n} per cell...")
    table_paths = run_grid_and_build_reports(
        model=cfg,
        n_runs=args.n,
        outputs_dir=outputs_dir,
        qualified_for_private_credit=bool(args.qualified_private_credit),
    )

    print("\nSaved summary tables:")
    for k, p in table_paths.items():
        print(f"  {k}: {p}")

    if args.with_sensitivity:
        print(f"\nRunning sensitivity suite with N={args.sensitivity_n} per cell...")
        sensitivity_paths = run_default_sensitivity_suite(
            config_dir=args.config,
            outputs_dir=outputs_dir,
            n_runs=args.sensitivity_n,
            qualified_for_private_credit=bool(args.qualified_private_credit),
        )
        print("Saved sensitivity tables:")
        for k, p in sensitivity_paths.items():
            print(f"  {k}: {p}")

    if args.thesis_exports:
        print("\nGenerating thesis-ready tables...")
        thesis_paths = export_thesis_tables(outputs_dir=outputs_dir, n_runs=args.n, config_dir=args.config)
        print("Saved thesis tables:")
        for k, p in thesis_paths.items():
            print(f"  {k}: {p}")

    if not args.no_plots:
        print("\nGenerating figures...")
        fig_paths = generate_all_figures(outputs_dir=outputs_dir, n_runs=args.n)
        print("Saved figures:")
        for k, p in fig_paths.items():
            print(f"  {k}: {p}")

    print("\nDone.")

if __name__ == "__main__":
    main()
