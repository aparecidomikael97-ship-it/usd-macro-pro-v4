"""A146 LAB: signed high-water attestation with distinct pinned key.

Only proves an attestation came from a pinned Ed25519 signing key.
It DOES NOT prove that attestation is the latest or from independent storage.
Both old signed checkpoint and old signed high-water can replay together.
"""
import base64
import binascii
from dataclasses import dataclass
import hmac
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_p0_a145_checkpoint_verifier_lab import CheckpointRejected
from aion_p0_a146_highwater_gate_lab import HighWater, HighWaterRejected, _validate, check_restart_gate

DOMAIN = b"AION-A146-HIGHWATER-LAB-v1\x00"


@dataclass(frozen=True)
class SignedHighWater:
    anchor: HighWater
    key_id: str
    signature_b64: str


def canonical_highwater_bytes(anchor):
    _validate(anchor)
    payload = json.dumps({"ledger_id": anchor.ledger_id,
                          "sequence": anchor.sequence,
                          "history_digest": anchor.history_digest},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return DOMAIN + payload.encode("utf-8")


def verify_signed_highwater(*, envelope, pinned_authorities, forbidden_checkpoint_key):
    if not isinstance(envelope, SignedHighWater):
        raise HighWaterRejected("missing_signed_highwater")
    if not isinstance(pinned_authorities, dict) or not pinned_authorities:
        raise HighWaterRejected("missing_highwater_trust_anchor")
    if not isinstance(envelope.key_id, str) or envelope.key_id not in pinned_authorities:
        raise HighWaterRejected("unknown_highwater_signer")
    key = pinned_authorities[envelope.key_id]
    if not isinstance(key, bytes) or len(key) != 32:
        raise HighWaterRejected("invalid_highwater_public_key")
    if not isinstance(forbidden_checkpoint_key, bytes) or len(forbidden_checkpoint_key) != 32:
        raise HighWaterRejected("missing_checkpoint_public_key")
    if hmac.compare_digest(key, forbidden_checkpoint_key):
        raise HighWaterRejected("same_witness_and_checkpoint_key")
    if not isinstance(envelope.signature_b64, str):
        raise HighWaterRejected("invalid_highwater_signature_encoding")
    try:
        signature = base64.b64decode(envelope.signature_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HighWaterRejected("invalid_highwater_signature_encoding") from exc
    if len(signature) != 64:
        raise HighWaterRejected("invalid_highwater_signature_length")
    payload = canonical_highwater_bytes(envelope.anchor)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, payload)
    except (InvalidSignature, ValueError) as exc:
        raise HighWaterRejected("highwater_signature_mismatch") from exc
    return envelope.anchor


def check_restart_with_signed_highwater(*, ledger_id, events, envelope,
                                        checkpoint_pinned_keys,
                                        highwater_pinned_keys,
                                        read_signed_highwater):
    """Return a LAB consistency marker only. Not a production authorization.

    Key material is pre-pinned externally; reader and key custody MUST be
    independently trusted and non-rollbackable for real freshness.
    """
    if not callable(read_signed_highwater):
        raise HighWaterRejected("highwater_reader_missing")
    if not hasattr(envelope, "key_id") or not isinstance(envelope.key_id, str):
        raise CheckpointRejected("invalid_checkpoint_envelope")
    if not isinstance(checkpoint_pinned_keys, dict):
        raise CheckpointRejected("missing_checkpoint_trust_anchor")
    cp_key = checkpoint_pinned_keys.get(envelope.key_id)
    if not isinstance(cp_key, bytes) or len(cp_key) != 32:
        raise CheckpointRejected("missing_checkpoint_public_key")

    def authenticated_reader(identity):
        signed_anchor = read_signed_highwater(identity)
        return verify_signed_highwater(
            envelope=signed_anchor,
            pinned_authorities=highwater_pinned_keys,
            forbidden_checkpoint_key=cp_key,
        )

    return check_restart_gate(
        ledger_id=ledger_id, events=events, envelope=envelope,
        pinned_keys=checkpoint_pinned_keys,
        read_highwater=authenticated_reader,
    )
