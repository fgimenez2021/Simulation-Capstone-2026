from __future__ import annotations

from typing import Dict

import pandas as pd

from .types import ModelConfig, RouteConfig

STATIC_APPENDIX_TABLE_NAMES = {
    "appendix_table_A1_asset_mechanics",
    "appendix_table_A2_scenario_and_queue_assumptions",
    "appendix_table_A3_route_level_parameter_assumptions",
    "appendix_table_A4_risk_event_parameter_assumptions",
}


def build_assumption_appendix_tables(model: ModelConfig) -> Dict[str, pd.DataFrame]:
    return {
        "appendix_table_A1_asset_mechanics": _table_a1_asset_mechanics(model),
        "appendix_table_A2_scenario_and_queue_assumptions": _table_a2_scenarios_and_queues(model),
        "appendix_table_A3_route_level_parameter_assumptions": _table_a3_route_level(model),
        "appendix_table_A4_risk_event_parameter_assumptions": _table_a4_risk_events(model),
    }


def _table_a1_asset_mechanics(model: ModelConfig) -> pd.DataFrame:
    liquid = model.assets["TBILL_MMF"].redemption
    illiquid = model.assets["PRIVATE_CREDIT"].redemption
    rows = [
        {
            "Config area": "`config/assets.yaml`",
            "Parameter(s)": "`TBILL_MMF.redemption.window_type / notice_days / settlement_days_to_cash`",
            "Current value": f"`{liquid.window_type} / {_fmt_num(liquid.notice_days)} / {_fmt_num(liquid.settlement_days_to_cash)}`",
            "Status": "`Direct evidence`",
            "Source support": "Franklin Templeton Trust (2025)",
            "Notes": "Franklin's prospectus supports business-day redeemability and typical next-business-day processing.",
        },
        {
            "Config area": "`config/assets.yaml`",
            "Parameter(s)": "`PRIVATE_CREDIT.redemption.window_type / notice_days / settlement_days_to_cash`",
            "Current value": f"`{illiquid.window_type} / {_fmt_num(illiquid.notice_days)} / {_fmt_num(illiquid.settlement_days_to_cash)}`",
            "Status": "`Direct evidence`",
            "Source support": "OneAscent Capital Opportunities Fund (2025)",
            "Notes": "Prospectus supports quarterly repurchase windows, an approximately 30-day notice period, and payment no more than seven days after the repurchase pricing date.",
        },
    ]
    return pd.DataFrame(rows)


