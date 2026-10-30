"""A285 LAB: live SQLite local data_version observation and its limits.

Only disposable local DB files. This is a characterization experiment, not a
VFS/FD identity binding, independent receipt, antirollback control, owner root,
power-loss proof, or operational permission. No production import is required.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any

SCHEMA = "ATLASQUANT_AION_SQLITE_DATA_VERSION_NATIVE_LAB_V1"
MODES = frozenset(("DELETE", "WAL"))


class LocalDataVersionWatch:
    """Same-connection local hint: detect outside commits, latch DENY.

    The official SQLite PRAGMA is a local counter. Changes by the SAME
    connection are not reflected, and a new connection creates a new
    baseline. A stable reading never permits external action.
    """

    def __init__(self, connection: Any) -> None:
        self._connection = connection if type(connection) is sqlite3.Connection else None
        self._baseline = self._read()
        self._denied = self._baseline is None

    def _read(self) -> int | None:
        if self._connection is None:
            return None
        try:
            row = self._connection.execute("PRAGMA data_version").fetchone()
            value = row[0] if row is not None else None
            return value if type(value) is int and value >= 0 else None
        except (sqlite3.Error, ValueError, TypeError):
            return None

    def check(self) -> dict:
        current = self._read()
        if current is None or current != self._baseline:
            self._denied = True
        return {
            "schema": SCHEMA,
            "decision": ("DENY_LOCAL_EXTERNAL_CHANGE_OR_UNAVAILABLE"
                         if self._denied else "UNCHANGED_LOCAL_HINT_NOT_AUTHORITY"),
            "local_change_seen": self._denied,
            "version_observed": current,
            "baseline_version": self._baseline,
            "is_independent_witness": False,
            "can_authorize_read_as_trusted": False,
            "can_authorize_send": False,
            "p0_5_homologated": False,
            "p0_6_homologated": False,
        }


def _base() -> dict:
    return {
        "schema": SCHEMA, "valid": False, "error": "INVALID_INPUT",
        "historical_only": True, "research_only": True,
        "source_sqlite_native": True, "temporary_disposable_database": True,
        "test_class": "NATIVE_SQLITE_LOCAL_CHARACTERIZATION_ONLY",
        "same_inode_native_fd_authenticated": False,
        "antirollback_witness_authenticated": False,
        "physical_power_loss_simulated": False,
        "external_effect_confirmed": False,
        "external_ownership_verified": False,
        "no_provider": True, "no_new_data_calls": True,
        "no_orders": True, "no_alerts": True,
        "zero_auto_resend": True, "authorizes_send": False,
        "p0_homologated": 0,
    }


def probe_live_semantic_reversion(*, journal_mode: Any = "DELETE") -> dict:
    """Two real native connections, 1 -> 2 -> 1 with reader kept open.

    The writes are ordinary committed SQL, NOT raw byte restoration,
    active-file corruption, crash, VFS attack or independent rollback.
    It illustrates why path/inode + quick_check + one content read cannot
    authenticate an immutable business-event history.
    """
    result = _base()
    if type(journal_mode) is not str or journal_mode not in MODES:
        result["error"] = "UNSUPPORTED_JOURNAL_MODE"
        return result
    with TemporaryDirectory(prefix="a285-sqlite-") as temp:
        db_path = Path(temp) / "synthetic.db"
        with closing(sqlite3.connect(str(db_path), isolation_level=None)) as writer:
            actual_mode = str(writer.execute(
                "PRAGMA journal_mode=" + journal_mode
            ).fetchone()[0]).upper()
            if actual_mode != journal_mode:
                result["error"] = "UNAVAILABLE_JOURNAL_MODE"
                return result
            writer.execute("CREATE TABLE semantic_state (id INTEGER PRIMARY KEY, value INTEGER)")
            writer.execute("INSERT INTO semantic_state VALUES (1, 1)")
            with closing(sqlite3.connect(str(db_path), isolation_level=None)) as reader:
                before_stat = db_path.stat()
                watch = LocalDataVersionWatch(reader)
                first = reader.execute(
                    "SELECT value FROM semantic_state WHERE id=1"
                ).fetchone()[0]
                initial_check = watch.check()
                writer.execute("UPDATE semantic_state SET value=2 WHERE id=1")
                second = reader.execute(
                    "SELECT value FROM semantic_state WHERE id=1"
                ).fetchone()[0]
                after_update_check = watch.check()
                writer.execute("UPDATE semantic_state SET value=1 WHERE id=1")
                third = reader.execute(
                    "SELECT value FROM semantic_state WHERE id=1"
                ).fetchone()[0]
                after_reversion_check = watch.check()
                check = reader.execute("PRAGMA quick_check").fetchone()[0]
                after_stat = db_path.stat()
                # A late, freshly opened watcher cannot see prior commits.
                with closing(sqlite3.connect(
                        str(db_path), isolation_level=None)) as late:
                    late_watch = LocalDataVersionWatch(late)
                    late_check = late_watch.check()
                result.update({
                    "valid": True, "error": None,
                    "journal_mode": actual_mode,
                    "observed_values": [first, second, third],
                    "same_path_exists": db_path.is_file(),
                    "same_path_inode": (
                        (before_stat.st_dev, before_stat.st_ino) ==
                        (after_stat.st_dev, after_stat.st_ino)
                    ),
                    "native_integrity_check": str(check).lower() == "ok",
                    "first_check": initial_check,
                    "after_external_update": after_update_check,
                    "after_semantic_reversion": after_reversion_check,
                    "late_open_check": late_check,
                    "same_connection_data_version_counter_only": True,
                    "external_sql_commit_detectable_while_reader_open": (
                        after_update_check["local_change_seen"]
                    ),
                    "late_open_can_attest_prior_history": False,
                    "semantic_reversion_not_byte_level_rollback": True,
                })
    return result


def probe_same_connection_change_not_seen() -> dict:
    """Negative control: same connection writes, data_version stays stable."""
    result = _base()
    with TemporaryDirectory(prefix="a285-sameconn-") as temp:
        db_path = Path(temp) / "synthetic.db"
        with closing(sqlite3.connect(str(db_path), isolation_level=None)) as db:
            db.execute("CREATE TABLE semantic_state (id INTEGER PRIMARY KEY, value INTEGER)")
            db.execute("INSERT INTO semantic_state VALUES (1, 1)")
            watch = LocalDataVersionWatch(db)
            first = db.execute(
                "SELECT value FROM semantic_state WHERE id=1"
            ).fetchone()[0]
            prior = watch.check()
            db.execute("UPDATE semantic_state SET value=9 WHERE id=1")
            after = db.execute(
                "SELECT value FROM semantic_state WHERE id=1"
            ).fetchone()[0]
            following = watch.check()
            result.update({
                "valid": True, "error": None,
                "values": [first, after],
                "initial": prior, "after_same_connection_write": following,
                "same_connection_change_detected_by_data_version": (
                    following["local_change_seen"]
                ),
                "local_hint_is_authority": False,
                "is_p0_security_proof": False,
            })
    return result


__all__ = [
    "SCHEMA", "MODES", "LocalDataVersionWatch",
    "probe_live_semantic_reversion", "probe_same_connection_change_not_seen",
]
