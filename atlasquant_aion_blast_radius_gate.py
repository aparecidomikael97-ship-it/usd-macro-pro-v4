"""AION blast-radius + independent review quorum gate.

Read-only policy gate that constrains blast radius and binds advisory quorum to
one exact candidate digest. Reviewer quorum never replaces HUMAN_OWNER
authority, and this module never executes an action.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

SCHEMA = "ATLASQUANT_AION_BLAST_RADIUS_QUORUM_V1"
BUDGET_SCHEMA = "ATLASQUANT_AION_CUMULATIVE_AUTHORITY_BUDGET_V1"
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
REVIEWER_KINDS = ("GUARDIAN", "SHADOW", "SENTINEL", "HUMAN_REVIEWER")
SENSITIVE_ACTIONS = frozenset({
    "MERGE_MAIN", "DEPLOY_PRODUCTION", "WRITE_SECRET", "CHARGE_CUSTOMER",
    "REAL_TRADING", "DELETE_DATA", "CHANGE_POLICY", "ENABLE_WORKER",
    "RESTORE_PRODUCTION", "EXTERNAL_BROADCAST",
})
CANDIDATE_FIELDS = frozenset({
    "owner_id", "tenant_id", "workspace_id", "action_id", "transaction_id",
    "action", "proposer_id", "risk_level", "affected_tenant_ids",
    "affected_workspace_ids", "affected_records", "external_targets",
    "financial_value_minor", "external_side_effect", "reversible",
    "rollback_ref", "authority_budget_ref", "authority_budget_policy_digest",
})
_RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id") or item.get("actor_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
    }


def _strict_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer() and value >= 0:
        return int(value)
    return None


def _positive_int(value: Any) -> int | None:
    out = _nonnegative_int(value)
    return out if out is not None and out > 0 else None


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def candidate_digest(candidate: Mapping[str, Any] | None) -> str:
    body = dict(candidate) if isinstance(candidate, Mapping) else {}
    return _digest({"schema": SCHEMA, "candidate": body})


def normalize_blast_radius_policy(
    raw: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    trusted = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")
    if item.get("state") != "VERIFIED":
        blockers.append("POLICY_NOT_VERIFIED")
    if any(_text(item.get(k), 120) != trusted[k] for k in trusted):
        blockers.append("POLICY_SCOPE_MISMATCH")

    policy_id = _text(item.get("policy_id"), 120)
    revision = _positive_int(item.get("revision"))
    if not policy_id:
        blockers.append("POLICY_ID_REQUIRED")
    if revision is None:
        blockers.append("POLICY_REVISION_INVALID")

    limits = {}
    for key in ("max_affected_records", "max_external_targets", "max_financial_value_minor"):
        value = _nonnegative_int(item.get(key))
        if value is None:
            blockers.append(key.upper() + "_INVALID")
        limits[key] = value

    max_tenants = _positive_int(item.get("max_tenants"))
    max_workspaces = _positive_int(item.get("max_workspaces"))
    if max_tenants is None:
        blockers.append("MAX_TENANTS_INVALID")
    if max_workspaces is None:
        blockers.append("MAX_WORKSPACES_INVALID")

    quorum_raw = item.get("quorum_by_risk")
    quorum: dict[str, int] = {}
    if not isinstance(quorum_raw, Mapping):
        blockers.append("QUORUM_POLICY_INVALID")
    else:
        for risk in RISK_LEVELS:
            count = _nonnegative_int(quorum_raw.get(risk))
            if count is None:
                blockers.append("QUORUM_POLICY_INVALID:" + risk)
            else:
                quorum[risk] = count

    owner_raw = item.get("human_owner_required_for")
    owner_required: list[str] = []
    if not isinstance(owner_raw, (list, tuple)):
        blockers.append("HUMAN_OWNER_POLICY_INVALID")
    else:
        for raw_risk in owner_raw:
            risk = _text(raw_risk, 40).upper()
            if risk not in RISK_LEVELS or risk in owner_required:
                blockers.append("HUMAN_OWNER_POLICY_INVALID")
                continue
            owner_required.append(risk)

    if "CRITICAL" not in owner_required:
        blockers.append("CRITICAL_MUST_REQUIRE_HUMAN_OWNER")

    return {
        "schema": SCHEMA,
        "state": "VERIFIED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "policy_id": policy_id,
        "revision": revision,
        **trusted,
        **limits,
        "max_tenants": max_tenants,
        "max_workspaces": max_workspaces,
        "quorum_by_risk": quorum,
        "human_owner_required_for": owner_required,
        "quorum_is_advisory_only": True,
        "quorum_never_replaces_human_owner": True,
        "executes_action": False,
    }


def _candidate(
    raw: Mapping[str, Any] | None,
    trusted: Mapping[str, str],
) -> tuple[dict[str, Any], list[str]]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    blockers: list[str] = []
    unknown = sorted(str(key) for key in item if key not in CANDIDATE_FIELDS)
    if unknown:
        blockers.append("CANDIDATE_UNKNOWN_FIELDS")
    for key in trusted:
        if _text(item.get(key), 120) != trusted[key]:
            blockers.append("CANDIDATE_SCOPE_MISMATCH")

    action_id = _text(item.get("action_id"), 160)
    transaction_id = _text(item.get("transaction_id"), 160)
    action = _text(item.get("action"), 100).upper()
    proposer_id = _text(item.get("proposer_id"), 160)
    risk = _text(item.get("risk_level"), 40).upper()
    if not action_id:
        blockers.append("ACTION_ID_REQUIRED")
    if not transaction_id:
        blockers.append("TRANSACTION_ID_REQUIRED")
    if not action:
        blockers.append("ACTION_REQUIRED")
    if not proposer_id:
        blockers.append("PROPOSER_ID_REQUIRED")
    if risk not in RISK_LEVELS:
        blockers.append("RISK_LEVEL_INVALID")

    tenants = item.get("affected_tenant_ids")
    workspaces = item.get("affected_workspace_ids")
    if not isinstance(tenants, (list, tuple)) or not tenants:
        blockers.append("AFFECTED_TENANTS_INVALID")
        tenant_ids: list[str] = []
    else:
        tenant_ids = []
        for value in tenants:
            token = _text(value, 120)
            if not token or token in tenant_ids:
                blockers.append("AFFECTED_TENANTS_INVALID")
            elif token:
                tenant_ids.append(token)

    if not isinstance(workspaces, (list, tuple)) or not workspaces:
        blockers.append("AFFECTED_WORKSPACES_INVALID")
        workspace_ids: list[str] = []
    else:
        workspace_ids = []
        for value in workspaces:
            token = _text(value, 120)
            if not token or token in workspace_ids:
                blockers.append("AFFECTED_WORKSPACES_INVALID")
            elif token:
                workspace_ids.append(token)

    affected_records = _nonnegative_int(item.get("affected_records"))
    external_targets = _nonnegative_int(item.get("external_targets"))
    financial = _nonnegative_int(item.get("financial_value_minor"))
    if affected_records is None:
        blockers.append("AFFECTED_RECORDS_INVALID")
    if external_targets is None:
        blockers.append("EXTERNAL_TARGETS_INVALID")
    if financial is None:
        blockers.append("FINANCIAL_VALUE_INVALID")

    external_side_effect = _strict_bool(item.get("external_side_effect"))
    reversible = _strict_bool(item.get("reversible"))
    if external_side_effect is None:
        blockers.append("EXTERNAL_SIDE_EFFECT_BOOL_REQUIRED")
    if reversible is None:
        blockers.append("REVERSIBLE_BOOL_REQUIRED")
    rollback_ref = _text(item.get("rollback_ref"), 240)
    if reversible is True and not rollback_ref:
        blockers.append("ROLLBACK_REF_REQUIRED")

    budget_ref = _text(item.get("authority_budget_ref"), 160)
    budget_digest = _text(item.get("authority_budget_policy_digest"), 160)
    if not budget_ref:
        blockers.append("AUTHORITY_BUDGET_REF_REQUIRED")
    if not budget_digest:
        blockers.append("AUTHORITY_BUDGET_POLICY_DIGEST_REQUIRED")

    normalized = {
        "owner_id": trusted["owner_id"],
        "tenant_id": trusted["tenant_id"],
        "workspace_id": trusted["workspace_id"],
        "action_id": action_id,
        "transaction_id": transaction_id,
        "action": action,
        "proposer_id": proposer_id,
        "risk_level": risk,
        "affected_tenant_ids": tenant_ids,
        "affected_workspace_ids": workspace_ids,
        "affected_records": affected_records,
        "external_targets": external_targets,
        "financial_value_minor": financial,
        "external_side_effect": external_side_effect,
        "reversible": reversible,
        "rollback_ref": rollback_ref,
        "authority_budget_ref": budget_ref,
        "authority_budget_policy_digest": budget_digest,
    }
    return normalized, list(dict.fromkeys(blockers))


def evaluate_blast_radius(
    *,
    trusted_scope: Mapping[str, Any] | None,
    policy: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    authority_budget_guard: Mapping[str, Any] | None,
    reviews: Sequence[Mapping[str, Any]] | None,
    human_owner_approval: Mapping[str, Any] | None = None,
    trusted_reviewer_assignments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    normalized_policy = normalize_blast_radius_policy(policy, trusted_scope=trusted)
    blockers.extend(normalized_policy["blockers"])

    cand, candidate_blockers = _candidate(candidate, trusted)
    blockers.extend(candidate_blockers)
    digest = candidate_digest(cand)

    if normalized_policy["state"] == "VERIFIED":
        if len(cand["affected_tenant_ids"]) > int(normalized_policy["max_tenants"]):
            blockers.append("TENANT_BLAST_RADIUS_LIMIT")
        if len(cand["affected_workspace_ids"]) > int(normalized_policy["max_workspaces"]):
            blockers.append("WORKSPACE_BLAST_RADIUS_LIMIT")
        if cand["affected_tenant_ids"] != [trusted["tenant_id"]]:
            blockers.append("CROSS_TENANT_BLAST_RADIUS_FORBIDDEN")
        if cand["affected_workspace_ids"] != [trusted["workspace_id"]]:
            blockers.append("CROSS_WORKSPACE_BLAST_RADIUS_FORBIDDEN")
        if cand["affected_records"] is not None and cand["affected_records"] > int(normalized_policy["max_affected_records"]):
            blockers.append("RECORD_BLAST_RADIUS_LIMIT")
        if cand["external_targets"] is not None and cand["external_targets"] > int(normalized_policy["max_external_targets"]):
            blockers.append("EXTERNAL_TARGET_BLAST_RADIUS_LIMIT")
        if cand["financial_value_minor"] is not None and cand["financial_value_minor"] > int(normalized_policy["max_financial_value_minor"]):
            blockers.append("FINANCIAL_BLAST_RADIUS_LIMIT")

    # Candidate-declared risk cannot lower a deterministic minimum implied by impact.
    declared_risk = cand.get("risk_level") if cand.get("risk_level") in RISK_LEVELS else "CRITICAL"
    minimum_risk = "LOW"
    if cand.get("external_side_effect") is True or (cand.get("external_targets") or 0) > 0:
        minimum_risk = "MEDIUM"
    if (cand.get("financial_value_minor") or 0) > 0:
        minimum_risk = "HIGH"
    if cand.get("action") in SENSITIVE_ACTIONS:
        minimum_risk = "CRITICAL"
    if _RISK_RANK.get(declared_risk, 3) < _RISK_RANK[minimum_risk]:
        blockers.append("RISK_LEVEL_UNDERSTATED")

    budget = dict(authority_budget_guard) if isinstance(authority_budget_guard, Mapping) else {}
    budget_required = (
        cand.get("external_side_effect") is True
        or (cand.get("external_targets") or 0) > 0
        or (cand.get("financial_value_minor") or 0) > 0
        or cand.get("action") in SENSITIVE_ACTIONS
        or declared_risk in {"MEDIUM", "HIGH", "CRITICAL"}
    )
    if budget_required:
        if budget.get("schema") != BUDGET_SCHEMA:
            blockers.append("AUTHORITY_BUDGET_SCHEMA_INVALID")
        if budget.get("allowed") is not True:
            blockers.append("AUTHORITY_BUDGET_BLOCKED")
        if _text(budget.get("transaction_id"), 160) != cand.get("transaction_id"):
            blockers.append("AUTHORITY_BUDGET_TRANSACTION_MISMATCH")
        if _text(budget.get("authority_budget_ref"), 160) != cand.get("authority_budget_ref"):
            blockers.append("AUTHORITY_BUDGET_REF_MISMATCH")
        if _text(budget.get("policy_digest"), 160) != cand.get("authority_budget_policy_digest"):
            blockers.append("AUTHORITY_BUDGET_POLICY_MISMATCH")
        budget_scope = budget.get("scope") if isinstance(budget.get("scope"), Mapping) else {}
        if any(_text(budget_scope.get(key), 120) != trusted[key] for key in trusted):
            blockers.append("AUTHORITY_BUDGET_SCOPE_MISMATCH")
        if budget.get("grants_authority") is not False:
            blockers.append("AUTHORITY_BUDGET_MUST_NOT_GRANT_AUTHORITY")
        if budget.get("executes_action") is not False:
            blockers.append("AUTHORITY_BUDGET_MUST_NOT_EXECUTE")
        if budget.get("execution_allowed_by_this_component") is not False:
            blockers.append("AUTHORITY_BUDGET_MUST_NOT_AUTHORIZE_EXECUTION")

    required_quorum = 0
    if normalized_policy["state"] == "VERIFIED" and cand.get("risk_level") in RISK_LEVELS:
        required_quorum = int(normalized_policy["quorum_by_risk"][cand["risk_level"]])

    assignments = (
        dict(trusted_reviewer_assignments)
        if isinstance(trusted_reviewer_assignments, Mapping)
        else {}
    )
    if required_quorum > 0 and not assignments:
        blockers.append("TRUSTED_REVIEWER_ASSIGNMENTS_REQUIRED")

    valid_reviewers: list[str] = []
    review_rows: list[dict[str, Any]] = []
    source = reviews if isinstance(reviews, (list, tuple)) else []
    if reviews is not None and not isinstance(reviews, (list, tuple)):
        blockers.append("REVIEWS_COLLECTION_INVALID")

    for raw in source[:64]:
        row = dict(raw) if isinstance(raw, Mapping) else {}
        row_blockers: list[str] = []
        reviewer_id = _text(row.get("reviewer_id"), 160)
        reviewer_kind = _text(row.get("reviewer_kind"), 60).upper()
        if not reviewer_id:
            row_blockers.append("REVIEWER_ID_REQUIRED")
        if reviewer_kind not in REVIEWER_KINDS:
            row_blockers.append("REVIEWER_KIND_INVALID")
        trusted_kind = _text(assignments.get(reviewer_id), 60).upper()
        if not trusted_kind:
            row_blockers.append("REVIEWER_NOT_IN_TRUSTED_ASSIGNMENTS")
        elif trusted_kind != reviewer_kind:
            row_blockers.append("REVIEWER_TRUSTED_KIND_MISMATCH")
        if reviewer_id == cand.get("proposer_id"):
            row_blockers.append("SELF_REVIEW_FORBIDDEN")
        if row.get("decision") != "SUPPORT":
            row_blockers.append("REVIEW_NOT_SUPPORT")
        if row.get("independent") is not True:
            row_blockers.append("REVIEW_INDEPENDENCE_NOT_PROVED")
        if _text(row.get("candidate_digest"), 80) != digest:
            row_blockers.append("REVIEW_CANDIDATE_BINDING_MISMATCH")
        for key in trusted:
            if _text(row.get(key), 120) != trusted[key]:
                row_blockers.append("REVIEW_SCOPE_MISMATCH")
        if not row_blockers and reviewer_id not in valid_reviewers:
            valid_reviewers.append(reviewer_id)
        elif not row_blockers and reviewer_id in valid_reviewers:
            row_blockers.append("DUPLICATE_REVIEWER")
        review_rows.append({
            "reviewer_id": reviewer_id,
            "reviewer_kind": reviewer_kind,
            "valid": not row_blockers,
            "blockers": list(dict.fromkeys(row_blockers)),
        })

    if len(valid_reviewers) < required_quorum:
        blockers.append("INDEPENDENT_REVIEW_QUORUM_INSUFFICIENT")

    owner_required = (
        cand.get("risk_level") in set(normalized_policy.get("human_owner_required_for") or [])
        or cand.get("action") in SENSITIVE_ACTIONS
    )
    owner = dict(human_owner_approval) if isinstance(human_owner_approval, Mapping) else {}
    owner_valid = False
    if owner_required:
        owner_blockers: list[str] = []
        if owner.get("approved") is not True:
            owner_blockers.append("HUMAN_OWNER_APPROVAL_REQUIRED")
        if owner.get("authority_class") != "HUMAN_OWNER":
            owner_blockers.append("HUMAN_OWNER_AUTHORITY_CLASS_REQUIRED")
        if _text(owner.get("owner_id"), 120) != trusted["owner_id"]:
            owner_blockers.append("HUMAN_OWNER_ID_MISMATCH")
        if _text(owner.get("action_id"), 160) != cand.get("action_id"):
            owner_blockers.append("HUMAN_OWNER_ACTION_BINDING_MISMATCH")
        if _text(owner.get("candidate_digest"), 80) != digest:
            owner_blockers.append("HUMAN_OWNER_CANDIDATE_BINDING_MISMATCH")
        for key in ("tenant_id", "workspace_id"):
            if _text(owner.get(key), 120) != trusted[key]:
                owner_blockers.append("HUMAN_OWNER_SCOPE_MISMATCH")
        blockers.extend(owner_blockers)
        owner_valid = not owner_blockers

    if cand.get("risk_level") in {"HIGH", "CRITICAL"} and cand.get("reversible") is not True:
        blockers.append("HIGH_RISK_MUST_BE_REVERSIBLE")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_DOWNSTREAM_EXECUTION_GATE" if ready else "BLOCKED",
        "blockers": blockers,
        "scope": trusted,
        "policy": normalized_policy,
        "candidate": cand,
        "candidate_digest": digest,
        "required_quorum": required_quorum,
        "valid_reviewer_count": len(valid_reviewers),
        "valid_reviewer_ids": valid_reviewers,
        "trusted_reviewer_assignment_count": len(assignments),
        "reviews": review_rows,
        "human_owner_required": owner_required,
        "human_owner_approval_valid": owner_valid,
        "quorum_is_advisory_only": True,
        "quorum_never_replaces_human_owner": True,
        "requires_specialized_execution_gate": cand.get("action") in SENSITIVE_ACTIONS,
        "execution_authorized": False,
        "external_action_executed": False,
        "automatic_execution": False,
        "automatic_scope_expansion": False,
        "executes_action": False,
    }


def blast_radius_policy_contract() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "same_tenant_only": True,
        "same_workspace_only": True,
        "cumulative_authority_budget_required_for_side_effects": True,
        "independent_review_quorum_supported": True,
        "quorum_is_advisory_only": True,
        "quorum_never_replaces_human_owner": True,
        "human_owner_required_for_critical": True,
        "sensitive_actions_require_specialized_execution_gate": True,
        "automatic_execution": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA", "BUDGET_SCHEMA", "RISK_LEVELS", "REVIEWER_KINDS", "SENSITIVE_ACTIONS",
    "candidate_digest", "normalize_blast_radius_policy", "evaluate_blast_radius",
    "blast_radius_policy_contract",
]