def _table_a2_scenarios_and_queues(model: ModelConfig) -> pd.DataFrame:
    baseline = model.scenarios["BASELINE"]
    stress = model.scenarios["STRESS"]
    q = model.queues
    rows = [
        {
            "Group": "Scenario settings",
            "Config area": "`config/scenarios.yaml`",
            "Parameter(s)": "`BASELINE.arrivals.onboarding_requests_per_day / redemption_requests_per_day`",
            "Current value": f"`{_fmt_num(baseline.arrivals.onboarding_requests_per_day)} / {_fmt_num(baseline.arrivals.redemption_requests_per_day)}`",
            "Status": "`Scenario assumption`",
            "Source support": "None for exact counts",
            "Notes": "Chosen to create a stable low-congestion benchmark; aligned with queue defaults.",
        },
        {
            "Group": "Scenario settings",
            "Config area": "`config/scenarios.yaml`",
            "Parameter(s)": "`STRESS.arrivals.onboarding_requests_per_day / redemption_requests_per_day`",
            "Current value": f"`{_fmt_num(stress.arrivals.onboarding_requests_per_day)} / {_fmt_num(stress.arrivals.redemption_requests_per_day)}`",
            "Status": "`Scenario assumption`",
            "Source support": "None for exact counts",
            "Notes": "Chosen to create visible backlog conditions without overwhelming the simulation.",
        },
        {
            "Group": "Scenario settings",
            "Config area": "`config/scenarios.yaml`",
            "Parameter(s)": "`STRESS.time_multipliers.default / TRADFI / TOKENIZED`",
            "Current value": f"`{_fmt_num(stress.time_multipliers['default'])} / {_fmt_num(stress.time_multipliers['TRADFI'])} / {_fmt_num(stress.time_multipliers['TOKENIZED'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Agur et al. (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Literature supports greater stress sensitivity for legacy/manual infrastructure than programmable settlement.",
        },
        {
            "Group": "Scenario settings",
            "Config area": "`config/scenarios.yaml`",
            "Parameter(s)": "`STRESS.cost_multipliers.default`",
            "Current value": f"`{_fmt_num(stress.cost_multipliers['default'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Small uplift kept to preserve current cost ranking without overstating crisis cost inflation.",
        },
        {
            "Group": "Scenario settings",
            "Config area": "`config/scenarios.yaml`",
            "Parameter(s)": "`STRESS.risk_multipliers.default / TRADFI / TOKENIZED`",
            "Current value": f"`{_fmt_num(stress.risk_multipliers['default'])} / {_fmt_num(stress.risk_multipliers['TRADFI'])} / {_fmt_num(stress.risk_multipliers['TOKENIZED'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Stress increases operational risk in both routes, but tokenized rails retain some automation benefit.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`kyc_queue.servers.baseline / stress`",
            "Current value": f"`{_fmt_num(q.kyc_queue.servers.baseline)} / {_fmt_num(q.kyc_queue.servers.stress)}`",
            "Status": "`Scenario assumption`",
            "Source support": "Financial Action Task Force (2021)",
            "Notes": "Reviewer-safe framing: operational capacity assumption for stress testing.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`kyc_queue.service_time`",
            "Current value": f"`{_fmt_dist_hours(q.kyc_queue.service_time.params['low'], q.kyc_queue.service_time.params['mode'], q.kyc_queue.service_time.params['high'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Supports off-chain compliance review with some digital efficiency in tokenized onboarding.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`kyc_queue.service_time_multipliers.TRADFI / TOKENIZED`",
            "Current value": f"`{_fmt_num(q.kyc_queue.service_time_multipliers['TRADFI'])} / {_fmt_num(q.kyc_queue.service_time_multipliers['TOKENIZED'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Tiny tokenized advantage added only to make stress mechanics route-aware without shifting results.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`redemption_queue.servers.baseline / stress`",
            "Current value": f"`{_fmt_num(q.redemption_queue.servers.baseline)} / {_fmt_num(q.redemption_queue.servers.stress)}`",
            "Status": "`Scenario assumption`",
            "Source support": "Franklin Templeton Trust (2025); Ondo Finance (n.d.-d)",
            "Notes": "Conservative capacity compression under stress.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`redemption_queue.service_time`",
            "Current value": f"`{_fmt_dist_hours(q.redemption_queue.service_time.params['low'], q.redemption_queue.service_time.params['mode'], q.redemption_queue.service_time.params['high'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Franklin Templeton Trust (2025); Ondo Finance (n.d.-d); International Organization of Securities Commissions (2025); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Reflects issuer/admin processing for both routes.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`redemption_queue.service_time_multipliers.TRADFI / TOKENIZED`",
            "Current value": f"`{_fmt_num(q.redemption_queue.service_time_multipliers['TRADFI'])} / {_fmt_num(q.redemption_queue.service_time_multipliers['TOKENIZED'])}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Franklin Templeton Trust (2025); Ondo Finance (n.d.-d); International Organization of Securities Commissions (2025); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Very small tokenized service edge retained to avoid materially changing outputs.",
        },
        {
            "Group": "Queue assumptions",
            "Config area": "`config/queues.yaml`",
            "Parameter(s)": "`queue_simulation_horizon_days.baseline / stress`",
            "Current value": f"`{_fmt_num(q.queue_simulation_horizon_days['baseline'])} / {_fmt_num(q.queue_simulation_horizon_days['stress'])}`",
            "Status": "`Structural model choice`",
            "Source support": "None for exact days",
            "Notes": "Chosen to estimate queue waiting-time distributions, not to simulate full market history.",
        },
    ]
    return pd.DataFrame(rows)


