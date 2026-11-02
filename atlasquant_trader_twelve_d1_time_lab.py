"""Twelve Data FX D1 timezone research adapter — offline synthetic LAB only.

The provider's documentation says timezone=UTC on /time_series is ignored
for intervals >= 1 day. Daily labels require a response-supplied exchange
timezone and *cannot* be assumed UTC or known to be bar closing times.
This tool never makes requests or validates provider identity/availability.
References: https://twelvedata.com/docs
and https://support.twelvedata.com/en/articles/5745849-timezones
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = "ATLASQUANT_TWELVE_FX_D1_LOCAL_TIME_AUDIT_LAB_V1"
MAX_LABELS = 5000


def _deny(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "LAB_REJECTED_UNVERIFIED_D1_TIME_LABEL",
            "reason": reason, "utc_bar_open_labels": [],
            "requested_utc_controls_daily_timezone": False,
            "bar_close_time_verified": False,
            "market_session_mapping_verified": False,
            "provider_response_independently_verified": False,
            "can_feed_bias": False, "can_feed_oos": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False}


def _local_to_utc(label: Any, zone: ZoneInfo) -> datetime | None:
    if not isinstance(label, str) or len(label) != 19:
        return None
    try:
        naive = datetime.strptime(label, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    # Reject nonexistent or ambiguous local clocks, rather than silently
    # choosing an arbitrary DST fold. For other instants both folds agree.
    possibilities = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        utc_dt = aware.astimezone(timezone.utc)
        back = utc_dt.astimezone(zone).replace(tzinfo=None)
        if back == naive:
            possibilities.add(utc_dt)
    if len(possibilities) != 1:
        return None
    return next(iter(possibilities))


def audit_synthetic_twelve_d1_time_labels_lab(
    payload: Any, *, at: datetime,
) -> dict[str, Any]:
    """Inspect original-looking local D1 bar labels without claiming closes.

    This is explicitly NOT a parser accepting live provider data: only
    LAB_SYNTHETIC_TWELVE_D1 fixtures are allowed. No OHLC leaves the module.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Evaluation time must have explicit timezone")
    now = at.astimezone(timezone.utc)
    if not isinstance(payload, Mapping):
        return _deny("Missing synthetic source envelope")
    if (payload.get("state") != "LAB_SYNTHETIC_TWELVE_D1"
            or payload.get("interval") != "1day"
            or payload.get("asset_class") != "forex"):
        return _deny("Only explicitly synthetic Forex D1 labels accepted")
    meta = payload.get("meta")
    if not isinstance(meta, Mapping):
        return _deny("Missing exchange timezone metadata")
    zone_name = meta.get("exchange_timezone")
    if not isinstance(zone_name, str) or len(zone_name) > 80:
        return _deny("Missing exchange_timezone; request timezone cannot substitute")
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return _deny("Invalid IANA exchange timezone")
    labels = payload.get("values")
    if not isinstance(labels, list) or not 1 <= len(labels) <= MAX_LABELS:
        return _deny("No bounded D1 labels provided")
    converted = []
    previous = None
    for item in labels:
        if not isinstance(item, Mapping):
            return _deny("Invalid bar-label item")
        stamp = _local_to_utc(item.get("datetime"), zone)
        if stamp is None:
            return _deny("Ambiguous, nonexistent or invalid local D1 time")
        if stamp > now:
            return _deny("Future daily label")
        if previous is not None and stamp <= previous:
            return _deny("Unordered/duplicate daily labels")
        converted.append({
            "provider_local_bar_label": item["datetime"],
            "calculated_utc_bar_open_label": stamp.isoformat(),
            "bar_close_time_verified": False,
            "price_available_at_this_label_verified": False,
        })
        previous = stamp
    return {"schema": SCHEMA, "state": "LAB_LOCAL_LABEL_CONVERSION_ONLY",
            "metadata_exchange_timezone": zone_name,
            "requested_timezone_ignored_for_daily": True,
            "requested_utc_controls_daily_timezone": False,
            "utc_bar_open_labels": converted,
            "count": len(converted),
            "bar_close_time_verified": False,
            "market_session_mapping_verified": False,
            "provider_response_independently_verified": False,
            "can_feed_bias": False, "can_feed_oos": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False,
            "reason": "Datetime label conversion is not proof of session close,"
                      " actual availability, market source or licensing."}


__all__ = ["SCHEMA", "audit_synthetic_twelve_d1_time_labels_lab"]
