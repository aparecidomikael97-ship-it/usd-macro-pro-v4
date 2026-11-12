"""Read-only Windows W32Time diagnosis for AtlasQuant/MT5 timestamp quality.

Never changes Windows settings, peers, registry or firewall. The diagnosis is
only a local OS self-report, not proof of trusted UTC or NTP reachability.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from typing import Any, Callable

from atlasquant_mt5_xauusd_one_step_lab import (
    _fold, inspect_windows_time_status_lab,
)

SCHEMA = "ATLASQUANT_WINDOWS_TIME_READONLY_DIAGNOSTIC_LAB_V1"
QUERIES = {
    "service": ("sc.exe", "query", "w32time"),
    "status": ("w32tm", "/query", "/status", "/verbose"),
    "source": ("w32tm", "/query", "/source"),
    "peers": ("w32tm", "/query", "/peers"),
    "configuration": ("w32tm", "/query", "/configuration"),
}
MAX_OUTPUT_CHARS = 32_768


def _count_peers(text: str) -> int | None:
    folded = _fold(text)
    for line in folded.splitlines():
        if re.search(r"(?:#\s*peers|num(?:ero)?\s+de\s+pares|n[.o°\s]*de\s+pares)\s*:", line):
            found = re.search(r":\s*(\d+)\b", line)
            if found:
                return int(found.group(1))
    return None


def _configured_ntp(text: str) -> bool | None:
    for line in _fold(text).splitlines():
        if re.match(r"^\s*ntpserver\s*:", line):
            value = line.split(":", 1)[1].strip()
            # A placeholder or disabled empty field is NOT a usable peer.
            return bool(value) and value not in ("(local)", "(padrao)", "none", "0.0.0.0")
    return None


def _running(text: str) -> bool | None:
    for line in _fold(text).splitlines():
        if re.search(r"(?:^|\s)(?:state|estado)\s*:\s*", line):
            match = re.search(r":\s*([1-7])\b", line)
            if match:
                return int(match.group(1)) == 4
    return None


def _source_local(text: str) -> bool | None:
    value = _fold(text).strip()
    if not value or "erro" in value or "error" in value:
        return None
    return any(x in value for x in (
        "local cmos", "cmos local", "relogio local", "free-running",
        "free running", "0.0.0.0", "unspecified", "nao sincronizado"))


def diagnose_windows_time_readonly_lab(
    responses: Any,
) -> dict[str, Any]:
    """Consume a mapping of command name -> (exit code, stdout) only."""
    result = {
        "schema": SCHEMA, "state": "LAB_WINDOWS_TIME_DIAG_INCONCLUSIVE",
        "reason": "MISSING_READONLY_DIAGNOSTIC_OUTPUT",
        "queries_expected": sorted(QUERIES), "queries_ok": [],
        "service_running": None, "peers_reported": None,
        "configured_ntp_peer_present": None,
        "current_source_obviously_local": None,
        "os_sync_candidate": False, "clock_preflight_reason": None,
        "ntp_udp123_or_dns_failure_proven": False,
        "independent_utc_attestation": False,
        "mt5_or_broker_accessed": False,
        "settings_changed": False, "firewall_changed": False,
        "trade_authorized": False, "operational_bias": "AGUARDAR",
        "new_cost_brl": 0,
    }
    if not isinstance(responses, dict) or set(responses) != set(QUERIES):
        return result
    parsed = {}
    for key in QUERIES:
        item = responses.get(key)
        if (not isinstance(item, tuple) or len(item) != 2
                or type(item[0]) is not int or not isinstance(item[1], str)
                or len(item[1]) > MAX_OUTPUT_CHARS):
            return result
        code, raw = item
        if code == 0:
            result["queries_ok"].append(key)
        parsed[key] = raw if code == 0 else ""
    result["service_running"] = _running(parsed["service"])
    result["peers_reported"] = _count_peers(parsed["peers"])
    result["configured_ntp_peer_present"] = _configured_ntp(parsed["configuration"])
    result["current_source_obviously_local"] = _source_local(parsed["source"])
    clock_status = inspect_windows_time_status_lab(
        parsed["status"], returncode=responses["status"][0])
    result["clock_preflight_reason"] = clock_status["reason"]
    result["os_sync_candidate"] = clock_status["clock_sync_candidate"]

    if result["service_running"] is False:
        result.update(state="LAB_W32TIME_SERVICE_STOPPED_CANDIDATE",
                      reason="SERVICE_NOT_RUNNING_CHECK_WITH_WINDOWS_ADMIN")
    elif result["service_running"] is None:
        result["reason"] = "SERVICE_STATUS_NOT_READABLE"
    elif clock_status["clock_sync_candidate"]:
        result.update(state="LAB_W32TIME_OS_SYNC_CANDIDATE_UNATTESTED",
                      reason="OS_STATUS_LOOKS_RECENT_BUT_NO_INDEPENDENT_UTC_WITNESS")
    elif (result["current_source_obviously_local"] is True
          and result["peers_reported"] == 0
          and result["configured_ntp_peer_present"] is False):
        result.update(state="LAB_W32TIME_NO_PEER_CONFIGURATION_CANDIDATE",
                      reason="NO_CONFIGURED_NTP_PEER_NEEDS_USER_REVIEW")
    elif result["current_source_obviously_local"] is True:
        result.update(state="LAB_W32TIME_STUCK_ON_LOCAL_CLOCK_CANDIDATE",
                      reason="TIME_SOURCE_LOCAL_CHECK_PEER_DNS_UDP123")
    elif (result["peers_reported"] is not None
          and result["peers_reported"] > 0
          and result["configured_ntp_peer_present"] is True):
        result.update(state="LAB_W32TIME_PEERS_PRESENT_SYNC_FAILURE_CANDIDATE",
                      reason="CHECK_DNS_UDP123_OR_REMOTE_NTP_REPLY_WITH_AUTHORIZED_DIAGNOSTICS")
    elif len(result["queries_ok"]) < len(QUERIES):
        result["reason"] = "SOME_W32TIME_READONLY_QUERIES_FAILED"
    else:
        result["reason"] = "W32TIME_DIAG_UNCERTAIN_REVIEW_RAW_OUTPUT_LOCALLY"
    return result


def _query_readonly(command: tuple[str, ...]) -> tuple[int, str]:
    try:
        done = subprocess.run(command, capture_output=True,
                              timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 2, ""
    if done.returncode != 0:
        return int(done.returncode), ""
    for encoding in ("utf-8", "cp850", "cp1252"):
        decoded = done.stdout.decode(encoding, errors="replace")
        if "\ufffd" not in decoded:
            return 0, decoded
    return 0, done.stdout.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose W32Time without changing settings")
    parser.parse_args()
    if os.name != "nt":
        print(json.dumps({"status": "BLOCKED", "reason": "WINDOWS_ONLY"}))
        return 2
    output = diagnose_windows_time_readonly_lab({
        name: _query_readonly(command) for name, command in QUERIES.items()})
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["state"] == "LAB_W32TIME_OS_SYNC_CANDIDATE_UNATTESTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
