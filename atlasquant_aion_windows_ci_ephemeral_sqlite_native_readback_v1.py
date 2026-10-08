"""AION Windows CI ephemeral SQLite CAS + native readback V1.

Non-production integration test fixture: writes ONLY to an automatically
allocated scratch directory inside an ephemeral GitHub-hosted Windows runner.
No owner workstation, install target, Windows Registry, ACL, startup, service,
reboot, package install, rollback, network, deploy or Worker access.

SQLite is real on-disk storage in this fixture; close/reopen is real, unlike
the in-memory #1061. This DOES NOT prove crash/power-loss durability,
physical AION installation or an independently trusted Windows verifier.
Environment guards are test isolation checks, NOT a security authority.
"""
from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Mapping
import json
import os
import sqlite3
import sys

from atlasquant_aion_windows_synthetic_durable_store_reboot_harness_v1 import (
    STORE_COMMITTED as MEMORY_COMMITTED,
    _valid_intent,
)
from atlasquant_aion_windows_terminal_receipt_persistence_postreboot_health_v1 import (
    INTENT_SCHEMA, INTENT_READY, _digest, _sha,
    validate_terminal_persistence_attestation_shape,
)

SCHEMA = "ATLASQUANT_AION_WINDOWS_EPHEMERAL_SQLITE_NATIVE_READBACK_V1"
CAS_APPLIED = "CI_EPHEMERAL_CAS_APPLIED_UNTRUSTED"
CAS_REJECTED = "CI_EPHEMERAL_CAS_CONFIRMED_NO_WRITE"
CAS_UNKNOWN = "CI_EPHEMERAL_CAS_OUTCOME_UNKNOWN"
READBACK_MATCHED = "CI_EPHEMERAL_DISK_REOPEN_MATCHED_UNTRUSTED"
READBACK_UNKNOWN = "CI_EPHEMERAL_DISK_REOPEN_UNKNOWN"
CLOSED = "CLOSED"
GUARD_REQUIRED = "WINDOWS_GITHUB_RUNNER_TEMP_REQUIRED"
POLICY = {
    "schema": SCHEMA,
    "github_hosted_ephemeral_runner_only": True,
    "allows_ci_scratch_sqlite_write": True,
    "test_only": True,
    "physical_ci_disk_write_can_occur": True,
    "owner_workstation_writes_allowed": False,
    "production_store_connected": False,
    "install_target_accessed": False,
    "windows_registry_changed": False,
    "windows_acl_changed": False,
    "startup_entry_changed": False,
    "service_created": False,
    "reboot_performed": False,
    "package_installed": False,
    "owner_authorization_consumed": False,
    "install_token_consumed": False,
    "real_aion_started": False,
    "aion_health_attested": False,
    "physical_install_trusted": False,
    "durable_power_loss_verified": False,
    "production_receipt_persisted": False,
    "independent_windows_attestor_implemented": False,
    "automatic_retry_after_unknown_allowed": False,
    "reinstall_authorized": False,
    "deploy_executed": False,
    "worker_activated": False,
}

_COLUMNS = (
    "installation_id", "store_identity_digest", "record_key_digest",
    "write_intent_digest", "terminal_candidate_digest", "terminal_outcome",
    "journal_plan_digest", "owner_sid_digest", "host_identity_digest",
    "package_manifest_digest", "target_snapshot_digest", "write_nonce_digest",
    "prior_state", "prior_revision", "terminal_state", "revision",
    "record_digest",
)
_INSERT_COLS = ", ".join(_COLUMNS)
_QS = ", ".join("?" for _ in _COLUMNS)


def _outcome(state: str, reason: str, *, record_digest: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "record_digest": record_digest, "ci_ephemeral_only": True,
        "physical_ci_disk_written": state in (CAS_APPLIED, CAS_UNKNOWN),
        "physical_aion_installed": False, "receipt_persisted_trusted": False,
        "automatic_retry_allowed": False,
        "owner_install_authorization_consumed": False,
    }


def _assert_windows_runner() -> Path:
    """Fail closed unless invoked by the Windows CI test job.

    Environment values are spoofable and do NOT establish security identity.
    No production code must import or invoke this writer.
    """
    if (
        os.name != "nt"
        or sys.platform != "win32"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_OS") != "Windows"
        or os.environ.get("AION_CI_EPHEMERAL_DISK_TEST") != "1"
        or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
    ):
        raise RuntimeError(GUARD_REQUIRED)
    raw = os.environ.get("RUNNER_TEMP", "")
    if not raw:
        raise RuntimeError(GUARD_REQUIRED)
    runner_temp = Path(raw)
    if not runner_temp.is_dir() or runner_temp.is_symlink():
        raise RuntimeError(GUARD_REQUIRED)
    return runner_temp.resolve(strict=True)


