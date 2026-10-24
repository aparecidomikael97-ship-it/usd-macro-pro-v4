"""G20 adversarial contract tests: ALL witness keys are synthetic test doubles."""
import unittest

from g20_independent_witness_recovery_contract_lab import (
    Admission, RecoveryDenied, WitnessAttestation, canonical_hash,
    first_attempt_admission, recovery_admission,
)

ROOT = "lab-pinned-independent-root"
KEY = "tenant:invoice:semantic-42"
LOCAL = {"semantic_key": KEY, "sequence": 7, "phase": "UNCERTAIN",
         "effect": "UNKNOWN", "request_id": "transport-1"}


class FakeWitness:
    def __init__(self, record=None, valid=True, raises=False):
        self.record = record or WitnessAttestation(
            KEY, 7, "UNCERTAIN", canonical_hash(LOCAL), ROOT, b"fake-signature")
        self.valid = valid
        self.raises = raises

    def attest_latest(self, semantic_key):
        if self.raises:
            raise TimeoutError("synthetic timeout")
        return self.record

    def verify(self, statement, pinned_root_id):
        return self.valid


def changed(**updates):
    source = dict(LOCAL)
    source.update(updates)
    return source


def record(**updates):
    data = dict(semantic_key=KEY, sequence=7, phase="UNCERTAIN",
                journal_digest=canonical_hash(LOCAL),
                trust_root_id=ROOT, signed_statement=b"fake-signature")
    data.update(updates)
    return WitnessAttestation(**data)


class G20WitnessContractTests(unittest.TestCase):
    def run_gate(self, *, local=LOCAL, witness=None, root=ROOT, key=KEY):
        return recovery_admission(semantic_key=key, local_journal=local,
                                  witness=FakeWitness() if witness is None else witness,
                                  pinned_root_id=root)

    def deny(self, expected, **kwargs):
        with self.assertRaisesRegex(RecoveryDenied, expected):
            self.run_gate(**kwargs)

    def test_01_matching_synthetic_witness_never_allows_resend(self):
        self.assertEqual(self.run_gate(), Admission.UNCERTAIN)

    def test_02_missing_root_denies(self):
        self.deny("INDEPENDENT_PINNED_ROOT_MISSING", root="")

    def test_03_mismatched_root_denies(self):
        self.deny("WITNESS_ROOT_MISMATCH", root="other-root")

    def test_04_unavailable_witness_denies(self):
        self.deny("INDEPENDENT_WITNESS_UNAVAILABLE", witness=FakeWitness(raises=True))

    def test_05_forged_signature_denies(self):
        self.deny("WITNESS_SIGNATURE_UNTRUSTED", witness=FakeWitness(valid=False))

    def test_06_missing_signature_denies(self):
        self.deny("WITNESS_SIGNATURE_MISSING",
                  witness=FakeWitness(record(signed_statement=b"")))

    def test_07_rollback_local_sequence_denies(self):
        self.deny("LOCAL_SEQUENCE_MISMATCH", local=changed(sequence=6))

    def test_08_replaced_local_payload_denies(self):
        self.deny("LOCAL_DIGEST_MISMATCH", local=changed(effect="CLAIMED_SUCCESS"))

    def test_09_deleted_journal_denies(self):
        self.deny("LOCAL_JOURNAL_MISSING", local=None)

    def test_10_wrong_semantic_key_denies(self):
        self.deny("LOCAL_SEMANTIC_MISMATCH",
                  local=changed(semantic_key="tenant:invoice:other"))

    def test_11_stale_phase_denies(self):
        self.deny("LOCAL_PHASE_MISMATCH", local=changed(phase="RESERVED"))

    def test_12_witness_for_other_intent_denies(self):
        self.deny("WITNESS_SEMANTIC_MISMATCH",
                  witness=FakeWitness(record(semantic_key="tenant:other")))

    def test_13_invalid_sequence_type_denies(self):
        self.deny("WITNESS_SEQUENCE_INVALID",
                  witness=FakeWitness(record(sequence=True)))

    def test_14_bad_witness_digest_denies(self):
        self.deny("LOCAL_DIGEST_MISMATCH",
                  witness=FakeWitness(record(journal_digest="0" * 64)))

    def test_15_even_matching_record_does_not_admit_first_send(self):
        with self.assertRaisesRegex(RecoveryDenied, "ATOMIC_EXTERNAL_RESERVATION_UNIMPLEMENTED"):
            first_attempt_admission(witness=FakeWitness(), pinned_root_id=ROOT)

    def test_16_no_first_send_without_witness(self):
        with self.assertRaisesRegex(RecoveryDenied, "EXTERNAL_RESERVATION_MISSING"):
            first_attempt_admission(witness=None, pinned_root_id=ROOT)


if __name__ == "__main__":
    unittest.main()
