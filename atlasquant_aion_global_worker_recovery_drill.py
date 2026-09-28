"""AION Global Worker Recovery / Incident Drill V1.

Simulation-only recovery exercise built on top of Operational Supervision V1.
It rehearses operator response to timeout, stale lease, unsafe receipt and
generic blocked verification without changing any shared state.

The drill never mutates the repository feature flag or runtime Checkpoint,
never runs a worker tick, never dispatches a workflow and never claims that a
real incident was contained or recovered.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_RECOVERY_DRILL_V1"
CONFIRMATION_PHRASE = "SIMULAR RECUPERACAO WORKER GLOBAL"

SUPPORTED_POSTURES = {
    "INCIDENT_LIVE_TIMEOUT",
    "INCIDENT_STALE_LEASE",
    "INCIDENT_UNSAFE_RECEIPT",
    "INCIDENT_VERIFICATION_BLOCKED",
}

SCENARIO_BY_POSTURE = {
    "INCIDENT_LIVE_TIMEOUT": "LIVE_TIMEOUT",
    "INCIDENT_STALE_LEASE": "STALE_LEASE",
    "INCIDENT_UNSAFE_RECEIPT": "UNSAFE_RECEIPT",
    "INCIDENT_VERIFICATION_BLOCKED": "VERIFICATION_BLOCKED",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _criteria(scenario: str) -> list[str]:
    common = [
        "Evidência original preservada e identificada pelo digest.",
        "Nenhuma permissão ampliada durante diagnóstico.",
        "Nenhum trading real, pagamento, publicação, deploy ou merge executado.",
        "Qualquer mudança real de feature flag continua exigindo a cerimônia ADMIN existente.",
        "Nova declaração LIVE só pode vir do verificador compartilhado após nova evidência real.",
    ]
    specific = {
        "LIVE_TIMEOUT": [
            "Feature flag deve ser confirmada em estado seguro antes de retry.",
            "Workflow/pulso agendado deve ser revisado sem fabricar heartbeat.",
            "Novo heartbeat e tick gha-* precisam surgir depois de uma futura reativação autorizada.",
        ],
        "STALE_LEASE": [
            "Owner, expires_at, heartbeat e fencing token do lease precisam ser explicados.",
            "Nenhum novo claim pode ser forçado enquanto houver lease stale não resolvido.",
            "Uma futura retomada exige lease coerente e evidência compartilhada fresca.",
        ],
        "UNSAFE_RECEIPT": [
            "Receipt inseguro deve permanecer preservado como evidência.",
            "Origem de provider/external/trading effect precisa ser identificada e bloqueada.",
            "Retomada exige receipts futuros sem efeitos externos/trading e nova verificação live.",
        ],
        "VERIFICATION_BLOCKED": [
            "Reason do verificador precisa ser resolvido com evidência autoritativa.",
            "Worker não pode ser considerado LIVE enquanto o bloqueio persistir.",
            "Nova avaliação deve repetir a cadeia Readiness -> Live Verification.",
        ],
    }.get(scenario, [])
    return common + specific


def _stages(scenario: str, safety_stop_recommended: bool) -> list[dict[str, Any]]:
    stages = [
        {
            "stage": "PRESERVE_EVIDENCE",
            "mode": "SIMULATION",
            "expected": "INCIDENT_EVIDENCE_PRESERVED",
            "executes_action": False,
        },
        {
            "stage": "FREEZE_AUTHORITY_EXPANSION",
            "mode": "SIMULATION",
            "expected": "NO_NEW_PERMISSIONS_OR_EXTERNAL_ACTIONS",
            "executes_action": False,
        },
    ]
    if safety_stop_recommended:
        stages.append(
            {
                "stage": "MANUAL_SAFETY_STOP",
                "mode": "SIMULATION",
                "expected": "ADMIN_CEREMONY_REQUIRED",
                "executes_action": False,
            }
        )
    else:
        stages.append(
            {
                "stage": "CONFIRM_SAFE_FLAG_POSTURE",
                "mode": "SIMULATION",
                "expected": "NO_AUTOMATIC_FLAG_CHANGE_REQUIRED",
                "executes_action": False,
            }
        )

    diagnostic = {
        "LIVE_TIMEOUT": "REVIEW_SCHEDULE_AND_SHARED_HEARTBEAT_PATH",
        "STALE_LEASE": "REVIEW_LEASE_OWNER_EXPIRY_HEARTBEAT_AND_FENCING",
        "UNSAFE_RECEIPT": "TRACE_AND_BLOCK_UNSAFE_EFFECT_PATH",
        "VERIFICATION_BLOCKED": "RESOLVE_VERIFIER_EVIDENCE_BLOCKER",
    }.get(scenario, "MANUAL_DIAGNOSIS_REQUIRED")
    stages.extend(
        [
            {
                "stage": "DIAGNOSE_ROOT_CAUSE",
                "mode": "SIMULATION",
                "expected": diagnostic,
                "executes_action": False,
            },
            {
                "stage": "REVALIDATE_SHARED_EVIDENCE",
                "mode": "SIMULATION",
                "expected": "FRESH_AUTHORITATIVE_EVIDENCE_REQUIRED",
                "executes_action": False,
            },
            {
                "stage": "REACTIVATION_GATE",
                "mode": "SIMULATION",
                "expected": "REACTIVATION_NOT_AUTHORIZED_BY_DRILL",
                "executes_action": False,
            },
        ]
    )
    return stages


def prepare_global_worker_recovery_drill(
    supervision: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Prepare a deterministic simulation plan from a supervision incident."""
    current = utc(now or _now())
    report = dict(supervision or {})
    posture = str(report.get("posture") or "UNKNOWN_REVIEW_REQUIRED")
    incident_open = report.get("incident_open") is True

    if not incident_open or posture not in SUPPORTED_POSTURES:
        return {
            "schema": SCHEMA,
            "status": "NO_DRILL_REQUIRED",
            "reason": "SUPPORTED_OPEN_INCIDENT_REQUIRED",
            "simulation_only": True,
            "executes_action": False,
            "feature_flag_modified": False,
            "runtime_modified": False,
            "real_trading_enabled": False,
        }

    scenario = SCENARIO_BY_POSTURE[posture]
    evidence_digest = str(report.get("evidence_digest") or "")
    if not evidence_digest:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "SUPERVISION_EVIDENCE_DIGEST_REQUIRED",
            "simulation_only": True,
            "executes_action": False,
            "feature_flag_modified": False,
            "runtime_modified": False,
            "real_trading_enabled": False,
        }

    binding = {
        "scenario": scenario,
        "posture": posture,
        "severity": str(report.get("severity") or "MEDIUM"),
        "evidence_digest": evidence_digest,
        "safety_stop_recommended": bool(report.get("safety_stop_recommended")),
    }
    plan_digest = digest(binding)
    return {
        "schema": SCHEMA,
        "status": "DRILL_READY",
        "prepared_at": current.isoformat(),
        "scenario": scenario,
        "posture": posture,
        "severity": binding["severity"],
        "source_evidence_digest": evidence_digest,
        "safety_stop_recommended": binding["safety_stop_recommended"],
        "plan_digest": plan_digest,
        "confirmation_phrase": CONFIRMATION_PHRASE,
        "stages": _stages(scenario, binding["safety_stop_recommended"]),
        "acceptance_criteria": _criteria(scenario),
        "simulation_only": True,
        "executes_action": False,
        "automatic_containment": False,
        "automatic_feature_flag_mutation": False,
        "automatic_checkpoint_mutation": False,
        "global_worker_tick_executed": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
    }


