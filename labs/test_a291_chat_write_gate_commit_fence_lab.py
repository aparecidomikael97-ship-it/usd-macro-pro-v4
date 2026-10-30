"""A291 LAB: real staged-chat COMMIT fence plus cooperative authorizer."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Message
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a291_chat_write_gate_commit_fence_lab import (
    SCHEMA, SCOPE, FAULTS, LocalChatCommitWriteGate,
    probe_normal_fenced_gate, probe_commit_ack_loss,
    probe_raw_same_handle_authorizer_uninstall,
)


class A291ChatWriteGateCommitFenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normal = probe_normal_fenced_gate()
        cls.before = probe_commit_ack_loss(phase="before")
        cls.after = probe_commit_ack_loss(phase="after")
        cls.bypass = probe_raw_same_handle_authorizer_uninstall()

    def test_01_actual_sqlite_chat_normal_commit_and_read(self):
        self.assertEqual(self.normal["schema"], SCHEMA)
        self.assertTrue(self.normal["real_staging_store"])
        self.assertEqual(self.normal["message_sequence"], 1)
        self.assertEqual(self.normal["external_read_count"], 1)

    def test_02_normal_commit_marker_cleared_on_ack(self):
        self.assertTrue(self.normal["store_healthy"])
        self.assertFalse(self.normal["pending_marker_after_ack"])

    def test_03_raw_sql_write_is_denied_after_valid_chat_commit(self):
        self.assertTrue(self.normal["direct_raw_write_denied"])
        self.assertGreaterEqual(self.normal["update_authorizer_checks"], 1)
        self.assertTrue(self.normal["cached_sql_authorizer_rearmed"])

    def test_04_before_commit_fault_is_uncertain_and_blocked(self):
        self.assertTrue(self.before["uncertain_error_raised"])
        self.assertEqual(self.before["synthetic_phase"], "before")
        self.assertEqual(self.before["committed_count_visible_externally"], 0)
        self.assertTrue(self.before["health_failed_sticky"])

    def test_05_after_commit_ack_loss_leaves_actual_durable_sql_row(self):
        self.assertTrue(self.after["uncertain_error_raised"])
        self.assertEqual(self.after["synthetic_phase"], "after")
        self.assertEqual(self.after["committed_count_visible_externally"], 1)
        self.assertTrue(self.after["health_failed_sticky"])

    def test_06_both_fault_phases_leave_commit_marker(self):
        for p in (self.before, self.after):
            self.assertTrue(p["pending_commit_marker_persists"])
            self.assertEqual(
                p["initial_uncertain_reason"],
                "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
            )
            self.assertEqual(
                p["health_after_marker_reason"],
                "MESSAGE_COMMIT_PENDING_ZERO_AUTO_RETRY",
            )

    def test_07_uncertain_commit_denies_same_handle_auto_retry(self):
        for p in (self.before, self.after):
            self.assertTrue(p["retry_denied"])
            self.assertEqual(
                p["message_count_after_denied_retry"],
                p["committed_count_visible_externally"],
            )
            self.assertTrue(p["rearm_after_unknown_commit"])

    def test_08_restart_is_denied_until_external_manual_review(self):
        for p in (self.before, self.after):
            self.assertTrue(p["restart_denied_by_local_marker"])

    def test_09_real_authorizer_can_be_uninstalled_by_same_process(self):
        self.assertTrue(
            self.bypass["authorizer_uninstalled_by_same_process"]
        )
        self.assertTrue(self.bypass["write_bypassed_local_gate"])
        self.assertTrue(self.bypass["no_independent_capability"])

    def test_10_same_handle_data_version_cannot_detect_direct_bypass(self):
        self.assertTrue(
            self.bypass["same_handle_data_version_cannot_attest"]
        )

    def test_11_guarded_normal_read_keeps_scope(self):
        with TemporaryDirectory(prefix="a291-scope-") as raw:
            gate = LocalChatCommitWriteGate(Path(raw) / "staging.db")
            try:
                c = gate.create_conversation("scoped")
                self.assertEqual(gate.get_conversation(c.id).id, c.id)
                self.assertEqual(gate.list_messages(c.id).items, [])
                self.assertEqual(gate.storage_health()["state"], HEALTHY)
            finally:
                gate.close()

    def test_12_same_prepared_update_is_denied_after_cache_rearm(self):
        with TemporaryDirectory(prefix="a291-cache-") as raw:
            gate = LocalChatCommitWriteGate(Path(raw) / "staging.db")
            try:
                c = gate.create_conversation("cached")
                gate.append_message(
                    Message(c.id, "user", "trusted", id="a291-cached")
                )
                row = gate._store.db.execute(
                    "SELECT updated, archived, title, data "
                    "FROM conversations WHERE id=?", (c.id,)
                ).fetchone()
                sql = (
                    "UPDATE conversations SET "
                    "updated=?,archived=?,title=?,data=? WHERE id=?"
                )
                with self.assertRaises(sqlite3.DatabaseError):
                    gate._store.db.execute(
                        sql, (row["updated"], row["archived"],
                              "forbidden", row["data"], c.id)
                    )
                self.assertEqual(gate.get_conversation(c.id).message_count, 1)
            finally:
                gate.close()

    def test_13_wrong_synthetic_ack_phase_rejected(self):
        with TemporaryDirectory(prefix="a291-type-") as raw:
            gate = LocalChatCommitWriteGate(
                Path(raw) / "staging.db", ack_loss_connection=True
            )
            try:
                for invalid in (None, 0, True, "", "unknown", [], {}):
                    with self.subTest(invalid=repr(invalid)):
                        with self.assertRaises(ValueError):
                            gate.trigger_ack_loss_once(invalid)
            finally:
                gate.close()

    def test_14_ack_loss_not_available_on_ordinary_connection(self):
        with TemporaryDirectory(prefix="a291-nofault-") as raw:
            gate = LocalChatCommitWriteGate(Path(raw) / "staging.db")
            try:
                with self.assertRaises(RuntimeError):
                    gate.trigger_ack_loss_once("after")
            finally:
                gate.close()

    def test_15_nested_write_grant_not_authorized(self):
        with TemporaryDirectory(prefix="a291-nested-") as raw:
            gate = LocalChatCommitWriteGate(Path(raw) / "staging.db")
            try:
                with gate._authorized_store_method():
                    with self.assertRaises(StorageUnavailableError):
                        with gate._authorized_store_method():
                            pass
                c = gate.create_conversation("after-nested")
                self.assertEqual(gate.get_conversation(c.id).id, c.id)
            finally:
                gate.close()

    def test_16_facade_closed_denies_calls(self):
        with TemporaryDirectory(prefix="a291-closed-") as raw:
            gate = LocalChatCommitWriteGate(Path(raw) / "staging.db")
            gate.close()
            with self.assertRaises(StorageUnavailableError):
                gate.create_conversation("denied")
            with self.assertRaises(StorageUnavailableError):
                gate.storage_health()

    def test_17_ack_loss_constructor_rejects_truthy_non_bool(self):
        with TemporaryDirectory(prefix="a291-init-") as raw:
            path = Path(raw) / "staging.db"
            for invalid in (None, 0, 1, "true", [], {}):
                with self.subTest(invalid=repr(invalid)):
                    with self.assertRaises(TypeError):
                        LocalChatCommitWriteGate(
                            path, ack_loss_connection=invalid
                        )
            self.assertFalse(path.exists())

    def test_18_all_probes_keep_hard_no_go_and_no_external_effect(self):
        for p in (self.normal, self.before, self.after, self.bypass):
            self.assertTrue(p["research_only"])
            self.assertTrue(p["native_sqlite"])
            self.assertTrue(p["zero_auto_resend"])
            self.assertTrue(p["no_provider_worker_deploy_orders"])
            self.assertTrue(p["no_external_effect_or_real_receipt"])
            self.assertFalse(p["can_authorize_send"])
            self.assertFalse(p["off_host_rollback_floor"])
            self.assertFalse(p["independent_owner_proof"])
            self.assertEqual(p["p0_homologated"], 0)


if __name__ == "__main__":
    unittest.main()
