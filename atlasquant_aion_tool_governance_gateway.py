"""AION Tool Governance Gateway P1.

Pure/offline composition gate over the existing Tool Hub, supply-chain,
sandbox, Guardian preflight and cumulative-authority budget evidence.

This module never calls a tool, connector, provider, network client, subprocess
or production runtime. READY_FOR_EXECUTOR is a bounded handoff state only; it is
not authorization and must be revalidated by the executor immediately before any
external boundary.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_portable import normalize_portable_core
from atlasquant_aion_tool_hub import plan_tool_call
from atlasquant_aion_tool_sandbox import sandbox_plan

SCHEMA = "ATLASQUANT_AION_TOOL_GOVERNANCE_GATEWAY_P1"
POLICY_VERSION = "p1-2026-10-05"

TRANSPORTS = ("LOCAL", "NATIVE", "API", "MCP", "FILE", "WEBHOOK")
SIDE_EFFECT_KINDS = frozenset({"WRITE", "PUBLISH", "FINANCIAL", "PRODUCTION", "SECRETS"})
CRITICAL_KINDS = frozenset({"FINANCIAL", "PRODUCTION", "SECRETS"})
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _clean(value: Any, limit: int = 320) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _token(value: Any) -> str:
    text = _clean(value, 128)
    return text if _SAFE_TOKEN.fullmatch(text) else ""


def _unique(values: Sequence[Any] | None, limit: int = 80) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[: max(1, limit * 2)]:
        item = _clean(raw, 180)
        if item and item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _clean(data.get("owner_id"), 120),
        "tenant_id": _clean(data.get("tenant_id"), 120),
        "workspace_id": _clean(data.get("workspace_id"), 120),
    }


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + sha256(raw.encode("utf-8")).hexdigest()


def _connector_protocol(
    connector_id: str,
    portable_core: Mapping[str, Any] | None,
) -> str:
    if not connector_id:
        return "LOCAL"
    core = normalize_portable_core(portable_core)
    row = next(
        (
            item
            for item in core["connectors"]
            if item.get("connector_id") == connector_id
        ),
        None,
    )
    return _clean((row or {}).get("protocol"), 30).upper()


def _budget_evidence(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, str],
    transaction_id: str,
    authority_budget_ref: str,
) -> dict[str, Any]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []

    if data.get("allowed") is not True:
        blockers.append("AUTHORITY_BUDGET_NOT_ALLOWED")
    if data.get("grants_authority") is not False:
        blockers.append("AUTHORITY_BUDGET_COMPONENT_UNSAFE")
    if data.get("executes_action") is not False:
        blockers.append("AUTHORITY_BUDGET_EXECUTION_UNSAFE")
    if _clean(data.get("transaction_id"), 128) != transaction_id:
        blockers.append("AUTHORITY_BUDGET_TRANSACTION_MISMATCH")
    if _clean(data.get("authority_budget_ref"), 128) != authority_budget_ref:
        blockers.append("AUTHORITY_BUDGET_REF_MISMATCH")
    if _scope(data.get("scope") if isinstance(data.get("scope"), Mapping) else {}) != trusted_scope:
        blockers.append("AUTHORITY_BUDGET_SCOPE_MISMATCH")
    if not _clean(data.get("policy_version"), 128):
        blockers.append("AUTHORITY_BUDGET_POLICY_VERSION_REQUIRED")
    if not _clean(data.get("policy_digest"), 180):
        blockers.append("AUTHORITY_BUDGET_POLICY_DIGEST_REQUIRED")

    return {
        "state": "VERIFIED" if not blockers else "BLOCK",
        "blockers": blockers,
        "authority_budget_ref": _clean(data.get("authority_budget_ref"), 128),
        "transaction_id": _clean(data.get("transaction_id"), 128),
        "policy_version": _clean(data.get("policy_version"), 128),
        "policy_digest": _clean(data.get("policy_digest"), 180),
        "grants_authority": False,
        "executes_action": False,
    }


def tool_governance_gateway(
    *,
    tool_id: Any,
    transport: Any,
    hub: Mapping[str, Any] | None,
    portable_core: Mapping[str, Any] | None,
    access: Mapping[str, Any] | None,
    trusted_scope: Mapping[str, Any] | None,
    trusted_granted_scopes: Sequence[Any] | None,
    transaction_id: Any,
    authority_budget_ref: Any = "",
    authority_budget_evidence: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: bool = False,
    approved: bool = False,
    approval_refs: Sequence[Any] | None = None,
    evidence_refs: Sequence[Any] | None = None,
    rollback_ref: Any = "",
    artifacts: Sequence[Any] | None = None,
    tests: Sequence[Mapping[str, Any]] | None = None,
    uncertainty_pct: Any = 100,
    impact: Any = "MEDIUM",
    reversible: bool = False,
) -> dict[str, Any]:
    """Compose an authority-free execution handoff preflight."""
    scope = _scope(trusted_scope)
    tx = _token(transaction_id)
    budget_ref = _token(authority_budget_ref)
    requested_transport = _clean(transport, 30).upper()
    approvals = _unique(approval_refs)
    evidence = _unique(evidence_refs)
    granted_scopes = set(_unique(trusted_granted_scopes))
    rollback = _clean(rollback_ref, 240)

    blockers: list[str] = []
    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if not tx:
        blockers.append("TRANSACTION_ID_INVALID")
    if requested_transport not in TRANSPORTS:
        blockers.append("TRANSPORT_UNSUPPORTED")

    preflight = plan_tool_call(
        tool_id,
        hub=hub,
        portable_core=portable_core,
        access=access,
        source_kind=source_kind,
        authenticated_admin=authenticated_admin is True,
        approved=approved is True,
        feature_flags=None,
        scope=f"{scope['tenant_id']}:{scope['workspace_id']}",
        artifacts=artifacts,
        tests=tests,
        rollback_plan=rollback,
        uncertainty_pct=uncertainty_pct,
        impact=impact,
        reversible=reversible is True,
    )

    if preflight.get("state") == "BLOCK":
        blockers.extend(str(x) for x in list(preflight.get("blockers") or [])[:100])
    if preflight.get("state") not in {"READY_FOR_EXECUTOR", "REVIEW"}:
        blockers.append("TOOL_HUB_PREFLIGHT_NOT_READY")

    tool = (
        dict(preflight.get("tool"))
        if isinstance(preflight.get("tool"), Mapping)
        else {}
    )
    tool_kind = _clean(tool.get("kind"), 30).upper()
    connector_id = _clean(tool.get("connector_id"), 96)
    tool_workspace = _clean(tool.get("workspace_id"), 120)
    required_scopes = set(_unique(tool.get("required_scopes")))

    if tool and tool_workspace != scope["workspace_id"]:
        blockers.append("TOOL_WORKSPACE_SCOPE_MISMATCH")
    missing_scopes = sorted(required_scopes - granted_scopes)
    if missing_scopes:
        blockers.extend(f"MISSING_SCOPE:{item}" for item in missing_scopes)

    expected_transport = _connector_protocol(connector_id, portable_core)
    if requested_transport in TRANSPORTS and expected_transport != requested_transport:
        blockers.append("TRANSPORT_CONNECTOR_MISMATCH")

    sandbox = sandbox_plan(tool) if tool else {
        "state": "BLOCK",
        "issues": ["TOOL_CONTRACT_MISSING"],
        "executes_action": False,
    }
    if sandbox.get("state") != "READY":
        blockers.extend(str(x) for x in list(sandbox.get("issues") or [])[:100])
        blockers.append("TOOL_SANDBOX_NOT_READY")

    has_side_effect = bool(
        tool.get("external_side_effects") is True or tool_kind in SIDE_EFFECT_KINDS
    )
    critical_kind = tool_kind in CRITICAL_KINDS

    budget = {
        "state": "NOT_REQUIRED",
        "blockers": [],
        "grants_authority": False,
        "executes_action": False,
    }

    if has_side_effect:
        if approved is not True:
            blockers.append("EXPLICIT_HUMAN_APPROVAL_REQUIRED")
        if not approvals:
            blockers.append("APPROVAL_REFERENCE_REQUIRED")
        if not evidence:
            blockers.append("EVIDENCE_REFERENCE_REQUIRED")
        if not rollback:
            blockers.append("ROLLBACK_OR_RECOVERY_REFERENCE_REQUIRED")
        if not budget_ref:
            blockers.append("AUTHORITY_BUDGET_REF_REQUIRED")
        budget = _budget_evidence(
            authority_budget_evidence,
            trusted_scope=scope,
            transaction_id=tx,
            authority_budget_ref=budget_ref,
        )
        if budget["state"] != "VERIFIED":
            blockers.extend(budget["blockers"])

    if critical_kind:
        if authenticated_admin is not True:
            blockers.append("CRITICAL_TOOL_ADMIN_REAUTH_REQUIRED")
        if len(approvals) < 1:
            blockers.append("CRITICAL_TOOL_APPROVAL_REQUIRED")

    if preflight.get("source_authority", {}).get("can_issue_action") is not True:
        blockers.append("SOURCE_AUTHORITY_REQUIRED")
    if preflight.get("proof_of_safety", {}).get("state") == "BLOCK":
        blockers.append("PROOF_OF_SAFETY_BLOCKED")
    if preflight.get("supply_chain", {}).get("state") != "VERIFIED":
        blockers.append("TOOL_SUPPLY_CHAIN_UNVERIFIED")
    if preflight.get("connector_called") is not False or preflight.get("tool_called") is not False:
        blockers.append("PREFLIGHT_SIDE_EFFECT_BOUNDARY_VIOLATED")

    blockers = list(dict.fromkeys(blockers))
    handoff_core = {
        "schema": SCHEMA,
        "policy_version": POLICY_VERSION,
        "transaction_id": tx,
        "tool_id": _clean(tool.get("tool_id") or tool_id, 96).lower(),
        "tool_kind": tool_kind,
        "transport": requested_transport,
        "connector_id": connector_id,
        "trusted_scope": scope,
        "required_scopes": sorted(required_scopes),
        "granted_scopes": sorted(granted_scopes),
        "tool_contract_hash": _clean(
            preflight.get("supply_chain", {}).get("contract_hash"), 180
        ),
        "sandbox_profile": _clean(sandbox.get("profile"), 80),
        "authority_budget_ref": budget_ref,
        "approval_refs": approvals,
        "evidence_refs": evidence,
        "rollback_ref": rollback,
        "side_effect": has_side_effect,
        "critical_kind": critical_kind,
    }
    handoff_digest = _digest(handoff_core)

    state = "BLOCK"
    if not blockers:
        state = "READY_FOR_EXECUTOR"

    return {
        **handoff_core,
        "state": state,
        "handoff_digest": handoff_digest,
        "tool_hub_preflight_state": _clean(preflight.get("state"), 60),
        "sandbox_state": _clean(sandbox.get("state"), 60),
        "authority_budget_state": _clean(budget.get("state"), 60),
        "blockers": blockers,
        "receipt_required": state == "READY_FOR_EXECUTOR",
        "executor_must_revalidate": True,
        "handoff_grants_authority": False,
        "tool_output_is_authority": False,
        "may_expand_permissions": False,
        "connector_called": False,
        "tool_called": False,
        "provider_called": False,
        "network_called": False,
        "subprocess_called": False,
        "production_mutation": False,
        "real_trading_enabled": False,
        "payment_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "POLICY_VERSION",
    "TRANSPORTS",
    "SIDE_EFFECT_KINDS",
    "CRITICAL_KINDS",
    "tool_governance_gateway",
]
