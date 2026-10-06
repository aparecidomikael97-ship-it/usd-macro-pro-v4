"""AION Controlled Execution Handoff V1.

Canonical bridge between a governed orchestration decision and a
capability-specific executor.

Authority is verified by the existing V2.13 Ed25519 trust-root path. This
module does not accept caller-supplied "verified" booleans or generic verifier
callbacks as authority. The cryptographic verification consumes its durable
nonce exactly once, then the handoff stores only the resulting public
verification lineage.

A ready handoff does not execute anything and never authorizes merge, deploy,
publish, payments, secrets, policy changes, permission expansion or real
trading.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_authority_verifier import RESULT_SCHEMA as AUTHORITY_RESULT_SCHEMA
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry
from atlasquant_aion_trusted_authority_bridge import (
    SCHEMA as TRUSTED_AUTHORITY_SCHEMA,
    verify_and_build_trusted_authority_view,
)

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
TRUSTED_SCOPE_FIELDS = ("subject_id", "tenant_id", "domain", "policy_id")


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:100]:
        item = _text(raw, 500)
        if item and item not in out:
            out.append(item)
    return out


def _trusted_scope(raw: Mapping[str, Any] | None) -> tuple[dict[str, str], list[str]]:
    source = dict(raw or {})
    out = {field: _text(source.get(field), 160) for field in TRUSTED_SCOPE_FIELDS}
    blockers = [f"TRUSTED_SCOPE_REQUIRED:{field}" for field, value in out.items() if not value]
    return out, blockers


def _authority_view_is_exact(
    view: Mapping[str, Any],
    *,
    scope: Mapping[str, str],
    capability: str,
) -> list[str]:
    blockers: list[str] = []
    if view.get("schema") != TRUSTED_AUTHORITY_SCHEMA:
        blockers.append("TRUSTED_AUTHORITY_SCHEMA_MISMATCH")
    required_true = (
        "authority_available",
        "authority_verified",
        "authority_binding_configured",
        "trust_root_configured",
        "signature_verification_available",
        "signature_verified",
        "origin_authenticated",
        "execution_authority_granted",
    )
    for field in required_true:
        if view.get(field) is not True:
            blockers.append("TRUSTED_AUTHORITY_REQUIRED:" + field)
    required_false = (
        "execution_allowed",
        "approval_implied",
        "executes_action",
        "network_called",
        "private_key_used",
    )
    for field in required_false:
        if view.get(field) is not False:
            blockers.append("TRUSTED_AUTHORITY_UNSAFE:" + field)
    if view.get("state") != "VERIFIED" or list(view.get("blockers") or []):
        blockers.append("TRUSTED_AUTHORITY_NOT_VERIFIED")

    verification = view.get("verification")
    if not isinstance(verification, Mapping):
        return blockers + ["AUTHORITY_VERIFICATION_RECORD_REQUIRED"]
    if verification.get("schema") != AUTHORITY_RESULT_SCHEMA:
        blockers.append("AUTHORITY_VERIFICATION_SCHEMA_MISMATCH")
    for field in TRUSTED_SCOPE_FIELDS:
        if verification.get(field) != scope[field]:
            blockers.append("AUTHORITY_SCOPE_MISMATCH:" + field)
    caps = verification.get("capabilities")
    if not isinstance(caps, (list, tuple)) or capability not in {str(x).upper() for x in caps}:
        blockers.append("CAPABILITY_NOT_IN_SIGNED_AUTHORITY")
    for field in (
        "trust_root_configured", "signature_verified", "binding_verified",
        "nonce_registered", "authority_verified", "execution_authority_granted",
    ):
        if verification.get(field) is not True:
            blockers.append("AUTHORITY_VERIFICATION_REQUIRED:" + field)
    for field in ("execution_allowed", "approval_implied", "executes_action", "private_key_used"):
        if verification.get(field) is not False:
            blockers.append("AUTHORITY_VERIFICATION_UNSAFE:" + field)
    return list(dict.fromkeys(blockers))


def build_controlled_handoff(
    *,
    orchestration: Mapping[str, Any] | None,
    trusted_scope: Mapping[str, Any] | None,
    capability: str,
    execution_class: str,
    executor_id: str,
    authority_statement: Mapping[str, Any] | None,
    authority_signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    evidence_refs: Sequence[Any] | None = None,
    expected_input_digest: str = "",
) -> dict[str, Any]:
    orch = dict(orchestration or {})
    scope, blockers = _trusted_scope(trusted_scope)
    cap = _text(capability, 120).upper()
    klass = _text(execution_class, 80).upper()
    executor = _text(executor_id, 160)
    refs = _refs(evidence_refs)

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
    expected_digest = _text(expected_input_digest, 160)
    if not expected_digest.startswith("sha256:"):
        blockers.append("EXPECTED_INPUT_DIGEST_REQUIRED")

    if orch.get("external_action_executed") is not False:
        blockers.append("ORCHESTRATION_ALREADY_EXECUTED_ACTION")
    if orch.get("state") in {"BLOCKED", "SECURITY_BLOCK", "DENIED"}:
        blockers.append("ORCHESTRATION_NOT_ELIGIBLE")
    if orch.get("execution_allowed") is True:
        blockers.append("ORCHESTRATION_CANNOT_SELF_AUTHORIZE_EXECUTION")
    if orch.get("external_ai_direct_tool_control") is True:
        blockers.append("EXTERNAL_AI_DIRECT_TOOL_CONTROL_FORBIDDEN")

    authority_view: dict[str, Any]
    if blockers and any(x.startswith("TRUSTED_SCOPE_REQUIRED:") for x in blockers):
        authority_view = {"state": "BLOCKED", "blockers": ["TRUSTED_SCOPE_INVALID"]}
    else:
        try:
            authority_view = verify_and_build_trusted_authority_view(
                authority_statement,
                signature_b64=authority_signature_b64,
                trust_roots=trust_roots,
                nonce_registry=nonce_registry,
                now_ts=_text(now_ts, 80),
                expected_binding=scope,
            )
        except Exception:
            authority_view = {"state": "BLOCKED", "blockers": ["AUTHORITY_VERIFICATION_EXCEPTION"]}
    blockers.extend(_authority_view_is_exact(authority_view, scope=scope, capability=cap))

    verification = authority_view.get("verification")
    verification = dict(verification) if isinstance(verification, Mapping) else {}
    blockers = list(dict.fromkeys(blockers))
    material = {
        "schema": SCHEMA,
        "state": READY if not blockers else BLOCKED,
        "blockers": blockers,
        **scope,
        "capability": cap,
        "execution_class": klass,
        "executor_id": executor,
        "expected_input_digest": expected_digest,
        "evidence_refs": refs,
        "orchestration_ref": _text(
            orch.get("request_id")
            or (orch.get("task") or {}).get("task_id")
            or orch.get("trace_id"),
            160,
        ),
        "authority_id": _text(verification.get("authority_id"), 160),
        "authority_statement_id": _text(verification.get("statement_id"), 160),
        "authority_key_id": _text(verification.get("key_id"), 160),
        "authority_key_version": verification.get("key_version"),
        "authority_nonce_registered": verification.get("nonce_registered") is True,
        "authority_verification_digest": _digest(verification) if verification else "",
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
    outcome = row.get("state")
    if outcome not in {"CONFIRMED_SUCCESS", "CONFIRMED_TERMINAL_FAILURE", "OUTCOME_UNKNOWN"}:
        blockers.append("RECEIPT_STATE_INVALID")
    if row.get("attributed") is not True:
        blockers.append("RECEIPT_ATTRIBUTION_REQUIRED")
    if not _text(row.get("receipt_digest"), 160).startswith("sha256:"):
        blockers.append("RECEIPT_DIGEST_REQUIRED")
    if outcome == "CONFIRMED_SUCCESS":
        if not _text(row.get("output_digest"), 160).startswith("sha256:"):
            blockers.append("SUCCESS_OUTPUT_DIGEST_REQUIRED")
        if handoff.get("execution_class") in {"SANDBOX_CODE", "SANDBOX_TEST"}:
            if row.get("tests_verified") is not True:
                blockers.append("SUCCESS_TEST_VERIFICATION_REQUIRED")
            refs = row.get("test_receipts")
            if not isinstance(refs, (list, tuple)) or not refs:
                blockers.append("SUCCESS_TEST_RECEIPTS_REQUIRED")
    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "outcome": outcome if not blockers else "UNTRUSTED",
        "handoff_digest": handoff.get("handoff_digest"),
        "receipt_digest": _text(row.get("receipt_digest"), 160),
        "automatic_retry_allowed": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA", "READY", "BLOCKED", "NON_DELEGABLE", "ALLOWED_EXECUTION_CLASSES",
    "build_controlled_handoff", "verify_executor_receipt",
]
