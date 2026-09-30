"""AION Backup & Recovery Policy V1.

Read-only governance for AtlasQuant/AION continuity.
It audits repository backup/recovery controls and prepares bounded backup/restore
review packets. It never creates a backup, restores data, changes runtime,
deletes files, calls a provider, or executes external actions.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import re

from atlasquant_aion_checkpoint_latest import validate_latest_checkpoint

SCHEMA = "ATLASQUANT_AION_BACKUP_RECOVERY_POLICY_V1"
VERSION = "1"

SOURCE_BACKUP_WORKFLOW = ".github/workflows/atlasquant-source-backup.yml"
CRITICAL_REPOSITORY_FILES = (
    "CONTEXTO_DO_PROJETO.md",
    "docs/continuidade/checkpoint_mestre_latest.json",
    "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-30.md",
    "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-30.json",
    "atlasquant_aion_recovery.py",
    "atlasquant_aion_memory.py",
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def backup_recovery_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BACKUP_RECOVERY_POLICY_DEFINED",
        "required_backup_layers": [
            "SOURCE_ARCHIVE_WITH_SHA256",
            "CHECKPOINT_VERSION_HISTORY",
            "SECONDARY_COPY_SEPARATE_FROM_PRIMARY_REFERENCE",
        ],
        "source_archive_must_self_test": True,
        "source_archive_must_verify_sha256": True,
        "critical_files_must_be_present": True,
        "runtime_checkpoint_kept_separate_from_source_archive": True,
        "restore_requires_integrity_check": True,
        "restore_requires_human_approval": True,
        "automatic_restore": False,
        "automatic_delete": False,
        "rpo_target_hours": None,
        "rto_target_hours": None,
        "rpo_rto_state": "ADMIN_TARGETS_REQUIRED",
        "executes_action": False,
    }


def audit_repository_backup_readiness(
    root: Path | None = None,
) -> dict[str, Any]:
    base = _root(root)
    blockers: list[str] = []

    workflow_path = base / SOURCE_BACKUP_WORKFLOW
    workflow_text = ""
    if not workflow_path.is_file():
        blockers.append("SOURCE_BACKUP_WORKFLOW_MISSING")
    else:
        workflow_text = workflow_path.read_text(encoding="utf-8", errors="replace")

    required_workflow_markers = (
        "workflow_dispatch:",
        "branches: [main]",
        'ATLASQUANT_REAL_EXECUTION: "0"',
        "BACKUP_MANIFEST.txt",
        "sha256sum",
        "sha256sum -c",
        "unzip -t",
        "retention-days: 30",
    )
    missing_markers = [
        marker for marker in required_workflow_markers
        if marker not in workflow_text
    ]
    if missing_markers:
        blockers.append("SOURCE_BACKUP_SELF_TEST_INCOMPLETE")

    missing_files = [
        rel for rel in CRITICAL_REPOSITORY_FILES
        if not (base / rel).is_file()
    ]
    if missing_files:
        blockers.append("CRITICAL_REPOSITORY_FILES_MISSING")

    checkpoint_validation = validate_latest_checkpoint(base)
    if checkpoint_validation.get("ok") is not True:
        blockers.append("LATEST_CHECKPOINT_VALIDATION_FAILED")

    runtime_recovery_present = (base / "atlasquant_aion_recovery.py").is_file()
    if not runtime_recovery_present:
        blockers.append("RUNTIME_RECOVERY_MODULE_MISSING")

    ready = not blockers
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "REPOSITORY_BACKUP_CONTROLS_VERIFIED"
            if ready
            else "REPOSITORY_BACKUP_CONTROLS_BLOCKED"
        ),
        "ready": ready,
        "source_backup_workflow": SOURCE_BACKUP_WORKFLOW,
        "workflow_markers_verified": not missing_markers,
        "missing_workflow_markers": missing_markers,
        "critical_repository_files": list(CRITICAL_REPOSITORY_FILES),
        "missing_critical_files": missing_files,
        "checkpoint_latest_valid": checkpoint_validation.get("ok") is True,
        "runtime_recovery_module_present": runtime_recovery_present,
        "runtime_checkpoint_in_source_archive_required": False,
        "blockers": blockers,
        "executes_action": False,
    }


def define_recovery_targets(
    *,
    rpo_target_hours: Any,
    rto_target_hours: Any,
) -> dict[str, Any]:
    def _hours(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if 0 < number <= 720 else None

    rpo = _hours(rpo_target_hours)
    rto = _hours(rto_target_hours)
    valid = rpo is not None and rto is not None

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "RECOVERY_TARGETS_DEFINED" if valid else "RECOVERY_TARGETS_INVALID",
        "rpo_target_hours": rpo,
        "rto_target_hours": rto,
        "targets_are_internal_planning_not_sla": True,
        "executes_action": False,
    }


def backup_set_review(
    *,
    source_sha: Any,
    source_backup_ref: Any,
    checkpoint_digest: Any,
    runtime_checkpoint_history_ref: Any,
    secondary_copy_ref: Any,
    recovery_targets: Mapping[str, Any] | None,
    operator: Any,
) -> dict[str, Any]:
    sha = _clean(source_sha, 64).lower()
    source_ref = _clean(source_backup_ref, 300)
    checkpoint = _clean(checkpoint_digest, 128).lower()
    runtime_ref = _clean(runtime_checkpoint_history_ref, 300)
    secondary_ref = _clean(secondary_copy_ref, 300)
    actor = _clean(operator, 120)
    targets = dict(recovery_targets or {}) if isinstance(recovery_targets, Mapping) else {}

    gates = {
        "source_sha_valid": bool(_SHA40.fullmatch(sha)),
        "source_backup_ref_present": bool(source_ref),
        "checkpoint_digest_valid": bool(_DIGEST64.fullmatch(checkpoint)),
        "runtime_checkpoint_history_ref_present": bool(runtime_ref),
        "secondary_copy_ref_present": bool(secondary_ref),
        "secondary_copy_is_distinct": bool(
            secondary_ref
            and source_ref
            and secondary_ref != source_ref
            and secondary_ref != runtime_ref
        ),
        "recovery_targets_defined": targets.get("state") == "RECOVERY_TARGETS_DEFINED",
        "operator_present": bool(actor),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "source_sha": sha,
        "source_backup_ref": source_ref,
        "checkpoint_digest": checkpoint,
        "runtime_checkpoint_history_ref": runtime_ref,
        "secondary_copy_ref": secondary_ref,
        "rpo_target_hours": targets.get("rpo_target_hours"),
        "rto_target_hours": targets.get("rto_target_hours"),
        "operator": actor,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BACKUP_SET_REVIEW_READY" if ready else "BACKUP_SET_INCOMPLETE",
        "gates": gates,
        "blockers": blockers,
        "backup_set_digest": _digest(payload) if payload else "",
        "source_sha": sha if ready else "",
        "source_backup_ref": source_ref if ready else "",
        "checkpoint_digest": checkpoint if ready else "",
        "runtime_checkpoint_history_ref": runtime_ref if ready else "",
        "secondary_copy_ref": secondary_ref if ready else "",
        "rpo_target_hours": targets.get("rpo_target_hours") if ready else None,
        "rto_target_hours": targets.get("rto_target_hours") if ready else None,
        "backup_created": False,
        "restore_authorized": False,
        "executes_action": False,
    }


def prepare_restore_drill(
    backup_set: Mapping[str, Any] | None,
    *,
    target_environment: Any,
    reason: Any,
) -> dict[str, Any]:
    row = dict(backup_set or {}) if isinstance(backup_set, Mapping) else {}
    environment = _clean(target_environment, 80).lower()
    reason_text = _clean(reason, 500)
    allowed_env = environment in {"sandbox", "local", "staging"}

    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "BACKUP_SET_REVIEW_READY"
        and _DIGEST64.fullmatch(_clean(row.get("backup_set_digest"), 128).lower())
        and allowed_env
        and reason_text
    )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "RESTORE_DRILL_READY" if ready else "RESTORE_DRILL_BLOCKED",
        "backup_set_digest": row.get("backup_set_digest") if ready else "",
        "target_environment": environment if ready else "",
        "reason": reason_text if ready else "",
        "simulation_only": True,
        "production_restore_allowed": False,
        "restore_authorized": False,
        "runtime_modified": False,
        "files_written": False,
        "executes_action": False,
    }


def restore_drill_verification_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "RESTORE_DRILL_EVIDENCE_REQUIRED",
        "required_checks": [
            "archive_sha256_verified",
            "archive_extract_test_passed",
            "critical_files_present",
            "checkpoint_digest_verified",
            "runtime_checkpoint_integrity_verified",
            "application_tests_passed",
            "ui_smoke_passed",
            "mobile_dom_passed",
            "no_production_write",
        ],
        "real_restore_confirmed": False,
        "production_restore_authorized": False,
        "automatic_restore": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "SOURCE_BACKUP_WORKFLOW",
    "CRITICAL_REPOSITORY_FILES",
    "backup_recovery_policy",
    "audit_repository_backup_readiness",
    "define_recovery_targets",
    "backup_set_review",
    "prepare_restore_drill",
    "restore_drill_verification_template",
]
