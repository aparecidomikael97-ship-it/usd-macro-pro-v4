"""AION Global Worker Operational Supervision V1.

Read-only interpretation layer above Live Activation Verification. It converts
verified states into operator posture, incident severity and recovery guidance.

It never disables the feature flag, mutates the runtime Checkpoint, runs a
worker tick, dispatches a workflow or performs an external/business action.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_OPERATIONAL_SUPERVISION_V1"
SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")

HEALTHY_STATES = {
    "LIVE_CONFIRMED_IDLE",
    "LIVE_CONFIRMED_WITH_WORK",
}
PENDING_STATES = {
    "AWAITING_LIVE_EVIDENCE",
    "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK",
}
SAFETY_STOP_RECOMMENDED_STATES = {
    "LIVE_EVIDENCE_TIMEOUT",
    "BLOCKED_STALE_LEASE",
    "BLOCKED_INFLIGHT_RECONCILIATION",
    "BLOCKED_UNSAFE_RECEIPT",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _severity(status: str) -> str:
    return {
        "NOT_ENABLED": "INFO",
        "AWAITING_LIVE_EVIDENCE": "LOW",
        "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK": "LOW",
        "LIVE_CONFIRMED_IDLE": "INFO",
        "LIVE_CONFIRMED_WITH_WORK": "INFO",
        "LIVE_EVIDENCE_TIMEOUT": "HIGH",
        "BLOCKED_STALE_LEASE": "HIGH",
        "BLOCKED_INFLIGHT_RECONCILIATION": "HIGH",
        "BLOCKED_UNSAFE_RECEIPT": "CRITICAL",
        "BLOCKED": "HIGH",
    }.get(status, "MEDIUM")


def _posture(status: str) -> str:
    if status == "NOT_ENABLED":
        return "STANDBY_SAFE"
    if status in PENDING_STATES:
        return "ACTIVATION_PENDING"
    if status == "LIVE_CONFIRMED_IDLE":
        return "HEALTHY_LIVE_IDLE"
    if status == "LIVE_CONFIRMED_WITH_WORK":
        return "HEALTHY_LIVE_WORK"
    if status == "LIVE_EVIDENCE_TIMEOUT":
        return "INCIDENT_LIVE_TIMEOUT"
    if status == "BLOCKED_STALE_LEASE":
        return "INCIDENT_STALE_LEASE"
    if status == "BLOCKED_INFLIGHT_RECONCILIATION":
        return "INCIDENT_INFLIGHT_RECONCILIATION"
    if status == "BLOCKED_UNSAFE_RECEIPT":
        return "INCIDENT_UNSAFE_RECEIPT"
    if status == "BLOCKED":
        return "INCIDENT_VERIFICATION_BLOCKED"
    return "UNKNOWN_REVIEW_REQUIRED"


def _steps(status: str) -> list[str]:
    common = [
        "Preservar a evidência compartilhada antes de qualquer alteração.",
        "Manter trading real, pagamentos, publicação, deploy e merge bloqueados.",
        "Não ampliar permissões durante o diagnóstico.",
    ]
    specific = {
        "NOT_ENABLED": [
            "Nenhuma ação operacional é necessária; o Worker Global não está habilitado.",
            "Continuar usando Readiness/cerimônias antes de qualquer ativação futura.",
        ],
        "AWAITING_LIVE_EVIDENCE": [
            "Aguardar o próximo pulso agendado dentro da janela de verificação.",
            "Reler feature flag e Checkpoint compartilhado; não gerar heartbeat artificial.",
        ],
        "LIVE_HEARTBEAT_CONFIRMED_AWAITING_TICK": [
            "Aguardar a conclusão do tick atual antes de declarar LIVE.",
            "Confirmar que lease/heartbeat continuam frescos e associados ao runtime gha-*.",
        ],
        "LIVE_CONFIRMED_IDLE": [
            "Nenhuma contenção necessária.",
            "Continuar observando ticks/heartbeat; receipt de trabalho só é esperado quando houver tarefa due.",
        ],
        "LIVE_CONFIRMED_WITH_WORK": [
            "Nenhuma contenção necessária.",
            "Verificar que receipts continuam sem provider/external/trading effects.",
        ],
        "LIVE_EVIDENCE_TIMEOUT": [
            "Tratar o Worker como NÃO confirmado operacional.",
            "Revisar o último workflow schedule e o Checkpoint antes de qualquer retry manual.",
            "Considerar a desativação de segurança da feature flag por aprovação explícita.",
        ],
        "BLOCKED_STALE_LEASE": [
            "Não forçar novo claim enquanto o lease stale não for explicado.",
            "Revisar owner, heartbeat, expires_at e fencing token.",
            "Considerar a desativação de segurança da feature flag por aprovação explícita.",
        ],
        "BLOCKED_INFLIGHT_RECONCILIATION": [
            "Não executar retry automático nem novo claim enquanto o inflight permanecer pendente.",
            "Revisar owner, fencing token, claimed_at e a persistência terminal do tick anterior.",
            "Reconciliar a evidência do Checkpoint antes de liberar nova execução.",
        ],
        "BLOCKED_UNSAFE_RECEIPT": [
            "Preservar o receipt inseguro como evidência de incidente.",
            "Não permitir novos wake-ups até revisão do caminho que reportou efeito externo/trading.",
            "Considerar a desativação de segurança da feature flag por aprovação explícita.",
        ],
        "BLOCKED": [
            "Revisar o reason do verificador antes de qualquer ação.",
            "Não considerar o Worker LIVE enquanto a evidência permanecer bloqueada.",
        ],
    }.get(status, [
        "Revisar o estado desconhecido e reunir evidência adicional.",
        "Não declarar o Worker operacional até classificação confirmada.",
    ])
    return common + specific


def supervise_global_worker(
    live_report: Mapping[str, Any] | None,
    flag_evidence: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify current evidence without performing containment."""
    current = utc(now or _now())
    live = dict(live_report or {})
    flag = dict(flag_evidence or {})
    status = str(live.get("status") or "UNKNOWN").upper()
    flag_state = str(flag.get("state") or "UNKNOWN").upper()
    flag_confirmed = str(flag.get("status") or "").upper() == "CONFIRMED"

    # A disabled/unset authoritative flag wins over stale healthy/pending UI
    # data, but it must never erase an already observed incident.
    if (
        flag_confirmed
        and flag_state in {"UNSET", "DISABLED"}
        and status not in SAFETY_STOP_RECOMMENDED_STATES
        and status != "BLOCKED"
    ):
        status = "NOT_ENABLED"

    severity = _severity(status)
    posture = _posture(status)
    stop_recommended = bool(
        flag_confirmed
        and flag_state == "ENABLED"
        and status in SAFETY_STOP_RECOMMENDED_STATES
    )
    incident_open = severity in {"HIGH", "CRITICAL"}
    reason = str(live.get("reason") or "")

    evidence = {
        "live_status": status,
        "live_confirmed": bool(live.get("live_confirmed")),
        "heartbeat_confirmed": bool(live.get("heartbeat_confirmed")),
        "tick_confirmed": bool(live.get("tick_confirmed")),
        "work_receipt_confirmed": bool(live.get("work_receipt_confirmed")),
        "unsafe_receipts": int(live.get("unsafe_receipts_after_activation") or 0),
        "stale_lease": bool(live.get("stale_lease")),
        "inflight_reconciliation_required": bool(live.get("inflight_reconciliation_required")),
        "inflight_owner": str(live.get("inflight_owner") or ""),
        "inflight_fencing_token": int(live.get("inflight_fencing_token") or 0),
        "inflight_since": str(live.get("inflight_since") or ""),
        "last_runtime_id": str(live.get("last_runtime_id") or ""),
        "last_heartbeat_at": str(live.get("last_heartbeat_at") or ""),
        "last_tick_at": str(live.get("last_tick_at") or ""),
        "feature_flag_state": flag_state,
        "feature_flag_confirmed": flag_confirmed,
    }
    evidence_digest = digest(evidence)

    return {
        "schema": SCHEMA,
        "generated_at": current.isoformat(),
        "posture": posture,
        "severity": severity,
        "incident_open": incident_open,
        "live_status": status,
        "reason": reason,
        "evidence": evidence,
        "evidence_digest": evidence_digest,
        "safety_stop_recommended": stop_recommended,
        "safety_stop_automatic": False,
        "recovery_steps": _steps(status),
        "requires_human_review": incident_open,
        "automatic_containment": False,
        "automatic_feature_flag_mutation": False,
        "automatic_checkpoint_mutation": False,
        "global_worker_tick_executed": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
    }


