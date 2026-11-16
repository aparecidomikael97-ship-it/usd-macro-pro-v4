"""LAB-only durable anti-replay floor for signed, sanitized FX28 Radar status.

Receives an *injected, explicitly configured* SQLite connection. The
application/administrator is responsible for a private server-side disk,
file permissions, backups, secret provisioning, clock integrity, TLS and
trusted bootstrap. No HTTP server, consumer, scheduler, MT5, or account
authentication is implemented or activated by this module.

The receiver locks SQLite with BEGIN IMMEDIATE, verifies HMAC + expiry
against the latest high-water mark, updates the mark with an SQL compare-
and-swap, commits it *before* returning the displayable status. A stale,
forged, altered or same-sequence message cannot pass after a process
restart, PROVIDED the original private database was not rolled back,
deleted, cloned or replaced. Reset/restore risks remain HARD NO-GO.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any
import sqlite3

from atlasquant_trader_fx28_signed_status_envelope_lab import (
    AUDIENCE, ISSUER, KEY_ID,
    verify_fx28_sanitized_radar_status_lab,
)

SCHEMA = "ATLASQUANT_FX28_DURABLE_REPLAY_FLOOR_SQLITE_LAB_V1"
TABLE = "atlasquant_fx28_replay_floor_v1"
APP_ID = 0x41515831  # 'AQX1', lab database fingerprint, not an auth proof
_VERIFIED = "LAB_FX28_SIGNED_RADAR_STATUS_KEY_HOLDER_ONLY_NO_GO"
_DDL = """
CREATE TABLE atlasquant_fx28_replay_floor_v1 (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  key_id TEXT NOT NULL CHECK (key_id = 'fx28-status-lab-v1'),
  audience TEXT NOT NULL CHECK (audience = 'ATLASQUANT_TRADER_RADAR_PRIVATE_LAB_V1'),
  issuer_claim TEXT NOT NULL CHECK (issuer_claim = 'AM12_FX28_LOCAL_RESEARCH_PUBLISHER_CLAIM_V1'),
  highest_accepted_sequence INTEGER NOT NULL
      CHECK (highest_accepted_sequence BETWEEN 0 AND 9223372036854775807),
  last_envelope_sha256 TEXT
      CHECK (last_envelope_sha256 IS NULL OR length(last_envelope_sha256) = 64)
)
"""


def _result(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SQLITE_REPLAY_REJECTED_NO_GO",
        "reason": reason,
        "sanitized_report": None,
        "db_transaction_committed": False,
        "highest_accepted_sequence_after_commit": None,
        "client_sent_raw_market_prices": False,
        "broker_source_independently_authenticated": False,
        "device_identity_independently_authenticated": False,
        "clock_independently_attested": False,
        "secret_installed_by_this_code": False,
        "transport_configured": False,
        "production_store_provisioned": False,
        "sqlite_disk_configured_by_caller_only": True,
        "durability_survives_disk_rollback_or_backup_restore": False,
        "trade_authorized": False,
        "score_unlocked": False,
        "mt5_calls": 0,
        "http_requests": 0,
        "database_rows_written": 0,
        "operational_bias": "AGUARDAR",
    }


def _conn_ready(conn: Any) -> bool:
    """Require a file-backed SQLite DB with FULL/EXTRA sync and safe journal."""
    if not isinstance(conn, sqlite3.Connection) or conn.in_transaction:
        return False
    try:
        attached = conn.execute("PRAGMA database_list").fetchall()
        if (len(attached) != 1 or attached[0][1] != "main"
                or not isinstance(attached[0][2], str)
                or not attached[0][2]):
            return False  # :memory:, temp/ATTACH, or ambiguous DB path
        sync = conn.execute("PRAGMA main.synchronous").fetchone()
        journal = conn.execute("PRAGMA main.journal_mode").fetchone()
        if (not sync or type(sync[0]) is not int or sync[0] < 2
                or not journal or str(journal[0]).lower() not in ("delete", "wal", "truncate", "persist")):
            return False
        return True
    except sqlite3.Error:
        return False


def bootstrap_fx28_replay_floor_sqlite_lab(
    *, conn: Any, explicitly_authorized_new_empty_database: Any,
) -> bool:
    """One-time lab initialization ONLY in a *new empty* durable database.

    Does not support reinitialization, migration, counter reset or restore.
    A production bootstrap policy would need authenticated administration.
    """
    if explicitly_authorized_new_empty_database is not True or not _conn_ready(conn):
        return False
    try:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM main.sqlite_master "
            "WHERE type IN ('table','view','trigger','index') "
            "AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        if count != 0 or conn.execute("PRAGMA main.user_version").fetchone()[0] != 0:
            conn.rollback()
            return False
        conn.execute(_DDL)
        conn.execute(
            f"INSERT INTO {TABLE} (id,key_id,audience,issuer_claim,"
            "highest_accepted_sequence,last_envelope_sha256) VALUES (1,?,?,?,0,NULL)",
            (KEY_ID, AUDIENCE, ISSUER))
        conn.execute(f"PRAGMA main.user_version = 1")
        conn.execute(f"PRAGMA main.application_id = {APP_ID}")
        conn.commit()
        return True
    except sqlite3.Error:
        if conn.in_transaction:
            conn.rollback()
        return False


def receive_fx28_signed_status_once_sqlite_lab(
    *, conn: Any, raw_envelope: Any,
    secret_key: Any, received_at_utc: Any,
) -> dict[str, Any]:
    """Atomic read/verify/advance; commit BEFORE exposing sanitized_report.

    Serialize across separate connections/processes using BEGIN IMMEDIATE.
    The caller should open the DB with FULL sync, private ACLs and a
    nonzero busy timeout. No retry, reset, network, or key persistence here.
    """
    out = _result("REPLAY_SQLITE_CONNECTION_NOT_DURABLE_OR_NOT_READY")
    if not _conn_ready(conn):
        return out
    try:
        conn.execute("BEGIN IMMEDIATE")
        identity = conn.execute(
            f"SELECT key_id,audience,issuer_claim,highest_accepted_sequence "
            f"FROM {TABLE} WHERE id=1").fetchone()
        total = conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()
        app_id = conn.execute("PRAGMA main.application_id").fetchone()
        version = conn.execute("PRAGMA main.user_version").fetchone()
        if (identity is None or total is None or total[0] != 1
                or identity[:3] != (KEY_ID,AUDIENCE,ISSUER)
                or type(identity[3]) is not int
                or not 0 <= identity[3] < 2**63
                or app_id[0] != APP_ID or version[0] != 1):
            conn.rollback()
            out["reason"] = "REPLAY_DB_SCHEMA_IDENTITY_OR_HIGH_WATER_INVALID"
            return out
        prior = identity[3]
        checked = verify_fx28_sanitized_radar_status_lab(
            raw_envelope=raw_envelope,
            secret_key=secret_key,
            received_at_utc=received_at_utc,
            trusted_last_sequence=prior)
        if checked.get("state") != _VERIFIED or checked.get("trade_authorized") is not False:
            conn.rollback()
            out["reason"] = "SIGNED_RECEIPT_INVALID_EXPIRED_OR_REPLAYED"
            return out
        next_seq = checked["proposed_new_sequence_for_external_atomic_commit"]
        if type(next_seq) is not int or next_seq <= prior:
            conn.rollback()
            out["reason"] = "NONMONOTONIC_VERIFIED_SEQUENCE"
            return out
        digest = sha256(raw_envelope).hexdigest()
        updated = conn.execute(
            f"UPDATE {TABLE} SET highest_accepted_sequence=?,"
            "last_envelope_sha256=? "
            "WHERE id=1 AND highest_accepted_sequence=?",
            (next_seq,digest,prior))
        if updated.rowcount != 1:
            conn.rollback()
            out["reason"] = "ATOMIC_SEQUENCE_UPDATE_FAILED"
            return out
        # COMMIT is the security boundary. Fail-closed on I/O errors.
        conn.commit()
    except (sqlite3.Error, ValueError, TypeError, RuntimeError):
        try:
            if isinstance(conn, sqlite3.Connection) and conn.in_transaction:
                conn.rollback()
        except sqlite3.Error:
            pass
        out["reason"] = "REPLAY_SQLITE_ATOMIC_READ_VERIFY_COMMIT_FAILED"
        return out

    out.update({
        "state": "LAB_FX28_SQLITE_REPLAY_ADVANCED_KEY_HOLDER_ONLY_NO_GO",
        "reason": "DURABLE_SEQUENCE_ADVANCED_NOT_BROKER_SOURCE_PROOF",
        "sanitized_report": checked["sanitized_report"],
        "highest_accepted_sequence_after_commit": next_seq,
        "db_transaction_committed": True,
        "database_rows_written": 1,
    })
    return out


__all__ = (
    "SCHEMA","TABLE","APP_ID",
    "bootstrap_fx28_replay_floor_sqlite_lab",
    "receive_fx28_signed_status_once_sqlite_lab",
)
