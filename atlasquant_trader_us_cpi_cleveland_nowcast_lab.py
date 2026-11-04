"""Documented Cleveland Fed CPI nowcast vs (unattested) claimed consensus, LAB.

A daily Federal Reserve Bank model NOWCAST is not a market consensus, a CPI
actual, a historical intraday receipt or a forecast of USD/EUR/USD direction.
No network access, signals, rate action, external expenses or automatic bias.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_TRADER_US_CPI_CLEVELAND_NOWCAST_RESEARCH_LAB_V1"
RESEARCH_FIELDS = frozenset((
    "schema", "state", "research_day_utc", "source_updated_day",
    "earliest_structural_research_asof_utc", "source_url", "schedule_url",
    "currency", "reference_month", "cpi_release_scheduled_utc", "model_name",
    "measures", "actual_release", "market_consensus",
    "original_intraday_capture_attested", "source_value_vintage_archived",
    "market_consensus_verified", "source_redistribution_rights_verified",
    "real_historical_backtest_authorized",
))
MEASURES = frozenset((
    "CPI_MOM_SA_PCT", "CORE_CPI_MOM_SA_PCT",
    "CPI_YOY_NSA_PCT", "CORE_CPI_YOY_NSA_PCT",
))
CONSENSUS_FIELDS = frozenset((
    "state", "source_name", "reference_month", "captured_at_utc",
    "cpi_mom_sa_pct", "core_cpi_mom_sa_pct",
))


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return dt.astimezone(timezone.utc) if dt.utcoffset() == timedelta(0) else None


def _pct(raw: Any) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        num = float(raw)
    except (ValueError, OverflowError):
        return None
    return num if isfinite(num) and -50 <= num <= 100 else None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CLEVELAND_NOWCAST_REFUSED",
        "reason": reason, "model_nowcast": None, "claimed_consensus": None,
        "model_minus_consensus_pp": None, "directional_bias": "AGUARDAR",
        "actual_cpi": None, "market_consensus_verified": False,
        "original_intraday_capture_attested": False,
        "real_historical_backtest_authorized": False,
        "accuracy_90_proven": False, "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def inspect_us_cpi_pre_event_nowcast_lab(
    manifest: Any, *, issued_at: datetime, evaluated_at: datetime,
    claimed_consensus: Any = None,
) -> dict[str, Any]:
    """Compare same-unit model-vs-consensus hypotheticals, never infer FX."""
    if (not isinstance(issued_at, datetime) or issued_at.tzinfo is None
            or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None):
        raise ValueError("Explicit issuance/evaluation timezone required")
    issued, evaluated = (issued_at.astimezone(timezone.utc),
                         evaluated_at.astimezone(timezone.utc))
    if issued > evaluated:
        return _deny("Issue time after evaluation")
    if not isinstance(manifest, Mapping) or set(manifest) != RESEARCH_FIELDS:
        return _deny("Case snapshot schema incomplete or expanded")
    if (manifest["schema"] != SCHEMA
            or manifest["state"] != "OFFICIAL_PUBLIC_NOWCAST_PAGE_DOCUMENT_RESEARCH_ONLY"
            or manifest["currency"] != "USD"
            or manifest["model_name"] != "CLEVELAND_FED_INFLATION_NOWCAST"):
        return _deny("No alternate claims or model labels permitted")
    if any(manifest[k] is not False for k in (
        "original_intraday_capture_attested", "source_value_vintage_archived",
        "market_consensus_verified", "source_redistribution_rights_verified",
        "real_historical_backtest_authorized",
    )) or manifest["actual_release"] is not None or manifest["market_consensus"] is not None:
        return _deny("No real receipt/market consensus/actual attestation")
    try:
        day = date.fromisoformat(manifest["research_day_utc"])
        updated_day = date.fromisoformat(manifest["source_updated_day"])
        reference = date.fromisoformat(manifest["reference_month"] + "-01")
    except (ValueError, TypeError):
        return _deny("Date fields invalid")
    earliest = _utc(manifest["earliest_structural_research_asof_utc"])
    release = _utc(manifest["cpi_release_scheduled_utc"])
    if (earliest is None or release is None
            or earliest != datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)
            or updated_day > day or not updated_day.year == reference.year
            or not release > earliest):
        return _deny("Research or event clock impossible")
    if manifest["source_url"] != "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting":
        return _deny("Expected official nowcast research URL absent")
    if manifest["schedule_url"] != "https://www.bls.gov/schedule/news_release/cpi.htm":
        return _deny("Expected BLS CPI schedule URL absent")
    raw = manifest["measures"]
    if not isinstance(raw, Mapping) or set(raw) != MEASURES:
        return _deny("Model nowcast measure labels incomplete or wrong unit")
    measures = {name: _pct(raw[name]) for name in MEASURES}
    if any(v is None for v in measures.values()):
        return _deny("Model nowcast values invalid")
    if issued < earliest:
        return _deny("Retrospective use of date-only research prohibited")
    if issued >= release:
        return {
            **_deny(""),
            "state": "LAB_CPI_CALENDAR_PAST_DUE_REQUIRES_NEW_ACTUAL",
            "reason": "Official CPI event passed; model estimate must not become actual",
        }
    if claimed_consensus is None:
        return {
            **_deny(""),
            "state": "LAB_PRE_EVENT_NOWCAST_MODEL_ONLY",
            "reason": "Real model nowcast documented; market consensus not sourced",
            "model_nowcast": dict(measures),
            "source_updated_day": updated_day.isoformat(),
            "official_cpi_scheduled_utc": release.isoformat(),
        }
    if not isinstance(claimed_consensus, Mapping) or set(claimed_consensus) != CONSENSUS_FIELDS:
        return _deny("Consensus must use strictly separate, synthetic contract")
    if (claimed_consensus["state"] != "LAB_SYNTHETIC_CONSENSUS_UNATTESTED"
            or claimed_consensus["reference_month"] != manifest["reference_month"]
            or not isinstance(claimed_consensus["source_name"], str)
            or not 3 <= len(claimed_consensus["source_name"].strip()) <= 120):
        return _deny("Source, period or consensus attestation incorrect")
    captured = _utc(claimed_consensus["captured_at_utc"])
    if captured is None or captured > issued or captured >= release:
        return _deny("Claimed consensus arrived after decision cutoff/release")
    headline = _pct(claimed_consensus["cpi_mom_sa_pct"])
    core = _pct(claimed_consensus["core_cpi_mom_sa_pct"])
    if headline is None or core is None:
        return _deny("Invalid or incomparable consensus units")
    return {
        **_deny(""),
        "state": "LAB_MODEL_VS_SYNTHETIC_CONSENSUS_ONLY",
        "reason": "Gap is research arithmetic, not a verified economic surprise",
        "model_nowcast": dict(measures),
        "claimed_consensus": {"cpi_mom_sa_pct": headline,
                              "core_cpi_mom_sa_pct": core},
        "model_minus_consensus_pp": {
            "CPI_MOM_SA_PP": round(measures["CPI_MOM_SA_PCT"] - headline, 6),
            "CORE_CPI_MOM_SA_PP": round(measures["CORE_CPI_MOM_SA_PCT"] - core, 6),
        },
        "official_cpi_scheduled_utc": release.isoformat(),
        "source_updated_day": updated_day.isoformat(),
    }


__all__ = ["SCHEMA", "MEASURES", "inspect_us_cpi_pre_event_nowcast_lab"]
