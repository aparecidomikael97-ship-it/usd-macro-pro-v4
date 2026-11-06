"""Strict offline Swiss FSO October-2026 CPI press-release text reader.

Accepts only a supplied, frozen English source-shaped text excerpt.
No HTTP, actual response authentication, point-in-time publication proof, forecast,
currency strength or trading. Do not substitute Swiss HICP for national CPI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_FSO_CHF_CPI_OCT2026_TEXT_LAB_V1"
SOURCE_URL = "https://www.bfs.admin.ch/en/newnsb/UA8hylpLYO6i"
DATA_PORTAL_URL = "https://statistik.admin.ch/en/asset/36894291"
MAX_BYTES = 128 * 1024
TITLE = "Consumer prices increased by 0.2% in October"
RELEASE_DATE = "3 November 2026"
EXACT_CLAIM = (
    "The Consumer Price Index (CPI) increased by 0.2% in October 2026 "
    "compared with the previous month, reaching 101.7 points "
    "(December 2025 = 100). Inflation was +1.5% compared with "
    "the same month of the previous year."
)
# A conservative cutoff for a release known only by calendar day, NOT its
# witnessed publication instant. This is stricter than the advertised schedule.
EARLIEST_ACCEPTED_CAPTURE_UTC = datetime(2026, 11, 4, tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED", "reason": reason,
        "currency": "CHF", "publisher": "SWISS_FEDERAL_STATISTICAL_OFFICE",
        "source_page": SOURCE_URL, "source_data_portal": DATA_PORTAL_URL,
        "reference_period": None, "observation_period": None,
        "observation_frequency": None, "index_base": None,
        "index_points_claim": None, "published_mom_percent_claim": None,
        "published_yoy_percent_claim": None, "seasonally_adjusted": None,
        "release_calendar_date_claim": None, "release_clock_attested": False,
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
        "publishable": False, "external_http_requests": 0, "new_cost_brl": 0,
    }


def parse_fso_chf_cpi_oct2026_text_lab(
    raw_text_utf8: Any, *, observed_at_utc: Any,
) -> dict[str, Any]:
    out = _blocked("INVALID_BYTES_OR_CAPTURE_CLOCK")
    if (not isinstance(raw_text_utf8, bytes)
            or not 180 <= len(raw_text_utf8) <= MAX_BYTES
            or not isinstance(observed_at_utc, datetime)
            or observed_at_utc.tzinfo is None
            or observed_at_utc.utcoffset() is None):
        return out
    captured = observed_at_utc.astimezone(timezone.utc)
    if captured < EARLIEST_ACCEPTED_CAPTURE_UTC:
        out["reason"] = "CAPTURE_PREDATES_CONSERVATIVE_RELEASE_DAY_BOUND"
        return out
    try:
        body = raw_text_utf8.decode("utf-8", "strict")
    except UnicodeDecodeError:
        out["reason"] = "INVALID_UTF8_TEXT"
        return out
    if any(x in body.lower() for x in ("<html", "<script", "\x00")):
        out["reason"] = "HTML_OR_CORRUPT_TEXT_UNSUPPORTED"
        return out
    normalized = " ".join(body.split())
    if (len(re.findall(re.escape(TITLE), normalized)) != 1
            or len(re.findall(re.escape(RELEASE_DATE), normalized)) != 1
            or "Neuchâtel, 03.11.2026" not in normalized):
        out["reason"] = "SWISS_RELEASE_IDENTITY_OR_DATE_MISSING_OR_DUPLICATE"
        return out
    if normalized.count(EXACT_CLAIM) != 1:
        out["reason"] = "NATIONAL_CPI_OCT2026_MONTHLY_ANNUAL_INDEX_CLAIMS_MISMATCH"
        return out
    if any(term in normalized.lower() for term in (
            "seasonally adjusted", "harmonised index of consumer prices",
            "harmonized index of consumer prices")):
        out["reason"] = "ADJUSTED_OR_HARMONIZED_INDICATOR_NOT_NATIONAL_CPI"
        return out
    out.update({
        "state": "LAB_CHF_FSO_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED",
        "reason": "SOURCE_SHAPED_TEXT_NOT_ORIGINAL_HTTP_OR_HISTORICAL_VINTAGE",
        "reference_period": "2026-10", "observation_period": "2026-10",
        "observation_frequency": "MONTHLY",
        "index_base": "DECEMBER_2025_100", "index_points_claim": "101.7",
        "published_mom_percent_claim": "0.2",
        "published_yoy_percent_claim": "1.5",
        "seasonally_adjusted": None,
        "release_calendar_date_claim": "2026-11-03",
        "source_sha256": sha256(raw_text_utf8).hexdigest(),
        "source_byte_count": len(raw_text_utf8),
        "observed_at_local_system_utc": captured.isoformat(),
    })
    return out


__all__ = ["SCHEMA", "SOURCE_URL", "DATA_PORTAL_URL", "parse_fso_chf_cpi_oct2026_text_lab"]
