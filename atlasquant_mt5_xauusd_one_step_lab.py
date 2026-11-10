"""One opt-in Windows command: time preflight -> read-only MT5 XAU -> audit.

No account/order/position access, no network requests from Python and no
Windows time changes. W32Time status is an OS claim, NOT UTC attestation.
If the time-service evidence is missing, no MT5 connection or archive occurs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
import unicodedata

from atlasquant_mt5_xauusd_closedbar_capture_lab import (
    collect_xauusd_closedbar_snapshot_lab,
)
from atlasquant_mt5_xauusd_archive_audit_lab import (
    audit_xauusd_closedbar_archive_lab,
)

SCHEMA = "ATLASQUANT_MT5_XAUUSD_ONE_STEP_CLOCK_CAPTURE_AUDIT_LAB_V1"
MAX_W32TIME_STATUS_LENGTH = 16_384
MAX_SYNC_AGE_SECONDS = 3600
MAX_PHASE_OFFSET_SECONDS = 1.0
W32TIME_READONLY_QUERY = ("w32tm", "/query", "/status", "/verbose")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold())
                   if not unicodedata.combining(c))


def _number(s: Any) -> float | None:
    if not isinstance(s, str):
        return None
    match = re.match(r"\s*([+-]?\d+(?:[.,]\d+)?)\s*s?\b", s, flags=re.I)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def inspect_windows_time_status_lab(output: Any, *, returncode: Any) -> dict[str, Any]:
    """Read W32Time verbose text without claiming an independent time source."""
    result = {
        "state": "LAB_WINDOWS_TIME_PREFLIGHT_BLOCKED",
        "reason": "W32TIME_STATUS_UNAVAILABLE_OR_UNPARSEABLE",
        "clock_sync_candidate": False,
        "w32time_status_command_ok": False,
        "clock_source_present": False,
        "clock_source_obviously_local": None,
        "leap_indicator_zero": False,
        "last_sync_error_zero": False,
        "time_since_last_good_sync_seconds": None,
        "phase_offset_seconds_magnitude": None,
        "clock_utc_independently_attested": False,
        "network_time_server_independently_authenticated": False,
        "read_only": True,
    }
    if (type(output) is not str or not 1 <= len(output) <= MAX_W32TIME_STATUS_LENGTH
            or type(returncode) is not int or returncode != 0):
        return result
    result["w32time_status_command_ok"] = True
    data = {}
    for line in output.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[_fold(key.strip())] = value.strip()

    def find_value(*prefixes: str) -> str | None:
        return next((v for k, v in data.items()
                     if any(k.startswith(prefix) for prefix in prefixes)), None)

    source = find_value("source", "origem", "fonte")
    leap = _number(find_value("leap indicator", "indicador de salto"))
    sync_error = _number(find_value("last sync error", "ultimo erro de sincronizacao"))
    elapsed = find_value("time since last good sync time")
    if elapsed is None:
        elapsed = next((v for k, v in data.items()
                        if k.startswith("tempo desde") and "sincron" in k), None)
    sync_age = _number(elapsed)
    offset = _number(find_value("phase offset", "deslocamento de fase"))
    local = (
        not source or any(term in _fold(source) for term in (
            "local cmos", "free-running", "free running", "relogio local",
            "cmos local", "localhost", "0.0.0.0", "nao sincronizado",
            "unsynchronized", "unspecified", "sem origem"))
    )
    result.update({
        "clock_source_present": bool(source),
        "clock_source_obviously_local": local,
        "leap_indicator_zero": leap == 0,
        "last_sync_error_zero": sync_error == 0,
        "time_since_last_good_sync_seconds": sync_age,
        "phase_offset_seconds_magnitude": abs(offset) if offset is not None else None,
    })
    if local:
        result["reason"] = "NO_NONLOCAL_TIME_SOURCE_IN_W32TIME_STATUS"
    elif leap != 0 or sync_error != 0:
        result["reason"] = "W32TIME_LEAP_OR_LAST_SYNC_ERROR_NOT_ZERO"
    elif sync_age is None or not 0 <= sync_age <= MAX_SYNC_AGE_SECONDS:
        result["reason"] = "W32TIME_LAST_GOOD_SYNC_TOO_OLD_OR_MISSING"
    elif offset is None or abs(offset) > MAX_PHASE_OFFSET_SECONDS:
        result["reason"] = "W32TIME_PHASE_OFFSET_TOO_LARGE_OR_MISSING"
    else:
        result["state"] = "LAB_WINDOWS_TIME_OS_SYNC_CANDIDATE_UNATTESTED"
        result["reason"] = "W32TIME_LOCAL_STATUS_SELF_REPORT_ONLY_NOT_A_UTC_WITNESS"
        result["clock_sync_candidate"] = True
    return result


def _base() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_XAUUSD_ONE_STEP_BLOCKED",
        "reason": "CLOCK_PREFLIGHT_NOT_PASSED",
        "clock_preflight": None, "mt5_capture": None,
        "archive_audit": None, "verified_local_bars": 0,
        "archive_directory": None,
        "os_clock_independently_authenticated": False,
        "pepperstone_broker_identity_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "calibrated_probability": None, "validated_accuracy": None,
        "gold_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "publishable": False,
        "trade_authorized": False, "new_cost_brl": 0,
    }


def run_xauusd_one_step_lab(
    api: Any, *, terminal_path: Any, output_root: Any,
    clock: Callable[[], datetime], status_text: Any,
    status_returncode: Any,
) -> dict[str, Any]:
    """Only collect if W32Time looks recent, then independently audit all bars."""
    result = _base()
    status = inspect_windows_time_status_lab(status_text, returncode=status_returncode)
    result["clock_preflight"] = status
    if not status["clock_sync_candidate"]:
        result["reason"] = "CLOCK_PREFLIGHT_BLOCKED:" + status["reason"]
        return result
    capture = collect_xauusd_closedbar_snapshot_lab(
        api, terminal_path=terminal_path, output_root=output_root, clock=clock)
    result["mt5_capture"] = capture
    if capture["series_count"] != 3 or capture["verified_local_bars"] != 3700:
        result["reason"] = "MT5_CAPTURE_BLOCKED:" + capture["reason"]
        return result
    root = Path(capture["directory"])
    result["archive_directory"] = str(root)
    audit = audit_xauusd_closedbar_archive_lab(root)
    result["archive_audit"] = audit
    if audit["status"] != "LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED":
        result["reason"] = "XAUUSD_ARCHIVE_INDEPENDENT_AUDIT_FAILED"
        return result
    result.update({
        "state": "LAB_XAUUSD_ONE_STEP_LOCAL_ARCHIVE_READY_UNATTESTED",
        "reason": "OS_TIME_BROKER_CANDLES_AND_PIT_NOT_INDEPENDENTLY_ATTESTED",
        "verified_local_bars": 3700,
    })
    return result


def _query_w32time_status() -> tuple[str, int]:
    try:
        done = subprocess.run(W32TIME_READONLY_QUERY, capture_output=True,
                              timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "", 2
    if done.returncode != 0:
        return "", int(done.returncode)
    candidates = [done.stdout.decode(codec, errors="replace")
                  for codec in ("utf-8", "cp850", "cp1252")]
    # Use an encoding only if all mandatory status fields survived decoding.
    for candidate in candidates:
        if inspect_windows_time_status_lab(candidate, returncode=0)["clock_sync_candidate"]:
            return candidate, 0
    return candidates[0], 0


def main() -> int:
    parser = argparse.ArgumentParser(description="One-step, strictly read-only XAUUSD capture+audit")
    parser.add_argument("--terminal-path", required=True,
                        help="Explicit Windows path of already open terminal64.exe")
    args = parser.parse_args()
    if os.name != "nt":
        print(json.dumps({"status": "BLOCKED", "reason": "WINDOWS_ONLY"}))
        return 2
    local_data = os.environ.get("LOCALAPPDATA")
    if not local_data:
        print(json.dumps({"status": "BLOCKED", "reason": "LOCALAPPDATA_MISSING"}))
        return 2
    status_text, status_rc = _query_w32time_status()
    clock_status = inspect_windows_time_status_lab(status_text, returncode=status_rc)
    if not clock_status["clock_sync_candidate"]:
        print(json.dumps({"status": "BLOCKED_NO_MT5_CALLED", "clock_preflight": clock_status},
                         ensure_ascii=False, indent=2))
        return 2
    try:
        import MetaTrader5 as mt5  # Only after clock preflight passes.
    except ImportError:
        print(json.dumps({"status": "BLOCKED", "reason": "METATRADER5_PYTHON_NOT_INSTALLED"}))
        return 2
    root = Path(local_data) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
    report = run_xauusd_one_step_lab(
        mt5, terminal_path=args.terminal_path, output_root=root,
        clock=lambda: datetime.now(timezone.utc).replace(microsecond=0),
        status_text=status_text, status_returncode=status_rc)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["state"] == "LAB_XAUUSD_ONE_STEP_LOCAL_ARCHIVE_READY_UNATTESTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
