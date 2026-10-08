"""AION Owner Stack Integration Certification V1.

Synthetic CI certification across the owner-facing stack built in #1015-#1028.

This module does not execute user actions. It aggregates deterministic evidence
from synthetic integration tests and checks policy surfaces across all stack
layers. A positive result is only:

SYNTHETIC_OWNER_STACK_CERTIFICATION_CANDIDATE

It is not production readiness, merge approval, deploy authorization, Worker
activation, provider authorization, or permission to perform physical actions.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_experience_v1 import owner_experience_policy
from atlasquant_aion_cognitive_continuity_v1 import cognitive_continuity_policy
from atlasquant_aion_secure_local_agent_v1 import secure_local_agent_policy
from atlasquant_aion_local_action_audit_receipt_v1 import local_action_audit_policy
from atlasquant_aion_secure_desktop_runtime_blueprint_v1 import (
    secure_desktop_runtime_policy,
)
from atlasquant_aion_voice_hotword_runtime_v1 import voice_privacy_policy
from atlasquant_aion_teaching_meeting_orchestrator_v1 import (
    teaching_meeting_policy,
)
from atlasquant_aion_presentation_artifact_control_v1 import presentation_policy
from atlasquant_aion_advisor_decision_support_v1 import advisor_policy
from atlasquant_aion_contract_communication_draft_approval_v1 import (
    contract_communication_policy,
)
from atlasquant_aion_approval_outbound_dispatch_bridge_v1 import (
    outbound_dispatch_policy,
)
from atlasquant_aion_outbound_execution_authorization_durable_dispatch_v1 import (
    outbound_execution_dispatch_policy,
)
from atlasquant_aion_sealed_provider_outcome_reconciliation_v1 import (
    outcome_chain_policy,
)
from atlasquant_aion_outbound_terminal_audit_certificate_v1 import (
    terminal_chain_policy,
)


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_INTEGRATION_CERTIFICATION_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_INTEGRATION_EVIDENCE_V1"
POLICY_SNAPSHOT_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_POLICY_SNAPSHOT_V1"
CERTIFICATION_VERSION = 1

REQUIRED_DIMENSIONS = (
    "OWNER_EXPERIENCE",
    "COGNITIVE_CONTINUITY",
    "SECURE_LOCAL_AGENT",
    "LOCAL_ACTION_AUDIT",
    "SECURE_DESKTOP_RUNTIME_BLUEPRINT",
    "VOICE_HOTWORD",
    "TEACHING_MEETING",
    "PRESENTATION_CONTROL",
    "ADVISOR_DECISION",
    "CONTRACT_COMMUNICATION",
    "APPROVAL_OUTBOUND_BRIDGE",
    "OUTBOUND_EXECUTION_DURABLE_DISPATCH",
    "SEALED_PROVIDER_OUTCOME_RECONCILIATION",
    "OUTBOUND_TERMINAL_AUDIT_CERTIFICATE",
    "CROSS_STACK_HANDOFFS",
    "GLOBAL_NO_SIDE_EFFECT_BOUNDARY",
)

POLICY_BUILDERS = (
    ("OWNER_EXPERIENCE", owner_experience_policy),
    ("COGNITIVE_CONTINUITY", cognitive_continuity_policy),
    ("SECURE_LOCAL_AGENT", secure_local_agent_policy),
    ("LOCAL_ACTION_AUDIT", local_action_audit_policy),
    ("SECURE_DESKTOP_RUNTIME_BLUEPRINT", secure_desktop_runtime_policy),
    ("VOICE_HOTWORD", voice_privacy_policy),
    ("TEACHING_MEETING", teaching_meeting_policy),
    ("PRESENTATION_CONTROL", presentation_policy),
    ("ADVISOR_DECISION", advisor_policy),
    ("CONTRACT_COMMUNICATION", contract_communication_policy),
    ("APPROVAL_OUTBOUND_BRIDGE", outbound_dispatch_policy),
    (
        "OUTBOUND_EXECUTION_DURABLE_DISPATCH",
        outbound_execution_dispatch_policy,
    ),
    ("SEALED_PROVIDER_OUTCOME_RECONCILIATION", outcome_chain_policy),
    ("OUTBOUND_TERMINAL_AUDIT_CERTIFICATE", terminal_chain_policy),
)

FORBIDDEN_TRUE_KEYS = (
    "executes_action",
    "external_action_executed",
    "provider_called",
    "network_called",
    "worker_armed",
    "deploy_executed",
    "core_checkpoint_write",
    "message_sent",
    "contract_signed",
    "payment_authorized",
    "trading_order_authorized",
    "automatic_execution",
    "execution_authorized",
    "application_launched",
    "microphone_started",
    "continuous_listener_started",
    "retry_executed",
    "execution_reopen_allowed",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


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


def owner_stack_policy_snapshot() -> dict[str, Any]:
    """Collect actual policy surfaces and fail closed on side-effect claims."""
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []

    for dimension, builder in POLICY_BUILDERS:
        try:
            policy = dict(builder())
        except Exception:
            blockers.append("POLICY_BUILD_FAILED:" + dimension)
            continue

        schema = _clean(policy.get("schema"), 180)
        if not schema:
            blockers.append("POLICY_SCHEMA_MISSING:" + dimension)
        if policy.get("executes_action") is not False:
            blockers.append("POLICY_EXECUTION_BOUNDARY_INVALID:" + dimension)

        violations = [
            key
            for key in FORBIDDEN_TRUE_KEYS
            if key in policy and policy.get(key) is True
        ]
        blockers.extend(
            f"POLICY_FORBIDDEN_TRUE:{dimension}:{key}"
            for key in violations
        )

        rows.append(
            {
                "dimension": dimension,
                "schema": schema,
                "policy_digest": _digest(policy),
                "forbidden_true_violations": violations,
                "executes_action": policy.get("executes_action"),
            }
        )

    blockers = list(dict.fromkeys(blockers))
    material = {
        "certification_version": CERTIFICATION_VERSION,
        "policies": rows,
    }
    return {
        "schema": POLICY_SNAPSHOT_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "blockers": blockers,
        **material,
        "policy_snapshot_digest": _digest(material),
        "policy_count": len(rows),
        "expected_policy_count": len(POLICY_BUILDERS),
        "executes_action": False,
    }


def build_integration_evidence(
    *,
    dimension: Any,
    source_ref: Any,
    evidence_material: Mapping[str, Any] | None,
    test_count: Any,
    passed: bool,
) -> dict[str, Any]:
    """Build synthetic CI evidence. This is not a trust-root attestation."""
    name = _clean(dimension, 100).upper()
    source = _clean(source_ref, 240)
    material = dict(evidence_material or {})
    blockers: list[str] = []

    if name not in REQUIRED_DIMENSIONS:
        blockers.append("DIMENSION_INVALID")
    if not source:
        blockers.append("SOURCE_REF_REQUIRED")
    try:
        count = int(test_count)
        if count < 1:
            blockers.append("POSITIVE_TEST_COUNT_REQUIRED")
    except Exception:
        count = 0
        blockers.append("TEST_COUNT_INVALID")
    if passed is not True:
        blockers.append("EVIDENCE_NOT_PASSING")

    dangerous = (
        "external_action_executed",
        "network_called",
        "provider_called",
        "deploy_executed",
        "worker_armed",
        "core_checkpoint_write",
        "physical_execution_performed",
    )
    for key in dangerous:
        if material.get(key) is True:
            blockers.append("EVIDENCE_SIDE_EFFECT_TRUE:" + key)

    blockers = list(dict.fromkeys(blockers))
    body = {
        "dimension": name,
        "source_ref": source,
        "test_count": count,
        "passed": passed is True,
        "synthetic": True,
        "material_digest": _digest(material),
        "external_action_executed": False,
        "network_called": False,
        "provider_called": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
    }
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "blockers": blockers,
        **body,
        "evidence_digest": _digest(body) if not blockers else "",
        "executes_action": False,
    }


def _verify_evidence_row(row: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if row.get("schema") != EVIDENCE_SCHEMA:
        blockers.append("EVIDENCE_SCHEMA_MISMATCH")
    if row.get("state") != "VALID" or row.get("blockers"):
        blockers.append("EVIDENCE_ROW_NOT_VALID")
    if _clean(row.get("dimension"), 100).upper() not in REQUIRED_DIMENSIONS:
        blockers.append("EVIDENCE_DIMENSION_INVALID")
    if row.get("passed") is not True:
        blockers.append("EVIDENCE_NOT_PASSING")
    if row.get("synthetic") is not True:
        blockers.append("EVIDENCE_MUST_BE_SYNTHETIC")
    if not _DIGEST_RE.fullmatch(_clean(row.get("evidence_digest"), 90)):
        blockers.append("EVIDENCE_DIGEST_INVALID")
    if row.get("executes_action") is not False:
        blockers.append("EVIDENCE_EXECUTION_BOUNDARY_INVALID")
    for key in (
        "external_action_executed",
        "network_called",
        "provider_called",
        "deploy_executed",
        "worker_armed",
        "core_checkpoint_write",
    ):
        if row.get(key) is not False:
            blockers.append("EVIDENCE_BOUNDARY_INVALID:" + key)
    return blockers


def certify_owner_stack(
    evidence_rows: Sequence[Mapping[str, Any]] | None,
    *,
    source_ref: Any,
    head_sha: Any,
) -> dict[str, Any]:
    """Certify synthetic integration semantics only."""
    blockers: list[str] = []
    source = _clean(source_ref, 240)
    sha = _clean(head_sha, 60)
    if not source:
        blockers.append("CERTIFICATION_SOURCE_REF_REQUIRED")
    if not _SHA_RE.fullmatch(sha):
        blockers.append("HEAD_SHA_INVALID")

    policy_snapshot = owner_stack_policy_snapshot()
    if policy_snapshot.get("state") != "VALID":
        blockers.append("POLICY_SNAPSHOT_INVALID")
    if policy_snapshot.get("policy_count") != len(POLICY_BUILDERS):
        blockers.append("POLICY_COUNT_MISMATCH")

    rows = [dict(row) for row in list(evidence_rows or [])]
    by_dimension: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        row_blockers = _verify_evidence_row(row)
        blockers.extend(
            f"EVIDENCE:{index}:{item}" for item in row_blockers
        )
        dimension = _clean(row.get("dimension"), 100).upper()
        if dimension:
            if dimension in by_dimension:
                blockers.append("DUPLICATE_DIMENSION:" + dimension)
            else:
                by_dimension[dimension] = row

    missing = [
        dimension
        for dimension in REQUIRED_DIMENSIONS
        if dimension not in by_dimension
    ]
    blockers.extend("MISSING_DIMENSION:" + item for item in missing)

    blockers = list(dict.fromkeys(blockers))
    evidence_digests = {
        dimension: _clean(by_dimension.get(dimension, {}).get("evidence_digest"), 90)
        for dimension in REQUIRED_DIMENSIONS
    }
    manifest = {
        "certification_version": CERTIFICATION_VERSION,
        "source_ref": source,
        "head_sha": sha,
        "required_dimensions": list(REQUIRED_DIMENSIONS),
        "policy_snapshot_digest": policy_snapshot.get("policy_snapshot_digest"),
        "evidence_digests": evidence_digests,
    }

    return {
        "schema": SCHEMA,
        "state": (
            "SYNTHETIC_OWNER_STACK_CERTIFICATION_CANDIDATE"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "source_ref": source,
        "head_sha": sha,
        "dimension_count": len(by_dimension),
        "required_dimension_count": len(REQUIRED_DIMENSIONS),
        "missing_dimensions": missing,
        "policy_snapshot": policy_snapshot,
        "evidence_digests": evidence_digests,
        "certification_manifest_digest": (
            _digest(manifest) if not blockers else ""
        ),
        "synthetic_only": True,
        "production_ready": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "physical_runtime_certified": False,
        "provider_execution_certified": False,
        "external_action_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "provider_called": False,
        "deploy_executed": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "EVIDENCE_SCHEMA",
    "POLICY_SNAPSHOT_SCHEMA",
    "CERTIFICATION_VERSION",
    "REQUIRED_DIMENSIONS",
    "POLICY_BUILDERS",
    "FORBIDDEN_TRUE_KEYS",
    "owner_stack_policy_snapshot",
    "build_integration_evidence",
    "certify_owner_stack",
]
