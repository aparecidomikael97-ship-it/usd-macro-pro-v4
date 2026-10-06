"""AION B2B controlled offline adapter plan V2.

Reconciles the Codex adapter V1 with the Red-Team hardened Command Plan V2.
No loose trusted_scope is accepted: scope is derived from the persisted,
cryptographically-bound execution chain rebuilt by Command Plan V2.

This module remains pure/offline and never selects or calls a real provider.
"""
from __future__ import annotations

from typing import Any

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as v1
from atlasquant_aion_b2b_owner_renewal_action_command_plan_v2 import (
    SCHEMA as COMMAND_PLAN_V2_SCHEMA,
    build_owner_renewal_action_command_plan_v2,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_PLAN_V2"
READY = v1.READY
ENVIRONMENT_SCHEMA = v1.ENVIRONMENT_SCHEMA
ADAPTER_KIND = v1.ADAPTER_KIND
FALSE_FIELDS = v1.FALSE_FIELDS
CAPABILITIES = v1.CAPABILITIES
RISKS = v1.RISKS
FINOPS_CAP_CENTS = v1.FINOPS_CAP_CENTS
BINDING_FIELDS_V2 = (
    *v1.BINDING_FIELDS,
    "execution_request_digest",
)


def _blocked(*items: str) -> dict[str, Any]:
    return v1.result(
        SCHEMA,
        "BLOCKED",
        items,
        command_plan_schema=COMMAND_PLAN_V2_SCHEMA,
        scope_source="PERSISTED_EXECUTION_RECORD",
        operation_kind_source="DERIVED_FROM_ACTION_FAMILY",
    )


def _binding_value_valid(key: str, value: Any) -> bool:
    if type(value) is not str:
        return False
    if key.endswith("digest"):
        return v1._HASH.fullmatch(value) is not None
    return v1._ID.fullmatch(value) is not None


def _canonical_body(binding, environment, rebuilt):
    body = v1.plan_body(binding, environment)
    body["command_plan_schema"] = COMMAND_PLAN_V2_SCHEMA
    body["scope_source"] = "PERSISTED_EXECUTION_RECORD"
    body["operation_kind_source"] = "DERIVED_FROM_ACTION_FAMILY"
    body["command_plan_v1_digest"] = rebuilt["command_plan_v1_digest"]
    body["red_team_hardening_digest"] = v1.digest(rebuilt["red_team_hardening"])
    return body


def build_owner_renewal_action_adapter_plan_v2(
    *,
    command_plan,
    execution_persistence_attestation,
    execution_writer_attestation,
    execution_preflight,
    adapter_environment,
    now_ts,
):
    """Rebuild Command Plan V2 and bind a fresh synthetic adapter environment."""
    try:
        supplied, persisted, writer, preflight, environment = v1.safe_copy([
            command_plan,
            execution_persistence_attestation,
            execution_writer_attestation,
            execution_preflight,
            adapter_environment,
        ])
        if any(
            type(item) is not dict
            for item in (supplied, persisted, writer, preflight, environment)
        ):
            raise ValueError("ADAPTER_V2_INPUT_INVALID")

        rebuilt = build_owner_renewal_action_command_plan_v2(
            execution_persistence_attestation=persisted,
            execution_writer_attestation=writer,
            execution_preflight=preflight,
        )
        if rebuilt.get("state") != "READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW":
            return _blocked(
                "COMMAND_PLAN_V2_REBUILD_BLOCKED",
                *rebuilt.get("blockers", []),
            )
        if rebuilt.get("schema") != COMMAND_PLAN_V2_SCHEMA:
            raise ValueError("COMMAND_PLAN_V2_SCHEMA_MISMATCH")
        if v1.digest(supplied) != v1.digest(rebuilt):
            raise ValueError("COMMAND_PLAN_V2_MISMATCH")
        if rebuilt.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
            raise ValueError("COMMAND_PLAN_V2_SCOPE_SOURCE_INVALID")
        if rebuilt.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
            raise ValueError("COMMAND_PLAN_V2_OPERATION_SOURCE_INVALID")
        hardening = rebuilt.get("red_team_hardening")
        if hardening != {
            "loose_trusted_scope_input_removed": True,
            "identity_truncation_rejected": True,
            "operation_kind_deterministically_derived": True,
        }:
            raise ValueError("COMMAND_PLAN_V2_HARDENING_INVALID")

        scope = rebuilt.get("scope")
        if not v1.scope_valid(scope):
            raise ValueError("COMMAND_PLAN_V2_SCOPE_INVALID")
        if persisted.get("blockers") != [] or writer.get("blockers") != []:
            raise ValueError("UPSTREAM_ATTESTATION_BLOCKED")

        plan = rebuilt["command_plan"]
        family = plan["action_family"]
        if v1.ACTION_FAMILY.get(plan["requested_choice"]) != family:
            raise ValueError("CHOICE_FAMILY_MISMATCH")
        if family not in CAPABILITIES:
            raise ValueError("ACTION_FAMILY_UNSUPPORTED")
        if plan.get("operation_kind") != v1.ACTION_OPERATION_KIND[family]:
            raise ValueError("OPERATION_KIND_MISMATCH")
        if plan.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
            raise ValueError("COMMAND_PLAN_SCOPE_PROVENANCE_MISSING")
        if plan.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
            raise ValueError("COMMAND_PLAN_OPERATION_PROVENANCE_MISSING")

        for key in BINDING_FIELDS_V2:
            if not _binding_value_valid(key, plan.get(key)):
                raise ValueError("COMMAND_BINDING_V2_INVALID")

        binding = {
            "scope": scope,
            **{key: plan[key] for key in BINDING_FIELDS_V2},
            "command_plan_digest": rebuilt["command_plan_digest"],
        }
        blockers = v1.environment_blockers(environment, binding, now_ts)
        if blockers:
            return _blocked(*blockers)

        body = _canonical_body(binding, environment, rebuilt)
        return v1.result(
            SCHEMA,
            READY,
            command_plan_schema=COMMAND_PLAN_V2_SCHEMA,
            scope_source="PERSISTED_EXECUTION_RECORD",
            operation_kind_source="DERIVED_FROM_ACTION_FAMILY",
            adapter_plan=body,
            adapter_plan_digest=v1.digest(body),
        )
    except (ValueError, KeyError, TypeError, OverflowError):
        return _blocked("ADAPTER_V2_INPUT_INVALID")


def validate_adapter_plan_v2(adapter_plan, now_ts):
    """Rebuild the canonical V2 adapter plan without accepting external scope."""
    supplied = v1.safe_copy(adapter_plan)
    if type(supplied) is not dict:
        raise ValueError("ADAPTER_PLAN_V2_INVALID")
    if supplied.get("schema") != SCHEMA or supplied.get("state") != READY:
        raise ValueError("ADAPTER_PLAN_V2_STATE_INVALID")
    if supplied.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
        raise ValueError("ADAPTER_PLAN_V2_SCOPE_SOURCE_INVALID")
    if supplied.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
        raise ValueError("ADAPTER_PLAN_V2_OPERATION_SOURCE_INVALID")

    body = supplied.get("adapter_plan")
    if type(body) is not dict:
        raise ValueError("ADAPTER_PLAN_V2_BODY_INVALID")
    binding = body.get("binding")
    expected_binding_keys = {"scope", "command_plan_digest", *BINDING_FIELDS_V2}
    if type(binding) is not dict or set(binding) != expected_binding_keys:
        raise ValueError("ADAPTER_BINDING_V2_INVALID")
    if not v1.scope_valid(binding.get("scope")):
        raise ValueError("ADAPTER_SCOPE_V2_INVALID")

    family = binding.get("action_family")
    if family not in CAPABILITIES:
        raise ValueError("ACTION_FAMILY_UNSUPPORTED")
    if v1.ACTION_FAMILY.get(binding.get("requested_choice")) != family:
        raise ValueError("CHOICE_FAMILY_MISMATCH")
    if binding.get("operation_kind") != v1.ACTION_OPERATION_KIND[family]:
        raise ValueError("OPERATION_KIND_MISMATCH")

    for key, value in binding.items():
        if key == "scope":
            continue
        if not _binding_value_valid(key, value):
            raise ValueError("ADAPTER_BINDING_V2_INVALID")

    if body.get("command_plan_schema") != COMMAND_PLAN_V2_SCHEMA:
        raise ValueError("COMMAND_PLAN_V2_SCHEMA_MISSING")
    if body.get("scope_source") != "PERSISTED_EXECUTION_RECORD":
        raise ValueError("COMMAND_PLAN_V2_SCOPE_SOURCE_MISSING")
    if body.get("operation_kind_source") != "DERIVED_FROM_ACTION_FAMILY":
        raise ValueError("COMMAND_PLAN_V2_OPERATION_SOURCE_MISSING")
    if not v1._HASH.fullmatch(body.get("command_plan_v1_digest", "")):
        raise ValueError("COMMAND_PLAN_V1_DIGEST_INVALID")
    if not v1._HASH.fullmatch(body.get("red_team_hardening_digest", "")):
        raise ValueError("RED_TEAM_HARDENING_DIGEST_INVALID")

    environment = body.get("environment")
    if (
        type(environment) is not dict
        or v1.environment_blockers(environment, binding, now_ts)
    ):
        raise ValueError("ADAPTER_ENVIRONMENT_V2_INVALID")

    rebuilt_stub = {
        "command_plan_v1_digest": body["command_plan_v1_digest"],
        "red_team_hardening": {
            "loose_trusted_scope_input_removed": True,
            "identity_truncation_rejected": True,
            "operation_kind_deterministically_derived": True,
        },
    }
    canonical = _canonical_body(binding, environment, rebuilt_stub)
    if canonical["red_team_hardening_digest"] != body["red_team_hardening_digest"]:
        raise ValueError("RED_TEAM_HARDENING_DIGEST_MISMATCH")

    expected = v1.result(
        SCHEMA,
        READY,
        command_plan_schema=COMMAND_PLAN_V2_SCHEMA,
        scope_source="PERSISTED_EXECUTION_RECORD",
        operation_kind_source="DERIVED_FROM_ACTION_FAMILY",
        adapter_plan=canonical,
        adapter_plan_digest=v1.digest(canonical),
    )
    if v1.digest(supplied) != v1.digest(expected):
        raise ValueError("ADAPTER_PLAN_V2_REBUILD_MISMATCH")
    return canonical


__all__ = [
    "SCHEMA",
    "READY",
    "ENVIRONMENT_SCHEMA",
    "ADAPTER_KIND",
    "FALSE_FIELDS",
    "CAPABILITIES",
    "RISKS",
    "FINOPS_CAP_CENTS",
    "BINDING_FIELDS_V2",
    "build_owner_renewal_action_adapter_plan_v2",
    "validate_adapter_plan_v2",
]
