"""Bounded offline adapter planning. Digests are bindings, never authority.

Upstream attestations must come from their trusted host verifiers. This module
does not re-sign, re-verify keys, claim nonces, load secrets or select a provider.
Only synthetic, explicitly scoped environment observations are accepted in V1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from atlasquant_aion_b2b_owner_renewal_action_command_plan import (
    ACTION_OPERATION_KIND, build_owner_renewal_action_command_plan,
)
from atlasquant_aion_b2b_owner_renewal_action_preflight import ACTION_FAMILY

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_PLAN_V1"
ENVIRONMENT_SCHEMA = "ATLASQUANT_AION_B2B_SYNTHETIC_ADAPTER_ENVIRONMENT_V1"
READY = "READY_FOR_CONTROLLED_ACTION_ADAPTER_DRY_RUN"
ADAPTER_KIND = "OFFLINE_MANAGED_SERVICE_CONTRACT"
MAX_WINDOW_SECONDS = 180
MAX_NODES = 4096
MAX_DEPTH = 12
MAX_TEXT = 512
FINOPS_CAP_CENTS = 20000

FALSE_FIELDS = (
    "provider_called", "network_called", "credential_material_included",
    "secret_material_included", "provider_endpoint_included", "http_method_included",
    "headers_included", "executable_payload_included", "shell_command_generated",
    "execution_command_generated", "execution_command_executed",
    "production_mutation_authorized", "production_mutation_performed",
    "customer_contact_authorized", "billing_authorized", "deploy_authorized",
    "executes_action", "provisioning_authorized", "crm_write_authorized",
    "external_action_executed", "business_action_authorized",
)
CAPABILITIES = {
    "RENEWAL": ("CONTRACT_CONTINUITY", "SERVICE_CONTINUITY", "BILLING_REVIEW_BOUNDARY", "CUSTOMER_NOTICE_BOUNDARY"),
    "RENEWAL_WITH_CHANGES": ("CONTRACT_CHANGE", "PACKAGE_SCOPE_REVIEW", "CAPACITY_REVIEW", "PRICING_BOUNDARY"),
    "NON_RENEWAL": ("OFFBOARDING_PLAN", "CUSTOMER_NOTICE_BOUNDARY", "DATA_RETENTION", "ACCESS_LIFECYCLE_PLAN", "ARCHIVE_EXPORT_BOUNDARY"),
    "REMEDIATION": ("SERVICE_REMEDIATION_PLAN", "SERVICE_HEALTH_RECHECK", "REMEDIATION_REVERSAL"),
    "CAPACITY_RESCOPE": ("CAPACITY_PLAN", "QUOTA_BOUNDARY", "FINOPS_VALIDATION", "SERVICE_HEALTH_RECHECK"),
    "REPRICING": ("COMMERCIAL_PRICING_PLAN", "CONTRACT_AMENDMENT_BOUNDARY", "OWNER_ONLY_APPROVAL_BOUNDARY"),
    "INCIDENT_REMEDIATION": ("INCIDENT_CONTAINMENT_PLAN", "SECURITY_PRIVACY_RECHECK", "SERVICE_HEALTH_RECHECK"),
    "SERVICE_PAUSE": ("PAUSE_SEQUENCING", "DATA_SAFETY", "CUSTOMER_IMPACT_REVIEW", "REVERSAL_PATH"),
    "SERVICE_TERMINATION": ("TERMINATION_SEQUENCING_PLAN", "DATA_RETENTION", "ARCHIVE_EXPORT_BOUNDARY", "ACCESS_REVOCATION_PLAN", "IRREVERSIBLE_ACTION_BOUNDARY"),
}
RISKS = (
    "billing_dispute", "security_incident", "privacy_incident", "contract_conflict",
    "irreversible_boundary_detected",
)
BINDING_FIELDS = (
    "customer_id", "pilot_id", "package", "review_type", "requested_choice",
    "action_family", "operation_kind", "action_parameters_digest",
    "execution_preflight_digest", "execution_record_digest",
    "execution_intent_writer_request_digest",
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BANNED_KEYS = {
    "secret", "password", "token", "api_key", "credential", "credentials",
    "cookie", "authorization", "endpoint", "url", "ip", "method", "http_method",
    "headers", "header", "payload", "body", "command", "shell", "subprocess",
    "powershell", "curl", "script", "request", "private_key", "access_token",
}


def safe_copy(value):
    """Reject subclasses/coercion/cycles/material and cap work before traversal."""
    budget = [MAX_NODES]

    def visit(item, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > MAX_DEPTH:
            raise ValueError("INPUT_BOUNDS_EXCEEDED")
        kind = type(item)
        if kind is dict:
            if len(item) > budget[0]:
                raise ValueError("INPUT_BOUNDS_EXCEEDED")
            out = {}
            for key, child in item.items():
                if type(key) is not str or len(key) > 120 or key.lower() in _BANNED_KEYS:
                    raise ValueError("UNSAFE_INPUT_MATERIAL")
                out[key] = visit(child, depth + 1)
            return out
        if kind is list:
            if len(item) > budget[0]:
                raise ValueError("INPUT_BOUNDS_EXCEEDED")
            return [visit(child, depth + 1) for child in item]
        if kind is str:
            if len(item) > MAX_TEXT or any(ord(c) < 32 for c in item):
                raise ValueError("UNSAFE_INPUT_MATERIAL")
            if re.search(r"(?i)(https?://|www\.|bearer\s|curl\s|powershell|(?:\d{1,3}\.){3}\d{1,3})", item):
                raise ValueError("UNSAFE_INPUT_MATERIAL")
            return item
        if kind in (bool, int) or item is None:
            if kind is int and abs(item) > 10**12:
                raise ValueError("INPUT_BOUNDS_EXCEEDED")
            return item
        raise ValueError("INPUT_TYPE_INVALID")

    return visit(value, 0)


def digest(value):
    return "sha256:" + sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def result(schema, state, blockers=(), **fields):
    return {"schema": schema, "state": state, "blockers": sorted(set(blockers)),
            **fields, **{key: False for key in FALSE_FIELDS}}


def scope_valid(scope):
    return (type(scope) is dict and set(scope) == {"owner_id", "tenant_id", "workspace_id"}
            and all(type(v) is str and _ID.fullmatch(v) for v in scope.values()))


def timestamp(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("TIME_INVALID")
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def environment_blockers(environment, binding, now_ts):
    expected = {"schema", "synthetic", "binding", "as_of", "expires_at", "evidence_refs",
                "provider_state", "rollback_state", "capacity_sufficient", "rollback_supported",
                "finops_monthly_cents", *RISKS}
    blockers = []
    if set(environment) != expected or environment.get("schema") != ENVIRONMENT_SCHEMA:
        blockers.append("ADAPTER_ENVIRONMENT_SCHEMA_INVALID")
    if environment.get("synthetic") is not True:
        blockers.append("SYNTHETIC_ENVIRONMENT_REQUIRED")
    if digest(environment.get("binding")) != digest(binding):
        blockers.append("ADAPTER_ENVIRONMENT_BINDING_MISMATCH")
    try:
        observed = timestamp(environment.get("as_of"))
        expires = timestamp(environment.get("expires_at"))
        now = timestamp(now_ts)
        if not (observed <= now < expires and 0 < (expires - observed).total_seconds() <= MAX_WINDOW_SECONDS):
            blockers.append("ADAPTER_ENVIRONMENT_STALE")
    except ValueError:
        blockers.append("ADAPTER_ENVIRONMENT_TIME_INVALID")
    for key in RISKS:
        if environment.get(key) is not False:
            blockers.append("ADAPTER_RISK:" + key)
    for key in ("capacity_sufficient", "rollback_supported"):
        if environment.get(key) is not True:
            blockers.append("ADAPTER_REQUIREMENT_MISSING:" + key)
    for key in ("provider_state", "rollback_state"):
        if environment.get(key) != "SYNTHETIC_READY":
            blockers.append("ADAPTER_DEGRADED:" + key)
    cost = environment.get("finops_monthly_cents")
    if type(cost) is not int or not 0 <= cost <= FINOPS_CAP_CENTS:
        blockers.append("FINOPS_CAP_VIOLATION")
    refs = environment.get("evidence_refs")
    if (type(refs) is not list or not 1 <= len(refs) <= 16
            or any(type(ref) is not str or not _ID.fullmatch(ref) for ref in refs)
            or len(set(refs)) != len(refs)):
        blockers.append("ADAPTER_EVIDENCE_REQUIRED")
    return blockers


def rollback_for(binding):
    """Reversal of simulation/pre-action staging only, never undo of deletion."""
    return {
        "binding": binding, "rollback_supported": True,
        "rollback_mode": "PRE_EXECUTION_STAGING_REVERSAL_ONLY",
        "rollback_steps_abstract": ["DISCARD_SYNTHETIC_CHANGESET", "RESTORE_SYNTHETIC_BEFORE_STATE", "REVIEW_OWNER_BOUNDARY"],
        "rollback_evidence_required": ["BEFORE_STATE_DIGEST", "RETENTION_AND_REVERSIBILITY_PROOF"],
        "rollback_receipt_required": True, "rollback_timeout_seconds": 180,
        "rollback_owner_confirmation_required": True, "irreversible_boundary_detected": False,
        **{key: False for key in FALSE_FIELDS},
    }


def plan_body(binding, environment):
    family = binding["action_family"]
    rollback = rollback_for(binding)
    return {
        "binding": binding, "adapter_kind": ADAPTER_KIND,
        "provider_class": "SYNTHETIC_MANAGED_SERVICE", "target_domain": "MANAGED_SERVICE",
        "operation_kind": binding["operation_kind"],
        "required_capabilities": list(CAPABILITIES[family]),
        "required_scopes": ["OWNER", "TENANT", "WORKSPACE", "CUSTOMER", "PILOT", "PACKAGE"],
        "rollback_strategy": "PRE_EXECUTION_STAGING_REVERSAL_ONLY",
        "idempotency_strategy": "BOUND_SCOPE_AND_COMMAND_PLAN_DIGEST",
        "idempotency_key_digest": digest(binding),
        "expected_side_effect_classes": ["SYNTHETIC_STATE_COMPARISON_ONLY"],
        "expected_receipt_classes": ["SYNTHETIC_DRY_RUN_RECEIPT"],
        "environment": environment, "environment_digest": digest(environment),
        "rollback_plan": rollback, "rollback_plan_digest": digest(rollback),
        "future_executor_requires_separate_contract": True,
        **{key: False for key in FALSE_FIELDS},
    }


def build_owner_renewal_action_adapter_plan(*, trusted_scope, command_plan,
        execution_persistence_attestation, execution_writer_attestation,
        execution_preflight, adapter_environment, now_ts):
    """Rebuild existing command plan and bind a fresh offline environment."""
    try:
        scope, supplied, persisted, writer, preflight, environment = safe_copy([
            trusted_scope, command_plan, execution_persistence_attestation,
            execution_writer_attestation, execution_preflight, adapter_environment])
        if not scope_valid(scope) or any(type(v) is not dict for v in (supplied, persisted, writer, preflight, environment)):
            raise ValueError("ADAPTER_INPUT_INVALID")
        rebuilt = build_owner_renewal_action_command_plan(trusted_scope=scope,
            execution_persistence_attestation=persisted, execution_writer_attestation=writer,
            execution_preflight=preflight)
        if rebuilt["state"] != "READY_FOR_BUSINESS_ACTION_COMMAND_ADAPTER_REVIEW":
            return result(SCHEMA, "BLOCKED", ["COMMAND_PLAN_REBUILD_BLOCKED", *rebuilt["blockers"]])
        if digest(supplied) != digest(rebuilt) or persisted.get("blockers") != [] or writer.get("blockers") != []:
            raise ValueError("COMMAND_PLAN_OR_ATTESTATION_MISMATCH")
        plan = rebuilt["command_plan"]
        if ACTION_FAMILY.get(plan["requested_choice"]) != plan["action_family"]:
            raise ValueError("CHOICE_FAMILY_MISMATCH")
        for key in BINDING_FIELDS:
            item = plan[key]
            if type(item) is not str or not (_HASH.fullmatch(item) if key.endswith("digest") else _ID.fullmatch(item)):
                raise ValueError("COMMAND_BINDING_INVALID")
        binding = {"scope": scope, **{key: plan[key] for key in BINDING_FIELDS},
                   "command_plan_digest": rebuilt["command_plan_digest"]}
        blockers = environment_blockers(environment, binding, now_ts)
        if blockers:
            return result(SCHEMA, "BLOCKED", blockers)
        body = plan_body(binding, environment)
        return result(SCHEMA, READY, adapter_plan=body, adapter_plan_digest=digest(body))
    except (ValueError, KeyError, TypeError, OverflowError):
        return result(SCHEMA, "BLOCKED", ["ADAPTER_INPUT_INVALID"])


def validate_adapter_plan(adapter_plan, trusted_scope, now_ts):
    """Structural simulation validation; never verifies real authority."""
    supplied = safe_copy(adapter_plan)
    scope = safe_copy(trusted_scope)
    if not scope_valid(scope) or type(supplied) is not dict:
        raise ValueError("ADAPTER_PLAN_INVALID")
    body = supplied.get("adapter_plan", {})
    binding = body.get("binding", {}) if type(body) is dict else {}
    if set(binding) != {"scope", "command_plan_digest", *BINDING_FIELDS} or binding.get("scope") != scope:
        raise ValueError("ADAPTER_SCOPE_OR_BINDING_INVALID")
    family = binding.get("action_family")
    if family not in CAPABILITIES or ACTION_FAMILY.get(binding.get("requested_choice")) != family:
        raise ValueError("ACTION_FAMILY_UNSUPPORTED")
    if binding.get("operation_kind") != ACTION_OPERATION_KIND[family]:
        raise ValueError("OPERATION_KIND_MISMATCH")
    for key, value in binding.items():
        if key == "scope":
            continue
        if type(value) is not str or not (_HASH.fullmatch(value) if key.endswith("digest") else _ID.fullmatch(value)):
            raise ValueError("ADAPTER_BINDING_INVALID")
    environment = body.get("environment", {})
    if type(environment) is not dict or environment_blockers(environment, binding, now_ts):
        raise ValueError("ADAPTER_ENVIRONMENT_INVALID")
    canonical = plan_body(binding, environment)
    if digest(supplied) != digest(result(SCHEMA, READY, adapter_plan=canonical, adapter_plan_digest=digest(canonical))):
        raise ValueError("ADAPTER_PLAN_REBUILD_MISMATCH")
    return canonical


__all__ = ["SCHEMA", "ENVIRONMENT_SCHEMA", "READY", "ADAPTER_KIND", "CAPABILITIES",
           "FALSE_FIELDS", "build_owner_renewal_action_adapter_plan", "validate_adapter_plan"]
