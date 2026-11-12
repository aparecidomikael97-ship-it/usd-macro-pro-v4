"""Read-only preflight for 13-Nov-2026 US PPI seven-FX AM12 workflow.

Checks existing frozen consensus bytes, official PARTIAL calendar receipts,
and seven MT5 symbol descriptors/visibility BEFORE any price capture.
No rates, ticks, symbol_select, account_info, orders, logins, signals,
news downloads, file writes, subscriptions, scheduling or trading.
Snapshot hashes and the terminal company are NOT independent provenance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from atlasquant_mt5_xauusd_closedbar_capture_lab import _terminal_path_ok
from atlasquant_trader_ppi_mt5_m15_capture_lab import _symbol_spec_for_capture
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    EVENT_UTC, LAST_REQUIRED_CLOSE_UTC, TD_PRE_EVENT_HTML_SHA256,
    TE_PRE_EVENT_HTML_SHA256, USD_FX,
)
from atlasquant_trader_ppi_pre_event_protocol_lab import (
    inspect_ppi_frozen_research_protocol_lab,
)
from atlasquant_trader_ppi_official_schedule_archive_lab import (
    inspect_ppi_three_official_schedule_files_lab,
)

SCHEMA = "ATLASQUANT_PPI_AM12_SEVEN_FX_READONLY_PREFLIGHT_LAB_V1"
MAX_SOURCE_BYTES = 750_000
SOURCES = {
    "TD_ECONOMICS": TD_PRE_EVENT_HTML_SHA256,
    "TRADING_ECONOMICS": TE_PRE_EVENT_HTML_SHA256,
}


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        return None
    return value.astimezone(timezone.utc)


def _empty(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PPI_PREFLIGHT_BLOCKED",
        "reason": reason,
        "release_utc": EVENT_UTC.isoformat(),
        "required_final_m15_close_utc": LAST_REQUIRED_CLOSE_UTC.isoformat(),
        "local_clock_phase_claim": None,
        "frozen_pre_event_protocol_checked": False,
        "td_te_source_hashes_matched_locally": 0,
        "official_partial_schedule_html_hashes_matched_locally": 0,
        "official_calendar_full_market_coverage_attested": False,
        "mt5_terminal_connected": False,
        "mt5_symbols_checked": 0,
        "seven_canonical_symbols_spec_consistent": 0,
        "visible_symbols": [],
        "hidden_symbols": [],
        "missing_or_invalid_symbols": [],
        "data_capture_performed": False,
        "m15_candles_read": 0,
        "tick_quotes_read": 0,
        "symbol_visibility_changed": False,
        "account_information_read": False,
        "positions_or_orders_read": False,
        "orders_sent": 0,
        "broker_or_active_quote_server_independently_authenticated": False,
        "no_causal_claim_from_partial_calendar": True,
        "pre_event_directional_forecast_registered": False,
        "forecast_accuracy_measured": False,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _hash_local_html(path: Any, expected: str) -> bool:
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        return False
    try:
        if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
            return False
        return sha256(path.read_bytes()).hexdigest() == expected
    except (OSError, ValueError):
        return False


def inspect_ppi_seven_fx_readiness_lab(
    *, api: Any, terminal_path: Any,
    td_html_path: Any, te_html_path: Any,
    official_calendar_archive_root: Any,
    as_of_utc: Any,
) -> dict[str, Any]:
    now = _utc(as_of_utc)
    out = _empty("INVALID_INPUT_OR_CLOCK")
    if now is None or not _terminal_path_ok(terminal_path):
        return out
    out["local_clock_phase_claim"] = (
        "PRE_RELEASE" if now < EVENT_UTC
        else "POST_RELEASE_WAIT_M15_H4_CLOSE" if now < LAST_REQUIRED_CLOSE_UTC
        else "POST_H4_WINDOW_CLOSED_ELIGIBLE_FOR_MANUAL_CAPTURE_CHECKS"
    )

    protocol = inspect_ppi_frozen_research_protocol_lab(as_of_utc=now)
    if (not protocol.get("pre_event_declared_abstention")
            or protocol.get("pre_event_directional_forecasts_registered") != 0):
        out["reason"] = "FROZEN_ABSTENTION_PROTOCOL_NOT_VERIFIED"
        return out
    out["frozen_pre_event_protocol_checked"] = True

    source_pairs = (
        (td_html_path, SOURCES["TD_ECONOMICS"]),
        (te_html_path, SOURCES["TRADING_ECONOMICS"]),
    )
    out["td_te_source_hashes_matched_locally"] = sum(
        _hash_local_html(path, digest) for path, digest in source_pairs
    )
    if out["td_te_source_hashes_matched_locally"] != 2:
        out["reason"] = "PRE_EVENT_TD_TE_ORIGINAL_SOURCE_BYTES_MISSING_OR_CHANGED"
        return out

    source_calendar = inspect_ppi_three_official_schedule_files_lab(
        archive_root=official_calendar_archive_root, as_of_utc=now)
    if source_calendar.get("state") != "LAB_PPI_THREE_OFFICIAL_SCHEDULES_LOCAL_SHA_MATCH_NO_GO":
        out["reason"] = "OFFICIAL_COMPETING_CALENDAR_ARCHIVES_MISSING_OR_CHANGED"
        return out
    out["official_partial_schedule_html_hashes_matched_locally"] = 3

    try:
        initialized = api.initialize(path=terminal_path, timeout=10000)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        out["reason"] = "MT5_INITIALIZATION_FAILED_NO_MARKET_DATA_READ"
        return out
    if not initialized:
        out["reason"] = "MT5_NOT_CONNECTED_NO_MARKET_DATA_READ"
        return out
    try:
        terminal = api.terminal_info()
        if terminal is None or terminal.connected is not True:
            out["reason"] = "MT5_TERMINAL_NOT_CONNECTED"
            return out
        out["mt5_terminal_connected"] = True
        for sym in USD_FX:
            info = api.symbol_info(sym)
            out["mt5_symbols_checked"] += 1
            if info is None or _symbol_spec_for_capture(info, sym) is None:
                out["missing_or_invalid_symbols"].append(sym)
                continue
            out["seven_canonical_symbols_spec_consistent"] += 1
            if getattr(info, "visible", None) is True:
                out["visible_symbols"].append(sym)
            else:
                out["hidden_symbols"].append(sym)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        out["reason"] = "MT5_SYMBOL_QUERY_FAILED"
        return out
    finally:
        try:
            api.shutdown()
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            out["reason"] = "MT5_SHUTDOWN_FAILED"
            out["state"] = "LAB_PPI_PREFLIGHT_BLOCKED"
            return out

    if out["missing_or_invalid_symbols"]:
        out["reason"] = "SEVEN_FX_IDENTITY_OR_PRECISION_INCOMPLETE"
    elif out["hidden_symbols"]:
        out["reason"] = "SEVEN_FX_VISIBILITY_INCOMPLETE_MANUAL_SHOW_ALL_REQUIRED"
    else:
        out["reason"] = "DOCUMENTARY_PREFLIGHT_COMPLETE_NOT_DATA_OR_TRADING_AUTHORIZATION"

    out["state"] = ("LAB_PPI_PREFLIGHT_7FX_VISIBLE_READONLY_WAIT"
                    if not out["hidden_symbols"] and not out["missing_or_invalid_symbols"]
                    else "LAB_PPI_PREFLIGHT_VISIBILITY_OR_SPEC_INCOMPLETE_NO_GO")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="PPI 7FX read-only local readiness check")
    ap.add_argument("--terminal-path", required=True)
    ap.add_argument("--td-html", required=True)
    ap.add_argument("--te-html", required=True)
    ap.add_argument("--official-calendar-root", required=True)
    args = ap.parse_args()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("BLOCKED_MT5_PYTHON_MODULE_NOT_AVAILABLE")
        return 2
    r = inspect_ppi_seven_fx_readiness_lab(
        api=mt5, terminal_path=args.terminal_path,
        td_html_path=Path(args.td_html),
        te_html_path=Path(args.te_html),
        official_calendar_archive_root=Path(args.official_calendar_root),
        as_of_utc=datetime.now(timezone.utc),
    )
    print(json.dumps(r, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if r["state"] == "LAB_PPI_PREFLIGHT_7FX_VISIBLE_READONLY_WAIT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
