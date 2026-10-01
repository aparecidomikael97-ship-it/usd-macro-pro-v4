"""AION Core — Library Foundation V1 (isolated, deterministic, offline).

Pure/offline: stdlib only. Documents and metadata are UNTRUSTED DATA, never
instructions to the executor. V1 never indexes anything: it maintains an
isolated, tenant/domain-scoped catalog with explicit editorial state,
byte-dedup by digest, verifiable versions and a fail-closed approval policy.

Contracts are coherent with domain_registry, memory_architecture, provenance,
trust_engine and evidence_pack; none of those modules is modified here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

SCHEMA = "ATLASQUANT_AION_LIBRARY_FOUNDATION_V1"
VERSION = 1

# --- editorial states -------------------------------------------------------
STATES = ("RECEIVED", "METADATA_REVIEW", "QUARANTINED", "APPROVED_FOR_INDEXING", "REVOKED")
TERMINAL_STATES = ("REVOKED",)

TRANSITIONS = {
    "RECEIVED": ("METADATA_REVIEW", "QUARANTINED", "REVOKED"),
    "METADATA_REVIEW": ("QUARANTINED", "APPROVED_FOR_INDEXING", "REVOKED"),
    "QUARANTINED": ("METADATA_REVIEW", "REVOKED"),
    "APPROVED_FOR_INDEXING": ("REVOKED",),
    "REVOKED": (),
}

LICENSE_KINDS = ("CC0", "CC_BY", "CC_BY_SA", "GPL_V3", "MIT", "APACHE_2", "ALL_RIGHTS_RESERVED", "UNKNOWN")
USAGE_SCOPES = ("INTERNAL", "RESEARCH", "SHARED_TENANT", "PUBLISHED")
RETENTION_POLICIES = ("AUDIT_RETAIN", "PURGE_ON_REVOKE", "INDEFINITE")

# fields that are allowed in a document registration; anything else is rejected
ALLOWED_FIELDS = frozenset({
    "tenant_id", "domain_id", "document_id", "version", "sha256",
    "source_type", "source_reference", "published_at", "language",
    "title", "license_kind", "rights_holder", "usage_scope",
    "retention_policy", "human_approved_by", "provenance_id",
})

_SECRET_RE = re.compile(
    r"(?i)(password\s*=\s*\S{4,}|api[_-]?key\s*=\s*\S{4,}|"
    r"Bearer\s+[A-Za-z0-9._-]{8,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|"
    r"ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})")
_PRIVILEGED_RE = re.compile(
    r"(?i)(ignore (all )?(previous|above) instructions?|ignore as regras|"
    r"revele o segredo|reveal the secret|system prompt|execute the following)")


class LibraryFoundationError(ValueError):
    """Fail-closed error for the library foundation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: object, limit: int) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        raise LibraryFoundationError(f"value exceeds limit {limit}")
    return text


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _require_nonempty(value: object, name: str, limit: int) -> str:
    text = _clean(value, limit)
    if not text:
        raise LibraryFoundationError(f"{name} is required")
    return text


def _check_secret_free(name: str, value: str) -> None:
    if _SECRET_RE.search(value):
        raise LibraryFoundationError(f"{name} contains secret-like content")


@dataclass(frozen=True)
class CatalogEntry:
    entry_id: str
    tenant_id: str
    domain_id: str
    document_id: str
    version: int
    sha256: str
    state: str
    source_type: str
    source_reference: str
    published_at: str
    language: str
    title: str
    license_kind: str
    rights_holder: str
    usage_scope: str
    retention_policy: str
    human_approved_by: str
    provenance_id: str
    created_at: str
    updated_at: str
    audit_trail: tuple  # tuple of (timestamp, from_state, to_state, actor, note)
    flags: tuple        # e.g. privileged_instruction_flagged, duplicate_of

    def to_dict(self) -> dict:
        d = asdict(self)
        d["audit_trail"] = list(d["audit_trail"])
        d["flags"] = list(d["flags"])
        return d


