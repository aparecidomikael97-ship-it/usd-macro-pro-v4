"""AION Windows Installation Completion + Postinstall Verification + Rollback Receipt V1.

Pure, design-only contracts. No installation, disk/registry/ACL/startup mutations,
persistence, launch, network traffic, or privileged trust decision.

A complete transaction journal is never by itself proof of an installed, healthy AION.
All "ready" and "candidate" classifications are shape-only and UNTRUSTED.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping

from atlasquant_aion_windows_atomic_install_start_file_transaction_journal_v1 import (
    JOURNAL_PLAN_SCHEMA, JOURNAL_ENTRY_SCHEMA, OP_OBSERVATION_SCHEMA, RECOVERY_SCHEMA,
    READY_JOURNAL_PLAN_STATE, READY_JOURNAL_ENTRY_STATE,
    CLASSIFIED_OPERATION_STATE, READY_RECOVERY_STATE, OP_APPLIED,
)

SCHEMA = "ATLASQUANT_AION_WINDOWS_INSTALL_COMPLETION_POSTINSTALL_ROLLBACK_RECEIPT_V1"
GATE_SCHEMA = "ATLASQUANT_AION_WINDOWS_INSTALL_COMPLETION_JOURNAL_GATE_V1"
VERIFY_PLAN_SCHEMA = "ATLASQUANT_AION_WINDOWS_POSTINSTALL_VERIFICATION_PLAN_V1"
VERIFY_EVIDENCE_SCHEMA = "ATLASQUANT_AION_WINDOWS_POSTINSTALL_EVIDENCE_SHAPE_V1"
ROLLBACK_RECEIPT_SCHEMA = "ATLASQUANT_AION_WINDOWS_ROLLBACK_TERMINAL_RECEIPT_CANDIDATE_V1"
TERMINAL_RECEIPT_SCHEMA = "ATLASQUANT_AION_WINDOWS_INSTALL_TERMINAL_RECEIPT_CANDIDATE_V1"
REVIEW_SCHEMA = "ATLASQUANT_AION_WINDOWS_INSTALL_COMPLETION_IMPLEMENTATION_REVIEW_V1"

GATE_READY = "JOURNAL_COMPLETION_SHAPE_READY_UNTRUSTED"
PLAN_READY = "POSTINSTALL_VERIFICATION_PLAN_READY_UNTRUSTED"
VERIFY_READY = "POSTINSTALL_EVIDENCE_SHAPE_READY_UNTRUSTED"
ROLLBACK_READY = "ROLLBACK_TERMINAL_RECEIPT_SHAPE_READY_UNTRUSTED"
TERMINAL_READY = "INSTALL_TERMINAL_RECEIPT_SHAPE_READY_UNTRUSTED"
REVIEW_READY = "READY_FOR_WINDOWS_INSTALL_COMPLETION_CONSUMER_IMPLEMENTATION"
BLOCKED = "BLOCKED"
UNKNOWN = "INSTALL_OUTCOME_UNKNOWN"
ROLLBACK_UNKNOWN = "ROLLBACK_OUTCOME_UNKNOWN"
SUCCESS_CANDIDATE = "INSTALL_SUCCESS_CANDIDATE_UNTRUSTED"
FAILURE_CANDIDATE = "INSTALL_TERMINAL_FAILURE_CANDIDATE_UNTRUSTED"
ROLLBACK_CANDIDATE = "INSTALL_ROLLBACK_TERMINAL_CANDIDATE_UNTRUSTED"

SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GLOBAL_CHECKS = (
    "INSTALL_COMMITMENT_CAS_REOPEN",
    "JOURNAL_CHAIN_REOPEN",
    "PACKAGE_MANIFEST_REOPEN",
    "TARGET_FILES_REOPEN",
    "OWNER_ACL_REOPEN",
    "STARTUP_ENTRY_REOPEN",
    "AION_RUNTIME_HEALTH_REOPEN",
)
ENTRY_FIELDS = (
    "journal_plan_digest", "installation_id", "sequence", "operation_id",
    "operation_kind", "target_digest", "before_state_digest",
    "intended_after_state_digest", "rollback_action_digest", "source_artifact_digest",
    "previous_entry_digest", "expected_previous_entry_digest",
)
OBS_FIELDS = (
    "journal_entry_digest", "installation_id", "sequence", "operation_id",
    "requested_outcome", "final_outcome", "operation_attempted",
    "before_state_observation_digest", "mutation_write_observation_digest",
    "after_state_observation_digest", "rollback_material_presence_digest",
    "terminal_failure_evidence_digest", "ambiguity_evidence_digest",
)

def _digest(obj: Any) -> str:
    return "sha256:" + sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()

def _sha(value: Any) -> str:
    return value if type(value) is str and SHA_RE.fullmatch(value) else ""

def _map(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_map(v) for v in value]

def _dedup(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))

def build_completion_journal_gate(
    journal_plan: Mapping[str, Any] | None,
    entries: Iterable[Mapping[str, Any]] | None,
    observations: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Verify complete ordered chain and classified observations; NEVER attest actual writes."""
    p = _map(journal_plan)
    es = _rows(entries)
    os = _rows(observations)
    errors: list[str] = []
    ops = _rows(p.get("operations"))
    count = p.get("operation_count")
    if p.get("schema") != JOURNAL_PLAN_SCHEMA or p.get("state") != READY_JOURNAL_PLAN_STATE:
        errors.append("READY_UPSTREAM_JOURNAL_PLAN_REQUIRED")
    if type(count) is not int or not 1 <= count <= 256 or count != len(ops):
        errors.append("JOURNAL_COUNT_INVALID")
    if not _sha(p.get("journal_plan_digest")) or not _sha(p.get("journal_genesis_digest")):
        errors.append("JOURNAL_PLAN_DIGESTS_REQUIRED")
    plan_material = {key: p.get(key) for key in (
        "atomic_install_contract_digest", "install_commitment_digest",
        "installation_id", "journal_genesis_digest", "operation_count", "operations",
    )}
    if _sha(p.get("journal_plan_digest")) != _digest(plan_material):
        errors.append("JOURNAL_PLAN_DIGEST_MISMATCH")
    if len(es) != len(ops) or len(os) != len(ops):
        errors.append("EVERY_OPERATION_AND_OBSERVATION_REQUIRED")
    previous = p.get("journal_genesis_digest")
    for i, op in enumerate(ops):
        seq = i + 1
        if type(op.get("sequence")) is not int or op["sequence"] != seq:
            errors.append(f"PLAN_SEQUENCE_MISMATCH:{seq}")
        if i >= len(es) or i >= len(os):
            continue
        e, obs = es[i], os[i]
        if e.get("schema") != JOURNAL_ENTRY_SCHEMA or e.get("state") != READY_JOURNAL_ENTRY_STATE:
            errors.append(f"JOURNAL_ENTRY_NOT_READY:{seq}")
        if type(e.get("sequence")) is not int or e["sequence"] != seq:
            errors.append(f"JOURNAL_ENTRY_SEQUENCE_MISMATCH:{seq}")
        if e.get("installation_id") != p.get("installation_id"):
            errors.append(f"INSTALLATION_ID_MISMATCH:{seq}")
        if e.get("journal_plan_digest") != p.get("journal_plan_digest"):
            errors.append(f"ENTRY_PLAN_DIGEST_MISMATCH:{seq}")
        for key in ("operation_id", "operation_kind", "target_digest",
                    "before_state_digest", "intended_after_state_digest",
                    "rollback_action_digest", "source_artifact_digest"):
            if e.get(key) != op.get(key):
                errors.append(f"ENTRY_OPERATION_MISMATCH:{seq}:{key}")
        if not _sha(previous) or e.get("previous_entry_digest") != previous or e.get("expected_previous_entry_digest") != previous:
            errors.append(f"JOURNAL_PREDECESSOR_MISMATCH:{seq}")
        if _sha(e.get("journal_entry_digest")) != _digest({k: e.get(k) for k in ENTRY_FIELDS}):
            errors.append(f"JOURNAL_ENTRY_DIGEST_MISMATCH:{seq}")
        previous = e.get("journal_entry_digest")
        if obs.get("schema") != OP_OBSERVATION_SCHEMA or obs.get("state") != CLASSIFIED_OPERATION_STATE:
            errors.append(f"OBSERVATION_NOT_CLASSIFIED:{seq}")
        if obs.get("installation_id") != p.get("installation_id") or obs.get("journal_entry_digest") != e.get("journal_entry_digest") or type(obs.get("sequence")) is not int or obs["sequence"] != seq or obs.get("operation_id") != op.get("operation_id"):
            errors.append(f"OBSERVATION_BINDING_MISMATCH:{seq}")
        if _sha(obs.get("operation_observation_digest")) != _digest({k: obs.get(k) for k in OBS_FIELDS}):
            errors.append(f"OBSERVATION_DIGEST_MISMATCH:{seq}")
        if (obs.get("final_outcome") != OP_APPLIED
            or obs.get("operation_applied_confirmed") is not True
            or obs.get("operation_outcome_unknown") is not False
            or obs.get("operation_terminal_failure_confirmed") is not False
            or obs.get("operation_attempted") is not True
            or obs.get("ambiguity_evidence_digest") not in ("", None)
            or not _sha(obs.get("mutation_write_observation_digest"))
            or obs.get("before_state_observation_digest") != op.get("before_state_digest")
            or obs.get("after_state_observation_digest") != op.get("intended_after_state_digest")
            or not _sha(obs.get("rollback_material_presence_digest"))):
            errors.append(f"OPERATION_NOT_POSITIVELY_APPLIED:{seq}")
    errors = _dedup(errors)
    material = {
        "installation_id": p.get("installation_id"),
        "journal_plan_digest": _sha(p.get("journal_plan_digest")),
        "final_journal_entry_digest": _sha(previous),
        "operation_observation_digests": [_sha(o.get("operation_observation_digest")) for o in os],
        "operation_count": count,
    }
    return {
        "schema": GATE_SCHEMA,
        "state": GATE_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "completion_gate_digest": _digest(material) if not errors else "",
        "journal_complete_shape_only": not errors,
        "journal_persisted_trusted": False,
        "files_verified_after_reopen": False,
        "installation_complete_trusted": False,
        "aion_healthy_trusted": False,
        "automatic_retry_allowed": False,
    }

