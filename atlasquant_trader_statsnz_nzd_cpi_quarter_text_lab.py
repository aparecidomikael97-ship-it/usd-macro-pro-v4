"""Offline Stats NZ September-2026 quarterly CPI extracted-text reader.

Explicit quarterly frequency; never backfill fictitious monthly observations.
Input is user-supplied text, not authenticated official HTTP response bytes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_STATS_NZ_CPI_QUARTER_TEXT_LAB_V1"
SOURCE_URL = "https://www.stats.govt.nz/information-releases/consumers-price-index-september-2026-quarter/"
MAX_BYTES = 64 * 1024
TITLE = "Consumers price index: September 2026 quarter"
RELEASE_DISPLAY = "22 October 2026, 10:45am"
_NUMBER = r"-?(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?"
_ROW = re.compile(
    rf"\s*CPI all groups\s*\|\s*(?P<quarter>{_NUMBER})\s*\|"
    rf"\s*(?P<annual>{_NUMBER})\s*"
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "NZD", "publisher": "STATS_NZ",
        "source_page": SOURCE_URL,
        "observation_frequency": "QUARTERLY",
        "observation_period": None,
        "period_end_month_not_monthly_observation": None,
        "headline_cpi_all_groups_quarter_change_percent_claim": None,
        "headline_cpi_all_groups_annual_change_percent_claim": None,
        "release_date_calendar_only": None,
        "publisher_display_time_without_verified_utc_instant": None,
        "source_sha256": None, "source_byte_count": None,
        "observed_at_local_system_utc": None,
        "official_http_response_independently_observed": False,
        "original_source_authenticity_verified": False,
        "publication_utc_instant_independently_verified": False,
        "historical_vintage_verified": False,
        "monthly_values_synthesized": False,
        "consensus_pre_event_attested": False,
        "cross_country_methods_equivalent": False,
        "commercial_redistribution_rights_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def parse_statsnz_nzd_cpi_sep2026_quarter_text_lab(
    raw_text_utf8: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_TEXT_OR_CLOCK")
    if (not isinstance(raw_text_utf8, bytes)
            or not 100 <= len(raw_text_utf8) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        return out
    now = observed_at_utc.astimezone(timezone.utc)
    try:
        body = raw_text_utf8.decode("utf-8", "strict")
    except UnicodeDecodeError:
        out["reason"] = "INVALID_UTF8"
        return out
    if "<html" in body.lower() or "<script" in body.lower() or "\x00" in body:
        out["reason"] = "HTML_OR_CORRUPT_TEXT_UNSUPPORTED"
        return out
    if (body.count(TITLE) != 1 or body.count(RELEASE_DISPLAY) != 1
            or now.date().isoformat() < "2026-10-22"):
        out["reason"] = "QUARTER_TITLE_RELEASE_DAY_OR_CAPTURE_DATE_MISMATCH"
        return out
    header = re.sub(r"\s+", " ", body)
    if "Description | Quarterly percentage change | Annual percentage change" not in header:
        out["reason"] = "QUARTERLY_VERSUS_ANNUAL_COLUMN_IDENTITY_MISSING"
        return out
    row_hits = [_ROW.fullmatch(line) for line in body.splitlines()]
    rows = [m for m in row_hits if m is not None]
    if len(rows) != 1:
        out["reason"] = "CPI_ALL_GROUPS_ROW_MISSING_OR_DUPLICATE"
        return out
    values = rows[0].groupdict()
    try:
        qtr, annual = Decimal(values["quarter"]), Decimal(values["annual"])
    except InvalidOperation:
        out["reason"] = "NONNUMERIC_CPI_RATE"
        return out
    if not -50 <= qtr <= 50 or not -50 <= annual <= 100:
        out["reason"] = "CPI_RATE_OUT_OF_RANGE"
        return out
    out.update({
        "state": "LAB_NZD_QUARTERLY_CPI_TEXT_QUARANTINED",
        "reason": "EXTRACTED_SOURCE_TEXT_NOT_ORIGINAL_HTTP_OR_PIT_VINTAGE",
        "observation_period": "2026-Q3",
        "period_end_month_not_monthly_observation": "2026-09",
        "headline_cpi_all_groups_quarter_change_percent_claim": values["quarter"],
        "headline_cpi_all_groups_annual_change_percent_claim": values["annual"],
        "release_date_calendar_only": "2026-10-22",
        "publisher_display_time_without_verified_utc_instant": "10:45am",
        "source_sha256": sha256(raw_text_utf8).hexdigest(),
        "source_byte_count": len(raw_text_utf8),
        "observed_at_local_system_utc": now.isoformat(),
    })
    return out


__all__ = ["SCHEMA", "SOURCE_URL", "parse_statsnz_nzd_cpi_sep2026_quarter_text_lab"]
