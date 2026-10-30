"""A289 LAB — SQLite authorizer compile-time/cache lease bypass characterization.

Real CPython sqlite3 (3.12) statements in memory and one disposable
SQLiteChatStore file. No production import of the probes, no provider/Worker,
no external send/order, no independent FD/history custody, no P0 closure.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from aion_chat.models import Scope
from aion_chat.store import HEALTHY, SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_SQLITE_AUTHORIZER_CACHE_LAB_V1"
MODES = frozenset((
    "cached_dynamic", "uncached_dynamic", "reinstall_after_revoke",
    "disable_authorizer", "distinct_sql",
))
SCOPE = Scope("owner-a289", "tenant-a289", "workspace-a289")


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "native_sqlite": True,
        "zero_auto_resend": True,
        "no_provider_worker_deploy_orders": True,
        "is_independent_witness": False,
        "native_fd_authenticated": False,
        "off_host_rollback_floor": False,
        "p0_homologated": 0,
        "can_authorize_send": False,
    }


def probe_dynamic_authorizer_reuse(*, mode="cached_dynamic"):
    """Same SQL compiled once with a grant, then executed after revocation.

    Crucial distinction: sqlite3 authorizer is evaluated at *compile time*;
    changing a Python Boolean is not a reliable revocation of cached SQL.
    This is a native local counterexample, not a production mitigation.
    """
    if type(mode) is not str or mode not in MODES:
        raise ValueError("unsupported LAB authorizer mode")
    cache = 0 if mode == "uncached_dynamic" else 128
    result = _base()
    with closing(sqlite3.connect(":memory:", cached_statements=cache)) as db:
        db.execute("CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER)")
        db.execute("INSERT INTO state VALUES (1, 1)")
        db.commit()
        local_grant = {"open": True}
        update_checks = []

        def authorizer(operation, arg1, arg2, db_name, trigger):
            if operation == sqlite3.SQLITE_UPDATE:
                update_checks.append((arg1, bool(local_grant["open"])))
                if not local_grant["open"]:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorizer)
        initial_version = db.execute("PRAGMA data_version").fetchone()[0]
        sql = "UPDATE state SET value=value+1 WHERE id=1"
        db.execute(sql)
        db.commit()
        after_trusted = db.execute(
            "SELECT value FROM state WHERE id=1"
        ).fetchone()[0]
        trusted_update_checks = len(update_checks)
        local_grant["open"] = False
        if mode == "reinstall_after_revoke":
            db.set_authorizer(authorizer)
        elif mode == "disable_authorizer":
            # A caller with the raw Python connection can remove the guard.
            # This is a deliberate negative control, NEVER a safe policy.
            db.set_authorizer(None)

        second_sql = (
            "UPDATE state SET value=value+2 WHERE id=1"
            if mode == "distinct_sql" else sql
        )
        second_blocked = False
        try:
            db.execute(second_sql)
            db.commit()
        except sqlite3.DatabaseError:
            second_blocked = True
            db.rollback()
        second_update_checks = len(update_checks) - trusted_update_checks
        final_version = db.execute("PRAGMA data_version").fetchone()[0]
        value = db.execute(
            "SELECT value FROM state WHERE id=1"
        ).fetchone()[0]
        integrity = str(db.execute("PRAGMA quick_check").fetchone()[0]).lower()
        result.update({
            "mode": mode,
            "cached_statements": cache,
            "trusted_update_value": after_trusted,
            "final_value": value,
            "second_update_blocked": second_blocked,
            "authorized_update_checks": trusted_update_checks,
            "after_revoke_update_checks": second_update_checks,
            "new_authorizer_installed": mode == "reinstall_after_revoke",
            "authorizer_disabled_by_same_process": mode == "disable_authorizer",
            "local_data_version_unchanged": initial_version == final_version,
            "native_quick_check_ok": integrity == "ok",
            "callback_not_runtime_write_proof": True,
        })
    return result


def probe_cached_select_authorizer_reuse():
    """SELECT, too, may reuse a previously authorized compiled statement."""
    result = _base()
    with closing(sqlite3.connect(":memory:", cached_statements=128)) as db:
        db.execute("CREATE TABLE state (value INTEGER)")
        db.execute("INSERT INTO state VALUES (7)")
        db.commit()
        grant = {"open": True}
        read_checks = []

        def authorizer(action, arg1, arg2, db_name, trigger):
            if action == sqlite3.SQLITE_READ:
                read_checks.append(grant["open"])
                if not grant["open"]:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorizer)
        sql = "SELECT value FROM state"
        first = db.execute(sql).fetchone()[0]
        baseline_checks = len(read_checks)
        grant["open"] = False
        allowed_after_revoke = False
        try:
            second = db.execute(sql).fetchone()[0]
            allowed_after_revoke = True
        except sqlite3.DatabaseError:
            second = None
        result.update({
            "first_value": first,
            "second_value": second,
            "read_returned_after_revoke": allowed_after_revoke,
            "first_compile_checks": baseline_checks,
            "second_compile_checks": len(read_checks) - baseline_checks,
            "no_realtime_per_step_authorizer_proof": True,
        })
    return result


def probe_real_store_same_handle_write():
    """Raw direct writes on the very handle a strict A288 store uses.

    A288's data_version only sees OTHER-connection commits. The store's
    publicly accessible raw Python db reference is not a trust boundary.
    """
    result = _base()
    with TemporaryDirectory(prefix="a289-realstore-") as raw:
        path = Path(raw) / "staging.db"
        store = SQLiteChatStore(path, strict_local_data_version=True)
        try:
            conv = store.create_conversation(SCOPE, "original")
            inode = (path.stat().st_dev, path.stat().st_ino)
            baseline = store._read_local_data_version()
            before = store.storage_health(deep=True)
            row = store.db.execute(
                "SELECT data FROM conversations WHERE id=?", (conv.id,)
            ).fetchone()
            edited = json.loads(row[0])
            edited["title"] = "raw-same-handle"
            store.db.execute(
                "UPDATE conversations SET title=?, data=? WHERE id=?",
                (edited["title"], json.dumps(edited), conv.id),
            )
            store.db.commit()
            returned = store.get_conversation(SCOPE, conv.id)
            after = store.storage_health(deep=True)
            final_version = store._read_local_data_version()
            result.update({
                "strict_mode_active": store._strict_local_data_version,
                "returned_raw_same_handle_title": returned.title,
                "same_path_inode": inode == (
                    path.stat().st_dev, path.stat().st_ino
                ),
                "version_unchanged": baseline == final_version,
                "health_before": before["state"],
                "health_after": after["state"],
                "integrity_ok": after["quick_check"] == "ok",
                "pending_chat_commit_marker_exists": (
                    store._message_commit_marker.exists()
                ),
                "raw_handle_is_not_independent_authority": True,
            })
        finally:
            store.close()
    return result


__all__ = [
    "SCHEMA", "MODES", "probe_dynamic_authorizer_reuse",
    "probe_cached_select_authorizer_reuse",
    "probe_real_store_same_handle_write",
]
