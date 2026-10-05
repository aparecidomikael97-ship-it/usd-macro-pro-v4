"""AION B2B Pilot Activation Execution Preflight V1.

Final pure/offline gate before any future activation-execution ceremony.

A pilot can become READY_FOR_ACTIVATION_EXECUTION_CEREMONY only when:
- the exact activation authorization record is persistence-attested;
- the exact activation persistence receipt has a cryptographically attested writer;
- the original activation preflight identity/digests remain unchanged;
- fresh execution-environment evidence passes stricter fail-closed checks.

This module never generates an activation command, never authorizes activation,
never activates a pilot and never performs customer/provider/CRM/deploy actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PREFLIGHT_V1"
PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PERSISTENCE_ATTESTATION_V1"
)
WRITER_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_WRITER_VERIFICATION_V1"
)
ACTIVATION_PREFLIGHT_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PREFLIGHT_V1"
)
ENVIRONMENT_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_ENVIRONMENT_V1"
)

MAX_ENVIRONMENT_AGE_SECONDS = 120
MAX_MONTHLY_INFRA_BRL = 200.0


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


def _refs(value: Any, limit: int = 60) -> list[str]:
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


def evaluate_activation_execution_preflight(
    *,
    trusted_scope: Mapping[str, Any] | None,
    activation_persistence_attestation: Mapping[str, Any] | None,
    activation_writer_attestation: Mapping[str, Any] | None,
    activation_preflight: Mapping[str, Any] | None,
    execution_environment: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Return execution-ceremony eligibility only; never execution authority."""
    trusted = _scope(trusted_scope)
    persisted = (
        dict(activation_persistence_attestation)
        if isinstance(activation_persistence_attestation, Mapping)
        else {}
    )
    writer = (
        dict(activation_writer_attestation)
        if isinstance(activation_writer_attestation, Mapping)
        else {}
    )
    original = (
        dict(activation_preflight)
        if isinstance(activation_preflight, Mapping)
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

    # Exact persisted activation authorization only.
    if persisted.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("ACTIVATION_PERSISTENCE_ATTESTATION_SCHEMA_INVALID")
    if (
        persisted.get("state")
        != "ACTIVATION_RECORD_PERSISTENCE_ATTESTED_AUTHORIZE"
    ):
        if persisted.get("state") == "ACTIVATION_RECORD_PERSISTENCE_ATTESTED_DENY":
            blockers.append("PILOT_ACTIVATION_DENIED")
        else:
            blockers.append("ACTIVATION_PERSISTENCE_NOT_AUTHORIZED")
    if persisted.get("decision") != "AUTHORIZE_PILOT_ACTIVATION":
        blockers.append("PERSISTED_ACTIVATION_DECISION_NOT_AUTHORIZE")
    if _scope(persisted.get("scope")) != trusted:
        blockers.append("ACTIVATION_PERSISTENCE_SCOPE_MISMATCH")
    if persisted.get("activation_record_persisted") is not True:
        blockers.append("ACTIVATION_RECORD_NOT_PERSISTED")
    if persisted.get("persistence_attested") is not True:
        blockers.append("ACTIVATION_PERSISTENCE_NOT_ATTESTED")
    if persisted.get("receipt_consistency_verified") is not True:
        blockers.append("ACTIVATION_RECEIPT_CONSISTENCY_NOT_VERIFIED")
    if persisted.get("writer_identity_verified") is not False:
        blockers.append("ACTIVATION_PERSISTENCE_WRITER_BOUNDARY_INVALID")
    if persisted.get("activation_authorization_intent") is not True:
        blockers.append("ACTIVATION_AUTHORIZATION_INTENT_MISSING")
    if persisted.get("activation_denial_intent") is not False:
        blockers.append("ACTIVATION_DENIAL_FLAG_INVALID")
    if (
        persisted.get("eligible_for_activation_execution_preflight")
        is not True
    ):
        blockers.append("ACTIVATION_NOT_EXECUTION_PREFLIGHT_ELIGIBLE")

    for key in (
        "pilot_activation_authorized",
        "pilot_activated",
        "customer_contact_authorized",
        "billing_authorized",
        "provisioning_authorized",
        "deploy_authorized",
        "production_mutation_authorized",
        "storage_write_performed",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if persisted.get(key) is not False:
            blockers.append("ACTIVATION_PERSISTENCE_UNSAFE_FIELD:" + key)

    candidate_id = _text(persisted.get("candidate_id"), 120)
    proposal_id = _text(persisted.get("proposal_id"), 120)
    pilot_id = _text(persisted.get("pilot_id"), 120)
    environment_digest = _text(persisted.get("environment_digest"), 180)
    original_preflight_digest = _text(
        persisted.get("preflight_digest"),
        180,
    )
    activation_record_digest = _text(
        persisted.get("activation_record_digest"),
        180,
    )
    receipt_digest = _text(persisted.get("receipt_digest"), 180)
    checkpoint_master_digest = _text(
        persisted.get("checkpoint_master_digest"),
        180,
    )
    for label, value in (
        ("CANDIDATE_ID", candidate_id),
        ("PROPOSAL_ID", proposal_id),
        ("PILOT_ID", pilot_id),
        ("ENVIRONMENT_DIGEST", environment_digest),
        ("PREFLIGHT_DIGEST", original_preflight_digest),
        ("ACTIVATION_RECORD_DIGEST", activation_record_digest),
        ("RECEIPT_DIGEST", receipt_digest),
        ("CHECKPOINT_MASTER_DIGEST", checkpoint_master_digest),
    ):
        if not value:
            blockers.append("ACTIVATION_PERSISTENCE_" + label + "_REQUIRED")

    # Writer for activation-record checkpoint must bind exact persistence proof.
    if writer.get("schema") != WRITER_SCHEMA:
        blockers.append("ACTIVATION_WRITER_SCHEMA_INVALID")
    if (
        writer.get("state")
        != "ACTIVATION_CHECKPOINT_WRITER_AUTHORITY_ATTESTED"
    ):
        blockers.append("ACTIVATION_WRITER_AUTHORITY_NOT_ATTESTED")
    if writer.get("writer_identity_verified") is not True:
        blockers.append("ACTIVATION_WRITER_IDENTITY_NOT_VERIFIED")
    if writer.get("writer_authority_verified") is not True:
        blockers.append("ACTIVATION_WRITER_AUTHORITY_NOT_VERIFIED")
    if writer.get("receipt_binding_verified") is not True:
        blockers.append("ACTIVATION_WRITER_RECEIPT_NOT_VERIFIED")
    if writer.get("nonce_registered") is not True:
        blockers.append("ACTIVATION_WRITER_NONCE_NOT_REGISTERED")
    if _text(writer.get("pilot_id"), 120) != pilot_id:
        blockers.append("ACTIVATION_WRITER_PILOT_MISMATCH")
    if _text(writer.get("receipt_digest"), 180) != receipt_digest:
        blockers.append("ACTIVATION_WRITER_RECEIPT_DIGEST_MISMATCH")
    if (
        _text(writer.get("after_checkpoint_digest"), 180)
        != checkpoint_master_digest
    ):
        blockers.append("ACTIVATION_WRITER_CHECKPOINT_DIGEST_MISMATCH")
    if (
        _text(writer.get("activation_record_digest"), 180)
        != activation_record_digest
    ):
        blockers.append("ACTIVATION_WRITER_RECORD_DIGEST_MISMATCH")

    for key in (
        "pilot_activation_authorized",
        "pilot_activated",
        "checkpoint_write_performed",
        "customer_contact_authorized",
        "billing_authorized",
        "provisioning_authorized",
        "deploy_authorized",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if writer.get(key) is not False:
            blockers.append("ACTIVATION_WRITER_UNSAFE_FIELD:" + key)

    # Original activation preflight remains immutable identity/evidence.
    if original.get("schema") != ACTIVATION_PREFLIGHT_SCHEMA:
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_SCHEMA_INVALID")
    if original.get("state") != "READY_FOR_ACTIVATION_CEREMONY":
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_NOT_READY")
    if _scope(original.get("scope")) != trusted:
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_SCOPE_MISMATCH")
    if _text(original.get("candidate_id"), 120) != candidate_id:
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_CANDIDATE_MISMATCH")
    if _text(original.get("proposal_id"), 120) != proposal_id:
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_PROPOSAL_MISMATCH")
    if _text(original.get("pilot_id"), 120) != pilot_id:
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_PILOT_MISMATCH")
    if (
        _text(original.get("environment_digest"), 180)
        != environment_digest
    ):
        blockers.append("ORIGINAL_ACTIVATION_ENVIRONMENT_DIGEST_MISMATCH")
    if (
        _text(original.get("preflight_digest"), 180)
        != original_preflight_digest
    ):
        blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_DIGEST_MISMATCH")
    if original.get("activation_ceremony_eligible") is not True:
        blockers.append("ORIGINAL_ACTIVATION_CEREMONY_NOT_ELIGIBLE")
    for key in (
        "activation_request_issued",
        "owner_activation_signature_verified",
        "pilot_activation_authorized",
        "pilot_activated",
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "provisioning_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "provider_called",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if original.get(key) is not False:
            blockers.append("ORIGINAL_ACTIVATION_PREFLIGHT_UNSAFE_FIELD:" + key)

    # Stricter fresh execution environment.
    if env.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("EXECUTION_ENVIRONMENT_SCHEMA_INVALID")
    if env.get("state") != "VERIFIED":
        blockers.append("EXECUTION_ENVIRONMENT_NOT_VERIFIED")
    if _scope(env) != trusted:
        blockers.append("EXECUTION_ENVIRONMENT_SCOPE_MISMATCH")
    if _text(env.get("pilot_id"), 120) != pilot_id:
        blockers.append("EXECUTION_ENVIRONMENT_PILOT_MISMATCH")
    if env.get("execution_mode") != "CONTROLLED_PILOT":
        blockers.append("EXECUTION_MODE_INVALID")
    if env.get("activation_slot_reserved") is not True:
        blockers.append("ACTIVATION_SLOT_NOT_RESERVED")
    if env.get("production_scope_expansion_allowed") is not False:
        blockers.append("PRODUCTION_SCOPE_EXPANSION_FORBIDDEN")

    required_true = (
        "tenant_isolation_ready",
        "secrets_vault_ready",
        "rollback_ready",
        "monitoring_ready",
        "audit_receipts_ready",
        "integration_health_ready",
        "kill_switch_ready",
        "idempotency_key_ready",
        "single_pilot_lock_ready",
        "dry_run_validation_pass",
    )
    for key in required_true:
        if env.get(key) is not True:
            blockers.append("EXECUTION_ENVIRONMENT_" + key.upper() + "_REQUIRED")

    required_false = (
        "security_incident",
        "privacy_incident",
        "scope_breach",
        "provider_degraded",
        "rollback_degraded",
    )
    for key in required_false:
        if env.get(key) is not False:
            blockers.append("EXECUTION_ENVIRONMENT_" + key.upper() + "_BLOCKED")

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
    if len(env_refs) < 6:
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

    execution_environment_material = {
        "scope": trusted,
        "pilot_id": pilot_id,
        "execution_mode": env.get("execution_mode"),
        "checked_at": env.get("checked_at"),
        "activation_slot_reserved": env.get("activation_slot_reserved"),
        "production_scope_expansion_allowed": env.get(
            "production_scope_expansion_allowed"
        ),
        "required_true": {key: env.get(key) for key in required_true},
        "required_false": {key: env.get(key) for key in required_false},
        "reserved_capacity_units": reserved_units,
        "available_capacity_units": available_units,
        "planned_monthly_infra_brl": planned_infra,
        "evidence_refs": env_refs,
    }
    execution_environment_digest = _digest(execution_environment_material)

    blockers = list(dict.fromkeys(blockers))
    preflight_material = {
        "scope": trusted,
        "candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "pilot_id": pilot_id,
        "activation_record_digest": activation_record_digest,
        "activation_persistence_attestation_digest": _text(
            persisted.get("attestation_digest"),
            180,
        ),
        "activation_writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "original_activation_preflight_digest": original_preflight_digest,
        "execution_environment_digest": execution_environment_digest,
    }

    return {
        "schema": SCHEMA,
        "state": (
            "READY_FOR_ACTIVATION_EXECUTION_CEREMONY"
            if not blockers
            else "BLOCKED"
        ),
        "scope": trusted,
        "candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "pilot_id": pilot_id,
        "blockers": blockers,
        "execution_environment_digest": execution_environment_digest,
        "execution_preflight_digest": _digest(preflight_material),
        "activation_execution_ceremony_eligible": not blockers,
        "human_execution_confirmation_required": True,
        "execution_request_issued": False,
        "owner_execution_signature_verified": False,
        "activation_command_generated": False,
        "activation_command_executed": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "provider_called": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PERSISTENCE_SCHEMA",
    "WRITER_SCHEMA",
    "ACTIVATION_PREFLIGHT_SCHEMA",
    "ENVIRONMENT_SCHEMA",
    "MAX_ENVIRONMENT_AGE_SECONDS",
    "MAX_MONTHLY_INFRA_BRL",
    "evaluate_activation_execution_preflight",
]
