"""A299 LAB: actual WAL/main-copy counterexample and native-VFS proof gap.

Uses real Python sqlite3, actual AION SQLiteChatStore and ONLY temporary DBs.
Does NOT load/compile native C extensions, install dependencies, call workers,
effect external services, or homologate P0-5/P0-6. G17/G18 are cited as
separate draft PRs; their unsigned lab binaries are never imported here.
"""
import ast
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from aion_chat.models import Message, Scope
from aion_chat.store import HEALTHY, SQLiteChatStore
from labs.a292_staged_chat_write_inventory_lab import (
    probe_one_writer_ack_boundary, probe_real_raw_helper_bypasses,
)
from labs.a293_host_sqlite_boundary_lab import (
    probe_external_process_write, probe_closed_store_rollback,
)

SCHEMA = "ATLASQUANT_AION_NATIVE_SQLITE_P0_5_6_GAP_LAB_V1"
SOURCE = Path(__file__).resolve().parents[1] / "aion_chat" / "store.py"
SCOPE = Scope("owner-a299", "tenant-a299", "workspace-a299")
G17 = {
    "pr_number": 1504,
    "commit": "b19b8a074c1a9bfa465429e1fe18fb9891d5b73d",
    "probe": "sqlite3_context_db_handle + SQLITE_FCNTL_HAS_MOVED",
    "risk": "UNSIGNED_NATIVE_EXTENSION_NOT_AUTHORIZED_FOR_RUNTIME",
}
G18 = {
    "pr_number": 1505,
    "commit": "7419a0684a5842c9ee530180fd4520eff13b15af",
    "probe": "sqlite3_context_db_handle + SQLITE_FCNTL_WIN32_GET_HANDLE",
    "risk": "CLOSED_HOST_REPLACE_WRONG_CONTENT_NATIVE_MATCH_RED",
}


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "native_sqlite3_not_mocked": True,
        "real_native_extension_loaded": False,
        "g17_g18_not_merged_or_integrated_by_a299": True,
        "no_provider_worker_deploy_orders": True,
        "no_new_paid_services": True,
        "zero_auto_resend": True,
        "p0_5_homologated": False,
        "p0_6_homologated": False,
        "p0_homologated": 0,
        "authenticated_vfs_fd_identity": False,
        "off_host_rollback_witness": False,
        "power_loss_durability_proved": False,
        "can_authorize_real_effect": False,
        "hard_no_go": True,
    }


def _count_messages(path, cid):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute(
            "SELECT COUNT(*) FROM messages WHERE cid=?", (cid,),
        ).fetchone()[0]


def probe_main_file_copy_vs_sqlite_backup():
    """After confirmed WAL COMMIT, raw '.db' bytes omit a visible message.

    Initialize and checkpoint schema/conversation first. Keep the owner
    connection open after append, so the committed change remains in WAL.
    Compare two alternatives made at this point:
      - shutil.copy2 MAIN db only: old message_count survives, new msg absent.
      - sqlite3.Connection.backup: logical snapshot contains committed msg.
    """
    result = _base()
    with TemporaryDirectory(prefix="a299-real-wal-") as raw:
        path = Path(raw) / "staging.db"
        main_only = Path(raw) / "db-only-copy.db"
        logical = Path(raw) / "sqlite-native-backup.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            conversation = store.create_conversation(SCOPE, "before-WAL")
            cid = conversation.id
            # Make the pre-message state durable in the main file, so
            # copying MAIN-only later is itself a valid older snapshot.
            checkpoint = store.db.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            before = _count_messages(path, cid)
            message = store.append_message(
                SCOPE, Message(
                    cid, "user", "commit-visible-through-WAL",
                    id="a299-wal-only-committed-message",
                )
            )
            visible = _count_messages(path, cid)
            wal_path = Path(str(path) + "-wal")
            wal_size = wal_path.stat().st_size if wal_path.exists() else 0

            # Intentionally UNSAFE backup counterexample, no actual
            # production file touched or restored.
            shutil.copy2(path, main_only)
            copied = _count_messages(main_only, cid)

            # Supported SQLite backup API includes committed WAL state.
            with closing(sqlite3.connect(str(logical))) as target:
                store.db.backup(target)
            native_backup = _count_messages(logical, cid)
            result.update({
                "checkpoint_busy": checkpoint[0],
                "sequence": message.sequence,
                "before_message_count": before,
                "external_original_reads_committed_message": visible,
                "wal_file_nonempty_after_commit": wal_size > 0,
                "wal_bytes_after_commit": wal_size,
                "main_only_copy_message_count": copied,
                "native_backup_message_count": native_backup,
                "lost_committed_message_in_main_only_copy": (
                    before == 0 and visible == 1
                    and copied == 0 and native_backup == 1
                    and wal_size > 0
                ),
                "pending_marker_absent_after_ack": not (
                    store._message_commit_marker.exists()
                ),
                "store_still_healthy": (
                    store.storage_health(deep=True)["state"] == HEALTHY
                ),
            })
        finally:
            store.close()
        result["primary_after_close_message_count"] = _count_messages(
            path, cid
        )
    return result


