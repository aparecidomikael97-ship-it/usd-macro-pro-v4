"""G24 adversarial challenge-bound Ed25519 freshness tests, no real custody."""
from dataclasses import replace
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, canonical_hash,
)
from g24_challenge_bound_witness_lab import (
    ChallengeResponse, challenge_payload, inspect_freshness, new_challenge,
)

ROOT = "G24_LAB_PIN"
KEY = "tenant:semantic:invoice-42"
LOCAL = {
    "semantic_key": KEY, "sequence": 5, "phase": "UNCERTAIN",
    "effect": "UNKNOWN", "transport_ref": "req-1",
}


class G24ChallengeBoundWitness(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.challenge = new_challenge()
        self.statement = WitnessAttestation(
            KEY, 5, "UNCERTAIN", canonical_hash(LOCAL), ROOT, b"challenge-attestation",
        )
        self.response = self.sign(self.statement, self.challenge)

    def sign(self, statement, challenge, private=None):
        signer = self.private if private is None else private
        return ChallengeResponse(
            statement, challenge,
            signer.sign(challenge_payload(statement, challenge)),
        )

    def check(self, *, local=LOCAL, response=None, challenge=None,
              root=ROOT, public=None, key=KEY):
        return inspect_freshness(
            semantic_key=key, local_journal=local,
            witness_response=self.response if response is None else response,
            pinned_root_id=root,
            pinned_public_key=self.public if public is None else public,
            challenge=self.challenge if challenge is None else challenge,
        )

    def deny(self, fragment, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, fragment):
            self.check(**kwargs)

    def test_01_valid_fresh_challenge_only_uncertain(self):
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_02_old_response_replayed_to_new_challenge_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", challenge=new_challenge())

    def test_03_response_nonce_substitution_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, challenge=b"x" * 32))

    def test_04_signature_bit_flip_denied(self):
        sig = self.response.signature
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, signature=bytes([sig[0] ^ 1]) + sig[1:]))

    def test_05_attacker_signed_unpinned_key_denied(self):
        attacker = Ed25519PrivateKey.generate()
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=self.sign(self.statement, self.challenge, private=attacker))

    def test_06_missing_pin_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", public=b"")

    def test_07_wrong_root_denied(self):
        self.deny("WITNESS_ROOT_MISMATCH", root="wrong")

    def test_08_signed_sequence_tamper_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, statement=replace(self.statement, sequence=4)))

    def test_09_signed_phase_tamper_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, statement=replace(self.statement, phase="RESERVED")))

    def test_10_signed_digest_tamper_denied(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  response=replace(self.response, statement=replace(self.statement, journal_digest="0" * 64)))

    def test_11_local_rollback_denied_with_current_attestation(self):
        self.deny("LOCAL_SEQUENCE_MISMATCH", local={**LOCAL, "sequence": 4})

    def test_12_local_payload_tamper_denied(self):
        self.deny("LOCAL_DIGEST_MISMATCH", local={**LOCAL, "effect": "CONFIRMED"})

    def test_13_deleted_local_journal_denied(self):
        self.deny("LOCAL_JOURNAL_MISSING", local=None)

    def test_14_invalid_short_challenge_denied(self):
        self.deny("G24_INVALID_CHALLENGE", challenge=b"short")

    def test_15_invalid_response_denied(self):
        self.deny("G24_INVALID_RESPONSE", response="bad-response")

    def test_16_new_challenges_distinct(self):
        self.assertEqual(len(self.challenge), 32)
        self.assertNotEqual(self.challenge, new_challenge())

    def test_17_compromised_witness_freshly_signs_OLD_history_red(self):
        old = {**LOCAL, "sequence": 4}
        old_statement = WitnessAttestation(
            KEY, 4, "UNCERTAIN", canonical_hash(old), ROOT, b"challenge-attestation",
        )
        # Same signing key can sign a fresh nonce over a rolled-back history.
        old_response = self.sign(old_statement, self.challenge)
        self.assertEqual(self.check(local=old, response=old_response), Admission.UNCERTAIN)
        print("G24_FRESH_NONCE_OLD_HISTORY_RED=SIGNER_CAN_ATTEST_ROLLBACK")

    def test_18_valid_response_still_never_authorizes_provider_send(self):
        self.assertNotEqual(self.check(), "SEND")


if __name__ == "__main__":
    unittest.main()
