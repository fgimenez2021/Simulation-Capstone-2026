from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from .types import (
    ArrivalSpec,
    AssetConfig,
    CostSpec,
    DistSpec,
    EligibilityAssetSpec,
    FrictionSpec,
    GatingSpec,
    ModelConfig,
    QueuesConfig,
    QueueArrivalConfig,
    QueueConfig,
    QueueServersConfig,
    QueueServiceConfig,
    RedemptionAssetSpec,
    RedemptionRuleSpec,
    RiskEvent,
    RiskFlagSpec,
    RiskImpactSpec,
    RiskOutcomeSpec,
    RouteConfig,
    ScenarioConfig,
    ScenarioQueuesSpec,
    StageDef,
    StageRouteSpec,
    TransferRestrictionSpec,
)


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_model_config(config_dir: str | Path = "config") -> ModelConfig:
    """
    Load all YAML config files into strongly-typed Python models.
    Expects the following files:
      - stages.yaml
      - assets.yaml
      - scenarios.yaml
      - routes_tradfi.yaml
      - routes_tokenized.yaml
      - risk_events.yaml
      - queues.yaml
    """
    config_dir = Path(config_dir)

    stages_raw = _read_yaml(config_dir / "stages.yaml")
    assets_raw = _read_yaml(config_dir / "assets.yaml")
    scenarios_raw = _read_yaml(config_dir / "scenarios.yaml")
    tradfi_raw = _read_yaml(config_dir / "routes_tradfi.yaml")
    tokenized_raw = _read_yaml(config_dir / "routes_tokenized.yaml")
    risk_raw = _read_yaml(config_dir / "risk_events.yaml")
    queues_raw = _read_yaml(config_dir / "queues.yaml")

    stages = _parse_stages(stages_raw)
    assets = _parse_assets(assets_raw)
    scenarios = _parse_scenarios(scenarios_raw)
    routes = {
        "TRADFI": _parse_route(tradfi_raw),
        "TOKENIZED": _parse_route(tokenized_raw),
    }
    risk_events = _parse_risk_events(risk_raw)
    queues = _parse_queues(queues_raw)

    _validate_stage_ids_consistent(stages=stages, routes=routes, risk_events=risk_events)

    return ModelConfig(
        stages=stages,
        assets=assets,
        routes=routes,
        scenarios=scenarios,
        risk_events=risk_events,
        queues=queues,
    )


def _parse_stages(raw: dict) -> Dict[str, StageDef]:
    items = raw.get("stages", [])
    if not isinstance(items, list) or not items:
        raise ValueError("config/stages.yaml must contain a non-empty 'stages' list.")

    out: Dict[str, StageDef] = {}
    for s in items:
        sid = str(s["id"]).strip()
        if sid in out:
            raise ValueError(f"Duplicate stage id in stages.yaml: {sid}")
        out[sid] = StageDef(
            id=sid,
            label=str(s.get("label", sid)),
            category=str(s.get("category", "unknown")),
        )
    return out


def _parse_assets(raw: dict) -> Dict[str, AssetConfig]:
    items = raw.get("assets", [])
    if not isinstance(items, list) or not items:
        raise ValueError("config/assets.yaml must contain a non-empty 'assets' list.")

    out: Dict[str, AssetConfig] = {}
    for a in items:
        aid = str(a["id"]).strip()
        redemption = a.get("redemption", {})
        eligibility = a.get("eligibility", {})

        out[aid] = AssetConfig(
            id=aid,
            label=str(a.get("label", aid)),
            liquidity_class=str(a.get("liquidity_class", "liquid")),
            redemption=RedemptionAssetSpec(
                window_type=str(redemption.get("window_type", "daily")),
                notice_days=int(redemption.get("notice_days", 0)),
                settlement_days_to_cash=int(redemption.get("settlement_days_to_cash", 1)),
            ),
            eligibility=EligibilityAssetSpec(
                requires_qualified_investor=bool(eligibility.get("requires_qualified_investor", False))
            ),
        )
        _validate_asset(out[aid], aid)
    return out


