"""AION Windows terminal receipt persistence and post-reboot health V1.

PURE design-only candidate contracts. No persistent writes, local device access,
Windows APIs, process launch, reboot, physical readback, deployment, or install.
All positive classifications are SHAPE ONLY, never trusted physical evidence.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping

from atlasquant_aion_windows_install_completion_postinstall_rollback_receipt_v1 import (
    TERMINAL_RECEIPT_SCHEMA, TERMINAL_READY,
    SUCCESS_CANDIDATE, FAILURE_CANDIDATE, ROLLBACK_CANDIDATE,
)

SCHEMA = "ATLASQUANT_AION_WINDOWS_TERMINAL_PERSISTENCE_POSTREBOOT_HEALTH_V1"
INTENT_SCHEMA = "ATLASQUANT_AION_WINDOWS_TERMINAL_RECEIPT_WRITE_INTENT_V1"
ATTEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_TERMINAL_PERSISTENCE_ATTESTATION_SHAPE_V1"
REBOOT_SCHEMA = "ATLASQUANT_AION_WINDOWS_POSTREBOOT_VERIFICATION_PLAN_V1"
OBS_SCHEMA = "ATLASQUANT_AION_WINDOWS_POSTREBOOT_HEALTH_OBSERVATION_V1"
REVIEW_SCHEMA = "ATLASQUANT_AION_WINDOWS_TERMINAL_PERSISTENCE_POSTREBOOT_REVIEW_V1"

INTENT_READY = "TERMINAL_RECEIPT_WRITE_INTENT_READY"
ATTEST_READY = "TERMINAL_PERSISTENCE_ATTESTATION_SHAPE_READY_UNTRUSTED"
REBOOT_READY = "POSTREBOOT_VERIFICATION_PLAN_READY_UNTRUSTED"
OBS_READY = "POSTREBOOT_HEALTH_OBSERVATION_SHAPE_CLASSIFIED_UNTRUSTED"
REVIEW_READY = "READY_FOR_TERMINAL_PERSISTENCE_AND_POSTREBOOT_CONSUMER_IMPLEMENTATION"
BLOCKED = "BLOCKED"
HEALTHY = "POSTREBOOT_HEALTHY_CANDIDATE_UNTRUSTED"
UNHEALTHY = "POSTREBOOT_UNHEALTHY_CANDIDATE_UNTRUSTED"
UNKNOWN = "POSTREBOOT_HEALTH_OUTCOME_UNKNOWN"
TERMINAL_OUTCOMES = (SUCCESS_CANDIDATE, FAILURE_CANDIDATE, ROLLBACK_CANDIDATE)
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{2,179}$")

TERMINAL_FIELDS = (
    "installation_id", "requested_disposition", "candidate_disposition",
    "completion_gate_digest", "journal_plan_digest",
    "postinstall_evidence_digest", "rollback_receipt_digest",
    "failure_evidence_digest", "terminal_reopen_receipt_digest",
    "independent_final_attestor_digest",
)
INTENT_FIELDS = (
    "installation_id", "terminal_candidate_digest", "terminal_outcome",
    "journal_plan_digest", "owner_sid_digest", "host_identity_digest",
    "package_manifest_digest", "target_snapshot_digest",
    "terminal_writer_manifest_digest", "durable_store_identity_digest",
    "terminal_policy_digest", "record_key_digest",
    "expected_terminal_state", "expected_revision",
    "committed_terminal_state_if_written", "next_revision_if_written",
    "write_nonce_digest",
)
ATTEST_FIELDS = (
    "installation_id", "write_intent_digest", "terminal_candidate_digest",
    "record_key_digest", "terminal_outcome", "durable_store_identity_digest",
    "observed_record_digest", "cas_write_receipt_digest",
    "cas_observation_digest", "read_after_write_digest",
    "independent_reopen_digest", "independent_verifier_manifest_digest",
    "observed_installation_id", "observed_record_key_digest",
    "observed_terminal_candidate_digest", "observed_terminal_state",
    "observed_revision", "observed_prior_state", "observed_prior_revision",
    "observed_owner_sid_digest", "observed_host_identity_digest",
    "observed_terminal_outcome", "write_attempt_nonce_digest",
)
REBOOT_CHECKS = (
    "TERMINAL_RECEIPT_FRESH_REOPEN",
    "INSTALL_COMMITMENT_AND_JOURNAL_REOPEN",
    "HOST_AND_OWNER_SID_MATCH",
    "BOOT_EPOCH_PROVES_REBOOT",
    "PACKAGE_AND_TARGET_FILES_READBACK",
    "OWNER_EFFECTIVE_ACL_REOPEN",
    "STARTUP_ENTRY_TARGET_READBACK",
    "AION_PROCESS_BINARY_AND_VERSION_MATCH",
    "AION_RUNTIME_HANDSHAKE_HEALTH",
    "NO_UNEXPECTED_MUTATION",
    "FRESH_CHALLENGE_ATTESTATION",
)
REBOOT_FIELDS = (
    "installation_id", "terminal_candidate_digest", "write_intent_digest",
    "persistence_attestation_digest", "journal_plan_digest",
    "owner_sid_digest", "host_identity_digest",
    "package_manifest_digest", "target_snapshot_digest",
    "owner_acl_policy_digest", "startup_policy_digest",
    "runtime_identity_policy_digest", "runtime_health_policy_digest",
    "preboot_epoch_digest", "reboot_challenge_digest",
    "reboot_verifier_manifest_digest", "reboot_policy_digest", "checks",
)

def _digest(v: Any) -> str:
    return "sha256:" + sha256(json.dumps(
        v, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()

def _sha(v: Any) -> str:
    return v if type(v) is str and SHA_RE.fullmatch(v) else ""

def _id(v: Any) -> str:
    return v if type(v) is str and ID_RE.fullmatch(v) else ""

def _row(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}

def _rows(v: Any) -> list[dict[str, Any]]:
    if not isinstance(v, (list, tuple)):
        return []
    return [_row(x) for x in v]

def _unique_errors(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))

def _candidate_errors(t: dict[str, Any]) -> list[str]:
    errors = []
    if t.get("schema") != TERMINAL_RECEIPT_SCHEMA or t.get("state") != TERMINAL_READY:
        errors.append("TERMINAL_SHAPE_CANDIDATE_REQUIRED")
    if not _id(t.get("installation_id")):
        errors.append("INSTALLATION_ID_INVALID")
    if (t.get("terminal_outcome") not in TERMINAL_OUTCOMES
        or t.get("terminal_outcome") != t.get("candidate_disposition")):
        errors.append("TERMINAL_OUTCOME_NOT_CANDIDATE")
    if not _sha(t.get("journal_plan_digest")):
        errors.append("TERMINAL_JOURNAL_BINDING_REQUIRED")
    if (_sha(t.get("terminal_receipt_candidate_digest")) !=
        _digest({key: t.get(key) for key in TERMINAL_FIELDS})):
        errors.append("TERMINAL_CANDIDATE_DIGEST_MISMATCH")
    for flag in ("physically_installed_trusted", "aion_healthy_trusted",
                 "terminal_disposition_persisted", "new_installation_authorized"):
        if t.get(flag) is not False:
            errors.append("TRUST_ESCALATION_FORBIDDEN:" + flag)
    return errors

def build_terminal_receipt_write_intent(
    terminal_candidate: Mapping[str, Any] | None,
    *,
    owner_sid_digest: Any, host_identity_digest: Any,
    package_manifest_digest: Any, target_snapshot_digest: Any,
    terminal_writer_manifest_digest: Any, durable_store_identity_digest: Any,
    terminal_policy_digest: Any, write_nonce_digest: Any,
    expected_terminal_state: Any, expected_revision: Any,
) -> dict[str, Any]:
    """Design CAS from NONE; no write, no authorization, no real evidence."""
    t = _row(terminal_candidate)
    errors = _candidate_errors(t)
    digests = {name: _sha(value) for name, value in (
        ("owner_sid_digest", owner_sid_digest),
        ("host_identity_digest", host_identity_digest),
        ("package_manifest_digest", package_manifest_digest),
        ("target_snapshot_digest", target_snapshot_digest),
        ("terminal_writer_manifest_digest", terminal_writer_manifest_digest),
        ("durable_store_identity_digest", durable_store_identity_digest),
        ("terminal_policy_digest", terminal_policy_digest),
        ("write_nonce_digest", write_nonce_digest),
    )}
    for name, value in digests.items():
        if not value:
            errors.append(name.upper() + "_REQUIRED")
    if expected_terminal_state != "NONE":
        errors.append("EXPECTED_TERMINAL_STATE_MUST_BE_NONE")
    if type(expected_revision) is not int or expected_revision < 0:
        errors.append("EXPECTED_REVISION_MUST_BE_NONNEGATIVE_INTEGER")
    record_key = _digest({
        "installation_id": t.get("installation_id"),
        "record_kind": "WINDOWS_SINGLE_TERMINAL_INSTALL_RECEIPT",
        "durable_store_identity_digest": digests["durable_store_identity_digest"],
    })
    material = {
        "installation_id": t.get("installation_id"),
        "terminal_candidate_digest": _sha(t.get("terminal_receipt_candidate_digest")),
        "terminal_outcome": t.get("terminal_outcome"),
        "journal_plan_digest": _sha(t.get("journal_plan_digest")),
        **digests,
        "record_key_digest": record_key,
        "expected_terminal_state": "NONE",
        "expected_revision": expected_revision,
        "committed_terminal_state_if_written": t.get("terminal_outcome"),
        "next_revision_if_written": expected_revision + 1 if type(expected_revision) is int and expected_revision >= 0 else -1,
    }
    errors = _unique_errors(errors)
    return {
        "schema": INTENT_SCHEMA, "state": INTENT_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "write_intent_digest": _digest(material) if not errors else "",
        "cas_single_assignment_required": True,
        "first_write_must_be_atomic": True,
        "idempotent_reopen_same_record_is_read_only": True,
        "conflicting_terminal_write_rejected": True,
        "durable_write_executed": False,
        "terminal_receipt_persisted": False,
        "terminal_state_trusted": False,
    }

def validate_terminal_persistence_attestation_shape(
    write_intent: Mapping[str, Any] | None,
    **evidence: Any,
) -> dict[str, Any]:
    """Receipt envelope only, not a CAS verification or persistence certificate."""
    intent = _row(write_intent)
    errors = []
    if intent.get("schema") != INTENT_SCHEMA or intent.get("state") != INTENT_READY:
        errors.append("READY_TERMINAL_WRITE_INTENT_REQUIRED")
    if (_sha(intent.get("write_intent_digest")) !=
        _digest({key: intent.get(key) for key in INTENT_FIELDS})):
        errors.append("WRITE_INTENT_DIGEST_MISMATCH")
    required = (
        "observed_record_digest", "cas_write_receipt_digest", "cas_observation_digest",
        "read_after_write_digest", "independent_reopen_digest",
        "independent_verifier_manifest_digest",
    )
    v = {name: _sha(evidence.get(name)) for name in required}
    for name, digest in v.items():
        if not digest:
            errors.append(name.upper() + "_REQUIRED")
    if evidence.get("observed_prior_state") != "NONE":
        errors.append("CAS_PRIOR_MUST_BE_NONE")
    if type(evidence.get("observed_prior_revision")) is not int or evidence.get("observed_prior_revision") != intent.get("expected_revision"):
        errors.append("CAS_PRIOR_REVISION_MISMATCH")
    if evidence.get("observed_terminal_state") != intent.get("committed_terminal_state_if_written"):
        errors.append("CAS_TERMINAL_STATE_MISMATCH")
    if type(evidence.get("observed_revision")) is not int or evidence.get("observed_revision") != intent.get("next_revision_if_written"):
        errors.append("CAS_NEXT_REVISION_MISMATCH")
    bindings = (
        ("observed_installation_id", "installation_id"),
        ("observed_record_key_digest", "record_key_digest"),
        ("observed_terminal_candidate_digest", "terminal_candidate_digest"),
        ("observed_owner_sid_digest", "owner_sid_digest"),
        ("observed_host_identity_digest", "host_identity_digest"),
        ("observed_terminal_outcome", "terminal_outcome"),
        ("write_attempt_nonce_digest", "write_nonce_digest"),
    )
    for observed, expected in bindings:
        if evidence.get(observed) != intent.get(expected):
            errors.append("PERSISTENCE_BINDING_MISMATCH:" + observed)
    if evidence.get("caller_claims_trusted") is True:
        errors.append("SELF_ATTESTED_TRUST_FORBIDDEN")
    material = {
        "installation_id": intent.get("installation_id"),
        "write_intent_digest": _sha(intent.get("write_intent_digest")),
        "terminal_candidate_digest": _sha(intent.get("terminal_candidate_digest")),
        "record_key_digest": _sha(intent.get("record_key_digest")),
        "terminal_outcome": intent.get("terminal_outcome"),
        "durable_store_identity_digest": _sha(intent.get("durable_store_identity_digest")),
        **v,
        "observed_installation_id": evidence.get("observed_installation_id"),
        "observed_record_key_digest": evidence.get("observed_record_key_digest"),
        "observed_terminal_candidate_digest": evidence.get("observed_terminal_candidate_digest"),
        "observed_terminal_state": evidence.get("observed_terminal_state"),
        "observed_revision": evidence.get("observed_revision"),
        "observed_prior_state": evidence.get("observed_prior_state"),
        "observed_prior_revision": evidence.get("observed_prior_revision"),
        "observed_owner_sid_digest": evidence.get("observed_owner_sid_digest"),
        "observed_host_identity_digest": evidence.get("observed_host_identity_digest"),
        "observed_terminal_outcome": evidence.get("observed_terminal_outcome"),
        "write_attempt_nonce_digest": evidence.get("write_attempt_nonce_digest"),
    }
    errors = _unique_errors(errors)
    return {
        "schema": ATTEST_SCHEMA,
        "state": ATTEST_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "attestation_candidate_digest": _digest(material) if not errors else "",
        "claim_shape_valid": not errors,
        "cas_durably_verified": False,
        "read_after_write_physically_verified": False,
        "reopen_physically_verified": False,
        "terminal_receipt_persisted_trusted": False,
        "terminal_state_trusted": False,
    }

def build_postreboot_verification_plan(
    terminal_candidate: Mapping[str, Any] | None,
    write_intent: Mapping[str, Any] | None,
    persistence_attestation: Mapping[str, Any] | None,
    *,
    owner_acl_policy_digest: Any, startup_policy_digest: Any,
    runtime_identity_policy_digest: Any, runtime_health_policy_digest: Any,
    preboot_epoch_digest: Any, reboot_challenge_digest: Any,
    reboot_verifier_manifest_digest: Any, reboot_policy_digest: Any,
) -> dict[str, Any]:
    """A reboot must actually occur; this defines future checks, not proof."""
    t, i, a = _row(terminal_candidate), _row(write_intent), _row(persistence_attestation)
    errors = _candidate_errors(t)
    if t.get("terminal_outcome") != SUCCESS_CANDIDATE:
        errors.append("HEALTH_RECHECK_REQUIRES_SUCCESS_CANDIDATE")
    if i.get("schema") != INTENT_SCHEMA or i.get("state") != INTENT_READY:
        errors.append("WRITE_INTENT_REQUIRED")
    if a.get("schema") != ATTEST_SCHEMA or a.get("state") != ATTEST_READY:
        errors.append("ATTESTATION_SHAPE_REQUIRED")
    if (i.get("terminal_candidate_digest") != t.get("terminal_receipt_candidate_digest")
        or i.get("installation_id") != t.get("installation_id")
        or a.get("write_intent_digest") != i.get("write_intent_digest")
        or a.get("terminal_candidate_digest") != t.get("terminal_receipt_candidate_digest")
        or a.get("installation_id") != t.get("installation_id")):
        errors.append("CROSS_RECEIPT_BINDING_MISMATCH")
    d = {name: _sha(value) for name, value in (
        ("owner_acl_policy_digest", owner_acl_policy_digest),
        ("startup_policy_digest", startup_policy_digest),
        ("runtime_identity_policy_digest", runtime_identity_policy_digest),
        ("runtime_health_policy_digest", runtime_health_policy_digest),
        ("preboot_epoch_digest", preboot_epoch_digest),
        ("reboot_challenge_digest", reboot_challenge_digest),
        ("reboot_verifier_manifest_digest", reboot_verifier_manifest_digest),
        ("reboot_policy_digest", reboot_policy_digest),
    )}
    for k, v in d.items():
        if not v:
            errors.append(k.upper() + "_REQUIRED")
    if d["preboot_epoch_digest"] and d["preboot_epoch_digest"] == d["reboot_challenge_digest"]:
        errors.append("EPOCH_AND_CHALLENGE_MUST_DIFFER")
    checks = [{"check_id": x, "expected_proof_binding_digest": _digest({
        "check_id": x, "installation_id": t.get("installation_id"),
        "terminal_candidate_digest": t.get("terminal_receipt_candidate_digest"),
        "reboot_challenge_digest": d["reboot_challenge_digest"],
        "reboot_policy_digest": d["reboot_policy_digest"],
    })} for x in REBOOT_CHECKS]
    material = {
        "installation_id": t.get("installation_id"),
        "terminal_candidate_digest": _sha(t.get("terminal_receipt_candidate_digest")),
        "write_intent_digest": _sha(i.get("write_intent_digest")),
        "persistence_attestation_digest": _sha(a.get("attestation_candidate_digest")),
        "journal_plan_digest": _sha(t.get("journal_plan_digest")),
        "owner_sid_digest": _sha(i.get("owner_sid_digest")),
        "host_identity_digest": _sha(i.get("host_identity_digest")),
        "package_manifest_digest": _sha(i.get("package_manifest_digest")),
        "target_snapshot_digest": _sha(i.get("target_snapshot_digest")),
        **d, "checks": checks,
    }
    errors = _unique_errors(errors)
    return {
        "schema": REBOOT_SCHEMA, "state": REBOOT_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "reboot_plan_digest": _digest(material) if not errors else "",
        "actual_reboot_observed": False,
        "reboot_health_verification_performed": False,
        "terminal_persistence_trusted": False,
        "postreboot_health_trusted": False,
    }

def classify_postreboot_health_evidence(
    plan: Mapping[str, Any] | None,
    observations: Iterable[Mapping[str, Any]] | None,
    *,
    observed_postboot_epoch_digest: Any,
    observed_challenge_digest: Any,
    independent_reboot_attestor_digest: Any,
    requested_result: Any,
) -> dict[str, Any]:
    """Strict fail-closed shape classification; no actual Windows measurements."""
    p = _row(plan)
    rows = _rows(observations)
    errors: list[str] = []
    if p.get("schema") != REBOOT_SCHEMA or p.get("state") != REBOOT_READY:
        errors.append("READY_POSTREBOOT_PLAN_REQUIRED")
    if (_sha(p.get("reboot_plan_digest")) !=
        _digest({key: p.get(key) for key in REBOOT_FIELDS})):
        errors.append("REBOOT_PLAN_DIGEST_MISMATCH")
    epoch, challenge, attestor = (
        _sha(observed_postboot_epoch_digest), _sha(observed_challenge_digest),
        _sha(independent_reboot_attestor_digest),
    )
    if not epoch or epoch == p.get("preboot_epoch_digest"):
        errors.append("FRESH_POSTBOOT_EPOCH_CHANGE_REQUIRED")
    if not challenge or challenge != p.get("reboot_challenge_digest"):
        errors.append("FRESH_REBOOT_CHALLENGE_MISMATCH")
    if not attestor:
        errors.append("INDEPENDENT_ATTESTOR_DIGEST_REQUIRED")
    checks = _rows(p.get("checks"))
    ids = [c.get("check_id") for c in checks]
    if ids != list(REBOOT_CHECKS):
        errors.append("MANDATORY_REBOOT_SCOPE_INVALID")
    if len(rows) != len(checks) or [r.get("check_id") for r in rows] != ids:
        errors.append("COMPLETE_ORDERED_REBOOT_EVIDENCE_REQUIRED")
    failed_checks: list[str] = []
    for idx, check in enumerate(checks):
        if idx >= len(rows):
            break
        row = rows[idx]
        if (row.get("proof_binding_digest") != check.get("expected_proof_binding_digest")
            or row.get("observed_postboot_epoch_digest") != epoch
            or row.get("observed_challenge_digest") != challenge
            or row.get("reopened_after_reboot") is not True
            or row.get("independent_verifier_observed") is not True
            or row.get("ambiguity_detected") is not False
            or not _sha(row.get("independent_readback_receipt_digest"))):
            errors.append("REBOOT_CHECK_EVIDENCE_INVALID:" + str(check.get("check_id")))
        status = row.get("result")
        if status == "VERIFIED_NEGATIVE":
            if not _sha(row.get("authoritative_negative_evidence_digest")):
                errors.append("NEGATIVE_OUTCOME_WITHOUT_PROOF:" + str(check.get("check_id")))
            failed_checks.append(str(check.get("check_id")))
        elif status != "VERIFIED_POSITIVE":
            errors.append("REBOOT_CHECK_UNKNOWN:" + str(check.get("check_id")))
    errors = _unique_errors(errors)
    if requested_result not in ("HEALTHY", "UNHEALTHY"):
        errors.append("INVALID_REBOOT_OUTCOME_REQUEST")
    if errors:
        disposition = UNKNOWN
    elif failed_checks:
        disposition = UNHEALTHY if requested_result == "UNHEALTHY" else UNKNOWN
    else:
        disposition = HEALTHY if requested_result == "HEALTHY" else UNKNOWN
    material = {
        "installation_id": p.get("installation_id"),
        "reboot_plan_digest": _sha(p.get("reboot_plan_digest")),
        "observed_postboot_epoch_digest": epoch,
        "observed_challenge_digest": challenge,
        "independent_reboot_attestor_digest": attestor,
        "observation_digests": [_digest(r) for r in rows],
        "negative_checks": failed_checks,
        "requested_result": requested_result,
        "classified_disposition": disposition,
    }
    return {
        "schema": OBS_SCHEMA, "state": OBS_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "observation_candidate_digest": _digest(material) if not errors else "",
        "postreboot_disposition": disposition,
        "reboot_health_verified_trusted": False,
        "terminal_persistence_trusted": False,
        "installation_healthy_trusted": False,
        "automatic_reinstall_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_continue_allowed": False,
        "reconciliation_required": disposition != HEALTHY,
    }

def build_consumer_implementation_review(
    write_intent: Mapping[str, Any] | None,
    reboot_plan: Mapping[str, Any] | None,
    *,
    durable_writer_source_digest: Any,
    independent_reopen_verifier_source_digest: Any,
    postreboot_health_consumer_source_digest: Any,
) -> dict[str, Any]:
    i, p = _row(write_intent), _row(reboot_plan)
    errors = []
    if i.get("state") != INTENT_READY or p.get("state") != REBOOT_READY:
        errors.append("READY_INTENT_AND_REBOOT_PLAN_REQUIRED")
    if p.get("write_intent_digest") != i.get("write_intent_digest"):
        errors.append("PLAN_INTENT_MISMATCH")
    digests = {k: _sha(v) for k, v in (
        ("durable_writer_source_digest", durable_writer_source_digest),
        ("independent_reopen_verifier_source_digest", independent_reopen_verifier_source_digest),
        ("postreboot_health_consumer_source_digest", postreboot_health_consumer_source_digest),
    )}
    for k, v in digests.items():
        if not v:
            errors.append(k.upper() + "_REQUIRED")
    material = {
        "write_intent_digest": _sha(i.get("write_intent_digest")),
        "reboot_plan_digest": _sha(p.get("reboot_plan_digest")),
        **digests,
        "next_pc_phase": "SYNTHETIC_CAS_STORE_AND_INDEPENDENT_WINDOWS_BOOT_EPOCH_VERIFIER",
    }
    errors = _unique_errors(errors)
    return {
        "schema": REVIEW_SCHEMA, "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors, **material,
        "implementation_review_digest": _digest(material) if not errors else "",
        **{k: False for k in (
            "durable_writer_implemented", "postreboot_consumer_implemented",
            "terminal_receipt_persisted", "terminal_cas_executed",
            "read_after_write_executed", "reopened_terminal_record",
            "reboot_executed", "postreboot_health_check_executed",
            "postreboot_health_trusted", "owner_authorization_consumed",
            "install_token_consumed", "journal_persisted",
            "installation_started", "files_copied", "filesystem_modified",
            "windows_acl_modified", "startup_entry_created",
            "rollback_performed", "package_installed", "process_spawned",
            "network_called", "github_api_called", "deploy_executed",
            "worker_activated", "production_persistence_activated",
        )},
    }

def terminal_reboot_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "design_only": True,
        "terminal_candidate_is_durable_receipt": False,
        "receipt_write_claim_is_persistence_proof": False,
        "durable_receipt_means_healthy_after_reboot": False,
        "single_terminal_record_per_install_required": True,
        "cas_prior_none_required": True,
        "cas_next_revision_exact_required": True,
        "read_after_write_and_fresh_reopen_required": True,
        "independent_reboot_attestor_required": True,
        "boot_epoch_change_required": True,
        "fresh_reboot_challenge_required": True,
        "all_postreboot_checks_required": True,
        "replay_and_cross_install_receipts_allowed": False,
        "unknown_is_healthy": False,
        "unhealthy_means_clean_terminal_failure": False,
        "automatic_retry_after_unknown_allowed": False,
        "automatic_reinstall_on_unhealthy_allowed": False,
        "terminal_receipt_persisted": False,
        "reboot_executed": False,
        "postreboot_health_trusted": False,
        "package_installed": False,
        "deploy_executed": False,
        "worker_activated": False,
    }

__all__ = [x for x in globals() if x.isupper() or x.startswith((
    "build_", "validate_", "classify_", "terminal_reboot_",
))]
