from __future__ import annotations

import unittest

from atlasquant_aion_core_v1_technical_closure_candidate import (
    REAL_WORLD_STEPS_STILL_SEPARATE,
    REQUIRED_TECHNICAL_LAYERS,
    STATE,
    TARGET_CI_PR,
    TARGET_COMMIT_SHA,
    build_core_v1_technical_closure_candidate,
)


class CoreV1TechnicalClosureCandidateTests(unittest.TestCase):
    def test_candidate_is_bound_to_validated_reference_ui_head(self):
        row = build_core_v1_technical_closure_candidate()
        self.assertEqual(
            TARGET_COMMIT_SHA,
            "1f0575a650bce16acb94c69a24b880c16a79b445",
        )
        self.assertEqual(TARGET_CI_PR, 950)
        self.assertEqual(row["target_commit_sha"], TARGET_COMMIT_SHA)
        self.assertEqual(row["target_ci_pr"], 950)
        self.assertEqual(row["state"], STATE)

    def test_required_structural_and_closure_layers_are_declared(self):
        row = build_core_v1_technical_closure_candidate()
        expected = {
            "REAL_TRUST_ROOT_AUTHORITY_V213",
            "DURABLE_EXECUTION_V214",
            "CAPABILITY_ISOLATION_V215",
            "OPERATIONAL_RESILIENCE_V216",
            "MULTIAGENT_MEMORY_GOVERNANCE_V217",
            "CONSTITUTION_POLICY_KERNEL_V218",
            "PROVIDER_NEUTRAL_MODEL_GATEWAY_V219",
            "CORE_CERTIFICATION_V220",
            "CORE_COMPLETION_REVIEW_V221",
            "CORE_FREEZE_PREFLIGHT_V222",
            "EXTERNAL_PERSISTENCE_ATTESTATION_V223_CONTRACT",
            "OWNER_SIGNATURE_CEREMONY_V224_CONTRACT",
            "EXPLICIT_OWNER_DECISION_V225_CONTRACT",
            "OWNER_DECISION_PERSISTENCE_V226_CONTRACT",
            "TERMINAL_CERTIFICATE_REFERENCE_UI_DRAFT",
            "GLOBAL_WORKER_READINESS_CONTRACT",
        }
        self.assertTrue(expected.issubset(set(REQUIRED_TECHNICAL_LAYERS)))
        self.assertEqual(
            row["technical_layer_count"],
            len(REQUIRED_TECHNICAL_LAYERS),
        )

    def test_real_world_critical_steps_remain_explicitly_separate(self):
        row = build_core_v1_technical_closure_candidate()
        expected = {
            "REAL_V223_EXTERNAL_CHECKPOINT_PERSISTENCE",
            "REAL_V224_OWNER_SIGNATURE",
            "REAL_V225_EXPLICIT_OWNER_DECISION",
            "REAL_V226_OWNER_DECISION_PERSISTENCE",
            "CORE_FREEZE_EXECUTION",
            "MERGE",
            "DEPLOY",
            "GLOBAL_WORKER_ACTIVATION",
        }
        self.assertEqual(set(REAL_WORLD_STEPS_STILL_SEPARATE), expected)
        self.assertEqual(set(row["real_world_steps_still_separate"]), expected)

    def test_candidate_never_implies_owner_decision_or_freeze(self):
        row = build_core_v1_technical_closure_candidate()
        self.assertTrue(row["technical_closure_candidate"])
        self.assertTrue(row["technical_scope_closed_for_owner_review"])
        self.assertTrue(row["candidate_is_not_freeze"])
        self.assertTrue(row["candidate_is_not_owner_decision"])
        self.assertTrue(row["owner_review_required"])
        self.assertTrue(row["requires_explicit_human_owner_action"])
        self.assertEqual(row["owner_decision"], "UNDECIDED")
        for key in (
            "owner_decision_recorded",
            "core_complete",
            "core_freeze_authorized",
            "core_freeze_execution_authorized",
            "core_frozen",
            "merge_authorized",
            "deploy_authorized",
            "execution_allowed",
            "worker_armed",
            "external_action_executed",
            "production_mutation_performed",
            "executes_action",
        ):
            self.assertIs(row[key], False, key)

    def test_real_persistence_and_signature_are_not_faked(self):
        row = build_core_v1_technical_closure_candidate()
        self.assertTrue(row["runtime_persistence_real_attestation_required"])
        self.assertTrue(row["owner_signature_real_required"])
        self.assertTrue(row["owner_decision_real_required"])
        self.assertTrue(row["owner_decision_persistence_real_required"])
        self.assertTrue(row["candidate_is_not_merge_or_deploy_authority"])
        self.assertTrue(row["candidate_is_not_runtime_activation"])


if __name__ == "__main__":
    unittest.main()
