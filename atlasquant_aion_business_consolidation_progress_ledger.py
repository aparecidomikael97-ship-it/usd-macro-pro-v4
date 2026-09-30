"""AION BUSINESS sequential consolidation progress ledger V1.

Maintains an offline, read-only ledger of verified post-merge receipts for the
canonical #394–#412 stack. It never performs merge, rollback, deploy or runtime
activation.

The ledger enforces:
- exact PR order;
- unique receipt digests;
- unique resulting main SHAs;
- rollback-reference continuity between consecutive steps;
- verified post-merge evidence only.

A complete ledger still requires a separate human completion review.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from atlasquant_aion_business_stack_consolidation_v2 import canonical_stack_manifest
from atlasquant_aion_business_consolidation_post_merge_verification import (
    SCHEMA as POST_MERGE_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_PROGRESS_LEDGER_V1"
VERSION = "1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")

COMPLETION_REQUIREMENTS = (
    "all_19_steps_verified",
    "final_main_ci_success",
    "final_ui_mobile_success",
    "final_main_sha_verified",
    "business_runtime_off",
    "deploy_decision_separate",
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def _rows(value: Any, limit: int = 100) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    out = []
    for row in list(value)[:limit]:
        if not isinstance(row, Mapping):
            return []
        out.append(dict(row))
    return out


def progress_ledger_template() -> dict[str, Any]:
    stack = canonical_stack_manifest()
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "ROOT_MAIN_SHA_REQUIRED",
        "stack_prs": [int(row["pr"]) for row in stack],
        "total_steps": len(stack),
        "completed_count": 0,
        "next_expected_pr": int(stack[0]["pr"]) if stack else None,
        "completion_requirements": list(COMPLETION_REQUIREMENTS),
        "ledger_complete": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "merge_authorized": False,
        "executes_action": False,
    }


def build_progress_ledger(
    verified_steps: Sequence[Mapping[str, Any]] | None,
    *,
    root_main_sha: Any,
) -> dict[str, Any]:
    stack = canonical_stack_manifest()
    stack_prs = [int(item["pr"]) for item in stack]
    rows = _rows(verified_steps, len(stack))
    root = _clean(root_main_sha, 80).lower()

    blockers = []
    if not _SHA40.fullmatch(root):
        blockers.append("root_main_sha")

    normalized = []
    seen_receipts = set()
    seen_main_shas = set()
    previous_main_sha = root

    for index, row in enumerate(rows):
        expected_pr = stack_prs[index] if index < len(stack_prs) else None
        target_pr = row.get("target_pr")
        receipt = _clean(row.get("verification_receipt_digest"), 128).lower()
        observed = _clean(row.get("observed_main_sha"), 80).lower()
        rollback = _clean(row.get("rollback_reference_sha"), 80).lower()

        row_blockers = []
        if row.get("schema") != POST_MERGE_SCHEMA:
            row_blockers.append("schema")
        if row.get("state") != "STEP_VERIFIED_FOR_NEXT_PREFLIGHT":
            row_blockers.append("state")
        if row.get("step_verified") is not True:
            row_blockers.append("step_verified")
        if row.get("next_preflight_allowed") is not True:
            row_blockers.append("next_preflight_allowed")
        if row.get("executes_action") is not False:
            row_blockers.append("unexpected_execution_path")
        if target_pr != expected_pr:
            row_blockers.append("target_pr_order")
        if not _DIGEST64.fullmatch(receipt):
            row_blockers.append("verification_receipt_digest")
        if receipt in seen_receipts:
            row_blockers.append("duplicate_receipt")
        if not _SHA40.fullmatch(observed):
            row_blockers.append("observed_main_sha")
        if observed in seen_main_shas:
            row_blockers.append("duplicate_main_sha")
        if not _SHA40.fullmatch(rollback) or rollback != previous_main_sha:
            row_blockers.append("rollback_chain")

        normalized.append({
            "position": index + 1,
            "target_pr": target_pr,
            "expected_pr": expected_pr,
            "verification_receipt_digest": receipt,
            "observed_main_sha": observed,
            "rollback_reference_sha": rollback,
            "passed": not row_blockers,
            "blockers": row_blockers,
        })

        if row_blockers:
            blockers.append(f"step_{index + 1}")
            break

        seen_receipts.add(receipt)
        seen_main_shas.add(observed)
        previous_main_sha = observed

    if len(rows) > len(stack):
        blockers.append("too_many_steps")

    valid_prefix_count = 0
    for row in normalized:
        if not row["passed"]:
            break
        valid_prefix_count += 1

    if blockers:
        state = "LEDGER_BLOCKED"
    elif valid_prefix_count == len(stack):
        state = "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED"
    elif valid_prefix_count == 0:
        state = "READY_FOR_FIRST_PREFLIGHT"
    else:
        state = "READY_FOR_NEXT_PREFLIGHT"

    next_expected_pr = (
        stack_prs[valid_prefix_count]
        if state in ("READY_FOR_FIRST_PREFLIGHT", "READY_FOR_NEXT_PREFLIGHT")
        and valid_prefix_count < len(stack_prs)
        else None
    )

    ledger_payload = {
        "root_main_sha": root,
        "entries": normalized[:valid_prefix_count],
        "completed_count": valid_prefix_count,
        "final_observed_main_sha": previous_main_sha if valid_prefix_count else root,
    } if not blockers and _SHA40.fullmatch(root) else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": state,
        "stack_prs": stack_prs,
        "total_steps": len(stack),
        "completed_count": valid_prefix_count,
        "next_expected_pr": next_expected_pr,
        "entries": normalized,
        "blockers": blockers,
        "root_main_sha": root if _SHA40.fullmatch(root) else "",
        "current_main_sha": previous_main_sha if valid_prefix_count else (root if _SHA40.fullmatch(root) else ""),
        "ledger_digest": _digest(ledger_payload) if ledger_payload else "",
        "ledger_complete": state == "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED",
        "next_preflight_allowed": state in ("READY_FOR_FIRST_PREFLIGHT", "READY_FOR_NEXT_PREFLIGHT"),
        "completion_review_required": state == "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED",
        "completion_requirements": list(COMPLETION_REQUIREMENTS),
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "merge_authorized": False,
        "executes_action": False,
    }


def completion_review_packet(
    ledger: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(ledger)
    ready = bool(
        row.get("schema") == SCHEMA
        and row.get("state") == "CONSOLIDATION_COMPLETE_REVIEW_REQUIRED"
        and row.get("ledger_complete") is True
        and row.get("completed_count") == row.get("total_steps")
        and _DIGEST64.fullmatch(_clean(row.get("ledger_digest"), 128).lower())
    )
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_CONSOLIDATION_COMPLETION_REVIEW_V1",
        "state": "FINAL_HUMAN_REVIEW_REQUIRED" if ready else "NOT_READY",
        "ledger_digest": _clean(row.get("ledger_digest"), 128).lower() if ready else "",
        "final_main_sha": _clean(row.get("current_main_sha"), 80).lower() if ready else "",
        "requirements": list(COMPLETION_REQUIREMENTS) if ready else [],
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "production_release_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "COMPLETION_REQUIREMENTS",
    "progress_ledger_template",
    "build_progress_ledger",
    "completion_review_packet",
]
