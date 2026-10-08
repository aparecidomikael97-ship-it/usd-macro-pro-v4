"""GitHub-hosted Windows scratch-disk integration tests, NOT owner-PC tests.

Only this test file exercises real SQLite file creation in RUNNER_TEMP.
No install target, ACL, Registry, startup, service, reboot, or deployment.
"""
import os
import sqlite3
import unittest
from unittest.mock import patch
from pathlib import Path

from atlasquant_aion_windows_install_completion_postinstall_rollback_receipt_v1 import (
    TERMINAL_READY, TERMINAL_RECEIPT_SCHEMA, SUCCESS_CANDIDATE,
)
from atlasquant_aion_windows_terminal_receipt_persistence_postreboot_health_v1 import (
    ATTEST_READY, _digest, build_terminal_receipt_write_intent,
)
from atlasquant_aion_windows_ci_ephemeral_sqlite_native_readback_v1 import (
    WindowsCIEphemeralSQLite, CAS_APPLIED, CAS_REJECTED, CAS_UNKNOWN,
    READBACK_MATCHED, READBACK_UNKNOWN, POLICY, GUARD_REQUIRED,
)

D = lambda c: "sha256:" + c * 64

class WindowsCIEphemeralDiskReceiptV1Tests(unittest.TestCase):
    def terminal(self, installation_id="ci-test-install-0001"):
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
        return {
            "schema": TERMINAL_RECEIPT_SCHEMA, "state": TERMINAL_READY,
            **material, "terminal_outcome": SUCCESS_CANDIDATE,
            "terminal_receipt_candidate_digest": _digest(material),
            "physically_installed_trusted": False,
            "aion_healthy_trusted": False,
            "terminal_disposition_persisted": False,
            "new_installation_authorized": False,
        }

    def intent(self, *, installation_id="ci-test-install-0001", revision=7, nonce="d"):
        return build_terminal_receipt_write_intent(
            self.terminal(installation_id),
            owner_sid_digest=D("6"), host_identity_digest=D("7"),
            package_manifest_digest=D("8"), target_snapshot_digest=D("9"),
            terminal_writer_manifest_digest=D("a"),
            durable_store_identity_digest=D("b"),
            terminal_policy_digest=D("c"), write_nonce_digest=D(nonce),
            expected_terminal_state="NONE", expected_revision=revision,
        )

    def store(self):
        return WindowsCIEphemeralSQLite(D("b"), initial_revision=7)

    def test_guard_fails_if_not_github_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                self.store()

    def test_guard_fails_if_not_windows_runner_claim(self):
        with patch.dict(os.environ, {"RUNNER_OS": "Linux"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                self.store()

    def test_guard_fails_if_runner_temp_missing(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": ""}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                self.store()

    def test_guard_fails_without_explicit_ci_test_switch(self):
        with patch.dict(os.environ, {"AION_CI_EPHEMERAL_DISK_TEST": "0"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                self.store()

    def test_guard_fails_for_workflow_dispatch_without_pr(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            with self.assertRaisesRegex(RuntimeError, GUARD_REQUIRED):
                self.store()

    def test_empty_store_reopen_before_cas(self):
        with self.store() as s:
            self.assertIsNone(s.read_reopen("ci-test-install-0001"))
            self.assertEqual(s.revision_reopen(), 7)
            self.assertTrue(s._root.is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()))

    def test_real_ci_disk_cas_reopens_as_untrusted(self):
        with self.store() as s:
            i = self.intent()
            out = s.commit(i)
            self.assertEqual(out["state"], CAS_APPLIED, out)
            self.assertTrue(s._db.is_file())
            self.assertEqual(s.revision_reopen(), 8)
            stored = s.read_reopen(i["installation_id"])
            self.assertEqual(stored["owner_sid_digest"], i["owner_sid_digest"])
            evidence = s.reconcile_reopen(i)
            self.assertEqual(evidence["state"], READBACK_MATCHED)
            self.assertFalse(evidence["power_loss_durability_proven"])
            attestation = s.attestation_envelope_untrusted(
                i, out, synthetic_verifier_manifest_digest=D("e"),
            )
            self.assertEqual(attestation["state"], ATTEST_READY, attestation)
            self.assertFalse(attestation["terminal_receipt_persisted_trusted"])
            self.assertFalse(attestation["independent_windows_attestor_trusted"])
            self.assertFalse(attestation["actual_windows_installation_verified"])

    def test_sqlite_scratch_dir_removed_on_context_exit(self):
        with self.store() as s:
            root = s._root
            self.assertTrue(root.exists())
            self.assertEqual(s.commit(self.intent())["state"], CAS_APPLIED)
        self.assertFalse(root.exists())

    def test_sqlite_cleanup_on_exception(self):
        root = None
        with self.assertRaisesRegex(ValueError, "synthetic abort"):
            with self.store() as s:
                root = s._root
                raise ValueError("synthetic abort")
        self.assertIsNotNone(root)
        self.assertFalse(root.exists())

    def test_before_commit_fault_rolls_back(self):
        with self.store() as s:
            i = self.intent()
            out = s.commit(i, fault="before_commit")
            self.assertEqual(out["state"], CAS_REJECTED)
            self.assertIsNone(s.read_reopen(i["installation_id"]))
            self.assertEqual(s.revision_reopen(), 7)

    def test_ack_loss_after_real_ci_commit_must_not_retry(self):
        with self.store() as s:
            i = self.intent()
            out = s.commit(i, fault="after_commit_ack_loss")
            self.assertEqual(out["state"], CAS_UNKNOWN)
            self.assertFalse(out["automatic_retry_allowed"])
            self.assertEqual(s.revision_reopen(), 8)
            self.assertTrue(s.reconcile_reopen(i)["unknown_ack_in_memory"])
            self.assertEqual(s.commit(i)["reason"], "ACK_UNKNOWN_REQUIRES_RECONCILIATION")
            self.assertEqual(s.attestation_envelope_untrusted(
                i, out, synthetic_verifier_manifest_digest=D("e"),
            )["state"], READBACK_UNKNOWN)

    def test_duplicate_same_intent_no_second_write(self):
        with self.store() as s:
            i = self.intent()
            s.commit(i)
            second = s.commit(i)
            self.assertEqual(second["state"], CAS_REJECTED)
            self.assertEqual(second["reason"], "TERMINAL_ALREADY_ASSIGNED")
            self.assertEqual(s.revision_reopen(), 8)

    def test_conflicting_nonce_cannot_replace_immutable_record(self):
        with self.store() as s:
            s.commit(self.intent())
            conflict = self.intent(nonce="f", revision=8)
            out = s.commit(conflict)
            self.assertEqual(out["state"], CAS_REJECTED)
            self.assertEqual(s.revision_reopen(), 8)

    def test_stale_revision_is_rejected(self):
        with self.store() as s:
            result = s.commit(self.intent(revision=6))
            self.assertEqual(result["reason"], "STALE_CAS_REVISION")
            self.assertEqual(s.revision_reopen(), 7)

    def test_tampered_digest_fails_before_write(self):
        with self.store() as s:
            i = self.intent()
            i["owner_sid_digest"] = D("f")
            self.assertEqual(s.commit(i)["reason"], "INVALID_OR_FOREIGN_INTENT")
            self.assertIsNone(s.read_reopen("ci-test-install-0001"))

    def test_intent_schema_mismatch_rejected(self):
        with self.store() as s:
            i = self.intent()
            i["schema"] = "SPOOFED"
            self.assertEqual(s.commit(i)["state"], CAS_REJECTED)

    def test_foreign_store_identity_rejected(self):
        with self.store() as s:
            i = self.intent()
            i["durable_store_identity_digest"] = D("f")
            self.assertEqual(s.commit(i)["state"], CAS_REJECTED)

    def test_invalid_fault_mode_rejected(self):
        with self.store() as s:
            self.assertEqual(s.commit(self.intent(), fault="real_install")["state"], CAS_REJECTED)
            self.assertEqual(s.revision_reopen(), 7)

    def test_conflicting_installations_require_latest_revision(self):
        with self.store() as s:
            first = self.intent()
            self.assertEqual(s.commit(first)["state"], CAS_APPLIED)
            stale = self.intent(installation_id="ci-test-install-0002", revision=7)
            self.assertEqual(s.commit(stale)["state"], CAS_REJECTED)
            second = self.intent(installation_id="ci-test-install-0002", revision=8, nonce="e")
            self.assertEqual(s.commit(second)["state"], CAS_APPLIED)
            self.assertEqual(s.revision_reopen(), 9)

    def test_disk_record_mutation_is_detected_on_reopen(self):
        with self.store() as s:
            i = self.intent()
            result = s.commit(i)
            with s._connect() as conn:
                conn.execute(
                    "UPDATE receipts SET owner_sid_digest=? WHERE installation_id=?",
                    (D("f"), i["installation_id"]),
                )
            self.assertEqual(s.reconcile_reopen(i)["state"], READBACK_UNKNOWN)
            self.assertEqual(s.attestation_envelope_untrusted(
                i, result, synthetic_verifier_manifest_digest=D("e"),
            )["state"], READBACK_UNKNOWN)

    def test_missing_record_must_not_be_success(self):
        with self.store() as s:
            i = self.intent()
            result = s.commit(i)
            with s._connect() as conn:
                conn.execute("DELETE FROM receipts WHERE installation_id=?", (i["installation_id"],))
            self.assertEqual(s.reconcile_reopen(i)["state"], READBACK_UNKNOWN)
            self.assertEqual(s.attestation_envelope_untrusted(
                i, result, synthetic_verifier_manifest_digest=D("e"),
            )["state"], READBACK_UNKNOWN)

    def test_no_independent_attestor_no_envelope(self):
        with self.store() as s:
            i = self.intent()
            result = s.commit(i)
            self.assertEqual(s.attestation_envelope_untrusted(
                i, result, synthetic_verifier_manifest_digest="",
            )["state"], READBACK_UNKNOWN)

    def test_all_runtime_and_production_effects_explicitly_denied(self):
        self.assertTrue(POLICY["physical_ci_disk_write_can_occur"])
        self.assertTrue(POLICY["test_only"])
        for key in (
            "owner_workstation_writes_allowed", "production_store_connected",
            "install_target_accessed", "windows_registry_changed",
            "windows_acl_changed", "startup_entry_changed", "service_created",
            "reboot_performed", "package_installed", "owner_authorization_consumed",
            "install_token_consumed", "real_aion_started",
            "aion_health_attested", "physical_install_trusted",
            "durable_power_loss_verified", "production_receipt_persisted",
            "independent_windows_attestor_implemented",
            "automatic_retry_after_unknown_allowed", "deploy_executed",
            "worker_activated",
        ):
            self.assertIs(POLICY[key], False, key)

if __name__ == "__main__":
    unittest.main()
