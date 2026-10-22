"""Synthetic Ed25519 checkpoint attestation tests. LAB ONLY."""
import base64
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from aion_p0_a145_checkpoint_verifier_lab import Checkpoint, CheckpointRejected, canonical_history_digest
from aion_p0_a145_authenticated_checkpoint_lab import (
    SignedCheckpoint, checkpoint_payload, verify_signed_checkpoint,
)


class AuthenticatedCheckpointLab(unittest.TestCase):
    def setUp(self):
        self.events = [{"seq": 1, "intent": "a"}, {"seq": 2, "intent": "b"}]
        self.checkpoint = Checkpoint("ledger-A", 2, canonical_history_digest(self.events))
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trust = {"witness-1": self.public}
        self.envelope = self.sign(self.checkpoint)

    def sign(self, checkpoint, key_id="witness-1", signer=None):
        signer = signer or self.private
        sig = signer.sign(checkpoint_payload(checkpoint))
        return SignedCheckpoint(checkpoint, key_id, base64.b64encode(sig).decode("ascii"))

    def verify(self, envelope=None, events=None, trust=None):
        return verify_signed_checkpoint(
            ledger_id="ledger-A",
            events=self.events if events is None else events,
            envelope=self.envelope if envelope is None else envelope,
            pinned_keys=self.trust if trust is None else trust,
        )

    def test_valid_signed_checkpoint(self):
        self.assertTrue(self.verify())

    def test_missing_anchor_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(trust={})

    def test_unknown_key_id_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=self.sign(self.checkpoint, key_id="unregistered"))

    def test_wrong_signer_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=self.sign(self.checkpoint, signer=Ed25519PrivateKey.generate()))

    def test_signature_corruption_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=SignedCheckpoint(self.checkpoint, "witness-1", base64.b64encode(b"X"*64).decode("ascii")))

    def test_signature_encoding_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=SignedCheckpoint(self.checkpoint, "witness-1", "@@invalid@@"))

    def test_valid_signature_for_stale_history_denied(self):
        with self.assertRaises(CheckpointRejected):
            self.verify(events=self.events[:1])

    def test_other_ledger_signed_checkpoint_denied(self):
        other = Checkpoint("ledger-B", 2, self.checkpoint.history_digest)
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=self.sign(other))

    def test_tampered_checkpoint_digest_denied(self):
        changed = Checkpoint("ledger-A", 2, "0"*64)
        with self.assertRaises(CheckpointRejected):
            self.verify(envelope=SignedCheckpoint(changed, self.envelope.key_id, self.envelope.signature_b64))

    def test_boolean_sequence_denied(self):
        with self.assertRaises(CheckpointRejected):
            checkpoint_payload(Checkpoint("ledger-A", True, self.checkpoint.history_digest))


if __name__ == "__main__":
    unittest.main()
