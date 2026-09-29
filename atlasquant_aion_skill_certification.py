"""Offline certification gate for AION skills/plugins.

This module evaluates a manifest against the existing Capability Registry and
Tool Hub. It does not register, activate or execute a skill, connector or tool.
Certification is metadata only and never grants runtime authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence
import json
import re

from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
from atlasquant_aion_observability import redact_text
from atlasquant_aion_tool_hub import default_tool_hub, normalize_tool_hub

SCHEMA = "ATLASQUANT_AION_SKILL_CERTIFICATION_V1"
STATES = ("CANDIDATE", "TESTED", "CERTIFIED", "SUSPENDED", "REVOKED")
RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
COST_CLASSES = ("FREE", "PAID", "UNKNOWN")
_SAFE_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,95}$")
MAX_ITEMS = 40


def _clean(value: Any, limit: int = 180) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _identifier(value: Any) -> str:
    text = _clean(value, 96).lower()
    return text if _SAFE_ID.fullmatch(text) else ""


def _unique(values: Any, limit: int = MAX_ITEMS) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    out: list[str] = []
    for raw in list(values)[:limit * 2]:
        text = _clean(raw, 160)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def manifest_fingerprint(payload: Mapping[str, Any]) -> str:
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _contains_secret(value: Any) -> bool:
    raw = _clean(value, 4000)
    if not raw:
        return False
    return "[REDACTED]" in redact_text(raw)


def _verified_refs(refs: Sequence[str], verifier: Any) -> bool:
    if not refs or not callable(verifier):
        return False
    try:
        result = verifier(list(refs))
    except Exception:
        return False
    if not isinstance(result, Mapping) or _clean(result.get("state"), 40).upper() != "VERIFIED":
        return False
    bound = sorted(_unique(result.get("bound_refs")))
    return bound == sorted(refs)


def assess_skill_manifest(
    manifest: Mapping[str, Any] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    capability_registry: CapabilityRegistry | None = None,
    tool_hub: Mapping[str, Any] | None = None,
    test_evidence: Mapping[str, Any] | None = None,
    provenance_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
    review_approved: Any = False,
) -> dict[str, Any]:
    """Assess one manifest without activating it or widening permissions."""
    raw = dict(manifest or {})
    trusted = dict(trusted_context or {})
    registry = capability_registry or default_registry()
    hub = normalize_tool_hub(tool_hub or default_tool_hub())
    tools_by_id = {str(row.get("tool_id") or ""): row for row in hub["tools"]}

    skill_id = _identifier(raw.get("skill_id"))
    version = _clean(raw.get("version"), 80)
    tenant_scope = _clean(raw.get("tenant_scope"), 80).upper()
    workspace_ids = [_identifier(x) for x in _unique(raw.get("workspace_ids"))]
    capability_ids = [_identifier(x) for x in _unique(raw.get("capability_ids"))]
    tool_ids = [_identifier(x) for x in _unique(raw.get("tool_ids"))]
    requested_roles = [x.upper() for x in _unique(raw.get("allowed_roles"))]
    requested_scopes = _unique(raw.get("required_scopes"))
    provenance_refs = _unique(raw.get("provenance_refs"))
    secret_refs = _unique(raw.get("secret_refs"))

    network_raw = raw.get("network_required", False)
    side_effect_raw = raw.get("external_side_effects", False)
    approval_raw = raw.get("requires_human_approval", False)
    rollback_raw = raw.get("rollback_supported", False)
    bool_fields_valid = all(
        isinstance(value, bool)
        for value in (network_raw, side_effect_raw, approval_raw, rollback_raw)
    )
    network_required = network_raw is True
    external_side_effects = side_effect_raw is True
    requires_human_approval = approval_raw is True
    rollback_supported = rollback_raw is True

    cost_class = _clean(raw.get("cost_class"), 30).upper() or "UNKNOWN"
    declared_risk = _clean(raw.get("risk"), 30).upper() or "CRITICAL"
    trusted_tenant = _clean(trusted.get("tenant_id"), 120)
    trusted_workspace = _identifier(trusted.get("workspace_id"))

    blockers: list[str] = []
    warnings: list[str] = []
    capabilities = []

    if not skill_id or not version:
        blockers.append("IDENTITY_REQUIRED")
    if tenant_scope != "CURRENT_TENANT":
        blockers.append("TENANT_SCOPE_INVALID")
    if not trusted_tenant or not trusted_workspace:
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if not workspace_ids or trusted_workspace not in workspace_ids or any(not x for x in workspace_ids):
        blockers.append("WORKSPACE_SCOPE_INVALID")
    if not capability_ids or any(not x for x in capability_ids):
        blockers.append("CAPABILITY_REQUIRED")
    if not bool_fields_valid:
        blockers.append("BOOLEAN_FIELD_INVALID")
    if cost_class not in COST_CLASSES:
        blockers.append("COST_CLASS_INVALID")
    if declared_risk not in RISK_ORDER:
        blockers.append("RISK_INVALID")
    if any(_contains_secret(ref) for ref in secret_refs):
        blockers.append("RAW_SECRET_DETECTED")
    if any(not _identifier(ref) for ref in secret_refs):
        blockers.append("SECRET_REF_INVALID")

    common_roles: set[str] | None = None
    allowed_tools: set[str] = set()
    allowed_scopes: set[str] = set()
    max_risk = "LOW"
    for cid in capability_ids:
        item = registry.get(cid)
        if item is None:
            blockers.append("CAPABILITY_NOT_REGISTERED:" + cid)
            continue
        capabilities.append(item)
        roles = set(item.allowed_roles)
        common_roles = roles if common_roles is None else common_roles & roles
        allowed_tools.update(item.allowed_tools)
        if RISK_ORDER.get(item.risk, 3) > RISK_ORDER[max_risk]:
            max_risk = item.risk

    if capabilities and RISK_ORDER.get(declared_risk, 3) < RISK_ORDER[max_risk]:
        blockers.append("RISK_DOWNGRADE")
    common_roles = common_roles or set()
    if not requested_roles or not set(requested_roles).issubset(common_roles):
        blockers.append("ROLE_SCOPE_EXPANSION")

    for tool_id in tool_ids:
        tool = tools_by_id.get(tool_id)
        if tool is None:
            blockers.append("TOOL_NOT_REGISTERED:" + tool_id)
            continue
        if tool_id not in allowed_tools:
            blockers.append("TOOL_NOT_ALLOWED_BY_CAPABILITY:" + tool_id)
        tool_workspace = _identifier(tool.get("workspace_id"))
        if not tool_workspace or tool_workspace not in workspace_ids:
            blockers.append("TOOL_WORKSPACE_OUT_OF_SCOPE:" + tool_id)
        connector_id = _identifier(tool.get("connector_id")) if tool.get("connector_id") else ""
        if connector_id and not network_required:
            blockers.append("NETWORK_UNDERDECLARED:" + tool_id)
        allowed_scopes.update(str(x) for x in list(tool.get("required_scopes") or []))
        if tool.get("external_side_effects") is True and not external_side_effects:
            blockers.append("SIDE_EFFECT_UNDERDECLARED:" + tool_id)

    if requested_scopes and not set(requested_scopes).issubset(allowed_scopes):
        blockers.append("SCOPE_EXPANSION")
    if external_side_effects and not requires_human_approval:
        blockers.append("APPROVAL_REQUIRED_FOR_SIDE_EFFECTS")
    if cost_class == "PAID" and not requires_human_approval:
        blockers.append("APPROVAL_REQUIRED_FOR_PAID")
    if external_side_effects and not rollback_supported:
        warnings.append("ROLLBACK_NOT_SUPPORTED")

    tests = dict(test_evidence or {})
    tests_pass = _clean(tests.get("state"), 40).upper() == "PASS" and tests.get("passed") is True
    if not tests_pass:
        warnings.append("TEST_EVIDENCE_MISSING")
    provenance_ok = _verified_refs(provenance_refs, provenance_verifier)
    if not provenance_ok:
        warnings.append("PROVENANCE_UNVERIFIED")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    if blockers:
        state = "CANDIDATE"
    elif tests_pass and provenance_ok and review_approved is True:
        state = "CERTIFIED"
    elif tests_pass:
        state = "TESTED"
    else:
        state = "CANDIDATE"

    normalized = {
        "skill_id": skill_id,
        "version": version,
        "tenant_scope": tenant_scope,
        "bound_tenant_id": trusted_tenant,
        "bound_workspace_id": trusted_workspace,
        "workspace_ids": workspace_ids,
        "capability_ids": capability_ids,
        "tool_ids": tool_ids,
        "allowed_roles": requested_roles,
        "required_scopes": requested_scopes,
        "network_required": network_required,
        "external_side_effects": external_side_effects,
        "requires_human_approval": requires_human_approval,
        "rollback_supported": rollback_supported,
        "cost_class": cost_class,
        "risk": declared_risk,
        "provenance_refs": provenance_refs,
        "secret_refs": secret_refs,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "manifest": normalized,
        "fingerprint": manifest_fingerprint(normalized),
        "blockers": blockers,
        "warnings": warnings,
        "max_capability_risk": max_risk,
        "tests_pass": tests_pass,
        "provenance_verified": provenance_ok,
        "review_approved": review_approved is True,
        "activates_skill": False,
        "activates_connector": False,
        "executes_tool": False,
        "expands_permissions": False,
        "creates_entitlement": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


def transition_skill_certification(
    record: Mapping[str, Any] | None,
    *,
    action: Any,
    trusted_context: Mapping[str, Any] | None,
    approved: Any = False,
    reason: Any = "",
) -> dict[str, Any]:
    """Suspend or revoke a certification record without activating anything."""
    current = dict(record or {})
    trusted = dict(trusted_context or {})
    current_state = _clean(current.get("state"), 40).upper()
    action_norm = _clean(action, 40).upper()
    manifest = (
        dict(current.get("manifest"))
        if isinstance(current.get("manifest"), Mapping)
        else {}
    )
    fingerprint = _clean(current.get("fingerprint"), 128)
    trusted_tenant = _clean(trusted.get("tenant_id"), 120)
    trusted_workspace = _identifier(trusted.get("workspace_id"))
    trusted_role = _clean(trusted.get("role"), 40).upper()
    reason_text = _clean(reason, 500)

    blockers: list[str] = []
    if current.get("schema") != SCHEMA:
        blockers.append("CERTIFICATION_SCHEMA_INVALID")
    if current_state not in STATES:
        blockers.append("CERTIFICATION_STATE_INVALID")
    if not manifest or not fingerprint:
        blockers.append("CERTIFICATION_RECORD_INCOMPLETE")
    elif manifest_fingerprint(manifest) != fingerprint:
        blockers.append("CERTIFICATION_FINGERPRINT_MISMATCH")
    workspace_ids = [
        _identifier(x)
        for x in _unique(manifest.get("workspace_ids"))
    ]
    bound_tenant = _clean(manifest.get("bound_tenant_id"), 120)
    bound_workspace = _identifier(manifest.get("bound_workspace_id"))
    if (
        not trusted_tenant
        or not trusted_workspace
        or trusted_workspace not in workspace_ids
        or bound_tenant != trusted_tenant
        or bound_workspace != trusted_workspace
    ):
        blockers.append("TRUSTED_SCOPE_MISMATCH")
    if trusted_role != "ADMIN":
        blockers.append("ADMIN_REQUIRED")
    if approved is not True:
        blockers.append("EXPLICIT_APPROVAL_REQUIRED")
    if not reason_text:
        blockers.append("TRANSITION_REASON_REQUIRED")

    next_state = current_state if current_state in STATES else "CANDIDATE"
    if action_norm == "SUSPEND":
        if current_state != "CERTIFIED":
            blockers.append("INVALID_SUSPEND_TRANSITION")
        else:
            next_state = "SUSPENDED"
    elif action_norm == "REVOKE":
        if current_state not in {"CERTIFIED", "SUSPENDED"}:
            blockers.append("INVALID_REVOKE_TRANSITION")
        else:
            next_state = "REVOKED"
    else:
        blockers.append("TRANSITION_ACTION_INVALID")

    blockers = list(dict.fromkeys(blockers))
    applied = not blockers
    if not applied:
        next_state = current_state if current_state in STATES else "CANDIDATE"

    return {
        "schema": SCHEMA,
        "state": next_state,
        "previous_state": current_state,
        "transition_action": action_norm,
        "transition_reason": reason_text,
        "transition_applied": applied,
        "terminal": next_state == "REVOKED",
        "manifest": manifest,
        "fingerprint": fingerprint,
        "blockers": blockers,
        "activates_skill": False,
        "activates_connector": False,
        "executes_tool": False,
        "expands_permissions": False,
        "creates_entitlement": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "STATES",
    "assess_skill_manifest",
    "transition_skill_certification",
    "manifest_fingerprint",
]
