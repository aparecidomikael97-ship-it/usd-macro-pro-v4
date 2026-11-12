"""Prospective PPI USD-FX M15 reaction measurement; offline / read-only LAB.

The cohort and windows are frozen before the 2026-11-13 US October PPI event.
No MT5 connection, credentials, automatic fetching, orders, or forecasts.
A local OHLC archive does NOT attest broker provenance or point-in-time access.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_PPI_USD_FX_M15_FORWARD_REACTION_LAB_V1"
EVENT_UTC = datetime(2026, 11, 13, 13, 30, tzinfo=timezone.utc)
M15 = timedelta(minutes=15)
USD_FX = ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD")
WINDOWS = (("M15", 15), ("H1", 60), ("H4", 240))
BASELINE_OPEN_UTC = EVENT_UTC - M15
LAST_REQUIRED_CLOSE_UTC = EVENT_UTC + timedelta(hours=4)
ROWS_REQUIRED = 17
MAX_CSV_BYTES = 30_000
FIELDS = ("time_utc_epoch", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
HEX = re.compile(r"[0-9a-f]{64}\Z")
PRICE = re.compile(r"[0-9]{1,7}(?:\.[0-9]{1,9})?\Z")
INTEGER = re.compile(r"[0-9]{1,12}\Z")

# Research-only; never substitute TE's proprietary forecast for the consensus.
TD_PRE_EVENT_HTML_SHA256 = "5f9d9eb128e5a3763ec6a3081bee7ba8c248a665a9d50e0ee132e9cbe037a42a"
TE_PRE_EVENT_HTML_SHA256 = "175c163514590db8e2ddd651f0c9865bd2eed298211f92072549233f670e23c0"
PRE_EVENT_HEADLINE_CONSENSUS_MOM = "0.4"
PRE_EVENT_CORE_CONSENSUS_MOM = "0.3"


@dataclass(frozen=True)
class ClaimedLocalPriceArchive:
    captured_at_utc: datetime
    sha256_by_symbol: dict[str, str]
    source_kind: str = "MT5_READONLY_M15_CSV_CLAIM_UNVERIFIED"


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _no_go(reason: str, *, state: str = "LAB_PPI_FX_REACTION_BLOCKED") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "event_release_utc": EVENT_UTC.isoformat(),
        "cohort_symbols": list(USD_FX), "window_minutes": [v for _,v in WINDOWS],
        "pre_event_consensus_mom_pct_claim": {
            "final_demand": PRE_EVENT_HEADLINE_CONSENSUS_MOM,
            "less_food_and_energy": PRE_EVENT_CORE_CONSENSUS_MOM,
        },
        "pre_event_source_hashes": {"td": TD_PRE_EVENT_HTML_SHA256, "te": TE_PRE_EVENT_HTML_SHA256},
        "price_reactions_usd_normalized_bps": None,
        "source_broker_independently_authenticated": False,
        "market_prices_original_capture_independently_attested": False,
        "event_first_release_outcome_authenticated": False,
        "prediction_precommitted_and_validated": False,
        "execution_bid_ask_and_slippage_verified": False,
        "statistical_causal_impact_identified": False,
        "independent_economic_event_sample_count": 0,
        "historical_out_of_sample_accuracy": None,
        "calibrated_probability": None, "directional_forecast": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _price_number(value: Any) -> Decimal | None:
    if not isinstance(value, str) or PRICE.fullmatch(value) is None:
        return None
    try:
        x = Decimal(value)
        return x if x.is_finite() and x > 0 else None
    except InvalidOperation:
        return None


def _read_m15(root: Path, symbol: str, expected_hash: str) -> dict[int, Decimal]:
    file = root / f"{symbol}_PPI_20261113_M15.csv"
    if not file.is_file() or file.is_symlink() or file.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("SERIES_MISSING_SYMLINK_OR_OVERSIZE")
    raw = file.read_bytes()
    if sha256(raw).hexdigest() != expected_hash:
        raise ValueError("ARCHIVE_RAW_SHA256_MISMATCH")
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8", "strict"), newline=""))
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("CSV_FIELDS_NOT_M15")
        records = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("CSV_DECODE_OR_PARSE_FAILED") from exc
    if len(records) != ROWS_REQUIRED:
        raise ValueError("ALL_17_CONTIGUOUS_M15_BARS_REQUIRED")
    prices: dict[int, Decimal] = {}
    for index, row in enumerate(records):
        if None in row or len(row) != len(FIELDS) or any(v is None for v in row.values()):
            raise ValueError("CSV_MALFORMED_ROW")
        epoch = row["time_utc_epoch"]
        if not isinstance(epoch, str) or not INTEGER.fullmatch(epoch):
            raise ValueError("BAD_M15_BAR_EPOCH")
        stamp = int(epoch)
        expected = int(BASELINE_OPEN_UTC.timestamp()) + index * 900
        if stamp != expected:
            raise ValueError("M15_GAP_DUPLICATE_OR_WRONG_EVENT_WINDOW")
        values = {field: _price_number(row[field]) for field in ("open", "high", "low", "close")}
        if any(v is None for v in values.values()):
            raise ValueError("INVALID_OHLC_PRICE")
        if values["low"] > min(values["open"], values["close"]) or values["high"] < max(values["open"], values["close"]) or values["low"] > values["high"]:
            raise ValueError("OHLC_RANGE_INCONSISTENT")
        for field in ("tick_volume", "spread", "real_volume"):
            v = row[field]
            if not isinstance(v, str) or not INTEGER.fullmatch(v):
                raise ValueError("INVALID_M15_VOLUME_OR_SPREAD")
        if int(row["tick_volume"]) == 0:
            raise ValueError("ZERO_TICK_VOLUME_NEEDS_BROKER_REVIEW")
        prices[stamp] = values["close"]
    return prices


def inspect_ppi_fx_m15_forward_reaction_lab(
    *, archive_root: Any, receipt: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Evaluate 7 complete M15 windows only AFTER all data are observable.

    The baseline is the 13:15–13:30 UTC candle close. Each window samples a
    *closed* candle at +15, +60 or +240 min, never an in-progress candle.
    For USD-quoted pairs, invert spot ratio to normalize USD strength exactly.
    Do NOT count the 7 simultaneously reacting pairs as independent events.
    """
    now = _utc(as_of_utc)
    if now is None:
        return _no_go("INVALID_AS_OF_CLOCK")
    if now < LAST_REQUIRED_CLOSE_UTC:
        return _no_go("FORWARD_WINDOWS_NOT_YET_CLOSED", state="LAB_WAIT_PPI_FX_FORWARD_WINDOW")
    if not isinstance(receipt, ClaimedLocalPriceArchive) or not isinstance(archive_root, (Path, str)):
        return _no_go("PRICE_ARCHIVE_NOT_SUPPLIED")
    captured = _utc(receipt.captured_at_utc)
    if (captured is None or not LAST_REQUIRED_CLOSE_UTC <= captured <= now
            or receipt.source_kind != "MT5_READONLY_M15_CSV_CLAIM_UNVERIFIED"
            or not isinstance(receipt.sha256_by_symbol, dict)
            or set(receipt.sha256_by_symbol) != set(USD_FX)
            or any(not isinstance(v, str) or HEX.fullmatch(v) is None
                   for v in receipt.sha256_by_symbol.values())):
        return _no_go("INVALID_OR_INCOMPLETE_SEVEN_PAIR_RECEIPT")
    root = Path(archive_root)
    if not root.is_dir() or root.is_symlink():
        return _no_go("ARCHIVE_ROOT_MISSING_OR_SYMLINK")
    results: dict[str, dict[str, str]] = {}
    for sym in USD_FX:
        try:
            closes = _read_m15(root, sym, receipt.sha256_by_symbol[sym])
        except (ValueError, OSError, OverflowError) as exc:
            result = _no_go("ALL_SEVEN_M15_SERIES_REQUIRED_UNALTERED")
            result["failed_symbol"] = sym
            result["series_failure"] = str(exc) if isinstance(exc, ValueError) else "FILE_READ_FAILED"
            return result
        base = closes[int(BASELINE_OPEN_UTC.timestamp())]
        row: dict[str, str] = {}
        for label, minutes in WINDOWS:
            candle_open = EVENT_UTC + timedelta(minutes=minutes - 15)
            latest = closes[int(candle_open.timestamp())]
            # Exact inversion for a USD quote: stronger USD == lower EURUSD, etc.
            ratio = (latest / base) if sym.startswith("USD") else (base / latest)
            bps = (ratio - Decimal(1)) * Decimal(10_000)
            row[label] = str(bps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        results[sym] = row
    out = _no_go("LOCAL_PRICE_BYTES_RESEARCH_ONLY_NO_CAUSALITY_OR_BROKER_ATTESTATION",
                  state="LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO")
    out["price_reactions_usd_normalized_bps"] = results
    out["archive_captured_at_utc_claim"] = captured.isoformat()
    out["local_seven_file_hashes_match"] = True
    out["independent_economic_event_sample_count"] = 1
    return out

__all__ = ["SCHEMA", "EVENT_UTC", "USD_FX", "WINDOWS", "ClaimedLocalPriceArchive",
           "inspect_ppi_fx_m15_forward_reaction_lab"]