"""A135 RED-first: no direct runtime Checkpoint Mestre PUT without trusted witness.

The test executes the real save_runtime_checkpoint entry point with a synthetic
RuntimeConfig. requests.put and all optional GET/readbacks are mocked. No real
GitHub write, product execution, account change, Worker, or provider effect.
"""
from __future__ import annotations

from copy import deepcopy
import os
import unittest
from unittest.mock import MagicMock, patch

from atlasquant_aion_memory import (
    RuntimeConfig, default_checkpoint, save_runtime_checkpoint,
)


class RuntimeDirectWriteIndependentWitnessNoGoLAB(unittest.TestCase):
    def setUp(self):
        self.config = RuntimeConfig(
            token="synthetic-never-used",
            repo="example/repo",
            branch="atlasquant-runtime",
            path="dados/aion/checkpoint_master.json",
        )
        self.payload = default_checkpoint()
        self.sha = "a"*40

    def attempt(self, *, env=None, payload=None, approved=True, expected_sha="",
                allow_global_arming_transition=False):
        cp = deepcopy(self.payload if payload is None else payload)
        conflict = MagicMock()
        conflict.status_code = 409
        with patch.dict(os.environ,env or {},clear=False), patch(
            "requests.put",return_value=conflict
        ) as put, patch(
            "requests.get"
        ) as get:
            result=save_runtime_checkpoint(
                cp,self.config,approved=approved,expected_sha=expected_sha,
                allow_global_arming_transition=allow_global_arming_transition,
            )
        self.assertEqual(result["status"],"BLOCKED",result)
        self.assertIs(result["saved"],False,result)
        self.assertIs(result["verified"],False,result)
        put.assert_not_called()
        get.assert_not_called()
        return result

    def test_01_approved_true_without_custody_cannot_put(self):
        self.attempt()

    def test_02_expected_sha_does_not_authorize_put(self):
        self.attempt(expected_sha=self.sha)

    def test_03_owner_approval_claim_in_env_is_not_custody(self):
        self.attempt(env={"AION_OWNER_APPROVED":"true"})

    def test_04_external_witness_verified_claim_in_env_is_not_custody(self):
        self.attempt(env={"AION_INDEPENDENT_WITNESS_VERIFIED":"true"})

    def test_05_enrollment_claim_in_env_is_not_custody(self):
        self.attempt(env={"AION_INDEPENDENT_WITNESS_ENROLLED":"true"})

    def test_06_restore_bypass_claim_is_not_custody(self):
        self.attempt(env={"AION_RECOVERY_WITNESS_BYPASS":"true"})

    def test_07_witness_claim_embedded_in_checkpoint_is_not_custody(self):
        cp=deepcopy(self.payload)
        cp["independent_witness"]={
            "verified":True,"owner_approved":True,
            "branch_head":"c"*40,"sequence":999999,
        }
        self.attempt(payload=cp)

    def test_08_checkpoint_content_claim_of_restoration_is_not_custody(self):
        cp=deepcopy(self.payload)
        cp["restoration_approved"]=True
        self.attempt(payload=cp,expected_sha=self.sha)

    def test_09_allow_global_arming_transition_is_not_custody(self):
        self.attempt(allow_global_arming_transition=True)

    def test_10_config_write_token_does_not_authenticate_owner_or_witness(self):
        self.attempt(env={"GITHUB_TOKEN_HISTORICO":"synthetic-never-used"})

    def test_11_no_approval_still_blocks_without_network(self):
        self.attempt(approved=False)


if __name__=="__main__":
    unittest.main()
