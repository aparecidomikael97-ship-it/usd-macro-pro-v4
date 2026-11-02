"""FX macro surprise: point-in-time synthetic evidence for AtlasQuant Trader LAB.

The event contract distinguishes previous vintage, pre-release consensus,
scheduled release, and captured actual. It can create a MACRO_SCHEDULE_ONLY
or MACRO_ACTUAL_RELEASED evidence for the existing daily freeze contract,
without treating a surprise as mechanically bullish/bearish for a currency.

Never fetches an API, verifies a vendor, proves historical custody, opens
trades, schedules workers, or asserts statistical market advantage.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from math import isfinite
import re
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES

SCHEMA = "ATLASQUANT_TRADER_MACRO_SURPRISE_PIT_LAB_V1"
INDICATORS = frozenset((
    "CPI", "HICP", "CORE_CPI", "PCE", "CORE_PCE", "PPI",
    "NFP", "ADP", "UNEMPLOYMENT", "WAGES",
    "POLICY_RATE", "GDP", "PMI", "ISM",
))
UNITS = frozenset(("PERCENT", "PERCENT_POINT", "THOUSANDS", "INDEX", "BPS"))
PRE_KEYS = frozenset((
    "state", "event_id", "currency", "indicator_id", "unit", "source",
    "previous", "previous_captured_at_utc",
    "consensus", "consensus_captured_at_utc",
    "scheduled_release_at_utc", "deadband_predeclared",
))
ACTUAL_KEYS = frozenset((
    "state", "event_id", "actual", "released_at_utc",
    "captured_at_utc", "source",
))
IDENTITY = re.compile(r"^[A-Za-z0-9:_-]{3,90}$")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo is not None else None


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        n = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return n if isfinite(n) and abs(n) <= 1e9 else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_EVENT_REJECTED",
        "reason": reason, "freeze_evidence": None, "surprise": None,
        "actual_released_at_cutoff": False,
        "macro_currency_direction": "UNDETERMINED",
        "provider_attested": False, "immutable_receipt_attested": False,
        "real_macro_history_verified": False, "predictive_edge_proven": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def build_macro_point_in_time_evidence_lab(
    preliminary: Any, actual_release: Any = None, *,
    forecast_issued_at: datetime, evaluated_at: datetime,
) -> dict[str, Any]:
    """Return exactly one synthetic freeze evidence, or reject.

    Supplying a future actual alongside a pre-release forecast is refused
    instead of quietly ignoring the value; caller must run a PRE-only
    scenario to avoid leaking the result into a historic forecast.
    """
    if (not isinstance(forecast_issued_at, datetime)
            or forecast_issued_at.tzinfo is None
            or not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None):
        raise ValueError("Forecast and evaluation instants require explicit timezone")
    cutoff = forecast_issued_at.astimezone(timezone.utc)
    now = evaluated_at.astimezone(timezone.utc)
    if cutoff > now:
        return _blocked("Forecast issuance is after evaluation instant")
    if not isinstance(preliminary, Mapping) or set(preliminary) != PRE_KEYS:
        return _blocked("Missing, unexpected or post-hoc pre-release snapshot field")
    if preliminary.get("state") != "LAB_SYNTHETIC_MACRO_PRE":
        return _blocked("Only explicitly synthetic pre-release events are permitted")
    event_id, currency, indicator = (preliminary.get("event_id"),
                                      preliminary.get("currency"),
                                      preliminary.get("indicator_id"))
    if (not isinstance(event_id, str) or not IDENTITY.fullmatch(event_id)
            or not isinstance(currency, str) or currency not in CURRENCIES
            or not isinstance(indicator, str) or indicator not in INDICATORS
            or not isinstance(preliminary.get("unit"), str)
            or preliminary["unit"] not in UNITS):
        return _blocked("Unsupported identity, currency, indicator or measurement unit")
    source = preliminary.get("source")
    if not isinstance(source, str) or not 2 <= len(source.strip()) <= 120:
        return _blocked("Pre-release consensus needs a named synthetic source")
    prev, consensus, deadband = (
        _numeric(preliminary.get("previous")),
        _numeric(preliminary.get("consensus")),
        _numeric(preliminary.get("deadband_predeclared")),
    )
    if prev is None or consensus is None or deadband is None or deadband < 0 or deadband > 1e6:
        return _blocked("Pre-release figures/deadband are invalid or unbounded")
    prev_captured = _utc(preliminary.get("previous_captured_at_utc"))
    expected_captured = _utc(preliminary.get("consensus_captured_at_utc"))
    scheduled = _utc(preliminary.get("scheduled_release_at_utc"))
    if (prev_captured is None or expected_captured is None or scheduled is None
            or not prev_captured <= expected_captured <= cutoff
            or not expected_captured < scheduled):
        return _blocked("Previous vintage or consensus was not known before release/cutoff")
    # The pre-snapshot is not proof that original data actually existed at
    # those timestamps; its provenance remains solely caller-controlled.
    common = {
        "state": "LAB_SYNTHETIC_EVIDENCE", "evidence_id": event_id,
        "currency": currency, "indicator_id": indicator,
        "unit": preliminary["unit"], "source": source,
        "previous": prev, "consensus": consensus,
        "deadband_predeclared": deadband,
        "previous_captured_at_utc": prev_captured.isoformat(),
        "consensus_captured_at_utc": expected_captured.isoformat(),
        "scheduled_release_at_utc": scheduled.isoformat(),
        "market_impact_direction": "UNDETERMINED",
        "real_point_in_time_verified": False,
        "trade_authorized": False,
    }
    if actual_release is None:
        if scheduled <= cutoff:
            return _blocked("Historical release already scheduled; actual absent")
        evidence = {
            **common, "kind": "MACRO_SCHEDULE_ONLY",
            "data_as_of_utc": expected_captured.isoformat(),
            "captured_at_utc": expected_captured.isoformat(),
            "released_at_utc": scheduled.isoformat(),
        }
        return {
            "schema": SCHEMA, "state": "LAB_MACRO_FUTURE_SCHEDULE_ONLY",
            "freeze_evidence": evidence,
            "surprise": None, "actual_released_at_cutoff": False,
            "macro_currency_direction": "UNDETERMINED",
            "provider_attested": False, "immutable_receipt_attested": False,
            "real_macro_history_verified": False, "predictive_edge_proven": False,
            "trade_authorized": False, "worker_enabled": False,
            "scheduler_enabled": False,
        }
    if not isinstance(actual_release, Mapping) or set(actual_release) != ACTUAL_KEYS:
        return _blocked("Unexpected or incomplete actual-release record")
    if (actual_release.get("state") != "LAB_SYNTHETIC_MACRO_ACTUAL"
            or actual_release.get("event_id") != event_id):
        return _blocked("Actual-release identity or state is inconsistent")
    actual_source = actual_release.get("source")
    if not isinstance(actual_source, str) or not 2 <= len(actual_source.strip()) <= 120:
        return _blocked("Actual publication needs a named synthetic source")
    actual_value = _numeric(actual_release.get("actual"))
    released = _utc(actual_release.get("released_at_utc"))
    received = _utc(actual_release.get("captured_at_utc"))
    if actual_value is None or released is None or received is None:
        return _blocked("Actual value or timestamps are invalid")
    if (released < scheduled - timedelta(hours=12)
            or released > scheduled + timedelta(hours=48)):
        return _blocked("Actual release differs substantially from planned schedule")
    if (not scheduled > expected_captured or not released >= expected_captured
            or not released <= received <= cutoff):
        return _blocked("Actual release/receipt occurred after forecast or before consensus")
    delta = actual_value - consensus
    if not isfinite(delta) or abs(delta) > 1e9:
        return _blocked("Invalid numeric difference")
    if delta > deadband:
        relationship = "ABOVE_CONSENSUS"
    elif delta < -deadband:
        relationship = "BELOW_CONSENSUS"
    else:
        relationship = "IN_LINE_WITH_CONSENSUS"
    evidence = {
        **common, "kind": "MACRO_ACTUAL_RELEASED",
        "data_as_of_utc": released.isoformat(),
        "released_at_utc": released.isoformat(),
        "captured_at_utc": received.isoformat(),
        "actual": actual_value,
        "actual_source": actual_source,
        "surprise": delta,
        "surprise_comparison": relationship,
    }
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_RELEASED_SYNTHETIC",
        "freeze_evidence": evidence,
        "surprise": delta,
        "surprise_comparison": relationship,
        "actual_released_at_cutoff": True,
        "macro_currency_direction": "UNDETERMINED",
        "provider_attested": False, "immutable_receipt_attested": False,
        "real_macro_history_verified": False, "predictive_edge_proven": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "A raw above/below consensus reading cannot prove "
                   "hawkish/dovish policy implications or FX price reaction.",
    }


__all__ = [
    "SCHEMA", "INDICATORS", "UNITS",
    "build_macro_point_in_time_evidence_lab",
]
