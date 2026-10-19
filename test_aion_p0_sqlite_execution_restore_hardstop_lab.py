"""AION P0: official SQLite restore must not erase execution evidence.

RED contracts authored before patch. The API may restore CHAT-ONLY databases
but must reject sources or existing targets containing ANY critical execution
schema, regardless of row count. Neither SQL quick_check nor a SHA hash
provides independent proof of a durable producer high-water mark.

All databases are synthetic temporary fixtures. No provider, Worker,
credential, network, merge, or operational restore.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError
from atlasquant_aion_execution_outbox import ExecutionOutbox

SCOPE = Scope("lab-restore-owner", "lab-restore-tenant", "lab-restore-space")
NOW = datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc)
DENIAL = "P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS"


class P0ExecutionRestoreHardstopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-p0-exec-restore-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def chat_database(self, name, title):
        path = self.root / name
        store = SQLiteChatStore(path)
        try:
            store.create_conversation(SCOPE, title)
        finally:
            store.close()
        return path

    def execution_database(self, name, state="PENDING"):
        path = self.root / name
        store = SQLiteChatStore(path)
        try:
            outbox = ExecutionOutbox(store, SCOPE)
            key = outbox.enqueue(
                intent_ref="synthetic-unique-intent",
                action="no_provider",
                payload={"fixture": True},
                aggregate_key="restore-probe",
                authorization_ref="fixture-approval",
                policy_version="fixture-policy",
                created_at=NOW,
                valid_until=NOW + timedelta(minutes=10),
            )["idempotency_key"]
            if state == "UNCERTAIN":
                with store.db:
                    store.db.execute(
                        "UPDATE action_outbox SET state='UNCERTAIN',dispatch_started_at=? "
                        "WHERE idempotency_key=?", (NOW.isoformat(), key)
                    )
        finally:
            store.close()
        return path

    def with_table(self, name, table):
        path = self.root / name
        store = SQLiteChatStore(path)
        try:
            with store.db:
                store.db.execute("CREATE TABLE " + table + "(x INTEGER)")
        finally:
            store.close()
        return path

    def verify(self, path):
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0], "ok")
            return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            con.close()

    def test_01_outbox_backup_to_new_path_denied_without_creating_target(self):
        source = self.execution_database("source.sqlite3")
        target = self.root / "no-subdirectory" / "destination.sqlite3"
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertFalse(target.exists())
        self.assertFalse(target.parent.exists())
        self.assertIn("action_outbox", self.verify(source))

    def test_02_uncertain_backup_cannot_replace_existing_chat_database(self):
        source = self.execution_database("uncertain-source.sqlite3", "UNCERTAIN")
        target = self.chat_database("chat-target.sqlite3", "keep-this-chat")
        before = target.read_bytes()
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(self.verify(source) & {"action_outbox"}, {"action_outbox"})

    def test_03_chat_backup_cannot_erase_uncertain_outbox_target(self):
        source = self.chat_database("chat-source.sqlite3", "snapshot")
        target = self.execution_database("uncertain-target.sqlite3", "UNCERTAIN")
        before = target.read_bytes()
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(target.read_bytes(), before)
        con = sqlite3.connect(str(target))
        try:
            self.assertEqual(con.execute("SELECT state FROM action_outbox").fetchone()[0], "UNCERTAIN")
        finally:
            con.close()

    def test_04_empty_budget_table_is_also_execution_state(self):
        source = self.with_table("budget-source.sqlite3", "aion_authority_spend")
        target = self.root / "budget-target.sqlite3"
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertFalse(target.exists())

    def test_05_saga_plan_table_alone_is_protected(self):
        source = self.with_table("saga-source.sqlite3", "aion_execution_sagas")
        target = self.root / "saga-target.sqlite3"
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertFalse(target.exists())

    def test_06_chat_only_backup_restores_to_new_path(self):
        source = self.chat_database("chat-backup.sqlite3", "backup-chat")
        target = self.root / "chat-restore.sqlite3"
        result = SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(result["state"], "RESTORE_VERIFIED")
        restored = SQLiteChatStore(target)
        try:
            self.assertEqual(restored.list_conversations(SCOPE).items[0].title, "backup-chat")
        finally:
            restored.close()

    def test_07_chat_only_backup_can_replace_chat_only_target(self):
        source = self.chat_database("chat-snapshot.sqlite3", "source-chat")
        target = self.chat_database("chat-live.sqlite3", "target-chat")
        result = SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(result["state"], "RESTORE_VERIFIED")
        restored = SQLiteChatStore(target)
        try:
            titles = [x.title for x in restored.list_conversations(SCOPE).items]
            self.assertEqual(titles, ["source-chat"])
        finally:
            restored.close()

    def test_08_invalid_source_does_not_overwrite_existing_chat(self):
        source = self.root / "invalid-source.sqlite3"
        source.write_bytes(b"not a sqlite database")
        target = self.chat_database("valid-target.sqlite3", "preserved")
        before = target.read_bytes()
        with self.assertRaises(StorageUnavailableError):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(target.read_bytes(), before)

    def test_09_orphaned_wal_sidecar_without_target_is_denied(self):
        source = self.chat_database("sidecar-source.sqlite3", "snapshot")
        target = self.root / "missing-target.sqlite3"
        sidecar = Path(str(target) + "-wal")
        sidecar.write_bytes(b"unsafe orphaned wal")
        with self.assertRaisesRegex(StorageUnavailableError, "P0_RESTORE_TARGET_SIDECAR_UNVERIFIED"):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(sidecar.read_bytes(), b"unsafe orphaned wal")

    def test_10_incomplete_saga_events_schema_is_protected(self):
        source = self.with_table("event-source.sqlite3", "aion_execution_saga_events")
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, self.root / "new-event-target.sqlite3")

    def test_11_empty_outbox_schema_is_protected_regardless_of_effect_rows(self):
        source = self.with_table("empty-outbox.sqlite3", "action_outbox")
        with self.assertRaisesRegex(StorageUnavailableError, DENIAL):
            SQLiteChatStore.restore_from_backup(source, self.root / "new-outbox-target.sqlite3")

    def test_12_unrelated_table_name_is_not_treated_as_exec_ledger(self):
        source = self.with_table("unrelated.sqlite3", "action_outbox_history_notes")
        result = SQLiteChatStore.restore_from_backup(source, self.root / "unrelated-copy.sqlite3")
        self.assertEqual(result["state"], "RESTORE_VERIFIED")

    def test_13_unreadable_existing_target_does_not_get_overwritten(self):
        source = self.chat_database("chat-valid.sqlite3", "backed-up")
        target = self.root / "corrupt-target.sqlite3"
        target.write_bytes(b"not a sqlite database")
        with self.assertRaises(StorageUnavailableError):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(target.read_bytes(), b"not a sqlite database")


if __name__ == "__main__":
    unittest.main()
