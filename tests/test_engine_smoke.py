from dataclasses import replace

from sim.config_loader import load_model_config
from sim.engine import run_single_lifecycle
from sim.gates import InvestorProfile


def test_engine_runs_baseline_tbill_tradfi():
    cfg = load_model_config("config")
    res = run_single_lifecycle(
        model=cfg,
        run_id=1,
        asset_id="TBILL_MMF",
        route_id="TRADFI",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=False),
    )
    assert res.asset_id == "TBILL_MMF"
    assert res.route_id == "TRADFI"
    assert res.scenario_id == "BASELINE"
    assert isinstance(res.total_time_hours, float)
    assert len(res.stages) > 0


def test_private_credit_blocks_retail_investor():
    cfg = load_model_config("config")
    res = run_single_lifecycle(
        model=cfg,
        run_id=1,
        asset_id="PRIVATE_CREDIT",
        route_id="TRADFI",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=False),
    )
    assert res.completed is False
    assert res.failed_stage_id is not None
    assert any(s.gate_events for s in res.stages)
    assert not any("GATE_DENIED" in ev for s in res.stages for ev in s.risk_events)


def test_private_credit_allows_qualified_investor():
    cfg = load_model_config("config")
    res = run_single_lifecycle(
        model=cfg,
        run_id=2,
        asset_id="PRIVATE_CREDIT",
        route_id="TOKENIZED",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=True),
    )
    assert res.completed is True
    assert len(res.stages) > 0


def test_redemption_rules_reject_is_applied_in_engine():
    cfg = load_model_config("config")
    tokenized = cfg.routes["TOKENIZED"]
    red_stage = tokenized.stages["REDEMPTION_PROCESSING"]
    forced_red_stage = replace(
        red_stage,
        redemption_rules=replace(
            red_stage.redemption_rules,
            redemption_hold_probability=0.0,
            redemption_reject_probability=1.0,
        ),
    )
    forced_tokenized = replace(
        tokenized,
        stages={**tokenized.stages, "REDEMPTION_PROCESSING": forced_red_stage},
    )
    forced_cfg = replace(cfg, routes={**cfg.routes, "TOKENIZED": forced_tokenized})

    res = run_single_lifecycle(
        model=forced_cfg,
        run_id=7,
        asset_id="TBILL_MMF",
        route_id="TOKENIZED",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=False),
    )

    assert res.exit_frozen is True
    red_rows = [s for s in res.stages if s.stage_id == "REDEMPTION_PROCESSING"]
    assert len(red_rows) == 1
    assert red_rows[0].redemption_attempted is True
    assert red_rows[0].redemption_success is False


def test_asset_time_adders_create_route_asset_interaction():
    cfg = load_model_config("config")
    tradfi = cfg.routes["TRADFI"]
    custody_stage = tradfi.stages["CUSTODY_RECORDING"]
    forced_custody = replace(
        custody_stage,
        asset_time_adders_hours={"PRIVATE_CREDIT": 24.0},
    )
    forced_tradfi = replace(
        tradfi,
        stages={**tradfi.stages, "CUSTODY_RECORDING": forced_custody},
    )
    forced_cfg = replace(cfg, routes={**cfg.routes, "TRADFI": forced_tradfi})

    tbill = run_single_lifecycle(
        model=forced_cfg,
        run_id=11,
        asset_id="TBILL_MMF",
        route_id="TRADFI",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=False),
    )
    private_credit = run_single_lifecycle(
        model=forced_cfg,
        run_id=11,
        asset_id="PRIVATE_CREDIT",
        route_id="TRADFI",
        scenario_id="BASELINE",
        investor=InvestorProfile(qualified_investor=True),
    )

    assert private_credit.total_time_hours > tbill.total_time_hours
