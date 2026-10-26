"""G102 LAB: signed out-of-band enrollment admission before first attempt.

Opt-in research seam, NOT a production Worker gate. It verifies a fresh signed
snapshot binding original business decision, witness trust root and custody
ordinal to a pinned attestation public key. The provisioning of that public
key and the actual independence/monotonicity of the attestor are OUTSIDE this
module; caller-supplied roots or a fake attestor defeat the guarantee. Never
interpret synthetic signatures as P0/hardware/third-party certification.
"""
import base64
import binascii
from hashlib import sha256
import secrets
from threading import Lock

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .intent_binding_a182_lab import (
    BoundFirstAttemptWitnessLab, semantic_bytes, trust_fingerprint,
)
from .signed_receipt_lab import canonical_bytes

ATTEST_SCHEMA = "AION:G102:LIVE_ENROLLMENT:V1"
ATTEST_DOMAIN = b"AION:G102:EXTERNAL_ATTESTATION:V1\x00"
_FIELDS = frozenset({
    "schema", "status", "issuer", "challenge", "original_sha256",
    "trust_sha256", "high_water", "count",
})


class PinnedExternalEnrollmentAdmissionLab:
    """Fail-closed probe + A182 verifier; all trust inputs must preexist intent.

    An attacker who can repin the trusted public key AND replace the attestor
    can still bypass this LAB contract. A live independent remote institution,
    protected provisioning and durable server-side monotonicity are required
    for a true external acceptance, and are not provided here.
    """

    def __init__(
        self, *, original_decision, enrolled_original_sha256,
        issuer, key_id, public_key, expected_trust_sha256,
        anchor_issuer, anchor_public_key, probe_attestation,
        minimum_sequence, checkpoint, reserve, now,
    ):
        original = semantic_bytes(original_decision)
        if (type(enrolled_original_sha256) is not str
                or len(enrolled_original_sha256) != 64
                or sha256(original).hexdigest() != enrolled_original_sha256):
            raise ValueError("G102_EXTERNAL_ORIGINAL_ENROLLMENT_REQUIRED")
        expected = trust_fingerprint(
            issuer=issuer, key_id=key_id, public_key=public_key,
        )
        if (type(expected_trust_sha256) is not str
                or expected_trust_sha256 != expected):
            raise ValueError("G102_EXTERNAL_ROOT_PIN_REQUIRED")
        if (type(anchor_issuer) is not str or not anchor_issuer
                or type(anchor_public_key) is not bytes
                or len(anchor_public_key) != 32):
            raise ValueError("G102_EXTERNAL_ATTESTOR_PIN_REQUIRED")
        if not callable(probe_attestation):
            raise TypeError("G102_ATTESTOR_PROBE_REQUIRED")
        if not callable(checkpoint):
            raise TypeError("G102_CUSTODY_SNAPSHOT_REQUIRED")
        if type(minimum_sequence) is not int or minimum_sequence < 0:
            raise ValueError("G102_SEQUENCE_FLOOR_REQUIRED")
        # A challenge at each call defeats replay of an earlier valid signed
        # observation; signature validity alone cannot prove current custody.
        self._lock = Lock()
        self._original = original
        self._original_sha256 = enrolled_original_sha256
        self._expected_trust_sha256 = expected_trust_sha256
        self._issuer = anchor_issuer
        self._anchor = Ed25519PublicKey.from_public_bytes(anchor_public_key)
        self._probe = probe_attestation
        self._checkpoint = checkpoint
        self._minimum = minimum_sequence
        self._bound = BoundFirstAttemptWitnessLab(
            original_decision=original_decision,
            issuer=issuer, key_id=key_id, public_key=public_key,
            expected_trust_sha256=expected_trust_sha256,
            minimum_sequence=minimum_sequence,
            checkpoint=checkpoint, reserve=reserve, now=now,
        )

    def _verify_fresh_enrollment(self, envelope, challenge, local):
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            return False
        payload = envelope["payload"]
        if type(payload) is not dict or set(payload) != _FIELDS:
            return False
        if (payload["schema"] != ATTEST_SCHEMA
                or payload["status"] != "CURRENT"
                or payload["issuer"] != self._issuer
                or payload["challenge"] != challenge
                or payload["original_sha256"] != self._original_sha256
                or payload["trust_sha256"] != self._expected_trust_sha256):
            return False
        if (type(payload["high_water"]) is not int
                or type(payload["count"]) is not int
                or payload["high_water"] != payload["count"]
                or payload["high_water"] < self._minimum
                or payload["high_water"] != local["high_water"]
                or payload["count"] != local["count"]):
            return False
        if type(envelope["signature"]) is not str:
            return False
        sig = base64.b64decode(envelope["signature"], validate=True)
        if len(sig) != 64:
            return False
        self._anchor.verify(sig, ATTEST_DOMAIN + canonical_bytes(payload))
        return True

    def __call__(self, intent):
        # The lock guards only this process. The external authority must keep
        # reservations monotonic and current across processes/restarts.
        with self._lock:
            try:
                if (type(intent) is not dict
                        or semantic_bytes(intent.get("decision")) != self._original):
                    return False
                local = self._checkpoint()
                if (type(local) is not dict
                        or set(local) != {"high_water", "count"}
                        or type(local["high_water"]) is not int
                        or type(local["count"]) is not int
                        or local["high_water"] != local["count"]
                        or local["high_water"] < self._minimum):
                    return False
                challenge = secrets.token_hex(32)
                attestation = self._probe(challenge)
                if not self._verify_fresh_enrollment(attestation, challenge, local):
                    return False
                # The existing A182 signed first-attempt reservation remains
                # mandatory; the attestation alone never authorizes SEND.
                return self._bound(intent) is True
            except (KeyError, TypeError, ValueError, RuntimeError, OSError,
                    InvalidSignature, binascii.Error):
                return False
