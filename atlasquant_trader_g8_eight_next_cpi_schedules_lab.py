"""Complete all eight G8 *next CPI calendar* currencies without inventing bias.

The three added sources cover different reference periods (Japan Oct monthly,
Swiss Nov monthly and New Zealand Q4 quarterly). Together with the existing
five-event casebook, they give two scheduled-date records per FX pair, not
comparable CPI measurements, consensus or validated directional predictions.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_oct2026_five_cpi_calendar_lab import (
    PINNED_CASEBOOK_SHA256 as PARENT_SHA256,
    inspect_g8_oct2026_five_cpi_calendar_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_EIGHT_NEXT_OFFICIAL_CPI_SCHEDULES_NO_FX_BIAS_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_G8_JPY_CHF_NZD_NEXT_CPI_SCHEDULES_LAB_V1"
PINNED_NEW_THREE_SHA256 = "8b8eb1e05cbb0583e8f6aab0dcd43a089a3feca279758d012f11ac7f843ec793"
ADMISSIBLE = datetime(2026, 11, 7, tzinfo=timezone.utc)
EXPECTED_THREE = (
    ("JPY_JAPAN_NATIONAL_OCT2026_CPI", "JPY", "2026-10", "MONTH", "MONTHLY",
     "2026-11-20", "NATIONAL_JAPAN_NOT_PRELIMINARY_TOKYO_CPI",
     "https://www.stat.go.jp/english/data/cpi/1582.htm"),
    ("CHF_SWISS_NOV2026_CPI", "CHF", "2026-11", "MONTH", "MONTHLY",
     "2026-12-02", "SWISS_NATIONAL_CPI_NOT_HICP",
     "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36353838/master"),
    ("NZD_NZ_DEC2026_QUARTER_CPI", "NZD", "2026-Q4", "QUARTER", "QUARTERLY",
     "2027-01-27", "NEW_ZEALAND_FULL_QUARTERLY_CPI_NOT_MONTHLY_SELECTED_PRICE_INDEX",
     "https://www.stats.govt.nz/indicators/consumers-price-index-cpi/"),
)
CASE_KEYS = frozenset((
    "schema", "kind", "research_calendar_date", "conservative_visible_after_utc",
    "source_original_bytes_archived", "independent_exact_source_consultation_instant_attested",
    "calendar_can_be_revised", "source_count", "events",
    "may_claim_release_occurred_after_schedule_passes",
    "may_compute_inflation_differential_from_unlike_reference_periods",
    "may_generate_fx_direction_or_accuracy",
))
EVENT_KEYS = frozenset((
    "event_id", "currency", "reference_period", "reference_period_type",
    "statistical_frequency", "scheduled_calendar_date", "statistical_scope",
    "source_url", "source_says_actual_published", "actual_headline_yoy_percent",
))
PARENT_VALID_STATES = frozenset((
    "LAB_OFFICIAL_SCHEDULE_NOT_VISIBLE_ASOF",
    "LAB_FIVE_CPI_SCHEDULE_DATES_ROUTED_NO_RELEASE_ACTUAL_OR_FX_BIAS",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "parent_casebook_sha256": None,
        "three_casebook_sha256": None,
        "visible_official_calendar_events": [], "visible_scheduled_currencies": [],
        "five_monthly_2026_oct_calendar_events": 0,
        "three_other_period_calendar_events": 0,
        "source_calendar_count": 0, "pair_count": 0,
        "pairs_with_two_currencies_in_schedule": 0,
        "pairs_with_upcoming_schedule": 0,
        "pairs_without_schedule": 0,
        "pair_rows": [],
        "observed_cpi_actual_by_currency": {},
        "surprise_to_consensus_by_currency": {},
        "relative_inflation_spreads": {},
        "ranked_currencies": [], "best_pair_of_day": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
        "calendar_may_change": True,
        "source_original_bytes_archived": False,
        "exact_source_consultation_instant_attested": False,
    }


def inspect_g8_eight_next_cpi_schedules_lab(
    *, five_calendar_casebook_raw: Any, three_calendar_casebook_raw: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    """Merge only vetted calendar metadata by currency, never CPI values."""
    out = _base("INVALID_CASEBOOK_TIME_PROVENANCE_OR_UNIVERSE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(three_calendar_casebook_raw, bytes)
            or not 1200 <= len(three_calendar_casebook_raw) <= 4500
            or sha256(three_calendar_casebook_raw).hexdigest() != PINNED_NEW_THREE_SHA256
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    parent = inspect_g8_oct2026_five_cpi_calendar_lab(
        five_calendar_casebook_raw, as_of_utc=now,
    )
    if (parent["state"] not in PARENT_VALID_STATES
            or parent["casebook_sha256"] != PARENT_SHA256
            or parent["pair_count"] != 28
            or {r["pair"] for r in parent["pair_rows"]} != set(OFFICIAL_PAIRS)):
        return out
    try:
        case = json.loads(
            three_calendar_casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if (not isinstance(case, dict) or case.keys() != CASE_KEYS
                or case["schema"] != CASE_SCHEMA
                or case["kind"] != "NEXT_OFFICIAL_CPI_RELEASE_CALENDAR_THREE_MISSING_G8_CURRENCIES_NOT_ACTUALS"
                or case["research_calendar_date"] != "2026-11-06"
                or case["conservative_visible_after_utc"] != "2026-11-07T00:00:00Z"
                or case["source_original_bytes_archived"] is not False
                or case["independent_exact_source_consultation_instant_attested"] is not False
                or case["calendar_can_be_revised"] is not True
                or type(case["source_count"]) is not int
                or case["source_count"] != 3
                or case["may_claim_release_occurred_after_schedule_passes"] is not False
                or case["may_compute_inflation_differential_from_unlike_reference_periods"] is not False
                or case["may_generate_fx_direction_or_accuracy"] is not False
                or not isinstance(case["events"], list)
                or len(case["events"]) != 3):
            return out
        for event, expected in zip(case["events"], EXPECTED_THREE):
            eid, currency, period, period_type, frequency, release_date, scope, url = expected
            if (not isinstance(event, dict) or event.keys() != EVENT_KEYS
                    or event["event_id"] != eid
                    or event["currency"] != currency
                    or event["reference_period"] != period
                    or event["reference_period_type"] != period_type
                    or event["statistical_frequency"] != frequency
                    or event["scheduled_calendar_date"] != release_date
                    or event["statistical_scope"] != scope
                    or event["source_url"] != url
                    or event["source_says_actual_published"] is not False
                    or event["actual_headline_yoy_percent"] is not None
                    or date.fromisoformat(event["scheduled_calendar_date"]).isoformat()
                    != release_date):
                return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError,
            AttributeError, OverflowError, RecursionError):
        return out

    visible = now >= ADMISSIBLE
    combined = []
    if visible:
        for event in parent["visible_calendar_events"]:
            combined.append({
                **event,
                "reference_period": event["reference_month"],
                "reference_period_type": "MONTH",
                "statistical_frequency": "MONTHLY",
                "statistical_scope": event["release_stage"],
                "evidence_cohort": "PARENT_OCT2026_FIVE_CALENDAR_DATES",
            })
        for eid, currency, period, period_type, frequency, release_date, scope, url in EXPECTED_THREE:
            combined.append({
                "event_id": eid, "currency": currency,
                "reference_period": period, "reference_period_type": period_type,
                "statistical_frequency": frequency,
                "scheduled_calendar_date": release_date, "statistical_scope": scope,
                "source_url": url,
                "calendar_status": (
                    "UPCOMING_SCHEDULED_RELEASE_NOT_VERIFIED"
                    if now.date() <= date.fromisoformat(release_date)
                    else "SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED"),
                "official_actual": None, "surprise": None,
                "evidence_cohort": "NEW_JPY_CHF_NZD_NEXT_CPI_SCHEDULES",
            })
    if (len(combined) not in (0, 8)
            or (visible and {e["currency"] for e in combined} != set(CURRENCIES))):
        return out

    combined.sort(key=lambda e: (e["scheduled_calendar_date"], e["currency"]))
    pair_rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        events = [{**e, "pair_currency_role": (
            "BASE" if e["currency"] == base else "QUOTE")}
            for e in combined if e["currency"] in (base, quote)]
        upcoming = [e for e in events if
                    e["calendar_status"] == "UPCOMING_SCHEDULED_RELEASE_NOT_VERIFIED"]
        next_date = upcoming[0]["scheduled_calendar_date"] if upcoming else None
        pair_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "calendar_events": events,
            "next_calendar_date": next_date,
            "next_calendar_events": [e for e in upcoming if
                                     e["scheduled_calendar_date"] == next_date],
            "calendar_currency_count": len(events),
            "comparable_cpi_reference_periods_verified": False,
            "currency_strength_score": None, "relative_macro_score": None,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "trade_authorized": False,
        })
    if (len(pair_rows) != 28 or any(r["calendar_currency_count"] !=
            (2 if visible else 0) for r in pair_rows)):
        return out

    out.update({
        "state": ("LAB_RESEARCH_NOT_VISIBLE_AT_ASOF" if not visible
                  else "LAB_8_CURRENCIES_28_PAIRS_TWO_CALENDAR_DATES_EACH_NO_FX_BIAS"),
        "reason": "CALENDAR_ONLY_MULTIPLE_REFERENCE_PERIODS_NOT_STATISTICAL_COMPARABILITY",
        "as_of_utc": now.isoformat(),
        "parent_casebook_sha256": PARENT_SHA256,
        "three_casebook_sha256": PINNED_NEW_THREE_SHA256,
        "visible_official_calendar_events": combined,
        "visible_scheduled_currencies": sorted(e["currency"] for e in combined),
        "five_monthly_2026_oct_calendar_events": 5 if visible else 0,
        "three_other_period_calendar_events": 3 if visible else 0,
        "source_calendar_count": 8 if visible else 0,
        "pair_count": 28,
        "pairs_with_two_currencies_in_schedule": 28 if visible else 0,
        "pairs_with_upcoming_schedule": sum(
            bool(r["next_calendar_events"]) for r in pair_rows),
        "pairs_without_schedule": 0 if visible else 28,
        "pair_rows": pair_rows,
    })
    return out


__all__ = ["SCHEMA", "PINNED_NEW_THREE_SHA256",
           "inspect_g8_eight_next_cpi_schedules_lab"]
