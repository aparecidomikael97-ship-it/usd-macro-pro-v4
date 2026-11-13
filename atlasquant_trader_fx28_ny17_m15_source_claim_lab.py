"""Documentary M15/NY17 price-label origin contract for FX28 LAB.

This checks ONLY local report declarations. It does not attest a broker,
historial original bytes, first-seen vintage, or that missing nominal
Sunday NY17 candles existed. Use in the archive roster, frozen campaign
census and forecast/outcome join: W1/D1 native terminal candles must NEVER
replace the predeclared NY17 M15 boundary labels, even when close matches.

No filesystem, MT5, network, timestamp inference, trading or alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SCHEMA = "ATLASQUANT_FX28_FROZEN_NY17_M15_ENDPOINT_CLAIM_LAB_V1"
FROZEN_BASIS = "NY17_17_ET_FROZEN"
SOURCE_TIMEFRAME = "M15"
EXPECTED_KEYS = frozenset((
    "source_timeframe_claim",
    "price_window_basis_claim",
    "expected_first_m15_open_utc",
    "expected_last_m15_open_utc",
    "expected_last_m15_close_utc",
    "native_mt5_d1_or_w1_used_as_endpoint",
))


def expected_ny17_m15_endpoint_claim_lab(
    *, start_at_utc: datetime, end_at_utc: datetime,
) -> dict[str, Any]:
    """Build ONLY the exact expected boundary metadata; not broker evidence."""
    if (not isinstance(start_at_utc, datetime)
            or not isinstance(end_at_utc, datetime)
            or start_at_utc.tzinfo is None
            or end_at_utc.tzinfo is None
            or start_at_utc.utcoffset() is None
            or end_at_utc.utcoffset() is None):
        raise ValueError("NY17_BOUNDARY_CLOCK_NOT_AWARE")
    start = start_at_utc.astimezone(timezone.utc)
    end = end_at_utc.astimezone(timezone.utc)
    if (start.microsecond or end.microsecond
            or start.minute != 0 or end.minute != 0
            or start.second or end.second
            or not start < end
            or (end - start) not in (
                timedelta(days=1), timedelta(days=5),
            )):
        raise ValueError("NY17_BOUNDARIES_INVALID")
    return {
        "source_timeframe_claim": SOURCE_TIMEFRAME,
        "price_window_basis_claim": FROZEN_BASIS,
        "expected_first_m15_open_utc": start.isoformat(),
        "expected_last_m15_open_utc": (
            end - timedelta(minutes=15)).isoformat(),
        "expected_last_m15_close_utc": end.isoformat(),
        "native_mt5_d1_or_w1_used_as_endpoint": False,
    }


def has_exact_ny17_m15_endpoint_claim_lab(
    row: Any, *, start_at_utc: datetime, end_at_utc: datetime,
) -> bool:
    """Reject absent/altered claims, not certify source bytes or actual M15."""
    if type(row) is not dict or not EXPECTED_KEYS <= set(row):
        return False
    try:
        expected = expected_ny17_m15_endpoint_claim_lab(
            start_at_utc=start_at_utc, end_at_utc=end_at_utc)
    except (ValueError, TypeError, OverflowError):
        return False
    return all(type(row[k]) is type(value) and row[k] == value
               for k, value in expected.items())


__all__ = (
    "SCHEMA", "FROZEN_BASIS", "SOURCE_TIMEFRAME",
    "EXPECTED_KEYS", "expected_ny17_m15_endpoint_claim_lab",
    "has_exact_ny17_m15_endpoint_claim_lab",
)
