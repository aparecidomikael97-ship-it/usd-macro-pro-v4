"""Offline FX bias-quality accounting with explicit abstentions (LAB only).

No genuine predictions, source-attested prices, out-of-sample certification,
probability calibration, execution costs or trading claims are made here.
Caller-supplied rows are NEVER a validated hit rate or profitability proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_FX_BIAS_QUALITY_ABSTENTION_LAB_V1"
HORIZONS = ("D1", "W1", "M1")
SIDES = ("UP", "DOWN", "ABSTAIN")
MIN_EMITTED_TRIALS_FOR_DESCRIPTIVE_INTERVAL = 100
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,63}\Z")
_PRICE = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,8})?\Z")


@dataclass(frozen=True)
class BiasTrial:
    trial_id: str
    pair: str
    horizon: str
    side: str
    features_captured_at: datetime
    entry_price_captured_at: datetime
    prediction_issued_at: datetime
    outcome_start_at: datetime
    outcome_end_at: datetime
    outcome_captured_at: datetime
    entry_close_price_claim: str
    exit_close_price_claim: str


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BIAS_QUALITY_BLOCKED", "reason": reason,
        "pair": None, "horizon": None,
        "total_decision_opportunities": 0, "emitted_biases": 0,
        "abstentions": 0, "hits": 0, "misses": 0,
        "neutral_forward_outcomes_counted_as_misses": 0,
        "research_claim_only_hit_rate_pct": None,
        "research_claim_only_coverage_pct": None,
        "research_claim_only_wilson_lower_95_pct": None,
        "research_claim_only_lower_bound_at_least_80pct": False,
        "minimum_emitted_sample_size_reached": False,
        "minimum_independent_signal_sample_reached": False,
        "wilson_iid_assumption_verified": False,
        "features_independently_point_in_time_verified": False,
        "broker_prices_independently_verified": False,
        "outcomes_independently_verified": False,
        "independent_out_of_sample_validation_completed": False,
        "transaction_costs_accounted_for": False,
        "calibrated_probability": None, "validated_accuracy": None,
        "can_feed_live_radar": False, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _number(value: Any) -> Decimal | None:
    if not isinstance(value, str) or _PRICE.fullmatch(value) is None:
        return None
    try:
        num = Decimal(value)
        return num if num.is_finite() and num > 0 else None
    except InvalidOperation:
        return None


def _wilson_lower(success: int, sample: int) -> float:
    """Descriptive binomial interval ONLY; correlated market trials violate IID."""
    z = 1.96
    p = success / sample
    z2 = z * z
    return ((p + z2 / (2 * sample) - z * math.sqrt(
        (p * (1 - p) + z2 / (4 * sample)) / sample)) /
        (1 + z2 / sample))


def inspect_fx_bias_quality_claims_lab(
    trials: Any, *, pair: str, horizon: str,
    evaluated_at_utc: datetime, neutral_band_bps: str = "5",
) -> dict[str, Any]:
    """Audit one FX pair/horizon trial set without claiming real-world accuracy.

    A resolved opportunity is counted once. Repeated updates with overlapping
    forward-label windows are rejected instead of inflating the sample size.
    """
    out = _blocked("INVALID_TRIALS_OR_CLOCK")
    evaluated = _clock(evaluated_at_utc)
    band = _number(neutral_band_bps)
    if (evaluated is None or pair not in OFFICIAL_PAIRS or horizon not in HORIZONS
            or not isinstance(trials, (list, tuple)) or not 1 <= len(trials) <= 10_000
            or band is None or band > Decimal("500")):
        return out
    rows: list[tuple[datetime, datetime, str, bool]] = []
    seen = set()
    neutral_misses = 0
    for v in trials:
        if (not isinstance(v, BiasTrial) or v.pair != pair or v.horizon != horizon
                or v.side not in SIDES or not isinstance(v.trial_id, str)
                or _ID.fullmatch(v.trial_id) is None or v.trial_id in seen):
            out["reason"] = "TRIAL_UNIVERSE_OR_ID_INVALID"
            return out
        seen.add(v.trial_id)
        clocks = [_clock(getattr(v, field)) for field in (
            "features_captured_at", "entry_price_captured_at",
            "prediction_issued_at", "outcome_start_at", "outcome_end_at",
            "outcome_captured_at")]
        if any(t is None for t in clocks):
            out["reason"] = "TRIAL_CLOCKS_INVALID"
            return out
        features, entry_captured, issued, start, end, captured = clocks
        if (features > issued or entry_captured > issued
                or not issued < start < end <= captured <= evaluated):
            out["reason"] = "FUTURE_LEAKAGE_OR_UNRESOLVED_OUTCOME"
            return out
        entry, exit_price = (_number(v.entry_close_price_claim),
                             _number(v.exit_close_price_claim))
        if entry is None or exit_price is None:
            out["reason"] = "INVALID_PRICE_LEVEL_CLAIMS"
            return out
        forward_bps = (exit_price / entry - Decimal("1")) * Decimal("10000")
        realized = ("UP" if forward_bps > band else
                    "DOWN" if forward_bps < -band else "FLAT")
        hit = v.side != "ABSTAIN" and v.side == realized
        if v.side != "ABSTAIN" and realized == "FLAT":
            neutral_misses += 1
        rows.append((start, end, v.side, hit))
    rows.sort(key=lambda x: x[0])
    for older, newer in zip(rows, rows[1:]):
        if newer[0] < older[1]:
            out["reason"] = "OVERLAPPING_OUTCOME_WINDOWS_MULTICOUNTING"
            return out
    opportunities = len(rows)
    emitted = sum(side != "ABSTAIN" for _, _, side, _ in rows)
    abstentions = opportunities - emitted
    hits = sum(hit for _, _, _, hit in rows)
    misses = emitted - hits
    coverage = round(100 * emitted / opportunities, 2)
    hit_rate = round(100 * hits / emitted, 2) if emitted else None
    sample_reached = emitted >= MIN_EMITTED_TRIALS_FOR_DESCRIPTIVE_INTERVAL
    wilson = (round(100 * _wilson_lower(hits, emitted), 2)
              if sample_reached else None)
    out.update({
        "state": "LAB_BIAS_QUALITY_SYNTHETIC_OR_CALLER_CLAIM_ACCOUNTED_NO_GO",
        "reason": "UNAUTHENTICATED_PRICE_FEATURE_AND_OUTCOME_CLAIMS_NOT_REAL_ACCURACY",
        "pair": pair, "horizon": horizon,
        "total_decision_opportunities": opportunities,
        "emitted_biases": emitted, "abstentions": abstentions,
        "hits": hits, "misses": misses,
        "neutral_forward_outcomes_counted_as_misses": neutral_misses,
        "research_claim_only_hit_rate_pct": hit_rate,
        "research_claim_only_coverage_pct": coverage,
        "minimum_emitted_sample_size_reached": sample_reached,
        # Non-overlapping FX outcomes can still share economic shocks/regimes.
        # Neither a trial count nor a Wilson calculation proves independence.
        "minimum_independent_signal_sample_reached": False,
        "research_claim_only_wilson_lower_95_pct": wilson,
        "research_claim_only_lower_bound_at_least_80pct": (
            wilson is not None and wilson >= 80),
    })
    return out


__all__ = ["SCHEMA", "BiasTrial", "inspect_fx_bias_quality_claims_lab"]
