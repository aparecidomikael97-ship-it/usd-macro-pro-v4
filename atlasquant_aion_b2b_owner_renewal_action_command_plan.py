"""AION B2B recurring business-action abstract command plan.

This layer freezes *what* the verified recurring action means, but deliberately
does not describe *how* to execute it. It never emits provider endpoints,
credentials, HTTP operations, shell commands, executable payloads or side
effects.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_execution_persistence_attestation import (
    SCHEMA as PERSISTENCE_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_preflight import (
    SCHEMA as EXECUTION_PREFLIGHT_SCHEMA,
)
from atlasquant_aion_b2b_owner_renewal_action_execution_writer_attestation import (
    RESULT_SCHEMA as WRITER_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_COMMAND_PLAN_V1"

ACTION_OPERATION_KIND = {
    "RENEWAL": "CONTRACT_CONTINUITY",
    "RENEWAL_WITH_CHANGES": "CONTRACT_CHANGE",
    "NON_RENEWAL": "SERVICE_OFFBOARDING",
    "REMEDIATION": "SERVICE_REMEDIATION",
    "CAPACITY_RESCOPE": "CAPACITY_CHANGE",
    "REPRICING": "COMMERCIAL_PRICING_CHANGE",
    "INCIDENT_REMEDIATION": "INCIDENT_REMEDIATION",
    "SERVICE_PAUSE": "SERVICE_PAUSE",
    "SERVICE_TERMINATION": "SERVICE_TERMINATION",
}

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

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

_PREFLIGHT_FALSE_FIELDS = (
    "execution_request_issued",
    "owner_execution_signature_verified",
    "execution_command_generated",
    "execution_command_executed",
    *_AUTHORITY_FIELDS,
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


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "command_plan": {},
        "command_plan_digest": "",
        "command_adapter_review_required": True,
        "requires_separate_adapter_binding": True,
        "requires_fresh_recheck_before_adapter": True,
        "provider_operation_materialized": False,
        "provider_endpoint_included": False,
        "http_method_included": False,
        "headers_included": False,
        "executable_payload_included": False,
        "credential_material_included": False,
        "secret_material_included": False,
        "execution_token_issued": False,
        "shell_command_generated": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def build_owner_renewal_action_command_plan(
    *,
    trusted_scope: Mapping[str, Any] | None,
    execution_persistence_attestation: Mapping[str, Any] | None,
    execution_writer_attestation: Mapping[str, Any] | None,
    execution_preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    persisted = (
        dict(execution_persistence_attestation)
        if isinstance(execution_persistence_attestation, Mapping)
        else {}
    )
    writer = (
        dict(execution_writer_attestation)
        if isinstance(execution_writer_attestation, Mapping)
        else {}
    )
    preflight = (
        dict(execution_preflight)
        if isinstance(execution_preflight, Mapping)
        else {}
    )
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")

    if persisted.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("EXECUTION_PERSISTENCE_ATTESTATION_SCHEMA_INVALID")
    if (
        persisted.get("state")
        != "OWNER_RENEWAL_ACTION_EXECUTION_RECORD_PERSISTENCE_ATTESTED"
    ):
        blockers.append("EXECUTION_PERSISTENCE_NOT_ATTESTED")
    if (
        persisted.get("execution_decision")
        != "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
    ):
        blockers.append("EXECUTION_DECISION_NOT_AUTHORIZE")
    if persisted.get("execution_record_persisted") is not True:
        blockers.append("EXECUTION_RECORD_NOT_PERSISTED")
    if persisted.get("persistence_attested") is not True:
        blockers.append("EXECUTION_PERSISTENCE_PROOF_MISSING")
    if persisted.get("receipt_consistency_verified") is not True:
        blockers.append("EXECUTION_RECEIPT_CONSISTENCY_NOT_VERIFIED")
    if persisted.get("writer_identity_verified") is not False:
        blockers.append("EXECUTION_PERSISTENCE_WRITER_BOUNDARY_INVALID")
    if persisted.get("eligible_for_command_planning") is not True:
        blockers.append("EXECUTION_NOT_COMMAND_PLANNING_ELIGIBLE")
    if persisted.get("storage_write_performed") is not False:
        blockers.append("EXECUTION_PERSISTENCE_WRITE_FLAG_UNSAFE")
    if persisted.get("execution_command_generated") is not False:
        blockers.append("EXECUTION_COMMAND_ALREADY_GENERATED")
    if persisted.get("execution_command_executed") is not False:
        blockers.append("EXECUTION_COMMAND_ALREADY_EXECUTED")
    if _scope(persisted.get("scope")) != trusted or _scope(persisted) != trusted:
        blockers.append("EXECUTION_PERSISTENCE_SCOPE_MISMATCH")
    for key in _AUTHORITY_FIELDS:
        if persisted.get(key) is not False:
            blockers.append("EXECUTION_PERSISTENCE_UNSAFE_FIELD:" + key)

    customer_id = _text(persisted.get("customer_id"), 120)
    pilot_id = _text(persisted.get("pilot_id"), 120)
    package = _text(persisted.get("package"), 40).upper()
    review_type = _text(persisted.get("review_type"), 120)
    choice = _text(persisted.get("requested_choice"), 120)
    family = _text(persisted.get("action_family"), 120)
    operation_kind = ACTION_OPERATION_KIND.get(family, "")
    if not all((customer_id, pilot_id, package, review_type, choice, family)):
        blockers.append("EXECUTION_IDENTITY_FIELDS_INCOMPLETE")
    if not operation_kind:
        blockers.append("ACTION_FAMILY_UNSUPPORTED")

    if writer.get("schema") != WRITER_SCHEMA:
        blockers.append("EXECUTION_WRITER_SCHEMA_INVALID")
    if writer.get("state") != "EXECUTION_INTENT_CHECKPOINT_WRITER_AUTHORITY_ATTESTED":
        blockers.append("EXECUTION_WRITER_NOT_ATTESTED")
    if writer.get("writer_identity_verified") is not True:
        blockers.append("EXECUTION_WRITER_IDENTITY_NOT_VERIFIED")
    if writer.get("writer_authority_verified") is not True:
        blockers.append("EXECUTION_WRITER_AUTHORITY_NOT_VERIFIED")
    if writer.get("receipt_binding_verified") is not True:
        blockers.append("EXECUTION_WRITER_RECEIPT_NOT_VERIFIED")
    if writer.get("nonce_registered") is not True:
        blockers.append("EXECUTION_WRITER_NONCE_NOT_REGISTERED")
    if writer.get("checkpoint_write_performed") is not False:
        blockers.append("EXECUTION_WRITER_WRITE_FLAG_UNSAFE")
    if writer.get("eligible_for_command_planning") is not True:
        blockers.append("EXECUTION_WRITER_NOT_COMMAND_PLANNING_ELIGIBLE")
    if writer.get("execution_command_generated") is not False:
        blockers.append("EXECUTION_WRITER_COMMAND_ALREADY_GENERATED")
    if writer.get("execution_command_executed") is not False:
        blockers.append("EXECUTION_WRITER_COMMAND_ALREADY_EXECUTED")
    for key in _AUTHORITY_FIELDS:
        if writer.get(key) is not False:
            blockers.append("EXECUTION_WRITER_UNSAFE_FIELD:" + key)

    writer_bindings = (
        ("customer_id", customer_id),
        ("pilot_id", pilot_id),
        ("requested_choice", choice),
        ("action_family", family),
        ("execution_decision", "AUTHORIZE_BUSINESS_ACTION_EXECUTION"),
        ("receipt_digest", _text(persisted.get("receipt_digest"), 180)),
        (
            "after_checkpoint_digest",
            _text(persisted.get("after_checkpoint_digest"), 180),
        ),
        (
            "execution_record_digest",
            _text(persisted.get("execution_record_digest"), 180),
        ),
    )
    for key, expected in writer_bindings:
        if _text(writer.get(key), 180) != expected:
            blockers.append("EXECUTION_WRITER_BINDING_MISMATCH:" + key)

    if preflight.get("schema") != EXECUTION_PREFLIGHT_SCHEMA:
        blockers.append("EXECUTION_PREFLIGHT_SCHEMA_INVALID")
    if preflight.get("state") != "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY":
        blockers.append("EXECUTION_PREFLIGHT_NOT_READY")
    if preflight.get("blockers"):
        blockers.append("EXECUTION_PREFLIGHT_HAS_BLOCKERS")
    if preflight.get("business_action_execution_ceremony_eligible") is not True:
        blockers.append("EXECUTION_PREFLIGHT_NOT_ELIGIBLE")
    if preflight.get("human_execution_confirmation_required") is not True:
        blockers.append("EXECUTION_PREFLIGHT_HUMAN_BOUNDARY_MISSING")
    if preflight.get("customer_visible") is not False:
        blockers.append("EXECUTION_PREFLIGHT_VISIBILITY_UNSAFE")
    if _scope(preflight.get("scope")) != trusted or _scope(preflight) != trusted:
        blockers.append("EXECUTION_PREFLIGHT_SCOPE_MISMATCH")
    for key in _PREFLIGHT_FALSE_FIELDS:
        if preflight.get(key) is not False:
            blockers.append("EXECUTION_PREFLIGHT_UNSAFE_FIELD:" + key)

    for key, expected in (
        ("customer_id", customer_id),
        ("pilot_id", pilot_id),
        ("package", package),
        ("review_type", review_type),
        ("requested_choice", choice),
        ("action_family", family),
    ):
        observed = _text(preflight.get(key), 120)
        if key == "package":
            observed = observed.upper()
        if observed != expected:
            blockers.append("EXECUTION_PREFLIGHT_BINDING_MISMATCH:" + key)

    digest_pairs = (
        ("action_record_digest", "action_record_digest"),
        (
            "action_persistence_receipt_digest",
            "action_persistence_receipt_digest",
        ),
        ("action_checkpoint_digest", "action_checkpoint_digest"),
        ("action_writer_request_digest", "action_writer_request_digest"),
        (
            "authorization_preflight_digest",
            "authorization_preflight_digest",
        ),
        ("action_parameters_digest", "action_parameters_digest"),
        ("execution_environment_digest", "execution_environment_digest"),
        ("execution_preflight_digest", "execution_preflight_digest"),
    )
    for persisted_key, preflight_key in digest_pairs:
        left = _text(persisted.get(persisted_key), 180)
        right = _text(preflight.get(preflight_key), 180)
        if not _SHA256_RE.fullmatch(left):
            blockers.append("EXECUTION_PERSISTENCE_DIGEST_INVALID:" + persisted_key)
        if not _SHA256_RE.fullmatch(right):
            blockers.append("EXECUTION_PREFLIGHT_DIGEST_INVALID:" + preflight_key)
        if left != right:
            blockers.append("EXECUTION_LINEAGE_DIGEST_MISMATCH:" + persisted_key)

    writer_request_digest = _text(writer.get("writer_request_digest"), 180)
    if not _SHA256_RE.fullmatch(writer_request_digest):
        blockers.append("EXECUTION_WRITER_REQUEST_DIGEST_INVALID")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return _blocked(*blockers)

    plan = {
        "scope": dict(trusted),
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "operation_kind": operation_kind,
        "target_domain": "MANAGED_SERVICE",
        "action_parameters_digest": persisted["action_parameters_digest"],
        "execution_preflight_digest": persisted["execution_preflight_digest"],
        "execution_record_digest": persisted["execution_record_digest"],
        "execution_intent_writer_request_digest": writer_request_digest,
        "provider_operation_materialized": False,
        "provider_adapter_selected": False,
        "provider_endpoint_included": False,
        "http_method_included": False,
        "headers_included": False,
        "executable_payload_included": False,
        "credential_material_included": False,
        "secret_material_included": False,
        "execution_token_issued": False,
        "shell_command_generated": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW",
        "blockers": [],
        "scope": dict(trusted),
        "customer_id": customer_id,
        "pilot_id": pilot_id,
        "package": package,
        "review_type": review_type,
        "requested_choice": choice,
        "action_family": family,
        "operation_kind": operation_kind,
        "command_plan": plan,
        "command_plan_digest": _digest(plan),
        "command_adapter_review_required": True,
        "requires_separate_adapter_binding": True,
        "requires_fresh_recheck_before_adapter": True,
        "provider_operation_materialized": False,
        "provider_adapter_selected": False,
        "provider_endpoint_included": False,
        "http_method_included": False,
        "headers_included": False,
        "executable_payload_included": False,
        "credential_material_included": False,
        "secret_material_included": False,
        "execution_token_issued": False,
        "shell_command_generated": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "ACTION_OPERATION_KIND",
    "build_owner_renewal_action_command_plan",
]
