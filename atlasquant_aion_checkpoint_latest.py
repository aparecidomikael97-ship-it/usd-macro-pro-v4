"""Read-only latest Checkpoint Mestre pointer validator.

This module only reads repository files. It does not write runtime state, call
network providers, merge, deploy, activate runtime or execute external actions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

LATEST_POINTER_PATH = "docs/continuidade/checkpoint_mestre_latest.json"
EXPECTED_POINTER_SCHEMA = "ATLASQUANT_AION_CHECKPOINT_MASTER_LATEST_POINTER_V1"
EXPECTED_MANIFEST_SCHEMA = "ATLASQUANT_AION_CHECKPOINT_MASTER_INCREMENTAL_V1"
EXPECTED_DATE = "2026-09-30"
EXPECTED_ROLE_IDS = (
    "orchestrator",
    "architect",
    "guardian",
    "executor",
    "memory",
    "finops",
    "reliability",
    "customer_success",
)
OFFICIAL_STATES = {
    "APROVADO / PENDENTE",
    "IMPLEMENTADO / EM VALIDAÇÃO",
    "VALIDADO",
    "DEPENDÊNCIA EXTERNA",
    "SUBSTITUÍDO",
    "DESCARTADO",
    "UNVERIFIED",
    "NEEDS HUMAN RECONCILIATION",
}


def _root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkpoint JSON must be an object")
    return value


def validate_latest_checkpoint(root: Path | None = None) -> dict[str, Any]:
    base = _root(root)
    errors: list[str] = []

    pointer_path = base / LATEST_POINTER_PATH
    if not pointer_path.is_file():
        return {"ok": False, "errors": ["latest pointer missing"]}

    pointer = _load(pointer_path)
    if pointer.get("schema") != EXPECTED_POINTER_SCHEMA:
        errors.append("pointer schema invalid")
    if pointer.get("latest_date") != EXPECTED_DATE:
        errors.append("latest date invalid")
    for key in (
        "preserves_history",
        "runtime_auto_apply",
        "merge_authorized",
        "deploy_authorized",
        "runtime_authorized",
    ):
        expected = key == "preserves_history"
        if pointer.get(key) is not expected:
            errors.append(f"{key} invalid")

    manifest_rel = str(pointer.get("latest_manifest") or "")
    narrative_rel = str(pointer.get("latest_narrative") or "")
    parent_manifest_rel = str(pointer.get("parent_manifest") or "")
    parent_narrative_rel = str(pointer.get("parent_narrative") or "")
    for label, rel in (
        ("latest manifest", manifest_rel),
        ("latest narrative", narrative_rel),
        ("parent manifest", parent_manifest_rel),
        ("parent narrative", parent_narrative_rel),
    ):
        if not rel or not (base / rel).is_file():
            errors.append(f"{label} missing")

    if errors:
        return {"ok": False, "errors": errors}

    manifest = _load(base / manifest_rel)
    narrative = (base / narrative_rel).read_text(encoding="utf-8")
    if manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA:
        errors.append("manifest schema invalid")
    if manifest.get("date") != EXPECTED_DATE:
        errors.append("manifest date invalid")
    if manifest.get("gate_id") not in narrative:
        errors.append("gate absent from narrative")

    parent = manifest.get("parent")
    if not isinstance(parent, Mapping):
        errors.append("parent binding missing")
    else:
        if parent.get("manifest") != parent_manifest_rel:
            errors.append("parent manifest binding mismatch")
        if parent.get("narrative") != parent_narrative_rel:
            errors.append("parent narrative binding mismatch")

    economics = manifest.get("economics")
    if not isinstance(economics, Mapping):
        errors.append("economics missing")
    elif economics.get("initial_monthly_budget_cap_brl") != 200:
        errors.append("initial budget cap must be 200 BRL")

    monetization = manifest.get("monetization")
    if not isinstance(monetization, Mapping):
        errors.append("monetization missing")
    else:
        if monetization.get("dropshipping_priority") is not False:
            errors.append("dropshipping must remain out of priority")
        if not str(monetization.get("priority_offer") or "").strip():
            errors.append("priority offer missing")

    external = manifest.get("external_ai_relationship")
    if not isinstance(external, Mapping):
        errors.append("external AI relationship missing")
    elif external.get("aion_must_run_without_chatgpt_subscription") is not True:
        errors.append("AION independence from ChatGPT missing")

    multiagent = manifest.get("multiagent")
    roles = multiagent.get("roles") if isinstance(multiagent, Mapping) else None
    role_ids = tuple(
        str(item.get("id") or "")
        for item in roles
        if isinstance(item, Mapping)
    ) if isinstance(roles, list) else ()
    if role_ids != EXPECTED_ROLE_IDS:
        errors.append("eight logical roles missing or out of order")
    if isinstance(multiagent, Mapping):
        if multiagent.get("independent_expensive_models_required") is not False:
            errors.append("multiagent cost model invalid")
        if multiagent.get("share_models_and_infrastructure") is not True:
            errors.append("shared infrastructure rule missing")

    decisions = manifest.get("decisions")
    seen: set[str] = set()
    if not isinstance(decisions, list) or not decisions:
        errors.append("decisions missing")
    else:
        for item in decisions:
            if not isinstance(item, Mapping):
                errors.append("decision entry invalid")
                continue
            decision_id = str(item.get("id") or "")
            state = str(item.get("state") or "")
            if not decision_id or decision_id in seen:
                errors.append("duplicate or empty decision id")
            seen.add(decision_id)
            if state not in OFFICIAL_STATES:
                errors.append(f"{decision_id}: invalid state")

    stack = manifest.get("business_stack")
    if not isinstance(stack, Mapping):
        errors.append("business stack missing")
    else:
        for key in (
            "current_runtime_authorized",
            "merge_authorized_by_this_checkpoint",
            "deploy_authorized_by_this_checkpoint",
            "billing_authorized_by_this_checkpoint",
            "quota_application_authorized_by_this_checkpoint",
        ):
            if stack.get(key) is not False:
                errors.append(f"{key} must remain false")

    return {
        "ok": not errors,
        "errors": errors,
        "latest_date": pointer.get("latest_date"),
        "manifest": manifest_rel,
        "decision_count": len(decisions or []),
        "role_count": len(role_ids),
        "budget_cap_brl": (
            economics.get("initial_monthly_budget_cap_brl")
            if isinstance(economics, Mapping)
            else None
        ),
    }


__all__ = ["validate_latest_checkpoint", "LATEST_POINTER_PATH"]
