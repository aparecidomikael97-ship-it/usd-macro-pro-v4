"""AION V2 isolated SQLite witness CAS reference; NO remote witness or authority.

Proves disk-persistent local CAS, serialized compare-and-swap, append-chain
integrity and crash/replay scenarios. This is a *different SQLite file* from
AION Chat/V2 hold DB, but NOT an independently protected trust anchor: the
privileged operator can restore/replace BOTH, including this file. There is
no network, witness private key, owner enrollment, provider call or billing.
All signatures are independently created by disposable CI fixtures.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from atlasquant_aion_v2_authenticated_witness_read_cas_reference import (
    CAS_CANDIDATE, READ_ROLE, READ_PURPOSE, READ_SCHEMA,
    review_reference_witness_cas_preconditions,
)
from atlasquant_aion_v2_external_witness_rollback_reference import (
    signed_receipt_sha256,
)

SCHEMA = "ATLASQUANT_AION_V2_ISOLATED_SQLITE_WITNESS_CAS_REFERENCE_V1"
COMMITTED = "REFERENCE_SQLITE_CAS_COMMITTED_UNTRUSTED"
REPLAY = "REFERENCE_SQLITE_ALREADY_COMMITTED_UNTRUSTED"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_CONFIG = frozenset({
    "witness_service_id", "witness_key_id", "witness_public_pin_sha256",
    "collector_public_pin_sha256", "owner_id", "tenant_id", "workspace_id",
    "period_id", "policy_generation", "owner_pin_sha256", "witness_epoch",
})
_HEAD = frozenset({
    "witness_epoch", "sequence", "receipt_sha256", "snapshot_sha256",
    "hold_count", "held_micro_usd", "limit_micro_usd",
})
FALSE_GATES = {
    "reference_file_only": True,
    "independent_protected_witness_verified": False,
    "witness_key_enrollment_verified": False,
    "remote_authenticated_read_verified": False,
    "production_monotonicity_verified": False,
    "cross_store_atomicity_verified": False,
    "owner_consent_verified": False,
    "owner_identity_verified": False,
    "real_budget_reserved": False,
    "real_witness_service_activated": False,
    "provider_request_approved": False,
    "model_invocation_authorized": False,
    "model_invocation_executed": False,
    "provider_called": False,
    "network_called": False,
    "billing_authorized": False,
    "installer_authorized": False,
    "safe_to_resume": False,
}


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":"))


def _digest(obj: Any) -> str:
    return sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _strict_int(v: Any, lo: int, hi: int) -> bool:
    return type(v) is int and lo <= v <= hi


def _hash(v: Any) -> bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _token(v: Any) -> bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _valid_head(head: Any) -> bool:
    return (type(head) is dict and set(head) == _HEAD
            and _strict_int(head["witness_epoch"], 1, 2**31-1)
            and _strict_int(head["sequence"], 1, 2**63-1)
            and _hash(head["receipt_sha256"])
            and _hash(head["snapshot_sha256"])
            and _strict_int(head["hold_count"], 0, 2**63-1)
            and _strict_int(head["held_micro_usd"], 0, 2_000_000_000)
            and _strict_int(head["limit_micro_usd"], 1, 2_000_000_000)
            and head["held_micro_usd"] <= head["limit_micro_usd"])


def _valid_config(config: Any) -> bool:
    return (type(config) is dict and set(config) == _CONFIG
            and all(_token(config[k]) for k in (
                "witness_service_id", "witness_key_id", "owner_id",
                "tenant_id", "workspace_id",
            ))
            and all(_hash(config[k]) for k in (
                "witness_public_pin_sha256",
                "collector_public_pin_sha256", "owner_pin_sha256",
            ))
            and type(config["period_id"]) is str
            and bool(re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",
                                  config["period_id"]))
            and _strict_int(config["witness_epoch"], 1, 2**31-1)
            and _strict_int(config["policy_generation"], 1, 2**31-1))


def pin_sha256(pin: Any) -> str:
    if (type(pin) is not dict or set(pin) != {"key_id", "public_key_hex"}
        or not _token(pin["key_id"]) or not _hash(pin["public_key_hex"])):
        raise ValueError("exact synthetic public pin required")
    return _digest(pin)


def _out(state: str, reason: str, *, head: Any = None,
         count: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "reason": reason,
        "reference_cas_committed": state == COMMITTED,
        "reference_idempotent_read_only": state == REPLAY,
        "current_local_witness_head": head if state != "BLOCKED" else None,
        "local_reference_appends": count if state != "BLOCKED" else 0,
        **FALSE_GATES,
    }


class ReferenceIsolatedSqliteWitnessCAS:
    """Independent *file* with local transactional CAS (not independent trust).

    The caller can choose the file and genesis. Any restored file with an old
    internally coherent chain looks valid WITHOUT an independently protected
    head floor. Never deploy or treat a COMMITTED result as paid consent.
    """

    def __init__(self, path: str | Path, *,
                 config: Mapping[str, Any], genesis_head: Mapping[str, Any]):
        if not _valid_config(config) or not _valid_head(genesis_head):
            raise ValueError("closed witness config/genesis required")
        if (genesis_head["witness_epoch"] != config["witness_epoch"]
            or genesis_head["sequence"] != 1
            or genesis_head["hold_count"] != 0
            or genesis_head["held_micro_usd"] != 0):
            raise ValueError("reference genesis must start at seq 1, no holds")
        self.config = dict(config)
        self.genesis = dict(genesis_head)
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            tables = {
                r[0] for r in self.db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            expected = {"witness_ref_state", "witness_ref_appends"}
            if tables and tables != expected:
                raise ValueError("unknown/partial witness reference DB; no reset")
            self.db.execute("PRAGMA busy_timeout=10000")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS witness_ref_state (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  config_json TEXT NOT NULL, genesis_json TEXT NOT NULL,
                  current_json TEXT NOT NULL
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS witness_ref_appends (
                  sequence INTEGER PRIMARY KEY,
                  operation_id TEXT UNIQUE NOT NULL,
                  query_sha256 TEXT NOT NULL,
                  next_receipt_sha256 TEXT NOT NULL UNIQUE,
                  previous_receipt_sha256 TEXT NOT NULL,
                  snapshot_sha256 TEXT NOT NULL,
                  hold_count INTEGER NOT NULL,
                  held_micro_usd INTEGER NOT NULL
                )
            """)
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM witness_ref_state WHERE singleton=1"
            ).fetchone()
            if row is None:
                if tables:
                    raise ValueError("cannot reinitialize missing state row")
                self.db.execute(
                    "INSERT INTO witness_ref_state VALUES (1,?,?,?)",
                    (_canonical(self.config), _canonical(self.genesis),
                     _canonical(self.genesis)),
                )
            self._verified_head()
            self.db.commit()
        except Exception:
            if self.db.in_transaction:
                self.db.rollback()
            self.db.close()
            raise

    def _verified_head(self) -> tuple[dict[str, Any], int]:
        row = self.db.execute(
            "SELECT * FROM witness_ref_state WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise ValueError("missing witness state")
        if (row["config_json"] != _canonical(self.config)
            or row["genesis_json"] != _canonical(self.genesis)):
            raise ValueError("witness config/genesis mismatch; no rollover")
        if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("witness file integrity failure")
        try:
            current = json.loads(row["current_json"])
        except (ValueError,TypeError):
            raise ValueError("invalid witness current head")
        if not _valid_head(current) or row["current_json"] != _canonical(current):
            raise ValueError("uncanonical witness head")
        prior = dict(self.genesis)
        events = self.db.execute(
            "SELECT * FROM witness_ref_appends ORDER BY sequence"
        ).fetchall()
        for record in events:
            if (record["sequence"] != prior["sequence"] + 1
                or record["previous_receipt_sha256"] != prior["receipt_sha256"]
                or record["hold_count"] != prior["hold_count"] + 1
                or not _strict_int(record["held_micro_usd"],
                                    prior["held_micro_usd"] + 1,
                                    prior["limit_micro_usd"])
                or not _hash(record["snapshot_sha256"])
                or not _hash(record["next_receipt_sha256"])
                or not _hash(record["query_sha256"])
                or not _token(record["operation_id"])):
                raise ValueError("witness local append chain inconsistent")
            prior = {
                "witness_epoch": prior["witness_epoch"],
                "sequence": record["sequence"],
                "receipt_sha256": record["next_receipt_sha256"],
                "snapshot_sha256": record["snapshot_sha256"],
                "hold_count": record["hold_count"],
                "held_micro_usd": record["held_micro_usd"],
                "limit_micro_usd": prior["limit_micro_usd"],
            }
        if current != prior:
            raise ValueError("witness head not anchored to local append chain")
        return current, len(events)

    def snapshot(self) -> dict[str, Any]:
        try:
            self.db.execute("BEGIN IMMEDIATE")
            head, count = self._verified_head()
            self.db.commit()
            return _out("LOCAL_REFERENCE_HEAD_ONLY", "NOT_A_REMOTE_WITNESS",
                        head=head, count=count)
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            if self.db.in_transaction:
                self.db.rollback()
            return _out("BLOCKED", "LOCAL_WITNESS_FILE_UNAVAILABLE_OR_CORRUPT")

    def unsigned_read_candidate(self, query: Any) -> dict[str, Any]:
        """Request body for fixture to sign; this product code NEVER signs."""
        state = self.snapshot()
        if state["state"] == "BLOCKED":
            raise ValueError("witness storage not readable")
        if type(query) is not dict or set(query) != {
            "witness_service_id", "owner_id", "tenant_id", "workspace_id",
            "period_id", "policy_generation", "owner_pin_sha256",
            "challenge_nonce_hex", "minimum_witness_epoch",
        }:
            raise ValueError("exact challenge required")
        if any(query.get(k) != self.config[k] for k in (
            "witness_service_id", "owner_id", "tenant_id", "workspace_id",
            "period_id", "policy_generation", "owner_pin_sha256",
        )):
            raise ValueError("scope/policy mismatch")
        if (not _hash(query["challenge_nonce_hex"])
            or query["challenge_nonce_hex"] == "0"*64
            or not _strict_int(query["minimum_witness_epoch"], 1, 2**31-1)
            or query["minimum_witness_epoch"] > self.config["witness_epoch"]):
            raise ValueError("challenge or witness epoch rejected")
        head = state["current_local_witness_head"]
        return {
            "schema": READ_SCHEMA, "purpose": READ_PURPOSE,
            "role": READ_ROLE, "witness_key_id": self.config["witness_key_id"],
            "witness_service_id": query["witness_service_id"],
            "owner_id": query["owner_id"], "tenant_id": query["tenant_id"],
            "workspace_id": query["workspace_id"],
            "period_id": query["period_id"],
            "policy_generation": query["policy_generation"],
            "owner_pin_sha256": query["owner_pin_sha256"],
            "challenge_nonce_hex": query["challenge_nonce_hex"],
            "minimum_witness_epoch": query["minimum_witness_epoch"],
            "witness_epoch": head["witness_epoch"],
            "head_sequence": head["sequence"],
            "head_receipt_sha256": head["receipt_sha256"],
            "head_snapshot_sha256": head["snapshot_sha256"],
            "head_hold_count": head["hold_count"],
            "head_held_micro_usd": head["held_micro_usd"],
            "head_limit_micro_usd": head["limit_micro_usd"],
        }

    def cas_reference_only(
        self, *, operation_id: Any, expected_query: Any,
        signed_read: Any, witness_public_pin: Any,
        signed_next_collector_receipt: Any,
        collector_public_pin: Any,
    ) -> dict[str, Any]:
        """Local SQLite CAS. Even COMMITTED is not a trusted remote commit."""
        if not _token(operation_id):
            return _out("BLOCKED", "OPERATION_ID_INVALID")
        try:
            if (pin_sha256(witness_public_pin) !=
                    self.config["witness_public_pin_sha256"]
                or pin_sha256(collector_public_pin) !=
                    self.config["collector_public_pin_sha256"]):
                return _out("BLOCKED", "REFERENCE_KEY_PIN_CHANGED")
            next_hash = signed_receipt_sha256(signed_next_collector_receipt)
            query_hash = _digest({
                "query": expected_query, "signed_read": signed_read,
            })
        except (ValueError, TypeError, OverflowError):
            return _out("BLOCKED", "REFERENCE_CAS_INPUT_INVALID")
        try:
            self.db.execute("BEGIN IMMEDIATE")
            head, count = self._verified_head()
            old = self.db.execute(
                "SELECT * FROM witness_ref_appends WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if old is not None:
                if (old["next_receipt_sha256"] == next_hash
                    and old["query_sha256"] == query_hash):
                    self.db.commit()
                    return _out(REPLAY, "PREVIOUS_LOCAL_CAS_ONLY_NO_REEXECUTION",
                                head=head, count=count)
                self.db.rollback()
                return _out("BLOCKED", "OPERATION_ID_REBOUND_OR_PAYLOAD_CHANGED")
            outcome = review_reference_witness_cas_preconditions(
                read_response=signed_read,
                trusted_witness_pin=witness_public_pin,
                expected_query=expected_query,
                current_service_head=head,
                signed_next_collector_receipt=signed_next_collector_receipt,
                collector_public_pin=collector_public_pin,
            )
            if outcome["state"] != CAS_CANDIDATE:
                self.db.rollback()
                return _out("BLOCKED", "SIGNED_READ_CAS_PRECONDITIONS_REJECTED")
            next_head = outcome["proposed_head"]
            self.db.execute("""
                INSERT INTO witness_ref_appends(
                  sequence, operation_id, query_sha256, next_receipt_sha256,
                  previous_receipt_sha256, snapshot_sha256, hold_count, held_micro_usd
                ) VALUES (?,?,?,?,?,?,?,?)
            """, (
                next_head["sequence"], operation_id, query_hash, next_hash,
                head["receipt_sha256"], next_head["snapshot_sha256"],
                next_head["hold_count"], next_head["held_micro_usd"],
            ))
            self.db.execute(
                "UPDATE witness_ref_state SET current_json=? WHERE singleton=1",
                (_canonical(next_head),),
            )
            verified, updated_count = self._verified_head()
            if verified != next_head or updated_count != count + 1:
                raise ValueError("atomic witness local ledger divergence")
            self.db.commit()
            return _out(COMMITTED, "LOCAL_REFERENCE_CAS_ONLY_NO_AUTHORITY",
                        head=next_head, count=updated_count)
        except (sqlite3.Error, ValueError, TypeError, OverflowError):
            if self.db.in_transaction:
                self.db.rollback()
            return _out("BLOCKED", "REFERENCE_SQLITE_CAS_ROLLED_BACK")

    def compare_supplied_external_anchor(self, expected_anchor: Any):
        """Never trust this *caller supplied* anchor as real independent trust."""
        snapshot = self.snapshot()
        if snapshot["state"] == "BLOCKED":
            return snapshot
        if not _valid_head(expected_anchor):
            return _out("BLOCKED", "PROTECTED_EXTERNAL_ANCHOR_REQUIRED")
        if snapshot["current_local_witness_head"] != expected_anchor:
            return _out("BLOCKED", "LOCALLY_RESTORED_WITNESS_BEHIND_ANCHOR")
        return _out("LOCAL_ANCHOR_EQUALITY_MATH_ONLY",
                    "CALLER_CAN_FORGE_OR_REPLAY_EXPECTED_ANCHOR",
                    head=expected_anchor, count=snapshot["local_reference_appends"])

    def close(self):
        self.db.close()


__all__ = [
    "SCHEMA", "COMMITTED", "REPLAY", "FALSE_GATES", "pin_sha256",
    "ReferenceIsolatedSqliteWitnessCAS",
]
