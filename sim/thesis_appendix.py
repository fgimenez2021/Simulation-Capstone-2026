from __future__ import annotations

from typing import Dict

import pandas as pd

from .analysis import apply_standard_ordering
from .assumption_appendix import (
    STATIC_APPENDIX_TABLE_NAMES as ASSUMPTION_STATIC_APPENDIX_TABLE_NAMES,
    build_assumption_appendix_tables,
)
from .types import ModelConfig

STATIC_APPENDIX_TABLE_NAMES = ASSUMPTION_STATIC_APPENDIX_TABLE_NAMES | {
    "appendix_table_B1_experimental_grid_and_reporting_profile",
    "appendix_table_B2_queue_setup_under_baseline_and_stress_conditions",
    "appendix_table_C1_canonical_lifecycle_stages_used_in_the_simulation",
    "appendix_table_D1_structural_gates_and_rule_based_restrictions",
    "appendix_table_D2_stochastic_risk_events",
    "appendix_table_G1_validation_and_reproducibility_features",
}

SCENARIO_DISPLAY = {"BASELINE": "Baseline", "STRESS": "Stress"}
ASSET_DISPLAY = {"TBILL_MMF": "T-bill / MMF", "PRIVATE_CREDIT": "Private credit"}
ROUTE_DISPLAY = {"TRADFI": "TradFi", "TOKENIZED": "Tokenized"}
YES_NO = {False: "No", True: "Yes"}

STAGE_OPERATIONAL_MEANINGS = {
    "ONBOARDING": "Initial account setup, entity intake, and platform registration.",
    "KYC_REVIEW": "Identity, AML/KYB, and compliance review before access is granted.",
    "ELIGIBILITY_GATE": "Suitability, allowlist, and investor-qualification checks.",
    "ORDER_PLACEMENT": "Investor submits the order or investment instruction.",
    "EXECUTION": "Trade or subscription is executed on the chosen route.",
    "CLEARING_SETTLEMENT": "Cash and position settlement completes on the route.",
    "CUSTODY_RECORDING": "The resulting position is booked and reflected in custody records.",
    "SERVICING_REPORTING": "Initial servicing, reporting, or attestation setup is completed.",
    "TRANSFERABILITY": "A secondary transfer attempt is processed under route rules.",
    "EXIT_INITIATION": "The investor starts the exit or redemption request.",
    "REDEMPTION_PROCESSING": "Redemption operations and settlement-to-cash are completed.",
}

STAGE_DRIVER_STAGE_IDS = [
    "CLEARING_SETTLEMENT",
    "KYC_REVIEW",
    "ONBOARDING",
    "REDEMPTION_PROCESSING",
    "TRANSFERABILITY",
]
STAGE_DRIVER_COLUMN_LABELS = {
    "CLEARING_SETTLEMENT": "Clearing and settlement (mean hours)",
    "KYC_REVIEW": "KYC review (mean hours)",
    "ONBOARDING": "Onboarding (mean hours)",
    "REDEMPTION_PROCESSING": "Redemption processing (mean hours)",
    "TRANSFERABILITY": "Transferability (mean hours)",
}


def build_static_appendix_tables(model: ModelConfig) -> Dict[str, pd.DataFrame]:
    tables = build_assumption_appendix_tables(model)
    tables.update(
        {
            "appendix_table_B1_experimental_grid_and_reporting_profile": _table_b1_experimental_grid(model),
            "appendix_table_B2_queue_setup_under_baseline_and_stress_conditions": _table_b2_queue_setup(model),
            "appendix_table_C1_canonical_lifecycle_stages_used_in_the_simulation": _table_c1_stage_map(model),
            "appendix_table_D1_structural_gates_and_rule_based_restrictions": _table_d1_structural_gates(model),
            "appendix_table_D2_stochastic_risk_events": _table_d2_risk_events(model),
            "appendix_table_G1_validation_and_reproducibility_features": _table_g1_reproducibility(model),
        }
    )
    return tables


def _display_scenario(scenario_id: str) -> str:
    return SCENARIO_DISPLAY.get(scenario_id, scenario_id)


