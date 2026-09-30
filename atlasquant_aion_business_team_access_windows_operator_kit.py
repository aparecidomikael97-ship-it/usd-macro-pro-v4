"""AION BUSINESS Team Access Windows Operator Kit V1.

Read-only policy and report validator for the local Windows sandbox operator
flow. This module never starts Docker, never writes secrets and never invokes
PowerShell. It validates only caller-supplied readiness reports.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping
import json
import re

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_WINDOWS_OPERATOR_KIT_V1"
READINESS_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_V1"
)
VERSION = "1"

REQUIRED_CHECKS = (
    "env_file_exists",
    "sandbox_marker",
    "placeholders_absent",
    "docker_cli",
    "docker_compose",
    "compose_config_valid",
    "production_name_absent",
)

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _timestamp_valid(value: Any) -> bool:
    token = _clean(value, 100)
    if not token:
        return False
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return False
    return parsed.tzinfo is not None


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def windows_operator_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_WINDOWS_OPERATOR_POLICY_DEFINED",
        "required_checks": list(REQUIRED_CHECKS),
        "secret_bootstrap_plan_only_default": True,
        "sandbox_start_plan_only_default": True,
        "explicit_apply_required_for_secret_file": True,
        "explicit_apply_start_required": True,
        "baseline_collection_separate_switch_required": True,
        "secret_values_may_be_printed": False,
        "production_targets_allowed": False,
        "lifecycle_execution_included": False,
        "executes_action": False,
    }


def validate_windows_operator_readiness(
    report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(report)
    checks = _mapping(row.get("checks"))
    operator_session_id = _clean(row.get("operator_session_id"), 64).lower()

    gates = {
        "schema_valid": row.get("schema") == READINESS_SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION",
        "captured_at_valid": _timestamp_valid(row.get("captured_at")),
        "operator_session_id_valid": bool(_SESSION32.fullmatch(operator_session_id)),
        "required_checks_complete": all(
            checks.get(name) is True for name in REQUIRED_CHECKS
        ),
        "secrets_absent": row.get("secrets_included") is False,
        "container_not_started_by_readiness": row.get("container_started") is False,
        "production_not_targeted": row.get("production_targeted") is False,
        "external_side_effects_absent": row.get("external_side_effects_executed") is False,
        "local_report_declared": row.get("local_report_written") is True,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    canonical = {
        "captured_at": _clean(row.get("captured_at"), 100),
        "operator_session_id": operator_session_id,
        "checks": {name: checks.get(name) is True for name in REQUIRED_CHECKS},
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION"
            if ready
            else "TEAM_ACCESS_WINDOWS_OPERATOR_READINESS_REJECTED"
        ),
        "gates": gates,
        "blockers": blockers,
        "readiness_digest": _digest(canonical) if ready else "",
        "captured_at": _clean(row.get("captured_at"), 100) if ready else "",
        "operator_session_id": operator_session_id if ready else "",
        "secret_values_returned": False,
        "sandbox_start_authorized": False,
        "baseline_collection_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def baseline_operator_handoff(
    readiness_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(readiness_review)
    digest = _clean(row.get("readiness_digest"), 80).lower()
    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION"
        and _DIGEST64.fullmatch(digest)
        and row.get("sandbox_start_authorized") is False
        and row.get("baseline_collection_authorized") is False
        and row.get("production_authorized") is False
        and row.get("executes_action") is False
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "WINDOWS_OPERATOR_MANUAL_APPLY_REQUIRED"
            if ready
            else "WINDOWS_OPERATOR_HANDOFF_BLOCKED"
        ),
        "readiness_digest": digest if ready else "",
        "next_manual_commands": [
            ".\\Prepare-TeamAccessSandboxEnv.ps1",
            ".\\Prepare-TeamAccessSandboxEnv.ps1 -Apply",
            ".\\Invoke-TeamAccessSandboxOperator.ps1",
            ".\\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart",
            ".\\Invoke-TeamAccessSandboxOperator.ps1 -ApplyStart -CollectBaseline",
        ] if ready else [],
        "manual_apply_required": True,
        "automatic_secret_write": False,
        "automatic_start": False,
        "automatic_baseline_collection": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "READINESS_SCHEMA",
    "VERSION",
    "REQUIRED_CHECKS",
    "windows_operator_policy",
    "validate_windows_operator_readiness",
    "baseline_operator_handoff",
]
