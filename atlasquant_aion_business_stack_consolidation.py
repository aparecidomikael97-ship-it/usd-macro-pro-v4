"""AION BUSINESS Draft PR Stack Consolidation V1.

Read-only administrative manifest for the current BUSINESS stack. It verifies
ordering, base/head continuity, required CI evidence and draft/open posture.
It never merges, rebases, deploys, publishes, activates runtime or changes
provider/runtime state.

A green stack means only READY_FOR_ADMIN_REVIEW.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_STACK_CONSOLIDATION_V1"
VERSION = "1"
SNAPSHOT_DATE = "2026-09-30"
ROOT_BASE_BRANCH = "cursor/aion-business-external-attestation-review-v1-8499"

REQUIRED_CHECKS = (
    "test",
    "readiness",
    "AION adversarial contracts",
    "Supply-chain audit",
)

OPTIONAL_UI_CHECKS = (
    "ui-smoke",
    "mobile-dom",
)

CANONICAL_STACK = (
    {
        "pr": 398,
        "title": "AION BUSINESS: runtime readiness V1",
        "head_branch": "cursor/aion-business-runtime-readiness-v1-8499",
        "base_branch": ROOT_BASE_BRANCH,
        "head_sha": "2df2b18c4c207fefa08ed53c7fba1fc79e81c2d4",
    },
    {
        "pr": 399,
        "title": "AION BUSINESS: deterministic sandbox harness V1",
        "head_branch": "cursor/aion-business-sandbox-harness-v1-8499",
        "base_branch": "cursor/aion-business-runtime-readiness-v1-8499",
        "head_sha": "4e58997a0affd63d98048cee8e7d2cebc609bf0f",
    },
    {
        "pr": 400,
        "title": "AION BUSINESS: visual demo and admin training V1",
        "head_branch": "cursor/aion-business-demo-ui-v1-8499",
        "base_branch": "cursor/aion-business-sandbox-harness-v1-8499",
        "head_sha": "ac3b59631a3d1385c1a7b189a5157b6d21185bf1",
    },
    {
        "pr": 401,
        "title": "AION BUSINESS: guided admin training V1",
        "head_branch": "cursor/aion-business-guided-training-v1-8499",
        "base_branch": "cursor/aion-business-demo-ui-v1-8499",
        "head_sha": "85dad12d0c02844b452cc527eb3300e3fc724fa5",
    },
    {
        "pr": 402,
        "title": "AION BUSINESS: diagnostic and proposal simulator V1",
        "head_branch": "cursor/aion-business-diagnostic-proposal-simulator-v1-8499",
        "base_branch": "cursor/aion-business-guided-training-v1-8499",
        "head_sha": "db88fe73638aec5a288b5321eabd7a3a34ea6aae",
    },
    {
        "pr": 403,
        "title": "AION BUSINESS: client portal demo V1",
        "head_branch": "cursor/aion-business-client-portal-demo-v1-8499",
        "base_branch": "cursor/aion-business-diagnostic-proposal-simulator-v1-8499",
        "head_sha": "4086109ef0e5bd04d413a9293a5f2b0e55c32828",
    },
    {
        "pr": 404,
        "title": "AION BUSINESS: onboarding and implementation demo V1",
        "head_branch": "cursor/aion-business-onboarding-implementation-demo-v1-8499",
        "base_branch": "cursor/aion-business-client-portal-demo-v1-8499",
        "head_sha": "c7a0c82f67ee2c5283f5aca67a3f870146d1240e",
    },
    {
        "pr": 405,
        "title": "AION BUSINESS: customer success and SLA demo V1",
        "head_branch": "cursor/aion-business-customer-success-sla-demo-v1-8499",
        "base_branch": "cursor/aion-business-onboarding-implementation-demo-v1-8499",
        "head_sha": "6d852e013caff8e10ed7536824239512159ad933",
    },
    {
        "pr": 406,
        "title": "AION BUSINESS: client finance and capacity demo V1",
        "head_branch": "cursor/aion-business-client-finance-demo-v1-8499",
        "base_branch": "cursor/aion-business-customer-success-sla-demo-v1-8499",
        "head_sha": "d2ce8b9d25efd13ab845a20a13736ebcf8b08c29",
    },
    {
        "pr": 407,
        "title": "AION BUSINESS: trend and opportunity intelligence V1",
        "head_branch": "cursor/aion-business-trend-opportunity-intelligence-v1-8499",
        "base_branch": "cursor/aion-business-client-finance-demo-v1-8499",
        "head_sha": "52fa1c9f87b91e268265898bb1ddf20dc2a99b96",
    },
    {
        "pr": 408,
        "title": "AION BUSINESS: commercial acquisition and client journey demo V1",
        "head_branch": "cursor/aion-business-commercial-acquisition-demo-v1-8499",
        "base_branch": "cursor/aion-business-trend-opportunity-intelligence-v1-8499",
        "head_sha": "b5704300aede1f2e0233fe13799f0770bf92ae25",
    },
    {
        "pr": 409,
        "title": "AION BUSINESS: integration hub readiness V1",
        "head_branch": "cursor/aion-business-integration-hub-readiness-v1-8499",
        "base_branch": "cursor/aion-business-commercial-acquisition-demo-v1-8499",
        "head_sha": "a96ecc95adbbcb5d79262dc807b1a96ed03d7db3",
    },
    {
        "pr": 410,
        "title": "AION BUSINESS: privacy LGPD and audit governance V1",
        "head_branch": "cursor/aion-business-privacy-audit-governance-v1-8499",
        "base_branch": "cursor/aion-business-integration-hub-readiness-v1-8499",
        "head_sha": "2d05143bc7a708eda6c3c8cd77080f94fd7a3129",
    },
    {
        "pr": 411,
        "title": "AION BUSINESS: master readiness panel V1",
        "head_branch": "cursor/aion-business-master-readiness-panel-v1-8499",
        "base_branch": "cursor/aion-business-privacy-audit-governance-v1-8499",
        "head_sha": "9f4527865edb632a67a9671100f4d5ce5a55d9da",
    },
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _seq(value: Any, limit: int = 100) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return list(value)[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def canonical_stack_manifest() -> list[dict[str, Any]]:
    return [dict(row) for row in CANONICAL_STACK]


def default_green_evidence() -> list[dict[str, Any]]:
    """Frozen CI snapshot verified on 2026-09-30; never treated as live GitHub data."""
    rows = []
    for item in CANONICAL_STACK:
        checks = {name: "success" for name in REQUIRED_CHECKS}
        if int(item["pr"]) >= 400:
            checks.update({name: "success" for name in OPTIONAL_UI_CHECKS})
        rows.append({
            **dict(item),
            "state": "open",
            "draft": True,
            "mergeable": True,
            "checks": checks,
            "evidence_date": SNAPSHOT_DATE,
            "live_github_verified": False,
        })
    return rows


def validate_stack(records: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    rows = [dict(row) for row in _seq(records, 50) if isinstance(row, Mapping)]
    expected = canonical_stack_manifest()
    by_pr = {int(row.get("pr")): row for row in rows if isinstance(row.get("pr"), int)}
    results = []
    previous_head_branch = ROOT_BASE_BRANCH

    for expected_row in expected:
        pr = int(expected_row["pr"])
        actual = _mapping(by_pr.get(pr))
        missing = not bool(actual)
        checks = _mapping(actual.get("checks"))
        required_checks_ok = bool(
            checks and all(_clean(checks.get(name), 40).lower() == "success" for name in REQUIRED_CHECKS)
        )
        expected_optional = pr >= 400
        optional_ui_ok = (
            all(_clean(checks.get(name), 40).lower() == "success" for name in OPTIONAL_UI_CHECKS)
            if expected_optional else True
        )
        base_ok = _clean(actual.get("base_branch"), 220) == expected_row["base_branch"]
        expected_chain_ok = expected_row["base_branch"] == previous_head_branch
        head_branch_ok = _clean(actual.get("head_branch"), 220) == expected_row["head_branch"]
        head_sha_ok = _clean(actual.get("head_sha"), 80) == expected_row["head_sha"]
        state_ok = _clean(actual.get("state"), 40).lower() == "open"
        draft_ok = actual.get("draft") is True
        mergeable_ok = actual.get("mergeable") is True

        passed = bool(
            not missing
            and base_ok
            and expected_chain_ok
            and head_branch_ok
            and head_sha_ok
            and state_ok
            and draft_ok
            and mergeable_ok
            and required_checks_ok
            and optional_ui_ok
        )
        results.append({
            "pr": pr,
            "title": expected_row["title"],
            "passed": passed,
            "missing": missing,
            "base_ok": base_ok,
            "expected_chain_ok": expected_chain_ok,
            "head_branch_ok": head_branch_ok,
            "head_sha_ok": head_sha_ok,
            "state_ok": state_ok,
            "draft_ok": draft_ok,
            "mergeable_ok": mergeable_ok,
            "required_checks_ok": required_checks_ok,
            "optional_ui_ok": optional_ui_ok,
        })
        previous_head_branch = expected_row["head_branch"]

    complete = bool(results and all(row["passed"] for row in results))
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "snapshot_date": SNAPSHOT_DATE,
        "state": "READY_FOR_ADMIN_REVIEW" if complete else "BLOCKED",
        "complete": complete,
        "pr_count": len(results),
        "passed_count": sum(1 for row in results if row["passed"]),
        "blocked_count": sum(1 for row in results if not row["passed"]),
        "rows": results,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def consolidation_preview(validation: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(validation)
    complete = row.get("state") == "READY_FOR_ADMIN_REVIEW" and row.get("complete") is True
    sequence = [
        {
            "order": index,
            "pr": item["pr"],
            "title": item["title"],
            "head_branch": item["head_branch"],
            "head_sha": item["head_sha"],
        }
        for index, item in enumerate(CANONICAL_STACK, start=1)
    ] if complete else []
    return {
        "schema": SCHEMA,
        "state": "ADMIN_DECISION_REQUIRED" if complete else "BLOCKED",
        "sequence": sequence,
        "strategy": "STACKED_ORDER_OLDEST_TO_NEWEST" if complete else "",
        "post_merge_validation_required": complete,
        "final_main_ci_required": complete,
        "final_production_sha_verification_required": complete,
        "merge_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def release_bundle_manifest(validation: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(validation)
    if row.get("state") != "READY_FOR_ADMIN_REVIEW" or row.get("complete") is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "bundle_digest": "",
            "executes_action": False,
        }
    payload = {
        "snapshot_date": SNAPSHOT_DATE,
        "root_base_branch": ROOT_BASE_BRANCH,
        "stack": canonical_stack_manifest(),
        "required_checks": list(REQUIRED_CHECKS),
        "optional_ui_checks": list(OPTIONAL_UI_CHECKS),
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BUNDLE_FROZEN_FOR_REVIEW",
        "bundle_digest": _digest(payload),
        "payload": payload,
        "merge_authorized": False,
        "deploy_authorized": False,
        "executes_action": False,
    }


def administrative_options(validation: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    row = _mapping(validation)
    ready = row.get("state") == "READY_FOR_ADMIN_REVIEW" and row.get("complete") is True
    if not ready:
        return [{
            "id": "FIX_BLOCKERS",
            "label": "Corrigir bloqueios antes de consolidar",
            "available": True,
            "executes_action": False,
        }]
    return [
        {
            "id": "KEEP_DRAFT_STACK",
            "label": "Manter stack em Draft para revisão adicional",
            "available": True,
            "executes_action": False,
        },
        {
            "id": "REQUEST_STACK_MERGE_REVIEW",
            "label": "Preparar revisão administrativa de merge em ordem",
            "available": True,
            "executes_action": False,
        },
        {
            "id": "FREEZE_BUNDLE",
            "label": "Congelar bundle e SHAs antes da decisão",
            "available": True,
            "executes_action": False,
        },
    ]


__all__ = [
    "SCHEMA",
    "VERSION",
    "SNAPSHOT_DATE",
    "ROOT_BASE_BRANCH",
    "REQUIRED_CHECKS",
    "OPTIONAL_UI_CHECKS",
    "CANONICAL_STACK",
    "canonical_stack_manifest",
    "default_green_evidence",
    "validate_stack",
    "consolidation_preview",
    "release_bundle_manifest",
    "administrative_options",
]
