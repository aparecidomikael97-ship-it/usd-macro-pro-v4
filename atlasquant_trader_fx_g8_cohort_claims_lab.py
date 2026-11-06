"""Offline audit of *claimed* G8 D1/W1 trial entries, never market signals.

The frozen cohort is immutable; this separately supplied ledger may be partial.
All timestamps, evidence hashes and model labels are self-declared. In particular,
acceptance here is NOT an independent precommit, verified source, or backtest.
No HTTP, broker access, persistence, scheduling or trades occur.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_fx_g8_frozen_cohort_lab import (
    EXPECTED_COUNT, inspect_g8_forward_cohort_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_G8_COHORT_CLAIMS_LAB_V1"
KIND = "MANUAL_RESEARCH_CLAIMS_UNATTESTED"
MODEL = "LAB_MACRO_HYPOTHESIS_WEIGHTS_V1_UNCALIBRATED"
DIRECTIONS = frozenset(("ALTA", "BAIXA"))
ABSTENTIONS = frozenset(("NEUTRO", "AGUARDAR"))
ABSTENTION_REASONS = frozenset((
    "INSUFFICIENT_PIT_MACRO", "CONFLICTING_EVIDENCE",
    "UNVERIFIED_SOURCE", "NO_CALIBRATED_MODEL",
))
FIELDS = frozenset(("schema", "research_kind", "cohort_id",
                    "cohort_sha256", "entries"))
ENTRY_FIELDS = frozenset(("slot_id", "pair", "horizon", "direction_claim",
                          "created_at_utc", "data_cutoff_utc", "model_version",
                          "evidence_sha256", "abstention_reason"))
SHA = re.compile(r"[0-9a-f]{64}\Z")
UTC = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
MAX_BYTES = 33000


def _baseline(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "cohort_sha256": None, "declared_slots": EXPECTED_COUNT,
        "submitted_slots": 0, "missing_slots": EXPECTED_COUNT,
        "directional_claims": 0, "neutral_abstentions": 0,
        "await_abstentions": 0, "coverage_fraction": 0.0,
        "missing_slot_ids": [], "aligned_d1_w1_pairs": [],
        "opposed_d1_w1_pairs": [],
        "claim_creation_times_self_declared": True,
        "macro_evidence_hashes_self_declared": True,
        "independent_external_precommit_witness_verified": False,
        "source_publication_times_verified": False,
        "macro_data_point_in_time_verified": False,
        "algorithm_frozen_before_forecasts_verified": False,
        "future_price_outcomes_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "probability_calibrated": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, str) or UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _now(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def inspect_g8_cohort_claims_lab(
    *, cohort_raw: Any, claims_raw: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Count every claimed decision and gap; never score or certify a forecast.

    Individual entries must match the already-frozen 56-slot manifest. An
    arbitrary claim with an old creation timestamp cannot prove precommit.
    """
    out = _baseline("INVALID_COHORT_CLAIMS_OR_INSPECTION_CLOCK")
    now = _now(inspected_at_utc)
    if (now is None or not isinstance(cohort_raw, bytes)
            or not isinstance(claims_raw, bytes)
            or not 100 <= len(claims_raw) <= MAX_BYTES):
        return out
    cohort_audit = inspect_g8_forward_cohort_lab(
        cohort_raw, inspected_at_utc=now)
    if not cohort_audit["all_56_slots_unmodified"]:
        out["reason"] = "FROZEN_COHORT_INVALID_OR_NOT_YET_CREATED"
        return out
    try:
        cohort = json.loads(cohort_raw.decode("utf-8", "strict"))
        claims = json.loads(
            claims_raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique_fields,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
        )
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        out["reason"] = "INVALID_OR_DUPLICATED_JSON"
        return out
    cohort_hash = sha256(cohort_raw).hexdigest()
    if (not isinstance(claims, dict) or set(claims) != FIELDS
            or claims["schema"] != SCHEMA or claims["research_kind"] != KIND
            or claims["cohort_id"] != cohort["cohort_id"]
            or claims["cohort_sha256"] != cohort_hash):
        out["reason"] = "CLAIMS_NOT_BOUND_TO_EXACT_COHORT_BYTES"
        return out
    rows = claims["entries"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= EXPECTED_COUNT:
        out["reason"] = "CLAIM_COUNT_OUT_OF_RANGE"
        return out
    expected = {s["slot_id"]: s for s in cohort["slots"]}
    planned = _clock(cohort["planning_reference_utc_claim"])
    if planned is None:
        out["reason"] = "FROZEN_COHORT_PLANNING_CLOCK_INVALID"
        return out
    submitted: dict[str, dict[str, Any]] = {}
    counts = {"ALTA": 0, "BAIXA": 0, "NEUTRO": 0, "AGUARDAR": 0}
    for row in rows:
        if not isinstance(row, dict) or set(row) != ENTRY_FIELDS:
            out["reason"] = "CLAIM_FIELDS_INVALID"
            return out
        slot_id = row["slot_id"]
        if (not isinstance(slot_id, str) or slot_id not in expected
                or slot_id in submitted):
            out["reason"] = "UNKNOWN_OR_DUPLICATE_SLOT"
            return out
        slot = expected[slot_id]
        if row["pair"] != slot["pair"] or row["horizon"] != slot["horizon"]:
            out["reason"] = "SLOT_PAIR_OR_HORIZON_MISMATCH"
            return out
        direction = row["direction_claim"]
        if not isinstance(direction, str) or direction not in DIRECTIONS | ABSTENTIONS:
            out["reason"] = "CLAIM_DIRECTION_INVALID"
            return out
        created, cutoff = _clock(row["created_at_utc"]), _clock(row["data_cutoff_utc"])
        deadline = _clock(slot["precommit_deadline_utc"])
        if (created is None or deadline is None or created < planned or created > now
                or created > deadline):
            out["reason"] = "CLAIM_CREATION_NOT_BEFORE_PRECOMMIT_DEADLINE"
            return out
        if direction == "AGUARDAR":
            if (row["data_cutoff_utc"] is not None
                    or row["model_version"] is not None
                    or row["evidence_sha256"] is not None
                    or not isinstance(row["abstention_reason"], str)
                    or row["abstention_reason"] not in ABSTENTION_REASONS):
                out["reason"] = "AWAIT_MUST_DECLARE_MISSING_EVIDENCE"
                return out
        elif (cutoff is None or cutoff > created or row["model_version"] != MODEL
              or not isinstance(row["evidence_sha256"], str)
              or SHA.fullmatch(row["evidence_sha256"]) is None
              or row["abstention_reason"] is not None):
            out["reason"] = "DIRECTION_OR_NEUTRAL_NEEDS_FROZEN_MODEL_AND_EVIDENCE"
            return out
        submitted[slot_id] = row
        counts[direction] += 1
    by_pair: dict[str, dict[str, str]] = {}
    for row in submitted.values():
        by_pair.setdefault(row["pair"], {})[row["horizon"]] = row["direction_claim"]
    aligned, opposed = [], []
    for pair, horizons in sorted(by_pair.items()):
        d1, w1 = horizons.get("D1"), horizons.get("W1")
        if d1 in DIRECTIONS and w1 in DIRECTIONS:
            (aligned if d1 == w1 else opposed).append(pair)
    missing = sorted(set(expected) - set(submitted))
    before_deadline = cohort_audit["still_before_60_minute_precommit_deadline"]
    out.update({
        "state": ("LAB_CLAIMS_STAGED_BEFORE_DEADLINE_UNATTESTED"
                  if before_deadline else "LAB_ARCHIVAL_CLAIMS_AFTER_DEADLINE_UNATTESTED"),
        "reason": "CLAIMED_BYTES_AND_TIMES_ARE_NOT_EXTERNAL_PRECOMMIT_PROOF",
        "cohort_sha256": cohort_hash,
        "submitted_slots": len(submitted), "missing_slots": len(missing),
        "directional_claims": counts["ALTA"] + counts["BAIXA"],
        "neutral_abstentions": counts["NEUTRO"],
        "await_abstentions": counts["AGUARDAR"],
        "coverage_fraction": len(submitted) / EXPECTED_COUNT,
        "missing_slot_ids": missing,
        "aligned_d1_w1_pairs": aligned,
        "opposed_d1_w1_pairs": opposed,
    })
    return out


__all__ = ["SCHEMA", "KIND", "MODEL", "inspect_g8_cohort_claims_lab"]
