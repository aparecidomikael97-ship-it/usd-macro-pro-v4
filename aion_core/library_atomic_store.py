"""Sandbox-only single-transaction PostgreSQL contract for AION Library.

This storage component is not an HTTP endpoint or authentication mechanism.
The trusted host owns the verifier, connection factory and catalog ingestion.
An approval commits the consumed nonce, document-state change and audit event
in ONE DB transaction. On any error it rolls back all three, then fails closed.
No existing SQLite gateway, Business ledger or production service is modified.
"""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from .library_authorization import AttestationVerifier, AuthorizationDenied, _encode
from .library_foundation import CatalogEntry, verify_entry_integrity

# This DDL is guidance for PRIVILEGED migrations only; never executed by the app.
MIGRATION_POSTGRESQL = """\
CREATE TABLE aion_library_documents (
  entry_id VARCHAR(28) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL,
  domain_id VARCHAR(64) NOT NULL,
  document_id VARCHAR(128) NOT NULL,
  version INTEGER NOT NULL CHECK (version > 0),
  content_sha256 CHAR(64) NOT NULL,
  license_kind VARCHAR(32) NOT NULL,
  usage_scope VARCHAR(32) NOT NULL,
  rights_holder VARCHAR(128) NOT NULL,
  human_approved_by VARCHAR(64) NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  source_reference VARCHAR(256) NOT NULL,
  state VARCHAR(32) NOT NULL CHECK (state IN ('METADATA_REVIEW','APPROVED_FOR_INDEXING','REVOKED')),
  UNIQUE(tenant_id,domain_id,document_id,version)
);
CREATE TABLE aion_library_atomic_approval_burns (
  approval_key CHAR(64) PRIMARY KEY,
  binding_sha256 CHAR(64) NOT NULL,
  burned_at_unix BIGINT NOT NULL
);
CREATE TABLE aion_library_atomic_audit (
  seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id VARCHAR(28) NOT NULL REFERENCES aion_library_documents(entry_id),
  prev_hash CHAR(64) NOT NULL,
  event_hash CHAR(64) NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  state_from VARCHAR(32) NOT NULL,
  state_to VARCHAR(32) NOT NULL,
  approval_key CHAR(64) NOT NULL,
  recorded_at_unix BIGINT NOT NULL
);
CREATE INDEX aion_library_atomic_audit_by_entry ON aion_library_atomic_audit(entry_id,seq);
-- Protected DB roles must forbid UPDATE/DELETE on audit and burn tables.
-- A DBA can rewrite this hash-chain: externally sign/checkpoint its digest
-- before considering any production-grade tamper evidence.
"""

_IMPORT = """INSERT INTO aion_library_documents
 (entry_id,tenant_id,domain_id,document_id,version,content_sha256,
  license_kind,usage_scope,rights_holder,human_approved_by,source_type,source_reference,state)
 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
_SELECT = """SELECT tenant_id,domain_id,document_id,version,content_sha256,license_kind,
 usage_scope,rights_holder,human_approved_by,source_type,source_reference,state
 FROM aion_library_documents WHERE entry_id=%s AND tenant_id=%s AND domain_id=%s FOR UPDATE"""
_LAST = """SELECT seq,prev_hash,event_hash,event_type,state_from,state_to,approval_key,recorded_at_unix
 FROM aion_library_atomic_audit WHERE entry_id=%s ORDER BY seq DESC LIMIT 1"""
_BURN = """INSERT INTO aion_library_atomic_approval_burns
 (approval_key,binding_sha256,burned_at_unix) VALUES (%s,%s,%s)
 ON CONFLICT (approval_key) DO NOTHING RETURNING approval_key"""
_UPDATE = """UPDATE aion_library_documents SET state='APPROVED_FOR_INDEXING'
 WHERE entry_id=%s AND tenant_id=%s AND domain_id=%s AND state='METADATA_REVIEW'"""
_AUDIT = """INSERT INTO aion_library_atomic_audit
 (entry_id,prev_hash,event_hash,event_type,state_from,state_to,approval_key,recorded_at_unix)
 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def _sha(value: object) -> str:
    return hashlib.sha256(_encode(value)).hexdigest()