def simulate_global_worker_recovery_drill(
    supervision: Mapping[str, Any] | None,
    *,
    confirmation: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the simulation in memory. No real recovery action is performed."""
    prepared = prepare_global_worker_recovery_drill(supervision, now=now)
    if prepared.get("status") != "DRILL_READY":
        return prepared

    if confirmation is not True or confirmation_phrase != CONFIRMATION_PHRASE:
        return {
            **prepared,
            "status": "CONFIRMATION_REQUIRED",
            "reason": "EXACT_SIMULATION_CONFIRMATION_REQUIRED",
            "drill_completed": False,
        }

    stages = [dict(stage) for stage in prepared.get("stages") or []]
    completed = all(
        stage.get("mode") == "SIMULATION"
        and stage.get("executes_action") is False
        for stage in stages
    )
    result_payload = {
        "scenario": prepared["scenario"],
        "source_evidence_digest": prepared["source_evidence_digest"],
        "plan_digest": prepared["plan_digest"],
        "stage_count": len(stages),
        "simulation_only": True,
    }
    return {
        **prepared,
        "status": "DRILL_COMPLETED_SIMULATION_ONLY" if completed else "BLOCKED",
        "reason": "" if completed else "NON_SIMULATION_STAGE_REJECTED",
        "completed_at": utc(now or _now()).isoformat(),
        "drill_completed": completed,
        "drill_digest": digest(result_payload) if completed else "",
        "real_incident_contained": False,
        "real_recovery_confirmed": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "executes_action": False,
    }


def recovery_drill_summary(
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compact operator summary that cannot be mistaken for real recovery."""
    drill = dict(result or {})
    return {
        "schema": SCHEMA,
        "status": str(drill.get("status") or "NOT_RUN"),
        "scenario": str(drill.get("scenario") or ""),
        "severity": str(drill.get("severity") or ""),
        "drill_completed": drill.get("drill_completed") is True,
        "simulation_only": True,
        "real_incident_contained": False,
        "real_recovery_confirmed": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "real_trading_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "CONFIRMATION_PHRASE",
    "SUPPORTED_POSTURES",
    "prepare_global_worker_recovery_drill",
    "simulate_global_worker_recovery_drill",
    "recovery_drill_summary",
]
