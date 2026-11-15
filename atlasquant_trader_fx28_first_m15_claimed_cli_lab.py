"""Explicit one-attempt FX28 first M15 CLI for future LAB integration.

NOT wired to AM12 schedule or to production. Default is offline preflight;
capture requires two explicit flags and an existing safe archive directory.
Never runs at import time, never retries, never accesses orders or accounts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Sequence

from atlasquant_trader_fx28_first_m15_atomic_claim_lab import (
    WINDOW, inspect_claim_lab,
)
from atlasquant_trader_fx28_first_m15_claimed_driver_lab import (
    run_claimed_first_m15_lab,
)

SCHEMA = "ATLASQUANT_FX28_FIRST_M15_EXPLICIT_CLAIMED_CLI_LAB_V1"
END_UTC = datetime(2026, 11, 15, 22, 15, tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_CLI_BLOCKED_NO_GO",
        "reason": reason,
        "window": WINDOW,
        "trade_authorized": False,
        "publishable": False,
        "automatic_retry_allowed": False,
        "scheduler_connected": False,
    }


def execute_cli_lab(
    *, mode: str, root: Path, terminal_path: str | None,
    confirm_window: str | None, api: Any,
    clock: Callable[[], datetime],
) -> dict[str, Any]:
    """No action unless capture is explicitly confirmed for the frozen window."""
    if mode not in ("preflight", "capture-once"):
        return _blocked("INVALID_MODE")
    if not isinstance(root, Path) or not root.is_absolute():
        return _blocked("INVALID_ABSOLUTE_ARCHIVE_ROOT")
    if mode == "preflight":
        report = inspect_claim_lab(archive_root=root)
        return {
            "schema": SCHEMA,
            "state": "LAB_FX28_CLI_PREFLIGHT_ONLY_NO_GO",
            "reason": "READONLY_PRECHECK_NOT_A_LOCK",
            "precheck": report,
            "window": WINDOW,
            "trade_authorized": False, "publishable": False,
            "scheduler_connected": False, "automatic_retry_allowed": False,
        }
    if confirm_window != WINDOW or not terminal_path:
        return _blocked("EXPLICIT_WINDOW_AND_TERMINAL_REQUIRED")
    try:
        now = clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return _blocked("INVALID_CAPTURE_CLOCK")
        now = now.astimezone(timezone.utc)
    except (TypeError, ValueError, RuntimeError, OverflowError):
        return _blocked("INVALID_CAPTURE_CLOCK")
    if now < END_UTC:
        return _blocked("FIRST_M15_NOT_CLOSED_NO_IO_OR_CLAIM")
    if api is None:
        return _blocked("MT5_API_UNAVAILABLE_NO_CLAIM")
    # The driver atomically claims before it invokes the read-only collector.
    # We do NOT use a separate preflight as a substitute for atomic locking.
    return run_claimed_first_m15_lab(
        api, terminal_path=terminal_path, output_root=root, clock=lambda: now,
    )


def main(argv: Sequence[str] | None = None, *,
         api_for_test: Any = None,
         clock: Callable[[], datetime] | None = None,
         environ: dict[str, str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FX28 first M15: preflight (default) or explicit one-shot LAB")
    p.add_argument("--mode", choices=("preflight", "capture-once"), default="preflight")
    p.add_argument("--archive-root", type=Path)
    p.add_argument("--terminal-path")
    p.add_argument("--confirm-window", choices=(WINDOW,))
    args = p.parse_args(argv)
    env = os.environ if environ is None else environ
    if args.archive_root is None:
        base = env.get("LOCALAPPDATA")
        if not base:
            print(json.dumps(_blocked("LOCALAPPDATA_MISSING_FAIL_CLOSED")))
            return 2
        root = Path(base) / "AtlasQuant" / "LAB" / "FX28_NY17_M15"
    else:
        root = args.archive_root
    now_fn = clock if clock is not None else lambda: datetime.now(timezone.utc)

    mt5 = api_for_test
    if args.mode == "capture-once" and args.confirm_window == WINDOW:
        # Check temporal and directory prerequisites before importing MT5;
        # importing a module itself does not query or authenticate the terminal.
        try:
            now = now_fn()
            ready = isinstance(now, datetime) and now.tzinfo is not None and (
                now.utcoffset() is not None and
                now.astimezone(timezone.utc) >= END_UTC
            )
        except (TypeError, ValueError, RuntimeError, OverflowError):
            ready = False
        if ready and mt5 is None and args.terminal_path:
            try:
                mt5 = importlib.import_module("MetaTrader5")
            except (ImportError, OSError):
                mt5 = None
        if not ready:
            result = _blocked("FIRST_M15_NOT_CLOSED_OR_CLOCK_INVALID_NO_IO")
            print(json.dumps(result, sort_keys=True))
            return 2

    result = execute_cli_lab(
        mode=args.mode, root=root, terminal_path=args.terminal_path,
        confirm_window=args.confirm_window, api=mt5, clock=now_fn,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False), flush=True)
    if args.mode == "preflight":
        return 0 if result.get("precheck", {}).get("single_attempt_start_precheck_clear") is True else 2
    return 0 if result.get("state") == "LAB_CLAIMED_FIRST_M15_ARCHIVE_CHECKED_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
