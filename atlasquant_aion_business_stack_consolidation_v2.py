"""AION BUSINESS Draft PR Stack Consolidation V2.

Read-only administrative manifest for the current AION Core + BUSINESS stack
#394–#412. It validates frozen branch/SHA/check evidence and prepares a merge
order preview, but never merges, rebases, deploys or activates runtime.

A green stack means only READY_FOR_ADMIN_REVIEW.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_BUSINESS_STACK_CONSOLIDATION_V2"
VERSION = "2"
SNAPSHOT_DATE = "2026-09-30"
ROOT_BASE_BRANCH = "main"

REQUIRED_CHECKS = (
    "test",
    "readiness",
    "AION adversarial contracts",
    "Supply-chain audit",
)

UI_CHECKS = (
    "ui-smoke",
    "mobile-dom",
)

CANONICAL_STACK = (
    {"pr":394,"title":"AION Core: overnight hardening, observability and recovery V2","head_branch":"cursor/aion-overnight-core-hardening-v2-8499","base_branch":"main","head_sha":"92978f6b453b4134bf16c754ab525268956f34ab"},
    {"pr":395,"title":"AION Core: validation gates and BUSINESS certification readiness V1","head_branch":"cursor/aion-core-validation-business-readiness-v1-8499","base_branch":"cursor/aion-overnight-core-hardening-v2-8499","head_sha":"86df2db8a8140a8ee740196c9b5ac3ed73b52be8"},
    {"pr":396,"title":"AION BUSINESS: certification package V1","head_branch":"cursor/aion-business-certification-package-v1-8499","base_branch":"cursor/aion-core-validation-business-readiness-v1-8499","head_sha":"85cf6b1dc63623b4c054940d96e2b25f0175bc6e"},
    {"pr":397,"title":"AION BUSINESS: external CI attestation and formal review V1","head_branch":"cursor/aion-business-external-attestation-review-v1-8499","base_branch":"cursor/aion-business-certification-package-v1-8499","head_sha":"586c00915909dce3bc8fc329ca8f2c2f12dbacf4"},
    {"pr":398,"title":"AION BUSINESS: runtime readiness V1","head_branch":"cursor/aion-business-runtime-readiness-v1-8499","base_branch":"cursor/aion-business-external-attestation-review-v1-8499","head_sha":"2df2b18c4c207fefa08ed53c7fba1fc79e81c2d4"},
    {"pr":399,"title":"AION BUSINESS: deterministic sandbox harness V1","head_branch":"cursor/aion-business-sandbox-harness-v1-8499","base_branch":"cursor/aion-business-runtime-readiness-v1-8499","head_sha":"4e58997a0affd63d98048cee8e7d2cebc609bf0f"},
    {"pr":400,"title":"AION BUSINESS: visual demo and admin training V1","head_branch":"cursor/aion-business-demo-ui-v1-8499","base_branch":"cursor/aion-business-sandbox-harness-v1-8499","head_sha":"ac3b59631a3d1385c1a7b189a5157b6d21185bf1"},
    {"pr":401,"title":"AION BUSINESS: guided admin training V1","head_branch":"cursor/aion-business-guided-training-v1-8499","base_branch":"cursor/aion-business-demo-ui-v1-8499","head_sha":"85dad12d0c02844b452cc527eb3300e3fc724fa5"},
    {"pr":402,"title":"AION BUSINESS: diagnostic and proposal simulator V1","head_branch":"cursor/aion-business-diagnostic-proposal-simulator-v1-8499","base_branch":"cursor/aion-business-guided-training-v1-8499","head_sha":"db88fe73638aec5a288b5321eabd7a3a34ea6aae"},
    {"pr":403,"title":"AION BUSINESS: client portal demo V1","head_branch":"cursor/aion-business-client-portal-demo-v1-8499","base_branch":"cursor/aion-business-diagnostic-proposal-simulator-v1-8499","head_sha":"4086109ef0e5bd04d413a9293a5f2b0e55c32828"},
    {"pr":404,"title":"AION BUSINESS: onboarding and implementation demo V1","head_branch":"cursor/aion-business-onboarding-implementation-demo-v1-8499","base_branch":"cursor/aion-business-client-portal-demo-v1-8499","head_sha":"c7a0c82f67ee2c5283f5aca67a3f870146d1240e"},
    {"pr":405,"title":"AION BUSINESS: customer success and SLA demo V1","head_branch":"cursor/aion-business-customer-success-sla-demo-v1-8499","base_branch":"cursor/aion-business-onboarding-implementation-demo-v1-8499","head_sha":"6d852e013caff8e10ed7536824239512159ad933"},
    {"pr":406,"title":"AION BUSINESS: client finance and capacity demo V1","head_branch":"cursor/aion-business-client-finance-demo-v1-8499","base_branch":"cursor/aion-business-customer-success-sla-demo-v1-8499","head_sha":"d2ce8b9d25efd13ab845a20a13736ebcf8b08c29"},
    {"pr":407,"title":"AION BUSINESS: trend and opportunity intelligence V1","head_branch":"cursor/aion-business-trend-opportunity-intelligence-v1-8499","base_branch":"cursor/aion-business-client-finance-demo-v1-8499","head_sha":"52fa1c9f87b91e268265898bb1ddf20dc2a99b96"},
    {"pr":408,"title":"AION BUSINESS: commercial acquisition and client journey demo V1","head_branch":"cursor/aion-business-commercial-acquisition-demo-v1-8499","base_branch":"cursor/aion-business-trend-opportunity-intelligence-v1-8499","head_sha":"b5704300aede1f2e0233fe13799f0770bf92ae25"},
    {"pr":409,"title":"AION BUSINESS: integration hub readiness V1","head_branch":"cursor/aion-business-integration-hub-readiness-v1-8499","base_branch":"cursor/aion-business-commercial-acquisition-demo-v1-8499","head_sha":"a96ecc95adbbcb5d79262dc807b1a96ed03d7db3"},
    {"pr":410,"title":"AION BUSINESS: privacy LGPD and audit governance V1","head_branch":"cursor/aion-business-privacy-audit-governance-v1-8499","base_branch":"cursor/aion-business-integration-hub-readiness-v1-8499","head_sha":"2d05143bc7a708eda6c3c8cd77080f94fd7a3129"},
    {"pr":411,"title":"AION BUSINESS: master readiness panel V1","head_branch":"cursor/aion-business-master-readiness-panel-v1-8499","base_branch":"cursor/aion-business-privacy-audit-governance-v1-8499","head_sha":"9f4527865edb632a67a9671100f4d5ce5a55d9da"},
    {"pr":412,"title":"AION BUSINESS: bounded first-pilot governance V1","head_branch":"cursor/aion-business-pilot-governance-v1-8499","base_branch":"cursor/aion-business-master-readiness-panel-v1-8499","head_sha":"273b169ead65f96e6815c9a27d2499c80cdbd8ed"},
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


def frozen_green_evidence() -> list[dict[str, Any]]:
    """Snapshot externally checked on 2026-09-30; this module itself is offline."""
    rows = []
    for item in CANONICAL_STACK:
        checks = {name: "success" for name in REQUIRED_CHECKS}
        if int(item["pr"]) >= 400:
            checks.update({name: "success" for name in UI_CHECKS})
        rows.append({
            **dict(item),
            "state": "open",
            "draft": True,
            "mergeable": True,
            "checks": checks,
            "evidence_date": SNAPSHOT_DATE,
            "evidence_origin": "EXTERNAL_VERIFICATION_SNAPSHOT",
            "module_live_github_access": False,
        })
    return rows


def validate_stack(records: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    rows = [dict(row) for row in _seq(records, 60) if isinstance(row, Mapping)]
    by_pr = {int(row.get("pr")): row for row in rows if isinstance(row.get("pr"), int)}
    results = []
    previous_head_branch = ROOT_BASE_BRANCH

    for expected in CANONICAL_STACK:
        pr = int(expected["pr"])
        actual = _mapping(by_pr.get(pr))
        checks = _mapping(actual.get("checks"))
        missing = not bool(actual)
        base_ok = _clean(actual.get("base_branch"), 220) == expected["base_branch"]
        chain_ok = expected["base_branch"] == previous_head_branch
        head_branch_ok = _clean(actual.get("head_branch"), 220) == expected["head_branch"]
        head_sha_ok = _clean(actual.get("head_sha"), 80) == expected["head_sha"]
        state_ok = _clean(actual.get("state"), 40).lower() == "open"
        draft_ok = actual.get("draft") is True
        mergeable_ok = actual.get("mergeable") is True
        required_checks_ok = bool(
            checks and all(_clean(checks.get(name), 40).lower() == "success" for name in REQUIRED_CHECKS)
        )
        ui_checks_ok = (
            all(_clean(checks.get(name), 40).lower() == "success" for name in UI_CHECKS)
            if pr >= 400 else True
        )
        passed = bool(
            not missing and base_ok and chain_ok and head_branch_ok and head_sha_ok
            and state_ok and draft_ok and mergeable_ok and required_checks_ok and ui_checks_ok
        )
        results.append({
            "pr": pr,
            "title": expected["title"],
            "passed": passed,
            "missing": missing,
            "base_ok": base_ok,
            "chain_ok": chain_ok,
            "head_branch_ok": head_branch_ok,
            "head_sha_ok": head_sha_ok,
            "state_ok": state_ok,
            "draft_ok": draft_ok,
            "mergeable_ok": mergeable_ok,
            "required_checks_ok": required_checks_ok,
            "ui_checks_ok": ui_checks_ok,
        })
        previous_head_branch = expected["head_branch"]

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
    ready = row.get("state") == "READY_FOR_ADMIN_REVIEW" and row.get("complete") is True
    sequence = [
        {
            "order": index,
            "pr": item["pr"],
            "title": item["title"],
            "head_branch": item["head_branch"],
            "head_sha": item["head_sha"],
        }
        for index,item in enumerate(CANONICAL_STACK, start=1)
    ] if ready else []
    return {
        "schema": SCHEMA,
        "state": "ADMIN_DECISION_REQUIRED" if ready else "BLOCKED",
        "sequence": sequence,
        "strategy": "STACKED_ORDER_OLDEST_TO_NEWEST" if ready else "",
        "post_merge_validation_required": ready,
        "final_main_ci_required": ready,
        "final_main_sha_verification_required": ready,
        "runtime_posture_recheck_required": ready,
        "merge_authorized": False,
        "auto_merge_enabled": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def release_bundle_manifest(validation: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(validation)
    if row.get("state") != "READY_FOR_ADMIN_REVIEW" or row.get("complete") is not True:
        return {"schema": SCHEMA, "state": "BLOCKED", "bundle_digest": "", "executes_action": False}
    payload = {
        "snapshot_date": SNAPSHOT_DATE,
        "root_base_branch": ROOT_BASE_BRANCH,
        "stack": canonical_stack_manifest(),
        "required_checks": list(REQUIRED_CHECKS),
        "ui_checks": list(UI_CHECKS),
    }
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "BUNDLE_FROZEN_FOR_REVIEW",
        "bundle_digest": _digest(payload),
        "payload": payload,
        "merge_authorized": False,
        "deploy_authorized": False,
        "runtime_activation_authorized": False,
        "executes_action": False,
    }


def rollback_integration_plan(validation: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(validation)
    ready = row.get("state") == "READY_FOR_ADMIN_REVIEW" and row.get("complete") is True
    return {
        "schema": SCHEMA,
        "state": "ROLLBACK_PLAN_READY" if ready else "BLOCKED",
        "steps": [
            "Freeze expected SHAs before merge.",
            "Merge only in stacked order if explicitly authorized.",
            "Run full CI after every consolidation boundary.",
            "Stop on first regression or unexpected diff.",
            "Preserve pre-merge main SHA as rollback reference.",
            "Verify final main SHA and runtime posture after consolidation.",
        ] if ready else [],
        "automatic_rollback": False,
        "production_write": False,
        "executes_action": False,
    }


def administrative_options(validation: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    row = _mapping(validation)
    ready = row.get("state") == "READY_FOR_ADMIN_REVIEW" and row.get("complete") is True
    if not ready:
        return [{"id":"FIX_BLOCKERS","label":"Corrigir bloqueios antes de consolidar","available":True,"executes_action":False}]
    return [
        {"id":"KEEP_DRAFT_STACK","label":"Manter toda a stack em Draft","available":True,"executes_action":False},
        {"id":"FREEZE_BUNDLE","label":"Congelar bundle, ordem e SHAs","available":True,"executes_action":False},
        {"id":"REQUEST_MERGE_AUTHORIZATION","label":"Pedir autorização administrativa separada de merge","available":True,"executes_action":False},
    ]


__all__ = [
    "SCHEMA","VERSION","SNAPSHOT_DATE","ROOT_BASE_BRANCH","REQUIRED_CHECKS","UI_CHECKS",
    "CANONICAL_STACK","canonical_stack_manifest","frozen_green_evidence","validate_stack",
    "consolidation_preview","release_bundle_manifest","rollback_integration_plan","administrative_options",
]
