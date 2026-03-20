from __future__ import annotations

from typing import Optional

from .gates import (
    GateResult,
    InvestorProfile,
    apply_stage_gates,
    redemption_notice_delay_hours,
    redemption_window_delay_hours,
)
from .randomness import RNG, sample_dist
from .risk import apply_risk_events_for_stage
from .types import DistSpec, ModelConfig, RunResult, StageResult


def run_single_lifecycle(
    *,
    model: ModelConfig,
    run_id: int,
    asset_id: str,
    route_id: str,
    scenario_id: str,
    investor: Optional[InvestorProfile] = None,
) -> RunResult:
    """Run one investor lifecycle for a given asset/route/scenario.

    Queue delays are not included here; they are injected by the hybrid runner.
    """
    if investor is None:
        investor = InvestorProfile(qualified_investor=False)

    if asset_id not in model.assets:
        raise KeyError(f"Unknown asset_id: {asset_id}")
    if route_id not in model.routes:
        raise KeyError(f"Unknown route_id: {route_id}")
    if scenario_id not in model.scenarios:
        raise KeyError(f"Unknown scenario_id: {scenario_id}")

    asset = model.assets[asset_id]
    route = model.routes[route_id]
    scenario = model.scenarios[scenario_id]

    rng = RNG.from_seed(scenario.seed + run_id)

    time_mult = float(scenario.time_multipliers.get(route_id, scenario.time_multipliers.get("default", 1.0)))
    cost_mult = float(scenario.cost_multipliers.get(route_id, scenario.cost_multipliers.get("default", 1.0)))

    result = RunResult(
        run_id=run_id,
        asset_id=asset_id,
        route_id=route_id,
        scenario_id=scenario_id,
    )

    for stage_id, stage_def in model.stages.items():
        if stage_id not in route.stages:
            raise ValueError(
                f"Route '{route.id}' missing stage '{stage_id}'. "
                "Every route must define every canonical stage."
            )

        stage_spec = route.stages[stage_id]

        if not stage_spec.enabled:
            continue

        stage_res = StageResult(stage_id=stage_id, stage_label=stage_def.label)

        gate: GateResult = apply_stage_gates(
            stage_id=stage_id,
            stage_spec=stage_spec,
            asset=asset,
            scenario=scenario,
            investor=investor,
            rng=rng,
        )

        if not gate.allowed:
            stage_res.gate_events.append(f"GATE_DENIED:{gate.reason}")
            result.stages.append(stage_res)

            result.completed = False
            result.failed_stage_id = stage_id
            _finalize_totals(result)
            return result

        if stage_id == "TRANSFERABILITY":
            stage_res.transfer_attempted = True
            stage_res.transfer_success = gate.transfer_success
            stage_res.gate_events.append(f"GATE:{gate.reason}")

        gate_delay = float(gate.add_delay_hours)

        if stage_id == "EXIT_INITIATION":
            gate_delay += redemption_notice_delay_hours(asset)
            gate_delay += redemption_window_delay_hours(asset)

        if stage_id == "REDEMPTION_PROCESSING":
            stage_res.redemption_attempted = True
            redemption_allowed = True if gate.redemption_allowed is None else bool(gate.redemption_allowed)
            stage_res.redemption_success = redemption_allowed
            stage_res.gate_events.append(f"GATE:{gate.reason}")
            if not redemption_allowed:
                result.exit_frozen = True

        asset_time_add = float(stage_spec.asset_time_adders_hours.get(asset_id, 0.0))
        base_time = (sample_dist(stage_spec.time, rng) + asset_time_add) * time_mult
        stage_res.base_time_hours = float(base_time)
        stage_res.gate_delay_hours = float(gate_delay)
        stage_time = base_time + gate_delay

        stage_res.explicit_cost += float(stage_spec.costs.explicit_fixed) * cost_mult
        stage_res.implicit_cost += float(stage_spec.costs.implicit_fixed) * cost_mult

        stage_res.approvals += int(stage_spec.friction.approvals)
        stage_res.handoffs += int(stage_spec.friction.handoffs)
        stage_res.intermediaries.update(set(stage_spec.friction.intermediaries))

        risk_apply = apply_risk_events_for_stage(
            stage_id=stage_id,
            route_id=route_id,
            risk_events=model.risk_events,
            scenario=scenario,
            rng=rng,
        )

        exception_time_hours = 0.0
        if risk_apply.triggered_event_ids:
            stage_res.risk_events.extend(list(risk_apply.triggered_event_ids))

            exc_spec = route.stages.get("EXCEPTION_HANDLING")
            if exc_spec is not None:
                exception_time_hours = sample_dist(exc_spec.time, rng)
                stage_res.explicit_cost += float(exc_spec.costs.explicit_fixed) * cost_mult
                stage_res.implicit_cost += float(exc_spec.costs.implicit_fixed) * cost_mult
            else:
                exception_time_hours = sample_dist(
                    DistSpec(dist="triangular", params={"low": 0.5, "mode": 4.0, "high": 24.0}),
                    rng,
                )
                stage_res.explicit_cost += 0.3 * cost_mult
                stage_res.implicit_cost += 0.1 * cost_mult
            stage_time += exception_time_hours

        stage_res.exception_delay_hours = float(exception_time_hours)
        stage_res.risk_delay_hours = float(risk_apply.add_time_hours)
        stage_time += stage_res.risk_delay_hours
        stage_res.explicit_cost += float(risk_apply.add_explicit_cost) * cost_mult
        stage_res.implicit_cost += float(risk_apply.add_implicit_cost) * cost_mult

        if stage_id == "TRANSFERABILITY" and risk_apply.transfer_success_override is not None:
            stage_res.transfer_attempted = True
            stage_res.transfer_success = bool(risk_apply.transfer_success_override)

        if risk_apply.blocks_progress:
            stage_res.time_hours = stage_time
            result.stages.append(stage_res)

            result.completed = False
            result.failed_stage_id = stage_id
            _finalize_totals(result)
            return result

        if risk_apply.freezes_exit:
            result.exit_frozen = True

        stage_res.time_hours = stage_time
        result.stages.append(stage_res)

        if stage_id == "CUSTODY_RECORDING" and result.time_to_position_hours is None:
            result.time_to_position_hours = _sum_time_hours(result)

        if stage_id == "REDEMPTION_PROCESSING":
            cash_lag_hours = float(asset.redemption.settlement_days_to_cash) * 24.0
            if not result.exit_frozen:
                result.time_to_cash_hours = _sum_time_hours(result) + cash_lag_hours

    _finalize_totals(result)
    return result


def _sum_time_hours(res: RunResult) -> float:
    return float(sum(s.time_hours for s in res.stages))


def _finalize_totals(res: RunResult) -> None:
    res.total_time_hours = _sum_time_hours(res)
    res.total_explicit_cost = float(sum(s.explicit_cost for s in res.stages))
    res.total_implicit_cost = float(sum(s.implicit_cost for s in res.stages))
    res.total_approvals = int(sum(s.approvals for s in res.stages))
    res.total_handoffs = int(sum(s.handoffs for s in res.stages))

    inter = set()
    for s in res.stages:
        inter.update(s.intermediaries)
    res.intermediaries = inter
