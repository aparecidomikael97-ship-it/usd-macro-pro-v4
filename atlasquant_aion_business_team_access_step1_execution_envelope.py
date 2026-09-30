"""AION BUSINESS Team Access Step 1 Manual Execution Envelope V1.

Prepares a short-lived, read-only envelope for a future manual execution of
Step 1 after an explicit Step 1 decision record has been verified.

This module never calls Keycloak, PostgreSQL, Docker or any executor. It never
creates the sandbox account and never appends lifecycle evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    ALLOWED_FACTORS,
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_decision_record import (
    verify_step1_decision_binding,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    verify_step1_preflight_package,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_EXECUTION_ENVELOPE_V1"
OBSERVATION_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_STEP1_EXECUTION_OBSERVATION_V1"
)
VERSION = "1"
MAX_DECISION_TO_ENVELOPE_AGE_SECONDS = 120
MAX_EXECUTION_OBSERVATION_AGE_SECONDS = 120

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            return []
        rows.append(dict(item))
    return rows


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


def step1_execution_envelope_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_EXECUTION_ENVELOPE_POLICY_DEFINED",
        "post_decision_observation_required": True,
        "target_account_absence_required": True,
        "decision_max_age_seconds": MAX_DECISION_TO_ENVELOPE_AGE_SECONDS,
        "observation_max_age_seconds": MAX_EXECUTION_OBSERVATION_AGE_SECONDS,
        "manual_apply_eligible": False,
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def execution_observation_template() -> dict[str, Any]:
    return {
        "schema": OBSERVATION_SCHEMA,
        "version": VERSION,
        "operator_session_id": "",
        "baseline_evidence_digest_observed": "",
        "observed_at": "",
        "observed_by": "",
        "target_username": "",
        "target_account_absent_verified": False,
        "identity_provider_account_lookup_verified": False,
        "tenant_scope_verified": False,
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
    steps = _rows(plan.get("steps"))

    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    acceptance_digest = _clean(
        row.get("baseline_acceptance_record_digest"), 80
    ).lower()
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()
    username = _clean(plan.get("test_username"), 160)
    tenants = [
        _clean(item, 120)
        for item in list(plan.get("tenant_ids") or [])
        if _clean(item, 120)
    ]
    factor = _clean(plan.get("factor_type"), 60).upper()
    requested_by = _clean(plan.get("requested_by"), 120)

    plan_payload = {
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "test_username": username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "requested_by": requested_by,
        "steps": steps,
    }
    materialization_payload = {
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "plan_digest": plan_digest,
        "test_username": username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "requested_by": requested_by,
    }

    gates = {
        "schema_valid": row.get("schema") == MATERIALIZATION_SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(_DIGEST64.fullmatch(baseline_digest)),
        "acceptance_digest_valid": bool(
            _DIGEST64.fullmatch(acceptance_digest)
        ),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "plan_digest_integrity": bool(
            _DIGEST64.fullmatch(plan_digest)
            and plan_digest == _digest(plan_payload)
            and plan_digest == _clean(plan.get("plan_digest"), 80).lower()
        ),
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "materialization_digest_integrity": bool(
            _DIGEST64.fullmatch(materialization_digest)
            and materialization_digest == _digest(materialization_payload)
        ),
        "target_username_is_sandbox": bool(
            username and username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenants),
        "target_step_is_account_creation": bool(
            steps
            and steps[0].get("order") == 1
            and _clean(steps[0].get("id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "non_executing_materialization": bool(
            row.get("lifecycle_execution_authorized") is False
            and row.get("automatic_step_execution") is False
            and row.get("production_authorized") is False
            and row.get("deploy_authorized") is False
            and row.get("runtime_authorized") is False
            and row.get("executes_action") is False
        ),
    }

    return {
        "valid": all(gates.values()),
        "gates": gates,
        "plan": plan,
        "plan_digest": plan_digest,
        "materialization_digest": materialization_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "baseline_acceptance_record_digest": acceptance_digest,
        "test_username": username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "requested_by": requested_by,
    }


def build_step1_execution_envelope(
    materialization: Mapping[str, Any] | None,
    preflight_packet: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
    execution_observation: Mapping[str, Any] | None,
    *,
    prepared_at: Any,
) -> dict[str, Any]:
    materialized = _materialization_integrity(materialization)
    packet = _mapping(preflight_packet)
    decision = _mapping(decision_record)
    observed = _mapping(execution_observation)

    packet_binding = verify_step1_preflight_package(packet)
    decision_binding = verify_step1_decision_binding(packet, decision)

    prepared = _parse_time(prepared_at)
    decided = _parse_time(decision.get("decided_at"))
    observed_at = _parse_time(observed.get("observed_at"))

    decision_age = (
        (prepared - decided).total_seconds()
        if prepared is not None and decided is not None
        else None
    )
    observation_age = (
        (prepared - observed_at).total_seconds()
        if prepared is not None and observed_at is not None
        else None
    )
    observation_after_decision = (
        (observed_at - decided).total_seconds()
        if observed_at is not None and decided is not None
        else None
    )

    observed_session = _clean(
        observed.get("operator_session_id"), 64
    ).lower()
    observed_baseline = _clean(
        observed.get("baseline_evidence_digest_observed"), 80
    ).lower()
    observed_by = _clean(observed.get("observed_by"), 120)
    observed_username = _clean(observed.get("target_username"), 160)
    decided_by = _clean(decision.get("decided_by"), 120)

    gates = {
        **materialized["gates"],
        "packet_binding_match": packet_binding.get("binding_match") is True,
        "decision_binding_match": decision_binding.get(
            "binding_match"
        ) is True,
        "packet_materialization_digest_matches": bool(
            _clean(packet.get("materialization_digest"), 80).lower()
            == materialized["materialization_digest"]
        ),
        "packet_plan_digest_matches": bool(
            _clean(packet.get("plan_digest"), 80).lower()
            == materialized["plan_digest"]
        ),
        "packet_session_matches": bool(
            _clean(packet.get("operator_session_id"), 64).lower()
            == materialized["operator_session_id"]
        ),
        "packet_baseline_matches": bool(
            _clean(packet.get("baseline_evidence_digest"), 80).lower()
            == materialized["baseline_evidence_digest"]
        ),
        "prepared_at_valid": prepared is not None,
        "decision_not_future": bool(
            decision_age is not None and decision_age >= 0
        ),
        "decision_still_fresh": bool(
            decision_age is not None
            and 0 <= decision_age <= MAX_DECISION_TO_ENVELOPE_AGE_SECONDS
        ),
        "execution_observation_not_future": bool(
            observation_age is not None and observation_age >= 0
        ),
        "execution_observation_fresh": bool(
            observation_age is not None
            and 0 <= observation_age
            <= MAX_EXECUTION_OBSERVATION_AGE_SECONDS
        ),
        "observation_after_decision": bool(
            observation_after_decision is not None
            and observation_after_decision >= 0
        ),
        "observation_schema_valid": observed.get("schema")
        == OBSERVATION_SCHEMA,
        "observation_session_valid": bool(
            _SESSION32.fullmatch(observed_session)
        ),
        "observation_session_matches": bool(
            observed_session == materialized["operator_session_id"]
        ),
        "observation_baseline_valid": bool(
            _DIGEST64.fullmatch(observed_baseline)
        ),
        "observation_baseline_matches": bool(
            observed_baseline == materialized["baseline_evidence_digest"]
        ),
        "observer_matches_decider": bool(
            observed_by and decided_by and observed_by == decided_by
        ),
        "target_username_matches": bool(
            observed_username
            and observed_username == materialized["test_username"]
        ),
        "target_account_absent_verified": observed.get(
            "target_account_absent_verified"
        ) is True,
        "identity_provider_lookup_verified": observed.get(
            "identity_provider_account_lookup_verified"
        ) is True,
        "tenant_scope_verified": observed.get(
            "tenant_scope_verified"
        ) is True,
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
        "observation_non_mutating": observed.get(
            "external_mutations_executed"
        ) is False,
    }

    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    observation_payload = {
        "schema": OBSERVATION_SCHEMA,
        "version": VERSION,
        "operator_session_id": observed_session,
        "baseline_evidence_digest_observed": observed_baseline,
        "observed_at": (
            observed_at.isoformat() if observed_at is not None else ""
        ),
        "observed_by": observed_by,
        "target_username": observed_username,
        "target_account_absent_verified": observed.get(
            "target_account_absent_verified"
        ) is True,
        "identity_provider_account_lookup_verified": observed.get(
            "identity_provider_account_lookup_verified"
        ) is True,
        "tenant_scope_verified": observed.get(
            "tenant_scope_verified"
        ) is True,
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
        "secret_material_included": False,
        "production_targeted": False,
        "external_mutations_executed": False,
    } if ready else {}
    observation_digest = _digest(observation_payload) if ready else ""

    payload = {
        "materialization_digest": materialized["materialization_digest"],
        "step1_packet_digest": _clean(
            packet.get("step1_packet_digest"), 80
        ).lower(),
        "decision_record_digest": _clean(
            decision.get("decision_record_digest"), 80
        ).lower(),
        "execution_observation_digest": observation_digest,
        "plan_digest": materialized["plan_digest"],
        "operator_session_id": materialized["operator_session_id"],
        "baseline_evidence_digest": materialized[
            "baseline_evidence_digest"
        ],
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": materialized["test_username"],
        "tenant_ids": materialized["tenant_ids"],
        "factor_type": materialized["factor_type"],
        "decided_at": (
            decided.isoformat() if decided is not None else ""
        ),
        "observed_at": (
            observed_at.isoformat() if observed_at is not None else ""
        ),
        "observed_by": observed_by,
        "prepared_at": prepared.isoformat() if prepared is not None else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY"
            if ready
            else "TEAM_ACCESS_STEP1_EXECUTION_ENVELOPE_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "decision_age_seconds": decision_age,
        "execution_observation_age_seconds": observation_age,
        "execution_envelope_digest": _digest(payload) if ready else "",
        "materialization_digest": materialized["materialization_digest"]
        if ready else "",
        "step1_packet_digest": _clean(
            packet.get("step1_packet_digest"), 80
        ).lower() if ready else "",
        "decision_record_digest": _clean(
            decision.get("decision_record_digest"), 80
        ).lower() if ready else "",
        "execution_observation_digest": observation_digest if ready else "",
        "execution_observation": observation_payload if ready else {},
        "plan_digest": materialized["plan_digest"] if ready else "",
        "operator_session_id": materialized["operator_session_id"]
        if ready else "",
        "baseline_evidence_digest": materialized[
            "baseline_evidence_digest"
        ] if ready else "",
        "decided_at": (
            decided.isoformat()
            if ready and decided is not None
            else ""
        ),
        "observed_at": (
            observed_at.isoformat()
            if ready and observed_at is not None
            else ""
        ),
        "observed_by": observed_by if ready else "",
        "prepared_at": (
            prepared.isoformat()
            if ready and prepared is not None
            else ""
        ),
        "target_step_order": 1 if ready else None,
        "target_step_id": LIFECYCLE_STEP_IDS[0] if ready else "",
        "target_username": materialized["test_username"] if ready else "",
        "tenant_ids": materialized["tenant_ids"] if ready else [],
        "factor_type": materialized["factor_type"] if ready else "",
        "manual_apply_eligible": ready,
        "manual_apply_required": True,
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "step_execution_receipt_present": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }




def verify_step1_execution_envelope(
    envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(envelope)

    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()
    packet_digest = _clean(
        row.get("step1_packet_digest"), 80
    ).lower()
    decision_digest = _clean(
        row.get("decision_record_digest"), 80
    ).lower()
    observation_digest = _clean(
        row.get("execution_observation_digest"), 80
    ).lower()
    observation = _mapping(row.get("execution_observation"))
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    session_id = _clean(row.get("operator_session_id"), 64).lower()
    baseline_digest = _clean(
        row.get("baseline_evidence_digest"), 80
    ).lower()
    target_username = _clean(row.get("target_username"), 160)
    tenants = [
        _clean(item, 120)
        for item in list(row.get("tenant_ids") or [])
        if _clean(item, 120)
    ]
    factor = _clean(row.get("factor_type"), 60).upper()
    decided_at = _parse_time(row.get("decided_at"))
    observed_at = _parse_time(row.get("observed_at"))
    observed_by = _clean(row.get("observed_by"), 120)
    prepared_at = _parse_time(row.get("prepared_at"))
    envelope_digest = _clean(
        row.get("execution_envelope_digest"), 80
    ).lower()

    canonical_observation = {
        "schema": _clean(observation.get("schema"), 180),
        "version": _clean(observation.get("version"), 20),
        "operator_session_id": _clean(
            observation.get("operator_session_id"), 64
        ).lower(),
        "baseline_evidence_digest_observed": _clean(
            observation.get("baseline_evidence_digest_observed"), 80
        ).lower(),
        "observed_at": (
            _parse_time(observation.get("observed_at")).isoformat()
            if _parse_time(observation.get("observed_at")) is not None
            else ""
        ),
        "observed_by": _clean(observation.get("observed_by"), 120),
        "target_username": _clean(
            observation.get("target_username"), 160
        ),
        "target_account_absent_verified": observation.get(
            "target_account_absent_verified"
        ) is True,
        "identity_provider_account_lookup_verified": observation.get(
            "identity_provider_account_lookup_verified"
        ) is True,
        "tenant_scope_verified": observation.get(
            "tenant_scope_verified"
        ) is True,
        "sandbox_health_verified": observation.get(
            "sandbox_health_verified"
        ) is True,
        "oidc_verified": observation.get("oidc_verified") is True,
        "registry_schema_verified": observation.get(
            "registry_schema_verified"
        ) is True,
        "secrets_local": observation.get("secrets_local") is True,
        "production_targets_absent": observation.get(
            "production_targets_absent"
        ) is True,
        "cleanup_path_ready": observation.get("cleanup_path_ready") is True,
        "secret_material_included": observation.get(
            "secret_material_included"
        ) is True,
        "production_targeted": observation.get(
            "production_targeted"
        ) is True,
        "external_mutations_executed": observation.get(
            "external_mutations_executed"
        ) is True,
    }
    recomputed_observation_digest = _digest(canonical_observation)

    payload = {
        "materialization_digest": materialization_digest,
        "step1_packet_digest": packet_digest,
        "decision_record_digest": decision_digest,
        "execution_observation_digest": observation_digest,
        "plan_digest": plan_digest,
        "operator_session_id": session_id,
        "baseline_evidence_digest": baseline_digest,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": target_username,
        "tenant_ids": sorted(set(tenants)),
        "factor_type": factor,
        "decided_at": (
            decided_at.isoformat() if decided_at is not None else ""
        ),
        "observed_at": (
            observed_at.isoformat() if observed_at is not None else ""
        ),
        "observed_by": observed_by,
        "prepared_at": (
            prepared_at.isoformat() if prepared_at is not None else ""
        ),
    }

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_1_APPLY",
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "packet_digest_valid": bool(_DIGEST64.fullmatch(packet_digest)),
        "decision_digest_valid": bool(
            _DIGEST64.fullmatch(decision_digest)
        ),
        "observation_digest_valid": bool(
            _DIGEST64.fullmatch(observation_digest)
        ),
        "observation_schema_valid": canonical_observation["schema"]
        == OBSERVATION_SCHEMA,
        "observation_version_valid": canonical_observation["version"]
        == VERSION,
        "observation_digest_integrity": bool(
            _DIGEST64.fullmatch(observation_digest)
            and observation_digest == recomputed_observation_digest
        ),
        "observation_safe_flags": bool(
            canonical_observation["target_account_absent_verified"] is True
            and canonical_observation[
                "identity_provider_account_lookup_verified"
            ] is True
            and canonical_observation["tenant_scope_verified"] is True
            and canonical_observation["sandbox_health_verified"] is True
            and canonical_observation["oidc_verified"] is True
            and canonical_observation["registry_schema_verified"] is True
            and canonical_observation["secrets_local"] is True
            and canonical_observation["production_targets_absent"] is True
            and canonical_observation["cleanup_path_ready"] is True
            and canonical_observation["secret_material_included"] is False
            and canonical_observation["production_targeted"] is False
            and canonical_observation["external_mutations_executed"] is False
        ),
        "observation_identity_matches_envelope": bool(
            canonical_observation["operator_session_id"] == session_id
            and canonical_observation[
                "baseline_evidence_digest_observed"
            ] == baseline_digest
            and canonical_observation["observed_at"]
            == (observed_at.isoformat() if observed_at is not None else "")
            and canonical_observation["observed_by"] == observed_by
            and canonical_observation["target_username"] == target_username
        ),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "session_valid": bool(_SESSION32.fullmatch(session_id)),
        "baseline_digest_valid": bool(
            _DIGEST64.fullmatch(baseline_digest)
        ),
        "target_step_exact": bool(
            row.get("target_step_order") == 1
            and _clean(row.get("target_step_id"), 120).upper()
            == LIFECYCLE_STEP_IDS[0]
        ),
        "target_username_sandbox": bool(
            target_username.startswith("sandbox.")
        ),
        "tenant_scope_present": bool(tenants),
        "factor_allowed": factor in ALLOWED_FACTORS,
        "decided_at_valid": decided_at is not None,
        "observed_at_valid": observed_at is not None,
        "observer_present": bool(observed_by),
        "prepared_at_valid": prepared_at is not None,
        "decision_not_after_observation": bool(
            decided_at is not None
            and observed_at is not None
            and decided_at <= observed_at
        ),
        "decision_age_at_preparation_valid": bool(
            decided_at is not None
            and prepared_at is not None
            and 0 <= (prepared_at - decided_at).total_seconds()
            <= MAX_DECISION_TO_ENVELOPE_AGE_SECONDS
        ),
        "observation_age_at_preparation_valid": bool(
            observed_at is not None
            and prepared_at is not None
            and 0 <= (prepared_at - observed_at).total_seconds()
            <= MAX_EXECUTION_OBSERVATION_AGE_SECONDS
        ),
        "observation_not_after_preparation": bool(
            observed_at is not None
            and prepared_at is not None
            and observed_at <= prepared_at
        ),
        "envelope_digest_valid": bool(
            _DIGEST64.fullmatch(envelope_digest)
        ),
        "envelope_digest_integrity": bool(
            _DIGEST64.fullmatch(envelope_digest)
            and envelope_digest == _digest(payload)
        ),
        "manual_apply_eligible": row.get(
            "manual_apply_eligible"
        ) is True,
        "manual_apply_required": row.get(
            "manual_apply_required"
        ) is True,
        "provider_command_not_generated": row.get(
            "provider_command_generated"
        ) is False,
        "physical_execution_not_performed": row.get(
            "physical_execution_performed"
        ) is False,
        "execution_receipt_absent": row.get(
            "step_execution_receipt_present"
        ) is False,
        "ledger_append_not_authorized": row.get(
            "ledger_append_authorized"
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
            "STEP1_EXECUTION_ENVELOPE_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_EXECUTION_ENVELOPE_BINDING_MATCH"
            if match
            else "STEP1_EXECUTION_ENVELOPE_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "gates": gates,
        "blockers": blockers,
        "execution_envelope_digest": envelope_digest if match else "",
        "execution_observation_digest": (
            observation_digest if match else ""
        ),
        "manual_apply_eligible": match,
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "ledger_append_authorized": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def verify_step1_execution_envelope_source_binding(
    materialization: Mapping[str, Any] | None,
    preflight_packet: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
    envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    materialized = _materialization_integrity(materialization)
    packet = _mapping(preflight_packet)
    decision = _mapping(decision_record)
    row = _mapping(envelope)

    envelope_binding = verify_step1_execution_envelope(row)
    packet_binding = verify_step1_preflight_package(packet)
    decision_binding = verify_step1_decision_binding(packet, decision)

    match = bool(
        materialized.get("valid") is True
        and packet_binding.get("binding_match") is True
        and decision_binding.get("binding_match") is True
        and envelope_binding.get("binding_match") is True
        and _clean(row.get("materialization_digest"), 80).lower()
        == materialized["materialization_digest"]
        and _clean(row.get("step1_packet_digest"), 80).lower()
        == _clean(packet.get("step1_packet_digest"), 80).lower()
        and _clean(row.get("decision_record_digest"), 80).lower()
        == _clean(decision.get("decision_record_digest"), 80).lower()
        and _clean(row.get("plan_digest"), 80).lower()
        == materialized["plan_digest"]
        and _clean(row.get("operator_session_id"), 64).lower()
        == materialized["operator_session_id"]
        and _clean(row.get("baseline_evidence_digest"), 80).lower()
        == materialized["baseline_evidence_digest"]
        and _clean(row.get("target_username"), 160)
        == materialized["test_username"]
        and sorted(
            {
                _clean(item, 120)
                for item in list(row.get("tenant_ids") or [])
                if _clean(item, 120)
            }
        )
        == materialized["tenant_ids"]
        and _clean(row.get("factor_type"), 60).upper()
        == materialized["factor_type"]
    )

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_EXECUTION_ENVELOPE_SOURCE_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_EXECUTION_ENVELOPE_SOURCE_BINDING_MATCH"
            if match
            else "STEP1_EXECUTION_ENVELOPE_SOURCE_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "execution_envelope_digest": _clean(
            row.get("execution_envelope_digest"), 80
        ).lower() if match else "",
        "provider_command_generated": False,
        "physical_execution_performed": False,
        "automatic_execution_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }

__all__ = [
    "SCHEMA",
    "OBSERVATION_SCHEMA",
    "VERSION",
    "MAX_DECISION_TO_ENVELOPE_AGE_SECONDS",
    "MAX_EXECUTION_OBSERVATION_AGE_SECONDS",
    "step1_execution_envelope_policy",
    "execution_observation_template",
    "build_step1_execution_envelope",
    "verify_step1_execution_envelope",
    "verify_step1_execution_envelope_source_binding",
]
