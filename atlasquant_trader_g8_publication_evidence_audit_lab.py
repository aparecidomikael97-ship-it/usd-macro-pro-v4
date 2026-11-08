"""Audit source timing evidence for G8 Forex, not economic predictions.

The 17 records in four public-page research pilots have different levels of
publication-time proof. An exact time on a present-day publisher page is
NOT an independent, historically captured, revision-free vintage.

No issuer numerical values, economic strength, orders, network or MT5 access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_gbp_nzd_official_pilot_lab import PILOT as GBP_NZD
from atlasquant_trader_usd_eur_official_pilot_lab import OFFICIAL_OBSERVATIONS as USD_EUR
from atlasquant_trader_aud_cad_official_pilot_lab import OFFICIAL_OBSERVATIONS as AUD_CAD
from atlasquant_trader_chf_jpy_official_pilot_lab import OFFICIAL_OBSERVATIONS as CHF_JPY

SCHEMA = "ATLASQUANT_TRADER_G8_PUBLICATION_EVIDENCE_AUDIT_LAB_V1"
HORIZONS = ("D1", "W1")
SOURCE_CATALOGS = (GBP_NZD, USD_EUR, AUD_CAD, CHF_JPY)

# These files were reported as captured on the AM12 *after* publication.
# They are not mounted here, have not been re-audited on the AM12 today and
# cannot establish a copy of the original release at its announcement time.
PREVIOUSLY_REPORTED_POST_RELEASE_LOCAL_FILES = frozenset((
    "GBP_CPI_2026_09", "NZD_CPI_2026_Q3", "GBP_BANK_RATE_2026_11",
))


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EVIDENCE_AUDIT_BLOCKED", "reason": reason,
        "decision_at_utc": None, "horizon": None,
        "catalogued_records": 0, "research_available_records": 0,
        "exact_publisher_time_records": 0,
        "date_only_conservative_records": 0,
        "current_update_not_original_records": 0,
        "known_mutable_publication_pages": 0,
        "sources": {}, "per_currency": {},
        "independently_attested_historical_vintages": 0,
        "fully_certified_currencies": 0, "backtest_ready_pairs": 0,
        "source_body_reverified_on_am12_now": False,
        "historical_backtest_approved": False, "operational_bias": "AGUARDAR",
        "probability": None, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def _time(raw: str) -> datetime:
    # A timezone-less value must never silently inherit the host computer's
    # local timezone. Keep catalog cutoffs canonical whole-second UTC.
    if (not isinstance(raw, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None):
        raise ValueError("NONCANONICAL_OR_TIMEZONELESS_AVAILABILITY_FLOOR")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _precision_grade(source: dict[str, Any]) -> str:
    evidence = source["time_evidence"]
    if not isinstance(evidence, str):
        raise ValueError("INVALID_TIME_EVIDENCE_TYPE")
    if evidence.startswith("EXACT_"):
        return "PUBLISHER_EXACT_TIME_RESEARCH_ONLY"
    if evidence.startswith("CURRENT_RATE_PAGE_LAST_UPDATED_TIME"):
        return "CURRENT_PAGE_UPDATE_NOT_ORIGINAL_ISSUE"
    if "NEXT" in evidence or "DATE_ONLY" in evidence:
        return "PUBLISHER_DATE_ONLY_CONSERVATIVE_CUTOFF"
    raise ValueError("UNKNOWN_TIME_EVIDENCE_CLASS")


def inspect_g8_publication_evidence_lab(
    *, decision_at_utc: datetime, horizon: str,
) -> dict[str, Any]:
    """Grade research metadata only; return no positive backtest authority.

    A passed timing floor only means the research catalog *could* have been
    available according to the current publisher page. It must never be fed
    as an independently captured historical economic record.
    """
    out = _blocked("INVALID_DECISION_OR_HORIZON")
    if (horizon not in HORIZONS or not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0):
        return out
    decision = decision_at_utc.astimezone(timezone.utc)

    records: dict[str, dict[str, Any]] = {}
    currency_rows: dict[str, dict[str, Any]] = {
        currency: {"available_research_records": 0, "publisher_exact_time_records": 0,
                   "independent_original_vintages": 0, "backtest_approved": False}
        for currency in CURRENCIES
    }
    grades: dict[str, int] = {
        "PUBLISHER_EXACT_TIME_RESEARCH_ONLY": 0,
        "PUBLISHER_DATE_ONLY_CONSERVATIVE_CUTOFF": 0,
        "CURRENT_PAGE_UPDATE_NOT_ORIGINAL_ISSUE": 0,
    }
    known_mutable_count = 0
    seen: set[str] = set()
    try:
        for catalog in SOURCE_CATALOGS:
            for key, source in catalog.items():
                if key in seen or source["currency"] not in currency_rows:
                    return _blocked("DUPLICATE_OR_NONCANONICAL_SOURCE")
                if ("source_page_mutable" in source
                        and not isinstance(source["source_page_mutable"], bool)):
                    return _blocked("NONBOOLEAN_MUTABLE_PAGE_FLAG")
                seen.add(key)
                grade = _precision_grade(source)
                floor = _time(source["availability_floor_utc"])
                available = decision >= floor
                known_mutable = source.get("source_page_mutable") is True
                records[key] = {
                    "currency": source["currency"], "family": source["family"],
                    "observation_period": source["observation_period"],
                    "published_date_claim": source.get("published_date"),
                    "publisher_time_precision_grade": grade,
                    "conservative_availability_floor_utc": source["availability_floor_utc"],
                    "research_by_publisher_boundary": available,
                    "known_mutable_latest_page": known_mutable,
                    "mutability_independently_excluded": False,
                    "post_release_local_capture_reported_not_reverified": (
                        key in PREVIOUSLY_REPORTED_POST_RELEASE_LOCAL_FILES),
                    "original_release_bytes_attested": False,
                    "historical_vintage_attested": False,
                    "safe_for_backtest": False,
                }
                grades[grade] += 1
                known_mutable_count += int(known_mutable)
                if available:
                    currency_rows[source["currency"]]["available_research_records"] += 1
                    currency_rows[source["currency"]]["publisher_exact_time_records"] += int(
                        grade == "PUBLISHER_EXACT_TIME_RESEARCH_ONLY")
    except (KeyError, TypeError, ValueError, OverflowError):
        return _blocked("MALFORMED_SOURCE_RESEARCH_CATALOG")

    out.update({
        "state": "LAB_RESEARCH_PUBLICATION_EVIDENCE_UNATTESTED",
        "reason": "PUBLICATION_TIMING_NOT_ORIGINAL_HISTORICAL_VINTAGE",
        "horizon": horizon, "decision_at_utc": decision.isoformat(),
        "catalogued_records": len(records),
        "research_available_records": sum(x["research_by_publisher_boundary"] for x in records.values()),
        "exact_publisher_time_records": grades["PUBLISHER_EXACT_TIME_RESEARCH_ONLY"],
        "date_only_conservative_records": grades["PUBLISHER_DATE_ONLY_CONSERVATIVE_CUTOFF"],
        "current_update_not_original_records": grades["CURRENT_PAGE_UPDATE_NOT_ORIGINAL_ISSUE"],
        "known_mutable_publication_pages": known_mutable_count,
        "sources": dict(sorted(records.items())), "per_currency": currency_rows,
    })
    return out


__all__ = ["SCHEMA", "HORIZONS", "inspect_g8_publication_evidence_lab"]
