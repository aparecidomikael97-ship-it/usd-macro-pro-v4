"""AION Windows Sandbox Physical Probe Plan + Evidence Schema V1.

Data-only plan for future Windows physical verification of the offline build
sandbox defined by #1048.

This module does not probe Windows, inspect tokens, create Job Objects, open
files, test network connectivity, spawn processes, or accept caller booleans as
physical proof.

It defines:
- the exact physical requirements inherited from the sandbox preflight;
- one canonical measurement plan per requirement;
- evidence envelope fields and host/collector/preflight binding;
- freshness/recheck policy;
- canonical uncollected evidence slots;
- structural validation that never upgrades evidence to verified physical proof.

A future Windows probe implementation must collect real evidence and add an
independent verifier/root-of-trust layer before any build may be authorized.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_windows_offline_build_sandbox_input_mount_v1 import (
    PREFLIGHT_SCHEMA,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_EVIDENCE_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_V1"
MEASUREMENT_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_MEASUREMENT_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_EVIDENCE_V1"
BUNDLE_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_EVIDENCE_BUNDLE_V1"
REVIEW_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_SANDBOX_PHYSICAL_PROBE_POLICY_V1"

READY_PLAN_STATE = "WINDOWS_SANDBOX_PHYSICAL_PROBE_PLAN_READY"
READY_REVIEW_STATE = "READY_FOR_WINDOWS_PHYSICAL_PROBE_IMPLEMENTATION_REVIEW"
BLOCKED_STATE = "BLOCKED"
UNMEASURED_STATE = "NOT_MEASURED"
NOT_COLLECTED = "NOT_COLLECTED"
WINDOWS_PLATFORM = "WINDOWS"
MAX_PLAN_AGE_SECONDS = 900

PROBE_REQUIREMENTS = (
    "WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED",
    "WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED",
    "CACHE_READ_ONLY_MOUNT_PROOF_REQUIRED",
    "SOURCE_READ_ONLY_MOUNT_PROOF_REQUIRED",
    "RUNTIME_READ_ONLY_MOUNT_PROOF_REQUIRED",
    "OUTPUT_TEMP_ONLY_WRITE_PROOF_REQUIRED",
    "SYMLINK_REPARSE_HARDLINK_ESCAPE_PROOF_REQUIRED",
    "ENVIRONMENT_SCRUB_PHYSICAL_PROOF_REQUIRED",
    "PINNED_PYTHON_BINARY_PROOF_REQUIRED",
    "NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED",
    "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED",
    "RESOURCE_LIMITS_PHYSICAL_PROOF_REQUIRED",
)

PROBE_SPECS = {
    "WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_ACCESS_TOKEN_INSPECTION",
        "expected_observation": "RESTRICTED_CURRENT_USER_TOKEN",
        "negative_test": "PRIVILEGE_ESCALATION_NOT_AVAILABLE",
        "freshness_seconds": 120,
    },
    "WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_JOB_OBJECT_QUERY",
        "expected_observation": "JOB_OBJECT_LIMITS_MATCH_PREFLIGHT",
        "negative_test": "SECOND_PROCESS_OR_CHILD_LIMIT_REJECTED",
        "freshness_seconds": 120,
    },
    "CACHE_READ_ONLY_MOUNT_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_FILESYSTEM_WRITE_PROBE",
        "expected_observation": "CACHE_WRITE_DENIED",
        "negative_test": "CREATE_MODIFY_DELETE_RENAME_DENIED",
        "freshness_seconds": 120,
    },
    "SOURCE_READ_ONLY_MOUNT_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_FILESYSTEM_WRITE_PROBE",
        "expected_observation": "SOURCE_WRITE_DENIED",
        "negative_test": "CREATE_MODIFY_DELETE_RENAME_DENIED",
        "freshness_seconds": 120,
    },
    "RUNTIME_READ_ONLY_MOUNT_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_FILESYSTEM_WRITE_PROBE",
        "expected_observation": "RUNTIME_WRITE_DENIED",
        "negative_test": "CREATE_MODIFY_DELETE_RENAME_DENIED",
        "freshness_seconds": 120,
    },
    "OUTPUT_TEMP_ONLY_WRITE_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_FILESYSTEM_BOUNDARY_PROBE",
        "expected_observation": "ONLY_OUTPUT_AND_TEMP_WRITABLE",
        "negative_test": "WRITE_OUTSIDE_OUTPUT_TEMP_DENIED",
        "freshness_seconds": 120,
    },
    "SYMLINK_REPARSE_HARDLINK_ESCAPE_PROOF_REQUIRED": {
        "measurement_method": "WINDOWS_REPARSE_HARDLINK_ESCAPE_PROBE",
        "expected_observation": "NO_FILESYSTEM_ESCAPE",
        "negative_test": "SYMLINK_REPARSE_HARDLINK_ESCAPE_DENIED",
        "freshness_seconds": 120,
    },
    "ENVIRONMENT_SCRUB_PHYSICAL_PROOF_REQUIRED": {
        "measurement_method": "CHILD_ENVIRONMENT_ENUMERATION",
        "expected_observation": "EXACT_SCRUBBED_ENVIRONMENT_ONLY",
        "negative_test": "FORBIDDEN_PARENT_ENVIRONMENT_ABSENT",
        "freshness_seconds": 120,
    },
    "PINNED_PYTHON_BINARY_PROOF_REQUIRED": {
        "measurement_method": "SECURE_HANDLE_BINARY_HASH_AND_PATH",
        "expected_observation": "EXACT_PINNED_PYTHON_BINARY",
        "negative_test": "ALTERNATE_EXECUTABLE_REJECTED",
        "freshness_seconds": 120,
    },
    "NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED": {
        "measurement_method": "CHILD_PROCESS_DENIAL_PROBE",
        "expected_observation": "CHILD_PROCESS_CREATION_DENIED",
        "negative_test": "CREATE_PROCESS_CHILD_ATTEMPT_BLOCKED",
        "freshness_seconds": 120,
    },
    "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED": {
        "measurement_method": "NETWORK_DENY_MULTI_SURFACE_PROBE",
        "expected_observation": "DNS_TCP_UDP_LOOPBACK_PROXY_REMOTE_PIPE_DENIED",
        "negative_test": "ALL_NETWORK_SURFACES_FAIL_CLOSED",
        "freshness_seconds": 60,
    },
    "RESOURCE_LIMITS_PHYSICAL_PROOF_REQUIRED": {
        "measurement_method": "JOB_RESOURCE_LIMIT_ENFORCEMENT_PROBE",
        "expected_observation": "CPU_MEMORY_OUTPUT_PROCESS_LIMITS_ENFORCED",
        "negative_test": "RESOURCE_LIMIT_BREACH_TERMINATES_OR_BLOCKS",
        "freshness_seconds": 120,
    },
}

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


class PhysicalProbePlanError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _clean(value: Any, limit: int = 1000) -> str:
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


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise PhysicalProbePlanError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise PhysicalProbePlanError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _canonical_measurements(
    *,
    preflight_digest: str,
    host_binding_digest: str,
    collector_manifest_digest: str,
    plan_created_at: str,
) -> list[dict[str, Any]]:
    rows = []
    for sequence, requirement in enumerate(PROBE_REQUIREMENTS, start=1):
        spec = PROBE_SPECS[requirement]
        material = {
            "sequence": sequence,
            "requirement": requirement,
            "platform": WINDOWS_PLATFORM,
            "measurement_method": spec["measurement_method"],
            "expected_observation": spec["expected_observation"],
            "negative_test": spec["negative_test"],
            "freshness_seconds": spec["freshness_seconds"],
            "sandbox_preflight_digest": preflight_digest,
            "host_binding_digest": host_binding_digest,
            "collector_manifest_digest": collector_manifest_digest,
            "plan_created_at": plan_created_at,
        }
        rows.append(
            {
                "schema": MEASUREMENT_SCHEMA,
                **material,
                "measurement_plan_digest": _digest(material),
                "requires_raw_evidence": True,
                "requires_raw_evidence_digest": True,
                "requires_collector_binary_digest": True,
                "requires_collector_signature_evidence": True,
                "requires_same_host_binding": True,
                "requires_preflight_binding": True,
                "requires_negative_test": True,
                "requires_recheck_before_use": True,
                "physical_probe_executed": False,
                "physical_proof_verified": False,
            }
        )
    return rows


def build_probe_plan(
    sandbox_preflight: Mapping[str, Any] | None,
    *,
    host_binding_digest: Any,
    collector_manifest_digest: Any,
    evidence_store_root_digest: Any,
    plan_created_at: Any,
) -> dict[str, Any]:
    preflight = dict(sandbox_preflight or {})
    blockers: list[str] = []

    if preflight.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("SANDBOX_PREFLIGHT_SCHEMA_MISMATCH")
    if preflight.get("state") != "WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE":
        blockers.append("PHYSICAL_PROBE_READY_SANDBOX_PREFLIGHT_REQUIRED")

    upstream = list(preflight.get("required_physical_proofs") or [])
    if upstream != list(PROBE_REQUIREMENTS):
        blockers.append("PHYSICAL_PROBE_REQUIREMENT_SET_MISMATCH")

    preflight_digest = _sha256(preflight.get("sandbox_preflight_digest"))
    host_digest = _sha256(host_binding_digest)
    collector_digest = _sha256(collector_manifest_digest)
    store_digest = _sha256(evidence_store_root_digest)
    if not preflight_digest:
        blockers.append("SANDBOX_PREFLIGHT_DIGEST_REQUIRED")
    if not host_digest:
        blockers.append("HOST_BINDING_DIGEST_REQUIRED")
    if not collector_digest:
        blockers.append("COLLECTOR_MANIFEST_DIGEST_REQUIRED")
    if not store_digest:
        blockers.append("EVIDENCE_STORE_ROOT_DIGEST_REQUIRED")

    try:
        created = _aware(plan_created_at, "PROBE_PLAN_CREATED_AT")
    except PhysicalProbePlanError as exc:
        created = None
        blockers.append(exc.code)

    created_text = created.isoformat() if created else ""
    measurements = _canonical_measurements(
        preflight_digest=preflight_digest,
        host_binding_digest=host_digest,
        collector_manifest_digest=collector_digest,
        plan_created_at=created_text,
    )
    material = {
        "platform": WINDOWS_PLATFORM,
        "sandbox_preflight_digest": preflight_digest,
        "host_binding_digest": host_digest,
        "collector_manifest_digest": collector_digest,
        "evidence_store_root_digest": store_digest,
        "plan_created_at": created_text,
        "max_plan_age_seconds": MAX_PLAN_AGE_SECONDS,
        "requirements": list(PROBE_REQUIREMENTS),
        "measurements": measurements,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PLAN_SCHEMA,
        "state": READY_PLAN_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "probe_plan_digest": _digest(material) if not blockers else "",
        "physical_probe_implemented": False,
        "physical_probe_executed": False,
        "physical_proof_verified": False,
        "independent_verifier_implemented": False,
        "external_root_of_trust_available": False,
        "build_authorized": False,
        "build_started": False,
    }


def uncollected_evidence_for_measurement(
    plan: Mapping[str, Any],
    measurement: Mapping[str, Any],
) -> dict[str, Any]:
    requirement = str(measurement.get("requirement") or "")
    material = {
        "requirement": requirement,
        "measurement_plan_digest": _sha256(measurement.get("measurement_plan_digest")),
        "probe_plan_digest": _sha256(plan.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(plan.get("sandbox_preflight_digest")),
        "host_binding_digest": _sha256(plan.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(plan.get("collector_manifest_digest")),
        "collection_state": NOT_COLLECTED,
    }
    return {
        "schema": EVIDENCE_SCHEMA,
        **material,
        "evidence_slot_digest": _digest(material),
        "observed_value": UNMEASURED_STATE,
        "negative_test_observed_value": UNMEASURED_STATE,
        "raw_evidence_ref": "",
        "raw_evidence_digest": "",
        "collector_binary_digest": "",
        "collector_signature_evidence_digest": "",
        "collected_at": "",
        "valid_until": "",
        "sequence": int(measurement.get("sequence") or 0),
        "evidence_is_physical": False,
        "independently_verified": False,
        "host_binding_verified": False,
        "preflight_binding_verified": False,
        "collector_identity_verified": False,
        "negative_test_verified": False,
        "freshness_verified": False,
        "physical_proof_verified": False,
    }


def build_uncollected_evidence_bundle(
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = dict(plan or {})
    blockers: list[str] = []
    if row.get("schema") != PLAN_SCHEMA:
        blockers.append("PROBE_PLAN_SCHEMA_MISMATCH")
    if row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")

    measurements = list(row.get("measurements") or [])
    if [item.get("requirement") for item in measurements if isinstance(item, Mapping)] != list(PROBE_REQUIREMENTS):
        blockers.append("CANONICAL_MEASUREMENT_ORDER_REQUIRED")

    evidence = [
        uncollected_evidence_for_measurement(row, measurement)
        for measurement in measurements
        if isinstance(measurement, Mapping)
    ]
    material = {
        "probe_plan_digest": _sha256(row.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(row.get("sandbox_preflight_digest")),
        "host_binding_digest": _sha256(row.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(row.get("collector_manifest_digest")),
        "evidence": evidence,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": BUNDLE_SCHEMA,
        "state": "PHYSICAL_PROBE_EVIDENCE_SCHEMA_READY_UNCOLLECTED"
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "evidence_bundle_digest": _digest(material) if not blockers else "",
        "required_total": len(PROBE_REQUIREMENTS),
        "collected_total": 0,
        "verified_total": 0,
        "missing_requirements": list(PROBE_REQUIREMENTS),
        "physical_probe_executed": False,
        "physical_proof_verified": False,
        "build_authorized": False,
    }


def validate_evidence_candidate_shape(
    plan: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate future evidence shape while refusing to trust it as proof.

    This function intentionally never returns physical_proof_verified=true.
    A future independent verifier must be implemented separately.
    """
    plan_row = dict(plan or {})
    row = dict(evidence or {})
    blockers: list[str] = []

    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    requirement = _clean(row.get("requirement"), 120)
    if requirement not in PROBE_REQUIREMENTS:
        blockers.append("UNKNOWN_PROBE_REQUIREMENT")
        spec = None
        measurement = None
    else:
        spec = PROBE_SPECS[requirement]
        measurement = next(
            (
                item
                for item in plan_row.get("measurements", [])
                if isinstance(item, Mapping)
                and item.get("requirement") == requirement
            ),
            None,
        )
        if measurement is None:
            blockers.append("MEASUREMENT_PLAN_NOT_FOUND")

    if row.get("schema") != EVIDENCE_SCHEMA:
        blockers.append("EVIDENCE_SCHEMA_MISMATCH")
    if _sha256(row.get("probe_plan_digest")) != _sha256(
        plan_row.get("probe_plan_digest")
    ):
        blockers.append("EVIDENCE_PLAN_BINDING_MISMATCH")
    if _sha256(row.get("sandbox_preflight_digest")) != _sha256(
        plan_row.get("sandbox_preflight_digest")
    ):
        blockers.append("EVIDENCE_PREFLIGHT_BINDING_MISMATCH")
    if _sha256(row.get("host_binding_digest")) != _sha256(
        plan_row.get("host_binding_digest")
    ):
        blockers.append("EVIDENCE_HOST_BINDING_MISMATCH")
    if _sha256(row.get("collector_manifest_digest")) != _sha256(
        plan_row.get("collector_manifest_digest")
    ):
        blockers.append("EVIDENCE_COLLECTOR_MANIFEST_MISMATCH")

    if measurement is not None:
        if _sha256(row.get("measurement_plan_digest")) != _sha256(
            measurement.get("measurement_plan_digest")
        ):
            blockers.append("EVIDENCE_MEASUREMENT_BINDING_MISMATCH")
        if int(row.get("sequence") or 0) != int(measurement.get("sequence") or 0):
            blockers.append("EVIDENCE_SEQUENCE_MISMATCH")

    for label, field in (
        ("RAW_EVIDENCE_DIGEST_REQUIRED", "raw_evidence_digest"),
        ("COLLECTOR_BINARY_DIGEST_REQUIRED", "collector_binary_digest"),
        (
            "COLLECTOR_SIGNATURE_EVIDENCE_DIGEST_REQUIRED",
            "collector_signature_evidence_digest",
        ),
    ):
        if not _sha256(row.get(field)):
            blockers.append(label)

    raw_ref = _identity(row.get("raw_evidence_ref"), 240)
    if not raw_ref:
        blockers.append("RAW_EVIDENCE_REF_REQUIRED")

    try:
        collected = _aware(row.get("collected_at"), "EVIDENCE_COLLECTED_AT")
        valid_until = _aware(row.get("valid_until"), "EVIDENCE_VALID_UNTIL")
        if valid_until <= collected:
            blockers.append("EVIDENCE_VALIDITY_WINDOW_INVALID")
        if spec is not None and (
            valid_until - collected
        ).total_seconds() > int(spec["freshness_seconds"]):
            blockers.append("EVIDENCE_VALIDITY_WINDOW_TOO_LONG")
    except PhysicalProbePlanError as exc:
        blockers.append(exc.code)

    if spec is not None:
        if row.get("observed_value") != spec["expected_observation"]:
            blockers.append("EXPECTED_OBSERVATION_NOT_MET")
        if row.get("negative_test_observed_value") != spec["negative_test"]:
            blockers.append("NEGATIVE_TEST_OBSERVATION_NOT_MET")

    # Caller self-asserted verification is never authority in this phase.
    for field in (
        "evidence_is_physical",
        "independently_verified",
        "host_binding_verified",
        "preflight_binding_verified",
        "collector_identity_verified",
        "negative_test_verified",
        "freshness_verified",
        "physical_proof_verified",
    ):
        if row.get(field) is True:
            blockers.append("CALLER_VERIFICATION_CLAIM_NOT_TRUSTED:" + field)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "requirement": requirement,
        "probe_plan_digest": _sha256(row.get("probe_plan_digest")),
        "measurement_plan_digest": _sha256(row.get("measurement_plan_digest")),
        "host_binding_digest": _sha256(row.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(row.get("collector_manifest_digest")),
        "raw_evidence_digest": _sha256(row.get("raw_evidence_digest")),
        "collector_binary_digest": _sha256(row.get("collector_binary_digest")),
        "collector_signature_evidence_digest": _sha256(
            row.get("collector_signature_evidence_digest")
        ),
        "observed_value": row.get("observed_value"),
        "negative_test_observed_value": row.get("negative_test_observed_value"),
        "collected_at": row.get("collected_at"),
        "valid_until": row.get("valid_until"),
    }
    return {
        "schema": REVIEW_SCHEMA,
        "state": "EVIDENCE_CANDIDATE_SHAPE_VALID_BUT_UNTRUSTED"
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "candidate_review_digest": _digest(material) if not blockers else "",
        "shape_valid": not blockers,
        "evidence_is_physical": False,
        "independently_verified": False,
        "physical_proof_verified": False,
        "build_authorized": False,
    }


