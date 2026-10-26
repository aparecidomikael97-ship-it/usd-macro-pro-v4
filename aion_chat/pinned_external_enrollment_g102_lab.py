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
import sqlite3
from threading import Lock

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .intent_binding_a182_lab import (
    BoundFirstAttemptWitnessLab, semantic_bytes, trust_fingerprint,
)
from .signed_receipt_lab import canonical_bytes

ATTEST_SCHEMA = "AION:G102:LIVE_ENROLLMENT:V1"
ATTEST_DOMAIN = b"AION:G102:EXTERNAL_ATTESTATION:V1\x00"
# A distinct signature domain binds the *committed* attempt; preflight alone
# cannot be treated as a first-attempt reservation confirmation.
POST_SCHEMA = "AION:G104:POST_RESERVATION:V1"
POST_DOMAIN = b"AION:G104:POST_RESERVATION_ATTESTATION:V1\x00"
POST_FIELDS = frozenset({
    "schema", "status", "issuer", "challenge", "original_sha256",
    "trust_sha256", "high_water", "count", "sequence", "effect_digest",
    "decision_sha256", "idempotency_key",
})
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
        post_attestation, minimum_sequence, checkpoint, reservation_lookup,
        coherent_observation, reserve, now,
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
        if not callable(post_attestation):
            raise TypeError("G104_POST_COMMIT_ATTESTOR_REQUIRED")
        if not callable(checkpoint):
            raise TypeError("G102_CUSTODY_SNAPSHOT_REQUIRED")
        if not callable(reservation_lookup):
            raise TypeError("G107_EXACT_RESERVATION_LOOKUP_REQUIRED")
        if not callable(coherent_observation):
            raise TypeError("G111_ATOMIC_OBSERVER_REQUIRED")
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
        self._post_probe = post_attestation
        self._checkpoint = checkpoint
        self._reservation_lookup = reservation_lookup
        self._coherent_observation = coherent_observation
        self._minimum = minimum_sequence
        self._last_reservation = None

        def capture_reservation(challenge, request):
            # Save the actual A180 signed envelope returned by the reservation.
            # It is not a second authority: the existing A182 verifier MUST
            # cryptographically validate this receipt before it can be used.
            envelope = reserve(challenge, request)
            self._last_reservation = envelope
            return envelope

        self._bound = BoundFirstAttemptWitnessLab(
            original_decision=original_decision,
            issuer=issuer, key_id=key_id, public_key=public_key,
            expected_trust_sha256=expected_trust_sha256,
            minimum_sequence=minimum_sequence,
            checkpoint=checkpoint, reserve=capture_reservation, now=now,
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

    def _verify_post_reservation(self, envelope, challenge, after, before, receipt):
        """Require external signature for this exact *committed* attempt.

        The signature proves only what the configured attestor said. Real
        monotonic storage, live independence, protected pinning and atomic
        reservation ownership remain outside this opt-in LAB seam.
        """
        if type(receipt) is not dict or type(receipt.get("payload")) is not dict:
            return False
        recorded = receipt["payload"]
        if (type(after) is not dict
                or set(after) != {"high_water", "count"}
                or type(after["high_water"]) is not int
                or type(after["count"]) is not int
                or after["high_water"] != before["high_water"] + 1
                or after["count"] != before["count"] + 1
                or after["count"] != after["high_water"]
                or type(recorded.get("sequence")) is not int
                or recorded["sequence"] != after["high_water"]):
            return False
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            return False
        payload = envelope["payload"]
        if type(payload) is not dict or set(payload) != POST_FIELDS:
            return False
        if (payload["schema"] != POST_SCHEMA
                or payload["status"] != "RESERVED"
                or payload["issuer"] != self._issuer
                or payload["challenge"] != challenge
                or payload["original_sha256"] != self._original_sha256
                or payload["trust_sha256"] != self._expected_trust_sha256
                or type(payload["high_water"]) is not int
                or type(payload["count"]) is not int
                or type(payload["sequence"]) is not int
                or payload["high_water"] != after["high_water"]
                or payload["count"] != after["count"]
                or payload["sequence"] != recorded["sequence"]):
            return False
        # The post-commit attestor must commit to the same effect and business
        # decision actually authenticated by the A180 signed receipt.
        for field in ("effect_digest", "decision_sha256", "idempotency_key"):
            if type(recorded.get(field)) is not str or payload[field] != recorded[field]:
                return False
        if type(envelope["signature"]) is not str:
            return False
        signature = base64.b64decode(envelope["signature"], validate=True)
        if len(signature) != 64:
            return False
        self._anchor.verify(
            signature, POST_DOMAIN + canonical_bytes(payload),
        )
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
                # Preflight may succeed before a rollback or forged local
                # reserve. The existing A182 signed reservation is necessary,
                # but never sufficient until a *separate* challenge confirms
                # its exact effect/decision/id/ordinal after the commit.
                self._last_reservation = None
                if self._bound(intent) is not True:
                    return False
                recorded = self._last_reservation
                if type(recorded) is not dict or type(recorded.get("payload")) is not dict:
                    return False
                signed_reservation = recorded["payload"]
                post_request = {
                    field: signed_reservation.get(field)
                    for field in ("sequence", "effect_digest",
                                  "decision_sha256", "idempotency_key")
                }
                after = self._checkpoint()
                post_challenge = secrets.token_hex(32)
                if post_challenge == challenge:
                    return False
                proof_after = self._post_probe(post_challenge, post_request)
                # False after a local reservation is UNKNOWN/SPENT, not
                # rollback. The Outbox must not authorize a provider send.
                if not self._verify_post_reservation(
                    proof_after, post_challenge, after, local, recorded,
                ):
                    return False
                # The postproof observer may have signed the correct earlier
                # state while the host-owned SQLite custodian was replaced,
                # erased, or advanced before this call returned. Reread after
                # cryptographic verification. This is an additional fail-
                # closed local check, NOT an atomic remote/host/provider lock.
                final = self._checkpoint()
                if not (
                    type(final) is dict
                    and set(final) == {"high_water", "count"}
                    and type(final["high_water"]) is int
                    and type(final["count"]) is int
                    and final["high_water"] == final["count"]
                    and final["high_water"] == after["high_water"]
                    and final["count"] == after["count"]
                ):
                    return False
                # Counters alone are susceptible to an equal-ordinal ABA
                # database substitution. The same LOCAL journal must also
                # contain the exact reservation authenticated by A180.
                stored = self._reservation_lookup(
                    signed_reservation["effect_digest"]
                )
                expected = (
                    "effect_digest", "idempotency_key", "decision_sha256",
                    "owner_id", "tenant_id", "workspace_id", "sequence",
                )
                if type(stored) is not dict or set(stored) != set(expected):
                    return False
                if not all(
                    type(stored[name]) is type(signed_reservation[name])
                    and stored[name] == signed_reservation[name]
                    for name in expected
                ):
                    return False
                # G107's separate checkpoint and record reads can be correct
                # at DIFFERENT points in time. A final coherent local SQLite
                # transaction must observe both values in a single snapshot.
                coherent = self._coherent_observation(
                    signed_reservation["effect_digest"]
                )
                if (type(coherent) is not dict
                        or set(coherent) != {"high_water", "count", "record"}
                        or type(coherent["high_water"]) is not int
                        or type(coherent["count"]) is not int
                        or coherent["high_water"] != after["high_water"]
                        or coherent["count"] != after["count"]):
                    return False
                record = coherent["record"]
                if type(record) is not dict or set(record) != set(expected):
                    return False
                return all(
                    type(record[name]) is type(signed_reservation[name])
                    and record[name] == signed_reservation[name]
                    for name in expected
                )
            except (KeyError, TypeError, ValueError, RuntimeError, OSError,
                    sqlite3.Error, InvalidSignature, binascii.Error):
                # The opt-in verifier itself must return literal False even
                # when a supplied local record reader leaks a raw SQLite
                # exception. A spent reservation remains UNCERTAIN/NO SEND.
                return False
