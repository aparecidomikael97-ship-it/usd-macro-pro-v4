"""Produce a canonical 56-slot G8 D1/W1 candidate for external precommit.

This module NEVER supplies predictions or contacts GitHub. Only a complete,
caller-provided claims ledger can be packaged, with every required macro
payload re-hashed and checked by existing validators. A local UTC clock, SHA,
Git author date or JSON timestamp is NOT independent pre-event testimony.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_fx_g8_claims_macro_binding_lab import (
    inspect_g8_claims_macro_bytes_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_G8_D1W1_PRECOMMIT_PACKET_LAB_V1"
KIND = "UNWITNESSED_OFFLINE_CANDIDATE_FOR_EXTERNAL_PIT_PRECOMMIT"
ALLOWED_BINDING_STATES = frozenset((
    "LAB_SUBMITTED_CLAIMS_MACRO_BYTES_BOUND_UNATTESTED",
    "LAB_ONLY_ABSTENTIONS_NO_MACRO_EVIDENCE_NEEDED",
))
MAX_PACKET_BYTES = 100_000


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "packet_bytes": None, "packet_sha256": None, "packet_size_bytes": None,
        "cohort_sha256": None, "claims_sha256": None,
        "total_slots": 56, "submitted_slots": 0, "unfilled_slots": 56,
        "directional_claims": 0, "neutral_abstentions": 0,
        "await_abstentions": 0, "macro_bytes_bound_slots": 0,
        "candidate_prepared_before_deadline_claim": False,
        "external_server_packet_witness_verified": False,
        "external_precommit_timestamp_independently_witnessed": False,
        "macroeconomic_release_vintage_independently_verified": False,
        "model_freeze_and_calibration_independently_verified": False,
        "future_market_prices_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "fx_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "can_feed_live_radar": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "new_cost_brl": 0,
    }


def prepare_g8_precommit_packet_lab(
    *, cohort_raw: Any, claims_raw: Any,
    macro_bytes_by_slot: Any, prepared_at_utc: Any,
) -> dict[str, Any]:
    """Assemble (never publish) one complete 56-slot precommit candidate.

    The caller is responsible for externally registering the exact returned
    bytes BEFORE the deadline, then preserving the server-issued witness.
    """
    out = _deny("CLOCK_OR_CLAIMS_NOT_READY_FOR_CANDIDATE_PRECOMMIT")
    now = _clock(prepared_at_utc)
    if now is None:
        return out
    binding = inspect_g8_claims_macro_bytes_lab(
        cohort_raw=cohort_raw, claims_raw=claims_raw,
        macro_bytes_by_slot=macro_bytes_by_slot, inspected_at_utc=now)
    if (binding["state"] not in ALLOWED_BINDING_STATES
            or binding["submitted_slots"] != 56
            or binding["missing_slots"] != 0
            or not binding["claims_still_before_precommit_deadline"]):
        out["reason"] = "INCOMPLETE_OR_LATE_OR_UNBOUND_56_SLOT_LEDGER"
        return out
    claims = json.loads(claims_raw)
    cohort = json.loads(cohort_raw)
    entries_by_id = {row["slot_id"]: row for row in claims["entries"]}
    # The canonical frozen cohort, not the researcher's preferred order,
    # decides the ordering of all 56 slots in the published packet.
    ordered = [entries_by_id[slot["slot_id"]] for slot in cohort["slots"]]
    packet = {
        "schema": SCHEMA, "kind": KIND,
        "cohort_id": cohort["cohort_id"],
        "cohort_sha256": binding["cohort_sha256"],
        "claims_sha256": binding["claims_sha256"],
        "macro_binding_receipt_sha256": binding["macro_binding_receipt_sha256"],
        "prepared_at_utc_claim": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "precommit_deadline_utc": cohort["daily_window"]["precommit_deadline_utc"],
        "declared_slots": 56,
        "directional_claims": binding["directional_claims"],
        "neutral_abstentions": binding["neutral_abstentions"],
        "await_abstentions": binding["await_abstentions"],
        "macro_bytes_bound_slots": binding["macro_bytes_bound_slots"],
        "entries": ordered,
        "independent_witness_url": None,
        "independent_server_timestamp": None,
        "prediction_accuracy_claim": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
    }
    raw = (json.dumps(packet, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True) + "\n").encode("ascii")
    if len(raw) > MAX_PACKET_BYTES:
        out["reason"] = "CANONICAL_PACKET_TOO_LARGE"
        return out
    out.update({
        "state": "LAB_CANONICAL_56_SLOT_PACKET_READY_NOT_EXTERNALLY_WITNESSED",
        "reason": "PACKET_MUST_BE_PUBLISHED_AND_WITNESSED_BEFORE_DEADLINE",
        "packet_bytes": raw, "packet_sha256": sha256(raw).hexdigest(),
        "packet_size_bytes": len(raw),
        "cohort_sha256": binding["cohort_sha256"],
        "claims_sha256": binding["claims_sha256"],
        "submitted_slots": 56, "unfilled_slots": 0,
        "directional_claims": binding["directional_claims"],
        "neutral_abstentions": binding["neutral_abstentions"],
        "await_abstentions": binding["await_abstentions"],
        "macro_bytes_bound_slots": binding["macro_bytes_bound_slots"],
        "candidate_prepared_before_deadline_claim": True,
    })
    return out


def inspect_g8_precommit_packet_lab(
    *, packet_raw: Any, cohort_raw: Any, claims_raw: Any,
    macro_bytes_by_slot: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Reconstruct the exact packet from originals, including after deadline.

    A late comparison can check tampering but CANNOT prove the packet existed
    before the deadline. Always keep independent witness status False.
    """
    out = _deny("INVALID_PACKET_OR_INSPECTION_CLOCK")
    now = _clock(inspected_at_utc)
    if now is None or not isinstance(packet_raw, bytes) or not 1000 <= len(packet_raw) <= MAX_PACKET_BYTES:
        return out
    try:
        parsed = json.loads(packet_raw.decode("utf-8", "strict"))
        if not isinstance(parsed, dict) or parsed.get("schema") != SCHEMA:
            return out
        created = datetime.strptime(parsed["prepared_at_utc_claim"],
                                    "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, RecursionError):
        return out
    if created > now:
        out["reason"] = "PREPARATION_CLAIM_IN_FUTURE"
        return out
    candidate = prepare_g8_precommit_packet_lab(
        cohort_raw=cohort_raw, claims_raw=claims_raw,
        macro_bytes_by_slot=macro_bytes_by_slot, prepared_at_utc=created)
    if candidate["packet_bytes"] is None or packet_raw != candidate["packet_bytes"]:
        out["reason"] = "PACKET_BYTES_OR_UNDERLYING_EVIDENCE_CHANGED"
        return out
    out.update(candidate)
    out["packet_bytes"] = None  # Avoid copying the potentially sensitive packet.
    out["state"] = "LAB_PACKET_REPLAY_IDENTICAL_BUT_HISTORICAL_WITNESS_MISSING"
    out["reason"] = "REPLAY_CAN_VERIFY_CONTENT_NOT_SERVER_TIME_OR_AUTHENTICITY"
    out["candidate_prepared_before_deadline_claim"] = True
    return out


__all__ = ["SCHEMA", "KIND", "prepare_g8_precommit_packet_lab",
           "inspect_g8_precommit_packet_lab"]
