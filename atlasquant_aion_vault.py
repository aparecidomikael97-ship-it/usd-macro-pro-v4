"""AION Vault contracts.

The Vault stores metadata, integrity and references to protected material.
It deliberately does NOT store plaintext credentials, tokens, API keys or
passwords. Secret values stay in an approved secret backend; the Vault keeps
only a reference name/locator plus audit metadata.

No encryption is invented here and no secret backend is called.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_VAULT_V1"
VAULT_VERSION = "1.0"

ENTRY_KINDS = (
    "SECRET_REF",
    "CHECKPOINT_BACKUP",
    "POLICY",
    "IDENTITY",
    "CONFIG_REF",
    "ARTIFACT_REF",
)
BACKENDS = (
    "ENVIRONMENT",
    "RENDER_SECRET",
    "GITHUB_ACTIONS_SECRET",
    "OS_KEYCHAIN",
    "EXTERNAL_VAULT",
    "RUNTIME_DATA",
    "REPOSITORY",
)
ENTRY_STATES = ("ACTIVE", "RETIRED", "PENDING")
FORBIDDEN_VALUE_KEYS = frozenset({
    "secret",
    "secret_value",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "credentials",
})
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _stable(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha256(raw.encode("utf-8")).hexdigest()[:24]


def _safe_id(value: Any) -> str:
    text = _clean(value, 96).lower()
    if not _SAFE_ID.fullmatch(text):
        raise ValueError("invalid vault id")
    return text


def _forbidden_hits(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key or "").strip().casefold()
            child = f"{path}.{key}"
            if key_text in FORBIDDEN_VALUE_KEYS:
                hits.append(child)
            hits.extend(_forbidden_hits(item, child))
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(list(value)[:200]):
            hits.extend(_forbidden_hits(item, f"{path}[{idx}]"))
    return hits[:100]


def vault_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VAULT_VERSION,
        "plaintext_secrets_allowed": False,
        "homegrown_encryption_allowed": False,
        "secret_values_exportable": False,
        "secret_references_exportable": True,
        "checkpoint_backups_versioned": True,
        "policy_versioned": True,
        "identity_versioned": True,
        "aion_self_delete_allowed": False,
        "aion_self_permission_expansion_allowed": False,
        "guardian_required_for_sensitive_changes": True,
        "proof_of_safety_required_for_sensitive_changes": True,
        "real_trading_enabled": False,
    }


def new_vault_entry(
    entry_id: Any,
    *,
    kind: Any,
    backend: Any,
    locator_ref: Any,
    label: Any = "",
    state: Any = "ACTIVE",
    content_digest: Any = "",
    version: Any = "1",
    metadata: Mapping[str, Any] | None = None,
    created_by: Any = "ADMIN",
    created_at: str | None = None,
) -> dict[str, Any]:
    eid = _safe_id(entry_id)
    kind_norm = _clean(kind, 40).upper()
    backend_norm = _clean(backend, 40).upper()
    state_norm = _clean(state, 30).upper()
    if kind_norm not in ENTRY_KINDS:
        raise ValueError("unsupported vault entry kind")
    if backend_norm not in BACKENDS:
        raise ValueError("unsupported vault backend")
    if state_norm not in ENTRY_STATES:
        state_norm = "PENDING"

    locator = _clean(locator_ref, 300)
    if not locator:
        raise ValueError("vault locator reference required")

    meta = dict(metadata or {})
    hits = _forbidden_hits(meta)
    if hits:
        raise ValueError("plaintext secret-like fields are forbidden in vault metadata")

    # Secret references may name a secret slot, but must not contain an obvious
    # bearer/private value. This is a heuristic defense; the primary contract is
    # that callers pass only backend reference names.
    if kind_norm == "SECRET_REF":
        suspicious = locator.casefold()
        if suspicious.startswith(("sk-", "ghp_", "github_pat_", "bearer ")) or "-----begin private key-----" in suspicious:
            raise ValueError("secret value detected where a reference was expected")

    created = str(created_at or _now())
    return {
        "entry_id": eid,
        "kind": kind_norm,
        "backend": backend_norm,
        "locator_ref": locator,
        "label": _clean(label, 160) or eid,
        "state": state_norm,
        "content_digest": _clean(content_digest, 128),
        "version": _clean(version, 80) or "1",
        "metadata": meta,
        "created_by": _clean(created_by, 120) or "ADMIN",
        "created_at": created,
        "updated_at": created,
        "contains_plaintext_secret": False,
        "mutable_by_aion_without_guardian": False,
        "real_trading_enabled": False,
    }


def normalize_vault_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw or {})
    return new_vault_entry(
        item.get("entry_id"),
        kind=item.get("kind"),
        backend=item.get("backend"),
        locator_ref=item.get("locator_ref"),
        label=item.get("label"),
        state=item.get("state"),
        content_digest=item.get("content_digest"),
        version=item.get("version"),
        metadata=item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {},
        created_by=item.get("created_by") or "ADMIN",
        created_at=str(item.get("created_at") or _now()),
    )


def normalize_vault_entries(rows: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(rows or [])[:1000]:
        if not isinstance(raw, Mapping):
            continue
        try:
            item = normalize_vault_entry(raw)
        except Exception:
            continue
        eid = item["entry_id"]
        if eid in seen:
            continue
        seen.add(eid)
        out.append(item)
    return out


def default_vault() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "version": VAULT_VERSION,
        "policy": vault_policy(),
        "entries": entries,
        "digest": vault_digest(entries),
        "backend_connected": False,
        "backend_state": "NOT_CONFIGURED",
        "plaintext_secrets_present": False,
        "aion_can_delete_vault": False,
        "real_trading_enabled": False,
    }


def normalize_vault(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(raw or {})
    # Reject unknown top-level fields that look like secret values. This does
    # not claim perfect DLP; it blocks the most dangerous accidental pattern.
    hits = _forbidden_hits({k: v for k, v in item.items() if k not in {"entries"}})
    entries = normalize_vault_entries(
        item.get("entries") if isinstance(item.get("entries"), (list, tuple)) else []
    )
    return {
        "schema": SCHEMA,
        "version": VAULT_VERSION,
        "policy": vault_policy(),
        "entries": entries,
        "digest": vault_digest(entries),
        "backend_connected": bool(item.get("backend_connected", False)) and not hits,
        "backend_state": _clean(item.get("backend_state"), 80) or "NOT_CONFIGURED",
        "plaintext_secrets_present": bool(hits),
        "forbidden_field_hits": hits,
        "aion_can_delete_vault": False,
        "real_trading_enabled": False,
    }


def vault_digest(entries: Sequence[Mapping[str, Any]] | None) -> str:
    return _stable(normalize_vault_entries(entries))


def upsert_vault_entry(
    rows: Sequence[Mapping[str, Any]] | None,
    entry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    current = normalize_vault_entries(rows)
    item = normalize_vault_entry(entry)
    out: list[dict[str, Any]] = []
    replaced = False
    for row in current:
        if row["entry_id"] == item["entry_id"]:
            out.append(item)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(item)
    return out


def vault_summary(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    state = normalize_vault(raw)
    entries = state["entries"]
    by_kind = {kind: 0 for kind in ENTRY_KINDS}
    for item in entries:
        by_kind[item["kind"]] += 1
    return {
        "schema": SCHEMA,
        "entries": len(entries),
        "active": sum(1 for x in entries if x["state"] == "ACTIVE"),
        "by_kind": by_kind,
        "backend_connected": bool(state["backend_connected"]),
        "backend_state": state["backend_state"],
        "plaintext_secrets_present": bool(state["plaintext_secrets_present"]),
        "policy_ok": not bool(state["plaintext_secrets_present"]),
        "aion_can_delete_vault": False,
        "digest": state["digest"],
        "real_trading_enabled": False,
    }


def vault_export_manifest(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Export references and integrity only; never secret values."""
    state = normalize_vault(raw)
    return {
        "schema": SCHEMA,
        "version": state["version"],
        "policy": state["policy"],
        "entries": [
            {
                "entry_id": x["entry_id"],
                "kind": x["kind"],
                "backend": x["backend"],
                "locator_ref": x["locator_ref"],
                "label": x["label"],
                "state": x["state"],
                "content_digest": x["content_digest"],
                "version": x["version"],
                "metadata": x["metadata"],
                "created_at": x["created_at"],
                "contains_plaintext_secret": False,
            }
            for x in state["entries"]
        ],
        "digest": state["digest"],
        "contains_secret_values": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VAULT_VERSION",
    "ENTRY_KINDS",
    "BACKENDS",
    "ENTRY_STATES",
    "FORBIDDEN_VALUE_KEYS",
    "vault_policy",
    "new_vault_entry",
    "normalize_vault_entry",
    "normalize_vault_entries",
    "default_vault",
    "normalize_vault",
    "vault_digest",
    "upsert_vault_entry",
    "vault_summary",
    "vault_export_manifest",
]
