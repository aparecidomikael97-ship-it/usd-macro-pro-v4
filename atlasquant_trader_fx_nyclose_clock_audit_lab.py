"""Read-only research check of FX D1/W1 bar time markers against NY 17:00.

Reference: Pepperstone's public statement about GMT+2/3 NY-close daily
candles. This is a *clock-pattern discrepancy diagnostic*, not broker-server
identification. MT5 bar labels may have platform/server conventions that must
be confirmed on the original terminal. No guessed offsets or date rewriting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any
import re

from atlasquant_instrument_registry import FX_28

SCHEMA = "ATLASQUANT_FX_NY_CLOSE_BAR_CLOCK_REFERENCE_LAB_V1"
REFERENCE = "PEPPERSTONE_PUBLIC_NEW_YORK_17H_CLOSE_REFERENCE"
REFERENCE_URL = "https://pepperstone.com/en-gb/about-us/trading-hours"
BAR_FRAMES = frozenset(("D1", "W1"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_SAMPLES = 120


@dataclass(frozen=True)
class FxClockSample:
    symbol: str
    timeframe: str
    bar_open_at_utc: datetime
    snapshot_observed_at_utc: datetime
    csv_sha256_claim: str


def _clock(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BAR_CLOCK_BLOCKED",
        "reason": reason, "reference": REFERENCE,
        "reference_url": REFERENCE_URL,
        "sample_count": 0, "frames_seen": [], "match_count": 0,
        "discrepancy_count": 0, "samples": [],
        "reference_is_official_but_specific_mt5_server_not_verified": True,
        "sample_source_sha_claims_independently_checked": False,
        "pepperstone_server_association_verified": False,
        "broker_identity_verified": False,
        "bar_label_equals_actual_session_open_verified": False,
        "broker_calendar_verified": False,
        "price_vintage_pit_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def audit_fx_nyclose_clock_lab(samples: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Compare *supplied* MT5 UTC bar labels with NY 17h conventions.

    A mismatch requires investigating the *actual* feed and server clock;
    it does NOT imply a missing bar or authorize shifting timestamps.
    Even matching samples cannot establish historical availability, source
    authenticity or market accuracy. Partial D1/W1 coverage is insufficient.
    """
    out = _result("INVALID_CLOCK_OR_SAMPLE_COLLECTION")
    now = _clock(as_of_utc)
    if (now is None or not isinstance(samples, (list, tuple))
            or not 2 <= len(samples) <= MAX_SAMPLES):
        return out
    try:
        ny = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        out["reason"] = "NY_TIMEZONE_DATABASE_NOT_AVAILABLE"
        return out

    keys: set[tuple[str, str, datetime]] = set()
    rows: list[dict[str, Any]] = []
    frames = set()
    for x in samples:
        if not isinstance(x, FxClockSample):
            out["reason"] = "INVALID_CLOCK_SAMPLE_TYPE"
            return out
        stamp, captured = _clock(x.bar_open_at_utc), _clock(x.snapshot_observed_at_utc)
        if (not isinstance(x.symbol, str) or x.symbol not in FX_28
                or x.timeframe not in BAR_FRAMES
                or not isinstance(x.csv_sha256_claim, str)
                or _HASH.fullmatch(x.csv_sha256_claim) is None
                or stamp is None or captured is None
                or not stamp < captured <= now):
            out["reason"] = "INVALID_SAMPLE_PROVENANCE_OR_CHRONOLOGY"
            return out
        key = (x.symbol, x.timeframe, stamp)
        if key in keys:
            out["reason"] = "DUPLICATED_SAMPLE"
            return out
        keys.add(key)
        frames.add(x.timeframe)
        local = stamp.astimezone(ny)
        # A New York 17:00 session belongs to Sun-Thu (daily); for the
        # next FX week it starts on Sunday. No holiday certification here.
        day_ok = (local.weekday() == 6 if x.timeframe == "W1"
                  else local.weekday() in (6, 0, 1, 2, 3))
        time_ok = (local.hour, local.minute, local.second) == (17, 0, 0)
        matches = bool(day_ok and time_ok)
        row = {
            "symbol": x.symbol, "timeframe": x.timeframe,
            "bar_open_utc": stamp.isoformat(),
            "bar_open_new_york": local.isoformat(),
            "snapshot_observed_utc_claim": captured.isoformat(),
            "csv_sha256_claim": x.csv_sha256_claim,
            "reference_pattern_match": matches,
            "clock_status": ("NY_CLOSE_PATTERN_MATCH_UNATTESTED" if matches
                            else "NY_CLOSE_PATTERN_DISCREPANCY_NEEDS_SERVER_REVIEW"),
            "broker_source_authenticated": False,
            "clock_shift_or_candle_imputation_authorized": False,
        }
        rows.append(row)
    rows.sort(key=lambda r: (r["timeframe"], r["symbol"], r["bar_open_utc"]))
    disagreements = sum(not r["reference_pattern_match"] for r in rows)
    out.update({
        "sample_count": len(rows), "frames_seen": sorted(frames),
        "match_count": len(rows) - disagreements,
        "discrepancy_count": disagreements, "samples": rows,
        "state": ("LAB_SESSION_CLOCK_REFERENCE_DISCREPANCY_REVIEW"
                  if disagreements else "LAB_NYCLOSE_REFERENCE_MATCH_UNATTESTED"),
        "reason": ("BAR_LABELS_NOT_ALIGNED_WITH_PUBLIC_NY_CLOSE_PATTERN"
                   if disagreements else "REFERENCE_MATCH_NOT_BROKER_PROOF"),
    })
    if frames != BAR_FRAMES:
        out["state"] = "LAB_BAR_CLOCK_BLOCKED"
        out["reason"] = "D1_W1_BOTH_REQUIRED_TO_ASSESS_COHORT"
    return out


__all__ = ["SCHEMA", "REFERENCE", "REFERENCE_URL", "FxClockSample", "audit_fx_nyclose_clock_lab"]
