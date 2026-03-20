"""Smoke tests for the hybrid lifecycle runner (queue injection path)."""

from dataclasses import replace

from sim.config_loader import load_model_config
from sim.gates import InvestorProfile
from sim.hybrid import run_single_lifecycle_hybrid
from sim.queues import _dist_from_queue_service, build_queue_wait_samplers


def test_hybrid_stress_injects_queue_delay():
    cfg = load_model_config("config")
    scenario = cfg.scenarios["STRESS"]
    samplers = build_queue_wait_samplers(model=cfg, scenario=scenario)

    res = run_single_lifecycle_hybrid(
        model=cfg,
        run_id=1,
        asset_id="TBILL_MMF",
        route_id="TRADFI",
        scenario_id="STRESS",
        investor=InvestorProfile(qualified_investor=False),
        queue_samplers=samplers,
    )

    assert res.scenario_id == "STRESS"
    assert res.route_id == "TRADFI"
    assert isinstance(res.total_time_hours, float)
    assert res.total_time_hours > 0

    kyc_stages = [s for s in res.stages if s.stage_id == "KYC_REVIEW"]
    red_stages = [s for s in res.stages if s.stage_id == "REDEMPTION_PROCESSING"]
    total_queue_delay = sum(s.queue_delay_hours for s in res.stages)
    assert total_queue_delay >= 0
    if kyc_stages:
        assert kyc_stages[0].queue_delay_hours >= 0
    if red_stages:
        assert red_stages[0].queue_delay_hours >= 0


def test_hybrid_baseline_no_queue_delay():
    cfg = load_model_config("config")

    res = run_single_lifecycle_hybrid(
        model=cfg,
        run_id=1,
        asset_id="TBILL_MMF",
        route_id="TOKENIZED",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=False),
        queue_samplers=None,
    )

    assert res.scenario_id == "BASELINE"
    total_queue_delay = sum(s.queue_delay_hours for s in res.stages)
    assert total_queue_delay == 0.0


def test_hybrid_stress_tokenized_private_credit():
    cfg = load_model_config("config")
    scenario = cfg.scenarios["STRESS"]
    samplers = build_queue_wait_samplers(model=cfg, scenario=scenario)

    res = run_single_lifecycle_hybrid(
        model=cfg,
        run_id=1,
        asset_id="PRIVATE_CREDIT",
        route_id="TOKENIZED",
        scenario_id="STRESS",
        investor=InvestorProfile(qualified_investor=True),
        queue_samplers=samplers,
    )

    assert res.scenario_id == "STRESS"
    assert res.asset_id == "PRIVATE_CREDIT"
    assert res.completed is True
    assert res.total_time_hours > 0


def test_route_specific_queue_service_multipliers_scale_service_distribution():
    cfg = load_model_config("config")
    stressed_queues = replace(
        cfg.queues,
        kyc_queue=replace(
            cfg.queues.kyc_queue,
            service_time_multipliers={"default": 1.0, "TRADFI": 1.5, "TOKENIZED": 0.5},
        ),
    )
    forced_cfg = replace(cfg, queues=stressed_queues)
    tradfi_spec = _dist_from_queue_service(forced_cfg.queues.kyc_queue, route_id="TRADFI")
    tokenized_spec = _dist_from_queue_service(forced_cfg.queues.kyc_queue, route_id="TOKENIZED")

    assert tradfi_spec.params["mode"] > tokenized_spec.params["mode"]
    assert tradfi_spec.params["high"] > tokenized_spec.params["high"]
