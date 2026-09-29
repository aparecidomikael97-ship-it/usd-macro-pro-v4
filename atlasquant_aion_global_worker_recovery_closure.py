"""AION Global Worker Recovery Evidence / Incident Closure V1.

Read-only closure-readiness layer for Global Worker incidents. It binds the
original supervision incident to newer shared evidence plus explicit remediation
evidence. It can only declare that a case is ready for human closure review.

It never closes an incident, mutates the feature flag/runtime Checkpoint, runs a
worker tick, dispatches a workflow, or authorizes reactivation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_RECOVERY_EVIDENCE_CLOSURE_V1"
REMEDIATION_SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_REMEDIATION_EVIDENCE_V1"
CONFIRMATION_PHRASE = "CONFIRMAR EVIDENCIA DE REMEDIACAO WORKER GLOBAL"

SUPPORTED_POSTURES = {
    "INCIDENT_LIVE_TIMEOUT",
    "INCIDENT_STALE_LEASE",
    "INCIDENT_INFLIGHT_RECONCILIATION",
    "INCIDENT_UNSAFE_RECEIPT",
    "INCIDENT_VERIFICATION_BLOCKED",
}

HEALTHY_LIVE_STATES = {
    "LIVE_CONFIRMED_IDLE",
    "LIVE_CONFIRMED_WITH_WORK",
}


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


def prepare_remediation_evidence(
    supervision: Mapping[str, Any] | None,
    *,
    root_cause_identified: bool,
    corrective_action_verified: bool,
    regression_check_passed: bool,
    evidence_preserved: bool,
    reviewer_confirmed: bool,
    confirmation_phrase: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create session-local remediation evidence bound to one incident."""
    current = utc(now or _now())
    report = dict(supervision or {})
    posture = str(report.get("posture") or "")
    incident_digest = str(report.get("evidence_digest") or "")
    incident_at = _parse_iso(report.get("generated_at"))

    if (
        report.get("incident_open") is not True
        or posture not in SUPPORTED_POSTURES
    ):
        return {
            "schema": REMEDIATION_SCHEMA,
            "status": "NO_OPEN_SUPPORTED_INCIDENT",
            "confirmed": False,
            "persistent": False,
            "executes_action": False,
        }

    if not incident_digest or incident_at is None:
        return {
            "schema": REMEDIATION_SCHEMA,
            "status": "BLOCKED",
            "reason": "INCIDENT_DIGEST_AND_TIMESTAMP_REQUIRED",
            "confirmed": False,
            "persistent": False,
            "executes_action": False,
        }

    checks = {
        "root_cause_identified": root_cause_identified is True,
        "corrective_action_verified": corrective_action_verified is True,
        "regression_check_passed": regression_check_passed is True,
        "evidence_preserved": evidence_preserved is True,
        "reviewer_confirmed": reviewer_confirmed is True,
    }
    all_checks = all(checks.values())
    phrase_ok = confirmation_phrase == CONFIRMATION_PHRASE

    payload = {
        "incident_evidence_digest": incident_digest,
        "incident_posture": posture,
        "incident_generated_at": incident_at.isoformat(),
        "reviewed_at": current.isoformat(),
        **checks,
    }
    remediation_digest = digest(payload)
    status = (
        "CONFIRMED"
        if all_checks and phrase_ok and current > incident_at
        else "CONFIRMATION_REQUIRED"
    )
    reason = ""
    if current <= incident_at:
        status = "BLOCKED"
        reason = "REMEDIATION_EVIDENCE_MUST_POSTDATE_INCIDENT"
    elif not all_checks:
        reason = "ALL_REMEDIATION_CHECKS_REQUIRED"
    elif not phrase_ok:
        reason = "EXACT_REMEDIATION_CONFIRMATION_REQUIRED"

    return {
        "schema": REMEDIATION_SCHEMA,
        "status": status,
        "reason": reason,
        "confirmed": status == "CONFIRMED",
        **payload,
        "remediation_digest": remediation_digest,
        "persistent": False,
        "session_only": True,
        "executes_action": False,
        "incident_closed": False,
        "automatic_closure": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "reactivation_authorized": False,
        "real_trading_enabled": False,
    }


