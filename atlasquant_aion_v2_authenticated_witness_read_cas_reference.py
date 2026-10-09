"""AION V2 signed witness READ + monotonic CAS preconditions, reference only.

Pure cryptographic checks, not a witness implementation. This module never
fetches a remote head, performs a CAS, enrolls keys, mutates a ledger, calls
a model, transfers funds or authorizes an installer. All keys/heads/challenges
are host-supplied: even valid mathematics is NOT independent trusted freshness.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_external_witness_rollback_reference import (
    HEAD_SCHEMA, PURPOSE as COLLECTOR_PURPOSE,
    ROLE as COLLECTOR_ROLE, canonical_witness_head, signed_receipt_sha256,
)

SCHEMA = "ATLASQUANT_AION_V2_WITNESS_SIGNED_READ_CAS_REFERENCE_V1"
READ_SCHEMA = "ATLASQUANT_AION_V2_WITNESS_FRESH_READ_V1"
READ_PURPOSE = "ECHO_ONE_FRESH_HEAD_CHALLENGE_REVIEW_ONLY"
READ_ROLE = "INDEPENDENT_WITNESS_ED25519"
READ_DOMAIN = b"ATLASQUANT_AION_V2_WITNESS_FRESH_READ_V1\x00"
READ_CANDIDATE = "READ_SIGNATURE_AND_CHALLENGE_MATH_ONLY_UNTRUSTED"
CAS_CANDIDATE = "CAS_PRECONDITIONS_MATH_ONLY_UNTRUSTED"
ZERO = "0" * 64
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_READ_KEYS = frozenset({
    "schema", "purpose", "role", "witness_key_id", "witness_service_id",
    "owner_id", "tenant_id", "workspace_id", "period_id",
    "policy_generation", "owner_pin_sha256", "challenge_nonce_hex",
    "minimum_witness_epoch", "witness_epoch", "head_sequence", "head_receipt_sha256",
    "head_snapshot_sha256", "head_hold_count", "head_held_micro_usd",
    "head_limit_micro_usd",
})
_QUERY_KEYS = frozenset({
    "witness_service_id", "owner_id", "tenant_id", "workspace_id",
    "period_id", "policy_generation", "owner_pin_sha256",
    "challenge_nonce_hex", "minimum_witness_epoch",
})
_HEAD_KEYS = frozenset({
    "witness_epoch", "sequence", "receipt_sha256", "snapshot_sha256",
    "hold_count", "held_micro_usd", "limit_micro_usd",
})
_ENVELOPE_KEYS = frozenset({"payload", "signature_hex"})
_PIN_KEYS = frozenset({"key_id", "public_key_hex"})
_NO_AUTHORITY = {
    "witness_public_key_enrolled": False,
    "witness_service_authenticated": False,
    "witness_freshness_independently_verified": False,
    "monotonicity_production_verified": False,
    "atomic_compare_and_swap_performed": False,
    "witness_append_durable": False,
    "owner_identity_verified": False,
    "owner_consent_verified": False,
    "collector_public_key_enrolled": False,
    "provider_request_approved": False,
    "model_invocation_authorized": False,
    "paid_dispatch_performed": False,
    "network_called": False,
    "billing_authorized": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _valid_hash(v: Any) -> bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _int(v: Any, lower: int, upper: int) -> bool:
    return type(v) is int and lower <= v <= upper


def _token(v: Any) -> bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_fresh_read(payload: Mapping[str, Any]) -> bytes:
    if type(payload) is not dict or set(payload) != _READ_KEYS:
        raise ValueError("exact fresh witness READ schema required")
    return READ_DOMAIN + _canonical(payload)


def _out(state: str, reason: str, *, head: Any = None,
         proposed: Any = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "mathematical_candidate_only": state in (READ_CANDIDATE, CAS_CANDIDATE),
        "read_head": head if state == READ_CANDIDATE else None,
        "proposed_head": proposed if state == CAS_CANDIDATE else None,
        "reference_only": True,
        **_NO_AUTHORITY,
    }


def _pin(v: Any) -> bool:
    return (type(v) is dict and set(v) == _PIN_KEYS
            and _token(v["key_id"]) and _valid_hash(v["public_key_hex"]))


def _head(v: Any) -> bool:
    return (type(v) is dict and set(v) == _HEAD_KEYS
            and _int(v["witness_epoch"], 1, 2**31-1)
            and _int(v["sequence"], 1, 2**63-1)
            and _valid_hash(v["receipt_sha256"])
            and _valid_hash(v["snapshot_sha256"])
            and _int(v["hold_count"], 0, 2**63-1)
            and _int(v["held_micro_usd"], 0, 2_000_000_000)
            and _int(v["limit_micro_usd"], 1, 2_000_000_000)
            and v["held_micro_usd"] <= v["limit_micro_usd"])


def _query(v: Any) -> bool:
    return (type(v) is dict and set(v) == _QUERY_KEYS
            and all(_token(v[k]) for k in (
                "witness_service_id", "owner_id", "tenant_id", "workspace_id"
            ))
            and type(v["period_id"]) is str
            and bool(re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",
                                  v["period_id"]))
            and _int(v["policy_generation"], 1, 2**31-1)
            and _int(v["minimum_witness_epoch"], 1, 2**31-1)
            and _valid_hash(v["owner_pin_sha256"])
            and _valid_hash(v["challenge_nonce_hex"])
            and v["challenge_nonce_hex"] != ZERO)


def _read_check(
    response: Any, *, trusted_witness_pin: Any, expected_query: Any,
) -> tuple[str, dict[str, Any] | None]:
    if not _pin(trusted_witness_pin):
        return "WITNESS_PUBLIC_PIN_REQUIRED", None
    if not _query(expected_query):
        return "FRESH_CHALLENGE_AND_SCOPE_REQUIRED", None
    if type(response) is not dict or set(response) != _ENVELOPE_KEYS:
        return "READ_ENVELOPE_SCHEMA_INVALID", None
    p = response["payload"]
    if (type(p) is not dict or set(p) != _READ_KEYS
        or not (type(response["signature_hex"]) is str
                and _HEX128.fullmatch(response["signature_hex"]))):
        return "READ_PAYLOAD_OR_SIGNATURE_INVALID", None
    if (p["schema"] != READ_SCHEMA
        or p["purpose"] != READ_PURPOSE
        or p["role"] != READ_ROLE
        or p["witness_key_id"] != trusted_witness_pin["key_id"]):
        return "READ_DOMAIN_ROLE_OR_KEY_MISMATCH", None
    for k in (
        "witness_service_id", "owner_id", "tenant_id", "workspace_id",
        "period_id", "policy_generation", "owner_pin_sha256",
        "challenge_nonce_hex", "minimum_witness_epoch",
    ):
        if type(p[k]) is not type(expected_query[k]) or p[k] != expected_query[k]:
            return "READ_CHALLENGE_OR_SCOPE_MISMATCH", None
    head = {
        "witness_epoch": p["witness_epoch"],
        "sequence": p["head_sequence"],
        "receipt_sha256": p["head_receipt_sha256"],
        "snapshot_sha256": p["head_snapshot_sha256"],
        "hold_count": p["head_hold_count"],
        "held_micro_usd": p["head_held_micro_usd"],
        "limit_micro_usd": p["head_limit_micro_usd"],
    }
    if (not _head(head)
        or head["witness_epoch"] < expected_query["minimum_witness_epoch"]):
        return "READ_EPOCH_OR_HEAD_INVALID", None
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(trusted_witness_pin["public_key_hex"])
        ).verify(
            bytes.fromhex(response["signature_hex"]), canonical_fresh_read(p)
        )
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return "WITNESS_READ_SIGNATURE_INVALID", None
    return "", head


def review_signed_fresh_witness_read(
    response: Any, *, trusted_witness_pin: Any, expected_query: Any,
) -> dict[str, Any]:
    """No network or freshness oracle. Host must supply an UNREUSED challenge."""
    reason, head = _read_check(
        response, trusted_witness_pin=trusted_witness_pin,
        expected_query=expected_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    return _out(READ_CANDIDATE, "VALID_MATH_NOT_ENROLLED_WITNESS_OR_FRESH_NETWORK",
                head=head)


def review_reference_witness_cas_preconditions(
    *,
    read_response: Any, trusted_witness_pin: Any, expected_query: Any,
    current_service_head: Any, signed_next_collector_receipt: Any,
    collector_public_pin: Any,
) -> dict[str, Any]:
    """Check a candidate next head, but never write a CAS or grant authority.

    'current_service_head' comes from the caller in this pure reference.
    An actual witness service must fetch it ATOMICALLY with the compare/swap,
    authenticated inside its trust boundary, never from the client.
    """
    reason, old = _read_check(
        read_response, trusted_witness_pin=trusted_witness_pin,
        expected_query=expected_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    if not _head(current_service_head) or current_service_head != old:
        return _out("BLOCKED", "SERVICE_HEAD_CHANGED_OR_STALE_READ")
    if not _pin(collector_public_pin):
        return _out("BLOCKED", "COLLECTOR_PIN_REQUIRED")
    if (type(signed_next_collector_receipt) is not dict
        or set(signed_next_collector_receipt) != _ENVELOPE_KEYS
        or type(signed_next_collector_receipt["payload"]) is not dict
        or not (type(signed_next_collector_receipt["signature_hex"]) is str
                and _HEX128.fullmatch(
                    signed_next_collector_receipt["signature_hex"]))):
        return _out("BLOCKED", "NEXT_RECEIPT_ENVELOPE_INVALID")
    new = signed_next_collector_receipt["payload"]
    try:
        data = canonical_witness_head(new)
    except (ValueError, TypeError, OverflowError):
        return _out("BLOCKED", "NEXT_RECEIPT_SCHEMA_INVALID")
    if (new["schema"] != HEAD_SCHEMA
        or new["purpose"] != COLLECTOR_PURPOSE
        or new["role"] != COLLECTOR_ROLE
        or new["collector_key_id"] != collector_public_pin["key_id"]
        or not all(_token(new[k]) for k in (
            "owner_id", "tenant_id", "workspace_id"
        ))
        or type(new["period_id"]) is not str
        or not _valid_hash(new["owner_pin_sha256"])
        or not _valid_hash(new["ledger_snapshot_sha256"])
        or not _valid_hash(new["previous_receipt_sha256"])
        or not _int(new["witness_sequence"], 1, 2**63-1)
        or not _int(new["policy_generation"], 1, 2**31-1)
        or not _int(new["ledger_hold_count"], 0, 2**63-1)
        or not _int(new["ledger_held_micro_usd"], 0, 2_000_000_000)
        or not _int(new["ledger_limit_micro_usd"], 1, 2_000_000_000)):
        return _out("BLOCKED", "NEXT_RECEIPT_PURPOSE_OR_FIELDS_INVALID")
    if any(new[k] != expected_query[k] for k in (
        "owner_id", "tenant_id", "workspace_id", "period_id",
        "policy_generation", "owner_pin_sha256"
    )):
        return _out("BLOCKED", "NEXT_RECEIPT_SCOPE_OR_POLICY_MISMATCH")
    if (new["witness_sequence"] != old["sequence"] + 1
        or new["previous_receipt_sha256"] != old["receipt_sha256"]
        or new["ledger_snapshot_sha256"] == old["snapshot_sha256"]
        or new["ledger_hold_count"] != old["hold_count"] + 1
        or new["ledger_limit_micro_usd"] != old["limit_micro_usd"]
        or not old["held_micro_usd"] < new["ledger_held_micro_usd"]
               <= old["limit_micro_usd"]
        or new["ledger_held_micro_usd"] - old["held_micro_usd"] > 20_000_000):
        return _out("BLOCKED", "NON_MONOTONIC_OR_NON_APPEND_WITNESS_PROPOSAL")
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(collector_public_pin["public_key_hex"])
        ).verify(bytes.fromhex(signed_next_collector_receipt["signature_hex"]),data)
        new_receipt_hash = signed_receipt_sha256(signed_next_collector_receipt)
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return _out("BLOCKED", "COLLECTOR_RECEIPT_SIGNATURE_MATH_INVALID")
    proposed = {
        "witness_epoch": old["witness_epoch"],
        "sequence": new["witness_sequence"],
        "receipt_sha256": new_receipt_hash,
        "snapshot_sha256": new["ledger_snapshot_sha256"],
        "hold_count": new["ledger_hold_count"],
        "held_micro_usd": new["ledger_held_micro_usd"],
        "limit_micro_usd": new["ledger_limit_micro_usd"],
    }
    return _out(
        CAS_CANDIDATE,
        "CAS_PRECONDITION_MATH_ONLY_NOT_DURABLE_NOT_DISPATCH_AUTHORITY",
        proposed=proposed,
    )


__all__ = [
    "SCHEMA", "READ_SCHEMA", "READ_PURPOSE", "READ_ROLE", "READ_DOMAIN",
    "READ_CANDIDATE", "CAS_CANDIDATE", "ZERO", "canonical_fresh_read",
    "review_signed_fresh_witness_read",
    "review_reference_witness_cas_preconditions",
]
