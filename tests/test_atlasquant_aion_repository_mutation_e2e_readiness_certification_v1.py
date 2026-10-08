import unittest

from atlasquant_aion_repository_mutation_e2e_readiness_certification_v1 import (
    CHAIN,
    EXPECTED_MAIN_BASELINE_SHA,
    RUNTIME_GAPS,
    audit_nonexecuting_policy_boundaries,
    build_e2e_readiness_certificate,
    build_runtime_gap_register,
    e2e_readiness_policy,
)


class AionRepositoryMutationE2EReadinessCertificationV1Tests(unittest.TestCase):
    def observed_rows(self):
        return [
            {
                "number": item["number"],
                "state": "open",
                "draft": True,
                "mergeable": True,
                "base": item["base"],
                "head": item["head"],
                "head_sha": item["head_sha"],
                "changed_files": 4,
                "additions": item["additions"],
                "deletions": 0,
                "workflows": [
                    {
                        "name": item["workflow"],
                        "status": "completed",
                        "conclusion": "success",
                    }
                ],
            }
            for item in CHAIN
        ]

    def certificate(self, **changes):
        kwargs = {
            "observed_prs": self.observed_rows(),
            "observed_main_sha": EXPECTED_MAIN_BASELINE_SHA,
            "observed_main_tree_sha": "a" * 40,
            "frozen_core_integrity_verified": True,
            "expected_main_baseline_unchanged": True,
            "deploy_remained_disabled": True,
            "worker_remained_disabled": True,
            "provider_activation_remained_disabled": True,
            "production_persistence_remained_disabled": True,
            "real_owner_signature_verified": False,
            "physical_runtime_components_implemented": False,
            "live_github_mutation_adapter_installed": False,
            "runtime_credentials_bound": False,
            "durable_replay_and_persistence_bound": False,
            "live_github_state_reader_bound": False,
            "live_network_mutation_path_tested": False,
        }
        kwargs.update(changes)
        return build_e2e_readiness_certificate(**kwargs)

    def test_chain_is_exact_1033_through_1040(self):
        self.assertEqual(
            [item["number"] for item in CHAIN],
            [1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040],
        )
        self.assertEqual(len(CHAIN), 8)
        self.assertEqual(EXPECTED_MAIN_BASELINE_SHA, "5744b2b7b17c84331e6f27c569064993ff587782")
        self.assertTrue(all(item["additions"] > 0 for item in CHAIN))

    def test_policy_boundary_audit_is_nonexecuting(self):
        audit = audit_nonexecuting_policy_boundaries()
        self.assertEqual(
            audit["state"],
            "NONEXECUTING_POLICY_BOUNDARIES_VERIFIED",
            audit["blockers"],
        )
        self.assertEqual(len(audit["checks"]), 8)
        self.assertTrue(all(row["state"] == "PASS" for row in audit["checks"]))
        self.assertFalse(audit["repository_mutation_performed"])
        self.assertFalse(audit["executes_action"])

    def test_runtime_gap_register_is_explicit_and_fail_closed(self):
        gaps = build_runtime_gap_register()
        self.assertEqual(gaps["state"], "PHYSICAL_RUNTIME_GAPS_EXPLICIT")
        self.assertEqual(gaps["gap_count"], len(RUNTIME_GAPS))
        self.assertEqual(gaps["required_gap_count"], len(RUNTIME_GAPS))
        self.assertGreaterEqual(gaps["gap_count"], 10)
        self.assertFalse(
            gaps["all_required_physical_runtime_components_implemented"]
        )
        self.assertFalse(gaps["physical_runtime_ready"])
        self.assertFalse(gaps["live_repository_mutation_ready"])
        self.assertFalse(gaps["repository_mutation_performed"])
        self.assertFalse(gaps["executes_action"])
        ids = {row["id"] for row in gaps["gaps"]}
        self.assertIn("HUMAN_OWNER_EXTERNAL_SIGNER", ids)
        self.assertIn("DURABLE_NONCE_REPLAY_REGISTRY", ids)
        self.assertIn("SIGNED_GITHUB_MUTATION_ADAPTER_BINARY", ids)
        self.assertIn("GITHUB_MUTATION_TRANSPORT_EXECUTOR", ids)
        self.assertIn("AUTHORITATIVE_POSTCONDITION_READER", ids)
        self.assertIn("EMERGENCY_MUTATION_KILL_SWITCH", ids)

    def test_happy_path_certifies_contract_chain_not_live_mutation(self):
        cert = self.certificate()
        self.assertEqual(
            cert["state"],
            "E2E_CONTRACT_CHAIN_CERTIFIED_READY_FOR_PHYSICAL_RUNTIME_IMPLEMENTATION",
            cert["blockers"],
        )
        self.assertTrue(cert["contract_chain_certified"])
        self.assertTrue(cert["ready_for_physical_runtime_implementation"])
        self.assertFalse(cert["ready_for_live_repository_mutation"])
        self.assertFalse(cert["ready_for_production_repository_mutation"])
        self.assertEqual(cert["chain_prs"], [1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040])
        self.assertTrue(all(row["state"] == "MATCH" for row in cert["chain_checks"]))
        self.assertFalse(cert["real_owner_signature_verified"])
        self.assertFalse(cert["physical_runtime_components_implemented"])
        self.assertFalse(cert["live_github_mutation_adapter_installed"])
        self.assertFalse(cert["runtime_credentials_bound"])
        self.assertFalse(cert["durable_replay_and_persistence_bound"])
        self.assertFalse(cert["live_github_state_reader_bound"])
        self.assertFalse(cert["live_network_mutation_path_tested"])
        self.assertFalse(cert["live_repository_mutation_authorized"])
        self.assertFalse(cert["repository_mutation_performed"])
        self.assertFalse(cert["merge_executed"])
        self.assertFalse(cert["retarget_executed"])
        self.assertFalse(cert["draft_transition_executed"])
        self.assertFalse(cert["branch_deleted"])
        self.assertFalse(cert["deploy_executed"])
        self.assertFalse(cert["worker_activated"])
        self.assertFalse(cert["provider_activated"])
        self.assertFalse(cert["production_persistence_activated"])
        self.assertFalse(cert["external_action_executed"])
        self.assertFalse(cert["executes_action"])

    def test_head_base_or_gate_drift_blocks_certification(self):
        rows = self.observed_rows()
        rows[0]["head_sha"] = "0" * 40
        rows[1]["base"] = "main"
        rows[2]["workflows"][0]["conclusion"] = "failure"
        cert = self.certificate(observed_prs=rows)
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("PR_1033:HEAD_SHA_DRIFT", cert["blockers"])
        self.assertIn("PR_1034:BASE_DRIFT", cert["blockers"])
        self.assertTrue(
            any(
                item.startswith("PR_1035:REQUIRED_WORKFLOW_NOT_GREEN:")
                for item in cert["blockers"]
            )
        )
        self.assertFalse(cert["contract_chain_certified"])

    def test_file_delta_or_addition_drift_blocks(self):
        rows = self.observed_rows()
        rows[3]["changed_files"] = 5
        rows[4]["deletions"] = 1
        rows[5]["additions"] += 1
        cert = self.certificate(observed_prs=rows)
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("PR_1036:FOUR_FILE_DELTA_REQUIRED", cert["blockers"])
        self.assertIn("PR_1037:ZERO_DELETIONS_REQUIRED", cert["blockers"])
        self.assertIn("PR_1038:ADDITION_COUNT_DRIFT", cert["blockers"])

    def test_main_baseline_or_core_integrity_drift_blocks(self):
        cert = self.certificate(
            observed_main_sha="0" * 40,
            expected_main_baseline_unchanged=False,
            frozen_core_integrity_verified=False,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("MAIN_BASELINE_SHA_DRIFT", cert["blockers"])
        self.assertIn(
            "EXPECTED_MAIN_BASELINE_MUST_REMAIN_UNCHANGED",
            cert["blockers"],
        )
        self.assertIn("FROZEN_CORE_INTEGRITY_REQUIRED", cert["blockers"])

    def test_any_activation_regression_blocks(self):
        cert = self.certificate(
            deploy_remained_disabled=False,
            worker_remained_disabled=False,
            provider_activation_remained_disabled=False,
            production_persistence_remained_disabled=False,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("DEPLOY_MUST_REMAIN_DISABLED", cert["blockers"])
        self.assertIn("WORKER_MUST_REMAIN_DISABLED", cert["blockers"])
        self.assertIn(
            "PROVIDER_ACTIVATION_MUST_REMAIN_DISABLED",
            cert["blockers"],
        )
        self.assertIn(
            "PRODUCTION_PERSISTENCE_MUST_REMAIN_DISABLED",
            cert["blockers"],
        )

    def test_physical_runtime_claims_are_out_of_scope_and_block(self):
        cert = self.certificate(
            real_owner_signature_verified=True,
            physical_runtime_components_implemented=True,
            live_github_mutation_adapter_installed=True,
            runtime_credentials_bound=True,
            durable_replay_and_persistence_bound=True,
            live_github_state_reader_bound=True,
            live_network_mutation_path_tested=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "REAL_OWNER_SIGNATURE_MUST_REMAIN_UNVERIFIED_IN_THIS_STAGE",
            cert["blockers"],
        )
        self.assertIn(
            "PHYSICAL_RUNTIME_IMPLEMENTATION_OUT_OF_SCOPE",
            cert["blockers"],
        )
        self.assertIn(
            "LIVE_MUTATION_ADAPTER_INSTALLATION_OUT_OF_SCOPE",
            cert["blockers"],
        )
        self.assertIn(
            "RUNTIME_CREDENTIAL_BINDING_OUT_OF_SCOPE",
            cert["blockers"],
        )
        self.assertIn(
            "DURABLE_RUNTIME_BINDING_OUT_OF_SCOPE",
            cert["blockers"],
        )
        self.assertIn(
            "LIVE_GITHUB_STATE_READER_BINDING_OUT_OF_SCOPE",
            cert["blockers"],
        )
        self.assertIn(
            "LIVE_NETWORK_MUTATION_TEST_OUT_OF_SCOPE",
            cert["blockers"],
        )

    def test_policy_explicitly_separates_contract_and_live_readiness(self):
        policy = e2e_readiness_policy()
        self.assertEqual(
            policy["chain_prs"],
            [1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040],
        )
        self.assertTrue(policy["exact_head_sha_per_pr_required"])
        self.assertTrue(policy["exact_base_per_pr_required"])
        self.assertTrue(policy["four_file_delta_per_pr_required"])
        self.assertTrue(policy["zero_deletions_per_pr_required"])
        self.assertTrue(policy["dedicated_green_workflow_per_pr_required"])
        self.assertTrue(policy["frozen_core_integrity_required"])
        self.assertTrue(policy["main_baseline_must_remain_unchanged"])
        self.assertTrue(policy["nonexecuting_policy_boundary_audit_required"])
        self.assertTrue(policy["physical_runtime_gap_register_required"])
        self.assertTrue(
            policy["contract_certification_is_not_live_mutation_readiness"]
        )
        self.assertTrue(
            policy["ready_for_physical_runtime_implementation_may_be_true"]
        )
        self.assertFalse(policy["ready_for_live_repository_mutation"])
        self.assertFalse(policy["ready_for_production_repository_mutation"])
        self.assertFalse(policy["real_owner_signature_verified"])
        self.assertFalse(policy["physical_runtime_components_implemented"])
        self.assertFalse(policy["live_github_mutation_adapter_installed"])
        self.assertFalse(policy["runtime_credentials_bound"])
        self.assertFalse(policy["durable_replay_and_persistence_bound"])
        self.assertFalse(policy["live_github_state_reader_bound"])
        self.assertFalse(policy["live_network_mutation_path_tested"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["repository_mutation_performed"])
        self.assertFalse(policy["merge_executed"])
        self.assertFalse(policy["retarget_executed"])
        self.assertFalse(policy["draft_transition_executed"])
        self.assertFalse(policy["branch_deleted"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])
        self.assertFalse(policy["external_action_executed"])
        self.assertFalse(policy["executes_action"])


if __name__ == "__main__":
    unittest.main()
