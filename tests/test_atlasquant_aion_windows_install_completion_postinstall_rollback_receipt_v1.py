"""Synthetic, fail-closed tests. No physical Windows installation is performed."""
import copy
import unittest

from atlasquant_aion_windows_atomic_install_start_file_transaction_journal_v1 import (
    JOURNAL_PLAN_SCHEMA, READY_JOURNAL_PLAN_STATE,
    READY_JOURNAL_ENTRY_STATE, READY_RECOVERY_STATE, OP_APPLIED, OP_UNKNOWN,
    build_journal_entry_candidate, classify_future_operation_observation,
    build_recovery_contract,
)
from atlasquant_aion_windows_install_completion_postinstall_rollback_receipt_v1 import (
    GATE_READY, PLAN_READY, VERIFY_READY, ROLLBACK_READY, TERMINAL_READY,
    BLOCKED, UNKNOWN, ROLLBACK_UNKNOWN, SUCCESS_CANDIDATE,
    ROLLBACK_CANDIDATE, FAILURE_CANDIDATE, REVIEW_READY,
    build_completion_journal_gate, build_postinstall_verification_plan,
    validate_postinstall_evidence_shape, build_rollback_terminal_receipt_candidate,
    build_terminal_install_receipt_candidate, build_completion_implementation_review,
    completion_policy, _digest,
)

D = lambda char: "sha256:" + char * 64

