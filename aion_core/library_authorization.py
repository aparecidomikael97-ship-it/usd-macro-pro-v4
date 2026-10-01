"""Offline *boundary contract* for AION Library. NOT an identity provider or production gateway.

Only attestations signed by independently configured issuers can enter this
adapter. HMAC is a testing/deployment-boundary reference, *not* user biometric
signing, a substitute for OIDC or a non-repudiable human signature. The caller
must keep raw LibraryCatalog inaccessible to untrusted users. No I/O or secrets
are stored here; never embed deployment signing keys in source or GitHub.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Mapping, Callable

from .library_foundation import CatalogEntry, LibraryCatalog, LibraryFoundationError

AUDIENCE = "atlasquant-aion-library"
SCHEMA = "ATLASQUANT_LIBRARY_AUTHZ_BOUNDARY_V1"
_ACTIONS = {"READ", "APPROVE_INDEX"}
_ROLES = {"LIBRARY_READER", "LIBRARY_REVIEWER", "LIBRARY_ADMIN"}
_FIELDS = {
    "identity": {"kind", "issuer", "audience", "subject", "tenant_id", "domain_id", "roles", "action", "issued_at", "expires_at"},
    "approval": {"kind", "issuer", "audience", "reviewer", "tenant_id", "domain_id", "document_id", "version", "sha256", "license_kind", "usage_scope", "action", "approval_id", "issued_at", "expires_at"},
    "rights": {"kind", "issuer", "audience", "rights_holder", "tenant_id", "domain_id", "document_id", "version", "sha256", "license_kind", "usage_scope", "rights_action", "grant_id", "issued_at", "expires_at"},
}
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class AuthorizationDenied(ValueError):
    """Refusal at an attestation boundary. Avoid reporting secrets in errors."""


def _encode(data: dict) -> bytes:
    try:
        return json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise AuthorizationDenied("malformed attestation") from exc


def _check_identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


def _keyset(source: Mapping[str, bytes]) -> dict[str, bytes]:
    if not isinstance(source, Mapping) or not source:
        raise AuthorizationDenied("trusted issuer keys required")
    result = {}
    for issuer, key in source.items():
        if not _check_identifier(issuer) or type(key) is not bytes or len(key) < 32:
            raise AuthorizationDenied("invalid trusted issuer configuration")
        result[issuer] = key
    return result


class AttestationVerifier:
    """Verifies three *independently keyed* trusted authorities, exact claims & expiry."""

    def __init__(self, *, identity_issuers: Mapping[str, bytes],
                 approval_issuers: Mapping[str, bytes], rights_issuers: Mapping[str, bytes],
                 clock: Callable[[], int] | None = None):
        self._keys = {
            "identity": _keyset(identity_issuers),
            "approval": _keyset(approval_issuers),
            "rights": _keyset(rights_issuers),
        }
        self._clock = clock if clock is not None else lambda: int(time.time())
        if not callable(self._clock):
            raise AuthorizationDenied("trusted clock must be callable")
        all_keys = [key for group in self._keys.values() for key in group.values()]
        if len(set(all_keys)) != len(all_keys):
            raise AuthorizationDenied("authority keys must be independent")

    def verify(self, kind: str, envelope: object) -> dict:
        now = self._clock()
        if kind not in _FIELDS or type(now) is not int or now < 0:
            raise AuthorizationDenied("invalid attestation request")
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            raise AuthorizationDenied("malformed attestation envelope")
        claims, sig = envelope["payload"], envelope["signature"]
        if type(claims) is not dict or set(claims) != _FIELDS[kind] or type(sig) is not str or not _HEX.fullmatch(sig):
            raise AuthorizationDenied("malformed attestation claims")
        issuer = claims["issuer"]
        if not _check_identifier(issuer) or issuer not in self._keys[kind]:
            raise AuthorizationDenied("untrusted attestation issuer")
        if claims["kind"] != kind or claims["audience"] != AUDIENCE:
            raise AuthorizationDenied("wrong attestation purpose or audience")
        issued, expires = claims["issued_at"], claims["expires_at"]
        max_ttl = {"identity": 3600, "approval": 86400, "rights": 31536000}[kind]
        if (type(issued) is not int or type(expires) is not int or issued < 0 or
                expires <= issued or expires - issued > max_ttl or not issued <= now < expires):
            raise AuthorizationDenied("expired or invalid attestation lifetime")
        canonical = _encode(claims)
        if len(canonical) > 8192:
            raise AuthorizationDenied("attestation exceeds bounded size")
        computed = hmac.new(self._keys[kind][issuer], canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, sig):
            raise AuthorizationDenied("attestation signature invalid")
        for field in ("tenant_id", "domain_id"):
            if not _check_identifier(claims[field]):
                raise AuthorizationDenied("invalid attestation scope")
        if kind == "identity":
            if (not _check_identifier(claims["subject"]) or
                    type(claims["action"]) is not str or claims["action"] not in _ACTIONS or
                    type(claims["roles"]) is not list or not claims["roles"] or
                    len(claims["roles"]) != len(set(map(str, claims["roles"]))) or
                    not all(type(role) is str and role in _ROLES for role in claims["roles"])):
                raise AuthorizationDenied("invalid identity claims")
        else:
            if (not _check_identifier(claims["document_id"]) or
                    type(claims["version"]) is not int or claims["version"] < 1 or
                    type(claims["sha256"]) is not str or not _HEX.fullmatch(claims["sha256"]) or
                    type(claims["license_kind"]) is not str or
                    type(claims["usage_scope"]) is not str):
                raise AuthorizationDenied("invalid document claims")
            id_field = "approval_id" if kind == "approval" else "grant_id"
            if not _check_identifier(claims[id_field]):
                raise AuthorizationDenied("invalid attestation ID")
            if kind == "approval":
                if claims["action"] != "APPROVE_INDEX" or not _check_identifier(claims["reviewer"]):
                    raise AuthorizationDenied("invalid decision approval")
            elif not _check_identifier(claims["rights_holder"]) or claims["rights_action"] not in ("INDEX", "PUBLISH"):
                raise AuthorizationDenied("invalid rights grant")
        return claims.copy()


@dataclass(frozen=True)
class AuthorizedDecision:
    entry_id: str
    principal: str
    action: str
    decision_sha256: str


class SecuredLibraryBoundary:
    """Scoped, in-memory reference facade. MUST be integrated with trusted storage/IdP before production.

    The raw catalog MUST NOT be made available to clients; replay ledger here is
    process-local and intentionally does not claim to survive restarts.
    """

    def __init__(self, catalog: LibraryCatalog, verifier: AttestationVerifier):
        if not isinstance(catalog, LibraryCatalog) or not isinstance(verifier, AttestationVerifier):
            raise AuthorizationDenied("invalid boundary setup")
        self._catalog = catalog
        self._verifier = verifier
        self._consumed: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def _principal(self, envelope: dict, *, action: str, tenant_id: str, domain_id: str) -> dict:
        identity = self._verifier.verify("identity", envelope)
        if (identity["action"] != action or identity["tenant_id"] != tenant_id or
                identity["domain_id"] != domain_id):
            raise AuthorizationDenied("identity not scoped to operation")
        required_roles = {"READ": {"LIBRARY_READER", "LIBRARY_REVIEWER", "LIBRARY_ADMIN"},
                          "APPROVE_INDEX": {"LIBRARY_REVIEWER", "LIBRARY_ADMIN"}}[action]
        if not set(identity["roles"]).intersection(required_roles):
            raise AuthorizationDenied("role not allowed for operation")
        return identity

    def read(self, *, tenant_id: str, domain_id: str, entry_id: str,
             identity_envelope: dict) -> CatalogEntry | None:
        self._principal(identity_envelope, action="READ", tenant_id=tenant_id, domain_id=domain_id)
        return self._catalog.find_by_entry_id(tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id)

    def approve_for_indexing(self, *, tenant_id: str, domain_id: str, entry_id: str,
                             identity_envelope: dict, approval_envelope: dict,
                             rights_envelope: dict) -> tuple[CatalogEntry, AuthorizedDecision]:
        with self._lock:
            identity = self._principal(identity_envelope, action="APPROVE_INDEX",
                                       tenant_id=tenant_id, domain_id=domain_id)
            approval = self._verifier.verify("approval", approval_envelope)
            rights = self._verifier.verify("rights", rights_envelope)
            entry = self._catalog.find_by_entry_id(tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id)
            if entry is None or entry.state != "METADATA_REVIEW":
                raise AuthorizationDenied("document unavailable for approval")
            common = ("tenant_id", "domain_id", "document_id", "version", "sha256", "license_kind", "usage_scope")
            if any(approval[field] != getattr(entry, field) or rights[field] != getattr(entry, field) for field in common):
                raise AuthorizationDenied("document/proof binding mismatch")
            if (approval["reviewer"] != identity["subject"] or
                    approval["reviewer"] != entry.human_approved_by):
                raise AuthorizationDenied("human reviewer binding mismatch")
            if not entry.rights_holder or rights["rights_holder"] != entry.rights_holder:
                raise AuthorizationDenied("rights holder mismatch or absent")
            if entry.license_kind in ("UNKNOWN", "ALL_RIGHTS_RESERVED", ""):
                raise AuthorizationDenied("rights status incompatible with V1 indexing")
            action = "PUBLISH" if entry.usage_scope == "PUBLISHED" else "INDEX"
            if rights["rights_action"] != action:
                raise AuthorizationDenied("rights grant does not cover requested scope")
            if not entry.source_type or not entry.source_reference:
                raise AuthorizationDenied("source provenance incomplete")
            replay_key = (approval["issuer"], approval["approval_id"])
            if replay_key in self._consumed:
                raise AuthorizationDenied("approval decision already consumed")
            # External IdP, approval and rights issuers are separate trusted authorities.
            # In-memory replay state is NOT suitable as production persistent ledger.
            try:
                updated = self._catalog.transition(tenant_id=tenant_id, domain_id=domain_id,
                                                   entry_id=entry_id, to_state="APPROVED_FOR_INDEXING",
                                                   actor=identity["subject"], note="verified offline boundary")
            except LibraryFoundationError as exc:
                raise AuthorizationDenied("catalog denied requested transition") from exc
            self._consumed.add(replay_key)
            attestation_digests = [hashlib.sha256(_encode(x)).hexdigest() for x in
                                   (identity_envelope, approval_envelope, rights_envelope)]
            decision_body = {"schema": SCHEMA, "entry_id": updated.entry_id, "tenant_id": tenant_id,
                             "domain_id": domain_id, "principal": identity["subject"],
                             "action": "APPROVE_INDEX", "proof_sha256": attestation_digests}
            decision = AuthorizedDecision(updated.entry_id, identity["subject"], "APPROVE_INDEX",
                                          hashlib.sha256(_encode(decision_body)).hexdigest())
            return updated, decision
