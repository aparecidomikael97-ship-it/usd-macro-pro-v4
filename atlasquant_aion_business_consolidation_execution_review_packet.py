"""AION BUSINESS consolidation execution review packet V1.

Builds a frozen, digest-bound, read-only dossier from a successful execution
preflight. It does not create or infer authorization and never performs GitHub
actions.

The highest state is READY_FOR_HUMAN_EXECUTION_REVIEW.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_consolidation_execution_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_EXECUTION_REVIEW_PACKET_V1"
VERSION = "1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

REVIEW_SECTIONS = (
    "identity",
    "target",
    "authorization_binding",
    "live_evidence",
    "rollback",
    "runtime_posture",
    "post_step_validation",
    "stop_conditions",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def review_packet_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PREFLIGHT_REQUIRED",
        "sections": list(REVIEW_SECTIONS),
        "human_execution_review_required": True,
        "authorization_created": False,
        "merge_execution_authorized": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def build_execution_review_packet(
    preflight: Mapping[str, Any] | None,
    *,
    repository: Any,
    candidate_head_sha: Any,
    base_head_sha: Any,
    evidence_ref: Any,
    reviewer: Any,
) -> dict[str, Any]:
    row = _mapping(preflight)
    repo = _clean(repository, 180)
    candidate = _clean(candidate_head_sha, 80).lower()
    base = _clean(base_head_sha, 80).lower()
    evidence = _clean(evidence_ref, 300)
    reviewer_clean = _clean(reviewer, 120)

    blockers = []
    if row.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("preflight_schema")
    if row.get("state") != "MERGE_EXECUTION_REVIEW_REQUIRED":
        blockers.append("preflight_state")
    if row.get("ready_for_separate_execution_review") is not True:
        blockers.append("execution_review_gate")
    if row.get("merge_execution_authorized") is not False:
        blockers.append("unexpected_merge_authority")
    if row.get("executes_action") is not False:
        blockers.append("unexpected_execution_path")
    target = _mapping(row.get("target"))
    target_sha = _clean(target.get("head_sha"), 80).lower()
    if not _SHA40.fullmatch(candidate) or candidate != target_sha:
        blockers.append("candidate_head_sha")
    if not _SHA40.fullmatch(base):
        blockers.append("base_head_sha")
    rollback_sha = _clean(row.get("rollback_reference_sha"), 80).lower()
    if not _SHA40.fullmatch(rollback_sha):
        blockers.append("rollback_reference_sha")
    request_digest = _clean(row.get("request_digest"), 128).lower()
    if not _DIGEST64.fullmatch(request_digest):
        blockers.append("request_digest")
    if not evidence:
        blockers.append("evidence_ref")
    if not reviewer_clean:
        blockers.append("reviewer")

    ready = not blockers
    payload = {
        "repository": repo,
        "target_pr": row.get("target_pr"),
        "target_head_sha": candidate,
        "base_head_sha": base,
        "pre_merge_main_sha": _clean(row.get("pre_merge_main_sha"), 80).lower(),
        "rollback_reference_sha": rollback_sha,
        "request_digest": request_digest,
        "evidence_ref": evidence,
        "reviewer": reviewer_clean,
        "post_step_requirements": list(row.get("post_step_requirements") or []),
        "stop_on_any_drift": row.get("stop_on_any_drift") is True,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "READY_FOR_HUMAN_EXECUTION_REVIEW" if ready else "BLOCKED",
        "ready_for_human_execution_review": ready,
        "blockers": blockers,
        "sections": list(REVIEW_SECTIONS),
        "packet_digest": _digest(payload) if ready else "",
        "payload": payload,
        "target_pr": row.get("target_pr") if ready else None,
        "target_head_sha": candidate if ready else "",
        "rollback_reference_sha": rollback_sha if ready else "",
        "request_digest": request_digest if ready else "",
        "human_execution_review_required": True,
        "authorization_created": False,
        "merge_execution_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def verify_review_packet(
    packet: Mapping[str, Any] | None,
    *,
    expected_packet_digest: Any,
    target_head_sha: Any,
    rollback_reference_sha: Any,
) -> dict[str, Any]:
    row = _mapping(packet)
    payload = _mapping(row.get("payload"))
    digest = _clean(row.get("packet_digest"), 128).lower()
    expected = _clean(expected_packet_digest, 128).lower()
    target = _clean(target_head_sha, 80).lower()
    rollback = _clean(rollback_reference_sha, 80).lower()

    digest_ok = bool(payload and _DIGEST64.fullmatch(digest) and _digest(payload) == digest)
    match = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_HUMAN_EXECUTION_REVIEW"
        and row.get("ready_for_human_execution_review") is True
        and digest_ok
        and digest == expected
        and row.get("target_head_sha") == target
        and row.get("rollback_reference_sha") == rollback
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_EXECUTION_REVIEW_PACKET_BINDING_V1",
        "state": "PACKET_BINDING_MATCH" if match else "PACKET_BINDING_MISMATCH",
        "binding_match": match,
        "merge_execution_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "REVIEW_SECTIONS",
    "review_packet_template",
    "build_execution_review_packet",
    "verify_review_packet",
]
