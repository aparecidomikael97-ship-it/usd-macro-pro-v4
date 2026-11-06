"""Fixed 2026-11-06 G8 macro *documentary* example, never a market bias.

Official-page numbers were manually transcribed in a committed casebook; this
code does not fetch, timestamp, authenticate or license the original bytes.
An event's embargo/publication date is not its independently witnessed receipt.
No pre-release consensus is available in this casebook, so surprise = null.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_NOV6_MACRO_DOCUMENTARY_CASE_LAB_V1"
KIND = "MANUAL_POST_RELEASE_TRANSCRIPTION_NOT_HISTORICAL_PIT"
MAX_BYTES = 7000

# Exact fixed documentary case, *not* a generic current data feed.
EVENTS = [
    {
        "event_id": "BOE_NOV2026_POLICY_DECISION",
        "currency": "GBP", "factor_family": "MONETARY_POLICY",
        "reference_period": "2026-11-05",
        "source_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026",
        "official_page_publication_date_utc": "2026-11-05",
        "publication_time_precision": "DATE_ONLY",
        "earliest_conservative_after_release_utc": "2026-11-06T00:00:00Z",
        "reported_metrics": {
            "bank_rate_percent_after": "4.00",
            "bank_rate_percent_before": "3.75",
            "announced_change_percentage_points": "0.25",
        },
        "pre_event_market_consensus_value": None,
        "source_original_bytes_archived": False,
    },
    {
        "event_id": "BLS_OCT2026_EMPLOYMENT_SITUATION",
        "currency": "USD", "factor_family": "EMPLOYMENT",
        "reference_period": "2026-10",
        "source_url": "https://www.bls.gov/news.release/archives/empsit_11062026.htm",
        "official_page_publication_date_utc": "2026-11-06",
        "publication_time_precision": "EMBARGO_CLOCK_ET",
        "earliest_conservative_after_release_utc": "2026-11-06T13:30:00Z",
        "reported_metrics": {
            "nonfarm_payroll_monthly_change_persons_sa": "165000",
            "unemployment_rate_percent_sa": "4.1",
        },
        "pre_event_market_consensus_value": None,
        "source_original_bytes_archived": False,
    },
]
EXPECTED = {
    "schema": SCHEMA, "data_kind": KIND,
    "research_date_utc": "2026-11-06",
    "events": EVENTS,
}


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("DUPLICATE_FIELD")
        data[key] = value
    return data


def _as_of(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _baseline(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "casebook_sha256": None, "event_count": 0,
        "documentary_events_not_before_asof": [],
        "not_yet_released_by_asof": [],
        "currencies_with_documentary_events": [],
        "pair_count": 0, "pair_documentary_coverage": [],
        "pair_count_by_documentary_sides": {},
        "official_source_bytes_independently_authenticated": False,
        "historical_source_capture_time_independently_attested": False,
        "pre_event_market_consensus_verified": False,
        "economic_surprise_verified": False,
        "cross_currency_macro_instruments_comparable": False,
        "market_reaction_prices_verified": False,
        "calibrated_directional_model_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "market_surprise": None, "relative_currency_strength": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_nov6_documentary_events_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Audit two source-page transcriptions and 28 crosses, no ex-ante proof.

    `as_of_utc` is a simulation clock, not proof that the documents were
    actually captured at that time. An embargo date cannot backdate a receipt.
    """
    out = _baseline("CASEBOOK_OR_ASOF_INVALID")
    now = _as_of(as_of_utc)
    if (now is None or not isinstance(casebook_raw, bytes)
            or not 200 <= len(casebook_raw) <= MAX_BYTES):
        return out
    try:
        obj = json.loads(
            casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique_fields,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")),
        )
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        out["reason"] = "INVALID_JSON_OR_DUPLICATE_FIELDS"
        return out
    # An explicit fixed research snapshot prevents replacing a value or
    # publication date silently while keeping the same experimental schema.
    if obj != EXPECTED:
        out["reason"] = "CASEBOOK_DOES_NOT_MATCH_FROZEN_DOCUMENTARY_VALUES"
        return out
    if len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28:
        out["reason"] = "G8_UNIVERSE_INVALID"
        return out
    past, future = [], []
    for event in EVENTS:
        not_before = datetime.strptime(
            event["earliest_conservative_after_release_utc"],
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
        (past if now >= not_before else future).append(event["event_id"])
    visible = {event["currency"] for event in EVENTS if event["event_id"] in past}
    pairs = []
    counts = {0: 0, 1: 0, 2: 0}
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        sides = int(base in visible) + int(quote in visible)
        counts[sides] += 1
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "documented_event_sides_after_release": sides,
            "base_has_documented_event": base in visible,
            "quote_has_documented_event": quote in visible,
            "common_indicator_surprise_comparison_available": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "fx_bias": None, "trade_authorized": False,
        })
    out.update({
        "state": "LAB_POST_RELEASE_DOCUMENTARY_CONTEXT_NO_FX_FORECAST",
        "reason": "CONSENSUS_AND_SOURCE_CAPTURE_PIT_MISSING",
        "casebook_sha256": sha256(casebook_raw).hexdigest(),
        "event_count": len(EVENTS),
        "documentary_events_not_before_asof": past,
        "not_yet_released_by_asof": future,
        "currencies_with_documentary_events": sorted(visible),
        "pair_count": len(pairs), "pair_documentary_coverage": pairs,
        "pair_count_by_documentary_sides": {str(k): v for k, v in counts.items()},
    })
    return out


__all__ = ["SCHEMA", "KIND", "EVENTS", "EXPECTED",
           "inspect_g8_nov6_documentary_events_lab"]
