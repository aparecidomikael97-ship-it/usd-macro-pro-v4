"""AION P0 LAB: explicit restore must recheck target runtime before historical readback.

Every runtime GET, history GET and save is mocked. No GitHub API calls, Worker
commands or external effects occur in the tests.
"""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from atlasquant_aion_memory import RuntimeConfig, checkpoint_integrity_report
from atlasquant_aion_recovery import restore_checkpoint_revision
from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate


class RecoveryLiveDestinationBindingLab(unittest.TestCase):
    def setUp(self):
        self.config = RuntimeConfig(
            token="synthetic-unused", repo="example/repo",
            branch="atlasquant-runtime", path="dados/aion/checkpoint_master.json",
        )
        self.current = _current()
        self.candidate = _candidate()
        self.expected_source = (
            "GitHub:" + self.config.branch + ":" + self.config.path
        )

    def live(self):
        return {
            "status": "CONFIRMED",
            "sha": self.current["sha"],
            "checkpoint": deepcopy(self.current["checkpoint"]),
            "source": self.expected_source,
        }

    def call(self, live):
        with patch(
            "atlasquant_aion_recovery.load_runtime_checkpoint",
            return_value=live,
        ) as runtime_get, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=deepcopy(self.candidate),
        ) as history_get, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
            return_value={"status": "CONFLICT", "saved": False, "verified": False},
        ) as save:
            result = restore_checkpoint_revision(
                deepcopy(self.candidate), deepcopy(self.current), self.config,
                approved=True,
            )
        return result, runtime_get, history_get, save

    def assert_blocked_without_history(self, live, *, expect_live_read=True):
        result, runtime_get, history_get, save = self.call(live)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIs(result["saved"], False)
        self.assertIs(result["verified"], False)
        self.assertIs(result.get("automatic_retry_allowed"), False)
        if expect_live_read:
            runtime_get.assert_called_once_with(self.config, timeout=12.0)
        else:
            runtime_get.assert_not_called()
        history_get.assert_not_called()
        save.assert_not_called()

    def test_01_live_same_scope_sha_content_permits_later_review(self):
        result, live, history, save = self.call(self.live())
        live.assert_called_once_with(self.config, timeout=12.0)
        history.assert_called_once_with(
            self.candidate["revision"], self.config, timeout=12.0
        )
        save.assert_called_once()
        self.assertEqual(result["status"], "CONFLICT")
        self.assertIs(result["restore_confirmed"], False)

    def test_02_live_sha_changed_is_blocked(self):
        live = self.live()
        live["sha"] = "c" * 40
        self.assert_blocked_without_history(live)

    def test_03_live_checkpoint_content_changed_with_same_sha_is_blocked(self):
        live = self.live()
        live["checkpoint"]["aion"]["priority"] = "different contents"
        self.assert_blocked_without_history(live)

    def test_04_live_status_unknown_is_blocked(self):
        live = self.live()
        live["status"] = "UNKNOWN"
        self.assert_blocked_without_history(live)

    def test_05_live_source_other_branch_is_blocked(self):
        live = self.live()
        live["source"] = "GitHub:other-branch:" + self.config.path
        self.assert_blocked_without_history(live)

    def test_06_live_source_other_path_is_blocked(self):
        live = self.live()
        live["source"] = "GitHub:" + self.config.branch + ":other.json"
        self.assert_blocked_without_history(live)

    def test_07_live_source_missing_is_blocked(self):
        live = self.live()
        live.pop("source")
        self.assert_blocked_without_history(live)

    def test_08_live_checkpoint_absent_is_blocked(self):
        live = self.live()
        live.pop("checkpoint")
        self.assert_blocked_without_history(live)

    def test_09_live_checkpoint_non_mapping_is_blocked(self):
        live = self.live()
        live["checkpoint"] = ["not-json-object"]
        self.assert_blocked_without_history(live)

    def test_10_live_not_found_is_blocked(self):
        live = self.live()
        live["status"] = "NOT_FOUND"
        self.assert_blocked_without_history(live)

    def test_11_live_read_error_is_blocked(self):
        live = self.live()
        live["status"] = "ERROR"
        self.assert_blocked_without_history(live)

    def test_12_live_result_not_mapping_is_blocked(self):
        self.assert_blocked_without_history("not-a-runtime")

    def test_13_caller_source_foreign_branch_is_blocked(self):
        self.current["source"] = "GitHub:foreign-branch:" + self.config.path
        self.assert_blocked_without_history(self.live(), expect_live_read=False)

    def test_14_caller_source_foreign_path_is_blocked(self):
        self.current["source"] = "GitHub:" + self.config.branch + ":other.json"
        self.assert_blocked_without_history(self.live(), expect_live_read=False)

    def test_15_no_explicit_approval_must_not_read_live(self):
        with patch("atlasquant_aion_recovery.load_runtime_checkpoint") as runtime, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision"
        ) as history, patch("atlasquant_aion_recovery.save_runtime_checkpoint") as save:
            result = restore_checkpoint_revision(
                self.candidate, self.current, self.config, approved=False
            )
        self.assertEqual(result["status"], "BLOCKED")
        runtime.assert_not_called()
        history.assert_not_called()
        save.assert_not_called()

    def test_16_legitimate_mismatch_repair_still_proceeds_to_review(self):
        self.current["checkpoint"]["studio"]["digest"] = "tampered"
        self.current["integrity"] = checkpoint_integrity_report(
            self.current["checkpoint"]
        )
        result, runtime, history, save = self.call(self.live())
        self.assertEqual(result["status"], "CONFLICT")
        runtime.assert_called_once()
        history.assert_called_once()
        save.assert_called_once()

    def test_17_valid_sha_unchanged_but_untrusted_caller_source_blocked(self):
        self.current["source"] = "GitHub:other-branch:" + self.config.path
        live = self.live()
        self.assertEqual(live["sha"], self.current["sha"])
        self.assertEqual(live["checkpoint"], self.current["checkpoint"])
        self.assert_blocked_without_history(live, expect_live_read=False)


    def test_18_exception_during_live_readback_is_blocked_without_retry(self):
        with patch(
            "atlasquant_aion_recovery.load_runtime_checkpoint",
            side_effect=TimeoutError("synthetic timeout"),
        ) as runtime_get, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
        ) as history_get, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
        ) as save:
            result = restore_checkpoint_revision(
                self.candidate, self.current, self.config, approved=True
            )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIs(result["saved"], False)
        self.assertIs(result.get("automatic_retry_allowed"), False)
        runtime_get.assert_called_once()
        history_get.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