class LibraryCatalog:
    """Deterministic, isolated catalog. No I/O, no execution of content."""

    def __init__(self, *, retention_default: str = "AUDIT_RETAIN"):
        if retention_default not in RETENTION_POLICIES:
            raise LibraryFoundationError("retention_default invalid")
        self._entries: dict[tuple, CatalogEntry] = {}
        self._by_digest: dict[tuple[str, str, str], tuple[str, int]] = {}  # (tenant, domain, digest) -> first registration
        self._retention_default = retention_default

    # -- registration ---------------------------------------------------------
    def register_document(self, *, tenant_id: str, domain_id: str, document_id: str,
                          version: int, sha256: str, source_type: str = "",
                          source_reference: str = "", published_at: str = "",
                          language: str = "", title: str = "", license_kind: str = "",
                          rights_holder: str = "", usage_scope: str = "",
                          retention_policy: str = "", human_approved_by: str = "",
                          provenance_id: str = "", extra_fields: dict | None = None) -> CatalogEntry:
        if extra_fields:
            # Callers must use named parameters: even allowlisted keys silently
            # shadowing values here would conceal unreviewed metadata.
            raise LibraryFoundationError("extra_fields are not supported; use named parameters")
        tenant_id = _require_nonempty(tenant_id, "tenant_id", 64)
        domain_id = _require_nonempty(domain_id, "domain_id", 64)
        for scope_name, scope_value in (("tenant_id", tenant_id), ("domain_id", domain_id)):
            if not re.fullmatch(r"[A-Za-z0-9_.:-]+", scope_value):
                raise LibraryFoundationError(f"{scope_name} has invalid characters")
        document_id = _require_nonempty(document_id, "document_id", 128)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", document_id):
            raise LibraryFoundationError("document_id has invalid characters")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise LibraryFoundationError("version must be a positive integer")
        sha256 = _require_nonempty(sha256, "sha256", 64)
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise LibraryFoundationError("sha256 must be lowercase hex 64 chars")
        for name, val, lim in (("source_type", source_type, 32), ("source_reference", source_reference, 256),
                               ("published_at", published_at, 32), ("language", language, 8),
                               ("title", title, 256), ("license_kind", license_kind, 32),
                               ("rights_holder", rights_holder, 128), ("usage_scope", usage_scope, 32),
                               ("retention_policy", retention_policy, 32), ("human_approved_by", human_approved_by, 64),
                               ("provenance_id", provenance_id, 64)):
            if val:
                _check_secret_free(name, str(val))
        title = _clean(title, 256)
        if _PRIVILEGED_RE.search(title):
            title_flags = ("privileged_instruction_flagged",)
        else:
            title_flags = ()
        license_kind = _clean(license_kind, 32)
        if license_kind and license_kind not in LICENSE_KINDS:
            raise LibraryFoundationError(f"license_kind not recognized: {license_kind}")
        usage_scope = _clean(usage_scope, 32)
        if usage_scope and usage_scope not in USAGE_SCOPES:
            raise LibraryFoundationError(f"usage_scope not recognized: {usage_scope}")
        retention_policy = _clean(retention_policy, 32) or self._retention_default
        if retention_policy not in RETENTION_POLICIES:
            raise LibraryFoundationError(f"retention_policy not recognized: {retention_policy}")
        human_approved_by = _clean(human_approved_by, 64)
        if human_approved_by and not re.fullmatch(r"[A-Za-z0-9_.-]+", human_approved_by):
            raise LibraryFoundationError("human_approved_by has invalid characters")

        key = (tenant_id, domain_id, document_id, version)
        if key in self._entries:
            existing = self._entries[key]
            if existing.sha256 != sha256:
                raise LibraryFoundationError(
                    f"version conflict: {document_id} v{version} already registered with different sha256")
            return existing  # idempotent identical re-registration

        scope_key = (tenant_id, domain_id)
        dup_flags = []
        if (tenant_id, domain_id, sha256) in self._by_digest:
            dup_flags.append("duplicate_bytes_in_scope")

        now = _now()
        entry_id = "LIB-" + _digest({"t": tenant_id, "d": domain_id, "doc": document_id,
                                      "v": version, "sha": sha256})
        entry = CatalogEntry(
            entry_id=entry_id, tenant_id=tenant_id, domain_id=domain_id,
            document_id=document_id, version=version, sha256=sha256,
            state="RECEIVED", source_type=_clean(source_type, 32),
            source_reference=_clean(source_reference, 256),
            published_at=_clean(published_at, 32), language=_clean(language, 8),
            title=title, license_kind=license_kind,
            rights_holder=_clean(rights_holder, 128), usage_scope=usage_scope,
            retention_policy=retention_policy, human_approved_by=human_approved_by,
            provenance_id=_clean(provenance_id, 64), created_at=now, updated_at=now,
            audit_trail=((now, "-", "RECEIVED", "register", "initial registration"),),
            flags=tuple(dup_flags + list(title_flags)),
        )
        self._entries[key] = entry
        self._by_digest.setdefault((tenant_id, domain_id, sha256), (document_id, version))
        return entry

    # -- transitions ------------------------------------------------------------
    def transition(self, *, tenant_id: str, domain_id: str, entry_id: str,
                   to_state: str, actor: str, note: str = "") -> CatalogEntry:
        # Caller scope is mandatory, but authentication/authorization MUST also be
        # enforced by a trusted external integration before calling this method.
        entry = self._find(entry_id, tenant_id=tenant_id, domain_id=domain_id)
        if to_state not in STATES:
            raise LibraryFoundationError(f"unknown state: {to_state}")
        if to_state == entry.state:
            raise LibraryFoundationError("no-op transition")
        if to_state not in TRANSITIONS[entry.state]:
            raise LibraryFoundationError(f"illegal transition {entry.state} -> {to_state}")
        if to_state == "APPROVED_FOR_INDEXING":
            if not entry.license_kind or entry.license_kind in ("UNKNOWN", "ALL_RIGHTS_RESERVED"):
                # A declared all-rights-reserved notice is not a verifiable grant.
                # Future verified rights grants need a separate, authenticated gate.
                raise LibraryFoundationError("cannot approve without licensed usage rights")
            if not entry.human_approved_by:
                raise LibraryFoundationError("cannot approve without explicit human approval")
            if actor != entry.human_approved_by:
                raise LibraryFoundationError("approval actor does not match declared human reviewer")
            if not entry.source_type or not entry.source_reference:
                raise LibraryFoundationError("cannot approve with incomplete origin")
        actor = _require_nonempty(actor, "actor", 64)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", actor):
            raise LibraryFoundationError("actor has invalid characters")
        now = _now()
        new_trail = entry.audit_trail + ((now, entry.state, to_state, actor, _clean(note, 128)),)
        updated = CatalogEntry(**{**entry.__dict__, "state": to_state, "updated_at": now,
                                  "audit_trail": new_trail})
        self._entries[(entry.tenant_id, entry.domain_id, entry.document_id, entry.version)] = updated
        return updated

    # -- queries ------------------------------------------------------------------
    def get(self, *, tenant_id: str, domain_id: str, document_id: str, version: int) -> CatalogEntry | None:
        return self._entries.get((tenant_id, domain_id, document_id, version))

    def find_by_entry_id(self, *, tenant_id: str, domain_id: str,
                         entry_id: str) -> CatalogEntry | None:
        # Scope filters prevent accidental cross-tenant lookups in shared catalogs.
        # Scope values supplied by the caller are NOT authentication claims.
        for e in self._entries.values():
            if (e.tenant_id, e.domain_id, e.entry_id) == (tenant_id, domain_id, entry_id):
                return e
        return None

    def versions(self, *, tenant_id: str, domain_id: str, document_id: str) -> list[CatalogEntry]:
        out = [e for e in self._entries.values()
               if (e.tenant_id, e.domain_id, e.document_id) == (tenant_id, domain_id, document_id)]
        return sorted(out, key=lambda e: e.version)

    def indexable(self, *, tenant_id: str, domain_id: str) -> list[CatalogEntry]:
        """V1 helper: documents that WOULD be indexable (nothing is actually indexed)."""
        return [e for e in self._entries.values()
                if (e.tenant_id, e.domain_id) == (tenant_id, domain_id)
                and e.state == "APPROVED_FOR_INDEXING"]

    def duplicate_of(self, *, tenant_id: str, domain_id: str, sha256: str) -> tuple | None:
        return self._by_digest.get((tenant_id, domain_id, sha256))

    def snapshot(self) -> dict:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "generated_at": _now(),
            "entries": [e.to_dict() for e in sorted(self._entries.values(),
                                                     key=lambda x: x.entry_id)],
            "digest": _digest({"entries": [e.to_dict() for e in sorted(
                self._entries.values(), key=lambda x: x.entry_id)]}),
        }

    def _find(self, entry_id: str, *, tenant_id: str, domain_id: str) -> CatalogEntry:
        entry = self.find_by_entry_id(tenant_id=tenant_id, domain_id=domain_id, entry_id=entry_id)
        if entry is None:
            raise LibraryFoundationError(f"unknown entry_id: {entry_id}")
        return entry


