"""G37 read-only recovery gate: two pinned issuer/custody signatures, NO SEND.

No authority or witness is independently owned: all test keys and SQLite
files remain locally controlled. Does not close any P0 or permit provider call.
"""
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied
from g37_signed_semantic_witness_lab import (
    DOMAIN, ROOT, TIP_DOMAIN, event_key, permit_digest, signing_bytes,
    tip_bytes, valid_permit,
)


def inspect_semantic_recovery(
    *, outbox: Any, idempotency_key: str, certified: Any, proof: Any,
    verifier_challenge: bytes, pinned_custody_key: bytes,
    pinned_issuer_key: bytes,
) -> Admission:
    """Only UNCERTAIN, even when all synthetic trust conditions match."""
    if (not isinstance(certified, dict) or
            set(certified) != {"permit", "issuer_signature"}):
        raise RecoveryDenied("G37_AUTHORITY_CERTIFICATE_MISSING")
    permit = certified["permit"]
    if not valid_permit(permit, now=int(datetime.now(timezone.utc).timestamp())):
        raise RecoveryDenied("G37_AUTHORITY_PERMIT_EXPIRED_OR_INVALID")
    if (not isinstance(pinned_issuer_key, bytes) or len(pinned_issuer_key) != 32
            or not isinstance(pinned_custody_key, bytes) or
            len(pinned_custody_key) != 32):
        raise RecoveryDenied("G37_BOTH_TRUST_PINS_REQUIRED")
    try:
        Ed25519PublicKey.from_public_bytes(pinned_issuer_key).verify(
            bytes.fromhex(certified["issuer_signature"]), signing_bytes(permit))
    except (ValueError, TypeError, KeyError, InvalidSignature) as exc:
        raise RecoveryDenied("G37_ISSUER_SIGNATURE_INVALID") from exc
    if not isinstance(proof, dict):
        raise RecoveryDenied("G37_CUSTODY_PROOF_MISSING")
    if (not isinstance(verifier_challenge, bytes) or
            len(verifier_challenge) != 32 or
            proof.get("nonce") != verifier_challenge.hex()):
        raise RecoveryDenied("G37_CUSTODY_CHALLENGE_MISMATCH")
    if proof.get("domain") != TIP_DOMAIN or proof.get("root_id") != ROOT:
        raise RecoveryDenied("G37_CUSTODY_ROOT_INVALID")
    if proof.get("event_key") != event_key(permit) or proof.get(
            "permit_digest") != permit_digest(permit):
        raise RecoveryDenied("G37_CERTIFICATE_CUSTODY_BINDING_MISMATCH")
    sequence = proof.get("event_sequence")
    latest = proof.get("global_sequence")
    head = proof.get("global_head")
    if (type(sequence) is not int or sequence < 1 or
            type(latest) is not int or latest < sequence or
            not isinstance(head, str) or len(head) != 64):
        raise RecoveryDenied("G37_CUSTODY_SEQUENCE_INVALID")
    try:
        Ed25519PublicKey.from_public_bytes(pinned_custody_key).verify(
            bytes.fromhex(proof["custody_signature"]), tip_bytes(proof))
    except (KeyError, ValueError, TypeError, InvalidSignature) as exc:
        raise RecoveryDenied("G37_CUSTODY_SIGNATURE_INVALID") from exc
    try:
        row = outbox.get(idempotency_key)
    except Exception as exc:
        raise RecoveryDenied("G37_OUTBOX_ROW_UNAVAILABLE") from exc
    if (row.get("idempotency_key") != idempotency_key or
            row.get("state") not in {"PENDING", "CLAIMED", "UNCERTAIN"}):
        raise RecoveryDenied("G37_UNSAFE_OR_UNSUPPORTED_LOCAL_STATE")
    decision = row.get("decision") or {}
    # Explicit synthetic business schema: never infer semantic identity from
    # caller-supplied request id or from a redacted credential-bearing digest.
    binding = {
        "business_event_id": permit["event_id"],
        "amount_minor": permit["amount_minor"],
        "currency": permit["currency"],
    }
    if (decision.get("payload") != binding or
            [decision.get("owner_id"), decision.get("tenant_id"),
             decision.get("workspace_id")] != permit["scope"] or
            decision.get("action") != permit["action"] or
            decision.get("aggregate_key") != permit["aggregate_key"]):
        raise RecoveryDenied("G37_REAL_OUTBOX_SEMANTIC_BINDING_MISMATCH")
    return Admission.UNCERTAIN
