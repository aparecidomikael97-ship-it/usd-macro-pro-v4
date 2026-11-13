"""G8 central-bank POLICY RATE source/instrument admission — offline LAB.

Avoid mixing Fed *target range* with point rates and treating eight
different monetary policy instruments as identical. The official issuer
URLs below are public landing-page CANDIDATES manually checked on 2026-11-12,
not trusted download/response receipts, release clocks or current values.

This does not fetch official content. Every supplied value, URL, effective
date and publication time is a CALLER CLAIM and may be false/backdated.
Matching a whitelist URL NEVER authenticates original raw bytes, a first
release timestamp, Fed range bounds, broker time, FX bias or profitability.

No network, filesystem, broker, account, orders, signals or scheduling.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_G8_POLICY_RATE_OFFICIAL_SOURCE_TYPE_LAB_V1"

# Instrument meaning explicitly differs by central bank. These names are
# not normalizations for direct carry/FX valuation or causal inference.
OFFICIAL_POLICY_CANDIDATES = {
    "USD": {
        "issuer": "Federal Reserve Board", "measure": "FED_FUNDS_TARGET_RANGE",
        "kind": "RANGE", "url":
            "https://www.federalreserve.gov/FOMC/fundsrate.htm",
    },
    "EUR": {
        "issuer": "European Central Bank", "measure": "ECB_DEPOSIT_FACILITY_RATE",
        "kind": "POINT", "url":
            "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.ga.html",
    },
    "GBP": {
        "issuer": "Bank of England", "measure": "BOE_BANK_RATE",
        "kind": "POINT", "url":
            "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate",
    },
    "JPY": {
        "issuer": "Bank of Japan", "measure": "BOJ_UNCOLLATERALIZED_OVERNIGHT_CALL_RATE_GUIDELINE",
        "kind": "POINT", "url": "https://www.boj.or.jp/en/",
    },
    "CHF": {
        "issuer": "Swiss National Bank", "measure": "SNB_POLICY_RATE",
        "kind": "POINT", "url":
            "https://www.snb.ch/en/srv/current_interest_exchange_rates",
    },
    "CAD": {
        "issuer": "Bank of Canada", "measure": "BOC_OVERNIGHT_RATE_TARGET",
        "kind": "POINT", "url":
            "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/",
    },
    "AUD": {
        "issuer": "Reserve Bank of Australia", "measure": "RBA_CASH_RATE_TARGET",
        "kind": "POINT", "url":
            "https://www.rba.gov.au/cash-rate-target-overview.html",
    },
    "NZD": {
        "issuer": "Reserve Bank of New Zealand", "measure": "RBNZ_OFFICIAL_CASH_RATE",
        "kind": "POINT", "url":
            "https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate",
    },
}
RATE = re.compile(r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,4})?\Z")
DATE = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\Z")
UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
FIELDS = frozenset((
    "currency", "issuer_name_claim", "measure_claim", "measure_kind_claim",
    "source_url_claim", "rate_lower_pct_claim", "rate_upper_pct_claim",
    "effective_date_claim", "issuer_published_at_utc_claim",
    "locally_observed_at_utc_claim",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_G8_POLICY_RATE_CANDIDATE_ADMISSION_BLOCKED",
        "reason": reason,
        "currencies_expected": len(CURRENCIES),
        "source_candidates_supplied": 0,
        "source_url_and_instrument_claim_matches": 0,
        "source_candidates_missing": sorted(CURRENCIES),
        "rate_ranges_preserved": 0,
        "point_rate_values_structurally_plausible": 0,
        "all_8_source_type_claims_locally_consistent": False,
        "raw_issuer_response_bytes_present": False,
        "http_response_headers_or_tls_authenticated": False,
        "original_issuer_release_authenticated": False,
        "publisher_first_available_timestamp_verified": False,
        "point_in_time_policy_vintage_verified": False,
        "official_rates_verified": False,
        "fed_range_compressed_to_midpoint": False,
        "policy_rate_measures_economically_comparable": False,
        "fx28_bilateral_macro_fully_authenticated": False,
        "forecast_publication_witnessed": False,
        "historical_accuracy_validated": False,
        "calibrated_directional_probability": None,
        "relative_currency_strength_score": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_calls": 0,
        "files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or DATE.fullmatch(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _rate(value: Any) -> Decimal | None:
    if not isinstance(value, str) or RATE.fullmatch(value) is None:
        return None
    try:
        rate = Decimal(value)
        return rate if rate.is_finite() and Decimal("-25") <= rate <= Decimal("100") else None
    except InvalidOperation:
        return None


def _exact_official_url(value: Any, expected: str) -> bool:
    """Require exact immutable-source LOCATION claim; no subdomain tricks."""
    if type(value) is not str or value != expected:
        return False
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    return (
        url.scheme == "https"
        and url.username is None and url.password is None
        and url.port is None and url.query == "" and url.fragment == ""
        and url.hostname in (
            "www.federalreserve.gov", "www.ecb.europa.eu",
            "www.bankofengland.co.uk", "www.boj.or.jp",
            "www.snb.ch", "www.bankofcanada.ca", "www.rba.gov.au",
            "www.rbnz.govt.nz",
        )
    )


def inspect_g8_policy_rate_candidates_lab(
    records: Any, *, decision_at_utc: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Admission of eight claimed source/metric types; no value attestation."""
    out = _blocked("INVALID_LIST_OR_CLOCK")
    if (type(records) not in (list, tuple) or len(records) > len(CURRENCIES)
            or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or not isinstance(inspected_at_utc, datetime)
            or inspected_at_utc.tzinfo is None
            or inspected_at_utc.utcoffset() is None):
        return out
    decision = decision_at_utc.astimezone(timezone.utc)
    now = inspected_at_utc.astimezone(timezone.utc)
    if decision.microsecond or now.microsecond or decision > now:
        out["reason"] = "DECISION_CLOCK_NOT_A_VALID_PIT_CUTOFF"
        return out
    provided = set()
    source_count = point_count = range_count = 0
    for record in records:
        if type(record) is not dict or set(record) != FIELDS:
            out["reason"] = "POLICY_RATE_CLAIM_SCHEMA_INVALID"
            return out
        cur = record.get("currency")
        if (type(cur) is not str or cur not in OFFICIAL_POLICY_CANDIDATES
                or cur in provided):
            out["reason"] = "CURRENCY_MISSING_DUPLICATE_OR_NOT_G8"
            return out
        provided.add(cur)
        expected = OFFICIAL_POLICY_CANDIDATES[cur]
        if (record.get("issuer_name_claim") != expected["issuer"]
                or record.get("measure_claim") != expected["measure"]
                or record.get("measure_kind_claim") != expected["kind"]
                or not _exact_official_url(
                    record.get("source_url_claim"), expected["url"])):
            out["reason"] = "POLICY_SOURCE_OR_METRIC_NOT_OFFICIAL_CANDIDATE"
            return out

        floor = _rate(record.get("rate_lower_pct_claim"))
        ceiling = _rate(record.get("rate_upper_pct_claim"))
        effective = _date(record.get("effective_date_claim"))
        published = _utc(record.get("issuer_published_at_utc_claim"))
        observed = _utc(record.get("locally_observed_at_utc_claim"))
        if (floor is None or ceiling is None or effective is None
                or published is None or observed is None
                or not published <= observed <= decision <= now
                # A date-only "effective today" field has no intraday
                # release time; do not assume it existed before the
                # decision cutoff on that same day.
                or effective >= decision.date()):
            out["reason"] = "RATE_VALUE_CLAIM_OR_POINT_IN_TIME_CHRONOLOGY_INVALID"
            return out
        if expected["kind"] == "RANGE":
            if floor >= ceiling:
                out["reason"] = "FED_RANGE_MUST_HAVE_DISTINCT_BOUNDS"
                return out
            range_count += 1
        else:
            if floor != ceiling:
                out["reason"] = "POINT_RATE_CANNOT_BE_FED_RANGE_OR_SPREAD"
                return out
            point_count += 1
        source_count += 1

    out.update({
        "source_candidates_supplied": len(provided),
        "source_url_and_instrument_claim_matches": source_count,
        "source_candidates_missing": sorted(set(CURRENCIES) - provided),
        "rate_ranges_preserved": range_count,
        "point_rate_values_structurally_plausible": point_count,
    })
    out["state"] = (
        "LAB_G8_POLICY_RATE_8_CANDIDATE_TYPES_LOCAL_ONLY_NO_GO"
        if len(provided) == len(CURRENCIES)
        else "LAB_G8_POLICY_RATE_PARTIAL_CANDIDATE_TYPES_NO_GO")
    out["reason"] = (
        "SELF_SUPPLIED_VALUES_SOURCE_URL_AND_TIMESTAMPS_NOT_VERIFIED"
        if len(provided) == len(CURRENCIES)
        else "MISSING_CURRENCY_CLAIMS_AND_NO_ISSUER_AUTHENTICATION")
    out["all_8_source_type_claims_locally_consistent"] = (
        len(provided) == len(CURRENCIES) and source_count == len(CURRENCIES)
        and range_count == 1 and point_count == 7)
    return out


__all__ = ("SCHEMA", "OFFICIAL_POLICY_CANDIDATES",
           "inspect_g8_policy_rate_candidates_lab")
