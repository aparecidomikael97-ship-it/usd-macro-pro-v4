"""A327: real strict SQLite semantic intent after full host-controlled rollback.

All files are newly created disposable A315 LAB fixtures. An older *valid*
SQLite backup replaces the closed live database, modeling co-rollback by a
host that owns its filesystem. This does NOT prove real power-loss durability,
operational custody, provider outcomes, authorization, or P0 closure.

No network, Worker, deploy, orders, external writes or paid services.
"""
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from aion_chat.models import Message, Scope
from aion_chat.store import HEALTHY, SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_A327_STRICT_INTENT_FULL_ROLLBACK_LAB_V1"
SCOPE = Scope("a327-owner", "a327-tenant", "a327-workspace")
MARKER = ".a315-synthetic-only"
MARKER_CONTENT = "A315 DISPOSABLE SYNTHETIC LAB ONLY\n"
INTENT_A = "a327-first-local-intent"
INTENT_B = "a327-second-local-intent"
BODY_A = "A315 TEST A327 initial synthetic message"
BODY_B = "A315 TEST A327 deterministic second synthetic message"


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "synthetic_fixture_only": True,
        "native_sqlite_used": True,
        "strict_semantic_intent_enabled": True,
        "external_write_or_provider_effect": False,
        "independent_off_host_witness": False,
        "local_pin_is_authenticated": False,
        "native_vfs_fd_identity_attested": False,
        "real_power_loss_durability_proven": False,
        "p0_5_homologated": False,
        "p0_6_homologated": False,
        "p0_homologated": 0,
        "can_restore_real_state": False,
        "can_resume": False,
        "can_replay": False,
        "can_resend": False,
        "can_auto_retry": False,
        "can_authorize_real_effect": False,
        "automatic_retries": 0,
        "zero_auto_resend": True,
        "hard_no_go": True,
        "no_worker_deploy_provider_orders": True,
        "new_paid_services": False,
    }


def _open(path):
    return SQLiteChatStore(
        path,
        strict_local_data_version=True,
        strict_private_write_helpers=True,
        strict_sql_authorizer=True,
        strict_semantic_intent=True,
    )


def _count(path, table):
    if table not in ("messages", "a315_local_intent_receipts"):
        raise ValueError("Table not in A327 fixture allowlist")
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def _quick_check(path):
    with closing(sqlite3.connect(str(path))) as db:
        return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def _digest(path):
    return sha256(path.read_bytes()).hexdigest()


def _append(store, cid, intent, transport, body):
    return store.append_message_once(
        SCOPE,
        Message(cid, "user", body, id=transport),
        intent_id=intent,
    )


