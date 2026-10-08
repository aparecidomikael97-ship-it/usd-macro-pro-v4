"""AION Owner Stack Post-Merge Main Certification + Branch Cleanup Plan V1.

Pure, non-mutating closure contract for the future #1015-#1029 merge sequence.

This layer defines:
1. post-merge certification of main after all 15 product-stack PRs are merged;
2. preservation requirements for merge evidence;
3. safe branch-cleanup eligibility;
4. dependency-aware cleanup ordering.

It does NOT merge, retarget, rebase, delete branches, deploy, activate Worker,
activate providers, or mutate GitHub.

Important:
- the 15 product-stack PRs are #1015 through #1029;
- governance PRs #1030+ are outside the product-stack certification set;
- a product branch cannot be deleted while any open PR still uses it as base.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_owner_stack_pre_merge_readiness_v1 import STACK


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_POST_MERGE_CERTIFICATION_CLEANUP_V1"
CERT_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_POST_MERGE_MAIN_CERTIFICATION_V1"
CLEANUP_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_BRANCH_CLEANUP_PLAN_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_BRANCH_CLEANUP_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_POST_MERGE_CLEANUP_POLICY_V1"

PRODUCT_PRS = tuple(item["number"] for item in STACK)
PRODUCT_BRANCHES = tuple(item["head"] for item in STACK)
PRODUCT_FILES = tuple(
    path
    for item in STACK
    for path in item["files"]
)

POST_MERGE_REQUIRED_WORKFLOWS = (
    "AION Owner Stack Integration Certification V1",
    "Quality tests",
    "AtlasQuant - Release Readiness",
    "AION Core Certification",
    "AION Core Security Gate",
)

GOVERNANCE_BRANCHES = (
    "impl/aion-owner-stack-pre-merge-readiness-v1-20261008",
    "impl/aion-owner-stack-merge-rollback-recovery-v1-20261008",
    "impl/aion-owner-stack-merge-ceremony-dry-run-v1-20261008",
    "impl/aion-owner-stack-live-merge-step-preflight-challenge-v1-20261008",
    "impl/aion-owner-stack-post-merge-certification-cleanup-v1-20261008",
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def _sha(value: Any) -> str:
    token = _clean(value, 60)
    return token if _SHA_RE.fullmatch(token) else ""


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


def _workflow_map(value: Any) -> dict[str, bool]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = _clean(row.get("name"), 240)
        if not name:
            continue
        out[name] = (
            _clean(row.get("status"), 40).lower() == "completed"
            and _clean(row.get("conclusion"), 40).lower() == "success"
        )
    return out


def build_post_merge_main_certification(
    *,
    observed_main_sha: Any,
    observed_main_tree_sha: Any,
    merged_pr_numbers: Sequence[Any] | None,
    observed_owner_stack_files: Sequence[Any] | None,
    observed_workflows: Sequence[Mapping[str, Any]] | None,
    merge_journal_digest: Any,
    rollback_plan_digest: Any,
    full_stack_certification_digest: Any,
    full_stack_certification_on_main: bool,
    all_expected_prs_confirmed_in_main: bool,
    frozen_core_integrity_verified: bool,
    no_unresolved_merge_conflicts: bool,
    no_unexpected_main_drift: bool,
    deploy_executed_during_sequence: bool,
    worker_activated_during_sequence: bool,
    provider_activated_during_sequence: bool,
    production_persistence_activated_during_sequence: bool,
) -> dict[str, Any]:
    """Certify final main state after the real product merge sequence."""
    blockers: list[str] = []

    main_sha = _sha(observed_main_sha)
    tree_sha = _sha(observed_main_tree_sha)
    journal_digest = _sha256(merge_journal_digest)
    rollback_digest = _sha256(rollback_plan_digest)
    stack_cert_digest = _sha256(full_stack_certification_digest)

    if not main_sha:
        blockers.append("MAIN_SHA_REQUIRED")
    if not tree_sha:
        blockers.append("MAIN_TREE_SHA_REQUIRED")
    if not journal_digest:
        blockers.append("MERGE_JOURNAL_DIGEST_REQUIRED")
    if not rollback_digest:
        blockers.append("ROLLBACK_PLAN_DIGEST_REQUIRED")
    if not stack_cert_digest:
        blockers.append("FULL_STACK_CERTIFICATION_DIGEST_REQUIRED")

    merged: list[int] = []
    for raw in list(merged_pr_numbers or []):
        try:
            merged.append(int(raw))
        except Exception:
            blockers.append("MERGED_PR_NUMBER_INVALID")
    if tuple(merged) != PRODUCT_PRS:
        blockers.append("EXACT_PRODUCT_PR_SEQUENCE_REQUIRED")

    files = sorted({_clean(item, 420) for item in list(observed_owner_stack_files or []) if _clean(item, 420)})
    expected_files = sorted(PRODUCT_FILES)
    if files != expected_files:
        blockers.append("EXACT_OWNER_STACK_FILE_INVENTORY_REQUIRED")
    if len(files) != 60:
        blockers.append("OWNER_STACK_FILE_COUNT_MUST_BE_60")

    workflow_map = _workflow_map(observed_workflows)
    for workflow in POST_MERGE_REQUIRED_WORKFLOWS:
        if workflow_map.get(workflow) is not True:
            blockers.append("POST_MERGE_WORKFLOW_NOT_GREEN:" + workflow)

    for label, flag in (
        ("FULL_STACK_CERTIFICATION_MUST_RUN_ON_MAIN", full_stack_certification_on_main),
        ("ALL_PRODUCT_PRS_MUST_BE_CONFIRMED_IN_MAIN", all_expected_prs_confirmed_in_main),
        ("FROZEN_CORE_INTEGRITY_REQUIRED", frozen_core_integrity_verified),
        ("NO_UNRESOLVED_MERGE_CONFLICTS_REQUIRED", no_unresolved_merge_conflicts),
        ("NO_UNEXPECTED_MAIN_DRIFT_REQUIRED", no_unexpected_main_drift),
    ):
        if flag is not True:
            blockers.append(label)

    if deploy_executed_during_sequence is not False:
        blockers.append("DEPLOY_MUST_REMAIN_FALSE")
    if worker_activated_during_sequence is not False:
        blockers.append("WORKER_MUST_REMAIN_FALSE")
    if provider_activated_during_sequence is not False:
        blockers.append("PROVIDER_ACTIVATION_MUST_REMAIN_FALSE")
    if production_persistence_activated_during_sequence is not False:
        blockers.append("PRODUCTION_PERSISTENCE_ACTIVATION_MUST_REMAIN_FALSE")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "main_sha": main_sha,
        "main_tree_sha": tree_sha,
        "merged_prs": merged,
        "owner_stack_files": files,
        "workflow_snapshot": {
            name: workflow_map.get(name, False)
            for name in POST_MERGE_REQUIRED_WORKFLOWS
        },
        "merge_journal_digest": journal_digest,
        "rollback_plan_digest": rollback_digest,
        "full_stack_certification_digest": stack_cert_digest,
        "full_stack_certification_on_main": full_stack_certification_on_main is True,
        "all_expected_prs_confirmed_in_main": all_expected_prs_confirmed_in_main is True,
        "frozen_core_integrity_verified": frozen_core_integrity_verified is True,
        "no_unresolved_merge_conflicts": no_unresolved_merge_conflicts is True,
        "no_unexpected_main_drift": no_unexpected_main_drift is True,
    }

    return {
        "schema": CERT_SCHEMA,
        "state": (
            "POST_MERGE_MAIN_CERTIFIED"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "post_merge_certification_digest": _digest(material) if not blockers else "",
        "product_stack_closed": not blockers,
        "governance_prs_included_in_product_certification": False,
        "branch_cleanup_may_be_evaluated": not blockers,
        "branch_deletion_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "production_persistence_activation_authorized": False,
        "repository_mutation_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def build_branch_cleanup_plan(
    post_merge_certification: Mapping[str, Any] | None,
    branch_observations: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Classify branch deletion eligibility without deleting anything."""
    cert = dict(post_merge_certification or {})
    blockers: list[str] = []

    if cert.get("schema") != CERT_SCHEMA:
        blockers.append("POST_MERGE_CERTIFICATION_SCHEMA_MISMATCH")
    if cert.get("state") != "POST_MERGE_MAIN_CERTIFIED":
        blockers.append("POST_MERGE_MAIN_CERTIFICATION_REQUIRED")
    if cert.get("branch_deletion_authorized") is not False:
        blockers.append("CERTIFICATION_MUST_NOT_PREAUTHORIZE_BRANCH_DELETION")

    rows = [
        dict(row)
        for row in list(branch_observations or [])
        if isinstance(row, Mapping)
    ]
    by_branch = {
        _clean(row.get("branch"), 300): row
        for row in rows
        if _clean(row.get("branch"), 300)
    }

    cleanup_rows: list[dict[str, Any]] = []
    eligible_branches: list[str] = []
    blocked_branches: list[str] = []

    # Reverse child-before-parent order is the safest cleanup order.
    for item in reversed(STACK):
        branch = item["head"]
        row = by_branch.get(branch)
        row_blockers: list[str] = []

        if row is None:
            row_blockers.append("BRANCH_OBSERVATION_MISSING")
            exists = False
        else:
            exists = row.get("exists") is True
            if row.get("exists") is not True:
                row_blockers.append("BRANCH_DOES_NOT_EXIST_OR_ALREADY_REMOVED")
            if row.get("merged_to_main_verified") is not True:
                row_blockers.append("MERGE_TO_MAIN_EVIDENCE_REQUIRED")
            if row.get("head_evidence_preserved") is not True:
                row_blockers.append("HEAD_EVIDENCE_PRESERVATION_REQUIRED")
            if row.get("pr_metadata_preserved") is not True:
                row_blockers.append("PR_METADATA_PRESERVATION_REQUIRED")
            if row.get("workflow_evidence_preserved") is not True:
                row_blockers.append("WORKFLOW_EVIDENCE_PRESERVATION_REQUIRED")
            if not _sha256(row.get("evidence_manifest_digest")):
                row_blockers.append("EVIDENCE_MANIFEST_DIGEST_REQUIRED")

            dependents = [
                _clean(value, 300)
                for value in list(row.get("open_pr_dependents") or [])
                if _clean(value, 300)
            ]
            if dependents:
                row_blockers.append("OPEN_PR_DEPENDENCY_PRESENT")

            try:
                unmerged_count = int(row.get("unmerged_commit_count"))
            except Exception:
                unmerged_count = -1
                row_blockers.append("UNMERGED_COMMIT_COUNT_INVALID")
            if unmerged_count != 0:
                row_blockers.append("UNMERGED_COMMITS_PRESENT")

            if row.get("protected_branch") is True:
                row_blockers.append("PROTECTED_BRANCH_MUST_NOT_BE_DELETED")
            if row.get("is_default_branch") is True:
                row_blockers.append("DEFAULT_BRANCH_MUST_NOT_BE_DELETED")

        row_blockers = list(dict.fromkeys(row_blockers))
        eligible = bool(row is not None and exists and not row_blockers)
        if eligible:
            eligible_branches.append(branch)
        else:
            blocked_branches.append(branch)

        cleanup_rows.append(
            {
                "pr_number": item["number"],
                "branch": branch,
                "state": "ELIGIBLE_FOR_OWNER_CLEANUP_REVIEW" if eligible else "BLOCKED",
                "blockers": row_blockers,
                "open_pr_dependents": (
                    list(row.get("open_pr_dependents") or []) if row else []
                ),
                "branch_deletion_authorized": False,
                "branch_deleted": False,
                "repository_mutation_performed": False,
            }
        )

    blockers = list(dict.fromkeys(blockers))
    material = {
        "post_merge_certification_digest": _sha256(
            cert.get("post_merge_certification_digest")
        ),
        "cleanup_order": [row["branch"] for row in cleanup_rows],
        "eligible_branches": eligible_branches,
        "blocked_branches": blocked_branches,
    }

    return {
        "schema": CLEANUP_SCHEMA,
        "state": (
            "BRANCH_CLEANUP_PLAN_READY"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "cleanup_order": [row["branch"] for row in cleanup_rows],
        "rows": cleanup_rows,
        "eligible_branches": eligible_branches,
        "blocked_branches": blocked_branches,
        "governance_branches_excluded_from_product_cleanup": list(GOVERNANCE_BRANCHES),
        "governance_branches_require_separate_disposition": True,
        "child_before_parent_cleanup_order": True,
        "branch_deletion_requires_separate_owner_authorization": True,
        "branch_deletion_authorized": False,
        "branch_deleted": False,
        "repository_mutation_performed": False,
        "plan_digest": _digest(material) if not blockers else "",
        "executes_action": False,
    }


def verify_branch_cleanup_candidate(
    cleanup_plan: Mapping[str, Any] | None,
    *,
    branch: Any,
) -> dict[str, Any]:
    """Verify one branch is eligible for review. Never authorizes deletion."""
    plan = dict(cleanup_plan or {})
    target = _clean(branch, 300)
    blockers: list[str] = []

    if plan.get("schema") != CLEANUP_SCHEMA:
        blockers.append("CLEANUP_PLAN_SCHEMA_MISMATCH")
    if plan.get("state") != "BRANCH_CLEANUP_PLAN_READY":
        blockers.append("READY_CLEANUP_PLAN_REQUIRED")

    row = next(
        (
            dict(item)
            for item in list(plan.get("rows") or [])
            if isinstance(item, Mapping)
            and _clean(item.get("branch"), 300) == target
        ),
        None,
    )
    if row is None:
        blockers.append("BRANCH_NOT_IN_PRODUCT_CLEANUP_PLAN")
    else:
        if row.get("state") != "ELIGIBLE_FOR_OWNER_CLEANUP_REVIEW":
            blockers.append("BRANCH_NOT_ELIGIBLE")
        if row.get("blockers"):
            blockers.append("BRANCH_HAS_CLEANUP_BLOCKERS")
        if row.get("open_pr_dependents"):
            blockers.append("OPEN_PR_DEPENDENCY_PRESENT")
        if row.get("branch_deletion_authorized") is not False:
            blockers.append("BRANCH_MUST_NOT_BE_PREAUTHORIZED")
        if row.get("branch_deleted") is not False:
            blockers.append("BRANCH_MUST_NOT_ALREADY_BE_MARKED_DELETED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "CLEANUP_CANDIDATE_VALID" if not blockers else "BLOCKED",
        "valid": not blockers,
        "blockers": blockers,
        "branch": target,
        "owner_authorization_still_required": True,
        "branch_deletion_authorized": False,
        "branch_deleted": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def post_merge_cleanup_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "product_prs": list(PRODUCT_PRS),
        "product_branch_count": len(PRODUCT_BRANCHES),
        "product_file_count": len(PRODUCT_FILES),
        "post_merge_full_stack_certification_on_main_required": True,
        "post_merge_quality_gate_required": True,
        "post_merge_release_readiness_required": True,
        "post_merge_core_certification_required": True,
        "post_merge_core_security_gate_required": True,
        "frozen_core_integrity_required": True,
        "merge_journal_required": True,
        "rollback_plan_digest_required": True,
        "zero_deploy_during_sequence_required": True,
        "zero_worker_activation_during_sequence_required": True,
        "zero_provider_activation_during_sequence_required": True,
        "zero_production_persistence_activation_during_sequence_required": True,
        "branch_cleanup_only_after_main_certification": True,
        "branch_cleanup_child_before_parent": True,
        "open_pr_dependency_blocks_branch_deletion": True,
        "unmerged_commits_block_branch_deletion": True,
        "evidence_preservation_required_before_branch_deletion": True,
        "default_branch_deletion_allowed": False,
        "protected_branch_deletion_allowed": False,
        "governance_branches_require_separate_disposition": True,
        "automatic_branch_deletion_allowed": False,
        "branch_deletion_requires_separate_owner_authorization": True,
        "branch_deletion_authorized": False,
        "branch_deleted": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "production_persistence_activation_authorized": False,
        "repository_mutation_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CERT_SCHEMA",
    "CLEANUP_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "PRODUCT_PRS",
    "PRODUCT_BRANCHES",
    "PRODUCT_FILES",
    "POST_MERGE_REQUIRED_WORKFLOWS",
    "GOVERNANCE_BRANCHES",
    "build_post_merge_main_certification",
    "build_branch_cleanup_plan",
    "verify_branch_cleanup_candidate",
    "post_merge_cleanup_policy",
]
