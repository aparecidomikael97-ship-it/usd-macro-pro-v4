"""AION Owner Stack Merge Ceremony Dry-Run V1.

Pure simulation for the future #1015-#1029 merge ceremony.

The simulator exercises:
- strict parent-before-child sequencing;
- virtual main advancement;
- child retarget/revalidation semantics;
- per-step gate and file-delta checks;
- stop conditions;
- virtual merge journal;
- reverse-dependency rollback planning.

It never changes GitHub state. All SHAs produced here are synthetic simulation
identifiers, not Git commit objects.

Maximum positive state:
DRY_RUN_SEQUENCE_COMPLETED

This is not merge authorization, repository mutation, production readiness or
proof that a real retarget/merge/revert succeeded.
"""
from __future__ import annotations

from hashlib import sha1, sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import (
    PINNED_MAIN_SHA,
    STACK,
)
from atlasquant_aion_owner_stack_merge_rollback_recovery_v1 import (
    PINNED_MAIN_TREE_SHA,
    rollback_order,
)


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_CEREMONY_DRY_RUN_V1"
ROLLBACK_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_ROLLBACK_DRY_RUN_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_CEREMONY_DRY_RUN_POLICY_V1"

SUPPORTED_FAULTS = (
    "MAIN_DRIFT",
    "HEAD_DRIFT",
    "BASE_DRIFT",
    "FILE_DELTA_DRIFT",
    "DELETION_DETECTED",
    "GATE_FAILURE",
    "OWNER_AUTHORIZATION_MISSING",
    "DRAFT_TRANSITION_NOT_AUTHORIZED",
    "PARENT_NOT_CONFIRMED_IN_MAIN",
    "RETARGET_CONFLICT",
    "POST_RETARGET_DIFF_DRIFT",
    "POST_RETARGET_GATE_FAILURE",
    "MERGE_CONFLICT",
    "UNEXPECTED_DEPLOY",
    "UNEXPECTED_WORKER_ACTIVATION",
    "UNEXPECTED_PROVIDER_ACTIVATION",
)


def _clean(value: Any, limit: int = 300) -> str:
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


def _virtual_git_sha(kind: str, material: Mapping[str, Any]) -> str:
    """Return a deterministic 40-hex simulation identifier, never a real Git write."""
    payload = {
        "simulation_kind": kind,
        "material": dict(material),
    }
    return sha1(_canonical(payload).encode("utf-8")).hexdigest()


def _fault_map(
    faults: Mapping[Any, Sequence[Any]] | None,
) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    if not isinstance(faults, Mapping):
        return out
    for raw_number, raw_values in faults.items():
        try:
            number = int(raw_number)
        except Exception:
            continue
        values = raw_values if isinstance(raw_values, (list, tuple, set)) else []
        cleaned = {
            _clean(value, 100).upper()
            for value in values
            if _clean(value, 100).upper() in SUPPORTED_FAULTS
        }
        if cleaned:
            out[number] = cleaned
    return out


def _validate_upstream(
    pre_merge_readiness: Mapping[str, Any] | None,
    merge_sequence_plan: Mapping[str, Any] | None,
    rollback_plan: Mapping[str, Any] | None,
) -> list[str]:
    readiness = dict(pre_merge_readiness or {})
    sequence = dict(merge_sequence_plan or {})
    rollback = dict(rollback_plan or {})
    blockers: list[str] = []

    if readiness.get("state") != "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW":
        blockers.append("VALID_PRE_MERGE_READINESS_REQUIRED")
    if readiness.get("merge_authorized") is not False:
        blockers.append("READINESS_MUST_NOT_AUTHORIZE_MERGE")

    if sequence.get("state") != "MERGE_SEQUENCE_PLAN_READY":
        blockers.append("VALID_MERGE_SEQUENCE_PLAN_REQUIRED")
    if sequence.get("step_count") != len(STACK):
        blockers.append("MERGE_SEQUENCE_STEP_COUNT_MISMATCH")
    if sequence.get("merge_authorized") is not False:
        blockers.append("SEQUENCE_MUST_NOT_AUTHORIZE_MERGE")

    if rollback.get("state") != "READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW":
        blockers.append("VALID_ROLLBACK_PLAN_REQUIRED")
    if rollback.get("anchor_main_sha") != PINNED_MAIN_SHA:
        blockers.append("ROLLBACK_MAIN_ANCHOR_MISMATCH")
    if rollback.get("anchor_main_tree_sha") != PINNED_MAIN_TREE_SHA:
        blockers.append("ROLLBACK_TREE_ANCHOR_MISMATCH")
    if rollback.get("rollback_authorized") is not False:
        blockers.append("ROLLBACK_PLAN_MUST_NOT_AUTHORIZE_ROLLBACK")

    return blockers


