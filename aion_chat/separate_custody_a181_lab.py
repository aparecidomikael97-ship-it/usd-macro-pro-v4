"""A181 LAB: independently stored first-attempt reservation custodian.

Runs on a separate SQLite file only as a TEST DOUBLE for a future EXTERNAL
authority. This is not independent by itself: caller-controlled disk, signer,
clock and key bootstrap can all be rolled back, replaced or forged.

Security objective being tested: once a signed first attempt is reserved and
the local AION Outbox disappears, the custodian still rejects re-reservation
of the same DECLARED effect, even under another technical request ID.
"""
from __future__ import annotations

import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
from typing import Callable, Mapping

from aion_chat.first_attempt_witness_lab import DOMAIN, SCHEMA
from aion_chat.signed_receipt_lab import canonical_bytes


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_FIELDS = frozenset({
    "idempotency_key", "effect_digest", "decision_sha256",
    "owner_id", "tenant_id", "workspace_id",
})


class CustodyUnavailable(RuntimeError):
    """No witnessed first reservation can be asserted."""


class SeparateSQLiteCustodyLab:
    """A two-file simulation only; NOT a production external witness.

    A different path on the same machine is NOT independent custody.
    bootstrap_lab() is deliberately EXPLICIT: open_existing() never creates
    a new empty database when the old one disappears.
    """

    def __init__(
        self, path: Path, *, issuer: str, key_id: str,
        signer: Callable[[bytes], bytes], now: datetime,
    ):
        self.path = Path(path)
        if (type(issuer) is not str or not _NAME.fullmatch(issuer)
                or type(key_id) is not str or not _NAME.fullmatch(key_id)):
            raise ValueError("invalid synthetic custodian identity")
        if not callable(signer):
            raise TypeError("synthetic signing callback required")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("aware fixture clock required")
        self.issuer, self.key_id = issuer, key_id
        self._signer = signer
        self._now = now.astimezone(timezone.utc)
        self._verify_schema()

    @classmethod
    def bootstrap_lab(cls, path, *, issuer, key_id, signer, now):
        """Explicit TEST enrollment. Never call this automatically on recovery.

        WARNING: a malicious operator can recreate this journal after its
        deletion; no real anti-rollback guarantee is provided.
        """
        path = Path(path)
        if not path.parent.is_dir() or path.exists():
            raise CustodyUnavailable("CUSTODY_BOOTSTRAP_REQUIRES_FRESH_LOCATION")
        with closing(sqlite3.connect(str(path), timeout=5)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE custody_meta("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "issuer TEXT NOT NULL,key_id TEXT NOT NULL,"
                "high_water INTEGER NOT NULL CHECK(high_water>=0))"
            )
            db.execute(
                "CREATE TABLE first_attempts("
                "effect_digest TEXT PRIMARY KEY,request_id TEXT NOT NULL,"
                "decision_sha256 TEXT NOT NULL,owner_id TEXT NOT NULL,"
                "tenant_id TEXT NOT NULL,workspace_id TEXT NOT NULL,"
                "sequence INTEGER NOT NULL UNIQUE)"
            )
            db.execute(
                "INSERT INTO custody_meta(singleton,issuer,key_id,high_water)"
                " VALUES(1,?,?,0)", (issuer,key_id)
            )
            db.commit()
        return cls(path, issuer=issuer, key_id=key_id,
                   signer=signer, now=now)

    def _connect(self):
        if not self.path.is_file():
            raise CustodyUnavailable("CUSTODY_FILE_MISSING_DENY")
        # The file may vanish after is_file(); a fresh SQLite db then lacks
        # the required schema, fails verification and must not bootstrap.
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _verify_schema(self):
        try:
            with closing(self._connect()) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise CustodyUnavailable("CUSTODY_INTEGRITY_FAILED")
                names = {
                    row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if names != {"custody_meta", "first_attempts"}:
                    raise CustodyUnavailable("CUSTODY_SCHEMA_UNTRUSTED")
                meta = db.execute(
                    "SELECT issuer,key_id,high_water FROM custody_meta "
                    "WHERE singleton=1"
                ).fetchone()
                if (meta is None or meta[0] != self.issuer
                        or meta[1] != self.key_id
                        or type(meta[2]) is not int or meta[2] < 0):
                    raise CustodyUnavailable("CUSTODY_IDENTITY_OR_ORDINAL_UNTRUSTED")
        except (sqlite3.DatabaseError, OSError) as exc:
            raise CustodyUnavailable("CUSTODY_UNAVAILABLE") from exc

    @staticmethod
    def _validate(challenge, request):
        if type(challenge) is not str or not _DIGEST.fullmatch(challenge):
            raise ValueError("invalid 256-bit challenge")
        if type(request) is not dict or set(request) != _FIELDS:
            raise ValueError("exact reservation fields required")
        for field in ("idempotency_key", "effect_digest", "decision_sha256"):
            if type(request[field]) is not str or not _DIGEST.fullmatch(request[field]):
                raise ValueError("invalid reservation digest")
        for field in ("owner_id", "tenant_id", "workspace_id"):
            if type(request[field]) is not str or not _NAME.fullmatch(request[field]):
                raise ValueError("invalid scope")

    def reserve(self, challenge, request):
        """Persist reservation BEFORE returning a synthetic signed proof.

        Failure after COMMIT but before returning the signature still leaves
        the request blocked on restart. Non-atomic external side effects and
        actual provider identity cannot be proven by this simulation.
        """
        self._validate(challenge, request)
        try:
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    meta = db.execute(
                        "SELECT issuer,key_id,high_water FROM custody_meta "
                        "WHERE singleton=1"
                    ).fetchone()
                    if (meta is None or meta[0] != self.issuer
                            or meta[1] != self.key_id):
                        raise CustodyUnavailable("CUSTODY_META_MISSING")
                    if db.execute(
                        "SELECT 1 FROM first_attempts WHERE effect_digest=?",
                        (request["effect_digest"],)
                    ).fetchone():
                        db.rollback()
                        return {"status": "ALREADY_RESERVED"}
                    seq = int(meta[2]) + 1
                    db.execute(
                        "INSERT INTO first_attempts("
                        "effect_digest,request_id,decision_sha256,"
                        "owner_id,tenant_id,workspace_id,sequence)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (request["effect_digest"], request["idempotency_key"],
                         request["decision_sha256"], request["owner_id"],
                         request["tenant_id"], request["workspace_id"], seq)
                    )
                    db.execute(
                        "UPDATE custody_meta SET high_water=? WHERE singleton=1",
                        (seq,)
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
        except (sqlite3.DatabaseError, OSError) as exc:
            raise CustodyUnavailable("CUSTODY_RESERVATION_NOT_VERIFIABLE") from exc

        # Deliberately sign AFTER durable commit. If signer fails there is
        # no SEND and the reservation remains locked; zero auto resend.
        signed = {
            "schema": SCHEMA,
            "status": "RESERVED",
            "issuer": self.issuer,
            "key_id": self.key_id,
            "challenge": challenge,
            "sequence": seq,
            "issued_at": self._now.isoformat(),
            "expires_at": (self._now + timedelta(seconds=40)).isoformat(),
            **request,
        }
        signature = self._signer(DOMAIN + canonical_bytes(signed))
        if type(signature) is not bytes or len(signature) != 64:
            raise CustodyUnavailable("CUSTODY_SIGNER_UNAVAILABLE")
        return {
            "payload": signed,
            "signature": base64.b64encode(signature).decode("ascii"),
        }

    def snapshot(self):
        """Read-only status for LAB assertions. Not authenticated evidence."""
        with closing(self._connect()) as db:
            return {
                "high_water": db.execute(
                    "SELECT high_water FROM custody_meta WHERE singleton=1"
                ).fetchone()[0],
                "count": db.execute(
                    "SELECT count(*) FROM first_attempts"
                ).fetchone()[0],
            }


__all__ = ["CustodyUnavailable", "SeparateSQLiteCustodyLab"]
