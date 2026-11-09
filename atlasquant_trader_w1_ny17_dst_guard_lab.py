"""Fail-closed, documentary guard for weekly NY 17:00 daylight-saving boundaries.

An FX weekly bar anchored on Sunday 17:00 New York can span 167 or 169
hours when US DST changes. A nominal +604800-second close must not silently
stand in for an independently verified broker session close. This pure module
neither shifts market timestamps nor asserts a particular terminal's timezone.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any


def w1_ny17_dst_crossing_lab(start: Any, nominal_close: Any) -> bool | None:
    """True when a Sunday-17 NY weekly span changes UTC offset; None on error.

    Only NY17-aligned starts are tested against this *conditional* reference.
    A False return is NOT broker calendar, bar alignment or PIT proof.
    """
    if (not isinstance(start, datetime) or not isinstance(nominal_close, datetime)
            or start.tzinfo is None or nominal_close.tzinfo is None
            or start.utcoffset() is None or nominal_close.utcoffset() is None
            or not start < nominal_close):
        return None
    try:
        ny = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        return None
    local_start = start.astimezone(ny)
    local_close = nominal_close.astimezone(ny)
    if (local_start.weekday(), local_start.hour, local_start.minute,
            local_start.second, local_start.microsecond) != (6, 17, 0, 0, 0):
        return False
    return local_start.utcoffset() != local_close.utcoffset()


__all__ = ["w1_ny17_dst_crossing_lab"]
