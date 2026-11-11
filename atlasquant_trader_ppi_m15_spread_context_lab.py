"""Read-only PPI M15 spread context; never an executable transaction-cost estimate.

MT5 `spread` is in terminal/broker points and may be zero, missing indicative
bid/ask history, or broker-specific. No point-size, ask stream, commission,
slippage, liquidity, causal significance or profit is attested by OHLC bars.
All seven complete CSV files must first pass the frozen PPI M15 archive gate.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    ClaimedLocalPriceArchive, LAST_REQUIRED_CLOSE_UTC, USD_FX,
    ROWS_REQUIRED, MAX_CSV_BYTES, FIELDS, HEX,
    inspect_ppi_fx_m15_forward_reaction_lab,
)

SCHEMA = "ATLASQUANT_TRADER_PPI_M15_SPREAD_CONTEXT_LAB_V1"
EXPECTED_PRICE = "LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO"
PASS = "LAB_PPI_7PAIR_SPREAD_DOCUMENTARY_NO_EXECUTION_CLAIM"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PPI_SPREAD_CONTEXT_BLOCKED",
        "reason": reason, "per_pair_spread_points": None,
        "pair_count_documentary": 0,
        "all_spread_points_zero_for_any_pair": None,
        "all_seven_price_hashes_revalidated": False,
        "mt5_point_size_or_digits_independently_verified": False,
        "historical_bid_ask_quotes_independently_verified": False,
        "broker_execution_spread_verified": False,
        "commission_slippage_or_total_cost_verified": False,
        "profit_or_net_return_calculated": False,
        "operational_bias": "AGUARDAR", "validated_accuracy": None,
        "calibrated_probability": None, "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _one_spread_series(root: Path, symbol: str, expected_sha256: str) -> list[int]:
    file = root / f"{symbol}_PPI_20261113_M15.csv"
    if (file.is_symlink() or not file.is_file()
            or file.stat().st_size > MAX_CSV_BYTES):
        raise ValueError("PRICE_ARCHIVE_UNSAFE_OR_MISSING")
    raw = file.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("SPREAD_SOURCE_DIGEST_CHANGED_BETWEEN_READS")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8", "strict"), newline=""))
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("SPREAD_FIELDS_CHANGED")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("SPREAD_SOURCE_PARSE_FAILED") from exc
    if len(rows) != ROWS_REQUIRED:
        raise ValueError("SPREAD_ROWS_CHANGED")
    points: list[int] = []
    for row in rows:
        if (None in row or len(row) != len(FIELDS)
                or any(v is None for v in row.values())
                or not row["spread"].isascii() or not row["spread"].isdigit()):
            raise ValueError("INVALID_OR_MISSING_SPREAD_FIELD")
        points.append(int(row["spread"]))
    return points


def inspect_ppi_m15_spread_context_lab(
    *, archive_root: Any, receipt: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Document per-symbol broker point values only after all price checks pass.

    Comparable spread ratios may be computed *within one pair only*. A raw
    spread of 20 points on USDJPY is not directly comparable to 20 on EURUSD.
    No arbitrary high-spread cutoff is treated as a calibrated risk threshold.
    """
    now = _utc(as_of_utc)
    if now is None or now < LAST_REQUIRED_CLOSE_UTC:
        return _deny("SPREAD_WINDOW_NOT_CLOSED_OR_INVALID_CLOCK")
    if (not isinstance(receipt, ClaimedLocalPriceArchive)
            or not isinstance(archive_root, (Path, str))
            or not isinstance(receipt.sha256_by_symbol, dict)
            or set(receipt.sha256_by_symbol) != set(USD_FX)
            or any(not isinstance(d, str) or HEX.fullmatch(d) is None
                   for d in receipt.sha256_by_symbol.values())):
        return _deny("FULL_SEVEN_PAIR_SPREAD_RECEIPT_REQUIRED")
    price = inspect_ppi_fx_m15_forward_reaction_lab(
        archive_root=archive_root, receipt=receipt, as_of_utc=now)
    if price["state"] != EXPECTED_PRICE:
        return _deny("SEVEN_PAIR_M15_OHLC_OR_HASH_GATE_REJECTED")
    root = Path(archive_root)
    stats: dict[str, dict[str, Any]] = {}
    for symbol in USD_FX:
        try:
            series = _one_spread_series(root, symbol, receipt.sha256_by_symbol[symbol])
        except (ValueError, OSError, OverflowError):
            return _deny("SPREAD_ARCHIVE_REVALIDATION_FAILED")
        baseline = series[0]
        post = series[1:]  # release bar at 13:30-13:45 UTC through +4h
        ordered = sorted(post)
        median = Decimal(ordered[7] + ordered[8]) / Decimal(2)
        ratio = (str((Decimal(max(post)) / Decimal(baseline)).quantize(Decimal("0.001")))
                 if baseline else None)
        stats[symbol] = {
            "baseline_m15_spread_points": baseline,
            "first_post_release_m15_spread_points": post[0],
            "post_release_four_hour_peak_spread_points": max(post),
            "post_release_four_hour_median_spread_points": str(median),
            "peak_over_baseline_same_pair_only": ratio,
            "zero_spread_rows_in_17_candles": series.count(0),
            "zero_could_mean_missing_or_unavailable_quote": bool(0 in series),
        }
    result = _deny("MT5_BAR_SPREAD_POINTS_NOT_EXECUTABLE_BID_ASK_OR_NET_RETURN")
    result.update({
        "state": PASS,
        "per_pair_spread_points": stats,
        "pair_count_documentary": len(stats),
        "all_spread_points_zero_for_any_pair": any(
            row["zero_spread_rows_in_17_candles"] == ROWS_REQUIRED for row in stats.values()),
        "all_seven_price_hashes_revalidated": True,
    })
    return result


__all__ = ["SCHEMA", "PASS", "inspect_ppi_m15_spread_context_lab"]
