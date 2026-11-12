"""AtlasQuant FX D1 cross-asset calendar completeness, offline LAB only.

A complete 28-pair D1 date can support descriptive research, NOT accuracy,
tradability or causal validation. A single missing date is quarantined; shared
closures cannot be called verified broker holidays from CSV data alone.
No synthetic candles, model fitting, trading, or network requests.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

SCHEMA = "ATLASQUANT_FX_D1_CROSS_ASSET_CALENDAR_GATE_LAB_V1"

def inspect_d1_date_coverage_lab(
    *, trading_date: Any, present_symbols: Any, expected_symbols: tuple[str, ...],
) -> dict[str, Any]:
    result = {
        "schema": SCHEMA, "date": None,
        "status": "LAB_D1_CALENDAR_BLOCKED",
        "observed_count": 0, "missing_count": None,
        "missing_symbols": None, "rank_28fx_coverage_complete": False,
        "trading_calendar_independently_verified": False,
        "historical_broker_source_independently_verified": False,
        "out_of_sample_accuracy_verified": False,
        "single_pair_backtest_authorized": False,
        "unrestricted_backtest_authorized": False,
        "imputation_allowed": False,
        "direction_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "research_only": True,
    }
    if (not isinstance(trading_date, date)
            or type(trading_date) is not date
            or not isinstance(expected_symbols, tuple)
            or len(expected_symbols) != 28
            or len(set(expected_symbols)) != 28
            or not all(isinstance(x, str) and len(x) == 6 for x in expected_symbols)
            or not isinstance(present_symbols, (tuple, list, set, frozenset))
            or any(not isinstance(s, str) for s in present_symbols)):
        result["reason"] = "INVALID_CALENDAR_OR_COHORT"
        return result
    present = list(present_symbols)
    if len(set(present)) != len(present) or not set(present).issubset(expected_symbols):
        result["reason"] = "UNKNOWN_OR_DUPLICATE_D1_SYMBOL"
        return result
    missing = [s for s in expected_symbols if s not in present]
    n = len(present)
    result.update({
        "date": trading_date.isoformat(),
        "observed_count": n,
        "missing_count": len(missing),
        "missing_symbols": missing,
    })
    if n == 28:
        status = "LAB_ALL_28_D1_BARS_PRESENT_DOCUMENTARY_UNATTESTED"
        result["rank_28fx_coverage_complete"] = True
    elif n == 27:
        status = "LAB_SINGLE_PAIR_D1_MISSING_DATE_QUARANTINE"
    elif n == 0:
        status = "LAB_SHARED_28FX_NO_D1_BARS_CALENDAR_UNVERIFIED"
    else:
        status = "LAB_PARTIAL_D1_COHORT_CALENDAR_UNVERIFIED"
    result["status"] = status
    result["reason"] = "LOCAL_DATE_COVERAGE_ONLY_NOT_BROKER_SCHEDULE"
    return result

__all__ = ["SCHEMA", "inspect_d1_date_coverage_lab"]
