"""Fail-closed LAB audit for pre-existing Forex daily OHLC caches.

This is a provenance/coverage gate, NOT a backtest or data feed. It accepts
existing historical JSON snapshots as *unverified*, never as licensed,
point-in-time-captured, market-validated 28-pair candles. No I/O is performed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_FX_LEGACY_DAILY_CACHE_AUDIT_LAB_V1"
USD_LEGS = ("EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD", "USD/JPY",
            "USD/CHF", "USD/CAD")
MAX_RECORDS_PER_PAIR = 2000


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 10 <= len(value) <= 60:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    x = float(value)
    return x if isfinite(x) and 0 < x <= 1e8 else None


def audit_legacy_fx_daily_cache_lab(
    payload: Any, *, at: datetime,
) -> dict[str, Any]:
    """Audit only; always withhold live bias/OOS-certification permission.

    The legacy file has no independently attested candle-capture timestamps,
    provider identity, license terms or proof of trading-calendar mapping.
    Adding untrusted self-asserted metadata cannot self-certify those facts.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Audit instant requires an explicit timezone")
    now = at.astimezone(timezone.utc)
    blockers: list[str] = []
    raw = payload.get("pairs") if isinstance(payload, Mapping) else None
    if not isinstance(raw, Mapping):
        raw = {}
        blockers.append("CACHE_MISSING_OR_INVALID")
    all_names = set(raw)
    supported = set(OFFICIAL_PAIRS)
    observed = sorted(all_names & supported)
    unsupported = sorted(str(p) for p in all_names - supported)
    if unsupported:
        blockers.append("UNEXPECTED_SYMBOLS")
    missing = sorted(supported - all_names)
    if missing:
        blockers.append("MISSING_28_INDEPENDENT_CROSSES")
    if any(code not in all_names for code in USD_LEGS):
        blockers.append("MISSING_G8_USD_LEGS")
    pairs: dict[str, dict[str, Any]] = {}
    dates_reference: tuple[str, ...] | None = None
    calendar_mismatch = False
    overall_bars = 0
    total_weekend = 0
    most_recent: datetime | None = None
    for code in observed:
        item = raw[code]
        records = item.get("records") if isinstance(item, Mapping) else None
        errors = []
        if (not isinstance(records, list) or not records
                or len(records) > MAX_RECORDS_PER_PAIR):
            errors.append("RECORDS_INVALID_OR_EMPTY")
            records = []
        stamps: list[str] = []
        weekends = 0
        previous: datetime | None = None
        for row in records:
            if not isinstance(row, Mapping):
                errors.append("RECORD_NOT_OBJECT")
                break
            instant = _dt(row.get("datetime"))
            o, h, l, c = (_number(row.get(k)) for k in
                          ("open", "high", "low", "close"))
            if instant is None or any(v is None for v in (o, h, l, c)):
                errors.append("BAD_TIMESTAMP_OR_PRICE")
                break
            if not (l <= min(o, c) <= max(o, c) <= h):
                errors.append("BAD_OHLC_RANGE")
                break
            if instant > now:
                errors.append("FUTURE_CANDLE")
                break
            if previous is not None and instant <= previous:
                errors.append("DUPLICATE_OR_UNORDERED_CANDLE")
                break
            if instant.weekday() >= 5:
                weekends += 1
            stamps.append(instant.isoformat())
            previous = instant
        if len(stamps) != len(records) and not errors:
            errors.append("INCOMPLETE_PARSE")
        if isinstance(item, Mapping):
            stamp = _dt(item.get("updated_at"))
            if stamp is None or stamp > now or (previous and stamp < previous):
                errors.append("INVALID_CACHE_UPDATE_CLOCK")
        if dates_reference is None and stamps:
            dates_reference = tuple(stamps)
        elif stamps and tuple(stamps) != dates_reference:
            calendar_mismatch = True
        if previous is not None:
            most_recent = max(previous, most_recent) if most_recent else previous
        overall_bars += len(records)
        total_weekend += weekends
        if weekends:
            errors.append("WEEKEND_DATED_BARS_NEED_SESSION_PROOF")
        pairs[code] = {"records": len(records), "weekend_dated_bars": weekends,
                       "first": stamps[0] if stamps else None,
                       "last": stamps[-1] if stamps else None,
                       "structurally_valid": not any(e != "WEEKEND_DATED_BARS_NEED_SESSION_PROOF"
                                                     for e in errors),
                       "audit_findings": sorted(set(errors))}
        if errors:
            blockers.append("PAIR_AUDIT_FINDINGS")
    if calendar_mismatch:
        blockers.append("CROSS_PAIR_CALENDAR_MISMATCH")
    changed = _dt(payload.get("updated_at")) if isinstance(payload, Mapping) else None
    if changed is None or changed > now or (most_recent and changed < most_recent):
        blockers.append("INVALID_GLOBAL_CACHE_CLOCK")
    age_days = (now - most_recent).total_seconds() / 86400 if most_recent else None
    if age_days is None or age_days > 4:
        blockers.append("HISTORY_NOT_FRESH_FOR_DAILY_BIAS")
    if total_weekend:
        blockers.append("UNVERIFIED_WEEKEND_SESSION_MAPPING")
    blockers.extend(("PROVIDER_ORIGIN_NOT_INDEPENDENTLY_VERIFIED",
                     "LEGACY_FX_D1_TIMEZONE_CONVERSION_UNATTESTED",
                     "LEGACY_D1_CLOSE_AVAILABILITY_UNVERIFIED",
                     "HISTORICAL_POINT_IN_TIME_CAPTURE_UNVERIFIED",
                     "MARKET_DATA_LICENSE_UNVERIFIED"))
    return {"schema": SCHEMA, "state": "QUARANTINED_UNVERIFIED_HISTORICAL_CACHE",
            "checked_at_utc": now.isoformat(),
            "covered_pairs": len(observed),
            "canonical_pair_count": len(OFFICIAL_PAIRS),
            "missing_28_pairs": missing,
            "present_usd_legs": len(set(USD_LEGS) & all_names),
            "usd_leg_count": len(USD_LEGS),
            "total_candles": overall_bars, "weekend_dated_bars": total_weekend,
            "latest_candle_utc": most_recent.isoformat() if most_recent else None,
            "age_days": round(age_days, 2) if age_days is not None else None,
            "aligned_candle_dates": not calendar_mismatch and dates_reference is not None,
            "pairs": pairs, "blockers": sorted(set(blockers)),
            # Autopilot V10.7 used Twelve Data /time_series and converted
            # datetimes via pd.to_datetime(..., utc=True). The provider documents
            # that timezone=UTC is IGNORED for D1, unlike intraday. The cache
            # has lost original provider meta.exchange_timezone and cannot
            # prove those UTC timestamps are the original candle instants.
            "probable_software_lineage": "Twelve Data time_series via autopilot_v107",
            "source_response_attested": False,
            "d1_requested_utc_timezone_effective": False,
            "provider_daily_exchange_timezone_attested": False,
            "bar_label_is_verified_close_time": False,
            "provider_identity_attested": False,
            "license_attested": False,
            "point_in_time_capture_attested": False,
            "historical_oos_ready": False, "daily_bias_ready": False,
            "real_accuracy_publishable": False, "derive_missing_crosses_as_real": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False,
            "reason": "Existing JSON alone cannot attest 28-pair pricing, session dates,"
                      " provider entitlement or historical forecast availability."}


__all__ = ["SCHEMA", "USD_LEGS", "audit_legacy_fx_daily_cache_lab"]
