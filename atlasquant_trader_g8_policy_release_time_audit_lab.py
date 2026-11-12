"""LAB-only G8 central-bank announcement clock evidence audit.

Issuer-declared release times, publisher schedules, and patterns are different
levels of evidence. None proves the original historical first-available bytes.
In particular, this retrospective casebook cannot be used as historical P-I-T
data, even where the original announcement itself prints a release clock.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_RELEASE_TIME_AUDIT_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_RELEASE_TIME_EVIDENCE_LAB_V1"
CASEBOOK_SHA256 = "1a1a7680bca46ab42780e104fc9ac17c9a1c726541f57e0867484b0d2cfdee2f"
AVAILABLE_FROM_UTC = datetime(2026, 11, 9, tzinfo=timezone.utc)

CASE_FIELDS = frozenset((
    "schema", "kind", "research_calendar_date", "conservative_visible_after_utc",
    "original_issuer_response_bytes_archived_at_release",
    "independent_first_publication_instant_attested",
    "decision_values_pit_verified", "schedule_times_are_not_actual_release_proof",
    "events",
))
EVENT_FIELDS = frozenset((
    "currency", "decision_date", "issuer_local_claim_time", "iana_zone",
    "evidence_class", "issuer_source_url", "evidence_note",
))
ISSUERS = {
    "USD": ("www.federalreserve.gov", "America/New_York", "ISSUER_EXPLICIT_RELEASE_TIME", "2026-10-28"),
    "EUR": ("www.ecb.europa.eu", "Europe/Berlin", "ISSUER_SCHEDULED_TIME", "2026-10-29"),
    "GBP": ("www.bankofengland.co.uk", "Europe/London", "ISSUER_SCHEDULED_TIME", "2026-11-05"),
    "CAD": ("www.bankofcanada.ca", "America/Toronto", "ISSUER_SCHEDULED_TIME", "2026-10-28"),
    "AUD": ("www.rba.gov.au", "Australia/Sydney", "ISSUER_SCHEDULED_TIME", "2026-11-03"),
    "JPY": ("www.boj.or.jp", "Asia/Tokyo", "ISSUER_EXPLICIT_RELEASE_TIME", "2026-10-30"),
    "CHF": ("www.snb.ch", "Europe/Zurich", "ISSUER_PATTERN_ONLY", "2026-09-24"),
    "NZD": ("www.rbnz.govt.nz", "Pacific/Auckland", "ISSUER_RECORDED_UPDATE_TIME", "2026-10-28"),
}


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in items:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _issuer_url(raw: Any, host: str) -> bool:
    if not isinstance(raw, str):
        return False
    url = urlsplit(raw)
    return (url.scheme == "https" and url.hostname == host
            and bool(url.path) and not url.username and not url.password
            and url.port is None and not url.query and not url.fragment)


def _blocked(reason: str, state: str = "LAB_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "research_visible_after_utc": "2026-11-09T00:00:00Z",
        "casebook_sha256": None, "currency_count": 0, "pair_count": 0,
        "currency_rows": [], "pair_rows": [], "time_class_counts": {},
        "issuer_explicit_release_time_claim_count": 0,
        "independent_first_publication_instant_attested": False,
        "original_issuer_response_bytes_archived_at_release": False,
        "rates_historical_pit_verified": False,
        "decision_values_pit_verified": False,
        "historical_intraday_asof_proven": False,
        "historical_backtest_allowed": False,
        "decision_clock_can_feed_live_bias": False,
        "fx_bias": None, "validated_directional_accuracy": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False, "publishable": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_g8_policy_release_time_audit_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Classify eight official time claims without authorizing historical replay."""
    out = _blocked("INVALID_ISSUER_CASEBOOK_OR_CLOCK")
    if (not isinstance(casebook_raw, bytes)
            or not 2500 <= len(casebook_raw) <= 15000
            or sha256(casebook_raw).hexdigest() != CASEBOOK_SHA256
            or not isinstance(as_of_utc, datetime)
            or as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28):
        return out
    if as_of_utc.astimezone(timezone.utc) < AVAILABLE_FROM_UTC:
        return _blocked("RETROSPECTIVE_RESEARCH_NOT_VISIBLE_AT_EARLIER_ASOF",
                        "LAB_RESEARCH_NOT_VISIBLE_ASOF")
    try:
        book = json.loads(casebook_raw.decode("utf-8", "strict"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(book, dict) or book.keys() != CASE_FIELDS
                or book["schema"] != CASE_SCHEMA
                or book["kind"] != "MANUALLY_RESEARCHED_ISSUER_TIME_CLAIMS_NOT_IMMUTABLE_ORIGINAL_PIT_CAPTURE"
                or book["research_calendar_date"] != "2026-11-08"
                or book["conservative_visible_after_utc"] != "2026-11-09T00:00:00Z"
                or book["original_issuer_response_bytes_archived_at_release"] is not False
                or book["independent_first_publication_instant_attested"] is not False
                or book["decision_values_pit_verified"] is not False
                or book["schedule_times_are_not_actual_release_proof"] is not True
                or not isinstance(book["events"], list) or len(book["events"]) != 8):
            return out

        rows = []
        for event in book["events"]:
            if not isinstance(event, dict) or event.keys() != EVENT_FIELDS:
                return out
            currency = event["currency"]
            if not isinstance(currency, str) or currency not in ISSUERS:
                return out
            host, zone_name, expected_class, expected_date = ISSUERS[currency]
            if (event["decision_date"] != expected_date
                    or event["iana_zone"] != zone_name
                    or event["evidence_class"] != expected_class
                    or not _issuer_url(event["issuer_source_url"], host)
                    or not isinstance(event["evidence_note"], str)
                    or not 15 <= len(event["evidence_note"]) <= 500):
                return out
            claim = event["issuer_local_claim_time"]
            if not isinstance(claim, str) or len(claim) != 5 or claim[2] != ":":
                return out
            local_day = date.fromisoformat(expected_date)
            local_clock = time.fromisoformat(claim)
            local_instant = datetime.combine(local_day, local_clock, ZoneInfo(zone_name))
            utc_instant = local_instant.astimezone(timezone.utc)
            if local_instant.hour != int(claim[:2]) or local_instant.minute != int(claim[3:]):
                return out
            # Confirm no wall-clock discontinuity/ambiguous local time was silently used.
            if utc_instant.astimezone(ZoneInfo(zone_name)).replace(tzinfo=None) != local_instant.replace(tzinfo=None):
                return out
            rows.append({
                "currency": currency,
                "claimed_local_date": expected_date,
                "claimed_local_clock": claim,
                "iana_zone": zone_name,
                "claimed_utc_instant_for_research_only": utc_instant.isoformat().replace("+00:00", "Z"),
                "evidence_class": expected_class,
                "issuer_declares_release_time_in_original_decision_document": (
                    expected_class == "ISSUER_EXPLICIT_RELEASE_TIME"),
                "actual_release_instant_independently_captured": False,
                "original_announcement_bytes_archived": False,
                "historical_asof_safe": False,
                "can_retroactively_use_as_market_information": False,
                "source_url": event["issuer_source_url"],
                "evidence_note": event["evidence_note"],
                "D1": "AGUARDAR", "W1": "AGUARDAR",
            })
        by_currency = {row["currency"]: row for row in rows}
        if len(by_currency) != 8 or set(by_currency) != set(CURRENCIES):
            return out
        pairs = []
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            pairs.append({
                "pair": pair, "base": base, "quote": quote,
                "both_issuers_have_explicit_release_clock_claims": (
                    by_currency[base]["issuer_declares_release_time_in_original_decision_document"]
                    and by_currency[quote]["issuer_declares_release_time_in_original_decision_document"]),
                "historical_asof_safe": False, "D1": "AGUARDAR", "W1": "AGUARDAR",
                "trade_authorized": False,
            })
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, OverflowError,
            ZoneInfoNotFoundError, RecursionError):
        return out

    counts = Counter(row["evidence_class"] for row in rows)
    out.update({
        "state": "LAB_EIGHT_ISSUER_CLOCK_CLAIMS_CLASSIFIED_NOT_PIT_ATTESTED",
        "reason": "ORIGINAL_FIRST_PUBLICATION_BYTES_UNAVAILABLE_AND_SCHEDULE_NOT_ACTUAL",
        "casebook_sha256": CASEBOOK_SHA256,
        "currency_count": 8, "pair_count": len(pairs),
        "currency_rows": sorted(rows, key=lambda row: row["currency"]),
        "pair_rows": pairs,
        "time_class_counts": dict(sorted(counts.items())),
        "issuer_explicit_release_time_claim_count": counts["ISSUER_EXPLICIT_RELEASE_TIME"],
    })
    return out


__all__ = ["SCHEMA", "CASEBOOK_SHA256", "inspect_g8_policy_release_time_audit_lab"]
