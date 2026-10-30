"""A293 LAB: bounded native SQLite cross-process, pathname swap and rollback probes.

Purely synthetic disposable databases. This is a negative security-boundary
characterization; no off-host identity/custody, FD authentication, authorization,
Worker, provider send, trade or P0 closure. Never operate on existing files.
"""
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

from aion_chat.models import Message, Scope
from aion_chat.store import (
    FAILED, HEALTHY, SQLiteChatStore, StorageUnavailableError,
)

SCHEMA = "ATLASQUANT_AION_HOST_SQLITE_BOUNDARY_LAB_V1"
SCOPE = Scope("owner-a293", "tenant-a293", "workspace-a293")
EXTERNAL_WRITE_SCRIPT = (
    "import sqlite3, sys\n"
    "db = sqlite3.connect(sys.argv[1], timeout=10)\n"
    "try:\n"
    "    db.execute('UPDATE conversations SET title=? WHERE id=?', "
    "(sys.argv[3], sys.argv[2]))\n"
    "    db.commit()\n"
    "finally:\n"
    "    db.close()\n"
)


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "sandbox_disposable_sqlite_only": True,
        "no_services_no_deploy_no_worker_no_orders": True,
        "zero_auto_resend": True,
        "p0_homologated": 0,
        "production_hard_no_go": True,
        "native_fd_authenticated": False,
        "off_host_witness": False,
        "independent_authority": False,
        "cross_process_tamper_resistance_proved": False,
    }


def _external_title(path, conversation_id):
    with closing(sqlite3.connect(str(path))) as db:
        row = db.execute(
            "SELECT title FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        return row[0] if row else None


def _external_message_count(path, conversation_id):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute(
            "SELECT COUNT(*) FROM messages WHERE cid=?",
            (conversation_id,),
        ).fetchone()[0]


def probe_external_process_write(*, strict=True):
    """An independent Python PID modifies a live SQLite DB without marker."""
    if type(strict) is not bool:
        raise ValueError("strict flag must be bool")
    result = _base()
    with TemporaryDirectory(prefix="a293-outside-process-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=strict)
        try:
            conv = store.create_conversation(SCOPE, "legitimate")
            marker_before = store._message_commit_marker.exists()
            cp = subprocess.run(
                [
                    sys.executable, "-c", EXTERNAL_WRITE_SCRIPT,
                    str(path), conv.id, "external-process-tampered",
                ],
                check=True, capture_output=True, text=True, timeout=20,
            )
            affected = _external_title(path, conv.id)
            marker_after = store._message_commit_marker.exists()
            denied_next_read = False
            try:
                store.get_conversation(SCOPE, conv.id)
            except StorageUnavailableError:
                denied_next_read = True
            result.update({
                "strict_single_writer_mode": strict,
                "independent_process_exit_zero": cp.returncode == 0,
                "external_process_sql_changed_title": (
                    affected == "external-process-tampered"
                ),
                "no_local_marker_before_or_after": (
                    not marker_before and not marker_after
                ),
                "guard_rejected_next_read": denied_next_read,
                "store_health_failed": store._health_state == FAILED,
                "local_reason": store._health_reason,
                "external_change_visible_before_guard": (\n                    affected == "external-process-tampered"\n                ),
            })
        finally:
            store.close()
    return result


def probe_closed_store_rollback():
    """Host replaces a closed DB with previously valid older bytes.

    All paths are brand-new temporary files. This intentionally shows why
    data_version baselines and removable local markers cannot attest history.
    """
    result = _base()
    with TemporaryDirectory(prefix="a293-closed-rollback-") as raw:
        path = Path(raw) / "staging.db"
        old_snapshot = Path(raw) / "old-snapshot.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            conv = store.create_conversation(SCOPE, "before")
            cid = conv.id
        finally:
            store.close()
        # Last connection closed. SQLite WAL checkpoints into the main DB.
        shutil.copy2(path, old_snapshot)
        baseline = _external_message_count(old_snapshot, cid)

        reopened = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            msg = reopened.append_message(
                SCOPE,
                Message(cid, "user", "this message will be rolled back",
                        id="a293-history-lost-message"),
            )
            seq = msg.sequence
        finally:
            reopened.close()
        before = _external_message_count(path, cid)

        # Host-controlled replacement, NOT the store's guarded restore API.
        os.replace(old_snapshot, path)
        marker = Path(str(path) + ".aion-message-commit-pending")
        marker_after = marker.exists()
        restored = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            after = _external_message_count(path, cid)
            read_count = restored.get_conversation(SCOPE, cid).message_count
            status = restored.storage_health(deep=True)
            result.update({
                "baseline_old_count": baseline,
                "new_message_sequence": seq,
                "count_before_rollback": before,
                "count_after_rollback": after,
                "reopened_conversation_message_count": read_count,
                "marker_absent_after_host_rollback": not marker_after,
                "strict_reopen_health_healthy": status["state"] == HEALTHY,
                "older_history_silently_accepted": (
                    baseline == 0 and before == 1 and after == 0
                    and read_count == 0 and status["state"] == HEALTHY
                ),
            })
        finally:
            restored.close()
    return result


def probe_live_pathname_swap():
    """POSIX-only hot pathname rename: local inode check detects next use.

    Windows may block replacement of a SQLite file while its handle is open.
    It is deliberately reported as UNTESTED there, not as success.
    """
    result = _base()
    if os.name != "posix":
        result.update({
            "supported_host": False,
            "tested": False,
            "reason": "HOT_REPLACE_OPEN_SQLITE_NOT_PORTABLE_ON_WINDOWS",
        })
        return result
    with TemporaryDirectory(prefix="a293-open-swap-") as raw:
        path = Path(raw) / "staging.db"
        replacement = Path(raw) / "replacement.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            conv = store.create_conversation(SCOPE, "live")
            with closing(sqlite3.connect(str(replacement))) as dst:
                store.db.backup(dst)
            before = store._pathname_binding_reason()
            os.replace(replacement, path)
            after = store._pathname_binding_reason()
            rejected = False
            try:
                store.get_conversation(SCOPE, conv.id)
            except StorageUnavailableError:
                rejected = True
            refused_again = False
            try:
                store.get_conversation(SCOPE, conv.id)
            except StorageUnavailableError:
                refused_again = True
            result.update({
                "supported_host": True,
                "tested": True,
                "pathname_reason_before": before,
                "pathname_reason_after": after,
                "next_local_guard_denied": rejected,
                "subsequent_local_guard_denied_sticky": refused_again,
                "health_failed_sticky": store._health_state == FAILED,
                "local_reason": store._health_reason,
                "pending_marker_absent": (
                    not store._message_commit_marker.exists()
                ),
                "independent_native_fd_proof": False,
            })
        finally:
            store.close()
    return result


__all__ = [
    "SCHEMA", "SCOPE", "EXTERNAL_WRITE_SCRIPT",
    "probe_external_process_write", "probe_closed_store_rollback",
    "probe_live_pathname_swap",
]
