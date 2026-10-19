"""OFFLINE P0 H0 custody-domain contract model, NOT a Cloudflare integration.

Uses two *ordinary local* SQLite files as educational models of executor and
separately administered durable-custody state. All responses remain NO-GO.
A local SQLite file is NEVER an external trust root, enrolled custodian, signed
witness, durable monotonic Cloudflare proof or producer/no-effect receipt.

Tests demonstrate:
- compare-and-swap prevents two modeled reservations for one intent;
- an ambiguous response NEVER licenses a second reservation/retry;
- rollback of executor alone can be observed if custody survives;
- rollback of BOTH domains is locally indistinguishable (PITR/admin threat).

NO Wrangler, HTTP, tokens, cloud account, authentication, signer, Worker,
trading, SMS, external provider, dispatch or real execution code.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re
import sqlite3
from typing import Any

LAB_SCHEMA = "AION_P0_H0_CUSTODY_TWO_DOMAINS_OFFLINE_MODEL_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9._:-]{8,128}\Z")
_NONCE = re.compile(r"[A-Za-z0-9_-]{24,128}\Z")
_FALSE = {
    "independent_custodian_enrolled": False,
    "custodian_identity_authenticated": False,
    "custodian_signature_verified": False,
    "custody_is_outside_executor": False,
    "external_highwater_verified": False,
    "rollback_ruled_out": False,
    "first_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "producer_effect_authenticated": False,
    "external_action_executed": False,
}


def _result(reason: str, **details: Any) -> dict[str, Any]:
    return {
        "schema": LAB_SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "simulation_only": True,
        **_FALSE,
        **details,
    }


def _valid_scope(scope: Any) -> bool:
    return type(scope) is str and bool(_SHA.fullmatch(scope))


def _valid_intent(value: Any) -> bool:
    return type(value) is str and bool(_TOKEN.fullmatch(value))


def _valid_nonce(value: Any) -> bool:
    return type(value) is str and bool(_NONCE.fullmatch(value))


def _valid_digest(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value))


def _valid_seq(value: Any) -> bool:
    return type(value) is int and 0 <= value < 2**63 - 1


def _valid_epoch(value: Any) -> bool:
    return type(value) is int and 1 <= value < 2**63 - 1


def _open_existing(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise OSError("custody unavailable or path untrusted")
    # Read/write only an existing local test DB; NEVER create an implicit
    # 'fresh witness' after rollback or a missing database.
    db = sqlite3.connect(p.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
    db.execute("PRAGMA busy_timeout=10000")
    return db


def initialize_model_fixture(path: str | Path, scope: str, *, epoch: int = 1) -> None:
    """Creates fake fixture ONLY. Calling this is NOT external enrollment."""
    if not _valid_scope(scope) or not _valid_epoch(epoch):
        raise ValueError("invalid local-model fixture scope or epoch")
    p = Path(path)
    if p.exists():
        raise FileExistsError("never reinitialize existing custodian model")
    with closing(sqlite3.connect(p)) as db:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("""CREATE TABLE witness_head (
            scope TEXT PRIMARY KEY, epoch INTEGER NOT NULL,
            sequence INTEGER NOT NULL, digest TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE intent_reservations (
            scope TEXT NOT NULL, intent TEXT NOT NULL, nonce TEXT NOT NULL,
            intent_digest TEXT NOT NULL, reserved_sequence INTEGER NOT NULL,
            PRIMARY KEY(scope, intent), UNIQUE(scope, nonce)
        )""")
        db.execute("INSERT INTO witness_head VALUES (?,?,?,?)", (scope, epoch, 0, "0" * 64))
        db.commit()


def reserve_first_attempt_model(
    path: str | Path, *, scope: Any, intent: Any, nonce: Any,
    intent_digest: Any, expected_sequence: Any, epoch: Any = 1,
    _caller_verified_claim: Any = None,
) -> dict[str, Any]:
    """Local CAS model. SUCCESSFUL MODEL RESERVATION IS STILL NOT AUTHORITY.

    Do not inspect _caller_verified_claim: caller input can't enroll custody.
    """
    if not (_valid_scope(scope) and _valid_intent(intent)
            and _valid_nonce(nonce) and _valid_digest(intent_digest)
            and _valid_seq(expected_sequence) and _valid_epoch(epoch)):
        return _result("MODEL_INPUT_INVALID")
    try:
        with closing(_open_existing(path)) as db:
            db.execute("BEGIN IMMEDIATE")
            head = db.execute(
                "SELECT epoch,sequence,digest FROM witness_head WHERE scope=?", (scope,)
            ).fetchone()
            if head is None:
                db.rollback()
                return _result("MODEL_SCOPE_NOT_ENROLLED")
            if head[0] != epoch:
                db.rollback()
                return _result("MODEL_EPOCH_MISMATCH")
            if db.execute(
                "SELECT 1 FROM intent_reservations WHERE scope=? AND intent=?",
                (scope, intent),
            ).fetchone():
                db.rollback()
                return _result("MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT")
            if db.execute(
                "SELECT 1 FROM intent_reservations WHERE scope=? AND nonce=?",
                (scope, nonce),
            ).fetchone():
                db.rollback()
                return _result("MODEL_NONCE_REUSED")
            if head[1] != expected_sequence:
                db.rollback()
                return _result("MODEL_EXPECTED_HEAD_MISMATCH")
            if expected_sequence >= 2**63 - 2:
                db.rollback()
                return _result("MODEL_SEQUENCE_EXHAUSTED")
            new_seq = expected_sequence + 1
            # This is a synthetic atomic state transition, NOT a cryptographic
            # signature, remote compare-and-swap or payment/send authorization.
            affected = db.execute(
                "UPDATE witness_head SET sequence=?, digest=? "
                "WHERE scope=? AND epoch=? AND sequence=?",
                (new_seq, intent_digest, scope, epoch, expected_sequence),
            ).rowcount
            if affected != 1:
                db.rollback()
                return _result("MODEL_CAS_CONFLICT")
            db.execute(
                "INSERT INTO intent_reservations "
                "(scope,intent,nonce,intent_digest,reserved_sequence) VALUES (?,?,?,?,?)",
                (scope, intent, nonce, intent_digest, new_seq),
            )
            db.commit()
            return _result("MODEL_RESERVED_NOT_AUTHORITY",
                           model_reserved_sequence=new_seq,
                           local_cas_committed_in_fixture=True)
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return _result("MODEL_CUSTODY_UNAVAILABLE_OR_CORRUPTED")


def compare_boot_highwater_model(
    path: str | Path, *, scope: Any, local_sequence: Any,
    local_digest: Any = None, _caller_verified_claim: Any = None,
) -> dict[str, Any]:
    """Read modeled custody state; never verify an actual remote custodian."""
    if not _valid_scope(scope) or not _valid_seq(local_sequence):
        return _result("MODEL_INPUT_INVALID")
    if local_digest is not None and not _valid_digest(local_digest):
        return _result("MODEL_INPUT_INVALID")
    try:
        with closing(_open_existing(path)) as db:
            head = db.execute(
                "SELECT epoch,sequence,digest FROM witness_head WHERE scope=?", (scope,)
            ).fetchone()
            if head is None or not _valid_epoch(head[0]) or not _valid_seq(head[1]):
                return _result("MODEL_CUSTODY_ROW_MISSING_OR_INVALID")
            if head[1] > local_sequence:
                kind = "MODEL_LOCAL_ROLLBACK_SUSPECTED"
            elif head[1] < local_sequence:
                kind = "MODEL_CUSTODY_STALE_OR_FORK_SUSPECTED"
            elif local_digest is not None and head[2] != local_digest:
                kind = "MODEL_SAME_SEQUENCE_DIGEST_FORK"
            else:
                kind = "MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF"
            return _result(kind, model_custody_epoch=head[0],
                           model_custody_sequence=head[1],
                           model_local_sequence=local_sequence)
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return _result("MODEL_CUSTODY_UNAVAILABLE_OR_CORRUPTED")
