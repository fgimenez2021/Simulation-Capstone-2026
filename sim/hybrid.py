from __future__ import annotations

from typing import Optional

from .engine import run_single_lifecycle
from .gates import InvestorProfile
from .queues import QueueWaitSamplers, build_queue_wait_samplers
from .randomness import RNG
from .types import ModelConfig, RunResult


def run_single_lifecycle_hybrid(
    *,
    model: ModelConfig,
    run_id: int,
    asset_id: str,
    route_id: str,
    scenario_id: str,
    investor: Optional[InvestorProfile] = None,
    queue_samplers: Optional[QueueWaitSamplers] = None,
) -> RunResult:
    """Hybrid runner: injects queue delays into KYC and redemption stages under stress."""
    scenario = model.scenarios[scenario_id]

    if not scenario.queues.enabled:
        return run_single_lifecycle(
            model=model,
            run_id=run_id,
            asset_id=asset_id,
            route_id=route_id,
            scenario_id=scenario_id,
            investor=investor,
        )

    samplers = queue_samplers or build_queue_wait_samplers(
        model=model,
        scenario=scenario,
        route_id=route_id,
    )

    res = run_single_lifecycle(
        model=model,
        run_id=run_id,
        asset_id=asset_id,
        route_id=route_id,
        scenario_id=scenario_id,
        investor=investor,
    )

    rng = RNG.from_seed(scenario.seed + run_id + 50_000)

    for s in res.stages:
        if s.stage_id == "KYC_REVIEW":
            q_wait = float(samplers.kyc_wait_hours(rng))
            s.time_hours += q_wait
            s.queue_delay_hours += q_wait
        elif s.stage_id == "REDEMPTION_PROCESSING":
            q_wait = float(samplers.redemption_wait_hours(rng))
            s.time_hours += q_wait
            s.queue_delay_hours += q_wait

    _recompute_totals_and_markers(model=model, res=res)
    return res


def _recompute_totals_and_markers(*, model: ModelConfig, res: RunResult) -> None:
    """Recompute run totals after queue delay injection."""
    res.total_time_hours = float(sum(s.time_hours for s in res.stages))
    res.total_explicit_cost = float(sum(s.explicit_cost for s in res.stages))
    res.total_implicit_cost = float(sum(s.implicit_cost for s in res.stages))
    res.total_approvals = int(sum(s.approvals for s in res.stages))
    res.total_handoffs = int(sum(s.handoffs for s in res.stages))

    inter = set()
    for s in res.stages:
        inter.update(s.intermediaries)
    res.intermediaries = inter

    res.time_to_position_hours = None
    running = 0.0
    for s in res.stages:
        running += float(s.time_hours)
        if s.stage_id == "CUSTODY_RECORDING" and res.time_to_position_hours is None:
            res.time_to_position_hours = running

    res.time_to_cash_hours = None
    if not res.exit_frozen:
        running = 0.0
        for s in res.stages:
            running += float(s.time_hours)
            if s.stage_id == "REDEMPTION_PROCESSING":
                asset = model.assets[res.asset_id]
                cash_lag_hours = float(asset.redemption.settlement_days_to_cash) * 24.0
                res.time_to_cash_hours = running + cash_lag_hours
                break
