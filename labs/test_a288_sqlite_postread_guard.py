"""A288 LAB: opt-in SQLiteChatStore post-read version guard integration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Message, Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError
from labs.a287_sqlite_read_race_probe import (
    ENDPOINTS, SCOPE, _foreign_commit, probe_reader_interleaving
)


class A288SQLiteIntegratedPostReadGuardTests(unittest.TestCase):
    def test_01_all_six_read_paths_now_deny_interleaved_commits(self):
        for endpoint in sorted(ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(
                    endpoint=endpoint, integrated_guard=True
                )
                self.assertTrue(p["injected_external_commit"])
                self.assertEqual(p["status"], "DENIED_AFTER_EXTERNAL_COMMIT")
                self.assertEqual(
                    p["store_reason_after_followup"], "LOCAL_DATA_VERSION_CHANGED"
                )
                self.assertEqual(p["store_health_before_followup"], FAILED)

    def test_02_historical_pre_only_negative_control_still_reproducible(self):
        for endpoint in sorted(ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                p = probe_reader_interleaving(endpoint=endpoint)
                self.assertEqual(p["status"], "RETURNED")
                self.assertTrue(p["counter_changed"])
                self.assertEqual(p["store_health_before_followup"], HEALTHY)
                self.assertFalse(p["integrated_store_postcheck"])

    def test_03_hardening_only_runs_for_explicit_strict_mode(self):
        with TemporaryDirectory(prefix="a288-default-") as raw:
            path = Path(raw) / "staging.db"
            first = SQLiteChatStore(path)
            second = SQLiteChatStore(path)
            try:
                c = first.create_conversation(SCOPE, "shared")
                self.assertEqual(second.get_conversation(SCOPE, c.id).id, c.id)
                self.assertEqual(first.storage_health()["state"], HEALTHY)
                self.assertEqual(second.storage_health()["state"], HEALTHY)
                self.assertFalse(first._strict_local_data_version)
            finally:
                second.close()
                first.close()

    def test_04_strict_reads_preserve_own_commit_and_no_other_writer(self):
        with TemporaryDirectory(prefix="a288-own-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                c = store.create_conversation(SCOPE, "own")
                m = store.append_message(
                    SCOPE, Message(c.id, "user", "self", id="a288-own")
                )
                self.assertEqual(store.get_conversation(SCOPE, c.id).id, c.id)
                self.assertEqual(
                    store.get_message(SCOPE, c.id, m.id).sequence, 1
                )
                self.assertEqual(
                    store.list_messages(SCOPE, c.id).items[0].id, m.id
                )
                self.assertEqual(store.storage_health()["state"], HEALTHY)
            finally:
                store.close()

    def test_05_attachment_missing_path_prioritizes_external_change(self):
        with TemporaryDirectory(prefix="a288-attachment-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "attachment")
                original = store.get_conversation

                def interposed(scope, cid):
                    row = original(scope, cid)
                    _foreign_commit(path, c.id, "external")
                    return row

                with mock.patch.object(
                    store, "get_conversation", side_effect=interposed
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                    ):
                        store.get_attachment(SCOPE, c.id, "not-present")
            finally:
                store.close()

    def test_06_latest_checkpoint_uses_shared_private_read_postcheck(self):
        with TemporaryDirectory(prefix="a288-latest-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "checkpoint")
                original = store.get_conversation

                def interposed(scope, cid):
                    row = original(scope, cid)
                    _foreign_commit(path, c.id, "external")
                    return row

                with mock.patch.object(
                    store, "get_conversation", side_effect=interposed
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                    ):
                        store.get_latest_checkpoint(SCOPE, c.id)
            finally:
                store.close()

    def test_07_search_uses_list_conversations_postcheck(self):
        with TemporaryDirectory(prefix="a288-search-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "before")
                original = store._scope

                def interposed(scope):
                    result = original(scope)
                    _foreign_commit(path, c.id, "external")
                    return result

                with mock.patch.object(store, "_scope", side_effect=interposed):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                    ):
                        store.search_conversations(SCOPE, "external")
            finally:
                store.close()

    def test_08_blank_retrieve_still_checks_new_external_change(self):
        with TemporaryDirectory(prefix="a288-blank-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "blank")
                original = store.get_conversation

                def interposed(scope, cid):
                    row = original(scope, cid)
                    _foreign_commit(path, c.id, "external")
                    return row

                with mock.patch.object(
                    store, "get_conversation", side_effect=interposed
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                    ):
                        store.retrieve_messages(
                            SCOPE, c.id, "", before_sequence=1
                        )
            finally:
                store.close()

    def test_09_ordinary_unknown_record_retains_lookup_error(self):
        with TemporaryDirectory(prefix="a288-missing-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                with self.assertRaises(LookupError):
                    store.get_conversation(SCOPE, "unknown")
                self.assertEqual(store.storage_health()["state"], HEALTHY)
            finally:
                store.close()

    def test_10_postread_check_still_not_atomic_with_return(self):
        with TemporaryDirectory(prefix="a288-after-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "initial")
                count = 0
                original_check = store._require_open

                def last_moment_commit():
                    nonlocal count
                    original_check()
                    count += 1
                    if count == 2:
                        _foreign_commit(path, c.id, "after-final-check")

                with mock.patch.object(
                    store, "_require_open", side_effect=last_moment_commit
                ):
                    result = store.get_conversation(SCOPE, c.id)
                self.assertEqual(count, 2)
                self.assertEqual(result.title, "initial")
                self.assertEqual(store._health_state, HEALTHY)
                self.assertEqual(
                    store.storage_health()["reason"], "LOCAL_DATA_VERSION_CHANGED"
                )
            finally:
                store.close()

    def test_11_data_version_read_error_fails_closed_in_postcheck(self):
        with TemporaryDirectory(prefix="a288-unavailable-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                c = store.create_conversation(SCOPE, "read-error")
                # Exercise the shared postcheck's fail-closed path.
                with mock.patch.object(
                    store, "_read_local_data_version", return_value=None
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_UNAVAILABLE"
                    ):
                        store._post_read_data_version_guard()
                self.assertEqual(store._health_state, FAILED)
            finally:
                store.close()

    def test_12_no_send_no_independent_p0_authority(self):
        with TemporaryDirectory(prefix="a288-no-go-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                self.assertEqual(store._local_data_version_reason(), "OK")
                store._post_read_data_version_guard()
                self.assertFalse(hasattr(store, "authorize_external_send"))
                self.assertFalse(hasattr(store, "attest_off_host_rollback_floor"))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
