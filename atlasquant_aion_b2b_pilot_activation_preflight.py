"""AION B2B Pilot Activation Preflight V1.

Pure/offline preflight before any future pilot activation ceremony.

A pilot can become READY_FOR_ACTIVATION_CEREMONY only when:
- an exact APPROVE_PILOT decision is durably persistence-attested;
- the exact persistence receipt has a cryptographically attested writer;
- owner-review packet, pilot handoff and operating contract remain bound;
- fresh activation-environment evidence passes fail-closed checks.

This module never issues an activation request, never signs, activates, contacts,
bills, provisions, deploys, writes CRM data, calls a provider or mutates
production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json
import math

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_PREFLIGHT_V1"
PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_PERSISTENCE_ATTESTATION_V1"
)
WRITER_SCHEMA = (
    "ATLASQUANT_AION_B2B_PILOT_CHECKPOINT_WRITER_VERIFICATION_V1"
)
PACKET_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_REVIEW_PACKET_V1"
HANDOFF_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_PLANNING_HANDOFF_V1"
OPERATING_CONTRACT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OPERATING_CONTRACT_V1"
ENVIRONMENT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_ENVIRONMENT_V1"

MAX_ENVIRONMENT_AGE_SECONDS = 300
MAX_MONTHLY_INFRA_BRL = 200.0


def _text(value: Any, limit: int = 420) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
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


def _refs(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:limit]:
        item = _text(raw, 320)
        if item and item not in out:
            out.append(item)
    return out


def evaluate_pilot_activation_preflight(
    *,
    trusted_scope: Mapping[str, Any] | None,
    persistence_attestation: Mapping[str, Any] | None,
    writer_attestation: Mapping[str, Any] | None,
    owner_review_packet: Mapping[str, Any] | None,
    pilot_handoff: Mapping[str, Any] | None,
    environment_evidence: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Return activation-ceremony eligibility only; never activation authority."""
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
    packet = (
        dict(owner_review_packet)
        if isinstance(owner_review_packet, Mapping)
        else {}
    )
    handoff = (
        dict(pilot_handoff)
        if isinstance(pilot_handoff, Mapping)
        else {}
    )
    env = (
        dict(environment_evidence)
        if isinstance(environment_evidence, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    # Persistence attestation: exact APPROVE only.
    if persisted.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("PERSISTENCE_ATTESTATION_SCHEMA_INVALID")
    if (
        persisted.get("state")
        != "DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE"
    ):
        if (
            persisted.get("state")
            == "DECISION_RECORD_PERSISTENCE_ATTESTED_DENY"
        ):
            blockers.append("PILOT_DECISION_DENIED")
        else:
            blockers.append("PERSISTENCE_ATTESTATION_NOT_APPROVED")
    if persisted.get("decision") != "APPROVE_PILOT":
        blockers.append("PERSISTED_DECISION_NOT_APPROVE")
    if _scope(persisted.get("scope")) != trusted:
        blockers.append("PERSISTENCE_SCOPE_MISMATCH")
    if persisted.get("owner_decision_recorded") is not True:
        blockers.append("OWNER_DECISION_NOT_RECORDED")
    if persisted.get("decision_record_persisted") is not True:
        blockers.append("DECISION_RECORD_NOT_PERSISTED")
    if persisted.get("persistence_attested") is not True:
        blockers.append("DECISION_PERSISTENCE_NOT_ATTESTED")
    if persisted.get("receipt_consistency_verified") is not True:
        blockers.append("PERSISTENCE_RECEIPT_NOT_VERIFIED")
    if persisted.get("pilot_approved") is not True:
        blockers.append("PERSISTED_PILOT_NOT_APPROVED")
    if persisted.get("pilot_denied") is not False:
        blockers.append("PERSISTED_PILOT_DENIAL_FLAG_INVALID")
    if persisted.get("eligible_for_activation_ceremony") is not True:
        blockers.append("PERSISTENCE_NOT_ACTIVATION_CEREMONY_ELIGIBLE")
    if persisted.get("pilot_activation_authorized") is not False:
        blockers.append("PERSISTENCE_ACTIVATION_ALREADY_AUTHORIZED")
    if persisted.get("pilot_activated") is not False:
        blockers.append("PERSISTENCE_PILOT_ALREADY_ACTIVE")
    for key in (
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "production_mutation_authorized",
        "storage_write_performed",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if persisted.get(key) is not False:
            blockers.append(f"PERSISTENCE_{key.upper()}_UNSAFE")

    candidate_id = _text(persisted.get("candidate_id"), 120)
    proposal_id = _text(persisted.get("proposal_id"), 120)
    pilot_id = _text(persisted.get("pilot_id"), 120)
    packet_digest = _text(persisted.get("packet_digest"), 180)
    receipt_digest = _text(persisted.get("receipt_digest"), 180)
    checkpoint_master_digest = _text(
        persisted.get("checkpoint_master_digest"),
        180,
    )
    decision_record_digest = _text(
        persisted.get("decision_record_digest"),
        180,
    )
    for label, value in (
        ("CANDIDATE_ID", candidate_id),
        ("PROPOSAL_ID", proposal_id),
        ("PILOT_ID", pilot_id),
        ("PACKET_DIGEST", packet_digest),
        ("RECEIPT_DIGEST", receipt_digest),
        ("CHECKPOINT_MASTER_DIGEST", checkpoint_master_digest),
        ("DECISION_RECORD_DIGEST", decision_record_digest),
    ):
        if not value:
            blockers.append(f"PERSISTENCE_{label}_REQUIRED")

    # Writer authority must bind the same receipt/checkpoint/decision.
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
    if _text(writer.get("pilot_id"), 120) != pilot_id:
        blockers.append("WRITER_PILOT_MISMATCH")
    if _text(writer.get("receipt_digest"), 180) != receipt_digest:
        blockers.append("WRITER_RECEIPT_DIGEST_MISMATCH")
    if (
        _text(writer.get("after_checkpoint_digest"), 180)
        != checkpoint_master_digest
    ):
        blockers.append("WRITER_CHECKPOINT_DIGEST_MISMATCH")
    if (
        _text(writer.get("decision_record_digest"), 180)
        != decision_record_digest
    ):
        blockers.append("WRITER_DECISION_RECORD_DIGEST_MISMATCH")
    for key in (
        "pilot_activation_authorized",
        "pilot_activated",
        "checkpoint_write_performed",
        "customer_contact_authorized",
        "billing_authorized",
        "deploy_authorized",
        "production_mutation_authorized",
        "external_action_executed",
        "network_called",
        "executes_action",
    ):
        if writer.get(key) is not False:
            blockers.append(f"WRITER_{key.upper()}_UNSAFE")

    # Original owner-review packet stays immutable evidence.
    if packet.get("schema") != PACKET_SCHEMA:
        blockers.append("OWNER_REVIEW_PACKET_SCHEMA_INVALID")
    if packet.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("OWNER_REVIEW_PACKET_NOT_READY")
    if _scope(packet.get("scope")) != trusted:
        blockers.append("OWNER_REVIEW_PACKET_SCOPE_MISMATCH")
    if _text(packet.get("candidate_id"), 120) != candidate_id:
        blockers.append("OWNER_REVIEW_PACKET_CANDIDATE_MISMATCH")
    if _text(packet.get("packet_digest"), 180) != packet_digest:
        blockers.append("OWNER_REVIEW_PACKET_DIGEST_MISMATCH")
    if packet.get("pilot_activation_authorized") is not False:
        blockers.append("OWNER_REVIEW_PACKET_ACTIVATION_UNSAFE")
    if packet.get("executes_action") is not False:
        blockers.append("OWNER_REVIEW_PACKET_EXECUTION_UNSAFE")

    summary = (
        dict(packet.get("summary"))
        if isinstance(packet.get("summary"), Mapping)
        else {}
    )
    proposal_summary = (
        dict(summary.get("proposal"))
        if isinstance(summary.get("proposal"), Mapping)
        else {}
    )
    pilot_summary = (
        dict(summary.get("pilot"))
        if isinstance(summary.get("pilot"), Mapping)
        else {}
    )
    evidence_summary = (
        dict(summary.get("evidence"))
        if isinstance(summary.get("evidence"), Mapping)
        else {}
    )
    if _text(proposal_summary.get("proposal_id"), 120) != proposal_id:
        blockers.append("OWNER_REVIEW_PACKET_PROPOSAL_MISMATCH")
    if _text(pilot_summary.get("pilot_id"), 120) != pilot_id:
        blockers.append("OWNER_REVIEW_PACKET_PILOT_MISMATCH")
    if (
        pilot_summary.get("activation_state")
        != "BLOCKED_UNTIL_OWNER_APPROVAL"
    ):
        blockers.append("OWNER_REVIEW_PACKET_ACTIVATION_BOUNDARY_INVALID")

    # Pilot handoff + operating contract must still be unchanged.
    if handoff.get("schema") != HANDOFF_SCHEMA:
        blockers.append("PILOT_HANDOFF_SCHEMA_INVALID")
    if handoff.get("state") != "PLANNED_FOR_OWNER_REVIEW":
        blockers.append("PILOT_HANDOFF_STATE_INVALID")
    if _scope(handoff.get("scope")) != trusted:
        blockers.append("PILOT_HANDOFF_SCOPE_MISMATCH")
    if _text(handoff.get("candidate_id"), 120) != candidate_id:
        blockers.append("PILOT_HANDOFF_CANDIDATE_MISMATCH")
    if _text(handoff.get("proposal_id"), 120) != proposal_id:
        blockers.append("PILOT_HANDOFF_PROPOSAL_MISMATCH")
    if _text(handoff.get("pilot_id"), 120) != pilot_id:
        blockers.append("PILOT_HANDOFF_PILOT_MISMATCH")
    if handoff.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("PILOT_HANDOFF_ACTIVATION_BOUNDARY_INVALID")
    if handoff.get("automatic_activation") is not False:
        blockers.append("PILOT_HANDOFF_AUTO_ACTIVATION_UNSAFE")
    if handoff.get("executes_action") is not False:
        blockers.append("PILOT_HANDOFF_EXECUTION_UNSAFE")

    contract_result = (
        dict(handoff.get("operating_contract"))
        if isinstance(handoff.get("operating_contract"), Mapping)
        else {}
    )
    if contract_result.get("schema") != OPERATING_CONTRACT_SCHEMA:
        blockers.append("OPERATING_CONTRACT_SCHEMA_INVALID")
    if contract_result.get("state") != "DRAFT_FOR_OWNER_APPROVAL":
        blockers.append("OPERATING_CONTRACT_STATE_INVALID")
    if (
        contract_result.get("activation_state")
        != "BLOCKED_UNTIL_OWNER_APPROVAL"
    ):
        blockers.append("OPERATING_CONTRACT_ACTIVATION_BOUNDARY_INVALID")
    if contract_result.get("human_owner_approval_required") is not True:
        blockers.append("OPERATING_CONTRACT_OWNER_BOUNDARY_MISSING")
    if contract_result.get("automatic_activation") is not False:
        blockers.append("OPERATING_CONTRACT_AUTO_ACTIVATION_UNSAFE")
    if contract_result.get("executes_action") is not False:
        blockers.append("OPERATING_CONTRACT_EXECUTION_UNSAFE")

    contract_digest = _text(
        contract_result.get("contract_digest"),
        180,
    )
    if (
        _text(
            evidence_summary.get("operating_contract_digest"),
            180,
        )
        != contract_digest
    ):
        blockers.append("OPERATING_CONTRACT_DIGEST_MISMATCH")

    contract = (
        dict(contract_result.get("contract"))
        if isinstance(contract_result.get("contract"), Mapping)
        else {}
    )
    if _scope(contract) != trusted:
        blockers.append("OPERATING_CONTRACT_SCOPE_MISMATCH")
    if _text(contract.get("candidate_id"), 120) != candidate_id:
        blockers.append("OPERATING_CONTRACT_CANDIDATE_MISMATCH")
    if _text(contract.get("pilot_id"), 120) != pilot_id:
        blockers.append("OPERATING_CONTRACT_PILOT_MISMATCH")

    contract_budget = _number(contract.get("max_monthly_infra_brl"))
    if contract_budget is None or contract_budget < 0:
        blockers.append("OPERATING_CONTRACT_BUDGET_INVALID")

    # Fresh activation-environment evidence.
    if env.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("ACTIVATION_ENVIRONMENT_SCHEMA_INVALID")
    if env.get("state") != "VERIFIED":
        blockers.append("ACTIVATION_ENVIRONMENT_NOT_VERIFIED")
    if _scope(env) != trusted:
        blockers.append("ACTIVATION_ENVIRONMENT_SCOPE_MISMATCH")
    if _text(env.get("pilot_id"), 120) != pilot_id:
        blockers.append("ACTIVATION_ENVIRONMENT_PILOT_MISMATCH")

    required_true = (
        "tenant_isolation_ready",
        "secrets_vault_ready",
        "rollback_ready",
        "monitoring_ready",
        "audit_receipts_ready",
        "sandbox_validation_pass",
        "integration_health_ready",
        "kill_switch_ready",
    )
    for key in required_true:
        if env.get(key) is not True:
            blockers.append(f"ACTIVATION_ENVIRONMENT_{key.upper()}_REQUIRED")

    for key in (
        "security_incident",
        "privacy_incident",
        "scope_breach",
    ):
        if env.get(key) is not False:
            blockers.append(f"ACTIVATION_ENVIRONMENT_{key.upper()}_BLOCKED")

    reserved_units = _positive_int(env.get("reserved_capacity_units"))
    available_units = _positive_int(env.get("available_capacity_units"))
    if reserved_units is None:
        blockers.append("ACTIVATION_RESERVED_CAPACITY_INVALID")
    if available_units is None:
        blockers.append("ACTIVATION_AVAILABLE_CAPACITY_INVALID")
    if (
        reserved_units is not None
        and available_units is not None
        and reserved_units > available_units
    ):
        blockers.append("ACTIVATION_CAPACITY_INSUFFICIENT")

    planned_infra = _number(env.get("planned_monthly_infra_brl"))
    if planned_infra is None or planned_infra < 0:
        blockers.append("ACTIVATION_MONTHLY_INFRA_INVALID")
    else:
        if planned_infra > MAX_MONTHLY_INFRA_BRL:
            blockers.append("ACTIVATION_MONTHLY_INFRA_GLOBAL_CAP_EXCEEDED")
        if (
            contract_budget is not None
            and planned_infra > contract_budget
        ):
            blockers.append("ACTIVATION_MONTHLY_INFRA_CONTRACT_CAP_EXCEEDED")

    env_refs = _refs(env.get("evidence_refs"))
    if len(env_refs) < 4:
        blockers.append("ACTIVATION_ENVIRONMENT_EVIDENCE_INSUFFICIENT")

    try:
        checked = _parse_ts(env.get("checked_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("ACTIVATION_ENVIRONMENT_TIME_INVALID")
    else:
        age = (now - checked).total_seconds()
        if age < -5:
            blockers.append("ACTIVATION_ENVIRONMENT_FROM_FUTURE")
        elif age > MAX_ENVIRONMENT_AGE_SECONDS:
            blockers.append("ACTIVATION_ENVIRONMENT_STALE")

    environment_material = {
        "scope": trusted,
        "pilot_id": pilot_id,
        "checked_at": env.get("checked_at"),
        "required_true": {
            key: env.get(key)
            for key in required_true
        },
        "incident_flags": {
            key: env.get(key)
            for key in (
                "security_incident",
                "privacy_incident",
                "scope_breach",
            )
        },
        "reserved_capacity_units": reserved_units,
        "available_capacity_units": available_units,
        "planned_monthly_infra_brl": planned_infra,
        "evidence_refs": env_refs,
    }
    environment_digest = _digest(environment_material)

    blockers = list(dict.fromkeys(blockers))
    preflight_material = {
        "scope": trusted,
        "candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "pilot_id": pilot_id,
        "packet_digest": packet_digest,
        "decision_record_digest": decision_record_digest,
        "persistence_attestation_digest": _text(
            persisted.get("attestation_digest"),
            180,
        ),
        "writer_request_digest": _text(
            writer.get("writer_request_digest"),
            180,
        ),
        "operating_contract_digest": contract_digest,
        "environment_digest": environment_digest,
    }

    return {
        "schema": SCHEMA,
        "state": (
            "READY_FOR_ACTIVATION_CEREMONY"
            if not blockers
            else "BLOCKED"
        ),
        "scope": trusted,
        "candidate_id": candidate_id,
        "proposal_id": proposal_id,
        "pilot_id": pilot_id,
        "blockers": blockers,
        "environment_digest": environment_digest,
        "preflight_digest": _digest(preflight_material),
        "activation_ceremony_eligible": not blockers,
        "activation_request_issued": False,
        "owner_activation_signature_required": True,
        "owner_activation_signature_verified": False,
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
    "PACKET_SCHEMA",
    "HANDOFF_SCHEMA",
    "OPERATING_CONTRACT_SCHEMA",
    "ENVIRONMENT_SCHEMA",
    "MAX_ENVIRONMENT_AGE_SECONDS",
    "MAX_MONTHLY_INFRA_BRL",
    "evaluate_pilot_activation_preflight",
]
