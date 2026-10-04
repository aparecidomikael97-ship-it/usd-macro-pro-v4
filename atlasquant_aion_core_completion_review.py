"""AION V2.21 Core Completion Review Gate.

This layer re-verifies a V2.20 Core Certification manifest against the supplied
public certification trust roots, then builds a deterministic owner-review
packet and a Checkpoint Mestre patch candidate.

It never records an owner decision, never freezes the Core, never persists a
checkpoint, never merges/deploys, and never performs external execution.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from atlasquant_aion_core_certification import (
    REQUIRED_DIMENSIONS,
    SCHEMA as CERTIFICATION_SCHEMA,
    certify_core,
)
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_CORE_COMPLETION_REVIEW_V1"
CHECKPOINT_PATCH_SCHEMA = "ATLASQUANT_AION_CORE_COMPLETION_CHECKPOINT_PATCH_V1"
VERSION = 1
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_UNSAFE_CERTIFICATION_FIELDS = (
    "core_complete_claim_allowed",
    "core_frozen",
    "core_freeze_authorized_by_this_module",
    "execution_allowed",
    "worker_armed",
    "merge_authorized",
    "deploy_authorized",
    "external_action_executed",
    "executes_action",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _raw_evidence_from_manifest_row(row: Mapping[str, Any]) -> dict[str, Any]:
    claimed = row.get("claimed_verified")
    if claimed is None:
        claimed = row.get("verified")
    return {
        "schema": row.get("schema"),
        "state": row.get("state"),
        "source": row.get("source"),
        "run_id": row.get("run_id"),
        "commit_sha": row.get("commit_sha"),
        "evidence_digest": row.get("evidence_digest"),
        "test_count": row.get("test_count"),
        "verified": claimed,
        "key_id": row.get("key_id"),
        "key_version": row.get("key_version"),
        "issued_at": row.get("issued_at"),
        "expires_at": row.get("expires_at"),
        "signature_b64": row.get("signature_b64"),
    }


def reverify_certification_manifest(
    manifest: Mapping[str, Any] | None,
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
) -> dict[str, Any]:
    """Rebuild V2.20 from signed evidence instead of trusting manifest booleans."""
    blockers: list[str] = []
    row = dict(manifest or {}) if isinstance(manifest, Mapping) else {}

    if not isinstance(manifest, Mapping):
        blockers.append("CERTIFICATION_MANIFEST_INVALID")
    if row.get("schema") != CERTIFICATION_SCHEMA:
        blockers.append("CERTIFICATION_SCHEMA_MISMATCH")
    if not isinstance(certification_trust_roots, TrustRootRegistry):
        blockers.append("CERTIFICATION_TRUST_ROOT_INVALID")

    target = _clean(row.get("target_commit_sha"), 64).lower()
    if not _SHA_RE.fullmatch(target):
        blockers.append("CERTIFICATION_TARGET_SHA_INVALID")

    evidence = row.get("evidence")
    if not isinstance(evidence, Mapping):
        blockers.append("CERTIFICATION_EVIDENCE_INVALID")
        evidence = {}

    supplied_keys = set(evidence) if isinstance(evidence, Mapping) else set()
    if supplied_keys != set(REQUIRED_DIMENSIONS):
        blockers.append("CERTIFICATION_EVIDENCE_DIMENSION_SET_MISMATCH")

    rebuilt = None
    if not blockers:
        raw_evidence = {
            dimension: _raw_evidence_from_manifest_row(evidence[dimension])
            for dimension in REQUIRED_DIMENSIONS
        }
        try:
            rebuilt = certify_core(
                raw_evidence,
                target_commit_sha=target,
                certification_trust_roots=certification_trust_roots,
                now_ts=now_ts,
                core_freeze_authorized=False,
            )
        except Exception:
            blockers.append("CERTIFICATION_REVERIFY_FAILURE")

    if rebuilt is not None:
        if row.get("manifest_digest") != rebuilt.get("manifest_digest"):
            blockers.append("CERTIFICATION_MANIFEST_DIGEST_MISMATCH")
        if row.get("state") != rebuilt.get("state"):
            blockers.append("CERTIFICATION_STATE_MISMATCH")
        if row.get("certification_candidate") is not rebuilt.get("certification_candidate"):
            blockers.append("CERTIFICATION_CANDIDATE_MISMATCH")
        if row.get("core_complete_candidate") is not rebuilt.get("core_complete_candidate"):
            blockers.append("CORE_COMPLETE_CANDIDATE_MISMATCH")
        if row.get("owner_core_complete_review_required") is not rebuilt.get(
            "owner_core_complete_review_required"
        ):
            blockers.append("OWNER_REVIEW_REQUIREMENT_MISMATCH")
        if rebuilt.get("certification_candidate") is not True:
            blockers.append("CERTIFICATION_NOT_CANDIDATE")

    for field in _UNSAFE_CERTIFICATION_FIELDS:
        if row.get(field) is not False:
            blockers.append(f"UNSAFE_CERTIFICATION_FIELD:{field}")

    if row.get("freeze_requires_explicit_owner_action_outside_certification") is not True:
        blockers.append("EXPLICIT_OWNER_FREEZE_BOUNDARY_MISSING")

    unique = sorted(set(blockers))
    verified = rebuilt is not None and not unique

    return {
        "schema": "ATLASQUANT_AION_CERTIFICATION_REVERIFICATION_V1",
        "target_commit_sha": target,
        "supplied_manifest_digest": _clean(row.get("manifest_digest"), 100),
        "rebuilt_manifest_digest": (
            rebuilt.get("manifest_digest", "") if isinstance(rebuilt, Mapping) else ""
        ),
        "certification_trust_root_binding_digest": (
            rebuilt.get("certification_trust_root_binding_digest", "")
            if isinstance(rebuilt, Mapping)
            else ""
        ),
        "canonical_gates_green": bool(
            isinstance(rebuilt, Mapping) and rebuilt.get("canonical_gates_green") is True
        ),
        "global_worker_readiness_green": bool(
            isinstance(rebuilt, Mapping)
            and rebuilt.get("global_worker_readiness_green") is True
        ),
        "all_evidence_cryptographically_verified": bool(
            isinstance(rebuilt, Mapping)
            and rebuilt.get("all_evidence_cryptographically_verified") is True
        ),
        "certification_verified": verified,
        "blockers": unique,
        "execution_allowed": False,
        "external_action_executed": False,
    }


def _review_material(review: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": review.get("schema"),
        "version": review.get("version"),
        "target_commit_sha": review.get("target_commit_sha"),
        "certification_manifest_digest": review.get("certification_manifest_digest"),
        "certification_trust_root_binding_digest": review.get(
            "certification_trust_root_binding_digest"
        ),
        "certification_verified": review.get("certification_verified"),
        "canonical_gates_green": review.get("canonical_gates_green"),
        "global_worker_readiness_green": review.get("global_worker_readiness_green"),
        "owner_review_ready": review.get("owner_review_ready"),
        "owner_decision_recorded": review.get("owner_decision_recorded"),
        "core_complete": review.get("core_complete"),
        "core_complete_claim_allowed": review.get("core_complete_claim_allowed"),
        "core_freeze_authorized": review.get("core_freeze_authorized"),
        "core_frozen": review.get("core_frozen"),
        "checkpoint_saved": review.get("checkpoint_saved"),
        "automatic_checkpoint_write": review.get("automatic_checkpoint_write"),
        "execution_allowed": review.get("execution_allowed"),
        "worker_armed": review.get("worker_armed"),
        "merge_authorized": review.get("merge_authorized"),
        "deploy_authorized": review.get("deploy_authorized"),
        "external_action_executed": review.get("external_action_executed"),
        "executes_action": review.get("executes_action"),
        "blockers": review.get("blockers"),
        "state": review.get("state"),
    }


def build_core_completion_review(
    certification_manifest: Mapping[str, Any] | None,
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
    expected_target_commit_sha: str,
) -> dict[str, Any]:
    """Build the highest automatic state: READY_FOR_OWNER_REVIEW."""
    expected = _clean(expected_target_commit_sha, 64).lower()
    if not _SHA_RE.fullmatch(expected):
        raise ValueError("expected_target_commit_sha must be a 40-char git SHA")

    verification = reverify_certification_manifest(
        certification_manifest,
        certification_trust_roots=certification_trust_roots,
        now_ts=now_ts,
    )
    blockers = list(verification["blockers"])
    if verification["target_commit_sha"] != expected:
        blockers.append("EXPECTED_TARGET_COMMIT_MISMATCH")
    if verification["certification_verified"] is not True:
        blockers.append("CERTIFICATION_REVERIFICATION_NOT_VERIFIED")

    unique = sorted(set(blockers))
    ready = not unique
    body = {
        "schema": SCHEMA,
        "version": VERSION,
        "target_commit_sha": expected,
        "certification_manifest_digest": verification["supplied_manifest_digest"],
        "certification_trust_root_binding_digest": verification[
            "certification_trust_root_binding_digest"
        ],
        "certification_verified": verification["certification_verified"] is True,
        "canonical_gates_green": verification["canonical_gates_green"] is True,
        "global_worker_readiness_green": verification[
            "global_worker_readiness_green"
        ] is True,
        "owner_review_ready": ready,
        "owner_decision_recorded": False,
        "core_complete": False,
        "core_complete_claim_allowed": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved": False,
        "automatic_checkpoint_write": False,
        "execution_allowed": False,
        "worker_armed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
        "blockers": unique,
        "state": "READY_FOR_OWNER_REVIEW" if ready else "BLOCKED",
    }
    review_digest = _digest(body)
    return {
        **body,
        "review_digest": review_digest,
    }


def build_checkpoint_patch_candidate(
    certification_manifest: Mapping[str, Any] | None,
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
    expected_target_commit_sha: str,
) -> dict[str, Any]:
    """Reverify signed V2.20 evidence and build a Checkpoint patch candidate.

    A caller-supplied review object is intentionally not accepted as authority.
    The review is rebuilt internally from the signed certification manifest on
    every call.
    """
    review = build_core_completion_review(
        certification_manifest,
        certification_trust_roots=certification_trust_roots,
        now_ts=now_ts,
        expected_target_commit_sha=expected_target_commit_sha,
    )
    if review.get("review_digest") != _digest(_review_material(review)):
        raise ValueError("internal core completion review digest mismatch")

    for field in (
        "owner_decision_recorded",
        "core_complete",
        "core_complete_claim_allowed",
        "core_freeze_authorized",
        "core_frozen",
        "checkpoint_saved",
        "automatic_checkpoint_write",
        "execution_allowed",
        "worker_armed",
        "merge_authorized",
        "deploy_authorized",
        "external_action_executed",
        "executes_action",
    ):
        if review.get(field) is not False:
            raise ValueError(f"unsafe internal review field: {field}")

    expected_ready = review.get("state") == "READY_FOR_OWNER_REVIEW"
    if review.get("owner_review_ready") is not expected_ready:
        raise ValueError("internal owner review readiness mismatch")

    checkpoint_record = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": review["state"],
        "target_commit_sha": review["target_commit_sha"],
        "certification_manifest_digest": review["certification_manifest_digest"],
        "certification_trust_root_binding_digest": review[
            "certification_trust_root_binding_digest"
        ],
        "review_digest": review["review_digest"],
        "blockers": list(review.get("blockers") or []),
        "owner_review_ready": review["owner_review_ready"] is True,
        "owner_decision_recorded": False,
        "core_complete": False,
        "core_frozen": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }
    patch = {"aion_core_completion_review": checkpoint_record}
    return {
        "schema": CHECKPOINT_PATCH_SCHEMA,
        "patch": patch,
        "patch_digest": _digest(patch),
        "recommended_event_id": (
            "aion-core-completion-review:"
            + review["target_commit_sha"][:12]
            + ":"
            + review["review_digest"].split(":", 1)[-1][:16]
        ),
        "requires_explicit_checkpoint_save": True,
        "automatic_checkpoint_write": False,
        "checkpoint_saved": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "CHECKPOINT_PATCH_SCHEMA",
    "VERSION",
    "reverify_certification_manifest",
    "build_core_completion_review",
    "build_checkpoint_patch_candidate",
]
