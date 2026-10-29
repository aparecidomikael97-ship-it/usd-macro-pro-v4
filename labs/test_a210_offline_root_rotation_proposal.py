"""A210 LAB: root rotation proposal tests, no key activation or providers."""
from dataclasses import FrozenInstanceError
import unittest

from labs.a210_offline_root_rotation_proposal import (
    SCHEMA, preflight_rotation_proposal,
)


class A210OfflineRotationIsNeverApprovalTests(unittest.TestCase):
    def setUp(self):
        self.owner = "synthetic-owner"
        self.root = "a" * 64
        self.checkpoint = "b" * 64
        self.proposal = {
            "schema": SCHEMA,
            "owner_id": self.owner,
            "ceremony_id": "synthetic-ceremony-1",
            "previous_root_fingerprint": self.root,
            "proposed_root_fingerprint": "d" * 64,
            "parent_checkpoint_hash": self.checkpoint,
            "next_checkpoint_sequence": 21,
            "nonce_hex": "f" * 64,
            "owner_intent_digest": "c" * 64,
            "witness_ref": "synthetic-external-witness",
            "requested_at": "2026-10-28T11:00:00Z",
        }

    def assess(self, proposal=None, *, owner=None, root=None,
               checkpoint=None, sequence=20, seen=None,
               anchor="2026-10-28T10:00:00Z",
               observed="2026-10-28T12:00:00Z"):
        return preflight_rotation_proposal(
            self.proposal if proposal is None else proposal,
            expected_owner=self.owner if owner is None else owner,
            current_root_fingerprint=self.root if root is None else root,
            current_checkpoint_hash=self.checkpoint if checkpoint is None else checkpoint,
            current_checkpoint_sequence=sequence,
            seen_nonces=[] if seen is None else seen,
            previous_anchor_at=anchor,
            observed_at=observed,
        )

    def test_01_well_formed_proposal_does_not_activate_root(self):
        result = self.assess()
        self.assertTrue(result.structurally_valid)
        self.assertFalse(result.may_rotate)
        self.assertEqual(result.code, "PROPOSAL_SHAPE_OK_EXTERNAL_OWNER_APPROVAL_MISSING")
        self.assertEqual(len(result.proposal_digest), 64)

    def test_02_canonical_commitment_independent_of_map_order(self):
        reordered = dict(reversed(list(self.proposal.items())))
        self.assertEqual(self.assess().proposal_digest, self.assess(reordered).proposal_digest)

    def test_03_changed_new_root_changes_commitment_but_still_no_authority(self):
        changed = {**self.proposal, "proposed_root_fingerprint": "e" * 64}
        original = self.assess()
        modified = self.assess(changed)
        self.assertTrue(modified.structurally_valid)
        self.assertNotEqual(original.proposal_digest, modified.proposal_digest)
        self.assertFalse(modified.may_rotate)

    def test_04_self_claimed_owner_approval_is_rejected(self):
        result = self.assess({**self.proposal, "owner_approved": True})
        self.assertEqual(result.code, "ROTATION_ENVELOPE_NOT_EXACT")
        self.assertFalse(result.may_rotate)

    def test_05_owner_mismatch_is_rejected(self):
        result = self.assess({**self.proposal, "owner_id": "different-owner"})
        self.assertEqual(result.code, "ROTATION_OWNER_MISMATCH")

    def test_06_missing_expected_owner_is_rejected(self):
        self.assertEqual(self.assess(owner="").code, "UNTRUSTED_OWNER_EXPECTATION")

    def test_07_old_root_mismatch_is_rejected(self):
        changed = {**self.proposal, "previous_root_fingerprint": "e" * 64}
        self.assertEqual(self.assess(changed).code, "OLD_ROOT_PIN_MISMATCH")

    def test_08_same_root_rotation_is_rejected(self):
        changed = {**self.proposal, "proposed_root_fingerprint": self.root}
        self.assertEqual(self.assess(changed).code, "ROTATION_REUSES_SAME_ROOT")

    def test_09_invalid_new_root_and_expected_pin_rejected(self):
        bad = {**self.proposal, "proposed_root_fingerprint": "BAD"}
        self.assertEqual(self.assess(bad).code, "INVALID_PROPOSED_ROOT")
        self.assertEqual(self.assess(root="").code, "UNTRUSTED_CURRENT_ROOT")

    def test_10_parent_checkpoint_mismatch_or_missing_is_rejected(self):
        bad = {**self.proposal, "parent_checkpoint_hash": "e" * 64}
        self.assertEqual(self.assess(bad).code, "PARENT_CHECKPOINT_MISMATCH")
        self.assertEqual(self.assess(checkpoint="").code, "UNTRUSTED_PARENT_CHECKPOINT")

    def test_11_sequence_replay_or_skip_rejected(self):
        for seq in (19, 20, 22, 100):
            with self.subTest(seq=seq):
                bad = {**self.proposal, "next_checkpoint_sequence": seq}
                self.assertEqual(self.assess(bad).code, "ROTATION_SEQUENCE_REPLAY_OR_SKIP")

    def test_12_invalid_sequence_and_untrusted_floor_rejected(self):
        for value in (True, False, -1, "21"):
            with self.subTest(value=value):
                bad = {**self.proposal, "next_checkpoint_sequence": value}
                self.assertEqual(self.assess(bad).code, "INVALID_NEXT_SEQUENCE")
        self.assertEqual(self.assess(sequence=True).code, "UNTRUSTED_SEQUENCE_ANCHOR")

    def test_13_reused_nonce_is_rejected(self):
        self.assertEqual(
            self.assess(seen=[self.proposal["nonce_hex"]]).code,
            "CEREMONY_NONCE_REPLAY",
        )

    def test_14_bad_nonce_or_history_is_rejected(self):
        bad = {**self.proposal, "nonce_hex": "not-hex"}
        self.assertEqual(self.assess(bad).code, "INVALID_CEREMONY_NONCE")
        self.assertEqual(self.assess(seen=[True]).code, "UNTRUSTED_NONCE_HISTORY")

    def test_15_invalid_owner_intent_digest_rejected(self):
        bad = {**self.proposal, "owner_intent_digest": "WRONG"}
        self.assertEqual(self.assess(bad).code, "INVALID_OWNER_INTENT_DIGEST")

    def test_16_missing_witness_or_ceremony_rejected(self):
        for field in ("witness_ref", "ceremony_id"):
            with self.subTest(field=field):
                bad = {**self.proposal, field: ""}
                self.assertEqual(self.assess(bad).code, "INVALID_CEREMONY_OR_WITNESS_REF")

    def test_17_future_predated_or_naive_ceremony_time_rejected(self):
        for stamp in ("2026-10-28T13:00:00Z",
                      "2026-10-28T09:00:00Z",
                      "2026-10-28T11:00:00"):
            with self.subTest(stamp=stamp):
                bad = {**self.proposal, "requested_at": stamp}
                self.assertFalse(self.assess(bad).structurally_valid)

    def test_18_missing_required_field_rejected(self):
        missing = {k: v for k, v in self.proposal.items() if k != "owner_intent_digest"}
        self.assertEqual(self.assess(missing).code, "ROTATION_ENVELOPE_NOT_EXACT")

    def test_19_output_is_immutable_and_cannot_be_elevated(self):
        result = self.assess()
        with self.assertRaises(FrozenInstanceError):
            result.may_rotate = True
        self.assertFalse(result.may_rotate)


if __name__ == "__main__":
    unittest.main()
