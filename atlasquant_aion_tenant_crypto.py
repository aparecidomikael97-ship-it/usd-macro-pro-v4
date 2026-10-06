"""Tenant/workspace authenticated encryption for staged AION durable data.

Uses AES-256-GCM from cryptography. Key material is supplied only by an injected
resolver and is never serialized, logged, cached here, or exposed in results.
The authenticated data binds tenant, workspace, key handle/version and the
inner durable-store revision/digest.

This is a staging cryptographic boundary, not a production KMS implementation.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import json
import os
from typing import Any, Callable, Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SCHEMA = "ATLASQUANT_AION_TENANT_CRYPTO_ENVELOPE_V1"
ALGORITHM = "AES-256-GCM"
NONCE_BYTES = 12
KEY_BYTES = 32
MAX_CIPHERTEXT_BYTES = 512_000


class TenantCryptoError(ValueError):
    def __init__(self, reason: str):
        self.reason = str(reason or "CRYPTO_FAILURE")
        super().__init__(self.reason)


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64d(value: Any, *, field: str, max_bytes: int) -> bytes:
    text = _clean(value, max_bytes * 2)
    if not text:
        raise TenantCryptoError(field.upper() + "_MISSING")
    try:
        raw = text.encode("ascii")
        out = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise TenantCryptoError(field.upper() + "_INVALID") from exc
    if not out or len(out) > max_bytes:
        raise TenantCryptoError(field.upper() + "_INVALID")
    return out


def _aad_payload(
    *,
    tenant_id: str,
    workspace_id: str,
    key_ref: str,
    key_version: str,
    revision: str,
    payload_digest: str,
) -> dict[str, str]:
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "key_ref": key_ref,
        "key_version": key_version,
        "revision": revision,
        "payload_digest": payload_digest,
    }


def _resolve_key(
    resolver: Callable[[Mapping[str, str]], Mapping[str, Any]],
    *,
    tenant_id: str,
    workspace_id: str,
    key_ref: str,
    key_version: str,
) -> bytes:
    if not callable(resolver):
        raise TenantCryptoError("KEY_RESOLVER_REQUIRED")
    request = {
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "key_ref": key_ref,
        "key_version": key_version,
    }
    try:
        result = resolver(dict(request))
    except Exception as exc:
        raise TenantCryptoError("KEY_RESOLUTION_FAILED") from exc
    if not isinstance(result, Mapping):
        raise TenantCryptoError("KEY_RESOLUTION_INVALID")
    for field, expected in request.items():
        if _clean(result.get(field), 240) != expected:
            raise TenantCryptoError("KEY_SCOPE_MISMATCH:" + field.upper())
    key = result.get("key_bytes")
    if not isinstance(key, bytes) or len(key) != KEY_BYTES:
        raise TenantCryptoError("AES256_KEY_REQUIRED")
    return key


def is_encrypted_envelope(raw: Mapping[str, Any] | None) -> bool:
    return isinstance(raw, Mapping) and raw.get("schema") == SCHEMA


def encrypt_tenant_envelope(
    inner: Mapping[str, Any],
    *,
    tenant_id: Any,
    workspace_id: Any,
    key_ref: Any,
    key_version: Any,
    key_resolver: Callable[[Mapping[str, str]], Mapping[str, Any]],
    nonce_factory: Callable[[int], bytes] = os.urandom,
) -> dict[str, Any]:
    tenant = _clean(tenant_id, 160)
    workspace = _clean(workspace_id, 160)
    ref = _clean(key_ref, 200)
    version = _clean(key_version, 80)
    if not tenant or not workspace or not ref or not version:
        raise TenantCryptoError("CRYPTO_BINDING_INCOMPLETE")
    row = dict(inner or {})
    revision = _clean(row.get("revision"), 160)
    payload_digest = _clean(row.get("payload_digest"), 160)
    if not revision or not payload_digest:
        raise TenantCryptoError("INNER_INTEGRITY_BINDING_MISSING")
    if _clean(row.get("tenant_id"), 160) != tenant:
        raise TenantCryptoError("INNER_TENANT_MISMATCH")
    if _clean(row.get("workspace_id"), 160) != workspace:
        raise TenantCryptoError("INNER_WORKSPACE_MISMATCH")

    key = _resolve_key(
        key_resolver,
        tenant_id=tenant,
        workspace_id=workspace,
        key_ref=ref,
        key_version=version,
    )
    nonce = nonce_factory(NONCE_BYTES)
    if not isinstance(nonce, bytes) or len(nonce) != NONCE_BYTES:
        raise TenantCryptoError("NONCE_INVALID")
    aad_row = _aad_payload(
        tenant_id=tenant,
        workspace_id=workspace,
        key_ref=ref,
        key_version=version,
        revision=revision,
        payload_digest=payload_digest,
    )
    aad = _canonical(aad_row)
    plaintext = _canonical(row)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    if len(ciphertext) > MAX_CIPHERTEXT_BYTES:
        raise TenantCryptoError("CIPHERTEXT_TOO_LARGE")
    return {
        **aad_row,
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ciphertext),
        "aad_digest": "sha256:" + sha256(aad).hexdigest(),
        "encrypted_at_rest": True,
        "key_material_serialized": False,
        "production_kms_connected": False,
    }


def decrypt_tenant_envelope(
    outer: Mapping[str, Any],
    *,
    tenant_id: Any,
    workspace_id: Any,
    key_resolver: Callable[[Mapping[str, str]], Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(outer, Mapping) or outer.get("schema") != SCHEMA:
        raise TenantCryptoError("CRYPTO_ENVELOPE_REQUIRED")
    tenant = _clean(tenant_id, 160)
    workspace = _clean(workspace_id, 160)
    if _clean(outer.get("algorithm"), 80) != ALGORITHM:
        raise TenantCryptoError("CRYPTO_ALGORITHM_MISMATCH")
    if _clean(outer.get("tenant_id"), 160) != tenant:
        raise TenantCryptoError("CRYPTO_TENANT_MISMATCH")
    if _clean(outer.get("workspace_id"), 160) != workspace:
        raise TenantCryptoError("CRYPTO_WORKSPACE_MISMATCH")
    ref = _clean(outer.get("key_ref"), 200)
    version = _clean(outer.get("key_version"), 80)
    revision = _clean(outer.get("revision"), 160)
    payload_digest = _clean(outer.get("payload_digest"), 160)
    if not ref or not version or not revision or not payload_digest:
        raise TenantCryptoError("CRYPTO_BINDING_INCOMPLETE")

    aad_row = _aad_payload(
        tenant_id=tenant,
        workspace_id=workspace,
        key_ref=ref,
        key_version=version,
        revision=revision,
        payload_digest=payload_digest,
    )
    aad = _canonical(aad_row)
    expected_aad = "sha256:" + sha256(aad).hexdigest()
    if _clean(outer.get("aad_digest"), 160) != expected_aad:
        raise TenantCryptoError("AAD_DIGEST_MISMATCH")

    nonce = _b64d(outer.get("nonce"), field="nonce", max_bytes=NONCE_BYTES)
    if len(nonce) != NONCE_BYTES:
        raise TenantCryptoError("NONCE_INVALID")
    ciphertext = _b64d(
        outer.get("ciphertext"),
        field="ciphertext",
        max_bytes=MAX_CIPHERTEXT_BYTES,
    )
    key = _resolve_key(
        key_resolver,
        tenant_id=tenant,
        workspace_id=workspace,
        key_ref=ref,
        key_version=version,
    )
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise TenantCryptoError("AUTHENTICATION_TAG_INVALID") from exc
    except Exception as exc:
        raise TenantCryptoError("DECRYPTION_FAILED") from exc
    try:
        inner = json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise TenantCryptoError("INNER_PAYLOAD_INVALID") from exc
    if not isinstance(inner, dict):
        raise TenantCryptoError("INNER_PAYLOAD_INVALID")
    if _clean(inner.get("tenant_id"), 160) != tenant:
        raise TenantCryptoError("INNER_TENANT_MISMATCH")
    if _clean(inner.get("workspace_id"), 160) != workspace:
        raise TenantCryptoError("INNER_WORKSPACE_MISMATCH")
    if _clean(inner.get("revision"), 160) != revision:
        raise TenantCryptoError("INNER_REVISION_MISMATCH")
    if _clean(inner.get("payload_digest"), 160) != payload_digest:
        raise TenantCryptoError("INNER_PAYLOAD_DIGEST_MISMATCH")
    return inner


def crypto_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "key_bytes": KEY_BYTES,
        "nonce_bytes": NONCE_BYTES,
        "key_material_serialized": False,
        "key_resolver_injected": True,
        "tenant_workspace_bound_aad": True,
        "encryption_required_for_production": True,
        "homegrown_crypto": False,
        "production_kms_connected": False,
        "automatic_key_deletion": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ALGORITHM",
    "TenantCryptoError",
    "is_encrypted_envelope",
    "encrypt_tenant_envelope",
    "decrypt_tenant_envelope",
    "crypto_policy",
]
