"""Fail-closed coverage contract for the AtlasQuant 28-pair FX scanner."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from atlasquant_instrument_registry import FX_28

@dataclass(frozen=True)
class PairCoverage:
    symbol: str
    analyzed: bool
    data_fresh: bool
    quality_ok: bool
    updated_at: datetime | None = None

def scanner_coverage(rows: Mapping[str, PairCoverage]) -> dict[str, object]:
    expected = set(FX_28)
    received = set(rows)
    missing = sorted(expected - received)
    unexpected = sorted(received - expected)
    healthy: list[str] = []
    unhealthy: list[str] = []
    now = datetime.now(timezone.utc)

    for symbol in FX_28:
        row = rows.get(symbol)
        if row is None:
            continue
        if row.analyzed and row.data_fresh and row.quality_ok:
            healthy.append(symbol)
        else:
            unhealthy.append(symbol)

    complete = not missing and not unexpected and len(healthy) == 28
    # UI is only allowed to claim "28/28 monitored" when complete is True.
    return {
        "expected": 28,
        "received": len(received & expected),
        "healthy": len(healthy),
        "complete": complete,
        "claim_28_of_28": complete,
        "missing": missing,
        "unhealthy": unhealthy,
        "unexpected": unexpected,
        "checked_at": now.isoformat(),
    }
