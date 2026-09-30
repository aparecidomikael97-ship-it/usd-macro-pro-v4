"""AION BUSINESS consolidation dry-run V1.

Read-only administrative runbook built on top of the frozen Business Draft PR
stack review. It consumes evidence supplied by a trusted caller and never calls
GitHub, merges, rebases, deploys, enables auto-merge, changes runtime state or
touches client/provider data.

The highest automatic state is READY_FOR_EXPLICIT_ADMIN_DECISION.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_business_stack_consolidation import canonical_stack_manifest

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_DRY_RUN_V1"
VERSION = "1"

LIVE_REVALIDATION_GATES = (
    "repository_identity_verified",
    "all_prs_open",
    "all_prs_draft",
    "all_head_shas_unchanged",
    "all_base_branches_unchanged",
    "all_prs_mergeable",
    "all_required_checks_success",
    "all_ui_checks_success",
)

STOP_CONDITIONS = (
    "repository identity mismatch",
    "PR closed or merged unexpectedly",
    "PR no longer Draft before explicit authorization",
    "head SHA drift",
    "base branch drift",
    "mergeability false or unknown",
    "required check failed, cancelled, skipped or pending",
    "UI/mobile validation failed or pending",
    "stack order changed",
    "explicit administrative authorization absent",
)


def _exact_true(value: Any) -> bool:
    return type(value) is bool and value is True


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def live_revalidation_snapshot(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    source = _mapping(evidence)
    rows = [
        {"gate": gate, "passed": _exact_true(source.get(gate))}
        for gate in LIVE_REVALIDATION_GATES
    ]
    missing = [row["gate"] for row in rows if not row["passed"]]
    complete = bool(rows and not missing)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LIVE_REVALIDATED" if complete else "LIVE_REVALIDATION_REQUIRED",
        "complete": complete,
        "rows": rows,
        "passed_count": sum(1 for row in rows if row["passed"]),
        "total": len(rows),
        "missing": missing,
        "evidence_source": _clean(source.get("evidence_source"), 180),
        "observed_at": _clean(source.get("observed_at"), 80),
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def _stack_is_ready(stack_validation: Mapping[str, Any] | None) -> bool:
    row = _mapping(stack_validation)
    return bool(
        row.get("state") == "READY_FOR_ADMIN_REVIEW"
        and row.get("complete") is True
        and row.get("merge_authorized") is False
        and row.get("deploy_authorized") is False
        and row.get("runtime_activation_authorized") is False
    )


def build_consolidation_runbook(
    stack_validation: Mapping[str, Any] | None,
    live_revalidation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    frozen_ready = _stack_is_ready(stack_validation)
    live = _mapping(live_revalidation)
    live_ready = bool(
        live.get("schema") == SCHEMA
        and live.get("state") == "LIVE_REVALIDATED"
        and live.get("complete") is True
        and live.get("merge_authorized") is False
    )

    if not frozen_ready:
        state = "STACK_REVIEW_BLOCKED"
    elif not live_ready:
        state = "AWAITING_LIVE_REVALIDATION"
    else:
        state = "READY_FOR_EXPLICIT_ADMIN_DECISION"

    steps = []
    if frozen_ready:
        for order, item in enumerate(canonical_stack_manifest(), start=1):
            steps.append({
                "order": order,
                "pr": int(item["pr"]),
                "title": item["title"],
                "expected_head_branch": item["head_branch"],
                "expected_base_branch": item["base_branch"],
                "expected_head_sha": item["head_sha"],
                "before_hypothetical_merge": [
                    "revalidate exact head SHA",
                    "revalidate exact base branch",
                    "confirm PR remains open and Draft",
                    "confirm mergeability is true",
                    "confirm required checks are success",
                    "confirm UI/mobile checks when applicable",
                    "confirm explicit administrative authorization exists",
                ],
                "hypothetical_action": "MERGE_ONLY_IF_SEPARATELY_AUTHORIZED",
                "after_hypothetical_merge": [
                    "stop sequence immediately if merge result is unexpected",
                    "revalidate target branch SHA",
                    "re-run required CI before considering next PR",
                    "verify no runtime/deploy authority changed",
                ],
                "stop_on_failure": True,
                "executes_action": False,
            })

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "frozen_stack_ready": frozen_ready,
        "live_revalidation_ready": live_ready,
        "step_count": len(steps),
        "steps": steps,
        "stop_conditions": list(STOP_CONDITIONS),
        "requires_explicit_admin_decision": state == "READY_FOR_EXPLICIT_ADMIN_DECISION",
        "requires_per_step_live_revalidation": True,
        "requires_post_step_ci": True,
        "requires_final_main_ci": True,
        "requires_final_production_sha_verification": True,
        "merge_authorized": False,
        "auto_merge_enabled": False,
        "rebase_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def administrative_decision_packet(
    runbook: Mapping[str, Any] | None,
    *,
    reviewer: Any,
    note: Any,
) -> dict[str, Any]:
    row = _mapping(runbook)
    reviewer_clean = _clean(reviewer, 120)
    note_clean = _clean(note, 500)
    eligible = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "READY_FOR_EXPLICIT_ADMIN_DECISION"
        and row.get("requires_explicit_admin_decision") is True
        and reviewer_clean
        and note_clean
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_ADMIN_DECISION_PACKET_V1",
        "state": "ADMIN_DECISION_REQUIRED" if eligible else "BLOCKED",
        "eligible_for_human_decision": eligible,
        "reviewer": reviewer_clean if eligible else "",
        "note": note_clean if eligible else "",
        "merge_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "LIVE_REVALIDATION_GATES",
    "STOP_CONDITIONS",
    "live_revalidation_snapshot",
    "build_consolidation_runbook",
    "administrative_decision_packet",
]
