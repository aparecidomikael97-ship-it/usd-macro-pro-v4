"""A278 LAB: locally hash-chained manual-plan journal, no external attestation.

This journal can detect changes relative to a head digest saved separately.
It cannot prove time of creation or resist a caller rebuilding/backdating
the entire chain. It is NOT the P0 independent witness or audit custody.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any

from atlasquant_aion_historical_csv import ALLOWED_SYMBOLS
from atlasquant_aion_trader_timeframes import PERIOD_MINUTES
from atlasquant_aion_csv_backtest_lab import (
    SETUPS, PLAN_FIELDS, MAX_PLANS, research_backtest_csv,
)

SCHEMA = "ATLASQUANT_AION_MANUAL_PLAN_JOURNAL_LAB_V1"
GENESIS = "0" * 64
JOURNAL_KEYS = frozenset((
    "schema", "symbol", "timeframe", "entries", "head_sha256",
    "externally_attested", "authorizes_send", "p0_homologated",
))
ENTRY_KEYS = frozenset((
    "sequence", "captured_at", "plan", "previous_sha256", "sha256",
))


def _ts(raw: Any) -> datetime | None:
    if type(raw) is not str:
        return None
    try:
        date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if date.tzinfo is None or date.utcoffset() is None:
            return None
        return date.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _number(value: Any) -> float | None:
    if type(value) not in (int, float) or value <= 0:
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except (OverflowError, ValueError):
        return None


def _canonical_plan(value: Any) -> dict | None:
    if type(value) is not dict or set(value) != PLAN_FIELDS:
        return None
    ts = _ts(value["signal_time"])
    setup, side = value["setup"], value["side"]
    if (ts is None or type(setup) is not str or setup not in SETUPS
            or type(side) is not str or side not in ("BUY", "SELL")):
        return None
    prices = [_number(value[key]) for key in ("entry", "stop", "target")]
    if any(x is None for x in prices):
        return None
    entry, stop, target = prices
    if (side == "BUY" and not stop < entry < target) or (
            side == "SELL" and not target < entry < stop):
        return None
    return {
        "signal_time": ts.isoformat(), "setup": setup, "side": side,
        "entry": entry, "stop": stop, "target": target,
    }


def _digest(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha(raw: Any) -> bool:
    return type(raw) is str and bool(re.fullmatch("[0-9a-f]{64}", raw))


def empty_plan_journal(*, symbol: Any, timeframe: Any) -> dict:
    """Create a local, untrusted scaffold; never credentials or custody."""
    if (type(symbol) is not str or symbol not in ALLOWED_SYMBOLS
            or type(timeframe) is not str or timeframe not in PERIOD_MINUTES):
        raise ValueError("UNKNOWN_SYMBOL_OR_TIMEFRAME")
    return {
        "schema": SCHEMA, "symbol": symbol, "timeframe": timeframe,
        "entries": [], "head_sha256": GENESIS,
        "externally_attested": False, "authorizes_send": False,
        "p0_homologated": 0,
    }


def verify_plan_journal(journal: Any, *, expected_head: Any) -> dict:
    """Verify native structure and chain against a separately pinned digest.

    This checks consistency ONLY: no independent author/time authenticity.
    """
    output = {
        "valid": False, "error": "INVALID_JOURNAL", "plans": [],
        "head_sha256": None, "externally_attested": False,
        "time_provenance": "CALLER_DECLARED_LOCAL_ONLY",
        "authorizes_send": False, "p0_homologated": 0,
    }
    if (type(journal) is not dict or set(journal) != JOURNAL_KEYS
            or journal["schema"] != SCHEMA
            or type(journal["symbol"]) is not str
            or journal["symbol"] not in ALLOWED_SYMBOLS
            or type(journal["timeframe"]) is not str
            or journal["timeframe"] not in PERIOD_MINUTES
            or type(journal["entries"]) is not list
            or len(journal["entries"]) > MAX_PLANS
            or journal["externally_attested"] is not False
            or journal["authorizes_send"] is not False
            or type(journal["p0_homologated"]) is not int
            or journal["p0_homologated"] != 0
            or not _sha(journal["head_sha256"])
            or not _sha(expected_head)):
        return output
    if journal["head_sha256"] != expected_head:
        output["error"] = "UNPINNED_OR_MISMATCHED_HEAD"
        return output

    previous, captured_previous = GENESIS, None
    plans, seen = [], set()
    for index, entry in enumerate(journal["entries"], start=1):
        if (type(entry) is not dict or set(entry) != ENTRY_KEYS
                or type(entry["sequence"]) is not int
                or entry["sequence"] != index
                or not _sha(entry["previous_sha256"])
                or not _sha(entry["sha256"])
                or entry["previous_sha256"] != previous):
            output["error"] = "BROKEN_HASH_CHAIN"
            return output
        captured = _ts(entry["captured_at"])
        plan = _canonical_plan(entry["plan"])
        if (captured is None or type(entry["captured_at"]) is not str
                or entry["captured_at"] != captured.isoformat()
                or plan is None or plan != entry["plan"]):
            output["error"] = "INVALID_PLAN_OR_CAPTURE_TIME"
            return output
        signal = _ts(plan["signal_time"])
        # To be usable by the existing engine, entry may occur only AFTER
        # the signal candle. The plan must claim capture BEFORE the NEXT
        # candle could close; no user-declared timestamp is external proof.
        try:
            next_close = signal + timedelta(minutes=PERIOD_MINUTES[journal["timeframe"]])
        except OverflowError:
            output["error"] = "INVALID_PLAN_OR_CAPTURE_TIME"
            return output
        if (captured >= next_close
                or captured_previous is not None and captured < captured_previous
                or (plan["signal_time"], plan["setup"], plan["side"]) in seen):
            output["error"] = "LATE_NONMONOTONIC_OR_DUPLICATE_CAPTURE"
            return output
        seen.add((plan["signal_time"], plan["setup"], plan["side"]))
        payload = {
            "sequence": index, "captured_at": captured.isoformat(),
            "plan": plan, "previous_sha256": previous,
        }
        computed = _digest(payload)
        if computed != entry["sha256"]:
            output["error"] = "BROKEN_HASH_CHAIN"
            return output
        previous, captured_previous = computed, captured
        plans.append(plan)
    if previous != journal["head_sha256"]:
        output["error"] = "BROKEN_HASH_CHAIN"
        return output
    output.update({
        "valid": True, "error": None, "plans": plans,
        "head_sha256": previous, "symbol": journal["symbol"],
        "timeframe": journal["timeframe"], "entry_count": len(plans),
    })
    return output


def append_manual_plan(journal: Any, *, plan: Any, captured_at: Any) -> dict:
    """Append a new local claim, returning a new journal without mutating input.

    captured_at is caller supplied and therefore UNATTESTED. For real
    point-in-time evidence it needs trusted independent timestamp custody.
    """
    result = {
        "accepted": False, "error": "INVALID_APPEND", "journal": None,
        "head_sha256": None, "externally_attested": False,
        "authorizes_send": False,
    }
    if type(journal) is not dict or not _sha(journal.get("head_sha256")):
        return result
    verified = verify_plan_journal(journal, expected_head=journal["head_sha256"])
    if not verified["valid"] or verified["entry_count"] >= MAX_PLANS:
        result["error"] = "INVALID_OR_FULL_JOURNAL"
        return result
    normalized = _canonical_plan(plan)
    if type(captured_at) is not datetime or captured_at.tzinfo is None or captured_at.utcoffset() is None:
        result["error"] = "INVALID_CAPTURE"
        return result
    stamp = captured_at.astimezone(timezone.utc).isoformat()
    if normalized is None:
        result["error"] = "INVALID_PLAN"
        return result
    prev = journal["head_sha256"]
    record = {
        "sequence": len(journal["entries"]) + 1,
        "captured_at": stamp, "plan": normalized,
        "previous_sha256": prev,
    }
    record["sha256"] = _digest(record)
    new_journal = {
        **journal, "entries": [*journal["entries"], record],
        "head_sha256": record["sha256"],
    }
    if not verify_plan_journal(new_journal, expected_head=new_journal["head_sha256"])["valid"]:
        result["error"] = "INVALID_CAPTURE_ORDER_OR_DUPLICATE"
        return result
    result.update({
        "accepted": True, "error": None,
        "journal": new_journal, "head_sha256": record["sha256"],
    })
    return result


def research_backtest_journal_csv(
    csv_text: Any, *, journal: Any, expected_head: Any,
    symbol: Any, timeframe: Any, timestamp_basis: Any,
    now: Any, validation_start: Any, cost_r: Any, slippage_r: Any,
    max_wait_bars: Any = 8, max_hold_bars: Any = 96,
) -> dict:
    """Fail closed before A277 unless the local declared journal verifies."""
    refused = {
        "schema": SCHEMA, "valid": False,
        "status": "INVALID_OR_UNATTESTED_PLAN_JOURNAL",
        "error": "INVALID_JOURNAL",
        "train": None, "holdout": None,
        "time_provenance": "CALLER_DECLARED_LOCAL_ONLY",
        "externally_attested": False,
        "no_orders": True, "authorizes_send": False, "p0_homologated": 0,
    }
    check = verify_plan_journal(journal, expected_head=expected_head)
    if not check["valid"]:
        refused["error"] = check["error"]
        return refused
    if (type(symbol) is not str or type(timeframe) is not str
            or check["symbol"] != symbol or check["timeframe"] != timeframe):
        refused["error"] = "JOURNAL_ASSET_TIMEFRAME_MISMATCH"
        return refused
    outcome = research_backtest_csv(
        csv_text, symbol=symbol, timeframe=timeframe,
        timestamp_basis=timestamp_basis, now=now,
        validation_start=validation_start, manual_plans=check["plans"],
        cost_r=cost_r, slippage_r=slippage_r,
        max_wait_bars=max_wait_bars, max_hold_bars=max_hold_bars,
    )
    outcome["plan_journal_schema"] = SCHEMA
    outcome["plan_journal_head_sha256"] = check["head_sha256"]
    outcome["plan_journal_entry_count"] = check["entry_count"]
    outcome["time_provenance"] = "CALLER_DECLARED_LOCAL_ONLY"
    outcome["externally_attested"] = False
    return outcome


__all__ = ["SCHEMA", "GENESIS", "empty_plan_journal", "append_manual_plan",
           "verify_plan_journal", "research_backtest_journal_csv"]