def _display_asset(asset_id: str) -> str:
    return ASSET_DISPLAY.get(asset_id, asset_id)


def _display_route(route_id: str) -> str:
    return ROUTE_DISPLAY.get(route_id, route_id)


def _yes_no(flag: bool) -> str:
    return YES_NO[bool(flag)]


def _route_multiplier(multipliers: dict[str, float], route_id: str) -> float:
    return float(multipliers.get(route_id, multipliers.get("default", 1.0)))


def _fmt_distribution(dist: str, params: dict[str, float]) -> str:
    if dist == "fixed":
        return f"{float(params.get('value', 0.0)):g}"
    if dist == "triangular":
        return f"({float(params['low']):g}, {float(params['mode']):g}, {float(params['high']):g})"
    return str(params)


def _select_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out.columns:
            out[col] = pd.NA
    return out[cols].copy()


def _round_columns(df: pd.DataFrame, round_map: Dict[str, int]) -> pd.DataFrame:
    out = df.copy()
    for col, digits in round_map.items():
        out[col] = pd.to_numeric(out[col], errors="coerce").round(digits)
    return out


def _friendly_axes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "scenario_id" in out.columns:
        out["scenario_id"] = out["scenario_id"].map(lambda value: _display_scenario(str(value)))
        out = out.rename(columns={"scenario_id": "Scenario"})
    if "asset_id" in out.columns:
        out["asset_id"] = out["asset_id"].map(lambda value: _display_asset(str(value)))
        out = out.rename(columns={"asset_id": "Asset"})
    if "route_id" in out.columns:
        out["route_id"] = out["route_id"].map(lambda value: _display_route(str(value)))
        out = out.rename(columns={"route_id": "Route"})
    return out


def _format_route_scope(applicable_routes: tuple[str, ...]) -> str:
    if not applicable_routes:
        return "Both routes"
    return ", ".join(_display_route(route_id) for route_id in applicable_routes)


def _format_outcome_flags(event) -> str:
    flags: list[str] = []
    if event.flags.blocks_progress:
        flags.append("blocks_progress")
    if event.flags.freezes_exit:
        flags.append("freezes_exit")
    if event.outcomes and event.outcomes.transfer_success is not None:
        flags.append(f"transfer_success={str(event.outcomes.transfer_success).lower()}")
    return ", ".join(flags) if flags else "none"


def _extract_sensitivity_n(df: pd.DataFrame) -> int:
    n_values = pd.to_numeric(df.get("N"), errors="coerce").dropna()
    return int(n_values.iloc[0]) if not n_values.empty else 0


def build_results_appendix_tables(
    *,
    kpi_overview: pd.DataFrame,
    route_deltas: pd.DataFrame,
    stage_time_mix: pd.DataFrame,
    summary_access: pd.DataFrame,
    summary_gate: pd.DataFrame,
    summary_risk: pd.DataFrame,
    summary_delay_attribution: pd.DataFrame,
    sensitivity_kyc: pd.DataFrame | None = None,
    sensitivity_redemption: pd.DataFrame | None = None,
    sensitivity_allowlist: pd.DataFrame | None = None,
) -> tuple[Dict[str, pd.DataFrame], Dict[str, int]]:
    tables = {
        "appendix_table_E1_full_kpi_overview": _table_e1_full_kpis(kpi_overview),
        "appendix_table_E2_route_deltas_tokenized_minus_tradfi": _table_e2_route_deltas(route_deltas),
        "appendix_table_E3_stage_driver_breakdown": _table_e3_stage_drivers(stage_time_mix),
        "appendix_table_E4_access_outcomes": _table_e4_access_outcomes(summary_access),
        "appendix_table_E5_gate_marker_summary": _table_e5_gate_summary(summary_gate),
        "appendix_table_E6_risk_event_summary": _table_e6_risk_summary(summary_risk),
        "appendix_table_E7_delay_attribution_summary": _table_e7_delay_summary(summary_delay_attribution),
    }
    run_count_overrides: Dict[str, int] = {}

    if sensitivity_kyc is not None and not sensitivity_kyc.empty:
        tables["appendix_table_F1_kyc_queue_capacity_sensitivity"] = _table_f1_kyc_sensitivity(sensitivity_kyc)
        run_count_overrides["appendix_table_F1_kyc_queue_capacity_sensitivity"] = _extract_sensitivity_n(
            sensitivity_kyc
        )
    if sensitivity_allowlist is not None and not sensitivity_allowlist.empty:
        tables["appendix_table_F2_tokenized_allowlist_sensitivity"] = _table_f2_allowlist_sensitivity(
            sensitivity_allowlist
        )
        run_count_overrides["appendix_table_F2_tokenized_allowlist_sensitivity"] = _extract_sensitivity_n(
            sensitivity_allowlist
        )
    if sensitivity_redemption is not None and not sensitivity_redemption.empty:
        tables["appendix_table_F3_redemption_capacity_sensitivity"] = _table_f3_redemption_sensitivity(
            sensitivity_redemption
        )
        run_count_overrides["appendix_table_F3_redemption_capacity_sensitivity"] = _extract_sensitivity_n(
            sensitivity_redemption
        )

    return tables, run_count_overrides


