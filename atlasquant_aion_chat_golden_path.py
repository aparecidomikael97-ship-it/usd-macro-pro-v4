"""Verified read-only Golden Path for AION Chat.

This layer is intentionally narrow. It may execute only already-allowlisted
local READ/SEARCH tools after the existing chat preflight and Tool Hub checks.
It never calls providers, network connectors, subprocesses, write tools,
publishers, brokers, payment rails, or persistence adapters.

The produced receipt is informational proof of the local read execution. It is
not an approval, authority token, signature, persistence attestation, or Core
Freeze artifact.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_chat_surface import (
    build_chat_turn,
    conversation_identity_binding,
)
from atlasquant_aion_command_orchestrator import orchestrate_local_command
from atlasquant_aion_local_traceability import local_contract_fingerprint

SCHEMA = "ATLASQUANT_AION_CHAT_GOLDEN_PATH_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_CHAT_READ_RECEIPT_V1"
SAFE_READ_KINDS = frozenset({"READ", "SEARCH"})


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(payload: Any) -> str:
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _planned_tool_ids(turn: Mapping[str, Any]) -> list[str]:
    preview = _mapping(turn.get("local_tool_preview"))
    tool_ids = [
        _clean(item, 96)
        for item in list(preview.get("tool_ids") or [])
        if _clean(item, 96)
    ]
    if not tool_ids:
        single = _clean(preview.get("tool_id"), 96)
        if single:
            tool_ids = [single]
    return tool_ids


def _planned_kinds(turn: Mapping[str, Any]) -> list[str]:
    preview = _mapping(turn.get("local_tool_preview"))
    if str(preview.get("mode") or "").upper() == "MULTI_READ":
        plan = _mapping(preview.get("bundle_plan"))
        return [
            _clean(item, 24).upper()
            for item in list(plan.get("kinds") or [])
            if _clean(item, 24)
        ]
    kind = _clean(preview.get("kind"), 24).upper()
    return [kind] if kind else []


def verify_readonly_execution(
    turn: Mapping[str, Any],
    execution: Mapping[str, Any],
    *,
    hub: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify that a completed local execution matches the read-only plan."""
    blockers: list[str] = []
    preview = _mapping(turn.get("local_tool_preview"))
    planned_ids = _planned_tool_ids(turn)
    planned_kinds = _planned_kinds(turn)
    results = _rows(execution.get("tool_results"))
    executed_ids = [_clean(item.get("tool_id"), 96) for item in results]
    expected_contract = local_contract_fingerprint(hub)
    turn_context = _mapping(turn.get("context"))
    expected_binding = conversation_identity_binding(
        turn_context,
        turn.get("conversation_id"),
    )
    actual_binding = _mapping(turn.get("identity_binding"))
    actual_binding_digest = _clean(turn.get("identity_binding_digest"), 64)
    turn_id = _clean(turn.get("turn_id"), 80)

    if expected_binding.get("complete") is not True:
        blockers.append("IDENTITY_BINDING_INCOMPLETE")
    if turn.get("identity_binding_complete") is not True:
        blockers.append("TURN_IDENTITY_BINDING_NOT_COMPLETE")
    if actual_binding.get("complete") is not True:
        blockers.append("IDENTITY_BINDING_OBJECT_NOT_COMPLETE")
    if actual_binding_digest != str(expected_binding.get("binding_digest") or ""):
        blockers.append("IDENTITY_BINDING_DIGEST_MISMATCH")
    if _clean(actual_binding.get("binding_digest"), 64) != actual_binding_digest:
        blockers.append("IDENTITY_BINDING_OBJECT_MISMATCH")

    if str(turn.get("state") or "") != "PLANNED":
        blockers.append("CHAT_TURN_NOT_PLANNED")
    if str(preview.get("state") or "") not in {"PLANNED", "PLANNED_MULTI"}:
        blockers.append("LOCAL_PREVIEW_NOT_PLANNED")
    if not planned_ids:
        blockers.append("NO_PLANNED_LOCAL_TOOL")
    if not planned_kinds or any(kind not in SAFE_READ_KINDS for kind in planned_kinds):
        blockers.append("NON_READ_TOOL_PLANNED")
    if execution.get("state") != "SUCCESS":
        blockers.append("EXECUTION_NOT_SUCCESS")
    if execution.get("executor_invoked") is not True:
        blockers.append("EXECUTOR_NOT_INVOKED")
    if execution.get("external_action_executed") is not False:
        blockers.append("EXTERNAL_ACTION_FLAG_NOT_FALSE")
    if execution.get("real_orders_enabled") is not False:
        blockers.append("REAL_ORDERS_FLAG_NOT_FALSE")
    if execution.get("tool_output_is_authority") is not False:
        blockers.append("TOOL_OUTPUT_AUTHORITY_FLAG_NOT_FALSE")
    if not results:
        blockers.append("NO_EXECUTION_RESULTS")
    if planned_ids != executed_ids:
        blockers.append("EXECUTED_TOOLS_DO_NOT_MATCH_PLAN")

    for index, item in enumerate(results):
        prefix = f"RESULT_{index + 1}:"
        request_id = _clean(item.get("request_id"), 120)
        if not turn_id or (
            request_id != turn_id
            and not request_id.startswith(turn_id + ":")
        ):
            blockers.append(prefix + "REQUEST_ID_NOT_BOUND_TO_TURN")
        if item.get("state") != "SUCCESS":
            blockers.append(prefix + "NOT_SUCCESS")
        if _clean(item.get("kind"), 24).upper() not in SAFE_READ_KINDS:
            blockers.append(prefix + "NON_READ_KIND")
        preflight = _mapping(item.get("preflight"))
        if preflight.get("state") != "READY_FOR_EXECUTOR":
            blockers.append(prefix + "PREFLIGHT_NOT_READY")
        if list(preflight.get("blockers") or []):
            blockers.append(prefix + "PREFLIGHT_HAS_BLOCKERS")
        if _clean(item.get("contract_fingerprint"), 80) != expected_contract:
            blockers.append(prefix + "CONTRACT_FINGERPRINT_MISMATCH")
        provenance = _mapping(item.get("provenance"))
        if provenance.get("local_only") is not True:
            blockers.append(prefix + "PROVENANCE_NOT_LOCAL")
        security = _mapping(item.get("security"))
        for key in (
            "network_called",
            "connector_called",
            "external_side_effects",
            "permissions_expanded",
            "secrets_included",
        ):
            if security.get(key) is not False:
                blockers.append(prefix + key.upper() + "_NOT_FALSE")
        if item.get("executes_action") is not False:
            blockers.append(prefix + "EXECUTES_ACTION_NOT_FALSE")
        if item.get("external_action_executed") is not False:
            blockers.append(prefix + "EXTERNAL_ACTION_NOT_FALSE")
        if item.get("real_orders_enabled") is not False:
            blockers.append(prefix + "REAL_ORDERS_NOT_FALSE")
        if item.get("tool_output_is_authority") is not False:
            blockers.append(prefix + "TOOL_OUTPUT_AUTHORITY_NOT_FALSE")

    traceability = _mapping(execution.get("traceability"))
    if traceability and str(traceability.get("state") or "") == "SECURITY_BLOCK":
        blockers.append("TRACEABILITY_SECURITY_BLOCK")
    if traceability.get("tool_output_is_authority") is True:
        blockers.append("TRACEABILITY_CLAIMS_AUTHORITY")

    blockers = list(dict.fromkeys(blockers))
    return {
        "state": "VERIFIED" if not blockers else "FAILED_SAFE",
        "verified": not blockers,
        "blockers": blockers,
        "planned_tool_ids": planned_ids,
        "executed_tool_ids": executed_ids,
        "planned_kinds": planned_kinds,
        "contract_fingerprint": expected_contract,
        "identity_binding_digest": actual_binding_digest,
        "identity_binding_complete": expected_binding.get("complete") is True,
        "verification_scope": "STRUCTURAL_LOCAL_READ_EXECUTION",
        "semantic_truth_verified": False,
        "executes_action": False,
        "grants_authority": False,
    }


