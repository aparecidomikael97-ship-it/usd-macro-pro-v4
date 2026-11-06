"""Route five official October CPI *calendar dates* to the 28 G8 FX crosses.

A scheduled date is neither an observed CPI number nor proof a release happened.
The research casebook is an offline, manually transcribed snapshot, so its
source HTML and original consultation instant cannot be independently attested.
This remains non-operational research, with no FX direction or live radar.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_ROUTING_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_G8_OCT2026_FIVE_OFFICIAL_NEXT_CPI_CALENDAR_LAB_V1"
PINNED_CASEBOOK_SHA256 = "9874b5160b0d5f54c7a538fdcebe24626315100df87331bca76cfc11812dc62a"
RESEARCH_AVAILABLE = datetime(2026, 11, 7, tzinfo=timezone.utc)
UNSCHEDULED_IN_THIS_COHORT = frozenset(("CHF", "JPY", "NZD"))
EXPECTED_EVENTS = (
    ("USD_BLS_OCT2026_CPI_FIRST_RELEASE", "USD", "2026-11-10",
     "FIRST_US_CPI_U_ALL_ITEMS_RELEASE_NOT_CURRENT_ACTUAL",
     "https://www.bls.gov/schedule/2026/11_sched_list.htm"),
    ("CAD_STATCAN_OCT2026_CPI_FIRST_RELEASE", "CAD", "2026-11-16",
     "FIRST_CANADA_CPI_ALL_ITEMS_RELEASE_NOT_CURRENT_ACTUAL",
     "https://www150.statcan.gc.ca/n1/daily-quotidien/261019/dq261019a-eng.htm"),
    ("EUR_EUROSTAT_OCT2026_HICP_FULL_RELEASE", "EUR", "2026-11-18",
     "FULL_EA21_HICP_AFTER_FLASH_NOT_CURRENT_ACTUAL",
     "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-04112026-ap"),
    ("GBP_ONS_OCT2026_CPI_FIRST_RELEASE", "GBP", "2026-11-18",
     "FIRST_UK_CPI_ALL_ITEMS_NOT_CPIH_RELEASE_NOT_CURRENT_ACTUAL",
     "https://www.ons.gov.uk/releases/consumerpriceinflationukoctober2026"),
    ("AUD_ABS_OCT2026_CPI_FIRST_RELEASE", "AUD", "2026-11-25",
     "FIRST_AU_ALL_GROUPS_CPI_RELEASE_NOT_CURRENT_ACTUAL",
     "https://www.abs.gov.au/release-calendar/future-releases/202611/rcc_economy"),
)
EVENT_KEYS = frozenset((
    "event_id", "currency", "scheduled_calendar_date", "reference_month",
    "release_stage", "source_url", "actual_value_published_in_casebook",
    "actual_headline_yoy_percent",
))
CASE_KEYS = frozenset((
    "schema", "kind", "research_calendar_date",
    "conservative_research_available_utc", "reference_month",
    "source_original_bytes_archived", "exact_calendar_consultation_instant_attested",
    "schedule_may_change", "post_schedule_actual_is_not_in_this_casebook",
    "sources_checked", "events",
    "currencies_without_an_oct2026_release_scheduled_in_this_casebook",
    "may_claim_any_event_has_released_new_actual", "may_calculate_surprise",
    "may_generate_currency_strength_or_fx_bias",
))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "casebook_sha256": None,
        "official_sources_checked": 0, "visible_calendar_events": [],
        "scheduled_currency_count": 0, "pair_count": 0,
        "pairs_with_calendar_metadata": 0,
        "pairs_with_two_calendar_currencies": 0,
        "pairs_with_one_calendar_currency": 0,
        "pairs_without_calendar_metadata": 0,
        "pairs_with_an_upcoming_calendar_event": 0,
        "pair_rows": [], "ranked_currencies": [],
        "best_pair_of_day": None, "latest_official_cpi_actual_by_currency": {},
        "release_surprises": {}, "currency_strength_score": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0, "validated_accuracy": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "new_cost_brl": 0,
        "calendar_may_change": True,
        "original_source_bytes_archived": False,
        "source_consultation_instant_independently_attested": False,
    }


def inspect_g8_oct2026_five_cpi_calendar_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Show source-calendar metadata only after conservative research gate."""
    out = _base("INVALID_CALENDAR_SNAPSHOT_CLOCK_OR_UNIVERSE")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(casebook_raw, bytes)
            or not 1800 <= len(casebook_raw) <= 6500
            or sha256(casebook_raw).hexdigest() != PINNED_CASEBOOK_SHA256
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28
            or len(set(OFFICIAL_PAIRS)) != 28):
        return out

    try:
        case = json.loads(
            casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        if (not isinstance(case, dict) or case.keys() != CASE_KEYS
                or case["schema"] != CASE_SCHEMA
                or case["kind"] != "PRIMARY_SOURCE_RELEASE_CALENDAR_METADATA_NOT_RELEASED_CPI_DATA"
                or case["research_calendar_date"] != "2026-11-06"
                or case["conservative_research_available_utc"] != "2026-11-07T00:00:00Z"
                or case["reference_month"] != "2026-10"
                or case["source_original_bytes_archived"] is not False
                or case["exact_calendar_consultation_instant_attested"] is not False
                or case["schedule_may_change"] is not True
                or case["post_schedule_actual_is_not_in_this_casebook"] is not True
                or type(case["sources_checked"]) is not int
                or case["sources_checked"] != 5
                or frozenset(case["currencies_without_an_oct2026_release_scheduled_in_this_casebook"])
                != UNSCHEDULED_IN_THIS_COHORT
                or case["may_claim_any_event_has_released_new_actual"] is not False
                or case["may_calculate_surprise"] is not False
                or case["may_generate_currency_strength_or_fx_bias"] is not False
                or not isinstance(case["events"], list)
                or len(case["events"]) != len(EXPECTED_EVENTS)):
            return out
        for row, (event_id, currency, release_date, stage, url) in zip(
            case["events"], EXPECTED_EVENTS,
        ):
            if (not isinstance(row, dict) or row.keys() != EVENT_KEYS
                    or row["event_id"] != event_id
                    or row["currency"] != currency
                    or row["scheduled_calendar_date"] != release_date
                    or row["release_stage"] != stage
                    or row["source_url"] != url
                    or row["reference_month"] != "2026-10"
                    or row["actual_value_published_in_casebook"] is not False
                    or row["actual_headline_yoy_percent"] is not None
                    or date.fromisoformat(row["scheduled_calendar_date"]).isoformat()
                    != release_date):
                return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError,
            AttributeError, OverflowError, RecursionError):
        return out

    now = as_of_utc.astimezone(timezone.utc)
    rows = []
    visible_events = []
    if now >= RESEARCH_AVAILABLE:
        visible_events = [{
            "event_id": event_id, "currency": currency,
            "scheduled_calendar_date": release_date, "reference_month": "2026-10",
            "release_stage": stage, "source_url": url,
            "calendar_status": (
                "UPCOMING_SCHEDULED_RELEASE_NOT_VERIFIED"
                if now.date() <= date.fromisoformat(release_date)
                else "SCHEDULE_DATE_PASSED_ACTUAL_UNVERIFIED"),
            "official_actual": None, "surprise": None,
        } for event_id, currency, release_date, stage, url in EXPECTED_EVENTS]

    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        events = [{**evt, "pair_currency_role": (
            "BASE" if evt["currency"] == base else "QUOTE")}
            for evt in visible_events if evt["currency"] in (base, quote)]
        events.sort(key=lambda e: (e["scheduled_calendar_date"], e["currency"]))
        upcoming = [evt for evt in events if
                    evt["calendar_status"] == "UPCOMING_SCHEDULED_RELEASE_NOT_VERIFIED"]
        next_date = upcoming[0]["scheduled_calendar_date"] if upcoming else None
        next_events = [evt for evt in upcoming if
                       evt["scheduled_calendar_date"] == next_date]
        rows.append({
            "pair": pair, "base": base, "quote": quote,
            "calendar_events": events,
            "next_calendar_date": next_date,
            "next_calendar_events": next_events,
            "scheduled_calendar_currency_count": len(events),
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "relative_macro_score": None, "currency_strength_score": None,
            "market_surprise": None, "trade_authorized": False,
        })

    counts = [sum(row["scheduled_calendar_currency_count"] == n for row in rows)
              for n in (0, 1, 2)]
    if (len(rows) != 28 or (counts not in ([3, 15, 10], [28, 0, 0]))
            or (now >= RESEARCH_AVAILABLE and len(visible_events) != 5)):
        return out
    out.update({
        "state": ("LAB_OFFICIAL_SCHEDULE_NOT_VISIBLE_ASOF" if not visible_events
                  else "LAB_FIVE_CPI_SCHEDULE_DATES_ROUTED_NO_RELEASE_ACTUAL_OR_FX_BIAS"),
        "reason": "SCHEDULE_ONLY_NOT_CPI_ACTUAL_NOR_EVENT_SURPRISE",
        "as_of_utc": now.isoformat(),
        "casebook_sha256": PINNED_CASEBOOK_SHA256,
        "official_sources_checked": 5,
        "visible_calendar_events": visible_events,
        "scheduled_currency_count": len(visible_events),
        "pair_count": len(rows),
        "pairs_with_calendar_metadata": counts[1] + counts[2],
        "pairs_with_two_calendar_currencies": counts[2],
        "pairs_with_one_calendar_currency": counts[1],
        "pairs_without_calendar_metadata": counts[0],
        "pairs_with_an_upcoming_calendar_event": sum(
            bool(row["next_calendar_events"]) for row in rows),
        "pair_rows": rows,
    })
    return out


__all__ = ["SCHEMA", "PINNED_CASEBOOK_SHA256",
           "inspect_g8_oct2026_five_cpi_calendar_lab"]