def _parse_scenarios(raw: dict) -> Dict[str, ScenarioConfig]:
    items = raw.get("scenarios", [])
    if not isinstance(items, list) or not items:
        raise ValueError("config/scenarios.yaml must contain a non-empty 'scenarios' list.")

    out: Dict[str, ScenarioConfig] = {}
    for s in items:
        sid = str(s["id"]).strip()
        queues = s.get("queues", {})
        arrivals = s.get("arrivals", {})

        out[sid] = ScenarioConfig(
            id=sid,
            label=str(s.get("label", sid)),
            mode=str(s.get("mode", "baseline")),
            seed=int(s.get("seed", 42)),
            time_multipliers=dict(s.get("time_multipliers", {"default": 1.0})),
            cost_multipliers=dict(s.get("cost_multipliers", {"default": 1.0})),
            risk_multipliers=dict(s.get("risk_multipliers", {"default": 1.0})),
            queues=ScenarioQueuesSpec(enabled=bool(queues.get("enabled", False))),
            arrivals=ArrivalSpec(
                onboarding_requests_per_day=int(arrivals.get("onboarding_requests_per_day", 50)),
                redemption_requests_per_day=int(arrivals.get("redemption_requests_per_day", 30)),
            ),
        )
        _validate_scenario(out[sid], sid)
    return out


def _parse_route(raw: dict) -> RouteConfig:
    route = raw.get("route", {})
    rid = str(route.get("id", "")).strip()
    label = str(route.get("label", rid))

    stages_raw = route.get("stages", {})
    if not isinstance(stages_raw, dict) or not stages_raw:
        raise ValueError(f"Route config for {rid} must contain a non-empty route.stages mapping.")

    stage_specs: Dict[str, StageRouteSpec] = {}
    for stage_id, spec in stages_raw.items():
        enabled = bool(spec.get("enabled", True))
        time = spec.get("time", {})
        costs = spec.get("costs", {})
        friction = spec.get("friction", {})
        asset_time_adders = spec.get("asset_time_adders_hours", {})

        gating = spec.get("gating")
        restrictions = spec.get("restrictions")
        redemption_rules = spec.get("redemption_rules")

        stage_specs[str(stage_id)] = StageRouteSpec(
            enabled=enabled,
            time=DistSpec(dist=str(time.get("dist", "fixed")), params=dict(time.get("params", {"value": 0.0}))),
            costs=CostSpec(
                explicit_fixed=float(costs.get("explicit_fixed", 0.0)),
                implicit_fixed=float(costs.get("implicit_fixed", 0.0)),
            ),
            friction=FrictionSpec(
                approvals=int(friction.get("approvals", 0)),
                handoffs=int(friction.get("handoffs", 0)),
                intermediaries=tuple(friction.get("intermediaries", [])),
            ),
            asset_time_adders_hours=(
                {str(k): float(v) for k, v in asset_time_adders.items()}
                if isinstance(asset_time_adders, dict)
                else {}
            ),
            gating=(
                GatingSpec(
                    requires_allowlist=bool(gating.get("requires_allowlist", False)),
                    allowlist_pass_probability=float(gating.get("allowlist_pass_probability", 1.0)),
                )
                if isinstance(gating, dict)
                else None
            ),
            restrictions=(
                TransferRestrictionSpec(
                    transfers_restricted=bool(restrictions.get("transfers_restricted", False)),
                    transfer_pass_probability=float(restrictions.get("transfer_pass_probability", 1.0)),
                )
                if isinstance(restrictions, dict)
                else None
            ),
            redemption_rules=(
                RedemptionRuleSpec(
                    redemption_hold_probability=float(redemption_rules.get("redemption_hold_probability", 0.0)),
                    redemption_reject_probability=float(redemption_rules.get("redemption_reject_probability", 0.0)),
                    hold_delay_hours=float(redemption_rules.get("hold_delay_hours", 24.0)),
                    hold_delay_hours_stress=float(redemption_rules.get("hold_delay_hours_stress", 72.0)),
                )
                if isinstance(redemption_rules, dict)
                else None
            ),
        )
        _validate_stage_route_spec(stage_specs[str(stage_id)], str(stage_id), rid)

    if not rid:
        raise ValueError("Route config missing route.id")

    return RouteConfig(id=rid, label=label, stages=stage_specs)