def _current_evidence_state(
    posture: str,
    live_report: Mapping[str, Any],
    flag_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(live_report.get("status") or "UNKNOWN")
    flag_status = str(flag_evidence.get("status") or "")
    flag_state = str(flag_evidence.get("state") or "UNKNOWN")
    flag_confirmed = flag_status == "CONFIRMED"
    healthy_live = bool(
        flag_confirmed
        and flag_state == "ENABLED"
        and status in HEALTHY_LIVE_STATES
        and live_report.get("live_confirmed") is True
        and live_report.get("heartbeat_confirmed") is True
        and live_report.get("tick_confirmed") is True
    )
    safely_disabled = bool(
        flag_confirmed
        and flag_state in {"UNSET", "DISABLED"}
        and status == "NOT_ENABLED"
    )

    blockers: list[str] = []
    if not flag_confirmed:
        blockers.append("FEATURE_FLAG_EVIDENCE_NOT_CONFIRMED")
    if not (healthy_live or safely_disabled):
        blockers.append("CURRENT_STATE_NOT_SAFE_OR_HEALTHY")

    if posture == "INCIDENT_STALE_LEASE" and live_report.get("stale_lease") is True:
        blockers.append("STALE_LEASE_STILL_PRESENT")
    if (
        posture == "INCIDENT_INFLIGHT_RECONCILIATION"
        and live_report.get("inflight_reconciliation_required") is True
    ):
        blockers.append("INFLIGHT_RECONCILIATION_STILL_REQUIRED")
    if posture == "INCIDENT_UNSAFE_RECEIPT":
        if int(live_report.get("unsafe_receipts_after_activation") or 0) > 0:
            blockers.append("UNSAFE_RECEIPT_STILL_PRESENT")
    if posture == "INCIDENT_LIVE_TIMEOUT":
        if flag_state == "ENABLED" and status not in HEALTHY_LIVE_STATES:
            blockers.append("LIVE_TIMEOUT_NOT_RECOVERED")
    if posture == "INCIDENT_VERIFICATION_BLOCKED":
        if status == "BLOCKED" or status.startswith("BLOCKED_"):
            blockers.append("VERIFICATION_STILL_BLOCKED")

    return {
        "status": status,
        "flag_state": flag_state,
        "flag_confirmed": flag_confirmed,
        "healthy_live": healthy_live,
        "safely_disabled": safely_disabled,
        "blockers": blockers,
    }


def assess_incident_closure_readiness(
    supervision: Mapping[str, Any] | None,
    live_report: Mapping[str, Any] | None,
    flag_evidence: Mapping[str, Any] | None,
    remediation_evidence: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assess closure readiness without closing or mutating anything."""
    current = utc(now or _now())
    incident = dict(supervision or {})
    live = dict(live_report or {})
    flag = dict(flag_evidence or {})
    remediation = dict(remediation_evidence or {})

    posture = str(incident.get("posture") or "")
    if (
        incident.get("incident_open") is not True
        or posture not in SUPPORTED_POSTURES
    ):
        return {
            "schema": SCHEMA,
            "status": "NO_OPEN_SUPPORTED_INCIDENT",
            "closure_review_ready": False,
            "incident_closed": False,
            "automatic_closure": False,
            "executes_action": False,
        }

    incident_digest = str(incident.get("evidence_digest") or "")
    incident_at = _parse_iso(incident.get("generated_at"))
    if not incident_digest or incident_at is None:
        return {
            "schema": SCHEMA,
            "status": "CLOSURE_BLOCKED",
            "reason": "INCIDENT_DIGEST_AND_TIMESTAMP_REQUIRED",
            "closure_review_ready": False,
            "incident_closed": False,
            "automatic_closure": False,
            "executes_action": False,
        }

    current_state = _current_evidence_state(posture, live, flag)
    blockers = list(current_state["blockers"])

    if str(remediation.get("schema") or "") != REMEDIATION_SCHEMA:
        blockers.append("REMEDIATION_EVIDENCE_SCHEMA_REQUIRED")
    if str(remediation.get("status") or "") != "CONFIRMED":
        blockers.append("CONFIRMED_REMEDIATION_EVIDENCE_REQUIRED")
    if (
        str(remediation.get("incident_evidence_digest") or "")
        != incident_digest
    ):
        blockers.append("REMEDIATION_INCIDENT_BINDING_MISMATCH")

    reviewed_at = _parse_iso(remediation.get("reviewed_at"))
    if reviewed_at is None or reviewed_at <= incident_at:
        blockers.append("REMEDIATION_MUST_POSTDATE_INCIDENT")

    current_evidence_at = _parse_iso(
        live.get("checked_at")
        or live.get("generated_at")
        or flag.get("checked_at")
        or flag.get("updated_at")
    )
    if current_evidence_at is None or current_evidence_at <= incident_at:
        blockers.append("FRESH_CURRENT_EVIDENCE_REQUIRED")

    unique_blockers = sorted(set(blockers))
    ready = not unique_blockers
    status = (
        "CLOSURE_REVIEW_READY"
        if ready
        else (
            "CONTAINED_AWAITING_REMEDIATION"
            if current_state["safely_disabled"]
            else "CLOSURE_BLOCKED"
        )
    )

    package = {
        "incident_evidence_digest": incident_digest,
        "incident_posture": posture,
        "remediation_digest": str(remediation.get("remediation_digest") or ""),
        "current_live_status": current_state["status"],
        "current_flag_state": current_state["flag_state"],
        "current_evidence_at": (
            current_evidence_at.isoformat() if current_evidence_at else ""
        ),
        "reviewed_at": reviewed_at.isoformat() if reviewed_at else "",
    }
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": unique_blockers[0] if unique_blockers else "",
        "blockers": unique_blockers,
        "closure_review_ready": ready,
        "closure_package_digest": digest(package) if ready else "",
        "current_state": current_state,
        "incident_evidence_digest": incident_digest,
        "remediation_digest": str(remediation.get("remediation_digest") or ""),
        "assessed_at": current.isoformat(),
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "real_recovery_evidence_confirmed": ready,
        "real_recovery_confirmed": False,
        "reactivation_authorized": False,
        "feature_flag_modified": False,
        "runtime_modified": False,
        "global_worker_tick_executed": False,
        "external_business_action_executed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }


def closure_review_record(
    assessment: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a session-only record for human review; never marks CLOSED."""
    report = dict(assessment or {})
    ready = report.get("closure_review_ready") is True
    return {
        "schema": SCHEMA,
        "status": "READY_FOR_HUMAN_CLOSURE_REVIEW" if ready else "NOT_READY",
        "closure_package_digest": str(
            report.get("closure_package_digest") or ""
        ),
        "incident_evidence_digest": str(
            report.get("incident_evidence_digest") or ""
        ),
        "remediation_digest": str(report.get("remediation_digest") or ""),
        "incident_closed": False,
        "automatic_closure": False,
        "human_closure_required": True,
        "persistent": False,
        "session_only": True,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REMEDIATION_SCHEMA",
    "CONFIRMATION_PHRASE",
    "SUPPORTED_POSTURES",
    "prepare_remediation_evidence",
    "assess_incident_closure_readiness",
    "closure_review_record",
]
