"""Offline point-in-time (PIT) chronology audit for EUR/USD policy expectations.

This is *not* a consensus feed. Caller-supplied clocks and documents are not
independent proof of public availability. Even a plausible pre-event document
stays quarantined. No HTTP, publication, scheduler, broker, or trade decision.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_EURUSD_POLICY_CONSENSUS_PIT_LAB_V1"
MAX_DOCUMENT_BYTES = 256 * 1024
SOURCES = {
    "ECB_SMA_AGGREGATE": "EUR",
    "ECB_MMSR_OIS_SPOT_MP_AGGREGATE": "EUR",
    "ECB_MMSR_OIS_FORWARD_QUARTER_AGGREGATE": "EUR",
    "ECB_EMMS_OIS_ANNUAL_HISTORY": "EUR",
    "ECB_ESTR_REALIZED_OVERNIGHT": "EUR",
    "ECB_YC_SOVEREIGN_BOND_FORWARD": "EUR",
    "EUREX_FST3_DAILY_TRADING_STATISTICS": "EUR",
    "EUREX_FST3_DAILY_SETTLEMENT": "EUR",
    "ICE_REPORT_CENTER_ESTR_FUTURES_SETTLEMENT": "EUR",
    "NYFED_SME_AGGREGATE": "USD",  # 2025 onwards
    "NYFED_SPD_AGGREGATE_LEGACY": "USD",  # through 2024
    "INDEPENDENT_PRE_EVENT_CANDIDATE_EUR": "EUR",
    "INDEPENDENT_PRE_EVENT_CANDIDATE_USD": "USD",
}
# Official ECB SMA and NY Fed SME/SPD public *aggregate results* are typically
# released after their respective monetary policy meetings. Questionnaires
# and survey response windows are NOT published consensus values.
KNOWN_POST_EVENT_AGGREGATES = frozenset({
    "ECB_SMA_AGGREGATE", "NYFED_SME_AGGREGATE",
    "NYFED_SPD_AGGREGATE_LEGACY",
})
# These official EUR series contain interesting money-market information but
# are NOT same-measure, pre-decision DFR consensus. In particular, MMSR OIS
# businessweek-frequency labels do not mean the aggregate was public that day:
# spot MP statistics are published after each maintenance period, while
# forward-dated OIS statistics aggregate a quarter and publish later.
EUR_MEASURE_GATES = {
    "ECB_MMSR_OIS_SPOT_MP_AGGREGATE": "OIS_MAINTENANCE_PERIOD_AGGREGATE_RELEASE_LAG",
    "ECB_MMSR_OIS_FORWARD_QUARTER_AGGREGATE": "OIS_FORWARD_QUARTER_AGGREGATE_RELEASE_LAG",
    "ECB_EMMS_OIS_ANNUAL_HISTORY": "OIS_ANNUAL_HISTORICAL_UPDATE_NOT_EVENT_CONSENSUS",
    "ECB_ESTR_REALIZED_OVERNIGHT": "REALIZED_ESTR_NOT_POLICY_EXPECTATION",
    "ECB_YC_SOVEREIGN_BOND_FORWARD": "GOVERNMENT_BOND_FORWARD_NOT_OIS_POLICY_EXPECTATION",
    # The public Eurex Daily Statistics .xls contains trading volume and
    # previous-day open interest for FST3, not a contract settlement price.
    "EUREX_FST3_DAILY_TRADING_STATISTICS": "FST3_VOLUME_AND_OPEN_INTEREST_NOT_PRICE",
    # Futures settle on a compounded overnight accrual interval. The price
    # (100 - implied rate) is not the expected *single meeting* ECB DFR level;
    # public daily reports also require actual availability/license evidence.
    "EUREX_FST3_DAILY_SETTLEMENT": "ESTR_FUTURES_ACCRUAL_NOT_SINGLE_MEETING_DFR_CONSENSUS",
    # ICE Report Center market data may not be incorporated into a product
    # without approval. Never turn an apparent public price into a feed.
    "ICE_REPORT_CENTER_ESTR_FUTURES_SETTLEMENT": "ICE_MARKET_DATA_PRODUCT_PERMISSION_NOT_VERIFIED",
}


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _event_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _result(reason: str, currency: Any, source_id: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency": currency if currency in ("EUR", "USD") else None,
        "source_id": source_id if isinstance(source_id, str) else None,
        "event_date": None, "document_sha256": None,
        "document_bytes": None, "source_publication_date_utc": None,
        "document_capture_date_utc": None,
        "survey_closed_date_utc": None,
        "source_timestamp_is_caller_supplied": True,
        "source_origin_independently_authenticated": False,
        "event_release_instant_independently_verified": False,
        "public_availability_independently_verified": False,
        "pre_event_consensus_verified": False,
        "source_measure_is_event_consensus_verified": False,
        "futures_contract_expiry_and_accrual_verified": False,
        "historical_price_publication_instant_verified": False,
        "market_data_product_license_verified": False,
        "historical_point_in_time_eligible": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


def audit_policy_consensus_pit_lab(
    *, source_id: str, currency: str, event_date: str,
    as_of_utc: datetime, published_at_utc: datetime | None,
    captured_at_utc: datetime | None,
    publication_kind: str, raw_document: bytes | None,
    survey_closed_at_utc: datetime | None = None,
) -> dict[str, Any]:
    """Check order of timestamps, never certify an ex-ante consensus value.

    The cutoff is the *start of the event's UTC date*, not an invented
    announcement time; same-day captures are blocked as chronologically
    ambiguous. INDICATIVE_SCHEDULE is explicitly not proof of publication.
    Raw bytes only establish a local SHA binding, not institutional origin.
    """
    out = _result("INVALID_INPUT", currency, source_id)
    if (not isinstance(source_id, str) or not isinstance(currency, str)
            or not isinstance(publication_kind, str)
            or source_id not in SOURCES or SOURCES[source_id] != currency
            or publication_kind not in ("INDICATIVE_SCHEDULE", "CLAIMED_OBSERVED")
            or not isinstance(raw_document, bytes)
            or not 1 <= len(raw_document) <= MAX_DOCUMENT_BYTES):
        return out
    event = _event_date(event_date)
    now = _utc(as_of_utc)
    published = _utc(published_at_utc)
    captured = _utc(captured_at_utc)
    closed = (_utc(survey_closed_at_utc)
              if survey_closed_at_utc is not None else None)
    if (event is None or now is None or published is None or captured is None
            or (survey_closed_at_utc is not None and closed is None)):
        return out
    out.update({
        "event_date": event.isoformat(),
        "document_sha256": sha256(raw_document).hexdigest(),
        "document_bytes": len(raw_document),
        "source_publication_date_utc": published.date().isoformat(),
        "document_capture_date_utc": captured.date().isoformat(),
        "survey_closed_date_utc": closed.date().isoformat() if closed else None,
    })
    if (published > now or captured > now or (closed is not None and closed > now)):
        out["reason"] = "FUTURE_METADATA_RELATIVE_TO_AS_OF"
    elif closed is not None and closed > published:
        out["reason"] = "SURVEY_CLOSED_AFTER_CLAIMED_PUBLICATION"
    elif published > captured:
        out["reason"] = "DOCUMENT_CAPTURE_BEFORE_CLAIMED_PUBLICATION"
    elif published.date() > event or captured.date() > event:
        out["reason"] = "DOCUMENT_NOT_PUBLIC_BEFORE_EVENT_DATE"
    elif published.date() == event or captured.date() == event:
        out["reason"] = "SAME_DAY_ORDER_NEEDS_WITNESSED_EVENT_TIME"
    elif source_id in KNOWN_POST_EVENT_AGGREGATES:
        out["reason"] = "OFFICIAL_AGGREGATE_NORMALLY_PUBLISHED_POST_EVENT"
    elif source_id in EUR_MEASURE_GATES:
        out["reason"] = EUR_MEASURE_GATES[source_id]
    elif publication_kind == "INDICATIVE_SCHEDULE":
        out["reason"] = "SCHEDULE_IS_NOT_ACTUAL_PUBLICATION"
    else:
        out["state"] = "LAB_PRE_EVENT_CHRONOLOGY_PLAUSIBLE_UNVERIFIED"
        out["reason"] = "NO_INDEPENDENT_PUBLIC_AVAILABILITY_OR_EVENT_INSTANT_PROOF"
    return out


def compare_eurusd_consensus_pit_lab(eur: Any, usd: Any) -> dict[str, Any]:
    """Link both research receipts without emitting a bilateral FX signal."""
    structurally_valid = (
        isinstance(eur, dict) and isinstance(usd, dict)
        and eur.get("schema") == SCHEMA and usd.get("schema") == SCHEMA
        and eur.get("currency") == "EUR" and usd.get("currency") == "USD"
    )
    return {
        "schema": SCHEMA,
        "state": ("LAB_BILATERAL_CONSENSUS_CHRONOLOGY_UNVERIFIED"
                  if structurally_valid
                  and eur.get("state") == "LAB_PRE_EVENT_CHRONOLOGY_PLAUSIBLE_UNVERIFIED"
                  and usd.get("state") == "LAB_PRE_EVENT_CHRONOLOGY_PLAUSIBLE_UNVERIFIED"
                  else "LAB_BILATERAL_CONSENSUS_BLOCKED"),
        "eur_reason": eur.get("reason") if structurally_valid else None,
        "usd_reason": usd.get("reason") if structurally_valid else None,
        "pre_event_consensus_verified": False,
        "historical_point_in_time_eligible": False,
        "market_surprise_bps": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_cost_brl": 0,
    }


__all__ = ["SCHEMA", "SOURCES", "KNOWN_POST_EVENT_AGGREGATES",
           "EUR_MEASURE_GATES",
           "audit_policy_consensus_pit_lab", "compare_eurusd_consensus_pit_lab"]
