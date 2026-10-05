"""AION operational resilience / disaster-recovery readiness gate.

Pure evidence evaluator for SLO, error-budget, RPO/RTO, backup freshness and
restore-drill evidence. It never restores data, deploys, changes production,
calls providers, starts workers or grants execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re

SCHEMA = "ATLASQUANT_AION_OPERATIONAL_RESILIENCE_DR_V1"
MAX_COMPONENTS = 128
MAX_BACKUPS = 128
MAX_DRILLS = 128
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive(value: Any) -> float | None:
    out = _number(value)
    if out is None or out <= 0:
        return None
    return out


def _nonnegative(value: Any) -> float | None:
    out = _number(value)
    if out is None or out < 0:
        return None
    return out


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out < 1 or not out.is_integer():
        return None
    return int(out)


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _age_seconds(checked_at: datetime, value: Any) -> float | None:
    parsed = _parse_ts(value)
    if parsed is None:
        return None
    delta = (checked_at - parsed).total_seconds()
    if delta < 0:
        return None
    return round(delta, 6)


def _duration_seconds(start: Any, end: Any) -> float | None:
    started = _parse_ts(start)
    completed = _parse_ts(end)
    if started is None or completed is None:
        return None
    delta = (completed - started).total_seconds()
    if delta < 0:
        return None
    return round(delta, 6)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _refs(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:80]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw or {})
    return {
        "owner_id": _text(item.get("owner_id"), 100),
        "tenant_id": _text(item.get("tenant_id"), 100),
        "workspace_id": _text(item.get("workspace_id"), 100),
    }


def _scope_ok(raw: Mapping[str, Any], trusted: Mapping[str, str]) -> bool:
    return all(_text(raw.get(key), 100) == trusted.get(key, "") for key in trusted)


def _strict_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def normalize_resilience_policy(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    item = dict(raw or {})
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")

    policy_id = _text(item.get("policy_id"), 120)
    revision = _positive_int(item.get("revision"))
    if item.get("state") != "VERIFIED":
        blockers.append("POLICY_NOT_VERIFIED")
    if not policy_id:
        blockers.append("POLICY_ID_REQUIRED")
    if revision is None:
        blockers.append("POLICY_REVISION_INVALID")
    if not _scope_ok(item, trusted):
        blockers.append("POLICY_SCOPE_MISMATCH")

    availability = _positive(item.get("availability_slo_pct"))
    if availability is None or availability > 100:
        blockers.append("AVAILABILITY_SLO_INVALID")

    error_budget = _nonnegative(item.get("max_error_budget_burn_pct"))
    if error_budget is None or error_budget > 100:
        blockers.append("ERROR_BUDGET_LIMIT_INVALID")

    rpo = _positive(item.get("rpo_seconds"))
    rto = _positive(item.get("rto_seconds"))
    max_drill_age = _positive(item.get("max_drill_age_seconds"))
    max_heartbeat_age = _positive(item.get("max_heartbeat_age_seconds"))
    min_drills = _positive_int(item.get("min_successful_drills"))
    for name, value in (
        ("RPO", rpo),
        ("RTO", rto),
        ("DRILL_AGE", max_drill_age),
        ("HEARTBEAT_AGE", max_heartbeat_age),
        ("SUCCESSFUL_DRILLS", min_drills),
    ):
        if value is None:
            blockers.append(f"{name}_POLICY_INVALID")

    required = item.get("required_components")
    components: list[str] = []
    if not isinstance(required, (list, tuple)):
        blockers.append("REQUIRED_COMPONENTS_INVALID")
    else:
        for raw_name in required[:MAX_COMPONENTS]:
            name = _text(raw_name, 120)
            if not name or name in components:
                blockers.append("REQUIRED_COMPONENTS_INVALID")
                continue
            components.append(name)
        if not components:
            blockers.append("REQUIRED_COMPONENTS_INVALID")

    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "policy_id": policy_id,
        "revision": revision,
        **trusted,
        "availability_slo_pct": availability,
        "max_error_budget_burn_pct": error_budget,
        "rpo_seconds": rpo,
        "rto_seconds": rto,
        "max_drill_age_seconds": max_drill_age,
        "max_heartbeat_age_seconds": max_heartbeat_age,
        "min_successful_drills": min_drills,
        "required_components": components,
        "automatic_restore": False,
        "automatic_deploy": False,
        "executes_action": False,
    }


def _normalize_service(
    raw: Mapping[str, Any],
    *,
    trusted: Mapping[str, str],
    checked_at: datetime,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not _scope_ok(raw, trusted):
        blockers.append("SCOPE_MISMATCH")

    component = _text(raw.get("component"), 120)
    if not component:
        blockers.append("COMPONENT_REQUIRED")

    state = _text(raw.get("state"), 40).upper()
    availability = _number(raw.get("availability_pct"))
    burn = _number(raw.get("error_budget_burn_pct"))
    heartbeat_age = _age_seconds(checked_at, raw.get("heartbeat_at"))
    refs = _refs(raw.get("evidence_refs"))

    if state != "HEALTHY":
        blockers.append("COMPONENT_NOT_HEALTHY")
    if availability is None or availability < 0 or availability > 100:
        blockers.append("AVAILABILITY_INVALID")
    elif availability < float(policy["availability_slo_pct"]):
        blockers.append("AVAILABILITY_SLO_BREACH")
    if burn is None or burn < 0:
        blockers.append("ERROR_BUDGET_BURN_INVALID")
    elif burn > float(policy["max_error_budget_burn_pct"]):
        blockers.append("ERROR_BUDGET_EXHAUSTED")
    if heartbeat_age is None:
        blockers.append("HEARTBEAT_TIMESTAMP_INVALID")
    elif heartbeat_age > float(policy["max_heartbeat_age_seconds"]):
        blockers.append("HEARTBEAT_STALE")
    if not refs:
        blockers.append("SERVICE_EVIDENCE_REQUIRED")

    return {
        "component": component,
        "state": state or "UNKNOWN",
        "availability_pct": availability,
        "error_budget_burn_pct": burn,
        "heartbeat_age_seconds": heartbeat_age,
        "evidence_refs": refs,
        "blockers": list(dict.fromkeys(blockers)),
        "ready": not blockers,
    }


def _normalize_backup(
    raw: Mapping[str, Any],
    *,
    trusted: Mapping[str, str],
    checked_at: datetime,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not _scope_ok(raw, trusted):
        blockers.append("SCOPE_MISMATCH")
    backup_id = _text(raw.get("backup_id"), 160)
    if not backup_id:
        blockers.append("BACKUP_ID_REQUIRED")

    completed_age = _age_seconds(checked_at, raw.get("completed_at"))
    if completed_age is None:
        blockers.append("BACKUP_TIMESTAMP_INVALID")
    elif completed_age > float(policy["rpo_seconds"]):
        blockers.append("RPO_BREACH")

    source_revision = _text(raw.get("source_revision"), 160)
    source_digest = _text(raw.get("source_digest"), 80).lower()
    if not source_revision:
        blockers.append("SOURCE_REVISION_REQUIRED")
    if not _SHA256_RE.fullmatch(source_digest):
        blockers.append("SOURCE_DIGEST_INVALID")

    integrity = _text(raw.get("integrity_state"), 40).upper()
    if integrity != "VERIFIED":
        blockers.append("BACKUP_INTEGRITY_NOT_VERIFIED")

    encrypted = _strict_bool(raw.get("encrypted"))
    key_available = _strict_bool(raw.get("key_available"))
    if encrypted is not True:
        blockers.append("BACKUP_ENCRYPTION_REQUIRED")
    if key_available is not True:
        blockers.append("BACKUP_KEY_UNAVAILABLE")
    if not _text(raw.get("key_ref"), 160):
        blockers.append("BACKUP_KEY_REF_REQUIRED")
    refs = _refs(raw.get("evidence_refs"))
    if not refs:
        blockers.append("BACKUP_EVIDENCE_REQUIRED")

    return {
        "backup_id": backup_id,
        "completed_age_seconds": completed_age,
        "source_revision": source_revision,
        "source_digest": source_digest,
        "integrity_state": integrity or "UNKNOWN",
        "encrypted": encrypted is True,
        "key_available": key_available is True,
        "key_ref": _text(raw.get("key_ref"), 160),
        "evidence_refs": refs,
        "blockers": list(dict.fromkeys(blockers)),
        "ready": not blockers,
    }


def _normalize_drill(
    raw: Mapping[str, Any],
    *,
    trusted: Mapping[str, str],
    checked_at: datetime,
    policy: Mapping[str, Any],
    backups: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not _scope_ok(raw, trusted):
        blockers.append("SCOPE_MISMATCH")

    drill_id = _text(raw.get("drill_id"), 160)
    backup_id = _text(raw.get("backup_id"), 160)
    if not drill_id:
        blockers.append("DRILL_ID_REQUIRED")
    if not backup_id:
        blockers.append("DRILL_BACKUP_ID_REQUIRED")

    completed_age = _age_seconds(checked_at, raw.get("completed_at"))
    duration = _duration_seconds(raw.get("started_at"), raw.get("completed_at"))
    if completed_age is None:
        blockers.append("DRILL_TIMESTAMP_INVALID")
    elif completed_age > float(policy["max_drill_age_seconds"]):
        blockers.append("DRILL_STALE")
    if duration is None:
        blockers.append("DRILL_DURATION_INVALID")
    elif duration > float(policy["rto_seconds"]):
        blockers.append("RTO_BREACH")

    backup = backups.get(backup_id)
    if backup is None:
        blockers.append("BACKUP_REFERENCE_NOT_FOUND")
    else:
        if backup.get("ready") is not True:
            blockers.append("BACKUP_REFERENCE_NOT_READY")
        recovered_revision = _text(raw.get("recovered_revision"), 160)
        recovered_digest = _text(raw.get("recovered_digest"), 80).lower()
        if recovered_revision != backup.get("source_revision"):
            blockers.append("RECOVERED_REVISION_MISMATCH")
        if recovered_digest != backup.get("source_digest"):
            blockers.append("RECOVERED_DIGEST_MISMATCH")

    integrity = _text(raw.get("integrity_state"), 40).upper()
    if integrity != "VERIFIED":
        blockers.append("RESTORE_INTEGRITY_NOT_VERIFIED")
    if _strict_bool(raw.get("application_boot_ok")) is not True:
        blockers.append("RESTORED_APPLICATION_BOOT_NOT_VERIFIED")
    if _strict_bool(raw.get("health_check_ok")) is not True:
        blockers.append("RESTORED_HEALTH_NOT_VERIFIED")
    if _strict_bool(raw.get("production_mutation")) is not False:
        blockers.append("DRILL_PRODUCTION_MUTATION_FORBIDDEN")
    if _strict_bool(raw.get("provider_called")) is not False:
        blockers.append("DRILL_PROVIDER_CALL_FORBIDDEN")
    if _strict_bool(raw.get("external_action_executed")) is not False:
        blockers.append("DRILL_EXTERNAL_ACTION_FORBIDDEN")

    refs = _refs(raw.get("evidence_refs"))
    if not refs:
        blockers.append("DRILL_EVIDENCE_REQUIRED")

    return {
        "drill_id": drill_id,
        "backup_id": backup_id,
        "completed_age_seconds": completed_age,
        "restore_duration_seconds": duration,
        "integrity_state": integrity or "UNKNOWN",
        "application_boot_ok": _strict_bool(raw.get("application_boot_ok")) is True,
        "health_check_ok": _strict_bool(raw.get("health_check_ok")) is True,
        "production_mutation": _strict_bool(raw.get("production_mutation")),
        "provider_called": _strict_bool(raw.get("provider_called")),
        "external_action_executed": _strict_bool(raw.get("external_action_executed")),
        "evidence_refs": refs,
        "blockers": list(dict.fromkeys(blockers)),
        "successful": not blockers,
    }


def evaluate_operational_resilience(
    *,
    trusted_scope: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    service_observations: Sequence[Mapping[str, Any]] | None,
    backups: Sequence[Mapping[str, Any]] | None,
    recovery_drills: Sequence[Mapping[str, Any]] | None,
    checked_at: Any,
) -> dict[str, Any]:
    checked = _parse_ts(checked_at)
    blockers: list[str] = []
    if checked is None:
        blockers.append("CHECKED_AT_INVALID")
        checked = datetime(1970, 1, 1, tzinfo=timezone.utc)

    trusted = _scope(trusted_scope)
    normalized_policy = normalize_resilience_policy(policy, trusted_scope=trusted)
    blockers.extend(normalized_policy["blockers"])

    if normalized_policy["state"] != "VERIFIED":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": list(dict.fromkeys(blockers)),
            "checked_at": _text(checked_at, 80),
            "scope": trusted,
            "policy": normalized_policy,
            "services": [],
            "backups": [],
            "recovery_drills": [],
            "successful_drills": 0,
            "release_claim_allowed": False,
            "recovery_authorized": False,
            "automatic_restore": False,
            "automatic_deploy": False,
            "executes_action": False,
        }

    services: list[dict[str, Any]] = []
    seen_components: set[str] = set()
    for raw in list(service_observations or [])[:MAX_COMPONENTS]:
        if not isinstance(raw, Mapping):
            blockers.append("SERVICE_OBSERVATION_INVALID")
            continue
        row = _normalize_service(raw, trusted=trusted, checked_at=checked, policy=normalized_policy)
        if row["component"] in seen_components:
            row["blockers"] = list(dict.fromkeys(row["blockers"] + ["DUPLICATE_COMPONENT"]))
            row["ready"] = False
        if row["component"]:
            seen_components.add(row["component"])
        services.append(row)

    required = set(normalized_policy["required_components"])
    present = {row["component"] for row in services if row["component"]}
    for missing in sorted(required - present):
        blockers.append(f"REQUIRED_COMPONENT_MISSING:{missing}")
    for row in services:
        blockers.extend(f"SERVICE:{row['component']}:{reason}" for reason in row["blockers"])

    backup_rows: list[dict[str, Any]] = []
    backup_by_id: dict[str, dict[str, Any]] = {}
    for raw in list(backups or [])[:MAX_BACKUPS]:
        if not isinstance(raw, Mapping):
            blockers.append("BACKUP_EVIDENCE_INVALID")
            continue
        row = _normalize_backup(raw, trusted=trusted, checked_at=checked, policy=normalized_policy)
        if row["backup_id"] in backup_by_id:
            row["blockers"] = list(dict.fromkeys(row["blockers"] + ["DUPLICATE_BACKUP_ID"]))
            row["ready"] = False
        if row["backup_id"]:
            backup_by_id[row["backup_id"]] = row
        backup_rows.append(row)
        blockers.extend(f"BACKUP:{row['backup_id']}:{reason}" for reason in row["blockers"])
    if not backup_rows:
        blockers.append("BACKUP_EVIDENCE_REQUIRED")

    drill_rows: list[dict[str, Any]] = []
    seen_drills: set[str] = set()
    for raw in list(recovery_drills or [])[:MAX_DRILLS]:
        if not isinstance(raw, Mapping):
            blockers.append("DRILL_EVIDENCE_INVALID")
            continue
        row = _normalize_drill(
            raw,
            trusted=trusted,
            checked_at=checked,
            policy=normalized_policy,
            backups=backup_by_id,
        )
        if row["drill_id"] in seen_drills:
            row["blockers"] = list(dict.fromkeys(row["blockers"] + ["DUPLICATE_DRILL_ID"]))
            row["successful"] = False
        if row["drill_id"]:
            seen_drills.add(row["drill_id"])
        drill_rows.append(row)
        blockers.extend(f"DRILL:{row['drill_id']}:{reason}" for reason in row["blockers"])

    successful = sum(1 for row in drill_rows if row["successful"])
    if successful < int(normalized_policy["min_successful_drills"]):
        blockers.append("SUCCESSFUL_DRILL_COUNT_INSUFFICIENT")

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_ADMIN_REVIEW" if not blockers else "BLOCKED"
    material = {
        "scope": trusted,
        "policy_id": normalized_policy["policy_id"],
        "policy_revision": normalized_policy["revision"],
        "checked_at": _text(checked_at, 80),
        "services": services,
        "backups": backup_rows,
        "drills": drill_rows,
        "blockers": blockers,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": blockers,
        "checked_at": _text(checked_at, 80),
        "scope": trusted,
        "policy": normalized_policy,
        "services": services,
        "backups": backup_rows,
        "recovery_drills": drill_rows,
        "successful_drills": successful,
        "readiness_digest": _digest(material),
        "requires_admin_review": state == "READY_FOR_ADMIN_REVIEW",
        "release_claim_allowed": False,
        "recovery_authorized": False,
        "production_restore_executed": False,
        "automatic_restore": False,
        "automatic_deploy": False,
        "provider_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def disaster_recovery_runbook(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(snapshot or {})
    return {
        "schema": SCHEMA,
        "state": "PLAN_READY" if data.get("state") == "READY_FOR_ADMIN_REVIEW" else "BLOCKED",
        "readiness_digest": _text(data.get("readiness_digest"), 80),
        "steps": [
            "Preservar evidências e congelar qualquer mutation path afetado.",
            "Confirmar incidente, escopo e autoridade do HUMAN_OWNER.",
            "Selecionar apenas backup com integridade, criptografia e chave verificadas.",
            "Reexecutar preflight de recovery e comparar revision/digest esperado.",
            "Executar restore somente em gate operacional explicitamente autorizado.",
            "Verificar boot, health, integridade e reconciliação antes de reabrir capability.",
            "Registrar RPO/RTO observado, evidências e decisão humana de encerramento.",
        ],
        "requires_human_owner": True,
        "requires_incident_control_gate": True,
        "automatic_restore": False,
        "automatic_reenable": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "normalize_resilience_policy",
    "evaluate_operational_resilience",
    "disaster_recovery_runbook",
]
