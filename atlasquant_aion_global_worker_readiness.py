"""Read-only activation readiness gate for AION Global Worker V1.

This module never arms, pauses, kills, saves or activates the real worker.
It inspects runtime evidence, the existing scheduler pulse, feature-flag posture
and an in-memory protocol simulation so activation can be decided separately.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from atlasquant_aion_github_io import github_get
from atlasquant_aion_global_worker import (
    GLOBAL_WORKER_NAMESPACE,
    _claim_state,
    global_worker_integrity,
    load_global_worker_state,
    stage_arm_global_worker,
    stage_kill_global_worker,
)
from atlasquant_aion_global_worker_arming import (
    CONFIRMATION_PHRASE,
    approve_global_worker_arming_plan,
    prepare_global_worker_arming_plan,
)
from atlasquant_aion_memory import (
    RuntimeConfig,
    checkpoint_integrity_report,
    config_from_mapping,
    load_runtime_checkpoint,
)
from atlasquant_runtime_store import evaluate_runtime_branch


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_ACTIVATION_READINESS_V1"
AUTOPILOT_WORKFLOW = ".github/workflows/autopilot-v107.yml"
GLOBAL_FLAG = "ATLASQUANT_AION_GLOBAL_WORKER_ENABLED"
MIN_SUCCESSFUL_PULSES = 3
MAX_PULSE_AGE_SECONDS = 5400


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return _utc(parsed)
    except Exception:
        return None


def feature_flag_state(raw: Any) -> str:
    text = str(raw or "").strip().casefold()
    if not text:
        return "UNSET"
    if text in {"0", "false", "no", "off"}:
        return "DISABLED"
    if text in {"1", "true", "yes", "on"}:
        return "ENABLED"
    return "INVALID"


def workflow_contract(workflow_text: str) -> dict[str, Any]:
    text = str(workflow_text or "")
    cron_count = text.count("cron:")
    worker_step = "AION Global Worker tick" in text
    condition = "vars.ATLASQUANT_AION_GLOBAL_WORKER_ENABLED == '1'" in text
    tick_command = "python atlasquant_aion_global_worker.py --tick" in text
    runtime_branch = 'GITHUB_DATA_BRANCH: "atlasquant-runtime"' in text
    write_permission = "contents: write" in text
    return {
        "state": (
            "PASS"
            if cron_count == 1
            and worker_step
            and condition
            and tick_command
            and runtime_branch
            else "FAIL"
        ),
        "cron_count": cron_count,
        "existing_pulse_reused": cron_count == 1,
        "worker_step_present": worker_step,
        "feature_flag_condition_present": condition,
        "tick_command_present": tick_command,
        "runtime_branch_explicit": runtime_branch,
        "workflow_contents_write": write_permission,
        "additional_cron_detected": cron_count != 1,
    }


def pulse_health(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    current = _utc(now)
    pulses = [
        dict(row)
        for row in list(rows or [])
        if isinstance(row, Mapping)
        and str(row.get("event") or "") == "schedule"
    ]
    pulses.sort(
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )
    recent = pulses[:5]
    completed = [
        row for row in recent
        if str(row.get("status") or "") == "completed"
    ]
    successes = [
        row for row in completed
        if str(row.get("conclusion") or "") == "success"
    ]

    latest = recent[0] if recent else {}
    latest_created = _parse_iso(latest.get("created_at")) if latest else None
    latest_age_seconds = (
        max(0, int((current - latest_created).total_seconds()))
        if latest_created is not None
        else None
    )
    latest_status = str(latest.get("status") or "")
    latest_conclusion = str(latest.get("conclusion") or "")
    latest_is_active = latest_status in {"queued", "in_progress"}

    latest_completed = completed[0] if completed else {}
    completed_created = (
        _parse_iso(latest_completed.get("created_at"))
        if latest_completed
        else None
    )
    completed_age_seconds = (
        max(0, int((current - completed_created).total_seconds()))
        if completed_created is not None
        else None
    )
    completed_conclusion = str(
        latest_completed.get("conclusion") or ""
    )

    stale_active = []
    for row in recent:
        if str(row.get("status") or "") not in {"queued", "in_progress"}:
            continue
        row_created = _parse_iso(row.get("created_at"))
        row_age = (
            max(0, int((current - row_created).total_seconds()))
            if row_created is not None
            else None
        )
        if row_age is None or row_age > MAX_PULSE_AGE_SECONDS:
            stale_active.append(row)

    latest_observation_ok = bool(
        latest_created is not None
        and latest_age_seconds is not None
        and latest_age_seconds <= MAX_PULSE_AGE_SECONDS
        and not stale_active
        and (
            latest_is_active
            or (
                latest_status == "completed"
                and latest_conclusion == "success"
            )
        )
    )
    latest_completed_ok = bool(
        completed_created is not None
        and completed_age_seconds is not None
        and completed_age_seconds <= MAX_PULSE_AGE_SECONDS
        and completed_conclusion == "success"
    )
    healthy = bool(
        len(successes) >= MIN_SUCCESSFUL_PULSES
        and latest_observation_ok
        and latest_completed_ok
    )
    return {
        "state": "PASS" if healthy else "BLOCKED",
        "observed": len(recent),
        "successful": len(successes),
        "minimum_successful": MIN_SUCCESSFUL_PULSES,
        "latest_created_at": latest_created.isoformat() if latest_created else "",
        "latest_age_seconds": latest_age_seconds,
        "latest_status": latest_status,
        "latest_conclusion": latest_conclusion,
        "latest_is_active": latest_is_active,
        "stale_active_count": len(stale_active),
        "latest_completed_created_at": (
            completed_created.isoformat() if completed_created else ""
        ),
        "latest_completed_age_seconds": completed_age_seconds,
        "latest_completed_conclusion": completed_conclusion,
        "max_age_seconds": MAX_PULSE_AGE_SECONDS,
    }


def _shadow_access() -> dict[str, Any]:
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "aion-readiness-shadow",
            "role": "ADMIN",
            "credential_fingerprint": "aion-readiness-shadow-fingerprint-000000000000",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


def protocol_shadow_probe(*, now: datetime) -> dict[str, Any]:
    """Exercise lease/fence/kill semantics entirely in memory."""
    current = _utc(now)
    access = _shadow_access()
    plan_result = prepare_global_worker_arming_plan(
        access,
        {},
        max_jobs=3,
        lease_seconds=600,
        approval_ttl_seconds=900,
        now=current,
    )
    approval_result = approve_global_worker_arming_plan(
        access,
        plan_result["plan"],
        confirmation=True,
        confirmation_phrase=CONFIRMATION_PHRASE,
        now=current,
    )
    armed_result = stage_arm_global_worker(
        access,
        {},
        confirmation=True,
        arming_approval=approval_result["approval"],
        max_jobs=3,
        lease_seconds=600,
        now=current,
    )
    checkpoint = deepcopy(armed_result.get("checkpoint") or {})
    state, state_status = load_global_worker_state(checkpoint)
    first, first_lease = _claim_state(
        state,
        runtime_id="shadow-runtime-a",
        now=current,
    )
    held_state, held = _claim_state(
        first,
        runtime_id="shadow-runtime-b",
        now=current + timedelta(seconds=30),
    )
    reclaimed, second_lease = _claim_state(
        first,
        runtime_id="shadow-runtime-b",
        now=current + timedelta(seconds=601),
    )
    killed = stage_kill_global_worker(
        access,
        checkpoint,
        confirmation=True,
    )
    killed_state, _ = load_global_worker_state(killed["checkpoint"])

    checks = {
        "plan_ready_in_memory_only": (
            plan_result.get("status") == "PLAN_READY"
            and plan_result.get("runtime_modified") is False
        ),
        "approval_ticket_in_memory_only": (
            approval_result.get("status") == "APPROVED_FOR_STAGING"
            and approval_result.get("runtime_modified") is False
        ),
        "armed_in_memory_only": (
            armed_result.get("status") == "STAGED_ARMED"
            and armed_result.get("external_persisted") is False
        ),
        "state_connected": state_status.get("state") == "CONNECTED",
        "first_fence_is_one": first_lease.get("fencing_token") == 1,
        "second_runtime_blocked_while_live": (
            held.get("state") == "LEASE_HELD"
            and held_state.get("digest") == first.get("digest")
        ),
        "expired_lease_reclaimed": (
            second_lease.get("state") == "CLAIMED"
            and second_lease.get("reclaimed") is True
        ),
        "fence_monotonic": second_lease.get("fencing_token") == 2,
        "crash_recovery_counted": (
            int((reclaimed.get("stats") or {}).get("crash_recoveries") or 0) == 1
        ),
        "kill_switch_staged_only": (
            killed.get("status") == "STAGED_KILLED"
            and killed.get("external_persisted") is False
            and killed_state.get("state") == "KILLED"
            and killed_state.get("kill_switch") is True
        ),
    }
    return {
        "state": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "network_called": False,
        "runtime_modified": False,
        "feature_flag_modified": False,
    }


def runtime_posture(
    runtime_result: Mapping[str, Any] | None,
    config: RuntimeConfig,
) -> dict[str, Any]:
    result = dict(runtime_result or {})
    branch = evaluate_runtime_branch(config.branch)
    status = str(result.get("status") or "UNKNOWN").upper()
    checkpoint = result.get("checkpoint")
    integrity = (
        checkpoint_integrity_report(checkpoint)
        if isinstance(checkpoint, Mapping)
        else {"state": "UNKNOWN"}
    )
    integrity_state = str(integrity.get("state") or "UNKNOWN").upper()
    has_worker = (
        isinstance(checkpoint, Mapping)
        and GLOBAL_WORKER_NAMESPACE in checkpoint
    )
    worker_state = "ABSENT"
    kill_switch = True
    worker_integrity_state = "ABSENT"
    lease_owner = ""
    lease_expires_at = ""
    if has_worker:
        raw = checkpoint.get(GLOBAL_WORKER_NAMESPACE)
        worker_integrity = global_worker_integrity(
            raw if isinstance(raw, Mapping) else None
        )
        worker_integrity_state = worker_integrity["state"]
        if worker_integrity_state == "MATCH":
            try:
                normalized, _ = load_global_worker_state(checkpoint)
                worker_state = str(normalized.get("state") or "UNKNOWN")
                kill_switch = bool(normalized.get("kill_switch", True))
                lease = (
                    normalized.get("lease")
                    if isinstance(normalized.get("lease"), Mapping)
                    else {}
                )
                lease_owner = str(lease.get("owner") or "")
                lease_expires_at = str(lease.get("expires_at") or "")
            except Exception:
                worker_state = "INVALID"
                worker_integrity_state = "MISMATCH"

    safe = bool(
        branch.safe_for_runtime_writes
        and status == "CONFIRMED"
        and str(result.get("sha") or "").strip()
        and integrity_state in {"CONFIRMED", "MIGRATION_REQUIRED"}
        and worker_integrity_state in {"ABSENT", "MATCH"}
    )
    return {
        "state": "PASS" if safe else "BLOCKED",
        "runtime_status": status,
        "runtime_branch": branch.branch,
        "runtime_branch_safe": branch.safe_for_runtime_writes,
        "runtime_sha_present": bool(str(result.get("sha") or "").strip()),
        "checkpoint_integrity": integrity_state,
        "global_worker_namespace": "PRESENT" if has_worker else "ABSENT",
        "global_worker_integrity": worker_integrity_state,
        "global_worker_state": worker_state,
        "global_kill_switch": kill_switch,
        "lease_owner_present": bool(lease_owner),
        "lease_expires_at": lease_expires_at,
    }


def activation_readiness_snapshot(
    *,
    runtime_result: Mapping[str, Any] | None,
    config: RuntimeConfig,
    feature_flag_raw: Any,
    workflow_text: str,
    pulse_rows: Sequence[Mapping[str, Any]] | None,
    now: datetime,
) -> dict[str, Any]:
    current = _utc(now)
    runtime = runtime_posture(runtime_result, config)
    workflow = workflow_contract(workflow_text)
    pulse = pulse_health(pulse_rows, now=current)
    shadow = protocol_shadow_probe(now=current)
    flag = feature_flag_state(feature_flag_raw)

    blockers: list[str] = []
    if runtime["state"] != "PASS":
        blockers.append("RUNTIME_POSTURE_NOT_CONFIRMED")
    if workflow["state"] != "PASS":
        blockers.append("WORKFLOW_CONTRACT_FAILED")
    if pulse["state"] != "PASS":
        blockers.append("SCHEDULED_PULSE_NOT_HEALTHY")
    if shadow["state"] != "PASS":
        blockers.append("SHADOW_PROTOCOL_PROBE_FAILED")
    if flag == "INVALID":
        blockers.append("FEATURE_FLAG_INVALID")

    worker_state = runtime["global_worker_state"]
    kill_switch = bool(runtime["global_kill_switch"])

    if flag == "ENABLED" and worker_state != "ARMED":
        blockers.append("FEATURE_FLAG_ENABLED_WITHOUT_PERSISTED_ARMING")
    if flag == "ENABLED" and kill_switch:
        blockers.append("FEATURE_FLAG_ENABLED_WHILE_KILL_SWITCH_ACTIVE")

    if blockers:
        stage = "BLOCKED"
    elif worker_state == "ARMED" and not kill_switch and flag in {"UNSET", "DISABLED"}:
        stage = "READY_FOR_FLAG_ENABLE"
    elif worker_state == "ARMED" and not kill_switch and flag == "ENABLED":
        stage = "ACTIVATION_ENABLED_REQUIRES_LIVE_HEARTBEAT_EVIDENCE"
    elif worker_state in {"ABSENT", "DISABLED", "PAUSED", "KILLED"} and flag in {"UNSET", "DISABLED"}:
        stage = "READY_FOR_ADMIN_ARMING"
    else:
        stage = "SAFE_NOT_READY"

    return {
        "schema": SCHEMA,
        "status": "PASS" if not blockers else "BLOCKED",
        "activation_stage": stage,
        "blockers": blockers,
        "checked_at": current.isoformat(),
        "runtime": runtime,
        "workflow": workflow,
        "pulse": pulse,
        "shadow_protocol": shadow,
        "feature_flag": {
            "name": GLOBAL_FLAG,
            "state": flag,
            "value_exposed": False,
        },
        "read_only": True,
        "runtime_modified": False,
        "feature_flag_modified": False,
        "worker_armed_by_this_check": False,
        "external_action_executed": False,
        "real_trading_enabled": False,
    }


def fetch_recent_autopilot_pulses(
    config: RuntimeConfig,
    *,
    token: str,
    timeout: float = 12.0,
    per_page: int = 5,
) -> dict[str, Any]:
    """Read recent scheduled workflow runs. Never dispatches or reruns anything."""
    if not config.repo:
        return {"status": "UNAVAILABLE", "runs": [], "reason": "repo missing"}
    url = "https://api.github.com/repos/" + config.repo + "/actions/runs"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        response = github_get(
            url,
            headers=headers,
            params={
                "branch": "main",
                "per_page": max(50, min(int(per_page) * 20, 100)),
            },
            timeout=timeout,
        )
        response.raise_for_status()
        obj = response.json()
        rows = obj.get("workflow_runs") if isinstance(obj, Mapping) else []
        safe_rows = []
        for row in list(rows or []):
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("name") or "")
            path = str(row.get("path") or "")
            event = str(row.get("event") or "")
            is_autopilot = (
                name == "AtlasQuant - Automatic Scanner + Autopilot"
                or path.endswith("/autopilot-v107.yml")
            )
            if not is_autopilot or event != "schedule":
                continue
            safe_rows.append({
                "id": row.get("id"),
                "event": event,
                "status": str(row.get("status") or ""),
                "conclusion": str(row.get("conclusion") or ""),
                "created_at": str(row.get("created_at") or ""),
                "updated_at": str(row.get("updated_at") or ""),
                "head_sha": str(row.get("head_sha") or "")[:40],
            })
            if len(safe_rows) >= max(3, min(int(per_page), 10)):
                break
        return {
            "status": "CONFIRMED" if safe_rows else "UNAVAILABLE",
            "runs": safe_rows,
            "reason": "" if safe_rows else "autopilot scheduled runs not found",
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "runs": [],
            "reason": type(exc).__name__,
        }


def _cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--workflow", default=AUTOPILOT_WORKFLOW)
    args = parser.parse_args()
    if not args.check_runtime:
        parser.error("--check-runtime is required")

    config = config_from_mapping()
    runtime = load_runtime_checkpoint(config, timeout=12.0)
    token = str(
        os.getenv("GITHUB_TOKEN_HISTORICO", "")
        or os.getenv("GITHUB_TOKEN", "")
        or ""
    ).strip()
    pulse_result = fetch_recent_autopilot_pulses(
        config,
        token=token,
        timeout=12.0,
    )
    workflow_text = Path(args.workflow).read_text(encoding="utf-8")
    report = activation_readiness_snapshot(
        runtime_result=runtime,
        config=config,
        feature_flag_raw=os.getenv("GLOBAL_WORKER_FLAG_STATE", ""),
        workflow_text=workflow_text,
        pulse_rows=pulse_result.get("runs"),
        now=datetime.now(timezone.utc),
    )
    report["pulse_source_status"] = pulse_result.get("status")
    if pulse_result.get("status") != "CONFIRMED":
        report["status"] = "BLOCKED"
        report["activation_stage"] = "BLOCKED"
        report["blockers"] = list(report["blockers"]) + ["PULSE_EVIDENCE_UNAVAILABLE"]

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())


__all__ = [
    "SCHEMA",
    "GLOBAL_FLAG",
    "feature_flag_state",
    "workflow_contract",
    "pulse_health",
    "protocol_shadow_probe",
    "runtime_posture",
    "activation_readiness_snapshot",
    "fetch_recent_autopilot_pulses",
]
