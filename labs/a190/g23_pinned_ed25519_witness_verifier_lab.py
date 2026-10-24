"""A190 G23: pinned Ed25519 witness signature verifier, isolated LAB only.

The pinned public key is injected separately from the signed statement and
local journal. The caller MUST establish the pin through a trusted external
provisioning process; this lab cannot establish that provenance or custody.
No private key, signing, provider calls, or production integration here.
"""
import base64
import json
from typing import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from g20_independent_witness_recovery_contract_lab import WitnessAttestation


class PinnedEd25519Witness:
    """Read-only witness verifier: no network, no external custody claim."""
    def __init__(self, *, attestation: WitnessAttestation,
                 trusted_public_keys: Mapping[str, bytes]):
        self._attestation = attestation
        self._trusted_keys = dict(trusted_public_keys)

    def attest_latest(self, semantic_key: str) -> WitnessAttestation:
        # This is a synthetic in-process store, not a remote monotonic log.
        return self._attestation

    def verify(self, statement: WitnessAttestation, pinned_root_id: str) -> bool:
        if statement.trust_root_id != pinned_root_id:
            return False
        raw = self._trusted_keys.get(pinned_root_id)
        if not isinstance(raw, bytes) or len(raw) != 32:
            return False
        if not isinstance(statement.signed_statement, bytes):
            return False
        if not isinstance(statement.journal_digest, str) or len(statement.journal_digest) != 64:
            return False
        try:
            int(statement.journal_digest, 16)
            payload = canonical_attestation_payload(statement)
            Ed25519PublicKey.from_public_bytes(raw).verify(
                statement.signed_statement, payload)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True


def canonical_attestation_payload(statement: WitnessAttestation) -> bytes:
    """Canonical signed domain binds semantic key, sequence, phase, digest, root."""
    payload = {
        "domain": "AION-A190-G23-WITNESS-LAB-V1",
        "semantic_key": statement.semantic_key,
        "sequence": statement.sequence,
        "phase": statement.phase,
        "journal_digest": statement.journal_digest,
        "trust_root_id": statement.trust_root_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