def _table_a3_route_level(model: ModelConfig) -> pd.DataFrame:
    tradfi = model.routes["TRADFI"]
    tokenized = model.routes["TOKENIZED"]
    rows = [
        {
            "Config area": "`config/routes_tradfi.yaml`",
            "Parameter(s)": "`CUSTODY_RECORDING.time`",
            "Current value": f"`{_fmt_stage_time(tradfi, 'CUSTODY_RECORDING')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Depository Trust & Clearing Corporation (2024); Committee on Payment and Settlement Systems & Technical Committee of the International Organization of Securities Commissions (2012); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Legacy post-trade reconciliation is slower than tokenized recording, but this stage intentionally excludes the settlement cycle already modeled elsewhere.",
        },
        {
            "Config area": "`config/routes_tradfi.yaml`",
            "Parameter(s)": "`SERVICING_REPORTING.time`",
            "Current value": f"`{_fmt_stage_time(tradfi, 'SERVICING_REPORTING')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Agur et al. (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Models setup/reconciliation burden rather than a full periodic reporting cycle.",
        },
        {
            "Config area": "`config/routes_tradfi.yaml`",
            "Parameter(s)": "`PRIVATE_CREDIT asset_time_adders` on custody / servicing / transfer`".rstrip("`"),
            "Current value": f"`{_fmt_num(tradfi.stages['CUSTODY_RECORDING'].asset_time_adders_hours['PRIVATE_CREDIT'])} / {_fmt_num(tradfi.stages['SERVICING_REPORTING'].asset_time_adders_hours['PRIVATE_CREDIT'])} / {_fmt_num(tradfi.stages['TRANSFERABILITY'].asset_time_adders_hours['PRIVATE_CREDIT'])} h`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Agur et al. (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Small overlays added to create route x asset interaction while preserving the main private-credit delay story in `assets.yaml`.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`ELIGIBILITY_GATE.time`",
            "Current value": f"`{_fmt_stage_time(tokenized, 'ELIGIBILITY_GATE')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Whitelist/allowlist review is mostly automated, with a tail for manual compliance review.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`ELIGIBILITY_GATE.gating.allowlist_pass_probability`",
            "Current value": f"`{_fmt_num(tokenized.stages['ELIGIBILITY_GATE'].gating.allowlist_pass_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Sources support compliance-gated access, but not an exact pass rate.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`EXECUTION.costs.explicit_fixed / implicit_fixed`",
            "Current value": f"`{_fmt_num(tokenized.stages['EXECUTION'].costs.explicit_fixed)} / {_fmt_num(tokenized.stages['EXECUTION'].costs.implicit_fixed)}`",
            "Status": "`Structural model choice`",
            "Source support": "Ondo Finance (n.d.-a); Baird et al. (2020)",
            "Notes": "Keep framed as relative cost proxies, not market fee quotes.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`CUSTODY_RECORDING.time`",
            "Current value": f"`{_fmt_stage_time(tokenized, 'CUSTODY_RECORDING')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "UK Jurisdiction Taskforce (2019); International Organization of Securities Commissions (2025); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Faster than TradFi due to tokenized ownership records, but not zero because admin/legal setup still exists.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`SERVICING_REPORTING.time`",
            "Current value": f"`{_fmt_stage_time(tokenized, 'SERVICING_REPORTING')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "UK Jurisdiction Taskforce (2019); International Organization of Securities Commissions (2025); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Real-time on-chain visibility helps, but attestation/oracle dependencies remain.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`TRANSFERABILITY.time`",
            "Current value": f"`{_fmt_stage_time(tokenized, 'TRANSFERABILITY')}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Near-instant if both wallets are already approved; longer if secondary allowlisting is needed.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`TRANSFERABILITY.restrictions.transfer_pass_probability`",
            "Current value": f"`{_fmt_num(tokenized.stages['TRANSFERABILITY'].restrictions.transfer_pass_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Literature supports whitelist restrictions, but not an exact success rate.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`PRIVATE_CREDIT asset_time_adders` on custody / servicing / transfer`".rstrip("`"),
            "Current value": f"`{_fmt_num(tokenized.stages['CUSTODY_RECORDING'].asset_time_adders_hours['PRIVATE_CREDIT'])} / {_fmt_num(tokenized.stages['SERVICING_REPORTING'].asset_time_adders_hours['PRIVATE_CREDIT'])} / {_fmt_num(tokenized.stages['TRANSFERABILITY'].asset_time_adders_hours['PRIVATE_CREDIT'])} h`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Agur et al. (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Keeps tokenized private credit slower than liquid tokenized products without undoing the tokenized route advantage.",
        },
        {
            "Config area": "`config/routes_tokenized.yaml`",
            "Parameter(s)": "`REDEMPTION_PROCESSING.redemption_hold_probability / redemption_reject_probability / hold_delay_hours / hold_delay_hours_stress`",
            "Current value": f"`{_fmt_num(tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.redemption_hold_probability)} / {_fmt_num(tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.redemption_reject_probability)} / {_fmt_num(tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.hold_delay_hours)} / {_fmt_num(tokenized.stages['REDEMPTION_PROCESSING'].redemption_rules.hold_delay_hours_stress)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Franklin Templeton Trust (2025); Ondo Finance (n.d.-d); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Sources support redemption controls and compliance checks, but not these exact exception rates.",
        },
    ]
    return pd.DataFrame(rows)