def build_probe_implementation_review(
    plan: Mapping[str, Any] | None,
    bundle: Mapping[str, Any] | None,
    *,
    collector_source_digest: Any,
    collector_test_digest: Any,
    independent_verifier_design_digest: Any,
    evidence_store_design_digest: Any,
) -> dict[str, Any]:
    plan_row = dict(plan or {})
    bundle_row = dict(bundle or {})
    blockers: list[str] = []

    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if bundle_row.get("state") != "PHYSICAL_PROBE_EVIDENCE_SCHEMA_READY_UNCOLLECTED":
        blockers.append("UNCOLLECTED_EVIDENCE_SCHEMA_REQUIRED")
    if _sha256(bundle_row.get("probe_plan_digest")) != _sha256(
        plan_row.get("probe_plan_digest")
    ):
        blockers.append("EVIDENCE_BUNDLE_PLAN_BINDING_MISMATCH")

    digests = {}
    for key, value, label in (
        ("collector_source_digest", collector_source_digest, "COLLECTOR_SOURCE_DIGEST_REQUIRED"),
        ("collector_test_digest", collector_test_digest, "COLLECTOR_TEST_DIGEST_REQUIRED"),
        (
            "independent_verifier_design_digest",
            independent_verifier_design_digest,
            "INDEPENDENT_VERIFIER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "evidence_store_design_digest",
            evidence_store_design_digest,
            "EVIDENCE_STORE_DESIGN_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "evidence_bundle_digest": _sha256(bundle_row.get("evidence_bundle_digest")),
        **digests,
        "next_physical_phase": "WINDOWS_PROBE_COLLECTOR_IMPLEMENTATION_ON_OWNER_PC",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": REVIEW_SCHEMA,
        "state": READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "implementation_review_digest": _digest(material) if not blockers else "",
        "collector_implemented": False,
        "collector_executed": False,
        "independent_verifier_implemented": False,
        "evidence_collected": False,
        "physical_probe_executed": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
    }


def physical_probe_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "platform": WINDOWS_PLATFORM,
        "requirements": list(PROBE_REQUIREMENTS),
        "requirement_count": len(PROBE_REQUIREMENTS),
        "preflight_requirement_set_must_match_exactly": True,
        "host_binding_required": True,
        "collector_manifest_binding_required": True,
        "sandbox_preflight_binding_required": True,
        "raw_evidence_digest_required": True,
        "collector_binary_digest_required": True,
        "collector_signature_evidence_required": True,
        "negative_test_required": True,
        "freshness_window_required": True,
        "recheck_before_use_required": True,
        "caller_boolean_verification_is_authority": False,
        "document_digest_is_physical_proof": False,
        "physical_probe_implemented": False,
        "physical_probe_executed": False,
        "collector_implemented": False,
        "collector_executed": False,
        "independent_verifier_implemented": False,
        "external_root_of_trust_available": False,
        "evidence_collected": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "MEASUREMENT_SCHEMA",
    "EVIDENCE_SCHEMA",
    "BUNDLE_SCHEMA",
    "REVIEW_SCHEMA",
    "POLICY_SCHEMA",
    "READY_PLAN_STATE",
    "READY_REVIEW_STATE",
    "BLOCKED_STATE",
    "PROBE_REQUIREMENTS",
    "PROBE_SPECS",
    "MAX_PLAN_AGE_SECONDS",
    "PhysicalProbePlanError",
    "build_probe_plan",
    "uncollected_evidence_for_measurement",
    "build_uncollected_evidence_bundle",
    "validate_evidence_candidate_shape",
    "build_probe_implementation_review",
    "physical_probe_policy",
]
