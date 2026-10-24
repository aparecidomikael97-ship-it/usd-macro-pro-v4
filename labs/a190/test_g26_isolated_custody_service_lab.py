"""G26 adversarial protocol tests: isolated in-memory custody, NOT remote trust."""
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, canonical_hash,
)
from g24_challenge_bound_witness_lab import new_challenge
from g25_monotonic_custody_contract_lab import inspect_monotonic_recovery
from g26_isolated_custody_service_lab import (
    CustodyConflict, IsolatedCustodyService,
)

ROOT = "G26_SYNTHETIC_PIN"
KEY = "tenant:semantic:invoice-42"


def local_for(sequence, *, key=KEY, effect="UNKNOWN"):
    return {"semantic_key": key, "sequence": sequence,
            "phase": "UNCERTAIN", "effect": effect}


class G26IsolatedCustody(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.service = IsolatedCustodyService(self.private, ROOT)
        self.first = self.service.reserve(KEY, "UNCERTAIN", canonical_hash(local_for(1)))
        self.challenge = new_challenge()

    def check(self, *, service=None, key=KEY, local=None, challenge=None, floor=None):
        srv = self.service if service is None else service
        ch = self.challenge if challenge is None else challenge
        response = srv.attest(key, ch)
        high_water = srv.high_water(key) if floor is None else floor
        return inspect_monotonic_recovery(
            semantic_key=key, local_journal=local_for(1) if local is None else local,
            witness_response=response, pinned_root_id=ROOT,
            pinned_public_key=self.public, verifier_challenge=ch,
            external_high_water=high_water,
        )

    def test_01_new_reservation_has_sequence_one(self):
        self.assertEqual(self.first.sequence, 1)

    def test_02_matching_signed_custody_only_uncertain(self):
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_03_identical_reservation_is_idempotent(self):
        same = self.service.reserve(KEY, "UNCERTAIN", canonical_hash(local_for(1)))
        self.assertEqual(same, self.first)

    def test_04_semantic_conflict_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_SEMANTIC_REUSE_CONFLICT"):
            self.service.reserve(KEY, "UNCERTAIN", "f" * 64)

    def test_05_missing_reservation_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_NO_EXTERNAL_RESERVATION"):
            self.service.high_water("missing")

    def test_06_attestation_missing_reservation_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_NO_EXTERNAL_RESERVATION"):
            self.service.attest("missing", self.challenge)

    def test_07_different_semantic_intent_gets_next_sequence(self):
        next_key = "tenant:semantic:invoice-43"
        next_local = local_for(2, key=next_key)
        second = self.service.reserve(next_key, "UNCERTAIN", canonical_hash(next_local))
        self.assertEqual(second.sequence, 2)
        self.assertEqual(self.service.high_water(next_key).sequence, 2)

    def test_08_replay_old_challenge_to_new_verifier_denied(self):
        response = self.service.attest(KEY, self.challenge)
        new_nonce = new_challenge()
        from g25_monotonic_custody_contract_lab import inspect_monotonic_recovery
        with self.assertRaisesRegex(RecoveryDenied, "WITNESS_SIGNATURE_UNTRUSTED"):
            inspect_monotonic_recovery(
                semantic_key=KEY, local_journal=local_for(1),
                witness_response=response, pinned_root_id=ROOT,
                pinned_public_key=self.public, verifier_challenge=new_nonce,
                external_high_water=self.service.high_water(KEY),
            )

    def test_09_local_sequence_rollback_denied(self):
        with self.assertRaisesRegex(RecoveryDenied, "LOCAL_SEQUENCE_MISMATCH"):
            self.check(local=local_for(0))

    def test_10_local_payload_tamper_denied(self):
        with self.assertRaisesRegex(RecoveryDenied, "LOCAL_DIGEST_MISMATCH"):
            self.check(local=local_for(1, effect="CONFIRMED"))

    def test_11_bad_digest_reservation_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_INVALID_DIGEST"):
            self.service.reserve("new-key", "UNCERTAIN", "bad")

    def test_12_bad_phase_reservation_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_UNSUPPORTED_PHASE"):
            self.service.reserve("new-key", "SEND", "a" * 64)

    def test_13_new_empty_service_cannot_recover_old_record(self):
        replacement = IsolatedCustodyService(Ed25519PrivateKey.generate(), ROOT)
        with self.assertRaisesRegex(CustodyConflict, "G26_NO_EXTERNAL_RESERVATION"):
            replacement.high_water(KEY)
        print("G26_CUSTODY_RESTART_RED=IN_MEMORY_RESERVATION_LOST")

    def test_14_recreated_service_can_reuse_sequence_one_red(self):
        replacement = IsolatedCustodyService(Ed25519PrivateKey.generate(), ROOT)
        new = replacement.reserve("tenant:semantic:invoice-99", "UNCERTAIN", "a" * 64)
        self.assertEqual(new.sequence, 1)
        print("G26_MONOTONIC_RESTART_RED=COUNTER_RESET_AFTER_RESTART")

    def test_15_host_supplied_old_service_can_rewind_custody_red(self):
        # Simulates replacing custody with an older in-memory snapshot.
        old = IsolatedCustodyService(self.private, ROOT)
        old.reserve(KEY, "UNCERTAIN", canonical_hash(local_for(1)))
        second_key = "tenant:semantic:invoice-43"
        self.service.reserve(second_key, "UNCERTAIN",
                             canonical_hash(local_for(2, key=second_key)))
        self.assertEqual(self.check(service=old), Admission.UNCERTAIN)
        print("G26_CUSTODY_ROLLBACK_RED=OLD_SERVICE_ACCEPTS_OLD_HISTORY")

    def test_16_service_does_not_expose_signing_key(self):
        self.assertNotIn("private", vars(self.service))
        self.assertNotIn("key", vars(self.service))

    def test_17_invalid_semantic_key_denied(self):
        with self.assertRaisesRegex(CustodyConflict, "G26_INVALID_SEMANTIC_KEY"):
            self.service.reserve("", "UNCERTAIN", "a" * 64)

    def test_18_matching_custody_never_authorizes_send(self):
        self.assertNotEqual(self.check(), "SEND")


if __name__ == "__main__":
    unittest.main()
