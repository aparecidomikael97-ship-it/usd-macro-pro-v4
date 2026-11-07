"""Join a private MT5 28-pair snapshot to two-sided macro evidence, LAB only.

The output is a research coverage receipt, never a price forecast, trade
signal or success probability. It revalidates broker-reported candle data and
uses the existing G8 publication/capture chronology gate for both currencies.
It cannot independently authenticate either upstream source or its vintage.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from atlasquant_instrument_registry import FX_28
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_macro_asof_lab import inspect_g8_pair_macro_asof_lab
from atlasquant_trader_mt5_readonly_snapshot_lab import (
    SCHEMA as SNAPSHOT_SCHEMA,
    TIMEFRAME_COUNTS,
    TIMEFRAME_SECONDS,
    _validate_bars,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_G8_MACRO_LINK_READONLY_LAB_V1"
MAX_SNAPSHOT_BYTES = 1_000_000
MAX_MACRO_BYTES = 48_000
MAX_BAR_AGE = {"M15": timedelta(hours=1), "D1": timedelta(hours=72),
               "W1": timedelta(days=9)}
SNAPSHOT_OK = "LAB_BROKER_HISTORY_STRUCTURALLY_VALID_UNVERIFIED"
MACRO_OK = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"


def _wait(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "snapshot_sha256": None, "snapshot_captured_at_utc": None,
        "decision_at_utc": None, "price_pairs_validated": 0,
        "macro_pairs_structurally_complete": 0,
        "m15_recent_pairs": 0, "d1_recent_pairs": 0, "w1_recent_pairs": 0,
        "pairs": {}, "macro_source_independently_authenticated": False,
        "broker_quote_source_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "macro_values_independently_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate snapshot JSON key")
        result[name] = value
    return result


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("+00:00"):
        raise ValueError("SNAPSHOT_UTC_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("SNAPSHOT_UTC_TIMESTAMP_INVALID") from exc
    if result.utcoffset() != timedelta(0):
        raise ValueError("SNAPSHOT_UTC_TIMESTAMP_INVALID")
    return result


def _check_snapshot(obj: Any, *, captured: datetime) -> dict[str, Any]:
    if (not isinstance(obj, dict) or obj.get("schema") != SNAPSHOT_SCHEMA
            or obj.get("state") != SNAPSHOT_OK
            or obj.get("captured_at_utc") != captured.isoformat()
            or obj.get("source") != "MT5_CONNECTED_TERMINAL_BROKER_REPORTED_UNVERIFIED"
            or obj.get("timestamp_basis") != "MT5_UNIX_SECONDS_UTC_REPORTED_NOT_INDEPENDENTLY_ATTESTED"
            or obj.get("timeframe_counts") != TIMEFRAME_COUNTS
            or obj.get("expected_pairs") != 28
            or obj.get("validated_pairs") != 28
            or obj.get("validated_bars") != 2968
            or not isinstance(obj.get("pairs"), dict)
            or set(obj["pairs"]) != set(FX_28)):
        raise ValueError("SNAPSHOT_DECLARED_UNIVERSE_OR_SOURCE_INVALID")
    for name in ("broker_identity_independently_verified",
                 "quotes_independently_verified",
                 "historical_vintage_point_in_time_verified",
                 "fx_ny_1700_d1w1_aligned", "trade_authorized", "can_feed_live_radar",
                 "worker_enabled", "scheduler_enabled", "publishable"):
        if obj.get(name) is not False:
            raise ValueError("SNAPSHOT_INCORRECTLY_CLAIMS_VERIFICATION_OR_AUTHORITY")
    if obj.get("fx_bias") is not None or obj.get("historical_predictive_accuracy") is not None:
        raise ValueError("SNAPSHOT_INCORRECTLY_CLAIMS_BIAS_OR_ACCURACY")
    if obj.get("operational_bias") != "AGUARDAR":
        raise ValueError("SNAPSHOT_INCORRECTLY_CLAIMS_BIAS_OR_ACCURACY")

    checked: dict[str, Any] = {}
    for symbol in FX_28:
        pair_rows = obj["pairs"][symbol]
        if not isinstance(pair_rows, dict) or set(pair_rows) != set(TIMEFRAME_COUNTS):
            raise ValueError("SNAPSHOT_PAIR_TIMEFRAMES_MISSING")
        result = {}
        for tf in TIMEFRAME_COUNTS:
            saved = pair_rows[tf]
            if not isinstance(saved, dict) or set(saved) != {
                "closed_bars", "first_bar_open_utc", "last_bar_open_utc",
                "non_contiguous_m15_intervals", "bars",
            }:
                raise ValueError("SNAPSHOT_CANDLE_METADATA_INVALID")
            source_bars = saved["bars"]
            if not isinstance(source_bars, list):
                raise ValueError("SNAPSHOT_CANDLE_ROWS_INVALID")
            for bar in source_bars:
                if (not isinstance(bar, dict)
                        or set(bar) != {"time", "open", "high", "low", "close",
                                            "tick_volume", "spread", "real_volume"}
                        or type(bar["time"]) is not int
                        or any(type(bar[k]) not in (float, int) for k in (
                            "open", "high", "low", "close"))
                        or any(type(bar[k]) is not int for k in (
                            "tick_volume", "spread", "real_volume"))):
                    raise ValueError("SNAPSHOT_CANDLE_ROWS_INVALID")
            computed = _validate_bars(saved["bars"], timeframe=tf,
                                      captured_epoch=int(captured.timestamp()))
            # Recompute, never accept potentially tampered self-declared totals.
            if saved != computed:
                raise ValueError("SNAPSHOT_CANDLE_COUNTS_OR_METADATA_MISMATCH")
            result[tf] = computed
        checked[symbol] = result
    return checked


def join_mt5_macro_lab(
    *, snapshot_raw: Any, macro_raw_by_pair: Any,
    decision_at_utc: datetime,
) -> dict[str, Any]:
    """Return coverage of all 28 pairs; no observation becomes a live bias."""
    out = _wait("INVALID_PRICE_SNAPSHOT_OR_DECISION_CLOCK")
    if (not isinstance(decision_at_utc, datetime)
            or decision_at_utc.tzinfo is None
            or decision_at_utc.utcoffset() is None
            or decision_at_utc.microsecond != 0
            or not isinstance(snapshot_raw, bytes)
            or not 100 <= len(snapshot_raw) <= MAX_SNAPSHOT_BYTES
            or not isinstance(macro_raw_by_pair, dict)
            or not set(macro_raw_by_pair).issubset(set(OFFICIAL_PAIRS))
            or any(not isinstance(raw, bytes) or len(raw) > MAX_MACRO_BYTES
                   for raw in macro_raw_by_pair.values())):
        return out
    decision = decision_at_utc.astimezone(timezone.utc)
    try:
        data = json.loads(snapshot_raw.decode("utf-8", "strict"),
                          object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        captured = _time(data.get("captured_at_utc"))
        if captured > decision:
            out["reason"] = "DECISION_PRECEDES_SNAPSHOT_COLLECTION"
            return out
        checked = _check_snapshot(data, captured=captured)
    except (UnicodeDecodeError, ValueError, TypeError, OverflowError, AttributeError,
            KeyError, RecursionError):
        out["reason"] = "SNAPSHOT_STRUCTURE_OR_CHRONOLOGY_REJECTED"
        return out

    out["snapshot_sha256"] = sha256(snapshot_raw).hexdigest()
    out["snapshot_captured_at_utc"] = captured.isoformat()
    out["decision_at_utc"] = decision.isoformat()
    out["price_pairs_validated"] = len(checked)
    rows: dict[str, Any] = {}
    for symbol, pair in zip(FX_28, OFFICIAL_PAIRS):
        recency = {}
        for tf in TIMEFRAME_COUNTS:
            last_open = checked[symbol][tf]["bars"][-1]["time"]
            age = decision - datetime.fromtimestamp(
                last_open + TIMEFRAME_SECONDS[tf], timezone.utc)
            is_recent = timedelta(0) <= age <= MAX_BAR_AGE[tf]
            recency[tf] = {
                "last_closed_bar_open_utc": checked[symbol][tf]["last_bar_open_utc"],
                "age_seconds_since_close": int(age.total_seconds()),
                "recent_for_research": is_recent,
            }
            if is_recent:
                out[{"M15": "m15_recent_pairs", "D1": "d1_recent_pairs",
                     "W1": "w1_recent_pairs"}[tf]] += 1

        raw_macro = macro_raw_by_pair.get(pair)
        macro_status = "MISSING"
        missing: list[str] = []
        macro_hash = None
        if raw_macro is not None:
            macro_hash = sha256(raw_macro).hexdigest()
            macro = inspect_g8_pair_macro_asof_lab(raw_macro, as_of_utc=decision)
            if (macro.get("pair") == pair
                    and macro.get("decision_at_utc") == decision.isoformat()):
                missing = list(macro.get("missing_or_stale", []))
                macro_status = "TWO_SIDED_UNATTESTED" if macro["state"] == MACRO_OK else "INCOMPLETE"
            else:
                macro_status = "INVALID_OR_CLOCK_MISMATCH"
        if macro_status == "TWO_SIDED_UNATTESTED":
            out["macro_pairs_structurally_complete"] += 1
        rows[pair] = {
            "symbol": symbol, "timeframes": recency,
            "macro_state": macro_status, "macro_missing_or_stale": missing,
            "macro_bytes_sha256": macro_hash, "research_bias": "AGUARDAR",
        }

    out["pairs"] = rows
    out["state"] = "LAB_PRICE_MACRO_COVERAGE_AUDITED_UNATTESTED"
    out["reason"] = "MACRO_AND_PRICE_SOURCE_PROVENANCE_NOT_ATTESTED_NO_SIGNAL"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline MT5+macro LAB coverage report")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="Create new local summary JSON, no overwrite")
    args = parser.parse_args(argv)
    try:
        if not args.snapshot.is_file() or not 100 <= args.snapshot.stat().st_size <= MAX_SNAPSHOT_BYTES:
            print("SNAPSHOT_FILE_UNAVAILABLE_OR_TOO_LARGE")
            return 2
        raw = args.snapshot.read_bytes()
    except OSError:
        print("SNAPSHOT_FILE_UNAVAILABLE")
        return 2
    # No authenticated macro byte receipts were supplied through this CLI.
    # Empty mapping must leave all 28 directional decisions in AGUARDAR.
    report = join_mt5_macro_lab(
        snapshot_raw=raw, macro_raw_by_pair={},
        decision_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
    )
    if args.out and report["state"] != "LAB_BLOCKED":
        try:
            with args.out.open("x", encoding="utf-8") as destination:
                json.dump(report, destination, ensure_ascii=False, sort_keys=True, allow_nan=False)
                destination.write("\n")
        except OSError:
            print("REPORT_FILE_NOT_CREATED")
            return 2
    print(json.dumps({k: report[k] for k in (
        "state", "reason", "price_pairs_validated", "macro_pairs_structurally_complete",
        "m15_recent_pairs", "d1_recent_pairs", "w1_recent_pairs", "operational_bias",
        "trade_authorized")}, ensure_ascii=False, sort_keys=True))
    return 0 if report["state"] != "LAB_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
