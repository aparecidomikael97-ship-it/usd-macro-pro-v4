"""Synthetic adversarial tests only. No real store, install, restart, or probe."""
import copy
import unittest

from atlasquant_aion_windows_install_completion_postinstall_rollback_receipt_v1 import (
    TERMINAL_RECEIPT_SCHEMA, TERMINAL_READY, SUCCESS_CANDIDATE,
    FAILURE_CANDIDATE,
)
from atlasquant_aion_windows_terminal_receipt_persistence_postreboot_health_v1 import (
    INTENT_READY, ATTEST_READY, REBOOT_READY, OBS_READY, REVIEW_READY,
    BLOCKED, HEALTHY, UNHEALTHY, UNKNOWN, INTENT_FIELDS,
    TERMINAL_FIELDS, REBOOT_FIELDS,
    build_terminal_receipt_write_intent,
    validate_terminal_persistence_attestation_shape,
    build_postreboot_verification_plan,
    classify_postreboot_health_evidence,
    build_consumer_implementation_review,
    terminal_reboot_policy, _digest,
)

D = lambda c: "sha256:" + c * 64

class TerminalReceiptPersistencePostrebootHealthV1Tests(unittest.TestCase):
    def terminal(self, outcome=SUCCESS_CANDIDATE):
        material = {
            "installation_id": "install-synthetic-777",
            "requested_disposition": "SUCCESS" if outcome == SUCCESS_CANDIDATE else "TERMINAL_FAILURE",
            "candidate_disposition": outcome,
            "completion_gate_digest": D("1"),
            "journal_plan_digest": D("2"),
            "postinstall_evidence_digest": D("3"),
            "rollback_receipt_digest": "",
            "failure_evidence_digest": "",
            "terminal_reopen_receipt_digest": D("4"),
            "independent_final_attestor_digest": D("5"),
        }
        assert set(material) == set(TERMINAL_FIELDS)
        return {
            "schema": TERMINAL_RECEIPT_SCHEMA,
            "state": TERMINAL_READY,
            **material,
            "terminal_outcome": outcome,
            "terminal_receipt_candidate_digest": _digest(material),
            "physically_installed_trusted": False,
            "aion_healthy_trusted": False,
            "terminal_disposition_persisted": False,
            "new_installation_authorized": False,
        }

    def intent(self, terminal=None):
        return build_terminal_receipt_write_intent(
            terminal if terminal is not None else self.terminal(),
            owner_sid_digest=D("6"),
            host_identity_digest=D("7"),
            package_manifest_digest=D("8"),
            target_snapshot_digest=D("9"),
            terminal_writer_manifest_digest=D("a"),
            durable_store_identity_digest=D("b"),
            terminal_policy_digest=D("c"),
            write_nonce_digest=D("d"),
            expected_terminal_state="NONE",
            expected_revision=7,
        )

    def attestation(self, intent=None, **overrides):
        i = intent if intent is not None else self.intent()
        fields = {
            "observed_record_digest": D("1"),
            "cas_write_receipt_digest": D("2"),
            "cas_observation_digest": D("3"),
            "read_after_write_digest": D("4"),
            "independent_reopen_digest": D("5"),
            "independent_verifier_manifest_digest": D("6"),
            "observed_prior_state": "NONE",
            "observed_prior_revision": 7,
            "observed_terminal_state": i["committed_terminal_state_if_written"],
            "observed_revision": i["next_revision_if_written"],
            "observed_installation_id": i["installation_id"],
            "observed_record_key_digest": i["record_key_digest"],
            "observed_terminal_candidate_digest": i["terminal_candidate_digest"],
            "observed_owner_sid_digest": i["owner_sid_digest"],
            "observed_host_identity_digest": i["host_identity_digest"],
            "observed_terminal_outcome": i["terminal_outcome"],
            "write_attempt_nonce_digest": i["write_nonce_digest"],
        }
        fields.update(overrides)
        return validate_terminal_persistence_attestation_shape(i, **fields)

    def plan(self, terminal=None, intent=None, attestation=None):
        t = terminal if terminal is not None else self.terminal()
        i = intent if intent is not None else self.intent(t)
        a = attestation if attestation is not None else self.attestation(i)
        return build_postreboot_verification_plan(
            t, i, a,
            owner_acl_policy_digest=D("1"),
            startup_policy_digest=D("2"),
            runtime_identity_policy_digest=D("3"),
            runtime_health_policy_digest=D("4"),
            preboot_epoch_digest=D("5"),
            reboot_challenge_digest=D("6"),
            reboot_verifier_manifest_digest=D("7"),
            reboot_policy_digest=D("8"),
        )

    def rows(self, plan=None):
        p = plan if plan is not None else self.plan()
        return [{
            "check_id": check["check_id"],
            "proof_binding_digest": check["expected_proof_binding_digest"],
            "observed_postboot_epoch_digest": D("9"),
            "observed_challenge_digest": p["reboot_challenge_digest"],
            "reopened_after_reboot": True,
            "independent_verifier_observed": True,
            "independent_readback_receipt_digest": D("a"),
            "result": "VERIFIED_POSITIVE",
            "ambiguity_detected": False,
        } for check in p["checks"]]

    def classify(self, plan=None, rows=None, result="HEALTHY", epoch=None, challenge=None):
        p = plan if plan is not None else self.plan()
        return classify_postreboot_health_evidence(
            p, rows if rows is not None else self.rows(p),
            observed_postboot_epoch_digest=epoch if epoch is not None else D("9"),
            observed_challenge_digest=challenge if challenge is not None else p["reboot_challenge_digest"],
            independent_reboot_attestor_digest=D("b"), requested_result=result,
        )

    def test_terminal_write_intent_valid_but_writes_nothing(self):
        intent = self.intent()
        self.assertEqual(intent["state"], INTENT_READY, intent)
        self.assertEqual(intent["committed_terminal_state_if_written"], SUCCESS_CANDIDATE)
        self.assertEqual(intent["next_revision_if_written"], 8)
        self.assertFalse(intent["durable_write_executed"])
        self.assertFalse(intent["terminal_receipt_persisted"])
        self.assertEqual(intent["write_intent_digest"], _digest({
            k: intent[k] for k in INTENT_FIELDS
        }))

    def test_upstream_digest_tamper_is_blocked(self):
        terminal = self.terminal()
        terminal["journal_plan_digest"] = D("f")
        out = self.intent(terminal)
        self.assertEqual(out["state"], BLOCKED)
        self.assertIn("TERMINAL_CANDIDATE_DIGEST_MISMATCH", out["blockers"])

    def test_upstream_trust_claim_blocks(self):
        terminal = self.terminal()
        terminal["terminal_disposition_persisted"] = True
        self.assertEqual(self.intent(terminal)["state"], BLOCKED)

    def test_cas_expected_none_and_revision_required(self):
        i = self.intent()
        t = self.terminal()
        self.assertEqual(i["state"], INTENT_READY)
        for state, revision in (("EXISTS", 7), ("NONE", -1), ("NONE", True), ("NONE", 1.5)):
            out = build_terminal_receipt_write_intent(
                t, owner_sid_digest=D("6"), host_identity_digest=D("7"),
                package_manifest_digest=D("8"), target_snapshot_digest=D("9"),
                terminal_writer_manifest_digest=D("a"), durable_store_identity_digest=D("b"),
                terminal_policy_digest=D("c"), write_nonce_digest=D("d"),
                expected_terminal_state=state, expected_revision=revision,
            )
            self.assertEqual(out["state"], BLOCKED)

    def test_missing_persistence_receipts_block(self):
        out = self.attestation(cas_write_receipt_digest="")
        self.assertEqual(out["state"], BLOCKED)
        self.assertFalse(out["terminal_receipt_persisted_trusted"])
        out = self.attestation(independent_reopen_digest="")
        self.assertEqual(out["state"], BLOCKED)

    def test_cas_replayed_or_revision_mismatch_block(self):
        self.assertEqual(self.attestation(observed_prior_state="COMMITTED")["state"], BLOCKED)
        self.assertEqual(self.attestation(observed_revision=10)["state"], BLOCKED)
        self.assertEqual(self.attestation(observed_prior_revision=6)["state"], BLOCKED)

    def test_cross_install_or_owner_replay_is_rejected(self):
        self.assertEqual(self.attestation(observed_installation_id="another-install")["state"], BLOCKED)
        self.assertEqual(self.attestation(observed_owner_sid_digest=D("f"))["state"], BLOCKED)
        self.assertEqual(self.attestation(write_attempt_nonce_digest=D("f"))["state"], BLOCKED)

    def test_shape_attestation_can_never_claim_real_persistence(self):
        a = self.attestation()
        self.assertEqual(a["state"], ATTEST_READY, a)
        self.assertFalse(a["terminal_receipt_persisted_trusted"])
        self.assertFalse(a["cas_durably_verified"])
        self.assertFalse(a["reopen_physically_verified"])

    def test_self_claim_of_trust_is_blocked(self):
        self.assertEqual(self.attestation(caller_claims_trusted=True)["state"], BLOCKED)

    def test_reboot_plan_rejects_terminal_failure_candidate(self):
        t = self.terminal(FAILURE_CANDIDATE)
        out = self.plan(t, self.intent(t), self.attestation(self.intent(t)))
        self.assertEqual(out["state"], BLOCKED)

    def test_postreboot_plan_lists_all_health_checks_without_reboot(self):
        p = self.plan()
        self.assertEqual(p["state"], REBOOT_READY, p)
        self.assertEqual(len(p["checks"]), 11)
        self.assertFalse(p["actual_reboot_observed"])
        self.assertFalse(p["postreboot_health_trusted"])

    def test_complete_positive_evidence_is_untrusted_healthy_candidate(self):
        result = self.classify()
        self.assertEqual(result["state"], OBS_READY, result)
        self.assertEqual(result["postreboot_disposition"], HEALTHY)
        self.assertFalse(result["reboot_health_verified_trusted"])
        self.assertFalse(result["installation_healthy_trusted"])

    def test_missing_runtime_health_or_startup_check_blocks(self):
        p = self.plan()
        for kind in ("AION_RUNTIME_HANDSHAKE_HEALTH", "STARTUP_ENTRY_TARGET_READBACK"):
            rows = [r for r in self.rows(p) if r["check_id"] != kind]
            out = self.classify(plan=p, rows=rows)
            self.assertEqual(out["postreboot_disposition"], UNKNOWN, kind)
            self.assertEqual(out["state"], BLOCKED)

    def test_replay_same_boot_epoch_and_challenge_mismatch_block(self):
        p = self.plan()
        self.assertEqual(self.classify(plan=p, epoch=p["preboot_epoch_digest"])["state"], BLOCKED)
        self.assertEqual(self.classify(plan=p, challenge=D("f"))["state"], BLOCKED)

    def test_cross_boot_replay_in_row_blocks(self):
        p = self.plan()
        rows = self.rows(p)
        rows[0]["observed_postboot_epoch_digest"] = D("f")
        self.assertEqual(self.classify(plan=p, rows=rows)["state"], BLOCKED)

    def test_mismatched_plan_hash_and_digest_block(self):
        p = self.plan()
        p["owner_sid_digest"] = D("f")
        self.assertEqual(self.classify(plan=p)["state"], BLOCKED)

    def test_verified_negative_requires_authoritative_evidence(self):
        p = self.plan()
        rows = self.rows(p)
        rows[8]["result"] = "VERIFIED_NEGATIVE"
        neg = self.classify(plan=p, rows=rows, result="UNHEALTHY")
        self.assertEqual(neg["state"], BLOCKED)
        self.assertEqual(neg["postreboot_disposition"], UNKNOWN)
        rows[8]["authoritative_negative_evidence_digest"] = D("f")
        neg = self.classify(plan=p, rows=rows, result="UNHEALTHY")
        self.assertEqual(neg["postreboot_disposition"], UNHEALTHY)
        self.assertFalse(neg["reboot_health_verified_trusted"])
        self.assertTrue(neg["reconciliation_required"])

    def test_contradictory_requested_healthy_with_failure_is_unknown(self):
        p = self.plan()
        rows = self.rows(p)
        rows[8]["result"] = "VERIFIED_NEGATIVE"
        rows[8]["authoritative_negative_evidence_digest"] = D("f")
        self.assertEqual(self.classify(plan=p, rows=rows)["postreboot_disposition"], UNKNOWN)

    def test_incomplete_or_ambiguous_probe_cannot_be_clean_unhealthy(self):
        p = self.plan()
        rows = self.rows(p)
        rows[8]["result"] = "UNKNOWN"
        self.assertEqual(self.classify(plan=p, rows=rows, result="UNHEALTHY")["postreboot_disposition"], UNKNOWN)
        rows[8]["result"] = "VERIFIED_POSITIVE"
        rows[8]["ambiguity_detected"] = True
        self.assertEqual(self.classify(plan=p, rows=rows)["state"], BLOCKED)

    def test_implementation_review_only_readiness_and_no_side_effect(self):
        i, p = self.intent(), self.plan()
        review = build_consumer_implementation_review(
            i, p, durable_writer_source_digest=D("1"),
            independent_reopen_verifier_source_digest=D("2"),
            postreboot_health_consumer_source_digest=D("3"),
        )
        self.assertEqual(review["state"], REVIEW_READY, review)
        for flag in ("terminal_receipt_persisted", "terminal_cas_executed",
                     "reopened_terminal_record", "reboot_executed",
                     "postreboot_health_trusted", "owner_authorization_consumed",
                     "files_copied", "windows_acl_modified", "process_spawned",
                     "deploy_executed", "worker_activated"):
            self.assertFalse(review[flag], flag)

    def test_policy_explicitly_denies_success_inference_and_auto_reinstall(self):
        policy = terminal_reboot_policy()
        self.assertFalse(policy["terminal_candidate_is_durable_receipt"])
        self.assertFalse(policy["durable_receipt_means_healthy_after_reboot"])
        self.assertFalse(policy["automatic_reinstall_on_unhealthy_allowed"])
        self.assertFalse(policy["unknown_is_healthy"])
        self.assertTrue(policy["design_only"])

if __name__ == "__main__":
    unittest.main()
