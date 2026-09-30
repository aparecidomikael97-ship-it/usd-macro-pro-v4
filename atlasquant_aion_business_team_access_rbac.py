"""AION BUSINESS team access / RBAC V1.

Fail-closed administrative contracts for employee access to Business.
This layer reuses the existing authenticated AtlasQuant session and adds:
- individual membership records;
- fixed Business profiles;
- explicit tenant/client scope;
- strong-auth requirement;
- revocation planning;
- AION action decisions using the same permissions.

It does not create accounts, send invitations, mutate credentials, enable MFA,
change billing, contact clients, deploy, publish, or execute external actions.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_access_control import (
    ROLES as BASE_ROLES,
    has_permission,
    normalize_role,
    normalize_username,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_RBAC_V1"
VERSION = "1"
MAX_TENANTS_PER_MEMBER = 10

TEAM_PROFILES = (
    "BUSINESS_OWNER",
    "BUSINESS_MANAGER",
    "FINANCE",
    "SUPPORT",
    "MARKETING",
    "OPERATOR",
    "VIEWER",
)

PROFILE_PERMISSIONS = {
    "BUSINESS_OWNER": frozenset({
        "business:read",
        "team:read",
        "team:manage",
        "client:read",
        "client:manage",
        "finance:read",
        "finance:manage",
        "support:read",
        "support:manage",
        "marketing:read",
        "marketing:manage",
        "operations:read",
        "operations:manage",
        "integrations:read",
        "reports:read",
    }),
    "BUSINESS_MANAGER": frozenset({
        "business:read",
        "team:read",
        "client:read",
        "client:manage",
        "finance:read",
        "support:read",
        "support:manage",
        "marketing:read",
        "marketing:manage",
        "operations:read",
        "operations:manage",
        "integrations:read",
        "reports:read",
    }),
    "FINANCE": frozenset({
        "business:read",
        "client:read",
        "finance:read",
        "finance:manage",
        "reports:read",
    }),
    "SUPPORT": frozenset({
        "business:read",
        "client:read",
        "support:read",
        "support:manage",
        "operations:read",
        "reports:read",
    }),
    "MARKETING": frozenset({
        "business:read",
        "client:read",
        "marketing:read",
        "marketing:manage",
        "reports:read",
    }),
    "OPERATOR": frozenset({
        "business:read",
        "client:read",
        "support:read",
        "operations:read",
        "operations:manage",
        "integrations:read",
        "reports:read",
    }),
    "VIEWER": frozenset({
        "business:read",
        "client:read",
        "reports:read",
    }),
}

ACTION_PERMISSION = {
    "read_business": "business:read",
    "read_team": "team:read",
    "manage_team": "team:manage",
    "read_client": "client:read",
    "manage_client": "client:manage",
    "read_finance": "finance:read",
    "manage_finance": "finance:manage",
    "read_support": "support:read",
    "manage_support": "support:manage",
    "read_marketing": "marketing:read",
    "manage_marketing": "marketing:manage",
    "read_operations": "operations:read",
    "run_authorized_workflow": "operations:manage",
    "read_integrations": "integrations:read",
    "read_reports": "reports:read",
}

FORBIDDEN_CRITICAL_ACTIONS = frozenset({
    "manage_global_users",
    "read_admin_memory",
    "read_other_tenant",
    "change_secrets",
    "approve_cost",
    "charge_customer",
    "change_billing",
    "deploy_production",
    "merge_main",
    "activate_runtime",
    "expand_scope",
    "apply_quota",
    "publish_external",
    "real_trade",
})

_SAFE_TENANT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,119}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _session(access: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(access, Mapping):
        return {}
    raw = access.get("session")
    if isinstance(raw, Mapping):
        return dict(raw)
    if access.get("username") and access.get("role"):
        return dict(access)
    return {}


def _tenant_ids(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    out: list[str] = []
    for item in value:
        tenant = _clean(item, 120)
        if (
            tenant
            and _SAFE_TENANT_RE.fullmatch(tenant)
            and tenant not in out
        ):
            out.append(tenant)
        if len(out) > MAX_TENANTS_PER_MEMBER:
            break
    return out


def normalize_team_profile(value: Any) -> str:
    profile = _clean(value, 80).upper()
    return profile if profile in TEAM_PROFILES else ""


def membership_record(
    *,
    username: Any,
    profile: Any,
    tenant_ids: Any,
    active: Any = True,
    strong_auth_required: Any = True,
) -> dict[str, Any]:
    user = normalize_username(username)
    team_profile = normalize_team_profile(profile)
    tenants = _tenant_ids(tenant_ids)
    active_ok = type(active) is bool
    strong_ok = type(strong_auth_required) is bool
    ready = bool(
        user
        and team_profile
        and 1 <= len(tenants) <= MAX_TENANTS_PER_MEMBER
        and active_ok
        and strong_ok
    )
    payload = {
        "username": user,
        "profile": team_profile,
        "tenant_ids": sorted(tenants),
        "active": active if active_ok else False,
        "strong_auth_required": (
            strong_auth_required if strong_ok else True
        ),
    } if ready else {}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_MEMBERSHIP_VALID" if ready else "TEAM_MEMBERSHIP_INVALID",
        **payload,
        "permissions": (
            sorted(PROFILE_PERMISSIONS[team_profile]) if ready else []
        ),
        "membership_digest": _digest(payload) if payload else "",
        "account_created": False,
        "invitation_sent": False,
        "credential_changed": False,
        "executes_action": False,
    }


def prepare_team_invitation_plan(
    admin_access: Mapping[str, Any] | None,
    *,
    username: Any,
    profile: Any,
    tenant_ids: Any,
    expires_at: Any,
    strong_auth_required: Any = True,
) -> dict[str, Any]:
    session = _session(admin_access)
    actor = normalize_username(session.get("username"))
    actor_role = normalize_role(session.get("role"))
    member = membership_record(
        username=username,
        profile=profile,
        tenant_ids=tenant_ids,
        active=True,
        strong_auth_required=strong_auth_required,
    )
    expiry = _clean(expires_at, 80)

    admin_ok = bool(
        actor
        and actor_role == "ADMIN"
        and has_permission(session, "admin:manage_users")
    )
    owner_assignment_ok = bool(
        member.get("profile") != "BUSINESS_OWNER"
        or actor_role == "ADMIN"
    )
    ready = bool(
        admin_ok
        and member.get("state") == "TEAM_MEMBERSHIP_VALID"
        and owner_assignment_ok
        and expiry
    )

    payload = {
        "actor": actor,
        "username": member.get("username"),
        "profile": member.get("profile"),
        "tenant_ids": member.get("tenant_ids"),
        "expires_at": expiry,
        "strong_auth_required": member.get("strong_auth_required"),
        "membership_digest": member.get("membership_digest"),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_INVITATION_REVIEW_READY" if ready else "TEAM_INVITATION_BLOCKED",
        "actor": actor if admin_ok else "",
        "membership": member if ready else {},
        "expires_at": expiry if ready else "",
        "invitation_plan_digest": _digest(payload) if payload else "",
        "requires_individual_account": True,
        "requires_strong_auth": True,
        "shared_admin_login_allowed": False,
        "invitation_sent": False,
        "account_created": False,
        "membership_applied": False,
        "executes_action": False,
    }


def audit_team_registry(
    memberships: Sequence[Mapping[str, Any]] | None,
    *,
    known_tenant_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    rows = list(memberships or [])
    known = set(_tenant_ids(known_tenant_ids or []))
    blockers: list[str] = []
    normalized: list[dict[str, Any]] = []
    seen_users: set[str] = set()

    for index, raw in enumerate(rows, start=1):
        row = membership_record(
            username=_mapping(raw).get("username"),
            profile=_mapping(raw).get("profile"),
            tenant_ids=_mapping(raw).get("tenant_ids"),
            active=_mapping(raw).get("active", True),
            strong_auth_required=_mapping(raw).get(
                "strong_auth_required", True
            ),
        )
        if row.get("state") != "TEAM_MEMBERSHIP_VALID":
            blockers.append(f"row_{index}_invalid")
            continue
        username = str(row["username"])
        if username in seen_users:
            blockers.append(f"row_{index}_duplicate_username")
        seen_users.add(username)
        if known and not set(row["tenant_ids"]).issubset(known):
            blockers.append(f"row_{index}_unknown_tenant_scope")
        normalized.append(row)

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "TEAM_REGISTRY_INTEGRITY_VERIFIED"
            if not blockers
            else "TEAM_REGISTRY_INTEGRITY_BLOCKED"
        ),
        "integrity_verified": not blockers,
        "member_count": len(normalized),
        "memberships": normalized if not blockers else [],
        "blockers": blockers,
        "shared_admin_login_allowed": False,
        "automatic_permission_escalation": False,
        "executes_action": False,
    }


def team_access_decision(
    access: Mapping[str, Any] | None,
    membership: Mapping[str, Any] | None,
    *,
    tenant_id: Any,
    action: Any,
    strong_auth_verified: Any,
) -> dict[str, Any]:
    session = _session(access)
    username = normalize_username(session.get("username"))
    base_role = normalize_role(session.get("role"))
    row = _mapping(membership)
    action_key = _clean(action, 120).casefold()
    target_tenant = _clean(tenant_id, 120)

    if action_key in FORBIDDEN_CRITICAL_ACTIONS:
        return {
            "schema": SCHEMA,
            "allowed": False,
            "action": action_key,
            "reason": "CRITICAL_ACTION_REQUIRES_SEPARATE_GATE",
            "tenant_id": target_tenant,
            "executes_action": False,
        }

    required_permission = ACTION_PERMISSION.get(action_key, "")
    member_user = normalize_username(row.get("username"))
    profile = normalize_team_profile(row.get("profile"))
    tenants = _tenant_ids(row.get("tenant_ids"))
    active = row.get("active") is True
    strong_required = row.get("strong_auth_required") is True
    strong_verified = (
        type(strong_auth_verified) is bool
        and strong_auth_verified is True
    )
    digest = _clean(row.get("membership_digest"), 128).lower()

    expected = membership_record(
        username=member_user,
        profile=profile,
        tenant_ids=tenants,
        active=active,
        strong_auth_required=strong_required,
    )
    membership_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "TEAM_MEMBERSHIP_VALID"
        and digest
        and digest == expected.get("membership_digest")
    )
    gates = {
        "authenticated_base_session": bool(
            username and base_role in BASE_ROLES
        ),
        "membership_integrity": membership_ok,
        "session_matches_membership": bool(
            username and username == member_user
        ),
        "membership_active": active,
        "owner_requires_admin_identity": bool(
            profile != "BUSINESS_OWNER" or base_role == "ADMIN"
        ),
        "strong_auth_verified": bool(
            not strong_required or strong_verified
        ),
        "tenant_in_scope": bool(
            target_tenant and target_tenant in tenants
        ),
        "known_action": bool(required_permission),
        "profile_permission": bool(
            profile
            and required_permission
            and required_permission in PROFILE_PERMISSIONS[profile]
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    allowed = not blockers

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "allowed": allowed,
        "action": action_key,
        "required_permission": required_permission,
        "profile": profile if membership_ok else "",
        "tenant_id": target_tenant if target_tenant in tenants else "",
        "reason": "TEAM_ACTION_ALLOWED" if allowed else "TEAM_ACTION_BLOCKED",
        "gates": gates,
        "blockers": blockers,
        "aion_must_obey_same_decision": True,
        "cross_tenant_access": False,
        "automatic_permission_escalation": False,
        "billing_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def prepare_membership_revocation_plan(
    admin_access: Mapping[str, Any] | None,
    membership: Mapping[str, Any] | None,
    *,
    reason: Any,
) -> dict[str, Any]:
    session = _session(admin_access)
    actor = normalize_username(session.get("username"))
    actor_role = normalize_role(session.get("role"))
    row = _mapping(membership)
    target = normalize_username(row.get("username"))
    reason_text = _clean(reason, 300)
    admin_ok = bool(
        actor
        and actor_role == "ADMIN"
        and has_permission(session, "admin:manage_users")
    )
    membership_ok = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "TEAM_MEMBERSHIP_VALID"
        and target
    )
    ready = bool(admin_ok and membership_ok and reason_text)
    payload = {
        "actor": actor,
        "target": target,
        "membership_digest": _clean(
            row.get("membership_digest"), 128
        ),
        "reason": reason_text,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_REVOCATION_REVIEW_READY" if ready else "TEAM_REVOCATION_BLOCKED",
        "actor": actor if admin_ok else "",
        "target_username": target if membership_ok else "",
        "reason": reason_text if ready else "",
        "revocation_plan_digest": _digest(payload) if payload else "",
        "membership_revoked": False,
        "session_revoked": False,
        "account_disabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_TENANTS_PER_MEMBER",
    "TEAM_PROFILES",
    "PROFILE_PERMISSIONS",
    "ACTION_PERMISSION",
    "FORBIDDEN_CRITICAL_ACTIONS",
    "normalize_team_profile",
    "membership_record",
    "prepare_team_invitation_plan",
    "audit_team_registry",
    "team_access_decision",
    "prepare_membership_revocation_plan",
]
