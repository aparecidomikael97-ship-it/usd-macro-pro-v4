"""A73: Global Worker readiness MUST fail closed without independently enrolled F1/T1.

These are offline fake local checkpoints; no external witness, producer, action,
credential, deployment, Worker or physical HUMAN_OWNER test is performed.
"""
import unittest
from copy import deepcopy

from atlasquant_aion_global_worker_readiness import (
    activation_readiness_snapshot, runtime_posture,
)
from atlasquant_aion_global_worker import stage_arm_global_worker
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    prepare_global_worker_arming_plan, approve_global_worker_arming_plan,
)
import test_atlasquant_aion_global_worker_readiness as prior


def snapshot(runtime=None, *, flag="0"):
    return activation_readiness_snapshot(
        runtime_result=runtime if runtime is not None else prior._runtime(),
        config=prior._config(), feature_flag_raw=flag,
        workflow_text=prior._workflow(),
        pulse_rows=prior._pulses(),
        now=prior.NOW,
    )


def staged_armed_checkpoint():
    access = prior._access()
    plan = prepare_global_worker_arming_plan(
        access, {}, max_jobs=5, lease_seconds=600,
        approval_ttl_seconds=900, now=prior.NOW,
    )
    ticket = approve_global_worker_arming_plan(
        access, plan["plan"], confirmation=True,
        confirmation_phrase=CONFIRMATION_PHRASE,
        now=prior.NOW,
    )
    staged = stage_arm_global_worker(
        access, {}, confirmation=True, arming_approval=ticket["approval"],
        max_jobs=5, lease_seconds=600, now=prior.NOW,
    )
    return staged["checkpoint"]


class A73IndependentSourceWitnessReadinessDenialTests(unittest.TestCase):
    def assert_denied(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["activation_stage"], "BLOCKED")
        self.assertIn("INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED", result["blockers"])
        self.assertIs(result["source_authenticity_verified"], False)
        self.assertIs(result["independent_witness_verified"], False)
        self.assertIs(result["source_resource_owner_bound"], False)
        self.assertIs(result["external_activation_allowed"], False)
        self.assertIs(result["worker_armed_by_this_check"], False)
        self.assertIs(result["runtime_modified"], False)
        self.assertIs(result["feature_flag_modified"], False)
        self.assertIs(result["external_action_executed"], False)

    def test_01_local_green_pulses_and_local_runtime_do_not_authorize_admin_arming(self):
        self.assertEqual(runtime_posture(prior._runtime(), prior._config())["state"], "PASS")
        self.assert_denied(snapshot(flag="0"))

    def test_02_staged_armed_checkpoint_must_not_be_ready_to_enable_worker(self):
        self.assert_denied(snapshot(prior._runtime(staged_armed_checkpoint()), flag="0"))

    def test_03_forged_attestation_claims_inside_runtime_never_unlock_readiness(self):
        base = prior._runtime(staged_armed_checkpoint())
        for fake in (True, "VERIFIED", {"state": "PASS", "trusted": True}):
            with self.subTest(value=repr(fake)):
                tampered = deepcopy(base)
                tampered["independent_witness_verified"] = fake
                tampered["source_authenticity_verified"] = fake
                tampered["external_activation_allowed"] = True
                tampered["witness"] = {"state": "VERIFIED", "monotonic_sequence": 99999}
                self.assert_denied(snapshot(tampered, flag="0"))

    def test_04_feature_enabled_and_self_attested_source_are_not_enough(self):
        runtime = prior._runtime(staged_armed_checkpoint())
        runtime["source"] = "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json"
        runtime["checkpoint"]["source_authenticity_verified"] = True
        self.assert_denied(snapshot(runtime, flag="1"))

    def test_05_source_status_is_not_implied_from_local_posture(self):
        result = snapshot(flag="")
        self.assertEqual(result["runtime"]["state"], "PASS")
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["independent_witness_verified"])
        self.assertFalse(result["external_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
