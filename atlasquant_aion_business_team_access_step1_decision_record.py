"""AION BUSINESS Team Access Step 1 Explicit Decision Record V1.

Validates a human decision for exactly Step 1 against one intact Step 1
preflight packet. Generic language is never authorization.

This module never executes Step 1, never appends to the lifecycle ledger and
never enables an executor.
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
from atlasquant_aion_business_team_access_step1_preflight_package import (
    MAX_OBSERVATION_AGE_SECONDS,
    SCHEMA as PREFLIGHT_PACKET_SCHEMA,
    verify_step1_preflight_package,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_DECISION_RECORD_V1"
VERSION = "1"
MAX_PACKET_DECISION_AGE_SECONDS = 300

REQUIRED_ACKNOWLEDGEMENTS = (
    "STEP1_ONLY",
    "PACKET_DIGEST_FROZEN",
    "SANDBOX_ONLY",
    "OBSERVATION_STILL_FRESH",
    "NO_PRODUCTION_TARGETS",
    "MANUAL_APPLY_ONLY",
    "STOP_ON_FIRST_MISMATCH",
    "NO_AUTOMATIC_LEDGER_APPEND",
    "EXECUTOR_REMAINS_DISABLED",
    "POST_STEP_RECEIPT_REQUIRED",
)

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


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


def _expected_token() -> str:
    return (
        f"AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_"
        f"{LIFECYCLE_STEP_IDS[0]}"
    )


def step1_decision_requirements() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPLICIT_STEP1_DECISION_RECORD_REQUIRED",
        "required_decision_token": _expected_token(),
        "required_acknowledgements": list(REQUIRED_ACKNOWLEDGEMENTS),
        "max_packet_decision_age_seconds": MAX_PACKET_DECISION_AGE_SECONDS,
        "max_observation_age_at_decision_seconds": (
            MAX_OBSERVATION_AGE_SECONDS
        ),
        "generic_language_is_authorization": False,
        "decision_record_verified": False,
        "manual_step1_execution_authorized": False,
        "step_execution_performed": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def step1_decision_record_template(
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(packet)
    binding = verify_step1_preflight_package(row)
    eligible = binding.get("binding_match") is True

    return {
        **step1_decision_requirements(),
        "state": (
            "EXPLICIT_STEP1_DECISION_RECORD_REQUIRED"
            if eligible
            else "STEP1_DECISION_TEMPLATE_BLOCKED"
        ),
        "step1_packet_digest": _clean(
            row.get("step1_packet_digest"), 80
        ).lower() if eligible else "",
        "target_step_order": 1 if eligible else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if eligible else "",
        "expected_decided_by": _clean(
            row.get("observation_observed_by"), 120
        ) if eligible else "",
        "decision": "",
        "decided_by": "",
        "decided_at": "",
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "automatic_execution_requested": False,
        "automatic_ledger_append_requested": False,
        "executor_enable_requested": False,
        "acknowledgements": {
            name: False for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    }


def validate_step1_decision_record(
    packet: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    packet_row = _mapping(packet)
    raw = _mapping(record)
    packet_binding = verify_step1_preflight_package(packet_row)

    packet_digest = _clean(
        packet_row.get("step1_packet_digest"), 80
    ).lower()
    supplied_packet_digest = _clean(
        raw.get("step1_packet_digest"), 80
    ).lower()
    decision = _clean(raw.get("decision"), 240)
    decided_by = _clean(raw.get("decided_by"), 120)
    expected_decider = _clean(
        packet_row.get("observation_observed_by"), 120
    )
    decided_at_raw = _clean(raw.get("decided_at"), 100)

    packet_evaluated_at = _parse_time(packet_row.get("evaluated_at"))
    observation_at = _parse_time(
        packet_row.get("observation_observed_at")
    )
    decided_at = _parse_time(decided_at_raw)

    packet_age_seconds = (
        (decided_at - packet_evaluated_at).total_seconds()
        if decided_at is not None and packet_evaluated_at is not None
        else None
    )
    observation_age_seconds = (
        (decided_at - observation_at).total_seconds()
        if decided_at is not None and observation_at is not None
        else None
    )

    acknowledgements = _mapping(raw.get("acknowledgements"))
    missing_acknowledgements = [
        name
        for name in REQUIRED_ACKNOWLEDGEMENTS
        if acknowledgements.get(name) is not True
    ]

    gates = {
        "packet_binding_match": packet_binding.get(
            "binding_match"
        ) is True,
        "packet_schema_valid": packet_row.get("schema")
        == PREFLIGHT_PACKET_SCHEMA,
        "packet_digest_valid": bool(
            _DIGEST64.fullmatch(packet_digest)
        ),
        "packet_digest_matches_record": bool(
            packet_digest
            and supplied_packet_digest == packet_digest
        ),
        "record_schema_valid": raw.get("schema") == SCHEMA,
        "decision_token_exact": decision == _expected_token(),
        "target_step_order_exact": raw.get("target_step_order") == 1,
        "target_step_id_exact": _clean(
            raw.get("target_step_id"), 120
        ).upper() == LIFECYCLE_STEP_IDS[0],
        "decided_by_matches_observer": bool(
            decided_by
            and expected_decider
            and decided_by == expected_decider
        ),
        "decided_at_valid": decided_at is not None,
        "packet_not_future": bool(
            packet_age_seconds is not None
            and packet_age_seconds >= 0
        ),
        "packet_still_fresh": bool(
            packet_age_seconds is not None
            and 0 <= packet_age_seconds
            <= MAX_PACKET_DECISION_AGE_SECONDS
        ),
        "observation_not_future": bool(
            observation_age_seconds is not None
            and observation_age_seconds >= 0
        ),
        "observation_still_fresh": bool(
            observation_age_seconds is not None
            and 0 <= observation_age_seconds
            <= MAX_OBSERVATION_AGE_SECONDS
        ),
        "sandbox_only": raw.get("sandbox_only") is True,
        "production_not_targeted": raw.get(
            "production_targeted"
        ) is False,
        "secret_material_absent": raw.get(
            "secret_material_included"
        ) is False,
        "automatic_execution_not_requested": raw.get(
            "automatic_execution_requested"
        ) is False,
        "automatic_ledger_append_not_requested": raw.get(
            "automatic_ledger_append_requested"
        ) is False,
        "executor_enable_not_requested": raw.get(
            "executor_enable_requested"
        ) is False,
        "acknowledgements_complete": not missing_acknowledgements,
    }

    blockers = [name for name, passed in gates.items() if not passed]
    verified = not blockers

    payload = {
        "schema": SCHEMA,
        "version": VERSION,
        "decision": decision,
        "step1_packet_digest": packet_digest,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "decided_by": decided_by,
        "decided_at": (
            decided_at.isoformat() if decided_at is not None else ""
        ),
        "sandbox_only": True,
        "production_targeted": False,
        "secret_material_included": False,
        "automatic_execution_requested": False,
        "automatic_ledger_append_requested": False,
        "executor_enable_requested": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        },
    } if verified else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED"
            if verified
            else "SANDBOX_STEP_1_DECISION_RECORD_REJECTED"
        ),
        "gates": gates,
        "blockers": blockers,
        "missing_acknowledgements": missing_acknowledgements,
        "decision_record_verified": verified,
        "decision": decision if verified else "",
        "step1_packet_digest": packet_digest if verified else "",
        "target_step_order": 1 if verified else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if verified else "",
        "decided_by": decided_by if verified else "",
        "decided_at": (
            decided_at.isoformat()
            if verified and decided_at is not None
            else ""
        ),
        "packet_age_seconds_at_decision": packet_age_seconds,
        "observation_age_seconds_at_decision": observation_age_seconds,
        "sandbox_only": True if verified else False,
        "production_targeted": False,
        "secret_material_included": False,
        "automatic_execution_requested": False,
        "automatic_ledger_append_requested": False,
        "executor_enable_requested": False,
        "acknowledgements": {
            name: acknowledgements.get(name) is True
            for name in REQUIRED_ACKNOWLEDGEMENTS
        } if verified else {},
        "decision_record_digest": _digest(payload) if verified else "",
        "manual_step1_execution_authorized": verified,
        "step_execution_performed": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "invalidated_by_packet_or_observation_drift": True,
        "executes_action": False,
    }


def verify_step1_decision_binding(
    packet: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(decision_record)
    recomputed = validate_step1_decision_record(packet, row)
    stored_digest = _clean(
        row.get("decision_record_digest"), 80
    ).lower()
    recomputed_digest = _clean(
        recomputed.get("decision_record_digest"), 80
    ).lower()

    match = bool(
        recomputed.get("decision_record_verified") is True
        and row.get("state")
        == "EXPLICIT_SANDBOX_STEP_1_DECISION_RECORD_VERIFIED"
        and row.get("decision_record_verified") is True
        and row.get("manual_step1_execution_authorized") is True
        and _DIGEST64.fullmatch(stored_digest)
        and stored_digest == recomputed_digest
        and row.get("step_execution_performed") is False
        and row.get("ledger_append_authorized") is False
        and row.get("automatic_execution_authorized") is False
        and row.get("automatic_ledger_append") is False
        and row.get("executor_enabled") is False
        and row.get("production_authorized") is False
        and row.get("executes_action") is False
    )

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_DECISION_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_DECISION_BINDING_MATCH"
            if match
            else "STEP1_DECISION_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "step1_packet_digest": _clean(
            recomputed.get("step1_packet_digest"), 80
        ).lower() if match else "",
        "decision_record_digest": stored_digest if match else "",
        "manual_step1_execution_authorized": match,
        "step_execution_performed": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_PACKET_DECISION_AGE_SECONDS",
    "REQUIRED_ACKNOWLEDGEMENTS",
    "step1_decision_requirements",
    "step1_decision_record_template",
    "validate_step1_decision_record",
    "verify_step1_decision_binding",
]