def build_stage_driver_table(stage_time_mix: pd.DataFrame) -> pd.DataFrame:
    cols = ["scenario_id", "asset_id", "route_id", "stage_id", "stage_time_hours_mean"]
    out = _select_columns(stage_time_mix, cols)
    filtered = out[out["stage_id"].isin(STAGE_DRIVER_STAGE_IDS)].copy()
    wide = (
        filtered.pivot_table(
            index=["scenario_id", "asset_id", "route_id"],
            columns="stage_id",
            values="stage_time_hours_mean",
            aggfunc="first",
        )
        .reset_index()
    )
    ordered = ["scenario_id", "asset_id", "route_id", *STAGE_DRIVER_STAGE_IDS]
    wide = apply_standard_ordering(wide.reindex(columns=ordered))
    wide = wide.rename(columns=STAGE_DRIVER_COLUMN_LABELS)
    return _round_columns(wide, {label: 2 for label in STAGE_DRIVER_COLUMN_LABELS.values()})


def _table_b1_experimental_grid(model: ModelConfig) -> pd.DataFrame:
    rows: list[dict] = []
    for scenario_id in ("BASELINE", "STRESS"):
        scenario = model.scenarios[scenario_id]
        for asset_id in ("TBILL_MMF", "PRIVATE_CREDIT"):
            asset = model.assets[asset_id]
            investor_profile = (
                "Qualified institutional investor"
                if asset.eligibility.requires_qualified_investor
                else "Institutional investor"
            )
            for route_id in ("TRADFI", "TOKENIZED"):
                rows.append(
                    {
                        "Scenario": _display_scenario(scenario_id),
                        "Asset": _display_asset(asset_id),
                        "Route": _display_route(route_id),
                        "Reporting investor profile": investor_profile,
                        "Qualification required?": _yes_no(asset.eligibility.requires_qualified_investor),
                        "Queues enabled?": _yes_no(scenario.queues.enabled),
                        "Time multiplier": _route_multiplier(scenario.time_multipliers, route_id),
                        "Risk multiplier": _route_multiplier(scenario.risk_multipliers, route_id),
                        "Cost multiplier": _route_multiplier(scenario.cost_multipliers, route_id),
                        "Redemption window": asset.redemption.window_type,
                        "Notice days": asset.redemption.notice_days,
                        "Settlement-to-cash days": asset.redemption.settlement_days_to_cash,
                    }
                )
    return pd.DataFrame(rows)


