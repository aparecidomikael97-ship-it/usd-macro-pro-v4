"""AION V2.18 Constitution / Policy Kernel.

Versioned, deterministic policy in code. The kernel decides whether an intent may
progress to later execution gates. It never executes the intent itself.

Critical invariants:
- model/agent/memory/health are never authority;
- approval is distinct from execution;
- kill switch dominates sensitive actions;
- tenant/domain/cost/capability scope cannot be widened by the caller;
- policy changes are review-only and never mutate the running constitution.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_POLICY_KERNEL_V1"
POLICY_ID = "AION_CONSTITUTION_V1"
POLICY_VERSION = 1

_ACTION_RULES = {
    "DIAGNOSTIC_READ": {
        "risk": "LOW",
        "owner_approval_required": False,
        "allowed_postures": [
            "NORMAL_MONITORED",
            "DEGRADED_MONITORED",
            "DEGRADED_READ_ONLY",
            "STOPPED_BY_KILL_SWITCH",
        ],
        "durable_mode": "",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "DRAFT": {
        "risk": "LOW",
        "owner_approval_required": False,
        "allowed_postures": ["NORMAL_MONITORED", "DEGRADED_MONITORED", "DEGRADED_READ_ONLY"],
        "durable_mode": "",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "INTERNAL_WRITE": {
        "risk": "MEDIUM",
        "owner_approval_required": False,
        "allowed_postures": ["NORMAL_MONITORED", "DEGRADED_MONITORED"],
        "durable_mode": "LOCAL_SAFE",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "EXTERNAL_SIDE_EFFECT": {
        "risk": "HIGH",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "SEND_EXTERNAL_MESSAGE": {
        "risk": "HIGH",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "CRM_MUTATION": {
        "risk": "HIGH",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "PAYMENT": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "REAL_TRADING": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": True,
    },
    "MERGE_MAIN": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "DEPLOY_PRODUCTION": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "WRITE_SECRET": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
    "TENANT_DELETE": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "EXTERNAL_EFFECT",
        "privacy_review_required": True,
        "real_trading_flag_required": False,
    },
    "CHANGE_POLICY": {
        "risk": "CRITICAL",
        "owner_approval_required": True,
        "allowed_postures": ["NORMAL_MONITORED"],
        "durable_mode": "",
        "privacy_review_required": False,
        "real_trading_flag_required": False,
    },
}

_INVARIANTS = {
    "llm_is_authority": False,
    "memory_grants_permission": False,
    "health_implies_approval": False,
    "approval_implies_execution": False,
    "readiness_implies_execution": False,
    "capability_scope_can_expand_parent": False,
    "agent_can_self_approve": False,
    "agent_can_change_policy": False,
    "automatic_merge": False,
    "automatic_deploy": False,
    "automatic_payment": False,
    "automatic_real_trading": False,
    "automatic_secret_write": False,
    "automatic_tenant_delete": False,
    "automatic_kill_switch_mutation": False,
    "cross_tenant_implicit_access": False,
    "execution_allowed_by_policy_kernel": False,
}


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _exact_bool(value: Any, name: str) -> bool:
    if value is not True and value is not False:
        raise ValueError(f"{name} must be an exact boolean")
    return value is True


def _money(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _base_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "version": POLICY_VERSION,
        "invariants": deepcopy(_INVARIANTS),
        "action_rules": deepcopy(_ACTION_RULES),
        "owner_role": "HUMAN_OWNER",
        "critical_actions": sorted(
            action for action, rule in _ACTION_RULES.items()
            if rule["owner_approval_required"]
        ),
        "policy_change_mode": "REVIEW_ONLY",
        "policy_source": "VERSIONED_CODE",
    }


def constitution_manifest() -> dict[str, Any]:
    body = _base_manifest()
    body["policy_digest"] = _digest(body)
    return body


def assert_constitution_integrity(manifest: Mapping[str, Any]) -> str:
    if not isinstance(manifest, Mapping):
        raise ValueError("constitution manifest required")
    expected = constitution_manifest()
    if dict(manifest) != expected:
        raise ValueError("constitution manifest mismatch")
    return expected["policy_digest"]


def approval_binding(
    *,
    action: Any,
    tenant_id: Any,
    domain: Any,
    approver_role: Any,
    approved: Any,
    policy_digest: Any,
) -> dict[str, Any]:
    return {
        "action": _clean(action, 80).upper(),
        "tenant_id": _clean(tenant_id, 120),
        "domain": _clean(domain, 80).upper(),
        "approver_role": _clean(approver_role, 80).upper(),
        "approved": _exact_bool(approved, "approved"),
        "policy_digest": _clean(policy_digest, 96),
    }


def _approval_valid(
    approval: Mapping[str, Any] | None,
    *,
    action: str,
    tenant_id: str,
    domain: str,
    policy_digest: str,
) -> bool:
    if not isinstance(approval, Mapping):
        return False
    return (
        approval.get("approved") is True
        and _clean(approval.get("approver_role"), 80).upper() == "HUMAN_OWNER"
        and _clean(approval.get("action"), 80).upper() == action
        and _clean(approval.get("tenant_id"), 120) == tenant_id
        and _clean(approval.get("domain"), 80).upper() == domain
        and _clean(approval.get("policy_digest"), 96) == policy_digest
    )


def evaluate_policy_intent(
    *,
    action: Any,
    trusted_tenant_id: Any,
    trusted_domain: Any,
    authority_verification: Mapping[str, Any],
    capability_scope: Mapping[str, Any],
    operational_resilience: Mapping[str, Any],
    multiagent_governance: Mapping[str, Any],
    durable_execution: Mapping[str, Any] | None,
    approval: Mapping[str, Any] | None = None,
    requested_cost_usd: Any = 0.0,
    budget_remaining_usd: Any = 0.0,
    kill_switch_engaged: Any = False,
    privacy_review_verified: Any = False,
    real_trading_enabled: Any = False,
) -> dict[str, Any]:
    """Evaluate a policy intent without executing it.

    A positive result means only that the intent may progress to a later
    execution gate. It is not execution authority.
    """
    act = _clean(action, 80).upper()
    rule = _ACTION_RULES.get(act)
    if rule is None:
        return {
            "schema": SCHEMA,
            "policy_id": POLICY_ID,
            "policy_digest": constitution_manifest()["policy_digest"],
            "action": act,
            "state": "BLOCKED",
            "blockers": ["ACTION_NOT_IN_CONSTITUTION"],
            "policy_allows_progress": False,
            "execution_allowed": False,
            "executes_action": False,
        }

    tenant = _clean(trusted_tenant_id, 120)
    domain = _clean(trusted_domain, 80).upper()
    blockers: list[str] = []
    manifest = constitution_manifest()
    policy_digest = manifest["policy_digest"]

    kill = _exact_bool(kill_switch_engaged, "kill_switch_engaged")
    privacy_ok = _exact_bool(privacy_review_verified, "privacy_review_verified")
    trading_flag = _exact_bool(real_trading_enabled, "real_trading_enabled")
    requested_cost = _money(requested_cost_usd, "requested_cost_usd")
    budget_remaining = _money(budget_remaining_usd, "budget_remaining_usd")

    if not tenant:
        blockers.append("TRUSTED_TENANT_REQUIRED")
    if not domain:
        blockers.append("TRUSTED_DOMAIN_REQUIRED")

    auth = dict(authority_verification or {})
    if auth.get("state") != "VERIFIED" or auth.get("authority_verified") is not True:
        blockers.append("AUTHORITY_NOT_VERIFIED")

    scope = dict(capability_scope or {})
    if scope.get("state") != "SCOPE_VERIFIED" or scope.get("capability_scope_verified") is not True:
        blockers.append("CAPABILITY_SCOPE_NOT_VERIFIED")
    if tenant and _clean(scope.get("tenant_id"), 120) != tenant:
        blockers.append("CAPABILITY_TENANT_MISMATCH")
    if domain and _clean(scope.get("domain"), 80).upper() != domain:
        blockers.append("CAPABILITY_DOMAIN_MISMATCH")

    resilience = dict(operational_resilience or {})
    posture = _clean(resilience.get("posture"), 80).upper()
    allowed_postures = set(rule["allowed_postures"])
    if posture not in allowed_postures:
        blockers.append("OPERATIONAL_POSTURE_BLOCKED")

    if kill and act != "DIAGNOSTIC_READ":
        blockers.append("GLOBAL_KILL_SWITCH_ENGAGED")
    if resilience.get("kill_switch_engaged") is True and act != "DIAGNOSTIC_READ":
        blockers.append("GLOBAL_KILL_SWITCH_ENGAGED")

    governance = dict(multiagent_governance or {})
    if governance.get("state") != "WITHIN_GOVERNANCE":
        blockers.append("MULTIAGENT_GOVERNANCE_BLOCKED")
    if governance.get("execution_allowed") is not False:
        blockers.append("MULTIAGENT_GOVERNANCE_CONTRACT_INVALID")

    scope_cost = scope.get("max_cost_usd")
    try:
        scope_cost_limit = _money(scope_cost, "scope max_cost_usd")
    except ValueError:
        scope_cost_limit = 0.0
        blockers.append("CAPABILITY_COST_CEILING_INVALID")
    if requested_cost > scope_cost_limit:
        blockers.append("CAPABILITY_COST_CEILING_EXCEEDED")
    if requested_cost > budget_remaining:
        blockers.append("BUDGET_REMAINING_EXCEEDED")

    durable_mode = rule["durable_mode"]
    if durable_mode:
        durable = dict(durable_execution or {})
        if durable.get("state") != "PREPARED":
            blockers.append("DURABLE_EXECUTION_NOT_PREPARED")
        if _clean(durable.get("mode"), 40).upper() != durable_mode:
            blockers.append("DURABLE_EXECUTION_MODE_MISMATCH")
        if durable.get("executes_action") is not False:
            blockers.append("DURABLE_EXECUTION_CONTRACT_INVALID")

    approval_present = _approval_valid(
        approval,
        action=act,
        tenant_id=tenant,
        domain=domain,
        policy_digest=policy_digest,
    )
    if rule["owner_approval_required"] and not approval_present:
        blockers.append("OWNER_APPROVAL_REQUIRED")

    if rule["privacy_review_required"] and not privacy_ok:
        blockers.append("PRIVACY_REVIEW_REQUIRED")

    if rule["real_trading_flag_required"] and not trading_flag:
        blockers.append("REAL_TRADING_FLAG_NOT_ENABLED")

    unique = sorted(set(blockers))
    progress = not unique
    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_digest": policy_digest,
        "action": act,
        "risk": rule["risk"],
        "state": "POLICY_PERMITS_PROGRESS" if progress else "BLOCKED",
        "blockers": unique,
        "owner_approval_required": rule["owner_approval_required"],
        "owner_approval_present": approval_present,
        "privacy_review_required": rule["privacy_review_required"],
        "privacy_review_verified": privacy_ok,
        "real_trading_flag_required": rule["real_trading_flag_required"],
        "real_trading_flag_enabled": trading_flag,
        "requested_cost_usd": requested_cost,
        "budget_remaining_usd": budget_remaining,
        "capability_cost_ceiling_usd": scope_cost_limit,
        "operational_posture": posture,
        "policy_allows_progress": progress,
        "policy_is_execution_authority": False,
        "approval_implies_execution": False,
        "memory_grants_authority": False,
        "health_implies_approval": False,
        "execution_allowed": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "automatic_payment": False,
        "automatic_real_trading": False,
        "automatic_secret_write": False,
        "automatic_tenant_delete": False,
        "automatic_kill_switch_mutation": False,
        "tool_called": False,
        "provider_called": False,
        "executes_action": False,
    }


def propose_constitution_change(proposed_manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    """Prepare review evidence. Never changes the active constitution."""
    current = constitution_manifest()
    proposed = dict(proposed_manifest or {})
    proposed_digest = ""
    try:
        proposed_digest = _digest(proposed)
    except Exception:
        pass
    same = proposed == current
    return {
        "schema": SCHEMA,
        "state": "NO_CHANGE" if same else "OWNER_REVIEW_REQUIRED",
        "active_policy_id": POLICY_ID,
        "active_policy_version": POLICY_VERSION,
        "active_policy_digest": current["policy_digest"],
        "proposed_digest": proposed_digest,
        "proposal_matches_active": same,
        "policy_mutated": False,
        "automatic_policy_change": False,
        "execution_allowed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "POLICY_ID",
    "POLICY_VERSION",
    "constitution_manifest",
    "assert_constitution_integrity",
    "approval_binding",
    "evaluate_policy_intent",
    "propose_constitution_change",
]
