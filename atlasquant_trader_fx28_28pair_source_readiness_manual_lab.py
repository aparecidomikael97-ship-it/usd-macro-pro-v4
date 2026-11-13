"""AtlasQuant FX28 Motor A: one local report for every pair, NEVER a signal.

Explicit --audit = local READ ONLY; --capture-missing = opt-in at most five
bounded issuer GETs through the existing collector, followed by the exact
same read-only source audit. No action without an explicit flag. Does NOT
authenticate central-bank first-seen time, event vintage, CPI, broker prices,
live signal, or historical/forward accuracy. All directions remain AGUARDAR.

Generated JSON contains only source coverage and block reasons. It never
prints local paths, original bytes, account data, bank rates, or forecasts.
No scheduler, main deploy, MT5, orders, positions, buys or paid APIs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_five_bank_capture_once_lab import (
    SCHEMA as CAPTURE_SCHEMA,
    collect_five_missing_policy_sources_once_lab,
)
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    inspect_fx28_official_policy_archive_replay_lab,
)
from atlasquant_trader_fx28_policy_why_wait_matrix_lab import (
    explain_fx28_policy_wait_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_28PAIR_SOURCE_READINESS_MANUAL_LAB_V1"
_MODES = frozenset(("audit", "capture_missing"))
_ARCHIVE_STATES = frozenset((
    "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
    "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO",
))
_CAPTURE_STATES = frozenset((
    "LAB_FX28_FIVE_SOURCE_CAPTURE_LOCAL_REPLAY_ONLY_NO_GO",
    "LAB_FX28_FIVE_SOURCE_CAPTURE_PARTIAL_OR_BLOCKED_NO_GO",
))


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _base(reason: str, mode: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_28PAIR_READINESS_BLOCKED",
        "reason": reason,
        "mode": mode,
        "expected_pairs": 28,
        "pairs_explained": 0,
        "per_pair": [],
        "local_policy_sources_checked_codes": [],
        "local_policy_sources_checked_count": 0,
        "pairs_with_two_policy_sources_locally_checked": 0,
        "policy_sources_missing_or_rejected_codes": [],
        "suggested_next_collection_by_documentary_coverage": [],
        "manual_capture_reported_http_attempts": 0,
        "manual_capture_results": {},
        "first_seen_pit_authenticated": False,
        "central_bank_issuer_independently_authenticated": False,
        "bilateral_cpi_yoy_authenticated": False,
        "broker_m15_verified": False,
        "pre_event_forecasts_independently_witnessed": False,
        "forecast_or_accuracy_validated": False,
        "source_coverage_is_not_currency_strength": True,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "paid_data_requests": 0, "new_cost_brl": 0,
    }


def inspect_28pair_source_readiness_once_lab(
    *, mode: Any, local_appdata: Any,
    decision_clock: Callable[[], datetime] = _now,
    capture: Callable[..., dict[str, Any]] = collect_five_missing_policy_sources_once_lab,
    archive: Callable[..., dict[str, Any]] = inspect_fx28_official_policy_archive_replay_lab,
    explain: Callable[..., dict[str, Any]] = explain_fx28_policy_wait_lab,
) -> dict[str, Any]:
    """One explicit command; fail closed on bad local inputs or any gate.

    `capture`, `archive`, `explain` injection are for offline tests. In
    the manual CLI they are the exact existing vetted functions above.
    """
    out = _base("EXPLICIT_AUDIT_OR_CAPTURE_FLAG_REQUIRED")
    if type(mode) is not str or mode not in _MODES:
        return out
    out = _base("UNSAFE_LOCAL_APPDATA_OR_CLOCK", mode=mode)
    if (type(local_appdata) is not str or not local_appdata
            or not callable(decision_clock)):
        return out
    try:
        root = Path(local_appdata)
        if not root.is_absolute() or root.is_symlink():
            return out
        atlas = root / "AtlasQuant"
        lab = atlas / "LAB"
        folder = lab / "official_macro_receipts"
        if any(p.is_symlink() for p in (atlas, lab, folder)):
            return out
        if any(p.exists() and not p.is_dir() for p in (root, atlas, lab, folder)):
            return out
        if not folder.resolve(strict=False).is_relative_to(lab.resolve(strict=False)):
            return out
        inspected = decision_clock()
        if (not isinstance(inspected, datetime) or inspected.tzinfo is None
                or inspected.utcoffset() is None or inspected.microsecond):
            return out
        inspected = inspected.astimezone(timezone.utc)
    except (OSError, RuntimeError, TypeError, ValueError, OverflowError):
        return out

    if mode == "capture_missing":
        try:
            captured = capture(
                capture_missing=True, local_appdata=local_appdata,
                decision_clock=decision_clock)
        except (OSError, ValueError, TypeError, RuntimeError, KeyError,
                OverflowError):
            out["reason"] = "MANUAL_CAPTURE_THROWN_EXCEPTION"
            return out
        if (type(captured) is not dict
                or captured.get("schema") != CAPTURE_SCHEMA
                or captured.get("state") not in _CAPTURE_STATES
                or captured.get("operational_bias") != "AGUARDAR"
                or captured.get("trade_authorized") is not False
                or captured.get("publishable") is not False):
            out["reason"] = "MANUAL_CAPTURE_REJECTED_OR_INCOHERENT"
            return out
        attempts = captured.get("https_gets_attempted_or_started")
        source_states = captured.get("currency_results")
        if (type(attempts) is not int or not 0 <= attempts <= 5
                or type(source_states) is not dict
                or set(source_states) != {"GBP", "JPY", "CHF", "AUD", "NZD"}
                or any(type(x) is not str or len(x) > 120
                       for x in source_states.values())):
            out["reason"] = "MANUAL_CAPTURE_COUNTS_OR_SOURCE_STATUS_INVALID"
            return out
        out["manual_capture_reported_http_attempts"] = attempts
        out["manual_capture_results"] = source_states

    try:
        # Read AGAIN after explicit capture. Never compare a fresh capture
        # against the pre-capture clock, and never backdate a source.
        now = decision_clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or now.microsecond):
            out["reason"] = "POST_ACTION_CLOCK_INVALID"
            return out
        now = now.astimezone(timezone.utc)
        if now < inspected:
            out["reason"] = "POST_ACTION_CLOCK_REWOUND"
            return out
        report = archive(local_appdata=local_appdata, decision_at_utc=now)
    except (OSError, ValueError, TypeError, RuntimeError, KeyError,
            OverflowError):
        out["reason"] = "POLICY_REPLAY_RAISED_EXCEPTION"
        return out
    if type(report) is not dict or report.get("state") not in _ARCHIVE_STATES:
        out["reason"] = "POLICY_ARCHIVE_ABSENT_OR_REJECTED"
        return out
    try:
        explained = explain(archive_report=report)
    except (OSError, ValueError, TypeError, RuntimeError, KeyError,
            OverflowError):
        out["reason"] = "FX28_EXPLANATION_RAISED_EXCEPTION"
        return out
    if (type(explained) is not dict
            or explained.get("state") != "LAB_FX28_POLICY_WHY_WAIT_MATRIX_COMPLETE_NO_GO"
            or explained.get("operational_bias") != "AGUARDAR"
            or explained.get("trade_authorized") is not False
            or explained.get("publishable") is not False
            or explained.get("pairs_admitted_for_direction") != 0):
        out["reason"] = "FX28_EXPLANATION_NOT_ADMISSIBLE"
        return out

    rows = explained.get("per_pair")
    priorities = explained.get("next_policy_sources_to_collect")
    checked = report.get("currencies_locally_checked")
    if (type(rows) is not list or len(rows) != 28
            or type(priorities) is not list or type(checked) is not list
            or [x.get("pair") for x in rows if type(x) is dict] != list(OFFICIAL_PAIRS)
            or any(type(row) is not dict
                   or row.get("operational_bias") != "AGUARDAR"
                   or row.get("trade_authorized") is not False
                   or row.get("fx_direction_admissible") is not False
                   or row.get("independently_witnessed_directional_bias") is not None
                   for row in rows)):
        out["reason"] = "FX28_28_PAIR_ROSTER_OR_NO_GO_CONTRACT_INVALID"
        return out
    if (type(explained.get("pairs_with_two_policy_sources_locally_checked")) is not int
            or not 0 <= explained["pairs_with_two_policy_sources_locally_checked"] <= 28
            or len(set(checked)) != len(checked)):
        out["reason"] = "FX28_SUMMARY_COUNTER_INVALID"
        return out

    # Small, reviewed caller-facing schema; not full original bytes/paths,
    # policy rates, broker accounts or unverified probability.
    safe_rows = [{
        "pair": row["pair"],
        "base_currency": row["base_currency"],
        "quote_currency": row["quote_currency"],
        "local_policy_source_for_both": row["policy_originals_locally_checked"],
        "missing_policy_currencies": row["missing_policy_currency_codes"],
        "rejected_policy_currencies": row["rejected_policy_currencies"],
        "why_wait_code": row["why_wait_code"],
        "why_wait_explanation": row["why_wait_explanation"],
        "bias": "AGUARDAR",
        "trade_authorized": False,
    } for row in rows]
    missing_codes = sorted(set(report.get("currencies_missing", []))
                           | set(report.get("currencies_rejected", {})))
    out.update({
        "state": "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO",
        "reason": "DOCUMENTARY_SOURCE_COVERAGE_NOT_PIT_BILATERAL_MACRO_OR_TRADE",
        "pairs_explained": 28, "per_pair": safe_rows,
        "local_policy_sources_checked_codes": sorted(checked),
        "local_policy_sources_checked_count": len(checked),
        "pairs_with_two_policy_sources_locally_checked":
            explained["pairs_with_two_policy_sources_locally_checked"],
        "policy_sources_missing_or_rejected_codes": missing_codes,
        "suggested_next_collection_by_documentary_coverage": [{
            "currency": item["currency"],
            "hypothetical_additional_two_policy_source_pairs":
                item["hypothetical_additional_two_policy_source_pairs"],
            "source_state": item["current_source_state"],
            "direction_or_trade_enabled_by_capture": False,
        } for item in priorities],
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual FX28 source coverage, never a signal")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--audit", action="store_true",
                       help="Read only public-source archive (no HTTP or file writes)")
    group.add_argument("--capture-missing", action="store_true",
                       help="Explicitly opt in to <=5 original-issuer HTTPS GETs")
    args = parser.parse_args(argv)
    mode = "audit" if args.audit else "capture_missing" if args.capture_missing else None
    result = inspect_28pair_source_readiness_once_lab(
        mode=mode, local_appdata=os.environ.get("LOCALAPPDATA", ""))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == (
        "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())
