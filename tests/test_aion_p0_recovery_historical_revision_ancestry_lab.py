"""RED-first LAB: a historical Git commit must belong to authorized runtime branch.

All network endpoints and persistence are mocked: this suite never restores a
real GitHub checkpoint, invokes a provider or starts a Worker.
"""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import RuntimeConfig
from atlasquant_aion_recovery import restore_checkpoint_revision
from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate


class HistoricalRevisionAncestryFenceLAB(unittest.TestCase):
    def setUp(self):
        self.cfg = RuntimeConfig(
            token="unused-synthetic", repo="example/repo",
            branch="atlasquant-runtime", path="dados/aion/checkpoint_master.json",
        )
        self.current = _current()
        self.candidate = _candidate()
        self.rev = self.candidate["revision"]

    def compare(self, *, status="ahead", base=None, merge_base=None, head=None):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": status,
            "base_commit": {"sha": base or self.rev},
            "merge_base_commit": {"sha": merge_base or self.rev},
            "head_commit": {"sha": head or "c" * 40},
        }
        return response

    def call(self, compare_response=None, *, compare_error=None):
        live = {
            **deepcopy(self.current),
            "source": "GitHub:" + self.cfg.branch + ":" + self.cfg.path,
        }
        branch_response = MagicMock()
        branch_response.raise_for_status.return_value = None
        compared_head = (
            compare_response.json.return_value.get("head_commit",{}).get("sha")
            if compare_response is not None
            and isinstance(compare_response.json.return_value,dict)
            else "c"*40
        )
        branch_response.json.return_value = {
            "ref":"refs/heads/atlasquant-runtime",
            "object":{"type":"commit","sha":compared_head},
        }
        with patch(
            "atlasquant_aion_recovery.load_runtime_checkpoint", return_value=live
        ) as runtime_get, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=deepcopy(self.candidate)
        ) as historical_read, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
            return_value={"status": "CONFLICT", "saved": False, "verified": False},
        ) as save, patch(
            "requests.get",
            side_effect=compare_error if compare_error is not None
            else [compare_response,branch_response],
        ) as compare_get:
            result = restore_checkpoint_revision(
                deepcopy(self.candidate), deepcopy(self.current),
                self.cfg, approved=True,
            )
        return result, runtime_get, historical_read, save, compare_get

    def blocked(self, response=None, *, exc=None):
        result, target, historical, save, get = self.call(
            response, compare_error=exc
        )
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIs(result["saved"], False)
        self.assertIs(result["verified"], False)
        self.assertIs(result.get("automatic_retry_allowed"), False)
        target.assert_called_once_with(self.cfg, timeout=12.0)
        historical.assert_not_called()
        save.assert_not_called()
        get.assert_called_once()
        return result

    def test_01_unrelated_branch_commit_denied_before_historical_read(self):
        self.blocked(self.compare(status="diverged", merge_base="d" * 40))

    def test_02_revision_newer_than_runtime_head_denied(self):
        self.blocked(self.compare(status="behind", merge_base="c" * 40))

    def test_03_false_ahead_but_unrelated_merge_base_denied(self):
        self.blocked(self.compare(status="ahead", merge_base="d" * 40))

    def test_04_false_ahead_with_base_commit_mismatch_denied(self):
        self.blocked(self.compare(status="ahead", base="d" * 40))

    def test_05_non_object_compare_response_denied(self):
        response = self.compare()
        response.json.return_value = ["not", "object"]
        self.blocked(response)

    def test_06_compare_missing_merge_base_denied(self):
        response = self.compare()
        response.json.return_value.pop("merge_base_commit")
        self.blocked(response)

    def test_07_compare_rate_limited_denied(self):
        self.blocked(exc=TimeoutError("synthetic timeout"))

    def test_08_compare_unknown_status_denied(self):
        self.blocked(self.compare(status="unknown"))

    def test_09_valid_ancestor_reaches_conditional_save_mock(self):
        result, target, historical, save, get = self.call(self.compare())
        self.assertEqual(result["status"], "CONFLICT")
        self.assertIs(result["restore_confirmed"], False)
        target.assert_called_once()
        historical.assert_called_once_with(self.rev, self.cfg, timeout=12.0)
        save.assert_called_once()
        self.assertEqual(get.call_count,2)

    def test_10_revision_identical_to_branch_head_allowed_for_review(self):
        result, target, historical, save, get = self.call(
            self.compare(status="identical", head=self.rev)
        )
        self.assertEqual(result["status"], "CONFLICT")
        historical.assert_called_once()
        save.assert_called_once()
        self.assertEqual(get.call_count,2)

    def test_11_compare_url_uses_selected_revision_and_runtime_branch(self):
        _, _, _, _, get = self.call(self.compare())
        self.assertEqual(get.call_count,2)
        url = get.call_args_list[0].args[0]
        self.assertIn("/repos/example/repo/compare/", url)
        self.assertIn(self.rev, url)
        self.assertIn("atlasquant-runtime", url)
        self.assertEqual(get.call_args_list[0].kwargs["timeout"], 12.0)

    def test_12_no_human_approval_skips_ancestry_and_all_reads(self):
        with patch("atlasquant_aion_recovery.load_runtime_checkpoint") as target, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision"
        ) as historical, patch("atlasquant_aion_recovery.save_runtime_checkpoint") as save, patch(
            "requests.get"
        ) as compare_get:
            result = restore_checkpoint_revision(
                self.candidate, self.current, self.cfg, approved=False
            )
        self.assertEqual(result["status"], "BLOCKED")
        target.assert_not_called()
        historical.assert_not_called()
        save.assert_not_called()
        compare_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
