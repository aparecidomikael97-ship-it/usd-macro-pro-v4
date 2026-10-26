"""G102 synthetic contract checks; NO live independent remote signer.

A separately provisioned real attestor is NOT present; the signer/state below
are in-process test doubles. They prove fail-closed wire format and first-attempt
dispatch integration only, not H0, antirollback or any actual external P0.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aion_chat.intent_binding_a182_lab import semantic_bytes, trust_fingerprint
from aion_chat.pinned_external_enrollment_g102_lab import (
    ATTEST_DOMAIN, ATTEST_SCHEMA, PinnedExternalEnrollmentAdmissionLab,
)
from aion_chat.signed_receipt_lab import canonical_bytes
from test_atlasquant_aion_signed_receipt_a178_lab import public_bytes
from test_atlasquant_aion_separate_custody_a181_lab import (
    ISSUER, KEY_ID, PRIVATE,
)
from test_atlasquant_aion_execution_outbox import NOW
from test_atlasquant_aion_intent_binding_a182_lab import A182Fixture


ANCHOR_ISSUER = "g102-synthetic-out-of-band-attestation"
ANCHOR_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x39" * 32)
OTHER_PRIVATE = Ed25519PrivateKey.from_private_bytes(b"\x40" * 32)


class G102PinnedExternalAdmission(A182Fixture):
    def setUp(self):
        super().setUp()
        self.remote_sequence = {"high_water": 0, "count": 0}
        self.remote_original = None
        self.remote_root = None
        self.probe_calls = 0

    def enroll_fixture(self):
        original = self.original()
        self.remote_original = sha256(
            semantic_bytes(original["decision"]),
        ).hexdigest()
        self.remote_root = trust_fingerprint(
            issuer=ISSUER, key_id=KEY_ID, public_key=public_bytes(PRIVATE),
        )
        return original

    def proof(self, challenge, *, signer=None, overrides=None):
        self.probe_calls += 1
        payload = {
            "schema": ATTEST_SCHEMA,
            "status": "CURRENT",
            "issuer": ANCHOR_ISSUER,
            "challenge": challenge,
            "original_sha256": self.remote_original,
            "trust_sha256": self.remote_root,
            "high_water": self.remote_sequence["high_water"],
            "count": self.remote_sequence["count"],
        }
        if overrides:
            payload.update(overrides)
        signer = signer or ANCHOR_PRIVATE
        return {
            "payload": payload,
            "signature": base64.b64encode(
                signer.sign(ATTEST_DOMAIN + canonical_bytes(payload)),
            ).decode("ascii"),
        }

    def reserve_synced(self, challenge, request):
        result = self.custody.reserve(challenge, request)
        if type(result) is dict and "signature" in result:
            # Only the synthetic in-memory test double advances this state.
            # A real independent custodian does not exist in this test.
            current = self.custody.snapshot()
            self.remote_sequence.update(current)
        return result

    def make_guard(self, original, *, issuer=ISSUER, key_id=KEY_ID,
                   public_key=None, witness_fingerprint=None,
                   original_pin=None, anchor_public=None, probe=None,
                   minimum_sequence=0, reserve=None, checkpoint=None):
        public_key = public_key or public_bytes(PRIVATE)
        witness_fingerprint = witness_fingerprint or trust_fingerprint(
            issuer=issuer, key_id=key_id, public_key=public_key,
        )
        return PinnedExternalEnrollmentAdmissionLab(
            original_decision=original["decision"],
            enrolled_original_sha256=(
                self.remote_original if original_pin is None else original_pin
            ),
            issuer=issuer,
            key_id=key_id,
            public_key=public_key,
            expected_trust_sha256=witness_fingerprint,
            anchor_issuer=ANCHOR_ISSUER,
            anchor_public_key=anchor_public or public_bytes(ANCHOR_PRIVATE),
            probe_attestation=self.proof if probe is None else probe,
            minimum_sequence=minimum_sequence,
            checkpoint=self.custody.snapshot if checkpoint is None else checkpoint,
            reserve=self.reserve_synced if reserve is None else reserve,
            now=NOW + timedelta(seconds=2),
        )

    def test_01_valid_synthetic_attestation_allows_one_in_memory_dispatch(self):
        original = self.enroll_fixture()
        guard = self.make_guard(original)
        store, out, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(out, row)
            self.assertEqual(result["state"], "CONFIRMED")
            self.assertEqual(adapter.send_calls, 1)
            self.assertEqual(self.remote_sequence["high_water"], 1)
            self.assertEqual(self.custody.snapshot()["count"], 1)
        finally:
            store.close()
        print("G102_SYNTHETIC_VALID=ONE_IN_MEMORY_EFFECT_ONLY")

    def test_02_missing_attestor_denies_before_reservation_and_send(self):
        original = self.enroll_fixture()
        def offline(_challenge):
            raise TimeoutError("G102_SYNTHETIC_EXTERNAL_UNAVAILABLE")
        guard = self.make_guard(original, probe=offline)
        store, out, row = self.host(guard=guard)
        try:
            result, adapter = self.claim_and_send(out, row)
            self.assertEqual(result["state"], "UNCERTAIN")
            self.assertEqual(adapter.send_calls, 0)
            self.assertEqual(self.custody.snapshot()["count"], 0)
        finally:
            store.close()
        print("G102_UNAVAILABLE=NO_RESERVATION_NO_SEND")

    def test_03_wrong_private_key_cannot_sign_valid_attestation(self):
        original = self.enroll_fixture()
        guard = self.make_guard(
            original, probe=lambda c: self.proof(c, signer=OTHER_PRIVATE),
        )
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_WRONG_SIGNER=DENIED")

    def test_04_stale_challenge_even_valid_signature_cannot_replay(self):
        original = self.enroll_fixture()
        replay = self.proof("0" * 64)
        guard = self.make_guard(original, probe=lambda _c: deepcopy(replay))
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_REPLAYED_SIGNATURE=DENIED")

    def test_05_changed_business_enrollment_denied_even_if_local_rebound(self):
        original = self.enroll_fixture()
        forged = deepcopy(original)
        forged["decision"]["aggregate_key"] = "synthetic-rebound-account"
        with self.assertRaisesRegex(
            ValueError, "G102_EXTERNAL_ORIGINAL_ENROLLMENT_REQUIRED",
        ):
            self.make_guard(forged)
        self.assertFalse(self.make_guard(original)(forged))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_REPLACEMENT_ORIGINAL=DENIED_BY_PIN")

    def test_06_replacing_local_witness_key_and_self_fingerprint_denied(self):
        original = self.enroll_fixture()
        forged_public = public_bytes(OTHER_PRIVATE)
        forged_fingerprint = trust_fingerprint(
            issuer=ISSUER, key_id=KEY_ID, public_key=forged_public,
        )
        guard = self.make_guard(
            original, public_key=forged_public,
            witness_fingerprint=forged_fingerprint,
        )
        self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_REPIN_LOCAL_ROOT=DENIED_BY_ATTESTED_ROOT")

    def test_07_local_custody_rebootstrap_denied_against_retained_remote_state(self):
        original = self.enroll_fixture()
        self.assertTrue(self.make_guard(original)(original))
        self.assertEqual(self.remote_sequence["count"], 1)
        self.custody_db.unlink()
        self.custody = self.bootstrap()
        self.assertEqual(self.custody.snapshot()["count"], 0)
        # Rebuild local guard from restored local storage, but DO NOT
        # restore the simulated external state. This tests the contract's
        # monotonic comparison, not a real independent custodian.
        self.assertFalse(self.make_guard(original)(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_LOCAL_CUSTODY_REBOOTSTRAP=DENIED_WITH_RETAINED_EXTERNAL")

    def test_08_signed_remote_sequence_disagreement_denies_reservation(self):
        original = self.enroll_fixture()
        self.remote_sequence = {"high_water": 5, "count": 5}
        self.assertFalse(self.make_guard(original)(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_SIGNED_SEQUENCE_DIVERGENCE=DENIED")

    def test_09_signed_malformed_body_denied_without_reservation(self):
        original = self.enroll_fixture()
        for forged in (
            {"ok": True},
            self.proof("abc", overrides={"status": "UNKNOWN"}),
            self.proof("abc", overrides={"high_water": True}),
        ):
            with self.subTest(envelope=repr(forged)[:80]):
                guard = self.make_guard(original, probe=lambda _c, x=forged: x)
                self.assertFalse(guard(original))
        self.assertEqual(self.custody.snapshot()["count"], 0)
        print("G102_MALFORMED_ENVELOPE=DENIED")

    def test_10_double_request_under_one_guard_reserves_only_once(self):
        original = self.enroll_fixture()
        guard = self.make_guard(original)
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(lambda _: guard(deepcopy(original)), range(6)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["high_water"], 1)
        print("G102_SAME_GUARD_CONCURRENCY=ONE_SYNTHETIC_RESERVATION")


if __name__ == "__main__":
    unittest.main()
