"""AION V2.18 red-team for Constitution / Policy Kernel."""
from __future__ import annotations

from copy import deepcopy

import pytest

from atlasquant_aion_policy_kernel import (
    approval_binding,
    assert_constitution_integrity,
    constitution_manifest,
    evaluate_policy_intent,
    propose_constitution_change,
)


TENANT = "tenant-a"
DOMAIN = "CORE"


def authority():
    return {
        "state": "VERIFIED",
        "authority_verified": True,
        "execution_allowed": False,
        "executes_action": False,
    }


def scope(**overrides):
    row = {
        "state": "SCOPE_VERIFIED",
        "capability_scope_verified": True,
        "tenant_id": TENANT,
        "domain": DOMAIN,
        "max_cost_usd": 10.0,
        "execution_allowed": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


def resilience(posture="NORMAL_MONITORED", kill=False):
    return {
        "posture": posture,
        "kill_switch_engaged": kill,
        "execution_allowed": False,
        "executes_action": False,
    }


def governance(state="WITHIN_GOVERNANCE"):
    return {
        "state": state,
        "execution_allowed": False,
        "executes_action": False,
    }


def durable(mode="EXTERNAL_EFFECT", state="PREPARED"):
    return {
        "mode": mode,
        "state": state,
        "executes_action": False,
    }


def approval(action, *, tenant=TENANT, domain=DOMAIN, approved=True, role="HUMAN_OWNER", digest=None):
    return approval_binding(
        action=action,
        tenant_id=tenant,
        domain=domain,
        approver_role=role,
        approved=approved,
        policy_digest=digest or constitution_manifest()["policy_digest"],
    )


def evaluate(action, **overrides):
    kwargs = {
        "action": action,
        "trusted_tenant_id": TENANT,
        "trusted_domain": DOMAIN,
        "authority_verification": authority(),
        "capability_scope": scope(),
        "operational_resilience": resilience(),
        "multiagent_governance": governance(),
        "durable_execution": None,
        "approval": None,
        "approval_evidence_verified": True,
        "requested_cost_usd": 1.0,
        "budget_remaining_usd": 20.0,
        "kill_switch_engaged": False,
        "privacy_review_verified": False,
        "real_trading_enabled": False,
    }
    kwargs.update(overrides)
    return evaluate_policy_intent(**kwargs)


def test_constitution_manifest_is_deterministic_and_integrity_bound():
    a = constitution_manifest()
    b = constitution_manifest()
    assert a == b
    assert a["policy_digest"].startswith("sha256:")
    assert assert_constitution_integrity(a) == a["policy_digest"]
    assert a["policy_source"] == "VERSIONED_CODE"
    assert a["invariants"]["execution_allowed_by_policy_kernel"] is False


@pytest.mark.parametrize("mutation", [
    ("invariants", "automatic_deploy", True),
    ("invariants", "memory_grants_permission", True),
    ("action_rules", "REAL_TRADING", {}),
])
def test_constitution_tamper_is_rejected(mutation):
    manifest = constitution_manifest()
    section, key, value = mutation
    manifest[section][key] = value
    with pytest.raises(ValueError):
        assert_constitution_integrity(manifest)


def test_unknown_action_is_blocked():
    result = evaluate("MAKE_ME_ROOT")
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["ACTION_NOT_IN_CONSTITUTION"]
    assert result["execution_allowed"] is False


def test_diagnostic_read_can_progress_in_degraded_read_only_without_execution():
    result = evaluate(
        "DIAGNOSTIC_READ",
        operational_resilience=resilience("DEGRADED_READ_ONLY"),
        requested_cost_usd=0,
    )
    assert result["state"] == "POLICY_PERMITS_PROGRESS"
    assert result["policy_allows_progress"] is True
    assert result["execution_allowed"] is False
    assert result["executes_action"] is False


def test_diagnostic_read_can_progress_while_kill_switch_is_engaged():
    result = evaluate(
        "DIAGNOSTIC_READ",
        operational_resilience=resilience("STOPPED_BY_KILL_SWITCH", kill=True),
        kill_switch_engaged=True,
        requested_cost_usd=0,
    )
    assert result["state"] == "POLICY_PERMITS_PROGRESS"
    assert result["execution_allowed"] is False


def test_draft_does_not_require_owner_approval_but_still_not_execution():
    result = evaluate("DRAFT", requested_cost_usd=0)
    assert result["state"] == "POLICY_PERMITS_PROGRESS"
    assert result["owner_approval_required"] is False
    assert result["execution_allowed"] is False


def test_internal_write_requires_local_safe_durable_record():
    blocked = evaluate("INTERNAL_WRITE", durable_execution=None)
    assert "DURABLE_EXECUTION_NOT_PREPARED" in blocked["blockers"]
    assert "DURABLE_EXECUTION_MODE_MISMATCH" in blocked["blockers"]

    ok = evaluate(
        "INTERNAL_WRITE",
        durable_execution=durable(mode="LOCAL_SAFE"),
    )
    assert ok["state"] == "POLICY_PERMITS_PROGRESS"
    assert ok["execution_allowed"] is False


def test_external_side_effect_requires_owner_approval_and_external_durable_mode():
    blocked = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
    )
    assert "OWNER_APPROVAL_REQUIRED" in blocked["blockers"]

    ok = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
    )
    assert ok["state"] == "POLICY_PERMITS_PROGRESS"
    assert ok["owner_approval_present"] is True
    assert ok["execution_allowed"] is False