def probe_full_host_rollback_strict_semantic_intent():
    """Compare normal restart de-dup with a host-controlled *closed* DB restore.

    Restore is performed only after store.close(), only inside a fresh marked
    temporary fixture, and never through an AION operational restore path.
    The local pin is deliberately editable by the same host, hence not trust.
    """
    out = _base()
    with TemporaryDirectory(prefix="a315-lab-a327-") as raw:
        folder = Path(raw)
        path = folder / "synthetic-chat.sqlite"
        old = folder / "old-committed-snapshot.sqlite"
        staging = folder / "restore-staging.sqlite"
        local_pin = folder / "untrusted-local-pin.json"
        if (not folder.name.startswith("a315-lab-a327-")
                or path.exists() or old.exists() or staging.exists()):
            raise RuntimeError("A327 exclusively creates fresh temporary fixtures")
        (folder / MARKER).write_text(MARKER_CONTENT, encoding="utf-8")

        first_store = _open(path)
        try:
            cid = first_store.create_conversation(
                SCOPE, "A315 TEST A327 disposable synthetic chat"
            ).id
            first = _append(
                first_store, cid, INTENT_A, "a327-transport-a", BODY_A
            )
        finally:
            first_store.close()

        # Native logical backup after a real committed A315 intent.
        with closing(sqlite3.connect(str(path))) as src:
            with closing(sqlite3.connect(str(old))) as dst:
                src.backup(dst)
        out["old_snapshot_sqlite_integrity_ok"] = _quick_check(old)
        out["old_snapshot_messages"] = _count(old, "messages")
        out["old_snapshot_intents"] = _count(
            old, "a315_local_intent_receipts"
        )

        second_store = _open(path)
        try:
            second = _append(
                second_store, cid, INTENT_B, "a327-transport-b", BODY_B
            )
        finally:
            second_store.close()

        # Positive control: an ordinary restart DOES deduplicate intent B.
        ordinary = _open(path)
        try:
            ordinary_replay = _append(
                ordinary, cid, INTENT_B, "a327-normal-restart", BODY_B
            )
        finally:
            ordinary.close()

        out["current_intent_count_before_rollback"] = _count(
            path, "a315_local_intent_receipts"
        )
        out["current_message_count_before_rollback"] = _count(
            path, "messages"
        )
        out["fresh_sqlite_integrity_ok"] = _quick_check(path)
        pin = {
            "schema": SCHEMA, "claimed_intent_count": 2,
            "claimed_sqlite_sha256": _digest(path),
        }
        local_pin.write_text(json.dumps(pin, sort_keys=True), encoding="utf-8")

        # Host has full access to both the SQLite bytes and its local pin.
        # ALL paths above were created in this exact TemporaryDirectory.
        shutil.copy2(old, staging)
        os.replace(staging, path)
        reverted_hash = _digest(path)
        out["older_backup_accepted_by_sqlite_integrity_check"] = (
            _quick_check(path)
        )
        out["restored_older_intent_count"] = _count(
            path, "a315_local_intent_receipts"
        )
        out["unchanged_local_pin_would_notice_rollback"] = (
            pin["claimed_sqlite_sha256"] != reverted_hash
            and pin["claimed_intent_count"]
            != out["restored_older_intent_count"]
        )
        # Deliberate counterexample: same host can co-rollback its "pin".
        local_pin.write_text(json.dumps({
            "schema": SCHEMA, "claimed_intent_count": 1,
            "claimed_sqlite_sha256": reverted_hash,
        }, sort_keys=True), encoding="utf-8")
        edited_pin = json.loads(local_pin.read_text(encoding="utf-8"))
        out["co_rolled_local_pin_matches_old_state"] = (
            edited_pin["claimed_sqlite_sha256"] == reverted_hash
            and edited_pin["claimed_intent_count"]
            == out["restored_older_intent_count"]
        )

        after_restore = _open(path)
        try:
            health = after_restore.storage_health(deep=True)
            repeated = _append(
                after_restore, cid, INTENT_B, "a327-post-rollback", BODY_B
            )
        finally:
            after_restore.close()

        out["first_local_status"] = first["status"]
        out["second_local_status_before_rollback"] = second["status"]
        out["ordinary_restart_status"] = ordinary_replay["status"]
        out["restored_strict_store_healthy_before_reack"] = (
            health["state"] == HEALTHY
        )
        out["post_rollback_same_intent_status"] = repeated["status"]
        out["message_count_after_reack"] = _count(path, "messages")
        out["receipt_count_after_reack"] = _count(
            path, "a315_local_intent_receipts"
        )
        out["local_semantic_reack_after_co_rollback"] = all((
            second["status"] == "LOCAL_ACKED_ONCE",
            ordinary_replay["status"] == "DUPLICATE_LOCAL_NO_EFFECT",
            repeated["status"] == "LOCAL_ACKED_ONCE",
            out["restored_strict_store_healthy_before_reack"],
            out["older_backup_accepted_by_sqlite_integrity_check"],
        ))
    return out


__all__ = [
    "SCHEMA", "probe_full_host_rollback_strict_semantic_intent",
]
