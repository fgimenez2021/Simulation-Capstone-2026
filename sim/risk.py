from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .randomness import RNG, bernoulli, sample_dist
from .types import RiskEvent, ScenarioConfig


@dataclass(frozen=True)


class RiskApplyResult:
    """
    Result of applying risk events at a given stage.
    """
    triggered_event_ids: Tuple[str, ...] = tuple()

    add_time_hours: float = 0.0
    add_explicit_cost: float = 0.0
    add_implicit_cost: float = 0.0

    blocks_progress: bool = False
    freezes_exit: bool = False

    transfer_success_override: Optional[bool] = None


def apply_risk_events_for_stage(
    *,
    stage_id: str,
    route_id: str,
    risk_events: Tuple[RiskEvent, ...],
    scenario: ScenarioConfig,
    rng: RNG,
) -> RiskApplyResult:
    """
    Evaluate all risk events that can trigger at this stage and route.

    - Events with applicable_routes are skipped when route_id is not listed.
    - Probabilities are base_probability * scenario risk multiplier.
    - Multiple events can trigger at the same stage (rare but allowed).

    Returns aggregated impacts and flags.
    """
    risk_scale = float(scenario.risk_multipliers.get(route_id, scenario.risk_multipliers.get("default", 1.0)))

    triggered: List[str] = []
    total_add_time = 0.0
    total_add_exp_cost = 0.0
    total_add_imp_cost = 0.0
    blocks_progress = False
    freezes_exit = False
    transfer_override: Optional[bool] = None

    for ev in risk_events:
        if stage_id not in ev.trigger_stages:
            continue
        if ev.applicable_routes and route_id not in ev.applicable_routes:
            continue

        p = float(ev.base_probability) * risk_scale
        p = max(0.0, min(1.0, p))

        if bernoulli(p, rng):
            triggered.append(ev.id)
            total_add_time += sample_dist(ev.impacts.add_time_hours, rng)
            total_add_exp_cost += float(ev.impacts.add_explicit_cost)
            total_add_imp_cost += float(ev.impacts.add_implicit_cost)
            if ev.flags.blocks_progress:
                blocks_progress = True
            if ev.flags.freezes_exit:
                freezes_exit = True
            if ev.outcomes and ev.outcomes.transfer_success is not None:
                transfer_override = bool(ev.outcomes.transfer_success)

    return RiskApplyResult(
        triggered_event_ids=tuple(triggered),
        add_time_hours=total_add_time,
        add_explicit_cost=total_add_exp_cost,
        add_implicit_cost=total_add_imp_cost,
        blocks_progress=blocks_progress,
        freezes_exit=freezes_exit,
        transfer_success_override=transfer_override,
    )
