"""G23 Ed25519 adversarial witness tests, entirely synthetic keys and data."""
from dataclasses import replace
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, canonical_hash,
    recovery_admission,
)
from g23_pinned_ed25519_witness_verifier_lab import (
    PinnedEd25519Witness, canonical_attestation_payload,
)

ROOT = "synthetic-pinned-root-G23"
KEY = "tenant:semantic-operation:42"
JOURNAL = {
    "semantic_key": KEY, "sequence": 9, "phase": "UNCERTAIN",
    "provider_effect": "UNKNOWN", "request_id": "synthetic-1",
}


class G23PinnedEd25519(unittest.TestCase):
    def setUp(self):
        self.signer = Ed25519PrivateKey.generate()  # ephemeral synthetic test key
        self.public = self.signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        unsigned = WitnessAttestation(
            KEY, 9, "UNCERTAIN", canonical_hash(JOURNAL), ROOT, b"",
        )
        self.statement = replace(
            unsigned,
            signed_statement=self.signer.sign(canonical_attestation_payload(unsigned)),
        )
        self.verifier = PinnedEd25519Witness(
            attestation=self.statement, trusted_public_keys={ROOT: self.public},
        )

    def check(self, *, journal=JOURNAL, statement=None, trusted_keys=None, root=ROOT):
        verifier = PinnedEd25519Witness(
            attestation=self.statement if statement is None else statement,
            trusted_public_keys={ROOT: self.public} if trusted_keys is None else trusted_keys,
        )
        return recovery_admission(
            semantic_key=KEY, local_journal=journal,
            witness=verifier, pinned_root_id=root,
        )

    def deny(self, fragment, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, fragment):
            self.check(**kwargs)

    def test_01_valid_pinned_signature_still_only_uncertain(self):
        self.assertEqual(self.check(), Admission.UNCERTAIN)

    def test_02_signature_bit_flip_denies(self):
        bad = self.statement.signed_statement
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  statement=replace(self.statement,
                                    signed_statement=bytes([bad[0] ^ 1]) + bad[1:]))

    def test_03_attacker_self_signed_unpinned_key_denies(self):
        attacker = Ed25519PrivateKey.generate()
        unsigned = replace(self.statement, signed_statement=b"")
        forged = replace(unsigned,
                         signed_statement=attacker.sign(canonical_attestation_payload(unsigned)))
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", statement=forged)

    def test_04_missing_pin_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", trusted_keys={})

    def test_05_wrong_pin_denies(self):
        other = Ed25519PrivateKey.generate()
        other_pub = other.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", trusted_keys={ROOT: other_pub})

    def test_06_modified_signed_sequence_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  statement=replace(self.statement, sequence=10))

    def test_07_modified_signed_phase_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  statement=replace(self.statement, phase="RESERVED"))

    def test_08_modified_signed_digest_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED",
                  statement=replace(self.statement, journal_digest="a" * 64))

    def test_09_modified_signed_semantic_key_denies(self):
        self.deny("WITNESS_SEMANTIC_MISMATCH",
                  statement=replace(self.statement, semantic_key="tenant:other"))

    def test_10_wrong_root_id_denies(self):
        self.deny("WITNESS_ROOT_MISMATCH", root="other-root")

    def test_11_host_rollback_of_local_journal_denies(self):
        self.deny("LOCAL_SEQUENCE_MISMATCH",
                  journal={**JOURNAL, "sequence": 8})

    def test_12_host_tampered_local_payload_denies(self):
        self.deny("LOCAL_DIGEST_MISMATCH",
                  journal={**JOURNAL, "provider_effect": "CONFIRMED"})

    def test_13_missing_local_journal_denies(self):
        self.deny("LOCAL_JOURNAL_MISSING", journal=None)

    def test_14_signed_old_statement_with_matching_old_journal_is_not_detected_red(self):
        """A valid old signature + old local journal cannot prove freshness."""
        old = {**JOURNAL, "sequence": 8}
        unsigned = WitnessAttestation(
            KEY, 8, "UNCERTAIN", canonical_hash(old), ROOT, b"",
        )
        old_signed = replace(
            unsigned,
            signed_statement=self.signer.sign(canonical_attestation_payload(unsigned)),
        )
        self.assertEqual(self.check(journal=old, statement=old_signed), Admission.UNCERTAIN)
        print("G23_SIGNED_REPLAY_RED=VALID_OLD_SIGNATURE_NOT_FRESHNESS_PROOF")

    def test_15_invalid_public_key_length_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", trusted_keys={ROOT: b"short"})

    def test_16_empty_signature_denies(self):
        self.deny("WITNESS_SIGNATURE_MISSING",
                  statement=replace(self.statement, signed_statement=b""))


if __name__ == "__main__":
    unittest.main()
