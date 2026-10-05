"""Opaque staging credential proxy for AION tools.

The model-facing side receives only a short-lived opaque handle. Secret backend
locators and secret values remain inside this proxy. A secret is resolved only
after the closed tool contract and post-DNS egress destination pass validation.

No secret backend implementation and no network client live in this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from atlasquant_aion_observability import is_secret_key
from atlasquant_aion_tool_sandbox import PROXY_PROFILE, validate_egress_request
from atlasquant_aion_vault import normalize_vault

SCHEMA = "ATLASQUANT_AION_CREDENTIAL_PROXY_V1"
MAX_HANDLE_TTL_SECONDS = 300
_ALLOWED_SECRET_BACKENDS = frozenset({
    "ENVIRONMENT",
    "RENDER_SECRET",
    "GITHUB_ACTIONS_SECRET",
    "OS_KEYCHAIN",
    "EXTERNAL_VAULT",
})


class CredentialProxyError(RuntimeError):
    pass


class CredentialLeakError(CredentialProxyError):
    pass


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _utc(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def _scopes(values: Sequence[Any] | None) -> list[str]:
    out = []
    for raw in list(values or [])[:40]:
        text = _clean(raw, 120)
        if text and text not in out:
            out.append(text)
    return out


def _contains_secret(value: Any, secret: str, depth: int = 0) -> bool:
    if depth > 8:
        return False
    if isinstance(value, Mapping):
        for key, item in value.items():
            if is_secret_key(key):
                return True
            if _contains_secret(item, secret, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item, secret, depth + 1) for item in value[:100])
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", "ignore")
        except Exception:
            return True
        return bool(secret and secret in text)
    if isinstance(value, str):
        return bool(secret and secret in value)
    return False


def _verified_credential_tool(tool: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(tool or {})
    if item.get("registry_approved") is not True:
        raise PermissionError("tool is not registry approved")
    if item.get("supply_chain_state") != "VERIFIED":
        raise PermissionError("tool supply chain is not verified")
    contract_hash = _clean(item.get("contract_hash"), 64)
    pinned_hash = _clean(item.get("pinned_contract_hash"), 64)
    if not contract_hash or contract_hash != pinned_hash:
        raise PermissionError("tool contract hash is not pinned")
    if _clean(item.get("sandbox_profile"), 60).upper() != PROXY_PROFILE:
        raise PermissionError("credentialed tool must use the egress proxy sandbox")
    if not _clean(item.get("credential_ref"), 96):
        raise PermissionError("tool has no credential reference")
    if not _scopes(item.get("credential_scopes")):
        raise PermissionError("tool has no credential scopes")
    return item


class CredentialProxy:
    """In-memory, short-lived handle broker for staging red-team proof."""

    def __init__(
        self,
        vault_state: Mapping[str, Any] | None,
        resolver: Callable[[str, str], Any],
        *,
        environment: Any = "STAGING",
    ):
        env = _clean(environment, 40).upper()
        if env not in {"LOCAL", "DEV", "DEVELOPMENT", "STAGING", "TEST", "QA"}:
            raise PermissionError("credential proxy is staging-only")
        if not callable(resolver):
            raise TypeError("secret backend resolver callable required")
        self._vault = normalize_vault(vault_state)
        self._resolver = resolver
        self._leases: dict[str, dict[str, Any]] = {}
        self.environment = env

    def _entry_for_tool(
        self,
        tool: Mapping[str, Any],
        requested_scopes: Sequence[Any] | None,
    ) -> tuple[dict[str, Any], list[str]]:
        item = _verified_credential_tool(tool)
        ref = _clean(item.get("credential_ref"), 96)
        entry = next(
            (
                dict(row)
                for row in self._vault.get("entries", [])
                if row.get("entry_id") == ref
            ),
            None,
        )
        if not entry:
            raise LookupError("credential reference is not present in the Vault")
        if entry.get("kind") != "SECRET_REF" or entry.get("state") != "ACTIVE":
            raise PermissionError("credential reference is not active")
        if entry.get("backend") not in _ALLOWED_SECRET_BACKENDS:
            raise PermissionError("secret backend is not approved for credential resolution")
        if entry.get("least_privilege_scoped") is not True:
            raise PermissionError("Vault secret reference is not least-privilege scoped")
        tool_id = _clean(item.get("tool_id"), 96)
        if tool_id not in _scopes(entry.get("allowed_tool_ids")):
            raise PermissionError("Vault secret reference is not approved for this tool")

        requested = _scopes(requested_scopes)
        tool_scopes = set(_scopes(item.get("credential_scopes")))
        vault_scopes = set(_scopes(entry.get("credential_scopes")))
        if not requested:
            raise ValueError("explicit credential scopes required")
        if not set(requested).issubset(tool_scopes):
            raise PermissionError("requested scope exceeds tool contract")
        if not set(requested).issubset(vault_scopes):
            raise PermissionError("requested scope exceeds Vault grant")
        return entry, requested

    def issue_handle(
        self,
        tool: Mapping[str, Any],
        *,
        requested_scopes: Sequence[Any] | None,
        ttl_seconds: int = 60,
        now: Any | None = None,
    ) -> dict[str, Any]:
        if isinstance(ttl_seconds, bool) or not 1 <= int(ttl_seconds) <= MAX_HANDLE_TTL_SECONDS:
            raise ValueError("invalid credential handle TTL")
        item = _verified_credential_tool(tool)
        entry, scopes = self._entry_for_tool(item, requested_scopes)
        created = _utc(now)
        expires = created + timedelta(seconds=int(ttl_seconds))
        handle = "crh_" + uuid4().hex
        self._leases[handle] = {
            "tool_id": _clean(item.get("tool_id"), 96),
            "contract_hash": _clean(item.get("contract_hash"), 64),
            "entry_id": entry["entry_id"],
            "backend": entry["backend"],
            "locator_ref": entry["locator_ref"],
            "scopes": scopes,
            "created_at": created,
            "expires_at": expires,
            "used": False,
            "revoked": False,
        }
        return {
            "schema": SCHEMA,
            "state": "ISSUED",
            "handle": handle,
            "tool_id": self._leases[handle]["tool_id"],
            "scopes": list(scopes),
            "expires_at": expires.isoformat(),
            "opaque": True,
            "contains_secret": False,
            "contains_locator": False,
            "model_may_resolve": False,
            "one_shot": True,
        }

    def revoke_handle(self, handle: Any) -> bool:
        key = _clean(handle, 100)
        lease = self._leases.get(key)
        if not lease:
            return False
        lease["revoked"] = True
        return True

    def _active_lease(
        self,
        handle: Any,
        tool: Mapping[str, Any],
        *,
        now: Any | None,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        key = _clean(handle, 100)
        if not key.startswith("crh_"):
            raise PermissionError("invalid credential handle")
        lease = self._leases.get(key)
        if not lease:
            raise PermissionError("credential handle unavailable")
        if lease["revoked"]:
            raise PermissionError("credential handle revoked")
        if lease["used"]:
            raise PermissionError("credential handle already consumed")
        moment = _utc(now)
        if moment >= lease["expires_at"]:
            raise PermissionError("credential handle expired")
        item = _verified_credential_tool(tool)
        if lease["tool_id"] != _clean(item.get("tool_id"), 96):
            raise PermissionError("credential handle bound to another tool")
        if lease["contract_hash"] != _clean(item.get("contract_hash"), 64):
            raise PermissionError("tool contract changed after handle issuance")
        if lease["entry_id"] != _clean(item.get("credential_ref"), 96):
            raise PermissionError("credential reference changed after handle issuance")
        return key, lease, item

    def invoke_egress(
        self,
        handle: Any,
        tool: Mapping[str, Any],
        *,
        url: Any,
        resolved_ips: Sequence[Any] | None,
        preflight: Mapping[str, Any] | None,
        callback: Callable[[str, Mapping[str, Any]], Any],
        now: Any | None = None,
    ) -> dict[str, Any]:
        """Resolve the secret only after egress validation; never return the secret."""
        if not callable(callback):
            raise TypeError("adapter callback required")
        key, lease, item = self._active_lease(handle, tool, now=now)
        gate = dict(preflight or {})
        gate_tool = (
            dict(gate.get("tool"))
            if isinstance(gate.get("tool"), Mapping)
            else {}
        )
        gate_connector = (
            dict(gate.get("connector"))
            if isinstance(gate.get("connector"), Mapping)
            else {}
        )
        if gate.get("state") != "READY_FOR_EXECUTOR":
            raise PermissionError("Tool Hub preflight is not READY_FOR_EXECUTOR")
        if _clean(gate_tool.get("tool_id"), 96) != lease["tool_id"]:
            raise PermissionError("preflight is bound to another tool")
        if _clean(gate_tool.get("contract_hash"), 64) != lease["contract_hash"]:
            raise PermissionError("preflight tool contract does not match credential handle")
        if gate_tool.get("supply_chain_state") != "VERIFIED":
            raise PermissionError("preflight supply chain is not verified")
        if gate_connector.get("required") is True and gate_connector.get("activated") is not True:
            raise PermissionError("preflight connector is not activated")

        egress = validate_egress_request(item, url, resolved_ips)

        # From this point on the one-shot lease is consumed even if resolution or
        # the adapter fails. This prevents replay after secret materialization.
        lease["used"] = True
        secret_value = self._resolver(lease["backend"], lease["locator_ref"])
        if isinstance(secret_value, bytes):
            secret = secret_value.decode("utf-8")
        else:
            secret = str(secret_value or "")
        if not secret:
            raise CredentialProxyError("secret backend returned an empty value")

        result = callback(secret, {
            "tool_id": lease["tool_id"],
            "scopes": list(lease["scopes"]),
            "egress": egress,
        })
        if _contains_secret(result, secret):
            raise CredentialLeakError("adapter result attempted to expose a credential")

        return {
            "schema": SCHEMA,
            "state": "COMPLETED",
            "tool_id": lease["tool_id"],
            "handle": key,
            "result": result,
            "egress": egress,
            "credential_resolved": True,
            "credential_exposed_to_model": False,
            "credential_in_result": False,
            "handle_consumed": True,
        }


__all__ = [
    "SCHEMA",
    "MAX_HANDLE_TTL_SECONDS",
    "CredentialProxyError",
    "CredentialLeakError",
    "CredentialProxy",
]
