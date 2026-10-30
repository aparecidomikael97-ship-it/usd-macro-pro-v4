"""A300: SQLite cold-restart WAL and uncertain-COMMIT marker negative probes.

Real sqlite3, actual staged-chat store, disposable paths. ZERO_AUTO_RESEND.
No production restore, power-cut simulation, native extension, external send.
"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import sqlite3

from aion_chat.models import Message, Scope
from aion_chat.store import (
    HEALTHY, SQLiteChatStore, StorageUnavailableError,
    StoreCommitOutcomeUncertainError,
)
from labs.a292_staged_chat_write_inventory_lab import (
    SCOPE as ACK_SCOPE, _open_ack_connection,
)

SCHEMA = "ATLASQUANT_AION_COLD_RESTART_WAL_RECOVERY_LAB_V1"
SCOPE = Scope("owner-a300", "tenant-a300", "workspace-a300")


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "real_sqlite3_and_chat_store": True,
        "temporary_paths_only": True,
        "store_restore_apis_not_called": True,
        "power_cut_simulated": False,
        "production_recovery_validated": False,
        "native_fd_attested": False,
        "off_host_rollback_witness": False,
        "no_provider_worker_deploy_orders": True,
        "zero_auto_resend": True,
        "no_paid_services": True,
        "p0_5_homologated": False,
        "p0_6_homologated": False,
        "p0_homologated": 0,
        "hard_no_go": True,
        "can_authorize_real_effect": False,
    }


def _cold_read(path, scope, cid):
    opened = SQLiteChatStore(path, strict_local_data_version=True)
    try:
        health = opened.storage_health(deep=True)
        messages = opened.list_messages(scope, cid).items
        return {
            "health": health["state"],
            "message_count": len(messages),
            "message_ids": [item.id for item in messages],
        }
    finally:
        opened.close()


def probe_cold_restart_after_incomplete_wal_copy():
    """Compare raw main-only copy and supported logical backup after reopen."""
    out = _base()
    with TemporaryDirectory(prefix="a300-wal-restart-") as root:
        source = Path(root) / "original.db"
        raw_main = Path(root) / "raw-main-only.db"
        backup = Path(root) / "native-backup.db"
        opened = SQLiteChatStore(source, strict_local_data_version=True)
        try:
            cid = opened.create_conversation(SCOPE, "pre-WAL").id
            chk = opened.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            msg = opened.append_message(
                SCOPE, Message(
                    cid, "user", "confirmed but still WAL-only",
                    id="a300-confirmed-message",
                ),
            )
            wal = Path(str(source) + "-wal")
            wal_bytes = wal.stat().st_size if wal.exists() else 0
            with closing(sqlite3.connect(str(source))) as verifier:
                count = verifier.execute(
                    "SELECT COUNT(*) FROM messages WHERE cid=?", (cid,),
                ).fetchone()[0]
            shutil.copy2(source, raw_main)
            with closing(sqlite3.connect(str(backup))) as target:
                opened.db.backup(target)
            out.update({
                "checkpoint_busy": chk[0],
                "committed_sequence": msg.sequence,
                "wal_bytes_before_close": wal_bytes,
                "another_connection_saw_commit": count,
                "raw_snapshot_wal_missing": not Path(
                    str(raw_main) + "-wal"
                ).exists(),
                "normal_ack_marker_absent": not (
                    opened._message_commit_marker.exists()
                ),
            })
        finally:
            opened.close()
        out["original_cold"] = _cold_read(source, SCOPE, cid)
        out["raw_main_cold"] = _cold_read(raw_main, SCOPE, cid)
        out["backup_cold"] = _cold_read(backup, SCOPE, cid)
        out["silent_loss_in_healthy_cold_raw_copy"] = (
            chk[0] == 0 and wal_bytes > 0 and count == 1
            and out["original_cold"]["message_count"] == 1
            and out["raw_main_cold"]["health"] == HEALTHY
            and out["raw_main_cold"]["message_count"] == 0
            and out["backup_cold"]["message_count"] == 1
        )
    return out


def probe_uncertain_ack_marker_not_in_database_backup():
    """COMMIT succeeds but ACK lost; standalone SQLite backup omits veto.

    The backup uses a separate sqlite3.Connection, NOT staging backup_to or
    restore_from_backup; no retry or marker removal is attempted.
    """
    out = _base()
    with TemporaryDirectory(prefix="a300-ack-restore-") as root:
        source = Path(root) / "source.db"
        logical = Path(root) / "relocated.db"
        opened = _open_ack_connection(source)
        try:
            cid = opened.create_conversation(ACK_SCOPE, "seed").id
            opened.db.fault_once = "after"
            uncertain = False
            try:
                opened.append_message(
                    ACK_SCOPE, Message(
                        cid, "user", "ACK lost after native COMMIT",
                        id="a300-uncertain-message",
                    ),
                )
            except StoreCommitOutcomeUncertainError:
                uncertain = True
            marker = opened._message_commit_marker.exists()
            with closing(sqlite3.connect(str(source))) as reader:
                effect = reader.execute(
                    "SELECT COUNT(*) FROM messages WHERE cid=?", (cid,),
                ).fetchone()[0]
                with closing(sqlite3.connect(str(logical))) as target:
                    reader.backup(target)
            out.update({
                "uncertain_error": uncertain,
                "original_pending_marker": marker,
                "confirmed_sqlite_effect": effect,
                "store_failed_sticky": opened._health_reason ==
                    "COMMIT_OUTCOME_UNKNOWN_ZERO_AUTO_RETRY",
                "relocated_marker_absent": not Path(
                    str(logical) + ".aion-message-commit-pending"
                ).exists(),
            })
        finally:
            opened.close()
        original_refused = False
        try:
            reopened = SQLiteChatStore(source, strict_local_data_version=True)
        except StorageUnavailableError:
            original_refused = True
        else:
            reopened.close()
        out["original_cold_restart_refused"] = original_refused
        out["relocated_db_cold"] = _cold_read(logical, ACK_SCOPE, cid)
        out["relocation_drops_uncertain_ack_veto"] = (
            uncertain and marker and effect == 1 and original_refused
            and out["relocated_marker_absent"]
            and out["relocated_db_cold"]["health"] == HEALTHY
            and out["relocated_db_cold"]["message_count"] == 1
        )
        out["automatic_retry_attempts"] = 0
    return out


__all__ = [
    "SCHEMA", "SCOPE",
    "probe_cold_restart_after_incomplete_wal_copy",
    "probe_uncertain_ack_marker_not_in_database_backup",
]
