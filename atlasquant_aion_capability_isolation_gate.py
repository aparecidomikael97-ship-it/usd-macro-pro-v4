"""AION V2.15 signed capability-scope and isolation gate.

A valid V2.13 authority statement is necessary but not sufficient. This gate
adds a second, signed scope grant bound to one tenant/workspace/domain,
capability, tool/action ceiling, namespace and cost ceiling.

Nothing in this module executes an action.
"""
from __future__ import annotations

import base64
import json
import math
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_authority_verifier import verify_authority_statement
from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_specialist_router import route_specialist
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_CAPABILITY_SCOPE_GRANT_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_CAPABILITY_SCOPE_VERIFICATION_V1"
GRANT_KIND = "CAPABILITY_SCOPE_GRANT"
MAX_GRANT_BYTES = 65_536
MAX_ITEMS = 64
FIELDS = {
    "schema",
    "grant_id",
    "parent_statement_id",
    "authority_id",
    "subject_id",
    "tenant_id",
    "workspace_id",
    "domain",
    "policy_id",
    "capability_id",
    "allowed_tools",
    "allowed_actions",
    "max_cost_usd",
    "namespace",
    "issued_at",
    "expires_at",
    "nonce",
    "key_id",
    "key_version",
    "grant_kind",
}


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    raw = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(raw) > MAX_GRANT_BYTES:
        raise ValueError("capability scope grant oversized")
    return raw


def canonical_scope_grant_bytes(value: Mapping[str, Any]) -> bytes:
    if not isinstance(value, Mapping) or set(value) != FIELDS:
        raise ValueError("capability scope grant shape mismatch")
    return _canonical_bytes(value)


def _decode_signature(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return decoded


def canonical_namespace(tenant_id: Any, workspace_id: Any, domain: Any) -> str:
    tenant = _clean(tenant_id, 128)
    workspace = _clean(workspace_id, 128)
    domain_token = _clean(domain, 64).upper()
    if not tenant or not workspace or not domain_token:
        raise ValueError("tenant/workspace/domain required")
    for value in (tenant, workspace, domain_token):
        if any(ch in value for ch in ("|", "\n", "\r", "\x00")):
            raise ValueError("invalid namespace component")
    return f"tenant/{tenant}/workspace/{workspace}/domain/{domain_token}"


def _blocked(*blockers: str, parent=None) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(str(x) for x in blockers if str(x))),
        "parent_authority_verified": bool(
            isinstance(parent, Mapping) and parent.get("authority_verified") is True
        ),
        "scope_signature_verified": False,
        "scope_binding_verified": False,
        "capability_registered": False,
        "capability_granted_by_parent": False,
        "domain_isolated": False,
        "tenant_isolated": False,
        "workspace_isolated": False,
        "namespace_verified": False,
        "role_allowed": False,
        "tool_scope_verified": False,
        "action_scope_verified": False,
        "budget_scope_verified": False,
        "capability_scope_verified": False,
        "execution_allowed": False,
        "approval_implied": False,
        "permissions_expanded": False,
        "tool_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "real_trading_enabled": False,
    }


