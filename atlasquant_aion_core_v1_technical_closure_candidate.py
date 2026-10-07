"""AION Core V1 technical closure candidate.

This module records a non-authoritative closure candidate bound to the exact
validated parent commit. It does not certify itself, does not persist owner
decisions, does not freeze the Core, and never authorizes merge, deploy, worker
activation, or external execution.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "ATLASQUANT_AION_CORE_V1_TECHNICAL_CLOSURE_CANDIDATE_V1"
VERSION = 1
TARGET_COMMIT_SHA = "1f0575a650bce16acb94c69a24b880c16a79b445"
TARGET_CI_PR = 950
STATE = "TECHNICAL_CLOSURE_CANDIDATE"

REQUIRED_TECHNICAL_LAYERS = (
    "REAL_TRUST_ROOT_AUTHORITY_V213",
    "DURABLE_EXECUTION_V214",
    "CAPABILITY_ISOLATION_V215",
    "OPERATIONAL_RESILIENCE_V216",
    "MULTIAGENT_MEMORY_GOVERNANCE_V217",
    "CONSTITUTION_POLICY_KERNEL_V218",
    "PROVIDER_NEUTRAL_MODEL_GATEWAY_V219",
    "CORE_CERTIFICATION_V220",
    "CORE_COMPLETION_REVIEW_V221",
    "CORE_FREEZE_PREFLIGHT_V222",
    "EXTERNAL_PERSISTENCE_ATTESTATION_V223_CONTRACT",
    "OWNER_SIGNATURE_CEREMONY_V224_CONTRACT",
    "EXPLICIT_OWNER_DECISION_V225_CONTRACT",
    "OWNER_DECISION_PERSISTENCE_V226_CONTRACT",
    "TERMINAL_CERTIFICATE_DURABLE_STORE_EXTENSION",
    "TERMINAL_CERTIFICATE_RUNTIME_READER",
    "TERMINAL_CERTIFICATE_READ_MODEL_RUNTIME_PROJECTION",
    "TERMINAL_CERTIFICATE_UI_RUNTIME_BINDING",
    "TERMINAL_CERTIFICATE_PANEL_COMPONENT",
    "TERMINAL_CERTIFICATE_REFERENCE_UI_DRAFT",
    "GLOBAL_WORKER_READINESS_CONTRACT",
)

REAL_WORLD_STEPS_STILL_SEPARATE = (
    "REAL_V223_EXTERNAL_CHECKPOINT_PERSISTENCE",
    "REAL_V224_OWNER_SIGNATURE",
    "REAL_V225_EXPLICIT_OWNER_DECISION",
    "REAL_V226_OWNER_DECISION_PERSISTENCE",
    "CORE_FREEZE_EXECUTION",
    "MERGE",
    "DEPLOY",
    "GLOBAL_WORKER_ACTIVATION",
)

_FALSE_AUTHORITY_FIELDS = (
    "owner_decision_recorded",
    "core_complete",
    "core_freeze_authorized",
    "core_freeze_execution_authorized",
    "core_frozen",
    "merge_authorized",
    "deploy_authorized",
    "execution_allowed",
    "worker_armed",
    "external_action_executed",
    "production_mutation_performed",
    "executes_action",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def build_core_v1_technical_closure_candidate() -> dict[str, Any]:
    """Return a deterministic, non-authoritative closure candidate."""
    if not _SHA_RE.fullmatch(TARGET_COMMIT_SHA):
        raise ValueError("TARGET_COMMIT_SHA_INVALID")

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": STATE,
        "target_commit_sha": TARGET_COMMIT_SHA,
        "target_ci_pr": TARGET_CI_PR,
        "technical_layers": list(REQUIRED_TECHNICAL_LAYERS),
        "technical_layer_count": len(REQUIRED_TECHNICAL_LAYERS),
        "real_world_steps_still_separate": list(REAL_WORLD_STEPS_STILL_SEPARATE),
        "technical_closure_candidate": True,
        "technical_scope_closed_for_owner_review": True,
        "candidate_is_not_freeze": True,
        "candidate_is_not_owner_decision": True,
        "candidate_is_not_merge_or_deploy_authority": True,
        "candidate_is_not_runtime_activation": True,
        "owner_review_required": True,
        "requires_explicit_human_owner_action": True,
        "owner_decision": "UNDECIDED",
        "runtime_persistence_real_attestation_required": True,
        "owner_signature_real_required": True,
        "owner_decision_real_required": True,
        "owner_decision_persistence_real_required": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "TARGET_COMMIT_SHA",
    "TARGET_CI_PR",
    "STATE",
    "REQUIRED_TECHNICAL_LAYERS",
    "REAL_WORLD_STEPS_STILL_SEPARATE",
    "build_core_v1_technical_closure_candidate",
]
