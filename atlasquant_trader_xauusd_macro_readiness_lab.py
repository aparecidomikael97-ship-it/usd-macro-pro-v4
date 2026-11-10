"""XAU/USD macro driver evidence gate, separate from the 28 G8 FX crosses.

Official FRED series definitions are labels only here. Caller-provided values,
publication times and hashes are UNAUTHENTICATED; even fully populated test
receipts must never generate a direction, probability, order or bias alert.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from atlasquant_instrument_registry import GOLD_REFERENCE, get_gold_reference

SCHEMA = "ATLASQUANT_TRADER_XAUUSD_MACRO_DRIVER_READINESS_LAB_V1"
HORIZONS = ("D1", "W1", "M1")
DRIVER_SPECS = {
    "US_REAL_YIELD_10Y": ("FRED_DFII10", "PERCENT_ANNUAL", "D1", 7 * 86400),
    "US_BROAD_DOLLAR": ("FRED_DTWEXBGS", "INDEX_JAN2006_100", "D1", 14 * 86400),
    "XAUUSD_BROKER_PRICE": ("PEPPERSTONE_MT5_XAUUSD", "USD_PER_TROY_OUNCE", "M15", 3600),
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DATE = re.compile(r"20\d\d-\d\d-\d\d\Z")
_STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_SIGNED = re.compile(r"[+-]?[0-9]{1,4}(?:\.[0-9]{1,6})?\Z")


@dataclass(frozen=True)
class GoldDriverClaim:
    driver: str
    source_id: str
    unit: str
    sampling: str
    observation_label: str
    value_claim: str
    published_at: datetime
    captured_at: datetime
    original_sha256_claim: str


def _utc(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _observation_clock(label: Any, sampling: str) -> datetime | None:
    if not isinstance(label, str):
        return None
    try:
        if sampling == "D1" and _DATE.fullmatch(label):
            return datetime.fromisoformat(label).replace(tzinfo=timezone.utc)
        if sampling == "M15" and _STAMP.fullmatch(label):
            stamp = datetime.fromisoformat(label[:-1] + "+00:00")
            if stamp.minute % 15 == 0 and stamp.second == 0:
                return stamp
    except ValueError:
        return None
    return None


def _number(value: Any, driver: str) -> Decimal | None:
    if not isinstance(value, str) or _SIGNED.fullmatch(value) is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    if driver == "US_REAL_YIELD_10Y":
        return number if Decimal("-25") <= number <= Decimal("25") else None
    return number if number > 0 else None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_DRIVER_READINESS_BLOCKED",
        "reason": reason, "canonical_instrument": GOLD_REFERENCE.canonical_id,
        "separate_from_fx_28": True, "driver_states": {},
        "claimed_complete_drivers": 0, "missing_drivers": sorted(DRIVER_SPECS),
        "all_three_driver_claims_present": False,
        "news_and_geopolitics_authenticated": False,
        "macro_calendar_authenticated": False,
        "fred_series_responses_authenticated": False,
        "pepperstone_xauusd_bars_authenticated": False,
        "broker_contract_spec_verified": False,
        "source_clocks_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "driver_relationships_directionally_validated": False,
        "xauusd_bias": None, "score_0_to_10": None,
        "calibrated_probability": None, "validated_accuracy": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_xauusd_macro_driver_readiness_lab(
    receipts: Any, *, instrument: Any,
    horizon: Any, decision_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Check synthetic/caller-asserted source metadata, never XAU direction."""
    out = _blocked("INVALID_INSTRUMENT_HORIZON_OR_CLOCK")
    decision, evaluation = _utc(decision_at_utc), _utc(evaluated_at_utc)
    try:
        gold = get_gold_reference(instrument)
    except ValueError:
        return out
    if (gold is not GOLD_REFERENCE or horizon not in HORIZONS
            or decision is None or evaluation is None or decision > evaluation
            or not isinstance(receipts, (list, tuple)) or len(receipts) > 6):
        return out
    by_driver: dict[str, list[tuple[datetime, datetime]]] = {
        k: [] for k in DRIVER_SPECS}
    seen: set[tuple[str, str]] = set()
    for v in receipts:
        if not isinstance(v, GoldDriverClaim) or not isinstance(v.driver, str):
            out["reason"] = "INVALID_SOURCE_RECEIPT"
            return out
        spec = DRIVER_SPECS.get(v.driver)
        if (spec is None or (v.source_id, v.unit, v.sampling) != spec[:3]
                or not isinstance(v.original_sha256_claim, str)
                or _SHA.fullmatch(v.original_sha256_claim) is None):
            out["reason"] = "UNSUPPORTED_SOURCE_UNIT_OR_HASH_CLAIM"
            return out
        observed = _observation_clock(v.observation_label, v.sampling)
        published, captured = _utc(v.published_at), _utc(v.captured_at)
        if (observed is None or published is None or captured is None
                or not observed <= published <= captured <= decision
                or (v.sampling == "M15" and
                    published < observed + timedelta(minutes=15))):
            out["reason"] = "FUTURE_OR_INVALID_OBSERVATION_RELEASE_CAPTURE_TIME"
            return out
        if _number(v.value_claim, v.driver) is None:
            out["reason"] = "INVALID_DRIVER_VALUE_CLAIM"
            return out
        key = (v.driver, v.observation_label)
        if key in seen:
            out["reason"] = "DUPLICATE_DRIVER_OBSERVATION"
            return out
        seen.add(key)
        by_driver[v.driver].append((observed, captured))

    rows: dict[str, Any] = {}
    complete: list[str] = []
    for driver, spec in DRIVER_SPECS.items():
        stamps = sorted(by_driver[driver])
        valid_pair = len(stamps) == 2
        if len(stamps) not in (0, 1, 2):
            out["reason"] = "TOO_MANY_OBSERVATIONS_FOR_DRIVER"
            return out
        if valid_pair and stamps[0][0] >= stamps[1][0]:
            out["reason"] = "DRIVER_OBSERVATIONS_NOT_DISTINCT"
            return out
        if valid_pair and (decision - stamps[-1][0]).total_seconds() > spec[3]:
            out["reason"] = "CLAIMED_DRIVER_OBSERVATION_STALE_" + driver
            return out
        if valid_pair:
            complete.append(driver)
        rows[driver] = {
            "source_id_claim": spec[0], "unit": spec[1],
            "sampling": spec[2], "received_observations": len(stamps),
            "pair_of_claimed_observations_present": valid_pair,
            "latest_reference_utc_claim": stamps[-1][0].isoformat() if stamps else None,
            "issuer_or_broker_authenticated": False,
            "real_time_price_available": False,
            "directional_contribution_allowed": False,
        }
    missing = sorted(set(DRIVER_SPECS) - set(complete))
    out.update({
        "state": ("LAB_XAUUSD_THREE_DRIVER_CLAIMS_PRESENT_UNATTESTED"
                  if not missing else "LAB_XAUUSD_DRIVER_CLAIMS_INCOMPLETE"),
        "reason": ("ALL_THREE_CLAIMED_ONLY_NEWS_GEO_AND_SOURCE_TRUST_MISSING"
                   if not missing else "MISSING_TWO_OBSERVATIONS_PER_REQUIRED_DRIVER"),
        "driver_states": rows, "claimed_complete_drivers": len(complete),
        "missing_drivers": missing,
        "all_three_driver_claims_present": not missing,
    })
    return out


__all__ = ["SCHEMA", "DRIVER_SPECS", "GoldDriverClaim",
           "inspect_xauusd_macro_driver_readiness_lab"]