def _parse_risk_events(raw: dict) -> Tuple[RiskEvent, ...]:
    items = raw.get("risk_events", [])
    if not isinstance(items, list):
        raise ValueError("config/risk_events.yaml must contain a 'risk_events' list.")

    out: List[RiskEvent] = []
    for e in items:
        impacts = e.get("impacts", {})
        add_time = impacts.get("add_time_hours", {"dist": "fixed", "params": {"value": 0.0}})
        flags = e.get("flags", {})
        outcomes = e.get("outcomes")

        raw_routes = e.get("applicable_routes", [])
        applicable_routes = tuple(str(r).strip() for r in raw_routes) if raw_routes else ()

        out.append(
            RiskEvent(
                id=str(e["id"]).strip(),
                label=str(e.get("label", e["id"])),
                trigger_stages=tuple(e.get("trigger_stages", [])),
                base_probability=float(e.get("base_probability", 0.0)),
                impacts=RiskImpactSpec(
                    add_time_hours=DistSpec(dist=str(add_time.get("dist", "fixed")), params=dict(add_time.get("params", {"value": 0.0}))),
                    add_explicit_cost=float(impacts.get("add_explicit_cost", 0.0)),
                    add_implicit_cost=float(impacts.get("add_implicit_cost", 0.0)),
                ),
                flags=RiskFlagSpec(
                    blocks_progress=bool(flags.get("blocks_progress", False)),
                    freezes_exit=bool(flags.get("freezes_exit", False)),
                ),
                outcomes=(
                    RiskOutcomeSpec(transfer_success=outcomes.get("transfer_success"))
                    if isinstance(outcomes, dict)
                    else None
                ),
                applicable_routes=applicable_routes,
            )
        )
        _validate_risk_event(out[-1])
    return tuple(out)


def _parse_queues(raw: dict) -> QueuesConfig:
    queues = raw.get("queues", {})
    horizon = raw.get("queue_simulation_horizon_days", {"baseline": 5, "stress": 10})

    def parse_one(q: dict) -> QueueConfig:
        return QueueConfig(
            label=str(q.get("label", "")),
            servers=QueueServersConfig(
                baseline=int(q.get("servers", {}).get("baseline", 1)),
                stress=int(q.get("servers", {}).get("stress", 1)),
            ),
            service_time=QueueServiceConfig(
                dist=str(q.get("service_time", {}).get("dist", "fixed")),
                params=dict(q.get("service_time", {}).get("params", {"value": 1.0})),
            ),
            arrivals=QueueArrivalConfig(
                model=str(q.get("arrivals", {}).get("model", "fixed_per_day")),
                baseline_rate_per_day=int(q.get("arrivals", {}).get("baseline_rate_per_day", 10)),
                stress_rate_per_day=int(q.get("arrivals", {}).get("stress_rate_per_day", 50)),
            ),
            service_time_multipliers=(
                {str(k): float(v) for k, v in q.get("service_time_multipliers", {"default": 1.0}).items()}
                if isinstance(q.get("service_time_multipliers", {"default": 1.0}), dict)
                else {"default": 1.0}
            ),
        )

    kyc = queues.get("kyc_queue", {})
    red = queues.get("redemption_queue", {})

    parsed = QueuesConfig(
        kyc_queue=parse_one(kyc),
        redemption_queue=parse_one(red),
        queue_simulation_horizon_days={
            "baseline": int(horizon.get("baseline", 5)),
            "stress": int(horizon.get("stress", 10)),
        },
    )
    _validate_queues(parsed)
    return parsed


