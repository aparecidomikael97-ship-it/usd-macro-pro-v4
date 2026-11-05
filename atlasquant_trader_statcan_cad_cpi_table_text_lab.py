"""Exploratory offline Canada CPI all-items table *text* contract.

Only accepts supplied plain text matching the specific StatCan Sep-2026
not-seasonally-adjusted table. It is NOT original publisher HTTP data,
historical availability proof, consensus or a tradable CAD direction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_CANADA_CPI_TABLE_TEXT_LAB_V1"
SOURCE_URL = "https://www150.statcan.gc.ca/n1/daily-quotidien/261019/t001a-eng.htm"
MAX_BYTES = 128 * 1024
_NUMBER = r"-?(?:0|[1-9]\d{0,3})(?:\.\d{1,2})?"
_ROW = re.compile(
    rf"\s*All-items\s*\|\s*(?P<sep25>{_NUMBER})\s*\|"
    rf"\s*(?P<aug26>{_NUMBER})\s*\|\s*(?P<sep26>{_NUMBER})\s*\|"
    rf"\s*(?P<mom>{_NUMBER})\s*\|\s*(?P<yoy>{_NUMBER})\s*"
)
_TITLE = "Consumer Price Index, major components and special aggregates, Canada – Not seasonally adjusted"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": "CAD", "publisher": "STATISTICS_CANADA",
        "source_page": SOURCE_URL,
        "reference_period": None, "base_year": None,
        "index_base": None, "page_modified_calendar_only": None,
        "index_sep_2025_claim": None, "index_aug_2026_claim": None,
        "index_sep_2026_claim": None, "published_mom_percent_claim": None,
        "published_yoy_percent_claim": None, "seasonally_adjusted": None,
        "source_sha256": None, "source_byte_count": None,
        "observed_at_local_system_utc": None,
        "source_is_original_official_http_response": False,
        "original_source_authenticity_independently_verified": False,
        "individual_release_instant_verified": False,
        "archived_historical_vintage_verified": False,
        "consensus_pre_event_attested": False,
        "cross_country_methods_equivalent": False,
        "commercial_redistribution_rights_verified": False,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def parse_statcan_cad_all_items_table_text_lab(
    raw_text_utf8: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_BYTES_OR_CAPTURE_CLOCK")
    if (not isinstance(raw_text_utf8, bytes)
            or not 100 <= len(raw_text_utf8) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        return out
    captured = observed_at_utc.astimezone(timezone.utc)
    try:
        body = raw_text_utf8.decode("utf-8", "strict")
    except UnicodeDecodeError:
        out["reason"] = "INVALID_UTF8_TEXT"
        return out
    if "<html" in body.lower() or "<script" in body.lower() or "\x00" in body:
        out["reason"] = "HTML_OR_CORRUPT_TEXT_NOT_SUPPORTED"
        return out
    # The official page shows the heading both above and inside Table 1.
    if not 1 <= body.count(_TITLE) <= 2:
        out["reason"] = "CANADA_NSA_ALL_ITEMS_TABLE_TITLE_MISSING_OR_AMBIGUOUS"
        return out
    # Require the exact year-specific columns and the index/percentage units.
    # The frozen 261019 table cannot be silently repurposed for another month.
    header = re.sub(r"\s+", " ", body)
    if (not re.search(r"September 2025\s*\|\s*August 2026\s*\|\s*September 2026"
                      r"\s*\|\s*August to September 2026\s*\|\s*"
                      r"September 2025 to September 2026", header)
            or header.count("(2002=100)") != 3
            or not re.search(r"% change\s*\|\s*% change", header)):
        out["reason"] = "PERIOD_COLUMNS_OR_2002_BASE_UNITS_MISMATCH"
        return out
    matches = [_ROW.fullmatch(line) for line in body.splitlines()]
    rows = [m for m in matches if m is not None]
    if len(rows) != 1:
        out["reason"] = "ALL_ITEMS_ROW_MISSING_OR_DUPLICATED"
        return out
    fields = rows[0].groupdict()
    try:
        levels = [Decimal(fields[x]) for x in ("sep25", "aug26", "sep26")]
        mom, yoy = Decimal(fields["mom"]), Decimal(fields["yoy"])
    except InvalidOperation:
        out["reason"] = "DECIMAL_INVALID"
        return out
    if (any(not 30 <= x <= 400 for x in levels)
            or not -30 <= mom <= 30 or not -50 <= yoy <= 100):
        out["reason"] = "CPI_LEVEL_OR_RATE_OUT_OF_RANGE"
        return out
    date_modified = re.findall(r"Date modified:\s*(20\d{2}-\d\d-\d\d)", body)
    if len(date_modified) != 1 or date_modified[0] != "2026-10-19":
        out["reason"] = "PAGE_MODIFIED_DATE_MISSING_OR_UNEXPECTED"
        return out
    # The page's modification date is not a verified publication instant.
    if captured.date().isoformat() < date_modified[0]:
        out["reason"] = "CAPTURE_PREDATES_DECLARED_PAGE_MODIFICATION_DAY"
        return out
    out.update({
        "state": "LAB_CANADA_CPI_SUPPLIED_TABLE_TEXT_QUARANTINED",
        "reason": "EXTRACTED_PAGE_TEXT_NOT_OFFICIAL_HTTP_OR_HISTORICAL_VINTAGE",
        "reference_period": "2026-09", "base_year": 2002,
        "index_base": "2002=100", "page_modified_calendar_only": date_modified[0],
        "index_sep_2025_claim": fields["sep25"],
        "index_aug_2026_claim": fields["aug26"],
        "index_sep_2026_claim": fields["sep26"],
        "published_mom_percent_claim": fields["mom"],
        "published_yoy_percent_claim": fields["yoy"],
        "seasonally_adjusted": False,
        "source_sha256": sha256(raw_text_utf8).hexdigest(),
        "source_byte_count": len(raw_text_utf8),
        "observed_at_local_system_utc": captured.isoformat(),
    })
    return out


__all__ = ["SCHEMA", "SOURCE_URL", "parse_statcan_cad_all_items_table_text_lab"]