def verify_entry_integrity(entry: CatalogEntry) -> dict:
    """Recompute expected invariants; returns checks (never mutates)."""
    checks = {
        "state_valid": entry.state in STATES,
        "terminal_consistent": (entry.state not in TERMINAL_STATES) or (not TRANSITIONS[entry.state]),
        "audit_starts_at_received": bool(entry.audit_trail) and
                                    entry.audit_trail[0][1:4] == ("-", "RECEIVED", "register"),
        "audit_transitions_valid": all(
            (record[1] == "-" and record[2] == "RECEIVED" if i == 0 else
             record[2] in TRANSITIONS.get(record[1], ()))
            for i, record in enumerate(entry.audit_trail)),
        "audit_chain_unbroken": all(
            a[2] == b[1] for a, b in zip(entry.audit_trail, entry.audit_trail[1:])),
        "audit_ends_at_current_state": bool(entry.audit_trail) and entry.audit_trail[-1][2] == entry.state,
        "approval_preconditions": (entry.state != "APPROVED_FOR_INDEXING") or
                                  (bool(entry.license_kind) and entry.license_kind != "UNKNOWN"
                                   and bool(entry.human_approved_by)
                                   and bool(entry.source_type) and bool(entry.source_reference)),
        "no_secrets_in_metadata": not any(_SECRET_RE.search(str(v)) for v in (
            entry.title, entry.source_reference, entry.rights_holder, entry.human_approved_by)),
    }
    return {"integrity_ok": all(checks.values()), **checks}
