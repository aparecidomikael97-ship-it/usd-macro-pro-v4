"""AION Controlled Execution Handoff V1.

Authority-free bridge between an already-governed orchestration decision and a
capability-specific executor. This module never invokes the executor. It only
builds a fail-closed, lineage-bound handoff envelope.

A ready handoff is not authorization to merge, deploy, publish, charge, trade,
change policy, read secrets, or mutate production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_CONTROLLED_EXECUTION_HANDOFF_V1"
READY = "READY_FOR_CAPABILITY_EXECUTOR"
BLOCKED = "BLOCKED"
NON_DELEGABLE = frozenset({
    "MERGE_MAIN", "DEPLOY_PRODUCTION", "WRITE_SECRET", "CHARGE_CUSTOMER",
    "REAL_TRADING", "CHANGE_POLICY", "EXPAND_PERMISSIONS", "DISABLE_SECURITY",
})
ALLOWED_EXECUTION_CLASSES = frozenset({
    "LOCAL_READ", "LOCAL_DRAFT", "SANDBOX_CODE", "SANDBOX_TEST",
})


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for raw in value[:100]:
        item = _text(raw, 500)
        if item and item not in out:
            out.append(item)
    return out


def build_controlled_handoff(
    *,
    orchestration: Mapping[str, Any] | None,
    trusted_scope: Mapping[str, Any] | None,
    capability: str,
    execution_class: str,
    executor_id: str,
    authority_evidence: Mapping[str, Any] | None,
    evidence_refs: Sequence[Any] | None = None,
    expected_input_digest: str = "",
) -> dict[str, Any]:
    orch = dict(orchestration or {})
    scope = dict(trusted_scope or {})
    authority = dict(authority_evidence or {})
    blockers: list[str] = []

    owner_id = _text(scope.get("owner_id"), 120)
    tenant_id = _text(scope.get("tenant_id"), 120)
    workspace_id = _text(scope.get("workspace_id"), 120)
    cap = _text(capability, 120).upper()
    klass = _text(execution_class, 80).upper()
    executor = _text(executor_id, 160)
    refs = _refs(evidence_refs)

    if not owner_id or not tenant_id or not workspace_id:
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if not cap:
        blockers.append("CAPABILITY_REQUIRED")
    if cap in NON_DELEGABLE:
        blockers.append("NON_DELEGABLE_CAPABILITY")
    if klass not in ALLOWED_EXECUTION_CLASSES:
        blockers.append("EXECUTION_CLASS_NOT_ALLOWED")
    if not executor:
        blockers.append("EXECUTOR_ID_REQUIRED")
    if not refs:
        blockers.append("EVIDENCE_REFS_REQUIRED")
    if not _text(expected_input_digest, 160).startswith("sha256:"):
        blockers.append("EXPECTED_INPUT_DIGEST_REQUIRED")

    if orch.get("external_action_executed") is not False:
        blockers.append("ORCHESTRATION_ALREADY_EXECUTED_ACTION")
    if orch.get("state") in {"BLOCKED", "SECURITY_BLOCK", "DENIED"}:
        blockers.append("ORCHESTRATION_NOT_ELIGIBLE")
    if orch.get("execution_allowed") is True:
        blockers.append("ORCHESTRATION_CANNOT_SELF_AUTHORIZE_EXECUTION")

    if authority.get("state") != "VERIFIED":
        blockers.append("AUTHORITY_EVIDENCE_NOT_VERIFIED")
    if authority.get("owner_id") != owner_id:
        blockers.append("AUTHORITY_OWNER_MISMATCH")
    if authority.get("tenant_id") != tenant_id:
        blockers.append("AUTHORITY_TENANT_MISMATCH")
    if authority.get("workspace_id") != workspace_id:
        blockers.append("AUTHORITY_WORKSPACE_MISMATCH")
    allowed_caps = authority.get("allowed_capabilities")
    if not isinstance(allowed_caps, (list, tuple)) or cap not in {str(x).upper() for x in allowed_caps}:
        blockers.append("CAPABILITY_NOT_IN_AUTHORITY_SCOPE")
    if authority.get("grants_root_authority") is True:
        blockers.append("ROOT_AUTHORITY_DELEGATION_FORBIDDEN")
    if authority.get("tool_output_is_authority") is True:
        blockers.append("TOOL_OUTPUT_AUTHORITY_FORBIDDEN")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "schema": SCHEMA,
        "state": READY if not blockers else BLOCKED,
        "blockers": blockers,
        "owner_id": owner_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "capability": cap,
        "execution_class": klass,
        "executor_id": executor,
        "expected_input_digest": _text(expected_input_digest, 160),
        "evidence_refs": refs,
        "orchestration_ref": _text(
            orch.get("request_id")
            or (orch.get("task") or {}).get("task_id")
            or orch.get("trace_id"),
            160,
        ),
        "authority_ref": _text(authority.get("authority_ref") or authority.get("decision_id"), 160),
        "executor_must_revalidate": True,
        "handoff_grants_authority": False,
        "external_ai_direct_tool_control": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "financial_action_allowed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }
    material["handoff_digest"] = _digest(material)
    return material


def verify_executor_receipt(
    handoff: Mapping[str, Any],
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(receipt or {})
    blockers: list[str] = []
    if handoff.get("schema") != SCHEMA or handoff.get("state") != READY:
        blockers.append("HANDOFF_NOT_READY")
    if row.get("handoff_digest") != handoff.get("handoff_digest"):
        blockers.append("RECEIPT_HANDOFF_MISMATCH")
    if row.get("executor_id") != handoff.get("executor_id"):
        blockers.append("RECEIPT_EXECUTOR_MISMATCH")
    if row.get("input_digest") != handoff.get("expected_input_digest"):
        blockers.append("RECEIPT_INPUT_MISMATCH")
    if row.get("state") not in {"CONFIRMED_SUCCESS", "CONFIRMED_TERMINAL_FAILURE", "OUTCOME_UNKNOWN"}:
        blockers.append("RECEIPT_STATE_INVALID")
    if row.get("attributed") is not True:
        blockers.append("RECEIPT_ATTRIBUTION_REQUIRED")
    if not _text(row.get("receipt_digest"), 160).startswith("sha256:"):
        blockers.append("RECEIPT_DIGEST_REQUIRED")
    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "outcome": row.get("state") if not blockers else "UNTRUSTED",
        "handoff_digest": handoff.get("handoff_digest"),
        "receipt_digest": _text(row.get("receipt_digest"), 160),
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA", "READY", "BLOCKED", "NON_DELEGABLE", "ALLOWED_EXECUTION_CLASSES",
    "build_controlled_handoff", "verify_executor_receipt",
]
