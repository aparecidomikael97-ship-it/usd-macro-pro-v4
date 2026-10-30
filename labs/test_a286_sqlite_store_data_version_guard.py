"""A286 LAB: opt-in SQLiteChatStore data_version guard, honest negative limits.

Disposable local SQLite only. Strict guard is intentionally NOT the default
for cooperative concurrent writers. It is not a P0-5/6 closure, independent
identity/FD/rollback proof, external send authority, or production activation.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from aion_chat.models import Scope
from aion_chat.store import FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError


SCOPE = Scope("owner-a286", "tenant-a286", "workspace-a286")


class A286StrictLocalSQLiteVersionTests(unittest.TestCase):
    def test_01_default_mode_preserves_cooperating_connections(self):
        with TemporaryDirectory(prefix="a286-default-") as raw:
            path = Path(raw) / "staging.db"
            first = SQLiteChatStore(path)
            second = SQLiteChatStore(path)
            try:
                c = first.create_conversation(SCOPE, "cooperative")
                self.assertEqual(second.get_conversation(SCOPE, c.id).id, c.id)
                self.assertEqual(first.require_healthy()["state"], HEALTHY)
                self.assertFalse(first._strict_local_data_version)
            finally:
                second.close()
                first.close()

    def test_02_strict_mode_self_commits_do_not_false_veto(self):
        with TemporaryDirectory(prefix="a286-self-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                c = store.create_conversation(SCOPE, "self commit")
                self.assertEqual(store.get_conversation(SCOPE, c.id).id, c.id)
                self.assertEqual(store.require_healthy()["state"], HEALTHY)
                self.assertEqual(store._local_data_version_reason(), "OK")
            finally:
                store.close()

    def test_03_raw_other_connection_commit_is_denied_same_inode(self):
        with TemporaryDirectory(prefix="a286-other-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "before")
                inode = (path.stat().st_dev, path.stat().st_ino)
                with closing(sqlite3.connect(str(path))) as external:
                    external.execute(
                        "UPDATE conversations SET title=? WHERE id=?",
                        ("raw-other-connection", c.id),
                    )
                    external.commit()
                self.assertEqual(inode, (path.stat().st_dev, path.stat().st_ino))
                self.assertEqual(store._pathname_binding_reason(), "OK")
                with self.assertRaisesRegex(
                    StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                ):
                    store.get_conversation(SCOPE, c.id)
                self.assertEqual(store._health_state, FAILED)
                self.assertEqual(store._health_reason, "LOCAL_DATA_VERSION_CHANGED")
            finally:
                store.close()

    def test_04_semantic_aba_reversion_does_not_restore_trust(self):
        with TemporaryDirectory(prefix="a286-aba-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "initial")
                with closing(sqlite3.connect(str(path))) as external:
                    external.execute(
                        "UPDATE conversations SET title='mutated' WHERE id=?",
                        (c.id,),
                    )
                    external.commit()
                    external.execute(
                        "UPDATE conversations SET title='initial' WHERE id=?",
                        (c.id,),
                    )
                    external.commit()
                    self.assertEqual(
                        external.execute("PRAGMA quick_check").fetchone()[0], "ok"
                    )
                self.assertEqual(store._pathname_binding_reason(), "OK")
                self.assertEqual(
                    store.storage_health(deep=True)["reason"],
                    "LOCAL_DATA_VERSION_CHANGED",
                )
                self.assertEqual(store.storage_health()["state"], FAILED)
                with self.assertRaises(StorageUnavailableError):
                    store.get_conversation(SCOPE, c.id)
            finally:
                store.close()

    def test_05_health_detects_external_change_without_reading_message(self):
        with TemporaryDirectory(prefix="a286-health-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                with closing(sqlite3.connect(str(path))) as external:
                    external.execute(
                        "CREATE TABLE a286_external_probe (id INTEGER)"
                    )
                    external.commit()
                report = store.storage_health(deep=True)
                self.assertEqual(report["state"], FAILED)
                self.assertEqual(report["reason"], "LOCAL_DATA_VERSION_CHANGED")
                self.assertEqual(report["quick_check"], "not_run")
                with self.assertRaises(StorageUnavailableError):
                    store.require_healthy()
            finally:
                store.close()

    def test_06_counter_unavailable_is_fail_closed_and_sticky(self):
        with TemporaryDirectory(prefix="a286-unavailable-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                with mock.patch.object(
                    store, "_read_local_data_version", return_value=None
                ):
                    with self.assertRaisesRegex(
                        StorageUnavailableError, "LOCAL_DATA_VERSION_UNAVAILABLE"
                    ):
                        store.create_conversation(SCOPE, "denied")
                self.assertEqual(store.storage_health()["state"], FAILED)
                self.assertEqual(
                    store.storage_health()["reason"],
                    "LOCAL_DATA_VERSION_UNAVAILABLE",
                )
            finally:
                store.close()

    def test_07_reopen_is_a_new_local_baseline_not_rollback_proof(self):
        with TemporaryDirectory(prefix="a286-reopen-") as raw:
            path = Path(raw) / "staging.db"
            store = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                c = store.create_conversation(SCOPE, "before")
                with closing(sqlite3.connect(str(path))) as external:
                    external.execute(
                        "UPDATE conversations SET title='other' WHERE id=?",
                        (c.id,),
                    )
                    external.commit()
                self.assertEqual(
                    store.storage_health()["reason"], "LOCAL_DATA_VERSION_CHANGED"
                )
            finally:
                store.close()
            reopened = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                self.assertEqual(reopened.storage_health()["state"], HEALTHY)
                self.assertEqual(reopened._local_data_version_reason(), "OK")
                # Reopened handle CANNOT attest the earlier change or reversal.
                self.assertNotEqual(reopened._local_data_version_baseline, None)
            finally:
                reopened.close()

    def test_08_strict_mode_rejects_non_bool_policy(self):
        with TemporaryDirectory(prefix="a286-type-") as raw:
            path = Path(raw) / "staging.db"
            for invalid in (None, 1, 0, "true", [], {}):
                with self.subTest(invalid=repr(invalid)):
                    with self.assertRaisesRegex(TypeError, "must be bool"):
                        SQLiteChatStore(path, strict_local_data_version=invalid)
            self.assertFalse(path.exists())

    def test_09_strict_guard_denies_cooperative_other_store_too(self):
        with TemporaryDirectory(prefix="a286-cooperative-") as raw:
            path = Path(raw) / "staging.db"
            strict = SQLiteChatStore(path, strict_local_data_version=True)
            other = SQLiteChatStore(path)
            try:
                c = other.create_conversation(SCOPE, "cooperative writer")
                with self.assertRaisesRegex(
                    StorageUnavailableError, "LOCAL_DATA_VERSION_CHANGED"
                ):
                    strict.get_conversation(SCOPE, c.id)
            finally:
                other.close()
                strict.close()

    def test_10_local_watch_never_approves_real_send_or_p0(self):
        with TemporaryDirectory(prefix="a286-scope-") as raw:
            store = SQLiteChatStore(
                Path(raw) / "staging.db", strict_local_data_version=True
            )
            try:
                self.assertEqual(store._local_data_version_reason(), "OK")
                # A stable counter is only a local observation; not authority.
                self.assertFalse(hasattr(store, "authorize_external_send"))
                self.assertFalse(hasattr(store, "attest_native_sqlite_vfs_fd"))
                self.assertFalse(hasattr(store, "attest_off_host_rollback_floor"))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
