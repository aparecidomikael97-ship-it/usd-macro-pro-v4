"""A290 LAB: cache-safe local SQLite authorizer write facade.

Synthetic disposable SQLite only. This is a cooperative in-process
hardening *experiment*, not a production subsystem, independent authority,
host-resistant VFS/FD binding, external ACK proof or P0 homologation.
"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

SCHEMA = "ATLASQUANT_AION_SQLITE_LOCAL_WRITE_GATE_LAB_V1"
MODES = frozenset(("uncached", "cached_rearmed", "cached_unrearmed"))

_WRITE_NAMES = (
    "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE",
    "SQLITE_CREATE_TABLE", "SQLITE_DROP_TABLE", "SQLITE_ALTER_TABLE",
    "SQLITE_CREATE_INDEX", "SQLITE_DROP_INDEX",
    "SQLITE_ATTACH", "SQLITE_DETACH",
)
WRITE_ACTIONS = frozenset(
    getattr(sqlite3, name) for name in _WRITE_NAMES if hasattr(sqlite3, name)
)
_UPDATE_SQL = "UPDATE state SET value=value+1 WHERE id=1"


class LocalWritePermitGate:
    """Only exposes read_value and cooperative trusted_increment.

    The raw Python connection is intentionally accessible as _db for the
    *negative* tests: same-process peers can still bypass Python authority.
    No caller should mistake this for a cryptographic capability.
    """

    def __init__(self, path, *, mode="uncached"):
        if type(mode) is not str or mode not in MODES:
            raise ValueError("unsupported LAB gate mode")
        self.mode = mode
        self._permit = False
        self._closed = False
        self._failed = False
        self._authorizer_update_checks = 0
        self._cache = 0 if mode == "uncached" else 128
        self._db = sqlite3.connect(
            str(path), cached_statements=self._cache, timeout=5
        )
        try:
            self._db.execute(
                "CREATE TABLE state(id INTEGER PRIMARY KEY, value INTEGER NOT NULL)"
            )
            self._db.execute("INSERT INTO state VALUES(1,1)")
            self._db.commit()
            self._db.set_authorizer(self._authorize)
        except Exception:
            self._db.close()
            self._closed = True
            raise

    def _authorize(self, action, first, second, name, trigger):
        if action == sqlite3.SQLITE_UPDATE:
            self._authorizer_update_checks += 1
        if action in WRITE_ACTIONS and not self._permit:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def _require_open(self):
        if self._closed or self._failed:
            raise RuntimeError("LAB local gate closed or failed")

    @contextmanager
    def _authorized_write(self):
        """Application-internal permission, NOT an independent identity."""
        self._require_open()
        if self._permit:
            raise RuntimeError("nested write lease is forbidden in LAB")
        self._permit = True
        try:
            yield
        finally:
            self._permit = False
            if self.mode == "cached_rearmed":
                # Re-installing the authorizer asks CPython to invalidate
                # previously authorized prepared statements. Defense in
                # depth only: whoever holds _db can uninstall it again.
                try:
                    self._db.set_authorizer(self._authorize)
                except sqlite3.DatabaseError:
                    self._failed = True
                    raise

    def trusted_increment(self):
        self._require_open()
        with self._authorized_write():
            try:
                self._db.execute(_UPDATE_SQL)
                self._db.commit()
            except sqlite3.DatabaseError:
                self._db.rollback()
                raise
        return self.read_value()

    def direct_unapproved_increment(self):
        """Negative test of the same SQL outside the cooperative lease."""
        self._require_open()
        self._db.execute(_UPDATE_SQL)
        self._db.commit()

    def read_value(self):
        self._require_open()
        return self._db.execute(
            "SELECT value FROM state WHERE id=1"
        ).fetchone()[0]

    def local_data_version(self):
        self._require_open()
        return self._db.execute("PRAGMA data_version").fetchone()[0]

    def quick_check(self):
        self._require_open()
        return self._db.execute("PRAGMA quick_check").fetchone()[0]

    @property
    def update_authorizations(self):
        return self._authorizer_update_checks

    def close(self):
        if not self._closed:
            self._db.close()
            self._closed = True


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "same_process_cooperation_only": True,
        "authorizes_send": False,
        "no_provider_worker_deploy_orders": True,
        "zero_auto_resend": True,
        "p0_homologated": 0,
        "native_fd_authenticated": False,
        "independent_owner_identity": False,
        "off_host_rollback_floor": False,
    }


def probe_gate_mode(*, mode="uncached"):
    if type(mode) is not str or mode not in MODES:
        raise ValueError("unsupported LAB gate mode")
    result = _base()
    with TemporaryDirectory(prefix="a290-gate-") as raw:
        gate = LocalWritePermitGate(Path(raw) / "staging.db", mode=mode)
        try:
            baseline = gate.local_data_version()
            trusted = gate.trusted_increment()
            callbacks_before = gate.update_authorizations
            blocked = False
            try:
                gate.direct_unapproved_increment()
            except sqlite3.DatabaseError:
                blocked = True
                gate._db.rollback()
            callbacks_second = gate.update_authorizations - callbacks_before
            final = gate.read_value()
            result.update({
                "mode": mode,
                "cached_statements": gate._cache,
                "trusted_increment_value": trusted,
                "second_write_blocked": blocked,
                "final_value": final,
                "second_write_authorizer_checks": callbacks_second,
                "local_data_version_unchanged": (
                    baseline == gate.local_data_version()
                ),
                "quick_check_ok": gate.quick_check() == "ok",
                "raw_python_handle_reachable": hasattr(gate, "_db"),
                "no_public_execute_method": not hasattr(gate, "execute"),
                "rearm_on_revocation": mode == "cached_rearmed",
                "not_an_independent_capability": True,
            })
        finally:
            gate.close()
    return result


def probe_same_process_uninstalls_authorizer():
    """Negative control: possession of the raw _db defeats this guard."""
    result = _base()
    with TemporaryDirectory(prefix="a290-disable-") as raw:
        gate = LocalWritePermitGate(
            Path(raw) / "staging.db", mode="cached_rearmed"
        )
        try:
            trusted = gate.trusted_increment()
            gate._db.set_authorizer(None)
            gate.direct_unapproved_increment()
            result.update({
                "trusted_increment_value": trusted,
                "raw_handle_authorizer_removed": True,
                "write_succeeded_after_removal": gate.read_value() == 3,
                "final_value": gate.read_value(),
                "not_a_host_boundary": True,
            })
        finally:
            gate.close()
    return result


__all__ = [
    "SCHEMA", "MODES", "LocalWritePermitGate",
    "probe_gate_mode", "probe_same_process_uninstalls_authorizer",
]