def verify_capability_scope(
    parent_statement: Any,
    *,
    parent_signature_b64: str,
    scope_grant: Any,
    scope_signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    expected_binding: Mapping[str, str],
    expected_workspace_id: str,
    actor_role: str,
    requested_tool: str = "",
    requested_action: str = "",
    registry: CapabilityRegistry | None = None,
) -> dict[str, Any]:
    """Verify authority + signed least-privilege capability scope.

    expected_binding and expected_workspace_id are trusted host context, not
    caller claims. The result remains a pre-execution scope decision.
    """
    parent = verify_authority_statement(
        parent_statement,
        signature_b64=parent_signature_b64,
        trust_roots=trust_roots,
        nonce_registry=nonce_registry,
        now_ts=now_ts,
        expected_binding=expected_binding,
    )
    if parent.get("state") != "VERIFIED" or parent.get("authority_verified") is not True:
        return _blocked("PARENT_AUTHORITY_NOT_VERIFIED", parent=parent)

    if not isinstance(scope_grant, Mapping) or set(scope_grant) != FIELDS:
        return _blocked("SCOPE_GRANT_SHAPE_MISMATCH", parent=parent)
    grant = dict(scope_grant)

    blockers: list[str] = []
    if grant.get("schema") != SCHEMA:
        blockers.append("SCOPE_SCHEMA_MISMATCH")
    if grant.get("grant_kind") != GRANT_KIND:
        blockers.append("SCOPE_GRANT_KIND_INVALID")

    for field in (
        "grant_id", "parent_statement_id", "authority_id", "subject_id",
        "tenant_id", "workspace_id", "domain", "policy_id", "capability_id",
        "namespace", "issued_at", "expires_at", "nonce", "key_id",
    ):
        value = grant.get(field)
        if not isinstance(value, str) or not value or len(value) > 256:
            blockers.append(f"SCOPE_FIELD_INVALID:{field}")

    version = grant.get("key_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        blockers.append("SCOPE_KEY_VERSION_INVALID")

    max_cost = grant.get("max_cost_usd")
    if (
        isinstance(max_cost, bool)
        or not isinstance(max_cost, (int, float))
        or not math.isfinite(float(max_cost))
        or float(max_cost) < 0
    ):
        blockers.append("SCOPE_COST_LIMIT_INVALID")

    def _list(field: str) -> list[str]:
        raw = grant.get(field)
        if (
            not isinstance(raw, list)
            or len(raw) > MAX_ITEMS
            or any(not isinstance(v, str) or not v or len(v) > 256 for v in raw)
            or len(raw) != len(set(raw))
        ):
            blockers.append(f"SCOPE_LIST_INVALID:{field}")
            return []
        return list(raw)

    granted_tools = _list("allowed_tools")
    granted_actions = [x.lower() for x in _list("allowed_actions")]

    if grant.get("parent_statement_id") != parent.get("statement_id"):
        blockers.append("SCOPE_PARENT_STATEMENT_MISMATCH")
    for field in ("authority_id", "subject_id", "tenant_id", "domain", "policy_id"):
        if grant.get(field) != parent.get(field):
            blockers.append(f"SCOPE_PARENT_BINDING_MISMATCH:{field}")
    # No delegated-signer policy exists yet. A child scope grant must therefore
    # be signed under the exact same trust-root key/version as its parent.
    if (
        grant.get("key_id") != parent.get("key_id")
        or grant.get("key_version") != parent.get("key_version")
    ):
        blockers.append("SCOPE_SIGNER_MISMATCH_PARENT")

    workspace = _clean(expected_workspace_id, 128)
    if not workspace or grant.get("workspace_id") != workspace:
        blockers.append("SCOPE_WORKSPACE_MISMATCH")

    expected_namespace = ""
    try:
        expected_namespace = canonical_namespace(
            parent.get("tenant_id"), workspace, parent.get("domain")
        )
    except ValueError:
        blockers.append("SCOPE_NAMESPACE_EXPECTATION_INVALID")
    if expected_namespace and grant.get("namespace") != expected_namespace:
        blockers.append("SCOPE_NAMESPACE_MISMATCH")

    cap_id = _clean(grant.get("capability_id"), 96).lower()
    if cap_id not in set(parent.get("capabilities") or []):
        blockers.append("SCOPE_CAPABILITY_NOT_GRANTED_BY_PARENT")

    try:
        reg = registry if registry is not None else default_registry()
        if not isinstance(reg, CapabilityRegistry):
            raise TypeError("invalid capability registry")
        capability = reg.get(cap_id)
    except Exception:
        capability = None
        blockers.append("SCOPE_CAPABILITY_REGISTRY_FAILURE")
    if capability is None and "SCOPE_CAPABILITY_REGISTRY_FAILURE" not in blockers:
        blockers.append("SCOPE_CAPABILITY_NOT_REGISTERED")

    try:
        route = route_specialist(domain=parent.get("domain"))
        if not isinstance(route, Mapping):
            raise TypeError("invalid specialist route")
    except Exception:
        route = {}
        blockers.append("SCOPE_SPECIALIST_ROUTER_FAILURE")
    if "SCOPE_SPECIALIST_ROUTER_FAILURE" not in blockers:
        if route.get("status") != "SELECTED":
            blockers.append("SCOPE_DOMAIN_NOT_ROUTABLE")
        elif cap_id not in set(route.get("capability_ids") or []):
            blockers.append("SCOPE_CAPABILITY_CROSS_DOMAIN")

    role = _clean(actor_role, 32).upper()
    if capability is not None and role not in set(capability.allowed_roles):
        blockers.append("SCOPE_ROLE_NOT_ALLOWED")

    profile_tools = set(route.get("profile_allowed_tools") or [])
    capability_tools = set(capability.allowed_tools if capability is not None else ())
    if any(tool not in capability_tools or tool not in profile_tools for tool in granted_tools):
        blockers.append("SCOPE_TOOL_GRANT_EXCEEDS_PROFILE")
    requested_tool_clean = _clean(requested_tool, 128)
    if requested_tool_clean and requested_tool_clean not in set(granted_tools):
        blockers.append("SCOPE_REQUESTED_TOOL_NOT_GRANTED")

    profile_actions = {str(x).lower() for x in route.get("profile_allowed_actions") or []}
    denied_actions = {str(x).lower() for x in route.get("denied_actions") or []}
    if any(action not in profile_actions or action in denied_actions for action in granted_actions):
        blockers.append("SCOPE_ACTION_GRANT_EXCEEDS_PROFILE")
    requested_action_clean = _clean(requested_action, 128).lower()
    if requested_action_clean and requested_action_clean not in set(granted_actions):
        blockers.append("SCOPE_REQUESTED_ACTION_NOT_GRANTED")

    if capability is not None and isinstance(max_cost, (int, float)) and not isinstance(max_cost, bool):
        if capability.estimated_cost_usd > float(max_cost):
            blockers.append("SCOPE_COST_CEILING_EXCEEDED")

    # The signed child grant cannot outlive its verified parent.
    try:
        from datetime import datetime, timezone

        def ts(value):
            if not isinstance(value, str) or not value.endswith("Z"):
                raise ValueError
            return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)

        now = ts(now_ts)
        issued = ts(grant["issued_at"])
        expires = ts(grant["expires_at"])
        parent_issued = ts(parent_statement["issued_at"])
        parent_expires = ts(parent_statement["expires_at"])
        if issued > now:
            blockers.append("SCOPE_NOT_YET_VALID")
        if expires <= now or expires <= issued:
            blockers.append("SCOPE_EXPIRED_OR_INVALID_WINDOW")
        if issued < parent_issued or expires > parent_expires:
            blockers.append("SCOPE_WINDOW_EXCEEDS_PARENT")
    except Exception:
        blockers.append("SCOPE_TIME_INVALID")

    entry = None
    if not blockers:
        try:
            entry, problem = trust_roots.verify_key_available(
                grant["key_id"], grant["key_version"], now_ts
            )
        except Exception:
            blockers.append("SCOPE_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if problem:
                blockers.append(problem)

    signature_verified = False
    if not blockers and entry is not None:
        try:
            signature = _decode_signature(scope_signature_b64)
            entry.public_key().verify(signature, _canonical_bytes(grant))
            signature_verified = True
        except (ValueError, InvalidSignature):
            blockers.append("SCOPE_SIGNATURE_INVALID")

    if blockers:
        result = _blocked(*blockers, parent=parent)
        result["scope_signature_verified"] = signature_verified
        return result

    scope = "|".join((
        "capability-scope",
        grant["authority_id"],
        grant["subject_id"],
        grant["tenant_id"],
        grant["workspace_id"],
        grant["domain"],
        grant["capability_id"],
    ))
    try:
        claimed = nonce_registry.claim(
            scope=scope,
            nonce=grant["nonce"],
            expires_at=grant["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("SCOPE_NONCE_REGISTRY_FAILURE", parent=parent)
        result["scope_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("SCOPE_NONCE_REPLAYED", parent=parent)
        result["scope_signature_verified"] = True
        return result

    return {
        "schema": RESULT_SCHEMA,
        "state": "SCOPE_VERIFIED",
        "blockers": [],
        "parent_authority_verified": True,
        "scope_signature_verified": True,
        "scope_binding_verified": True,
        "capability_registered": True,
        "capability_granted_by_parent": True,
        "domain_isolated": True,
        "tenant_isolated": True,
        "workspace_isolated": True,
        "namespace_verified": True,
        "role_allowed": True,
        "tool_scope_verified": True,
        "action_scope_verified": True,
        "budget_scope_verified": True,
        "capability_scope_verified": True,
        "authority_id": grant["authority_id"],
        "subject_id": grant["subject_id"],
        "tenant_id": grant["tenant_id"],
        "workspace_id": grant["workspace_id"],
        "domain": grant["domain"],
        "policy_id": grant["policy_id"],
        "namespace": grant["namespace"],
        "capability_id": cap_id,
        "allowed_tools": sorted(granted_tools),
        "allowed_actions": sorted(granted_actions),
        "max_cost_usd": float(max_cost),
        "actor_role": role,
        "requested_tool": requested_tool_clean,
        "requested_action": requested_action_clean,
        "execution_mode": capability.execution_mode if capability is not None else "READ_ONLY",
        "execution_allowed": False,
        "approval_implied": False,
        "permissions_expanded": False,
        "tool_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "real_trading_enabled": False,
        "parent_verification": parent,
    }
