"""D1/W1 FX28 experimental MACRO aggregation of caller-provided factor claims.

This is the first *computing* research prototype, NOT a calibrated forex
forecast. Signed scores supplied by callers are subjective, unverified
hypothetical impact points; raw CPI surprises, rates and macro values must
NOT be passed directly. Model weights/bands are provisional, not trained,
backtested, independently attested, or safe for positions.

Generate 8 arithmetic currency composites, 28 reciprocal-consistent
relative hypotheses via the existing bilateral symmetry veto, and ABSTAIN
for mixed strong factor signs. A hypothetical research label is NEVER
an authenticated prospective GitHub witness or trade advice.

No HTTP/files, broker, account, MT5, real-time worker, signal, execution,
publishing, fees, precision percentage or fitted probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_bilateral_symmetry_guard_lab import (
    CurrencyScoreClaim, PairRelativeClaim,
    NEUTRAL_BAND, inspect_fx28_bilateral_symmetry_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, _nominal_windows,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_EXPERIMENTAL_MACRO_RELATIVE_SCORE_LAB_V2"
WEIGHTS: dict[str, int] = {
    "policy_expectations": 40,
    "inflation_impact": 20,
    "activity_impact": 25,
    "labor_impact": 15,
}
MAX_EVENT_AGE_DAYS: dict[str, int] = {
    "policy_expectations": 45,
    "inflation_impact": 55,
    "activity_impact": 45,
    "labor_impact": 45,
}
WINDOW_MAX_EARLY_HOURS = 12
W1_ADDITIONAL_ABSTENTION_BAND = 55
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
ROOT = re.compile(r"[A-Z0-9][A-Z0-9._:-]{3,79}\Z")
WEIGHT_SUM = sum(WEIGHTS.values())


@dataclass(frozen=True)
class HypotheticalMacroFactorClaim:
    currency: str
    category: str
    signed_impact_points: int
    event_published_at_utc: datetime
    source_locally_captured_at_utc: datetime
    event_root_id: str
    source_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _configuration_digest() -> str:
    payload = {
        "schema": SCHEMA,
        "factors": WEIGHTS,
        "max_event_age_days": MAX_EVENT_AGE_DAYS,
        "nominal_neutral_band": NEUTRAL_BAND,
        "weekly_additional_abstention_band": W1_ADDITIONAL_ABSTENTION_BAND,
        "earliest_snapshot_hours": WINDOW_MAX_EARLY_HOURS,
        "shared_event_root_pair_veto": True,
        "shared_event_root_pair_veto_version": "V1_ALWAYS_ABSTAIN_OVERLAPPING_ROOT",
    }
    return sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")).hexdigest()


def _base(reason: str, *, horizon: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_HYPOTHETICAL_MACRO_SCORE_BLOCKED",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "horizon": horizon,
        "model_contract_sha256": _configuration_digest(),
        "weights": dict(WEIGHTS),
        "neutral_band_points_not_probability": NEUTRAL_BAND,
        "score_is_synthetic_relative_points_not_economic_measure": True,
        "inputs_are_authenticated_macro_sources": False,
        "macro_surprises_were_calculated_from_official_values": False,
        "first_seen_independently_attested": False,
        "prospective_forecast_witnessed": False,
        "out_of_sample_accuracy_measured": False,
        "percentage_accuracy": None,
        "calibrated_probability": None,
        "currency_score_claims_reconciled": 0,
        "currency_scores_research_only": {},
        "conflicting_currency_codes": [],
        "distinct_root_catalyst_claim_count": 0,
        "shared_event_root_ids": [],
        "pair_shared_root_overlap_veto_count": 0,
        "pair_shared_event_root_overlap_is_not_independent_factor": True,
        "pair_claims_are_independent_economic_events": False,
        "pairs": [{
            "pair": pair, "research_relative_label": "AGUARDAR",
            "hypothetical_points": None,
            "shared_event_root_ids_for_both_legs": [],
            "shared_event_root_overlap_veto": False,
            "reason": "NO_ADMISSIBLE_HYPOTHETICAL_MACRO_INPUT",
            "real_market_direction_authenticated": False,
            "trade_authorized": False,
        } for pair in OFFICIAL_PAIRS],
        "hypothetical_labeled_pair_count": 0,
        "abstained_pair_count": len(OFFICIAL_PAIRS),
        "bilateral_consistency_rechecked": False,
        "directional_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def evaluate_experimental_fx28_macro_relative_score_lab(
    *,
    horizon: Any,
    window_start_utc: Any,
    calculated_at_utc: Any,
    claimed_factors: Any,
) -> dict[str, Any]:
    """Mathematically combine UNVERIFIED impact labels before a window.

    All positive or negative points are USER/TEST hypotheses, NOT findings.
    Even a coherent matrix with 28 research labels remains non-actionable.
    """
    out = _base("INVALID_WINDOW_OR_CUTOFF")
    start, now = _utc(window_start_utc), _utc(calculated_at_utc)
    if (horizon not in ("D1", "W1")
            or start is None or now is None
            or not now < start
            or start - now > timedelta(hours=WINDOW_MAX_EARLY_HOURS)
            or not any(t0 == start for t0, _ in _nominal_windows(horizon))
            or WEIGHT_SUM != 100
            or type(claimed_factors) not in (tuple, list)
            or len(claimed_factors) != len(CURRENCIES) * len(WEIGHTS)):
        return out
    out = _base("INVALID_OR_DUPLICATE_FACTOR_CLAIMS", horizon=horizon)

    seen: dict[tuple[str, str], HypotheticalMacroFactorClaim] = {}
    # One real-world event may be relevant to several currencies,
    # but must not be misrepresented as several INDEPENDENT releases.
    # The same root can be reused only for the same factor/category,
    # source digest and source timing, on a DIFFERENT currency.
    roots: dict[str, tuple[str, str, datetime, datetime]] = {}
    root_currencies: dict[str, set[str]] = {}
    for claim in claimed_factors:
        if (not isinstance(claim, HypotheticalMacroFactorClaim)
                or claim.currency not in CURRENCIES
                or claim.category not in WEIGHTS
                or type(claim.signed_impact_points) is not int
                or not -100 <= claim.signed_impact_points <= 100
                or type(claim.event_root_id) is not str
                or ROOT.fullmatch(claim.event_root_id) is None
                or type(claim.source_sha256_claim) is not str
                or SHA64.fullmatch(claim.source_sha256_claim) is None):
            return out
        key = (claim.currency, claim.category)
        publication = _utc(claim.event_published_at_utc)
        captured = _utc(claim.source_locally_captured_at_utc)
        if (key in seen or publication is None or captured is None
                or publication > captured or captured > now
                or publication > now
                or now - publication > timedelta(
                    days=MAX_EVENT_AGE_DAYS[claim.category])
                or (now - captured) > timedelta(hours=12)):
            return out
        root_identity = (
            claim.category, claim.source_sha256_claim, publication, captured)
        original_identity = roots.get(claim.event_root_id)
        if (original_identity is not None
                and (original_identity != root_identity
                     or claim.currency in root_currencies[claim.event_root_id])):
            # Reject cross-category "independent" use of the same catalyst,
            # issuer/hash/time collisions, and same-currency double counts.
            out["reason"] = "REUSED_CATALYST_NOT_AN_INDEPENDENT_MACRO_FACTOR"
            return out
        roots[claim.event_root_id] = root_identity
        root_currencies.setdefault(claim.event_root_id, set()).add(claim.currency)
        seen[key] = claim

    if (len(seen) != 32 or set(seen) != {
            (currency, factor)
            for currency in CURRENCIES for factor in WEIGHTS}):
        out["reason"] = "INCOMPLETE_EIGHT_CURRENCY_FOUR_FACTOR_ROSTER"
        return out

    scores: dict[str, int] = {}
    claims: list[CurrencyScoreClaim] = []
    conflicting: set[str] = set()
    for currency in sorted(CURRENCIES):
        parts = [seen[(currency, name)] for name in WEIGHTS]
        signed = [p.signed_impact_points for p in parts]
        # Opposite strong factors warn of regime ambiguity. Even a large
        # weighted total cannot override an internal contradiction.
        if any(n >= 40 for n in signed) and any(n <= -40 for n in signed):
            conflicting.add(currency)
        numerator = sum(
            WEIGHTS[p.category] * p.signed_impact_points for p in parts
        )
        score = int((Decimal(numerator) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
        scores[currency] = score
        # SHA describes ONLY caller-supplied claims. It is not an issuer
        # signature, a trustworthy data vintage or a signed model artifact.
        packet = [{
            "currency": p.currency, "category": p.category,
            "signed_impact_points": p.signed_impact_points,
            "event_root_id": p.event_root_id,
            "source_sha256_claim": p.source_sha256_claim,
            "published_at": _utc(p.event_published_at_utc).isoformat(),
            "captured_at": _utc(p.source_locally_captured_at_utc).isoformat(),
        } for p in sorted(parts, key=lambda x: x.category)]
        digest = sha256(json.dumps(
            packet, sort_keys=True, separators=(",", ":"),
        ).encode("ascii")).hexdigest()
        claims.append(CurrencyScoreClaim(
            currency=currency, synthetic_points=score,
            score_captured_at=now, source_sha256_claim=digest,
        ))

    pair_claims = []
    rows = []
    candidate_count = 0
    overlapping_pair_count = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        points = scores[base] - scores[quote]
        # One real-world news story can affect BOTH currencies of a pair.
        # Do NOT mistake its two subjective impact labels for independent
        # evidence. Without a fitted relative event-response model, their
        # subtraction can produce an exaggerated apparent directional edge.
        # Conservative quarantine affects only a pair with BOTH legs on
        # the SAME root. Other 27 pairs are NOT suppressed automatically.
        shared_roots = sorted(
            root for root, currencies in root_currencies.items()
            if base in currencies and quote in currencies
        )
        overlap_veto = bool(shared_roots)
        overlapping_pair_count += int(overlap_veto)
        if overlap_veto:
            label, presented, reason = (
                "AGUARDAR", None,
                "SHARED_EVENT_ROOT_BOTH_CURRENCY_LEGS_NO_RELATIVE_CALIBRATION")
        elif base in conflicting or quote in conflicting:
            label, presented, reason = (
                "AGUARDAR", None, "CONFLICTING_STRONG_MACRO_COMPONENTS")
        elif horizon == "W1" and abs(points) <= W1_ADDITIONAL_ABSTENTION_BAND:
            label, presented, reason = (
                "AGUARDAR", None, "WEEKLY_CONSERVATIVE_ABSTENTION_BAND")
        else:
            label = ("BASE_RELATIVE" if points > NEUTRAL_BAND
                     else "QUOTE_RELATIVE" if points < -NEUTRAL_BAND
                     else "NEUTRAL")
            presented, reason = points, "HYPOTHETICAL_ONLY_UNVERIFIED_FACTORS"
            candidate_count += int(label != "NEUTRAL")
        pair_claims.append(PairRelativeClaim(
            pair=pair, relative_points=presented,
            relative_label=label))
        rows.append({
            "pair": pair, "research_relative_label": label,
            "hypothetical_points": presented, "reason": reason,
            "shared_event_root_ids_for_both_legs": shared_roots,
            "shared_event_root_overlap_veto": overlap_veto,
            "real_market_direction_authenticated": False,
            "trade_authorized": False,
        })

    checked = inspect_fx28_bilateral_symmetry_lab(
        currency_scores=claims,
        pair_claims=pair_claims,
        horizon=horizon,
        decision_at_utc=now,
        inspected_at_utc=now,
    )
    if (checked.get("state") != "LAB_FX28_BILATERAL_COHERENT_CLAIMS_NO_GO"
            or checked.get("pair_score_consistency_verified_locally") is not True
            or checked.get("trade_authorized") is not False):
        out["reason"] = "BILATERAL_SYMMETRY_VETO"
        return out

    out.update({
        "state": "LAB_FX28_HYPOTHETICAL_MACRO_SCORE_COHERENT_NO_GO",
        "reason": "ALL_FACTOR_IMPACTS_ARE_CALLER_SUPPLIED_NOT_REAL_PROVEN_FORECAST",
        "currency_score_claims_reconciled": 8,
        "currency_scores_research_only": {
            name: scores[name] for name in sorted(CURRENCIES)},
        "conflicting_currency_codes": sorted(conflicting),
        "distinct_root_catalyst_claim_count": len(roots),
        "shared_event_root_ids": sorted(
            root for root, currencies in root_currencies.items()
            if len(currencies) > 1),
        "pair_shared_root_overlap_veto_count": overlapping_pair_count,
        "pairs": rows,
        "hypothetical_labeled_pair_count": candidate_count,
        "abstained_pair_count": sum(
            row["research_relative_label"] == "AGUARDAR" for row in rows),
        "bilateral_consistency_rechecked": True,
    })
    return out


__all__ = (
    "SCHEMA", "HypotheticalMacroFactorClaim",
    "evaluate_experimental_fx28_macro_relative_score_lab",
)