def operational_incident(
    supervision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return an Incident-Center-compatible read-only proposal."""
    report = dict(supervision or {})
    if not report.get("incident_open"):
        return {
            "schema": SCHEMA,
            "status": "NO_INCIDENT",
            "incident": None,
            "executes_action": False,
        }

    posture = str(report.get("posture") or "UNKNOWN_REVIEW_REQUIRED")
    severity = str(report.get("severity") or "MEDIUM")
    evidence_digest = str(report.get("evidence_digest") or "")
    incident = {
        "incident_id": "INC-AION-GW-" + evidence_digest[:12].upper(),
        "kind": "OBSERVABILITY",
        "severity": severity if severity in SEVERITIES else "MEDIUM",
        "title": "AION Global Worker · " + posture,
        "detail": str(report.get("reason") or posture),
        "source": "aion_global_worker_live_verification",
        "evidence_state": "CONFIRMED",
        "status": "OPEN",
        "response_key": "global_worker",
        "safety_stop_recommended": bool(report.get("safety_stop_recommended")),
        "automatic_containment": False,
        "automatic_rollback": False,
        "automatic_account_mutation": False,
        "real_orders_enabled": False,
    }
    return {
        "schema": SCHEMA,
        "status": "INCIDENT_PROPOSED",
        "incident": incident,
        "executes_action": False,
    }


def supervision_history_event(
    supervision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a compact immutable observation suitable for session history."""
    report = dict(supervision or {})
    payload = {
        "posture": str(report.get("posture") or "UNKNOWN_REVIEW_REQUIRED"),
        "severity": str(report.get("severity") or "MEDIUM"),
        "live_status": str(report.get("live_status") or "UNKNOWN"),
        "reason": str(report.get("reason") or ""),
        "evidence_digest": str(report.get("evidence_digest") or ""),
        "incident_open": bool(report.get("incident_open")),
        "safety_stop_recommended": bool(report.get("safety_stop_recommended")),
    }
    event_digest = digest(payload)
    return {
        "event_id": "GW-SUP-" + event_digest[:16].upper(),
        "observed_at": str(report.get("generated_at") or ""),
        **payload,
        "automatic_containment": False,
        "automatic_feature_flag_mutation": False,
        "real_trading_enabled": False,
    }


def append_supervision_history(
    history: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    supervision: Mapping[str, Any] | None,
    *,
    max_entries: int = 50,
) -> list[dict[str, Any]]:
    """Append one observation, deduplicated by evidence, without persistence."""
    if type(max_entries) is not int or not 1 <= max_entries <= 200:
        raise ValueError("invalid supervision history limit")

    rows = [dict(row) for row in (history or []) if isinstance(row, Mapping)]
    event = supervision_history_event(supervision)
    event_id = str(event.get("event_id") or "")
    rows = [row for row in rows if str(row.get("event_id") or "") != event_id]
    rows.append(event)
    return rows[-max_entries:]


def supervision_history_summary(
    history: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
) -> dict[str, Any]:
    """Summarize session-local supervision observations."""
    rows = [dict(row) for row in (history or []) if isinstance(row, Mapping)]
    incidents = [row for row in rows if row.get("incident_open") is True]
    critical = [
        row for row in incidents
        if str(row.get("severity") or "").upper() == "CRITICAL"
    ]
    return {
        "schema": SCHEMA,
        "observations": len(rows),
        "incidents": len(incidents),
        "critical_incidents": len(critical),
        "latest": rows[-1] if rows else None,
        "persistent": False,
        "runtime_modified": False,
        "feature_flag_modified": False,
    }


__all__ = [
    "SCHEMA",
    "SEVERITIES",
    "HEALTHY_STATES",
    "PENDING_STATES",
    "SAFETY_STOP_RECOMMENDED_STATES",
    "supervise_global_worker",
    "operational_incident",
    "supervision_history_event",
    "append_supervision_history",
    "supervision_history_summary",
]