def _table_b2_queue_setup(model: ModelConfig) -> pd.DataFrame:
    rows: list[dict] = []
    queue_specs = [
        (
            "KYC / compliance review",
            model.queues.kyc_queue,
            lambda scenario: scenario.arrivals.onboarding_requests_per_day,
        ),
        (
            "Redemption processing",
            model.queues.redemption_queue,
            lambda scenario: scenario.arrivals.redemption_requests_per_day,
        ),
    ]
    for scenario_id in ("BASELINE", "STRESS"):
        scenario = model.scenarios[scenario_id]
        mode = str(scenario.mode)
        for queue_name, queue, demand_selector in queue_specs:
            rows.append(
                {
                    "Scenario": _display_scenario(scenario_id),
                    "Queue": queue_name,
                    "Queues enabled?": _yes_no(scenario.queues.enabled),
                    "Requests per day": demand_selector(scenario),
                    "Servers": getattr(queue.servers, mode),
                    "Service time (hours)": _fmt_distribution(queue.service_time.dist, queue.service_time.params),
                    "TradFi service multiplier": float(
                        queue.service_time_multipliers.get(
                            "TRADFI",
                            queue.service_time_multipliers.get("default", 1.0),
                        )
                    ),
                    "Tokenized service multiplier": float(
                        queue.service_time_multipliers.get(
                            "TOKENIZED",
                            queue.service_time_multipliers.get("default", 1.0),
                        )
                    ),
                    "Queue simulation horizon (days)": int(model.queues.queue_simulation_horizon_days[mode]),
                }
            )
    return pd.DataFrame(rows)


def _table_c1_stage_map(model: ModelConfig) -> pd.DataFrame:
    rows: list[dict] = []
    stage_order = 0
    for stage_id, stage in model.stages.items():
        if stage_id == "EXCEPTION_HANDLING":
            continue
        stage_order += 1
        rows.append(
            {
                "Stage order": stage_order,
                "Stage ID": stage.id,
                "Thesis label": stage.label,
                "Category": stage.category,
                "Operational meaning": STAGE_OPERATIONAL_MEANINGS.get(stage_id, stage.label),
            }
        )
    return pd.DataFrame(rows)