def build_postinstall_verification_plan(
    journal_plan: Mapping[str, Any] | None,
    gate: Mapping[str, Any] | None,
    *,
    reopen_policy_digest: Any,
    health_policy_digest: Any,
    independent_verifier_manifest_digest: Any,
) -> dict[str, Any]:
    p, g = _map(journal_plan), _map(gate)
    errors: list[str] = []
    if p.get("state") != READY_JOURNAL_PLAN_STATE or p.get("schema") != JOURNAL_PLAN_SCHEMA:
        errors.append("JOURNAL_PLAN_REQUIRED")
    if g.get("state") != GATE_READY or g.get("schema") != GATE_SCHEMA:
        errors.append("COMPLETE_JOURNAL_GATE_REQUIRED")
    if g.get("journal_plan_digest") != p.get("journal_plan_digest") or g.get("installation_id") != p.get("installation_id"):
        errors.append("GATE_AND_PLAN_BINDING_MISMATCH")
    digests = {
        "reopen_policy_digest": _sha(reopen_policy_digest),
        "health_policy_digest": _sha(health_policy_digest),
        "independent_verifier_manifest_digest": _sha(independent_verifier_manifest_digest),
    }
    for k, d in digests.items():
        if not d:
            errors.append(k.upper() + "_REQUIRED")
    final_targets: dict[str, dict[str, Any]] = {}
    for op in _rows(p.get("operations")):
        target = _sha(op.get("target_digest"))
        after = _sha(op.get("intended_after_state_digest"))
        if not target or not after:
            errors.append("TARGET_AND_AFTER_STATE_DIGEST_REQUIRED")
        else:
            final_targets[target] = {
                "check_id": "TARGET:" + target,
                "check_kind": "TARGET_FINAL_STATE_REOPEN",
                "target_digest": target,
                "expected_digest": after,
                "last_sequence": op.get("sequence"),
                "last_operation_kind": op.get("operation_kind"),
            }
    checks = [
        {"check_id": "GLOBAL:" + kind, "check_kind": kind,
         "expected_digest": _digest({
             "kind": kind, "installation_id": p.get("installation_id"),
             "journal_plan_digest": p.get("journal_plan_digest"),
             "reopen_policy_digest": digests["reopen_policy_digest"],
             "health_policy_digest": digests["health_policy_digest"],
         })}
        for kind in GLOBAL_CHECKS
    ] + [final_targets[k] for k in sorted(final_targets)]
    material = {
        "installation_id": p.get("installation_id"),
        "journal_plan_digest": _sha(p.get("journal_plan_digest")),
        "completion_gate_digest": _sha(g.get("completion_gate_digest")),
        **digests,
        "checks": checks,
    }
    errors = _dedup(errors)
    return {
        "schema": VERIFY_PLAN_SCHEMA,
        "state": PLAN_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "verification_plan_digest": _digest(material) if not errors else "",
        "fresh_reopen_required": True,
        "all_checks_required": True,
        "independent_verifier_required": True,
        "runtime_health_required": True,
        "verification_performed": False,
        "installed_and_healthy_trusted": False,
    }

