"""AION Signed GitHub Mutation Adapter + Immutable Outcome Receipt V1.

Pure, non-executing contracts for the first repository-mutation layer that sits
after READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT.

This module never calls GitHub. It never opens network transport, resolves an
endpoint, loads credentials, constructs a raw API request, marks a PR ready,
retargets, rebases, merges, closes, deletes a branch, deploys, activates Worker,
activates providers or activates production persistence.

It defines four things only:

1. evidence required to attest a signed least-privilege GitHub mutation adapter;
2. an immutable external attempt observation bound to one executor boundary;
3. an immutable primary mutation outcome receipt;
4. verification/policy rules that force ambiguity to OUTCOME_UNKNOWN.

Primary outcome states are exactly:
- CONFIRMED_SUCCESS
- CONFIRMED_TERMINAL_FAILURE
- OUTCOME_UNKNOWN

OUTCOME_UNKNOWN never authorizes retry. A new attempt requires a fresh
authorization ceremony and separate reconciliation/evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_repository_mutation_executor_boundary_v1 import (
    EXECUTOR_BOUNDARY_SCHEMA,
    LOGICAL_OPERATIONS,
    verify_executor_boundary,
)


SCHEMA = "ATLASQUANT_AION_SIGNED_GITHUB_MUTATION_ADAPTER_OUTCOME_V1"
ADAPTER_SCHEMA = "ATLASQUANT_AION_SIGNED_GITHUB_MUTATION_ADAPTER_ATTESTATION_V1"
ATTEMPT_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_ATTEMPT_OBSERVATION_V1"
OUTCOME_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_OUTCOME_RECEIPT_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_OUTCOME_RECEIPT_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_GITHUB_MUTATION_OUTCOME_POLICY_V1"

PROVIDER_IDENTITY = "GITHUB"
TRANSPORT_CLASS = "HTTPS_API_EXTERNAL_ADAPTER"
OUTCOME_STATES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "OUTCOME_UNKNOWN",
)
AMBIGUITY_TRIGGERS = (
    "TIMEOUT_AFTER_DISPATCH",
    "CONNECTION_RESET_AFTER_DISPATCH",
    "PROCESS_CRASH_AFTER_DISPATCH",
    "MISSING_PROVIDER_RESPONSE",
    "MALFORMED_PROVIDER_RESPONSE",
    "AMBIGUOUS_PROVIDER_RESPONSE",
    "RESPONSE_CORRELATION_MISMATCH",
    "RESPONSE_AUTHENTICITY_UNVERIFIED",
    "RESPONSE_SCHEMA_MISMATCH",
    "POSTCONDITION_READBACK_MISSING",
    "POSTCONDITION_READBACK_CONFLICT",
    "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT",
    "DUPLICATE_RESPONSE_CONFLICT",
    "EVIDENCE_INCOMPLETE",
)
EXPECTED_POSTCONDITIONS = {
    "PR_DRAFT_TO_READY": "PR_IS_READY_FOR_REVIEW",
    "PR_RETARGET_TO_MAIN": "PR_BASE_IS_MAIN",
    "SQUASH_MERGE_TO_MAIN": "PR_MERGED_AND_MERGE_COMMIT_PRESENT_IN_MAIN",
}
ALLOWED_LOGICAL_OPERATIONS = tuple(LOGICAL_OPERATIONS.values())
FORBIDDEN_ADAPTER_CAPABILITIES = (
    "DELETE_REPOSITORY",
    "DELETE_BRANCH",
    "FORCE_PUSH",
    "RESET_MAIN",
    "REWRITE_HISTORY",
    "CREATE_RELEASE",
    "DEPLOY",
    "WRITE_SECRETS",
    "WRITE_ACTIONS_SECRETS",
    "WRITE_ENVIRONMENT_SECRETS",
    "ADMIN_REPOSITORY",
    "TRANSFER_REPOSITORY",
    "CHANGE_RULESETS",
    "CHANGE_BRANCH_PROTECTION",
)
MAX_ATTEMPT_OBSERVATION_AGE_SECONDS = 30

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


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


def _sha(value: Any) -> str:
    token = _clean(value, 60)
    return token if _SHA_RE.fullmatch(token) else ""


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


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
        raise ValueError(f"{label} invalid") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return dt.astimezone(timezone.utc)


def build_signed_github_mutation_adapter_attestation(
    executor_boundary: Mapping[str, Any] | None,
    *,
    adapter_id: Any,
    adapter_version: Any,
    adapter_manifest_digest: Any,
    adapter_build_digest: Any,
    supply_chain_evidence_digest: Any,
    repository_identity_digest: Any,
    capability_scope_digest: Any,
    response_schema_digest: Any,
    error_taxonomy_digest: Any,
    postcondition_policy_digest: Any,
    signed_adapter_verified: bool,
    trusted_signing_root_verified: bool,
    repository_identity_match: bool,
    least_privilege_scope_verified: bool,
    logical_operation_allowlist: Sequence[Any] | None,
    forbidden_capabilities_declared: Sequence[Any] | None,
    checked_at: Any,
) -> dict[str, Any]:
    """Attest a future concrete adapter without loading or calling it."""
    boundary = dict(executor_boundary or {})
    blockers: list[str] = []

    boundary_check = verify_executor_boundary(boundary)
    if boundary_check.get("valid") is not True:
        blockers.append("VALID_EXECUTOR_BOUNDARY_REQUIRED")
    if boundary.get("schema") != EXECUTOR_BOUNDARY_SCHEMA:
        blockers.append("EXECUTOR_BOUNDARY_SCHEMA_MISMATCH")
    if boundary.get("state") != "READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT":
        blockers.append("READY_EXECUTOR_BOUNDARY_REQUIRED")
    if boundary.get("authorization_consumed_before_attempt") is not True:
        blockers.append("AUTHORIZATION_CONSUMPTION_REQUIRED")

    aid = _identity(adapter_id, 180)
    version = _identity(adapter_version, 120)
    manifest = _sha256(adapter_manifest_digest)
    build = _sha256(adapter_build_digest)
    supply = _sha256(supply_chain_evidence_digest)
    repository_digest = _sha256(repository_identity_digest)
    capability_digest = _sha256(capability_scope_digest)
    response_digest = _sha256(response_schema_digest)
    error_digest = _sha256(error_taxonomy_digest)
    postcondition_digest = _sha256(postcondition_policy_digest)

    if not aid:
        blockers.append("ADAPTER_ID_REQUIRED")
    if not version:
        blockers.append("ADAPTER_VERSION_REQUIRED")
    for label, value in (
        ("ADAPTER_MANIFEST_DIGEST_REQUIRED", manifest),
        ("ADAPTER_BUILD_DIGEST_REQUIRED", build),
        ("SUPPLY_CHAIN_EVIDENCE_DIGEST_REQUIRED", supply),
        ("REPOSITORY_IDENTITY_DIGEST_REQUIRED", repository_digest),
        ("CAPABILITY_SCOPE_DIGEST_REQUIRED", capability_digest),
        ("RESPONSE_SCHEMA_DIGEST_REQUIRED", response_digest),
        ("ERROR_TAXONOMY_DIGEST_REQUIRED", error_digest),
        ("POSTCONDITION_POLICY_DIGEST_REQUIRED", postcondition_digest),
    ):
        if not value:
            blockers.append(label)

    if manifest and manifest != _sha256(boundary.get("adapter_manifest_digest")):
        blockers.append("ADAPTER_MANIFEST_BOUNDARY_MISMATCH")
    if build and build != _sha256(boundary.get("adapter_build_digest")):
        blockers.append("ADAPTER_BUILD_BOUNDARY_MISMATCH")
    if repository_identity_match is not True:
        blockers.append("REPOSITORY_IDENTITY_MATCH_REQUIRED")
    if signed_adapter_verified is not True:
        blockers.append("SIGNED_ADAPTER_VERIFICATION_REQUIRED")
    if trusted_signing_root_verified is not True:
        blockers.append("TRUSTED_SIGNING_ROOT_REQUIRED")
    if least_privilege_scope_verified is not True:
        blockers.append("LEAST_PRIVILEGE_SCOPE_REQUIRED")

    allowed = tuple(
        _clean(item, 120).upper()
        for item in list(logical_operation_allowlist or [])
        if _clean(item, 120)
    )
    required_operation = _clean(boundary.get("logical_operation"), 120).upper()
    if required_operation not in allowed:
        blockers.append("REQUIRED_LOGICAL_OPERATION_NOT_ALLOWLISTED")
    if any(item not in ALLOWED_LOGICAL_OPERATIONS for item in allowed):
        blockers.append("UNKNOWN_LOGICAL_OPERATION_IN_ALLOWLIST")

    forbidden_declared = {
        _clean(item, 160).upper()
        for item in list(forbidden_capabilities_declared or [])
        if _clean(item, 160)
    }
    missing_forbidden = [
        capability
        for capability in FORBIDDEN_ADAPTER_CAPABILITIES
        if capability not in forbidden_declared
    ]
    if missing_forbidden:
        blockers.append("FORBIDDEN_CAPABILITY_DECLARATION_INCOMPLETE")

    try:
        checked = _aware(checked_at, "checked_at")
    except ValueError:
        checked = None
        blockers.append("ADAPTER_ATTESTATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "adapter_id": aid,
        "adapter_version": version,
        "provider_identity": PROVIDER_IDENTITY,
        "transport_class": TRANSPORT_CLASS,
        "executor_boundary_digest": _sha256(
            boundary.get("executor_boundary_digest")
        ),
        "repository_ref_digest": _sha256(
            boundary.get("repository_ref_digest")
        ),
        "pr_number": boundary.get("pr_number"),
        "requested_mutation": boundary.get("requested_mutation"),
        "logical_operation": boundary.get("logical_operation"),
        "adapter_manifest_digest": manifest,
        "adapter_build_digest": build,
        "supply_chain_evidence_digest": supply,
        "repository_identity_digest": repository_digest,
        "capability_scope_digest": capability_digest,
        "response_schema_digest": response_digest,
        "error_taxonomy_digest": error_digest,
        "postcondition_policy_digest": postcondition_digest,
        "logical_operation_allowlist": list(allowed),
        "forbidden_capabilities_declared": sorted(forbidden_declared),
        "signed_adapter_verified": signed_adapter_verified is True,
        "trusted_signing_root_verified": trusted_signing_root_verified is True,
        "repository_identity_match": repository_identity_match is True,
        "least_privilege_scope_verified": least_privilege_scope_verified is True,
        "checked_at": checked.isoformat() if checked else "",
    }

    return {
        "schema": ADAPTER_SCHEMA,
        "state": "SIGNED_GITHUB_MUTATION_ADAPTER_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "adapter_attestation_digest": _digest(material) if not blockers else "",
        "endpoint_included": False,
        "credential_material_included": False,
        "token_material_included": False,
        "raw_request_payload_included": False,
        "adapter_loaded_by_this_module": False,
        "api_request_generated": False,
        "github_api_called": False,
        "network_called": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def build_external_mutation_attempt_observation(
    executor_boundary: Mapping[str, Any] | None,
    adapter_attestation: Mapping[str, Any] | None,
    *,
    observation_id: Any,
    request_correlation_digest: Any,
    transport_observation_digest: Any,
    provider_request_identity_digest: Any,
    attempted_at: Any,
    observed_at: Any,
    trusted_adapter_observation_verified: bool,
    request_dispatch_observed: bool,
    network_transport_observed: bool,
) -> dict[str, Any]:
    """Represent an externally supplied attempt observation.

    This module does not perform the attempt. It only binds an attested
    observation from a future adapter.
    """
    boundary = dict(executor_boundary or {})
    adapter = dict(adapter_attestation or {})
    blockers: list[str] = []

    if verify_executor_boundary(boundary).get("valid") is not True:
        blockers.append("VALID_EXECUTOR_BOUNDARY_REQUIRED")
    if adapter.get("schema") != ADAPTER_SCHEMA:
        blockers.append("ADAPTER_ATTESTATION_SCHEMA_MISMATCH")
    if adapter.get("state") != "SIGNED_GITHUB_MUTATION_ADAPTER_ATTESTED":
        blockers.append("SIGNED_ADAPTER_ATTESTATION_REQUIRED")
    if _sha256(adapter.get("executor_boundary_digest")) != _sha256(
        boundary.get("executor_boundary_digest")
    ):
        blockers.append("ADAPTER_EXECUTOR_BOUNDARY_MISMATCH")

    oid = _identity(observation_id, 180)
    correlation = _sha256(request_correlation_digest)
    transport = _sha256(transport_observation_digest)
    request_identity = _sha256(provider_request_identity_digest)
    if not oid:
        blockers.append("OBSERVATION_ID_REQUIRED")
    if not correlation:
        blockers.append("REQUEST_CORRELATION_DIGEST_REQUIRED")
    if not transport:
        blockers.append("TRANSPORT_OBSERVATION_DIGEST_REQUIRED")
    if not request_identity:
        blockers.append("PROVIDER_REQUEST_IDENTITY_DIGEST_REQUIRED")
    if trusted_adapter_observation_verified is not True:
        blockers.append("TRUSTED_ADAPTER_OBSERVATION_REQUIRED")
    if request_dispatch_observed is not True:
        blockers.append("REQUEST_DISPATCH_OBSERVATION_REQUIRED")
    if network_transport_observed is not True:
        blockers.append("NETWORK_TRANSPORT_OBSERVATION_REQUIRED")

    try:
        attempted = _aware(attempted_at, "attempted_at")
        observed = _aware(observed_at, "observed_at")
        if observed < attempted:
            blockers.append("ATTEMPT_OBSERVATION_PRECEDES_ATTEMPT")
        if (observed - attempted).total_seconds() > MAX_ATTEMPT_OBSERVATION_AGE_SECONDS:
            blockers.append("ATTEMPT_OBSERVATION_STALE")
    except ValueError:
        attempted = None
        observed = None
        blockers.append("ATTEMPT_OBSERVATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "observation_id": oid,
        "execution_attempt_id": boundary.get("execution_attempt_id"),
        "executor_boundary_digest": _sha256(
            boundary.get("executor_boundary_digest")
        ),
        "adapter_attestation_digest": _sha256(
            adapter.get("adapter_attestation_digest")
        ),
        "provider_identity": PROVIDER_IDENTITY,
        "pr_number": boundary.get("pr_number"),
        "requested_mutation": boundary.get("requested_mutation"),
        "logical_operation": boundary.get("logical_operation"),
        "main_sha": _sha(boundary.get("main_sha")),
        "main_tree_sha": _sha(boundary.get("main_tree_sha")),
        "head_sha": _sha(boundary.get("head_sha")),
        "base_branch": boundary.get("base_branch"),
        "idempotency_key_digest": _sha256(
            boundary.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(boundary.get("effect_key_digest")),
        "lease_identity_digest": _sha256(
            boundary.get("lease_identity_digest")
        ),
        "request_correlation_digest": correlation,
        "transport_observation_digest": transport,
        "provider_request_identity_digest": request_identity,
        "trusted_adapter_observation_verified": (
            trusted_adapter_observation_verified is True
        ),
        "request_dispatch_observed": request_dispatch_observed is True,
        "network_transport_observed": network_transport_observed is True,
        "attempted_at": attempted.isoformat() if attempted else "",
        "observed_at": observed.isoformat() if observed else "",
    }

    return {
        "schema": ATTEMPT_SCHEMA,
        "state": "MUTATION_ATTEMPT_EXTERNALLY_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "attempt_observation_digest": _digest(material) if not blockers else "",
        "attempt_performed_by_this_module": False,
        "api_request_generated_by_this_module": False,
        "github_api_called_by_this_module": False,
        "network_called_by_this_module": False,
        "repository_mutation_performed_by_this_module": False,
        "automatic_retry_allowed": False,
        "retry_scheduled": False,
        "retry_performed": False,
        "executes_action": False,
    }


def build_immutable_mutation_outcome_receipt(
    attempt_observation: Mapping[str, Any] | None,
    *,
    receipt_id: Any,
    declared_outcome: Any,
    provider_response_evidence_digest: Any,
    postcondition_evidence_digest: Any,
    terminal_failure_evidence_digest: Any,
    ambiguity_evidence_digest: Any,
    ambiguity_triggers: Sequence[Any] | None,
    provider_response_received: bool,
    response_correlation_verified: bool,
    response_authenticity_verified: bool,
    response_schema_verified: bool,
    provider_success_semantics_verified: bool,
    provider_terminal_failure_semantics_verified: bool,
    repository_postcondition_readback_verified: bool,
    expected_postcondition_match: bool,
    authoritative_no_effect_or_terminal_rejection_verified: bool,
    evidence_complete: bool,
    observed_at: Any,
) -> dict[str, Any]:
    """Classify one externally attested mutation attempt fail-closed."""
    attempt = dict(attempt_observation or {})
    blockers: list[str] = []

    if attempt.get("schema") != ATTEMPT_SCHEMA:
        blockers.append("ATTEMPT_OBSERVATION_SCHEMA_MISMATCH")
    if attempt.get("state") != "MUTATION_ATTEMPT_EXTERNALLY_ATTESTED":
        blockers.append("ATTESTED_MUTATION_ATTEMPT_REQUIRED")
    if attempt.get("automatic_retry_allowed") is not False:
        blockers.append("ATTEMPT_AUTOMATIC_RETRY_BOUNDARY_INVALID")

    rid = _identity(receipt_id, 180)
    declared = _clean(declared_outcome, 100).upper()
    response_evidence = _sha256(provider_response_evidence_digest)
    postcondition_evidence = _sha256(postcondition_evidence_digest)
    terminal_evidence = _sha256(terminal_failure_evidence_digest)
    ambiguity_evidence = _sha256(ambiguity_evidence_digest)

    if not rid:
        blockers.append("OUTCOME_RECEIPT_ID_REQUIRED")
    if declared not in OUTCOME_STATES:
        blockers.append("DECLARED_OUTCOME_INVALID")

    triggers = sorted(
        {
            _clean(item, 160).upper()
            for item in list(ambiguity_triggers or [])
            if _clean(item, 160).upper() in AMBIGUITY_TRIGGERS
        }
    )
    unknown_forced = bool(triggers)

    if not response_evidence:
        unknown_forced = True
        if "EVIDENCE_INCOMPLETE" not in triggers:
            triggers.append("EVIDENCE_INCOMPLETE")
    if not evidence_complete:
        unknown_forced = True
        if "EVIDENCE_INCOMPLETE" not in triggers:
            triggers.append("EVIDENCE_INCOMPLETE")

    success_ready = all(
        (
            provider_response_received is True,
            response_correlation_verified is True,
            response_authenticity_verified is True,
            response_schema_verified is True,
            provider_success_semantics_verified is True,
            repository_postcondition_readback_verified is True,
            expected_postcondition_match is True,
            bool(postcondition_evidence),
            evidence_complete is True,
        )
    )

    terminal_failure_ready = all(
        (
            provider_response_received is True,
            response_correlation_verified is True,
            response_authenticity_verified is True,
            response_schema_verified is True,
            provider_terminal_failure_semantics_verified is True,
            authoritative_no_effect_or_terminal_rejection_verified is True,
            bool(terminal_evidence),
            evidence_complete is True,
        )
    )

    if declared == "CONFIRMED_SUCCESS" and not success_ready:
        unknown_forced = True
        if "EVIDENCE_INCOMPLETE" not in triggers:
            triggers.append("EVIDENCE_INCOMPLETE")
    if declared == "CONFIRMED_TERMINAL_FAILURE" and not terminal_failure_ready:
        unknown_forced = True
        if "EVIDENCE_INCOMPLETE" not in triggers:
            triggers.append("EVIDENCE_INCOMPLETE")
    if declared == "OUTCOME_UNKNOWN":
        unknown_forced = True

    if (
        provider_success_semantics_verified is True
        and provider_terminal_failure_semantics_verified is True
    ):
        unknown_forced = True
        if "SUCCESS_AND_FAILURE_SIGNAL_CONFLICT" not in triggers:
            triggers.append("SUCCESS_AND_FAILURE_SIGNAL_CONFLICT")

    if provider_response_received is not True:
        unknown_forced = True
        if "MISSING_PROVIDER_RESPONSE" not in triggers:
            triggers.append("MISSING_PROVIDER_RESPONSE")

    final_outcome = (
        "OUTCOME_UNKNOWN"
        if unknown_forced
        else declared
    )

    expected_postcondition = EXPECTED_POSTCONDITIONS.get(
        _clean(attempt.get("requested_mutation"), 100).upper(),
        "",
    )
    if not expected_postcondition:
        blockers.append("EXPECTED_POSTCONDITION_POLICY_MISSING")

    try:
        observed = _aware(observed_at, "observed_at")
        attempted = _aware(attempt.get("attempted_at"), "attempted_at")
        if observed < attempted:
            blockers.append("OUTCOME_OBSERVED_BEFORE_ATTEMPT")
    except ValueError:
        observed = None
        blockers.append("OUTCOME_OBSERVATION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    triggers = sorted(set(triggers))
    material = {
        "receipt_id": rid,
        "attempt_observation_digest": _sha256(
            attempt.get("attempt_observation_digest")
        ),
        "execution_attempt_id": attempt.get("execution_attempt_id"),
        "executor_boundary_digest": _sha256(
            attempt.get("executor_boundary_digest")
        ),
        "adapter_attestation_digest": _sha256(
            attempt.get("adapter_attestation_digest")
        ),
        "provider_identity": PROVIDER_IDENTITY,
        "pr_number": attempt.get("pr_number"),
        "requested_mutation": attempt.get("requested_mutation"),
        "logical_operation": attempt.get("logical_operation"),
        "idempotency_key_digest": _sha256(
            attempt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(attempt.get("effect_key_digest")),
        "request_correlation_digest": _sha256(
            attempt.get("request_correlation_digest")
        ),
        "declared_outcome": declared,
        "outcome": final_outcome,
        "expected_postcondition": expected_postcondition,
        "provider_response_evidence_digest": response_evidence,
        "postcondition_evidence_digest": postcondition_evidence,
        "terminal_failure_evidence_digest": terminal_evidence,
        "ambiguity_evidence_digest": ambiguity_evidence,
        "ambiguity_triggers": triggers,
        "provider_response_received": provider_response_received is True,
        "response_correlation_verified": response_correlation_verified is True,
        "response_authenticity_verified": response_authenticity_verified is True,
        "response_schema_verified": response_schema_verified is True,
        "provider_success_semantics_verified": (
            provider_success_semantics_verified is True
        ),
        "provider_terminal_failure_semantics_verified": (
            provider_terminal_failure_semantics_verified is True
        ),
        "repository_postcondition_readback_verified": (
            repository_postcondition_readback_verified is True
        ),
        "expected_postcondition_match": expected_postcondition_match is True,
        "authoritative_no_effect_or_terminal_rejection_verified": (
            authoritative_no_effect_or_terminal_rejection_verified is True
        ),
        "evidence_complete": evidence_complete is True,
        "observed_at": observed.isoformat() if observed else "",
    }

    classified = not blockers
    success = classified and final_outcome == "CONFIRMED_SUCCESS"
    terminal_failure = (
        classified and final_outcome == "CONFIRMED_TERMINAL_FAILURE"
    )
    unknown = classified and final_outcome == "OUTCOME_UNKNOWN"

    return {
        "schema": OUTCOME_SCHEMA,
        "state": "IMMUTABLE_MUTATION_OUTCOME_RECORDED" if classified else "BLOCKED",
        "blockers": blockers,
        **material,
        "outcome_receipt_digest": _digest(material) if classified else "",
        "receipt_immutable": classified,
        "receipt_append_only": classified,
        "success_confirmed": success,
        "terminal_failure_confirmed": terminal_failure,
        "outcome_unknown_recorded": unknown,
        "absence_of_error_is_success": False,
        "absence_of_response_is_terminal_failure": False,
        "automatic_retry_allowed": False,
        "retry_scheduled": False,
        "retry_performed": False,
        "reconciliation_required": unknown,
        "separate_reconciliation_record_required": unknown,
        "separate_reconciliation_authorization_required": unknown,
        "new_attempt_authorized": False,
        "fresh_authorization_required_for_new_attempt": True,
        "new_effect_key_required_for_new_attempt": True,
        "new_execution_attempt_id_required": True,
        "original_receipt_mutable": False,
        "receipt_persisted_by_this_module": False,
        "github_api_called_by_this_module": False,
        "network_called_by_this_module": False,
        "repository_mutation_performed_by_this_module": False,
        "executes_action": False,
    }


def verify_mutation_outcome_receipt(
    receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Verify receipt integrity and immutable outcome semantics."""
    raw = dict(receipt or {})
    blockers: list[str] = []

    if raw.get("schema") != OUTCOME_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
    if raw.get("state") != "IMMUTABLE_MUTATION_OUTCOME_RECORDED":
        blockers.append("IMMUTABLE_OUTCOME_RECEIPT_REQUIRED")
    if raw.get("receipt_immutable") is not True:
        blockers.append("RECEIPT_IMMUTABILITY_REQUIRED")
    if raw.get("receipt_append_only") is not True:
        blockers.append("APPEND_ONLY_RECEIPT_REQUIRED")
    if raw.get("automatic_retry_allowed") is not False:
        blockers.append("AUTOMATIC_RETRY_MUST_BE_FALSE")
    if raw.get("retry_scheduled") is not False:
        blockers.append("RETRY_SCHEDULED_MUST_BE_FALSE")
    if raw.get("retry_performed") is not False:
        blockers.append("RETRY_PERFORMED_MUST_BE_FALSE")
    if raw.get("new_attempt_authorized") is not False:
        blockers.append("NEW_ATTEMPT_MUST_REMAIN_UNAUTHORIZED")
    if raw.get("original_receipt_mutable") is not False:
        blockers.append("ORIGINAL_RECEIPT_MUST_REMAIN_IMMUTABLE")

    material = {
        key: raw.get(key)
        for key in (
            "receipt_id",
            "attempt_observation_digest",
            "execution_attempt_id",
            "executor_boundary_digest",
            "adapter_attestation_digest",
            "provider_identity",
            "pr_number",
            "requested_mutation",
            "logical_operation",
            "idempotency_key_digest",
            "effect_key_digest",
            "request_correlation_digest",
            "declared_outcome",
            "outcome",
            "expected_postcondition",
            "provider_response_evidence_digest",
            "postcondition_evidence_digest",
            "terminal_failure_evidence_digest",
            "ambiguity_evidence_digest",
            "ambiguity_triggers",
            "provider_response_received",
            "response_correlation_verified",
            "response_authenticity_verified",
            "response_schema_verified",
            "provider_success_semantics_verified",
            "provider_terminal_failure_semantics_verified",
            "repository_postcondition_readback_verified",
            "expected_postcondition_match",
            "authoritative_no_effect_or_terminal_rejection_verified",
            "evidence_complete",
            "observed_at",
        )
    }
    supplied = _sha256(raw.get("outcome_receipt_digest"))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("OUTCOME_RECEIPT_DIGEST_MISMATCH")

    outcome = _clean(raw.get("outcome"), 100).upper()
    if outcome not in OUTCOME_STATES:
        blockers.append("OUTCOME_STATE_INVALID")

    if outcome == "CONFIRMED_SUCCESS":
        if raw.get("success_confirmed") is not True:
            blockers.append("SUCCESS_CONFIRMATION_FLAG_REQUIRED")
        if raw.get("repository_postcondition_readback_verified") is not True:
            blockers.append("SUCCESS_POSTCONDITION_READBACK_REQUIRED")
        if raw.get("expected_postcondition_match") is not True:
            blockers.append("SUCCESS_POSTCONDITION_MATCH_REQUIRED")
        if raw.get("evidence_complete") is not True:
            blockers.append("SUCCESS_COMPLETE_EVIDENCE_REQUIRED")
    elif outcome == "CONFIRMED_TERMINAL_FAILURE":
        if raw.get("terminal_failure_confirmed") is not True:
            blockers.append("TERMINAL_FAILURE_CONFIRMATION_FLAG_REQUIRED")
        if (
            raw.get("authoritative_no_effect_or_terminal_rejection_verified")
            is not True
        ):
            blockers.append("TERMINAL_FAILURE_AUTHORITATIVE_EVIDENCE_REQUIRED")
        if raw.get("evidence_complete") is not True:
            blockers.append("TERMINAL_FAILURE_COMPLETE_EVIDENCE_REQUIRED")
    elif outcome == "OUTCOME_UNKNOWN":
        if raw.get("outcome_unknown_recorded") is not True:
            blockers.append("OUTCOME_UNKNOWN_FLAG_REQUIRED")
        if raw.get("reconciliation_required") is not True:
            blockers.append("UNKNOWN_RECONCILIATION_REQUIRED")
        if raw.get("separate_reconciliation_record_required") is not True:
            blockers.append("UNKNOWN_SEPARATE_RECONCILIATION_RECORD_REQUIRED")
        if raw.get("separate_reconciliation_authorization_required") is not True:
            blockers.append("UNKNOWN_SEPARATE_AUTHORIZATION_REQUIRED")

    for key in (
        "receipt_persisted_by_this_module",
        "github_api_called_by_this_module",
        "network_called_by_this_module",
        "repository_mutation_performed_by_this_module",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("OUTCOME_RECEIPT_UNSAFE_FIELD:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_MUTATION_OUTCOME_RECEIPT" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "outcome": outcome,
        "outcome_receipt_digest": supplied,
        "automatic_retry_allowed": False,
        "repository_mutation_performed_by_this_module": False,
        "executes_action": False,
    }


def github_mutation_outcome_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "provider_identity": PROVIDER_IDENTITY,
        "transport_class": TRANSPORT_CLASS,
        "outcome_states": list(OUTCOME_STATES),
        "ambiguity_triggers": list(AMBIGUITY_TRIGGERS),
        "expected_postconditions": dict(EXPECTED_POSTCONDITIONS),
        "allowed_logical_operations": list(ALLOWED_LOGICAL_OPERATIONS),
        "forbidden_adapter_capabilities": list(FORBIDDEN_ADAPTER_CAPABILITIES),
        "signed_adapter_required": True,
        "trusted_signing_root_required": True,
        "least_privilege_scope_required": True,
        "repository_identity_binding_required": True,
        "adapter_manifest_and_build_binding_required": True,
        "supply_chain_evidence_required": True,
        "response_schema_evidence_required": True,
        "error_taxonomy_required": True,
        "postcondition_policy_required": True,
        "raw_endpoint_material_allowed": False,
        "credential_material_allowed": False,
        "raw_request_payload_allowed": False,
        "attempt_observation_must_be_external_attestation": True,
        "attempt_performed_by_this_module": False,
        "absence_of_error_is_success": False,
        "absence_of_response_is_terminal_failure": False,
        "success_requires_authoritative_postcondition_readback": True,
        "terminal_failure_requires_authoritative_no_effect_or_rejection": True,
        "ambiguity_always_maps_to_outcome_unknown": True,
        "outcome_unknown_receipt_immutable": True,
        "automatic_retry_after_outcome_unknown_allowed": False,
        "reconciliation_required_after_outcome_unknown": True,
        "separate_reconciliation_record_required": True,
        "separate_reconciliation_authorization_required": True,
        "fresh_authorization_required_for_new_attempt": True,
        "new_effect_key_required_for_new_attempt": True,
        "new_execution_attempt_id_required": True,
        "github_api_called": False,
        "network_called": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "branch_deleted": False,
        "deploy_executed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "production_persistence_activation_allowed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ADAPTER_SCHEMA",
    "ATTEMPT_SCHEMA",
    "OUTCOME_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "PROVIDER_IDENTITY",
    "TRANSPORT_CLASS",
    "OUTCOME_STATES",
    "AMBIGUITY_TRIGGERS",
    "EXPECTED_POSTCONDITIONS",
    "ALLOWED_LOGICAL_OPERATIONS",
    "FORBIDDEN_ADAPTER_CAPABILITIES",
    "MAX_ATTEMPT_OBSERVATION_AGE_SECONDS",
    "build_signed_github_mutation_adapter_attestation",
    "build_external_mutation_attempt_observation",
    "build_immutable_mutation_outcome_receipt",
    "verify_mutation_outcome_receipt",
    "github_mutation_outcome_policy",
]
