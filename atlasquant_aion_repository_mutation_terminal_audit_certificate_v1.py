"""AION Repository Mutation Terminal Audit Certificate V1.

Pure, non-executing read-only certification for one repository mutation
attempt lineage.

The certificate binds:
- repository-mutation authorization receipt;
- authorization persistence attestation;
- atomic authorization-consumption attestation;
- executor boundary;
- signed GitHub adapter attestation;
- external mutation-attempt observation;
- immutable primary outcome receipt;
- optional append-only reconciliation record.

Unlike a terminal-only external-effect certificate, this certificate may also
truthfully represent an unresolved attempt as CERTIFIED_OPEN_AMBIGUOUS.

It never mutates GitHub, retries/replays a mutation, queries GitHub, persists a
certificate, deploys, or activates runtime capabilities.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_repository_mutation_authorization_receipt_v1 import (
    RECEIPT_SCHEMA as AUTH_RECEIPT_SCHEMA,
    PERSISTENCE_SCHEMA as AUTH_PERSISTENCE_SCHEMA,
    verify_repository_mutation_authorization_receipt,
)
from atlasquant_aion_repository_mutation_executor_boundary_v1 import (
    CONSUMPTION_ATTESTATION_SCHEMA,
    EXECUTOR_BOUNDARY_SCHEMA,
    verify_executor_boundary,
)
from atlasquant_aion_signed_github_mutation_adapter_outcome_v1 import (
    ADAPTER_SCHEMA,
    ATTEMPT_SCHEMA,
    OUTCOME_SCHEMA,
    verify_mutation_outcome_receipt,
)
from atlasquant_aion_github_mutation_outcome_reconciliation_v1 import (
    RECONCILIATION_SCHEMA,
    verify_outcome_reconciliation_record,
)


SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_V1"
CERTIFICATE_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_RECORD_V1"
)
PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_PERSISTENCE_V1"
)
VERIFY_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_VERIFY_V1"
)
POLICY_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_TERMINAL_AUDIT_CERTIFICATE_POLICY_V1"
)

CERTIFICATE_OUTCOMES = (
    "CERTIFIED_FINAL_SUCCESS",
    "CERTIFIED_FINAL_TERMINAL_FAILURE",
    "CERTIFIED_OPEN_AMBIGUOUS",
)
PRIMARY_FINAL_SUCCESS = "CONFIRMED_SUCCESS"
PRIMARY_FINAL_FAILURE = "CONFIRMED_TERMINAL_FAILURE"
PRIMARY_UNKNOWN = "OUTCOME_UNKNOWN"
RECONCILED_SUCCESS = "RECONCILED_CONFIRMED_SUCCESS"
RECONCILED_FAILURE = "RECONCILED_CONFIRMED_TERMINAL_FAILURE"
RECONCILED_UNKNOWN = "STILL_OUTCOME_UNKNOWN"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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
    return token if _DIGEST_RE.fullmatch(token) else ""


def _verify_lineage(
    authorization_receipt: Mapping[str, Any] | None,
    authorization_persistence: Mapping[str, Any] | None,
    consumption_attestation: Mapping[str, Any] | None,
    executor_boundary: Mapping[str, Any] | None,
    adapter_attestation: Mapping[str, Any] | None,
    attempt_observation: Mapping[str, Any] | None,
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation_record: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    auth = dict(authorization_receipt or {})
    persisted = dict(authorization_persistence or {})
    consumed = dict(consumption_attestation or {})
    boundary = dict(executor_boundary or {})
    adapter = dict(adapter_attestation or {})
    attempt = dict(attempt_observation or {})
    outcome = dict(outcome_receipt or {})
    reconciliation = dict(reconciliation_record or {})
    blockers: list[str] = []

    if auth.get("schema") != AUTH_RECEIPT_SCHEMA:
        blockers.append("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
    if verify_repository_mutation_authorization_receipt(auth).get("valid") is not True:
        blockers.append("VALID_AUTHORIZATION_RECEIPT_REQUIRED")

    auth_digest = _sha256(auth.get("authorization_receipt_digest"))
    if not auth_digest:
        blockers.append("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")

    if persisted.get("schema") != AUTH_PERSISTENCE_SCHEMA:
        blockers.append("AUTHORIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if persisted.get("state") != "AUTHORIZATION_RECEIPT_PERSISTENCE_ATTESTED":
        blockers.append("AUTHORIZATION_PERSISTENCE_ATTESTATION_REQUIRED")
    if _sha256(persisted.get("authorization_receipt_digest")) != auth_digest:
        blockers.append("AUTHORIZATION_PERSISTENCE_BINDING_MISMATCH")
    persistence_digest = _sha256(
        persisted.get("persistence_attestation_digest")
    )
    if not persistence_digest:
        blockers.append("AUTHORIZATION_PERSISTENCE_DIGEST_REQUIRED")

    if consumed.get("schema") != CONSUMPTION_ATTESTATION_SCHEMA:
        blockers.append("CONSUMPTION_ATTESTATION_SCHEMA_MISMATCH")
    if consumed.get("state") != "AUTHORIZATION_CONSUMPTION_ATTESTED":
        blockers.append("AUTHORIZATION_CONSUMPTION_ATTESTATION_REQUIRED")
    if consumed.get("authorization_consumed") is not True:
        blockers.append("AUTHORIZATION_CONSUMPTION_REQUIRED")
    if _sha256(consumed.get("authorization_receipt_digest")) != auth_digest:
        blockers.append("CONSUMPTION_AUTHORIZATION_RECEIPT_BINDING_MISMATCH")
    consumption_digest = _sha256(consumed.get("consumption_attestation_digest"))
    if not consumption_digest:
        blockers.append("CONSUMPTION_ATTESTATION_DIGEST_REQUIRED")

    if boundary.get("schema") != EXECUTOR_BOUNDARY_SCHEMA:
        blockers.append("EXECUTOR_BOUNDARY_SCHEMA_MISMATCH")
    if verify_executor_boundary(boundary).get("valid") is not True:
        blockers.append("VALID_EXECUTOR_BOUNDARY_REQUIRED")
    if _sha256(boundary.get("authorization_receipt_digest")) != auth_digest:
        blockers.append("EXECUTOR_AUTHORIZATION_RECEIPT_BINDING_MISMATCH")
    if _sha256(boundary.get("consumption_attestation_digest")) != consumption_digest:
        blockers.append("EXECUTOR_CONSUMPTION_BINDING_MISMATCH")
    boundary_digest = _sha256(boundary.get("executor_boundary_digest"))
    if not boundary_digest:
        blockers.append("EXECUTOR_BOUNDARY_DIGEST_REQUIRED")

    if adapter.get("schema") != ADAPTER_SCHEMA:
        blockers.append("ADAPTER_ATTESTATION_SCHEMA_MISMATCH")
    if adapter.get("state") != "SIGNED_GITHUB_MUTATION_ADAPTER_ATTESTED":
        blockers.append("SIGNED_ADAPTER_ATTESTATION_REQUIRED")
    if _sha256(adapter.get("executor_boundary_digest")) != boundary_digest:
        blockers.append("ADAPTER_EXECUTOR_BOUNDARY_BINDING_MISMATCH")
    adapter_digest = _sha256(adapter.get("adapter_attestation_digest"))
    if not adapter_digest:
        blockers.append("ADAPTER_ATTESTATION_DIGEST_REQUIRED")

    if attempt.get("schema") != ATTEMPT_SCHEMA:
        blockers.append("ATTEMPT_OBSERVATION_SCHEMA_MISMATCH")
    if attempt.get("state") != "MUTATION_ATTEMPT_EXTERNALLY_ATTESTED":
        blockers.append("ATTESTED_MUTATION_ATTEMPT_REQUIRED")
    if _sha256(attempt.get("executor_boundary_digest")) != boundary_digest:
        blockers.append("ATTEMPT_EXECUTOR_BOUNDARY_BINDING_MISMATCH")
    if _sha256(attempt.get("adapter_attestation_digest")) != adapter_digest:
        blockers.append("ATTEMPT_ADAPTER_BINDING_MISMATCH")
    attempt_digest = _sha256(attempt.get("attempt_observation_digest"))
    if not attempt_digest:
        blockers.append("ATTEMPT_OBSERVATION_DIGEST_REQUIRED")

    if outcome.get("schema") != OUTCOME_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
    if verify_mutation_outcome_receipt(outcome).get("valid") is not True:
        blockers.append("VALID_OUTCOME_RECEIPT_REQUIRED")
    if _sha256(outcome.get("attempt_observation_digest")) != attempt_digest:
        blockers.append("OUTCOME_ATTEMPT_BINDING_MISMATCH")
    outcome_digest = _sha256(outcome.get("outcome_receipt_digest"))
    if not outcome_digest:
        blockers.append("OUTCOME_RECEIPT_DIGEST_REQUIRED")

    for field in (
        "execution_attempt_id",
        "pr_number",
        "requested_mutation",
        "logical_operation",
        "idempotency_key_digest",
        "effect_key_digest",
    ):
        boundary_value = boundary.get(field)
        attempt_value = attempt.get(field)
        outcome_value = outcome.get(field)
        if attempt_value != boundary_value:
            blockers.append("ATTEMPT_LINEAGE_MISMATCH:" + field)
        if outcome_value != boundary_value:
            blockers.append("OUTCOME_LINEAGE_MISMATCH:" + field)

    primary = _clean(outcome.get("outcome"), 120).upper()
    reconciliation_digest = ""
    reconciled = ""
    if reconciliation:
        if primary != PRIMARY_UNKNOWN:
            blockers.append("RECONCILIATION_NOT_ALLOWED_FOR_PRIMARY_FINAL_OUTCOME")
        if reconciliation.get("schema") != RECONCILIATION_SCHEMA:
            blockers.append("RECONCILIATION_SCHEMA_MISMATCH")
        if verify_outcome_reconciliation_record(reconciliation).get("valid") is not True:
            blockers.append("VALID_RECONCILIATION_RECORD_REQUIRED")
        if _sha256(reconciliation.get("original_outcome_receipt_digest")) != outcome_digest:
            blockers.append("RECONCILIATION_OUTCOME_RECEIPT_BINDING_MISMATCH")
        for field in (
            "execution_attempt_id",
            "pr_number",
            "requested_mutation",
            "idempotency_key_digest",
            "effect_key_digest",
        ):
            if reconciliation.get(field) != outcome.get(field):
                blockers.append("RECONCILIATION_LINEAGE_MISMATCH:" + field)
        reconciliation_digest = _sha256(reconciliation.get("reconciliation_digest"))
        if not reconciliation_digest:
            blockers.append("RECONCILIATION_DIGEST_REQUIRED")
        reconciled = _clean(
            reconciliation.get("reconciled_outcome"), 120
        ).upper()

    lineage = {
        "authorization_receipt_digest": auth_digest,
        "authorization_persistence_digest": persistence_digest,
        "consumption_attestation_digest": consumption_digest,
        "executor_boundary_digest": boundary_digest,
        "adapter_attestation_digest": adapter_digest,
        "attempt_observation_digest": attempt_digest,
        "outcome_receipt_digest": outcome_digest,
        "reconciliation_digest": reconciliation_digest,
        "execution_attempt_id": boundary.get("execution_attempt_id"),
        "pr_number": boundary.get("pr_number"),
        "requested_mutation": boundary.get("requested_mutation"),
        "logical_operation": boundary.get("logical_operation"),
        "repository_ref_digest": _sha256(boundary.get("repository_ref_digest")),
        "main_sha": boundary.get("main_sha"),
        "main_tree_sha": boundary.get("main_tree_sha"),
        "head_branch": boundary.get("head_branch"),
        "head_sha": boundary.get("head_sha"),
        "base_branch": boundary.get("base_branch"),
        "idempotency_key_digest": _sha256(
            boundary.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(boundary.get("effect_key_digest")),
        "primary_outcome": primary,
        "reconciled_outcome": reconciled,
    }
    return lineage, list(dict.fromkeys(blockers))


def build_terminal_audit_certificate(
    authorization_receipt: Mapping[str, Any] | None,
    authorization_persistence: Mapping[str, Any] | None,
    consumption_attestation: Mapping[str, Any] | None,
    executor_boundary: Mapping[str, Any] | None,
    adapter_attestation: Mapping[str, Any] | None,
    attempt_observation: Mapping[str, Any] | None,
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation_record: Mapping[str, Any] | None = None,
    *,
    certificate_revision: Any,
    audit_chain_digest: Any,
    evidence_bundle_digest: Any,
    rollback_plan_digest: Any,
    lineage_evidence_authenticated: bool,
    lineage_evidence_complete: bool,
    unresolved_lineage_conflict_present: bool,
) -> dict[str, Any]:
    """Build deterministic read-only certificate for final or open outcome."""
    lineage, blockers = _verify_lineage(
        authorization_receipt,
        authorization_persistence,
        consumption_attestation,
        executor_boundary,
        adapter_attestation,
        attempt_observation,
        outcome_receipt,
        reconciliation_record,
    )

    try:
        revision = int(certificate_revision)
        if revision < 1:
            blockers.append("CERTIFICATE_REVISION_INVALID")
    except Exception:
        revision = 0
        blockers.append("CERTIFICATE_REVISION_INVALID")

    audit_digest = _sha256(audit_chain_digest)
    evidence_digest = _sha256(evidence_bundle_digest)
    rollback_digest = _sha256(rollback_plan_digest)
    if not audit_digest:
        blockers.append("AUDIT_CHAIN_DIGEST_REQUIRED")
    if not evidence_digest:
        blockers.append("EVIDENCE_BUNDLE_DIGEST_REQUIRED")
    if not rollback_digest:
        blockers.append("ROLLBACK_PLAN_DIGEST_REQUIRED")
    if lineage_evidence_authenticated is not True:
        blockers.append("LINEAGE_EVIDENCE_AUTHENTICATION_REQUIRED")
    if lineage_evidence_complete is not True:
        blockers.append("LINEAGE_EVIDENCE_COMPLETENESS_REQUIRED")
    if unresolved_lineage_conflict_present is True:
        blockers.append("UNRESOLVED_LINEAGE_CONFLICT")

    primary = lineage.get("primary_outcome", "")
    reconciled = lineage.get("reconciled_outcome", "")

    if primary == PRIMARY_FINAL_SUCCESS:
        certificate_outcome = "CERTIFIED_FINAL_SUCCESS"
    elif primary == PRIMARY_FINAL_FAILURE:
        certificate_outcome = "CERTIFIED_FINAL_TERMINAL_FAILURE"
    elif primary == PRIMARY_UNKNOWN:
        if reconciled == RECONCILED_SUCCESS:
            certificate_outcome = "CERTIFIED_FINAL_SUCCESS"
        elif reconciled == RECONCILED_FAILURE:
            certificate_outcome = "CERTIFIED_FINAL_TERMINAL_FAILURE"
        elif reconciled in ("", RECONCILED_UNKNOWN):
            certificate_outcome = "CERTIFIED_OPEN_AMBIGUOUS"
        else:
            blockers.append("RECONCILED_OUTCOME_INVALID")
            certificate_outcome = ""
    else:
        blockers.append("PRIMARY_OUTCOME_INVALID")
        certificate_outcome = ""

    terminal_closed = certificate_outcome in (
        "CERTIFIED_FINAL_SUCCESS",
        "CERTIFIED_FINAL_TERMINAL_FAILURE",
    )
    open_ambiguous = certificate_outcome == "CERTIFIED_OPEN_AMBIGUOUS"

    blockers = list(dict.fromkeys(blockers))
    manifest = {
        "certificate_revision": revision,
        "certificate_outcome": certificate_outcome,
        "terminal_closed": terminal_closed,
        "open_ambiguous": open_ambiguous,
        **lineage,
        "audit_chain_digest": audit_digest,
        "evidence_bundle_digest": evidence_digest,
        "rollback_plan_digest": rollback_digest,
        "lineage_evidence_authenticated": lineage_evidence_authenticated is True,
        "lineage_evidence_complete": lineage_evidence_complete is True,
        "unresolved_lineage_conflict_present": (
            unresolved_lineage_conflict_present is True
        ),
    }

    return {
        "schema": CERTIFICATE_SCHEMA,
        "state": "AUDIT_CERTIFICATE_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "manifest": manifest,
        "certificate_digest": _digest(manifest) if not blockers else "",
        "certificate_outcome": certificate_outcome,
        "terminal_closed": terminal_closed if not blockers else False,
        "open_ambiguous": open_ambiguous if not blockers else False,
        "reconciliation_required": open_ambiguous if not blockers else False,
        "certificate_is_read_only": True,
        "certificate_is_immutable": True,
        "certificate_is_append_only_evidence": True,
        "certificate_is_execution_authorization": False,
        "certificate_authorizes_retry": False,
        "certificate_authorizes_reopen": False,
        "certificate_authorizes_new_attempt": False,
        "certificate_authorizes_repository_mutation": False,
        "certificate_persisted_by_this_module": False,
        "github_queried_by_this_module": False,
        "github_api_called_by_this_module": False,
        "network_called_by_this_module": False,
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


def build_certificate_persistence_attestation(
    certificate: Mapping[str, Any] | None,
    *,
    persistence_record_digest: Any,
    writer_attestation_digest: Any,
    read_after_write_verified: bool,
    atomic_write_or_cas_verified: bool,
    writer_identity_verified: bool,
    reopen_consistency_verified: bool,
) -> dict[str, Any]:
    """Represent external persistence proof. Does not persist certificate."""
    cert = dict(certificate or {})
    blockers: list[str] = []

    if cert.get("schema") != CERTIFICATE_SCHEMA:
        blockers.append("CERTIFICATE_SCHEMA_MISMATCH")
    if cert.get("state") != "AUDIT_CERTIFICATE_READY":
        blockers.append("READY_AUDIT_CERTIFICATE_REQUIRED")
    if cert.get("certificate_is_immutable") is not True:
        blockers.append("CERTIFICATE_IMMUTABILITY_REQUIRED")
    if cert.get("certificate_is_read_only") is not True:
        blockers.append("READ_ONLY_CERTIFICATE_REQUIRED")

    cert_digest = _sha256(cert.get("certificate_digest"))
    record_digest = _sha256(persistence_record_digest)
    writer_digest = _sha256(writer_attestation_digest)
    if not cert_digest:
        blockers.append("CERTIFICATE_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("PERSISTENCE_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    for label, flag in (
        ("READ_AFTER_WRITE_REQUIRED", read_after_write_verified),
        ("ATOMIC_WRITE_OR_CAS_REQUIRED", atomic_write_or_cas_verified),
        ("WRITER_IDENTITY_REQUIRED", writer_identity_verified),
        ("REOPEN_CONSISTENCY_REQUIRED", reopen_consistency_verified),
    ):
        if flag is not True:
            blockers.append(label)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "certificate_digest": cert_digest,
        "certificate_outcome": cert.get("certificate_outcome"),
        "persistence_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "read_after_write_verified": read_after_write_verified is True,
        "atomic_write_or_cas_verified": atomic_write_or_cas_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
        "reopen_consistency_verified": reopen_consistency_verified is True,
    }

    return {
        "schema": PERSISTENCE_SCHEMA,
        "state": (
            "AUDIT_CERTIFICATE_PERSISTENCE_ATTESTED"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "persistence_attestation_digest": _digest(material) if not blockers else "",
        "persisted_by_this_module": False,
        "certificate_authorizes_retry": False,
        "certificate_authorizes_repository_mutation": False,
        "github_api_called_by_this_module": False,
        "network_called_by_this_module": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def verify_terminal_audit_certificate(
    certificate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(certificate or {})
    blockers: list[str] = []

    if raw.get("schema") != CERTIFICATE_SCHEMA:
        blockers.append("CERTIFICATE_SCHEMA_MISMATCH")
    if raw.get("state") != "AUDIT_CERTIFICATE_READY":
        blockers.append("READY_AUDIT_CERTIFICATE_REQUIRED")
    if raw.get("certificate_is_read_only") is not True:
        blockers.append("READ_ONLY_CERTIFICATE_REQUIRED")
    if raw.get("certificate_is_immutable") is not True:
        blockers.append("IMMUTABLE_CERTIFICATE_REQUIRED")
    if raw.get("certificate_is_execution_authorization") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_EXECUTION")
    if raw.get("certificate_authorizes_retry") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_RETRY")
    if raw.get("certificate_authorizes_new_attempt") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_NEW_ATTEMPT")
    if raw.get("certificate_authorizes_repository_mutation") is not False:
        blockers.append("CERTIFICATE_MUST_NOT_AUTHORIZE_REPOSITORY_MUTATION")

    manifest = raw.get("manifest")
    if not isinstance(manifest, Mapping):
        blockers.append("CERTIFICATE_MANIFEST_REQUIRED")
        manifest = {}
    supplied = _sha256(raw.get("certificate_digest"))
    expected = _digest(dict(manifest))
    if not supplied or supplied != expected:
        blockers.append("CERTIFICATE_DIGEST_MISMATCH")

    outcome = _clean(raw.get("certificate_outcome"), 120).upper()
    if outcome not in CERTIFICATE_OUTCOMES:
        blockers.append("CERTIFICATE_OUTCOME_INVALID")
    if manifest.get("certificate_outcome") != outcome:
        blockers.append("CERTIFICATE_OUTCOME_MANIFEST_MISMATCH")

    if outcome == "CERTIFIED_OPEN_AMBIGUOUS":
        if raw.get("terminal_closed") is not False:
            blockers.append("OPEN_AMBIGUOUS_MUST_NOT_BE_TERMINAL_CLOSED")
        if raw.get("open_ambiguous") is not True:
            blockers.append("OPEN_AMBIGUOUS_FLAG_REQUIRED")
        if raw.get("reconciliation_required") is not True:
            blockers.append("OPEN_AMBIGUOUS_RECONCILIATION_REQUIRED")
    else:
        if raw.get("terminal_closed") is not True:
            blockers.append("FINAL_CERTIFICATE_TERMINAL_CLOSURE_REQUIRED")
        if raw.get("open_ambiguous") is not False:
            blockers.append("FINAL_CERTIFICATE_MUST_NOT_BE_OPEN_AMBIGUOUS")

    for key in (
        "certificate_persisted_by_this_module",
        "github_queried_by_this_module",
        "github_api_called_by_this_module",
        "network_called_by_this_module",
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
            blockers.append("CERTIFICATE_UNSAFE_FIELD:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_AUDIT_CERTIFICATE" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "certificate_outcome": outcome,
        "certificate_digest": supplied,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def terminal_audit_certificate_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "certificate_outcomes": list(CERTIFICATE_OUTCOMES),
        "full_lineage_required": True,
        "authorization_receipt_required": True,
        "authorization_persistence_required": True,
        "authorization_consumption_required": True,
        "executor_boundary_required": True,
        "signed_adapter_attestation_required": True,
        "attempt_observation_required": True,
        "immutable_outcome_receipt_required": True,
        "reconciliation_required_only_for_unknown_resolution": True,
        "primary_final_outcome_forbids_reconciliation_record": True,
        "unknown_without_resolution_certifies_open_ambiguous": True,
        "still_unknown_certifies_open_ambiguous": True,
        "reconciled_success_certifies_final_success": True,
        "reconciled_failure_certifies_final_terminal_failure": True,
        "original_outcome_receipt_remains_immutable": True,
        "certificate_is_read_only": True,
        "certificate_is_immutable": True,
        "certificate_is_append_only_evidence": True,
        "certificate_is_execution_authorization": False,
        "certificate_authorizes_retry": False,
        "certificate_authorizes_reopen": False,
        "certificate_authorizes_new_attempt": False,
        "certificate_authorizes_repository_mutation": False,
        "open_ambiguous_reconciliation_required": True,
        "automatic_retry_allowed": False,
        "repository_mutation_replayed": False,
        "github_query_performed_by_this_module": False,
        "github_api_called_by_this_module": False,
        "network_called_by_this_module": False,
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
    "CERTIFICATE_SCHEMA",
    "PERSISTENCE_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "CERTIFICATE_OUTCOMES",
    "build_terminal_audit_certificate",
    "build_certificate_persistence_attestation",
    "verify_terminal_audit_certificate",
    "terminal_audit_certificate_policy",
]
