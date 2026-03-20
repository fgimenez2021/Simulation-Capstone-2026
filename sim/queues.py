from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, List

import simpy

from .randomness import RNG, sample_dist
from .types import DistSpec, ModelConfig, ScenarioConfig


@dataclass(frozen=True)
class QueueWaitSamplers:
    """
    Callable samplers returning a waiting time in HOURS.
    These are estimated from a separate queue environment simulation.
    """
    kyc_wait_hours: Callable[[RNG], float]
    redemption_wait_hours: Callable[[RNG], float]


def build_queue_wait_samplers(
    *,
    model: ModelConfig,
    scenario: ScenarioConfig,
    route_id: str | None = None,
) -> QueueWaitSamplers:
    """Build waiting-time samplers by simulating KYC and redemption queues for a scenario."""
    mode = scenario.mode
    horizon_days = int(model.queues.queue_simulation_horizon_days.get(mode, 5))
    horizon_hours = float(horizon_days) * 24.0

    q_rng = RNG.from_seed(scenario.seed + 10_000)

    kyc_arrival_rate, red_arrival_rate = _effective_arrival_rates_per_day(model, scenario)

    kyc_waits = _simulate_single_queue_waits(
        rng=q_rng,
        env_horizon_hours=horizon_hours,
        queue_name="kyc_queue",
        servers=_servers_for_mode(model.queues.kyc_queue, mode),
        arrival_model=model.queues.kyc_queue.arrivals.model,
        arrival_rate_per_day=kyc_arrival_rate,
        service_time=_dist_from_queue_service(
            model.queues.kyc_queue,
            route_id=route_id,
        ),
    )

    red_waits = _simulate_single_queue_waits(
        rng=q_rng,
        env_horizon_hours=horizon_hours,
        queue_name="redemption_queue",
        servers=_servers_for_mode(model.queues.redemption_queue, mode),
        arrival_model=model.queues.redemption_queue.arrivals.model,
        arrival_rate_per_day=red_arrival_rate,
        service_time=_dist_from_queue_service(
            model.queues.redemption_queue,
            route_id=route_id,
        ),
    )

    def make_sampler(waits: List[float]) -> Callable[[RNG], float]:
        if not waits:
            return lambda _rng: 0.0

        def sampler(rng: RNG) -> float:
            idx = int(rng.gen.integers(0, len(waits)))
            return float(waits[idx])

        return sampler

    return QueueWaitSamplers(
        kyc_wait_hours=make_sampler(kyc_waits),
        redemption_wait_hours=make_sampler(red_waits),
    )


def _servers_for_mode(queue_cfg, mode: str) -> int:
    return int(queue_cfg.servers.baseline if mode == "baseline" else queue_cfg.servers.stress)


def _arrival_rate_for_mode(queue_cfg, mode: str) -> int:
    return int(queue_cfg.arrivals.baseline_rate_per_day if mode == "baseline" else queue_cfg.arrivals.stress_rate_per_day)


def _effective_arrival_rates_per_day(model: ModelConfig, scenario: ScenarioConfig) -> tuple[int, int]:
    """
    Arrival-rate source of truth:
      1) Use scenario-level arrivals for traceability across scenario definitions.
      2) Fallback to queue-level rates if scenario value is missing/invalid.
    Mapping:
      - scenario.arrivals.onboarding_requests_per_day -> kyc_queue
      - scenario.arrivals.redemption_requests_per_day -> redemption_queue
    """
    mode = scenario.mode
    kyc_fallback = _arrival_rate_for_mode(model.queues.kyc_queue, mode)
    red_fallback = _arrival_rate_for_mode(model.queues.redemption_queue, mode)

    kyc = int(getattr(scenario.arrivals, "onboarding_requests_per_day", 0))
    red = int(getattr(scenario.arrivals, "redemption_requests_per_day", 0))

    if kyc <= 0:
        kyc = kyc_fallback
    if red <= 0:
        red = red_fallback

    return kyc, red


def _dist_from_queue_service(queue_cfg, *, route_id: str | None = None) -> DistSpec:
    multiplier = float(queue_cfg.service_time_multipliers.get("default", 1.0))
    if route_id is not None:
        multiplier = float(queue_cfg.service_time_multipliers.get(route_id, multiplier))

    spec = DistSpec(dist=queue_cfg.service_time.dist, params=queue_cfg.service_time.params)
    return _scale_dist_spec(spec, multiplier)


def _scale_dist_spec(spec: DistSpec, multiplier: float) -> DistSpec:
    if multiplier == 1.0:
        return spec

    if spec.dist == "fixed":
        return DistSpec(dist="fixed", params={"value": float(spec.params["value"]) * multiplier})

    if spec.dist == "triangular":
        return DistSpec(
            dist="triangular",
            params={
                "low": float(spec.params["low"]) * multiplier,
                "mode": float(spec.params["mode"]) * multiplier,
                "high": float(spec.params["high"]) * multiplier,
            },
        )

    if spec.dist == "lognormal":
        return DistSpec(
            dist="lognormal",
            params={
                "mean": float(spec.params["mean"]) + math.log(multiplier),
                "sigma": float(spec.params["sigma"]),
            },
        )

    return spec


def _simulate_single_queue_waits(
    *,
    rng: RNG,
    env_horizon_hours: float,
    queue_name: str,
    servers: int,
    arrival_model: str,
    arrival_rate_per_day: int,
    service_time: DistSpec,
) -> List[float]:
    """
    Simulates a single queue environment and collects waiting times for arriving jobs.

    - arrivals: fixed_per_day or poisson_per_day
    - servers: number of parallel resources
    - service_time: distribution for service duration (hours)

    Returns list of observed waits in hours.
    """
    env = simpy.Environment()
    resource = simpy.Resource(env, capacity=max(1, int(servers)))

    waits: List[float] = []

    lam_per_hour = float(arrival_rate_per_day) / 24.0

    def arrival_process():
        t = 0.0
        while env.now < env_horizon_hours:
            if arrival_model == "fixed_per_day":
                inter = 24.0 / max(1.0, float(arrival_rate_per_day))
            elif arrival_model == "poisson_per_day":
                if lam_per_hour <= 0:
                    break
                inter = float(rng.gen.exponential(1.0 / lam_per_hour))
            else:
                raise ValueError(f"Unknown arrival model: {arrival_model}")

            t += inter
            if t > env_horizon_hours:
                break

            env.process(job_process(arrival_time=t))

            yield env.timeout(inter)

    def job_process(arrival_time: float):
        if env.now < arrival_time:
            yield env.timeout(arrival_time - env.now)

        with resource.request() as req:
            start_wait = env.now
            yield req
            wait = env.now - start_wait
            waits.append(float(wait))

            svc = sample_dist(service_time, rng)
            yield env.timeout(svc)

    env.process(arrival_process())
    env.run(until=env_horizon_hours)

    return waits
