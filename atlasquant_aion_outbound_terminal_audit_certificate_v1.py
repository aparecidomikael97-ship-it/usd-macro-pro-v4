"""AION Outbound Terminal Finalization + Audit Certificate V1.

Pure, non-executing terminal closure contracts for outbound external effects.

This module:
- accepts only authoritative known outcome states;
- blocks OUTCOME_UNKNOWN and STILL_OUTCOME_UNKNOWN;
- prepares terminal finalization;
- validates external persistence attestations;
- builds a deterministic audit-seal manifest;
- validates audit-seal persistence evidence;
- builds a read-only terminal certificate descriptor.

It does NOT persist anything, call providers, retry/reopen execution, sign with a
real key, send messages, export/sign contracts, write CRM, deploy or mutate Core.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_sealed_provider_outcome_reconciliation_v1 import (
    OUTCOME_RECEIPT_SCHEMA,
    RECONCILIATION_SCHEMA,
    verify_outcome_chain_record,
)


SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_AUDIT_CERTIFICATE_V1"
FINALIZATION_SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_FINALIZATION_V1"
FINALIZATION_PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_OUTBOUND_TERMINAL_FINALIZATION_PERSISTENCE_ATTESTATION_V1"
)
AUDIT_SEAL_SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_AUDIT_SEAL_V1"
AUDIT_SEAL_PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_OUTBOUND_TERMINAL_AUDIT_SEAL_PERSISTENCE_ATTESTATION_V1"
)
CERTIFICATE_SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_CERTIFICATE_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_CHAIN_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OUTBOUND_TERMINAL_CHAIN_POLICY_V1"

FINALIZABLE_OUTCOMES = (
    "CONFIRMED_SUCCESS",
    "CONFIRMED_TERMINAL_FAILURE",
    "RECONCILED_CONFIRMED_SUCCESS",
    "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
)
NON_FINALIZABLE_OUTCOMES = ("OUTCOME_UNKNOWN", "STILL_OUTCOME_UNKNOWN")
FINAL_STATES = ("FINALIZED_SUCCESS", "FINALIZED_TERMINAL_FAILURE")
DIGEST_ALGORITHM = "SHA256"
CANONICAL_ENCODING = "UTF8_CANONICAL_JSON"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


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


def _material(row: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    raw = dict(row)
    raw.pop(digest_field, None)
    return raw


def _terminal_outcome(
    receipt: Mapping[str, Any] | None,
    reconciliation: Mapping[str, Any] | None,
) -> tuple[str, str, str, list[str]]:
    raw = dict(receipt or {})
    recon = dict(reconciliation or {})
    blockers: list[str] = []

    if raw.get("schema") != OUTCOME_RECEIPT_SCHEMA:
        blockers.append("OUTCOME_RECEIPT_SCHEMA_MISMATCH")
        return "", "", "", blockers
    if raw.get("state") != "OUTCOME_RECEIPT_READY":
        blockers.append("VALID_OUTCOME_RECEIPT_REQUIRED")
        return "", "", "", blockers
    if verify_outcome_chain_record(raw).get("valid") is not True:
        blockers.append("OUTCOME_RECEIPT_VERIFICATION_FAILED")
        return "", "", "", blockers

    receipt_digest = _sha256(raw.get("outcome_receipt_digest"))
    if not receipt_digest:
        blockers.append("OUTCOME_RECEIPT_DIGEST_REQUIRED")

    outcome = _clean(raw.get("outcome_state"), 80).upper()
    reconciliation_digest = ""

    if outcome in ("CONFIRMED_SUCCESS", "CONFIRMED_TERMINAL_FAILURE"):
        return outcome, receipt_digest, reconciliation_digest, blockers

    if outcome != "OUTCOME_UNKNOWN":
        blockers.append("OUTCOME_STATE_NOT_FINALIZABLE")
        return outcome, receipt_digest, reconciliation_digest, blockers

    if recon.get("schema") != RECONCILIATION_SCHEMA:
        blockers.append("RECONCILIATION_REQUIRED_FOR_UNKNOWN")
        return outcome, receipt_digest, reconciliation_digest, blockers
    if recon.get("state") != "RECONCILIATION_RECORD_READY":
        blockers.append("VALID_RECONCILIATION_REQUIRED")
        return outcome, receipt_digest, reconciliation_digest, blockers
    if verify_outcome_chain_record(recon).get("valid") is not True:
        blockers.append("RECONCILIATION_VERIFICATION_FAILED")
        return outcome, receipt_digest, reconciliation_digest, blockers
    if _sha256(recon.get("original_outcome_receipt_digest")) != receipt_digest:
        blockers.append("RECONCILIATION_RECEIPT_BINDING_MISMATCH")
    reconciliation_digest = _sha256(recon.get("reconciliation_digest"))
    if not reconciliation_digest:
        blockers.append("RECONCILIATION_DIGEST_REQUIRED")

    reconciled = _clean(recon.get("reconciled_outcome_state"), 100).upper()
    if reconciled == "RECONCILED_CONFIRMED_SUCCESS":
        outcome = reconciled
    elif reconciled == "RECONCILED_CONFIRMED_TERMINAL_FAILURE":
        outcome = reconciled
    elif reconciled == "STILL_OUTCOME_UNKNOWN":
        blockers.append("STILL_OUTCOME_UNKNOWN_NOT_FINALIZABLE")
        outcome = reconciled
    else:
        blockers.append("RECONCILIATION_OUTCOME_INVALID")
        outcome = reconciled

    return outcome, receipt_digest, reconciliation_digest, blockers


def build_terminal_finalization(
    outcome_receipt: Mapping[str, Any] | None,
    reconciliation: Mapping[str, Any] | None = None,
    *,
    terminal_revision: Any,
    terminal_evidence_set_digest: Any,
    finops_observation_digest: Any,
    rollback_or_compensation_settlement_digest: Any = "",
    execution_id_match: bool,
    trace_id_match: bool,
    idempotency_key_match: bool,
    effect_key_match: bool,
    provider_request_correlation_match: bool,
    provider_identity_match: bool,
    terminal_evidence_authenticated: bool,
    terminal_evidence_fresh: bool,
    unresolved_conflict_present: bool,
    pending_reconciliation: bool,
    pending_rollback_or_compensation: bool,
    finops_within_policy: bool,
    effect_confirmation_complete: bool = False,
    expected_postcondition_match: bool = False,
    no_effect_or_terminal_rejection_complete: bool = False,
) -> dict[str, Any]:
    """Prepare authoritative terminal closure; never persists final state."""
    receipt = dict(outcome_receipt or {})
    outcome, receipt_digest, reconciliation_digest, blockers = _terminal_outcome(
        receipt,
        reconciliation,
    )

    try:
        revision = int(terminal_revision)
        if revision < 1:
            blockers.append("TERMINAL_REVISION_INVALID")
    except Exception:
        revision = 0
        blockers.append("TERMINAL_REVISION_INVALID")

    terminal_evidence = _sha256(terminal_evidence_set_digest)
    finops = _sha256(finops_observation_digest)
    settlement = (
        _sha256(rollback_or_compensation_settlement_digest)
        if rollback_or_compensation_settlement_digest
        else ""
    )
    if not terminal_evidence:
        blockers.append("TERMINAL_EVIDENCE_SET_DIGEST_REQUIRED")
    if not finops:
        blockers.append("FINOPS_OBSERVATION_DIGEST_REQUIRED")

    required_common = (
        ("EXECUTION_ID_MATCH_REQUIRED", execution_id_match),
        ("TRACE_ID_MATCH_REQUIRED", trace_id_match),
        ("IDEMPOTENCY_KEY_MATCH_REQUIRED", idempotency_key_match),
        ("EFFECT_KEY_MATCH_REQUIRED", effect_key_match),
        ("PROVIDER_CORRELATION_MATCH_REQUIRED", provider_request_correlation_match),
        ("PROVIDER_IDENTITY_MATCH_REQUIRED", provider_identity_match),
        ("TERMINAL_EVIDENCE_AUTHENTICATION_REQUIRED", terminal_evidence_authenticated),
        ("TERMINAL_EVIDENCE_FRESHNESS_REQUIRED", terminal_evidence_fresh),
        ("FINOPS_POLICY_SETTLEMENT_REQUIRED", finops_within_policy),
    )
    for label, flag in required_common:
        if flag is not True:
            blockers.append(label)

    if unresolved_conflict_present is True:
        blockers.append("UNRESOLVED_TERMINAL_CONFLICT")
    if pending_reconciliation is True:
        blockers.append("PENDING_RECONCILIATION")
    if pending_rollback_or_compensation is True:
        blockers.append("PENDING_ROLLBACK_OR_COMPENSATION")

    success = outcome in (
        "CONFIRMED_SUCCESS",
        "RECONCILED_CONFIRMED_SUCCESS",
    )
    failure = outcome in (
        "CONFIRMED_TERMINAL_FAILURE",
        "RECONCILED_CONFIRMED_TERMINAL_FAILURE",
    )

    if success:
        if effect_confirmation_complete is not True:
            blockers.append("EFFECT_CONFIRMATION_REQUIRED")
        if expected_postcondition_match is not True:
            blockers.append("EXPECTED_POSTCONDITION_MATCH_REQUIRED")
        final_state = "FINALIZED_SUCCESS"
    elif failure:
        if no_effect_or_terminal_rejection_complete is not True:
            blockers.append("NO_EFFECT_OR_TERMINAL_REJECTION_EVIDENCE_REQUIRED")
        final_state = "FINALIZED_TERMINAL_FAILURE"
    else:
        final_state = ""
        if outcome in NON_FINALIZABLE_OUTCOMES:
            blockers.append("UNKNOWN_OUTCOME_CANNOT_BE_FINALIZED")
        elif outcome not in FINALIZABLE_OUTCOMES:
            blockers.append("TERMINAL_OUTCOME_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    row: dict[str, Any] = {
        "schema": FINALIZATION_SCHEMA,
        "state": "READY_FOR_FINALIZATION_PERSISTENCE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "execution_id": _clean(receipt.get("execution_id"), 160),
        "observability_trace_id": _clean(
            receipt.get("observability_trace_id"), 200
        ),
        "final_execution_state": final_state,
        "source_terminal_outcome": outcome,
        "terminal_revision": revision,
        "outcome_receipt_digest": receipt_digest,
        "reconciliation_digest": reconciliation_digest,
        "durable_dispatch_record_digest": _sha256(
            receipt.get("durable_dispatch_record_digest")
        ),
        "call_boundary_digest": _sha256(receipt.get("call_boundary_digest")),
        "subject_digest": _sha256(receipt.get("subject_digest")),
        "idempotency_key_digest": _sha256(
            receipt.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(receipt.get("effect_key_digest")),
        "provider_request_correlation_digest": _sha256(
            receipt.get("provider_request_correlation_digest")
        ),
        "terminal_evidence_set_digest": terminal_evidence,
        "finops_observation_digest": finops,
        "rollback_or_compensation_settlement_digest": settlement,
        "execution_id_match": execution_id_match is True,
        "trace_id_match": trace_id_match is True,
        "idempotency_key_match": idempotency_key_match is True,
        "effect_key_match": effect_key_match is True,
        "provider_request_correlation_match": (
            provider_request_correlation_match is True
        ),
        "provider_identity_match": provider_identity_match is True,
        "terminal_evidence_authenticated": terminal_evidence_authenticated is True,
        "terminal_evidence_fresh": terminal_evidence_fresh is True,
        "unresolved_conflict_present": unresolved_conflict_present is True,
        "pending_reconciliation": pending_reconciliation is True,
        "pending_rollback_or_compensation": (
            pending_rollback_or_compensation is True
        ),
        "finops_within_policy": finops_within_policy is True,
        "effect_confirmation_complete": effect_confirmation_complete is True,
        "expected_postcondition_match": expected_postcondition_match is True,
        "no_effect_or_terminal_rejection_complete": (
            no_effect_or_terminal_rejection_complete is True
        ),
        "finalization_is_retry": False,
        "execution_reopened": False,
        "external_effect_replayed": False,
        "provider_called": False,
        "network_called": False,
        "final_state_persisted_by_this_module": False,
        "external_action_executed": False,
        "executes_action": False,
        "finalization_digest": "",
    }
    row["finalization_digest"] = (
        _digest(_material(row, "finalization_digest")) if not blockers else ""
    )
    return row


def build_finalization_persistence_attestation(
    finalization: Mapping[str, Any] | None,
    *,
    finalization_record_digest: Any,
    writer_attestation_digest: Any,
    read_after_write_verified: bool,
    atomic_write_or_cas_verified: bool,
    writer_identity_verified: bool,
) -> dict[str, Any]:
    raw = dict(finalization or {})
    blockers: list[str] = []

    if raw.get("schema") != FINALIZATION_SCHEMA:
        blockers.append("FINALIZATION_SCHEMA_MISMATCH")
    if raw.get("state") != "READY_FOR_FINALIZATION_PERSISTENCE":
        blockers.append("READY_FINALIZATION_REQUIRED")

    finalization_digest = _sha256(raw.get("finalization_digest"))
    record_digest = _sha256(finalization_record_digest)
    writer_digest = _sha256(writer_attestation_digest)
    if not finalization_digest:
        blockers.append("FINALIZATION_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("FINALIZATION_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("READ_AFTER_WRITE_REQUIRED")
    if atomic_write_or_cas_verified is not True:
        blockers.append("ATOMIC_WRITE_OR_CAS_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("WRITER_IDENTITY_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    row = {
        "schema": FINALIZATION_PERSISTENCE_SCHEMA,
        "state": "FINALIZATION_PERSISTENCE_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        "execution_id": _clean(raw.get("execution_id"), 160),
        "final_execution_state": _clean(
            raw.get("final_execution_state"), 80
        ).upper(),
        "terminal_revision": raw.get("terminal_revision"),
        "finalization_digest": finalization_digest,
        "finalization_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "read_after_write_verified": read_after_write_verified is True,
        "atomic_write_or_cas_verified": atomic_write_or_cas_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
        "persisted_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "persistence_attestation_digest": "",
    }
    row["persistence_attestation_digest"] = (
        _digest(_material(row, "persistence_attestation_digest"))
        if not blockers
        else ""
    )
    return row


def build_audit_seal(
    finalization: Mapping[str, Any] | None,
    persistence_attestation: Mapping[str, Any] | None,
    *,
    pre_terminal_audit_chain_digest: Any,
) -> dict[str, Any]:
    final = dict(finalization or {})
    persisted = dict(persistence_attestation or {})
    blockers: list[str] = []

    if final.get("schema") != FINALIZATION_SCHEMA:
        blockers.append("FINALIZATION_SCHEMA_MISMATCH")
    if final.get("state") != "READY_FOR_FINALIZATION_PERSISTENCE":
        blockers.append("READY_FINALIZATION_REQUIRED")
    if persisted.get("schema") != FINALIZATION_PERSISTENCE_SCHEMA:
        blockers.append("FINALIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if persisted.get("state") != "FINALIZATION_PERSISTENCE_ATTESTED":
        blockers.append("PERSISTED_FINALIZATION_REQUIRED")
    if _sha256(persisted.get("finalization_digest")) != _sha256(
        final.get("finalization_digest")
    ):
        blockers.append("FINALIZATION_PERSISTENCE_BINDING_MISMATCH")

    audit_chain = _sha256(pre_terminal_audit_chain_digest)
    if not audit_chain:
        blockers.append("PRE_TERMINAL_AUDIT_CHAIN_DIGEST_REQUIRED")
    if final.get("final_execution_state") not in FINAL_STATES:
        blockers.append("TERMINAL_FINAL_STATE_REQUIRED")
    if final.get("source_terminal_outcome") in NON_FINALIZABLE_OUTCOMES:
        blockers.append("UNRESOLVED_UNKNOWN_OUTCOME")
    if final.get("pending_reconciliation") is not False:
        blockers.append("PENDING_RECONCILIATION")
    if final.get("pending_rollback_or_compensation") is not False:
        blockers.append("PENDING_ROLLBACK_OR_COMPENSATION")

    blockers = list(dict.fromkeys(blockers))
    manifest = {
        "schema_version": 1,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonical_encoding": CANONICAL_ENCODING,
        "execution_id": _clean(final.get("execution_id"), 160),
        "final_execution_state": _clean(
            final.get("final_execution_state"), 80
        ).upper(),
        "terminal_revision": final.get("terminal_revision"),
        "finalization_digest": _sha256(final.get("finalization_digest")),
        "finalization_record_digest": _sha256(
            persisted.get("finalization_record_digest")
        ),
        "finalization_persistence_attestation_digest": _sha256(
            persisted.get("persistence_attestation_digest")
        ),
        "durable_dispatch_record_digest": _sha256(
            final.get("durable_dispatch_record_digest")
        ),
        "call_boundary_digest": _sha256(final.get("call_boundary_digest")),
        "outcome_receipt_digest": _sha256(final.get("outcome_receipt_digest")),
        "reconciliation_digest": _sha256(final.get("reconciliation_digest")),
        "subject_digest": _sha256(final.get("subject_digest")),
        "idempotency_key_digest": _sha256(
            final.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(final.get("effect_key_digest")),
        "provider_request_correlation_digest": _sha256(
            final.get("provider_request_correlation_digest")
        ),
        "terminal_evidence_set_digest": _sha256(
            final.get("terminal_evidence_set_digest")
        ),
        "rollback_or_compensation_settlement_digest": _sha256(
            final.get("rollback_or_compensation_settlement_digest")
        ),
        "finops_observation_digest": _sha256(
            final.get("finops_observation_digest")
        ),
        "observability_trace_id": _clean(
            final.get("observability_trace_id"), 200
        ),
        "pre_terminal_audit_chain_digest": audit_chain,
    }

    row = {
        "schema": AUDIT_SEAL_SCHEMA,
        "state": "AUDIT_SEAL_READY_FOR_PERSISTENCE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "manifest": manifest,
        "audit_seal_manifest_digest": _digest(manifest) if not blockers else "",
        "seal_is_immutable": True,
        "seal_is_append_only": True,
        "seal_creates_execution_authority": False,
        "seal_authorizes_retry": False,
        "seal_authorizes_reopen": False,
        "seal_authorizes_external_effect": False,
        "real_signature_created": False,
        "seal_persisted_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }
    return row


def build_audit_seal_persistence_attestation(
    audit_seal: Mapping[str, Any] | None,
    *,
    audit_seal_persistence_record_digest: Any,
    writer_attestation_digest: Any,
    reopen_consistency_verified: bool,
    read_after_write_verified: bool,
    writer_identity_verified: bool,
) -> dict[str, Any]:
    seal = dict(audit_seal or {})
    blockers: list[str] = []

    if seal.get("schema") != AUDIT_SEAL_SCHEMA:
        blockers.append("AUDIT_SEAL_SCHEMA_MISMATCH")
    if seal.get("state") != "AUDIT_SEAL_READY_FOR_PERSISTENCE":
        blockers.append("READY_AUDIT_SEAL_REQUIRED")

    seal_digest = _sha256(seal.get("audit_seal_manifest_digest"))
    record_digest = _sha256(audit_seal_persistence_record_digest)
    writer_digest = _sha256(writer_attestation_digest)
    if not seal_digest:
        blockers.append("AUDIT_SEAL_MANIFEST_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("AUDIT_SEAL_PERSISTENCE_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    if reopen_consistency_verified is not True:
        blockers.append("AUDIT_SEAL_REOPEN_CONSISTENCY_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("AUDIT_SEAL_READ_AFTER_WRITE_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("AUDIT_SEAL_WRITER_IDENTITY_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    row = {
        "schema": AUDIT_SEAL_PERSISTENCE_SCHEMA,
        "state": "AUDIT_SEAL_PERSISTENCE_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        "audit_seal_manifest_digest": seal_digest,
        "audit_seal_persistence_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "reopen_consistency_verified": reopen_consistency_verified is True,
        "read_after_write_verified": read_after_write_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
        "persisted_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "persistence_attestation_digest": "",
    }
    row["persistence_attestation_digest"] = (
        _digest(_material(row, "persistence_attestation_digest"))
        if not blockers
        else ""
    )
    return row


def build_terminal_certificate(
    finalization: Mapping[str, Any] | None,
    finalization_persistence: Mapping[str, Any] | None,
    audit_seal: Mapping[str, Any] | None,
    audit_seal_persistence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    final = dict(finalization or {})
    fp = dict(finalization_persistence or {})
    seal = dict(audit_seal or {})
    sp = dict(audit_seal_persistence or {})
    blockers: list[str] = []

    if final.get("schema") != FINALIZATION_SCHEMA:
        blockers.append("FINALIZATION_SCHEMA_MISMATCH")
    if final.get("state") != "READY_FOR_FINALIZATION_PERSISTENCE":
        blockers.append("READY_FINALIZATION_REQUIRED")
    if fp.get("schema") != FINALIZATION_PERSISTENCE_SCHEMA:
        blockers.append("FINALIZATION_PERSISTENCE_SCHEMA_MISMATCH")
    if fp.get("state") != "FINALIZATION_PERSISTENCE_ATTESTED":
        blockers.append("PERSISTED_FINALIZATION_REQUIRED")
    if seal.get("schema") != AUDIT_SEAL_SCHEMA:
        blockers.append("AUDIT_SEAL_SCHEMA_MISMATCH")
    if seal.get("state") != "AUDIT_SEAL_READY_FOR_PERSISTENCE":
        blockers.append("READY_AUDIT_SEAL_REQUIRED")
    if sp.get("schema") != AUDIT_SEAL_PERSISTENCE_SCHEMA:
        blockers.append("AUDIT_SEAL_PERSISTENCE_SCHEMA_MISMATCH")
    if sp.get("state") != "AUDIT_SEAL_PERSISTENCE_ATTESTED":
        blockers.append("PERSISTED_AUDIT_SEAL_REQUIRED")

    final_state = _clean(final.get("final_execution_state"), 80).upper()
    if final_state not in FINAL_STATES:
        blockers.append("TERMINAL_FINAL_STATE_REQUIRED")
    if final.get("source_terminal_outcome") in NON_FINALIZABLE_OUTCOMES:
        blockers.append("UNKNOWN_OUTCOME_PRESENT")
    if _sha256(fp.get("finalization_digest")) != _sha256(
        final.get("finalization_digest")
    ):
        blockers.append("FINALIZATION_PERSISTENCE_DIGEST_MISMATCH")
    if _sha256(sp.get("audit_seal_manifest_digest")) != _sha256(
        seal.get("audit_seal_manifest_digest")
    ):
        blockers.append("AUDIT_SEAL_PERSISTENCE_DIGEST_MISMATCH")

    blockers = list(dict.fromkeys(blockers))
    manifest = {
        "schema_version": 1,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonical_encoding": CANONICAL_ENCODING,
        "execution_id": _clean(final.get("execution_id"), 160),
        "final_execution_state": final_state,
        "terminal_revision": final.get("terminal_revision"),
        "finalization_record_digest": _sha256(
            fp.get("finalization_record_digest")
        ),
        "finalization_persistence_attestation_digest": _sha256(
            fp.get("persistence_attestation_digest")
        ),
        "audit_seal_manifest_digest": _sha256(
            seal.get("audit_seal_manifest_digest")
        ),
        "audit_seal_persistence_record_digest": _sha256(
            sp.get("audit_seal_persistence_record_digest")
        ),
        "audit_seal_persistence_attestation_digest": _sha256(
            sp.get("persistence_attestation_digest")
        ),
        "idempotency_key_digest": _sha256(
            final.get("idempotency_key_digest")
        ),
        "effect_key_digest": _sha256(final.get("effect_key_digest")),
        "provider_request_correlation_digest": _sha256(
            final.get("provider_request_correlation_digest")
        ),
        "terminal_evidence_set_digest": _sha256(
            final.get("terminal_evidence_set_digest")
        ),
        "rollback_or_compensation_settlement_digest": _sha256(
            final.get("rollback_or_compensation_settlement_digest")
        ),
        "finops_observation_digest": _sha256(
            final.get("finops_observation_digest")
        ),
        "observability_trace_id": _clean(
            final.get("observability_trace_id"), 200
        ),
        "pre_terminal_audit_chain_digest": _sha256(
            dict(seal.get("manifest") or {}).get(
                "pre_terminal_audit_chain_digest"
            )
        ),
    }
    certificate_digest = _digest(manifest) if not blockers else ""

    return {
        "schema": CERTIFICATE_SCHEMA,
        "state": "TERMINAL_CERTIFICATE_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "manifest": manifest,
        "certificate_digest": certificate_digest,
        "certificate_is_read_only": True,
        "certificate_is_execution_authorization": False,
        "certificate_authorizes_retry": False,
        "certificate_authorizes_reopen": False,
        "certificate_authorizes_external_effect": False,
        "certificate_is_real_signature": False,
        "certificate_persisted_by_this_module": False,
        "provider_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def verify_terminal_certificate(
    certificate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(certificate or {})
    blockers: list[str] = []

    if raw.get("schema") != CERTIFICATE_SCHEMA:
        blockers.append("CERTIFICATE_SCHEMA_MISMATCH")
    if raw.get("state") != "TERMINAL_CERTIFICATE_READY":
        blockers.append("TERMINAL_CERTIFICATE_REQUIRED")

    manifest = dict(raw.get("manifest") or {})
    supplied = _sha256(raw.get("certificate_digest"))
    expected = _digest(manifest)
    if not supplied or supplied != expected:
        blockers.append("CERTIFICATE_DIGEST_MISMATCH")
    if manifest.get("final_execution_state") not in FINAL_STATES:
        blockers.append("CERTIFICATE_TERMINAL_STATE_INVALID")

    for key in (
        "certificate_is_execution_authorization",
        "certificate_authorizes_retry",
        "certificate_authorizes_reopen",
        "certificate_authorizes_external_effect",
        "certificate_is_real_signature",
        "certificate_persisted_by_this_module",
        "provider_called",
        "network_called",
        "external_action_executed",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("CERTIFICATE_BOUNDARY_INVALID:" + key)
    if raw.get("certificate_is_read_only") is not True:
        blockers.append("CERTIFICATE_READ_ONLY_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "certificate_digest": supplied,
        "executes_action": False,
    }


def terminal_chain_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "finalizable_outcomes": list(FINALIZABLE_OUTCOMES),
        "non_finalizable_outcomes": list(NON_FINALIZABLE_OUTCOMES),
        "unknown_outcome_can_be_finalized": False,
        "still_unknown_outcome_can_be_finalized": False,
        "terminal_evidence_required": True,
        "terminal_evidence_authentication_required": True,
        "terminal_evidence_freshness_required": True,
        "success_requires_effect_confirmation": True,
        "success_requires_expected_postcondition_match": True,
        "terminal_failure_requires_no_effect_or_terminal_rejection": True,
        "unresolved_conflict_blocks_finalization": True,
        "pending_reconciliation_blocks_finalization": True,
        "pending_rollback_or_compensation_blocks_finalization": True,
        "finalization_is_retry": False,
        "execution_reopen_allowed": False,
        "audit_seal_is_immutable": True,
        "audit_seal_is_append_only": True,
        "audit_seal_creates_execution_authority": False,
        "terminal_certificate_is_read_only": True,
        "terminal_certificate_is_execution_authorization": False,
        "terminal_certificate_authorizes_retry": False,
        "terminal_certificate_authorizes_reopen": False,
        "terminal_certificate_is_real_signature": False,
        "provider_called": False,
        "network_called": False,
        "message_sent": False,
        "contract_exported": False,
        "signature_requested": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "FINALIZATION_SCHEMA",
    "FINALIZATION_PERSISTENCE_SCHEMA",
    "AUDIT_SEAL_SCHEMA",
    "AUDIT_SEAL_PERSISTENCE_SCHEMA",
    "CERTIFICATE_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "FINALIZABLE_OUTCOMES",
    "NON_FINALIZABLE_OUTCOMES",
    "FINAL_STATES",
    "build_terminal_finalization",
    "build_finalization_persistence_attestation",
    "build_audit_seal",
    "build_audit_seal_persistence_attestation",
    "build_terminal_certificate",
    "verify_terminal_certificate",
    "terminal_chain_policy",
]
