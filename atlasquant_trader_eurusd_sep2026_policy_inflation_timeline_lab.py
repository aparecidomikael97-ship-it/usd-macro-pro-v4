"""Offline, retrospective policy + CPI release chronology for EUR/USD.

Joining OFFICIAL published-page references does not authenticate original
historical vintages, policy expectations, surprise, or a directional FX bias.
Decision date != effective date. No HTTP, orders, scheduler, or publishing.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_eurusd_sep2026_official_headline_lab import (
    inspect_eurusd_sep2026_official_headline_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEPOCT2026_POLICY_CPI_TIMELINE_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_EURUSD_SEPOCT2026_POLICY_DECISIONS_DOCUMENTARY_LAB_V1"
CASE_KIND = "OFFICIAL_POLICY_RELEASE_PAGE_REFERENCES_MANUALLY_TRANSCRIBED_NOT_PIT_RECEIPTS"
PINNED_POLICY_SHA256 = "75559559c42a2bf3f8fb9dd2289691ba18ec97d93afb107f668850ca13b8ae82"
EXPECTED_EVENTS = [
    ("EUR", "ECB_GOVERNING_COUNCIL",
     "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260910~314e508016.en.html",
     "2026-09-10", "2026-09-11T00:00:00Z", "DEPOSIT_FACILITY_RATE",
     "RAISE_25_BP", 25, 2.5, None, None, "2026-09-16"),
    ("USD", "US_FOMC",
     "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
     "2026-09-16", "2026-09-17T00:00:00Z", "FEDERAL_FUNDS_TARGET_RANGE",
     "RAISE_25_BP", 25, None, 3.75, 4.0, "2026-09-17"),
    ("USD", "US_FOMC",
     "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm",
     "2026-10-28", "2026-10-29T00:00:00Z", "FEDERAL_FUNDS_TARGET_RANGE",
     "HOLD", 0, None, 3.75, 4.0, "2026-09-17"),
    ("EUR", "ECB_GOVERNING_COUNCIL",
     "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html",
     "2026-10-29", "2026-10-30T00:00:00Z", "DEPOSIT_FACILITY_RATE",
     "HOLD", 0, 2.5, None, None, "2026-09-16"),
]
EVENT_KEYS = (
    "currency", "authority", "document_url", "decision_date",
    "conservative_public_from_utc", "instrument", "decision_action",
    "change_basis_points", "level_percent", "range_lower_percent",
    "range_upper_percent", "current_level_effective_from",
)
NOT_VERIFIED = frozenset((
    "MARKET_SURPRISE_VS_PRE_MEETING_EXPECTATIONS",
    "HISTORICAL_ORIGINAL_PAGE_BYTES_AND_INDEPENDENT_RELEASE_INSTANT",
    "ECB_DEPOSIT_FACILITY_AND_FOMC_TARGET_RANGE_SAME_INSTRUMENT",
    "JURISDICTIONS_CPI_HEADLINES_SAME_METHODS",
    "FX_SPOT_REACTION_TO_ANNOUNCEMENT",
    "DIRECTIONAL_EURUSD_FORECAST_OR_ACCURACY",
))


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "policy_casebook_sha256": None,
        "known_policy_announcements": [],
        "latest_effective_policy_level_by_currency": {},
        "inflation_visible_currencies": [],
        "inflation_headline_context": [],
        "inflation_and_policy_context_documentarily_present_for_both": False,
        "historical_original_policy_pages_attested": False,
        "historical_original_inflation_pages_attested": False,
        "independent_exact_release_times_attested": False,
        "pre_meeting_expectations_verified": False,
        "pre_cpi_consensus_verified": False,
        "policy_rate_instruments_directly_comparable": False,
        "cross_currency_rate_spread_bps": None,
        "cpi_surprise_percent": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "validated_forward_prediction_count": 0,
        "validated_accuracy": None, "can_feed_live_radar": False,
        "trade_authorized": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_eurusd_sep2026_policy_inflation_timeline_lab(
    policy_casebook_raw: Any, *, inflation_casebook_raw: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Respect documentary release gates and separate announced/effective rates."""
    out = _base("INVALID_POLICY_OR_INFLATION_DOCUMENTARY_CONTEXT_OR_CLOCK")
    if (not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or not isinstance(policy_casebook_raw, bytes)
            or not 1100 <= len(policy_casebook_raw) <= 12000
            or sha256(policy_casebook_raw).hexdigest() != PINNED_POLICY_SHA256):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    inflation = inspect_eurusd_sep2026_official_headline_lab(
        inflation_casebook_raw, as_of_utc=now,
    )
    if inflation["state"] not in (
        "LAB_INCOMPLETE_SEP2026_DOCUMENTARY_CONTEXT_ONLY",
        "LAB_SAME_SEP2026_PERIOD_DOCUMENTARY_HEADLINE_CONTEXT_ONLY",
    ):
        return out
    try:
        case = json.loads(
            policy_casebook_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
        events = case["decisions"]
        if (case["schema"] != CASE_SCHEMA or case["kind"] != CASE_KIND
                or case["research_date"] != "2026-11-06"
                or case["official_http_original_release_bytes_archived"] is not False
                or case["market_consensus_before_each_meeting_verified"] is not False
                or case["same_instrument_policy_spread_calculable"] is not False
                or case["trade_authorized"] is not False
                or frozenset(case["not_verified"]) != NOT_VERIFIED
                or not isinstance(events, list)
                or len(events) != len(EXPECTED_EVENTS)):
            return out
        for event, expected in zip(events, EXPECTED_EVENTS):
            if tuple(event[k] for k in EVENT_KEYS) != expected:
                return out
            if (type(event["change_basis_points"]) is not int
                    or any(type(event[k]) is not float
                           for k in ("level_percent", "range_lower_percent",
                                     "range_upper_percent") if event[k] is not None)):
                return out
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError,
            RecursionError, OverflowError):
        return out

    published_events: list[dict[str, Any]] = []
    effective_levels: dict[str, dict[str, Any]] = {}
    for event in events:
        if now < datetime.fromisoformat(event["conservative_public_from_utc"].replace(
                "Z", "+00:00")):
            continue
        effective = date.fromisoformat(event["current_level_effective_from"]) <= now.date()
        view = {
            "currency": event["currency"],
            "decision_date": event["decision_date"],
            "source_url": event["document_url"],
            "instrument": event["instrument"],
            "decision_action": event["decision_action"],
            "change_basis_points": event["change_basis_points"],
            "announced_rate_or_range_in_effect_asof": effective,
            "level_percent": event["level_percent"],
            "range_lower_percent": event["range_lower_percent"],
            "range_upper_percent": event["range_upper_percent"],
        }
        published_events.append(view)
        if effective:
            effective_levels[event["currency"]] = {
                "source_decision_date": event["decision_date"],
                "instrument": event["instrument"],
                "level_percent": event["level_percent"],
                "range_lower_percent": event["range_lower_percent"],
                "range_upper_percent": event["range_upper_percent"],
            }

    both = (set(effective_levels) == {"EUR", "USD"}
            and inflation["same_observation_month_available_in_both_releases"])
    out.update({
        "state": ("LAB_BOTH_POLICY_AND_SEP_CPI_DOCUMENTARY_CONTEXT_ONLY"
                  if both else "LAB_PARTIAL_DOCUMENTARY_CONTEXT_NO_DIRECTION"),
        "reason": "POLICY_ANNOUNCEMENTS_AND_CPI_LEVELS_NOT_EX_ANTE_SURPRISE_OR_FX_DIRECTION",
        "policy_casebook_sha256": sha256(policy_casebook_raw).hexdigest(),
        "known_policy_announcements": published_events,
        "latest_effective_policy_level_by_currency": effective_levels,
        "inflation_visible_currencies": inflation["visible_currencies"],
        "inflation_headline_context": inflation["visible_press_release_context"],
        "inflation_and_policy_context_documentarily_present_for_both": both,
    })
    return out


__all__ = ["SCHEMA", "PINNED_POLICY_SHA256",
           "inspect_eurusd_sep2026_policy_inflation_timeline_lab"]
