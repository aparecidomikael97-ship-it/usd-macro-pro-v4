"""A184 synthetic LAB protection tests; no production/authority attestation.

Real temporary SQLite files are used. Mocked boundary timing makes the old
validate/reopen and validate/publish races deterministic; it does not emulate
an independently controlled VFS or prove freshness after coordinated rollback.
"""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from aion_chat.models import Scope
from aion_chat import store as storage
from aion_chat.store import SQLiteChatStore, StorageUnavailableError


class SQLiteRecoveryA184LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = Scope("LAB-owner", "LAB-tenant", "LAB-workspace")

    def database(self, name, title):
        path = self.root / name
        db = SQLiteChatStore(path)
        db.create_conversation(self.scope, title)
        db.close()
        # Recovery input is explicitly offline; live WAL is not a backup.
        db = sqlite3.connect(str(path))
        db.execute("PRAGMA journal_mode=DELETE")
        db.close()
        return path

    def titles(self, path):
        db = sqlite3.connect(str(path))
        try:
            return [row[0] for row in db.execute("SELECT title FROM conversations")]
        finally:
            db.close()

    def assert_rejected_without_replacing(self, source, target):
        before = target.read_bytes()
        with self.assertRaises(StorageUnavailableError):
            SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(target.read_bytes(), before)

    def test_zero_byte_input_cannot_erase_valid_target(self):
        source = self.root / "zero.db"
        source.touch()
        target = self.database("target.db", "PRESERVED")
        self.assert_rejected_without_replacing(source, target)

    def test_valid_sqlite_without_chat_schema_cannot_erase_target(self):
        source = self.root / "wrong-schema.db"
        db = sqlite3.connect(str(source))
        db.execute("CREATE TABLE unrelated(value TEXT)")
        db.commit()
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_validated_source_replacement_cannot_change_restored_bytes(self):
        source = self.database("source.db", "VALIDATED-A")
        replacement = self.database("replacement.db", "UNVALIDATED-B")
        target = self.root / "target.db"
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        original = storage._validate_database_file
        attacked = []

        def validate_then_replace(path):
            report = original(path)
            if Path(path) == source:
                shutil.copyfile(replacement, source)
                attacked.append(True)
            return report

        with patch.object(storage, "_validate_database_file", validate_then_replace):
            report = SQLiteChatStore.restore_from_backup(source, target)
        self.assertTrue(attacked, "the controlled validate/copy boundary was exercised")
        self.assertEqual(self.titles(target), ["VALIDATED-A"])
        self.assertEqual(report["source_sha256"], expected)
        self.assertEqual(report["restored_sha256"], expected)

    def test_missing_input_is_never_created(self):
        source = self.root / "missing.db"
        target = self.database("target.db", "PRESERVED")
        self.assert_rejected_without_replacing(source, target)
        self.assertFalse(source.exists())

    def test_source_sidecar_is_ambiguous_even_when_empty(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(source) + suffix)
                sidecar.touch()
                self.assert_rejected_without_replacing(source, target)
                sidecar.unlink()

    def test_target_sidecars_are_not_silently_reused_after_restore(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        sidecar = Path(str(target) + "-wal")
        sidecar.write_bytes(b"synthetic unresolved WAL")
        self.assert_rejected_without_replacing(source, target)
        self.assertEqual(sidecar.read_bytes(), b"synthetic unresolved WAL")

    def test_backup_cannot_publish_bytes_changed_after_validation(self):
        live = SQLiteChatStore(self.root / "live.db")
        self.addCleanup(live.close)
        live.create_conversation(self.scope, "VALIDATED-A")
        replacement = self.database("replacement.db", "UNVALIDATED-B")
        destination = self.root / "backup.db"
        original = storage._validate_database_file
        attacked = []

        def validate_then_replace(path):
            report = original(path)
            if Path(path).name.startswith("backup.db.tmp-"):
                shutil.copyfile(replacement, path)
                attacked.append(True)
            return report

        with patch.object(storage, "_validate_database_file", validate_then_replace):
            report = live.backup_to(destination)
        self.assertTrue(attacked, "the controlled validate/publish boundary was exercised")
        self.assertEqual(self.titles(destination), ["VALIDATED-A"])
        self.assertEqual(report["sha256"], hashlib.sha256(destination.read_bytes()).hexdigest())

    def test_disappearing_input_is_not_recreated_by_native_sqlite(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        original = os.open
        attacked = []

        def disappear_before_open(path, flags, *args, **kwargs):
            if Path(path) == source:
                source.unlink()
                attacked.append(True)
            return original(path, flags, *args, **kwargs)

        with patch.object(storage.os, "open", disappear_before_open):
            self.assert_rejected_without_replacing(source, target)
        self.assertTrue(attacked)
        self.assertFalse(source.exists())

    def test_mutation_during_single_fd_capture_is_denied(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        original = os.read
        attacked = []

        def mutate_during_read(fd, count):
            data = original(fd, count)
            if not attacked:
                with source.open("ab") as handle:
                    handle.write(b"ambiguous concurrent write")
                attacked.append(True)
            return data

        with patch.object(storage.os, "read", mutate_during_read):
            self.assert_rejected_without_replacing(source, target)
        self.assertTrue(attacked)

    def test_wal_header_without_sidecars_is_still_not_offline_backup(self):
        source = self.root / "uncheckpointed-format.db"
        db = SQLiteChatStore(source)
        db.create_conversation(self.scope, "SOURCE")
        db.close()
        self.assertEqual(source.read_bytes()[18:20], b"\x02\x02")
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_chat_columns_without_message_uniqueness_are_rejected(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        db.executescript("""
            DROP TABLE messages;
            CREATE TABLE messages(id TEXT PRIMARY KEY,
                cid TEXT NOT NULL REFERENCES conversations(id),
                seq INTEGER NOT NULL, content TEXT NOT NULL, data TEXT NOT NULL);
        """)
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_added_required_column_cannot_pass_recovery_gate(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        db.execute("ALTER TABLE messages ADD COLUMN required_extra TEXT NOT NULL")
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_unexpected_check_constraint_cannot_pass_recovery_gate(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        ddl = db.execute("SELECT sql FROM sqlite_schema WHERE name='conversations'").fetchone()[0]
        db.execute("DROP TABLE conversations")
        db.execute(ddl.replace("title TEXT NOT NULL", "title TEXT NOT NULL CHECK(title='')"))
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_explicit_unique_index_cannot_add_constraints_to_chat_tables(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        db.execute("CREATE UNIQUE INDEX unapproved_title_constraint ON conversations(title)")
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_ordinary_additional_tables_remain_permitted(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        db.executescript("""
            CREATE TABLE extra_outbox_lab(id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE INDEX extra_outbox_state_lab ON extra_outbox_lab(state);
            INSERT INTO extra_outbox_lab VALUES('synthetic-only', 'UNCERTAIN');
            CREATE TABLE extra_saga_lab(id TEXT PRIMARY KEY, phase TEXT NOT NULL);
        """)
        db.close()
        target = self.root / "target.db"
        SQLiteChatStore.restore_from_backup(source, target)
        db = SQLiteChatStore(target)
        try:
            self.assertEqual(db.db.execute("SELECT state FROM extra_outbox_lab").fetchall()[0][0],
                             "UNCERTAIN")
            self.assertEqual(db.create_conversation(self.scope, "normal").title, "normal")
        finally:
            db.close()

    def test_ddl_comparison_allows_case_spacing_but_not_syntax_erasure(self):
        canonical = "CREATE TABLE messages(id TEXT PRIMARY KEY,seq INTEGER NOT NULL)"
        tokens = storage._recovery_ddl_tokens(canonical)
        self.assertEqual(tokens, storage._recovery_ddl_tokens(
            "create\tTABLE messages ( id text PRIMARY key , seq INTEGER NOT NULL )"))
        for altered in (
            "CREATE TABLE messages(id TEXT PRIMARY KEY,seq INTEGERNOTNULL)",
            "CREATE TABLE messages(id TEXT PRIMARY KEY,seq INTEGER NOT NULL CHECK(seq=0))",
            'CREATE TABLE "messages"(id TEXT PRIMARY KEY,seq INTEGER NOT NULL)',
            "CREATE TABLE messages(id TEXT PRIMARY KEY,seq INTEGER NOT /* comment */ NULL)",
        ):
            with self.subTest(ddl=altered):
                self.assertNotEqual(tokens, storage._recovery_ddl_tokens(altered))

    def test_trigger_bearing_backup_is_not_a_passive_chat_artifact(self):
        source = self.database("source.db", "SOURCE")
        db = sqlite3.connect(str(source))
        db.executescript("""
            CREATE TRIGGER unexpected AFTER INSERT ON messages BEGIN
              DELETE FROM conversations;
            END;
        """)
        db.close()
        self.assert_rejected_without_replacing(
            source, self.database("target.db", "PRESERVED"))

    def test_source_alias_and_dangling_sidecar_alias_are_denied(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        alias = self.root / "source-alias.db"
        try:
            alias.symlink_to(source)
        except OSError as exc:
            self.skipTest("OS does not permit this synthetic symlink fixture: " + str(exc))
        self.assert_rejected_without_replacing(alias, target)
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(source) + suffix)
                sidecar.symlink_to(self.root / "missing-sidecar")
                self.assert_rejected_without_replacing(source, target)
                sidecar.unlink()

    def test_source_hardlink_is_denied(self):
        source = self.database("source.db", "SOURCE")
        alias = self.root / "source-hardlink.db"
        os.link(source, alias)
        self.assert_rejected_without_replacing(
            alias, self.database("target.db", "PRESERVED"))

    def test_missing_native_deserialize_fails_closed(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")

        class NoDeserialize:
            def close(self):
                pass

        with patch.object(storage.sqlite3, "connect", return_value=NoDeserialize()):
            self.assert_rejected_without_replacing(source, target)

    def test_write_failure_before_publish_preserves_target(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        with patch.object(storage.os, "write", side_effect=OSError("LAB disk failure")):
            self.assert_rejected_without_replacing(source, target)

    def test_visible_concurrent_target_commit_is_not_overwritten(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        original = os.write
        attacked = []

        def write_then_commit_target(fd, data):
            written = original(fd, data)
            if not attacked:
                db = sqlite3.connect(str(target))
                db.execute("UPDATE conversations SET title='CONCURRENT-COMMIT'")
                db.commit()
                db.close()
                attacked.append(True)
            return written

        with patch.object(storage.os, "write", write_then_commit_target):
            with self.assertRaisesRegex(StorageUnavailableError, "RECOVERY_TARGET_CHANGED"):
                SQLiteChatStore.restore_from_backup(source, target)
        self.assertTrue(attacked)
        self.assertEqual(self.titles(target), ["CONCURRENT-COMMIT"])

    def test_lost_replace_response_reports_uncertain_and_never_retries(self):
        source = self.database("source.db", "SOURCE")
        target = self.database("target.db", "PRESERVED")
        original = os.replace
        calls = []

        def replace_then_lose_response(before, after):
            calls.append((before, after))
            original(before, after)
            raise OSError("LAB response lost after actual rename")

        with patch.object(storage.os, "replace", replace_then_lose_response):
            with self.assertRaisesRegex(StorageUnavailableError, "UNCERTAIN_ZERO_AUTO_RESEND"):
                SQLiteChatStore.restore_from_backup(source, target)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.titles(target), ["SOURCE"])

    def test_changed_published_file_reports_uncertain_without_claiming_rollback(self):
        source = self.database("source.db", "SOURCE")
        replacement = self.database("replacement.db", "HOST-CONTROLLED-B")
        target = self.database("target.db", "PRESERVED")
        original = os.replace

        def replace_then_host_changes(before, after):
            original(before, after)
            shutil.copyfile(replacement, after)

        with patch.object(storage.os, "replace", replace_then_host_changes):
            with self.assertRaisesRegex(StorageUnavailableError, "UNCERTAIN_ZERO_AUTO_RESEND"):
                SQLiteChatStore.restore_from_backup(source, target)
        # The hostile host changed bytes. Detection cannot undo that effect.
        self.assertEqual(self.titles(target), ["HOST-CONTROLLED-B"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
