"""Fail-closed 28-FX batch audit of caller-provided M15 archives.

Runs each pair through the independently unit-tested local CSV.gz -> NY17
coverage gate. This module has NO access to MT5, disks, accounts or network.
A batch-level pass means only caller-supplied archived bytes and manifest
claims were structurally self-consistent for a requested time window.
It is NEVER historical price provenance or validated trading accuracy.

Missing, duplicate, extra or malformed pair payloads are not ignored:
none of those cases may be reported as 'all 28 FX complete'.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_m15_ny17_archive_join_lab import (
    inspect_mt5_m15_archive_ny17_join_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MT5_28FX_M15_NY17_BATCH_LAB_V1"
VALID = "LAB_MT5_M15_ARCHIVE_NY17_LOCAL_JOIN_NO_GO"
PAYLOAD_KEYS = frozenset({
    "manifest_record", "compressed_csv_gz", "archive_captured_at_utc",
})


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_MT5_28FX_M15_BATCH_BLOCKED",
        "reason": reason,
        "horizon": None, "expected_pair_count": 28,
        "received_pair_count": 0,
        "missing_pairs": [],
        "unexpected_pairs": [],
        "coverage_claim_complete_pairs": 0,
        "coverage_claim_blocked_pairs": 0,
        "all_28_local_archive_window_checks_passed": False,
        "pair_results": {},
        "source_archive_hashes_independently_attested": False,
        "broker_identity_independently_verified": False,
        "broker_calendar_independently_verified": False,
        "broker_price_origins_independently_verified": False,
        "point_in_time_market_evidence_verified": False,
        "precommitted_biases_independently_verified": False,
        "historical_directional_accuracy_validated": False,
        "cross_pair_independence_verified": False,
        "calibrated_direction_probability": None,
        "directional_bias": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "can_feed_live_radar": False,
        "trade_authorized": False, "live_alert_allowed": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_28fx_m15_archive_batch_lab(
    *, snapshots_by_pair: Any, horizon: Any,
    start_at_utc: Any, end_at_utc: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Audit ONE NY17 research window across exactly the 28 canonical pairs.

    Each supplied snapshot record must have the keys in PAYLOAD_KEYS.
    Return an explicit result even for pairs with failed coverage, rather
    than quietly dropping unfavorable or missing price periods.
    """
    out = _base("INVALID_BATCH_INPUT_OR_HORIZON")
    if (horizon not in ("D1", "W1")
            or not isinstance(snapshots_by_pair, Mapping)
            or len(OFFICIAL_PAIRS) != 28):
        return out
    try:
        supplied = set(snapshots_by_pair)
    except (TypeError, ValueError):
        return out
    if any(not isinstance(k, str) for k in supplied):
        return out
    expected = set(OFFICIAL_PAIRS)
    missing = [pair for pair in OFFICIAL_PAIRS if pair not in supplied]
    extra = sorted(supplied - expected)
    out.update(horizon=horizon, received_pair_count=len(supplied),
               missing_pairs=missing, unexpected_pairs=extra)
    if missing or extra:
        out["reason"] = "INCOMPLETE_OR_EXTRA_28FX_PAIR_INVENTORY"
        return out

    all_results = {}
    passed = 0
    for pair in OFFICIAL_PAIRS:
        payload = snapshots_by_pair[pair]
        if not isinstance(payload, Mapping) or set(payload) != PAYLOAD_KEYS:
            all_results[pair] = {
                "state": "LAB_MT5_M15_ARCHIVE_NY17_JOIN_BLOCKED",
                "reason": "INVALID_ARCHIVE_PAYLOAD_KEYS_OR_TYPE",
                "m15_rows_examined": 0,
                "window_m15_rows_found": 0,
                "window_expected_m15_rows": None,
            }
            continue
        result = inspect_mt5_m15_archive_ny17_join_lab(
            pair=pair, horizon=horizon,
            start_at_utc=start_at_utc, end_at_utc=end_at_utc,
            evaluated_at_utc=evaluated_at_utc,
            manifest_record=payload["manifest_record"],
            compressed_csv_gz=payload["compressed_csv_gz"],
            archive_captured_at_utc=payload["archive_captured_at_utc"],
        )
        passed += int(result["state"] == VALID)
        all_results[pair] = {
            "state": result["state"], "reason": result["reason"],
            "m15_rows_examined": result["m15_rows_examined"],
            "window_m15_rows_found": result["window_m15_rows_found"],
            "window_expected_m15_rows": result["window_expected_m15_rows"],
            "manifest_local_hash_consistent": result[
                "manifest_local_hash_consistent"],
        }

    # 'All checks passed' refers only to locally consistent *claims* and
    # NEVER a market-ready bias, performance result or broker provenance.
    out.update({
        "state": ("LAB_MT5_28FX_WINDOW_LOCAL_CLAIMS_ONLY_NO_GO"
                  if passed == 28
                  else "LAB_MT5_28FX_WINDOW_INCOMPLETE_NO_GO"),
        "reason": ("LOCAL_ARCHIVE_COVERAGE_NOT_REAL_BROKER_ATTESTATION"
                   if passed == 28
                   else "ONE_OR_MORE_PAIR_ARCHIVES_BLOCKED_NO_SKIP"),
        "coverage_claim_complete_pairs": passed,
        "coverage_claim_blocked_pairs": 28 - passed,
        "all_28_local_archive_window_checks_passed": passed == 28,
        "pair_results": all_results,
    })
    return out


__all__ = ("SCHEMA", "inspect_28fx_m15_archive_batch_lab")