def test_bound_owner_approval_without_verified_evidence_is_blocked():
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
        approval_evidence_verified=False,
    )
    assert result["owner_approval_binding_valid"] is True
    assert result["owner_approval_evidence_verified"] is False
    assert result["owner_approval_present"] is False
    assert "OWNER_APPROVAL_EVIDENCE_NOT_VERIFIED" in result["blockers"]
    assert result["policy_allows_progress"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("action", [
    "MERGE_MAIN",
    "DEPLOY_PRODUCTION",
    "PAYMENT",
    "WRITE_SECRET",
    "TENANT_DELETE",
    "CHANGE_POLICY",
])
def test_critical_actions_require_bound_owner_approval(action):
    durable_record = None if action == "CHANGE_POLICY" else durable()
    result = evaluate(action, durable_execution=durable_record)
    assert "OWNER_APPROVAL_REQUIRED" in result["blockers"]
    assert result["policy_allows_progress"] is False


@pytest.mark.parametrize("approval_override", [
    {"tenant": "tenant-b"},
    {"domain": "BUSINESS"},
    {"role": "ADMIN"},
    {"approved": False},
    {"digest": "sha256:" + "0" * 64},
])
def test_forged_or_misbound_approval_is_rejected(approval_override):
    evidence = approval("EXTERNAL_SIDE_EFFECT", **approval_override)
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=evidence,
    )
    assert "OWNER_APPROVAL_REQUIRED" in result["blockers"]
    assert result["owner_approval_present"] is False


def test_kill_switch_blocks_sensitive_action_even_with_owner_approval():
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
        kill_switch_engaged=True,
    )
    assert "GLOBAL_KILL_SWITCH_ENGAGED" in result["blockers"]
    assert result["policy_allows_progress"] is False


def test_resilience_kill_switch_signal_also_blocks_sensitive_action():
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
        operational_resilience=resilience("NORMAL_MONITORED", kill=True),
    )
    assert "GLOBAL_KILL_SWITCH_ENGAGED" in result["blockers"]


@pytest.mark.parametrize("posture", [
    "DEGRADED_MONITORED",
    "DEGRADED_READ_ONLY",
    "EMERGENCY_STOP_RECOMMENDED",
    "STOPPED_BY_KILL_SWITCH",
])
def test_sensitive_action_requires_normal_operational_posture(posture):
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
        operational_resilience=resilience(posture),
    )
    assert "OPERATIONAL_POSTURE_BLOCKED" in result["blockers"]


def test_authority_must_be_cryptographically_verified():
    result = evaluate(
        "DRAFT",
        authority_verification={"state": "BLOCKED", "authority_verified": False},
    )
    assert "AUTHORITY_NOT_VERIFIED" in result["blockers"]


def test_capability_scope_must_be_verified():
    result = evaluate(
        "DRAFT",
        capability_scope={"state": "BLOCKED", "capability_scope_verified": False},
    )
    assert "CAPABILITY_SCOPE_NOT_VERIFIED" in result["blockers"]


def test_capability_scope_cannot_cross_tenant():
    result = evaluate("DRAFT", capability_scope=scope(tenant_id="tenant-b"))
    assert "CAPABILITY_TENANT_MISMATCH" in result["blockers"]


def test_capability_scope_cannot_cross_domain():
    result = evaluate("DRAFT", capability_scope=scope(domain="BUSINESS"))
    assert "CAPABILITY_DOMAIN_MISMATCH" in result["blockers"]


def test_multiagent_governance_must_be_within_limits():
    result = evaluate("DRAFT", multiagent_governance=governance("BLOCK"))
    assert "MULTIAGENT_GOVERNANCE_BLOCKED" in result["blockers"]


def test_multiagent_governance_cannot_claim_execution_allowed():
    bad = governance()
    bad["execution_allowed"] = True
    result = evaluate("DRAFT", multiagent_governance=bad)
    assert "MULTIAGENT_GOVERNANCE_CONTRACT_INVALID" in result["blockers"]


@pytest.mark.parametrize("state,mode,blocker", [
    ("LEASED", "EXTERNAL_EFFECT", "DURABLE_EXECUTION_NOT_PREPARED"),
    ("PREPARED", "LOCAL_SAFE", "DURABLE_EXECUTION_MODE_MISMATCH"),
])
def test_external_durable_contract_is_strict(state, mode, blocker):
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(mode=mode, state=state),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
    )
    assert blocker in result["blockers"]


def test_durable_contract_cannot_claim_it_already_executes():
    row = durable()
    row["executes_action"] = True
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=row,
        approval=approval("EXTERNAL_SIDE_EFFECT"),
    )
    assert "DURABLE_EXECUTION_CONTRACT_INVALID" in result["blockers"]


