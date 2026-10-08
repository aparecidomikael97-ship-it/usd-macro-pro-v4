"""Adversarial isolated synthetic tests, no Windows filesystem or OS interaction."""
from copy import deepcopy
import unittest

from atlasquant_aion_windows_install_completion_postinstall_rollback_receipt_v1 import (
    TERMINAL_RECEIPT_SCHEMA, TERMINAL_READY, SUCCESS_CANDIDATE,
)
from atlasquant_aion_windows_terminal_receipt_persistence_postreboot_health_v1 import (
    ATTEST_READY, BLOCKED, HEALTHY, UNHEALTHY, UNKNOWN, TERMINAL_FIELDS,
    build_terminal_receipt_write_intent, build_postreboot_verification_plan, _digest,
)
from atlasquant_aion_windows_synthetic_durable_store_reboot_harness_v1 import (
    SyntheticCASStore, synthetic_persistence_shape, simulate_postreboot_probe,
    synthetic_harness_review, SIMULATOR_POLICY, READY, STORE_COMMITTED,
    STORE_UNKNOWN, STORE_REJECTED, REOPEN_ONLY,
)

D = lambda c: "sha256:" + c * 64

class SyntheticDurableStoreRebootHarnessV1Tests(unittest.TestCase):
    def terminal(self, installation_id="synthetic-install-0001"):
        material = {
            "installation_id": installation_id,
            "requested_disposition": "SUCCESS",
            "candidate_disposition": SUCCESS_CANDIDATE,
            "completion_gate_digest": D("1"),
            "journal_plan_digest": D("2"),
            "postinstall_evidence_digest": D("3"),
            "rollback_receipt_digest": "",
            "failure_evidence_digest": "",
            "terminal_reopen_receipt_digest": D("4"),
            "independent_final_attestor_digest": D("5"),
        }
        self.assertEqual(set(material), set(TERMINAL_FIELDS))
        return {
            "schema": TERMINAL_RECEIPT_SCHEMA, "state": TERMINAL_READY,
            **material, "terminal_outcome": SUCCESS_CANDIDATE,
            "terminal_receipt_candidate_digest": _digest(material),
            "physically_installed_trusted": False,
            "aion_healthy_trusted": False,
            "terminal_disposition_persisted": False,
            "new_installation_authorized": False,
        }

    def intent(self, terminal=None, revision=7, *, nonce="d"):
        return build_terminal_receipt_write_intent(
            terminal or self.terminal(),
            owner_sid_digest=D("6"), host_identity_digest=D("7"),
            package_manifest_digest=D("8"), target_snapshot_digest=D("9"),
            terminal_writer_manifest_digest=D("a"), durable_store_identity_digest=D("b"),
            terminal_policy_digest=D("c"), write_nonce_digest=D(nonce),
            expected_terminal_state="NONE", expected_revision=revision,
        )

    def committed(self):
        t, i = self.terminal(), self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        outcome = store.apply(i)
        self.assertEqual(outcome["state"], STORE_COMMITTED, outcome)
        shape = synthetic_persistence_shape(
            store, i, outcome, verifier_manifest_digest=D("e"),
        )
        self.assertEqual(shape["state"], ATTEST_READY, shape)
        return t, i, store, outcome, shape

    def plan(self, terminal, intent, attestation):
        p = build_postreboot_verification_plan(
            terminal, intent, attestation,
            owner_acl_policy_digest=D("1"),
            startup_policy_digest=D("2"),
            runtime_identity_policy_digest=D("3"),
            runtime_health_policy_digest=D("4"),
            preboot_epoch_digest=D("5"),
            reboot_challenge_digest=D("6"),
            reboot_verifier_manifest_digest=D("7"),
            reboot_policy_digest=D("8"),
        )
        self.assertEqual(p["state"], "POSTREBOOT_VERIFICATION_PLAN_READY_UNTRUSTED", p)
        return p

    def observed(self, p, i):
        return {
            "terminal_record_key_digest": i["record_key_digest"],
            "journal_plan_digest": p["journal_plan_digest"],
            "journal_chain_valid": True,
            "host_identity_digest": p["host_identity_digest"],
            "owner_sid_digest": p["owner_sid_digest"],
            "package_manifest_digest": p["package_manifest_digest"],
            "target_snapshot_digest": p["target_snapshot_digest"],
            "owner_acl_policy_digest": p["owner_acl_policy_digest"],
            "startup_policy_digest": p["startup_policy_digest"],
            "runtime_identity_policy_digest": p["runtime_identity_policy_digest"],
            "runtime_health_policy_digest": p["runtime_health_policy_digest"],
            "runtime_handshake_ok": True,
            "unexpected_mutation": False,
            "challenge_response_digest": p["reboot_challenge_digest"],
            "challenge_response_ok": True,
        }

    def healthy(self):
        t, i, store, outcome, attestation = self.committed()
        plan = self.plan(t, i, attestation)
        snapshot = self.observed(plan, i)
        return t, i, store, plan, snapshot

    def probe(self, plan, store, snapshot, *, epoch=None, challenge=None):
        return simulate_postreboot_probe(
            plan, store, snapshot,
            simulated_boot_epoch_digest=D("9") if epoch is None else epoch,
            simulated_challenge_digest=plan["reboot_challenge_digest"] if challenge is None else challenge,
            synthetic_attestor_digest=D("c"),
        )

    def test_synthetic_commit_and_attestation_never_claims_durable_truth(self):
        _, _, store, result, a = self.committed()
        self.assertEqual(store.revision, 8)
        self.assertTrue(result["synthetic_only"])
        self.assertFalse(result["physical_write_performed"])
        self.assertFalse(a["terminal_receipt_persisted_trusted"])
        self.assertFalse(a["physical_persistence_verified"])

    def test_precommit_fault_is_authoritative_only_inside_test_fixture(self):
        i = self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        result = store.apply(i, fault="before_commit")
        self.assertEqual(result["state"], STORE_REJECTED)
        self.assertEqual(store.revision, 7)
        self.assertIsNone(store.read(i["installation_id"]))
        self.assertEqual(synthetic_persistence_shape(store, i, result, verifier_manifest_digest=D("e"))["state"], BLOCKED)

    def test_ack_loss_after_commit_is_unknown_and_no_auto_retry(self):
        i = self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        result = store.apply(i, fault="after_commit_unknown")
        self.assertEqual(result["state"], STORE_UNKNOWN)
        self.assertEqual(store.revision, 8)
        self.assertIsNotNone(store.read(i["installation_id"]))
        self.assertEqual(store.apply(i)["reason"], "UNKNOWN_WRITE_REQUIRES_SEPARATE_RECONCILIATION")
        self.assertEqual(synthetic_persistence_shape(store, i, result, verifier_manifest_digest=D("e"))["state"], BLOCKED)
        snap = store.reconcile_snapshot(i["installation_id"])
        self.assertEqual(snap["state"], REOPEN_ONLY)
        self.assertTrue(snap["ack_uncertain"])
        self.assertFalse(snap["automatic_retry_allowed"])

    def test_duplicate_identical_commit_is_read_only_denial(self):
        i = self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        store.apply(i)
        result = store.apply(i)
        self.assertEqual(result["state"], STORE_REJECTED)
        self.assertEqual(result["reason"], "TERMINAL_RECORD_ALREADY_EXISTS_READ_ONLY")
        self.assertEqual(store.revision, 8)

    def test_conflicting_terminal_for_same_install_rejected(self):
        i = self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        store.apply(i)
        other = self.intent(nonce="f", revision=8)
        self.assertEqual(store.apply(other)["state"], STORE_REJECTED)
        self.assertEqual(store.revision, 8)

    def test_stale_global_cas_revision_rejected(self):
        store = SyntheticCASStore(D("b"), initial_revision=7)
        i = self.intent(revision=6)
        self.assertEqual(store.apply(i)["reason"], "STALE_COMPARE_AND_SET_REVISION")
        self.assertEqual(store.revision, 7)

    def test_tampered_intent_refused_before_store_change(self):
        store = SyntheticCASStore(D("b"), initial_revision=7)
        i = self.intent()
        i["owner_sid_digest"] = D("f")
        self.assertEqual(store.apply(i)["reason"], "INVALID_OR_TAMPERED_WRITE_INTENT")
        self.assertEqual(store.revision, 7)

    def test_wrong_store_identity_refused(self):
        i = self.intent()
        store = SyntheticCASStore(D("c"), initial_revision=7)
        self.assertEqual(store.apply(i)["reason"], "WRONG_STORE_IDENTITY")

    def test_unrecognized_fault_mode_is_rejected(self):
        i = self.intent()
        store = SyntheticCASStore(D("b"), initial_revision=7)
        self.assertEqual(store.apply(i, fault="write_twice")["state"], STORE_REJECTED)

    def test_reopen_is_deep_copy_not_disk_persistence(self):
        t, i, store, result, att = self.committed()
        clone = store.simulated_reopen()
        cloned_record = clone.read(i["installation_id"])
        cloned_record["owner_sid_digest"] = D("f")
        self.assertEqual(store.read(i["installation_id"])["owner_sid_digest"], D("6"))
        self.assertFalse(att["terminal_receipt_persisted_trusted"])

    def test_tampered_store_record_invalidates_synthetic_receipt(self):
        t, i, store, result, att = self.committed()
        store._records[i["installation_id"]]["owner_sid_digest"] = D("f")
        a = synthetic_persistence_shape(store, i, result, verifier_manifest_digest=D("e"))
        self.assertEqual(a["state"], BLOCKED)

    def test_fresh_synthetic_health_uses_all_reboot_checks(self):
        t, i, store, plan, observed = self.healthy()
        result = self.probe(plan, store, observed)
        self.assertEqual(len(plan["checks"]), 11)
        self.assertEqual(result["postreboot_disposition"], HEALTHY, result)
        self.assertEqual(result["state"], "POSTREBOOT_HEALTH_OBSERVATION_SHAPE_CLASSIFIED_UNTRUSTED")
        self.assertFalse(result["real_postreboot_healthy"])
        self.assertFalse(result["trusted_independent_verifier_used"])
        self.assertFalse(result["actual_reboot_performed"])

    def test_missing_runtime_readback_is_unknown(self):
        _, i, store, p, s = self.healthy()
        del s["runtime_handshake_ok"]
        result = self.probe(p, store, s)
        self.assertEqual(result["state"], BLOCKED)
        self.assertEqual(result["postreboot_disposition"], UNKNOWN)

    def test_synthetic_negative_runtime_health_is_not_real_diagnosis(self):
        _, i, store, p, s = self.healthy()
        s["runtime_handshake_ok"] = False
        result = self.probe(p, store, s)
        self.assertEqual(result["postreboot_disposition"], UNHEALTHY, result)
        self.assertFalse(result["real_postreboot_healthy"])
        self.assertTrue(result["reconciliation_required"])

    def test_startup_redirection_classifies_unhealthy_candidate(self):
        _, i, store, p, s = self.healthy()
        s["startup_policy_digest"] = D("f")
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_owner_acl_change_classifies_unhealthy_candidate(self):
        _, i, store, p, s = self.healthy()
        s["owner_acl_policy_digest"] = D("f")
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_wrong_owner_host_or_package_classifies_unhealthy_candidate(self):
        for name in ("owner_sid_digest", "host_identity_digest", "package_manifest_digest"):
            _, i, store, p, s = self.healthy()
            s[name] = D("f")
            self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY, name)

    def test_process_version_mismatch_blocks_healthy_claim(self):
        _, i, store, p, s = self.healthy()
        s["runtime_identity_policy_digest"] = D("f")
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_missing_real_reboot_epoch_change_is_unknown(self):
        _, i, store, p, s = self.healthy()
        result = self.probe(p, store, s, epoch=p["preboot_epoch_digest"])
        self.assertEqual(result["postreboot_disposition"], UNKNOWN)

    def test_old_challenge_replay_blocks(self):
        _, i, store, p, s = self.healthy()
        result = self.probe(p, store, s, challenge=D("f"))
        self.assertEqual(result["postreboot_disposition"], UNKNOWN)

    def test_unexpected_mutation_classifies_unhealthy(self):
        _, i, store, p, s = self.healthy()
        s["unexpected_mutation"] = True
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_journal_reopen_failed_classifies_unhealthy(self):
        _, i, store, p, s = self.healthy()
        s["journal_chain_valid"] = False
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_tampered_terminal_record_blocks_success_candidate(self):
        _, i, store, p, s = self.healthy()
        store._records[i["installation_id"]]["terminal_candidate_digest"] = D("f")
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNHEALTHY)

    def test_missing_synthetic_store_record_is_not_health(self):
        _, i, store, p, s = self.healthy()
        del store._records[i["installation_id"]]
        self.assertEqual(self.probe(p, store, s)["postreboot_disposition"], UNKNOWN)

    def test_simulated_harness_review_never_authorizes_real_install(self):
        review = synthetic_harness_review(
            test_cases_passed=24, test_cases_expected=24,
            source_digest=D("1"), test_digest=D("2"),
        )
        self.assertEqual(review["state"], READY)
        self.assertFalse(review["ready_for_real_windows_install"])
        self.assertFalse(review["physical_durable_store_used"])
        self.assertFalse(review["worker_activated"])
        self.assertEqual(synthetic_harness_review(
            test_cases_passed=23, test_cases_expected=24,
            source_digest=D("1"), test_digest=D("2"),
        )["state"], BLOCKED)

    def test_policy_remains_in_memory_and_never_launches(self):
        self.assertTrue(SIMULATOR_POLICY["test_only"])
        for key in ("physical_durable_store_used", "physical_windows_reads_used",
                    "real_windows_reboot_performed", "trusted_witness_generated",
                    "terminal_receipt_persisted", "package_installed",
                    "github_api_called", "deploy_executed", "worker_activated"):
            self.assertFalse(SIMULATOR_POLICY[key], key)

if __name__ == "__main__":
    unittest.main()
