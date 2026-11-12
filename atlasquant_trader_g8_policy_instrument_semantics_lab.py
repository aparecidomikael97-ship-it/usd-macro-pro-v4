"""Audit 8 heterogeneous G8 policy instruments without a rate-strength score.

This is manually researched source context as of 2026-11-08. The exact policy
decision PDF/HTML was not independently preserved at original release time.
Nominal cross-country rates are not interchangeable: no FX side or probability.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_issuer_custody_chain_lab import DOCS

SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_INSTRUMENT_SEMANTICS_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_INSTRUMENT_RESEARCH_LAB_V1"
CASEBOOK_SHA256 = "392f62e1c7d6d29a8dd3d4c0b850ffb5e3b52df01c403a42c728e04ac551f30c"
VISIBLE_AFTER_UTC = datetime(2026, 11, 9, tzinfo=timezone.utc)
CASE_FIELDS = frozenset((
    "schema", "kind", "research_date", "conservative_visible_after_utc",
    "original_issuer_response_bytes_archived_at_release",
    "first_publication_time_independently_attested",
    "rate_instruments_internationally_harmonized",
    "observed_market_rate_or_future_expected_path", "entries",
))
ROW_FIELDS = frozenset((
    "currency", "decision_date", "instrument_id", "representation",
    "value_point_pct", "lower_pct", "upper_pct", "source_url",
))
INSTRUMENTS = {
    "USD": ("FEDERAL_FUNDS_TARGET_RANGE", "TARGET_RANGE"),
    "EUR": ("ECB_DEPOSIT_FACILITY_RATE", "EXACT_INSTRUMENT_LEVEL"),
    "GBP": ("BOE_BANK_RATE", "EXACT_INSTRUMENT_LEVEL"),
    "CAD": ("BOC_OVERNIGHT_TARGET_RATE", "EXACT_INSTRUMENT_LEVEL"),
    "AUD": ("RBA_CASH_RATE_TARGET", "EXACT_INSTRUMENT_LEVEL"),
    "JPY": ("BOJ_UNCOLLATERALIZED_OVERNIGHT_CALL_GUIDELINE", "APPROXIMATE_GUIDELINE"),
    "CHF": ("SNB_POLICY_RATE", "EXACT_INSTRUMENT_LEVEL"),
    "NZD": ("RBNZ_OFFICIAL_CASH_RATE", "EXACT_INSTRUMENT_LEVEL"),
}
_DECIMAL = re.compile(r"-?(?:0|[1-9]\d?)\.\d{2}\Z")


def _pairs_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in items:
        if key in out:
            raise ValueError("duplicate JSON field")
        out[key] = val
    return out


def _number(raw: Any) -> Decimal | None:
    if not isinstance(raw, str) or _DECIMAL.fullmatch(raw) is None:
        return None
    try:
        x = Decimal(raw)
    except InvalidOperation:
        return None
    return x if x.is_finite() and Decimal("-10") <= x <= Decimal("50") else None


def _blocked(reason: str, state: str = "LAB_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "casebook_sha256": None,
        "research_visible_after_utc": "2026-11-09T00:00:00Z",
        "currency_count": 0, "pair_count": 0, "currency_rows": [], "pair_rows": [],
        "representation_counts": {},
        "original_issuer_response_bytes_archived_at_release": False,
        "historical_policy_rate_vintages_verified": False,
        "issuer_release_instant_independently_attested": False,
        "nominal_instruments_cross_currency_comparable": False,
        "actual_market_yields_observed": False,
        "future_policy_expectation_curve_available": False,
        "real_interest_rate_differentials_verified": False,
        "policy_strength_scores_calculated": False,
        "validated_directional_accuracy": None,
        "operational_bias": "AGUARDAR", "fx_bias": None,
        "trade_authorized": False, "historical_backtest_approved": False,
        "can_feed_live_radar": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_g8_policy_instrument_semantics_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Grade static issuer-rate *research*, never use rate differences as FX bias."""
    out = _blocked("INVALID_CASEBOOK_OR_CLOCK")
    if (not isinstance(casebook_raw, bytes) or not 1000 <= len(casebook_raw) <= 14000
            or sha256(casebook_raw).hexdigest() != CASEBOOK_SHA256
            or not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None or len(CURRENCIES) != 8
            or len(OFFICIAL_PAIRS) != 28 or set(DOCS) != set(CURRENCIES)):
        return out
    if as_of_utc.astimezone(timezone.utc) < VISIBLE_AFTER_UTC:
        return _blocked("RETROSPECTIVE_RESEARCH_NOT_VISIBLE_YET",
                        "LAB_RESEARCH_NOT_VISIBLE_ASOF")
    try:
        case = json.loads(casebook_raw.decode("utf-8", "strict"),
                          object_pairs_hook=_pairs_no_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
        if (not isinstance(case, dict) or case.keys() != CASE_FIELDS
                or case["schema"] != CASE_SCHEMA
                or case["kind"] != "RETROSPECTIVE_OFFICIAL_DECISION_VALUES_NOT_VINTAGE_OR_POLICY_STANCE_SCORE"
                or case["research_date"] != "2026-11-08"
                or case["conservative_visible_after_utc"] != "2026-11-09T00:00:00Z"
                or case["original_issuer_response_bytes_archived_at_release"] is not False
                or case["first_publication_time_independently_attested"] is not False
                or case["rate_instruments_internationally_harmonized"] is not False
                or case["observed_market_rate_or_future_expected_path"] is not False
                or not isinstance(case["entries"], list) or len(case["entries"]) != 8):
            return out
        rows = []
        for entry in case["entries"]:
            if not isinstance(entry, dict) or entry.keys() != ROW_FIELDS:
                return out
            currency = entry["currency"]
            if not isinstance(currency, str) or currency not in DOCS:
                return out
            expected_day, expected_url, _ = DOCS[currency]
            instrument, representation = INSTRUMENTS[currency]
            if (entry["decision_date"] != expected_day
                    or entry["source_url"] != expected_url
                    or entry["instrument_id"] != instrument
                    or entry["representation"] != representation):
                return out
            point = _number(entry["value_point_pct"])
            lower = _number(entry["lower_pct"])
            upper = _number(entry["upper_pct"])
            if representation == "TARGET_RANGE":
                if (entry["value_point_pct"] is not None
                        or lower is None or upper is None or lower >= upper):
                    return out
            elif point is None or entry["lower_pct"] is not None or entry["upper_pct"] is not None:
                return out
            rows.append({
                "currency": currency, "decision_calendar_date_claim": expected_day,
                "instrument_id": instrument, "representation": representation,
                "issuer_researched_point_pct_claim": entry["value_point_pct"],
                "issuer_researched_range_low_pct_claim": entry["lower_pct"],
                "issuer_researched_range_high_pct_claim": entry["upper_pct"],
                "source_url": expected_url,
                "rate_claim_is_a_measured_market_yield": False,
                "approximate_wording_must_be_preserved": (
                    representation == "APPROXIMATE_GUIDELINE"),
                "original_release_bytes_independently_attested": False,
                "historical_asof_safe": False,
                "D1": "AGUARDAR", "W1": "AGUARDAR",
            })
    except (UnicodeDecodeError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError):
        return out
    by = {r["currency"]: r for r in rows}
    if len(by) != 8 or set(by) != set(CURRENCIES):
        return out
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "base_instrument": by[base]["instrument_id"],
            "quote_instrument": by[quote]["instrument_id"],
            "raw_nominal_level_spread_pct_points": None,
            "economic_stance_comparable": False,
            "rate_instrument_mapping_is_not_a_currency_strength_score": True,
            "historical_asof_safe": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })
    out.update({
        "state": "LAB_EIGHT_POLICY_INSTRUMENTS_RESEARCHED_HETEROGENEOUS_UNATTESTED",
        "reason": "LEVELS_DIFFER_IN_DEFINITION_AND_NO_PIT_EXPECTATIONS_OR_REAL_RATE_DATA",
        "casebook_sha256": CASEBOOK_SHA256,
        "currency_count": len(rows), "pair_count": len(pairs),
        "currency_rows": sorted(rows, key=lambda r: r["currency"]),
        "pair_rows": pairs,
        "representation_counts": dict(sorted(Counter(
            r["representation"] for r in rows).items())),
    })
    return out


__all__ = ["SCHEMA", "CASEBOOK_SHA256", "INSTRUMENTS",
           "inspect_g8_policy_instrument_semantics_lab"]
