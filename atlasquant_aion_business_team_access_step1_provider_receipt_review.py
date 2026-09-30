"""AION BUSINESS Team Access Step 1 Provider Receipt + Ledger Review V1.

Validates the sanitized physical Step 1 provider receipt and constructs an
in-memory lifecycle ledger preview with Step 1 completed.

This module never calls Keycloak/PostgreSQL/Docker and never writes or appends
the lifecycle ledger.
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
    build_evidence_receipt,
    build_lifecycle_evidence_ledger,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
)
from atlasquant_aion_business_team_access_step1_apply_plan import (
    verify_step1_apply_plan,
    verify_step1_apply_plan_source_binding,
)
from atlasquant_aion_business_team_access_step1_execution_envelope import (
    verify_step1_execution_envelope,
)
from atlasquant_aion_business_team_access_step1_preflight_package import (
    verify_step1_preflight_package,
)
from atlasquant_aion_business_team_access_step1_provider_runner import (
    verify_provider_runner_preflight,
)

SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
    "STEP1_PROVIDER_RECEIPT_LEDGER_REVIEW_V1"
)
PROVIDER_RECEIPT_SCHEMA = (
    "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
    "STEP1_PROVIDER_EXECUTION_RECEIPT_V1"
)
VERSION = "1"
MAX_RUNNER_TO_EXECUTION_SECONDS = 180

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_SESSION32 = re.compile(r"^[0-9a-f]{32}$")
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


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


def provider_receipt_review_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_STEP1_PROVIDER_RECEIPT_REVIEW_POLICY_DEFINED",
        "provider_receipt_required": True,
        "runner_preflight_binding_required": True,
        "empty_ledger_source_required": True,
        "canonical_lifecycle_receipt_required": True,
        "ledger_preview_only": True,
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "step2_execution_authorized": False,
        "automatic_ledger_append": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def validate_provider_receipt_and_preview_ledger(
    materialization: Mapping[str, Any] | None,
    authorization_package: Mapping[str, Any] | None,
    step1_preflight_packet: Mapping[str, Any] | None,
    execution_envelope: Mapping[str, Any] | None,
    apply_plan: Mapping[str, Any] | None,
    runner_preflight: Mapping[str, Any] | None,
    provider_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    materialized = _mapping(materialization)
    auth = _mapping(authorization_package)
    packet = _mapping(step1_preflight_packet)
    envelope = _mapping(execution_envelope)
    plan_artifact = _mapping(apply_plan)
    runner = _mapping(runner_preflight)
    receipt = _mapping(provider_receipt)
    lifecycle_plan = _mapping(materialized.get("plan"))

    auth_binding = verify_materialized_authorization_binding(
        lifecycle_plan, auth
    )
    packet_binding = verify_step1_preflight_package(packet)
    envelope_binding = verify_step1_execution_envelope(envelope)
    apply_binding = verify_step1_apply_plan(plan_artifact)
    apply_source_binding = verify_step1_apply_plan_source_binding(
        envelope, plan_artifact
    )
    runner_binding = verify_provider_runner_preflight(
        envelope, plan_artifact, runner
    )

    receipt_apply_digest = _clean(
        receipt.get("apply_plan_digest"), 80
    ).lower()
    receipt_runner_digest = _clean(
        receipt.get("runner_preflight_digest"), 80
    ).lower()
    receipt_envelope_digest = _clean(
        receipt.get("execution_envelope_digest"), 80
    ).lower()
    receipt_session = _clean(
        receipt.get("operator_session_id"), 64
    ).lower()
    receipt_baseline = _clean(
        receipt.get("baseline_evidence_digest"), 80
    ).lower()
    receipt_step_id = _clean(
        receipt.get("target_step_id"), 120
    ).upper()
    receipt_username = _clean(
        receipt.get("target_username"), 160
    )
    provider_user_id = _clean(
        receipt.get("provider_user_id"), 160
    )
    executed_at = _parse_time(receipt.get("executed_at"))
    runner_evaluated_at = _parse_time(runner.get("evaluated_at"))
    execution_age = (
        (executed_at - runner_evaluated_at).total_seconds()
        if executed_at is not None and runner_evaluated_at is not None
        else None
    )

    packet_ledger = _mapping(packet.get("ledger"))
    materialization_digest = _clean(
        materialized.get("materialization_digest"), 80
    ).lower()
    materialized_plan_digest = _clean(
        lifecycle_plan.get("plan_digest"), 80
    ).lower()

    gates = {
        "materialization_schema_valid": materialized.get("schema")
        == MATERIALIZATION_SCHEMA,
        "materialization_state_ready": materialized.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "materialization_digest_matches_authorization": bool(
            materialization_digest
            == _clean(auth.get("materialization_digest"), 80).lower()
        ),
        "materialization_digest_matches_envelope": bool(
            materialization_digest
            == _clean(envelope.get("materialization_digest"), 80).lower()
        ),
        "materialized_plan_digest_valid": bool(
            _DIGEST64.fullmatch(materialized_plan_digest)
        ),
        "plan_digest_matches_apply_plan": bool(
            materialized_plan_digest
            == _clean(plan_artifact.get("plan_digest"), 80).lower()
        ),
        "plan_digest_matches_envelope": bool(
            materialized_plan_digest
            == _clean(envelope.get("plan_digest"), 80).lower()
        ),
        "authorization_binding_match": auth_binding.get(
            "binding_match"
        ) is True,
        "step1_packet_binding_match": packet_binding.get(
            "binding_match"
        ) is True,
        "execution_envelope_binding_match": envelope_binding.get(
            "binding_match"
        ) is True,
        "apply_plan_binding_match": apply_binding.get(
            "binding_match"
        ) is True,
        "apply_plan_source_binding_match": apply_source_binding.get(
            "binding_match"
        ) is True,
        "runner_preflight_binding_match": runner_binding.get(
            "binding_match"
        ) is True,
        "runner_was_apply_authorized": bool(
            runner.get("state")
            == "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY"
            and runner.get("apply_requested") is True
            and runner.get("physical_apply_authorized") is True
        ),
        "source_ledger_was_empty": bool(
            packet_ledger.get("state")
            == "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP"
            and packet_ledger.get("completed_count") == 0
            and list(packet_ledger.get("entries") or []) == []
            and packet_ledger.get("chain_head_digest") == GENESIS_DIGEST
            and packet_ledger.get("next_expected_step_order") == 1
            and packet_ledger.get("next_expected_step_id")
            == LIFECYCLE_STEP_IDS[0]
        ),
        "provider_receipt_schema_valid": receipt.get("schema")
        == PROVIDER_RECEIPT_SCHEMA,
        "provider_receipt_version_valid": receipt.get("version") == VERSION,
        "provider_receipt_state_valid": receipt.get("state")
        == "STEP1_PROVIDER_APPLY_EXECUTED_PENDING_LEDGER_REVIEW",
        "apply_plan_digest_valid": bool(
            _DIGEST64.fullmatch(receipt_apply_digest)
        ),
        "apply_plan_digest_matches": receipt_apply_digest
        == _clean(plan_artifact.get("apply_plan_digest"), 80).lower(),
        "runner_preflight_digest_valid": bool(
            _DIGEST64.fullmatch(receipt_runner_digest)
        ),
        "runner_preflight_digest_matches": receipt_runner_digest
        == _clean(runner.get("runner_preflight_digest"), 80).lower(),
        "execution_envelope_digest_valid": bool(
            _DIGEST64.fullmatch(receipt_envelope_digest)
        ),
        "execution_envelope_digest_matches": receipt_envelope_digest
        == _clean(
            envelope.get("execution_envelope_digest"), 80
        ).lower(),
        "operator_session_valid": bool(
            _SESSION32.fullmatch(receipt_session)
        ),
        "operator_session_matches": receipt_session
        == _clean(
            materialized.get("operator_session_id"), 64
        ).lower(),
        "baseline_digest_valid": bool(
            _DIGEST64.fullmatch(receipt_baseline)
        ),
        "baseline_digest_matches": receipt_baseline
        == _clean(
            materialized.get("baseline_evidence_digest"), 80
        ).lower(),
        "target_step_order_exact": receipt.get(
            "target_step_order"
        ) == 1,
        "target_step_id_exact": receipt_step_id
        == LIFECYCLE_STEP_IDS[0],
        "target_username_exact": bool(
            receipt_username
            and receipt_username
            == _clean(plan_artifact.get("target_username"), 160)
        ),
        "provider_exact": receipt.get("provider") == "KEYCLOAK",
        "realm_exact": receipt.get("realm") == "atlasquant-sandbox",
        "provider_user_id_valid": bool(
            _PROVIDER_ID.fullmatch(provider_user_id)
        ),
        "http_status_exact": receipt.get("http_status") == 201,
        "exact_readback_verified": receipt.get(
            "exact_readback_verified"
        ) is True,
        "executed_at_valid": executed_at is not None,
        "runner_evaluated_at_valid": runner_evaluated_at is not None,
        "execution_after_runner_preflight": bool(
            execution_age is not None and execution_age >= 0
        ),
        "execution_near_runner_preflight": bool(
            execution_age is not None
            and 0 <= execution_age <= MAX_RUNNER_TO_EXECUTION_SECONDS
        ),
        "secret_material_absent": receipt.get(
            "secret_material_included"
        ) is False,
        "access_token_absent": receipt.get(
            "access_token_included"
        ) is False,
        "authorization_token_absent": receipt.get(
            "authorization_token_included"
        ) is False,
        "ledger_append_not_pre_authorized": receipt.get(
            "ledger_append_authorized"
        ) is False,
        "automatic_ledger_append_off": receipt.get(
            "automatic_ledger_append"
        ) is False,
        "production_not_targeted": receipt.get(
            "production_targeted"
        ) is False,
    }

    blockers = [name for name, passed in gates.items() if not passed]
    sources_ready = not blockers

    normalized_provider_evidence = {
        "schema": PROVIDER_RECEIPT_SCHEMA,
        "version": VERSION,
        "materialization_digest": materialization_digest,
        "plan_digest": materialized_plan_digest,
        "authorization_package_digest": _clean(
            auth.get("authorization_package_digest"), 80
        ).lower(),
        "apply_plan_digest": receipt_apply_digest,
        "runner_preflight_digest": receipt_runner_digest,
        "execution_envelope_digest": receipt_envelope_digest,
        "operator_session_id": receipt_session,
        "baseline_evidence_digest": receipt_baseline,
        "target_step_order": 1,
        "target_step_id": LIFECYCLE_STEP_IDS[0],
        "target_username": receipt_username,
        "provider": "KEYCLOAK",
        "realm": "atlasquant-sandbox",
        "provider_user_id": provider_user_id,
        "http_status": 201,
        "exact_readback_verified": True,
        "executed_at": (
            executed_at.isoformat() if executed_at is not None else ""
        ),
        "secret_material_included": False,
        "access_token_included": False,
        "authorization_token_included": False,
        "ledger_append_authorized": False,
        "automatic_ledger_append": False,
        "production_targeted": False,
    } if sources_ready else {}

    provider_evidence_digest = (
        _digest(normalized_provider_evidence)
        if sources_ready
        else ""
    )

    canonical_receipt = {}
    ledger_preview = {}
    if sources_ready:
        canonical_receipt = build_evidence_receipt(
            lifecycle_plan,
            auth,
            step_order=1,
            step_id=LIFECYCLE_STEP_IDS[0],
            evidence_digest=provider_evidence_digest,
            observed_at=executed_at.isoformat(),
            previous_entry_digest=GENESIS_DIGEST,
            mutation_observed=True,
            sandbox_only=True,
            production_targeted=False,
            secret_material_included=False,
        )

        if canonical_receipt.get("state") != (
            "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY"
        ):
            blockers.append("canonical_lifecycle_receipt")
        else:
            ledger_preview = build_lifecycle_evidence_ledger(
                lifecycle_plan,
                auth,
                [canonical_receipt],
            )
            if not (
                ledger_preview.get("state")
                == "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"
                and ledger_preview.get("completed_count") == 1
                and ledger_preview.get("next_expected_step_order") == 2
                and ledger_preview.get("next_expected_step_id")
                == LIFECYCLE_STEP_IDS[1]
                and ledger_preview.get("automatic_next_step_authorized")
                is False
                and ledger_preview.get("executor_enabled") is False
                and ledger_preview.get("production_authorized") is False
                and ledger_preview.get("executes_action") is False
            ):
                blockers.append("ledger_preview")

    ready = not blockers

    review_payload = {
        "provider_evidence_digest": provider_evidence_digest,
        "materialization_digest": materialization_digest,
        "plan_digest": materialized_plan_digest,
        "authorization_package_digest": _clean(
            auth.get("authorization_package_digest"), 80
        ).lower(),
        "canonical_receipt_digest": _clean(
            canonical_receipt.get("receipt_digest"), 80
        ).lower(),
        "ledger_preview_digest": _clean(
            ledger_preview.get("ledger_digest"), 80
        ).lower(),
        "apply_plan_digest": receipt_apply_digest,
        "runner_preflight_digest": receipt_runner_digest,
        "execution_envelope_digest": receipt_envelope_digest,
        "operator_session_id": receipt_session,
        "provider_user_id": provider_user_id,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW"
            if ready
            else "TEAM_ACCESS_STEP1_PROVIDER_RECEIPT_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "provider_evidence_digest": provider_evidence_digest
        if ready else "",
        "materialization_digest": materialization_digest if ready else "",
        "plan_digest": materialized_plan_digest if ready else "",
        "authorization_package_digest": _clean(
            auth.get("authorization_package_digest"), 80
        ).lower() if ready else "",
        "apply_plan_digest": receipt_apply_digest if ready else "",
        "runner_preflight_digest": receipt_runner_digest if ready else "",
        "execution_envelope_digest": receipt_envelope_digest if ready else "",
        "operator_session_id": receipt_session if ready else "",
        "provider_user_id": provider_user_id if ready else "",
        "canonical_lifecycle_receipt": canonical_receipt
        if ready else {},
        "ledger_preview": ledger_preview if ready else {},
        "receipt_review_digest": _digest(review_payload)
        if ready else "",
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "step2_execution_authorized": False,
        "automatic_ledger_append": False,
        "automatic_next_step_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }




def verify_provider_receipt_review(
    review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(review)
    canonical = _mapping(row.get("canonical_lifecycle_receipt"))
    ledger = _mapping(row.get("ledger_preview"))

    provider_evidence_digest = _clean(
        row.get("provider_evidence_digest"), 80
    ).lower()
    materialization_digest = _clean(
        row.get("materialization_digest"), 80
    ).lower()
    plan_digest = _clean(row.get("plan_digest"), 80).lower()
    authorization_package_digest = _clean(
        row.get("authorization_package_digest"), 80
    ).lower()
    apply_plan_digest = _clean(
        row.get("apply_plan_digest"), 80
    ).lower()
    runner_preflight_digest = _clean(
        row.get("runner_preflight_digest"), 80
    ).lower()
    execution_envelope_digest = _clean(
        row.get("execution_envelope_digest"), 80
    ).lower()
    operator_session_id = _clean(
        row.get("operator_session_id"), 64
    ).lower()
    provider_user_id = _clean(
        row.get("provider_user_id"), 160
    )
    canonical_receipt_digest = _clean(
        canonical.get("receipt_digest"), 80
    ).lower()
    ledger_preview_digest = _clean(
        ledger.get("ledger_digest"), 80
    ).lower()
    review_digest = _clean(
        row.get("receipt_review_digest"), 80
    ).lower()

    payload = {
        "provider_evidence_digest": provider_evidence_digest,
        "materialization_digest": materialization_digest,
        "plan_digest": plan_digest,
        "authorization_package_digest": authorization_package_digest,
        "canonical_receipt_digest": canonical_receipt_digest,
        "ledger_preview_digest": ledger_preview_digest,
        "apply_plan_digest": apply_plan_digest,
        "runner_preflight_digest": runner_preflight_digest,
        "execution_envelope_digest": execution_envelope_digest,
        "operator_session_id": operator_session_id,
        "provider_user_id": provider_user_id,
    }

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "state_ready": row.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW",
        "provider_evidence_digest_valid": bool(
            _DIGEST64.fullmatch(provider_evidence_digest)
        ),
        "materialization_digest_valid": bool(
            _DIGEST64.fullmatch(materialization_digest)
        ),
        "plan_digest_valid": bool(_DIGEST64.fullmatch(plan_digest)),
        "authorization_package_digest_valid": bool(
            _DIGEST64.fullmatch(authorization_package_digest)
        ),
        "apply_plan_digest_valid": bool(
            _DIGEST64.fullmatch(apply_plan_digest)
        ),
        "runner_preflight_digest_valid": bool(
            _DIGEST64.fullmatch(runner_preflight_digest)
        ),
        "execution_envelope_digest_valid": bool(
            _DIGEST64.fullmatch(execution_envelope_digest)
        ),
        "operator_session_valid": bool(
            _SESSION32.fullmatch(operator_session_id)
        ),
        "provider_user_id_valid": bool(
            _PROVIDER_ID.fullmatch(provider_user_id)
        ),
        "canonical_receipt_digest_valid": bool(
            _DIGEST64.fullmatch(canonical_receipt_digest)
        ),
        "ledger_preview_digest_valid": bool(
            _DIGEST64.fullmatch(ledger_preview_digest)
        ),
        "ledger_preview_exact": bool(
            ledger.get("state")
            == "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP"
            and ledger.get("completed_count") == 1
            and ledger.get("next_expected_step_order") == 2
            and ledger.get("next_expected_step_id")
            == LIFECYCLE_STEP_IDS[1]
            and ledger.get("automatic_next_step_authorized") is False
            and ledger.get("executor_enabled") is False
            and ledger.get("production_authorized") is False
            and ledger.get("executes_action") is False
        ),
        "append_not_authorized": row.get(
            "ledger_append_authorized"
        ) is False,
        "append_not_performed": row.get(
            "ledger_append_performed"
        ) is False,
        "step2_not_authorized": row.get(
            "step2_execution_authorized"
        ) is False,
        "automatic_append_off": row.get(
            "automatic_ledger_append"
        ) is False,
        "production_not_authorized": row.get(
            "production_authorized"
        ) is False,
        "review_digest_valid": bool(
            _DIGEST64.fullmatch(review_digest)
        ),
        "review_digest_integrity": bool(
            _DIGEST64.fullmatch(review_digest)
            and review_digest == _digest(payload)
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    match = not blockers

    return {
        "schema": (
            "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_"
            "STEP1_PROVIDER_RECEIPT_REVIEW_BINDING_V1"
        ),
        "version": VERSION,
        "state": (
            "STEP1_PROVIDER_RECEIPT_REVIEW_BINDING_MATCH"
            if match
            else "STEP1_PROVIDER_RECEIPT_REVIEW_BINDING_MISMATCH"
        ),
        "binding_match": match,
        "gates": gates,
        "blockers": blockers,
        "receipt_review_digest": review_digest if match else "",
        "canonical_receipt_digest": (
            canonical_receipt_digest if match else ""
        ),
        "ledger_preview_digest": (
            ledger_preview_digest if match else ""
        ),
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "step2_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }

__all__ = [
    "SCHEMA",
    "PROVIDER_RECEIPT_SCHEMA",
    "VERSION",
    "MAX_RUNNER_TO_EXECUTION_SECONDS",
    "provider_receipt_review_policy",
    "validate_provider_receipt_and_preview_ledger",
    "verify_provider_receipt_review",
]
