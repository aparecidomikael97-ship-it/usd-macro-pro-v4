"""A146 LAB: two Ed25519 keys, highwater envelope tamper, replay limitations."""
import base64
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, canonical_history_digest
from aion_p0_a145_authenticated_checkpoint_lab import SignedCheckpoint, checkpoint_payload
from aion_p0_a146_highwater_gate_lab import HighWater, HighWaterRejected
from aion_p0_a146_signed_highwater_lab import (
    SignedHighWater, canonical_highwater_bytes,
    check_restart_with_signed_highwater, verify_signed_highwater,
)


def pub(private):
    return private.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                              format=serialization.PublicFormat.Raw)


class SignedHighWaterLAB(unittest.TestCase):
    def setUp(self):
        self.cp_signer = Ed25519PrivateKey.generate()
        self.floor_signer = Ed25519PrivateKey.generate()
        self.checkpoint_trust = {"checkpoint-key": pub(self.cp_signer)}
        self.floor_trust = {"floor-key": pub(self.floor_signer)}
        self.events1 = [{"seq": 1, "intent": "first"}]
        self.events2 = self.events1 + [{"seq": 2, "intent": "second"}]
        self.cp1 = self.make_cp(self.events1)
        self.cp2 = self.make_cp(self.events2)
        self.hw1 = self.make_floor(self.events1)
        self.hw2 = self.make_floor(self.events2)

    def make_cp(self, events):
        checkpoint = Checkpoint("ledger-A", len(events), canonical_history_digest(events))
        return SignedCheckpoint(checkpoint, "checkpoint-key",
                                base64.b64encode(self.cp_signer.sign(checkpoint_payload(checkpoint))).decode("ascii"))

    def make_floor(self, events, signer=None):
        floor = HighWater("ledger-A", len(events), canonical_history_digest(events))
        signer = signer or self.floor_signer
        return SignedHighWater(floor, "floor-key",
                               base64.b64encode(signer.sign(canonical_highwater_bytes(floor))).decode("ascii"))

    def gate(self, cp=None, floor=None, events=None, floor_keys=None, checkpoint_keys=None):
        return check_restart_with_signed_highwater(
            ledger_id="ledger-A",
            events=self.events1 if events is None else events,
            envelope=self.cp1 if cp is None else cp,
            checkpoint_pinned_keys=self.checkpoint_trust if checkpoint_keys is None else checkpoint_keys,
            highwater_pinned_keys=self.floor_trust if floor_keys is None else floor_keys,
            read_signed_highwater=lambda _: self.hw1 if floor is None else floor,
        )

    def test_01_distinct_keys_matching_attestations(self):
        self.assertEqual(self.gate(), "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")

    def test_02_old_checkpoint_after_new_floor_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "signed_checkpoint_rollback"):
            self.gate(floor=self.hw2)

    def test_03_new_checkpoint_before_floor_ack_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "unwitnessed_local_advance"):
            self.gate(cp=self.cp2, events=self.events2)

    def test_04_wrong_highwater_signer_denied(self):
        forged = self.make_floor(self.events1, signer=Ed25519PrivateKey.generate())
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            self.gate(floor=forged)

    def test_05_corrupted_highwater_signature_denied(self):
        forged = SignedHighWater(self.hw1.anchor, "floor-key", base64.b64encode(b"A"*64).decode("ascii"))
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            self.gate(floor=forged)

    def test_06_missing_highwater_trust_anchor_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "missing_highwater_trust_anchor"):
            self.gate(floor_keys={})

    def test_07_same_key_for_both_domains_denied(self):
        floor = self.make_floor(self.events1, signer=self.cp_signer)
        with self.assertRaisesRegex(HighWaterRejected, "same_witness_and_checkpoint_key"):
            self.gate(floor=floor, floor_keys={"floor-key": pub(self.cp_signer)})

    def test_08_highwater_envelope_field_tamper_denied(self):
        mutated = SignedHighWater(HighWater("ledger-A", 1, "0"*64), "floor-key", self.hw1.signature_b64)
        with self.assertRaisesRegex(HighWaterRejected, "highwater_signature_mismatch"):
            self.gate(floor=mutated)

    def test_09_unknown_highwater_signer_denied(self):
        forged = SignedHighWater(self.hw1.anchor, "untrusted", self.hw1.signature_b64)
        with self.assertRaisesRegex(HighWaterRejected, "unknown_highwater_signer"):
            self.gate(floor=forged)

    def test_10_missing_reader_denied(self):
        with self.assertRaisesRegex(HighWaterRejected, "highwater_reader_missing"):
            check_restart_with_signed_highwater(ledger_id="ledger-A", events=self.events1,
                envelope=self.cp1, checkpoint_pinned_keys=self.checkpoint_trust,
                highwater_pinned_keys=self.floor_trust, read_signed_highwater=None)

    def test_11_unknown_checkpoint_key_denied(self):
        from aion_p0_a145_checkpoint_verifier_lab import CheckpointRejected
        with self.assertRaises(CheckpointRejected):
            self.gate(checkpoint_keys={})

    def test_12_negative_both_old_signed_attestations_still_pass(self):
        # NEGATIVE PROOF. Independent non-rollbackable freshness is still absent.
        self.assertEqual(self.gate(cp=self.cp1, floor=self.hw1, events=self.events1),
                         "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")

    def test_13_new_healthy_matching_pair(self):
        self.assertEqual(self.gate(cp=self.cp2, floor=self.hw2, events=self.events2),
                         "LAB_READ_ONLY_CONSISTENT_NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