def _table_d1_structural_gates(model: ModelConfig) -> pd.DataFrame:
    tradfi = model.routes["TRADFI"]
    tokenized = model.routes["TOKENIZED"]
    rows = [
        {
            "Mechanism": "Qualified-investor eligibility",
            "Stage": "ELIGIBILITY_GATE",
            "Route scope": "Both routes",
            "Asset scope": "Private credit",
            "Trigger / rule": "Private-credit exposure requires a qualified investor profile.",
            "Configured value": "`PRIVATE_CREDIT.requires_qualified_investor = true`",
            "Outcome if triggered": "Lifecycle is blocked before investment access is granted.",
            "Why structural": "It is an asset-level eligibility rule, not a random exception.",
        },
        {
            "Mechanism": "Suitability / allowlist gate",
            "Stage": "ELIGIBILITY_GATE",
            "Route scope": "TradFi",
            "Asset scope": "Both assets",
            "Trigger / rule": "Investor must pass the configured TradFi suitability gate.",
            "Configured value": f"`allowlist_pass_probability = {tradfi.stages['ELIGIBILITY_GATE'].gating.allowlist_pass_probability:g}`",
            "Outcome if triggered": "Run records `GATE_DENIED:allowlist_failed` and does not proceed.",
            "Why structural": "The check happens deterministically for every run at the same stage.",
        },
        {
            "Mechanism": "Suitability / allowlist gate",
            "Stage": "ELIGIBILITY_GATE",
            "Route scope": "Tokenized",
            "Asset scope": "Both assets",
            "Trigger / rule": "Investor wallet and profile must pass the tokenized allowlist gate.",
            "Configured value": f"`allowlist_pass_probability = {tokenized.stages['ELIGIBILITY_GATE'].gating.allowlist_pass_probability:g}`",
            "Outcome if triggered": "Run records `GATE_DENIED:allowlist_failed` and does not proceed.",
            "Why structural": "The route is designed around rule-based access control before execution.",
        },
        {
            "Mechanism": "Transfer restriction",
            "Stage": "TRANSFERABILITY",
            "Route scope": "TradFi",
            "Asset scope": "Both assets",
            "Trigger / rule": "Transfer attempt is checked against TradFi restriction logic before success is recorded.",
            "Configured value": f"`transfer_pass_probability = {tradfi.stages['TRANSFERABILITY'].restrictions.transfer_pass_probability:g}`",
            "Outcome if triggered": "Transfer is marked unsuccessful even though the stage is attempted.",
            "Why structural": "This is embedded route logic rather than a stochastic incident.",
        },
        {
            "Mechanism": "Transfer restriction",
            "Stage": "TRANSFERABILITY",
            "Route scope": "Tokenized",
            "Asset scope": "Both assets",
            "Trigger / rule": "Secondary transfer requires an allowlisted counterparty under tokenized rules.",
            "Configured value": f"`transfer_pass_probability = {tokenized.stages['TRANSFERABILITY'].restrictions.transfer_pass_probability:g}`",
            "Outcome if triggered": "Transfer is blocked by the route rule before completion is recorded.",
            "Why structural": "This is deterministic smart-contract or admin restriction logic.",
        },
        {
            "Mechanism": "Tokenized redemption hold by rules",
            "Stage": "REDEMPTION_PROCESSING",
            "Route scope": "Tokenized",
            "Asset scope": "Both assets",
            "Trigger / rule": "Tokenized redemption rules can place an otherwise valid exit on hold.",
            "Configured value": (
                f"`hold_probability = {tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.redemption_hold_probability:g}; "
                f"hold_delay_hours = {tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.hold_delay_hours:g}; "
                f"hold_delay_hours_stress = {tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.hold_delay_hours_stress:g}`"
            ),
            "Outcome if triggered": "The run remains active but receives the configured deterministic hold delay.",
            "Why structural": "The route hard-codes a redemption-control branch instead of sampling a separate event library entry.",
        },
        {
            "Mechanism": "Tokenized redemption reject by rules",
            "Stage": "REDEMPTION_PROCESSING",
            "Route scope": "Tokenized",
            "Asset scope": "Both assets",
            "Trigger / rule": "Tokenized redemption rules can reject an exit request outright.",
            "Configured value": f"`redemption_reject_probability = {tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.redemption_reject_probability:g}`",
            "Outcome if triggered": "Exit is frozen and the run records a rejected redemption outcome.",
            "Why structural": "The rule is part of the configured route logic rather than a separate operational shock.",
        },
    ]
    return pd.DataFrame(rows)


def _table_d2_risk_events(model: ModelConfig) -> pd.DataFrame:
    rows: list[dict] = []
    for event in model.risk_events:
        rows.append(
            {
                "Risk event": event.id,
                "Label": event.label,
                "Stage(s)": ", ".join(event.trigger_stages),
                "Route scope": _format_route_scope(event.applicable_routes),
                "Base probability": round(float(event.base_probability), 4),
                "Delay impact (hours)": _fmt_distribution(
                    event.impacts.add_time_hours.dist,
                    event.impacts.add_time_hours.params,
                ),
                "Cost impact": (
                    f"explicit +{event.impacts.add_explicit_cost:g}; "
                    f"implicit +{event.impacts.add_implicit_cost:g}"
                ),
                "Outcome flags": _format_outcome_flags(event),
            }
        )
    return pd.DataFrame(rows)


def _table_g1_reproducibility(model: ModelConfig) -> pd.DataFrame:
    rows = [
        {
            "Item": "Scenario seeds",
            "Value / method": ", ".join(
                f"{_display_scenario(sid)} = {model.scenarios[sid].seed}" for sid in ("BASELINE", "STRESS")
            ),
            "Evidence / location": "`config/scenarios.yaml`",
        },
        {
            "Item": "Deterministic lifecycle seeding",
            "Value / method": "Lifecycle runs use deterministic run-based random seeds.",
            "Evidence / location": "`sim/engine.py`",
        },
        {
            "Item": "Deterministic queue simulation",
            "Value / method": "Queue wait-time generation uses scenario-specific seeded simulation.",
            "Evidence / location": "`sim/queues.py`, `sim/hybrid.py`",
        },
        {
            "Item": "Raw output export",
            "Value / method": "Per-cell run logs and stage logs are exported as CSVs.",
            "Evidence / location": "`outputs/runs/`, `outputs/stages/`",
        },
        {
            "Item": "Config validation",
            "Value / method": "Typed config loading enforces distribution, probability, and consistency checks.",
            "Evidence / location": "`sim/config_loader.py`",
        },
        {
            "Item": "Automated testing",
            "Value / method": "Pytest covers smoke behavior, output schema, and thesis export regression cases.",
            "Evidence / location": "`tests/`",
        },
        {
            "Item": "Config-driven reproducibility",
            "Value / method": "A clean rebuild path regenerates outputs from YAML config plus CLI flags.",
            "Evidence / location": "`main.py`, `config/`",
        },
    ]
    return pd.DataFrame(rows)


