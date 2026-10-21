"""A134 RED-first: no independent enrolled witness means no checkpoint restore.

All network, recovery history and Git write functions are mocked. This LAB suite
tests the real restore gate and requires never reaching even a mocked save.
Caller/env claims and synthetic signatures are not independent authority.
"""
from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from atlasquant_aion_memory import RuntimeConfig
from atlasquant_aion_recovery import restore_checkpoint_revision
from test_atlasquant_aion_recovery_traceability_gate import _current, _candidate


class RecoveryIndependentHeadWitnessNoGoLab(unittest.TestCase):
    def setUp(self):
        self.cfg=RuntimeConfig(
            token="synthetic-unused",
            repo="example/repo",branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",
        )
        self.current=_current()
        self.candidate=_candidate()

    def attempt(self, *, env=None, mutate_current=None, mutate_candidate=None,
                approved=True):
        current=deepcopy(self.current)
        selected=deepcopy(self.candidate)
        if mutate_current:
            mutate_current(current)
        if mutate_candidate:
            mutate_candidate(selected)
        remote={**deepcopy(current),
                "source":f"GitHub:{self.cfg.branch}:{self.cfg.path}"}
        # The local GitHub checks all pass in the synthetic control case.
        # Still not enough without independent, enrolled monotonic witness.
        with patch.dict(os.environ,env or {},clear=False), patch(
            "atlasquant_aion_recovery.load_runtime_checkpoint",
            return_value=remote,
        ) as live, patch(
            "atlasquant_aion_recovery._verify_runtime_revision_ancestry",
            return_value={"allowed":True,"runtime_branch_head":"c"*40},
        ) as ancestry, patch(
            "atlasquant_aion_recovery.load_checkpoint_revision",
            return_value=selected,
        ) as history, patch(
            "atlasquant_aion_recovery._recheck_runtime_branch_head_before_save",
            return_value={"allowed":True,"runtime_branch_head":"c"*40},
        ) as git_head, patch(
            "atlasquant_aion_recovery.save_runtime_checkpoint",
            return_value={"status":"CONFIRMED","saved":True,"verified":True,
                          "reconciliation_required":False},
        ) as save:
            result=restore_checkpoint_revision(
                selected,current,self.cfg,approved=approved,
            )
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertIs(result["saved"],False,result)
        self.assertIs(result["verified"],False,result)
        self.assertIs(result.get("restore_confirmed"),False,result)
        self.assertIs(result.get("automatic_retry_allowed"),False,result)
        self.assertIs(result.get("automatic_restore"),False,result)
        self.assertIs(result.get("reconciliation_required"),False,result)
        save.assert_not_called()
        if approved:
            live.assert_called_once()
            ancestry.assert_called_once()
            history.assert_called_once()
            git_head.assert_called_once()
        else:
            live.assert_not_called()
            ancestry.assert_not_called()
            history.assert_not_called()
            git_head.assert_not_called()

    def test_01_approved_true_still_lacks_independent_head(self):
        self.attempt()

    def test_02_env_enrolled_true_is_not_trust_root(self):
        self.attempt(env={"AION_INDEPENDENT_WITNESS_ENROLLED":"true"})

    def test_03_env_witness_verified_flag_is_not_trust_root(self):
        self.attempt(env={"AION_WITNESS_VERIFIED":"true"})

    def test_04_env_owner_approved_is_not_custody(self):
        self.attempt(env={"AION_OWNER_APPROVED":"true"})

    def test_05_env_witness_bypass_is_not_custody(self):
        self.attempt(env={"AION_RECOVERY_WITNESS_BYPASS":"1"})

    def test_06_env_head_is_not_monotonic_proof(self):
        self.attempt(env={"AION_WITNESS_HEAD":"c"*40})

    def test_07_current_envelope_autocertification_does_not_authorize(self):
        self.attempt(mutate_current=lambda current:current.update({
            "independent_head_witness":{"verified":True,"status":"CONFIRMED",
                                        "head":"c"*40},
        }))

    def test_08_candidate_envelope_signed_read_claim_does_not_authorize(self):
        self.attempt(mutate_candidate=lambda selected:selected.update({
            "signed_fresh_read":{"issuer":"independent","verified":True,
                                 "sequence":999999},
        }))

    def test_09_fake_owner_signature_does_not_authorize(self):
        self.attempt(env={"AION_OWNER_SIGNATURE_VERIFIED":"true",
                          "AION_WITNESS_PUBLIC_KEY":"0"*64})

    def test_10_valid_github_cas_and_ancestry_still_not_authority(self):
        self.attempt(env={"AION_GITHUB_HEAD_VERIFIED":"true"})

    def test_11_no_explicit_approval_still_denies_before_network(self):
        self.attempt(approved=False)


if __name__=="__main__":
    unittest.main()