def _valid_id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _connect(factory: Callable[[], object]):
    db = factory()
    if db is None or getattr(db, "autocommit", None) is not False:
        _safe_close(None, db)
        raise AuthorizationDenied("transactional database connection required")
    return db


def _safe_rollback(db):
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass


def _safe_close(cursor, db):
    if cursor is not None:
        try:
            cursor.close()
        except Exception:
            pass
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


@dataclass(frozen=True)
class AtomicApprovalReceipt:
    entry_id: str
    tenant_id: str
    domain_id: str
    state: str
    audit_hash: str


class AtomicLibraryStore:
    """Trusted-host DB port; an entry is never approved through raw caller metadata.

    `import_reviewed` is exclusively for trusted migration of catalog entries,
    NOT untrusted user input. App routes must only expose `approve` through a
    trusted identity bridge and never expose this class to external callers.
    """

    def __init__(self, *, connect: Callable[[], object], verifier: AttestationVerifier,
                 clock: Callable[[], int] | None = None):
        if not callable(connect) or type(verifier) is not AttestationVerifier:
            raise AuthorizationDenied("trusted atomic storage configuration required")
        if clock is not None and not callable(clock):
            raise AuthorizationDenied("trusted clock required")
        self._connect = connect
        self._verifier = verifier
        self._clock = clock or (lambda: int(time.time()))

    def _now(self):
        now = self._clock()
        if type(now) is not int or now < 0:
            raise AuthorizationDenied("invalid trusted clock")
        return now

    def import_reviewed(self, *, trusted_entry: CatalogEntry):
        """Host-only migration import; insert metadata-review row AND genesis audit atomically."""
        if (type(trusted_entry) is not CatalogEntry or
                trusted_entry.state != "METADATA_REVIEW" or
                not verify_entry_integrity(trusted_entry)["integrity_ok"] or
                not all(_valid_id(v) for v in (trusted_entry.entry_id, trusted_entry.tenant_id,
                                               trusted_entry.domain_id, trusted_entry.document_id)) or
                type(trusted_entry.version) is not int or trusted_entry.version < 1 or
                type(trusted_entry.sha256) is not str or not _HEX.fullmatch(trusted_entry.sha256)):
            raise AuthorizationDenied("trusted reviewed document invalid")
        now = self._now()
        db = cursor = None
        try:
            db = _connect(self._connect)
            cursor = db.cursor()
            cursor.execute(_IMPORT, (trusted_entry.entry_id, trusted_entry.tenant_id, trusted_entry.domain_id,
                trusted_entry.document_id, trusted_entry.version, trusted_entry.sha256,
                trusted_entry.license_kind, trusted_entry.usage_scope, trusted_entry.rights_holder,
                trusted_entry.human_approved_by, trusted_entry.source_type,
                trusted_entry.source_reference, trusted_entry.state))
            event = self._event("GENESIS", "RECEIVED", "METADATA_REVIEW", "0"*64, "0"*64, now)
            cursor.execute(_AUDIT, (trusted_entry.entry_id, *event))
            db.commit()
            return trusted_entry.entry_id
        except Exception as exc:
            _safe_rollback(db)
            raise AuthorizationDenied("document import denied; transaction rolled back") from exc
        finally:
            _safe_close(cursor, db)

    @staticmethod
    def _event(kind: str, before: str, after: str, previous: str, approval_key: str, now: int):
        # First entry's prev hash is zero; later entries link to last event hash.
        body = [previous, kind, before, after, approval_key, now]
        return previous, _sha(body), kind, before, after, approval_key, now

    def approve(self, *, tenant_id: str, domain_id: str, entry_id: str,
                identity_envelope: dict, approval_envelope: dict, rights_envelope: dict) -> AtomicApprovalReceipt:
        if not all(_valid_id(x) for x in (tenant_id, domain_id, entry_id)):
            raise AuthorizationDenied("invalid operation scope")
        now = self._now()
        identity = self._verifier.verify("identity", identity_envelope)
        approval = self._verifier.verify("approval", approval_envelope)
        rights = self._verifier.verify("rights", rights_envelope)
        if (identity["tenant_id"],identity["domain_id"],identity["action"]) != (tenant_id,domain_id,"APPROVE_INDEX"):
            raise AuthorizationDenied("identity scope or action mismatch")
        if not set(identity["roles"]) & {"LIBRARY_REVIEWER", "LIBRARY_ADMIN"}:
            raise AuthorizationDenied("trusted reviewer role required")
        db = cursor = None
        try:
            db = _connect(self._connect)
            cursor = db.cursor()
            cursor.execute(_SELECT, (entry_id, tenant_id, domain_id))
            row = cursor.fetchone()
            if row is None or len(row) != 12 or row[-1] != "METADATA_REVIEW":
                raise AuthorizationDenied("document unavailable for approval")
            # A lock can wait. Recheck ALL expiry/revocation-aware proof verifiers
            # after acquiring the document row lock and before side effects.
            for kind, envelope in (("identity", identity_envelope),
                                   ("approval", approval_envelope), ("rights", rights_envelope)):
                self._verifier.verify(kind, envelope)
            now = self._now()
            fields = ("tenant_id", "domain_id", "document_id", "version", "sha256", "license_kind", "usage_scope")
            values = dict(zip(fields, row[:7]))
            if any(approval[f] != values[f] or rights[f] != values[f] for f in fields):
                raise AuthorizationDenied("document and signed proof mismatch")
            rights_holder, human, source_type, source_ref = row[7:11]
            if (not human or human != identity["subject"] or approval["reviewer"] != human or
                    not rights_holder or rights["rights_holder"] != rights_holder or
                    not source_type or not source_ref or values["license_kind"] in ("", "UNKNOWN", "ALL_RIGHTS_RESERVED") or
                    rights["rights_action"] != ("PUBLISH" if values["usage_scope"] == "PUBLISHED" else "INDEX")):
                raise AuthorizationDenied("reviewer, origin or legal rights insufficient")
            # Require an existing genesis event; no approval from unsourced DB rows.
            cursor.execute(_LAST, (entry_id,))
            last = cursor.fetchone()
            if (last is None or len(last) != 8 or last[3] != "GENESIS" or last[5] != "METADATA_REVIEW" or
                    last[1] != "0"*64 or last[6] != "0"*64 or
                    last[2] != _sha([last[1], last[3], last[4], last[5], last[6], last[7]])):
                raise AuthorizationDenied("audit genesis absent or invalid")
            opaque = _sha([approval["issuer"], approval["approval_id"]])
            binding = _sha([entry_id,tenant_id,domain_id,values["document_id"],values["version"],
                            values["sha256"],_sha(approval_envelope)])
            cursor.execute(_BURN, (opaque,binding,now))
            if cursor.fetchone() != (opaque,):
                raise AuthorizationDenied("approval already consumed")
            cursor.execute(_UPDATE, (entry_id,tenant_id,domain_id))
            if cursor.rowcount != 1:
                raise AuthorizationDenied("document state concurrently changed")
            event = self._event("APPROVE_INDEX", "METADATA_REVIEW", "APPROVED_FOR_INDEXING", last[2], opaque, now)
            cursor.execute(_AUDIT, (entry_id,*event))
            db.commit()
            return AtomicApprovalReceipt(entry_id,tenant_id,domain_id,"APPROVED_FOR_INDEXING",event[1])
        except AuthorizationDenied:
            _safe_rollback(db)
            raise
        except Exception as exc:
            _safe_rollback(db)
            raise AuthorizationDenied("atomic document approval unavailable; all changes rolled back") from exc
        finally:
            _safe_close(cursor, db)