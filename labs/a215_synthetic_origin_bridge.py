"""A215 LAB: compose local Outbox binding + synthetic Ed25519 signature math.

This deliberately does NOT verify independent key custody, provider effects,
out-of-band provenance, external receipts, external antirollback or witnesses.
A caller can generate every key/byte. The entire bridge is read-only and
always sets independent_origin_verified=False and may_confirm=False.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Mapping

from atlasquant_aion_external_evidence_intake import (
    decode_candidate_json, make_local_evidence_challenge,
    preflight_untrusted_effect_candidate,
)
from labs.a212_synthetic_signed_effect_preflight import (
    decode_strict_json_receipt, preflight_signed_synthetic_effect,
)


@dataclass(frozen=True)
class SyntheticOriginBridge:
    local_binding_ok: bool
    signature_math_valid: bool
    independent_origin_verified: bool
    may_confirm: bool
    code: str
    challenge_digest: str
    signed_statement_digest: str


def _deny(code: str, *, local_ok: bool = False, digest: str = "") -> SyntheticOriginBridge:
    return SyntheticOriginBridge(
        local_binding_ok=local_ok,
        signature_math_valid=False,
        independent_origin_verified=False,
        may_confirm=False,
        code=code,
        challenge_digest=digest,
        signed_statement_digest="",
    )


def _observation_text(value: Any) -> str:
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("unsupported observation clock")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("observation clock requires timezone")
    return stamp.astimezone(timezone.utc).isoformat()


def inspect_synthetic_origin_bridge(
    outbox_record: Any,
    candidate: Any,
    signed_receipt: Any,
    *,
    candidate_pubkey_bytes: Any,
    receipt_nonce_hex: Any,
    observed_at: Any,
    last_witness_sequence: Any,
    seen_provider_event_ids: Any,
    seen_receipt_nonces: Any,
) -> SyntheticOriginBridge:
    """Read-only, negative-authority cross-check of two existing lab contracts.

    Signature math valid under a supplied key NEVER verifies the key's origin.
    Untrusted caller-supplied histories NEVER establish durable non-replay.
    This LAB function is NOT an Outbox CONFIRMED admission path.
    """
    local = preflight_untrusted_effect_candidate(
        outbox_record, candidate, observed_at=observed_at,
    )
    if not local.matches_local_binding or local.may_confirm:
        return _deny("LOCAL_BINDING_" + local.code)

    if isinstance(candidate, str):
        try:
            candidate = decode_candidate_json(candidate)
        except ValueError:
            return _deny("AMBIGUOUS_LOCAL_CANDIDATE")
    if not isinstance(candidate, Mapping):
        return _deny("LOCAL_CANDIDATE_NOT_MAPPING")

    try:
        challenge = make_local_evidence_challenge(outbox_record)
        intent = json.loads(challenge.challenge_json)
    except (ValueError, TypeError, OverflowError):
        return _deny("LOCAL_INTENT_SNAPSHOT_INVALID")

    if isinstance(signed_receipt, str):
        try:
            signed_receipt = decode_strict_json_receipt(signed_receipt)
        except ValueError:
            return _deny(
                "MALFORMED_OR_AMBIGUOUS_SIGNED_RECEIPT",
                local_ok=True, digest=challenge.challenge_digest,
            )
    if not isinstance(signed_receipt, Mapping):
        return _deny(
            "SIGNED_RECEIPT_NOT_MAPPING",
            local_ok=True, digest=challenge.challenge_digest,
        )

    # Cross-source claims: both sides are still host-controlled. Match all
    # fields shared by A214 and A212, including event, effect, witness and time.
    shared = (
        "provider_id", "provider_event_id", "effect_ref", "effect_state",
        "witness_checkpoint_hash", "witness_sequence", "occurred_at",
    )
    for field in shared:
        if (
            field not in signed_receipt
            or type(signed_receipt[field]) is not type(candidate[field])
            or signed_receipt[field] != candidate[field]
        ):
            return _deny(
                "SYNTHETIC_RECEIPT_CANDIDATE_CONFLICT",
                local_ok=True, digest=challenge.challenge_digest,
            )
    if signed_receipt.get("witness_root_id") != candidate["witness_root_fingerprint"]:
        return _deny(
            "SYNTHETIC_ROOT_CLAIM_CONFLICT",
            local_ok=True, digest=challenge.challenge_digest,
        )

    # Expected fields are exclusively derived from a local Outbox snapshot
    # and a host-provided claim, never an authenticated provider or external root.
    expected = {
        "owner_id": intent["owner_id"],
        "tenant_id": intent["tenant_id"],
        "workspace_id": intent["workspace_id"],
        "operation_kind": intent["action"].upper(),
        "intent_digest": challenge.challenge_digest,
        "idempotency_key": intent["idempotency_key"],
        "provider_id": candidate["provider_id"],
        "witness_root_id": candidate["witness_root_fingerprint"],
        "witness_checkpoint_hash": candidate["witness_checkpoint_hash"],
        "receipt_nonce_hex": receipt_nonce_hex,
        "subject_digest": candidate["provider_receipt_digest"],
    }
    try:
        observed_text = _observation_text(observed_at)
    except (ValueError, OverflowError, TypeError):
        return _deny(
            "INVALID_OBSERVATION_CLOCK",
            local_ok=True, digest=challenge.challenge_digest,
        )

    assessed = preflight_signed_synthetic_effect(
        signed_receipt, expected=expected,
        candidate_pubkey_bytes=candidate_pubkey_bytes,
        authorized_at=intent["dispatch_started_at"],
        observed_at=observed_text,
        last_witness_sequence=last_witness_sequence,
        seen_provider_event_ids=seen_provider_event_ids,
        seen_receipt_nonces=seen_receipt_nonces,
    )
    if not assessed.mathematically_valid_signature or assessed.may_confirm:
        return _deny(
            "SYNTHETIC_SIGNATURE_" + assessed.code,
            local_ok=True, digest=challenge.challenge_digest,
        )

    # No authenticated, independently acquired key, provider proof, log
    # inclusion/consistency or durable external nonce floor was consulted.
    return SyntheticOriginBridge(
        local_binding_ok=True,
        signature_math_valid=True,
        independent_origin_verified=False,
        may_confirm=False,
        code="LOCAL_AND_SIGNATURE_MATH_MATCH_BUT_ORIGIN_AND_EFFECT_UNPROVEN",
        challenge_digest=challenge.challenge_digest,
        signed_statement_digest=assessed.statement_digest,
    )


__all__ = ["SyntheticOriginBridge", "inspect_synthetic_origin_bridge"]