def _table_e1_full_kpis(kpi_overview: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "total_time_days_p50",
        "total_time_days_p50_ci95_low",
        "total_time_days_p50_ci95_high",
        "time_to_cash_days_p50",
        "time_to_cash_days_p50_ci95_low",
        "time_to_cash_days_p50_ci95_high",
        "total_explicit_cost_mean",
        "total_implicit_cost_mean",
        "total_cost_mean",
    ]
    out = apply_standard_ordering(_select_columns(kpi_overview, cols))
    out["completion_rate"] = pd.to_numeric(out["completion_rate"], errors="coerce") * 100.0
    out["exit_frozen_rate"] = pd.to_numeric(out["exit_frozen_rate"], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "completion_rate": "Completion rate (%)",
            "exit_frozen_rate": "Exit frozen rate (%)",
            "total_time_days_p50": "Median total time (days)",
            "total_time_days_p50_ci95_low": "Total time CI95 low",
            "total_time_days_p50_ci95_high": "Total time CI95 high",
            "time_to_cash_days_p50": "Median time to cash (days)",
            "time_to_cash_days_p50_ci95_low": "Time-to-cash CI95 low",
            "time_to_cash_days_p50_ci95_high": "Time-to-cash CI95 high",
            "total_explicit_cost_mean": "Mean explicit cost",
            "total_implicit_cost_mean": "Mean implicit cost",
            "total_cost_mean": "Mean total cost",
        }
    )
    return _round_columns(
        out,
        {
            "Completion rate (%)": 2,
            "Exit frozen rate (%)": 2,
            "Median total time (days)": 2,
            "Total time CI95 low": 2,
            "Total time CI95 high": 2,
            "Median time to cash (days)": 2,
            "Time-to-cash CI95 low": 2,
            "Time-to-cash CI95 high": 2,
            "Mean explicit cost": 2,
            "Mean implicit cost": 2,
            "Mean total cost": 2,
        },
    )


def _table_e2_route_deltas(route_deltas: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "delta_time_to_cash_days_p50",
        "delta_total_time_days_p50",
        "delta_total_cost_mean",
        "delta_completion_rate_pp",
        "delta_exit_frozen_rate_pp",
    ]
    out = apply_standard_ordering(_select_columns(route_deltas, cols))
    out = _friendly_axes(out).rename(
        columns={
            "delta_time_to_cash_days_p50": "Delta time to cash (days)",
            "delta_total_time_days_p50": "Delta total time (days)",
            "delta_total_cost_mean": "Delta mean total cost",
            "delta_completion_rate_pp": "Delta completion rate (pp)",
            "delta_exit_frozen_rate_pp": "Delta exit frozen rate (pp)",
        }
    )
    return _round_columns(
        out,
        {
            "Delta time to cash (days)": 2,
            "Delta total time (days)": 2,
            "Delta mean total cost": 2,
            "Delta completion rate (pp)": 2,
            "Delta exit frozen rate (pp)": 2,
        },
    )


def _table_e3_stage_drivers(stage_time_mix: pd.DataFrame) -> pd.DataFrame:
    return _friendly_axes(build_stage_driver_table(stage_time_mix))


