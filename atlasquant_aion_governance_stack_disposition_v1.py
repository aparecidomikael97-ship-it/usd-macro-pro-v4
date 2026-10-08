"""AION Governance Stack Disposition V1.

Pure, non-mutating disposition contract for governance PRs #1030-#1034.

The contract answers what should happen to the governance stack after the
product stack #1015-#1029 is merged and independently verified.

Decision:
- all five governance PRs must be preserved and merged in strict order;
- #1030 and #1032 become frozen historical governance evidence;
- #1031, #1033 and #1034 become maintained governance references;
- no PR in #1030-#1034 is safe to skip/close unmerged in the current topology.

Why:
- later modules import #1030;
- #1033/#1034 sit above #1032 in the stacked Git ancestry;
- skipping a middle PR would change the intended diff/topology and require a
  separate replacement/consolidation design.

This module never marks PRs ready, retargets, rebases, merges, closes or deletes
branches. It never deploys or activates runtime capabilities.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA = "ATLASQUANT_AION_GOVERNANCE_STACK_DISPOSITION_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_GOVERNANCE_STACK_DISPOSITION_VERIFY_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_GOVERNANCE_STACK_MERGE_PLAN_V1"
RETENTION_SCHEMA = "ATLASQUANT_AION_GOVERNANCE_STACK_RETENTION_POLICY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_GOVERNANCE_STACK_DISPOSITION_POLICY_V1"

PRODUCT_STACK_PRS = tuple(range(1015, 1030))

GOVERNANCE_STACK = (
    {
        "number": 1030,
        "title": "IMPLEMENTATION SAFE — AION Owner Stack Pre-Merge Readiness V1",
        "base": "impl/aion-owner-stack-integration-certification-v1-20261008",
        "head": "impl/aion-owner-stack-pre-merge-readiness-v1-20261008",
        "head_sha": "513d39f2bfb1eb2081a4a7916efa1b8048c42cd8",
        "required_workflow": "AION Owner Stack Pre-Merge Readiness V1",
        "disposition": "MERGE_REQUIRED_FROZEN_HISTORICAL_EVIDENCE",
        "post_merge_role": "FROZEN_HISTORICAL_REFERENCE",
        "reason": (
            "Pins the exact pre-merge snapshot and is imported by later "
            "governance modules."
        ),
    },
    {
        "number": 1031,
        "title": "IMPLEMENTATION SAFE — AION Owner Stack Merge Rollback + Recovery V1",
        "base": "impl/aion-owner-stack-pre-merge-readiness-v1-20261008",
        "head": "impl/aion-owner-stack-merge-rollback-recovery-v1-20261008",
        "head_sha": "6828469c6c414449c74a5b333ef1a8c429b4e320",
        "required_workflow": "AION Owner Stack Merge Rollback Recovery V1",
        "disposition": "MERGE_REQUIRED_ACTIVE_GOVERNANCE_REFERENCE",
        "post_merge_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "reason": (
            "Preserves non-destructive rollback/recovery and merge-journal "
            "rules."
        ),
    },
    {
        "number": 1032,
        "title": "IMPLEMENTATION SAFE — AION Owner Stack Merge Ceremony Dry-Run V1",
        "base": "impl/aion-owner-stack-merge-rollback-recovery-v1-20261008",
        "head": "impl/aion-owner-stack-merge-ceremony-dry-run-v1-20261008",
        "head_sha": "97dcbed629b0df47b01e0da8a63e85e2b494e071",
        "required_workflow": "AION Owner Stack Merge Ceremony Dry Run V1",
        "disposition": "MERGE_REQUIRED_FROZEN_HISTORICAL_EVIDENCE",
        "post_merge_role": "FROZEN_HISTORICAL_REFERENCE",
        "reason": (
            "Records the exact synthetic rehearsal and remains in the ancestry "
            "of later governance PRs."
        ),
    },
    {
        "number": 1033,
        "title": "IMPLEMENTATION SAFE — AION Live Merge Step Preflight + Owner Challenge V1",
        "base": "impl/aion-owner-stack-merge-ceremony-dry-run-v1-20261008",
        "head": "impl/aion-owner-stack-live-merge-step-preflight-challenge-v1-20261008",
        "head_sha": "1b625f5cd70b3d2e70ba9f6edd34be3ca5e73a55",
        "required_workflow": "AION Owner Stack Live Merge Step Preflight Challenge V1",
        "disposition": "MERGE_REQUIRED_ACTIVE_GOVERNANCE_REFERENCE",
        "post_merge_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "reason": (
            "Defines live repository-mutation preflight and HUMAN_OWNER "
            "challenge boundaries."
        ),
    },
    {
        "number": 1034,
        "title": "IMPLEMENTATION SAFE — AION Post-Merge Main Certification + Branch Cleanup V1",
        "base": "impl/aion-owner-stack-live-merge-step-preflight-challenge-v1-20261008",
        "head": "impl/aion-owner-stack-post-merge-certification-cleanup-v1-20261008",
        "head_sha": "3f7a4390248ea17d53c8973a7db0911b38f6b793",
        "required_workflow": "AION Owner Stack Post-Merge Certification Cleanup V1",
        "disposition": "MERGE_REQUIRED_ACTIVE_GOVERNANCE_REFERENCE",
        "post_merge_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "reason": (
            "Defines final product-main certification and safe branch cleanup "
            "eligibility."
        ),
    },
)

FROZEN_HISTORICAL_PRS = (1030, 1032)
ACTIVE_REFERENCE_PRS = (1031, 1033, 1034)
CLOSE_UNMERGED_PRS: tuple[int, ...] = ()


def _clean(value: Any, limit: int = 500) -> str:
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


def _workflow_green(rows: Any, name: str) -> bool:
    if not isinstance(rows, (list, tuple)):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("name"), 240) != name:
            continue
        return (
            _clean(row.get("status"), 40).lower() == "completed"
            and _clean(row.get("conclusion"), 40).lower() == "success"
        )
    return False


def evaluate_governance_disposition_readiness(
    observed_prs: Sequence[Mapping[str, Any]] | None,
    *,
    product_stack_post_merge_certified: bool,
    product_stack_prs_confirmed_in_main: Sequence[Any] | None,
    product_stack_full_gate_green_on_main: bool,
    frozen_core_integrity_verified: bool,
    deploy_remained_disabled: bool,
    worker_remained_disabled: bool,
    provider_activation_remained_disabled: bool,
    production_persistence_remained_disabled: bool,
) -> dict[str, Any]:
    """Validate that governance disposition may be reviewed."""
    blockers: list[str] = []

    if product_stack_post_merge_certified is not True:
        blockers.append("PRODUCT_STACK_POST_MERGE_CERTIFICATION_REQUIRED")

    product_prs: list[int] = []
    for raw in list(product_stack_prs_confirmed_in_main or []):
        try:
            product_prs.append(int(raw))
        except Exception:
            blockers.append("PRODUCT_STACK_PR_NUMBER_INVALID")
    if tuple(product_prs) != PRODUCT_STACK_PRS:
        blockers.append("EXACT_PRODUCT_STACK_CONFIRMATION_REQUIRED")
    if product_stack_full_gate_green_on_main is not True:
        blockers.append("PRODUCT_STACK_FULL_GATE_ON_MAIN_REQUIRED")
    if frozen_core_integrity_verified is not True:
        blockers.append("FROZEN_CORE_INTEGRITY_REQUIRED")
    if deploy_remained_disabled is not True:
        blockers.append("DEPLOY_MUST_REMAIN_DISABLED")
    if worker_remained_disabled is not True:
        blockers.append("WORKER_MUST_REMAIN_DISABLED")
    if provider_activation_remained_disabled is not True:
        blockers.append("PROVIDER_ACTIVATION_MUST_REMAIN_DISABLED")
    if production_persistence_remained_disabled is not True:
        blockers.append("PRODUCTION_PERSISTENCE_MUST_REMAIN_DISABLED")

    rows = [
        dict(row)
        for row in list(observed_prs or [])
        if isinstance(row, Mapping)
    ]
    by_number: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            number = int(row.get("number"))
        except Exception:
            blockers.append("GOVERNANCE_PR_NUMBER_INVALID")
            continue
        if number in by_number:
            blockers.append(f"DUPLICATE_GOVERNANCE_PR:{number}")
        else:
            by_number[number] = row

    checks: list[dict[str, Any]] = []
    for item in GOVERNANCE_STACK:
        number = item["number"]
        row = by_number.get(number)
        pr_blockers: list[str] = []

        if row is None:
            pr_blockers.append("PR_MISSING")
        else:
            if _clean(row.get("state"), 40).lower() != "open":
                pr_blockers.append("PR_NOT_OPEN")
            if row.get("draft") is not True:
                pr_blockers.append("PR_MUST_REMAIN_DRAFT_BEFORE_DISPOSITION_AUTHORIZATION")
            if row.get("mergeable") is not True:
                pr_blockers.append("PR_NOT_MERGEABLE")
            if _clean(row.get("base"), 300) != item["base"]:
                pr_blockers.append("BASE_DRIFT")
            if _clean(row.get("head"), 300) != item["head"]:
                pr_blockers.append("HEAD_BRANCH_DRIFT")
            if _clean(row.get("head_sha"), 60) != item["head_sha"]:
                pr_blockers.append("HEAD_SHA_DRIFT")
            if int(row.get("changed_files") or 0) != 4:
                pr_blockers.append("FOUR_FILE_DELTA_REQUIRED")
            if int(row.get("deletions") or 0) != 0:
                pr_blockers.append("ZERO_DELETIONS_REQUIRED")
            if not _workflow_green(
                row.get("workflows"),
                item["required_workflow"],
            ):
                pr_blockers.append(
                    "REQUIRED_WORKFLOW_NOT_GREEN:" + item["required_workflow"]
                )

        pr_blockers = list(dict.fromkeys(pr_blockers))
        checks.append(
            {
                "number": number,
                "state": "MATCH" if not pr_blockers else "BLOCKED",
                "blockers": pr_blockers,
                "disposition": item["disposition"],
                "post_merge_role": item["post_merge_role"],
            }
        )
        blockers.extend(f"PR_{number}:{reason}" for reason in pr_blockers)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "product_stack_prs": product_prs,
        "checks": checks,
        "frozen_historical_prs": list(FROZEN_HISTORICAL_PRS),
        "active_reference_prs": list(ACTIVE_REFERENCE_PRS),
    }

    return {
        "schema": VERIFY_SCHEMA,
        "state": (
            "READY_FOR_HUMAN_OWNER_GOVERNANCE_DISPOSITION_REVIEW"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "checks": checks,
        "frozen_historical_prs": list(FROZEN_HISTORICAL_PRS),
        "active_reference_prs": list(ACTIVE_REFERENCE_PRS),
        "close_unmerged_prs": list(CLOSE_UNMERGED_PRS),
        "disposition_digest": _digest(material) if not blockers else "",
        "all_five_current_prs_required": True,
        "skip_middle_pr_allowed": False,
        "close_current_governance_pr_unmerged_allowed": False,
        "replacement_or_consolidation_requires_separate_design": True,
        "governance_merge_authorized": False,
        "pr_close_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "branch_delete_authorized": False,
        "deploy_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def build_governance_disposition_plan(
    readiness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build strict governance disposition sequence. No Git mutation occurs."""
    raw = dict(readiness or {})
    if raw.get("state") != "READY_FOR_HUMAN_OWNER_GOVERNANCE_DISPOSITION_REVIEW":
        return {
            "schema": PLAN_SCHEMA,
            "state": "BLOCKED",
            "blockers": ["VALID_GOVERNANCE_DISPOSITION_READINESS_REQUIRED"],
            "steps": [],
            "governance_merge_authorized": False,
            "executes_action": False,
        }

    steps: list[dict[str, Any]] = []
    for index, item in enumerate(GOVERNANCE_STACK):
        parent = GOVERNANCE_STACK[index - 1] if index else None
        steps.append(
            {
                "order": index + 1,
                "pr_number": item["number"],
                "title": item["title"],
                "disposition": item["disposition"],
                "post_merge_role": item["post_merge_role"],
                "reason": item["reason"],
                "pinned_head_sha": item["head_sha"],
                "current_base": item["base"],
                "parent_pr_number": parent["number"] if parent else 1029,
                "product_stack_must_already_be_certified": True,
                "parent_must_be_confirmed_in_main": True,
                "live_main_refetch_required": True,
                "separate_owner_authorization_required": True,
                "draft_to_ready_requires_separate_authorization": True,
                "retarget_or_rebase_requires_separate_authorization": True,
                "merge_requires_separate_authorization": True,
                "exact_four_file_delta_required_after_base_change": True,
                "zero_deletions_required_after_base_change": True,
                "dedicated_gate_rerun_required": True,
                "stop_on_any_drift_or_ambiguity": True,
                "deploy_forbidden": True,
                "worker_activation_forbidden": True,
                "provider_activation_forbidden": True,
                "production_persistence_activation_forbidden": True,
            }
        )

    return {
        "schema": PLAN_SCHEMA,
        "state": "GOVERNANCE_DISPOSITION_PLAN_READY",
        "blockers": [],
        "steps": steps,
        "step_count": len(steps),
        "merge_order": [item["number"] for item in GOVERNANCE_STACK],
        "strict_order_required": True,
        "skip_step_allowed": False,
        "close_unmerged_allowed": False,
        "all_five_merged_before_governance_branch_cleanup": True,
        "post_merge_retention_policy_required": True,
        "governance_merge_authorized": False,
        "pr_close_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "branch_delete_authorized": False,
        "deploy_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def governance_retention_policy() -> dict[str, Any]:
    """Classify post-merge meaning without deleting historical material."""
    return {
        "schema": RETENTION_SCHEMA,
        "frozen_historical_prs": list(FROZEN_HISTORICAL_PRS),
        "active_reference_prs": list(ACTIVE_REFERENCE_PRS),
        "close_unmerged_prs": list(CLOSE_UNMERGED_PRS),
        "pr_1030_role": "FROZEN_HISTORICAL_REFERENCE",
        "pr_1031_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "pr_1032_role": "FROZEN_HISTORICAL_REFERENCE",
        "pr_1033_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "pr_1034_role": "MAINTAINED_GOVERNANCE_REFERENCE",
        "historical_v1_files_remain_in_main_after_merge": True,
        "historical_v1_files_should_not_be_rewritten_to_fake_current_state": True,
        "active_reference_v1_can_be_superseded_by_new_version": True,
        "superseding_version_must_not_destroy_v1_evidence": True,
        "consolidated_replacement_is_future_separate_design": True,
        "current_stack_can_be_closed_unmerged_after_consolidation": False,
        "governance_pr_metadata_should_be_preserved": True,
        "workflow_evidence_should_be_preserved": True,
        "head_sha_evidence_should_be_preserved": True,
        "merge_journal_should_reference_governance_prs": True,
        "branch_cleanup_only_after_all_dependents_resolved": True,
        "governance_branch_cleanup_child_before_parent": True,
        "automatic_branch_deletion_allowed": False,
        "branch_delete_authorized": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def governance_disposition_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "product_stack_must_be_certified_before_governance_merge": True,
        "governance_prs": [item["number"] for item in GOVERNANCE_STACK],
        "strict_governance_order_required": True,
        "all_five_current_governance_prs_required": True,
        "skip_middle_pr_allowed": False,
        "close_current_governance_pr_unmerged_allowed": False,
        "replacement_or_consolidation_requires_separate_design": True,
        "frozen_historical_prs": list(FROZEN_HISTORICAL_PRS),
        "active_reference_prs": list(ACTIVE_REFERENCE_PRS),
        "historical_evidence_preserved_in_main": True,
        "historical_evidence_must_not_be_rewritten_as_current": True,
        "active_reference_may_be_superseded_not_erased": True,
        "governance_merge_requires_live_revalidation": True,
        "governance_merge_requires_separate_owner_authorization_per_mutation": True,
        "governance_gate_rerun_after_base_change_required": True,
        "governance_branch_cleanup_after_all_dependencies_resolved": True,
        "automatic_merge_allowed": False,
        "automatic_close_allowed": False,
        "automatic_retarget_allowed": False,
        "automatic_rebase_allowed": False,
        "automatic_branch_delete_allowed": False,
        "automatic_deploy_allowed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "production_persistence_activation_allowed": False,
        "governance_merge_authorized": False,
        "pr_close_authorized": False,
        "branch_delete_authorized": False,
        "deploy_authorized": False,
        "repository_mutation_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERIFY_SCHEMA",
    "PLAN_SCHEMA",
    "RETENTION_SCHEMA",
    "POLICY_SCHEMA",
    "PRODUCT_STACK_PRS",
    "GOVERNANCE_STACK",
    "FROZEN_HISTORICAL_PRS",
    "ACTIVE_REFERENCE_PRS",
    "CLOSE_UNMERGED_PRS",
    "evaluate_governance_disposition_readiness",
    "build_governance_disposition_plan",
    "governance_retention_policy",
    "governance_disposition_policy",
]
