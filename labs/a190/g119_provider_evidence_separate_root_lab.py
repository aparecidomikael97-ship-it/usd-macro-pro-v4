"""G119 — provider evidence *statement* verification, never SEND authority.

This is a LAB-only, signed-contract interface. Provider signatures here are
issued by a TEST FIXTURE, NOT an independent business provider. Correctly
signed statements are labelled SYNTHETIC CLAIMS, not actual delivery proofs.
Even an EXECUTED claim never permits automatic SEND, RETRY, Outbox CONFIRMED
or P0 GO. Actual provider provenance/key custody are unhomologated.

The witness root (G114) and provider statement root (G119) have distinct
domains and distinct pinned Ed25519 public keys in this test. Both private
keys still exist under the SAME HOST/TEST HARNESS, so no external trust.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import re
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a190.g118_signed_witness_recovery_lab import G118SignedWitnessRecoveryLab

PROVIDER_SCHEMA = "AION:G119:SYNTHETIC_PROVIDER_STATEMENT:V1"
PROVIDER_DOMAIN = b"AION:G119:PROVIDER_STATEMENT_SEPARATE_DOMAIN:V1\x00"
_PROVIDER_FIELDS = frozenset({
    "schema", "issuer", "challenge", "event_id", "original_sha256",
    "owner_id", "tenant_id", "workspace_id", "effect_digest",
    "idempotency_key", "sequence", "provider_event_ref", "claim",
})
_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


@dataclass(frozen=True)
class ProviderEvidenceAssessmentLab:
    disposition: str
    signed_statement: bool = False
    provider_claim: str = "UNVERIFIED"
    # No external authority yet, regardless of signed simulation.
    verified_real_provider: bool = False
    provider_outcome: str = "UNKNOWN"
    allow_send: bool = False
    allow_retry: bool = False
    may_mark_provider_confirmed: bool = False


class G119SyntheticProviderEvidenceVerifierLab:
    """One-use challenge and exact Ed25519 test statement, read-only."""

    def __init__(self, *, recovery_reader, provider_public_key, provider_issuer):
        if type(recovery_reader) is not G118SignedWitnessRecoveryLab:
            raise TypeError("G119_G118_SIGNED_RECOVERY_REQUIRED")
        if type(provider_public_key) is not bytes or len(provider_public_key) != 32:
            raise ValueError("G119_PROVIDER_PUBLIC_PIN_REQUIRED")
        if type(provider_issuer) is not str or not _REF.fullmatch(provider_issuer):
            raise ValueError("G119_PROVIDER_ISSUER_REQUIRED")
        witness_pin = recovery_reader._client._pin.public_bytes(
            Encoding.Raw, PublicFormat.Raw,
        )
        if provider_public_key == witness_pin:
            raise ValueError("G119_PROVIDER_WITNESS_KEY_MUST_DIFFER")
        self._recovery = recovery_reader
        self._provider_pin = Ed25519PublicKey.from_public_bytes(provider_public_key)
        self._issuer = provider_issuer
        self._outstanding = None
        self._used = set()

    def challenge(self):
        """A new one-use nonce; no reserve or external network request."""
        if self._outstanding is not None:
            raise RuntimeError("G119_OUTSTANDING_CHALLENGE_MUST_BE_RESOLVED")
        challenge = secrets.token_hex(32)
        while challenge in self._used:
            challenge = secrets.token_hex(32)
        self._outstanding = challenge
        return challenge

    def inspect_statement(self, envelope):
        """A consumed challenge cannot be reused, even after invalid proof."""
        nonce = self._outstanding
        if nonce is None:
            return ProviderEvidenceAssessmentLab("G119_NO_FRESH_CHALLENGE_DENIED")
        self._outstanding = None
        self._used.add(nonce)
        try:
            if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
                return ProviderEvidenceAssessmentLab("G119_MALFORMED_ENVELOPE_DENIED")
            payload = envelope["payload"]
            if type(payload) is not dict or set(payload) != _PROVIDER_FIELDS:
                return ProviderEvidenceAssessmentLab("G119_MALFORMED_PAYLOAD_DENIED")
            if (payload["schema"] != PROVIDER_SCHEMA
                    or payload["issuer"] != self._issuer
                    or payload["challenge"] != nonce):
                return ProviderEvidenceAssessmentLab("G119_ISSUER_DOMAIN_OR_REPLAY_DENIED")
            if (payload["claim"] not in ("EXECUTED", "REJECTED", "PENDING")
                    or type(payload["claim"]) is not str
                    or type(payload["provider_event_ref"]) is not str
                    or not _REF.fullmatch(payload["provider_event_ref"])):
                return ProviderEvidenceAssessmentLab("G119_INVALID_PROVIDER_CLAIM_DENIED")
            if (type(payload["sequence"]) is not int
                    or payload["sequence"] < 1
                    or type(envelope["signature"]) is not str):
                return ProviderEvidenceAssessmentLab("G119_SEQUENCE_OR_SIGNATURE_DENIED")
            signature = base64.b64decode(envelope["signature"], validate=True)
            if len(signature) != 64:
                return ProviderEvidenceAssessmentLab("G119_INVALID_SIGNATURE_DENIED")
            self._provider_pin.verify(
                signature, PROVIDER_DOMAIN + canonical_bytes(payload),
            )
            # Provider signature alone is insufficient: independently check
            # fresh signed witness reservation via the G118 read-only reader.
            observation = self._recovery.inspect()
            if observation.disposition != "RESERVATION_PRESENT_PROVIDER_UNKNOWN":
                return ProviderEvidenceAssessmentLab("G119_WITNESS_RESERVATION_NOT_VERIFIED")
            expected = {
                "event_id": self._recovery._event,
                "original_sha256": self._recovery._original_sha256,
                "effect_digest": self._recovery._effect,
                "idempotency_key": self._recovery._request_id,
                "owner_id": self._recovery._scope[0],
                "tenant_id": self._recovery._scope[1],
                "workspace_id": self._recovery._scope[2],
                "sequence": observation.observed_sequence,
            }
            if any(type(payload[field]) is not type(value)
                   or payload[field] != value
                   for field, value in expected.items()):
                return ProviderEvidenceAssessmentLab("G119_ORIGINAL_EFFECT_BINDING_DENIED")
            return ProviderEvidenceAssessmentLab(
                "G119_SYNTHETIC_PROVIDER_CLAIM_ONLY",
                signed_statement=True,
                provider_claim=payload["claim"],
            )
        except (KeyError, ValueError, TypeError, InvalidSignature, binascii.Error,
                OverflowError):
            return ProviderEvidenceAssessmentLab("G119_INVALID_SIGNATURE_OR_CONTENT_DENIED")
