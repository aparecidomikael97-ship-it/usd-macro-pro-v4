"""AION V2 external witness HEAD challenge -- mathematical reference, NO authority.

This module NEVER runs a witness, network request, collector signer, model
request, TPM operation or installation. It compares a *caller-supplied*
external head and public pin against a detached Ed25519-signed commitment to
all local V2 hold records. CI supplies an independently retained fake head.
A compromised caller can supply an old head or forged trust pin, so success
cannot prove true external freshness, enrollment, monotonicity or antirollback.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_chat_reference_v2_nonce_cost_hold import (
    ReferenceV2NonceCostLedger, SCHEMA as LEDGER_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_V2_EXTERNAL_WITNESS_CHALLENGE_REFERENCE_V1"
HEAD_SCHEMA = "ATLASQUANT_AION_V2_REFERENCE_WITNESS_SIGNED_HEAD_V1"
PURPOSE = "WITNESS_V2_SQLITE_HOLD_STATE_MATH_ONLY_NO_DISPATCH"
ROLE = "COLLECTOR_ED25519"
DOMAIN = b"ATLASQUANT_AION_V2_REFERENCE_WITNESS_HEAD_V1\x00"
SNAPSHOT_DOMAIN = b"ATLASQUANT_AION_V2_REFERENCE_LEDGER_SNAPSHOT_V1\x00"
RECEIPT_DOMAIN = b"ATLASQUANT_AION_V2_REFERENCE_WITNESS_RECEIPT_V1\x00"
CANDIDATE = "EXTERNAL_HEAD_MATCH_MATH_ONLY_UNTRUSTED"
ZERO = "0" * 64
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_KEYS = frozenset({
    "schema", "purpose", "role", "collector_key_id",
    "owner_id", "tenant_id", "workspace_id",
    "period_id", "policy_generation", "owner_pin_sha256",
    "ledger_hold_count", "ledger_held_micro_usd",
    "ledger_limit_micro_usd", "ledger_snapshot_sha256",
    "witness_sequence", "previous_receipt_sha256",
})
_ENVELOPE = frozenset({"payload", "signature_hex"})
_PIN = frozenset({"key_id", "public_key_hex"})
_HEAD = frozenset({"sequence", "receipt_sha256"})
NO_AUTHORITY = {
    "trusted_collector_enrollment_verified": False,
    "collector_custody_verified": False,
    "trusted_human_owner_consent": False,
    "independent_witness_service_verified": False,
    "independent_witness_freshness_verified": False,
    "rollback_protection_production_verified": False,
    "witness_append_performed": False,
    "witness_sequence_reservation_verified": False,
    "cross_database_atomicity_verified": False,
    "production_budget_reserved": False,
    "model_invocation_authorized": False,
    "provider_called": False,
    "network_called": False,
    "billing_authorized": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _sha(value: Any) -> bool:
    return type(value) is str and bool(_HEX64.fullmatch(value))


def _strict_int(value: Any, lo: int, hi: int) -> bool:
    return type(value) is int and lo <= value <= hi


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _result(state: str, reason: str, *, digest: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "local_and_supplied_head_match": state == CANDIDATE,
        "signed_collector_math_valid": state == CANDIDATE,
        "checked_receipt_sha256": digest if state == CANDIDATE else "",
        "reference_only": True,
        **NO_AUTHORITY,
    }


def canonical_witness_head(payload: Mapping[str, Any]) -> bytes:
    """Closed, canonical and domain-separated. Not a signature."""
    if type(payload) is not dict or set(payload) != _KEYS:
        raise ValueError("exact signed witness V1 payload required")
    return DOMAIN + _canonical(payload)


def signed_receipt_sha256(envelope: Mapping[str, Any]) -> str:
    """Fingerprint of a candidate receipt; NOT a validity decision."""
    if (type(envelope) is not dict or set(envelope) != _ENVELOPE
        or type(envelope["payload"]) is not dict
        or set(envelope["payload"]) != _KEYS
        or type(envelope["signature_hex"]) is not str
        or not _HEX128.fullmatch(envelope["signature_hex"])):
        raise ValueError("exact witness envelope required")
    data = canonical_witness_head(envelope["payload"])
    return sha256(RECEIPT_DOMAIN + data +
                  bytes.fromhex(envelope["signature_hex"])).hexdigest()


def local_v2_snapshot_commitment(
    ledger: ReferenceV2NonceCostLedger,
) -> dict[str, Any]:
    """Stable digest of full V2 local state; never an external witness.

    Transaction locks local DB for internally consistent reads only.
    Return hashes/counters, no original message or authorization.
    """
    if type(ledger) is not ReferenceV2NonceCostLedger:
        raise ValueError("only exact V2 reference ledger accepted")
    db = ledger.db
    if db.in_transaction:
        raise ValueError("concurrent/unfinished transaction blocked")
    try:
        db.execute("BEGIN IMMEDIATE")
        config = ledger._verify_internal_consistency()
        cols = (
            "nonce_hex", "scope_owner", "scope_tenant", "scope_workspace",
            "conversation_id", "message_id", "signed_intent_sha256",
            "full_request_sha256", "amount_micro_usd",
            "policy_generation", "period_id",
        )
        records = [
            {k: row[k] for k in cols}
            for row in db.execute(
                "SELECT * FROM reference_v2_holds ORDER BY nonce_hex"
            ).fetchall()
        ]
        conf = {
            k: config[k] for k in (
                "contract_schema", "owner_id", "tenant_id", "workspace_id",
                "period_id", "policy_generation", "pin_sha256",
                "limit_micro_usd", "held_total_micro_usd", "hold_count",
            )
        }
        if conf["contract_schema"] != LEDGER_SCHEMA:
            raise ValueError("not V2 ledger schema")
        snapshot = {"schema": SCHEMA, "config": conf, "records": records}
        digest = sha256(SNAPSHOT_DOMAIN + _canonical(snapshot)).hexdigest()
        return {
            "schema": SCHEMA,
            "snapshot_sha256": digest,
            "hold_count": conf["hold_count"],
            "held_micro_usd": conf["held_total_micro_usd"],
            "limit_micro_usd": conf["limit_micro_usd"],
            "owner_id": conf["owner_id"],
            "tenant_id": conf["tenant_id"],
            "workspace_id": conf["workspace_id"],
            "owner_pin_sha256": conf["pin_sha256"],
            "policy_generation": conf["policy_generation"],
            "period_id": conf["period_id"],
            "reference_only": True,
            **NO_AUTHORITY,
        }
    finally:
        if db.in_transaction:
            db.rollback()


def make_unsigned_witness_head_candidate(
    ledger: ReferenceV2NonceCostLedger, *,
    collector_key_id: Any, witness_sequence: Any,
    previous_receipt_sha256: Any,
) -> dict[str, Any]:
    """Candidate to submit to a *future* independent witness, no signing."""
    if (type(collector_key_id) is not str
        or not _TOKEN.fullmatch(collector_key_id)
        or not _strict_int(witness_sequence, 1, 2**63 - 1)
        or not _sha(previous_receipt_sha256)):
        raise ValueError("candidate sequence, pin ID or previous head invalid")
    state = local_v2_snapshot_commitment(ledger)
    return {
        "schema": HEAD_SCHEMA, "purpose": PURPOSE, "role": ROLE,
        "collector_key_id": collector_key_id,
        "owner_id": state["owner_id"],
        "tenant_id": state["tenant_id"],
        "workspace_id": state["workspace_id"],
        "period_id": state["period_id"],
        "policy_generation": state["policy_generation"],
        "owner_pin_sha256": state["owner_pin_sha256"],
        "ledger_hold_count": state["hold_count"],
        "ledger_held_micro_usd": state["held_micro_usd"],
        "ledger_limit_micro_usd": state["limit_micro_usd"],
        "ledger_snapshot_sha256": state["snapshot_sha256"],
        "witness_sequence": witness_sequence,
        "previous_receipt_sha256": previous_receipt_sha256,
    }


def review_witnessed_v2_reference_state(
    ledger: Any, *, envelope: Any,
    collector_public_pin: Any, independent_expected_head: Any,
) -> dict[str, Any]:
    """Compare one signed receipt to an independently fetched authoritative head.

    'independent_expected_head' is caller-provided: NO actual external fetch,
    enrollment, signature of remote read, trusted clock or freshness proof.
    Supplying a stale expected head can make matching stale local state pass.
    """
    if (type(collector_public_pin) is not dict
        or set(collector_public_pin) != _PIN
        or type(collector_public_pin["key_id"]) is not str
        or not _TOKEN.fullmatch(collector_public_pin["key_id"])
        or not _sha(collector_public_pin["public_key_hex"])):
        return _result("BLOCKED", "TRUSTED_COLLECTOR_PIN_INPUT_REQUIRED")
    if (type(independent_expected_head) is not dict
        or set(independent_expected_head) != _HEAD
        or not _strict_int(independent_expected_head["sequence"], 1, 2**63 - 1)
        or not _sha(independent_expected_head["receipt_sha256"])):
        return _result("BLOCKED", "FRESH_INDEPENDENT_HEAD_REQUIRED")
    if type(envelope) is not dict or set(envelope) != _ENVELOPE:
        return _result("BLOCKED", "WITNESS_ENVELOPE_INVALID")
    payload = envelope["payload"]
    if type(payload) is not dict or set(payload) != _KEYS:
        return _result("BLOCKED", "WITNESS_PAYLOAD_SCHEMA_INVALID")
    if not (type(envelope["signature_hex"]) is str and
            _HEX128.fullmatch(envelope["signature_hex"])):
        return _result("BLOCKED", "WITNESS_SIGNATURE_FORMAT_INVALID")
    if (payload["schema"] != HEAD_SCHEMA
        or payload["purpose"] != PURPOSE
        or payload["role"] != ROLE
        or payload["collector_key_id"] != collector_public_pin["key_id"]
        or not all(type(payload[k]) is str for k in (
            "owner_id", "tenant_id", "workspace_id", "period_id",
        ))
        or not all(_sha(payload[k]) for k in (
            "owner_pin_sha256", "ledger_snapshot_sha256",
            "previous_receipt_sha256",
        ))
        or not _strict_int(payload["witness_sequence"], 1, 2**63 - 1)
        or not _strict_int(payload["policy_generation"], 1, 2**31-1)
        or not _strict_int(payload["ledger_hold_count"], 0, 2**63 - 1)
        or not _strict_int(payload["ledger_held_micro_usd"], 0, 2_000_000_000)
        or not _strict_int(payload["ledger_limit_micro_usd"], 1, 2_000_000_000)):
        return _result("BLOCKED", "WITNESS_FIELDS_OR_PURPOSE_INVALID")
    try:
        data = canonical_witness_head(payload)
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(collector_public_pin["public_key_hex"])
        ).verify(bytes.fromhex(envelope["signature_hex"]), data)
        receipt = signed_receipt_sha256(envelope)
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _result("BLOCKED", "COLLECTOR_SIGNATURE_MATH_INVALID")

    # The supplied independently observed head is an exact-equality gate:
    # any older/newer sequence or forked receipt is rejected, not reconciled.
    if payload["witness_sequence"] != independent_expected_head["sequence"]:
        return _result("BLOCKED", "EXTERNAL_WITNESS_SEQUENCE_STALE_OR_FUTURE")
    if receipt != independent_expected_head["receipt_sha256"]:
        return _result("BLOCKED", "EXTERNAL_WITNESS_RECEIPT_FORK_OR_ROLLBACK")
    try:
        observed = local_v2_snapshot_commitment(ledger)
    except (ValueError, TypeError, sqlite3.Error, OverflowError):
        return _result("BLOCKED", "LOCAL_V2_LEDGER_UNAVAILABLE_OR_CORRUPT")
    if (payload["owner_id"] != observed["owner_id"]
        or payload["tenant_id"] != observed["tenant_id"]
        or payload["workspace_id"] != observed["workspace_id"]
        or payload["period_id"] != observed["period_id"]
        or payload["policy_generation"] != observed["policy_generation"]
        or payload["owner_pin_sha256"] != observed["owner_pin_sha256"]
        or payload["ledger_hold_count"] != observed["hold_count"]
        or payload["ledger_held_micro_usd"] != observed["held_micro_usd"]
        or payload["ledger_limit_micro_usd"] != observed["limit_micro_usd"]
        or payload["ledger_snapshot_sha256"] != observed["snapshot_sha256"]):
        return _result("BLOCKED", "LOCAL_SQLITE_SNAPSHOT_NOT_AT_EXTERNAL_HEAD")
    return _result(
        CANDIDATE,
        "SIGNED_HEAD_MATCHES_CALLER_PROVIDED_HEAD_MATH_ONLY_NO_AUTHORITY",
        digest=receipt,
    )


__all__ = [
    "SCHEMA", "HEAD_SCHEMA", "PURPOSE", "ROLE", "DOMAIN", "SNAPSHOT_DOMAIN",
    "CANDIDATE", "ZERO", "NO_AUTHORITY", "canonical_witness_head",
    "signed_receipt_sha256", "local_v2_snapshot_commitment",
    "make_unsigned_witness_head_candidate", "review_witnessed_v2_reference_state",
]
