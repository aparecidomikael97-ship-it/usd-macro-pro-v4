"""AION V2 second-trust-domain high-watermark protocol (math-only reference).

A signed, challenge-bound independent anchor READ is compared with the
existing signed primary witness READ from #1128. An append preflight demands
exactly one monotonic primary witness step from the previously anchored head.

There are NO external reads, writes, CAS, keys, enrollments, cloud resources,
owner presence checks, paid model calls, background tasks or real authority.
Tests inject ALL trust roots and source state. Even a mathematically matching
two-domain transcript is NOT proof that real domains are independent.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_authenticated_witness_read_cas_reference import (
    READ_CANDIDATE, review_signed_fresh_witness_read,
)

SCHEMA = "ATLASQUANT_AION_V2_SECOND_DOMAIN_ANCHOR_REFERENCE_V1"
ANCHOR_READ_SCHEMA = "ATLASQUANT_AION_V2_ANCHOR_FRESH_READ_V1"
ANCHOR_READ_PURPOSE = "ATTEST_ONE_INDEPENDENT_HIGH_WATERMARK_READ_ONLY"
ANCHOR_ROLE = "SECOND_DOMAIN_ANCHOR_ED25519"
ANCHOR_DOMAIN = b"ATLASQUANT_AION_V2_SECOND_DOMAIN_ANCHOR_READ_V1\x00"
HEAD_MATCH = "TWO_SIGNED_HEADS_EQUAL_MATH_ONLY_UNTRUSTED"
ADVANCE_CANDIDATE = "SECOND_ANCHOR_ADVANCE_PRECONDITIONS_MATH_ONLY_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX128 = re.compile(r"[0-9a-f]{128}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_ENVELOPE_KEYS = frozenset({"payload", "signature_hex"})
_PIN_KEYS = frozenset({"key_id", "public_key_hex"})
_ANCHOR_KEYS = frozenset({
    "schema", "purpose", "role", "anchor_key_id", "anchor_service_id",
    "witness_service_id", "owner_id", "tenant_id", "workspace_id",
    "period_id", "policy_generation", "owner_pin_sha256",
    "witness_pin_sha256", "challenge_nonce_hex", "minimum_anchor_epoch",
    "anchor_epoch", "head_sequence", "head_receipt_sha256",
    "head_snapshot_sha256", "head_hold_count", "head_held_micro_usd",
    "head_limit_micro_usd",
})
_QUERY_KEYS = frozenset({
    "anchor_service_id", "witness_service_id", "owner_id", "tenant_id",
    "workspace_id", "period_id", "policy_generation", "owner_pin_sha256",
    "witness_pin_sha256", "challenge_nonce_hex", "minimum_anchor_epoch",
})
_HEAD_KEYS = frozenset({
    "witness_epoch", "sequence", "receipt_sha256", "snapshot_sha256",
    "hold_count", "held_micro_usd", "limit_micro_usd",
})
_FALSE_GATES = {
    "reference_only": True,
    "actual_two_trust_domains_verified": False,
    "anchor_public_key_enrolled": False,
    "witness_public_key_enrolled": False,
    "owner_public_key_enrolled": False,
    "owner_presence_verified": False,
    "freshness_independently_verified": False,
    "anchor_cas_committed": False,
    "anchor_high_watermark_durable": False,
    "rollback_protection_production_verified": False,
    "witness_rollback_resistant": False,
    "cloud_provisioned": False,
    "cross_domain_atomicity_verified": False,
    "real_budget_reserved": False,
    "owner_consent_verified": False,
    "model_invocation_authorized": False,
    "paid_provider_called": False,
    "billing_authorized": False,
    "network_called": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _hash(value: Any) -> bool:
    return type(value) is str and bool(_HEX64.fullmatch(value))


def _int(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _token(value: Any) -> bool:
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def _head(value: Any) -> bool:
    return (type(value) is dict and set(value) == _HEAD_KEYS
        and _int(value["witness_epoch"], 1, 2**31-1)
        and _int(value["sequence"], 1, 2**63-1)
        and _hash(value["receipt_sha256"])
        and _hash(value["snapshot_sha256"])
        and _int(value["hold_count"], 0, 2**63-1)
        and _int(value["held_micro_usd"], 0, 2_000_000_000)
        and _int(value["limit_micro_usd"], 1, 2_000_000_000)
        and value["held_micro_usd"] <= value["limit_micro_usd"])


def _out(state: str, reason: str, *, proposed: Any = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "mathematics_match": state in (HEAD_MATCH, ADVANCE_CANDIDATE),
        "proposed_anchor_head": proposed if state == ADVANCE_CANDIDATE else None,
        **_FALSE_GATES,
    }


def canonical_anchor_read(payload: Mapping[str, Any]) -> bytes:
    if type(payload) is not dict or set(payload) != _ANCHOR_KEYS:
        raise ValueError("closed independent-anchor signed READ required")
    return ANCHOR_DOMAIN + json.dumps(
        payload, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _anchor_read(
    envelope: Any, *, public_pin: Any, query: Any,
) -> tuple[str, dict[str, Any] | None]:
    if (type(public_pin) is not dict or set(public_pin) != _PIN_KEYS
        or not _token(public_pin["key_id"])
        or not _hash(public_pin["public_key_hex"])):
        return "ANCHOR_PUBLIC_PIN_INVALID", None
    if (type(query) is not dict or set(query) != _QUERY_KEYS
        or any(not _token(query[k]) for k in (
            "anchor_service_id", "witness_service_id", "owner_id",
            "tenant_id", "workspace_id"
        ))
        or not _int(query["policy_generation"], 1, 2**31-1)
        or not _int(query["minimum_anchor_epoch"], 1, 2**31-1)
        or not _hash(query["owner_pin_sha256"])
        or not _hash(query["witness_pin_sha256"])
        or not _hash(query["challenge_nonce_hex"])
        or query["challenge_nonce_hex"] == "0"*64
        or type(query["period_id"]) is not str
        or not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", query["period_id"])):
        return "ANCHOR_SCOPE_OR_CHALLENGE_INVALID", None
    if type(envelope) is not dict or set(envelope) != _ENVELOPE_KEYS:
        return "ANCHOR_ENVELOPE_SCHEMA_INVALID", None
    p=envelope["payload"]
    if (type(p) is not dict or set(p) != _ANCHOR_KEYS
        or type(envelope["signature_hex"]) is not str
        or not _HEX128.fullmatch(envelope["signature_hex"])):
        return "ANCHOR_PAYLOAD_OR_SIGNATURE_INVALID", None
    if (p["schema"] != ANCHOR_READ_SCHEMA
        or p["purpose"] != ANCHOR_READ_PURPOSE
        or p["role"] != ANCHOR_ROLE
        or p["anchor_key_id"] != public_pin["key_id"]):
        return "ANCHOR_ROLE_PURPOSE_OR_KEY_INVALID", None
    if any(type(p[k]) is not type(query[k]) or p[k] != query[k]
           for k in _QUERY_KEYS):
        return "ANCHOR_SIGNED_SCOPE_OR_CHALLENGE_MISMATCH", None
    head={
        "witness_epoch":p["anchor_epoch"],
        "sequence":p["head_sequence"],
        "receipt_sha256":p["head_receipt_sha256"],
        "snapshot_sha256":p["head_snapshot_sha256"],
        "hold_count":p["head_hold_count"],
        "held_micro_usd":p["head_held_micro_usd"],
        "limit_micro_usd":p["head_limit_micro_usd"],
    }
    if not _head(head) or head["witness_epoch"] < query["minimum_anchor_epoch"]:
        return "ANCHOR_EPOCH_OR_HEAD_INVALID", None
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_pin["public_key_hex"])
        ).verify(bytes.fromhex(envelope["signature_hex"]),
                 canonical_anchor_read(p))
    except (InvalidSignature, ValueError, TypeError, OverflowError):
        return "ANCHOR_SIGNATURE_MATH_INVALID", None
    return "", head


def _primary_read(
    response: Any, *, pin: Any, query: Any,
) -> tuple[str, dict[str, Any] | None]:
    result=review_signed_fresh_witness_read(
        response, trusted_witness_pin=pin, expected_query=query,
    )
    if result["state"] != READ_CANDIDATE:
        return "PRIMARY_SIGNED_READ_NOT_VERIFIED", None
    return "", result["read_head"]


def _scope_consistent(primary_query: Any, anchor_query: Any, pin: Any) -> bool:
    if (type(primary_query) is not dict or type(anchor_query) is not dict
        or type(pin) is not dict or set(pin) != _PIN_KEYS):
        return False
    try:
        # Do not trust the client to bind two unrelated tenant/workspace heads.
        if any(primary_query[k] != anchor_query[k] for k in (
            "witness_service_id", "owner_id", "tenant_id", "workspace_id",
            "period_id", "policy_generation", "owner_pin_sha256",
        )):
            return False
        # Pin digest over exact canonical existing witness public key inputs.
        expected=__import__("hashlib").sha256(json.dumps(
            pin, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return anchor_query["witness_pin_sha256"] == expected
    except (KeyError, TypeError, ValueError):
        return False


def review_two_signed_domains(
    *, primary_signed_read: Any, primary_public_pin: Any,
    primary_query: Any, anchor_signed_read: Any, anchor_public_pin: Any,
    anchor_query: Any,
) -> dict[str, Any]:
    """Never trust equality as proof the keys, services or epoch are enrolled."""
    if not _scope_consistent(primary_query, anchor_query, primary_public_pin):
        return _out("BLOCKED", "TWO_DOMAIN_SCOPE_OR_WITNESS_PIN_MISMATCH")
    reason,primary=_primary_read(
        primary_signed_read,pin=primary_public_pin,query=primary_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    reason,anchored=_anchor_read(
        anchor_signed_read,public_pin=anchor_public_pin,query=anchor_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    if primary["witness_epoch"] != anchored["witness_epoch"]:
        return _out("BLOCKED", "TWO_DOMAIN_EPOCH_MISMATCH")
    if primary["sequence"] < anchored["sequence"]:
        return _out("BLOCKED", "PRIMARY_ROLLBACK_BEHIND_SECOND_ANCHOR")
    if primary["sequence"] > anchored["sequence"]:
        return _out("BLOCKED", "PRIMARY_AHEAD_OF_ANCHOR_RECONCILIATION_REQUIRED")
    if primary != anchored:
        return _out("BLOCKED", "SAME_SEQUENCE_WITNESS_FORK_OR_MUTATION")
    return _out(
        HEAD_MATCH,
        "MATCHING_MATH_ONLY_NO_ENROLLED_INDEPENDENCE_OR_SPENDING_AUTHORITY",
    )


def review_secondary_anchor_advance_preconditions(
    *, old_anchor_signed_read: Any, old_anchor_public_pin: Any,
    old_anchor_query: Any, primary_signed_read: Any,
    primary_public_pin: Any, primary_query: Any,
    current_anchor_head_for_fixture: Any,
) -> dict[str, Any]:
    """Mathematical one-step advance only. No write/network/real CAS.

    A real second service MUST get current head from its own durable store
    inside its atomic compare-and-swap. Caller-supplied state is not authority.
    """
    if not _scope_consistent(primary_query, old_anchor_query,
                             primary_public_pin):
        return _out("BLOCKED", "TWO_DOMAIN_SCOPE_OR_WITNESS_PIN_MISMATCH")
    reason,old=_anchor_read(
        old_anchor_signed_read,public_pin=old_anchor_public_pin,
        query=old_anchor_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    reason,new=_primary_read(
        primary_signed_read,pin=primary_public_pin,query=primary_query,
    )
    if reason:
        return _out("BLOCKED", reason)
    if not _head(current_anchor_head_for_fixture) or old != current_anchor_head_for_fixture:
        return _out("BLOCKED", "SECOND_ANCHOR_CAS_STALE_OR_FORKED")
    if (new["witness_epoch"] != old["witness_epoch"]
        or new["sequence"] != old["sequence"]+1
        or new["hold_count"] != old["hold_count"]+1
        or new["limit_micro_usd"] != old["limit_micro_usd"]
        or new["snapshot_sha256"] == old["snapshot_sha256"]
        or new["receipt_sha256"] == old["receipt_sha256"]
        or not old["held_micro_usd"] < new["held_micro_usd"]
               <= old["limit_micro_usd"]
        or new["held_micro_usd"]-old["held_micro_usd"] > 20_000_000):
        return _out("BLOCKED", "SECOND_ANCHOR_NON_MONOTONIC_PROPOSAL")
    return _out(
        ADVANCE_CANDIDATE,
        "SECOND_ANCHOR_CAS_PRECHECK_ONLY_NO_ATOMIC_COMMIT",
        proposed=new,
    )


__all__=[
    "SCHEMA","ANCHOR_READ_SCHEMA","ANCHOR_READ_PURPOSE","ANCHOR_ROLE",
    "ANCHOR_DOMAIN","HEAD_MATCH","ADVANCE_CANDIDATE",
    "canonical_anchor_read","review_two_signed_domains",
    "review_secondary_anchor_advance_preconditions",
]
