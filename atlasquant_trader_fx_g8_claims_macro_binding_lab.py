"""Bind G8/28 D1/W1 prospective claims to ACTUAL supplied macro bytes.

The earlier cohort-claims validator only checks a self-declared 64-hex
evidence_sha256. This additional offline gate re-hashes original macro JSON,
checks two-sided CPI/policy metadata and compares all record times with the
claimed forecast cutoff. It does NOT authenticate macro issuers, calendar
vintages, external pre-registration timestamps or any price outcome.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_fx_g8_cohort_claims_lab import (
    inspect_g8_cohort_claims_lab,
)
from atlasquant_trader_g8_macro_asof_lab import (
    inspect_g8_pair_macro_asof_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_G8_CLAIMED_MACRO_BYTES_BINDING_LAB_V1"
CLAIMS_OK = frozenset((
    "LAB_CLAIMS_STAGED_BEFORE_DEADLINE_UNATTESTED",
    "LAB_ARCHIVAL_CLAIMS_AFTER_DEADLINE_UNATTESTED",
))
MACRO_OK = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"
MAX_TOTAL_BYTES = 1_000_000
REQUIRES_EVIDENCE = frozenset(("ALTA", "BAIXA", "NEUTRO"))


def _baseline(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "cohort_sha256": None, "claims_sha256": None,
        "total_slots": 56, "submitted_slots": 0, "missing_slots": 56,
        "await_abstentions": 0, "directional_claims": 0,
        "neutral_abstentions": 0,
        "evidence_requiring_slots": 0, "macro_bytes_bound_slots": 0,
        "macro_binding_receipt_sha256": None,
        "first_failed_slot_id": None,
        "claims_still_before_precommit_deadline": False,
        "all_submitted_required_macro_bytes_hash_bound": False,
        "all_submitted_required_macro_times_consistent": False,
        "macro_source_independently_authenticated": False,
        "source_publication_times_independently_verified": False,
        "point_in_time_macro_vintage_independently_verified": False,
        "external_precommit_timestamp_independently_witnessed": False,
        "model_calibration_verified": False,
        "independent_d1_w1_future_prices_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(s: str) -> datetime:
    # The parent validator already enforced the canonical '...Z' format.
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def inspect_g8_claims_macro_bytes_lab(
    *, cohort_raw: Any, claims_raw: Any,
    macro_bytes_by_slot: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Check raw bytes for EVERY declared ALTA/BAIXA/NEUTRO slot.

    AGUARDAR needs no macro input. Missing trial slots remain missing;
    structurally consistent entries are not externally witnessed predictions.
    """
    out = _baseline("INVALID_COHORT_CLAIMS_OR_MACRO_INPUT_MAPPING")
    claims_report = inspect_g8_cohort_claims_lab(
        cohort_raw=cohort_raw, claims_raw=claims_raw,
        inspected_at_utc=inspected_at_utc)
    if claims_report["state"] not in CLAIMS_OK:
        out["reason"] = "COHORT_OR_CLAIM_LEDGER_REJECTED"
        return out
    out.update({
        "cohort_sha256": claims_report["cohort_sha256"],
        "claims_sha256": sha256(claims_raw).hexdigest(),
        "submitted_slots": claims_report["submitted_slots"],
        "missing_slots": claims_report["missing_slots"],
        "await_abstentions": claims_report["await_abstentions"],
        "directional_claims": claims_report["directional_claims"],
        "neutral_abstentions": claims_report["neutral_abstentions"],
        "claims_still_before_precommit_deadline": (
            claims_report["state"] == "LAB_CLAIMS_STAGED_BEFORE_DEADLINE_UNATTESTED"),
    })
    if not isinstance(macro_bytes_by_slot, dict):
        return out
    # The prior validator has already rejected duplicate keys, non-finite
    # fields, extra fields and wrong cohort/slot times.
    rows = json.loads(claims_raw)["entries"]
    required = {r["slot_id"]: r for r in rows
                if r["direction_claim"] in REQUIRES_EVIDENCE}
    out["evidence_requiring_slots"] = len(required)
    if (set(macro_bytes_by_slot) != set(required)
            or any(not isinstance(b, bytes) for b in macro_bytes_by_slot.values())
            or sum(len(b) for b in macro_bytes_by_slot.values()) > MAX_TOTAL_BYTES):
        out["reason"] = "MISSING_EXTRA_NONBYTE_OR_EXCESSIVE_MACRO_EVIDENCE"
        return out

    if not required:
        # Full abstention coverage is valid as an inventory but cannot be
        # reported as macro proof: zero predictive claims were made.
        out.update({
            "state": "LAB_ONLY_ABSTENTIONS_NO_MACRO_EVIDENCE_NEEDED",
            "reason": "NO_DIRECTIONAL_OR_NEUTRAL_EVIDENCE_CLAIMS_TO_BIND",
        })
        return out

    bound_hashes: list[str] = []
    for slot_id, entry in sorted(required.items()):
        raw = macro_bytes_by_slot[slot_id]
        digest = sha256(raw).hexdigest()
        if digest != entry["evidence_sha256"]:
            out.update(reason="MACRO_HASH_DOES_NOT_MATCH_CLAIMED_BYTES",
                       first_failed_slot_id=slot_id)
            return out
        created = _utc(entry["created_at_utc"])
        cutoff = _utc(entry["data_cutoff_utc"])
        macro = inspect_g8_pair_macro_asof_lab(raw, as_of_utc=created)
        if (macro["state"] != MACRO_OK
                or macro["pair"] != entry["pair"]
                or macro["decision_at_utc"] != created.isoformat()):
            out.update(reason="MACRO_PAIR_CLOCK_OR_TWO_SIDED_RECEIPTS_INVALID",
                       first_failed_slot_id=slot_id)
            return out
        # Every record, including records not selected as current by the
        # macro validator, must have existed by the forecast data cutoff.
        records = json.loads(raw)["records"]
        if any(_utc(r["captured_at_utc"]) > cutoff
               or _utc(r["published_at_utc"]) > cutoff
               for r in records):
            out.update(reason="MACRO_RELEASE_OR_CAPTURE_AFTER_CLAIMED_DATA_CUTOFF",
                       first_failed_slot_id=slot_id)
            return out
        bound_hashes.append(f"{slot_id}:{digest}")
        out["macro_bytes_bound_slots"] += 1

    # A digest here binds the ordered set of slot/digest pairs for later
    # comparison. It is not a third-party timestamp or immutable storage.
    receipt = ("\n".join(bound_hashes) + "\n").encode("ascii")
    out.update({
        "state": "LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED",
        "reason": "CLAIMED_PUBLICATION_TIMES_AND_EXTERNAL_PRECOMMIT_NOT_VERIFIED",
        "macro_binding_receipt_sha256": sha256(receipt).hexdigest(),
        "all_submitted_required_macro_bytes_hash_bound": True,
        "all_submitted_required_macro_times_consistent": True,
    })
    return out


__all__ = ["SCHEMA", "inspect_g8_claims_macro_bytes_lab"]
