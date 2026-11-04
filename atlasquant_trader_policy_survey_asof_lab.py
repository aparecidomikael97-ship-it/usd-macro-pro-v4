"""Strict documentary as-of audit of official central-bank policy surveys.

This is not a trading strategy, policy-rate consensus API, forecast, or proof
of independent point-in-time capture. Source data are caller-supplied and
validated structurally; the bundled documentary case is manually transcribed.
No network, scheduler, background worker, external dependencies or orders.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_TRADER_POLICY_SURVEY_ASOF_LAB_V1"
BOOK_SCHEMA = "ATLASQUANT_TRADER_DOCUMENTARY_POLICY_SURVEYS_20261103_V1"
FIELDS = frozenset((
    "record_id", "currency", "authority", "publication_state",
    "source_url", "collected_through", "published_on",
    "scheduled_publication_on", "target_event_on", "expectation_kind",
    "median_pct", "p25_pct", "p75_pct", "respondents",
    "documentary_note",
))
AUTHORITY_HOSTS = {
    ("GBP", "BANK_OF_ENGLAND"): "www.bankofengland.co.uk",
    ("EUR", "ECB"): "www.ecb.europa.eu",
    ("USD", "NY_FED"): "www.newyorkfed.org",
}
KINDS = ("RESULT_PUBLISHED", "TIMETABLE_ONLY", "RESULT_NOT_OBSERVED")
EXPECTED = "SURVEY_MEDIAN_MODAL_POST_MEETING_POLICY_RATE"
STALE_AFTER_DAYS = 30  # Conservative LAB freshness policy; not validated.


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return None
    return day if day.isoformat() == value else None


def _rate(value: Any) -> Decimal | None:
    # Decimal string only: floats and booleans cannot silently round surveys.
    if not isinstance(value, str) or len(value) > 12:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() and Decimal("-5") <= parsed <= 30 else None


def _valid_source(url: Any, currency: str, authority: str) -> bool:
    if not isinstance(url, str) or len(url) > 500:
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname == AUTHORITY_HOSTS[(currency, authority)]
                and p.username is None and p.password is None and p.port in (None, 443)
                and bool(p.path) and not p.fragment and not p.query)
    except (KeyError, ValueError):
        return False


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED",
        "reason": reason, "records": [], "currency_coverage": [],
        "cross_currency_policy_bias": None, "policy_probability": None,
        "accuracy_90_proven": False, "independent_historical_receipt": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def audit_official_policy_surveys_lab(book: Any, *, evaluated_at: datetime) -> dict[str, Any]:
    """Assess *documentary* pre-event eligibility without inferring FX direction.

    Date-only publication is treated as available no earlier than the next
    UTC calendar day. Same-day target decisions are blocked regardless of
    their unknown release hour. All statuses remain read-only LAB claims.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    now = evaluated_at.astimezone(timezone.utc)
    if not isinstance(book, Mapping) or set(book) != {"schema", "records"}:
        return _reject("Book must have exact schema and records fields")
    if book["schema"] != BOOK_SCHEMA or not isinstance(book["records"], list):
        return _reject("Unknown documentary book schema")
    if not 1 <= len(book["records"]) <= 40:
        return _reject("One to forty survey records required")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in book["records"]:
        if not isinstance(raw, Mapping) or set(raw) != FIELDS:
            return _reject("Survey record has missing or extra fields")
        rid = raw["record_id"]
        if (not isinstance(rid, str) or not 3 <= len(rid) <= 100
                or not all(c.isupper() or c.isdigit() or c == "_" for c in rid)
                or rid in seen):
            return _reject("Duplicate or invalid survey record identity")
        seen.add(rid)
        currency, authority = raw["currency"], raw["authority"]
        if (not isinstance(currency, str) or not isinstance(authority, str)
                or (currency, authority) not in AUTHORITY_HOSTS
                or not _valid_source(raw["source_url"], currency, authority)):
            return _reject("Authority, currency or primary-source URL mismatch")
        state = raw["publication_state"]
        if state not in KINDS:
            return _reject("Unknown publication state")
        event = _day(raw["target_event_on"])
        collected = _day(raw["collected_through"])
        published = _day(raw["published_on"])
        scheduled = _day(raw["scheduled_publication_on"])
        if event is None:
            return _reject("Target event needs ISO calendar date")
        if (collected is None and raw["collected_through"] is not None
                or published is None and raw["published_on"] is not None
                or scheduled is None and raw["scheduled_publication_on"] is not None):
            return _reject("Malformed survey date")
        if (not isinstance(raw["documentary_note"], str)
                or not 10 <= len(raw["documentary_note"].strip()) <= 400):
            return _reject("Documentary note required")
        if state == "RESULT_PUBLISHED":
            if (published is None or collected is None or scheduled is not None
                    or collected > published or raw["expectation_kind"] != EXPECTED
                    or type(raw["respondents"]) is not int
                    or not 1 <= raw["respondents"] <= 10000):
                return _reject("Published survey needs consistent dated provenance")
            rates = tuple(_rate(raw[field]) for field in ("p25_pct", "median_pct", "p75_pct"))
            if any(rate is None for rate in rates) or not rates[0] <= rates[1] <= rates[2]:
                return _reject("Policy-rate survey quantiles malformed or unordered")
            # Examine leakage BEFORE target-passed status, to keep the reason visible.
            if published >= event:
                decision = "POST_EVENT_LEAK_BLOCKED"
            elif (now.date() <= published):
                decision = "NOT_YET_AVAILABLE_CONSERVATIVE_UTC"
            elif now.date() >= event:
                decision = "TARGET_EVENT_DAY_OR_PASSED"
            elif (now.date() - published).days > STALE_AFTER_DAYS:
                decision = "PRE_EVENT_BUT_STALE"
            else:
                decision = "PRE_EVENT_DOCUMENTARY_CURRENT"
            age = (now.date() - published).days if now.date() > published else None
            med = raw["median_pct"] if decision in (
                "PRE_EVENT_DOCUMENTARY_CURRENT", "PRE_EVENT_BUT_STALE"
            ) else None
        else:
            if (published is not None or collected is not None
                    or raw["expectation_kind"] is not None
                    or any(raw[k] is not None for k in (
                        "median_pct", "p25_pct", "p75_pct", "respondents"))):
                return _reject("Schedule or unobserved result cannot carry survey values")
            if state == "TIMETABLE_ONLY" and scheduled is None:
                return _reject("Timetable needs a date, not a fabricated published result")
            if state == "RESULT_NOT_OBSERVED" and scheduled is not None:
                return _reject("Unobserved result cannot assert scheduled publication")
            decision = ("TIMETABLE_ONLY_NOT_ATTESTED"
                        if state == "TIMETABLE_ONLY" else "RESULT_NOT_PUBLICLY_OBSERVED")
            med, age = None, None
        result.append({
            "record_id": rid, "currency": currency, "authority": authority,
            "publication_state": state, "status": decision,
            "target_event_on": event.isoformat(),
            "published_on": published.isoformat() if published else None,
            "scheduled_publication_on": scheduled.isoformat() if scheduled else None,
            "asof_utc": now.isoformat(),
            "document_age_days": age,
            "pre_event_document_available": decision in (
                "PRE_EVENT_DOCUMENTARY_CURRENT", "PRE_EVENT_BUT_STALE"),
            "fresh_under_lab_policy": decision == "PRE_EVENT_DOCUMENTARY_CURRENT",
            "documentary_median_policy_rate_pct": med,
            "source_url": raw["source_url"],
            "historical_capture_receipt_verified": False,
            "cross_currency_signal_authorized": False,
        })
    covered = sorted({row["currency"] for row in result
                      if row["status"] == "PRE_EVENT_DOCUMENTARY_CURRENT"})
    return {
        **_reject(""), "state": "LAB_DOCUMENTARY_POLICY_AVAILABILITY_ONLY",
        "reason": ("Publication-date audit; no independent archival receipt, "
                   "same-horizon peer path or calibrated FX directional model"),
        "evaluated_at_utc": now.isoformat(),
        "stale_after_days_lab_policy": STALE_AFTER_DAYS,
        "date_only_publication_eligible_next_utc_day": True,
        "records": result, "currency_coverage": covered,
    }


__all__ = [
    "SCHEMA", "BOOK_SCHEMA", "STALE_AFTER_DAYS",
    "audit_official_policy_surveys_lab",
]
