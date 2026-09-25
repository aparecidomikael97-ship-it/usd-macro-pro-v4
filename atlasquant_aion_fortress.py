"""AION Fortress & Sovereignty contracts.

Deterministic security layer that sits outside model output. It treats content
from websites, tools, documents, email and external models as data, never as
authority. It combines source authority, Guardian authorization, autonomy
budgeting and a Proof-of-Safety preflight.

This module does not execute tools, mutate permissions, deploy, publish, charge,
delete files, disable security software or place trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_core import guardian_decision

SCHEMA = "ATLASQUANT_AION_FORTRESS_SOVEREIGNTY_V1"

SOURCE_KINDS = (
    "SYSTEM_POLICY",
    "ADMIN",
    "CHECKPOINT",
    "INTERNAL_MEMORY",
    "TOOL_OUTPUT",
    "WEB",
    "DOCUMENT",
    "EMAIL",
    "EXTERNAL_AI",
    "UNKNOWN",
)
UNTRUSTED_CONTENT_SOURCES = {
    "TOOL_OUTPUT",
    "WEB",
    "DOCUMENT",
    "EMAIL",
    "EXTERNAL_AI",
    "UNKNOWN",
}
IMPACT_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
AUTONOMY_MODES = (
    "READ_ONLY",
    "ADVISE",
    "DRAFT_ONLY",
    "REVERSIBLE_WITH_APPROVAL",
    "ADMIN_REQUIRED",
    "BLOCKED",
)
SENSITIVE_RISKS = {"WRITE", "PUBLISH", "FINANCIAL", "PRODUCTION", "SECRETS", "REAL_TRADING"}
CRITICAL_SIGNAL_KINDS = {
    "MALWARE",
    "RANSOMWARE",
    "SECRET_EXPOSURE",
    "SUPPLY_CHAIN",
    "PROMPT_INJECTION",
    "TOOL_INJECTION",
    "NETWORK_ANOMALY",
    "PRIVILEGE_ESCALATION",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else float(default)
    except Exception:
        return float(default)


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return prefix + "-" + sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def normalize_source_kind(value: Any) -> str:
    kind = _upper(value)
    return kind if kind in SOURCE_KINDS else "UNKNOWN"


def source_authority(
    source_kind: Any,
    *,
    authenticated_admin: bool = False,
    signed_system_policy: bool = False,
) -> dict[str, Any]:
    """Classify whether an origin may issue an instruction.

    Content sources can still be useful evidence, but never become controllers.
    """
    kind = normalize_source_kind(source_kind)
    if kind == "SYSTEM_POLICY" and signed_system_policy:
        authority = "POLICY"
        can_issue_action = True
        reason = "Política de sistema autenticada pode impor limites, nunca ampliar permissões do modelo."
    elif kind == "ADMIN" and authenticated_admin:
        authority = "ADMIN"
        can_issue_action = True
        reason = "Intenção veio de sessão ADMIN autenticada; ações sensíveis ainda dependem do Guardian."
    elif kind in {"CHECKPOINT", "INTERNAL_MEMORY"}:
        authority = "EVIDENCE"
        can_issue_action = False
        reason = "Memória/checkpoint é contexto auditável, não autorização de ação por si só."
    else:
        authority = "UNTRUSTED_CONTENT"
        can_issue_action = False
        reason = "Conteúdo externo é dado não confiável e não pode comandar o AION."

    return {
        "schema": SCHEMA,
        "source_kind": kind,
        "authority": authority,
        "can_issue_action": can_issue_action,
        "may_be_used_as_evidence": True,
        "may_override_policy": False,
        "may_expand_permissions": False,
        "reason": reason,
        "executes_action": False,
    }


def instruction_boundary(
    source_kind: Any,
    *,
    authenticated_admin: bool = False,
    signed_system_policy: bool = False,
    contains_action_instruction: bool = True,
) -> dict[str, Any]:
    """Fail closed when untrusted content contains instructions.

    Detection is not the security boundary: even undetected external commands
    still lack authority because source classification is authoritative.
    """
    authority = source_authority(
        source_kind,
        authenticated_admin=authenticated_admin,
        signed_system_policy=signed_system_policy,
    )
    instruction = bool(contains_action_instruction)
    blocked = bool(instruction and not authority["can_issue_action"])
    return {
        "schema": SCHEMA,
        "state": "BLOCK_INSTRUCTION" if blocked else "ALLOW_AS_CONTEXT",
        "instruction_present": instruction,
        "instruction_authorized": bool(instruction and authority["can_issue_action"]),
        "content_may_be_read": True,
        "content_may_be_evidence": True,
        "content_may_control_tools": bool(instruction and authority["can_issue_action"]),
        "source_authority": authority,
        "prompt_injection_resistant_by_source_boundary": True,
        "executes_action": False,
    }


def autonomy_budget(
    *,
    guardian_risk: Any,
    uncertainty_pct: Any = 100,
    impact: Any = "MEDIUM",
    reversible: bool = False,
    external_side_effects: bool = False,
) -> dict[str, Any]:
    """Compute a conservative autonomy lane; it never grants tool permission."""
    risk = _upper(guardian_risk) or "UNKNOWN"
    impact_norm = _upper(impact)
    if impact_norm not in IMPACT_LEVELS:
        impact_norm = "MEDIUM"
    uncertainty = max(0.0, min(100.0, _finite(uncertainty_pct, 100.0)))

    penalty = 0
    penalty += {
        "READ": 0,
        "DRAFT": 10,
        "WRITE": 30,
        "PUBLISH": 45,
        "FINANCIAL": 55,
        "PRODUCTION": 65,
        "SECRETS": 70,
        "REAL_TRADING": 100,
        "UNKNOWN": 100,
    }.get(risk, 100)
    penalty += {"LOW": 0, "MEDIUM": 10, "HIGH": 25, "CRITICAL": 50}[impact_norm]
    penalty += round(uncertainty * 0.35)
    if external_side_effects:
        penalty += 20
    if reversible:
        penalty -= 10
    score = max(0, min(100, 100 - penalty))

    if risk in {"REAL_TRADING", "UNKNOWN"}:
        mode = "BLOCKED"
    elif risk == "READ" and score >= 55:
        mode = "READ_ONLY"
    elif risk == "DRAFT" and score >= 45:
        mode = "DRAFT_ONLY"
    elif risk in {"WRITE"} and reversible and score >= 35:
        mode = "REVERSIBLE_WITH_APPROVAL"
    elif risk in SENSITIVE_RISKS:
        mode = "ADMIN_REQUIRED"
    else:
        mode = "ADVISE"

    return {
        "schema": SCHEMA,
        "score": score,
        "mode": mode,
        "guardian_risk": risk,
        "uncertainty_pct": round(uncertainty, 2),
        "impact": impact_norm,
        "reversible": bool(reversible),
        "external_side_effects": bool(external_side_effects),
        "grants_permission": False,
        "executes_action": False,
    }


def proof_of_safety(
    action: Any,
    access: Mapping[str, Any] | None,
    *,
    approved: bool = False,
    feature_flags: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: bool = False,
    signed_system_policy: bool = False,
    scope: Any = "",
    artifacts: Sequence[Any] | None = None,
    tests: Sequence[Mapping[str, Any]] | None = None,
    rollback_plan: Any = "",
    uncertainty_pct: Any = 100,
    impact: Any = "MEDIUM",
    reversible: bool = False,
    external_side_effects: bool = False,
) -> dict[str, Any]:
    """Build a non-cryptographic, auditable pre-execution safety proof.

    PASS means eligible for a downstream executor to evaluate. It never means
    that execution occurred or that a tool call is automatically authorized.
    """
    action_key = _clean(action, 120).lower()
    guardian = guardian_decision(
        action_key,
        access,
        approved=bool(approved),
        feature_flags=feature_flags,
    )
    authority = source_authority(
        source_kind,
        authenticated_admin=authenticated_admin,
        signed_system_policy=signed_system_policy,
    )
    budget = autonomy_budget(
        guardian_risk=guardian.get("risk") or "UNKNOWN",
        uncertainty_pct=uncertainty_pct,
        impact=impact,
        reversible=reversible,
        external_side_effects=external_side_effects,
    )

    scope_text = _clean(scope, 800)
    artifact_rows = [_clean(x, 260) for x in list(artifacts or []) if _clean(x, 260)]
    test_rows = [dict(x) for x in list(tests or []) if isinstance(x, Mapping)]
    passed_tests = [
        row for row in test_rows
        if str(row.get("state") or row.get("status") or "").upper() in {"PASS", "PASSED", "SUCCESS", "OK"}
    ]
    failed_tests = [
        row for row in test_rows
        if str(row.get("state") or row.get("status") or "").upper() in {"FAIL", "FAILED", "ERROR", "BLOCKED"}
    ]
    rollback = _clean(rollback_plan, 1200)
    risk = str(guardian.get("risk") or "UNKNOWN").upper()
    sensitive = risk in SENSITIVE_RISKS
    uncertainty = float(budget["uncertainty_pct"])

    blockers: list[str] = []
    warnings: list[str] = []

    if not authority["can_issue_action"]:
        blockers.append("SOURCE_HAS_NO_COMMAND_AUTHORITY")
    if not bool(guardian.get("allowed", False)):
        blockers.append("GUARDIAN_DENIED")
    if not scope_text:
        blockers.append("SCOPE_MISSING")
    if failed_tests:
        blockers.append("TEST_FAILURE")
    if risk == "REAL_TRADING":
        blockers.append("REAL_TRADING_BLOCKED")
    if sensitive and not rollback:
        blockers.append("ROLLBACK_MISSING")
    if sensitive and not test_rows:
        blockers.append("TEST_EVIDENCE_MISSING")
    if sensitive and uncertainty > 30.0:
        blockers.append("UNCERTAINTY_TOO_HIGH_FOR_SENSITIVE_ACTION")
    if sensitive and bool(external_side_effects) and not bool(approved):
        blockers.append("EXPLICIT_APPROVAL_REQUIRED")

    if not artifact_rows and risk in {"WRITE", "PRODUCTION", "SECRETS"}:
        warnings.append("ARTIFACT_SCOPE_EMPTY")
    if test_rows and not passed_tests and not failed_tests:
        warnings.append("TEST_STATE_UNKNOWN")
    if budget["mode"] in {"ADMIN_REQUIRED", "BLOCKED"} and not blockers:
        warnings.append("AUTONOMY_REQUIRES_ADMIN_REVIEW")

    if blockers:
        state = "BLOCK"
    elif warnings:
        state = "REVIEW"
    else:
        state = "PASS"

    payload = {
        "action": action_key,
        "source_kind": authority["source_kind"],
        "guardian": guardian,
        "authority": authority,
        "autonomy": budget,
        "scope": scope_text,
        "artifacts": artifact_rows,
        "tests": test_rows,
        "rollback_plan": rollback,
        "approved": bool(approved),
        "impact": budget["impact"],
        "uncertainty_pct": uncertainty,
        "external_side_effects": bool(external_side_effects),
    }

    return {
        "schema": SCHEMA,
        "proof_id": _stable_id("POS", payload),
        "generated_at": _now(),
        "state": state,
        "action": action_key,
        "source_authority": authority,
        "guardian": guardian,
        "autonomy_budget": budget,
        "scope": scope_text,
        "artifacts": artifact_rows,
        "test_count": len(test_rows),
        "passed_test_count": len(passed_tests),
        "failed_test_count": len(failed_tests),
        "rollback_present": bool(rollback),
        "blockers": blockers,
        "warnings": warnings,
        "eligible_for_downstream_executor": state == "PASS",
        "cryptographic_proof": False,
        "proof_meaning": "AUDITABLE_PREFLIGHT_NOT_EXECUTION_CERTIFICATE",
        "executes_action": False,
        "real_orders_enabled": False,
    }


def cyber_immune_plan(
    signals: Sequence[Mapping[str, Any]] | None,
    *,
    antivirus_or_edr_present: bool | None = None,
) -> dict[str, Any]:
    """Return a defensive containment plan without performing containment."""
    rows: list[dict[str, Any]] = []
    critical_confirmed = 0
    high_or_critical = 0
    for raw in list(signals or [])[:200]:
        if not isinstance(raw, Mapping):
            continue
        kind = _upper(raw.get("kind") or "UNKNOWN")
        severity = _upper(raw.get("severity") or "MEDIUM")
        if severity not in IMPACT_LEVELS:
            severity = "MEDIUM"
        evidence = _upper(raw.get("evidence_state") or raw.get("truth_state") or "UNKNOWN")
        if evidence not in {"CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}:
            evidence = "UNKNOWN"
        item = {
            "kind": kind,
            "severity": severity,
            "evidence_state": evidence,
            "source": _clean(raw.get("source"), 220),
            "detail": _clean(raw.get("detail"), 800),
        }
        rows.append(item)
        if severity in {"HIGH", "CRITICAL"}:
            high_or_critical += 1
        if kind in CRITICAL_SIGNAL_KINDS and severity == "CRITICAL" and evidence == "CONFIRMED":
            critical_confirmed += 1

    if critical_confirmed:
        posture = "QUARANTINE_RECOMMENDED"
    elif high_or_critical:
        posture = "INVESTIGATE_AND_ISOLATE_IF_CONFIRMED"
    elif rows:
        posture = "OBSERVE"
    else:
        posture = "NO_SIGNAL"

    steps = [
        "Preservar evidências e hashes antes de qualquer limpeza.",
        "Reduzir privilégios e isolar o componente suspeito quando houver evidência suficiente.",
        "Bloquear somente conectores/comunicações suspeitos dentro do escopo autorizado.",
        "Validar backup/rollback antes de remoção destrutiva.",
        "Revalidar integridade e comportamento depois da contenção.",
    ]
    if antivirus_or_edr_present is True:
        steps.insert(1, "Manter antivírus/EDR ativo; usar seus alertas como evidência adicional.")
    elif antivirus_or_edr_present is None:
        steps.insert(1, "Estado de antivírus/EDR não confirmado; não assumir proteção ativa ou ausente.")

    return {
        "schema": SCHEMA,
        "generated_at": _now(),
        "posture": posture,
        "signals": rows,
        "signal_count": len(rows),
        "critical_confirmed": critical_confirmed,
        "steps": steps,
        "automatic_containment": False,
        "automatic_deletion": False,
        "disable_antivirus_or_edr": False,
        "disable_security_controls": False,
        "requires_human_review_for_destructive_action": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def emergency_cutoff_posture(
    *,
    critical_incident: bool = False,
    policy_integrity_ok: bool | None = None,
    permission_integrity_ok: bool | None = None,
    secret_exposure_confirmed: bool = False,
) -> dict[str, Any]:
    """Advisory kill-switch posture. It never disables tools by itself."""
    reasons: list[str] = []
    if critical_incident:
        reasons.append("CRITICAL_INCIDENT")
    if policy_integrity_ok is False:
        reasons.append("POLICY_INTEGRITY_FAILURE")
    if permission_integrity_ok is False:
        reasons.append("PERMISSION_INTEGRITY_FAILURE")
    if secret_exposure_confirmed:
        reasons.append("SECRET_EXPOSURE")
    if policy_integrity_ok is None:
        reasons.append("POLICY_INTEGRITY_UNKNOWN")
    if permission_integrity_ok is None:
        reasons.append("PERMISSION_INTEGRITY_UNKNOWN")

    hard = any(x in reasons for x in {
        "CRITICAL_INCIDENT",
        "POLICY_INTEGRITY_FAILURE",
        "PERMISSION_INTEGRITY_FAILURE",
        "SECRET_EXPOSURE",
    })
    state = "CUT_SENSITIVE_TOOLS_RECOMMENDED" if hard else (
        "SAFE_MODE_RECOMMENDED" if reasons else "NORMAL"
    )
    return {
        "schema": SCHEMA,
        "state": state,
        "reasons": reasons,
        "recommended_sensitive_tool_access": "OFF" if hard else "READ_ONLY" if reasons else "POLICY_CONTROLLED",
        "automatic_cutoff": False,
        "requires_independent_controller": True,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_KINDS",
    "UNTRUSTED_CONTENT_SOURCES",
    "IMPACT_LEVELS",
    "AUTONOMY_MODES",
    "normalize_source_kind",
    "source_authority",
    "instruction_boundary",
    "autonomy_budget",
    "proof_of_safety",
    "cyber_immune_plan",
    "emergency_cutoff_posture",
]
