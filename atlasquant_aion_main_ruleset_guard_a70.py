"""A70: pure, offline validation of a *proposed* GitHub main ruleset.

This does not call GitHub, apply settings, create approvals, attest an
independent witness, or authorize any merge/deployment. The connection in use
has no administration permissions. Statuses need to be emitted on actual PRs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROPOSAL = Path(__file__).resolve().parent / "docs/aion/main_governance_ruleset_proposal_a70.json"
MAIN_REF = "refs/heads/main"
CHECK_SOURCE_APP_ID = 15368
REQUIRED_CHECKS = frozenset(("test", "AION adversarial contracts", "Supply-chain audit"))


def read_proposal() -> dict[str, Any]:
    return json.loads(PROPOSAL.read_text(encoding="utf-8"))


def evaluate_ruleset(policy: Any) -> list[str]:
    """All missing safeguards are reported; fail closed on unknown shapes."""
    fail: list[str] = []
    if not isinstance(policy, dict):
        return ["A70_RULESET_INVALID"]
    if policy.get("name") != "ATLASQUANT_MAIN_P0_GUARD":
        fail.append("A70_NAME_MISMATCH")
    if policy.get("target") != "branch" or policy.get("enforcement") != "active":
        fail.append("A70_NOT_ACTIVE_BRANCH_GUARD")
    if policy.get("bypass_actors") != []:
        fail.append("A70_BYPASS_NOT_EMPTY")
    conditions = policy.get("conditions") or {}
    refs = conditions.get("ref_name") if isinstance(conditions, dict) else None
    if not isinstance(refs, dict) or refs.get("include") != [MAIN_REF] or refs.get("exclude") != []:
        fail.append("A70_MAIN_ONLY_SCOPE_REQUIRED")
    rules = policy.get("rules") or []
    if not isinstance(rules, list) or any(not isinstance(x, dict) for x in rules):
        return fail + ["A70_RULES_INVALID"]
    by_type = {rule.get("type"): rule for rule in rules}
    if len(by_type) != len(rules):
        fail.append("A70_DUPLICATE_RULES")
    pr = by_type.get("pull_request")
    p = pr.get("parameters") if isinstance(pr, dict) else None
    if not isinstance(p, dict) or any((
        p.get("required_approving_review_count") != 0,
        p.get("required_review_thread_resolution") is not True,
        p.get("dismiss_stale_reviews_on_push") is not True,
        p.get("require_code_owner_review") is not False,
        p.get("require_last_push_approval") is not False,
        not isinstance(p.get("allowed_merge_methods"), list) or not p.get("allowed_merge_methods"),
    )):
        fail.append("A70_PR_REQUIRED_OR_REVIEW_POLICY_CHANGED")
    checks = by_type.get("required_status_checks")
    cp = checks.get("parameters") if isinstance(checks, dict) else None
    actual_contexts: Any = cp.get("required_status_checks") if isinstance(cp, dict) else None
    if not isinstance(cp, dict) or cp.get("strict_required_status_checks_policy") is not True:
        fail.append("A70_STRICT_REQUIRED_CHECKS_MISSING")
    if not isinstance(actual_contexts, list):
        fail.append("A70_REQUIRED_CHECKS_INVALID")
    else:
        valid = [
            item for item in actual_contexts
            if isinstance(item, dict)
            and isinstance(item.get("context"), str)
            and item.get("integration_id") == CHECK_SOURCE_APP_ID
        ]
        names = [item["context"] for item in valid]
        if (len(valid) != len(actual_contexts) or
                set(names) != REQUIRED_CHECKS or
                len(names) != len(REQUIRED_CHECKS)):
            fail.append("A70_REQUIRED_CHECK_SET_OR_SOURCE_MISMATCH")
    if "non_fast_forward" not in by_type:
        fail.append("A70_FORCE_PUSH_NOT_BLOCKED")
    if "deletion" not in by_type:
        fail.append("A70_DELETION_NOT_BLOCKED")
    return fail


def audit_observed(branch: Any, rulesets: Any) -> dict[str, Any]:
    """Verify known policy. GH summary-only rulesets are NOT enough for GO."""
    errors: list[str] = []
    if not isinstance(branch, dict) or branch.get("protected") is not True:
        errors.append("A70_MAIN_UNPROTECTED")
    if not isinstance(rulesets, list) or not rulesets:
        errors.append("A70_NO_ACTIVE_RULESET")
    elif not any(isinstance(item, dict) and not evaluate_ruleset(item) for item in rulesets):
        errors.append("A70_NO_VERIFIED_RULESET_DETAILS")
    return {
        "schema": "AION_MAIN_RULESET_READINESS_A70",
        "status": "PROTECTION_POLICY_VERIFIED" if not errors else "HARD_NO_GO",
        "missing": errors,
        "applies_any_change": False,
        "approves_merge": False,
        "independent_f1_t1_witness": False,
    }


__all__ = ["read_proposal", "evaluate_ruleset", "audit_observed"]
