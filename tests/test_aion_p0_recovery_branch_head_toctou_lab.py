"""A133 RED-first: detect runtime branch HEAD movement before recovery save.

No external network, GitHub write, recovery, Worker or provider effect occurs:
all GitHub GETs and the save function are mocked. This is SAME-GITHUB branch
consistency, not proof of an independently monotonic or trustworthy latest HEAD.
"""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import RuntimeConfig
from atlasquant_aion_recovery import restore_checkpoint_revision
from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate

HEAD = "c" * 40
OTHER = "d" * 40


class RecoveryBranchHeadTOCTOUFenceLAB(unittest.TestCase):
    def setUp(self):
        self.cfg=RuntimeConfig(
            token="unused-synthetic",repo="example/repo",
            branch="atlasquant-runtime",path="dados/aion/checkpoint_master.json",
        )
        self.current=_current()
        self.candidate=_candidate()

    def branch_ref(self, sha=HEAD, *, obj_type="commit", raw=None):
        response=MagicMock()
        response.raise_for_status.return_value=None
        response.json.return_value = (
            {"ref":"refs/heads/atlasquant-runtime",
             "object":{"type":obj_type,"sha":sha}}
            if raw is None else raw
        )
        return response

    def call(self, response, *, raised=None, ancestry_head=HEAD):
        current={**deepcopy(self.current),
                 "source":f"GitHub:{self.cfg.branch}:{self.cfg.path}"}
        with patch(
            "atlasquant_aion_recovery.load_runtime_checkpoint",
            return_value=current,
        ) as target, patch(
            "atlasquant_aion_recovery._verify_runtime_revision_ancestry",
            return_value={"allowed":True,"runtime_branch_head":ancestry_head},
        ) as compare, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=deepcopy(self.candidate),
        ) as history, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
            return_value={"status":"CONFLICT","saved":False,"verified":False},
        ) as save, patch(
            "atlasquant_aion_recovery._require_independent_recovery_head_witness",
            return_value={"allowed":True,"synthetic_test_only":True},
        ), patch(
            "requests.get",return_value=response,side_effect=raised,
        ) as git_get:
            result=restore_checkpoint_revision(
                deepcopy(self.candidate),deepcopy(self.current),
                self.cfg,approved=True,
            )
        return result,target,compare,history,save,git_get

    def blocked(self,response,*,raised=None,ancestry_head=HEAD,expect_git_get=True):
        result,target,compare,history,save,git_get=self.call(
            response,raised=raised,ancestry_head=ancestry_head,
        )
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertIs(result["saved"],False)
        self.assertIs(result["verified"],False)
        self.assertIs(result.get("automatic_retry_allowed"),False)
        self.assertIs(result.get("automatic_restore"),False)
        target.assert_called_once()
        compare.assert_called_once()
        history.assert_called_once()
        save.assert_not_called()
        if expect_git_get:
            git_get.assert_called_once()
        else:
            git_get.assert_not_called()
        return result

    def test_01_changed_branch_head_blocks_save(self):
        self.blocked(self.branch_ref(OTHER))

    def test_02_missing_ref_object_blocks_save(self):
        self.blocked(self.branch_ref(raw={"ref":"refs/heads/atlasquant-runtime"}))

    def test_03_non_object_response_blocks_save(self):
        self.blocked(self.branch_ref(raw=["not-a-git-ref"]))

    def test_04_missing_commit_sha_blocks_save(self):
        self.blocked(self.branch_ref(raw={"object":{"type":"commit"}}))

    def test_05_boolean_commit_sha_blocks_save(self):
        self.blocked(self.branch_ref(sha=True))

    def test_06_short_commit_sha_blocks_save(self):
        self.blocked(self.branch_ref(sha="a"*39))

    def test_07_tag_object_ref_blocks_save(self):
        self.blocked(self.branch_ref(obj_type="tag"))

    def test_08_non_matching_ref_name_blocks_save(self):
        self.blocked(self.branch_ref(raw={
            "ref":"refs/heads/other",
            "object":{"type":"commit","sha":HEAD},
        }))

    def test_09_timeout_blocks_save(self):
        self.blocked(None,raised=TimeoutError("synthetic timeout"))

    def test_10_missing_compared_head_blocks_save(self):
        self.blocked(self.branch_ref(),ancestry_head=None,expect_git_get=False)

    def test_11_match_reaches_conditional_save_mock(self):
        result,target,compare,history,save,git_get=self.call(
            self.branch_ref()
        )
        self.assertEqual(result["status"],"CONFLICT",result)
        self.assertIs(result["restore_confirmed"],False)
        target.assert_called_once()
        history.assert_called_once()
        save.assert_called_once()
        git_get.assert_called_once()

    def test_12_git_ref_url_scope_is_configured_repo_and_branch(self):
        _,_,_,_,_,git_get=self.call(self.branch_ref())
        git_get.assert_called_once()
        args=git_get.call_args
        self.assertEqual(
            args.args[0],
            "https://api.github.com/repos/example/repo/git/ref/heads/atlasquant-runtime",
        )
        self.assertEqual(args.kwargs.get("timeout"),12.0)
        self.assertIn("Authorization",args.kwargs["headers"])

    def test_13_unapproved_restore_never_checks_head(self):
        with patch("requests.get") as get,patch(
            "atlasquant_aion_recovery.load_checkpoint_revision"
        ) as history,patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint"
        ) as save:
            result=restore_checkpoint_revision(
                deepcopy(self.candidate),deepcopy(self.current),
                self.cfg,approved=False,
            )
        self.assertEqual(result["status"],"BLOCKED")
        get.assert_not_called()
        history.assert_not_called()
        save.assert_not_called()


if __name__=="__main__":
    unittest.main()
