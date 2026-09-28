"""AION Global Worker Human Incident Closure Ceremony V1.

Explicit human-decision ceremony that can run only after Recovery Evidence /
Incident Closure V1 reports CLOSURE_REVIEW_READY.

V1 records the human closure decision in memory/session scope only. It does not
persist to the runtime Checkpoint or Incident Center, mutate the feature flag,
run a worker tick, dispatch a workflow, authorize reactivation, or claim that an
authoritative shared incident record has been closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_HUMAN_INCIDENT_CLOSURE_V1"
CONFIRMATION_PHRASE = "ENCERRAR INCIDENTE WORKER GLOBAL"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def prepare_human_incident_closure(
    assessment: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Prepare a closure ceremony bound to one closure-readiness assessment."""
    current = utc(now or _now())
    report = dict(assessment or {})
    ready = (
        str(report.get("status") or "") == "CLOSURE_REVIEW_READY"
        and report.get("closure_review_ready") is True
    )
    package_digest = str(report.get("closure_package_digest") or "")
    incident_digest = str(report.get("incident_evidence_digest") or "")
    remediation_digest = str(report.get("remediation_digest") or "")
    assessed_at = _parse_iso(report.get("assessed_at"))

    if not ready:
        return {
            "schema": SCHEMA,
            "status": "CLOSURE_NOT_READY",
            "reason": "CLOSURE_REVIEW_READY_REQUIRED",
            "ceremony_ready": False,
            "human_closure_decision_recorded": False,
            "authoritative_incident_closed": False,
            "executes_action": False,
        }

    if (
        not package_digest
        or not incident_digest
        or not remediation_digest
        or assessed_at is None
    ):
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "reason": "BOUND_CLOSURE_EVIDENCE_REQUIRED",
            "ceremony_ready": False,
            "human_closure_decision_recorded": False,
            "authoritative_incident_closed": False,
            "executes_action": False,
        }

    binding = {
        "closure_package_digest": package_digest,
        "incident_evidence_digest": incident_digest,
        "remediation_digest": remediation_digest,
        "assessed_at": assessed_at.isoformat(),
    }
    ceremony_digest = digest(binding)
    return {
        "schema": SCHEMA,
        "status": "CEREMONY_READY",
        "ceremony_ready": True,
        "prepared_at": current.isoformat(),
        "closure_package_digest": package_digest,
        "incident_evidence_digest": incident_digest,
        "remediation_digest": remediation_digest,
        "assessment_assessed_at": assessed_at.isoformat(),
        "ceremony_digest": ceremony_digest,
        "confirmation_phrase": CONFIRMATION_PHRASE,
        "requires_exact_phrase": True,
        "requires_human_confirmation": True,
        "requires_evidence_acknowledgement": True,
        "requires_reactivation_separation_acknowledgement": True,
        "human_closure_decision_recorded": False,
        "authoritative_incident_closed": False,
        "persistent": False,
        "session_only": True,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "global_worker_tick_executed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


def record_human_incident_closure(
    assessment: Mapping[str, Any] | None,
    *,
    human_confirmation: bool,
    evidence_acknowledged: bool,
    reactivation_separation_acknowledged: bool,
    confirmation_phrase: str,
    operator_note: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record a human closure decision in memory without authoritative mutation."""
    current = utc(now or _now())
    prepared = prepare_human_incident_closure(assessment, now=current)
    if prepared.get("status") != "CEREMONY_READY":
        return prepared

    acknowledgements = {
        "human_confirmation": human_confirmation is True,
        "evidence_acknowledged": evidence_acknowledged is True,
        "reactivation_separation_acknowledged": (
            reactivation_separation_acknowledged is True
        ),
    }
    if not all(acknowledgements.values()):
        return {
            **prepared,
            "status": "CONFIRMATION_REQUIRED",
            "reason": "ALL_HUMAN_ACKNOWLEDGEMENTS_REQUIRED",
            "acknowledgements": acknowledgements,
        }

    if confirmation_phrase != CONFIRMATION_PHRASE:
        return {
            **prepared,
            "status": "CONFIRMATION_REQUIRED",
            "reason": "EXACT_HUMAN_CLOSURE_CONFIRMATION_REQUIRED",
            "acknowledgements": acknowledgements,
        }

    note = str(operator_note or "").strip()
    payload = {
        "closure_package_digest": prepared["closure_package_digest"],
        "incident_evidence_digest": prepared["incident_evidence_digest"],
        "remediation_digest": prepared["remediation_digest"],
        "ceremony_digest": prepared["ceremony_digest"],
        "recorded_at": current.isoformat(),
        "operator_note": note,
        **acknowledgements,
    }
    record_digest = digest(payload)
    return {
        **prepared,
        "status": "HUMAN_CLOSURE_DECISION_RECORDED_SESSION_ONLY",
        "recorded_at": current.isoformat(),
        "closure_record_id": "GW-CLOSE-" + record_digest[:16].upper(),
        "closure_record_digest": record_digest,
        "operator_note": note,
        "acknowledgements": acknowledgements,
        "human_closure_decision": "APPROVED",
        "human_closure_decision_recorded": True,
        "authoritative_incident_closed": False,
        "shared_incident_record_modified": False,
        "persistent": False,
        "session_only": True,
        "reactivation_authorized": False,
        "reactivation_separate_ceremony_required": True,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "global_worker_tick_executed": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


def human_closure_summary(
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return operator-facing truth-safe closure summary."""
    closure = dict(record or {})
    recorded = closure.get("human_closure_decision_recorded") is True
    return {
        "schema": SCHEMA,
        "status": str(closure.get("status") or "NOT_RUN"),
        "human_closure_decision_recorded": recorded,
        "human_closure_decision": (
            str(closure.get("human_closure_decision") or "")
            if recorded
            else ""
        ),
        "closure_record_id": str(closure.get("closure_record_id") or ""),
        "authoritative_incident_closed": False,
        "persistent": False,
        "session_only": True,
        "reactivation_authorized": False,
        "reactivation_separate_ceremony_required": True,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CONFIRMATION_PHRASE",
    "prepare_human_incident_closure",
    "record_human_incident_closure",
    "human_closure_summary",
]
