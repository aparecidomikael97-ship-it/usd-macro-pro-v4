"""A174 LAB ONLY: local durable reservation for an uncertain write.

This module is NOT wired to the AION worker or production chat facade.
It supplies a reversible, self-contained lab demonstration of restart-time
duplicate blocking. A host can delete/rollback the entire journal: no
independent receipt, monotonic custodian, or real-effect proof exists.
"""
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import stat


class ReservationDenied(RuntimeError):
    """Attempted resend, payload mismatch or absent reservation."""


class ReservationJournalUnavailable(RuntimeError):
    """Local journal is unreadable, replaced or not trusted by this instance."""


class LocalWriteReservationLab:
    _REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{16,96}\Z")
    _SHA256 = re.compile(r"[0-9a-f]{64}\Z")
    _EFFECT_PART = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")
    _EFFECT_FIELDS = frozenset({"tenant", "provider", "action", "business_id"})

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise ReservationJournalUnavailable("JOURNAL_ABSOLUTE_PATH_REQUIRED")
        self._inspect_parents()
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            pass  # local first bootstrap, not independently attested
        else:
            if not stat.S_ISREG(info.st_mode):
                raise ReservationJournalUnavailable("JOURNAL_NOT_REGULAR_FILE")
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.path), timeout=5, isolation_level=None)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reservations(
                    request_id TEXT PRIMARY KEY,
                    payload_sha256 TEXT NOT NULL,
                    effect_digest TEXT NOT NULL UNIQUE,
                    effect_json TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK(state IN ('PENDING','UNKNOWN'))
                )""")
            cols = {row[1] for row in conn.execute("PRAGMA table_info(reservations)")}
            if cols != {"request_id", "payload_sha256", "effect_digest", "effect_json", "state"}:
                raise ReservationJournalUnavailable("JOURNAL_LEGACY_SCHEMA_UNBOUND")
            if str(conn.execute("PRAGMA quick_check").fetchone()[0]).lower() != "ok":
                raise ReservationJournalUnavailable("JOURNAL_INTEGRITY_FAILED")
        except (sqlite3.DatabaseError, OSError) as exc:
            raise ReservationJournalUnavailable(
                "JOURNAL_BOOTSTRAP_UNAVAILABLE") from exc
        finally:
            if conn is not None:
                conn.close()
        self._identity = self._fingerprint()

    def _inspect_parents(self):
        parent = self.path.parent
        while True:
            try:
                info = parent.lstat()
                maybe_junction = getattr(parent, "is_junction", None)
                junction = bool(maybe_junction()) if callable(maybe_junction) else False
            except OSError as exc:
                raise ReservationJournalUnavailable(
                    "JOURNAL_PARENT_UNAVAILABLE") from exc
            if stat.S_ISLNK(info.st_mode) or junction:
                raise ReservationJournalUnavailable("JOURNAL_PARENT_ALIAS_DENIED")
            if not stat.S_ISDIR(info.st_mode):
                raise ReservationJournalUnavailable("JOURNAL_PARENT_NOT_DIRECTORY")
            if parent.parent == parent:
                break
            parent = parent.parent

    def _fingerprint(self):
        self._inspect_parents()
        try:
            info = self.path.lstat()
        except OSError as exc:
            raise ReservationJournalUnavailable("JOURNAL_MISSING") from exc
        if not stat.S_ISREG(info.st_mode):
            raise ReservationJournalUnavailable("JOURNAL_PATH_ALIAS_DENIED")
        return (info.st_dev, info.st_ino)

    @classmethod
    def _request(cls, request_id):
        value = str(request_id)
        if not cls._REQUEST_ID.fullmatch(value):
            raise ReservationDenied("INVALID_REQUEST_ID")
        return value

    @classmethod
    def _payload(cls, digest):
        value = str(digest)
        if not cls._SHA256.fullmatch(value):
            raise ReservationDenied("INVALID_PAYLOAD_SHA256")
        return value

    @classmethod
    def _effect(cls, descriptor):
        """Canonical business-event identity, NOT proof the caller was honest.

        Callers must provide an immutable business event ID. Reusing a different
        ID for the same real effect remains an external trust problem.
        """
        if type(descriptor) is not dict or set(descriptor) != cls._EFFECT_FIELDS:
            raise ReservationDenied("EFFECT_DESCRIPTOR_REQUIRED")
        if any(type(v) is not str or not cls._EFFECT_PART.fullmatch(v)
               for v in descriptor.values()):
            raise ReservationDenied("INVALID_EFFECT_DESCRIPTOR")
        canonical = json.dumps(
            {"version": "A175:v1", **descriptor},
            ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("ascii")).hexdigest(), canonical

    def _transact(self, action):
        if self._fingerprint() != self._identity:
            raise ReservationJournalUnavailable("JOURNAL_REPLACED")
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.path), timeout=5, isolation_level=None)
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            value = action(conn)
            conn.execute("COMMIT")
            if self._fingerprint() != self._identity:
                # Local commit may already exist; no auto retry.
                raise ReservationJournalUnavailable(
                    "JOURNAL_CHANGED_AFTER_COMMIT")
            return value
        except sqlite3.DatabaseError as exc:
            if conn is not None:
                conn.rollback()
            raise ReservationJournalUnavailable(
                "JOURNAL_TRANSACTION_UNAVAILABLE") from exc
        except BaseException:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()

    def reserve(self, request_id, payload_sha256, effect):
        """Atomic request-ID AND semantic-effect reservation (LAB ONLY).

        The effect descriptor must identify the actual immutable business
        event. This is not an attestation of that event or external delivery.
        """
        request_id = self._request(request_id)
        payload_sha256 = self._payload(payload_sha256)
        effect_digest, effect_json = self._effect(effect)

        def action(conn):
            prior = conn.execute(
                "SELECT payload_sha256,state FROM reservations "
                "WHERE request_id=?", (request_id,)).fetchone()
            if prior is not None:
                if prior[0] != payload_sha256:
                    raise ReservationDenied("PAYLOAD_MISMATCH_DENIED")
                raise ReservationDenied("ALREADY_RESERVED_DENIED")
            prior_effect = conn.execute(
                "SELECT request_id FROM reservations WHERE effect_digest=?",
                (effect_digest,)).fetchone()
            if prior_effect is not None:
                raise ReservationDenied("SEMANTIC_EFFECT_ALREADY_RESERVED")
            conn.execute(
                "INSERT INTO reservations("
                "request_id,payload_sha256,effect_digest,effect_json,state) "
                "VALUES(?,?,?,?,'PENDING')",
                (request_id, payload_sha256, effect_digest, effect_json))
            return {"request_id": request_id, "state": "PENDING",
                    "effect_digest": effect_digest}

        return self._transact(action)

    def mark_unknown(self, request_id):
        """Keep a reserved operation blocked after an ambiguous result."""
        request_id = self._request(request_id)

        def action(conn):
            prior = conn.execute(
                "SELECT state FROM reservations WHERE request_id=?",
                (request_id,)).fetchone()
            if prior is None:
                raise ReservationDenied("RESERVATION_NOT_FOUND")
            if prior[0] == "PENDING":
                conn.execute(
                    "UPDATE reservations SET state='UNKNOWN' "
                    "WHERE request_id=?", (request_id,))
            return {"request_id": request_id, "state": "UNKNOWN"}

        return self._transact(action)

    def status(self, request_id):
        request_id = self._request(request_id)

        def action(conn):
            row = conn.execute(
                "SELECT payload_sha256,state FROM reservations "
                "WHERE request_id=?", (request_id,)).fetchone()
            return None if row is None else {
                "request_id": request_id, "payload_sha256": row[0],
                "state": row[1],
            }

        return self._transact(action)
