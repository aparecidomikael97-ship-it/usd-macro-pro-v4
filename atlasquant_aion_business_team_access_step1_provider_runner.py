"""AION BUSINESS Team Access Step 1 Provider Runner V1.

Defines the fail-closed preflight for a local Windows runner that may execute
exactly one sandbox Keycloak Step 1 create-user request only after an explicit
physical apply token is supplied.

This Python module itself is read-only. It performs no network or process I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_apply_plan import (
    REALM,
    RELATIVE_PATH,
    verify_step1_apply_plan,
    verify_step1_apply_plan_source_binding,
)
from atlasquant_aion_business_team_access_step1_execution_envelope import (
    verify_step1_execution_envelope,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_PROVIDER_RUNNER_V1"
VERSION = "1"
MAX_EXECUTION_ENVELOPE_AGE_SECONDS = 120

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_LOCAL_URL = re.compile(r"^http://127\.0\.0\.1:(\d{2,5})$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
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


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 100)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _local_port(base_url: Any) -> int | None:
    token = _clean(base_url, 200)
    match = _LOCAL_URL.fullmatch(token)
    if not match:
        return None
    port = int(match.group(1))
    if not 1024 <= port <= 65535:
        return None
    return port


def required_physical_apply_token(
    apply_plan: Mapping[str, Any] | None,
) -> str:
    row = _mapping(apply_plan)
    binding = verify_step1_apply_plan(row)
    digest = _clean(row.get("apply_plan_digest"), 80).lower()
    if binding.get("binding_match") is not True:
        return ""
    if not _DIGEST64.fullmatch(digest):
        return ""
    return (
        "APPLY_SANDBOX_STEP1_"
        f"{LIFECYCLE_STEP_IDS[0]}_{digest}"
    )


def provider_runner_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_PROVIDER_RUNNER_POLICY_DEFINED",
        "plan_only_default": True,
        "apply_switch_required": True,
        "exact_physical_apply_token_required": True,
        "fresh_execution_envelope_required": True,
        "max_execution_envelope_age_seconds": (
            MAX_EXECUTION_ENVELOPE_AGE_SECONDS
        ),
        "pre_post_username_lookup_required": True,
        "localhost_only": True,
        "sandbox_only": True,
        "production_allowed": False,
        "generic_language_is_physical_authorization": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "production_authorized": False,
    }


def build_provider_runner_preflight(
    execution_envelope: Mapping[str, Any] | None,
    apply_plan: Mapping[str, Any] | None,
    *,
    evaluated_at: Any,
    base_url: Any,
    sandbox_only: Any,
    production_targeted: Any,
    secrets_local: Any,
    apply_requested: Any,
    authorization_token: Any,
) -> dict[str, Any]:
    envelope = _mapping(execution_envelope)
    plan = _mapping(apply_plan)

    envelope_binding = verify_step1_execution_envelope(envelope)
    plan_binding = verify_step1_apply_plan(plan)
    source_binding = verify_step1_apply_plan_source_binding(
        envelope, plan
    )

    evaluated = _parse_time(evaluated_at)
    prepared = _parse_time(envelope.get("prepared_at"))
    age_seconds = (
        (evaluated - prepared).total_seconds()
        if evaluated is not None and prepared is not None
        else None
    )

    port = _local_port(base_url)
    digest = _clean(plan.get("apply_plan_digest"), 80).lower()
    required_token = required_physical_apply_token(plan)
    supplied_token = _clean(authorization_token, 240)
    wants_apply = apply_requested is True

    common_gates = {
        "execution_envelope_binding_match": envelope_binding.get(
            "binding_match"
        ) is True,
        "apply_plan_binding_match": plan_binding.get(
            "binding_match"
        ) is True,
        "apply_plan_source_binding_match": source_binding.get(
            "binding_match"
        ) is True,
        "apply_plan_digest_valid": bool(_DIGEST64.fullmatch(digest)),
        "evaluated_at_valid": evaluated is not None,
        "envelope_prepared_at_valid": prepared is not None,
        "envelope_not_future": bool(
            age_seconds is not None and age_seconds >= 0
        ),
        "execution_envelope_fresh": bool(
            age_seconds is not None
            and 0 <= age_seconds <= MAX_EXECUTION_ENVELOPE_AGE_SECONDS
        ),
        "localhost_base_url_valid": port is not None,
        "sandbox_only": sandbox_only is True,
        "production_not_targeted": production_targeted is False,
        "secrets_local": secrets_local is True,
        "provider_realm_exact": _clean(
            plan.get("provider_operation", {}).get("realm"), 120
        ) == REALM,
        "provider_path_exact": _clean(
            plan.get("provider_operation", {}).get("relative_path"), 240
        ) == RELATIVE_PATH,
        "target_step_exact": bool(
            plan.get("target_step_order") == 1
            and _clean(plan.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "target_username_is_sandbox": _clean(
            plan.get("target_username"), 160
        ).startswith("sandbox."),
        "provider_command_not_prebaked": plan.get(
            "provider_command_generated"
        ) is False,
        "physical_execution_not_already_performed": plan.get(
            "physical_execution_performed"
        ) is False,
        "receipt_not_already_present": plan.get(
            "step_execution_receipt_present"
        ) is False,
        "ledger_append_not_authorized": plan.get(
            "ledger_append_authorized"
        ) is False,
        "automatic_execution_off": plan.get(
            "automatic_execution_authorized"
        ) is False,
        "executor_disabled": plan.get("executor_enabled") is False,
        "production_not_authorized": plan.get(
            "production_authorized"
        ) is False,
        "non_executing_plan": plan.get("executes_action") is False,
    }

    common_blockers = [
        name for name, passed in common_gates.items() if not passed
    ]
    common_ready = not common_blockers

    if not wants_apply:
        plan_payload = {
            "apply_plan_digest": digest,
            "execution_envelope_digest": _clean(
                envelope.get("execution_envelope_digest"), 80
            ).lower(),
            "base_url": _clean(base_url, 200),
            "evaluated_at": (
                evaluated.isoformat() if evaluated is not None else ""
            ),
            "apply_requested": False,
        } if common_ready else {}
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": (
                "STEP1_PROVIDER_RUNNER_PLAN_ONLY"
                if common_ready
                else "STEP1_PROVIDER_RUNNER_BLOCKED"
            ),
            "gates": common_gates,
            "blockers": common_blockers,
            "execution_envelope_age_seconds": age_seconds,
            "base_url": _clean(base_url, 200) if common_ready else "",
            "local_port": port if common_ready else None,
            "apply_plan_digest": digest if common_ready else "",
            "runner_preflight_digest": (
                _digest(plan_payload) if common_ready else ""
            ),
            "required_physical_apply_token": (
                required_token if common_ready else ""
            ),
            "pre_post_username_lookup_required": True,
            "apply_requested": False,
            "physical_apply_authorized": False,
            "physical_execution_performed": False,
            "receipt_created": False,
            "ledger_append_authorized": False,
            "automatic_execution_authorized": False,
            "automatic_ledger_append": False,
            "executor_enabled": False,
            "production_authorized": False,
            "executes_action": False,
        }

    apply_gates = {
        **common_gates,
        "apply_switch_explicit": wants_apply,
        "authorization_token_exact": bool(
            required_token and supplied_token == required_token
        ),
    }
    blockers = [
        name for name, passed in apply_gates.items() if not passed
    ]
    ready = not blockers
    apply_payload = {
        "apply_plan_digest": digest,
        "execution_envelope_digest": _clean(
            envelope.get("execution_envelope_digest"), 80
        ).lower(),
        "base_url": _clean(base_url, 200),
        "evaluated_at": (
            evaluated.isoformat() if evaluated is not None else ""
        ),
        "apply_requested": True,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY"
            if ready
            else "STEP1_PROVIDER_RUNNER_BLOCKED"
        ),
        "gates": apply_gates,
        "blockers": blockers,
        "execution_envelope_age_seconds": age_seconds,
        "base_url": _clean(base_url, 200) if ready else "",
        "local_port": port if ready else None,
        "apply_plan_digest": digest if ready else "",
        "runner_preflight_digest": _digest(apply_payload) if ready else "",
        "required_physical_apply_token": (
            required_token if common_ready else ""
        ),
        "pre_post_username_lookup_required": True,
        "apply_requested": wants_apply,
        "physical_apply_authorized": ready,
        "physical_execution_performed": False,
        "receipt_created": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_EXECUTION_ENVELOPE_AGE_SECONDS",
    "provider_runner_policy",
    "required_physical_apply_token",
    "build_provider_runner_preflight",
]
