"""A145 isolated comparator contract tests (no trusted witness integration)."""
import unittest
from aion_p0_a145_checkpoint_verifier_lab import (
    Checkpoint, CheckpointRejected, canonical_history_digest, verify_checkpoint,
)


class CheckpointComparatorLab(unittest.TestCase):
    def setUp(self):
        self.events = [{"seq": 1, "intent": "a"}, {"seq": 2, "intent": "b"}]
        self.witness = Checkpoint("ledger-A", 2, canonical_history_digest(self.events))

    def test_matching_checkpoint(self):
        self.assertTrue(verify_checkpoint(ledger_id="ledger-A", events=self.events, witness=self.witness))

    def test_missing_witness_denied(self):
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=self.events, witness=None)

    def test_restored_old_history_denied(self):
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=self.events[:1], witness=self.witness)

    def test_changed_history_denied(self):
        altered = [dict(e) for e in self.events]
        altered[1]["intent"] = "forged"
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=altered, witness=self.witness)

    def test_other_ledger_denied(self):
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-B", events=self.events, witness=self.witness)

    def test_sequence_gap_denied(self):
        altered = [{"seq": 1}, {"seq": 3}]
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=altered, witness=self.witness)


    def test_malformed_witness_identity_denied(self):
        bad = Checkpoint(None, 2, self.witness.history_digest)
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=self.events, witness=bad)

    def test_invalid_witness_digest_denied(self):
        bad = Checkpoint("ledger-A", 2, "z" * 64)
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=self.events, witness=bad)

    def test_unserializable_history_denied(self):
        altered = [{"seq": 1, "intent": object()}, {"seq": 2, "intent": "b"}]
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=altered, witness=self.witness)

    def test_boolean_sequence_denied(self):
        bad = Checkpoint("ledger-A", True, self.witness.history_digest)
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=self.events, witness=bad)

    def test_extra_event_field_denied(self):
        altered = [dict(e) for e in self.events]
        altered[0]["untrusted"] = "payload"
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=altered, witness=self.witness)

    def test_empty_intent_denied(self):
        altered = [dict(e) for e in self.events]
        altered[0]["intent"] = ""
        with self.assertRaises(CheckpointRejected):
            verify_checkpoint(ledger_id="ledger-A", events=altered, witness=self.witness)

if __name__ == "__main__":
    unittest.main()
