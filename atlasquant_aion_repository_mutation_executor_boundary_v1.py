"""AION Atomic Authorization Consumption + Repository Mutation Executor Boundary V1.

Pure, non-executing final boundary before a future repository mutation adapter.

This module requires:
- a verified single-use repository-mutation authorization receipt;
- an external persistence attestation for that receipt;
- a fresh execution-time repository-state rebuild;
- exact idempotency/effect/lease bindings;
- external proof of atomic authorization consumption;
- a signed least-privilege logical repository adapter attestation.

It may reach READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT.

It NEVER:
- calls GitHub;
- opens network;
- generates an API request;
- exposes a token/credential;
- marks a PR ready;
- retargets/rebases;
- merges;
- closes/deletes;
- deploys or activates Worker/provider/persistence.

The actual mutation adapter and its outcome receipt remain separate future work.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_owner_stack_live_merge_step_preflight_challenge_v1 import (
    PREFLIGHT_SCHEMA,
)
from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    RECEIPT_SCHEMA,
    PERSISTENCE_SCHEMA,
    verify_repository_mutation_authorization_receipt,
)


SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_EXECUTOR_BOUNDARY_V1"
CONSUMPTION_CANDIDATE_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTH_CONSUMPTION_CANDIDATE_V1"
)
CONSUMPTION_ATTESTATION_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTH_CONSUMPTION_ATTESTATION_V1"
)
EXECUTOR_BOUNDARY_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_SINGLE_ATTEMPT_BOUNDARY_V1"
)
VERIFY_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_EXECUTOR_BOUNDARY_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_EXECUTOR_BOUNDARY_POLICY_V1"

LOGICAL_OPERATIONS = {
    "PR_DRAFT_TO_READY": "SET_PR_READY_FOR_REVIEW",
    "PR_RETARGET_TO_MAIN": "SET_PR_BASE_TO_MAIN",
    "SQUASH_MERGE_TO_MAIN": "SQUASH_MERGE_PR_TO_MAIN",
}
MAX_EXECUTION_PREFLIGHT_AGE_SECONDS = 15

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 700) -> str:
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


def build_authorization_consumption_candidate(
    receipt: Mapping[str, Any] | None,
    receipt_persistence: Mapping[str, Any] | None,
    live_rebuilt_preflight: Mapping[str, Any] | None,
    *,
    execution_attempt_id: Any,
    repository_ref_digest: Any,
    idempotency_key_digest: Any,
    effect_key_digest: Any,
    lease_identity_digest: Any,
    checked_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Prepare exact atomic-consumption material. Does not consume anything."""
    auth = dict(receipt or {})
    persistence = dict(receipt_persistence or {})
    rebuilt = dict(live_rebuilt_preflight or {})
    blockers: list[str] = []

    try:
        current = _aware(now, "now")
        auth_check = verify_repository_mutation_authorization_receipt(
            auth,
            now=current.isoformat(),
        )
    except ValueError:
        current = None
        auth_check = {"valid": False}
        blockers.append("EXECUTOR_NOW_INVALID")

    if auth_check.get("valid") is not True:
        blockers.append("VALID_FRESH_AUTHORIZATION_RECEIPT_REQUIRED")
    if auth.get("schema") != RECEIPT_SCHEMA:
        blockers.append("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
    if auth.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")
    if auth.get("repository_mutation_performed") is not False:
        blockers.append("REPOSITORY_MUTATION_ALREADY_PERFORMED")

    if persistence.get("schema") != PERSISTENCE_SCHEMA:
        blockers.append("AUTHORIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if persistence.get("state") != "AUTHORIZATION_RECEIPT_PERSISTENCE_ATTESTED":
        blockers.append("AUTHORIZATION_PERSISTENCE_ATTESTATION_REQUIRED")
    if _sha256(persistence.get("authorization_receipt_digest")) != _sha256(
        auth.get("authorization_receipt_digest")
    ):
        blockers.append("PERSISTED_AUTHORIZATION_RECEIPT_DIGEST_MISMATCH")
    if not _sha256(persistence.get("persistence_attestation_digest")):
        blockers.append("PERSISTENCE_ATTESTATION_DIGEST_REQUIRED")
    if persistence.get("authorization_consumed") is not False:
        blockers.append("PERSISTENCE_SHOWS_AUTHORIZATION_CONSUMED")

    if rebuilt.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("EXECUTION_TIME_PREFLIGHT_SCHEMA_MISMATCH")
    if rebuilt.get("state") != "LIVE_STEP_PREFLIGHT_READY":
        blockers.append("EXECUTION_TIME_PREFLIGHT_REQUIRED")

    binding_pairs = (
        ("pr_number", "pr_number"),
        ("requested_mutation", "requested_mutation"),
        ("main_sha", "observed_main_sha"),
        ("main_tree_sha", "observed_main_tree_sha"),
        ("head_branch", "observed_head"),
        ("head_sha", "observed_head_sha"),
        ("base_branch", "observed_base"),
        ("file_delta_digest", "observed_files_digest"),
        ("workflow_snapshot_digest", "observed_workflows_digest"),
        ("readiness_digest", "current_readiness_digest"),
        ("rollback_plan_digest", "rollback_plan_digest"),
    )
    for receipt_key, rebuild_key in binding_pairs:
        if auth.get(receipt_key) != rebuilt.get(rebuild_key):
            blockers.append("EXECUTION_TIME_STATE_MISMATCH:" + receipt_key)

    if _sha256(auth.get("live_rebuilt_preflight_digest")) != _sha256(
        rebuilt.get("preflight_digest")
    ):
        blockers.append("EXECUTION_TIME_PREFLIGHT_DIGEST_MISMATCH")

    attempt = _identity(execution_attempt_id, 180)
    repository_digest = _sha256(repository_ref_digest)
    idempotency_digest = _sha256(idempotency_key_digest)
    effect_digest = _sha256(effect_key_digest)
    lease_digest = _sha256(lease_identity_digest)
    if not attempt:
        blockers.append("EXECUTION_ATTEMPT_ID_REQUIRED")
    if not repository_digest:
        blockers.append("REPOSITORY_REF_DIGEST_REQUIRED")
    if not idempotency_digest:
        blockers.append("IDEMPOTENCY_KEY_DIGEST_REQUIRED")
    if not effect_digest:
        blockers.append("EFFECT_KEY_DIGEST_REQUIRED")
    if not lease_digest:
        blockers.append("LEASE_IDENTITY_DIGEST_REQUIRED")

    mutation = _clean(auth.get("requested_mutation"), 100).upper()
    logical_operation = LOGICAL_OPERATIONS.get(mutation, "")
    if not logical_operation:
        blockers.append("SUPPORTED_LOGICAL_MUTATION_REQUIRED")

    try:
        checked = _aware(checked_at, "checked_at")
        if current is None:
            raise ValueError("now missing")
        age = (current - checked).total_seconds()
        if age < 0:
            blockers.append("EXECUTION_PREFLIGHT_FROM_FUTURE")
        if age > MAX_EXECUTION_PREFLIGHT_AGE_SECONDS:
            blockers.append("EXECUTION_PREFLIGHT_STALE")
        expires = _aware(auth.get("expires_at"), "authorization_expires_at")
        if current > expires:
            blockers.append("AUTHORIZATION_EXPIRED_BEFORE_CONSUMPTION")
    except ValueError:
        checked = None
        blockers.append("EXECUTION_PREFLIGHT_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "execution_attempt_id": attempt,
        "authorization_receipt_digest": _sha256(
            auth.get("authorization_receipt_digest")
        ),
        "authorization_persistence_attestation_digest": _sha256(
            persistence.get("persistence_attestation_digest")
        ),
        "execution_time_preflight_digest": _sha256(
            rebuilt.get("preflight_digest")
        ),
        "repository_ref_digest": repository_digest,
        "pr_number": auth.get("pr_number"),
        "requested_mutation": mutation,
        "logical_operation": logical_operation,
        "main_sha": _sha(auth.get("main_sha")),
        "main_tree_sha": _sha(auth.get("main_tree_sha")),
        "head_branch": auth.get("head_branch"),
        "head_sha": _sha(auth.get("head_sha")),
        "base_branch": auth.get("base_branch"),
        "file_delta_digest": _sha256(auth.get("file_delta_digest")),
        "workflow_snapshot_digest": _sha256(
            auth.get("workflow_snapshot_digest")
        ),
        "idempotency_key_digest": idempotency_digest,
        "effect_key_digest": effect_digest,
        "lease_identity_digest": lease_digest,
        "checked_at": checked.isoformat() if checked else "",
    }
    return {
        "schema": CONSUMPTION_CANDIDATE_SCHEMA,
        "state": (
            "READY_FOR_ATOMIC_AUTHORIZATION_CONSUMPTION"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "consumption_candidate_digest": _digest(material) if not blockers else "",
        "authorization_consumed": False,
        "authorization_consumed_by_this_module": False,
        "repository_mutation_request_generated": False,
        "repository_mutation_authorized_by_candidate": False,
        "github_api_called": False,
        "network_called": False,
        "credential_material_included": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def build_atomic_consumption_attestation(
    consumption_candidate: Mapping[str, Any] | None,
    *,
    consumption_record_digest: Any,
    writer_attestation_digest: Any,
    consumed_at: Any,
    atomic_compare_and_set_verified: bool,
    read_after_write_verified: bool,
    writer_identity_verified: bool,
    prior_unconsumed_state_verified: bool,
    future_reuse_rejection_verified: bool,
) -> dict[str, Any]:
    """Represent external proof that authorization was consumed exactly once."""
    candidate = dict(consumption_candidate or {})
    blockers: list[str] = []

    if candidate.get("schema") != CONSUMPTION_CANDIDATE_SCHEMA:
        blockers.append("CONSUMPTION_CANDIDATE_SCHEMA_MISMATCH")
    if candidate.get("state") != "READY_FOR_ATOMIC_AUTHORIZATION_CONSUMPTION":
        blockers.append("READY_CONSUMPTION_CANDIDATE_REQUIRED")
    if candidate.get("authorization_consumed") is not False:
        blockers.append("CANDIDATE_ALREADY_CONSUMED")

    candidate_digest = _sha256(candidate.get("consumption_candidate_digest"))
    record_digest = _sha256(consumption_record_digest)
    writer_digest = _sha256(writer_attestation_digest)
    if not candidate_digest:
        blockers.append("CONSUMPTION_CANDIDATE_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("CONSUMPTION_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    if atomic_compare_and_set_verified is not True:
        blockers.append("ATOMIC_COMPARE_AND_SET_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("READ_AFTER_WRITE_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("WRITER_IDENTITY_REQUIRED")
    if prior_unconsumed_state_verified is not True:
        blockers.append("PRIOR_UNCONSUMED_STATE_REQUIRED")
    if future_reuse_rejection_verified is not True:
        blockers.append("FUTURE_REUSE_REJECTION_REQUIRED")

    try:
        consumed = _aware(consumed_at, "consumed_at")
    except ValueError:
        consumed = None
        blockers.append("CONSUMPTION_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "consumption_candidate_digest": candidate_digest,
        "authorization_receipt_digest": _sha256(
            candidate.get("authorization_receipt_digest")
        ),
        "execution_attempt_id": candidate.get("execution_attempt_id"),
        "pr_number": candidate.get("pr_number"),
        "requested_mutation": candidate.get("requested_mutation"),
        "logical_operation": candidate.get("logical_operation"),
        "idempotency_key_digest": _sha256(
            candidate.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(candidate.get("effect_key_digest")),
        "lease_identity_digest": _sha256(
            candidate.get("lease_identity_digest")
        ),
        "consumption_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "consumed_at": consumed.isoformat() if consumed else "",
        "atomic_compare_and_set_verified": atomic_compare_and_set_verified is True,
        "read_after_write_verified": read_after_write_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
        "prior_unconsumed_state_verified": prior_unconsumed_state_verified is True,
        "future_reuse_rejection_verified": future_reuse_rejection_verified is True,
    }
    return {
        "schema": CONSUMPTION_ATTESTATION_SCHEMA,
        "state": "AUTHORIZATION_CONSUMPTION_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "consumption_attestation_digest": _digest(material) if not blockers else "",
        "authorization_consumed": not blockers,
        "authorization_consumed_by_this_module": False,
        "repository_mutation_performed": False,
        "github_api_called": False,
        "network_called": False,
        "executes_action": False,
    }


def build_repository_mutation_executor_boundary(
    consumption_candidate: Mapping[str, Any] | None,
    consumption_attestation: Mapping[str, Any] | None,
    *,
    adapter_manifest_digest: Any,
    adapter_build_digest: Any,
    signed_adapter_verified: bool,
    repository_identity_match: bool,
    least_privilege_scope_verified: bool,
    target_pr_match: bool,
    requested_mutation_match: bool,
    main_sha_match: bool,
    head_sha_match: bool,
    base_branch_match: bool,
    file_delta_match: bool,
    workflow_snapshot_match: bool,
    checked_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Seal one future logical mutation attempt. Does not call GitHub."""
    candidate = dict(consumption_candidate or {})
    consumed = dict(consumption_attestation or {})
    blockers: list[str] = []

    if candidate.get("schema") != CONSUMPTION_CANDIDATE_SCHEMA:
        blockers.append("CONSUMPTION_CANDIDATE_SCHEMA_MISMATCH")
    if candidate.get("state") != "READY_FOR_ATOMIC_AUTHORIZATION_CONSUMPTION":
        blockers.append("READY_CONSUMPTION_CANDIDATE_REQUIRED")

    if consumed.get("schema") != CONSUMPTION_ATTESTATION_SCHEMA:
        blockers.append("CONSUMPTION_ATTESTATION_SCHEMA_MISMATCH")
    if consumed.get("state") != "AUTHORIZATION_CONSUMPTION_ATTESTED":
        blockers.append("AUTHORIZATION_CONSUMPTION_ATTESTATION_REQUIRED")
    if consumed.get("authorization_consumed") is not True:
        blockers.append("AUTHORIZATION_MUST_BE_CONSUMED")
    if _sha256(consumed.get("consumption_candidate_digest")) != _sha256(
        candidate.get("consumption_candidate_digest")
    ):
        blockers.append("CONSUMPTION_CANDIDATE_BINDING_MISMATCH")

    adapter_manifest = _sha256(adapter_manifest_digest)
    adapter_build = _sha256(adapter_build_digest)
    if not adapter_manifest:
        blockers.append("ADAPTER_MANIFEST_DIGEST_REQUIRED")
    if not adapter_build:
        blockers.append("ADAPTER_BUILD_DIGEST_REQUIRED")

    for label, flag in (
        ("SIGNED_ADAPTER_VERIFICATION_REQUIRED", signed_adapter_verified),
        ("REPOSITORY_IDENTITY_MATCH_REQUIRED", repository_identity_match),
        ("LEAST_PRIVILEGE_SCOPE_REQUIRED", least_privilege_scope_verified),
        ("TARGET_PR_MATCH_REQUIRED", target_pr_match),
        ("REQUESTED_MUTATION_MATCH_REQUIRED", requested_mutation_match),
        ("MAIN_SHA_MATCH_REQUIRED", main_sha_match),
        ("HEAD_SHA_MATCH_REQUIRED", head_sha_match),
        ("BASE_BRANCH_MATCH_REQUIRED", base_branch_match),
        ("FILE_DELTA_MATCH_REQUIRED", file_delta_match),
        ("WORKFLOW_SNAPSHOT_MATCH_REQUIRED", workflow_snapshot_match),
    ):
        if flag is not True:
            blockers.append(label)

    try:
        checked = _aware(checked_at, "checked_at")
        current = _aware(now, "now")
        age = (current - checked).total_seconds()
        if age < 0:
            blockers.append("ADAPTER_PREFLIGHT_FROM_FUTURE")
        if age > MAX_EXECUTION_PREFLIGHT_AGE_SECONDS:
            blockers.append("ADAPTER_PREFLIGHT_STALE")
    except ValueError:
        checked = None
        blockers.append("ADAPTER_PREFLIGHT_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "execution_attempt_id": candidate.get("execution_attempt_id"),
        "authorization_receipt_digest": _sha256(
            candidate.get("authorization_receipt_digest")
        ),
        "consumption_attestation_digest": _sha256(
            consumed.get("consumption_attestation_digest")
        ),
        "repository_ref_digest": _sha256(
            candidate.get("repository_ref_digest")
        ),
        "pr_number": candidate.get("pr_number"),
        "requested_mutation": candidate.get("requested_mutation"),
        "logical_operation": candidate.get("logical_operation"),
        "main_sha": _sha(candidate.get("main_sha")),
        "main_tree_sha": _sha(candidate.get("main_tree_sha")),
        "head_branch": candidate.get("head_branch"),
        "head_sha": _sha(candidate.get("head_sha")),
        "base_branch": candidate.get("base_branch"),
        "file_delta_digest": _sha256(candidate.get("file_delta_digest")),
        "workflow_snapshot_digest": _sha256(
            candidate.get("workflow_snapshot_digest")
        ),
        "idempotency_key_digest": _sha256(
            candidate.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(candidate.get("effect_key_digest")),
        "lease_identity_digest": _sha256(
            candidate.get("lease_identity_digest")
        ),
        "adapter_manifest_digest": adapter_manifest,
        "adapter_build_digest": adapter_build,
        "signed_adapter_verified": signed_adapter_verified is True,
        "repository_identity_match": repository_identity_match is True,
        "least_privilege_scope_verified": least_privilege_scope_verified is True,
        "target_pr_match": target_pr_match is True,
        "requested_mutation_match": requested_mutation_match is True,
        "main_sha_match": main_sha_match is True,
        "head_sha_match": head_sha_match is True,
        "base_branch_match": base_branch_match is True,
        "file_delta_match": file_delta_match is True,
        "workflow_snapshot_match": workflow_snapshot_match is True,
        "checked_at": checked.isoformat() if checked else "",
    }
    return {
        "schema": EXECUTOR_BOUNDARY_SCHEMA,
        "state": (
            "READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "executor_boundary_digest": _digest(material) if not blockers else "",
        "exactly_one_mutation_attempt_allowed": not blockers,
        "authorization_consumed_before_attempt": not blockers,
        "provider_switch_allowed": False,
        "repository_switch_allowed": False,
        "pr_switch_allowed": False,
        "mutation_switch_allowed": False,
        "main_sha_switch_allowed": False,
        "head_sha_switch_allowed": False,
        "base_switch_allowed": False,
        "scope_expansion_allowed": False,
        "api_request_generated": False,
        "api_method_selected": False,
        "api_endpoint_included": False,
        "credential_material_included": False,
        "github_api_called": False,
        "network_called": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "branch_deleted": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
        "executes_action": False,
    }


def verify_executor_boundary(
    boundary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(boundary or {})
    blockers: list[str] = []

    if raw.get("schema") != EXECUTOR_BOUNDARY_SCHEMA:
        blockers.append("EXECUTOR_BOUNDARY_SCHEMA_MISMATCH")
    if raw.get("state") != "READY_FOR_SINGLE_REPOSITORY_MUTATION_ATTEMPT":
        blockers.append("READY_EXECUTOR_BOUNDARY_REQUIRED")

    material = {
        key: raw.get(key)
        for key in (
            "execution_attempt_id",
            "authorization_receipt_digest",
            "consumption_attestation_digest",
            "repository_ref_digest",
            "pr_number",
            "requested_mutation",
            "logical_operation",
            "main_sha",
            "main_tree_sha",
            "head_branch",
            "head_sha",
            "base_branch",
            "file_delta_digest",
            "workflow_snapshot_digest",
            "idempotency_key_digest",
            "effect_key_digest",
            "lease_identity_digest",
            "adapter_manifest_digest",
            "adapter_build_digest",
            "signed_adapter_verified",
            "repository_identity_match",
            "least_privilege_scope_verified",
            "target_pr_match",
            "requested_mutation_match",
            "main_sha_match",
            "head_sha_match",
            "base_branch_match",
            "file_delta_match",
            "workflow_snapshot_match",
            "checked_at",
        )
    }
    supplied = _sha256(raw.get("executor_boundary_digest"))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("EXECUTOR_BOUNDARY_DIGEST_MISMATCH")

    if raw.get("exactly_one_mutation_attempt_allowed") is not True:
        blockers.append("SINGLE_ATTEMPT_SCOPE_REQUIRED")
    if raw.get("authorization_consumed_before_attempt") is not True:
        blockers.append("AUTHORIZATION_CONSUMPTION_REQUIRED")

    for key in (
        "provider_switch_allowed",
        "repository_switch_allowed",
        "pr_switch_allowed",
        "mutation_switch_allowed",
        "main_sha_switch_allowed",
        "head_sha_switch_allowed",
        "base_switch_allowed",
        "scope_expansion_allowed",
        "api_request_generated",
        "api_method_selected",
        "api_endpoint_included",
        "credential_material_included",
        "github_api_called",
        "network_called",
        "repository_mutation_performed",
        "merge_executed",
        "retarget_executed",
        "draft_transition_executed",
        "branch_deleted",
        "deploy_executed",
        "worker_activated",
        "provider_activated",
        "production_persistence_activated",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("EXECUTOR_BOUNDARY_UNSAFE_FIELD:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_EXECUTOR_BOUNDARY" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "executor_boundary_digest": supplied,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def repository_mutation_executor_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "authorization_receipt_must_be_verified": True,
        "authorization_receipt_must_be_persisted": True,
        "execution_time_live_state_rebuild_required": True,
        "execution_preflight_max_age_seconds": MAX_EXECUTION_PREFLIGHT_AGE_SECONDS,
        "exact_receipt_state_match_required": True,
        "idempotency_key_required": True,
        "effect_key_required": True,
        "lease_identity_required": True,
        "atomic_authorization_consumption_required": True,
        "read_after_write_consumption_required": True,
        "future_reuse_rejection_required": True,
        "authorization_consumed_before_attempt": True,
        "signed_adapter_required": True,
        "least_privilege_scope_required": True,
        "repository_identity_match_required": True,
        "single_mutation_attempt_only": True,
        "logical_operations": dict(LOGICAL_OPERATIONS),
        "provider_switch_allowed": False,
        "repository_switch_allowed": False,
        "pr_switch_allowed": False,
        "mutation_switch_allowed": False,
        "main_sha_switch_allowed": False,
        "head_sha_switch_allowed": False,
        "base_switch_allowed": False,
        "scope_expansion_allowed": False,
        "raw_api_request_generation_allowed": False,
        "raw_api_endpoint_included": False,
        "credential_material_included": False,
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
    "CONSUMPTION_CANDIDATE_SCHEMA",
    "CONSUMPTION_ATTESTATION_SCHEMA",
    "EXECUTOR_BOUNDARY_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "LOGICAL_OPERATIONS",
    "MAX_EXECUTION_PREFLIGHT_AGE_SECONDS",
    "build_authorization_consumption_candidate",
    "build_atomic_consumption_attestation",
    "build_repository_mutation_executor_boundary",
    "verify_executor_boundary",
    "repository_mutation_executor_policy",
]
