from __future__ import annotations

import ast
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from atlasquant_aion_developer_adversarial_auditor import (
    SCHEMA,
    audit_developer_chain,
    format_audit_report,
    main,
)

_ROOT=Path(__file__).resolve().parent
_AUDITOR=_ROOT/"atlasquant_aion_developer_adversarial_auditor.py"

_HARDENED_INVARIANTS={
    "replay.gate_not_bound_to_targets",
    "lineage.stale_snapshot_after_authorization",
    "scope.plan_records_outside_snapshot",
    "scope.post_authorization_expansion",
    "branch.equivalent_refs",
    "branch.prefix_bypass",
    "candidate.unbound_ref",
    "candidate.baseline_casefold_equal",
    "identity.case_variants",
    "identity.unicode_nfkc",
    "identity.fullwidth",
    "identity.combining",
    "auth.replay_other_envelope",
    "auth.stolen_authorization_id",
    "auth.approver_is_builder",
    "rollback.reused_text",
    "tests.approval_accepts_weakening",
    "workflow.envelope_includes_workflow",
    "release.notes_ready",
    "payload.excess_files_not_rejected",
    "identity.format_characters",
    "branch.nested_refs_and_aliases",
    "release.deployment_and_deploy_scripts",
    "tests.added_skip_or_expected_failure",
    "tests.recomputed_manifest_still_blocks_weakening",
    "runner.external_test_path",
    "runner.windows_absolute_test_path",
    "runner.unauthorized_or_nonexistent_test",
    "preflight.windows_drive_path",
    "patch.diff_header_mismatch",
    "patch.secret_beyond_prefix",
    "patch.additive_test_neutralization",
    "command.executable_nul",
    "command.executable_newline",
    "command.executable_whitespace",
    "command.non_mapping_entry",
    "command.runtime_budget_invalid",
    "command.memory_budget_invalid",
    "command.output_budget_invalid",
    "command.command_budget_invalid",
    "patch.missing_hunk",
    "runner.excessive_test_targets",
    "path.symlink_hardlink_physical_boundary_unverified",
    "test_contract.candidate_tests_mutated_after_request_id",
    "test_contract.mandatory_gates_mutated_after_request_id",
    "test_contract.required_gate_removed",
    "test_contract.arbitrary_gate",
    "test_contract.candidate_tests_string",
    "test_contract.mandatory_gates_string",
    "test_contract.review_refs_string",
    "test_contract.non_string_elements",
    "budget.runtime_true_initial",
    "budget.runtime_false_initial",
    "budget.runtime_numeric_string",
    "budget.runtime_integral_float",
    "budget.runtime_fractional_float",
    "budget.runtime_none",
    "budget.max_commands_true_initial",
    "budget.runtime_list_and_dict",
    "budget.runtime_mutated_to_true_keeps_id",
    "budget.max_commands_mutated_to_true_keeps_id",
    "budget.recompute_rejects_true",
    "budget.runner_revalidates_exact_int",
    "budget.command_policy_revalidates_exact_int",
    "attestation.forged",
    "attestation.stolen_id",
    "attestation.patch_digest_mutated",
    "attestation.candidate_sha_mutated",
    "attestation.baseline_sha_mutated",
    "attestation.tree_sha_mutated",
    "attestation.request_id_mismatch",
    "attestation.preflight_id_mismatch",
    "attestation.validation_id_mismatch",
    "attestation.replay_other_patch",
    "principal.duplicate_ids",
    "principal.same_id_distinct_display",
    "principal.empty",
    "principal.control_or_invisible",
    "pinning.relative_path",
    "pinning.malformed_sha256",
    "pinning.extra_executable",
    "pinning.python_without_git",
    "command.path_lookup_enabled",
    "command.caller_environment_override",
    "command.pythonpath_injection",
    "command.pythonstartup_injection",
    "command.home_injection",
    "command.git_config_injection",
    "command.pycache_inside_worktree",
    "command.pycache_inside_repository",
    "pinning.fake_verified_true",
    "runner.boolean_binding_without_attestation",
    "command.compileall_without_cache_policy",
    "attestation.mutated_after_seal",
    "runner_policy.runtime_stale_id",
    "runner_policy.memory_stale_id",
    "runner_policy.output_stale_id",
    "runner_policy.max_commands_stale_id",
    "runner_policy.targets_stale_id",
    "runner_policy.mandatory_gate_stale_id",
    "runner_policy.reviewer_stale_id",
    "runner_policy.review_ref_stale_id",
    "runner_policy.builder_request_id_stale",
    "runner_policy.preflight_id_stale",
    "runner_policy.patch_validation_id_stale",
    "runner_policy.patch_digest_stale",
    "runner_policy.attestation_id_stale",
    "runner_policy.structurally_bound_stale",
    "runner_policy.argv_stale",
    "runner_policy.executable_stale",
    "runner_policy.cwd_stale",
    "runner_policy.shell_stale",
    "runner_policy.network_stale",
    "runner_policy.writes_repo_stale",
    "runner_policy.pycache_prefix_stale",
    "runner_policy.ephemeral_cache_stale",
    "runner_policy.path_lookup_stale",
    "runner_policy.parent_env_stale",
    "runner_policy.caller_env_flag_stale",
    "runner_policy.authority_flag_stale",
    "runner_policy.deepcopy_nested_stale",
    "command_policy.mutated_keeps_id",
    "command_policy.fixed_environment_stale",
    "command_policy.validated_plan_stale",
    "runner_policy.chained_boundary_stale",
    "principal.integration_missing_builder",
    "principal.integration_missing_reviewer",
    "principal.integration_missing_breaker",
    "principal.integration_malformed",
    "principal.integration_same_id_different_display",
    "principal.integration_cyrillic_same_id",
    "principal.integration_same_display_distinct_ids",
    "principal.integration_approver_is_builder",
    "principal.integration_approver_is_reviewer",
    "principal.integration_approver_is_breaker",
    "principal.integration_mutate_after_readiness",
    "principal.integration_mutate_after_authorization",
    "principal.integration_request_differs_from_authorization",
    "principal.integration_legacy_authorization",
    "principal.integration_display_does_not_change_id",
    "principal.integration_principal_changes_id",
    "provenance.placeholder_synthetic",
    "provenance.placeholder_external_probe",
    "provenance.real_sha_stays_synthetic",
    "provenance.external_probe_without_probe",
    "provenance.source_mutated_after_id",
    "provenance.stolen_source",
    "provenance.caller_verified_true",
    "provenance.invalid_source",
    "provenance.missing_source",
    "provenance.legacy_without_source",
    "principal.integration_attestor_collides",
    "self_reseal.stale_id_contrast",
    "self_reseal.policy_argv",
    "self_reseal.policy_executable",
    "self_reseal.policy_cwd",
    "self_reseal.policy_runtime_out_of_range",
    "self_reseal.policy_runtime_string",
    "self_reseal.policy_memory_invalid",
    "self_reseal.policy_pythonpath",
    "self_reseal.policy_pythonhashseed",
    "self_reseal.policy_env_copies_diverge",
    "self_reseal.policy_shell_allowed",
    "self_reseal.runner_argv_boundary",
    "self_reseal.runner_budget_old_policy",
    "self_reseal.joint_documents",
    "self_reseal.budget_mismatch_both_valid",
    "self_reseal.plan_not_canonical",
    "self_reseal.nested_mutation",
    "self_reseal.authority_flag",
    "self_reseal.security_flag_relaxed",
    "self_reseal.extra_environment_key",
    "self_reseal.legitimate_constructor",
    "upstream_provenance.builder_request_id",
    "upstream_provenance.preflight_id",
    "upstream_provenance.patch_validation_id",
    "upstream_provenance.patch_digest",
    "upstream_provenance.attestation_id",
    "upstream_provenance.joint_reseal",
    "upstream_provenance.legitimate",
    "blocked_to_ready.review_false_same_id",
    "blocked_to_ready.review_false_resealed",
    "blocked_to_ready.missing_refs",
    "blocked_to_ready.revision_unverified",
    "blocked_to_ready.missing_targets",
    "blocked_to_ready.policy_promoted",
    "blocked_to_ready.policy_ready_with_blockers",
    "review_principal.mismatch",
    "review_principal.reviewed_false",
    "review_principal.refs_removed",
    "review_principal.display_is_label",
    "test_target_origin.replaced",
    "test_target_origin.removed",
    "test_target_origin.unapproved",
    "test_target_origin.gates",
    "policy_provenance.missing_upstream",
    "policy_provenance.caller_structural_true",
    "policy_provenance.independent_true",
    "policy_provenance.false_lineage",
    "policy_provenance.different_upstream",
    "policy_provenance.bundle_swap",
    "policy_provenance.structural_claim_reseal",
    "policy_provenance.ready_with_provenance_blocker",
    "policy_provenance.blocker_removed",
    "policy_provenance.structural_false_not_ready",
    "policy_provenance.legitimate",
    "policy_provenance.cross_bound_not_independent",
    "os_sandbox.missing_provenance",
    "os_sandbox.structural_false",
    "os_sandbox.independent_true",
    "os_sandbox.fake_pinning_verified",
    "os_sandbox.path_lookup",
    "os_sandbox.parent_environment",
    "os_sandbox.caller_environment",
    "os_sandbox.secrets_mounted",
    "os_sandbox.network_allowed",
    "os_sandbox.network_isolation_claim",
    "os_sandbox.shell_allowed",
    "os_sandbox.child_process_allow",
    "os_sandbox.repo_write",
    "os_sandbox.filesystem_isolation_claim",
    "os_sandbox.symlink_claim",
    "os_sandbox.hardlink_claim",
    "os_sandbox.verified_claim",
    "os_sandbox.resource_limits_claim",
    "os_sandbox.budget_escape",
    "os_sandbox.platform_adapter_claim",
    "os_sandbox.cleared_physical_proof",
    "os_sandbox.stale_ready_id",
    "os_sandbox.reseal_promotion",
    "os_sandbox.swapped_environment",
    "os_sandbox.swapped_pinning",
    "os_sandbox.bundle_swap",
    "os_sandbox.extra_authority",
    "os_sandbox.legitimate",
}


class AionDeveloperAdversarialAuditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=audit_developer_chain()

    def test_report_shape_is_deterministic_and_unscored(self):
        report=self.report
        self.assertEqual(report["schema"],SCHEMA)
        self.assertEqual(report["cases_total"],272)
        self.assertEqual(
            report["gap_count"]+report["blocked_by_design_count"]+report["pass_count"],
            272,
        )
        self.assertFalse(report["symlink_physical_boundary_verified"])
        self.assertFalse(report["hardlink_physical_boundary_verified"])
        self.assertNotIn("score",report)
        self.assertNotIn("security_score",report)
        for key in (
            "executes_repository_code","writes_existing_files","network_called",
            "subprocess_called","automatic_commit","automatic_merge",
            "automatic_deploy","real_trading_enabled","tool_output_is_authority",
        ):
            self.assertFalse(report[key])

    def test_manifest_hardening_closes_previous_critical_and_high_findings(self):
        gaps={item["invariant_id"]:item for item in self.report["gaps"]}
        still_open=sorted(_HARDENED_INVARIANTS & set(gaps))
        self.assertEqual(still_open,[])
        self.assertEqual(self.report["gaps_by_severity"]["CRITICAL"],[])
        self.assertEqual(self.report["gaps_by_severity"]["HIGH"],[])

    def test_every_remaining_gap_is_explicit_and_noncritical(self):
        for item in self.report["gaps"]:
            self.assertIn(item["severity"],{"MEDIUM","LOW"})
            self.assertTrue(item["invariant_id"])
            self.assertTrue(item["description"])

    def test_report_is_deterministic_and_has_no_secret(self):
        again=audit_developer_chain()
        self.assertEqual(again["report_digest"],self.report["report_digest"])
        text=format_audit_report(self.report)
        self.assertNotIn("supersecretvalue",text)
        self.assertNotIn("ghp_ADVERSARIALAUDITOR1234567890",text)

    def test_cli_exit_matches_gap_state_without_dumping_secrets(self):
        buffer=StringIO()
        with redirect_stdout(buffer):
            code=main()
        text=buffer.getvalue()
        self.assertEqual(code,1 if self.report["gap_count"] else 0)
        self.assertIn("AION Developer Adversarial Audit",text)
        self.assertNotIn("supersecretvalue",text)
        self.assertNotIn("ghp_",text)

    def test_auditor_source_is_read_only(self):
        tree=ast.parse(_AUDITOR.read_text(encoding="utf-8"))
        banned_calls={"eval","exec","__import__","getattr"}
        banned_modules={"importlib","subprocess","socket","requests","urllib","http","ftplib","smtplib"}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                func=node.func
                name=func.id if isinstance(func,ast.Name) else func.attr if isinstance(func,ast.Attribute) else ""
                self.assertNotIn(name,banned_calls)
                if name in {"system","Popen"}:
                    self.fail(name)
            if isinstance(node,ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0],banned_modules)
            if isinstance(node,ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0],banned_modules)
        source=_AUDITOR.read_text(encoding="utf-8")
        self.assertNotIn("expectedFailure",source)
        self.assertNotIn("unittest.skip",source)


if __name__=="__main__":
    unittest.main()
