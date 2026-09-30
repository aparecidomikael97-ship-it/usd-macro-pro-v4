"""AION BUSINESS consolidation decision request V1.

Creates a non-executing, digest-bound request for a future explicit human
authorization decision. The request binds the exact repository, candidate SHA,
base SHA, frozen stack bundle digest and live-evidence reference.

A valid request never authorizes merge, deploy, pilot or runtime. Any binding
drift invalidates the request and requires a new review.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json
import re

from atlasquant_aion_business_consolidation_dry_run_v2 import SCHEMA as DRY_RUN_SCHEMA

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_DECISION_REQUEST_V1"
VERSION = "1"
EXPECTED_REPOSITORY = "aparecidomikael97-ship-it/usd-macro-pro-v4"
DECISION_SCOPE = "STACK_CONSOLIDATION_394_412_ONLY"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


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


def decision_request_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "INPUT_REQUIRED",
        "required_bindings": [
            "repository",
            "candidate_sha",
            "base_sha",
            "bundle_digest",
            "live_evidence_ref",
            "reviewer",
            "decision_scope",
        ],
        "expected_repository": EXPECTED_REPOSITORY,
        "expected_decision_scope": DECISION_SCOPE,
        "authorization_recorded": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def build_decision_request(
    runbook: Mapping[str, Any] | None,
    bundle: Mapping[str, Any] | None,
    *,
    repository: Any,
    candidate_sha: Any,
    base_sha: Any,
    live_evidence_ref: Any,
    reviewer: Any,
    decision_scope: Any = DECISION_SCOPE,
) -> dict[str, Any]:
    run = _mapping(runbook)
    frozen = _mapping(bundle)
    repo = _clean(repository, 180)
    candidate = _clean(candidate_sha, 80).lower()
    base = _clean(base_sha, 80).lower()
    bundle_digest = _clean(frozen.get("bundle_digest"), 128).lower()
    evidence_ref = _clean(live_evidence_ref, 300)
    reviewer_clean = _clean(reviewer, 120)
    scope = _clean(decision_scope, 120)

    blockers = []
    if run.get("schema") != DRY_RUN_SCHEMA:
        blockers.append("dry_run_schema")
    if run.get("state") != "READY_FOR_EXPLICIT_ADMIN_DECISION":
        blockers.append("dry_run_state")
    if run.get("requires_explicit_admin_decision") is not True:
        blockers.append("explicit_admin_decision_gate")
    if run.get("merge_authorized") is not False:
        blockers.append("unexpected_merge_authority")
    if frozen.get("state") != "BUNDLE_FROZEN_FOR_REVIEW":
        blockers.append("bundle_state")
    if not _DIGEST64.fullmatch(bundle_digest):
        blockers.append("bundle_digest")
    if repo != EXPECTED_REPOSITORY:
        blockers.append("repository")
    if not _SHA40.fullmatch(candidate):
        blockers.append("candidate_sha")
    if not _SHA40.fullmatch(base):
        blockers.append("base_sha")
    if candidate and base and candidate == base:
        blockers.append("candidate_base_same_sha")
    if not evidence_ref:
        blockers.append("live_evidence_ref")
    if not reviewer_clean:
        blockers.append("reviewer")
    if scope != DECISION_SCOPE:
        blockers.append("decision_scope")

    eligible = not blockers
    binding_payload = {
        "repository": repo,
        "candidate_sha": candidate,
        "base_sha": base,
        "bundle_digest": bundle_digest,
        "live_evidence_ref": evidence_ref,
        "decision_scope": scope,
    } if eligible else {}
    request_digest = _digest(binding_payload) if eligible else ""

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED" if eligible else "BLOCKED",
        "eligible_for_explicit_human_authorization": eligible,
        "blockers": blockers,
        "repository": repo if eligible else "",
        "candidate_sha": candidate if eligible else "",
        "base_sha": base if eligible else "",
        "bundle_digest": bundle_digest if eligible else "",
        "live_evidence_ref": evidence_ref if eligible else "",
        "reviewer": reviewer_clean if eligible else "",
        "decision_scope": scope if eligible else "",
        "request_digest": request_digest,
        "binding_payload": binding_payload,
        "invalidated_by_any_binding_drift": True,
        "revalidation_required_before_every_step": True,
        "authorization_recorded": False,
        "merge_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def verify_decision_binding(
    request: Mapping[str, Any] | None,
    *,
    repository: Any,
    candidate_sha: Any,
    base_sha: Any,
    bundle_digest: Any,
    live_evidence_ref: Any,
) -> dict[str, Any]:
    row = _mapping(request)
    observed = {
        "repository": _clean(repository, 180),
        "candidate_sha": _clean(candidate_sha, 80).lower(),
        "base_sha": _clean(base_sha, 80).lower(),
        "bundle_digest": _clean(bundle_digest, 128).lower(),
        "live_evidence_ref": _clean(live_evidence_ref, 300),
        "decision_scope": _clean(row.get("decision_scope"), 120),
    }
    expected = _mapping(row.get("binding_payload"))
    request_digest = _clean(row.get("request_digest"), 128).lower()
    digest_ok = bool(
        expected
        and _DIGEST64.fullmatch(request_digest)
        and _digest(expected) == request_digest
    )
    match = bool(
        row.get("state") == "HUMAN_AUTHORIZATION_RECORD_REQUIRED"
        and row.get("eligible_for_explicit_human_authorization") is True
        and digest_ok
        and observed == expected
    )
    mismatches = [
        key for key in (
            "repository",
            "candidate_sha",
            "base_sha",
            "bundle_digest",
            "live_evidence_ref",
            "decision_scope",
        )
        if expected.get(key) != observed.get(key)
    ]
    if not digest_ok:
        mismatches.append("request_digest")

    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_DECISION_BINDING_V1",
        "state": "BINDING_MATCH" if match else "BINDING_MISMATCH",
        "binding_match": match,
        "mismatches": sorted(set(mismatches)),
        "authorization_recorded": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "EXPECTED_REPOSITORY",
    "DECISION_SCOPE",
    "decision_request_template",
    "build_decision_request",
    "verify_decision_binding",
]
