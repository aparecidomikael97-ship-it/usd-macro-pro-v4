"""Strict, offline ABS September-2026 monthly all-groups CPI text receipt.

Pinned September-2026 release figures checked in official public ABS page.
Source-shaped UTF-8 test input is NOT authenticated HTTP, PIT or event proof.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_ABS_AUD_MONTHLY_CPI_TEXT_LAB_V1"
SOURCE_URL = "https://www.abs.gov.au/media-centre/media-releases/cpi-rose-43-year-september-2026"
RELEASE_TITLE = "CPI rose 4.3% in the year to September 2026"
RELEASE_DISPLAY = "28/10/2026 11:30am AEDT"
SERIES_HEADER = "All groups CPI, Australia, monthly and annual movement (%)"
COLUMN_HEADER = "Change from previous month (%) | Annual change (%)"
MAX_BYTES = 128 * 1024
_NUM = r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?"
_ROW = re.compile(rf"(?P<month>Aug-26|Sep-26)\s*\|\s*(?P<mom>{_NUM})\s*\|\s*(?P<yoy>{_NUM})")
_MIN_CAPTURE_UTC = datetime(2026, 10, 28, 0, 30, tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "AUD", "publisher": "AUSTRALIAN_BUREAU_OF_STATISTICS",
        "source_page": SOURCE_URL, "source_format": "EXTRACTED_UTF8_TEXT_ONLY",
        "observation_frequency": "MONTHLY", "observation_period": None,
        "seasonally_adjusted": False,
        "headline_cpi_all_groups_monthly_change_percent_claim": None,
        "headline_cpi_all_groups_annual_change_percent_claim": None,
        "prior_month_annual_change_percent_claim": None,
        "published_local_time_claim_AEDT": None,
        "published_release_calendar_date": None,
        "source_sha256": None, "source_byte_count": None,
        "observed_at_local_system_utc": None,
        "official_http_response_independently_observed": False,
        "original_source_authenticity_verified": False,
        "publication_utc_instant_independently_verified": False,
        "point_in_time_historical_vintage_verified": False,
        "consensus_pre_event_attested": False,
        "cross_country_methods_equivalent": False,
        "commercial_redistribution_rights_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def parse_abs_aud_cpi_sep2026_monthly_text_lab(
    raw_text_utf8: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_TEXT_OR_CLOCK")
    if (not isinstance(raw_text_utf8, bytes)
            or not 100 <= len(raw_text_utf8) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        return out
    observed = observed_at_utc.astimezone(timezone.utc)
    if observed < _MIN_CAPTURE_UTC:
        out["reason"] = "CAPTURE_PRECEDES_DISPLAYED_RELEASE_TIME"
        return out
    try:
        body = raw_text_utf8.decode("utf-8", "strict")
    except UnicodeDecodeError:
        out["reason"] = "INVALID_UTF8"
        return out
    if "<html" in body.lower() or "<script" in body.lower() or "\x00" in body:
        out["reason"] = "HTML_OR_CORRUPT_TEXT_UNSUPPORTED"
        return out
    normalized = re.sub(r"\s+", " ", body)
    if (body.count(RELEASE_TITLE) != 1 or body.count(RELEASE_DISPLAY) != 1
            or body.count(SERIES_HEADER) != 1
            or COLUMN_HEADER not in normalized):
        out["reason"] = "RELEASE_TITLE_TIME_OR_MONTHLY_COLUMN_CONTRACT_MISSING"
        return out
    if ("The Consumer Price Index (CPI) rose 4.3 per cent in the 12 months"
            " to September 2026, up from 4.0 per cent in the 12 months to August"
            not in normalized):
        out["reason"] = "RELEASE_NARRATIVE_AND_TABLE_NOT_CROSS_CHECKABLE"
        return out
    extracted = {}
    for month in ("Aug-26", "Sep-26"):
        lines = [line.strip() for line in body.splitlines()
                 if re.match(rf"^\s*{month}\s*\|", line)]
        if len(lines) != 1:
            out["reason"] = "MONTHLY_CPI_ROW_MISSING_OR_DUPLICATE"
            return out
        hit = _ROW.fullmatch(lines[0])
        if hit is None or hit.group("month") != month:
            out["reason"] = "MALFORMED_MONTHLY_CPI_ROW"
            return out
        extracted[month] = hit.groupdict()
    try:
        values = {(month, key): Decimal(row[key])
                  for month, row in extracted.items() for key in ("mom", "yoy")}
    except InvalidOperation:
        out["reason"] = "NONNUMERIC_CPI_RATE"
        return out
    # Fixed-vintage receipt: reject swapped seasonal adjustment, shifted columns,
    # silently updated values or mislabelled month. This is not a generic scraper.
    expected = {("Aug-26", "mom"): Decimal("0.4"),
                ("Aug-26", "yoy"): Decimal("4.0"),
                ("Sep-26", "mom"): Decimal("0.8"),
                ("Sep-26", "yoy"): Decimal("4.3")}
    if values != expected:
        out["reason"] = "PINNED_ORIGINAL_ALL_GROUPS_CPI_VALUES_MISMATCH"
        return out
    out.update({
        "state": "LAB_AUD_ABS_MONTHLY_CPI_SUPPLIED_TEXT_QUARANTINED",
        "reason": "SOURCE_SHAPED_TEXT_NOT_ORIGINAL_HTTP_OR_PIT_VINTAGE",
        "observation_period": "2026-09",
        "headline_cpi_all_groups_monthly_change_percent_claim": "0.8",
        "headline_cpi_all_groups_annual_change_percent_claim": "4.3",
        "prior_month_annual_change_percent_claim": "4.0",
        "published_local_time_claim_AEDT": "11:30am AEDT",
        "published_release_calendar_date": "2026-10-28",
        "source_sha256": sha256(raw_text_utf8).hexdigest(),
        "source_byte_count": len(raw_text_utf8),
        "observed_at_local_system_utc": observed.isoformat(),
    })
    return out


__all__ = ["SCHEMA", "SOURCE_URL", "parse_abs_aud_cpi_sep2026_monthly_text_lab"]