def test_cost_cannot_exceed_signed_capability_ceiling():
    result = evaluate("DRAFT", requested_cost_usd=11, capability_scope=scope(max_cost_usd=10))
    assert "CAPABILITY_COST_CEILING_EXCEEDED" in result["blockers"]


def test_cost_cannot_exceed_remaining_budget():
    result = evaluate("DRAFT", requested_cost_usd=5, budget_remaining_usd=4)
    assert "BUDGET_REMAINING_EXCEEDED" in result["blockers"]


@pytest.mark.parametrize("field,value", [
    ("requested_cost_usd", -1),
    ("budget_remaining_usd", float("nan")),
    ("kill_switch_engaged", "false"),
    ("privacy_review_verified", 1),
    ("real_trading_enabled", None),
    ("approval_evidence_verified", "true"),
])
def test_security_inputs_are_strict(field, value):
    with pytest.raises(ValueError):
        evaluate("DRAFT", **{field: value})


@pytest.mark.parametrize("field,blocker", [
    ("authority_verification", "AUTHORITY_EVIDENCE_INVALID"),
    ("capability_scope", "CAPABILITY_SCOPE_EVIDENCE_INVALID"),
    ("operational_resilience", "OPERATIONAL_RESILIENCE_EVIDENCE_INVALID"),
    ("multiagent_governance", "MULTIAGENT_GOVERNANCE_EVIDENCE_INVALID"),
])
def test_malformed_upstream_evidence_fails_closed(field, blocker):
    result = evaluate("DRAFT", **{field: "forged"})
    assert result["state"] == "BLOCKED"
    assert blocker in result["blockers"]
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field,evidence,blocker", [
    (
        "authority_verification",
        {"state": "VERIFIED", "authority_verified": True, "execution_allowed": True, "executes_action": False},
        "AUTHORITY_CONTRACT_INVALID",
    ),
    (
        "capability_scope",
        {**scope(), "execution_allowed": True},
        "CAPABILITY_SCOPE_CONTRACT_INVALID",
    ),
    (
        "operational_resilience",
        {**resilience(), "executes_action": True},
        "OPERATIONAL_RESILIENCE_CONTRACT_INVALID",
    ),
])
def test_upstream_execution_claims_are_rejected(field, evidence, blocker):
    result = evaluate("DRAFT", **{field: evidence})
    assert blocker in result["blockers"]
    assert result["policy_allows_progress"] is False
    assert result["execution_allowed"] is False


def test_tenant_delete_requires_privacy_review_in_addition_to_approval():
    result = evaluate(
        "TENANT_DELETE",
        durable_execution=durable(),
        approval=approval("TENANT_DELETE"),
        privacy_review_verified=False,
    )
    assert "PRIVACY_REVIEW_REQUIRED" in result["blockers"]

    ok = evaluate(
        "TENANT_DELETE",
        durable_execution=durable(),
        approval=approval("TENANT_DELETE"),
        privacy_review_verified=True,
    )
    assert ok["state"] == "POLICY_PERMITS_PROGRESS"
    assert ok["execution_allowed"] is False
    assert ok["automatic_tenant_delete"] is False


def test_real_trading_requires_separate_flag_and_owner_approval():
    no_flag = evaluate(
        "REAL_TRADING",
        durable_execution=durable(),
        approval=approval("REAL_TRADING"),
        real_trading_enabled=False,
    )
    assert "REAL_TRADING_FLAG_NOT_ENABLED" in no_flag["blockers"]

    with_flag = evaluate(
        "REAL_TRADING",
        durable_execution=durable(),
        approval=approval("REAL_TRADING"),
        real_trading_enabled=True,
    )
    assert with_flag["state"] == "POLICY_PERMITS_PROGRESS"
    assert with_flag["automatic_real_trading"] is False
    assert with_flag["execution_allowed"] is False


def test_policy_change_never_mutates_active_constitution():
    active = constitution_manifest()
    proposed = deepcopy(active)
    proposed["invariants"]["automatic_deploy"] = True
    result = propose_constitution_change(proposed)
    assert result["state"] == "OWNER_REVIEW_REQUIRED"
    assert result["policy_mutated"] is False
    assert result["automatic_policy_change"] is False
    assert constitution_manifest() == active


def test_same_manifest_is_no_change_not_runtime_mutation():
    result = propose_constitution_change(constitution_manifest())
    assert result["state"] == "NO_CHANGE"
    assert result["policy_mutated"] is False


def test_policy_progress_never_equals_execution():
    result = evaluate(
        "EXTERNAL_SIDE_EFFECT",
        durable_execution=durable(),
        approval=approval("EXTERNAL_SIDE_EFFECT"),
    )
    assert result["policy_allows_progress"] is True
    assert result["policy_is_execution_authority"] is False
    assert result["approval_implies_execution"] is False
    assert result["memory_grants_authority"] is False
    assert result["health_implies_approval"] is False
    assert result["execution_allowed"] is False
    assert result["tool_called"] is False
    assert result["provider_called"] is False
    assert result["executes_action"] is False
