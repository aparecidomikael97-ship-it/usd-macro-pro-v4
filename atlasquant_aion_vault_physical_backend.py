"""Physical encrypted staging secret backend for AION Vault.

This backend proves durable encrypted-at-rest storage, scope isolation,
rotation, revocation and restart behavior without connecting production KMS or
real provider secrets. Key material is supplied only by an injected resolver
and is never serialized, logged or returned by metadata/attestation methods.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
import json
import os
import re
import sqlite3

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aion_chat.models import Scope
from atlasquant_aion_vault import normalize_vault

SCHEMA = "ATLASQUANT_AION_SECRET_BACKEND_V1"
ATTESTATION_SCHEMA = "ATLASQUANT_AION_SECRET_BACKEND_ATTESTATION_V1"
ALGORITHM = "AES-256-GCM"
KEY_BYTES = 32
NONCE_BYTES = 12
MAX_SECRET_BYTES = 16 * 1024
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{1,127}$")
_ALLOWED_ENVS = frozenset({"LOCAL", "DEV", "DEVELOPMENT", "STAGING", "TEST", "QA"})


class SecretBackendError(RuntimeError):
    pass


class SecretBackendIntegrityError(SecretBackendError):
    pass


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _token(value: Any, name: str, limit: int = 128) -> str:
    text = _text(value, limit).lower()
    if not _SAFE_ID.fullmatch(text):
        raise ValueError(f"invalid {name}")
    return text


def _utc(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def _scope(scope: Scope) -> dict[str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    if not scope.owner_id or not scope.tenant_id or not scope.workspace_id:
        raise ValueError("complete trusted scope required")
    return {
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
    }


def _secret_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raise TypeError("secret must be str or bytes")
    if not raw or len(raw) > MAX_SECRET_BYTES:
        raise ValueError("secret size outside staging bounds")
    return raw


def _aad(
    scope: Mapping[str, str],
    *,
    secret_id: str,
    secret_version: int,
    key_ref: str,
    key_version: str,
) -> bytes:
    return _canonical({
        "schema": SCHEMA,
        **dict(scope),
        "secret_id": secret_id,
        "secret_version": secret_version,
        "key_ref": key_ref,
        "key_version": key_version,
        "algorithm": ALGORITHM,
    })


def _resolve_key(
    resolver: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    scope: Mapping[str, str],
    *,
    key_ref: str,
    key_version: str,
) -> bytes:
    if not callable(resolver):
        raise SecretBackendError("KEY_RESOLVER_REQUIRED")
    request = {
        **dict(scope),
        "key_ref": key_ref,
        "key_version": key_version,
    }
    try:
        result = resolver(dict(request))
    except Exception as exc:
        raise SecretBackendError("KEY_RESOLUTION_FAILED") from exc
    if not isinstance(result, Mapping):
        raise SecretBackendError("KEY_RESOLUTION_INVALID")
    for field, expected in request.items():
        if _text(result.get(field), 240) != expected:
            raise SecretBackendError("KEY_SCOPE_MISMATCH:" + field.upper())
    key = result.get("key_bytes")
    if not isinstance(key, bytes) or len(key) != KEY_BYTES:
        raise SecretBackendError("AES256_KEY_REQUIRED")
    return key


class EncryptedStagingSecretBackend:
    """SQLite + AES-GCM staging backend. Never model-facing."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        scope: Scope,
        *,
        key_resolver: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        key_ref: Any,
        key_version: Any,
        environment: Any = "STAGING",
    ):
        env = _text(environment, 40).upper()
        if env not in _ALLOWED_ENVS:
            raise PermissionError("secret backend is staging-only")
        self.scope_obj = scope
        self.scope = _scope(scope)
        self.key_resolver = key_resolver
        self.key_ref = _token(key_ref, "key_ref")
        self.key_version = _token(key_version, "key_version")
        root = Path(path).expanduser().resolve()
        root.parent.mkdir(parents=True, exist_ok=True)
        self.path = root
        self.environment = env
        self.db = sqlite3.connect(str(root))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    def close(self) -> None:
        self.db.close()

    def _ensure_schema(self) -> None:
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS aion_staged_secrets(
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                secret_id TEXT NOT NULL,
                secret_version INTEGER NOT NULL,
                state TEXT NOT NULL,
                key_ref TEXT NOT NULL,
                key_version TEXT NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                ciphertext_digest TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(owner,tenant,workspace,secret_id,secret_version)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS aion_staged_secret_one_active
              ON aion_staged_secrets(owner,tenant,workspace,secret_id)
              WHERE state='ACTIVE';

            CREATE TABLE IF NOT EXISTS aion_staged_secret_events(
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                secret_id TEXT NOT NULL,
                secret_version INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                event_digest TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS aion_staged_secret_events_scope
              ON aion_staged_secret_events(owner,tenant,workspace,event_id);
            """)

    def _scope_args(self) -> tuple[str, str, str]:
        return (
            self.scope["owner_id"],
            self.scope["tenant_id"],
            self.scope["workspace_id"],
        )

    def _latest(self, secret_id: str):
        return self.db.execute(
            """SELECT * FROM aion_staged_secrets
               WHERE owner=? AND tenant=? AND workspace=? AND secret_id=?
               ORDER BY secret_version DESC LIMIT 1""",
            (*self._scope_args(), secret_id),
        ).fetchone()

    def _active(self, secret_id: str):
        return self.db.execute(
            """SELECT * FROM aion_staged_secrets
               WHERE owner=? AND tenant=? AND workspace=? AND secret_id=? AND state='ACTIVE'""",
            (*self._scope_args(), secret_id),
        ).fetchone()

    def _encrypt(
        self,
        secret_id: str,
        secret_version: int,
        value: Any,
    ) -> tuple[bytes, bytes, str]:
        raw = _secret_bytes(value)
        key = _resolve_key(
            self.key_resolver,
            self.scope,
            key_ref=self.key_ref,
            key_version=self.key_version,
        )
        nonce = os.urandom(NONCE_BYTES)
        aad = _aad(
            self.scope,
            secret_id=secret_id,
            secret_version=secret_version,
            key_ref=self.key_ref,
            key_version=self.key_version,
        )
        ciphertext = AESGCM(key).encrypt(nonce, raw, aad)
        return nonce, ciphertext, _digest_bytes(ciphertext)

    def _decrypt_row(self, row) -> bytes:
        ciphertext = bytes(row["ciphertext"])
        if _digest_bytes(ciphertext) != row["ciphertext_digest"]:
            raise SecretBackendIntegrityError("CIPHERTEXT_DIGEST_MISMATCH")
        key = _resolve_key(
            self.key_resolver,
            self.scope,
            key_ref=str(row["key_ref"]),
            key_version=str(row["key_version"]),
        )
        aad = _aad(
            self.scope,
            secret_id=str(row["secret_id"]),
            secret_version=int(row["secret_version"]),
            key_ref=str(row["key_ref"]),
            key_version=str(row["key_version"]),
        )
        try:
            return AESGCM(key).decrypt(bytes(row["nonce"]), ciphertext, aad)
        except InvalidTag as exc:
            raise SecretBackendIntegrityError("AUTHENTICATION_TAG_INVALID") from exc

    def _event(self, secret_id: str, version: int, event_type: str, created_at: str) -> None:
        material = {
            **self.scope,
            "secret_id": secret_id,
            "secret_version": version,
            "event_type": event_type,
            "created_at": created_at,
        }
        self.db.execute(
            """INSERT INTO aion_staged_secret_events(
                owner,tenant,workspace,secret_id,secret_version,event_type,created_at,event_digest
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                *self._scope_args(),
                secret_id,
                version,
                event_type,
                created_at,
                _digest_bytes(_canonical(material)),
            ),
        )

    def put(
        self,
        secret_id: Any,
        value: Any,
        *,
        explicit_owner_approval: Any,
        created_at: Any | None = None,
    ) -> dict[str, Any]:
        if explicit_owner_approval is not True:
            raise PermissionError("explicit HUMAN_OWNER approval required")
        sid = _token(secret_id, "secret_id")
        if self._latest(sid) is not None:
            raise ValueError("secret already exists; use rotate")
        when = _iso(_utc(created_at))
        nonce, ciphertext, digest = self._encrypt(sid, 1, value)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                """INSERT INTO aion_staged_secrets(
                    owner,tenant,workspace,secret_id,secret_version,state,
                    key_ref,key_version,nonce,ciphertext,ciphertext_digest,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?,?,?,?)""",
                (
                    *self._scope_args(),
                    sid,
                    1,
                    self.key_ref,
                    self.key_version,
                    nonce,
                    ciphertext,
                    digest,
                    when,
                    when,
                ),
            )
            self._event(sid, 1, "CREATED", when)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.metadata(sid)

    def resolve(self, secret_id: Any) -> bytes:
        sid = _token(secret_id, "secret_id")
        row = self._active(sid)
        if row is None:
            raise PermissionError("active secret unavailable")
        return self._decrypt_row(row)

    def credential_resolver(self, backend: str, locator_ref: str) -> bytes:
        if _text(backend, 60).upper() != "EXTERNAL_VAULT":
            raise PermissionError("backend name not handled by staged secret backend")
        return self.resolve(locator_ref)

    def rotate(
        self,
        secret_id: Any,
        new_value: Any,
        *,
        expected_version: Any,
        explicit_owner_approval: Any,
        changed_at: Any | None = None,
    ) -> dict[str, Any]:
        if explicit_owner_approval is not True:
            raise PermissionError("explicit HUMAN_OWNER approval required")
        sid = _token(secret_id, "secret_id")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValueError("valid expected_version required")
        when = _iso(_utc(changed_at))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._active(sid)
            if current is None:
                raise LookupError("active secret unavailable")
            current_version = int(current["secret_version"])
            if current_version != expected_version:
                raise ValueError("SECRET_VERSION_CONFLICT")
            next_version = current_version + 1
            nonce, ciphertext, digest = self._encrypt(sid, next_version, new_value)
            self.db.execute(
                """UPDATE aion_staged_secrets
                   SET state='RETIRED',updated_at=?
                   WHERE owner=? AND tenant=? AND workspace=? AND secret_id=? AND secret_version=? AND state='ACTIVE'""",
                (when, *self._scope_args(), sid, current_version),
            )
            self.db.execute(
                """INSERT INTO aion_staged_secrets(
                    owner,tenant,workspace,secret_id,secret_version,state,
                    key_ref,key_version,nonce,ciphertext,ciphertext_digest,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?,?,?,?)""",
                (
                    *self._scope_args(),
                    sid,
                    next_version,
                    self.key_ref,
                    self.key_version,
                    nonce,
                    ciphertext,
                    digest,
                    when,
                    when,
                ),
            )
            self._event(sid, next_version, "ROTATED", when)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.metadata(sid)

    def revoke(
        self,
        secret_id: Any,
        *,
        expected_version: Any,
        explicit_owner_approval: Any,
        changed_at: Any | None = None,
    ) -> dict[str, Any]:
        if explicit_owner_approval is not True:
            raise PermissionError("explicit HUMAN_OWNER approval required")
        sid = _token(secret_id, "secret_id")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise ValueError("valid expected_version required")
        when = _iso(_utc(changed_at))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._active(sid)
            if current is None:
                raise LookupError("active secret unavailable")
            if int(current["secret_version"]) != expected_version:
                raise ValueError("SECRET_VERSION_CONFLICT")
            self.db.execute(
                """UPDATE aion_staged_secrets
                   SET state='REVOKED',updated_at=?
                   WHERE owner=? AND tenant=? AND workspace=? AND secret_id=? AND secret_version=? AND state='ACTIVE'""",
                (when, *self._scope_args(), sid, expected_version),
            )
            self._event(sid, expected_version, "REVOKED", when)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.metadata(sid)

    def metadata(self, secret_id: Any) -> dict[str, Any]:
        sid = _token(secret_id, "secret_id")
        row = self._latest(sid)
        if row is None:
            raise LookupError("secret metadata unavailable")
        return {
            "schema": SCHEMA,
            **self.scope,
            "secret_id": sid,
            "secret_version": int(row["secret_version"]),
            "state": str(row["state"]),
            "key_ref": str(row["key_ref"]),
            "key_version": str(row["key_version"]),
            "ciphertext_digest": str(row["ciphertext_digest"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "algorithm": ALGORITHM,
            "contains_secret_value": False,
            "key_material_serialized": False,
            "production_backend": False,
            "executes_action": False,
        }

    def integrity_report(self) -> dict[str, Any]:
        rows = self.db.execute(
            """SELECT * FROM aion_staged_secrets
               WHERE owner=? AND tenant=? AND workspace=?
               ORDER BY secret_id,secret_version""",
            self._scope_args(),
        ).fetchall()
        blockers: list[str] = []
        active_ids: list[str] = []
        for row in rows:
            ciphertext = bytes(row["ciphertext"])
            if _digest_bytes(ciphertext) != row["ciphertext_digest"]:
                blockers.append("CIPHERTEXT_DIGEST_MISMATCH:" + str(row["secret_id"]))
                continue
            if row["state"] == "ACTIVE":
                active_ids.append(str(row["secret_id"]))
                try:
                    self._decrypt_row(row)
                except Exception as exc:
                    blockers.append(type(exc).__name__ + ":" + str(row["secret_id"]))
        return {
            "schema": SCHEMA,
            "state": "MATCH" if not blockers else "MISMATCH",
            "blockers": blockers,
            "scope": dict(self.scope),
            "records": len(rows),
            "active": len(active_ids),
            "active_secret_ids": sorted(active_ids),
            "algorithm": ALGORITHM,
            "physical_store": "SQLITE",
            "encrypted_at_rest": True,
            "plaintext_persisted": False,
            "key_material_serialized": False,
            "rotation_supported": True,
            "revocation_supported": True,
            "production_backend": False,
            "executes_action": False,
        }

    def attestation(self) -> dict[str, Any]:
        report = self.integrity_report()
        verified = report["state"] == "MATCH"
        return {
            "schema": ATTESTATION_SCHEMA,
            "state": "VERIFIED_STAGING_BACKEND" if verified else "BLOCKED",
            "scope": dict(self.scope),
            "integrity_state": report["state"],
            "active_secret_ids": list(report["active_secret_ids"]),
            "algorithm": ALGORITHM,
            "physical_store": "SQLITE",
            "encrypted_at_rest": True,
            "plaintext_persisted": False,
            "key_material_serialized": False,
            "rotation_supported": True,
            "revocation_supported": True,
            "backend_connected": verified,
            "production_kms_connected": False,
            "production_ready": False,
            "automatic_rotation": False,
            "automatic_revocation": False,
            "executes_action": False,
        }


def verified_vault_backend_view(
    vault_state: Mapping[str, Any] | None,
    backend_attestation: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    vault = normalize_vault(vault_state)
    attestation = dict(backend_attestation) if isinstance(backend_attestation, Mapping) else {}
    trusted = {
        "owner_id": _text((trusted_scope or {}).get("owner_id"), 120)
        if isinstance(trusted_scope, Mapping) else "",
        "tenant_id": _text((trusted_scope or {}).get("tenant_id"), 120)
        if isinstance(trusted_scope, Mapping) else "",
        "workspace_id": _text((trusted_scope or {}).get("workspace_id"), 120)
        if isinstance(trusted_scope, Mapping) else "",
    }
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if attestation.get("schema") != ATTESTATION_SCHEMA:
        blockers.append("BACKEND_ATTESTATION_SCHEMA_INVALID")
    if attestation.get("state") != "VERIFIED_STAGING_BACKEND":
        blockers.append("BACKEND_NOT_VERIFIED")
    if attestation.get("scope") != trusted:
        blockers.append("BACKEND_SCOPE_MISMATCH")
    if attestation.get("encrypted_at_rest") is not True:
        blockers.append("BACKEND_ENCRYPTION_REQUIRED")
    if attestation.get("plaintext_persisted") is not False:
        blockers.append("BACKEND_PLAINTEXT_FORBIDDEN")
    if attestation.get("key_material_serialized") is not False:
        blockers.append("BACKEND_KEY_SERIALIZATION_FORBIDDEN")
    if attestation.get("rotation_supported") is not True:
        blockers.append("BACKEND_ROTATION_REQUIRED")
    if attestation.get("revocation_supported") is not True:
        blockers.append("BACKEND_REVOCATION_REQUIRED")
    if attestation.get("production_kms_connected") is not False:
        blockers.append("PRODUCTION_KMS_CLAIM_FORBIDDEN")
    if attestation.get("production_ready") is not False:
        blockers.append("PRODUCTION_READY_CLAIM_FORBIDDEN")
    if attestation.get("executes_action") is not False:
        blockers.append("BACKEND_ATTESTATION_MUST_NOT_EXECUTE")

    active_ids = set(
        str(x)
        for x in attestation.get("active_secret_ids", [])
        if isinstance(x, str)
    )
    required = [
        str(row.get("locator_ref"))
        for row in vault.get("entries", [])
        if row.get("kind") == "SECRET_REF"
        and row.get("state") == "ACTIVE"
        and row.get("backend") == "EXTERNAL_VAULT"
    ]
    unresolved = sorted(ref for ref in required if ref not in active_ids)
    if unresolved:
        blockers.append("ACTIVE_VAULT_REFS_UNRESOLVED")

    return {
        "schema": ATTESTATION_SCHEMA,
        "state": "VERIFIED_STAGING_BACKEND" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "scope": trusted,
        "vault_digest": vault.get("digest"),
        "active_external_vault_refs": len(required),
        "unresolved_refs": unresolved,
        "backend_connected": not blockers,
        "backend_state": "VERIFIED_STAGING" if not blockers else "BLOCKED",
        "encrypted_at_rest": True,
        "plaintext_secrets_present": vault.get("plaintext_secrets_present") is True,
        "production_kms_connected": False,
        "production_ready": False,
        "secret_values_exported": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ATTESTATION_SCHEMA",
    "ALGORITHM",
    "SecretBackendError",
    "SecretBackendIntegrityError",
    "EncryptedStagingSecretBackend",
    "verified_vault_backend_view",
]
