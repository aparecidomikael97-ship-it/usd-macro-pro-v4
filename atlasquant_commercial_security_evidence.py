"""Offline commercial security evidence for AtlasQuant.

These checks validate local security contracts only. They do not certify legal,
licensing, support, billing or public-launch readiness, and they never mutate
accounts, secrets, trading gates or network state.
"""
from __future__ import annotations

from typing import Any

from atlasquant_access_control import (
    AccessUser,
    ROLE_PERMISSIONS,
    credential_fingerprint,
    session_is_current,
)
from atlasquant_registry_admin import set_account_active
from atlasquant_account_change_audit import build_account_change_audit

SCHEMA="ATLASQUANT_COMMERCIAL_SECURITY_EVIDENCE_V1"
_STATIC_HASH="pbkdf2_sha256$200000$"+"00"*16+"$"+"00"*32


def sales_role_isolation_evidence()->bool:
    sales=set(ROLE_PERMISSIONS.get("SALES",frozenset()))
    admin=set(ROLE_PERMISSIONS.get("ADMIN",frozenset()))
    return bool(
        sales=={"app:read","sales:read"}
        and not any(str(x).startswith("admin:") for x in sales)
        and "admin:manage_users" in admin
    )


def account_revocation_evidence()->bool:
    name="security.audit"
    user=AccessUser(name,"SALES",_STATIC_HASH,True)
    session={
        "username":name,
        "role":"SALES",
        "credential_fingerprint":credential_fingerprint(user),
    }
    users={name:user}
    if not session_is_current(session,users):
        return False

    inactive=AccessUser(name,"SALES",_STATIC_HASH,False)
    changed_role=AccessUser(name,"USER",_STATIC_HASH,True)
    rotated=AccessUser(name,"SALES",_STATIC_HASH[:-2]+"11",True)
    return bool(
        not session_is_current(session,{name:inactive})
        and not session_is_current(session,{name:changed_role})
        and not session_is_current(session,{name:rotated})
    )


def account_admin_contract_evidence()->bool:
    admin=AccessUser("admin.audit","ADMIN",_STATIC_HASH,True)
    user=AccessUser("user.audit","USER",_STATIC_HASH,True)
    users={admin.username:admin,user.username:user}
    try:
        updated=set_account_active(users,user.username,False)
        ordinary_deactivation_ok=not bool(updated[user.username].active)
    except Exception:
        return False

    last_admin_protected=False
    try:
        set_account_active(users,admin.username,False)
    except ValueError:
        last_admin_protected=True
    except Exception:
        return False
    return bool(ordinary_deactivation_ok and last_admin_protected)


def audit_manifest_evidence()->bool:
    try:
        manifest=build_account_change_audit(
            actor="admin.audit",
            diff={
                "added":[],
                "changed":[{"username":"user.audit","fields":["active"]}],
                "destructive_removal_detected":False,
            },
            registry_json='{"users":{}}',
            generated_at="2026-01-01T00:00:00+00:00",
        )
    except Exception:
        return False
    digest=str(manifest.get("registry_sha256") or "")
    return bool(
        manifest.get("contains_password") is False
        and manifest.get("contains_password_hash") is False
        and manifest.get("automatic_apply") is False
        and len(digest)==64
    )


def collect_commercial_security_evidence()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "sales_role_isolated_ok":sales_role_isolation_evidence(),
        "account_revocation_ok":account_revocation_evidence(),
        "account_admin_ok":account_admin_contract_evidence(),
        "audit_manifest_ok":audit_manifest_evidence(),
        "external_legal_verified":False,
        "external_data_licensing_verified":False,
        "external_billing_verified":False,
    }
