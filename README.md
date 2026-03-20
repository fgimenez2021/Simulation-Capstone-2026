## TradFi vs Tokenized Lifecycle Simulation

Config-driven Monte Carlo + queue-hybrid simulation for comparing end-to-end investor lifecycle outcomes across:

- Routes: `TRADFI`, `TOKENIZED`
- Assets: `TBILL_MMF`, `PRIVATE_CREDIT`
- Scenarios: `BASELINE`, `STRESS`

The model simulates full lifecycle performance (not only settlement), including:

- Processing time and time-to-cash
- Explicit and implicit costs
- Operational friction (approvals, handoffs, intermediaries)
- Structural gates (eligibility, allowlist, transfer/redeem constraints)
- Probabilistic risk events (operational and governance disruptions)
- Stress queue effects (KYC and redemption backlogs via SimPy)

## Project Structure

- `config/`: YAML model assumptions and route/scenario definitions
- `sim/`: core simulation package
- `dashboard/`: Streamlit interactive dashboard (run with `streamlit run dashboard/Home.py`)
- `outputs/`: generated runs, stage-level logs, summary tables, figures
- `tests/`: smoke and output-shape tests
- `main.py`: CLI entrypoint for full-grid execution

## Installation

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
```

## Running the Model

Run full experiment grid and generate summary tables, thesis tables, and figures:

```bash
python main.py --n 200
```

For a clean final rebuild with sensitivity exports:

```bash
python main.py --clean --n 1000 --with-sensitivity --sensitivity-n 200
```

Useful options:

- `--n`: runs per `(scenario, asset, route)` cell
- `--outputs`: output directory (default `outputs`)
- `--config`: config directory (default `config`)
- `--clean`: delete the output directory before rebuilding
- `--no-plots`: skip figure generation
- `--no-thesis-exports`: skip thesis-ready and appendix tables
- `--with-sensitivity`: run the default sensitivity suite and export sensitivity CSVs
- `--sensitivity-n`: runs per cell for the sensitivity suite (default `200`)
- `--qualified-private-credit`: use qualified-investor profile for private credit cells
- `--no-qualified-private-credit`: force non-qualified profile for private credit cells

## Model Flow

1. Load and validate config (`sim/config_loader.py`)
2. Run lifecycle simulation (`sim/engine.py`)
3. Apply gates and restrictions (`sim/gates.py`)
4. Apply risk events (`sim/risk.py`)
5. In stress, inject queue-derived waits (`sim/queues.py` + `sim/hybrid.py`)
6. Aggregate outputs (`sim/metrics.py`, `sim/reporting.py`)
7. Generate figures (`sim/plots.py`)

## Key Technical Notes

- Canonical stages are defined once (`config/stages.yaml`), and each route must define all canonical stages.
- Queue inflows are driven by scenario demand assumptions (`config/scenarios.yaml` arrivals), with queue-file rates as fallback defaults.
- Queue wait distributions are built once per grid cell for performance and consistency.
- Gate outcomes and risk outcomes are tracked separately (`gate_events` vs `risk_events`) for cleaner interpretation.
- Route-level redemption rules (`redemption_hold_probability`, `redemption_reject_probability`, `hold_delay_hours`) are enforced in execution logic.
- Risk events support `applicable_routes` filtering: tokenized-specific risks (governance pause, transfer blocks, attestation delays) only affect tokenized runs.
- Exception handling overhead is route-specific and config-driven (sourced from the disabled `EXCEPTION_HANDLING` stage in each route config).
- Route configs may include small asset-specific stage-time adders (`asset_time_adders_hours`) to capture light route x asset interactions without changing global asset mechanics.
- Queue service assumptions support modest per-route efficiency multipliers, allowing stress backlogs to remain comparable while still reflecting route-specific operating models.
- Scenario multipliers support per-route overrides (falls back to `default` key).

## Outputs

### Per-cell raw outputs

- `outputs/runs/runs_<SCENARIO>__<ASSET>__<ROUTE>__N<n>.csv`
- `outputs/stages/stages_<SCENARIO>__<ASSET>__<ROUTE>__N<n>.csv`

### Aggregated tables

- `outputs/tables/summary_runs__N<n>.csv`
- `outputs/tables/summary_transfer__N<n>.csv`
- `outputs/tables/summary_risk__N<n>.csv`
- `outputs/tables/summary_gate__N<n>.csv`
- `outputs/tables/summary_access__N<n>.csv`
- `outputs/tables/summary_delay_attribution__N<n>.csv`
- `outputs/tables/kpi_overview__N<n>.csv`
- `outputs/tables/route_deltas__N<n>.csv`
- `outputs/tables/stage_time_mix__N<n>.csv`
- `outputs/tables/headline_conclusions__N<n>.csv`
- `outputs/tables/kpi_glossary.csv`
- `outputs/tables/thesis_table_6_1_overall__N<n>.csv`
- `outputs/tables/thesis_table_6_2_access__N<n>.csv`
- `outputs/tables/thesis_table_6_2_operational__N<n>.csv`
- `outputs/tables/thesis_table_6_3_stage_drivers__N<n>.csv`
- `outputs/tables/appendix_table_A1_asset_mechanics.csv`
- `outputs/tables/appendix_table_A2_scenario_and_queue_assumptions.csv`
- `outputs/tables/appendix_table_A3_route_level_parameter_assumptions.csv`
- `outputs/tables/appendix_table_A4_risk_event_parameter_assumptions.csv`
- `outputs/tables/appendix_table_B1_experimental_grid_and_reporting_profile.csv`
- `outputs/tables/appendix_table_B2_queue_setup_under_baseline_and_stress_conditions.csv`
- `outputs/tables/appendix_table_C1_canonical_lifecycle_stages_used_in_the_simulation.csv`
- `outputs/tables/appendix_table_D1_structural_gates_and_rule_based_restrictions.csv`
- `outputs/tables/appendix_table_D2_stochastic_risk_events.csv`
- `outputs/tables/appendix_table_E1_full_kpi_overview__N<n>.csv`
- `outputs/tables/appendix_table_E2_route_deltas_tokenized_minus_tradfi__N<n>.csv`
- `outputs/tables/appendix_table_E3_stage_driver_breakdown__N<n>.csv`
- `outputs/tables/appendix_table_E4_access_outcomes__N<n>.csv`
- `outputs/tables/appendix_table_E5_gate_marker_summary__N<n>.csv`
- `outputs/tables/appendix_table_E6_risk_event_summary__N<n>.csv`
- `outputs/tables/appendix_table_E7_delay_attribution_summary__N<n>.csv`
- `outputs/tables/appendix_table_G1_validation_and_reproducibility_features.csv`

### Figures

Saved in `outputs/figures/`.

### Sensitivity tables

Generated when `--with-sensitivity` is used:

- `outputs/tables/sensitivity_kyc_servers__N<n>.csv`
- `outputs/tables/sensitivity_red_servers__N<n>.csv`
- `outputs/tables/sensitivity_allowlist__N<n>.csv`
- `outputs/tables/sensitivity_compact_kyc__N<n>.csv`
- `outputs/tables/sensitivity_compact_red__N<n>.csv`
- `outputs/tables/sensitivity_compact_allowlist__N<n>.csv`
- `outputs/tables/appendix_table_F1_kyc_queue_capacity_sensitivity__N<n>.csv`
- `outputs/tables/appendix_table_F2_tokenized_allowlist_sensitivity__N<n>.csv`
- `outputs/tables/appendix_table_F3_redemption_capacity_sensitivity__N<n>.csv`

## Validation and Safety Checks

Config loading now enforces:

- Probability bounds `[0, 1]` for gating and risk probabilities
- Valid distribution specs (`fixed`, `triangular`, `lognormal`)
- Triangular parameter consistency (`low <= mode <= high`)
- Non-negative costs/friction counts
- Positive scenario multipliers
- Queue server/rate/horizon sanity checks
- Stage consistency across canonical stages, routes, and risk triggers
- Non-negative hold delay values for redemption rules

## Testing

Run tests:

```bash
pytest
```

Core tests cover:

- Config and engine smoke behavior
- Eligibility blocking behavior
- Runner output schema and CSV generation

## Reproducibility

- Scenario seeds are configured in `config/scenarios.yaml`.
- Lifecycle RNG uses deterministic run-based seeding.
- Queue simulation uses deterministic scenario-specific seeding.

## Interactive Dashboard

Launch the Streamlit dashboard for interactive exploration:

```bash
streamlit run dashboard/Home.py
```

Pages include:

- **Home** -- headline KPI cards and route delta summary
- **Lifecycle Race** -- animated side-by-side stage progression (TradFi vs Tokenized)
- **Deep Dive** -- interactive Plotly charts (waterfall, distributions, heatmap)
- **Parameter Sandbox** -- tweak parameters and re-run the simulation live
- **Data Export** -- browse and download all thesis-ready tables

## Recommended Thesis Workflow

1. Run small `N` for sanity (e.g., `N=50` or `N=200`)
2. Validate output shapes and directional behavior
3. Run final `N` for reporting (e.g., `N=1000`)
4. Export thesis tables and figures from `main.py` / `sim/plots.py`
5. Maintain a parameter/assumptions table for traceability and sensitivity ranges