def inspect_actual_store_native_boundary():
    """Source audit of the current staged-chat runtime, NOT binary attestation."""
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [
        item for item in tree.body
        if isinstance(item, ast.ClassDef)
        and item.name == "SQLiteChatStore"
    ]
    if len(classes) != 1:
        raise ValueError("SQLiteChatStore must have one class")
    methods = {
        item.name: item for item in classes[0].body
        if isinstance(item, ast.FunctionDef)
    }
    required = (
        "__init__", "_pathname_binding_reason",
        "_read_local_data_version", "_local_data_version_reason",
        "_commit_fenced_chat_write",
    )
    if any(name not in methods for name in required):
        raise ValueError("known boundary method missing")
    calls = []
    for method in methods.values():
        for node in ast.walk(method):
            if isinstance(node, ast.Call) and isinstance(
                node.func, ast.Attribute
            ):
                calls.append(node.func.attr)
    result = _base()
    result.update({
        "current_store_has_pathname_identity_guard": (
            "_pathname_binding_reason" in calls
        ),
        "current_store_has_local_data_version_guard": (
            "_local_data_version_reason" in calls
        ),
        "current_store_uses_local_commit_marker": (
            "_publish_message_commit_marker" in calls
        ),
        "current_store_calls_native_extension_loader": any(
            name in calls for name in (
                "enable_load_extension", "load_extension"
            )
        ),
        "native_fd_attestation_callable_found": any(
            name in calls for name in (
                "aion_lab_native_has_moved",
                "aion_lab_win32_native_identity",
                "sqlite3_file_control",
            )
        ),
        "g17_lab_reference": dict(G17),
        "g18_lab_reference": dict(G18),
        "g17_g18_github_source_reviewed_not_executed": True,
        "runtime_native_identity_not_proven": True,
        "native_extension_supply_chain_not_reviewed_for_production": True,
    })
    return result


def probe_combined_p0_5_6_negative_evidence():
    """Re-run independent-PID, H0 rollback, COMMIT-ACK and helper bypass."""
    result = _base()
    external = probe_external_process_write(strict=False)
    rollback = probe_closed_store_rollback()
    ack = probe_one_writer_ack_boundary(
        writer="append_message", phase="after"
    )
    helper = probe_real_raw_helper_bypasses()
    result.update({
        "other_pid_can_commit_unmarked_data": (
            external["external_process_sql_changed_title"]
            and external["no_local_marker_before_or_after"]
        ),
        "closed_valid_rollback_still_accepted": (
            rollback["older_history_silently_accepted"]
        ),
        "commit_may_succeed_before_ack_loss": (
            ack["first_effect_count"] == 1
            and ack["uncertain_error_raised"]
            and ack["automatic_retry_denied"]
            and ack["pending_marker_persisted"]
        ),
        "same_process_private_sql_bypass_remains": (
            helper["raw_save_record_helper_inserted_checkpoint"]
            and helper["pending_commit_marker_absent"]
        ),
        "no_canonical_p0_closure_from_negative_tests": True,
    })
    return result


__all__ = [
    "SCHEMA", "SOURCE", "SCOPE", "G17", "G18",
    "probe_main_file_copy_vs_sqlite_backup",
    "inspect_actual_store_native_boundary",
    "probe_combined_p0_5_6_negative_evidence",
]
