"""AION B2B recurring-service business action preflight.

Pure/offline gate between a persistence-attested owner decision and any future
business-action authorization ceremony.

A clean result means only that the exact persisted choice is eligible to enter a
separate authorization ceremony. It never issues a request, verifies an action
signature, authorizes or executes renewal, non-renewal, remediation, repricing,
capacity changes, pause, termination, billing, customer contact or production
mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_review import (
    SCHEMA as OWNER_REVIEW_SCHEMA,
    STATE_DECISION,
)
from atlasquant_aion_b2b_owner_renewal_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)
from atlasquant_aion_b2b_value_bound_service_cycle import (
    SCHEMA as SERVICE_CYCLE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_PREFLIGHT_V1"
ENVIRONMENT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ENVIRONMENT_V1"
)
MAX_ENVIRONMENT_AGE_SECONDS = 300
MAX_MONTHLY_INFRA_BRL = 200.0

ACTION_FAMILY = {
    "RENEW_AS_IS_REVIEW": "RENEWAL",
    "RENEW_WITH_CHANGES_REVIEW": "RENEWAL_WITH_CHANGES",
    "NON_RENEWAL_REVIEW": "NON_RENEWAL",
    "REMEDIATION_PLAN_REVIEW": "REMEDIATION",
    "RESCOPE_CAPACITY_REVIEW": "CAPACITY_RESCOPE",
    "REPRICE_REVIEW": "REPRICING",
    "INCIDENT_REMEDIATION_REVIEW": "INCIDENT_REMEDIATION",
    "PAUSE_SERVICE_REVIEW": "SERVICE_PAUSE",
    "TERMINATION_REVIEW": "SERVICE_TERMINATION",
}

CHOICE_PRECONDITIONS = {
    "RENEW_AS_IS_REVIEW": (
        "renewal_terms_confirmed",
        "no_material_change_requested",
    ),
    "RENEW_WITH_CHANGES_REVIEW": (
        "change_scope_defined",
        "contract_change_review_ready",
    ),
    "NON_RENEWAL_REVIEW": (
        "offboarding_plan_ready",
        "data_retention_plan_ready",
    ),
    "REMEDIATION_PLAN_REVIEW": (
        "remediation_plan_ready",
        "remediation_owner_identified",
    ),
    "RESCOPE_CAPACITY_REVIEW": (
        "capacity_plan_ready",
        "capacity_impact_assessed",
    ),
    "REPRICE_REVIEW": (
        "pricing_rationale_ready",
        "pricing_review_packet_ready",
    ),
    "INCIDENT_REMEDIATION_REVIEW": (
        "incident_remediation_plan_ready",
        "incident_containment_ready",
    ),
    "PAUSE_SERVICE_REVIEW": (
        "pause_plan_ready",
        "customer_impact_assessed",
    ),
    "TERMINATION_REVIEW": (
        "termination_plan_ready",
        "data_retention_plan_ready",
        "customer_impact_assessed",
    ),
}

_ACTION_AUTHORITY_FIELDS = (
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

_UPSTREAM_FALSE_FIELDS = (
    "renewal_authorized",
    "expansion_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
    "executes_action",
)

_REVIEW_FALSE_FIELDS = (
    "automatic_owner_choice",
    "automatic_renewal",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pause",
    "automatic_termination",
    "automatic_billing",
    "automatic_pricing_change",
    "automatic_quota_increase",
    "automatic_role_change",
    "automatic_integration_change",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "provider_called",
    "crm_write",
    "production_mutation",
    "executes_action",
)

_CYCLE_FALSE_FIELDS = (
    "automatic_renewal",
    "automatic_expansion",
    "automatic_package_change",
    "automatic_pause",
    "automatic_termination",
    "automatic_billing",
    "automatic_quota_increase",
    "automatic_role_change",
    "automatic_integration_change",
    "automatic_customer_contact",
    "automatic_provisioning",
    "automatic_deploy",
    "provider_called",
    "production_mutation",
    "executes_action",
)

_ENVIRONMENT_READY_FIELDS = (
    "tenant_isolation_ready",
    "audit_receipts_ready",
    "service_snapshot_fresh",
    "contract_snapshot_fresh",
    "support_state_known",
    "billing_state_known",
    "capacity_state_known",
    "customer_safe_projection_ready",
    "rollback_or_reversal_plan_ready",
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
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


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


def _refs(value: Any, limit: int = 60) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "action_family": "",
        "action_ceremony_eligible": False,
        "action_request_issued": False,
        "owner_action_signature_required": True,
        "owner_action_signature_verified": False,
        "preflight_digest": "",
        "environment_digest": "",
        "customer_visible": False,
        **{key: False for key in _ACTION_AUTHORITY_FIELDS},
    }


def evaluate_owner_renewal_action_preflight(
    *,
    trusted_scope: Mapping[str, Any] | None,
    persistence_attestation: Mapping[str, Any] | None,
    writer_attestation: Mapping[str, Any] | None,
    owner_review_packet: Mapping[str, Any] | None,
    service_cycle: Mapping[str, Any] | None,
    action_environment: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    persisted = (
        dict(persistence_attestation)
        if isinstance(persistence_attestation, Mapping)
        else {}
    )
    writer = (
        dict(writer_attestation)
        if isinstance(writer_attestation, Mapping)
        else {}
    )
    review = (
        dict(owner_review_packet)
        if isinstance(owner_review_packet, Mapping)
        else {}
    )
    cycle = (
        dict(service_cycle)
        if isinstance(service_cycle, Mapping)
        else {}
    )
    env = (
        dict(action_environment)
        if isinstance(action_environment, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    # Exact persistence proof.
    if persisted.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("PERSISTENCE_ATTESTATION_SCHEMA_INVALID")
    if (
        persisted.get("state")
        != "OWNER_RENEWAL_DECISION_PERSISTENCE_ATTESTED"
    ):
        blockers.append("PERSISTENCE_ATTESTATION_NOT_READY")
    if _scope(persisted.get("scope")) != trusted:
        blockers.append("PERSISTENCE_SCOPE_MISMATCH")
    if persisted.get("owner_decision_recorded") is not True:
        blockers.append("OWNER_DECISION_NOT_RECORDED")
    if persisted.get("decision_persisted") is not True:
        blockers.append("OWNER_DECISION_NOT_PERSISTED")
    if persisted.get("persistence_attested") is not True:
        blockers.append("OWNER_DECISION_PERSISTENCE_NOT_ATTESTED")
    if persisted.get("receipt_consistency_verified") is not True:
        blockers.append("PERSISTENCE_RECEIPT_NOT_VERIFIED")
    if persisted.get("writer_identity_verified") is not False:
        blockers.append("PERSISTENCE_WRITER_BOUNDARY_INVALID")
    if persisted.get("eligible_for_action_preflight") is not True:
        blockers.append("PERSISTENCE_NOT_ACTION_PREFLIGHT_ELIGIBLE")
    if persisted.get("storage_write_performed") is not False:
        blockers.append("PERSISTENCE_STORAGE_WRITE_FLAG_UNSAFE")
    if persisted.get("network_called") is not False:
        blockers.append("PERSISTENCE_NETWORK_FLAG_UNSAFE")

    for key in _UPSTREAM_FALSE_FIELDS:
        if persisted.get(key) is not False:
            blockers.append("PERSISTENCE_UNSAFE_FIELD:" + key)

    choice = _text(persisted.get("requested_choice"), 120)
    action_family = ACTION_FAMILY.get(choice, "")
    if not action_family:
        blockers.append("PERSISTED_OWNER_CHOICE_UNSUPPORTED")

    customer_id = _text(persisted.get("customer_id"), 120)
    pilot_id = _text(persisted.get("pilot_id"), 120)
    package = _text(persisted.get("package"), 40).upper()
    review_type = _text(persisted.get("review_type"), 120)
    receipt_digest = _text(persisted.get("receipt_digest"), 180)
    checkpoint_digest = _text(
        persisted.get("after_checkpoint_digest"),
        180,
    )
    decision_record_digest = _text(
        persisted.get("decision_record_digest"),
        180,
    )
    review_digest = _text(
        persisted.get("owner_review_packet_digest"),
        180,
    )
    cycle_digest = _text(
        persisted.get("cycle_evidence_digest"),
        180,
    )
    contract_digest = _text(persisted.get("contract_digest"), 180)
    conversion_digest = _text(
        persisted.get("value_bound_conversion_digest"),
        180,
    )

    for label, value in (
        ("CUSTOMER_ID", customer_id),
        ("PILOT_ID", pilot_id),
        ("PACKAGE", package),
        ("REVIEW_TYPE", review_type),
        ("RECEIPT_DIGEST", receipt_digest),
        ("CHECKPOINT_DIGEST", checkpoint_digest),
        ("DECISION_RECORD_DIGEST", decision_record_digest),
        ("OWNER_REVIEW_PACKET_DIGEST", review_digest),
        ("CYCLE_EVIDENCE_DIGEST", cycle_digest),
        ("CONTRACT_DIGEST", contract_digest),
        ("VALUE_BOUND_CONVERSION_DIGEST", conversion_digest),
    ):
        if not value:
            blockers.append("PERSISTENCE_" + label + "_REQUIRED")

    # Exact trusted writer acknowledgement.
    if writer.get("schema") != WRITER_SCHEMA:
        blockers.append("WRITER_ATTESTATION_SCHEMA_INVALID")
    if writer.get("state") != "CHECKPOINT_WRITER_AUTHORITY_ATTESTED":
        blockers.append("WRITER_AUTHORITY_NOT_ATTESTED")
    if writer.get("writer_identity_verified") is not True:
        blockers.append("WRITER_IDENTITY_NOT_VERIFIED")
    if writer.get("writer_authority_verified") is not True:
        blockers.append("WRITER_AUTHORITY_NOT_VERIFIED")
    if writer.get("receipt_binding_verified") is not True:
        blockers.append("WRITER_RECEIPT_BINDING_NOT_VERIFIED")
    if writer.get("nonce_registered") is not True:
        blockers.append("WRITER_NONCE_NOT_REGISTERED")
    if writer.get("checkpoint_write_performed") is not False:
        blockers.append("WRITER_WRITE_FLAG_UNSAFE")
    if writer.get("business_action_authorized") is not False:
        blockers.append("WRITER_BUSINESS_AUTHORITY_UNSAFE")

    if _text(writer.get("customer_id"), 120) != customer_id:
        blockers.append("WRITER_CUSTOMER_MISMATCH")
    if _text(writer.get("pilot_id"), 120) != pilot_id:
        blockers.append("WRITER_PILOT_MISMATCH")
    if _text(writer.get("requested_choice"), 120) != choice:
        blockers.append("WRITER_CHOICE_MISMATCH")
    if _text(writer.get("receipt_digest"), 180) != receipt_digest:
        blockers.append("WRITER_RECEIPT_DIGEST_MISMATCH")
    if (
        _text(writer.get("after_checkpoint_digest"), 180)
        != checkpoint_digest
    ):
        blockers.append("WRITER_CHECKPOINT_DIGEST_MISMATCH")
    if (
        _text(writer.get("decision_record_digest"), 180)
        != decision_record_digest
    ):
        blockers.append("WRITER_DECISION_RECORD_DIGEST_MISMATCH")

    for key in _UPSTREAM_FALSE_FIELDS:
        if key in writer and writer.get(key) is not False:
            blockers.append("WRITER_UNSAFE_FIELD:" + key)

    # Immutable original owner-review packet.
    if review.get("schema") != OWNER_REVIEW_SCHEMA:
        blockers.append("OWNER_REVIEW_PACKET_SCHEMA_INVALID")
    if review.get("state") != "REVIEWABLE":
        blockers.append("OWNER_REVIEW_PACKET_NOT_REVIEWABLE")
    if review.get("decision") != "OWNER_REVIEW_REQUIRED":
        blockers.append("OWNER_REVIEW_PACKET_DECISION_BOUNDARY_INVALID")
    if review.get("blockers"):
        blockers.append("OWNER_REVIEW_PACKET_HAS_BLOCKERS")
    if review.get("owner_decision_required") is not True:
        blockers.append("OWNER_REVIEW_PACKET_OWNER_DECISION_BOUNDARY_MISSING")
    if review.get("owner_only") is not True:
        blockers.append("OWNER_REVIEW_PACKET_OWNER_ONLY_BOUNDARY_MISSING")
    if review.get("customer_visible") is not False:
        blockers.append("OWNER_REVIEW_PACKET_VISIBILITY_UNSAFE")
    if _scope(review.get("scope")) != trusted or _scope(review) != trusted:
        blockers.append("OWNER_REVIEW_PACKET_SCOPE_MISMATCH")
    if _text(review.get("customer_id"), 120) != customer_id:
        blockers.append("OWNER_REVIEW_PACKET_CUSTOMER_MISMATCH")
    if _text(review.get("pilot_id"), 120) != pilot_id:
        blockers.append("OWNER_REVIEW_PACKET_PILOT_MISMATCH")
    if _text(review.get("package"), 40).upper() != package:
        blockers.append("OWNER_REVIEW_PACKET_PACKAGE_MISMATCH")
    if _text(review.get("review_type"), 120) != review_type:
        blockers.append("OWNER_REVIEW_PACKET_REVIEW_TYPE_MISMATCH")
    if _text(review.get("evidence_digest"), 180) != review_digest:
        blockers.append("OWNER_REVIEW_PACKET_DIGEST_MISMATCH")
    if _text(review.get("cycle_evidence_digest"), 180) != cycle_digest:
        blockers.append("OWNER_REVIEW_PACKET_CYCLE_DIGEST_MISMATCH")
    if _text(review.get("contract_digest"), 180) != contract_digest:
        blockers.append("OWNER_REVIEW_PACKET_CONTRACT_DIGEST_MISMATCH")
    if (
        _text(review.get("value_bound_conversion_digest"), 180)
        != conversion_digest
    ):
        blockers.append("OWNER_REVIEW_PACKET_CONVERSION_DIGEST_MISMATCH")
    if choice not in list(review.get("allowed_owner_choices") or []):
        blockers.append("OWNER_CHOICE_NOT_ALLOWED_BY_REVIEW_PACKET")

    for key in _REVIEW_FALSE_FIELDS:
        if review.get(key) is not False:
            blockers.append("OWNER_REVIEW_PACKET_UNSAFE_FIELD:" + key)

    # Immutable service-cycle lineage.
    if cycle.get("schema") != SERVICE_CYCLE_SCHEMA:
        blockers.append("SERVICE_CYCLE_SCHEMA_INVALID")
    if cycle.get("blockers"):
        blockers.append("SERVICE_CYCLE_HAS_BLOCKERS")
    if _scope(cycle.get("scope")) != trusted or _scope(cycle) != trusted:
        blockers.append("SERVICE_CYCLE_SCOPE_MISMATCH")
    if _text(cycle.get("customer_id"), 120) != customer_id:
        blockers.append("SERVICE_CYCLE_CUSTOMER_MISMATCH")
    if _text(cycle.get("pilot_id"), 120) != pilot_id:
        blockers.append("SERVICE_CYCLE_PILOT_MISMATCH")
    if _text(cycle.get("package"), 40).upper() != package:
        blockers.append("SERVICE_CYCLE_PACKAGE_MISMATCH")
    if _text(cycle.get("evidence_digest"), 180) != cycle_digest:
        blockers.append("SERVICE_CYCLE_EVIDENCE_DIGEST_MISMATCH")
    if _text(cycle.get("contract_digest"), 180) != contract_digest:
        blockers.append("SERVICE_CYCLE_CONTRACT_DIGEST_MISMATCH")
    if (
        _text(cycle.get("value_bound_conversion_digest"), 180)
        != conversion_digest
    ):
        blockers.append("SERVICE_CYCLE_CONVERSION_DIGEST_MISMATCH")
    if cycle.get("owner_review_required") is not True:
        blockers.append("SERVICE_CYCLE_OWNER_REVIEW_BOUNDARY_MISSING")
    if cycle.get("customer_visible") is not False:
        blockers.append("SERVICE_CYCLE_VISIBILITY_UNSAFE")
    if cycle.get("contains_internal_finops") is not True:
        blockers.append("SERVICE_CYCLE_FINOPS_MARKER_MISSING")
    if cycle.get("requires_customer_safe_projection") is not True:
        blockers.append("SERVICE_CYCLE_SAFE_PROJECTION_BOUNDARY_MISSING")

    mapped_review_type = STATE_DECISION.get(
        (cycle.get("state"), cycle.get("decision")),
        "",
    )
    if mapped_review_type != review_type:
        blockers.append("SERVICE_CYCLE_REVIEW_TYPE_LINEAGE_MISMATCH")

    for key in _CYCLE_FALSE_FIELDS:
        if cycle.get(key) is not False:
            blockers.append("SERVICE_CYCLE_UNSAFE_FIELD:" + key)

    # Fresh action environment.
    if env.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("ACTION_ENVIRONMENT_SCHEMA_INVALID")
    if env.get("state") != "VERIFIED":
        blockers.append("ACTION_ENVIRONMENT_NOT_VERIFIED")
    if _scope(env) != trusted:
        blockers.append("ACTION_ENVIRONMENT_SCOPE_MISMATCH")
    if _text(env.get("customer_id"), 120) != customer_id:
        blockers.append("ACTION_ENVIRONMENT_CUSTOMER_MISMATCH")
    if _text(env.get("pilot_id"), 120) != pilot_id:
        blockers.append("ACTION_ENVIRONMENT_PILOT_MISMATCH")
    if _text(env.get("package"), 40).upper() != package:
        blockers.append("ACTION_ENVIRONMENT_PACKAGE_MISMATCH")

    for key in _ENVIRONMENT_READY_FIELDS:
        if env.get(key) is not True:
            blockers.append("ACTION_ENVIRONMENT_NOT_READY:" + key)

    for key in (
        "security_incident",
        "privacy_incident",
        "scope_breach",
    ):
        if env.get(key) is not False:
            blockers.append("ACTION_ENVIRONMENT_INCIDENT:" + key)

    projected_infra = _number(env.get("projected_monthly_infra_brl"))
    if projected_infra is None or projected_infra < 0:
        blockers.append("ACTION_ENVIRONMENT_INFRA_COST_INVALID")
    elif projected_infra > MAX_MONTHLY_INFRA_BRL:
        blockers.append("ACTION_ENVIRONMENT_GLOBAL_INFRA_CAP_EXCEEDED")

    evidence_refs = _refs(env.get("evidence_refs"))
    if len(evidence_refs) < 4:
        blockers.append("ACTION_ENVIRONMENT_EVIDENCE_INSUFFICIENT")

    preconditions = (
        dict(env.get("choice_preconditions"))
        if isinstance(env.get("choice_preconditions"), Mapping)
        else {}
    )
    for key in CHOICE_PRECONDITIONS.get(choice, ()):
        if preconditions.get(key) is not True:
            blockers.append("ACTION_CHOICE_PRECONDITION_MISSING:" + key)

    try:
        checked_at = _parse_ts(env.get("checked_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("ACTION_ENVIRONMENT_TIME_INVALID")
    else:
        age = (now - checked_at).total_seconds()
        if age < 0:
            blockers.append("ACTION_ENVIRONMENT_FROM_FUTURE")
        elif age > MAX_ENVIRONMENT_AGE_SECONDS:
            blockers.append("ACTION_ENVIRONMENT_STALE")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return _blocked(*blockers)

    environment_material = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "requested_choice": choice,
        "action_family": action_family,
        "projected_monthly_infra_brl": projected_infra,
        "checked_at": env["checked_at"],
        "evidence_refs": evidence_refs,
        "choice_preconditions": {
            key: True
            for key in CHOICE_PRECONDITIONS[choice]
        },
    }
    environment_digest = _digest(environment_material)

    preflight_material = {
        "scope": trusted,
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": action_family,
        "owner_review_packet_digest": review_digest,
        "cycle_evidence_digest": cycle_digest,
        "contract_digest": contract_digest,
        "value_bound_conversion_digest": conversion_digest,
        "decision_record_digest": decision_record_digest,
        "persistence_receipt_digest": receipt_digest,
        "checkpoint_digest": checkpoint_digest,
        "writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "environment_digest": environment_digest,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY",
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
        "action_family": action_family,
        "owner_review_packet_digest": review_digest,
        "cycle_evidence_digest": cycle_digest,
        "contract_digest": contract_digest,
        "value_bound_conversion_digest": conversion_digest,
        "decision_record_digest": decision_record_digest,
        "persistence_receipt_digest": receipt_digest,
        "checkpoint_digest": checkpoint_digest,
        "writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "environment_digest": environment_digest,
        "preflight_digest": _digest(preflight_material),
        "action_ceremony_eligible": True,
        "requires_fresh_recheck_before_ceremony": True,
        "action_request_issued": False,
        "owner_action_signature_required": True,
        "owner_action_signature_verified": False,
        "customer_visible": False,
        **{key: False for key in _ACTION_AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "ENVIRONMENT_SCHEMA",
    "MAX_ENVIRONMENT_AGE_SECONDS",
    "MAX_MONTHLY_INFRA_BRL",
    "ACTION_FAMILY",
    "CHOICE_PRECONDITIONS",
    "evaluate_owner_renewal_action_preflight",
]