def simulate_merge_ceremony(
    pre_merge_readiness: Mapping[str, Any] | None,
    merge_sequence_plan: Mapping[str, Any] | None,
    rollback_plan: Mapping[str, Any] | None,
    *,
    injected_faults: Mapping[Any, Sequence[Any]] | None = None,
) -> dict[str, Any]:
    """Simulate all merge transitions without touching repository state."""
    blockers = _validate_upstream(
        pre_merge_readiness,
        merge_sequence_plan,
        rollback_plan,
    )
    faults = _fault_map(injected_faults)

    current_main_sha = PINNED_MAIN_SHA
    current_tree_sha = PINNED_MAIN_TREE_SHA
    completed: list[int] = []
    rows: list[dict[str, Any]] = []
    stop_pr: int | None = None

    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "steps": [],
            "completed_prs": [],
            "stop_pr": None,
            "synthetic_only": True,
            "repository_mutation_performed": False,
            "actual_merge_executed": False,
            "actual_retarget_executed": False,
            "actual_rebase_executed": False,
            "actual_revert_executed": False,
            "deploy_executed": False,
            "worker_activated": False,
            "provider_activated": False,
            "merge_authorized": False,
            "executes_action": False,
        }

    for index, item in enumerate(STACK):
        number = item["number"]
        step_faults = faults.get(number, set())
        step_blockers: list[str] = []

        parent = STACK[index - 1] if index else None
        expected_parent_confirmed = parent is None or parent["number"] in completed

        observed_main_sha = current_main_sha
        if "MAIN_DRIFT" in step_faults:
            observed_main_sha = "0" * 40
            step_blockers.append("MAIN_DRIFT")

        observed_head_sha = item["head_sha"]
        if "HEAD_DRIFT" in step_faults:
            observed_head_sha = "1" * 40
            step_blockers.append("HEAD_DRIFT")

        observed_base = item["base"]
        if "BASE_DRIFT" in step_faults:
            observed_base = "unexpected/base"
            step_blockers.append("BASE_DRIFT")

        if "FILE_DELTA_DRIFT" in step_faults:
            step_blockers.append("FILE_DELTA_DRIFT")
        if "DELETION_DETECTED" in step_faults:
            step_blockers.append("DELETION_DETECTED")
        if "GATE_FAILURE" in step_faults:
            step_blockers.append("GATE_FAILURE")
        if "OWNER_AUTHORIZATION_MISSING" in step_faults:
            step_blockers.append("OWNER_AUTHORIZATION_MISSING")
        if "DRAFT_TRANSITION_NOT_AUTHORIZED" in step_faults:
            step_blockers.append("DRAFT_TRANSITION_NOT_AUTHORIZED")
        if not expected_parent_confirmed or "PARENT_NOT_CONFIRMED_IN_MAIN" in step_faults:
            step_blockers.append("PARENT_NOT_CONFIRMED_IN_MAIN")

        child_requires_retarget = parent is not None
        if child_requires_retarget:
            if "RETARGET_CONFLICT" in step_faults:
                step_blockers.append("RETARGET_CONFLICT")
            if "POST_RETARGET_DIFF_DRIFT" in step_faults:
                step_blockers.append("POST_RETARGET_DIFF_DRIFT")
            if "POST_RETARGET_GATE_FAILURE" in step_faults:
                step_blockers.append("POST_RETARGET_GATE_FAILURE")

        if "MERGE_CONFLICT" in step_faults:
            step_blockers.append("MERGE_CONFLICT")
        if "UNEXPECTED_DEPLOY" in step_faults:
            step_blockers.append("UNEXPECTED_DEPLOY")
        if "UNEXPECTED_WORKER_ACTIVATION" in step_faults:
            step_blockers.append("UNEXPECTED_WORKER_ACTIVATION")
        if "UNEXPECTED_PROVIDER_ACTIVATION" in step_faults:
            step_blockers.append("UNEXPECTED_PROVIDER_ACTIVATION")

        step_blockers = list(dict.fromkeys(step_blockers))
        pre_sha = current_main_sha
        pre_tree = current_tree_sha

        if step_blockers:
            stop_pr = number
            rows.append(
                {
                    "order": index + 1,
                    "pr_number": number,
                    "state": "STOPPED",
                    "blockers": step_blockers,
                    "virtual_pre_main_sha": pre_sha,
                    "virtual_pre_tree_sha": pre_tree,
                    "virtual_post_main_sha": "",
                    "virtual_post_tree_sha": "",
                    "parent_confirmed_in_virtual_main": expected_parent_confirmed,
                    "synthetic_owner_authorization_simulated": (
                        "OWNER_AUTHORIZATION_MISSING" not in step_faults
                    ),
                    "real_owner_authorization_used": False,
                    "draft_transition_simulated": True,
                    "actual_draft_transition_performed": False,
                    "child_retarget_required": child_requires_retarget,
                    "retarget_simulated": child_requires_retarget,
                    "actual_retarget_performed": False,
                    "post_retarget_diff_exact": (
                        "POST_RETARGET_DIFF_DRIFT" not in step_faults
                    ),
                    "post_retarget_gate_green": (
                        "POST_RETARGET_GATE_FAILURE" not in step_faults
                    ),
                    "merge_simulated": False,
                    "actual_merge_performed": False,
                    "repository_mutation_performed": False,
                }
            )
            break

        virtual_tree = _virtual_git_sha(
            "TREE",
            {
                "pre_tree": pre_tree,
                "pr_number": number,
                "head_sha": item["head_sha"],
                "files": list(item["files"]),
            },
        )
        virtual_main = _virtual_git_sha(
            "COMMIT",
            {
                "pre_main": pre_sha,
                "post_tree": virtual_tree,
                "pr_number": number,
                "head_sha": item["head_sha"],
                "strategy": "SYNTHETIC_SQUASH_EQUIVALENT",
            },
        )

        rows.append(
            {
                "order": index + 1,
                "pr_number": number,
                "state": "SIMULATED_MERGE_VERIFIED",
                "blockers": [],
                "virtual_pre_main_sha": pre_sha,
                "virtual_pre_tree_sha": pre_tree,
                "virtual_post_main_sha": virtual_main,
                "virtual_post_tree_sha": virtual_tree,
                "virtual_merge_commit_sha": virtual_main,
                "observed_source_head_sha": observed_head_sha,
                "observed_source_base": observed_base,
                "expected_file_delta": list(item["files"]),
                "file_delta_exact": True,
                "deletions_present": False,
                "required_gates_green": True,
                "parent_confirmed_in_virtual_main": expected_parent_confirmed,
                "synthetic_owner_authorization_simulated": True,
                "real_owner_authorization_used": False,
                "draft_transition_simulated": True,
                "actual_draft_transition_performed": False,
                "child_retarget_required": child_requires_retarget,
                "retarget_simulated": child_requires_retarget,
                "retarget_target": "main" if child_requires_retarget else item["base"],
                "actual_retarget_performed": False,
                "actual_rebase_performed": False,
                "post_retarget_diff_exact": True,
                "post_retarget_gate_green": True,
                "old_readiness_reused_after_virtual_base_change": False,
                "fresh_virtual_revalidation_performed": True,
                "merge_simulated": True,
                "actual_merge_performed": False,
                "deploy_executed": False,
                "worker_activated": False,
                "provider_activated": False,
                "repository_mutation_performed": False,
            }
        )
        completed.append(number)
        current_main_sha = virtual_main
        current_tree_sha = virtual_tree

    if stop_pr is not None:
        state = "DRY_RUN_STOP_CONDITION_VERIFIED"
    elif len(completed) == len(STACK):
        state = "DRY_RUN_SEQUENCE_COMPLETED"
    else:
        state = "BLOCKED"
        blockers.append("DRY_RUN_INCOMPLETE_WITHOUT_STOP_REASON")

    manifest = {
        "anchor_main_sha": PINNED_MAIN_SHA,
        "anchor_tree_sha": PINNED_MAIN_TREE_SHA,
        "completed_prs": completed,
        "stop_pr": stop_pr,
        "final_virtual_main_sha": current_main_sha,
        "final_virtual_tree_sha": current_tree_sha,
        "steps": rows,
    }

    return {
        "schema": SCHEMA,
        "state": state,
        "blockers": blockers,
        "steps": rows,
        "completed_prs": completed,
        "completed_count": len(completed),
        "expected_count": len(STACK),
        "stop_pr": stop_pr,
        "final_virtual_main_sha": current_main_sha,
        "final_virtual_tree_sha": current_tree_sha,
        "ceremony_digest": _digest(manifest),
        "synthetic_only": True,
        "virtual_shas_are_not_git_objects": True,
        "real_owner_authorization_used": False,
        "repository_mutation_performed": False,
        "actual_merge_executed": False,
        "actual_retarget_executed": False,
        "actual_rebase_executed": False,
        "actual_revert_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "merge_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "revert_authorized": False,
        "deploy_authorized": False,
        "executes_action": False,
    }


