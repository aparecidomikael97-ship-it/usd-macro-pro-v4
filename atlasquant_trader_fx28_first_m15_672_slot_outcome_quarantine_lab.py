"""Read-only linkage: failed nominal Sunday M15 -> frozen 672 D1/W1 slots.

The ONE physically observed first-15-minute interval is shared by both
the D1 and W1 windows. If all 28 start prices are absent, that blocks
documentary outcome labeling for 56 pair-horizon slots, NOT 56 separate
price fetches, 56 wrong forecasts, or 56 losing trades.

The archive verifier reads existing files; the ledger is rebuilt offline.
Never rerun MT5, substitute the first available Monday bar, edit frozen
calendar, backfill predictions, or compute accuracy. The input may still be
a fabricated local archive: no broker or independent PIT authentication.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_first_m15_archive_census_readonly_lab import (
    inspect_first_m15_archive_census_lab,
)
from atlasquant_trader_fx28_ny17_672_slot_issuance_ledger_lab import (
    inspect_fx28_ny17_672_slot_issuance_ledger_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC,
)

SCHEMA = "ATLASQUANT_FX28_FIRST_M15_672_SLOT_OUTCOME_QUARANTINE_LAB_V1"
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
ARCHIVE_MISSING = "LAB_FX28_FIRST_M15_ALL_28_MISSING_PRICE_INSUFFICIENT_NO_GO"
LEDGER_ACCEPTED = "LAB_FX28_672_SLOTS_ACCOUNTED_UNATTESTED_NO_GO"
STATUS = "NOMINAL_START_M15_NOT_OBSERVED_OUTCOME_UNLABELABLE_CLAIM_ONLY"
FIRST_WINDOW_UTC = datetime(2026, 11, 15, 22, tzinfo=timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_FIRST_M15_672_SLOT_LINK_BLOCKED_NO_GO",
        "reason": reason,
        "frozen_total_pair_horizon_slots": 672,
        "ledger_slots_accounted": 0,
        "first_window_pair_horizon_slots": 0,
        "first_window_d1_slots": 0,
        "first_window_w1_slots": 0,
        "distinct_nominal_m15_start_price_checks": 28,
        "missing_distinct_nominal_m15_start_prices": None,
        "quarantined_first_window_slots": 0,
        "other_frozen_slots_not_assessed": 672,
        "first_window_rows": [],
        "claimed_issuance_summary": None,
        "archive_manifest_sha256": None,
        "attempt_claim_sha256": None,
        "github_witness_absence_independently_verified": False,
        "pre_event_predictions_authenticated": 0,
        "broker_price_source_independently_authenticated": False,
        "first_seen_broker_utc_authenticated": False,
        "price_source_may_be_local_or_untrusted": True,
        "validate_historical_accuracy": False,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "mt5_calls": 0,
        "http_requests": 0,
        "file_writes": 0,
    }


def inspect_first_m15_672_slot_outcome_quarantine_lab(
    *, archive_root: Any, window_claims: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Recompute frozen ledger; inspect exactly one local archive, offline.

    `window_claims=[]` is only an empty caller-supplied input. It is not
    evidence that no forecast was published to GitHub or elsewhere.
    """
    result = _blocked("INVALID_CLOCK_ARCHIVE_ROOT_OR_LEDGER_INPUT")
    if (not isinstance(archive_root, Path) or not archive_root.is_absolute()
            or not isinstance(window_claims, (list, tuple))
            or not isinstance(inspected_at_utc, datetime)
            or inspected_at_utc.tzinfo is None
            or inspected_at_utc.utcoffset() is None
            or inspected_at_utc.microsecond):
        return result
    now = inspected_at_utc.astimezone(timezone.utc)
    if now < FIRST_WINDOW_UTC:
        result["reason"] = "FROZEN_FIRST_WINDOW_NOT_STARTED"
        return result
    if FROZEN_START_UTC != FIRST_WINDOW_UTC or len(OFFICIAL_PAIRS) != 28:
        result["reason"] = "FROZEN_START_OR_FX28_ROSTER_DRIFT"
        return result

    ledger = inspect_fx28_ny17_672_slot_issuance_ledger_lab(
        window_claims=window_claims, inspected_at_utc=now)
    if (ledger.get("state") != LEDGER_ACCEPTED
            or ledger.get("slots_expected") != 672
            or ledger.get("slots_accounted") != 672
            or len(ledger.get("slots", [])) != 672
            or ledger.get("independently_authenticated_forecasts") != 0
            or ledger.get("absence_of_github_witness_independently_verified") is not False
            or ledger.get("validated_directional_accuracy") is not None
            or ledger.get("trade_authorized") is not False):
        result["reason"] = "FROZEN_672_SLOT_LEDGER_INCOMPLETE_OR_UNVERIFIED"
        return result

    archive = inspect_first_m15_archive_census_lab(
        archive_root=archive_root, inspected_at_utc=now)
    if archive.get("state") != ARCHIVE_MISSING:
        result["reason"] = "ARCHIVE_NOT_CONFIRMED_ALL_28_NOMINAL_M15_ABSENT"
        return result
    hashes = (archive.get("archive_manifest_sha256"),
              archive.get("attempt_claim_marker_sha256"))
    if (archive.get("candidate_window_artifact_count") != 1
            or archive.get("attempt_claim_marker_present") is not True
            or any(type(v) is not str or SHA64.fullmatch(v) is None
                   or v == "0" * 64 for v in hashes)
            or archive.get("symbol_hashes_verified") != 28
            or archive.get("m15_rows_semantically_verified") != 0
            or archive.get("missing_expected_m15_open_count") != 28
            or archive.get("all_28_nominal_m15_missing") is not True
            or archive.get("source_observation_class") !=
                "28_VALID_EMPTY_ARRAY_CLAIMS_LOCAL_ONLY"
            or archive.get("broker_source_independently_authenticated") is not False
            or archive.get("trade_authorized") is not False
            or (archive.get("mt5_calls"), archive.get("file_writes"),
                archive.get("http_requests")) != (0, 0, 0)):
        result["reason"] = "INCOMPLETE_OR_UNSAFE_M15_ARCHIVE_CENSUS"
        return result

    first = [row for row in ledger["slots"]
             if row.get("window_start_utc") == FIRST_WINDOW_UTC.isoformat()]
    d1 = [r for r in first if r.get("horizon") == "D1"]
    w1 = [r for r in first if r.get("horizon") == "W1"]
    official = set(OFFICIAL_PAIRS)
    if (len(first) != 56 or len(d1) != 28 or len(w1) != 28
            or set(r.get("pair") for r in d1) != official
            or set(r.get("pair") for r in w1) != official
            or any(r.get("broker_price_verified") is not False
                   or r.get("forecast_issued_independently_verified") is not False
                   or r.get("trade_authorized") is not False
                   for r in first)):
        result["reason"] = "FIRST_D1_W1_WINDOW_NOT_56_DISTINCT_FROZEN_SLOTS"
        return result

    result.update({
        "state": "LAB_FX28_FIRST_M15_56_OUTCOMES_QUARANTINED_NO_GO",
        "reason": "LOCAL_NOMINAL_START_PRICE_ABSENT_IN_28_PAIRS_D1_W1_NOT_SCOREABLE",
        "ledger_slots_accounted": 672,
        "first_window_pair_horizon_slots": 56,
        "first_window_d1_slots": 28,
        "first_window_w1_slots": 28,
        "missing_distinct_nominal_m15_start_prices": 28,
        "quarantined_first_window_slots": 56,
        "other_frozen_slots_not_assessed": 616,
        "claimed_issuance_summary": {
            "not_yet_due_slots": ledger["not_yet_due_slots"],
            "not_issued_before_window_slots_in_caller_input":
                ledger["not_issued_before_window_slots"],
            "past_unattested_claim_slots":
                ledger["past_unattested_claim_slots"],
        },
        "archive_manifest_sha256": hashes[0],
        "attempt_claim_sha256": hashes[1],
        "first_window_rows": [
            {
                "pair": row["pair"],
                "horizon": row["horizon"],
                "slot_id": row["slot_id"],
                "nominal_window_start_utc": row["window_start_utc"],
                "forecast_issuance_claim_only": row["issuance_accounting_status"],
                "nominal_start_price_status": STATUS,
                "scored_as_hit": False,
                "scored_as_miss": False,
                "scored_as_trade": False,
                "broker_price_authenticated": False,
            }
            for row in first
        ],
    })
    return result


__all__ = (
    "SCHEMA", "STATUS", "inspect_first_m15_672_slot_outcome_quarantine_lab",
)
