"""Read-only B2B pilot activation governance model for the Negócios cockpit.

Consumes only the final Activation Execution Preflight and exposes aggregate,
non-authoritative status. It deliberately omits candidate identity, evidence
refs, cryptographic digests, writer details and every activation control.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_STATUS_READ_MODEL_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_ACTIVATION_EXECUTION_PREFLIGHT_V1"


def _text(value: Any, limit: int = 240) -> str:
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


def build_pilot_activation_status_read_model(
    execution_preflight: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = (
        dict(execution_preflight)
        if isinstance(execution_preflight, Mapping)
        else {}
    )
    scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if source.get("schema") != SOURCE_SCHEMA:
        blockers.append("ACTIVATION_EXECUTION_PREFLIGHT_SCHEMA_INVALID")
    if source.get("state") != "READY_FOR_ACTIVATION_EXECUTION_CEREMONY":
        blockers.append("ACTIVATION_EXECUTION_PREFLIGHT_NOT_READY")
    if _scope(source.get("scope")) != scope:
        blockers.append("ACTIVATION_EXECUTION_PREFLIGHT_SCOPE_MISMATCH")
    if source.get("activation_execution_ceremony_eligible") is not True:
        blockers.append("ACTIVATION_EXECUTION_CEREMONY_NOT_ELIGIBLE")
    if source.get("human_execution_confirmation_required") is not True:
        blockers.append("HUMAN_EXECUTION_CONFIRMATION_BOUNDARY_MISSING")

    safe_false = (
        "execution_request_issued",
        "owner_execution_signature_verified",
        "activation_command_generated",
        "activation_command_executed",
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
    )
    for key in safe_false:
        if source.get(key) is not False:
            blockers.append(
                "ACTIVATION_EXECUTION_PREFLIGHT_" + key.upper() + "_UNSAFE"
            )

    pilot_id = _text(source.get("pilot_id"), 120)
    if not pilot_id:
        blockers.append("PILOT_ID_REQUIRED")
    if not _text(source.get("candidate_id"), 120):
        blockers.append("CANDIDATE_ID_REQUIRED")
    if not _text(source.get("proposal_id"), 120):
        blockers.append("PROPOSAL_ID_REQUIRED")
    if source.get("blockers"):
        blockers.append("ACTIVATION_EXECUTION_PREFLIGHT_HAS_BLOCKERS")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "read_only": True,
            "activation_control_exposed": False,
            "activation_command_exposed": False,
            "raw_evidence_exposed": False,
            "candidate_identity_exposed": False,
            "cryptographic_digest_exposed": False,
            "writer_identity_exposed": False,
            "grants_authority": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "scope": scope,
        "pilot_id": pilot_id,
        "governance_state": "WAITING_HUMAN_EXECUTION_CONFIRMATION",
        "pilot_decision_state": "ATTESTED",
        "activation_preflight_state": "ATTESTED",
        "activation_authorization_state": "ATTESTED",
        "activation_persistence_state": "ATTESTED",
        "activation_writer_state": "ATTESTED",
        "execution_environment_state": "VERIFIED",
        "execution_state": "BLOCKED_PENDING_HUMAN_CONFIRMATION",
        "monthly_infra_cap_brl": 200.0,
        "human_execution_confirmation_required": True,
        "read_only": True,
        "activation_control_exposed": False,
        "activation_command_exposed": False,
        "raw_evidence_exposed": False,
        "candidate_identity_exposed": False,
        "cryptographic_digest_exposed": False,
        "writer_identity_exposed": False,
        "automatic_activation": False,
        "automatic_customer_contact": False,
        "automatic_billing": False,
        "automatic_provisioning": False,
        "automatic_deploy": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SOURCE_SCHEMA",
    "build_pilot_activation_status_read_model",
]
