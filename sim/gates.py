from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .randomness import RNG, bernoulli
from .types import AssetConfig, ScenarioConfig, StageRouteSpec


@dataclass(frozen=True)


class GateResult:
    """Result of applying structural gates at a stage."""
    allowed: bool
    reason: str = "ok"
    add_delay_hours: float = 0.0

    transfer_success: Optional[bool] = None
    redemption_allowed: Optional[bool] = None


@dataclass(frozen=True)


class InvestorProfile:
    """Investor profile for eligibility gating."""
    qualified_investor: bool = False


def check_asset_eligibility(
    asset: AssetConfig,
    investor: InvestorProfile,
) -> Tuple[bool, str]:
    if asset.eligibility.requires_qualified_investor and not investor.qualified_investor:
        return False, "requires_qualified_investor"
    return True, "ok"


def apply_stage_gates(
    *,
    stage_id: str,
    stage_spec: StageRouteSpec,
    asset: AssetConfig,
    scenario: ScenarioConfig,
    investor: InvestorProfile,
    rng: RNG,
) -> GateResult:
    """
    Apply structural gates (eligibility, allowlist, transfer restrictions) at a stage.

    Separate from risk events, which are probabilistic (handled in risk.py).
    """
    ok, reason = check_asset_eligibility(asset, investor)
    if not ok:
        return GateResult(allowed=False, reason=reason)

    if stage_spec.gating and stage_spec.gating.requires_allowlist:
        p = float(stage_spec.gating.allowlist_pass_probability)
        if not bernoulli(p, rng):
            return GateResult(allowed=False, reason="allowlist_failed")

    if stage_id == "TRANSFERABILITY":
        if stage_spec.restrictions and stage_spec.restrictions.transfers_restricted:
            p = float(stage_spec.restrictions.transfer_pass_probability)
            success = bernoulli(p, rng)
            return GateResult(allowed=True, reason="transfer_restricted_checked", transfer_success=success)

        return GateResult(allowed=True, reason="transfer_unrestricted", transfer_success=True)

    if stage_id == "EXIT_INITIATION":
        return GateResult(allowed=True, reason="exit_allowed", redemption_allowed=True)

    if stage_id == "REDEMPTION_PROCESSING":
        rules = stage_spec.redemption_rules
        if rules is None:
            return GateResult(allowed=True, reason="redemption_ok", redemption_allowed=True)

        reject_p = float(rules.redemption_reject_probability)
        hold_p = float(rules.redemption_hold_probability)

        r = float(rng.gen.random())
        if r < reject_p:
            return GateResult(
                allowed=True,
                reason="redemption_rejected_by_rules",
                redemption_allowed=False,
            )
        if r < reject_p + hold_p:
            hold_delay = (
                float(rules.hold_delay_hours_stress)
                if scenario.mode == "stress"
                else float(rules.hold_delay_hours)
            )
            return GateResult(
                allowed=True,
                reason="redemption_hold_by_rules",
                add_delay_hours=hold_delay,
                redemption_allowed=True,
            )

        return GateResult(allowed=True, reason="redemption_ok", redemption_allowed=True)

    return GateResult(allowed=True, reason="ok")


def redemption_window_delay_hours(asset: AssetConfig) -> float:
    """Average wait for next redemption window (half the window period)."""
    wt = asset.redemption.window_type
    if wt == "daily":
        return 0.0
    if wt == "weekly":
        return 3.0 * 24.0
    if wt == "monthly":
        return 15.0 * 24.0
    if wt == "quarterly":
        return 45.0 * 24.0
    return 0.0


def redemption_notice_delay_hours(asset: AssetConfig) -> float:
    """Notice period delay in hours."""
    return float(asset.redemption.notice_days) * 24.0
