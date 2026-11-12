"""Guard consistency of 28 documentary FX relative rankings against 8 G8 anchors.

Strictly offline LAB. Relative points are research labels, not economic facts,
market directions, profits, independent observations or calibrated probabilities.
Never promote a coherent synthetic matrix to a tradable directional bias.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_FX28_BILATERAL_SYMMETRY_GUARD_LAB_V1"
HORIZON_MAX_SCORE_AGE = {"D1": timedelta(hours=12), "W1": timedelta(days=3)}
NEUTRAL_BAND = 40  # synthetic points only, not 40% confidence
LABELS = frozenset({"BASE_RELATIVE", "QUOTE_RELATIVE", "NEUTRAL", "AGUARDAR"})
SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class CurrencyScoreClaim:
    currency: str
    synthetic_points: int
    score_captured_at: datetime
    source_sha256_claim: str


@dataclass(frozen=True)
class PairRelativeClaim:
    pair: str
    relative_points: int | None
    relative_label: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BILATERAL_COHERENCE_BLOCKED",
        "reason": reason, "currency_count": 0, "pair_count": 0,
        "ready_pair_count": 0, "abstained_pair_count": 0,
        "stale_currencies": [], "abstained_pairs": [],
        "inverse_checks": 0, "triangle_checks": 0,
        "pair_score_consistency_verified_locally": False,
        "pair_claims_not_independent_economic_events": True,
        "model_scores_are_calibrated_probabilities": False,
        "independent_macro_sources_authenticated": False,
        "historical_point_in_time_proven": False,
        "validated_accuracy": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "live_alert_allowed": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_fx28_bilateral_symmetry_lab(
    *, currency_scores: Any, pair_claims: Any,
    horizon: Any, decision_at_utc: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Audit supplied labels at a fixed decision cutoff; never calculate a bias.

    Every claim is from the caller and may be synthetic/fabricated. A fail-closed
    check rejects mathematically contradictory pair labels and missing
    abstentions. One stale anchor affects exactly seven crosses, not all 28.
    """
    out = _result("INVALID_INPUT_OR_CUTOFF")
    decision, inspected = _utc(decision_at_utc), _utc(inspected_at_utc)
    if (horizon not in HORIZON_MAX_SCORE_AGE or decision is None or inspected is None
            or inspected < decision or not isinstance(currency_scores, (list, tuple))
            or not isinstance(pair_claims, (list, tuple))
            or len(currency_scores) != len(CURRENCIES)
            or len(pair_claims) != len(OFFICIAL_PAIRS)):
        return out
    scores: dict[str, int] = {}
    stale: set[str] = set()
    for claim in currency_scores:
        if (not isinstance(claim, CurrencyScoreClaim)
                or claim.currency not in CURRENCIES
                or claim.currency in scores
                or type(claim.synthetic_points) is not int
                or not -200 <= claim.synthetic_points <= 200
                or not isinstance(claim.source_sha256_claim, str)
                or SHA.fullmatch(claim.source_sha256_claim) is None):
            out["reason"] = "DUPLICATE_MISSING_OR_INVALID_CURRENCY_SCORE"
            return out
        captured = _utc(claim.score_captured_at)
        if captured is None or captured > decision:
            out["reason"] = "FUTURE_OR_INVALID_SCORE_CAPTURE"
            return out
        # A score snapshot is time-limited even if underlying CPI/policy data
        # may legitimately have a much older observation period.
        if decision - captured > HORIZON_MAX_SCORE_AGE[horizon]:
            stale.add(claim.currency)
        scores[claim.currency] = claim.synthetic_points
    if set(scores) != set(CURRENCIES):
        out["reason"] = "CURRENCY_UNIVERSE_NOT_COMPLETE"
        return out
    # Different capture times are allowed, but never treated as 8 independent
    # original economic events; each currency's age is checked individually.
    claims: dict[str, PairRelativeClaim] = {}
    for claim in pair_claims:
        if (not isinstance(claim, PairRelativeClaim)
                or claim.pair not in OFFICIAL_PAIRS or claim.pair in claims
                or claim.relative_label not in LABELS):
            out["reason"] = "PAIR_UNIVERSE_OR_LABEL_INVALID"
            return out
        claims[claim.pair] = claim
    if set(claims) != set(OFFICIAL_PAIRS):
        out["reason"] = "PAIR_UNIVERSE_NOT_COMPLETE"
        return out

    ready: dict[frozenset[str], tuple[str, str, int]] = {}
    abstained: list[str] = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        claim = claims[pair]
        missing_anchor = base in stale or quote in stale
        if missing_anchor:
            if claim.relative_label != "AGUARDAR" or claim.relative_points is not None:
                out["reason"] = "STALE_ANCHOR_USED_AS_DIRECTIONAL_PAIR"
                return out
            abstained.append(pair)
            continue
        if claim.relative_label == "AGUARDAR":
            if claim.relative_points is not None:
                out["reason"] = "WAIT_PAIR_MUST_NOT_CLAIM_RELATIVE_POINTS"
                return out
            abstained.append(pair)
            continue
        expected = scores[base] - scores[quote]
        expected_label = (
            "BASE_RELATIVE" if expected > NEUTRAL_BAND else
            "QUOTE_RELATIVE" if expected < -NEUTRAL_BAND else "NEUTRAL"
        )
        if (type(claim.relative_points) is not int
                or claim.relative_points != expected
                or claim.relative_label != expected_label):
            out["reason"] = "PAIR_DIFFERENTIAL_OR_SIGN_CONTRADICTS_BILATERAL_ANCHORS"
            return out
        ready[frozenset((base, quote))] = (base, quote, expected)

    def oriented(a: str, b: str) -> int | None:
        v = ready.get(frozenset((a, b)))
        if v is None:
            return None
        base, quote, diff = v
        return diff if (a, b) == (base, quote) else -diff

    triangles = 0
    for a, b, c in combinations(CURRENCIES, 3):
        ab, bc, ac = oriented(a, b), oriented(b, c), oriented(a, c)
        if ab is None or bc is None or ac is None:
            continue
        if ab + bc != ac:
            out["reason"] = "INCONSISTENT_CURRENCY_TRIANGLE"
            return out
        triangles += 1
    out.update({
        "state": "LAB_FX28_BILATERAL_COHERENT_CLAIMS_NO_GO",
        "reason": "SYNTHETIC_OR_CALLER_SUPPLIED_SCORES_NOT_AUTHENTICATED",
        "currency_count": len(scores), "pair_count": len(claims),
        "ready_pair_count": len(ready),
        "abstained_pair_count": len(abstained),
        "stale_currencies": sorted(stale),
        "abstained_pairs": abstained,
        "inverse_checks": len(ready), "triangle_checks": triangles,
        "pair_score_consistency_verified_locally": True,
    })
    return out


__all__ = (
    "CurrencyScoreClaim", "PairRelativeClaim", "NEUTRAL_BAND",
    "inspect_fx28_bilateral_symmetry_lab",
)