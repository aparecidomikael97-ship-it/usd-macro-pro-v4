from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from aion_chat.models import Message, Scope
from aion_chat.store import (
    BUSY_TIMEOUT_MS,
    HEALTHY,
    SQLiteChatStore,
    StorageUnavailableError,
)
from atlasquant_aion_chat_host_staging import (
    DIRECTORY_KEY,
    FLAG,
    TENANT_KEY,
    WORKSPACE_KEY,
    build_staged_host_binding,
    close_all_staged_host_stores,
)
from atlasquant_aion_chat_storage_resilience import (
    STAGING_RPO_SECONDS,
    STAGING_RTO_SECONDS,
    create_verified_staging_backup,
    restore_verified_staging_backup,
)


def _access(username="mikael", fingerprint="runtime-resilience-fingerprint"):
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "reason": "OK",
        "role": "ADMIN",
        "session": {
            "username": username,
            "role": "ADMIN",
            "permissions": ["app:read", "aion:admin", "aion:checkpoint"],
            "credential_fingerprint": fingerprint,
            "authenticated_at": 1.0,
            "last_seen": 1.0,
        },
    }


def _config(root):
    return {
        FLAG: "true",
        TENANT_KEY: "tenant-staging",
        WORKSPACE_KEY: "aion-staging",
        DIRECTORY_KEY: str(root),
    }


class SQLiteRuntimeResilienceTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("mikael", "tenant-staging", "aion-staging")

    def test_health_exposes_wal_busy_timeout_and_integrity(self):
        with tempfile.TemporaryDirectory() as raw:
            store = SQLiteChatStore(Path(raw) / "chat.sqlite3")
            health = store.storage_health(deep=True)
            self.assertEqual(health["state"], HEALTHY)
            self.assertEqual(health["journal_mode"], "wal")
            self.assertGreaterEqual(health["busy_timeout_ms"], BUSY_TIMEOUT_MS)
            self.assertEqual(health["quick_check"].lower(), "ok")
            self.assertEqual(health["foreign_key_violations"], 0)
            store.close()
            self.assertEqual(store.storage_health()["state"], "failed")

    def test_concurrent_separate_handles_serialize_without_lost_messages(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "chat.sqlite3"
            seed = SQLiteChatStore(path)
            conv = seed.create_conversation(self.scope, "concorrencia")
            seed.close()

            def write(index):
                local = SQLiteChatStore(path)
                try:
                    return local.append_message(
                        self.scope,
                        Message(
                            conv.id,
                            "user",
                            f"mensagem-{index}",
                            id=f"CONCURRENT-{index:04d}",
                        ),
                    ).sequence
                finally:
                    local.close()

            with ThreadPoolExecutor(max_workers=8) as pool:
                sequences = list(pool.map(write, range(64)))

            reopened = SQLiteChatStore(path)
            rows = reopened.list_messages(
                self.scope,
                conv.id,
                page_size=200,
            ).items
            self.assertEqual(len(rows), 64)
            self.assertEqual(len({row.id for row in rows}), 64)
            self.assertEqual([row.sequence for row in rows], list(range(1, 65)))
            self.assertEqual(sorted(sequences), list(range(1, 65)))
            self.assertEqual(
                reopened.get_conversation(self.scope, conv.id).message_count,
                64,
            )
            self.assertEqual(reopened.require_healthy()["state"], HEALTHY)
            reopened.close()

    def test_verified_backup_restore_is_snapshot_not_live_copy(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            live_path = root / "live.sqlite3"
            backup_path = root / "backups" / "snapshot.sqlite3"
            restored_path = root / "restored.sqlite3"

            store = SQLiteChatStore(live_path)
            conv = store.create_conversation(self.scope, "snapshot")
            store.append_message(
                self.scope,
                Message(conv.id, "user", "antes do backup", id="BEFORE-BACKUP"),
            )
            backup = create_verified_staging_backup(store, backup_path)
            self.assertEqual(backup["state"], "BACKUP_VERIFIED")
            self.assertEqual(backup["rpo_seconds"], STAGING_RPO_SECONDS)
            self.assertEqual(backup["rto_seconds"], STAGING_RTO_SECONDS)
            self.assertEqual(backup["backup"]["checkpoint"]["mode"], "FULL")
            self.assertEqual(backup["backup"]["checkpoint"]["busy"], 0)
            self.assertTrue(Path(backup["manifest_path"]).is_file())

            store.append_message(
                self.scope,
                Message(conv.id, "user", "depois do backup", id="AFTER-BACKUP"),
            )
            store.close()

            restored = restore_verified_staging_backup(
                backup_path,
                restored_path,
            )
            self.assertEqual(restored["state"], "RESTORE_VERIFIED")
            self.assertEqual(restored["restored_health"]["state"], HEALTHY)

            snapshot = SQLiteChatStore(restored_path)
            rows = snapshot.list_messages(
                self.scope,
                conv.id,
                page_size=20,
            ).items
            self.assertEqual([row.content for row in rows], ["antes do backup"])
            self.assertEqual(
                snapshot.get_conversation(self.scope, conv.id).message_count,
                1,
            )
            snapshot.close()

    def test_corrupted_backup_is_rejected_without_replacing_target(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            live = SQLiteChatStore(root / "live.sqlite3")
            conv = live.create_conversation(self.scope, "source")
            live.append_message(
                self.scope,
                Message(conv.id, "user", "safe", id="SAFE-SOURCE"),
            )
            backup_path = root / "backup.sqlite3"
            live.backup_to(backup_path)
            live.close()

            target_path = root / "target.sqlite3"
            target = SQLiteChatStore(target_path)
            sentinel = target.create_conversation(self.scope, "sentinel")
            target.close()

            data = bytearray(backup_path.read_bytes())
            data[: min(96, len(data))] = b"X" * min(96, len(data))
            backup_path.write_bytes(data)

            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore.restore_from_backup(backup_path, target_path)

            preserved = SQLiteChatStore(target_path)
            self.assertEqual(
                preserved.get_conversation(self.scope, sentinel.id).title,
                "sentinel",
            )
            self.assertEqual(preserved.require_healthy()["state"], HEALTHY)
            preserved.close()

    def test_corrupt_database_fails_startup_instead_of_recreating_blank_store(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "corrupt.sqlite3"
            path.write_bytes(b"not-a-sqlite-database" * 32)
            with self.assertRaises(StorageUnavailableError):
                SQLiteChatStore(path)
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_process_kill_rolls_back_uncommitted_wal_transaction(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "crash.sqlite3"
            marker = root / "ready"
            store = SQLiteChatStore(path)
            conv = store.create_conversation(self.scope, "crash")
            store.close()

            script = (
                "import pathlib,sqlite3,sys,time;"
                "db=sqlite3.connect(sys.argv[1],timeout=5);"
                "db.execute('PRAGMA journal_mode=WAL');"
                "db.execute('BEGIN IMMEDIATE');"
                "db.execute(\"INSERT INTO messages VALUES ('CRASH-PENDING',?,1,'pending','{}')\",(sys.argv[2],));"
                "pathlib.Path(sys.argv[3]).write_text('ready');"
                "time.sleep(60)"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", script, str(path), conv.id, str(marker)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                for _ in range(200):
                    if marker.exists():
                        break
                    if proc.poll() is not None:
                        self.fail(proc.stderr.read().decode("utf-8", "replace"))
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "child never entered uncommitted transaction")
                proc.kill()
                proc.wait(timeout=10)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)
                if proc.stderr:
                    proc.stderr.close()

            reopened = SQLiteChatStore(path)
            self.assertEqual(reopened.require_healthy()["state"], HEALTHY)
            self.assertEqual(
                reopened.db.execute(
                    "SELECT count(*) FROM messages WHERE cid=?",
                    (conv.id,),
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                reopened.get_conversation(self.scope, conv.id).message_count,
                0,
            )
            reopened.close()


class StagedHostIdentityLifecycleTests(unittest.TestCase):
    def test_credential_rotation_closes_old_handle_and_rebinds(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            session = {}
            first = build_staged_host_binding(
                session,
                _access(fingerprint="fingerprint-a"),
                config=_config(root),
                environment="STAGING",
            )
            conv = first["store"].create_conversation(first["scope"], "keep")
            second = build_staged_host_binding(
                session,
                _access(fingerprint="fingerprint-b"),
                config=_config(root),
                environment="STAGING",
            )
            self.assertIsNot(first["store"], second["store"])
            self.assertEqual(first["store"].storage_health()["state"], "failed")
            self.assertNotEqual(
                first["session_binding_digest"],
                second["session_binding_digest"],
            )
            self.assertEqual(
                second["store"].get_conversation(second["scope"], conv.id).id,
                conv.id,
            )
            self.assertEqual(second["storage_health"]["state"], HEALTHY)
            close_all_staged_host_stores(session)

    def test_user_switch_closes_previous_scoped_handle_and_uses_different_file(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            session = {}
            first = build_staged_host_binding(
                session,
                _access(username="mikael", fingerprint="mikael-fp"),
                config=_config(root),
                environment="STAGING",
            )
            first_path = first["staging_store_path"]

            second = build_staged_host_binding(
                session,
                _access(username="other-admin", fingerprint="other-fp"),
                config=_config(root),
                environment="STAGING",
            )
            self.assertNotEqual(first_path, second["staging_store_path"])
            self.assertEqual(first["store"].storage_health()["state"], "failed")
            self.assertEqual(second["scope"].owner_id, "other-admin")
            self.assertEqual(second["storage_health"]["state"], HEALTHY)
            close_all_staged_host_stores(session)

    def test_close_all_staged_handles_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            session = {}
            binding = build_staged_host_binding(
                session,
                _access(),
                config=_config(Path(raw)),
                environment="STAGING",
            )
            self.assertEqual(close_all_staged_host_stores(session), 1)
            self.assertEqual(close_all_staged_host_stores(session), 0)
            self.assertEqual(binding["store"].storage_health()["state"], "failed")

    def test_access_panel_logout_contains_staged_handle_cleanup_hook(self):
        source = Path("atlasquant_access_panel.py").read_text(encoding="utf-8")
        self.assertIn(
            "from atlasquant_aion_chat_host_staging import close_all_staged_host_stores",
            source,
        )
        self.assertIn("close_all_staged_host_stores(st.session_state)", source)


if __name__ == "__main__":
    unittest.main()
