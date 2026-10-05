"""AION B2B recurring business-action execution preflight.

Final pure/offline gate before any future recurring business-action execution
ceremony.

A clean result means only that the exact owner-authorized, persistence-attested
and writer-attested action may enter a separate execution ceremony. This module
never generates or executes a business command.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_preflight import (
    SCHEMA as AUTHORIZATION_PREFLIGHT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_PREFLIGHT_V1"
ENVIRONMENT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_ENVIRONMENT_V1"
)
MAX_ENVIRONMENT_AGE_SECONDS = 120
MAX_MONTHLY_INFRA_BRL = 200.0

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

REVIEW_SERVICE_STATE = {
    "RENEWAL_REVIEW": "HEALTHY",
    "REMEDIATION_REVIEW": "REMEDIATION",
    "CAPACITY_REVIEW": "CAPACITY_HOLD",
    "INCIDENT_REVIEW": "INCIDENT_REVIEW",
}

ACTION_REQUIRED_PRECONDITIONS = {
    "RENEWAL": (
        "renewal_terms_snapshot_ready",
        "service_continuity_plan_ready",
    ),
    "RENEWAL_WITH_CHANGES": (
        "change_scope_locked",
        "contract_change_packet_ready",
        "service_continuity_plan_ready",
    ),
    "NON_RENEWAL": (
        "offboarding_plan_ready",
        "data_retention_plan_ready",
        "customer_notice_plan_ready",
    ),
    "REMEDIATION": (
        "remediation_plan_ready",
        "remediation_owner_ready",
    ),
    "CAPACITY_RESCOPE": (
        "capacity_plan_ready",
        "quota_change_plan_ready",
    ),
    "REPRICING": (
        "pricing_packet_ready",
        "contract_change_packet_ready",
    ),
    "INCIDENT_REMEDIATION": (
        "incident_containment_ready",
        "incident_remediation_plan_ready",
    ),
    "SERVICE_PAUSE": (
        "pause_plan_ready",
        "customer_impact_assessed",
    ),
    "SERVICE_TERMINATION": (
        "termination_plan_ready",
        "data_retention_plan_ready",
        "customer_impact_assessed",
    ),
}

_AUTHORITY_FIELDS = (
    "business_action_authorized",
    "renewal_authorized",
    "expansion_authorized",
    "non_renewal_authorized",
    "remediation_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "package_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
    "network_called",
    "executes_action",
)

_REQUIRED_TRUE = (
    "tenant_isolation_ready",
    "contract_snapshot_fresh",
    "service_health_fresh",
    "sla_state_fresh",
    "finops_state_fresh",
    "capacity_state_fresh",
    "support_state_fresh",
    "rollback_or_reversal_ready",
    "audit_receipts_ready",
    "idempotency_key_ready",
    "single_action_lock_ready",
    "customer_safe_projection_ready",
    "kill_switch_ready",
    "dry_run_validation_pass",
)

_REQUIRED_FALSE = (
    "security_incident",
    "privacy_incident",
    "scope_breach",
    "provider_degraded",
    "rollback_degraded",
    "contract_conflict",
    "unresolved_billing_dispute",
)

_ENV_DIGEST_FIELDS = (
    "action_parameters_digest",
    "service_health_digest",
    "sla_digest",
    "finops_digest",
    "capacity_digest",
    "support_digest",
    "security_digest",
    "customer_safe_projection_digest",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, limit: int = 420) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(row.get("owner_id"), 120),
        "tenant_id": _text(row.get("tenant_id"), 120),
        "workspace_id": _text(row.get("workspace_id"), 120),
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _refs(value: Any, limit: int = 80) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp required")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "business_action_execution_ceremony_eligible": False,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "execution_environment_digest": "",
        "execution_preflight_digest": "",
        "customer_visible": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def evaluate_owner_renewal_action_execution_preflight(
    *,
    trusted_scope: Mapping[str, Any] | None,
    action_persistence_attestation: Mapping[str, Any] | None,
    action_writer_attestation: Mapping[str, Any] | None,
    authorization_preflight: Mapping[str, Any] | None,
    execution_environment: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    persisted = (
        dict(action_persistence_attestation)
        if isinstance(action_persistence_attestation, Mapping)
        else {}
    )
    writer = (
        dict(action_writer_attestation)
        if isinstance(action_writer_attestation, Mapping)
        else {}
    )
    original = (
        dict(authorization_preflight)
        if isinstance(authorization_preflight, Mapping)
        else {}
    )
    env = (
        dict(execution_environment)
        if isinstance(execution_environment, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    # Exact persisted business-action authorization only.
    if persisted.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("ACTION_PERSISTENCE_ATTESTATION_SCHEMA_INVALID")
    if (
        persisted.get("state")
        != "OWNER_RENEWAL_ACTION_RECORD_PERSISTENCE_ATTESTED"
    ):
        blockers.append("ACTION_PERSISTENCE_NOT_ATTESTED")
    if persisted.get("authorization_decision") != "AUTHORIZE_BUSINESS_ACTION":
        if persisted.get("authorization_decision") == "DENY_BUSINESS_ACTION":
            blockers.append("BUSINESS_ACTION_DENIED")
        else:
            blockers.append("BUSINESS_ACTION_AUTHORIZATION_DECISION_INVALID")
    if _scope(persisted.get("scope")) != trusted:
        blockers.append("ACTION_PERSISTENCE_SCOPE_MISMATCH")
    if persisted.get("action_record_persisted") is not True:
        blockers.append("ACTION_RECORD_NOT_PERSISTED")
    if persisted.get("persistence_attested") is not True:
        blockers.append("ACTION_PERSISTENCE_NOT_ATTESTED")
    if persisted.get("receipt_consistency_verified") is not True:
        blockers.append("ACTION_RECEIPT_CONSISTENCY_NOT_VERIFIED")
    if persisted.get("writer_identity_verified") is not False:
        blockers.append("ACTION_PERSISTENCE_WRITER_BOUNDARY_INVALID")
    if (
        persisted.get("eligible_for_action_execution_preflight")
        is not True
    ):
        blockers.append("ACTION_NOT_EXECUTION_PREFLIGHT_ELIGIBLE")
    if persisted.get("storage_write_performed") is not False:
        blockers.append("ACTION_PERSISTENCE_WRITE_FLAG_UNSAFE")

    for key in _AUTHORITY_FIELDS:
        if persisted.get(key) is not False:
            blockers.append("ACTION_PERSISTENCE_UNSAFE_FIELD:" + key)

    choice = _text(persisted.get("requested_choice"), 120)
    family = _text(persisted.get("action_family"), 120)
    review_type = _text(persisted.get("review_type"), 120)
    customer_id = _text(persisted.get("customer_id"), 120)
    pilot_id = _text(persisted.get("pilot_id"), 120)
    package = _text(persisted.get("package"), 40).upper()
    action_record_digest = _text(
        persisted.get("action_record_digest"),
        180,
    )
    receipt_digest = _text(persisted.get("receipt_digest"), 180)
    after_checkpoint_digest = _text(
        persisted.get("after_checkpoint_digest"),
        180,
    )
    authorization_preflight_digest = _text(
        persisted.get("authorization_preflight_digest"),
        180,
    )
    contract_digest = _text(persisted.get("contract_digest"), 180)
    cycle_digest = _text(persisted.get("cycle_evidence_digest"), 180)

    for label, value in (
        ("REQUESTED_CHOICE", choice),
        ("ACTION_FAMILY", family),
        ("REVIEW_TYPE", review_type),
        ("CUSTOMER_ID", customer_id),
        ("PILOT_ID", pilot_id),
        ("PACKAGE", package),
        ("ACTION_RECORD_DIGEST", action_record_digest),
        ("RECEIPT_DIGEST", receipt_digest),
        ("AFTER_CHECKPOINT_DIGEST", after_checkpoint_digest),
        ("AUTHORIZATION_PREFLIGHT_DIGEST", authorization_preflight_digest),
        ("CONTRACT_DIGEST", contract_digest),
        ("CYCLE_EVIDENCE_DIGEST", cycle_digest),
    ):
        if not value:
            blockers.append("ACTION_PERSISTENCE_" + label + "_REQUIRED")

    if family not in ACTION_REQUIRED_PRECONDITIONS:
        blockers.append("ACTION_FAMILY_UNSUPPORTED")
    expected_service_state = REVIEW_SERVICE_STATE.get(review_type)
    if not expected_service_state:
        blockers.append("ACTION_REVIEW_TYPE_UNSUPPORTED")

    # Trusted writer must bind the exact persistence receipt.
    if writer.get("schema") != WRITER_SCHEMA:
        blockers.append("ACTION_WRITER_SCHEMA_INVALID")
    if writer.get("state") != "ACTION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED":
        blockers.append("ACTION_WRITER_AUTHORITY_NOT_ATTESTED")
    if writer.get("writer_identity_verified") is not True:
        blockers.append("ACTION_WRITER_IDENTITY_NOT_VERIFIED")
    if writer.get("writer_authority_verified") is not True:
        blockers.append("ACTION_WRITER_AUTHORITY_NOT_VERIFIED")
    if writer.get("receipt_binding_verified") is not True:
        blockers.append("ACTION_WRITER_RECEIPT_BINDING_NOT_VERIFIED")
    if writer.get("nonce_registered") is not True:
        blockers.append("ACTION_WRITER_NONCE_NOT_REGISTERED")
    if writer.get("checkpoint_write_performed") is not False:
        blockers.append("ACTION_WRITER_WRITE_FLAG_UNSAFE")
    if (
        writer.get("eligible_for_action_execution_preflight")
        is not True
    ):
        blockers.append("ACTION_WRITER_NOT_EXECUTION_PREFLIGHT_ELIGIBLE")

    for key, expected in (
        ("customer_id", customer_id),
        ("pilot_id", pilot_id),
        ("requested_choice", choice),
        ("action_family", family),
        ("authorization_decision", "AUTHORIZE_BUSINESS_ACTION"),
        ("receipt_digest", receipt_digest),
        ("after_checkpoint_digest", after_checkpoint_digest),
        ("action_record_digest", action_record_digest),
    ):
        if _text(writer.get(key), 180) != expected:
            blockers.append("ACTION_WRITER_BINDING_MISMATCH:" + key)

    for key in _AUTHORITY_FIELDS:
        if writer.get(key) is not False:
            blockers.append("ACTION_WRITER_UNSAFE_FIELD:" + key)

    # Original authorization preflight must remain the exact same review object.
    if original.get("schema") != AUTHORIZATION_PREFLIGHT_SCHEMA:
        blockers.append("ORIGINAL_AUTHORIZATION_PREFLIGHT_SCHEMA_INVALID")
    if (
        original.get("state")
        != "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY"
    ):
        blockers.append("ORIGINAL_AUTHORIZATION_PREFLIGHT_NOT_READY")
    if original.get("blockers"):
        blockers.append("ORIGINAL_AUTHORIZATION_PREFLIGHT_HAS_BLOCKERS")
    if _scope(original.get("scope")) != trusted:
        blockers.append("ORIGINAL_AUTHORIZATION_PREFLIGHT_SCOPE_MISMATCH")
    if _text(original.get("customer_id"), 120) != customer_id:
        blockers.append("ORIGINAL_AUTHORIZATION_CUSTOMER_MISMATCH")
    if _text(original.get("pilot_id"), 120) != pilot_id:
        blockers.append("ORIGINAL_AUTHORIZATION_PILOT_MISMATCH")
    if _text(original.get("package"), 40).upper() != package:
        blockers.append("ORIGINAL_AUTHORIZATION_PACKAGE_MISMATCH")
    if _text(original.get("review_type"), 120) != review_type:
        blockers.append("ORIGINAL_AUTHORIZATION_REVIEW_TYPE_MISMATCH")
    if _text(original.get("requested_choice"), 120) != choice:
        blockers.append("ORIGINAL_AUTHORIZATION_CHOICE_MISMATCH")
    if _text(original.get("action_family"), 120) != family:
        blockers.append("ORIGINAL_AUTHORIZATION_FAMILY_MISMATCH")
    if (
        _text(original.get("preflight_digest"), 180)
        != authorization_preflight_digest
    ):
        blockers.append("ORIGINAL_AUTHORIZATION_PREFLIGHT_DIGEST_MISMATCH")
    if original.get("action_ceremony_eligible") is not True:
        blockers.append("ORIGINAL_AUTHORIZATION_CEREMONY_NOT_ELIGIBLE")
    if original.get("requires_fresh_recheck_before_ceremony") is not True:
        blockers.append("ORIGINAL_AUTHORIZATION_FRESH_RECHECK_BOUNDARY_MISSING")
    if original.get("action_request_issued") is not False:
        blockers.append("ORIGINAL_AUTHORIZATION_REQUEST_ALREADY_ISSUED")
    if original.get("owner_action_signature_verified") is not False:
        blockers.append("ORIGINAL_AUTHORIZATION_SIGNATURE_PREVERIFIED_UNSAFE")
    for key in _AUTHORITY_FIELDS:
        if original.get(key) is not False:
            blockers.append("ORIGINAL_AUTHORIZATION_UNSAFE_FIELD:" + key)

    # Fresh execution environment.
    if env.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("EXECUTION_ENVIRONMENT_SCHEMA_INVALID")
    if env.get("state") != "VERIFIED":
        blockers.append("EXECUTION_ENVIRONMENT_NOT_VERIFIED")
    if _scope(env) != trusted:
        blockers.append("EXECUTION_ENVIRONMENT_SCOPE_MISMATCH")
    if _text(env.get("customer_id"), 120) != customer_id:
        blockers.append("EXECUTION_ENVIRONMENT_CUSTOMER_MISMATCH")
    if _text(env.get("pilot_id"), 120) != pilot_id:
        blockers.append("EXECUTION_ENVIRONMENT_PILOT_MISMATCH")
    if _text(env.get("package"), 40).upper() != package:
        blockers.append("EXECUTION_ENVIRONMENT_PACKAGE_MISMATCH")
    if _text(env.get("review_type"), 120) != review_type:
        blockers.append("EXECUTION_ENVIRONMENT_REVIEW_TYPE_MISMATCH")
    if _text(env.get("requested_choice"), 120) != choice:
        blockers.append("EXECUTION_ENVIRONMENT_CHOICE_MISMATCH")
    if _text(env.get("action_family"), 120) != family:
        blockers.append("EXECUTION_ENVIRONMENT_FAMILY_MISMATCH")
    if env.get("execution_mode") != "CONTROLLED_MANAGED_SERVICE_ACTION":
        blockers.append("EXECUTION_MODE_INVALID")
    if env.get("action_window_reserved") is not True:
        blockers.append("ACTION_WINDOW_NOT_RESERVED")
    if env.get("production_scope_expansion_allowed") is not False:
        blockers.append("PRODUCTION_SCOPE_EXPANSION_FORBIDDEN")
    if _text(env.get("contract_digest"), 180) != contract_digest:
        blockers.append("EXECUTION_CONTRACT_DIGEST_MISMATCH")
    if _text(env.get("cycle_evidence_digest"), 180) != cycle_digest:
        blockers.append("EXECUTION_CYCLE_DIGEST_MISMATCH")
    if _text(env.get("service_state"), 120) != expected_service_state:
        blockers.append("EXECUTION_SERVICE_STATE_MISMATCH")

    for key in _REQUIRED_TRUE:
        if env.get(key) is not True:
            blockers.append("EXECUTION_ENVIRONMENT_REQUIRED:" + key)
    for key in _REQUIRED_FALSE:
        if env.get(key) is not False:
            blockers.append("EXECUTION_ENVIRONMENT_BLOCKED:" + key)

    for key in _ENV_DIGEST_FIELDS:
        if not _SHA256_RE.fullmatch(_text(env.get(key), 180)):
            blockers.append("EXECUTION_ENVIRONMENT_DIGEST_INVALID:" + key)

    preconditions = (
        dict(env.get("action_preconditions"))
        if isinstance(env.get("action_preconditions"), Mapping)
        else {}
    )
    for key in ACTION_REQUIRED_PRECONDITIONS.get(family, ()):
        if preconditions.get(key) is not True:
            blockers.append("EXECUTION_ACTION_PRECONDITION_MISSING:" + key)

    reserved_units = _positive_int(env.get("reserved_capacity_units"))
    available_units = _positive_int(env.get("available_capacity_units"))
    if reserved_units is None:
        blockers.append("EXECUTION_RESERVED_CAPACITY_INVALID")
    if available_units is None:
        blockers.append("EXECUTION_AVAILABLE_CAPACITY_INVALID")
    if (
        reserved_units is not None
        and available_units is not None
        and reserved_units > available_units
    ):
        blockers.append("EXECUTION_CAPACITY_INSUFFICIENT")

    planned_infra = _number(env.get("planned_monthly_infra_brl"))
    if planned_infra is None or planned_infra < 0:
        blockers.append("EXECUTION_MONTHLY_INFRA_INVALID")
    elif planned_infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("EXECUTION_MONTHLY_INFRA_CAP_EXCEEDED")

    env_refs = _refs(env.get("evidence_refs"))
    if len(env_refs) < 8:
        blockers.append("EXECUTION_ENVIRONMENT_EVIDENCE_INSUFFICIENT")

    try:
        checked = _parse_ts(env.get("checked_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("EXECUTION_ENVIRONMENT_TIME_INVALID")
    else:
        age = (now - checked).total_seconds()
        if age < -5:
            blockers.append("EXECUTION_ENVIRONMENT_FROM_FUTURE")
        elif age > MAX_ENVIRONMENT_AGE_SECONDS:
            blockers.append("EXECUTION_ENVIRONMENT_STALE")

    environment_material = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "service_state": env.get("service_state"),
        "execution_mode": env.get("execution_mode"),
        "checked_at": env.get("checked_at"),
        "action_window_reserved": env.get("action_window_reserved"),
        "production_scope_expansion_allowed": env.get(
            "production_scope_expansion_allowed"
        ),
        "contract_digest": env.get("contract_digest"),
        "cycle_evidence_digest": env.get("cycle_evidence_digest"),
        "required_true": {key: env.get(key) for key in _REQUIRED_TRUE},
        "required_false": {key: env.get(key) for key in _REQUIRED_FALSE},
        "action_preconditions": {
            key: preconditions.get(key)
            for key in ACTION_REQUIRED_PRECONDITIONS.get(family, ())
        },
        "snapshot_digests": {
            key: env.get(key)
            for key in _ENV_DIGEST_FIELDS
        },
        "reserved_capacity_units": reserved_units,
        "available_capacity_units": available_units,
        "planned_monthly_infra_brl": planned_infra,
        "evidence_refs": env_refs,
    }
    environment_digest = _digest(environment_material)

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return _blocked(*blockers)

    preflight_material = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "action_record_digest": action_record_digest,
        "action_persistence_receipt_digest": receipt_digest,
        "action_checkpoint_digest": after_checkpoint_digest,
        "action_writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "authorization_preflight_digest": authorization_preflight_digest,
        "action_parameters_digest": env["action_parameters_digest"],
        "execution_environment_digest": environment_digest,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY",
        "blockers": [],
        "scope": dict(trusted),
        "owner_id": trusted["owner_id"],
        "tenant_id": trusted["tenant_id"],
        "workspace_id": trusted["workspace_id"],
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "action_record_digest": action_record_digest,
        "action_persistence_receipt_digest": receipt_digest,
        "action_checkpoint_digest": after_checkpoint_digest,
        "action_writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "authorization_preflight_digest": authorization_preflight_digest,
        "action_parameters_digest": env["action_parameters_digest"],
        "execution_environment_digest": environment_digest,
        "execution_preflight_digest": _digest(preflight_material),
        "business_action_execution_ceremony_eligible": True,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "customer_visible": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "ENVIRONMENT_SCHEMA",
    "MAX_ENVIRONMENT_AGE_SECONDS",
    "MAX_MONTHLY_INFRA_BRL",
    "REVIEW_SERVICE_STATE",
    "ACTION_REQUIRED_PRECONDITIONS",
    "evaluate_owner_renewal_action_execution_preflight",
]
