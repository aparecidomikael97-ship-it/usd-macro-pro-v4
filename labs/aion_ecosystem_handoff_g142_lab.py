"""G142 LAB: proposed AION cross-workspace handoff; not a runtime authorization gate.

AION orchestrates Trader, Investimentos, Negocios and AION. This module
accepts UNTRUSTED routing hints only and NEVER reads information or authorizes
access, external effects, billing, market orders, enrollment or provider calls.

Authentication, tenant ACL, owner enrollment and external custody remain
unimplemented/independent; G122 real P0 checks remain RED by design.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

SCHEMA = "ATLASQUANT_AION_G142_ECOSYSTEM_HANDOFF_LAB_V1"
WORKSPACES = ("TRADER", "INVESTIMENTOS", "NEGOCIOS", "AION")
SCOPES = ("OWNER_PRIVATE", "SUBSCRIBER_PERSONAL", "BUSINESS_TENANT")
READ_ONLY_PLANS = frozenset({"EXPLAIN", "READ_SUMMARY", "PREPARE_DRAFT"})
ALLOWED_SCOPE = {
    "TRADER": frozenset({"OWNER_PRIVATE", "SUBSCRIBER_PERSONAL"}),
    "INVESTIMENTOS": frozenset({"OWNER_PRIVATE", "SUBSCRIBER_PERSONAL"}),
    "NEGOCIOS": frozenset({"OWNER_PRIVATE", "BUSINESS_TENANT"}),
    "AION": frozenset(SCOPES),
}
_SUBSCRIBER_NS = re.compile(r"tenant/[a-f0-9]{32}\Z")
_COMPANY_NS = re.compile(r"company/[a-z0-9][a-z0-9._-]{7,79}\Z")
_SELF_APPROVAL_KEYS = frozenset({
    "approved", "verified_owner", "can_execute", "admin", "permit",
    "external_authority", "trust_root", "p0_homologated",
})


def _token(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def _valid_namespace(scope: str, namespace: object) -> bool:
    if not isinstance(namespace, str):
        return False
    if scope == "OWNER_PRIVATE":
        return namespace == "owner/private"
    if scope == "SUBSCRIBER_PERSONAL":
        return bool(_SUBSCRIBER_NS.fullmatch(namespace))
    if scope == "BUSINESS_TENANT":
        return bool(_COMPANY_NS.fullmatch(namespace))
    return False


def assess_handoff(
    *,
    workspace: object,
    principal_scope: object,
    principal_namespace: object,
    target_namespace: object,
    request_kind: object = "READ_SUMMARY",
    caller_claims: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Plan an isolated, non-executing route from caller-supplied UNTRUSTED hints.

    The result is never an access decision; even eligible_for_planning=True
    does NOT grant read, memory access, tenant identity or provider permission.
    """
    area = _token(workspace)
    scope = _token(principal_scope)
    kind = _token(request_kind)
    blockers: list[str] = []
    if area not in WORKSPACES:
        blockers.append("UNKNOWN_WORKSPACE")
    if scope not in SCOPES:
        blockers.append("UNKNOWN_PRINCIPAL_SCOPE")
    if not _valid_namespace(scope, principal_namespace):
        blockers.append("UNVERIFIED_OR_INVALID_PRINCIPAL_NAMESPACE")
    if not _valid_namespace(scope, target_namespace):
        blockers.append("INVALID_TARGET_NAMESPACE")
    if (isinstance(principal_namespace, str) and
            isinstance(target_namespace, str) and
            principal_namespace != target_namespace):
        blockers.append("CROSS_SCOPE_OR_TENANT_HANDOFF_DENIED")
    if area in ALLOWED_SCOPE and scope not in ALLOWED_SCOPE[area]:
        blockers.append("WORKSPACE_NOT_AVAILABLE_FOR_SCOPE")
    if kind not in READ_ONLY_PLANS:
        blockers.append("NON_READ_ONLY_REQUEST_HARD_NO_GO")
    if isinstance(caller_claims, Mapping) and any(
        caller_claims.get(key) for key in _SELF_APPROVAL_KEYS
    ):
        blockers.append("CALLER_SELF_ATTESTATION_NOT_AUTHORITY")

    eligible = not blockers
    route = None
    if eligible:
        route = (
            "NEGOCIOS_OWNER_OVERVIEW_ONLY"
            if area == "NEGOCIOS" and scope == "OWNER_PRIVATE"
            else area
        )
    return {
        "schema": SCHEMA,
        "workspace": area,
        "principal_scope_hint": scope,
        "request_kind": kind,
        "route_candidate": route,
        "eligible_for_planning": eligible,
        "blockers": blockers,
        "trust_class": "UNTRUSTED_CALLER_HINTS",
        "identity_authenticated": False,
        "tenant_acl_verified": False,
        "data_read_authorized": False,
        "cross_tenant_access_authorized": False,
        "owner_memory_exposed": False,
        "client_memory_exposed": False,
        "external_action_authorized": False,
        "external_action_executed": False,
        "memory_written": False,
        "provider_called": False,
        "billing_authorized": False,
        "worker_enabled": False,
        "real_trade_enabled": False,
        "p0_homologated": 0,
        "hard_no_go": True,
        "status": "PAPER_ROUTE_ONLY_NEEDS_REAL_IDENTITY_ACL_AND_P0",
    }


def ecosystem_contract_snapshot() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "workspaces": list(WORKSPACES),
        "scope_matrix": {key: sorted(value) for key, value in ALLOWED_SCOPE.items()},
        "read_only_plan_kinds": sorted(READ_ONLY_PLANS),
        "owner_business_route": "NEGOCIOS_OWNER_OVERVIEW_ONLY",
        "subscriber_business_data_access": False,
        "business_tenant_private_trader_access": False,
        "owner_admin_memory_shared_with_clients": False,
        "external_action_authorized": False,
        "hard_no_go": True,
        "p0_homologated": 0,
    }
