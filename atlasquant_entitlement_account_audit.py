"""Read-only AtlasQuant account × entitlement audit.

This module does not participate in authentication and never grants/revokes
access. It reconciles configured account records with provider-confirmed
entitlements so the administrator can spot commercial-access mismatches before
any future enforcement is enabled.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from atlasquant_access_control import AccessUser, normalize_username
from atlasquant_aion_entitlements import (
    entitlement_effective,
    normalize_entitlements,
)

SCHEMA="ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1"
DEFAULT_SCOPE="APP_ACCESS"
INTERNAL_ROLES=frozenset({"ADMIN","SALES"})


def _valid_users(users:Mapping[str,AccessUser]|None)->dict[str,AccessUser]:
    out={}
    if not isinstance(users,Mapping):
        return out
    for key,user in users.items():
        if not isinstance(user,AccessUser):
            continue
        name=normalize_username(key)
        if not name or name!=user.username:
            continue
        out[name]=user
    return out


def audit_account_entitlements(
    users:Mapping[str,AccessUser]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    scope:str=DEFAULT_SCOPE,
    now:datetime|None=None,
)->dict[str,Any]:
    """Build a non-enforcing reconciliation report.

    USER accounts are the only accounts expected to carry commercial access by
    default. SALES and ADMIN are internal roles and are explicitly exempt from
    this audit expectation.
    """
    accounts=_valid_users(users)
    rows=normalize_entitlements(entitlements)
    target_scope=str(scope or DEFAULT_SCOPE).strip().upper() or DEFAULT_SCOPE

    by_subject:dict[str,list[dict[str,Any]]]={}
    effective_ids=set()
    for item in rows:
        if str(item.get("scope") or "").upper()!=target_scope:
            continue
        subject=normalize_username(item.get("subject_ref"))
        if not subject:
            continue
        by_subject.setdefault(subject,[]).append(item)
        result=entitlement_effective(item,now=now)
        if result["effective"]:
            effective_ids.add(str(item.get("entitlement_id") or ""))

    account_rows=[]
    active_user_accounts=0
    effective_user_accounts=0
    missing_effective=0
    duplicate_effective=0

    for username,user in sorted(accounts.items()):
        matches=by_subject.get(username,[])
        effective_matches=[
            item for item in matches
            if str(item.get("entitlement_id") or "") in effective_ids
        ]

        if not user.active:
            state="ACCOUNT_INACTIVE"
        elif user.role in INTERNAL_ROLES:
            state="INTERNAL_ROLE_EXEMPT"
        else:
            active_user_accounts+=1
            if len(effective_matches)>1:
                state="DUPLICATE_EFFECTIVE_ENTITLEMENTS"
                duplicate_effective+=1
                effective_user_accounts+=1
            elif len(effective_matches)==1:
                state="ENTITLEMENT_EFFECTIVE"
                effective_user_accounts+=1
            else:
                state="NO_EFFECTIVE_ENTITLEMENT"
                missing_effective+=1

        account_rows.append({
            "username":username,
            "role":user.role,
            "account_active":bool(user.active),
            "scope":target_scope,
            "matching_entitlements":len(matches),
            "effective_entitlements":len(effective_matches),
            "state":state,
            "enforcement_applied":False,
            "account_changed":False,
            "role_changed":False,
        })

    orphan_rows=[]
    for item in rows:
        if str(item.get("scope") or "").upper()!=target_scope:
            continue
        result=entitlement_effective(item,now=now)
        if not result["effective"]:
            continue
        subject=normalize_username(item.get("subject_ref"))
        if subject and subject in accounts:
            continue
        orphan_rows.append({
            "entitlement_id":str(item.get("entitlement_id") or ""),
            "subject_ref":str(item.get("subject_ref") or ""),
            "scope":target_scope,
            "state":"ORPHAN_EFFECTIVE_ENTITLEMENT",
            "provider_confirmed":bool(
                (item.get("provider_evidence") or {}).get("confirmed",False)
            ),
        })

    return {
        "schema":SCHEMA,
        "scope":target_scope,
        "accounts_total":len(accounts),
        "active_user_accounts":active_user_accounts,
        "effective_user_accounts":effective_user_accounts,
        "user_accounts_without_effective_entitlement":missing_effective,
        "duplicate_effective_user_accounts":duplicate_effective,
        "orphan_effective_entitlements":len(orphan_rows),
        "account_rows":account_rows,
        "orphan_rows":orphan_rows,
        "enforcement_enabled":False,
        "authentication_changed":False,
        "automatic_provisioning":False,
        "automatic_revocation":False,
        "real_trading_changed":False,
    }


def audit_requires_review(report:Mapping[str,Any]|None)->bool:
    data=dict(report or {})
    return any(
        int(data.get(key) or 0)>0
        for key in (
            "user_accounts_without_effective_entitlement",
            "duplicate_effective_user_accounts",
            "orphan_effective_entitlements",
        )
    )


__all__=[
    "SCHEMA","DEFAULT_SCOPE","INTERNAL_ROLES",
    "audit_account_entitlements","audit_requires_review",
]
