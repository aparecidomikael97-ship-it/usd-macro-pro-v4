"""AION BUSINESS Team Access Step 1 Preflight Package V1.

Builds a zero-receipt lifecycle ledger and a read-only preflight for exactly
Step 1 after a materialized lifecycle authorization package has been verified.

This layer never executes Step 1, never appends to the ledger and never calls
Keycloak, PostgreSQL, Docker or any external provider.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_team_access_lifecycle_authorization_package import (
    verify_materialized_authorization_binding,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
    build_lifecycle_evidence_ledger,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_step_gate import (
    build_step_execution_preflight,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_PREFLIGHT_PACKAGE_V1"
OBSERVATION_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_READINESS_OBSERVATION_V1"
)
VERSION = "1"
MAX_OBSERVATION_AGE_SECONDS = 900

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


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


def step1_preflight_package_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_PREFLIGHT_PACKAGE_POLICY_DEFINED",
        "zero_receipt_ledger_required": True,
        "genesis_chain_required": True,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "fresh_observation_required": True,
        "max_observation_age_seconds": MAX_OBSERVATION_AGE_SECONDS,
        "generic_language_is_step_authorization": False,
        "manual_decision_recorded": False,
        "step_execution_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def readiness_observation_template() -> dict[str, Any]:
    return {
        "schema": OBSERVATION_SCHEMA,
        "version": VERSION,
        "operator_session_id": "",
        "baseline_evidence_digest_observed": "",
        "observed_at": "",
        "observed_by": "",
        "sandbox_health_verified": False,
        "oidc_verified": False,
        "registry_schema_verified": False,
        "secrets_local": False,
        "production_targets_absent": False,
        "cleanup_path_ready": False,
        "secret_material_included": False,
        "production_targeted": False,
        "external_mutations_executed": False,
    }


def _materialization_integrity(
    materialization: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(materialization)
    plan = _mapping(row.get("plan"))
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    acceptance_digest = _clean(
        row.get("baseline_acceptance_record_digest"), 80
    ).lower()
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()

    payload = {
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "plan_digest": plan_digest,
        "test_username": plan.get("test_username"),
        "tenant_ids": plan.get("tenant_ids"),
        "factor_type": plan.get("factor_type"),
        "requested_by": plan.get("requested_by"),
    }

    gates = {
        "materialization_schema_valid": row.get("schema")
        == MATERIALIZATION_SCHEMA,
        "materialization_state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "operator_session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "acceptance_digest_valid": bool(
            _DIGEST64.fullmatch(acceptance_digest)
        ),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "plan_digest_matches_nested_plan": bool(
            plan_digest
            and plan_digest == _clean(plan.get("plan_digest"), 80).lower()
        ),
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "materialization_digest_integrity": bool(
            _DIGEST64.fullmatch(materialization_digest)
            and materialization_digest == _digest(payload)
        ),
        "materialization_non_authorizing": bool(
            row.get("lifecycle_authorization_recorded") is False
            and row.get("lifecycle_execution_authorized") is False
            and row.get("automatic_step_execution") is False
            and row.get("production_authorized") is False
            and row.get("deploy_authorized") is False
            and row.get("runtime_authorized") is False
            and row.get("executes_action") is False
        ),
        "plan_non_authorizing": bool(
            plan.get("decision_recorded") is False
            and plan.get("account_creation_authorized") is False
            and plan.get("mfa_enrollment_authorized") is False
            and plan.get("registry_write_authorized") is False
            and plan.get("session_revocation_authorized") is False
            and plan.get("production_authorized") is False
            and plan.get("deploy_authorized") is False
            and plan.get("runtime_authorized") is False
            and plan.get("executes_action") is False
        ),
    }
    return {
        "valid": all(gates.values()),
        "gates": gates,
        "plan": plan,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "plan_digest": plan_digest,
        "materialization_digest": materialization_digest,
    }


def build_step1_preflight_package(
    materialization: Mapping[str, Any] | None,
    authorization_package: Mapping[str, Any] | None,
    observation: Mapping[str, Any] | None,
    *,
    evaluated_at: Any,
) -> dict[str, Any]:
    materialized = _materialization_integrity(materialization)
    auth = _mapping(authorization_package)
    observed = _mapping(observation)
    plan = materialized["plan"]

    auth_binding = verify_materialized_authorization_binding(plan, auth)
    ledger = build_lifecycle_evidence_ledger(plan, auth, [])

    observed_time = _parse_time(observed.get("observed_at"))
    evaluated_time = _parse_time(evaluated_at)
    age_seconds = (
        (evaluated_time - observed_time).total_seconds()
        if evaluated_time is not None and observed_time is not None
        else None
    )

    observed_session = _clean(
        observed.get("operator_session_id"), 64
    ).lower()
    observed_baseline = _clean(
        observed.get("baseline_evidence_digest_observed"), 80
    ).lower()
    observed_by = _clean(observed.get("observed_by"), 120)
    approved_by = _clean(auth.get("approved_by"), 120)

    observation_gates = {
        "observation_schema_valid": observed.get("schema")
        == OBSERVATION_SCHEMA,
        "observation_session_valid": bool(
            _SESSION32.fullmatch(observed_session)
        ),
        "observation_session_matches": bool(
            observed_session
            and observed_session == materialized["operator_session_id"]
            and observed_session
            == _clean(auth.get("operator_session_id"), 64).lower()
        ),
        "observed_baseline_valid": bool(
            _DIGEST64.fullmatch(observed_baseline)
        ),
        "observed_baseline_matches": bool(
            observed_baseline
            and observed_baseline
            == materialized["baseline_evidence_digest"]
        ),
        "observed_at_valid": observed_time is not None,
        "evaluated_at_valid": evaluated_time is not None,
        "observation_not_future": bool(
            age_seconds is not None and age_seconds >= 0
        ),
        "observation_fresh": bool(
            age_seconds is not None
            and 0 <= age_seconds <= MAX_OBSERVATION_AGE_SECONDS
        ),
        "observed_by_present": bool(observed_by),
        "observer_matches_approver": bool(
            observed_by and approved_by and observed_by == approved_by
        ),
        "sandbox_health_verified": observed.get(
            "sandbox_health_verified"
        ) is True,
        "oidc_verified": observed.get("oidc_verified") is True,
        "registry_schema_verified": observed.get(
            "registry_schema_verified"
        ) is True,
        "secrets_local": observed.get("secrets_local") is True,
        "production_targets_absent": observed.get(
            "production_targets_absent"
        ) is True,
        "cleanup_path_ready": observed.get("cleanup_path_ready") is True,
        "secret_material_absent": observed.get(
            "secret_material_included"
        ) is False,
        "production_not_targeted": observed.get(
            "production_targeted"
        ) is False,
        "observation_non_executing": observed.get(
            "external_mutations_executed"
        ) is False,
    }

    package_gates = {
        **materialized["gates"],
        "authorization_binding_match": auth_binding.get(
            "binding_match"
        ) is True,
        "authorization_manual_scope": bool(
            auth.get("sandbox_lifecycle_manual_execution_authorized") is True
            and auth.get("automatic_execution_authorized") is False
            and auth.get("executor_enabled") is False
            and auth.get("production_authorized") is False
            and auth.get("executes_action") is False
        ),
        "authorization_materialization_digest_matches": bool(
            _clean(auth.get("materialization_digest"), 80).lower()
            == materialized["materialization_digest"]
        ),
        "authorization_acceptance_digest_matches": bool(
            _clean(
                auth.get("baseline_acceptance_record_digest"), 80
            ).lower()
            == materialized["baseline_acceptance_record_digest"]
        ),
        "empty_ledger_ready": bool(
            ledger.get("state")
            == "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP"
            and ledger.get("completed_count") == 0
            and list(ledger.get("entries") or []) == []
            and ledger.get("next_expected_step_order") == 1
            and ledger.get("next_expected_step_id")
            == LIFECYCLE_STEP_IDS[0]
            and ledger.get("chain_head_digest") == GENESIS_DIGEST
            and _DIGEST64.fullmatch(
                _clean(ledger.get("ledger_digest"), 80).lower()
            )
            and ledger.get("automatic_next_step_authorized") is False
            and ledger.get("executor_enabled") is False
            and ledger.get("production_authorized") is False
            and ledger.get("executes_action") is False
        ),
        **observation_gates,
    }

    preliminary_ready = all(package_gates.values())
    if preliminary_ready:
        preflight = build_step_execution_preflight(
            plan,
            auth,
            ledger,
            target_step_order=1,
            baseline_evidence_digest_observed=observed_baseline,
            sandbox_health_verified=observed.get("sandbox_health_verified"),
            oidc_verified=observed.get("oidc_verified"),
            registry_schema_verified=observed.get("registry_schema_verified"),
            secrets_local=observed.get("secrets_local"),
            production_targets_absent=observed.get(
                "production_targets_absent"
            ),
            cleanup_path_ready=observed.get("cleanup_path_ready"),
            requested_by=observed_by,
        )
    else:
        preflight = {
            "state": "SANDBOX_LIFECYCLE_STEP_PREFLIGHT_NOT_EVALUATED",
            "blockers": ["package_prerequisites"],
            "required_step_decision_token": "",
            "step_execution_authorized": False,
            "automatic_execution_authorized": False,
            "automatic_ledger_append": False,
            "executor_enabled": False,
            "production_authorized": False,
            "deploy_authorized": False,
            "runtime_authorized": False,
            "executes_action": False,
        }

    package_gates["step1_preflight_ready"] = bool(
        preflight.get("state")
        == "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION"
        and preflight.get("target_step_order") == 1
        and preflight.get("target_step_id") == LIFECYCLE_STEP_IDS[0]
        and _DIGEST64.fullmatch(
            _clean(preflight.get("preflight_digest"), 80).lower()
        )
        and preflight.get("step_execution_authorized") is False
        and preflight.get("automatic_execution_authorized") is False
        and preflight.get("automatic_ledger_append") is False
        and preflight.get("executor_enabled") is False
        and preflight.get("production_authorized") is False
        and preflight.get("executes_action") is False
    )

    blockers = [
        name for name, passed in package_gates.items() if not passed
    ]
    ready = not blockers

    payload = {
        "materialization_digest": materialized["materialization_digest"],
        "authorization_package_digest": _clean(
            auth.get("authorization_package_digest"), 80
        ).lower(),
        "ledger_digest": _clean(ledger.get("ledger_digest"), 80).lower(),
        "preflight_digest": _clean(
            preflight.get("preflight_digest"), 80
        ).lower(),
        "operator_session_id": materialized["operator_session_id"],
        "baseline_evidence_digest": observed_baseline,
        "observation_observed_at": _clean(
            observed.get("observed_at"), 100
        ),
        "observation_observed_by": observed_by,
        "evaluated_at": (
            evaluated_time.isoformat() if evaluated_time is not None else ""
        ),
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET"
            if ready
            else "TEAM_ACCESS_STEP1_PREFLIGHT_PACKAGE_BLOCKED"
        ),
        "gates": package_gates,
        "blockers": blockers,
        "observation_age_seconds": age_seconds,
        "ledger": ledger,
        "preflight": preflight,
        "step1_packet_digest": _digest(payload) if ready else "",
        "materialization_digest": materialized["materialization_digest"]
        if ready else "",
        "authorization_package_digest": _clean(
            auth.get("authorization_package_digest"), 80
        ).lower() if ready else "",
        "ledger_digest": _clean(
            ledger.get("ledger_digest"), 80
        ).lower() if ready else "",
        "preflight_digest": _clean(
            preflight.get("preflight_digest"), 80
        ).lower() if ready else "",
        "operator_session_id": materialized["operator_session_id"]
        if ready else "",
        "baseline_evidence_digest": observed_baseline if ready else "",
        "observation_observed_at": _clean(
            observed.get("observed_at"), 100
        ) if ready else "",
        "observation_observed_by": observed_by if ready else "",
        "evaluated_at": (
            evaluated_time.isoformat()
            if ready and evaluated_time is not None
            else ""
        ),
        "target_step_order": 1 if ready else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if ready else "",
        "required_step_decision_token": _clean(
            preflight.get("required_step_decision_token"), 240
        ) if ready else "",
        "manual_apply_required": True,
        "manual_decision_recorded": False,
        "step_execution_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }




def verify_step1_preflight_package(
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(packet)
    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()
    authorization_package_digest = _clean(
        row.get("authorization_package_digest"), 80
    ).lower()
    ledger_digest = _clean(row.get("ledger_digest"), 80).lower()
    preflight_digest = _clean(row.get("preflight_digest"), 80).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    observation_at = _clean(
        row.get("observation_observed_at"), 100
    )
    observation_by = _clean(
        row.get("observation_observed_by"), 120
    )
    evaluated_at = _parse_time(row.get("evaluated_at"))
    packet_digest = _clean(
        row.get("step1_packet_digest"), 80
    ).lower()

    payload = {
        "materialization_digest": materialization_digest,
        "authorization_package_digest": authorization_package_digest,
        "ledger_digest": ledger_digest,
        "preflight_digest": preflight_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "observation_observed_at": observation_at,
        "observation_observed_by": observation_by,
        "evaluated_at": (
            evaluated_at.isoformat() if evaluated_at is not None else ""
        ),
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
    }

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_DECISION_PACKET",
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "authorization_package_digest_valid": bool(
            _DIGEST64.fullmatch(authorization_package_digest)
        ),
        "ledger_digest_valid": bool(_DIGEST64.fullmatch(ledger_digest)),
        "preflight_digest_valid": bool(
            _DIGEST64.fullmatch(preflight_digest)
        ),
        "operator_session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(
            _DIGEST64.fullmatch(baseline_digest)
        ),
        "observation_timestamp_present": bool(
            _parse_time(observation_at) is not None
        ),
        "observer_present": bool(observation_by),
        "evaluated_at_valid": evaluated_at is not None,
        "target_is_step1": bool(
            row.get("target_step_order") == 1
            and row.get("target_step_id") == LIFECYCLE_STEP_IDS[0]
        ),
        "decision_token_present": bool(
            _clean(row.get("required_step_decision_token"), 240)
            == (
                f"AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_"
                f"{LIFECYCLE_STEP_IDS[0]}"
            )
        ),
        "packet_digest_valid": bool(
            _DIGEST64.fullmatch(packet_digest)
        ),
        "packet_digest_integrity": bool(
            _DIGEST64.fullmatch(packet_digest)
            and packet_digest == _digest(payload)
        ),
        "manual_decision_not_recorded": row.get(
            "manual_decision_recorded"
        ) is False,
        "step_not_authorized": row.get(
            "step_execution_authorized"
        ) is False,
        "automatic_execution_not_authorized": row.get(
            "automatic_execution_authorized"
        ) is False,
        "automatic_ledger_append_off": row.get(
            "automatic_ledger_append"
        ) is False,
        "executor_disabled": row.get("executor_enabled") is False,
        "production_not_authorized": row.get(
            "production_authorized"
        ) is False,
        "deploy_not_authorized": row.get("deploy_authorized") is False,
        "runtime_not_authorized": row.get("runtime_authorized") is False,
        "non_executing": row.get("executes_action") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    match = not blockers
    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_PREFLIGHT_PACKAGE_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_PREFLIGHT_PACKAGE_BINDING_MATCH"
            if match
            else "STEP1_PREFLIGHT_PACKAGE_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "gates": gates,
        "blockers": blockers,
        "step1_packet_digest": packet_digest if match else "",
        "evaluated_at": (
            evaluated_at.isoformat()
            if match and evaluated_at is not None
            else ""
        ),
        "manual_decision_recorded": False,
        "step_execution_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }

__all__ = [
    "SCHEMA",
    "OBSERVATION_SCHEMA",
    "VERSION",
    "MAX_OBSERVATION_AGE_SECONDS",
    "step1_preflight_package_policy",
    "readiness_observation_template",
    "build_step1_preflight_package",
    "verify_step1_preflight_package",
]