def simulate_rollback_ceremony(
    merged_pr_numbers: Sequence[Any] | None,
    *,
    failure_at_pr: Any,
) -> dict[str, Any]:
    """Simulate dependency-safe reverts without touching Git history."""
    order = rollback_order(
        merged_pr_numbers,
        failure_at_pr=failure_at_pr,
    )
    if order.get("state") != "ROLLBACK_ORDER_READY":
        return {
            "schema": ROLLBACK_SCHEMA,
            "state": "BLOCKED",
            "blockers": list(order.get("blockers") or []),
            "virtual_revert_steps": [],
            "repository_mutation_performed": False,
            "actual_revert_executed": False,
            "revert_authorized": False,
            "executes_action": False,
        }

    canonical = [item["number"] for item in STACK]
    merged = list(order["merged_prs"])
    revert_order = list(order["revert_pr_order"])
    remaining = [number for number in merged if number not in revert_order]

    virtual_steps = []
    prior_virtual = _virtual_git_sha(
        "ROLLBACK_START",
        {"merged": merged, "failure_at_pr": int(failure_at_pr)},
    )
    for number in revert_order:
        next_virtual = _virtual_git_sha(
            "REVERT_COMMIT",
            {
                "prior": prior_virtual,
                "revert_pr": number,
                "history_preserved": True,
            },
        )
        virtual_steps.append(
            {
                "pr_number": number,
                "state": "SIMULATED_REVERT_VERIFIED",
                "virtual_pre_revert_sha": prior_virtual,
                "virtual_revert_commit_sha": next_virtual,
                "actual_revert_performed": False,
                "force_push_used": False,
                "remote_reset_used": False,
                "history_rewrite_used": False,
                "repository_mutation_performed": False,
            }
        )
        prior_virtual = next_virtual

    full_recovery = not remaining
    virtual_recovery_tree = (
        PINNED_MAIN_TREE_SHA
        if full_recovery
        else _virtual_git_sha(
            "PARTIAL_RECOVERY_TREE",
            {
                "anchor_tree": PINNED_MAIN_TREE_SHA,
                "remaining_prs": remaining,
                "remaining_heads": [
                    STACK[canonical.index(number)]["head_sha"]
                    for number in remaining
                ],
            },
        )
    )

    return {
        "schema": ROLLBACK_SCHEMA,
        "state": (
            "FULL_ROLLBACK_DRY_RUN_COMPLETED"
            if full_recovery
            else "PARTIAL_ROLLBACK_DRY_RUN_COMPLETED"
        ),
        "blockers": [],
        "merged_prs": merged,
        "failure_at_pr": int(failure_at_pr),
        "revert_pr_order": revert_order,
        "remaining_prs": remaining,
        "virtual_revert_steps": virtual_steps,
        "virtual_recovery_tree_sha": virtual_recovery_tree,
        "anchor_tree_match_simulated": full_recovery,
        "history_preserved_simulated": True,
        "synthetic_only": True,
        "actual_revert_executed": False,
        "force_push_used": False,
        "remote_reset_used": False,
        "history_rewrite_used": False,
        "repository_mutation_performed": False,
        "revert_authorized": False,
        "executes_action": False,
    }


