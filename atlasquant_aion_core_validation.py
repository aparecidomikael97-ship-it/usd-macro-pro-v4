"""Read-only validation gates for AION Core and BUSINESS readiness.

This layer turns evidence into validation posture. It does not deploy, merge,
activate a specialist, publish, charge, trade, or write a runtime checkpoint.
Rollback verification is an in-memory sandbox drill only.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_build_identity import compare_deploy_identity, normalize_commit_sha

SCHEMA = "ATLASQUANT_AION_CORE_VALIDATION_V1"
VERSION = 1
CHECKPOINT_STATES = ("IMPLEMENTADO / EM VALIDAÇÃO", "VALIDADO")
BUSINESS_STATE = "READY_FOR_CERTIFICATION_REVIEW"
_MAX_REFS = 30
_MAX_REF = 300
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

BUSINESS_REQUIRED_GATES = (
    "offer_bundle_defined",
    "delivery_scope_defined",
    "demo_sandbox_passed",
    "admin_training_ready",
    "client_portal_contract_defined",
    "lgpd_privacy_defined",
    "financial_margin_model_defined",
    "support_sla_defined",
    "human_approval_boundaries_defined",
    "specialist_proof_package_ready",
)


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _refs(value: Any) -> tuple[list[str], bool]:
    raw = list(value or []) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []
    truncated = len(raw) > _MAX_REFS
    out: list[str] = []
    for item in raw[:_MAX_REFS]:
        ref = _clean(item, _MAX_REF)
        if ref and ref not in out:
            out.append(ref)
    return out, truncated


def _canonical_digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def production_identity_gate(
    expected_sha: Any,
    observed_identity: Mapping[str, Any] | None,
    *,
    target_url: Any,
) -> dict[str, Any]:
    """Require an exact non-local production SHA match.

    The observed identity must already have been collected by the caller.
    No network request is performed here.
    """
    identity = _mapping(observed_identity)
    expected = normalize_commit_sha(expected_sha)
    observed = normalize_commit_sha(identity.get("commit_sha"))
    comparison = compare_deploy_identity(expected, observed, target_url=target_url)
    environment = _clean(identity.get("environment"), 80) or "UNKNOWN"
    observed_flag = _exact_true(identity.get("commit_observed"))
    verified = (
        comparison.get("state") == "MATCH"
        and comparison.get("proves_production") is True
        and observed_flag
        and environment != "UNKNOWN"
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "VERIFIED" if verified else comparison.get("state", "UNKNOWN"),
        "verified": verified,
        "expected_sha": expected,
        "observed_sha": observed,
        "environment": environment,
        "target_is_local": comparison.get("target_is_local") is True,
        "proves_production": verified,
        "provider_called": False,
        "external_write": False,
    }


def sandbox_checkpoint_restore_drill(
    last_known_good: Mapping[str, Any] | None,
    *,
    expected_digest: Any = "",
) -> dict[str, Any]:
    """Exercise a checkpoint restore in memory without persisting it."""
    source = _mapping(last_known_good)
    if not source:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "BLOCKED",
            "passed": False,
            "reason": "CHECKPOINT_MISSING",
            "source_digest": "",
            "restored_digest": "",
            "external_write": False,
            "runtime_mutated": False,
        }
    try:
        source_digest = _canonical_digest(source)
        restored = deepcopy(source)
        restored_digest = _canonical_digest(restored)
    except (TypeError, ValueError, OverflowError):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "BLOCKED",
            "passed": False,
            "reason": "CHECKPOINT_NOT_CANONICAL_JSON",
            "source_digest": "",
            "restored_digest": "",
            "external_write": False,
            "runtime_mutated": False,
        }
    claimed = _clean(expected_digest, 80).lower()
    digest_claim_valid = not claimed or bool(_HEX64.fullmatch(claimed))
    claim_matches = not claimed or claimed == source_digest
    passed = source_digest == restored_digest and digest_claim_valid and claim_matches
    reason = "RESTORE_VERIFIED" if passed else (
        "DIGEST_MALFORMED" if claimed and not digest_claim_valid else
        "DIGEST_MISMATCH" if claimed and not claim_matches else
        "RESTORE_MISMATCH"
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "RESTORED_VERIFIED" if passed else "BLOCKED",
        "passed": passed,
        "reason": reason,
        "source_digest": source_digest,
        "restored_digest": restored_digest,
        "expected_digest": claimed,
        "external_write": False,
        "runtime_mutated": False,
    }


def checkpoint_master_validation_gate(
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return VALIDADO only when all named evidence gates are explicit."""
    payload = _mapping(evidence)
    refs, refs_truncated = _refs(payload.get("evidence_refs"))
    production = _mapping(payload.get("production_identity"))
    rollback = _mapping(payload.get("rollback_drill"))
    digest = _clean(payload.get("checkpoint_digest"), 80).lower()
    gates = {
        "checkpoint_integrity_verified": _exact_true(payload.get("checkpoint_integrity_verified")),
        "checkpoint_ref_present": bool(_clean(payload.get("checkpoint_ref"), 300)),
        "checkpoint_digest_valid": bool(_HEX64.fullmatch(digest)),
        "production_identity_verified": (
            production.get("schema") == SCHEMA
            and _exact_true(production.get("verified"))
            and _exact_true(production.get("proves_production"))
        ),
        "rollback_drill_passed": (
            rollback.get("schema") == SCHEMA
            and rollback.get("state") == "RESTORED_VERIFIED"
            and _exact_true(rollback.get("passed"))
        ),
        "human_validation_approved": _exact_true(payload.get("human_validation_approved")),
        "evidence_refs_present": bool(refs) and not refs_truncated,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    validated = not blockers
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "VALIDADO" if validated else "IMPLEMENTADO / EM VALIDAÇÃO",
        "validated": validated,
        "implemented": True,
        "gates": gates,
        "blockers": blockers,
        "evidence_refs": refs,
        "evidence_refs_truncated": refs_truncated,
        "persists_checkpoint": False,
        "activates_runtime": False,
        "authorizes_merge": False,
        "authorizes_deploy": False,
    }