def _table_e4_access_outcomes(summary_access: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "N_onboarding_runs",
        "onboarding_success_rate",
        "N_transfer_attempts",
        "transfer_success_rate",
        "N_redemption_attempts",
        "redemption_allowed_rate",
    ]
    out = apply_standard_ordering(_select_columns(summary_access, cols))
    for col in ("onboarding_success_rate", "transfer_success_rate", "redemption_allowed_rate"):
        out[col] = pd.to_numeric(out[col], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "N_onboarding_runs": "Onboarding runs",
            "onboarding_success_rate": "Onboarding success (%)",
            "N_transfer_attempts": "Transfer attempts",
            "transfer_success_rate": "Transfer success (%)",
            "N_redemption_attempts": "Redemption attempts",
            "redemption_allowed_rate": "Redemption allowed (%)",
        }
    )
    return _round_columns(
        out,
        {
            "Onboarding success (%)": 2,
            "Transfer success (%)": 2,
            "Redemption allowed (%)": 2,
        },
    )


def _table_e5_gate_summary(summary_gate: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "N_stage_rows",
        "gate_event_rate_per_stage_row",
        "unique_gate_event_ids_observed",
    ]
    out = apply_standard_ordering(_select_columns(summary_gate, cols))
    out["gate_event_rate_per_stage_row"] = pd.to_numeric(
        out["gate_event_rate_per_stage_row"], errors="coerce"
    ) * 100.0
    out["unique_gate_event_ids_observed"] = (
        out["unique_gate_event_ids_observed"].fillna("").astype(str).str.replace(";", ", ", regex=False)
    )
    out = _friendly_axes(out).rename(
        columns={
            "N_stage_rows": "Stage rows observed",
            "gate_event_rate_per_stage_row": "Gate check/outcome rate per stage row (%)",
            "unique_gate_event_ids_observed": "Observed gate markers",
        }
    )
    return _round_columns(out, {"Gate check/outcome rate per stage row (%)": 2})


def _table_e6_risk_summary(summary_risk: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "N_stage_rows",
        "risk_event_rate_per_stage_row",
        "unique_risk_event_ids_observed",
    ]
    out = apply_standard_ordering(_select_columns(summary_risk, cols))
    out["risk_event_rate_per_stage_row"] = pd.to_numeric(
        out["risk_event_rate_per_stage_row"], errors="coerce"
    ) * 100.0
    out["unique_risk_event_ids_observed"] = (
        out["unique_risk_event_ids_observed"].fillna("").astype(str).str.replace(";", ", ", regex=False)
    )
    out = _friendly_axes(out).rename(
        columns={
            "N_stage_rows": "Stage rows observed",
            "risk_event_rate_per_stage_row": "Risk event rate per stage row (%)",
            "unique_risk_event_ids_observed": "Observed risk event IDs",
        }
    )
    return _round_columns(out, {"Risk event rate per stage row (%)": 2})


def _table_e7_delay_summary(summary_delay_attribution: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "scenario_id",
        "asset_id",
        "route_id",
        "queue_delay_hours_mean_per_run",
        "risk_delay_hours_mean_per_run",
        "exception_delay_hours_mean_per_run",
        "gate_delay_hours_mean_per_run",
        "queue_delay_share_of_total_time_mean",
        "risk_delay_share_of_total_time_mean",
        "exception_delay_share_of_total_time_mean",
        "gate_delay_share_of_total_time_mean",
    ]
    out = apply_standard_ordering(_select_columns(summary_delay_attribution, cols))
    for col in (
        "queue_delay_share_of_total_time_mean",
        "risk_delay_share_of_total_time_mean",
        "exception_delay_share_of_total_time_mean",
        "gate_delay_share_of_total_time_mean",
    ):
        out[col] = pd.to_numeric(out[col], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "queue_delay_hours_mean_per_run": "Queue delay mean per run (hours)",
            "risk_delay_hours_mean_per_run": "Risk delay mean per run (hours)",
            "exception_delay_hours_mean_per_run": "Exception delay mean per run (hours)",
            "gate_delay_hours_mean_per_run": "Gate delay mean per run (hours)",
            "queue_delay_share_of_total_time_mean": "Queue delay share (%)",
            "risk_delay_share_of_total_time_mean": "Risk delay share (%)",
            "exception_delay_share_of_total_time_mean": "Exception delay share (%)",
            "gate_delay_share_of_total_time_mean": "Gate delay share (%)",
        }
    )
    return _round_columns(
        out,
        {
            "Queue delay mean per run (hours)": 2,
            "Risk delay mean per run (hours)": 2,
            "Exception delay mean per run (hours)": 2,
            "Gate delay mean per run (hours)": 2,
            "Queue delay share (%)": 2,
            "Risk delay share (%)": 2,
            "Exception delay share (%)": 2,
            "Gate delay share (%)": 2,
        },
    )


