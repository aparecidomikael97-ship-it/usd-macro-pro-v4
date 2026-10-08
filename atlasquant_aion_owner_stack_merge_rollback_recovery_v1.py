"""AION Owner Stack Merge Rollback + Recovery V1.

Pure rollback/recovery planning contract for the #1015-#1029 stacked merge line.

The plan preserves Git history and forbids destructive recovery:
- no force push;
- no reset of remote main;
- no history rewrite;
- no automatic branch deletion;
- no automatic deploy rollback;
- no automatic production data rollback.

If a merged parent must be reverted after dependent children were also merged,
reverts must occur in reverse dependency order.

A positive state is only READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW.
No repository mutation is performed or authorized.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import (
    PINNED_MAIN_SHA,
    STACK,
)


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_ROLLBACK_RECOVERY_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_ROLLBACK_PLAN_V1"
JOURNAL_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_JOURNAL_REVIEW_V1"
RECOVERY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_RECOVERY_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_ROLLBACK_POLICY_V1"

PINNED_MAIN_TREE_SHA = "c98cc45a56224b187d366079b87a2569f6a357f0"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


def build_rollback_recovery_plan(
    pre_merge_readiness: Mapping[str, Any] | None,
    merge_sequence_plan: Mapping[str, Any] | None,
    *,
    observed_anchor_main_sha: Any,
    observed_anchor_tree_sha: Any,
) -> dict[str, Any]:
    """Prepare recovery controls before any real merge starts."""
    readiness = dict(pre_merge_readiness or {})
    sequence = dict(merge_sequence_plan or {})
    blockers: list[str] = []

    if readiness.get("state") != "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW":
        blockers.append("VALID_PRE_MERGE_READINESS_REQUIRED")
    if readiness.get("merge_authorized") is not False:
        blockers.append("READINESS_MUST_NOT_AUTHORIZE_MERGE")
    if sequence.get("state") != "MERGE_SEQUENCE_PLAN_READY":
        blockers.append("VALID_MERGE_SEQUENCE_PLAN_REQUIRED")
    if sequence.get("merge_authorized") is not False:
        blockers.append("SEQUENCE_MUST_NOT_AUTHORIZE_MERGE")

    main_sha = _clean(observed_anchor_main_sha, 60)
    tree_sha = _clean(observed_anchor_tree_sha, 60)
    if main_sha != PINNED_MAIN_SHA:
        blockers.append("ANCHOR_MAIN_SHA_MISMATCH")
    if tree_sha != PINNED_MAIN_TREE_SHA:
        blockers.append("ANCHOR_MAIN_TREE_SHA_MISMATCH")

    steps = []
    for index, item in enumerate(STACK):
        steps.append(
            {
                "order": index + 1,
                "pr_number": item["number"],
                "pinned_head_sha": item["head_sha"],
                "capture_pre_merge_main_sha": True,
                "capture_pre_merge_tree_sha": True,
                "capture_post_merge_main_sha": True,
                "capture_post_merge_tree_sha": True,
                "capture_merge_commit_sha": True,
                "capture_exact_file_delta": True,
                "capture_gate_results": True,
                "capture_owner_authorization_ref": True,
                "revert_commit_required_for_rollback": True,
                "force_push_allowed": False,
                "remote_reset_allowed": False,
                "history_rewrite_allowed": False,
            }
        )

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PLAN_SCHEMA,
        "state": (
            "READY_FOR_HUMAN_OWNER_ROLLBACK_PLAN_REVIEW"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "anchor_main_sha": main_sha,
        "anchor_main_tree_sha": tree_sha,
        "stack_prs": [item["number"] for item in STACK],
        "steps": steps,
        "rollback_strategy": "REVERT_COMMITS_IN_REVERSE_DEPENDENCY_ORDER",
        "recovery_comparison_uses_tree_not_commit_sha": True,
        "anchor_history_may_differ_after_revert": True,
        "anchor_tree_must_match_for_full_stack_recovery": True,
        "force_push_allowed": False,
        "remote_main_reset_allowed": False,
        "history_rewrite_allowed": False,
        "automatic_revert_allowed": False,
        "automatic_branch_delete_allowed": False,
        "automatic_deploy_rollback_allowed": False,
        "automatic_production_data_rollback_allowed": False,
        "unrelated_main_drift_requires_human_reconciliation": True,
        "rollback_conflict_requires_human_reconciliation": True,
        "merge_authorized": False,
        "rollback_authorized": False,
        "revert_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "external_action_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
        "plan_digest": "",
    } | {
        "plan_digest": _digest({
            "anchor_main_sha": main_sha,
            "anchor_main_tree_sha": tree_sha,
            "stack_prs": [item["number"] for item in STACK],
            "steps": steps,
            "rollback_strategy": "REVERT_COMMITS_IN_REVERSE_DEPENDENCY_ORDER",
        }) if not blockers else ""
    }


def rollback_order(
    merged_pr_numbers: Sequence[Any] | None,
    *,
    failure_at_pr: Any,
) -> dict[str, Any]:
    """Return safe reverse dependency order. Never performs reverts."""
    valid_order = [item["number"] for item in STACK]
    merged: list[int] = []
    blockers: list[str] = []

    for raw in list(merged_pr_numbers or []):
        try:
            number = int(raw)
        except Exception:
            blockers.append("MERGED_PR_NUMBER_INVALID")
            continue
        if number not in valid_order:
            blockers.append(f"PR_NOT_IN_STACK:{number}")
            continue
        if number not in merged:
            merged.append(number)

    merged_sorted = sorted(merged, key=valid_order.index)
    if merged != merged_sorted:
        blockers.append("MERGED_SEQUENCE_NOT_PARENT_BEFORE_CHILD")

    try:
        failed = int(failure_at_pr)
    except Exception:
        failed = 0
        blockers.append("FAILURE_PR_INVALID")

    if failed not in merged:
        blockers.append("FAILURE_PR_MUST_ALREADY_BE_MERGED")

    if blockers:
        order: list[int] = []
    else:
        failure_index = valid_order.index(failed)
        affected = [
            number
            for number in merged
            if valid_order.index(number) >= failure_index
        ]
        order = list(reversed(affected))

    return {
        "schema": SCHEMA,
        "state": "ROLLBACK_ORDER_READY" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "failure_at_pr": failed,
        "merged_prs": merged,
        "revert_pr_order": order,
        "reverse_dependency_order": True,
        "force_push_allowed": False,
        "remote_main_reset_allowed": False,
        "automatic_revert_allowed": False,
        "revert_authorized": False,
        "executes_action": False,
    }


def evaluate_merge_journal(
    journal_entries: Sequence[Mapping[str, Any]] | None,
    *,
    expected_sequence_prefix: Sequence[Any] | None,
) -> dict[str, Any]:
    """Audit future merge evidence without mutating GitHub."""
    blockers: list[str] = []
    entries = [
        dict(row)
        for row in list(journal_entries or [])
        if isinstance(row, Mapping)
    ]

    prefix: list[int] = []
    for raw in list(expected_sequence_prefix or []):
        try:
            prefix.append(int(raw))
        except Exception:
            blockers.append("EXPECTED_SEQUENCE_PREFIX_INVALID")

    canonical_order = [item["number"] for item in STACK]
    if prefix != canonical_order[: len(prefix)]:
        blockers.append("EXPECTED_PREFIX_NOT_CANONICAL")

    if len(entries) != len(prefix):
        blockers.append("JOURNAL_ENTRY_COUNT_MISMATCH")

    prior_post_sha = PINNED_MAIN_SHA
    rows = []
    for index, number in enumerate(prefix):
        row = entries[index] if index < len(entries) else {}
        row_blockers: list[str] = []

        if int(row.get("pr_number") or 0) != number:
            row_blockers.append("PR_NUMBER_MISMATCH")
        pre_sha = _clean(row.get("pre_merge_main_sha"), 60)
        post_sha = _clean(row.get("post_merge_main_sha"), 60)
        merge_sha = _clean(row.get("merge_commit_sha"), 60)
        pre_tree = _clean(row.get("pre_merge_tree_sha"), 60)
        post_tree = _clean(row.get("post_merge_tree_sha"), 60)

        if pre_sha != prior_post_sha:
            row_blockers.append("MAIN_CHAIN_DISCONTINUITY")
        for label, value in (
            ("PRE_MAIN_SHA_INVALID", pre_sha),
            ("POST_MAIN_SHA_INVALID", post_sha),
            ("MERGE_COMMIT_SHA_INVALID", merge_sha),
            ("PRE_TREE_SHA_INVALID", pre_tree),
            ("POST_TREE_SHA_INVALID", post_tree),
        ):
            if not _SHA_RE.fullmatch(value):
                row_blockers.append(label)

        if row.get("owner_authorization_verified") is not True:
            row_blockers.append("OWNER_AUTHORIZATION_EVIDENCE_REQUIRED")
        if row.get("exact_file_delta_verified") is not True:
            row_blockers.append("EXACT_FILE_DELTA_VERIFICATION_REQUIRED")
        if row.get("required_gates_green") is not True:
            row_blockers.append("POST_MERGE_GATE_VERIFICATION_REQUIRED")
        if row.get("deploy_executed") is not False:
            row_blockers.append("DEPLOY_MUST_REMAIN_FALSE")
        if row.get("worker_activated") is not False:
            row_blockers.append("WORKER_MUST_REMAIN_FALSE")
        if row.get("provider_activated") is not False:
            row_blockers.append("PROVIDER_ACTIVATION_MUST_REMAIN_FALSE")

        if post_sha == pre_sha and _SHA_RE.fullmatch(post_sha):
            row_blockers.append("POST_MAIN_SHA_MUST_ADVANCE")
        if post_tree == pre_tree and _SHA_RE.fullmatch(post_tree):
            row_blockers.append("POST_TREE_MUST_ADVANCE")

        if post_sha:
            prior_post_sha = post_sha

        rows.append(
            {
                "pr_number": number,
                "state": "VERIFIED" if not row_blockers else "BLOCKED",
                "blockers": row_blockers,
                "pre_merge_main_sha": pre_sha,
                "post_merge_main_sha": post_sha,
                "merge_commit_sha": merge_sha,
                "pre_merge_tree_sha": pre_tree,
                "post_merge_tree_sha": post_tree,
            }
        )
        blockers.extend(f"PR_{number}:{item}" for item in row_blockers)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": JOURNAL_SCHEMA,
        "state": "MERGE_JOURNAL_PREFIX_VERIFIED" if not blockers else "BLOCKED",
        "blockers": blockers,
        "verified_prefix": prefix if not blockers else [],
        "entries": rows,
        "next_expected_pr": (
            canonical_order[len(prefix)]
            if not blockers and len(prefix) < len(canonical_order)
            else None
        ),
        "merge_authorized": False,
        "rollback_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def verify_full_recovery(
    *,
    recovery_tree_sha: Any,
    unresolved_revert_conflicts: bool,
    all_revert_commits_verified: bool,
    quality_gates_green: bool,
    full_stack_gate_green_if_applicable: bool,
    deploy_executed_during_recovery: bool,
    worker_activated_during_recovery: bool,
    provider_activated_during_recovery: bool,
) -> dict[str, Any]:
    """Verify tree-level restoration after reverse-order revert commits."""
    blockers: list[str] = []
    tree_sha = _clean(recovery_tree_sha, 60)

    if tree_sha != PINNED_MAIN_TREE_SHA:
        blockers.append("RECOVERY_TREE_DOES_NOT_MATCH_ANCHOR")
    if unresolved_revert_conflicts is not False:
        blockers.append("UNRESOLVED_REVERT_CONFLICT")
    if all_revert_commits_verified is not True:
        blockers.append("REVERT_COMMIT_VERIFICATION_REQUIRED")
    if quality_gates_green is not True:
        blockers.append("QUALITY_GATES_REQUIRED")
    if full_stack_gate_green_if_applicable is not True:
        blockers.append("FULL_STACK_GATE_REQUIRED")
    if deploy_executed_during_recovery is not False:
        blockers.append("DEPLOY_MUST_REMAIN_FALSE")
    if worker_activated_during_recovery is not False:
        blockers.append("WORKER_MUST_REMAIN_FALSE")
    if provider_activated_during_recovery is not False:
        blockers.append("PROVIDER_ACTIVATION_MUST_REMAIN_FALSE")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": RECOVERY_SCHEMA,
        "state": "RECOVERY_TREE_VERIFIED" if not blockers else "BLOCKED",
        "blockers": blockers,
        "anchor_tree_sha": PINNED_MAIN_TREE_SHA,
        "recovery_tree_sha": tree_sha,
        "history_preserved": True,
        "anchor_commit_sha_equality_required": False,
        "anchor_tree_sha_equality_required": True,
        "force_push_used": False,
        "remote_reset_used": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "recovery_authorized": False,
        "repository_mutation_performed_by_this_module": False,
        "executes_action": False,
    }


def rollback_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "capture_anchor_main_sha_before_sequence": True,
        "capture_anchor_tree_sha_before_sequence": True,
        "capture_each_merge_commit_sha": True,
        "capture_each_pre_post_tree_sha": True,
        "capture_owner_authorization_reference": True,
        "preserve_git_history": True,
        "force_push_allowed": False,
        "remote_main_reset_allowed": False,
        "history_rewrite_allowed": False,
        "dependent_children_reverted_before_parent": True,
        "reverse_dependency_order_required": True,
        "unrelated_main_drift_requires_human_reconciliation": True,
        "rollback_conflict_requires_human_reconciliation": True,
        "automatic_revert_allowed": False,
        "automatic_branch_delete_allowed": False,
        "automatic_deploy_rollback_allowed": False,
        "automatic_production_data_rollback_allowed": False,
        "tree_level_recovery_verification_required": True,
        "commit_sha_equality_with_anchor_required": False,
        "quality_gates_after_recovery_required": True,
        "full_stack_gate_after_recovery_required_if_applicable": True,
        "merge_authorized": False,
        "rollback_authorized": False,
        "revert_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "repository_mutation_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "JOURNAL_SCHEMA",
    "RECOVERY_SCHEMA",
    "POLICY_SCHEMA",
    "PINNED_MAIN_TREE_SHA",
    "build_rollback_recovery_plan",
    "rollback_order",
    "evaluate_merge_journal",
    "verify_full_recovery",
    "rollback_policy",
]
