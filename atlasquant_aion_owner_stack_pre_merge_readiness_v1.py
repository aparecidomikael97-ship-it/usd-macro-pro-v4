"""AION Owner Stack Pre-Merge Readiness V1.

Pure, non-mutating readiness contract for the stacked owner-facing PR line
#1015 through #1029 as observed on 2026-10-08.

This module pins:
- the current main SHA;
- exact PR order, bases, heads and head SHAs;
- exact four-file delta for every PR;
- required successful workflow names.

A positive result is only READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW.
It never authorizes or performs a merge, retarget, rebase, deploy, Worker
activation, provider activation or any production/external action.

Important stacked-PR rule:
after a parent is merged into main, the next child must be re-evaluated against
the new main before it may proceed. The child must preserve its exact intended
file delta and rerun its required gate(s). Readiness never carries forward
implicitly across a changed base.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA = "ATLASQUANT_AION_OWNER_STACK_PRE_MERGE_READINESS_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_PRE_MERGE_VERIFY_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_MERGE_SEQUENCE_PLAN_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_OWNER_STACK_PRE_MERGE_POLICY_V1"

PINNED_MAIN_SHA = "5744b2b7b17c84331e6f27c569064993ff587782"

STACK = (
    {
        "number": 1015,
        "title": "IMPLEMENTATION SAFE — AION Owner Experience V1",
        "base": "main",
        "head": "impl/aion-owner-experience-v1-20261008",
        "head_sha": "e14f01b03b072c4bc20694e488c1c399ab8c97d1",
        "required_workflows": (
            "AION Owner Experience V1",
            "Quality tests",
            "AtlasQuant - Release Readiness",
            "AION Core Certification",
            "AION Core Security Gate",
        ),
        "files": (
            ".github/workflows/aion-owner-experience-v1.yml",
            "atlasquant_aion_owner_experience_v1.py",
            "docs/aion/AION_OWNER_EXPERIENCE_V1.md",
            "tests/test_atlasquant_aion_owner_experience_v1.py",
        ),
    },
    {
        "number": 1016,
        "title": "IMPLEMENTATION SAFE — AION Cognitive Memory + Continuity V1",
        "base": "impl/aion-owner-experience-v1-20261008",
        "head": "impl/aion-cognitive-memory-continuity-v1-20261008",
        "head_sha": "9f5bdcd10f40917400a28c205efa41dcb86df90d",
        "required_workflows": ("AION Cognitive Memory Continuity V1",),
        "files": (
            ".github/workflows/aion-cognitive-memory-continuity-v1.yml",
            "atlasquant_aion_cognitive_continuity_v1.py",
            "docs/aion/AION_COGNITIVE_MEMORY_CONTINUITY_V1.md",
            "tests/test_atlasquant_aion_cognitive_continuity_v1.py",
        ),
    },
    {
        "number": 1017,
        "title": "IMPLEMENTATION SAFE — AION Secure Local Agent V1",
        "base": "impl/aion-cognitive-memory-continuity-v1-20261008",
        "head": "impl/aion-secure-local-agent-v1-20261008",
        "head_sha": "02bc4f3550ba40a205d93a0cac43e7fe4358e1ea",
        "required_workflows": ("AION Secure Local Agent V1",),
        "files": (
            ".github/workflows/aion-secure-local-agent-v1.yml",
            "atlasquant_aion_secure_local_agent_v1.py",
            "docs/aion/AION_SECURE_LOCAL_AGENT_V1.md",
            "tests/test_atlasquant_aion_secure_local_agent_v1.py",
        ),
    },
    {
        "number": 1018,
        "title": "IMPLEMENTATION SAFE — AION Local Action Audit Receipt V1",
        "base": "impl/aion-secure-local-agent-v1-20261008",
        "head": "impl/aion-local-action-audit-receipt-v1-20261008",
        "head_sha": "ca165bac3928bdd0be61b9ff580abdd7ed823d44",
        "required_workflows": ("AION Local Action Audit Receipt V1",),
        "files": (
            ".github/workflows/aion-local-action-audit-receipt-v1.yml",
            "atlasquant_aion_local_action_audit_receipt_v1.py",
            "docs/aion/AION_LOCAL_ACTION_AUDIT_RECEIPT_V1.md",
            "tests/test_atlasquant_aion_local_action_audit_receipt_v1.py",
        ),
    },
    {
        "number": 1019,
        "title": "IMPLEMENTATION SAFE — AION Secure Desktop Runtime Blueprint V1",
        "base": "impl/aion-local-action-audit-receipt-v1-20261008",
        "head": "impl/aion-secure-desktop-runtime-blueprint-v1-20261008",
        "head_sha": "4132ff6e04265a4b44f9b011ec8a9c4f01724073",
        "required_workflows": ("AION Secure Desktop Runtime Blueprint V1",),
        "files": (
            ".github/workflows/aion-secure-desktop-runtime-blueprint-v1.yml",
            "atlasquant_aion_secure_desktop_runtime_blueprint_v1.py",
            "docs/aion/AION_SECURE_DESKTOP_RUNTIME_BLUEPRINT_V1.md",
            "tests/test_atlasquant_aion_secure_desktop_runtime_blueprint_v1.py",
        ),
    },
    {
        "number": 1020,
        "title": "IMPLEMENTATION SAFE — AION Voice + Hotword Runtime V1",
        "base": "impl/aion-secure-desktop-runtime-blueprint-v1-20261008",
        "head": "impl/aion-voice-hotword-runtime-v1-20261008",
        "head_sha": "a19f46e6dbf1a3f4e92b9d6439eaf95e58b19543",
        "required_workflows": ("AION Voice Hotword Runtime V1",),
        "files": (
            ".github/workflows/aion-voice-hotword-runtime-v1.yml",
            "atlasquant_aion_voice_hotword_runtime_v1.py",
            "docs/aion/AION_VOICE_HOTWORD_RUNTIME_V1.md",
            "tests/test_atlasquant_aion_voice_hotword_runtime_v1.py",
        ),
    },
    {
        "number": 1021,
        "title": "IMPLEMENTATION SAFE — AION Teaching + Meeting Orchestrator V1",
        "base": "impl/aion-voice-hotword-runtime-v1-20261008",
        "head": "impl/aion-teaching-meeting-orchestrator-v1-20261008",
        "head_sha": "ef2be130743aba4d9910bb0063cb339dec956009",
        "required_workflows": ("AION Teaching Meeting Orchestrator V1",),
        "files": (
            ".github/workflows/aion-teaching-meeting-orchestrator-v1.yml",
            "atlasquant_aion_teaching_meeting_orchestrator_v1.py",
            "docs/aion/AION_TEACHING_MEETING_ORCHESTRATOR_V1.md",
            "tests/test_atlasquant_aion_teaching_meeting_orchestrator_v1.py",
        ),
    },
    {
        "number": 1022,
        "title": "IMPLEMENTATION SAFE — AION Presentation Artifact + Control V1",
        "base": "impl/aion-teaching-meeting-orchestrator-v1-20261008",
        "head": "impl/aion-presentation-artifact-control-v1-20261008",
        "head_sha": "a46fe0be5f2578821c7f9dbc2ceac2c1fafc5321",
        "required_workflows": ("AION Presentation Artifact Control V1",),
        "files": (
            ".github/workflows/aion-presentation-artifact-control-v1.yml",
            "atlasquant_aion_presentation_artifact_control_v1.py",
            "docs/aion/AION_PRESENTATION_ARTIFACT_CONTROL_V1.md",
            "tests/test_atlasquant_aion_presentation_artifact_control_v1.py",
        ),
    },
    {
        "number": 1023,
        "title": "IMPLEMENTATION SAFE — AION Advisor + Decision Support V1",
        "base": "impl/aion-presentation-artifact-control-v1-20261008",
        "head": "impl/aion-advisor-decision-support-v1-20261008",
        "head_sha": "13607c00ebdb57156abe3c0ceb806cdf82d93597",
        "required_workflows": ("AION Advisor Decision Support V1",),
        "files": (
            ".github/workflows/aion-advisor-decision-support-v1.yml",
            "atlasquant_aion_advisor_decision_support_v1.py",
            "docs/aion/AION_ADVISOR_DECISION_SUPPORT_V1.md",
            "tests/test_atlasquant_aion_advisor_decision_support_v1.py",
        ),
    },
    {
        "number": 1024,
        "title": "IMPLEMENTATION SAFE — AION Contract + Communication Draft & Approval V1",
        "base": "impl/aion-advisor-decision-support-v1-20261008",
        "head": "impl/aion-contract-communication-draft-approval-v1-20261008",
        "head_sha": "2994c52d04124aaada8b577dd24fe328c80a2908",
        "required_workflows": ("AION Contract Communication Draft Approval V1",),
        "files": (
            ".github/workflows/aion-contract-communication-draft-approval-v1.yml",
            "atlasquant_aion_contract_communication_draft_approval_v1.py",
            "docs/aion/AION_CONTRACT_COMMUNICATION_DRAFT_APPROVAL_V1.md",
            "tests/test_atlasquant_aion_contract_communication_draft_approval_v1.py",
        ),
    },
    {
        "number": 1025,
        "title": "IMPLEMENTATION SAFE — AION Approval + Outbound Dispatch Bridge V1",
        "base": "impl/aion-contract-communication-draft-approval-v1-20261008",
        "head": "impl/aion-approval-outbound-dispatch-bridge-v1-20261008",
        "head_sha": "460932516f9a17fa5baa19bb0f0e6cf7c0963df2",
        "required_workflows": ("AION Approval Outbound Dispatch Bridge V1",),
        "files": (
            ".github/workflows/aion-approval-outbound-dispatch-bridge-v1.yml",
            "atlasquant_aion_approval_outbound_dispatch_bridge_v1.py",
            "docs/aion/AION_APPROVAL_OUTBOUND_DISPATCH_BRIDGE_V1.md",
            "tests/test_atlasquant_aion_approval_outbound_dispatch_bridge_v1.py",
        ),
    },
    {
        "number": 1026,
        "title": "IMPLEMENTATION SAFE — AION Outbound Execution Authorization + Durable Dispatch V1",
        "base": "impl/aion-approval-outbound-dispatch-bridge-v1-20261008",
        "head": "impl/aion-outbound-execution-authorization-durable-dispatch-v1-20261008",
        "head_sha": "f3f3d82205590f7b780ecf30fd29afcd18d703b7",
        "required_workflows": (
            "AION Outbound Execution Authorization Durable Dispatch V1",
        ),
        "files": (
            ".github/workflows/aion-outbound-execution-authorization-durable-dispatch-v1.yml",
            "atlasquant_aion_outbound_execution_authorization_durable_dispatch_v1.py",
            "docs/aion/AION_OUTBOUND_EXECUTION_AUTHORIZATION_DURABLE_DISPATCH_V1.md",
            "tests/test_atlasquant_aion_outbound_execution_authorization_durable_dispatch_v1.py",
        ),
    },
    {
        "number": 1027,
        "title": "IMPLEMENTATION SAFE — AION Sealed Provider Outcome + Reconciliation V1",
        "base": "impl/aion-outbound-execution-authorization-durable-dispatch-v1-20261008",
        "head": "impl/aion-sealed-provider-outcome-reconciliation-v1-20261008",
        "head_sha": "2b3a3de8e0e6d5f48dbd2c2edf3620c7ece660d8",
        "required_workflows": ("AION Sealed Provider Outcome Reconciliation V1",),
        "files": (
            ".github/workflows/aion-sealed-provider-outcome-reconciliation-v1.yml",
            "atlasquant_aion_sealed_provider_outcome_reconciliation_v1.py",
            "docs/aion/AION_SEALED_PROVIDER_OUTCOME_RECONCILIATION_V1.md",
            "tests/test_atlasquant_aion_sealed_provider_outcome_reconciliation_v1.py",
        ),
    },
    {
        "number": 1028,
        "title": "IMPLEMENTATION SAFE — AION Outbound Terminal Audit Certificate V1",
        "base": "impl/aion-sealed-provider-outcome-reconciliation-v1-20261008",
        "head": "impl/aion-outbound-terminal-audit-certificate-v1-20261008",
        "head_sha": "7187806300d75114da41541fbb7b1928e474ac48",
        "required_workflows": ("AION Outbound Terminal Audit Certificate V1",),
        "files": (
            ".github/workflows/aion-outbound-terminal-audit-certificate-v1.yml",
            "atlasquant_aion_outbound_terminal_audit_certificate_v1.py",
            "docs/aion/AION_OUTBOUND_TERMINAL_AUDIT_CERTIFICATE_V1.md",
            "tests/test_atlasquant_aion_outbound_terminal_audit_certificate_v1.py",
        ),
    },
    {
        "number": 1029,
        "title": "IMPLEMENTATION SAFE — AION Owner Stack Integration Certification V1",
        "base": "impl/aion-outbound-terminal-audit-certificate-v1-20261008",
        "head": "impl/aion-owner-stack-integration-certification-v1-20261008",
        "head_sha": "ad837c2face371526c3c3a29a97e3052e14908b4",
        "required_workflows": ("AION Owner Stack Integration Certification V1",),
        "files": (
            ".github/workflows/aion-owner-stack-integration-certification-v1.yml",
            "atlasquant_aion_owner_stack_integration_certification_v1.py",
            "docs/aion/AION_OWNER_STACK_INTEGRATION_CERTIFICATION_V1.md",
            "tests/test_atlasquant_aion_owner_stack_integration_certification_v1.py",
        ),
    },
)


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


def _text(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _workflow_success_map(value: Any) -> dict[str, bool]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = _text(row.get("name"), 220)
        if not name:
            continue
        out[name] = (
            _text(row.get("status"), 40).lower() == "completed"
            and _text(row.get("conclusion"), 40).lower() == "success"
        )
    return out


def _file_rows(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, (list, tuple)) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str):
            out.append({"filename": row, "status": "added", "deletions": 0})
        elif isinstance(row, Mapping):
            out.append(
                {
                    "filename": _text(row.get("filename"), 400),
                    "status": _text(row.get("status"), 40).lower(),
                    "deletions": int(row.get("deletions") or 0),
                }
            )
    return out


def pinned_stack_manifest() -> dict[str, Any]:
    rows = []
    for index, item in enumerate(STACK):
        rows.append(
            {
                "order": index + 1,
                "number": item["number"],
                "title": item["title"],
                "base": item["base"],
                "head": item["head"],
                "head_sha": item["head_sha"],
                "required_workflows": list(item["required_workflows"]),
                "files": list(item["files"]),
            }
        )
    material = {
        "main_sha": PINNED_MAIN_SHA,
        "stack": rows,
    }
    return {
        "schema": SCHEMA,
        "main_sha": PINNED_MAIN_SHA,
        "stack": rows,
        "stack_size": len(rows),
        "stack_manifest_digest": _digest(material),
        "merge_authorized": False,
        "executes_action": False,
    }


def evaluate_pre_merge_readiness(
    observed_prs: Sequence[Mapping[str, Any]] | None,
    *,
    observed_main_sha: Any,
) -> dict[str, Any]:
    """Validate the exact current stacked snapshot. Any drift blocks."""
    blockers: list[str] = []
    main_sha = _text(observed_main_sha, 60)
    if main_sha != PINNED_MAIN_SHA:
        blockers.append("MAIN_SHA_DRIFT")

    rows = [dict(row) for row in list(observed_prs or []) if isinstance(row, Mapping)]
    by_number: dict[int, dict[str, Any]] = {}
    for row in rows:
        try:
            number = int(row.get("number"))
        except Exception:
            blockers.append("INVALID_PR_NUMBER")
            continue
        if number in by_number:
            blockers.append(f"DUPLICATE_PR:{number}")
        else:
            by_number[number] = row

    unexpected = sorted(set(by_number) - {item["number"] for item in STACK})
    blockers.extend(f"UNEXPECTED_PR:{number}" for number in unexpected)

    checks: list[dict[str, Any]] = []
    for item in STACK:
        number = item["number"]
        row = by_number.get(number)
        pr_blockers: list[str] = []
        if row is None:
            pr_blockers.append("PR_MISSING")
            checks.append(
                {
                    "number": number,
                    "state": "BLOCKED",
                    "blockers": pr_blockers,
                }
            )
            blockers.append(f"PR_{number}:PR_MISSING")
            continue

        if _text(row.get("state"), 40).lower() != "open":
            pr_blockers.append("PR_NOT_OPEN")
        if row.get("draft") is not True:
            pr_blockers.append("PR_MUST_REMAIN_DRAFT_BEFORE_OWNER_AUTHORIZATION")
        if row.get("mergeable") is not True:
            pr_blockers.append("PR_NOT_MERGEABLE")
        if _text(row.get("base"), 260) != item["base"]:
            pr_blockers.append("BASE_DRIFT")
        if _text(row.get("head"), 260) != item["head"]:
            pr_blockers.append("HEAD_BRANCH_DRIFT")
        if _text(row.get("head_sha"), 60) != item["head_sha"]:
            pr_blockers.append("HEAD_SHA_DRIFT")

        files = _file_rows(row.get("files"))
        observed_names = [entry["filename"] for entry in files]
        if sorted(observed_names) != sorted(item["files"]):
            pr_blockers.append("FILE_DELTA_DRIFT")
        if len(files) != 4:
            pr_blockers.append("FOUR_FILE_DELTA_REQUIRED")
        for entry in files:
            if entry["status"] not in {"added", "modified"}:
                pr_blockers.append("FILE_STATUS_NOT_ALLOWED:" + entry["filename"])
            if entry["deletions"] != 0:
                pr_blockers.append("DELETION_NOT_ALLOWED:" + entry["filename"])

        workflow_map = _workflow_success_map(row.get("workflows"))
        for workflow in item["required_workflows"]:
            if workflow_map.get(workflow) is not True:
                pr_blockers.append("REQUIRED_WORKFLOW_NOT_GREEN:" + workflow)

        pr_blockers = list(dict.fromkeys(pr_blockers))
        checks.append(
            {
                "number": number,
                "state": "MATCH" if not pr_blockers else "BLOCKED",
                "blockers": pr_blockers,
                "base": _text(row.get("base"), 260),
                "head": _text(row.get("head"), 260),
                "head_sha": _text(row.get("head_sha"), 60),
                "file_count": len(files),
                "required_workflows": list(item["required_workflows"]),
            }
        )
        blockers.extend(f"PR_{number}:{reason}" for reason in pr_blockers)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "pinned_main_sha": PINNED_MAIN_SHA,
        "observed_main_sha": main_sha,
        "checks": checks,
    }
    return {
        "schema": VERIFY_SCHEMA,
        "state": (
            "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        "pinned_main_sha": PINNED_MAIN_SHA,
        "observed_main_sha": main_sha,
        "stack_size": len(STACK),
        "checks": checks,
        "readiness_digest": _digest(material),
        "snapshot_pinned": True,
        "snapshot_invalidated_by_main_change": True,
        "snapshot_invalidated_by_pr_head_change": True,
        "snapshot_invalidated_by_base_change": True,
        "snapshot_invalidated_by_file_delta_change": True,
        "snapshot_invalidated_by_gate_regression": True,
        "requires_human_owner_review": not blockers,
        "merge_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "external_action_authorized": False,
        "merge_executed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


def build_merge_sequence_plan(
    readiness: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Create the only safe sequence; no Git mutation is performed."""
    raw = dict(readiness or {})
    if raw.get("state") != "READY_FOR_HUMAN_OWNER_MERGE_SEQUENCE_REVIEW":
        return {
            "schema": PLAN_SCHEMA,
            "state": "BLOCKED",
            "blockers": ["VALID_PRE_MERGE_READINESS_REQUIRED"],
            "steps": [],
            "merge_authorized": False,
            "executes_action": False,
        }

    steps: list[dict[str, Any]] = []
    for index, item in enumerate(STACK):
        parent = STACK[index - 1] if index else None
        step = {
            "order": index + 1,
            "pr_number": item["number"],
            "title": item["title"],
            "pinned_head_sha": item["head_sha"],
            "current_base": item["base"],
            "parent_pr_number": parent["number"] if parent else None,
            "explicit_human_owner_authorization_required": True,
            "previous_step_must_be_confirmed_merged": bool(parent),
            "main_must_be_refetched_immediately_before_step": True,
            "pr_must_be_open": True,
            "pr_must_be_mergeable": True,
            "draft_transition_requires_separate_owner_authorization": True,
            "if_base_changed_recompute_diff": True,
            "if_head_changed_rebuild_readiness_snapshot": True,
            "expected_file_delta": list(item["files"]),
            "expected_file_count": 4,
            "deletions_allowed": False,
            "required_workflows_to_rerun": list(item["required_workflows"]),
            "all_required_workflows_must_be_green_on_current_head": True,
            "no_deploy": True,
            "no_worker_activation": True,
            "no_provider_activation": True,
            "no_production_persistence_activation": True,
            "stop_on_any_ambiguity": True,
        }
        if parent:
            step.update(
                {
                    "child_base_must_be_re_evaluated_after_parent_merge": True,
                    "retarget_to_main_only_after_parent_is_confirmed_in_main": True,
                    "post_retarget_diff_must_still_equal_expected_file_delta": True,
                    "post_retarget_gate_rerun_required": True,
                    "old_readiness_does_not_carry_across_retarget": True,
                }
            )
        else:
            step.update(
                {
                    "child_base_must_be_re_evaluated_after_parent_merge": False,
                    "retarget_to_main_only_after_parent_is_confirmed_in_main": False,
                    "post_retarget_diff_must_still_equal_expected_file_delta": True,
                    "post_retarget_gate_rerun_required": False,
                    "old_readiness_does_not_carry_across_retarget": False,
                }
            )
        steps.append(step)

    return {
        "schema": PLAN_SCHEMA,
        "state": "MERGE_SEQUENCE_PLAN_READY",
        "blockers": [],
        "steps": steps,
        "step_count": len(steps),
        "merge_strategy": "STRICT_SEQUENTIAL_PARENT_BEFORE_CHILD",
        "squash_merge_permitted_only_with_explicit_owner_authorization": True,
        "branch_deletion_must_not_break_open_child_pr": True,
        "branch_deletion_should_be_deferred_until_children_are_rebased_or_retargeted": True,
        "after_final_pr_merge_main_full_stack_certification_required": True,
        "after_final_pr_merge_post_merge_main_audit_required": True,
        "rollback_plan_required_before_sequence": True,
        "merge_authorized": False,
        "retarget_authorized": False,
        "rebase_authorized": False,
        "branch_delete_authorized": False,
        "deploy_authorized": False,
        "worker_activation_authorized": False,
        "provider_activation_authorized": False,
        "production_persistence_activation_authorized": False,
        "merge_executed": False,
        "executes_action": False,
    }