def _table_a4_risk_events(model: ModelConfig) -> pd.DataFrame:
    risk_events = {event.id: event for event in model.risk_events}
    rows = [
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`KYC_MANUAL_REVIEW.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['KYC_MANUAL_REVIEW'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Risk-based AML/CFT review supports escalation beyond straight-through processing.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`KYC_FAILURE.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['KYC_FAILURE'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Financial Action Task Force (2021)",
            "Notes": "Rare but plausible terminal compliance failure.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`REDEMPTION_HOLD.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['REDEMPTION_HOLD'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Franklin Templeton Trust (2025); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Separate from ordinary redemption timing; represents exceptional review.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`REDEMPTION_REJECTED.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['REDEMPTION_REJECTED'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Franklin Templeton Trust (2025); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Rare terminal redemption denial.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`SETTLEMENT_FAIL.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['SETTLEMENT_FAIL'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Depository Trust & Clearing Corporation (2024); U.S. Securities and Exchange Commission (2022)",
            "Notes": "DTCC and SEC sources support the existence of settlement fails and Rule 204 close-out requirements, but the 3% value is retained as a calibrated proxy rather than as a directly observed thesis-level incident statistic.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`ACATS_COMPLICATION.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['ACATS_COMPLICATION'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Financial Industry Regulatory Authority (2006)",
            "Notes": "FINRA documentation supports the existence of account-transfer delays and complications; 5% is retained as a conservative calibration rather than a published incident rate.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`CUSTODY_RECONCILIATION_ERROR.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['CUSTODY_RECONCILIATION_ERROR'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Agur et al. (2025); Committee on Payment and Settlement Systems & Technical Committee of the International Organization of Securities Commissions (2012); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Captures low but non-zero legacy reconciliation mismatch risk.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`ATTESTATION_DELAY.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['ATTESTATION_DELAY'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Tokenized products still rely on off-chain reporting and governance dependencies.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`TRANSFER_BLOCKED.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['TRANSFER_BLOCKED'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "Ondo Finance (n.d.-b); International Organization of Securities Commissions (2025); Financial Action Task Force (2021)",
            "Notes": "Models exceptional transfer denial beyond the structural transfer gate.",
        },
        {
            "Config area": "`config/risk_events.yaml`",
            "Parameter(s)": "`GOVERNANCE_PAUSE.base_probability`",
            "Current value": f"`{_fmt_num(risk_events['GOVERNANCE_PAUSE'].base_probability)}`",
            "Status": "`Directionally supported calibration`",
            "Source support": "International Organization of Securities Commissions (2025); Financial Stability Board (2024); Bank for International Settlements & Committee on Payments and Market Infrastructures (2024)",
            "Notes": "Rare smart-contract or platform intervention assumption.",
        },
    ]
    return pd.DataFrame(rows)


def _fmt_stage_time(route: RouteConfig, stage_id: str) -> str:
    spec = route.stages[stage_id].time
    if spec.dist == "triangular":
        return _fmt_dist_hours(spec.params["low"], spec.params["mode"], spec.params["high"])
    if spec.dist == "fixed":
        return f"{_fmt_num(spec.params['value'])} h"
    return str(spec.params)


def _fmt_dist_hours(low: float, mode: float, high: float) -> str:
    return f"({_fmt_num(low)}, {_fmt_num(mode)}, {_fmt_num(high)}) h"


def _fmt_num(value: float | int) -> str:
    return f"{float(value):g}" if isinstance(value, float) else str(value)