class InstallCompletionPostinstallRollbackReceiptTests(unittest.TestCase):
    def fixture(self):
        kinds = ["COPY_NEW_FILE", "REPLACE_EXISTING_FILE", "SET_OWNER_ACL", "CREATE_STARTUP_ENTRY"]
        ops = [
            {
                "sequence": i,
                "operation_id": f"op-{i}",
                "operation_kind": kind,
                "target_digest": D(str(i)),
                "before_state_digest": D("a"),
                "intended_after_state_digest": D("b"),
                "rollback_action_digest": D("c"),
                "source_artifact_digest": D("d"),
            }
            for i, kind in enumerate(kinds, 1)
        ]
        p = {
            "atomic_install_contract_digest": D("1"),
            "install_commitment_digest": D("2"),
            "installation_id": "install-synthetic-only-001",
            "journal_genesis_digest": _digest({
                "installation_id": "install-synthetic-only-001",
                "install_commitment_digest": D("2"),
                "journal_kind": "WINDOWS_INSTALL_FILE_TRANSACTION_V1",
            }),
            "operation_count": len(ops),
            "operations": ops,
        }
        p = {
            "schema": JOURNAL_PLAN_SCHEMA,
            "state": READY_JOURNAL_PLAN_STATE,
            **p,
            "journal_plan_digest": _digest(p),
        }
        entries, observations = [], []
        for seq, op in enumerate(ops, 1):
            entry = build_journal_entry_candidate(
                p, sequence=seq,
                previous_entry=entries[-1] if entries else None,
                previous_entry_digest=entries[-1]["journal_entry_digest"] if entries else p["journal_genesis_digest"],
            )
            assert entry["state"] == READY_JOURNAL_ENTRY_STATE, entry
            entries.append(entry)
            obs = classify_future_operation_observation(
                entry, requested_outcome=OP_APPLIED, operation_attempted=True,
                before_state_observation_digest=op["before_state_digest"],
                mutation_write_observation_digest=D("e"),
                after_state_observation_digest=op["intended_after_state_digest"],
                rollback_material_presence_digest=D("f"),
            )
            assert obs["final_outcome"] == OP_APPLIED, obs
            observations.append(obs)
        return p, entries, observations

    def verified_fixture(self):
        p, es, os = self.fixture()
        gate = build_completion_journal_gate(p, es, os)
        self.assertEqual(gate["state"], GATE_READY, gate)
        plan = build_postinstall_verification_plan(
            p, gate, reopen_policy_digest=D("1"),
            health_policy_digest=D("2"), independent_verifier_manifest_digest=D("3"),
        )
        self.assertEqual(plan["state"], PLAN_READY, plan)
        rows = [
            {
                "check_id": check["check_id"],
                "expected_digest": check["expected_digest"],
                "observed_digest": check["expected_digest"],
                "verified_after_reopen": True,
                "independent_verifier_observed": True,
                "readback_receipt_digest": D("4"),
                "independent_verifier_receipt_digest": D("5"),
                "ambiguity_detected": False,
            }
            for check in plan["checks"]
        ]
        evidence = validate_postinstall_evidence_shape(plan, rows)
        self.assertEqual(evidence["state"], VERIFY_READY, evidence)
        return p, es, os, gate, plan, rows, evidence

    def test_complete_ordered_chain_is_only_untrusted_shape(self):
        p, es, os = self.fixture()
        gate = build_completion_journal_gate(p, es, os)
        self.assertEqual(gate["state"], GATE_READY)
        self.assertFalse(gate["installation_complete_trusted"])
        self.assertFalse(gate["aion_healthy_trusted"])
        self.assertFalse(gate["journal_persisted_trusted"])

    def test_missing_operation_or_missing_observation_blocks(self):
        p, es, os = self.fixture()
        self.assertEqual(build_completion_journal_gate(p, es[:-1], os)["state"], BLOCKED)
        self.assertEqual(build_completion_journal_gate(p, es, os[:-1])["state"], BLOCKED)
        self.assertEqual(build_completion_journal_gate(p, es[::-1], os)["state"], BLOCKED)

    def test_forged_chain_or_observation_blocks_even_if_ready_claimed(self):
        p, es, os = self.fixture()
        fake = copy.deepcopy(es)
        fake[2]["previous_entry_digest"] = D("f")
        self.assertEqual(build_completion_journal_gate(p, fake, os)["state"], BLOCKED)
        fakeobs = copy.deepcopy(os)
        fakeobs[1]["operation_applied_confirmed"] = True
        fakeobs[1]["after_state_observation_digest"] = D("1")
        self.assertEqual(build_completion_journal_gate(p, es, fakeobs)["state"], BLOCKED)
        fakeplan = copy.deepcopy(p)
        fakeplan["operations"][0]["operation_id"] = "tampered-operation"
        self.assertEqual(build_completion_journal_gate(fakeplan, es, os)["state"], BLOCKED)

    def test_unknown_or_failed_operation_never_counts_as_completion(self):
        p, es, os = self.fixture()
        unknown = classify_future_operation_observation(
            es[1], requested_outcome=OP_APPLIED, operation_attempted=True,
            before_state_observation_digest=D("a"),
            mutation_write_observation_digest=D("e"),
            after_state_observation_digest=D("f"),
            rollback_material_presence_digest=D("f"),
        )
        self.assertEqual(unknown["final_outcome"], OP_UNKNOWN)
        changed = list(os)
        changed[1] = unknown
        self.assertEqual(build_completion_journal_gate(p, es, changed)["state"], BLOCKED)

    def test_postinstall_plan_requires_all_global_checks_and_each_final_target(self):
        p, es, os, gate, plan, rows, evidence = self.verified_fixture()
        names = {x["check_kind"] for x in plan["checks"]}
        self.assertTrue({
            "INSTALL_COMMITMENT_CAS_REOPEN", "JOURNAL_CHAIN_REOPEN",
            "PACKAGE_MANIFEST_REOPEN", "TARGET_FILES_REOPEN", "OWNER_ACL_REOPEN",
            "STARTUP_ENTRY_REOPEN", "AION_RUNTIME_HEALTH_REOPEN",
            "TARGET_FINAL_STATE_REOPEN",
        }.issubset(names))
        self.assertEqual(len(rows), 11)
        self.assertFalse(evidence["package_installed_trusted"])
        self.assertFalse(evidence["aion_healthy_trusted"])

    def test_missing_runtime_health_acl_startup_or_target_readback_blocks(self):
        _, _, _, _, plan, rows, _ = self.verified_fixture()
        for absent in ("AION_RUNTIME_HEALTH_REOPEN", "OWNER_ACL_REOPEN", "STARTUP_ENTRY_REOPEN", "TARGET_FINAL_STATE_REOPEN"):
            bad = [r for r in rows if not (
                r["check_id"].endswith(absent) if absent != "TARGET_FINAL_STATE_REOPEN"
                else r["check_id"].startswith("TARGET:")
            )]
            self.assertEqual(validate_postinstall_evidence_shape(plan, bad)["state"], BLOCKED, absent)

    def test_reopen_mismatch_ambiguous_and_forged_duplicate_are_blocked(self):
        _, _, _, _, plan, rows, _ = self.verified_fixture()
        bad = copy.deepcopy(rows)
        bad[-1]["observed_digest"] = D("9")
        self.assertEqual(validate_postinstall_evidence_shape(plan, bad)["state"], BLOCKED)
        bad = copy.deepcopy(rows)
        bad[0]["ambiguity_detected"] = True
        self.assertEqual(validate_postinstall_evidence_shape(plan, bad)["state"], BLOCKED)
        bad = copy.deepcopy(rows)
        bad[1] = bad[0]
        self.assertEqual(validate_postinstall_evidence_shape(plan, bad)["state"], BLOCKED)

    def test_terminal_success_shape_never_claims_physical_install(self):
        p, _, _, gate, _, _, evidence = self.verified_fixture()
        result = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="SUCCESS",
            journal_gate=gate, postinstall_evidence=evidence,
            terminal_reopen_receipt_digest=D("6"),
            independent_final_attestor_digest=D("7"),
        )
        self.assertEqual(result["state"], TERMINAL_READY, result)
        self.assertEqual(result["terminal_outcome"], SUCCESS_CANDIDATE)
        self.assertFalse(result["physically_installed_trusted"])
        self.assertFalse(result["aion_healthy_trusted"])
        self.assertFalse(result["terminal_disposition_persisted"])

    def test_success_blocked_if_health_evidence_missing_or_wrong_install_id(self):
        p, _, _, gate, plan, rows, evidence = self.verified_fixture()
        bad = validate_postinstall_evidence_shape(plan, rows[:-1])
        res = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="SUCCESS",
            journal_gate=gate, postinstall_evidence=bad,
            terminal_reopen_receipt_digest=D("6"), independent_final_attestor_digest=D("7"),
        )
        self.assertEqual(res["state"], BLOCKED)
        res = build_terminal_install_receipt_candidate(
            installation_id="other-install", requested_disposition="SUCCESS",
            journal_gate=gate, postinstall_evidence=evidence,
            terminal_reopen_receipt_digest=D("6"), independent_final_attestor_digest=D("7"),
        )
        self.assertEqual(res["terminal_outcome"], UNKNOWN)

    def rollback_fixture(self):
        p, es, os = self.fixture()
        unknown = classify_future_operation_observation(
            es[1], requested_outcome=OP_APPLIED, operation_attempted=True,
            before_state_observation_digest=D("a"),
            mutation_write_observation_digest=D("e"),
            after_state_observation_digest=D("f"),
            rollback_material_presence_digest=D("f"),
        )
        recovery = build_recovery_contract(
            p, unknown, journal_reopen_policy_digest=D("1"),
            filesystem_readback_policy_digest=D("2"),
            rollback_executor_manifest_digest=D("3"),
        )
        self.assertEqual(recovery["state"], READY_RECOVERY_STATE, recovery)
        steps = [
            {
                "sequence": seq,
                "operation_id": p["operations"][seq-1]["operation_id"],
                "rollback_action_digest": p["operations"][seq-1]["rollback_action_digest"],
                "observed_restored_state_digest": p["operations"][seq-1]["before_state_digest"],
                "rollback_step_outcome": "ROLLBACK_STEP_APPLIED_CONFIRMED",
                "verified_after_reopen": True,
                "ambiguity_detected": False,
                "rollback_write_receipt_digest": D("4"),
                "readback_receipt_digest": D("5"),
                "independent_verifier_receipt_digest": D("6"),
            }
            for seq in [2,1]
        ]
        return p, recovery, steps

    def test_reverse_rollback_shape_works_but_never_claims_execution(self):
        p, recovery, steps = self.rollback_fixture()
        receipt = build_rollback_terminal_receipt_candidate(
            p, recovery, steps, final_clean_reopen_receipt_digest=D("7"),
            independent_verifier_manifest_digest=D("8"),
        )
        self.assertEqual(receipt["state"], ROLLBACK_READY, receipt)
        self.assertEqual(receipt["rollback_sequences"], [2, 1])
        self.assertFalse(receipt["rollback_executed_trusted"])
        self.assertFalse(receipt["new_installation_authorized"])
        terminal = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="ROLLBACK_TERMINAL",
            rollback_receipt=receipt, terminal_reopen_receipt_digest=D("9"),
            independent_final_attestor_digest=D("a"),
        )
        self.assertEqual(terminal["terminal_outcome"], ROLLBACK_CANDIDATE)
        self.assertFalse(terminal["rollback_performed"])

    def test_rollback_missing_reverse_order_or_reopen_is_unknown(self):
        p, recovery, steps = self.rollback_fixture()
        for broken in (steps[::-1], steps[:1]):
            r = build_rollback_terminal_receipt_candidate(
                p, recovery, broken, final_clean_reopen_receipt_digest=D("7"),
                independent_verifier_manifest_digest=D("8"),
            )
            self.assertEqual(r["rollback_disposition"], ROLLBACK_UNKNOWN)
        bad = copy.deepcopy(steps)
        bad[0]["verified_after_reopen"] = False
        r = build_rollback_terminal_receipt_candidate(
            p, recovery, bad, final_clean_reopen_receipt_digest=D("7"),
            independent_verifier_manifest_digest=D("8"),
        )
        self.assertEqual(r["state"], BLOCKED)

    def test_terminal_failure_requires_authoritative_no_write_and_clean_reopen(self):
        p, _, _ = self.fixture()
        fail = {
            "installation_id": p["installation_id"],
            "install_commitment_digest": p["install_commitment_digest"],
            "journal_plan_digest": p["journal_plan_digest"],
            "authoritative_failure_receipt_digest": D("1"),
            "independent_no_write_evidence_digest": D("2"),
            "no_residual_changes_reopen_receipt_digest": D("3"),
            "failure_before_first_mutation": True,
            "no_write_authoritatively_proven": True,
            "no_residual_changes_after_reopen": True,
            "ambiguity_detected": False,
        }
        good = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="TERMINAL_FAILURE",
            failure_evidence=fail, terminal_reopen_receipt_digest=D("4"),
            independent_final_attestor_digest=D("5"),
        )
        self.assertEqual(good["terminal_outcome"], FAILURE_CANDIDATE)
        bad = dict(fail, ambiguity_detected=True)
        out = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="TERMINAL_FAILURE",
            failure_evidence=bad, terminal_reopen_receipt_digest=D("4"),
            independent_final_attestor_digest=D("5"),
        )
        self.assertEqual(out["terminal_outcome"], UNKNOWN)

    def test_forged_verification_plan_cannot_remove_required_health_check(self):
        _, _, _, _, plan, rows, _ = self.verified_fixture()
        fake = copy.deepcopy(plan)
        fake["checks"] = [c for c in fake["checks"] if c["check_kind"] != "AION_RUNTIME_HEALTH_REOPEN"]
        fake["verification_plan_digest"] = _digest({
            k: fake.get(k) for k in (
                "installation_id", "journal_plan_digest", "completion_gate_digest",
                "reopen_policy_digest", "health_policy_digest",
                "independent_verifier_manifest_digest", "checks",
            )
        })
        fake_rows = [r for r in rows if "AION_RUNTIME_HEALTH_REOPEN" not in r["check_id"]]
        outcome = validate_postinstall_evidence_shape(fake, fake_rows)
        self.assertEqual(outcome["state"], BLOCKED)
        self.assertIn("MANDATORY_GLOBAL_REOPEN_SCOPE_MISSING", outcome["blockers"])

    def test_replayed_failure_evidence_from_another_installation_blocks(self):
        p, _, _ = self.fixture()
        fake = {
            "installation_id": "unrelated-install",
            "install_commitment_digest": p["install_commitment_digest"],
            "authoritative_failure_receipt_digest": D("1"),
            "independent_no_write_evidence_digest": D("2"),
            "no_residual_changes_reopen_receipt_digest": D("3"),
            "failure_before_first_mutation": True,
            "no_write_authoritatively_proven": True,
            "no_residual_changes_after_reopen": True,
            "ambiguity_detected": False,
        }
        receipt = build_terminal_install_receipt_candidate(
            installation_id=p["installation_id"], requested_disposition="TERMINAL_FAILURE",
            failure_evidence=fake, terminal_reopen_receipt_digest=D("4"),
            independent_final_attestor_digest=D("5"),
        )
        self.assertEqual(receipt["state"], BLOCKED)
        self.assertEqual(receipt["terminal_outcome"], UNKNOWN)

    def test_implementation_review_does_not_install_or_deploy(self):
        _, _, _, gate, plan, _, _ = self.verified_fixture()
        review = build_completion_implementation_review(
            gate, plan, verifier_source_digest=D("1"),
            terminal_receipt_writer_source_digest=D("2"),
            rollback_attestor_source_digest=D("3"),
        )
        self.assertEqual(review["state"], REVIEW_READY)
        for key in (
            "install_commitment_written", "journal_persisted", "installation_started",
            "files_copied", "windows_acl_modified", "startup_entry_created",
            "rollback_performed", "package_installed", "postinstall_verification_executed",
            "terminal_receipt_persisted", "github_api_called", "deploy_executed",
            "worker_activated",
        ):
            self.assertIs(review[key], False, key)

    def test_policy_makes_journal_success_insufficient(self):
        policy = completion_policy()
        self.assertIs(policy["journal_finished_means_installed"], False)
        self.assertIs(policy["shape_validation_is_physical_truth"], False)
        self.assertIs(policy["terminal_failure_with_possible_write_allowed"], False)
        self.assertIs(policy["automatic_forward_retry_after_unknown_allowed"], False)
        self.assertIs(policy["design_only"], True)

if __name__ == "__main__":
    unittest.main()