def dry_run_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "strict_parent_before_child_simulated": True,
        "main_advance_simulated_per_step": True,
        "child_retarget_simulated_after_parent": True,
        "fresh_revalidation_simulated_after_base_change": True,
        "old_readiness_reuse_after_base_change_allowed": False,
        "exact_file_delta_rechecked_per_step": True,
        "zero_deletion_rechecked_per_step": True,
        "gate_rerun_rechecked_per_step": True,
        "stop_on_main_drift": True,
        "stop_on_head_drift": True,
        "stop_on_base_drift": True,
        "stop_on_file_delta_drift": True,
        "stop_on_gate_failure": True,
        "stop_on_missing_owner_authorization": True,
        "stop_on_retarget_conflict": True,
        "stop_on_merge_conflict": True,
        "stop_on_unexpected_deploy": True,
        "stop_on_unexpected_worker_activation": True,
        "stop_on_unexpected_provider_activation": True,
        "rollback_reverse_dependency_order_simulated": True,
        "virtual_shas_are_not_git_objects": True,
        "synthetic_owner_authorization_is_not_real_authorization": True,
        "repository_mutation_performed": False,
        "actual_merge_executed": False,
        "actual_retarget_executed": False,
        "actual_rebase_executed": False,
        "actual_revert_executed": False,
        "merge_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "revert_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "ROLLBACK_SCHEMA",
    "POLICY_SCHEMA",
    "SUPPORTED_FAULTS",
    "simulate_merge_ceremony",
    "simulate_rollback_ceremony",
    "dry_run_policy",
]
