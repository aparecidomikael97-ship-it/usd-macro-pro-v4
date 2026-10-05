"""AION B2B recurring business-action command-plan hardening V2.

Removes the loose trusted_scope input from the public contract, rejects identity
values that would require truncation or normalization, and records provenance
for scope and operation-kind derivation. Delegates the already-validated V1
semantic checks after these stricter guards pass.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    ACTION_OPERATION_KIND,
    SCHEMA as V1_SCHEMA,
    build_owner_renewal_action_command_plan as _build_v1,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_COMMAND_PLAN_V2"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _identity(value: Any, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        return ""
    if "\x00" in value or " ".join(value.split()) != value:
        return ""
    return value


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _identity(row.get("owner_id"), 120),
        "tenant_id": _identity(row.get("tenant_id"), 120),
        "workspace_id": _identity(row.get("workspace_id"), 120),
    }


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "command_plan": {},
        "command_plan_digest": "",
        "scope_source": "PERSISTED_EXECUTION_RECORD",
        "operation_kind_source": "DERIVED_FROM_ACTION_FAMILY",
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
        "business_action_authorized": False,
        "provider_called": False,
        "network_called": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_owner_renewal_action_command_plan_v2(
    *,
    execution_persistence_attestation: Mapping[str, Any] | None,
    execution_writer_attestation: Mapping[str, Any] | None,
    execution_preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
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

    trusted = _scope(persisted.get("scope"))
    if not all(trusted.values()):
        blockers.append("PERSISTED_EXECUTION_SCOPE_INVALID")
    if _scope(persisted) != trusted:
        blockers.append("PERSISTED_EXECUTION_SCOPE_DUPLICATE_MISMATCH")
    if _scope(preflight.get("scope")) != trusted or _scope(preflight) != trusted:
        blockers.append("EXECUTION_PREFLIGHT_SCOPE_MISMATCH")

    identity_specs = (
        ("customer_id", 120),
        ("pilot_id", 120),
        ("package", 40),
        ("review_type", 120),
        ("requested_choice", 120),
        ("action_family", 120),
    )
    writer_identity_keys = {
        "customer_id", "pilot_id", "requested_choice", "action_family"
    }
    for key, limit in identity_specs:
        p_value = _identity(persisted.get(key), limit)
        e_value = _identity(preflight.get(key), limit)
        if not p_value:
            blockers.append("PERSISTED_IDENTITY_INVALID:" + key)
        if e_value != p_value:
            blockers.append("PREFLIGHT_IDENTITY_MISMATCH:" + key)
        if key in writer_identity_keys:
            w_value = _identity(writer.get(key), limit)
            if w_value != p_value:
                blockers.append("WRITER_IDENTITY_MISMATCH:" + key)

    execution_request_digest = persisted.get("execution_request_digest")
    if (
        not isinstance(execution_request_digest, str)
        or _SHA256_RE.fullmatch(execution_request_digest) is None
    ):
        blockers.append("EXECUTION_REQUEST_DIGEST_INVALID")

    family = _identity(persisted.get("action_family"), 120)
    operation_kind = ACTION_OPERATION_KIND.get(family, "")
    if not operation_kind:
        blockers.append("ACTION_FAMILY_UNSUPPORTED")

    if blockers:
        return _blocked(*blockers)

    v1 = _build_v1(
        trusted_scope=trusted,
        execution_persistence_attestation=persisted,
        execution_writer_attestation=writer,
        execution_preflight=preflight,
    )
    if v1.get("schema") != V1_SCHEMA:
        return _blocked("V1_COMMAND_PLAN_SCHEMA_INVALID")
    if v1.get("state") != "READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW":
        out = _blocked("V1_COMMAND_PLAN_BLOCKED")
        out["blockers"] = sorted(
            set(out["blockers"] + ["V1:" + str(x) for x in v1.get("blockers", [])])
        )
        return out
    if v1.get("operation_kind") != operation_kind:
        return _blocked("OPERATION_KIND_DERIVATION_MISMATCH")

    command_plan = dict(v1.get("command_plan") or {})
    command_plan["scope_source"] = "PERSISTED_EXECUTION_RECORD"
    command_plan["operation_kind_source"] = "DERIVED_FROM_ACTION_FAMILY"
    command_plan["execution_request_digest"] = execution_request_digest

    out = dict(v1)
    out["schema"] = SCHEMA
    out["scope_source"] = "PERSISTED_EXECUTION_RECORD"
    out["operation_kind_source"] = "DERIVED_FROM_ACTION_FAMILY"
    out["execution_request_digest"] = execution_request_digest
    out["command_plan"] = command_plan
    out["command_plan_v1_digest"] = v1["command_plan_digest"]
    out["command_plan_digest"] = _digest(command_plan)
    out["red_team_hardening"] = {
        "loose_trusted_scope_input_removed": True,
        "identity_truncation_rejected": True,
        "operation_kind_deterministically_derived": True,
    }
    return out


__all__ = [
    "SCHEMA",
    "ACTION_OPERATION_KIND",
    "build_owner_renewal_action_command_plan_v2",
]