def business_certification_readiness(
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Assess whether BUSINESS has enough product evidence to enter certification review.

    This is deliberately below specialist certification. It never returns
    CERTIFIED and never enables runtime or external actions.
    """
    payload = _mapping(evidence)
    refs, refs_truncated = _refs(payload.get("evidence_refs"))
    gates = {name: _exact_true(payload.get(name)) for name in BUSINESS_REQUIRED_GATES}
    gates["evidence_refs_present"] = bool(refs) and not refs_truncated
    missing = [name for name, passed in gates.items() if not passed]
    ready = not missing
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "specialist": "BUSINESS",
        "state": BUSINESS_STATE if ready else "NOT_READY",
        "ready_for_certification_review": ready,
        "certification_state": "NOT_CERTIFIED",
        "runtime_capability_available": False,
        "runtime_activated": False,
        "external_action_executed": False,
        "payment_executed": False,
        "publication_executed": False,
        "gates": gates,
        "missing": missing,
        "evidence_refs": refs,
        "evidence_refs_truncated": refs_truncated,
    }


def core_validation_summary(
    *,
    checkpoint: Mapping[str, Any] | None = None,
    business: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint_row = _mapping(checkpoint)
    business_row = _mapping(business)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "checkpoint_state": checkpoint_row.get("state") or "IMPLEMENTADO / EM VALIDAÇÃO",
        "checkpoint_validated": _exact_true(checkpoint_row.get("validated")),
        "business_state": business_row.get("state") or "NOT_READY",
        "business_certification_state": "NOT_CERTIFIED",
        "business_runtime_activated": False,
        "core_runtime_activated": False,
        "real_trading_enabled": False,
        "payment_enabled": False,
        "publication_enabled": False,
        "merge_authorized": False,
        "deploy_authorized": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "CHECKPOINT_STATES",
    "BUSINESS_STATE",
    "BUSINESS_REQUIRED_GATES",
    "production_identity_gate",
    "sandbox_checkpoint_restore_drill",
    "checkpoint_master_validation_gate",
    "business_certification_readiness",
    "core_validation_summary",
]