def validate_postinstall_evidence_shape(
    verification_plan: Mapping[str, Any] | None,
    evidence_rows: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Comparison of proof-envelope fields, not proof of a physical readback."""
    p, rows = _map(verification_plan), _rows(evidence_rows)
    errors: list[str] = []
    if p.get("schema") != VERIFY_PLAN_SCHEMA or p.get("state") != PLAN_READY:
        errors.append("VERIFICATION_PLAN_REQUIRED")
    checks = _rows(p.get("checks"))
    expected_ids = [c.get("check_id") for c in checks]
    actual_ids = [r.get("check_id") for r in rows]
    if len(rows) != len(checks) or len(set(map(str, actual_ids))) != len(actual_ids) or actual_ids != expected_ids:
        errors.append("CHECK_COVERAGE_ORDER_OR_DUPLICATE_FAILURE")
    for i, check in enumerate(checks):
        if i >= len(rows):
            break
        row = rows[i]
        if (row.get("check_id") != check.get("check_id")
            or row.get("expected_digest") != check.get("expected_digest")
            or row.get("observed_digest") != check.get("expected_digest")
            or row.get("verified_after_reopen") is not True
            or row.get("independent_verifier_observed") is not True
            or not _sha(row.get("readback_receipt_digest"))
            or not _sha(row.get("independent_verifier_receipt_digest"))
            or row.get("ambiguity_detected") is not False):
            errors.append("REOPEN_VERIFICATION_UNCONFIRMED:" + str(check.get("check_id")))
    errors = _dedup(errors)
    material = {
        "installation_id": p.get("installation_id"),
        "verification_plan_digest": _sha(p.get("verification_plan_digest")),
        "check_evidence_digests": [_digest(r) for r in rows],
    }
    return {
        "schema": VERIFY_EVIDENCE_SCHEMA,
        "state": VERIFY_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "verification_evidence_candidate_digest": _digest(material) if not errors else "",
        "all_checks_shape_matched": not errors,
        "physical_reopen_verified_trusted": False,
        "package_installed_trusted": False,
        "aion_healthy_trusted": False,
        "installation_success_authorized": False,
    }

def build_rollback_terminal_receipt_candidate(
    journal_plan: Mapping[str, Any] | None,
    recovery_contract: Mapping[str, Any] | None,
    rollback_step_receipts: Iterable[Mapping[str, Any]] | None,
    *,
    final_clean_reopen_receipt_digest: Any,
    independent_verifier_manifest_digest: Any,
) -> dict[str, Any]:
    p, recovery = _map(journal_plan), _map(recovery_contract)
    rows = _rows(rollback_step_receipts)
    errors: list[str] = []
    if p.get("schema") != JOURNAL_PLAN_SCHEMA or p.get("state") != READY_JOURNAL_PLAN_STATE:
        errors.append("JOURNAL_PLAN_REQUIRED")
    if recovery.get("schema") != RECOVERY_SCHEMA or recovery.get("state") != READY_RECOVERY_STATE:
        errors.append("RECOVERY_CONTRACT_REQUIRED")
    if recovery.get("journal_plan_digest") != p.get("journal_plan_digest") or recovery.get("installation_id") != p.get("installation_id"):
        errors.append("RECOVERY_PLAN_MISMATCH")
    n = recovery.get("failed_or_unknown_sequence")
    expected = list(range(n, 0, -1)) if type(n) is int and 1 <= n <= len(_rows(p.get("operations"))) else []
    if not expected or recovery.get("rollback_sequences") != expected:
        errors.append("REVERSE_SEQUENCE_INVALID")
    if len(rows) != len(expected):
        errors.append("EXACT_ROLLBACK_RECEIPT_COVERAGE_REQUIRED")
    ops = _rows(p.get("operations"))
    for idx, seq in enumerate(expected):
        if idx >= len(rows):
            break
        row, op = rows[idx], ops[seq - 1]
        if (type(row.get("sequence")) is not int or row.get("sequence") != seq
            or row.get("operation_id") != op.get("operation_id")
            or row.get("rollback_action_digest") != op.get("rollback_action_digest")
            or row.get("observed_restored_state_digest") != op.get("before_state_digest")
            or row.get("rollback_step_outcome") != "ROLLBACK_STEP_APPLIED_CONFIRMED"
            or row.get("verified_after_reopen") is not True
            or row.get("ambiguity_detected") is not False
            or not _sha(row.get("rollback_write_receipt_digest"))
            or not _sha(row.get("readback_receipt_digest"))
            or not _sha(row.get("independent_verifier_receipt_digest"))):
            errors.append(f"ROLLBACK_STEP_NOT_VERIFIED:{seq}")
    if not _sha(final_clean_reopen_receipt_digest):
        errors.append("FINAL_CLEAN_REOPEN_RECEIPT_REQUIRED")
    if not _sha(independent_verifier_manifest_digest):
        errors.append("INDEPENDENT_VERIFIER_MANIFEST_REQUIRED")
    errors = _dedup(errors)
    material = {
        "installation_id": p.get("installation_id"),
        "journal_plan_digest": _sha(p.get("journal_plan_digest")),
        "recovery_contract_digest": _sha(recovery.get("recovery_contract_digest")),
        "rollback_sequences": expected,
        "rollback_step_receipt_digests": [_digest(r) for r in rows],
        "final_clean_reopen_receipt_digest": _sha(final_clean_reopen_receipt_digest),
        "independent_verifier_manifest_digest": _sha(independent_verifier_manifest_digest),
    }
    return {
        "schema": ROLLBACK_RECEIPT_SCHEMA,
        "state": ROLLBACK_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "rollback_receipt_candidate_digest": _digest(material) if not errors else "",
        "rollback_disposition": ROLLBACK_CANDIDATE if not errors else ROLLBACK_UNKNOWN,
        "rollback_executed_trusted": False,
        "rollback_terminal_trusted": False,
        "residual_changes_absent_trusted": False,
        "new_installation_authorized": False,
        "automatic_forward_retry_allowed": False,
    }

def build_terminal_install_receipt_candidate(
    *,
    installation_id: Any,
    requested_disposition: Any,
    journal_gate: Mapping[str, Any] | None = None,
    postinstall_evidence: Mapping[str, Any] | None = None,
    rollback_receipt: Mapping[str, Any] | None = None,
    failure_evidence: Mapping[str, Any] | None = None,
    terminal_reopen_receipt_digest: Any,
    independent_final_attestor_digest: Any,
) -> dict[str, Any]:
    """Mutually exclusive candidate: success, clean terminal failure, rollback, or unknown."""
    gate, v, r, f = map(_map, (journal_gate, postinstall_evidence, rollback_receipt, failure_evidence))
    errors: list[str] = []
    requested = requested_disposition
    if requested not in ("SUCCESS", "TERMINAL_FAILURE", "ROLLBACK_TERMINAL"):
        errors.append("TERMINAL_DISPOSITION_INVALID")
    if type(installation_id) is not str or not installation_id or len(installation_id) > 180:
        errors.append("INSTALLATION_ID_INVALID")
    if not _sha(terminal_reopen_receipt_digest):
        errors.append("TERMINAL_REOPEN_RECEIPT_REQUIRED")
    if not _sha(independent_final_attestor_digest):
        errors.append("INDEPENDENT_FINAL_ATTESTOR_REQUIRED")
    if requested == "SUCCESS":
        if (gate.get("schema") != GATE_SCHEMA or gate.get("state") != GATE_READY
            or gate.get("installation_id") != installation_id
            or v.get("schema") != VERIFY_EVIDENCE_SCHEMA or v.get("state") != VERIFY_READY
            or v.get("installation_id") != installation_id
            or r or f):
            errors.append("EXHAUSTIVE_POSTINSTALL_REOPEN_PROOF_SHAPE_REQUIRED")
        disposition = SUCCESS_CANDIDATE
    elif requested == "ROLLBACK_TERMINAL":
        if (r.get("schema") != ROLLBACK_RECEIPT_SCHEMA or r.get("state") != ROLLBACK_READY
            or r.get("installation_id") != installation_id or gate or v or f):
            errors.append("REVERSE_ROLLBACK_AND_CLEAN_REOPEN_PROOF_SHAPE_REQUIRED")
        disposition = ROLLBACK_CANDIDATE
    elif requested == "TERMINAL_FAILURE":
        if (not _sha(f.get("authoritative_failure_receipt_digest"))
            or not _sha(f.get("independent_no_write_evidence_digest"))
            or not _sha(f.get("no_residual_changes_reopen_receipt_digest"))
            or f.get("failure_before_first_mutation") is not True
            or f.get("no_write_authoritatively_proven") is not True
            or f.get("no_residual_changes_after_reopen") is not True
            or f.get("ambiguity_detected") is not False
            or gate or v or r):
            errors.append("AUTHORITATIVE_CLEAN_TERMINAL_FAILURE_PROOF_SHAPE_REQUIRED")
        disposition = FAILURE_CANDIDATE
    else:
        disposition = UNKNOWN
    errors = _dedup(errors)
    material = {
        "installation_id": installation_id,
        "requested_disposition": requested,
        "candidate_disposition": disposition if not errors else UNKNOWN,
        "completion_gate_digest": _sha(gate.get("completion_gate_digest")),
        "postinstall_evidence_digest": _sha(v.get("verification_evidence_candidate_digest")),
        "rollback_receipt_digest": _sha(r.get("rollback_receipt_candidate_digest")),
        "failure_evidence_digest": _digest(f) if f else "",
        "terminal_reopen_receipt_digest": _sha(terminal_reopen_receipt_digest),
        "independent_final_attestor_digest": _sha(independent_final_attestor_digest),
    }
    return {
        "schema": TERMINAL_RECEIPT_SCHEMA,
        "state": TERMINAL_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "terminal_receipt_candidate_digest": _digest(material) if not errors else "",
        "terminal_outcome": disposition if not errors else (ROLLBACK_UNKNOWN if requested == "ROLLBACK_TERMINAL" else UNKNOWN),
        "physically_installed_trusted": False,
        "aion_healthy_trusted": False,
        "terminal_disposition_persisted": False,
        "rollback_performed": False,
        "new_installation_authorized": False,
        "automatic_retry_allowed": False,
        "automatic_continue_allowed": False,
    }

def build_completion_implementation_review(
    completion_gate: Mapping[str, Any] | None,
    verification_plan: Mapping[str, Any] | None,
    *,
    verifier_source_digest: Any,
    terminal_receipt_writer_source_digest: Any,
    rollback_attestor_source_digest: Any,
) -> dict[str, Any]:
    g, p = _map(completion_gate), _map(verification_plan)
    errors: list[str] = []
    if g.get("state") != GATE_READY:
        errors.append("COMPLETION_GATE_REQUIRED")
    if p.get("state") != PLAN_READY or p.get("completion_gate_digest") != g.get("completion_gate_digest"):
        errors.append("VERIFICATION_PLAN_BINDING_REQUIRED")
    digests = {
        "verifier_source_digest": _sha(verifier_source_digest),
        "terminal_receipt_writer_source_digest": _sha(terminal_receipt_writer_source_digest),
        "rollback_attestor_source_digest": _sha(rollback_attestor_source_digest),
    }
    for name, value in digests.items():
        if not value:
            errors.append(name.upper() + "_REQUIRED")
    errors = _dedup(errors)
    material = {
        "completion_gate_digest": _sha(g.get("completion_gate_digest")),
        "verification_plan_digest": _sha(p.get("verification_plan_digest")),
        **digests,
        "next_pc_phase": "IMPLEMENT_SYNTHETIC_POSTINSTALL_READBACK_AND_TERMINAL_ATTESTOR",
    }
    return {
        "schema": REVIEW_SCHEMA,
        "state": REVIEW_READY if not errors else BLOCKED,
        "blockers": errors,
        **material,
        "implementation_review_digest": _digest(material) if not errors else "",
        **{key: False for key in (
            "install_commitment_written", "owner_install_authorization_consumed",
            "install_token_consumed", "journal_persisted", "installation_started",
            "files_copied", "filesystem_modified", "windows_acl_modified",
            "windows_registry_modified", "startup_entry_created", "rollback_performed",
            "package_installed", "postinstall_verification_executed", "aion_healthy_trusted",
            "terminal_receipt_persisted", "process_spawned", "network_called",
            "github_api_called", "deploy_executed", "worker_activated",
            "production_persistence_activated",
        )},
    }

def completion_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "journal_finished_means_installed": False,
        "all_operations_confirmed_required": True,
        "complete_chain_and_observation_binding_required": True,
        "final_target_state_after_reopen_required": True,
        "owner_acl_and_startup_after_reopen_required": True,
        "runtime_health_after_reopen_required": True,
        "independent_terminal_attestation_required": True,
        "success_on_missing_health_allowed": False,
        "success_on_missing_reopen_allowed": False,
        "terminal_failure_with_possible_write_allowed": False,
        "rollback_reverse_order_required": True,
        "rollback_terminal_requires_clean_reopen": True,
        "ambiguity_is_terminal_success": False,
        "automatic_forward_retry_after_unknown_allowed": False,
        "automatic_forward_continue_after_unknown_allowed": False,
        "shape_validation_is_physical_truth": False,
        "design_only": True,
        "installation_started": False,
        "filesystem_modified": False,
        "rollback_performed": False,
        "package_installed": False,
        "terminal_receipt_persisted": False,
        "deploy_executed": False,
        "worker_activated": False,
    }

__all__ = [name for name in globals() if name.isupper() or name.startswith(("build_", "validate_", "completion_"))]
