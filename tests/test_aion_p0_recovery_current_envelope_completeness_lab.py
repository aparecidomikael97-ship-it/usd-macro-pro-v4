"""LAB adversarial regressions: a SHA alone cannot stand in for a runtime checkpoint.

No real GitHub calls, no persistence and no Worker activity. This suite proves
only local fail-closed classification of the caller-supplied current envelope.
"""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from atlasquant_aion_recovery import recovery_preflight, restore_checkpoint_revision
from atlasquant_aion_memory import RuntimeConfig, checkpoint_integrity_report
from test_atlasquant_aion_recovery_traceability_gate import _candidate, _current


class RecoveryCurrentEnvelopeCompletenessLab(unittest.TestCase):
    def setUp(self):
        self.current = _current()
        self.candidate = _candidate()

    def assert_invalid_current_blocks(self, checkpoint_marker, *, missing=False):
        current = deepcopy(self.current)
        if missing:
            current.pop("checkpoint", None)
        else:
            current["checkpoint"] = checkpoint_marker
        result = recovery_preflight(current, deepcopy(self.candidate))
        self.assertIs(result.get("allowed"), False, result)
        self.assertIs(result.get("executes_action"), False, result)
        self.assertIn("current", result.get("reason", "").lower())

    def test_01_original_valid_full_checkpoint_still_eligible(self):
        result = recovery_preflight(self.current, self.candidate)
        self.assertIs(result["allowed"], True)
        self.assertEqual(result["expected_sha"], "b" * 40)
        self.assertIs(result["executes_action"], False)

    def test_02_missing_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks(None, missing=True)

    def test_03_null_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks(None)

    def test_04_empty_mapping_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks({})

    def test_05_list_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks([])

    def test_06_string_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks("not-a-checkpoint")

    def test_07_int_current_checkpoint_is_denied(self):
        self.assert_invalid_current_blocks(42)

    def test_08_real_mismatch_repair_review_path_remains(self):
        current = deepcopy(self.current)
        current["checkpoint"]["studio"]["digest"] = "tampered"
        current["integrity"] = checkpoint_integrity_report(current["checkpoint"])
        result = recovery_preflight(current, self.candidate)
        self.assertIs(result["allowed"], True)
        self.assertEqual(result["candidate_integrity"], "CONFIRMED")

    def test_09_missing_checkpoint_cannot_call_historical_readback(self):
        current = deepcopy(self.current)
        current.pop("checkpoint")
        cfg = RuntimeConfig(token="unused", repo="example/repo", branch="atlasquant-runtime")
        with patch("atlasquant_aion_recovery.load_checkpoint_revision") as read, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint"
        ) as write:
            result = restore_checkpoint_revision(
                deepcopy(self.candidate), current, cfg, approved=True
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["saved"], False)
        read.assert_not_called()
        write.assert_not_called()

    def test_10_empty_checkpoint_cannot_call_historical_readback(self):
        current = deepcopy(self.current)
        current["checkpoint"] = {}
        cfg = RuntimeConfig(token="unused", repo="example/repo", branch="atlasquant-runtime")
        with patch("atlasquant_aion_recovery.load_checkpoint_revision") as read, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint"
        ) as write:
            result = restore_checkpoint_revision(
                deepcopy(self.candidate), current, cfg, approved=True
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["verified"], False)
        read.assert_not_called()
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
