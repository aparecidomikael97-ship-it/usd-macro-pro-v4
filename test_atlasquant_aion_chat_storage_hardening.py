"""Focused storage hardening proofs for the staged AION chat SQLite store."""
import sqlite3
import threading

import pytest

from aion_chat.models import Message, Scope
from aion_chat.store import SQLiteChatStore, StorageUnavailableError


def test_sqlite_policy_health_and_checkpoint(tmp_path):
    store = SQLiteChatStore(tmp_path / "chat.sqlite")
    try:
        assert store.db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert store.db.execute("PRAGMA busy_timeout").fetchone()[0] == SQLiteChatStore.BUSY_TIMEOUT_MS
        assert store.db.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
        assert store.health() == {"state": "healthy", "detail": "ok"}
        checkpoint = store.checkpoint("FULL")
        assert checkpoint["mode"] == "FULL"
        assert checkpoint["busy"] == 0
        with pytest.raises(ValueError):
            store.checkpoint("INVALID")
    finally:
        store.close()


def test_concurrent_writers_serialize_without_lost_sequences(tmp_path):
    db = tmp_path / "concurrent.sqlite"
    scope = Scope("owner", "tenant", "workspace")
    bootstrap = SQLiteChatStore(db)
    conversation = bootstrap.create_conversation(scope, "concorrencia")
    bootstrap.close()

    worker_count = 4
    writes_per_worker = 25
    barrier = threading.Barrier(worker_count)
    errors = []

    def worker(worker_id):
        store = None
        try:
            store = SQLiteChatStore(db)
            barrier.wait(timeout=10)
            for index in range(writes_per_worker):
                store.append_message(
                    scope,
                    Message(conversation.id, "user", f"worker={worker_id};index={index}"),
                )
        except Exception as exc:  # surfaced below with the original exception repr
            errors.append(repr(exc))
        finally:
            if store is not None:
                store.close()

    threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not any(thread.is_alive() for thread in threads), "writer thread did not terminate"
    assert errors == []

    reopened = SQLiteChatStore(db)
    try:
        messages = reopened.list_messages(scope, conversation.id, page_size=200).items
        expected = worker_count * writes_per_worker
        assert len(messages) == expected
        assert [message.sequence for message in messages] == list(range(1, expected + 1))
        assert reopened.get_conversation(scope, conversation.id).message_count == expected
        assert reopened.health()["state"] == "healthy"
    finally:
        reopened.close()


def test_backup_restore_uses_sqlite_api_and_preserves_consistent_snapshot(tmp_path):
    db = tmp_path / "source.sqlite"
    backup = tmp_path / "backup.sqlite"
    restored = tmp_path / "restored.sqlite"
    scope = Scope("owner", "tenant", "workspace")

    store = SQLiteChatStore(db)
    conversation = store.create_conversation(scope, "backup")
    for index in range(12):
        store.append_message(scope, Message(conversation.id, "user", f"m{index}"))

    backup_path = store.backup_to(backup)
    assert backup_path == backup
    store.close()

    source_check = sqlite3.connect(str(backup))
    try:
        assert source_check.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        source_check.close()

    restored_path = SQLiteChatStore.restore_backup(backup, restored)
    assert restored_path == restored

    reopened = SQLiteChatStore(restored)
    try:
        assert reopened.get_conversation(scope, conversation.id).message_count == 12
        assert [m.content for m in reopened.list_messages(scope, conversation.id, page_size=50).items] == [
            f"m{index}" for index in range(12)
        ]
        assert reopened.health() == {"state": "healthy", "detail": "ok"}
    finally:
        reopened.close()


def test_restore_rejects_corrupt_backup_and_existing_destination(tmp_path):
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"not-a-sqlite-database")
    with pytest.raises(StorageUnavailableError):
        SQLiteChatStore.restore_backup(corrupt, tmp_path / "restored.sqlite")

    good_store = SQLiteChatStore(tmp_path / "good.sqlite")
    good_store.close()
    existing = tmp_path / "existing.sqlite"
    existing.write_bytes(b"do-not-overwrite")
    with pytest.raises(FileExistsError):
        SQLiteChatStore.restore_backup(tmp_path / "good.sqlite", existing)
