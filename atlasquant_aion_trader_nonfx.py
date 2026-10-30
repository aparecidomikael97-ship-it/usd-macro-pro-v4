"""A275: opt-in, offline AION Trader read overlay for Radar non-FX symbols.

The Radar's existing symbols are presentation references, NOT provider
tickers or live tradeable contracts. WIN and WDO are unresolved future roots.
No fetch, resample, signal, broker, alert, orders, or independent attestation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_radar_board import INDEX_UNIVERSE
from atlasquant_aion_trader_timeframes import (
    PERIOD_MINUTES, NO_SEPARATE, INVALID, classify_tf,
)

SCHEMA = "ATLASQUANT_AION_NONFX_READ_ONLY_OVERLAY_LAB_V1"
WATCHLIST = tuple(INDEX_UNIVERSE)
SYMBOLS = tuple(symbol for symbol, _label in WATCHLIST)
FUTURE_ROOTS = frozenset(("WIN", "WDO"))
assert len(SYMBOLS) == 7 and len(set(SYMBOLS)) == 7


def nonfx_readonly_overlay(
    evidence: Any = None, *, now: datetime | None = None,
) -> dict:
    """Classify caller-supplied candles without promoting them to proof.

    `None` explicitly builds an empty scaffold. Malformed or unknown
    packages invalidate the overlay instead of pretending current prices.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware native datetime required")
    now = now.astimezone(timezone.utc)
    root_valid = (
        evidence is None
        or (type(evidence) is dict
            and len(evidence) <= len(SYMBOLS)
            and all(type(key) is str and key in SYMBOLS for key in evidence))
    )
    supplied = evidence if type(evidence) is dict and root_valid else {}
    coverage = {tf: 0 for tf in PERIOD_MINUTES}
    rows = []

    for symbol, label in WATCHLIST:
        statuses = {tf: NO_SEPARATE for tf in PERIOD_MINUTES}
        if not root_valid:
            statuses = {tf: INVALID for tf in PERIOD_MINUTES}
        elif symbol in supplied:
            periods = supplied[symbol]
            if (type(periods) is not dict
                    or any(type(tf) is not str or tf not in PERIOD_MINUTES
                           for tf in periods)):
                statuses = {tf: INVALID for tf in PERIOD_MINUTES}
            else:
                for tf, candles in periods.items():
                    status, _last_close = classify_tf(candles, tf, now=now)
                    statuses[tf] = status

        for tf, status in statuses.items():
            if status == "INPUT_FRESH_CLOSED_" + tf + "_UNATTESTED":
                coverage[tf] += 1
        is_future = symbol in FUTURE_ROOTS
        rows.append({
            "symbol": symbol,
            "label": label,
            "asset_class": "FUTURE_ROOT" if is_future else "INDEX_REFERENCE",
            "provider_mapping_verified": False,
            "specific_contract_expiry_selected": False,
            "timeframes": statuses,
            "recommendation": "NONE_READ_ONLY",
            "authorizes_order": False,
        })

    return {
        "schema": SCHEMA,
        "source": "EXISTING_RADAR_INDEX_UNIVERSE_PRESENTATION_ONLY",
        "generated_at": now.isoformat(),
        "universe": "NON_FX_7_PRESENTATION_IDS",
        "expected_symbols": len(SYMBOLS),
        "rows": rows,
        "mtf_coverage": coverage,
        "mtf_coverage_is_external_attestation": False,
        "input_root_valid": root_valid,
        "provider_symbols_authenticated": False,
        "futures_expiry_resolved": False,
        "no_orders": True,
        "no_alerts": True,
        "no_new_data_calls": True,
        "authorizes_send": False,
        "p0_homologated": 0,
    }


__all__ = ["SCHEMA", "WATCHLIST", "SYMBOLS", "FUTURE_ROOTS",
           "nonfx_readonly_overlay"]
