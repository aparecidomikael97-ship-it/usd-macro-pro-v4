"""A287: deterministic SQLite native read-interleaving negative tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aion_chat.models import Scope
from aion_chat.store import HEALTHY, SQLiteChatStore, StorageUnavailableError
from labs.a287_sqlite_read_race_probe import (
    ENDPOINTS, SCHEMA, SCOPE, _foreign_commit,
    postcheck_read_candidate, probe_last_moment_postcheck_gap,
    probe_reader_interleaving,
)


class A287SQLiteLocalReadInterleavingTests(unittest.TestCase):
    def test_01_all_existing_read_endpoints_return_after_external_commit(self):
        for endpoint in sorted(ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(endpoint=endpoint)
                self.assertEqual(p["schema"], SCHEMA)
                self.assertTrue(p["injected_external_commit"])
                self.assertEqual(p["status"], "RETURNED")
                self.assertTrue(p["counter_changed"])
                self.assertEqual(p["store_health_before_followup"], HEALTHY)

    def test_02_get_and_list_conversation_can_return_foreign_mutation(self):
        for endpoint in ("get_conversation", "list_conversations"):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(endpoint=endpoint)
                self.assertTrue(p["returned_foreign_title"])
                self.assertEqual(
                    p["store_reason_after_followup"], "LOCAL_DATA_VERSION_CHANGED"
                )

    def test_03_new_postcheck_candidate_denies_all_six_interleavings(self):
        for endpoint in sorted(ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(endpoint=endpoint, postcheck=True)
                self.assertEqual(p["status"], "DENIED_AFTER_EXTERNAL_COMMIT")
                self.assertFalse(p["returned_foreign_title"])
                self.assertEqual(
                    p["store_health_before_followup"], "failed"
                )
                self.assertEqual(
                    p["store_reason_after_followup"], "LOCAL_DATA_VERSION_CHANGED"
                )

    def test_04_same_inode_and_native_integrity_do_not_establish_history(self):
        for endpoint in sorted(ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(endpoint=endpoint)
                self.assertTrue(p["same_path_inode"])
                self.assertTrue(p["quick_check_ok"])
                self.assertFalse(p["native_fd_authenticated"])
                self.assertFalse(p["off_host_rollback_witness"])
                self.assertFalse(p["antirollback_proven"])

    def test_05_late_health_sees_external_commit_even_when_read_returned(self):
        p = probe_reader_interleaving(endpoint="get_message")
        self.assertEqual(p["store_health_after_followup"], "failed")
        self.assertEqual(
            p["store_reason_after_followup"], "LOCAL_DATA_VERSION_CHANGED"
        )

    def test_06_postcheck_candidate_works_when_no_other_writer_commits(self):
        with TemporaryDirectory(prefix="a287-clean-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                c = store.create_conversation(SCOPE, "clean")
                found = postcheck_read_candidate(
                    store, lambda: store.get_conversation(SCOPE, c.id)
                )
                self.assertEqual(found.id, c.id)
                self.assertEqual(store.storage_health()["state"], HEALTHY)
            finally:
                store.close()

    def test_07_postcheck_candidate_preserves_own_commit(self):
        with TemporaryDirectory(prefix="a287-self-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                c = store.create_conversation(SCOPE, "own-commit")
                found = postcheck_read_candidate(
                    store, lambda: store.get_conversation(SCOPE, c.id)
                )
                self.assertEqual(found.id, c.id)
                self.assertEqual(store._local_data_version_reason(), "OK")
            finally:
                store.close()

    def test_08_exception_path_prioritizes_storage_uncertainty(self):
        with TemporaryDirectory(prefix="a287-exception-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "initial")

                def read_that_loses_a_race():
                    _foreign_commit(path, c.id, "foreign")
                    raise LookupError("not found")

                with self.assertRaisesRegex(
                    StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                ):
                    postcheck_read_candidate(store, read_that_loses_a_race)
                self.assertEqual(
                    store.storage_health()["reason"], "LOCAL_DATA_VERSION_CHANGED"
                )
            finally:
                store.close()

    def test_09_postcheck_still_has_final_window_not_atomic_proof(self):
        p = probe_last_moment_postcheck_gap()
        self.assertEqual(p["schema"], SCHEMA)
        self.assertEqual(p["checks"], 3)
        self.assertTrue(p["injected_after_final_check"])
        self.assertTrue(p["read_returned"])
        self.assertTrue(p["returned_original_title"])
        self.assertTrue(p["temporarily_healthy_after_return"])
        self.assertTrue(p["later_health_denies"])
        self.assertFalse(p["atomic_proof"])

    def test_10_unsupported_endpoint_and_bad_policy_denied(self):
        for invalid in (None, 1, [], "not-a-read"):
            with self.subTest(endpoint=repr(invalid)):
                with self.assertRaises(ValueError):
                    probe_reader_interleaving(endpoint=invalid)
        for invalid in (None, 0, 1, "yes", [], {}):
            with self.subTest(postcheck=repr(invalid)):
                with self.assertRaises(TypeError):
                    probe_reader_interleaving(postcheck=invalid)

    def test_11_no_send_worker_orders_or_p0_promotion(self):
        for postcheck in (False, True):
            p = probe_reader_interleaving(
                endpoint="get_conversation", postcheck=postcheck
            )
            self.assertFalse(p["authorizes_send"])
            self.assertTrue(p["zero_auto_resend"])
            self.assertTrue(p["no_worker_orders_network"])
            self.assertEqual(p["p0_homologated"], 0)
        last = probe_last_moment_postcheck_gap()
        self.assertEqual(last["p0_homologated"], 0)
        self.assertFalse(last["authorizes_send"])


if __name__ == "__main__":
    unittest.main()