def _table_f1_kyc_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["scenario_id"] == "STRESS"].copy()
    out["KYC stress setting"] = out["tag"].astype(str).str.replace("KYC_stress_servers=", "", regex=False)
    cols = [
        "KYC stress setting",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_days_p50",
        "total_time_days_p50",
    ]
    out = apply_standard_ordering(_select_columns(out, cols))
    out["completion_rate"] = pd.to_numeric(out["completion_rate"], errors="coerce") * 100.0
    out["exit_frozen_rate"] = pd.to_numeric(out["exit_frozen_rate"], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "completion_rate": "Completion rate (%)",
            "exit_frozen_rate": "Exit frozen rate (%)",
            "time_to_cash_days_p50": "Median time to cash (days)",
            "total_time_days_p50": "Median total time (days)",
        }
    )
    return _round_columns(
        out,
        {
            "Completion rate (%)": 2,
            "Exit frozen rate (%)": 2,
            "Median time to cash (days)": 2,
            "Median total time (days)": 2,
        },
    )


def _table_f2_allowlist_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    out = df[(df["scenario_id"] == "BASELINE") & (df["route_id"] == "TOKENIZED")].copy()
    out["Allowlist setting"] = out["tag"].astype(str).str.replace("ALLOWLIST_p=", "p = ", regex=False)
    cols = [
        "Allowlist setting",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_days_p50",
        "total_time_days_p50",
    ]
    out = apply_standard_ordering(_select_columns(out, cols))
    out["completion_rate"] = pd.to_numeric(out["completion_rate"], errors="coerce") * 100.0
    out["exit_frozen_rate"] = pd.to_numeric(out["exit_frozen_rate"], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "completion_rate": "Completion rate (%)",
            "exit_frozen_rate": "Exit frozen rate (%)",
            "time_to_cash_days_p50": "Median time to cash (days)",
            "total_time_days_p50": "Median total time (days)",
        }
    )
    return _round_columns(
        out,
        {
            "Completion rate (%)": 2,
            "Exit frozen rate (%)": 2,
            "Median time to cash (days)": 2,
            "Median total time (days)": 2,
        },
    )


def _table_f3_redemption_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["scenario_id"] == "STRESS"].copy()
    out["Redemption stress setting"] = out["tag"].astype(str).str.replace(
        "REDEMPTION_stress_servers=",
        "",
        regex=False,
    )
    cols = [
        "Redemption stress setting",
        "asset_id",
        "route_id",
        "completion_rate",
        "exit_frozen_rate",
        "time_to_cash_days_p50",
        "total_time_days_p50",
    ]
    out = apply_standard_ordering(_select_columns(out, cols))
    out["completion_rate"] = pd.to_numeric(out["completion_rate"], errors="coerce") * 100.0
    out["exit_frozen_rate"] = pd.to_numeric(out["exit_frozen_rate"], errors="coerce") * 100.0
    out = _friendly_axes(out).rename(
        columns={
            "completion_rate": "Completion rate (%)",
            "exit_frozen_rate": "Exit frozen rate (%)",
            "time_to_cash_days_p50": "Median time to cash (days)",
            "total_time_days_p50": "Median total time (days)",
        }
    )
    return _round_columns(
        out,
        {
            "Completion rate (%)": 2,
            "Exit frozen rate (%)": 2,
            "Median time to cash (days)": 2,
            "Median total time (days)": 2,
        },
    )
