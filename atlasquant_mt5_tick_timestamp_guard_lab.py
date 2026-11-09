"""AtlasQuant LAB: guard against unverified MT5 tick timestamp conventions.

This is a narrow, read-only diagnostic. A plausible timestamp is NEVER proof
of UTC provenance, a broker session, historical availability, or a trade signal.
No broker-server offset is guessed or applied to ticks or archived bars.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from numbers import Integral
from typing import Any, Callable


SCHEMA = "ATLASQUANT_MT5_TICK_TIMESTAMP_GUARD_LAB_V1"
SYMBOL = "EURUSD"
FUTURE_TOLERANCE_SECONDS = 5
STALE_LIMIT_SECONDS = 300
MAX_PROBE_SECONDS = 10


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_TICK_CLOCK_BLOCKED",
        "reason": reason,
        "symbol": SYMBOL,
        "reported_tick_utc_interpretation": None,
        "observation_before_utc": None,
        "observation_after_utc": None,
        "tick_minus_observation_after_seconds": None,
        "terminal_connected_observed": False,
        "broker_server_authenticated": False,
        "computer_clock_independently_synchronized": False,
        "mt5_timestamp_is_utc_attested": False,
        "clock_shift_authorized": False,
        "safe_for_point_in_time_join": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "trade_authorized": False,
        "validated_directional_accuracy": None,
        "new_cost_brl": 0,
    }


def audit_tick_timestamp_lab(
    *, before_utc: Any, after_utc: Any, tick_epoch: Any,
    terminal_connected: Any, symbol_visible: Any,
) -> dict[str, Any]:
    """Classify one tick against a bounded UTC wall-clock observation window.

    Input times must be timezone-aware. This detects a discrepancy; it cannot
    explain whether it comes from broker server conventions, PC clock, or API.
    """
    out = _blocked("INVALID_CLOCK_WINDOW")
    before, after = _as_utc(before_utc), _as_utc(after_utc)
    if before is None or after is None or after < before:
        return out
    out["observation_before_utc"] = _stamp(before)
    out["observation_after_utc"] = _stamp(after)
    if (after - before).total_seconds() > MAX_PROBE_SECONDS:
        out["reason"] = "PROBE_WINDOW_TOO_LONG"
        return out
    if terminal_connected is not True:
        out["reason"] = "TERMINAL_NOT_CONNECTED"
        return out
    out["terminal_connected_observed"] = True
    if symbol_visible is not True:
        out["reason"] = "SYMBOL_NOT_VISIBLE_NO_AUTO_SELECT"
        return out
    if not isinstance(tick_epoch, Integral) or isinstance(tick_epoch, bool) or tick_epoch <= 0:
        out["reason"] = "INVALID_TICK_EPOCH"
        return out
    try:
        reported = datetime.fromtimestamp(int(tick_epoch), timezone.utc)
    except (OverflowError, ValueError, OSError):
        out["reason"] = "UNREPRESENTABLE_TICK_EPOCH"
        return out
    out["reported_tick_utc_interpretation"] = _stamp(reported)
    out["tick_minus_observation_after_seconds"] = round((reported - after).total_seconds(), 3)
    if reported > after + timedelta(seconds=FUTURE_TOLERANCE_SECONDS):
        out["reason"] = "TICK_TIMESTAMP_IN_FUTURE_RELATIVE_TO_PC"
    elif reported < before - timedelta(seconds=STALE_LIMIT_SECONDS):
        out["reason"] = "TICK_TIMESTAMP_STALE_OR_MARKET_CLOSED"
    else:
        out["state"] = "LAB_TICK_CLOCK_PLAUSIBLE_UNATTESTED"
        out["reason"] = "WALL_CLOCK_MATCH_IS_NOT_TIME_SOURCE_ATTESTATION"
    return out


def run_readonly_probe(
    api: Any, *, terminal_path: str, clock: Callable[[], datetime],
) -> dict[str, Any]:
    """Use terminal_info, symbol_info and symbol_info_tick; never trade/select.

    Caller must ensure the specified MT5 terminal is already running. No
    login, account_info, orders, positions or symbol_select are requested.
    """
    if not isinstance(terminal_path, str) or not terminal_path:
        return _blocked("INVALID_TERMINAL_PATH")
    try:
        initialized = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, TypeError, OSError):
        return _blocked("MT5_INITIALIZATION_EXCEPTION")
    if not initialized:
        return _blocked("MT5_INITIALIZATION_FAILED")
    try:
        before = clock()
        terminal = api.terminal_info()
        symbol = api.symbol_info(SYMBOL)
        tick = api.symbol_info_tick(SYMBOL)
        after = clock()
        return audit_tick_timestamp_lab(
            before_utc=before, after_utc=after,
            tick_epoch=getattr(tick, "time", None),
            terminal_connected=getattr(terminal, "connected", None),
            symbol_visible=getattr(symbol, "visible", None),
        )
    except (AttributeError, TypeError, ValueError, OSError, RuntimeError):
        return _blocked("MT5_READONLY_PROBE_EXCEPTION")
    finally:
        api.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", required=True)
    args = parser.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        result = _blocked("MT5_PYTHON_LIBRARY_UNAVAILABLE")
    else:
        result = run_readonly_probe(
            mt5, terminal_path=args.terminal_path,
            clock=lambda: datetime.now(timezone.utc),
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "LAB_TICK_CLOCK_PLAUSIBLE_UNATTESTED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