def _receipt(
    turn: Mapping[str, Any],
    execution: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    tool_results = _rows(execution.get("tool_results"))
    truth = []
    for item in tool_results:
        view = _mapping(item.get("truth"))
        truth.append({
            "tool_id": _clean(item.get("tool_id"), 96),
            "status": _clean(view.get("status"), 40) or "UNKNOWN",
            "freshness": _clean(view.get("freshness"), 40) or "UNVERIFIED",
        })
    traceability = _mapping(execution.get("traceability"))
    material = {
        "schema": RECEIPT_SCHEMA,
        "conversation_id": _clean(turn.get("conversation_id"), 120),
        "identity_binding_digest": _clean(turn.get("identity_binding_digest"), 64),
        "turn_id": _clean(turn.get("turn_id"), 80),
        "message_digest": _clean(turn.get("message_digest"), 64),
        "tool_ids": list(verification.get("executed_tool_ids") or []),
        "contract_fingerprint": _clean(verification.get("contract_fingerprint"), 80),
        "execution_digest": _digest({
            "tool_results": tool_results,
            "synthesis": execution.get("synthesis"),
            "traceability": traceability,
        }),
        "summary": _clean(execution.get("summary"), 1600),
        "truth": truth,
        "verification_scope": "STRUCTURAL_LOCAL_READ_EXECUTION",
        "semantic_truth_verified": False,
        "local_only": True,
        "read_only": True,
        "authorization": "NONE",
        "approval_used": False,
        "grants_authority": False,
        "network_called": False,
        "provider_called": False,
        "connector_called": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "persisted_externally": False,
        "memory_written": False,
        "learning_promoted": False,
        "executes_action": False,
    }
    receipt_id = "AION-CHAT-RCPT-" + _digest(material)[:24].upper()
    sealed = {**material, "receipt_id": receipt_id}
    sealed["receipt_digest"] = _digest(sealed)
    return sealed


def _update_path(
    turn: Mapping[str, Any],
    *,
    execution_state: str,
    verification_state: str,
    receipt_state: str,
    outcome_state: str,
) -> list[dict[str, Any]]:
    rows = _rows(turn.get("golden_path"))
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        stage = str(item.get("stage") or "")
        if stage == "EXECUTION":
            item["state"] = execution_state
        elif stage == "VERIFICATION":
            item["state"] = verification_state
        elif stage == "RECEIPT":
            item["state"] = receipt_state
        elif stage == "OUTCOME":
            item["state"] = outcome_state
        elif stage == "MEMORY_LESSON":
            item["state"] = "NOT_PROMOTED"
        item["executes_action"] = False
        out.append(item)
    return out


def _blocked(
    turn: Mapping[str, Any],
    *,
    reason: str,
    blockers: Sequence[Any] | None = None,
    execution: Mapping[str, Any] | None = None,
    verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED" if execution is None else "FAILED_SAFE",
        "reason": reason,
        "conversation_id": _clean(turn.get("conversation_id"), 120),
        "identity_binding_digest": _clean(turn.get("identity_binding_digest"), 64),
        "identity_binding_complete": turn.get("identity_binding_complete") is True,
        "turn_id": _clean(turn.get("turn_id"), 80),
        "turn": dict(turn),
        "execution": dict(execution or {}),
        "verification": dict(verification or {}),
        "blockers": [_clean(item, 160) for item in list(blockers or []) if _clean(item, 160)],
        "receipt": {},
        "receipt_created": False,
        "golden_path": _update_path(
            turn,
            execution_state="NOT_STARTED" if execution is None else "FAILED_SAFE",
            verification_state="NOT_STARTED" if execution is None else "FAILED_SAFE",
            receipt_state="NOT_CREATED",
            outcome_state="NOT_RECORDED",
        ),
        "may_execute_external_action": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "provider_called": False,
        "network_called": False,
        "automatic_memory_write": False,
        "automatic_learning_change": False,
        "persisted_externally": False,
    }


def execute_readonly_golden_path(
    message: Any,
    *,
    context: Mapping[str, Any] | None = None,
    runtime_context: Mapping[str, Any] | None = None,
    access: Mapping[str, Any] | None = None,
    attachments: Sequence[Mapping[str, Any]] | None = None,
    conversation_id: Any = "",
    turn_index: int = 0,
    feature_flags: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: bool = False,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one verified local read path from a chat turn.

    This function deliberately has no `approved` argument. READ/SEARCH handlers
    run with the existing command orchestrator's approval=False behavior. Any
    sensitive or write-shaped request remains outside this path.
    """
    turn = build_chat_turn(
        message,
        context=context,
        attachments=attachments,
        conversation_id=conversation_id,
        turn_index=turn_index,
        feature_flags=feature_flags,
    )
    if turn.get("state") != "PLANNED":
        return _blocked(
            turn,
            reason="CHAT_PREFLIGHT_NOT_EXECUTABLE",
            blockers=[turn.get("reason") or turn.get("state") or "UNKNOWN"],
        )
    if authenticated_admin is not True:
        return _blocked(
            turn,
            reason="AUTHENTICATED_ADMIN_REQUIRED_FOR_V1",
            blockers=["AUTHENTICATED_ADMIN_REQUIRED"],
        )
    if turn.get("identity_binding_complete") is not True:
        return _blocked(
            turn,
            reason="IDENTITY_BINDING_INCOMPLETE",
            blockers=["TENANT_WORKSPACE_ACTOR_BINDING_REQUIRED"],
        )

    preview = _mapping(turn.get("local_tool_preview"))
    tool_ids = _planned_tool_ids(turn)
    kinds = _planned_kinds(turn)
    if str(preview.get("state") or "") not in {"PLANNED", "PLANNED_MULTI"}:
        return _blocked(
            turn,
            reason="NO_SAFE_LOCAL_READ_PLAN",
            blockers=[preview.get("state") or "NO_LOCAL_PLAN"],
        )
    if not tool_ids or not kinds or any(kind not in SAFE_READ_KINDS for kind in kinds):
        return _blocked(
            turn,
            reason="READ_ONLY_BOUNDARY_REJECTED",
            blockers=["NON_READ_OR_UNRESOLVED_TOOL"],
        )

    execution = orchestrate_local_command(
        message,
        execute=True,
        runtime_context=runtime_context,
        hub=hub,
        portable_core=portable_core,
        access=access,
        feature_flags=feature_flags,
        source_kind=source_kind,
        authenticated_admin=True,
        request_id=_clean(turn.get("turn_id"), 80),
    )
    verification = verify_readonly_execution(turn, execution, hub=hub)
    if verification.get("verified") is not True:
        return _blocked(
            turn,
            reason="LOCAL_READ_VERIFICATION_FAILED",
            blockers=verification.get("blockers"),
            execution=execution,
            verification=verification,
        )

    receipt = _receipt(turn, execution, verification)
    return {
        "schema": SCHEMA,
        "state": "CONFIRMED_SUCCESS",
        "reason": "VERIFIED_LOCAL_READ_COMPLETED",
        "conversation_id": _clean(turn.get("conversation_id"), 120),
        "identity_binding_digest": _clean(turn.get("identity_binding_digest"), 64),
        "identity_binding_complete": turn.get("identity_binding_complete") is True,
        "turn_id": _clean(turn.get("turn_id"), 80),
        "turn": dict(turn),
        "execution": dict(execution),
        "verification": verification,
        "receipt": receipt,
        "receipt_created": True,
        "golden_path": _update_path(
            turn,
            execution_state="CONFIRMED_LOCAL_READ",
            verification_state="VERIFIED",
            receipt_state="CREATED_INFORMATIONAL",
            outcome_state="OBSERVED_NOT_PERSISTED",
        ),
        "response": execution.get("executive_response") or execution.get("summary") or "",
        "may_execute_external_action": False,
        "execution_authorized": False,
        "external_action_executed": False,
        "provider_called": False,
        "network_called": False,
        "automatic_memory_write": False,
        "automatic_learning_change": False,
        "persisted_externally": False,
    }


__all__ = [
    "SCHEMA",
    "RECEIPT_SCHEMA",
    "SAFE_READ_KINDS",
    "verify_readonly_execution",
    "execute_readonly_golden_path",
]
