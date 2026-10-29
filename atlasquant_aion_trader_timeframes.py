"""A269: offline, separately supplied closed-candle timeframe evidence.

Strictly a read model. Input claims and timestamps can be forged by a host:
NO independent provider verification, no trade signal and no execution grant.
Never fetch, aggregate M5 candles into H1, or infer one TF from another.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from atlasquant_instrument_registry import FX_28, FX_BY_SYMBOL

PERIOD_MINUTES = {
    "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440,
}
# Maximum age of LAST *closed* candle, not the file's fetch time.
# Conservative time-specific policy; market closures remain historical.
MAX_CLOSED_AGE = {
    "M5": 20, "M15": 70, "M30": 100,
    "H1": 180, "H4": 600, "D1": 3000,
}
SOURCE = "ATLASQUANT_OFFLINE_CLOSED_CANDLE_INPUT_V1"
NO_SEPARATE = "NO_SEPARATE_TIMEFRAME_EVIDENCE"
INVALID = "INVALID_OR_UNVERIFIED_TIMEFRAME_INPUT"
STALE = "HISTORICAL_ONLY"
CONFLICT = "CONFLICT_WITH_RESIDENT_M15_BLOCKED"


def _ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        date = value
    elif type(value) is str:
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if date.tzinfo is None or date.utcoffset() is None:
        return None
    return date.astimezone(timezone.utc)


def _asset(value: Any) -> str | None:
    if type(value) is not str:
        return None
    name = value.strip().upper()
    if name.startswith("FX:"):
        name = name[3:]
    for ch in ("/", "_", "-", " "):
        name = name.replace(ch, "")
    return name if name in FX_BY_SYMBOL else None


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def classify_tf(record: Any, timeframe: str, *, now: datetime) -> tuple[str, float | None]:
    """Return a local-only structural classification plus last close value.

    Metadata supplied by a caller is NOT proof of a real independent feed.
    """
    if timeframe not in PERIOD_MINUTES or type(record) is not dict:
        return INVALID, None
    if set(record) != {"timeframe", "source", "closed_candles", "fetched_at", "bars"}:
        return INVALID, None
    if (record["timeframe"] != timeframe or record["source"] != SOURCE
            or record["closed_candles"] is not True):
        return INVALID, None
    fetch = _ts(record["fetched_at"])
    if fetch is None or fetch > now:
        return INVALID, None
    bars = record["bars"]
    if type(bars) not in (list, tuple) or not (2 <= len(bars) <= 240):
        return INVALID, None
    previous = None
    last_close = None
    for candle in bars:
        if type(candle) is not dict or set(candle) != {
            "closed_at", "open", "high", "low", "close"
        }:
            return INVALID, None
        closed_at = _ts(candle["closed_at"])
        if closed_at is None or closed_at > now or closed_at > fetch:
            return INVALID, None
        vals = [candle[k] for k in ("open", "high", "low", "close")]
        if not all(_number(v) for v in vals):
            return INVALID, None
        open_, high, low, close = vals
        if high < max(open_, close, low) or low > min(open_, close, high):
            return INVALID, None
        if previous is not None:
            elapsed = (closed_at - previous).total_seconds() / 60.0
            if elapsed < PERIOD_MINUTES[timeframe]:
                # This also rejects duplicate or out-of-order timestamps.
                return INVALID, None
        previous = closed_at
        last_close = float(close)
    age = (now - previous).total_seconds() / 60.0
    # Freshness of candles and retrieval must BOTH be established.
    fetch_age = (now - fetch).total_seconds() / 60.0
    if (not math.isfinite(age) or age < 0
            or not math.isfinite(fetch_age) or fetch_age < 0):
        return INVALID, None
    if age >= MAX_CLOSED_AGE[timeframe] or fetch_age >= MAX_CLOSED_AGE[timeframe]:
        return STALE, last_close
    return "INPUT_FRESH_CLOSED_" + timeframe + "_UNATTESTED", last_close


def evaluate_mtf_input(raw: Any, *, now: datetime) -> tuple[dict[str, dict], list[str], int]:
    """No provider reads. Accept keyed pairs, detect ambiguous aliases."""
    if type(raw) is not dict or len(raw) > 100:
        return {}, [], 1
    normalized = {}
    duplicates = set()
    unknown = 0
    for raw_pair, periods in raw.items():
        pair = _asset(raw_pair)
        if pair is None:
            unknown += 1
            continue
        if pair in normalized:
            duplicates.add(pair)
        else:
            normalized[pair] = periods
    for pair in duplicates:
        normalized[pair] = {"__ambiguous__": True}
    return normalized, sorted(duplicates), unknown


def merge_mtf_readonly(
    board: dict,
    *,
    evidence: Any,
    now: datetime,
    resident_rows: Any,
) -> dict:
    """Annotate an already-created A268 board; never promote trade permission."""
    invalid_root = type(evidence) is not dict or len(evidence) > 100
    indexed, dupes, unknown = evaluate_mtf_input(evidence, now=now)
    resident = {}
    if type(resident_rows) is list:
        for item in resident_rows:
            if type(item) is dict and _asset(item.get("asset")):
                resident[_asset(item["asset"])] = item

    counts = {tf: 0 for tf in PERIOD_MINUTES}
    for row in board["rows"]:
        pair = row["asset"]
        periods = indexed.get(pair)
        if invalid_root:
            # A malformed supplied package cannot silently fall back to
            # resident M15 and claim 28/28 current coverage.
            row["timeframes"] = {tf: INVALID for tf in PERIOD_MINUTES}
            row["market_evidence"] = INVALID
        elif periods is not None:
            if pair in dupes or type(periods) is not dict or any(
                    type(k) is not str or k not in PERIOD_MINUTES for k in periods):
                periods = {tf: None for tf in PERIOD_MINUTES}
            for tf in PERIOD_MINUTES:
                if tf not in periods:
                    continue
                status, close = classify_tf(periods[tf], tf, now=now)
                if status == "INPUT_FRESH_CLOSED_M15_UNATTESTED":
                    # A supplemental claim alone never promotes the legacy
                    # verified-resident 28/28 counter. If a validated resident
                    # M15 already exists, it must agree on last close.
                    old = resident.get(pair, {})
                    if row["market_evidence"] == "FRESH_CLOSED_M15":
                        if (type(old.get("series")) not in (list, tuple)
                                or not old["series"] or not _number(old["series"][-1])
                                or not math.isclose(
                                    close, old["series"][-1],
                                    rel_tol=1e-9, abs_tol=1e-9
                                )):
                            status = CONFLICT
                        else:
                            status = "FRESH_CLOSED_M15"
                row["timeframes"][tf] = status
                if tf == "M15":
                    row["market_evidence"] = status
        for tf, status in row["timeframes"].items():
            if status == "FRESH_CLOSED_M15" or status == (
                    "INPUT_FRESH_CLOSED_" + tf + "_UNATTESTED"):
                counts[tf] += 1
    # Never turn 28 unverified caller-supplied M15 records into a verified
    # 28/28 resident claim. Count those only in 'mtf_coverage' with caveat.
    verified_m15 = sum(
        row["timeframes"]["M15"] == "FRESH_CLOSED_M15"
        for row in board["rows"]
    )
    board["fresh_m15_pairs"] = verified_m15
    board["historical_m15_pairs"] = sum(
        row["timeframes"]["M15"] == STALE for row in board["rows"]
    )
    board["all_28_fresh_closed_m15"] = (
        verified_m15 == 28 and not board["duplicate_pairs"] and not dupes
    )
    board["mtf_coverage"] = counts
    board["mtf_coverage_is_external_attestation"] = False
    board["mtf_input_duplicate_pairs"] = dupes
    board["mtf_input_unknown_pairs"] = unknown
    board["mtf_input_root_valid"] = not invalid_root
    board["mtf_verification"] = "CALLER_INPUT_STRUCTURAL_ONLY_NO_EXTERNAL_ATTESTATION"
    return board
