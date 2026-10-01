"""Offline security integration *contract*: server-only identity bridge and local durable approval burn.

NOT a configured identity provider, production gateway or distributed ledger.
A trusted host MUST supply a signature-validating identity verifier, trusted
membership lookup, issuer key and private absolute SQLite path. The raw catalog
and bare SecuredLibraryBoundary must not be callable by external users.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Callable, Mapping

from .library_authorization import (
    AUDIENCE, AttestationVerifier, AuthorizationDenied, SecuredLibraryBoundary, _encode,
)
from .library_foundation import CatalogEntry

SCHEMA = "ATLASQUANT_LIBRARY_SECURITY_RUNTIME_CONTRACT_V1"
_IDENT = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_ACTION_ROLES = {"READ": {"LIBRARY_READER", "LIBRARY_REVIEWER", "LIBRARY_ADMIN"},
                 "APPROVE_INDEX": {"LIBRARY_REVIEWER", "LIBRARY_ADMIN"}}
_VALID_ROLES = _ACTION_ROLES["READ"]


def _identifier(value: object) -> bool:
    return type(value) is str and _IDENT.fullmatch(value) is not None


def _config_key(value: object) -> bytes:
    if type(value) is not bytes or len(value) < 32:
        raise AuthorizationDenied("trusted signing key configuration required")
    return value


@dataclass(frozen=True)
class VerifiedSession:
    """Output from a TRUSTED adapter that has already verified external token signatures.

    External input MUST NOT be deserialized straight into this type and trusted.
    """
    issuer: str
    audience: str
    subject: str
    issued_at: int
    expires_at: int


class ExternalIdentityBridge:
    """Contract for app-owned OIDC/WebAuthn adapter; NEVER trusts roles from token claims.

    `verify_token` must cryptographically validate issuer keys, audience, nonce,
    expiry and token/session context in the host. `lookup_roles` must use an
    authenticated server-side tenant/domain membership source. Neither callback
    may be chosen by remote callers.
    """

    def __init__(self, *, verify_token: Callable[[str], VerifiedSession],
                 lookup_roles: Callable[[str, str, str], object], trusted_issuer: str,
                 token_audience: str, attestation_issuer: str, signing_key: bytes,
                 clock: Callable[[], int] | None = None):
        if not callable(verify_token) or not callable(lookup_roles) or not all(
            _identifier(x) for x in (trusted_issuer, token_audience, attestation_issuer)
        ):
            raise AuthorizationDenied("trusted identity connector configuration required")
        self._verify = verify_token
        self._roles = lookup_roles
        self._trusted_issuer = trusted_issuer
        self._token_audience = token_audience
        self._attestation_issuer = attestation_issuer
        self._key = _config_key(signing_key)
        self._clock = clock or (lambda: int(time.time()))
        if not callable(self._clock):
            raise AuthorizationDenied("trusted clock required")

    def identity_envelope(self, *, token: str, tenant_id: str, domain_id: str, action: str) -> dict:
        if (type(token) is not str or not 16 <= len(token) <= 8192 or any(c.isspace() for c in token) or
                not _identifier(tenant_id) or not _identifier(domain_id) or action not in _ACTION_ROLES):
            raise AuthorizationDenied("malformed identity request")
        now = self._clock()
        if type(now) is not int or now < 0:
            raise AuthorizationDenied("trusted clock invalid")
        try:
            session = self._verify(token)
        except Exception as exc:
            raise AuthorizationDenied("external identity could not be verified") from exc
        if (type(session) is not VerifiedSession or session.issuer != self._trusted_issuer or
                session.audience != self._token_audience or not _identifier(session.subject) or
                type(session.issued_at) is not int or type(session.expires_at) is not int or
                session.issued_at > now or session.expires_at <= now or
                session.issued_at < 0 or session.expires_at <= session.issued_at):
            raise AuthorizationDenied("external identity invalid or expired")
        try:
            supplied_roles = self._roles(session.subject, tenant_id, domain_id)
        except Exception as exc:
            raise AuthorizationDenied("membership verification unavailable") from exc
        if (type(supplied_roles) not in (tuple, frozenset) or not supplied_roles or
                not all(type(x) is str and x in _VALID_ROLES for x in supplied_roles)):
            raise AuthorizationDenied("membership invalid or revoked")
        roles = sorted(set(supplied_roles))
        if not _ACTION_ROLES[action].intersection(roles):
            raise AuthorizationDenied("operation not permitted")
        expiry = min(session.expires_at, now + 300)
        if expiry <= now:
            raise AuthorizationDenied("identity session expired")
        claims = {"kind": "identity", "issuer": self._attestation_issuer, "audience": AUDIENCE,
                  "subject": session.subject, "tenant_id": tenant_id, "domain_id": domain_id,
                  "roles": roles, "action": action, "issued_at": now, "expires_at": expiry}
        digest = hmac.new(self._key, _encode(claims), hashlib.sha256).hexdigest()
        return {"payload": claims, "signature": digest}


class SqliteApprovalBurnLedger:
    """Local single-host durable at-most-once reservation of an approval identity.

    An approved nonce is BURNED and committed BEFORE changing the in-memory
    catalog. On crash after burn but before transition, manual reissue is needed.
    Never use this as a distributed store, or as the application's event ledger.
    """

    def __init__(self, *, trusted_absolute_path: str):
        if (type(trusted_absolute_path) is not str or not trusted_absolute_path or
                "\x00" in trusted_absolute_path or trusted_absolute_path.startswith("file:")):
            raise AuthorizationDenied("trusted absolute ledger path required")
        path = Path(trusted_absolute_path)
        if not path.is_absolute() or path.name in ("", ".", "..") or not path.parent.is_dir():
            raise AuthorizationDenied("trusted ledger directory must exist")
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise AuthorizationDenied("ledger path must be a regular file")
        self._path = str(path)
        try:
            with closing(self._connect()) as db:
                db.execute("""CREATE TABLE IF NOT EXISTS burned_approvals (
                    approval_key TEXT PRIMARY KEY NOT NULL,
                    binding_sha256 TEXT NOT NULL,
                    burned_at INTEGER NOT NULL
                )""")
                db.execute("PRAGMA user_version = 1")
        except sqlite3.Error as exc:
            raise AuthorizationDenied("approval ledger unavailable") from exc

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout = 5000")
            db.execute("PRAGMA synchronous = FULL")
            # Fail closed if a different schema is present; no automatic migrations.
            ver = db.execute("PRAGMA user_version").fetchone()[0]
            if ver not in (0, 1):
                raise AuthorizationDenied("unsupported approval ledger version")
            return db
        except BaseException:
            db.close()
            raise

    def burn(self, *, issuer: str, approval_id: str, binding_sha256: str) -> str:
        if not _identifier(issuer) or not _identifier(approval_id) or (
                type(binding_sha256) is not str or re.fullmatch("[a-f0-9]{64}", binding_sha256) is None):
            raise AuthorizationDenied("invalid approval key or binding")
        opaque_key = hashlib.sha256(_encode([issuer, approval_id])).hexdigest()
        try:
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO burned_approvals (approval_key, binding_sha256, burned_at) VALUES (?, ?, ?)",
                           (opaque_key, binding_sha256, int(time.time())))
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise AuthorizationDenied("approval has already been used or reserved") from exc
            except Exception:
                db.execute("ROLLBACK")
                raise
            finally:
                db.close()
        except sqlite3.Error as exc:
            raise AuthorizationDenied("approval ledger unavailable; deny operation") from exc
        return opaque_key

    def burned(self, *, issuer: str, approval_id: str) -> bool:
        if not _identifier(issuer) or not _identifier(approval_id):
            raise AuthorizationDenied("invalid approval key")
        key = hashlib.sha256(_encode([issuer, approval_id])).hexdigest()
        try:
            with closing(self._connect()) as db:
                return db.execute("SELECT 1 FROM burned_approvals WHERE approval_key = ?", (key,)).fetchone() is not None
        except sqlite3.Error as exc:
            raise AuthorizationDenied("approval ledger unavailable; deny operation") from exc


class DurableLibraryApprovalGateway:
    """Server-side demonstration of a persistent burn before in-memory approval.

    Calls existing signed SecuredLibraryBoundary after independent preflight,
    and requires both a signed identity envelope and rights/approval attestations.
    The raw boundary and catalog MUST stay private to the host application.
    """

    def __init__(self, *, boundary: SecuredLibraryBoundary, verifier: AttestationVerifier,
                 ledger: SqliteApprovalBurnLedger):
        if (type(boundary) is not SecuredLibraryBoundary or type(verifier) is not AttestationVerifier or
                type(ledger) is not SqliteApprovalBurnLedger or boundary._verifier is not verifier):
            raise AuthorizationDenied("trusted gateway configuration required")
        self._boundary = boundary
        self._verifier = verifier
        self._ledger = ledger

    def approve_for_indexing(self, *, tenant_id: str, domain_id: str, entry_id: str,
                             identity_envelope: dict, approval_envelope: dict,
                             rights_envelope: dict):
        # All preflight checks BEFORE a durable burn. If any fail, no mutation.
        identity = self._boundary._principal(identity_envelope, action="APPROVE_INDEX",
                                              tenant_id=tenant_id, domain_id=domain_id)
        approval = self._verifier.verify("approval", approval_envelope)
        rights = self._verifier.verify("rights", rights_envelope)
        entry = self._boundary._catalog.find_by_entry_id(
            tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id)
        if entry is None or entry.state != "METADATA_REVIEW":
            raise AuthorizationDenied("document unavailable for approval")
        common = ("tenant_id", "domain_id", "document_id", "version", "sha256", "license_kind", "usage_scope")
        if any(approval[k] != getattr(entry, k) or rights[k] != getattr(entry, k) for k in common):
            raise AuthorizationDenied("document/proof binding mismatch")
        if approval["reviewer"] != identity["subject"] or approval["reviewer"] != entry.human_approved_by:
            raise AuthorizationDenied("human reviewer binding mismatch")
        if (not entry.rights_holder or rights["rights_holder"] != entry.rights_holder or
                entry.license_kind in ("UNKNOWN", "ALL_RIGHTS_RESERVED", "") or
                not entry.source_type or not entry.source_reference or
                rights["rights_action"] != ("PUBLISH" if entry.usage_scope == "PUBLISHED" else "INDEX")):
            raise AuthorizationDenied("rights or source not sufficient")
        # Never store a raw token or identity data: only a digest of scope/approval binding.
        binding = hashlib.sha256(_encode({
            "tenant_id": entry.tenant_id, "domain_id": entry.domain_id,
            "document_id": entry.document_id, "version": entry.version,
            "sha256": entry.sha256, "approval_envelope_sha256": hashlib.sha256(_encode(approval_envelope)).hexdigest(),
        })).hexdigest()
        self._ledger.burn(issuer=approval["issuer"], approval_id=approval["approval_id"], binding_sha256=binding)
        # Failures after durable burn are deliberately conservative: this nonce
        # remains consumed and must be reissued, rather than risk cross-process replay.
        return self._boundary.approve_for_indexing(
            tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id,
            identity_envelope=identity_envelope, approval_envelope=approval_envelope,
            rights_envelope=rights_envelope)


class AuthenticatedLibraryService:
    """App-owned facade: exchange trusted external session for a short-lived proof.

    Host must expose ONLY this facade to its routes; no raw catalog, raw boundary,
    signing keys, mutable role lookup or arbitrary proof minting may be exposed.
    Authentication, server routing, durable document state and rights-vetting are
    outside this offline contract.
    """

    def __init__(self, *, identities: ExternalIdentityBridge,
                 boundary: SecuredLibraryBoundary, approvals: DurableLibraryApprovalGateway):
        if (type(identities) is not ExternalIdentityBridge or
                type(boundary) is not SecuredLibraryBoundary or
                type(approvals) is not DurableLibraryApprovalGateway or
                approvals._boundary is not boundary):
            raise AuthorizationDenied("trusted service wiring required")
        self._identities = identities
        self._boundary = boundary
        self._approvals = approvals

    def read(self, *, token: str, tenant_id: str, domain_id: str, entry_id: str):
        envelope = self._identities.identity_envelope(
            token=token, tenant_id=tenant_id, domain_id=domain_id, action="READ")
        return self._boundary.read(
            tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id, identity_envelope=envelope)

    def approve_for_indexing(self, *, token: str, tenant_id: str, domain_id: str,
                             entry_id: str, approval_envelope: dict, rights_envelope: dict):
        envelope = self._identities.identity_envelope(
            token=token, tenant_id=tenant_id, domain_id=domain_id, action="APPROVE_INDEX")
        return self._approvals.approve_for_indexing(
            tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id,
            identity_envelope=envelope, approval_envelope=approval_envelope,
            rights_envelope=rights_envelope)
