"""LAB-only date-level policy decision cadence audit for the eight G8 currencies.

Manual official-publisher calendar transcription is SHA-pinned but not an
archived point-in-time publication record. Scheduled meetings must NEVER
become actual decisions, rate values, currency strength, or trade signals.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_macro_asof_lab import (
    FRESH_DAYS, OBSERVATION_AGE_LIMIT_DAYS,
)

SCHEMA = "ATLASQUANT_TRADER_G8_POLICY_SCHEDULE_AGE_AUDIT_LAB_V1"
CASE_SCHEMA = "ATLASQUANT_TRADER_G8_EIGHT_POLICY_DECISION_CALENDAR_LAB_V1"
CASEBOOK_SHA256 = "4352df6faf0cca27bf99edd7ebc0fcd50833c63413f50b164bd64a5fdda9d10f"
AVAILABLE_FROM_UTC = datetime(2026, 11, 9, tzinfo=timezone.utc)
CASE_FIELDS = frozenset((
    "schema", "kind", "research_calendar_date", "conservative_visible_after_utc",
    "original_publisher_html_archived", "exact_consultation_instant_independently_attested",
    "announcement_instant_independently_attested", "schedules_can_change",
    "future_decisions_are_not_actuals", "events",
))
EVENT_FIELDS = frozenset((
    "currency", "instrument", "previous_announced_decision_date",
    "next_scheduled_decision_date", "previous_source_url", "calendar_source_url",
))
ISSUERS = {
    "USD": "www.federalreserve.gov", "EUR": "www.ecb.europa.eu",
    "GBP": "www.bankofengland.co.uk", "CAD": "www.bankofcanada.ca",
    "AUD": "www.rba.gov.au", "JPY": "www.boj.or.jp",
    "CHF": "www.snb.ch", "NZD": "www.rbnz.govt.nz",
}


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "as_of_utc": None, "casebook_sha256": None,
        "currency_count": 0, "pair_count": 0, "currency_rows": [], "pair_rows": [],
        "currencies_with_schedule_age_gap": [], "max_decision_gap_days": None,
        "minimum_published_age_margin_days": None,
        "rate_values_from_issuers_verified": False,
        "historical_rate_vintages_verified": False,
        "original_publisher_bytes_archived": False,
        "exact_research_consultation_instant_attested": False,
        "exact_original_announcement_instant_attested": False,
        "future_scheduled_decisions_occurred": False,
        "unplanned_decisions_are_excluded": False,
        "real_broker_prices_verified": False,
        "policy_rates_cross_currency_comparable": False,
        "validated_directional_accuracy": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    out = {}
    for k, v in items:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def _url_from_issuer(raw: Any, issuer: str) -> bool:
    if not isinstance(raw, str):
        return False
    parsed = urlsplit(raw)
    return (parsed.scheme == "https" and parsed.hostname == issuer
            and not parsed.username and not parsed.password and not parsed.query
            and not parsed.fragment and parsed.port is None and bool(parsed.path))


def inspect_g8_policy_schedule_age_audit_lab(
    casebook_raw: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Compare announcement-date gaps to LAB age ceilings, not to market bias."""
    out = _blocked("INVALID_CASEBOOK_SOURCE_OR_CLOCK")
    if (not isinstance(casebook_raw, bytes)
            or not 2000 <= len(casebook_raw) <= 10000
            or sha256(casebook_raw).hexdigest() != CASEBOOK_SHA256
            or not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None
            or as_of_utc.utcoffset() is None
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28):
        return out
    now = as_of_utc.astimezone(timezone.utc)
    if now < AVAILABLE_FROM_UTC:
        out["state"] = "LAB_RESEARCH_NOT_VISIBLE_ASOF"
        out["reason"] = "CALENDAR_RESEARCH_PRECEDES_ASOF_PROOF"
        return out
    try:
        case = json.loads(casebook_raw.decode("utf-8", "strict"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if (not isinstance(case, dict) or case.keys() != CASE_FIELDS
                or case["schema"] != CASE_SCHEMA
                or case["kind"] != "OFFICIAL_POLICY_DECISION_DATE_RESEARCH_NOT_RATE_OR_VERIFIED_VINTAGE"
                or case["research_calendar_date"] != "2026-11-08"
                or case["conservative_visible_after_utc"] != "2026-11-09T00:00:00Z"
                or case["original_publisher_html_archived"] is not False
                or case["exact_consultation_instant_independently_attested"] is not False
                or case["announcement_instant_independently_attested"] is not False
                or case["schedules_can_change"] is not True
                or case["future_decisions_are_not_actuals"] is not True
                or not isinstance(case["events"], list)
                or len(case["events"]) != 8):
            return out
        entries = []
        for e in case["events"]:
            if not isinstance(e, dict) or e.keys() != EVENT_FIELDS:
                return out
            c = e["currency"]
            if (not isinstance(c, str) or c not in ISSUERS
                    or not isinstance(e["instrument"], str)
                    or len(e["instrument"]) < 4
                    or not _url_from_issuer(e["previous_source_url"], ISSUERS[c])
                    or not _url_from_issuer(e["calendar_source_url"], ISSUERS[c])):
                return out
            last = date.fromisoformat(e["previous_announced_decision_date"])
            future = date.fromisoformat(e["next_scheduled_decision_date"])
            if (not last < date(2026, 11, 9) < future
                    or last.isoformat() != e["previous_announced_decision_date"]
                    or future.isoformat() != e["next_scheduled_decision_date"]):
                return out
            days = (future - timedelta(days=1) - last).days
            # The legacy policy-rate schema carries a YYYY-MM competence.
            # Its month-end age is only a coarse backup, *not* the decision day.
            month_end = date(last.year, last.month, monthrange(last.year, last.month)[1])
            competence_age = (future - timedelta(days=1) - month_end).days
            max_published_age = FRESH_DAYS["POLICY_RATE"]
            max_competence_age = OBSERVATION_AGE_LIMIT_DAYS[("POLICY_RATE", "MONTHLY")]
            if (type(max_published_age) is not int or max_published_age <= 0
                    or type(max_competence_age) is not int or max_competence_age <= 0):
                return out
            entries.append({
                "currency": c, "instrument": e["instrument"],
                "prior_decision_calendar_date_claim": last.isoformat(),
                "next_scheduled_decision_calendar_date_claim": future.isoformat(),
                "prior_to_next_announcement_eve_days": days,
                "legacy_monthly_period_end_date": month_end.isoformat(),
                "legacy_monthly_period_age_at_next_eve_days": competence_age,
                "publication_age_ceiling_days": max_published_age,
                "observation_month_age_ceiling_days": max_competence_age,
                "published_age_margin_days": max_published_age - days,
                "observation_month_age_margin_days": max_competence_age - competence_age,
                "both_ceilings_cover_next_scheduled_decision_eve": (
                    days <= max_published_age and competence_age <= max_competence_age),
                "source_urls_are_manual_claims_not_archived_raw": True,
                "future_schedule_is_not_an_announced_decision": True,
                "excluded_non_decision_events_from_rate_calendar": (
                    ["FINANCIAL_STABILITY_REPORT"] if c == "NZD" else []),
            })
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError):
        return out
    by_currency = {e["currency"]: e for e in entries}
    if len(by_currency) != 8 or set(by_currency) != set(CURRENCIES):
        return out
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "both_schedule_windows_fit_ceilings": (
                by_currency[base]["both_ceilings_cover_next_scheduled_decision_eve"]
                and by_currency[quote]["both_ceilings_cover_next_scheduled_decision_eve"]),
            "D1": "AGUARDAR", "W1": "AGUARDAR", "trade_authorized": False,
        })
    gaps = sorted(e["currency"] for e in entries
                  if not e["both_ceilings_cover_next_scheduled_decision_eve"])
    out.update({
        "state": ("LAB_EIGHT_POLICY_CALENDAR_WINDOWS_FIT_CURRENT_AGE_CEILINGS_UNATTESTED"
                  if not gaps else "LAB_POLICY_CALENDAR_AGE_CEILING_REVIEW_REQUIRED"),
        "reason": ("OFFICIAL_DATE_RESEARCH_NOT_PIT_RELEASE_OR_RATE_VALUE"
                   if not gaps else "POLICY_AGE_CAP_EXPIRES_BEFORE_SCHEDULE"),
        "as_of_utc": now.isoformat(), "casebook_sha256": CASEBOOK_SHA256,
        "currency_rows": sorted(entries, key=lambda e: e["currency"]),
        "pair_rows": pairs, "currency_count": 8, "pair_count": len(pairs),
        "currencies_with_schedule_age_gap": gaps,
        "max_decision_gap_days": max(e["prior_to_next_announcement_eve_days"] for e in entries),
        "minimum_published_age_margin_days": min(e["published_age_margin_days"] for e in entries),
    })
    return out


__all__ = ["SCHEMA", "CASEBOOK_SHA256", "inspect_g8_policy_schedule_age_audit_lab"]
