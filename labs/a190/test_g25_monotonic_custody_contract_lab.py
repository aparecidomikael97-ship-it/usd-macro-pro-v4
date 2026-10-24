"""G25 monotonic custody boundary, signed challenge and host-floor RED tests."""
from dataclasses import replace
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, canonical_hash,
)
from g24_challenge_bound_witness_lab import (
    ChallengeResponse, challenge_payload, new_challenge,
)
from g25_monotonic_custody_contract_lab import (
    TrustedHighWaterMark, inspect_monotonic_recovery,
)

ROOT = "G25_SYNTHETIC_EXTERNAL_PIN"
KEY = "tenant:invoice:semantic-42"
LOCAL = {"semantic_key": KEY, "sequence": 8, "phase": "UNCERTAIN",
         "effect": "UNKNOWN", "transport_ref": "g25-ref"}


class G25MonotonicCustodyContract(unittest.TestCase):
    def setUp(self):
        self.signer = Ed25519PrivateKey.generate()
        self.public = self.signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.challenge = new_challenge()
        self.statement = self.statement_for(LOCAL)
        self.response = self.sign(self.statement)
        self.floor = self.floor_for(LOCAL)

    def statement_for(self, local):
        return WitnessAttestation(
            KEY, local["sequence"], local["phase"],
            canonical_hash(local), ROOT, b"synthetic",
        )

    def sign(self, statement, *, challenge=None):
        ch = self.challenge if challenge is None else challenge
        return ChallengeResponse(statement, ch,
                                 self.signer.sign(challenge_payload(statement, ch)))

    def floor_for(self, local):
        return TrustedHighWaterMark(KEY, local["sequence"], canonical_hash(local))

    def check(self, *, local=LOCAL, response=None, floor="default",
              challenge=None, pin=None, root=ROOT):
        actual_floor = self.floor if floor == "default" else floor
        return inspect_monotonic_recovery(
            semantic_key=KEY, local_journal=local,
            witness_response=self.response if response is None else response,
            pinned_root_id=root,
            pinned_public_key=self.public if pin is None else pin,
            verifier_challenge=self.challenge if challenge is None else challenge,
            external_high_water=actual_floor,
        )

    def deny(self, message, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, message):
            self.check(**kwargs)

    def test_01_matching_synthetic_floor_only_uncertain(self):
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_02_missing_floor_denies(self):
        self.deny("G25_EXTERNAL_MONOTONIC_FLOOR_MISSING", floor=None)

    def test_03_witness_below_independent_floor_denies(self):
        old = {**LOCAL, "sequence": 7}
        self.deny("G25_WITNESS_BELOW_EXTERNAL_FLOOR",
                  local=old, response=self.sign(self.statement_for(old)))

    def test_04_floor_behind_witness_denies(self):
        self.deny("G25_EXTERNAL_FLOOR_STALE_OR_UNVERIFIED",
                  floor=TrustedHighWaterMark(KEY, 7, canonical_hash(LOCAL)))

    def test_05_same_sequence_different_digest_denies(self):
        self.deny("G25_EXTERNAL_DIGEST_CONFLICT",
                  floor=TrustedHighWaterMark(KEY, 8, "0" * 64))

    def test_06_external_floor_wrong_semantic_denies(self):
        self.deny("G25_EXTERNAL_SEMANTIC_MISMATCH",
                  floor=TrustedHighWaterMark("tenant:other", 8, canonical_hash(LOCAL)))

    def test_07_invalid_sequence_type_denies(self):
        self.deny("G25_EXTERNAL_SEQUENCE_INVALID",
                  floor=TrustedHighWaterMark(KEY, True, canonical_hash(LOCAL)))

    def test_08_invalid_digest_denies(self):
        self.deny("G25_EXTERNAL_DIGEST_INVALID",
                  floor=TrustedHighWaterMark(KEY, 8, "short"))

    def test_09_replayed_response_new_nonce_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", challenge=new_challenge())

    def test_10_unpinned_key_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", pin=b"short")

    def test_11_signature_bit_flip_denies(self):
        sig = self.response.signature
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, signature=bytes([sig[0] ^ 1]) + sig[1:]))

    def test_12_local_rollback_with_current_floor_denies(self):
        self.deny("LOCAL_SEQUENCE_MISMATCH",
                  local={**LOCAL, "sequence": 7})

    def test_13_local_payload_tamper_denies(self):
        self.deny("LOCAL_DIGEST_MISMATCH",
                  local={**LOCAL, "effect": "CONFIRMED"})

    def test_14_deleted_local_history_denies(self):
        self.deny("LOCAL_JOURNAL_MISSING", local=None)

    def test_15_host_controls_floor_and_rewinds_both_red(self):
        old = {**LOCAL, "sequence": 7}
        old_statement = self.statement_for(old)
        old_response = self.sign(old_statement)
        host_supplied_floor = self.floor_for(old)
        self.assertEqual(
            self.check(local=old, response=old_response, floor=host_supplied_floor),
            Admission.UNCERTAIN,
        )
        print("G25_HOST_CONTROLLED_FLOOR_RED=OLD_JOURNAL_OLD_FLOOR_MATCH")

    def test_16_malformed_floor_denies(self):
        self.deny("G25_EXTERNAL_MONOTONIC_FLOOR_MALFORMED", floor="bad")

    def test_17_wrong_pinned_root_denies(self):
        self.deny("WITNESS_ROOT_MISMATCH", root="wrong")

    def test_18_matching_floor_does_not_authorize_send(self):
        self.assertNotEqual(self.check(), "SEND")


if __name__ == "__main__":
    unittest.main()