def _validate_stage_ids_consistent(
    stages: Dict[str, StageDef],
    routes: Dict[str, RouteConfig],
    risk_events: Tuple[RiskEvent, ...],
) -> None:
    stage_ids = set(stages.keys())

    for rkey, route in routes.items():
        missing_stage_ids = [sid for sid in stage_ids if sid not in route.stages]
        if missing_stage_ids:
            raise ValueError(
                f"Route '{route.id}' is missing canonical stages: {sorted(missing_stage_ids)}. "
                "Every canonical stage must be configured in each route."
            )
        for sid in route.stages.keys():
            if sid not in stage_ids:
                raise ValueError(
                    f"Route '{route.id}' references unknown stage id '{sid}'. "
                    f"Add it to config/stages.yaml or fix the route config."
                )

    for ev in risk_events:
        for sid in ev.trigger_stages:
            if sid not in stage_ids:
                raise ValueError(
                    f"Risk event '{ev.id}' references unknown trigger stage '{sid}'. "
                    f"Add it to config/stages.yaml or fix risk_events.yaml."
                )


def _validate_probability(value: float, context: str) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{context} must be in [0,1]. Got {value}.")


def _validate_multiplier(value: float, context: str) -> None:
    if value <= 0.0:
        raise ValueError(f"{context} must be > 0. Got {value}.")


def _validate_dist_spec(spec: DistSpec, context: str) -> None:
    if spec.dist not in {"fixed", "triangular", "lognormal"}:
        raise ValueError(f"{context}: unsupported distribution '{spec.dist}'.")

    p = spec.params
    if spec.dist == "fixed":
        value = float(p.get("value", 0.0))
        if value < 0.0:
            raise ValueError(f"{context}: fixed.value must be >= 0. Got {value}.")
        return

    if spec.dist == "triangular":
        low = float(p["low"])
        mode = float(p["mode"])
        high = float(p["high"])
        if low < 0.0:
            raise ValueError(f"{context}: triangular.low must be >= 0. Got {low}.")
        if not (low <= mode <= high):
            raise ValueError(
                f"{context}: triangular params must satisfy low <= mode <= high. "
                f"Got low={low}, mode={mode}, high={high}."
            )
        return

    mean = float(p["mean"])
    sigma = float(p["sigma"])
    if sigma < 0.0:
        raise ValueError(f"{context}: lognormal.sigma must be >= 0. Got {sigma}.")


def _validate_stage_route_spec(spec: StageRouteSpec, stage_id: str, route_id: str) -> None:
    ctx = f"route={route_id} stage={stage_id}"
    _validate_dist_spec(spec.time, f"{ctx}.time")

    if spec.costs.explicit_fixed < 0.0:
        raise ValueError(f"{ctx}.costs.explicit_fixed must be >= 0.")
    if spec.costs.implicit_fixed < 0.0:
        raise ValueError(f"{ctx}.costs.implicit_fixed must be >= 0.")
    if spec.friction.approvals < 0:
        raise ValueError(f"{ctx}.friction.approvals must be >= 0.")
    if spec.friction.handoffs < 0:
        raise ValueError(f"{ctx}.friction.handoffs must be >= 0.")
    for asset_id, add_hours in spec.asset_time_adders_hours.items():
        if float(add_hours) < 0.0:
            raise ValueError(f"{ctx}.asset_time_adders_hours.{asset_id} must be >= 0.")

    if spec.gating is not None:
        _validate_probability(spec.gating.allowlist_pass_probability, f"{ctx}.gating.allowlist_pass_probability")

    if spec.restrictions is not None:
        _validate_probability(spec.restrictions.transfer_pass_probability, f"{ctx}.restrictions.transfer_pass_probability")

    if spec.redemption_rules is not None:
        _validate_probability(spec.redemption_rules.redemption_hold_probability, f"{ctx}.redemption_rules.redemption_hold_probability")
        _validate_probability(spec.redemption_rules.redemption_reject_probability, f"{ctx}.redemption_rules.redemption_reject_probability")
        total = (
            spec.redemption_rules.redemption_hold_probability
            + spec.redemption_rules.redemption_reject_probability
        )
        if total > 1.0:
            raise ValueError(f"{ctx}.redemption_rules hold+reject probabilities cannot exceed 1. Got {total}.")
        if spec.redemption_rules.hold_delay_hours < 0.0:
            raise ValueError(f"{ctx}.redemption_rules.hold_delay_hours must be >= 0.")
        if spec.redemption_rules.hold_delay_hours_stress < 0.0:
            raise ValueError(f"{ctx}.redemption_rules.hold_delay_hours_stress must be >= 0.")


