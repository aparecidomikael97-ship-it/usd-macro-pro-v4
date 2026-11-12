"""Pure BLS CPI-U level -> twelve-month percent-change calculator (LAB).

The BLS series CUUR0000SA0 is the not-seasonally-adjusted CPI-U All Items
index for U.S. city average. API levels, NOT already annual inflation rates,
must be paired with the same month a year earlier. This module performs no
HTTP and never attests first release, revisions, PIT availability or a bias.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_US_BLS_CPI_U_YOY_SNAPSHOT_LAB_V1"
SERIES = "CUUR0000SA0"
SOURCE_URL_CLAIM = "https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0"
_MONTH = re.compile(r"20\d\d-(?:0[1-9]|1[0-2])\Z")
_INDEX = re.compile(r"[1-9][0-9]{0,3}(?:\.[0-9]{1,6})?\Z")
MAX_RESPONSE_BYTES = 512 * 1024
SEPTEMBER_2026_RELEASE_URL_CLAIM = (
    "https://www.bls.gov/news.release/archives/cpi_10142026.htm"
)
# BLS 10 Nov 2026 October release: the October 2025 CPI-U index was not
# available because of the 2025 appropriations lapse. Do not calculate an
# October 2026 YoY from a caller-invented previous-year index. Reassess only
# against a later, independently verified official historical revision.
KNOWN_UNAVAILABLE_PRIOR_YEAR_INDEX_PERIODS_AS_OF_2026_11_10 = frozenset({"2025-10"})
_NAMES = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLS_CPI_SNAPSHOT_BLOCKED", "reason": reason,
        "source_url_claim": SOURCE_URL_CLAIM, "series_id": SERIES,
        "reference_period": None, "previous_year_reference_period": None,
        "current_index_level_claim": None, "previous_year_index_level_claim": None,
        "derived_yoy_percent": None,
        "derived_value_is_official_published_yoy": False,
        "local_response_hash_verified": False,
        "issuer_first_release_authenticated": False,
        "revisions_independently_audited": False,
        "historical_point_in_time_eligible": False,
        "comparable_with_eurostat_without_methodology_checks": False,
        "can_feed_macro_bias": False, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("JSON_DUPLICATE_PROPERTY")
        out[key] = value
    return out


def _load_positive_index(value: Any) -> Decimal | None:
    if not isinstance(value, str) or _INDEX.fullmatch(value) is None:
        return None
    try:
        n = Decimal(value)
        return n if n.is_finite() and n > 0 else None
    except InvalidOperation:
        return None


def interpret_bls_cpi_u_snapshot_lab(
    raw_response: Any, *, reference_period: Any,
) -> dict[str, Any]:
    """Compute a *derived* YoY rate from two claimed BLS monthly index levels.

    No collection time is accepted or invented. Treat current API data as
    mutable; this calculation cannot reconstruct historical first-seen data.
    """
    out = _blocked("INVALID_BLS_JSON_OR_REFERENCE_PERIOD")
    if (not isinstance(raw_response, bytes) or not 1 <= len(raw_response) <= MAX_RESPONSE_BYTES
            or not isinstance(reference_period, str)
            or _MONTH.fullmatch(reference_period) is None):
        return out
    try:
        raw = json.loads(raw_response.decode("utf-8", errors="strict"),
                         object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return out
    if (not isinstance(raw, dict) or raw.get("status") != "REQUEST_SUCCEEDED"
            or raw.get("message") != []):
        return out
    results = raw.get("Results")
    if isinstance(results, list) and len(results) == 1:
        results = results[0]
    if not isinstance(results, dict):
        return out
    series = results.get("series")
    if (not isinstance(series, list) or len(series) != 1
            or not isinstance(series[0], dict)
            or series[0].get("seriesID") != SERIES):
        return out
    data = series[0].get("data")
    if not isinstance(data, list) or not 2 <= len(data) <= 48:
        return out
    observations: dict[str, Decimal] = {}
    for row in data:
        if not isinstance(row, dict):
            return out
        year, month, name = row.get("year"), row.get("period"), row.get("periodName")
        if (not isinstance(year, str) or not re.fullmatch(r"20\d\d", year)
                or not isinstance(month, str) or not re.fullmatch(r"M(?:0[1-9]|1[0-2])", month)
                or name != _NAMES[int(month[1:]) - 1]):
            return out
        value = _load_positive_index(row.get("value"))
        if value is None:
            return out
        footnotes = row.get("footnotes", [])
        if not isinstance(footnotes, list) or any(
            not isinstance(note, dict)
            or any(v not in (None, "") for v in note.values())
            for note in footnotes
        ):
            # Unexpected revisions or annotations demand manual review.
            return out
        key = f"{year}-{month[1:]}"
        if key in observations:
            out["reason"] = "DUPLICATE_MONTH_OR_AMBIGUOUS_VINTAGE"
            return out
        observations[key] = value

    year, month = reference_period.split("-")
    prior_period = f"{int(year)-1:04d}-{month}"
    if prior_period in KNOWN_UNAVAILABLE_PRIOR_YEAR_INDEX_PERIODS_AS_OF_2026_11_10:
        out["reason"] = "OFFICIAL_2025_10_CPI_U_YEAR_AGO_INDEX_UNAVAILABLE"
        return out
    current, prior = observations.get(reference_period), observations.get(prior_period)
    if current is None or prior is None:
        out["reason"] = "TARGET_OR_PRIOR_YEAR_SAME_MONTH_INDEX_MISSING"
        return out
    rate = ((current / prior - Decimal("1")) * Decimal("100")).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP)
    out.update({
        "state": "LAB_BLS_CPI_U_DERIVED_YOY_FROM_MUTABLE_API_BYTES_UNATTESTED",
        "reason": "TWO_LEVEL_ARITHMETIC_ONLY_NO_OFFICIAL_RELEASE_OR_PIT_PROOF",
        "reference_period": reference_period,
        "previous_year_reference_period": prior_period,
        "current_index_level_claim": str(current),
        "previous_year_index_level_claim": str(prior),
        "derived_yoy_percent": str(rate),
    })
    return out


def reconcile_bls_september_2026_release_lab(
    parsed: Any, *, release_url_claim: Any, published_yoy_percent_claim: Any,
) -> dict[str, Any]:
    """Compare arithmetic to one *caller-transcribed* BLS release number.

    This is not a publisher-signed API capture. The official September 2026
    archived release shows unadjusted all-items 324.800 (Sep 2025), 336.940
    (Sep 2026) and a reported 3.7% 12-month change. All inputs are claims.
    """
    out = {
        "state": "LAB_BLS_RELEASE_ARITHMETIC_REVIEW_REQUIRED",
        "reason": "INVALID_SOURCE_OR_UNVERIFIED_LEVELS",
        "reference_period": None, "official_reported_yoy_claim": None,
        "derived_one_decimal_yoy": None, "arithmetic_matches_claim": False,
        "release_source_independently_authenticated": False,
        "source_first_release_authenticated": False,
        "historical_point_in_time_eligible": False,
        "can_feed_macro_bias": False, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }
    if (not isinstance(parsed, dict)
            or parsed.get("schema") != SCHEMA
            or parsed.get("state") !=
                "LAB_BLS_CPI_U_DERIVED_YOY_FROM_MUTABLE_API_BYTES_UNATTESTED"
            or parsed.get("reference_period") != "2026-09"
            or parsed.get("previous_year_reference_period") != "2025-09"
            or parsed.get("derived_value_is_official_published_yoy") is not False
            or parsed.get("historical_point_in_time_eligible") is not False
            or parsed.get("issuer_first_release_authenticated") is not False
            or parsed.get("trade_authorized") is not False
            or parsed.get("can_feed_macro_bias") is not False
            or release_url_claim != SEPTEMBER_2026_RELEASE_URL_CLAIM
            or not isinstance(published_yoy_percent_claim, str)
            or re.fullmatch(r"(?:0|[1-9][0-9]?)\.[0-9]", published_yoy_percent_claim) is None):
        return out
    current = _load_positive_index(parsed.get("current_index_level_claim"))
    previous = _load_positive_index(parsed.get("previous_year_index_level_claim"))
    if current is None or previous is None:
        return out
    computed = ((current / previous - 1) * 100).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP)
    published = Decimal(published_yoy_percent_claim)
    if computed != published:
        out["reason"] = "REPORTED_AND_RECOMPUTED_TWELVE_MONTH_RATES_DIFFER"
        return out
    out.update({
        "state": "LAB_BLS_RELEASE_ARITHMETIC_MATCHES_CLAIM_UNATTESTED",
        "reason": "ARITHMETIC_MATCH_ONLY_NOT_AUTHENTICATED_SOURCE_OR_PIT",
        "reference_period": "2026-09",
        "official_reported_yoy_claim": str(published),
        "derived_one_decimal_yoy": str(computed),
        "arithmetic_matches_claim": True,
    })
    return out


__all__ = ["SCHEMA", "SERIES", "SOURCE_URL_CLAIM",
           "SEPTEMBER_2026_RELEASE_URL_CLAIM",
           "interpret_bls_cpi_u_snapshot_lab",
           "reconcile_bls_september_2026_release_lab"]
