"""LAB-only D1/W1 bias-outcome quality, with FX New York 17:00 windows.

A 24-hour or 5-day duration alone can cover the wrong market sessions.
Check each claimed label against the *existing* IANA NY17 reference convention
before delegating to the synthetic/caller-claim bias-quality accountant.
Neither the calendar nor the result prices are independent broker evidence.
MN1 is deliberately excluded until a monthly FX window contract exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_bias_quality_lab import (
    BiasTrial, inspect_fx_bias_quality_claims_lab,
)
from atlasquant_trader_fx_ny_rollover_lab import (
    CONVENTION, inspect_fx_ny_close_window_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_BIAS_NY17_CALENDAR_JOIN_LAB_V1"
APPROVED_QUALITY_STATE = "LAB_BIAS_QUALITY_SYNTHETIC_OR_CALLER_CLAIM_ACCOUNTED_NO_GO"
APPROVED_CALENDAR_STATE = "LAB_FX_NY_ROLLOVER_WINDOW_STRUCTURALLY_VALID"
MAX_TRIALS = 10000


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str, *, pair: str | None = None,
             horizon: str | None = None, rejected_index: int | None = None
             ) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX_BIAS_NY17_JOIN_BLOCKED",
        "reason": reason,
        "pair": pair,
        "horizon": horizon,
        "rejected_trial_index": rejected_index,
        "calendar_convention": CONVENTION,
        "claimed_sessions_checked": 0,
        "claimed_quality_accounting": None,
        "strict_ny17_claim_window_shape_checked": False,
        "new_york_iana_timezone_applied": False,
        "broker_session_calendar_independently_verified": False,
        "broker_holidays_and_early_closes_verified": False,
        "prediction_precommit_independently_verified": False,
        "point_in_time_features_independently_verified": False,
        "price_originals_independently_verified": False,
        "outcomes_independently_verified": False,
        "statistical_independence_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "can_feed_live_radar": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx_bias_ny17_calendar_join_lab(
    trials: Any, *, pair: Any, horizon: Any,
    evaluated_at_utc: Any, neutral_band_bps: str = "5",
) -> dict[str, Any]:
    """Check each claimed outcome session before documentary quality counts.

    Reject all input if one candidate is misaligned or a quality rule fails:
    silently omitting it would bias denominators. This is not a broker bar
    calendar or a point-in-time snapshot verifier.
    """
    evaluated = _utc(evaluated_at_utc)
    if (not isinstance(pair, str) or pair not in OFFICIAL_PAIRS
            or not isinstance(horizon, str) or horizon not in ("D1", "W1")
            or evaluated is None or not isinstance(trials, (list, tuple))
            or not 1 <= len(trials) <= MAX_TRIALS):
        return _blocked("INVALID_INPUT_OR_UNSUPPORTED_MN1_CALENDAR")

    for index, trial in enumerate(trials):
        if (not isinstance(trial, BiasTrial) or trial.pair != pair
                or trial.horizon != horizon):
            return _blocked("TRIAL_PAIR_HORIZON_OR_TYPE_CONFLICT",
                            pair=pair, horizon=horizon, rejected_index=index)
        start = _utc(trial.outcome_start_at)
        end = _utc(trial.outcome_end_at)
        if start is None or end is None:
            return _blocked("NON_UTC_AWARE_OR_SUBSECOND_WINDOW",
                            pair=pair, horizon=horizon, rejected_index=index)
        calendar = inspect_fx_ny_close_window_lab(
            horizon=horizon, start_at_utc=start, end_at_utc=end,
        )
        if calendar["state"] != APPROVED_CALENDAR_STATE:
            return _blocked("NONCANONICAL_NY17_" + calendar["reason"],
                            pair=pair, horizon=horizon, rejected_index=index)

    accountant = inspect_fx_bias_quality_claims_lab(
        trials, pair=pair, horizon=horizon,
        evaluated_at_utc=evaluated, neutral_band_bps=neutral_band_bps,
    )
    if accountant["state"] != APPROVED_QUALITY_STATE:
        return _blocked("BIAS_QUALITY_" + accountant["reason"],
                        pair=pair, horizon=horizon)

    result = _blocked("ALL_WINDOWS_ARE_CONVENTIONAL_NOT_SOURCE_ATTESTED",
                      pair=pair, horizon=horizon)
    result.update({
        "state": "LAB_FX_NY17_BIAS_QUALITY_CLAIM_ONLY_NO_GO",
        "claimed_sessions_checked": len(trials),
        "claimed_quality_accounting": accountant,
        "strict_ny17_claim_window_shape_checked": True,
        "new_york_iana_timezone_applied": True,
    })
    return result


__all__ = ("SCHEMA", "inspect_fx_bias_ny17_calendar_join_lab")