def _validate_scenario(s: ScenarioConfig, scenario_id: str) -> None:
    for k, v in s.time_multipliers.items():
        _validate_multiplier(float(v), f"scenario={scenario_id}.time_multipliers.{k}")
    for k, v in s.cost_multipliers.items():
        _validate_multiplier(float(v), f"scenario={scenario_id}.cost_multipliers.{k}")
    for k, v in s.risk_multipliers.items():
        _validate_multiplier(float(v), f"scenario={scenario_id}.risk_multipliers.{k}")

    if s.arrivals.onboarding_requests_per_day < 0:
        raise ValueError(f"scenario={scenario_id}.arrivals.onboarding_requests_per_day must be >= 0.")
    if s.arrivals.redemption_requests_per_day < 0:
        raise ValueError(f"scenario={scenario_id}.arrivals.redemption_requests_per_day must be >= 0.")


def _validate_risk_event(ev: RiskEvent) -> None:
    _validate_probability(ev.base_probability, f"risk_event={ev.id}.base_probability")
    _validate_dist_spec(ev.impacts.add_time_hours, f"risk_event={ev.id}.impacts.add_time_hours")

    if ev.impacts.add_explicit_cost < 0.0:
        raise ValueError(f"risk_event={ev.id}.impacts.add_explicit_cost must be >= 0.")
    if ev.impacts.add_implicit_cost < 0.0:
        raise ValueError(f"risk_event={ev.id}.impacts.add_implicit_cost must be >= 0.")


def _validate_queues(q: QueuesConfig) -> None:
    for name, queue in (("kyc_queue", q.kyc_queue), ("redemption_queue", q.redemption_queue)):
        if queue.servers.baseline < 1 or queue.servers.stress < 1:
            raise ValueError(f"{name}.servers baseline/stress must both be >= 1.")
        if queue.arrivals.baseline_rate_per_day < 0 or queue.arrivals.stress_rate_per_day < 0:
            raise ValueError(f"{name}.arrivals baseline/stress rates must be >= 0.")
        for route_key, multiplier in queue.service_time_multipliers.items():
            _validate_multiplier(float(multiplier), f"{name}.service_time_multipliers.{route_key}")
        _validate_dist_spec(
            DistSpec(dist=queue.service_time.dist, params=queue.service_time.params),
            f"{name}.service_time",
        )

    for mode in ("baseline", "stress"):
        if int(q.queue_simulation_horizon_days.get(mode, 0)) <= 0:
            raise ValueError(f"queue_simulation_horizon_days.{mode} must be > 0.")


def _validate_asset(asset: AssetConfig, asset_id: str) -> None:
    if asset.liquidity_class not in {"liquid", "illiquid"}:
        raise ValueError(f"asset={asset_id}.liquidity_class must be 'liquid' or 'illiquid'.")

    if asset.redemption.window_type not in {"daily", "weekly", "monthly", "quarterly"}:
        raise ValueError(
            f"asset={asset_id}.redemption.window_type must be one of "
            f"daily/weekly/monthly/quarterly. Got {asset.redemption.window_type}."
        )

    if asset.redemption.notice_days < 0:
        raise ValueError(f"asset={asset_id}.redemption.notice_days must be >= 0.")
    if asset.redemption.settlement_days_to_cash < 0:
        raise ValueError(f"asset={asset_id}.redemption.settlement_days_to_cash must be >= 0.")
