"""AION BUSINESS consolidation merge-execution preflight V1.

Read-only preflight for the physical merge boundary. It verifies that the exact
decision request, explicit authorization record, live revalidation, sequence
position, main SHA and runtime posture are coherent.

Even a fully passing preflight stops at MERGE_EXECUTION_REVIEW_REQUIRED. This
module never calls GitHub and never merges, rebases, deploys or activates
runtime.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re

from atlasquant_aion_business_stack_consolidation_v2 import canonical_stack_manifest
from atlasquant_aion_business_consolidation_dry_run_v2 import SCHEMA as DRY_RUN_SCHEMA
from atlasquant_aion_business_consolidation_decision_request import (
    SCHEMA as DECISION_REQUEST_SCHEMA,
)
from atlasquant_aion_business_consolidation_authorization_record import (
    SCHEMA as AUTHORIZATION_RECORD_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_EXECUTION_PREFLIGHT_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

PREFLIGHT_REQUIREMENTS = (
    "dry_run_ready",
    "decision_request_bound",
    "explicit_authorization_record_verified",
    "live_revalidation_current",
    "stack_prefix_valid",
    "target_is_next_pr",
    "main_sha_matches_expected",
    "business_runtime_off",
    "deploy_authority_absent",
)

POST_STEP_REQUIREMENTS = (
    "verify merge result SHA",
    "run full required CI",
    "re-run UI/mobile checks when applicable",
    "revalidate BUSINESS runtime remains OFF",
    "preserve previous main SHA as rollback reference",
    "stop immediately on drift or regression",
    "refresh decision evidence before next PR",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _int_sequence(value: Any, limit: int = 100) -> list[int]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    out = []
    for raw in list(value)[:limit]:
        if isinstance(raw, int) and not isinstance(raw, bool):
            out.append(raw)
        else:
            return []
    return out


def execution_preflight_template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EVIDENCE_REQUIRED",
        "requirements": list(PREFLIGHT_REQUIREMENTS),
        "post_step_requirements": list(POST_STEP_REQUIREMENTS),
        "merge_execution_authorized": False,
        "auto_merge_enabled": False,
        "rebase_authorized": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def build_merge_execution_preflight(
    runbook: Mapping[str, Any] | None,
    decision_request: Mapping[str, Any] | None,
    authorization_record: Mapping[str, Any] | None,
    live_revalidation: Mapping[str, Any] | None,
    *,
    target_pr: Any,
    completed_prs: Any,
    observed_main_sha: Any,
    expected_main_sha: Any,
    business_runtime_off: Any,
    deploy_authority_absent: Any,
) -> dict[str, Any]:
    run = _mapping(runbook)
    request = _mapping(decision_request)
    authorization = _mapping(authorization_record)
    live = _mapping(live_revalidation)

    stack = canonical_stack_manifest()
    stack_prs = [int(item["pr"]) for item in stack]
    completed = _int_sequence(completed_prs, len(stack_prs))
    prefix_valid = completed == stack_prs[: len(completed)] and len(set(completed)) == len(completed)
    expected_next_pr = stack_prs[len(completed)] if prefix_valid and len(completed) < len(stack_prs) else None

    target = target_pr if isinstance(target_pr, int) and not isinstance(target_pr, bool) else None
    observed_sha = _clean(observed_main_sha, 80).lower()
    expected_sha = _clean(expected_main_sha, 80).lower()
    request_digest = _clean(request.get("request_digest"), 128).lower()
    authorization_request_digest = _clean(authorization.get("request_digest"), 128).lower()

    gates = {
        "dry_run_ready": bool(
            run.get("schema") == DRY_RUN_SCHEMA
            and run.get("state") == "READY_FOR_EXPLICIT_ADMIN_DECISION"
            and run.get("requires_explicit_admin_decision") is True
            and run.get("merge_authorized") is False
        ),
        "decision_request_bound": bool(
            request.get("schema") == DECISION_REQUEST_SCHEMA
            and request.get("state") == "HUMAN_AUTHORIZATION_RECORD_REQUIRED"
            and request.get("eligible_for_explicit_human_authorization") is True
            and _DIGEST64.fullmatch(request_digest)
            and request.get("merge_authorized") is False
        ),
        "explicit_authorization_record_verified": bool(
            authorization.get("schema") == AUTHORIZATION_RECORD_SCHEMA
            and authorization.get("state") == "EXPLICIT_AUTHORIZATION_RECORD_VERIFIED"
            and authorization.get("authorization_record_verified") is True
            and authorization_request_digest == request_digest
            and _DIGEST64.fullmatch(_clean(authorization.get("record_digest"), 128).lower())
            and authorization.get("merge_execution_authorized") is False
        ),
        "live_revalidation_current": bool(
            live.get("schema") == DRY_RUN_SCHEMA
            and live.get("state") == "LIVE_REVALIDATED"
            and live.get("complete") is True
            and live.get("merge_authorized") is False
        ),
        "stack_prefix_valid": prefix_valid,
        "target_is_next_pr": bool(expected_next_pr is not None and target == expected_next_pr),
        "main_sha_matches_expected": bool(
            _SHA40.fullmatch(observed_sha)
            and _SHA40.fullmatch(expected_sha)
            and observed_sha == expected_sha
        ),
        "business_runtime_off": _exact_true(business_runtime_off),
        "deploy_authority_absent": _exact_true(deploy_authority_absent),
    }

    blockers = [name for name in PREFLIGHT_REQUIREMENTS if not gates.get(name)]
    ready = not blockers
    target_row = next((dict(item) for item in stack if int(item["pr"]) == target), {}) if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "MERGE_EXECUTION_REVIEW_REQUIRED" if ready else "BLOCKED",
        "ready_for_separate_execution_review": ready,
        "gates": gates,
        "blockers": blockers,
        "completed_prs": completed if prefix_valid else [],
        "next_expected_pr": expected_next_pr,
        "target_pr": target if ready else None,
        "target": target_row,
        "pre_merge_main_sha": observed_sha if ready else "",
        "rollback_reference_sha": observed_sha if ready else "",
        "request_digest": request_digest if ready else "",
        "post_step_requirements": list(POST_STEP_REQUIREMENTS) if ready else [],
        "stop_on_any_drift": True,
        "requires_fresh_revalidation_at_action_time": True,
        "merge_execution_authorized": False,
        "auto_merge_enabled": False,
        "rebase_authorized": False,
        "deploy_authorized": False,
        "pilot_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "PREFLIGHT_REQUIREMENTS",
    "POST_STEP_REQUIREMENTS",
    "execution_preflight_template",
    "build_merge_execution_preflight",
]