class WindowsCIEphemeralSQLite(AbstractContextManager):
    """On-disk test-only CAS; directory is auto-created inside RUNNER_TEMP."""

    def __init__(self, store_identity_digest: str, *, initial_revision: int = 0) -> None:
        base = _assert_windows_runner()
        if not _sha(store_identity_digest) or type(initial_revision) is not int or initial_revision < 0:
            raise ValueError("invalid fixture identity/revision")
        self.identity = store_identity_digest
        self._temp = TemporaryDirectory(prefix="aion-ci-sqlite-", dir=str(base))
        self._root = Path(self._temp.name).resolve(strict=True)
        if base not in self._root.parents:
            self._temp.cleanup()
            raise RuntimeError("TEST_TEMP_OUTSIDE_RUNNER_ROOT")
        self._db = self._root / "terminal-receipt-test.sqlite3"
        self._closed = False
        self._unknown_ids: set[str] = set()
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE meta (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    revision INTEGER NOT NULL CHECK(revision >= 0),
                    store_identity_digest TEXT NOT NULL
                );
                CREATE TABLE receipts (
                    installation_id TEXT PRIMARY KEY,
                    store_identity_digest TEXT NOT NULL,
                    record_key_digest TEXT NOT NULL,
                    write_intent_digest TEXT NOT NULL,
                    terminal_candidate_digest TEXT NOT NULL,
                    terminal_outcome TEXT NOT NULL,
                    journal_plan_digest TEXT NOT NULL,
                    owner_sid_digest TEXT NOT NULL,
                    host_identity_digest TEXT NOT NULL,
                    package_manifest_digest TEXT NOT NULL,
                    target_snapshot_digest TEXT NOT NULL,
                    write_nonce_digest TEXT NOT NULL,
                    prior_state TEXT NOT NULL,
                    prior_revision INTEGER NOT NULL,
                    terminal_state TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    record_digest TEXT NOT NULL
                );
            """)
            conn.execute(
                "INSERT INTO meta (id, revision, store_identity_digest) VALUES (1, ?, ?)",
                (initial_revision, store_identity_digest),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._closed:
            raise RuntimeError(CLOSED)
        # Every usage owns a new connection and closes the Windows file handle.
        con = sqlite3.connect(str(self._db), isolation_level=None, timeout=1.0)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA busy_timeout=1000")
            yield con
        finally:
            con.close()

    def read_reopen(self, installation_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM receipts WHERE installation_id=?", (installation_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def revision_reopen(self) -> int:
        with self._connect() as con:
            row = con.execute("SELECT revision FROM meta WHERE id=1").fetchone()
        if row is None:
            raise RuntimeError("STORE_META_MISSING")
        return int(row["revision"])

    def commit(self, intent: Mapping[str, Any], *, fault: str = "none") -> dict[str, Any]:
        if fault not in ("none", "before_commit", "after_commit_ack_loss"):
            return _outcome(CAS_REJECTED, "UNKNOWN_FAULT")
        if (intent.get("schema") != INTENT_SCHEMA or not _valid_intent(intent)
                or intent.get("durable_store_identity_digest") != self.identity):
            return _outcome(CAS_REJECTED, "INVALID_OR_FOREIGN_INTENT")
        install_id = intent["installation_id"]
        if install_id in self._unknown_ids:
            return _outcome(CAS_REJECTED, "ACK_UNKNOWN_REQUIRES_RECONCILIATION")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            old = con.execute(
                "SELECT revision, store_identity_digest FROM meta WHERE id=1"
            ).fetchone()
            if old is None or old["store_identity_digest"] != self.identity:
                con.rollback()
                return _outcome(CAS_REJECTED, "STORE_IDENTITY_CHANGED")
            if con.execute(
                "SELECT 1 FROM receipts WHERE installation_id=?", (install_id,)
            ).fetchone() is not None:
                con.rollback()
                return _outcome(CAS_REJECTED, "TERMINAL_ALREADY_ASSIGNED")
            if int(old["revision"]) != intent["expected_revision"]:
                con.rollback()
                return _outcome(CAS_REJECTED, "STALE_CAS_REVISION")
            if fault == "before_commit":
                con.rollback()
                return _outcome(CAS_REJECTED, "INJECTED_CONFIRMED_NO_WRITE")
            row = {
                "installation_id": install_id,
                "store_identity_digest": self.identity,
                "record_key_digest": intent["record_key_digest"],
                "write_intent_digest": intent["write_intent_digest"],
                "terminal_candidate_digest": intent["terminal_candidate_digest"],
                "terminal_outcome": intent["terminal_outcome"],
                "journal_plan_digest": intent["journal_plan_digest"],
                "owner_sid_digest": intent["owner_sid_digest"],
                "host_identity_digest": intent["host_identity_digest"],
                "package_manifest_digest": intent["package_manifest_digest"],
                "target_snapshot_digest": intent["target_snapshot_digest"],
                "write_nonce_digest": intent["write_nonce_digest"],
                "prior_state": "NONE",
                "prior_revision": int(old["revision"]),
                "terminal_state": intent["committed_terminal_state_if_written"],
                "revision": intent["next_revision_if_written"],
            }
            record_digest = _digest(row)
            con.execute(
                f"INSERT INTO receipts ({_INSERT_COLS}) VALUES ({_QS})",
                tuple([row[col] for col in _COLUMNS[:-1]] + [record_digest]),
            )
            updated = con.execute(
                "UPDATE meta SET revision=? WHERE id=1 AND revision=?",
                (intent["next_revision_if_written"], intent["expected_revision"]),
            )
            if updated.rowcount != 1:
                con.rollback()
                return _outcome(CAS_REJECTED, "CAS_LOST_RACE")
            con.commit()
        if fault == "after_commit_ack_loss":
            self._unknown_ids.add(install_id)
            return _outcome(CAS_UNKNOWN, "INJECTED_ACK_LOSS_POST_COMMIT")
        return _outcome(CAS_APPLIED, "EPHEMERAL_SQLITE_CAS_COMMITTED", record_digest=record_digest)

    def reconcile_reopen(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        record = self.read_reopen(str(intent.get("installation_id", "")))
        expected = _sha(intent.get("write_intent_digest"))
        match = bool(record and record.get("write_intent_digest") == expected
                     and record.get("record_digest") == _digest({
                         col: record[col] for col in _COLUMNS[:-1]
                     }))
        return {
            "schema": SCHEMA,
            "state": READBACK_MATCHED if match else READBACK_UNKNOWN,
            "record_present": record is not None,
            "disk_reopen_record_matched": match,
            "record_digest": record.get("record_digest", "") if record else "",
            "unknown_ack_in_memory": intent.get("installation_id") in self._unknown_ids,
            "trusted_independent_attestor": False,
            "power_loss_durability_proven": False,
            "physical_aion_installed": False,
            "automatic_retry_allowed": False,
        }

    def attestation_envelope_untrusted(
        self, intent: Mapping[str, Any], outcome: Mapping[str, Any],
        *, synthetic_verifier_manifest_digest: str,
    ) -> dict[str, Any]:
        if outcome.get("state") != CAS_APPLIED or not _sha(synthetic_verifier_manifest_digest):
            return {"state": READBACK_UNKNOWN, "trusted": False}
        record = self.read_reopen(intent["installation_id"])
        if (
            record is None
            or record.get("record_digest") != outcome.get("record_digest")
            or record.get("record_digest") != _digest({
                col: record[col] for col in _COLUMNS[:-1]
            })
            or record.get("write_intent_digest") != intent.get("write_intent_digest")
        ):
            return {"state": READBACK_UNKNOWN, "trusted": False}
        payload = {
            "observed_record_digest": record["record_digest"],
            "cas_write_receipt_digest": _digest({"test_only": True, "record": record["record_digest"]}),
            "cas_observation_digest": _digest({
                "test_only": True, "prior": record["prior_revision"], "next": record["revision"],
            }),
            "read_after_write_digest": _digest({"test_only": True, "record": record}),
            "independent_reopen_digest": _digest({"ci_test_reopened_sqlite": True, "record": record}),
            "independent_verifier_manifest_digest": synthetic_verifier_manifest_digest,
            "observed_installation_id": record["installation_id"],
            "observed_record_key_digest": record["record_key_digest"],
            "observed_terminal_candidate_digest": record["terminal_candidate_digest"],
            "observed_terminal_state": record["terminal_state"],
            "observed_revision": record["revision"],
            "observed_prior_state": record["prior_state"],
            "observed_prior_revision": record["prior_revision"],
            "observed_owner_sid_digest": record["owner_sid_digest"],
            "observed_host_identity_digest": record["host_identity_digest"],
            "observed_terminal_outcome": record["terminal_outcome"],
            "write_attempt_nonce_digest": record["write_nonce_digest"],
        }
        envelope = validate_terminal_persistence_attestation_shape(intent, **payload)
        envelope["ci_ephemeral_disk_only"] = True
        envelope["independent_windows_attestor_trusted"] = False
        envelope["actual_windows_installation_verified"] = False
        envelope["power_loss_durability_verified"] = False
        return envelope

    def __enter__(self) -> "WindowsCIEphemeralSQLite":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._closed = True
        self._temp.cleanup()


def ci_readiness_policy() -> dict[str, Any]:
    return deepcopy(POLICY)


__all__ = [
    "SCHEMA", "WindowsCIEphemeralSQLite", "CAS_APPLIED", "CAS_REJECTED",
    "CAS_UNKNOWN", "READBACK_MATCHED", "READBACK_UNKNOWN", "POLICY",
    "ci_readiness_policy", "GUARD_REQUIRED",
]
