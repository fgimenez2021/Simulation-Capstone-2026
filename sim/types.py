from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Set, Tuple

DistName = Literal["fixed", "triangular", "lognormal"]


@dataclass(frozen=True)


class DistSpec:
    """
    Generic distribution specification used throughout the configs.

    Supported:
      - fixed:      params: {value: float}
      - triangular: params: {low: float, mode: float, high: float}
      - lognormal:  params: {mean: float, sigma: float}  (in natural log space if you prefer)
    """
    dist: DistName
    params: Dict[str, float]


@dataclass(frozen=True)


class StageDef:
    """Canonical stage definition from config/stages.yaml"""
    id: str
    label: str
    category: str


@dataclass(frozen=True)


class FrictionSpec:
    approvals: int = 0
    handoffs: int = 0
    intermediaries: Tuple[str, ...] = tuple()


@dataclass(frozen=True)


class CostSpec:
    explicit_fixed: float = 0.0
    implicit_fixed: float = 0.0


@dataclass(frozen=True)


class GatingSpec:
    """
    Optional gating rules used mainly in tokenized stages (eligibility/allowlist).
    """
    requires_allowlist: bool = False
    allowlist_pass_probability: float = 1.0


@dataclass(frozen=True)


class TransferRestrictionSpec:
    """
    Optional transfer restrictions used mainly in tokenized TRANSFERABILITY stage.
    """
    transfers_restricted: bool = False
    transfer_pass_probability: float = 1.0


@dataclass(frozen=True)


class RedemptionRuleSpec:
    """
    Optional redemption rules (holds/rejections) used mainly in tokenized REDEMPTION_PROCESSING stage.
    """
    redemption_hold_probability: float = 0.0
    redemption_reject_probability: float = 0.0
    hold_delay_hours: float = 24.0
    hold_delay_hours_stress: float = 72.0


@dataclass(frozen=True)


class StageRouteSpec:
    """
    Per-route configuration for a single stage.
    """
    enabled: bool
    time: DistSpec
    costs: CostSpec
    friction: FrictionSpec

    asset_time_adders_hours: Dict[str, float] = field(default_factory=dict)

    gating: Optional[GatingSpec] = None
    restrictions: Optional[TransferRestrictionSpec] = None
    redemption_rules: Optional[RedemptionRuleSpec] = None


@dataclass(frozen=True)


class RouteConfig:
    id: str
    label: str
    stages: Dict[str, StageRouteSpec]


@dataclass(frozen=True)


class RedemptionAssetSpec:
    window_type: Literal["daily", "weekly", "monthly", "quarterly"]
    notice_days: int
    settlement_days_to_cash: int


@dataclass(frozen=True)


class EligibilityAssetSpec:
    requires_qualified_investor: bool = False


@dataclass(frozen=True)


class AssetConfig:
    id: str
    label: str
    liquidity_class: Literal["liquid", "illiquid"]
    redemption: RedemptionAssetSpec
    eligibility: EligibilityAssetSpec


@dataclass(frozen=True)


class ArrivalSpec:
    onboarding_requests_per_day: int
    redemption_requests_per_day: int


@dataclass(frozen=True)


class ScenarioQueuesSpec:
    enabled: bool


@dataclass(frozen=True)


class ScenarioConfig:
    id: str
    label: str
    mode: Literal["baseline", "stress"]
    seed: int

    time_multipliers: Dict[str, float]
    cost_multipliers: Dict[str, float]
    risk_multipliers: Dict[str, float]

    queues: ScenarioQueuesSpec
    arrivals: ArrivalSpec


@dataclass(frozen=True)


class RiskImpactSpec:
    add_time_hours: DistSpec
    add_explicit_cost: float = 0.0
    add_implicit_cost: float = 0.0


@dataclass(frozen=True)


class RiskFlagSpec:
    blocks_progress: bool = False
    freezes_exit: bool = False


@dataclass(frozen=True)


class RiskOutcomeSpec:
    transfer_success: Optional[bool] = None


@dataclass(frozen=True)


class RiskEvent:
    id: str
    label: str
    trigger_stages: Tuple[str, ...]
    base_probability: float
    impacts: RiskImpactSpec
    flags: RiskFlagSpec
    outcomes: Optional[RiskOutcomeSpec] = None
    applicable_routes: Tuple[str, ...] = ()

QueueArrivalModel = Literal["fixed_per_day", "poisson_per_day"]


@dataclass(frozen=True)


class QueueArrivalConfig:
    model: QueueArrivalModel
    baseline_rate_per_day: int
    stress_rate_per_day: int


@dataclass(frozen=True)


class QueueServiceConfig:
    dist: DistName
    params: Dict[str, float]


@dataclass(frozen=True)


class QueueServersConfig:
    baseline: int
    stress: int


@dataclass(frozen=True)


class QueueConfig:
    label: str
    servers: QueueServersConfig
    service_time: QueueServiceConfig
    arrivals: QueueArrivalConfig
    service_time_multipliers: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)


class QueuesConfig:
    kyc_queue: QueueConfig
    redemption_queue: QueueConfig
    queue_simulation_horizon_days: Dict[str, int]


@dataclass


class StageResult:
    stage_id: str
    stage_label: str

    time_hours: float = 0.0
    base_time_hours: float = 0.0
    gate_delay_hours: float = 0.0
    risk_delay_hours: float = 0.0
    exception_delay_hours: float = 0.0
    queue_delay_hours: float = 0.0
    explicit_cost: float = 0.0
    implicit_cost: float = 0.0

    approvals: int = 0
    handoffs: int = 0
    intermediaries: Set[str] = field(default_factory=set)

    transfer_attempted: bool = False
    transfer_success: Optional[bool] = None
    redemption_attempted: bool = False
    redemption_success: Optional[bool] = None

    risk_events: List[str] = field(default_factory=list)
    gate_events: List[str] = field(default_factory=list)


@dataclass


class RunResult:
    run_id: int
    asset_id: str
    route_id: str
    scenario_id: str

    total_time_hours: float = 0.0
    total_explicit_cost: float = 0.0
    total_implicit_cost: float = 0.0

    total_approvals: int = 0
    total_handoffs: int = 0
    intermediaries: Set[str] = field(default_factory=set)

    completed: bool = True
    exit_frozen: bool = False
    failed_stage_id: Optional[str] = None

    time_to_position_hours: Optional[float] = None
    time_to_cash_hours: Optional[float] = None

    stages: List[StageResult] = field(default_factory=list)


@dataclass(frozen=True)


class ModelConfig:
    """
    Container for everything loaded from config/*.yaml.
    """
    stages: Dict[str, StageDef]
    assets: Dict[str, AssetConfig]
    routes: Dict[str, RouteConfig]
    scenarios: Dict[str, ScenarioConfig]
    risk_events: Tuple[RiskEvent, ...]
    queues: QueuesConfig