def pre_merge_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "pinned_main_sha_required": True,
        "exact_linear_stack_required": True,
        "exact_head_sha_required": True,
        "exact_base_required_before_sequence": True,
        "exact_four_file_delta_required": True,
        "zero_deletion_delta_required": True,
        "required_gates_green_on_current_head": True,
        "drafts_remain_draft_until_owner_authorizes_transition": True,
        "strict_parent_before_child_sequence": True,
        "revalidate_after_each_parent_merge": True,
        "old_readiness_invalid_after_main_change": True,
        "old_readiness_invalid_after_head_change": True,
        "old_readiness_invalid_after_base_change": True,
        "old_readiness_invalid_after_file_delta_change": True,
        "old_readiness_invalid_after_gate_regression": True,
        "retarget_child_only_after_parent_confirmed_in_main": True,
        "rerun_child_gate_after_retarget": True,
        "post_retarget_exact_file_delta_required": True,
        "delete_parent_branch_before_child_retarget": False,
        "final_full_stack_certification_on_main_required": True,
        "final_post_merge_main_audit_required": True,
        "explicit_owner_authorization_required_for_each_mutation": True,
        "automatic_merge_allowed": False,
        "automatic_retarget_allowed": False,
        "automatic_rebase_allowed": False,
        "automatic_branch_delete_allowed": False,
        "automatic_deploy_allowed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "production_persistence_activation_allowed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "merge_executed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERIFY_SCHEMA",
    "PLAN_SCHEMA",
    "POLICY_SCHEMA",
    "PINNED_MAIN_SHA",
    "STACK",
    "pinned_stack_manifest",
    "evaluate_pre_merge_readiness",
    "build_merge_sequence_plan",
    "pre_merge_policy",
]
