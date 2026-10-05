from __future__ import annotations

from copy import deepcopy
import unittest

from atlasquant_aion_checkpoint_master import (
    MAX_EVENT_ID_CHARS,
    CheckpointConflict,
    CheckpointIntegrityError,
    CheckpointMasterError,
    append_checkpoint_patch,
    checkpoint_master_digest,
    future_signature_hook,
    new_checkpoint_master,
    reconstruct_checkpoint,
)


class Weird:
    pass


class AionV26CheckpointIdentityRedTeamTests(unittest.TestCase):
    def master(self):
        return new_checkpoint_master(
            {"task": {"state": "PLANNED", "value": 0}},
            created_at="2026-10-04T00:00:00+00:00",
        )

    def test_distinct_canonical_ids_with_same_payload_remain_distinct(self):
        master = self.master()
        one = append_checkpoint_patch(
            master, event_id="EV-A", patch={"value": 1}, expected_revision=0
        )
        two = append_checkpoint_patch(
            one, event_id="EV-B", patch={"value": 1}, expected_revision=1
        )
        self.assertEqual(reconstruct_checkpoint(two)["revision"], 2)
        self.assertEqual(len(two["journal"]), 2)
        self.assertEqual(two["journal"][0]["event_id"], "EV-A")
        self.assertEqual(two["journal"][1]["event_id"], "EV-B")

    def test_overlong_event_id_is_rejected_instead_of_truncated(self):
        prefix = "X" * MAX_EVENT_ID_CHARS
        id_a = prefix + "A"
        id_b = prefix + "B"
        self.assertNotEqual(id_a, id_b)
        with self.assertRaisesRegex(CheckpointMasterError, "event_id length invalid"):
            append_checkpoint_patch(
                self.master(), event_id=id_a, patch={"value": 1}, expected_revision=0
            )
        with self.assertRaisesRegex(CheckpointMasterError, "event_id length invalid"):
            append_checkpoint_patch(
                self.master(), event_id=id_b, patch={"value": 1}, expected_revision=0
            )

    def test_whitespace_normalization_collision_is_rejected(self):
        self.assertNotEqual("a  b", "a b")
        with self.assertRaisesRegex(CheckpointMasterError, "event_id must be canonical"):
            append_checkpoint_patch(
                self.master(), event_id="a  b", patch={"value": 1}, expected_revision=0
            )
        accepted = append_checkpoint_patch(
            self.master(), event_id="a b", patch={"value": 1}, expected_revision=0
        )
        self.assertEqual(accepted["journal"][0]["event_id"], "a b")

    def test_nul_removal_collision_is_rejected(self):
        self.assertNotEqual("ab\x00c", "abc")
        with self.assertRaisesRegex(CheckpointMasterError, "event_id must be canonical"):
            append_checkpoint_patch(
                self.master(), event_id="ab\x00c", patch={"value": 1}, expected_revision=0
            )
        accepted = append_checkpoint_patch(
            self.master(), event_id="abc", patch={"value": 1}, expected_revision=0
        )
        self.assertEqual(accepted["journal"][0]["event_id"], "abc")

    def test_non_string_event_identity_is_rejected(self):
        for value in (1, True, b"EV", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(CheckpointMasterError, "event_id must be a string"):
                    append_checkpoint_patch(
                        self.master(), event_id=value, patch={"value": 1}, expected_revision=0
                    )

    def test_exact_retry_with_original_revision_remains_idempotent(self):
        master = self.master()
        one = append_checkpoint_patch(
            master, event_id="EV-RETRY", patch={"value": 1}, expected_revision=0
        )
        replay = append_checkpoint_patch(
            one, event_id="EV-RETRY", patch={"value": 1}, expected_revision=0
        )
        self.assertEqual(replay, one)
        self.assertEqual(reconstruct_checkpoint(replay)["revision"], 1)

    def test_same_id_different_payload_still_conflicts(self):
        one = append_checkpoint_patch(
            self.master(), event_id="EV-ONE", patch={"value": 1}, expected_revision=0
        )
        with self.assertRaisesRegex(CheckpointConflict, "IDEMPOTENCY_CONFLICT"):
            append_checkpoint_patch(
                one, event_id="EV-ONE", patch={"value": 2}, expected_revision=1
            )

    def test_tampered_noncanonical_stored_identity_is_detected(self):
        one = append_checkpoint_patch(
            self.master(), event_id="EV-ONE", patch={"value": 1}, expected_revision=0
        )
        tampered = deepcopy(one)
        tampered["journal"][0]["event_id"] = "EV-ONE  "
        with self.assertRaisesRegex(CheckpointIntegrityError, "event_id invalid"):
            reconstruct_checkpoint(tampered)

    def test_structural_public_apis_reject_nonserializable_state(self):
        with self.assertRaises(CheckpointMasterError):
            new_checkpoint_master({"x": Weird()})
        master = self.master()
        with self.assertRaises(CheckpointMasterError):
            append_checkpoint_patch(
                master, event_id="EV-WEIRD", patch={"x": Weird()}, expected_revision=0
            )
        tampered = deepcopy(master)
        tampered["base_snapshot"]["x"] = Weird()
        with self.assertRaises(CheckpointMasterError):
            reconstruct_checkpoint(tampered)
        with self.assertRaises(CheckpointMasterError):
            future_signature_hook(tampered)
        # Digest-only helper remains deterministic metadata materialization; it is
        # not an acceptance/validation surface for checkpoint state.
        self.assertTrue(checkpoint_master_digest(tampered).startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
