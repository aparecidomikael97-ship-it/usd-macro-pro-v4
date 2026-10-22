"""A146 synthetic only: replay, interruption, CAS, volatile-witness limits."""
import base64
import threading
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, CheckpointRejected, canonical_history_digest
from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint, checkpoint_payload
from aion_p0_a146_highwater_gate_lab import (
    HighWater, HighWaterRejected, SyntheticVolatileWitnessLAB, check_restart_gate,
)


class HighWaterGateLAB(unittest.TestCase):
    def setUp(self):
        self.ledger_id = "ledger-A"
        self.events1 = [{"seq": 1, "intent": "one"}]
        self.events2 = self.events1 + [{"seq": 2, "intent": "two"}]
        self.signer = Ed25519PrivateKey.generate()
        self.public = self.signer.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        self.pinned = {"witness-1": self.public}
        self.witness = SyntheticVolatileWitnessLAB()
        self.zero = HighWater(self.ledger_id, 0, canonical_history_digest([]))
        self.one = HighWater(self.ledger_id, 1, canonical_history_digest(self.events1))
        self.two = HighWater(self.ledger_id, 2, canonical_history_digest(self.events2))
        self.witness.publish(self.zero, expected_sequence=None)
        self.witness.publish(self.one, expected_sequence=0)

    def signed(self, anchor):
        cp = Checkpoint(anchor.ledger_id, anchor.sequence, anchor.history_digest)
        return SignedCheckpoint(cp, "witness-1", base64.b64encode(self.signer.sign(checkpoint_payload(cp))).decode("ascii"))

    def gate(self, *, anchor=None, events=None, reader=None, ledger_id=None, pinned=None):
        return check_restart_gate(
            ledger_id=self.ledger_id if ledger_id is None else ledger_id,
            events=self.events1 if events is None else events,
            envelope=self.signed(self.one if anchor is None else anchor),
            pinned_keys=self.pinned if pinned is None else pinned,
            read_highwater=self.witness.read if reader is None else reader,
        )

    def test_01_matching_authenticated_checkpoint(self):
        self.assertEqual(self.gate(), "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")

    def test_02_old_signed_checkpoint_after_highwater_advance(self):
        self.witness.publish(self.two, expected_sequence=1)
        with self.assertRaisesRegex(HighWaterRejected, "signed_checkpoint_rollback"):
            self.gate()

    def test_03_unwitnessed_local_advance_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "unwitnessed_local_advance"):
            self.gate(anchor=self.two, events=self.events2)

    def test_04_witness_offline_denied(self):
        self.witness.offline = True
        with self.assertRaisesRegex(HighWaterRejected, "witness_unavailable"):
            self.gate()

    def test_05_missing_reader_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "witness_reader_missing"):
            self.gate(reader=False)

    def test_06_unknown_ledger_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "no_highwater_enrollment"):
            self.gate(reader=lambda _: self.witness.read("unknown"))

    def test_07_wrong_highwater_ledger_denied(self):
        wrong = HighWater("ledger-B", 1, self.one.history_digest)
        with self.assertRaisesRegex(HighWaterRejected, "witness_ledger_mismatch"):
            self.gate(reader=lambda _: wrong)

    def test_08_same_sequence_wrong_digest_denied(self):
        wrong = HighWater(self.ledger_id, 1, "a" * 64)
        with self.assertRaisesRegex(HighWaterRejected, "highwater_digest_disagreement"):
            self.gate(reader=lambda _: wrong)

    def test_09_malformed_highwater_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "invalid_highwater_sequence"):
            self.gate(reader=lambda _: HighWater(self.ledger_id, True, self.one.history_digest))

    def test_10_unknown_pinned_signer_denied(self):
        with self.assertRaisesRegex(CheckpointRejected, "missing_trust_anchor"):
            self.gate(pinned={})

    def test_11_cas_rejects_wrong_expected_sequence(self):
        with self.assertRaisesRegex(HighWaterRejected, "cas_conflict"):
            self.witness.publish(self.two, expected_sequence=0)
        self.assertEqual(self.witness.read(self.ledger_id), self.one)

    def test_12_cas_rejects_sequence_gap(self):
        far = HighWater(self.ledger_id, 3, "f" * 64)
        with self.assertRaisesRegex(HighWaterRejected, "nonmonotonic_or_gap"):
            self.witness.publish(far, expected_sequence=1)

    def test_13_cas_rejects_same_sequence_other_digest(self):
        wrong = HighWater(self.ledger_id, 1, "f" * 64)
        with self.assertRaisesRegex(HighWaterRejected, "same_sequence_digest_conflict"):
            self.witness.publish(wrong, expected_sequence=1)

    def test_14_cas_rejects_rollback(self):
        with self.assertRaisesRegex(HighWaterRejected, "nonmonotonic_or_gap"):
            self.witness.publish(self.zero, expected_sequence=1)

    def test_15_cas_rejects_unapproved_rebootstrap(self):
        with self.assertRaisesRegex(HighWaterRejected, "genesis_denied"):
            SyntheticVolatileWitnessLAB().publish(self.one, expected_sequence=None)

    def test_16_read_exception_denied(self):
        def down(_):
            raise OSError("synthetic failure")
        with self.assertRaisesRegex(HighWaterRejected, "witness_read_failed"):
            self.gate(reader=down)

    def test_17_cas_idempotence(self):
        self.assertTrue(self.witness.publish(self.one, expected_sequence=1))
        self.assertEqual(self.witness.read(self.ledger_id), self.one)

    def test_18_concurrent_cas_only_one_writer_advances(self):
        outcomes = []
        def task(anchor):
            try:
                self.witness.publish(anchor, expected_sequence=1)
                outcomes.append("accepted")
            except HighWaterRejected:
                outcomes.append("rejected")
        t1 = threading.Thread(target=task, args=(self.two,))
        t2 = threading.Thread(target=task, args=(HighWater(self.ledger_id, 2, "d" * 64),))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(sorted(outcomes), ["accepted", "rejected"])

    def test_19_manual_simulated_reconciliation_after_uncertain_commit(self):
        with self.assertRaisesRegex(HighWaterRejected, "unwitnessed_local_advance"):
            self.gate(anchor=self.two, events=self.events2)
        # Test-only explicit update, not automatic retry or production reconciliation.
        self.witness.publish(self.two, expected_sequence=1)
        self.assertEqual(self.gate(anchor=self.two, events=self.events2),
                         "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")

    def test_20_negative_resetting_volatile_witness_can_accept_old_checkpoint(self):
        self.witness.publish(self.two, expected_sequence=1)
        reset = SyntheticVolatileWitnessLAB()
        reset.publish(self.zero, expected_sequence=None)
        reset.publish(self.one, expected_sequence=0)
        # Negative proof, NOT security success: both witness+db reverted.
        self.assertEqual(self.gate(reader=reset.read), "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
