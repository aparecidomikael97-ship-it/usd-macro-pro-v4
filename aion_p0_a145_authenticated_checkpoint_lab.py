"""A145 signed checkpoint verifier — isolated LAB, no external authority.

HMAC is deliberately NOT used as proof of an independent witness.
Ed25519 public key must be pinned out-of-band; caller-provided keys in
untrusted envelopes must never be accepted as trust roots.
Requires cryptography package. No production authorization.
"""
import base64
import json
from dataclasses import dataclass

from aion_p0_a145_checkpoint_verifier_lab import (
    Checkpoint, CheckpointRejected, verify_checkpoint,
)

DOMAIN = b"AION-A145-CHECKPOINT-LAB-v1\x00"


@dataclass(frozen=True)
class SignedCheckpoint:
    checkpoint: Checkpoint
    key_id: str
    signature_b64: str


def checkpoint_payload(checkpoint):
    if not isinstance(checkpoint, Checkpoint):
        raise CheckpointRejected("invalid_checkpoint")
    if not isinstance(checkpoint.ledger_id, str) or not checkpoint.ledger_id:
        raise CheckpointRejected("invalid_ledger_identity")
    if type(checkpoint.sequence) is not int or checkpoint.sequence < 0:
        raise CheckpointRejected("invalid_sequence")
    if (not isinstance(checkpoint.history_digest, str)
            or len(checkpoint.history_digest) != 64
            or any(c not in "0123456789abcdef" for c in checkpoint.history_digest)):
        raise CheckpointRejected("invalid_digest")
    return DOMAIN + json.dumps({
        "ledger_id": checkpoint.ledger_id,
        "sequence": checkpoint.sequence,
        "history_digest": checkpoint.history_digest,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_signed_checkpoint(*, ledger_id, events, envelope, pinned_keys):
    """Verify signature against externally pinned key, then compare history.

    WARNING: signature verification does not prove freshness, key custody,
    witness independence or monotonicity across restarts.
    """
    if not isinstance(envelope, SignedCheckpoint):
        raise CheckpointRejected("invalid_envelope")
    if not isinstance(pinned_keys, dict) or not pinned_keys:
        raise CheckpointRejected("missing_trust_anchor")
    if not isinstance(envelope.key_id, str) or envelope.key_id not in pinned_keys:
        raise CheckpointRejected("unknown_witness_key")
    key = pinned_keys[envelope.key_id]
    if not isinstance(key, bytes) or len(key) != 32:
        raise CheckpointRejected("invalid_pinned_key")
    if not isinstance(envelope.signature_b64, str):
        raise CheckpointRejected("invalid_signature")
    try:
        signature = base64.b64decode(envelope.signature_b64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise CheckpointRejected("invalid_signature_encoding") from exc
    if len(signature) != 64:
        raise CheckpointRejected("invalid_signature_length")
    payload = checkpoint_payload(envelope.checkpoint)
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(key).verify(signature, payload)
    except ImportError as exc:
        raise CheckpointRejected("cryptography_unavailable") from exc
    except ValueError as exc:
        raise CheckpointRejected("invalid_pinned_key") from exc
    except Exception as exc:
        from cryptography.exceptions import InvalidSignature
        if isinstance(exc, InvalidSignature):
            raise CheckpointRejected("signature_verification_failed") from exc
        raise
    return verify_checkpoint(ledger_id=ledger_id, events=events, witness=envelope.checkpoint)
