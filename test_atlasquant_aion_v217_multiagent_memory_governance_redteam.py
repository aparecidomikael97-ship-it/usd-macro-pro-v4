"""AION V2.17 red-team for multi-agent and memory governance."""
from __future__ import annotations

import pytest

from atlasquant_aion_memory_contract import create_memory_record
from atlasquant_aion_multiagent_memory_governor import (
    build_expiry_tombstone,
    govern_memory_use,
    govern_multiagent_session,
)


NOW = "2026-10-04T19:00:00Z"
SESSION_DEADLINE = "2026-10-04T20:00:00Z"


def node(
    node_id,
    parent_id="",
    *,
    delegated_by=None,
    capability="core.plan",
    deadline_at="2026-10-04T19:30:00Z",
    cost=0.10,
    **extra,
):
    row = {
        "node_id": node_id,
        "parent_id": parent_id,
        "delegated_by": parent_id if delegated_by is None else delegated_by,
        "requested_capability": capability,
        "deadline_at": deadline_at,
        "estimated_cost_usd": cost,
        "guardian_risk": "READ",
        "impact": "LOW",
        "uncertainty_pct": 0,
        "reversible": False,
        "external_side_effects": False,
    }
    row.update(extra)
    return row


def plan(*nodes, **overrides):
    kwargs = {
        "trusted_context": {
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
        },
        "supervisor_id": "aion-core",
        "allowed_capabilities": ["core.plan", "core.read"],
        "now_ts": NOW,
        "session_deadline_at": SESSION_DEADLINE,
        "cost_limit_usd": 5.0,
        "cost_used_usd": 1.0,
        "max_depth": 3,
        "max_fanout": 4,
        "max_nodes": 16,
        "call_limit": 100,
        "calls_used": 2,
        "token_limit": 100000,
        "tokens_used": 1000,
        "wall_seconds_limit": 300,
        "wall_seconds_used": 10,
        "memory_mb_limit": 1024,
        "memory_mb_used": 100,
    }
    kwargs.update(overrides)
    return govern_multiagent_session(list(nodes), **kwargs)


def memory(
    *,
    namespace="PERSONA",
    memory_class="TENANT",
    tenant="tenant-a",
    persona="admin",
    validation_state="VALIDATED",
    retention="PROJECT",
    confidence="95",
    valid_from="2026-10-04T18:00:00Z",
    expires_at="2026-10-04T20:00:00Z",
    version=1,
    previous_version="",
    tombstone=False,
):
    metadata = {"confidence_pct": confidence}
    if valid_from is not None:
        metadata["valid_from"] = valid_from
    if expires_at is not None:
        metadata["expires_at"] = expires_at
    return create_memory_record(
        namespace=namespace,
        memory_class=memory_class,
        content="" if tombstone else "validated operational memory",
        scope={"tenant_id": tenant, "persona_id": persona},
        provenance_ids=["PROV-1"],
        evidence_refs=["EVID-1"],
        version=version,
        previous_version=previous_version,
        validation_state=validation_state,
        retention=retention,
        sensitivity="RESTRICTED",
        tombstone=tombstone,
        created_at="2026-10-04T18:00:00Z",
        metadata=metadata,
    )


def use(record, **overrides):
    kwargs = {
        "now_ts": NOW,
        "trusted_tenant_id": "tenant-a",
        "trusted_persona_id": "admin",
        "minimum_confidence_pct": 70,
    }
    kwargs.update(overrides)
    return govern_memory_use(record, **kwargs)


def test_valid_multiagent_plan_is_governed_but_not_authorized():
    result = plan(
        node("aion-core"),
        node("researcher", "aion-core", capability="core.read"),
    )
    assert result["state"] == "WITHIN_GOVERNANCE"
    assert result["blockers"] == []
    assert result["supervisor_binding_verified"] is True
    assert result["delegation_lineage_verified"] is True
    assert result["capability_requests_within_host_ceiling"] is True
    assert result["grants_permission"] is False
    assert result["execution_allowed"] is False
    assert result["starts_agent"] is False
    assert result["starts_worker"] is False
    assert result["executes_action"] is False


def test_supervisor_must_be_canonical_root():
    result = plan(node("fake-root"), supervisor_id="aion-core")
    assert result["state"] == "BLOCK"
    assert "SUPERVISOR_ROOT_MISMATCH" in result["blockers"]


def test_delegation_lineage_must_match_parent():
    result = plan(
        node("aion-core"),
        node("child", "aion-core", delegated_by="other-agent"),
    )
    assert result["state"] == "BLOCK"
    assert "DELEGATION_LINEAGE_MISMATCH:child" in result["blockers"]


def test_root_cannot_claim_delegator():
    result = plan(node("aion-core", delegated_by="someone"))
    assert "ROOT_DELEGATION_INVALID:aion-core" in result["blockers"]


def test_capability_escalation_is_blocked():
    result = plan(node("aion-core", capability="deploy.production"))
    assert "CAPABILITY_ESCALATION_REQUESTED:aion-core" in result["blockers"]
    assert result["execution_allowed"] is False


def test_missing_capability_scope_is_blocked():
    result = plan(node("aion-core", capability=""))
    assert "CAPABILITY_SCOPE_MISSING:aion-core" in result["blockers"]


def test_session_deadline_expired_is_blocked():
    result = plan(
        node("aion-core", deadline_at="2026-10-04T18:30:00Z"),
        session_deadline_at="2026-10-04T18:59:59Z",
    )
    assert "SESSION_DEADLINE_EXCEEDED" in result["blockers"]


def test_node_deadline_cannot_outlive_session():
    result = plan(
        node("aion-core", deadline_at="2026-10-04T20:00:01Z"),
    )
    assert "NODE_DEADLINE_EXCEEDS_SESSION:aion-core" in result["blockers"]


def test_node_deadline_cannot_be_expired():
    result = plan(node("aion-core", deadline_at="2026-10-04T18:59:59Z"))
    assert "NODE_DEADLINE_EXPIRED:aion-core" in result["blockers"]


def test_invalid_node_deadline_is_blocked():
    result = plan(node("aion-core", deadline_at="tomorrow"))
    assert "NODE_DEADLINE_INVALID:aion-core" in result["blockers"]


def test_cost_budget_includes_existing_and_planned_cost():
    result = plan(
        node("aion-core", cost=2.5),
        node("child", "aion-core", cost=2.0),
        cost_limit_usd=5.0,
        cost_used_usd=1.0,
    )
    assert result["projected_cost_usd"] == 5.5
    assert "COST_BUDGET_EXCEEDED" in result["blockers"]


@pytest.mark.parametrize("bad", [True, -1, "NaN", float("inf")])
def test_invalid_node_cost_fails_closed(bad):
    result = plan(node("aion-core", cost=bad))
    assert "NODE_COST_INVALID:aion-core" in result["blockers"]


def test_existing_loop_cycle_is_inherited():
    result = plan(
        node("a", "b", delegated_by="b"),
        node("b", "a", delegated_by="a"),
        supervisor_id="a",
    )
    assert "CYCLE" in result["blockers"]


def test_existing_depth_limit_is_inherited():
    result = plan(
        node("aion-core"),
        node("b", "aion-core"),
        node("c", "b"),
        node("d", "c"),
        max_depth=3,
    )
    assert "DEPTH_LIMIT" in result["blockers"]


def test_existing_fanout_limit_is_inherited():
    children = [node(f"c{i}", "aion-core") for i in range(5)]
    result = plan(node("aion-core"), *children, max_fanout=4)
    assert "FANOUT_LIMIT" in result["blockers"]


def test_cross_tenant_plan_is_inherited_from_loop_governor():
    result = plan(node("aion-core", tenant_id="tenant-b"))
    assert "SCOPE_MISMATCH" in result["blockers"]


def test_shared_resource_budget_is_inherited():
    result = plan(node("aion-core"), call_limit=10, calls_used=10)
    assert "RESOURCE_BUDGET" in result["blockers"]


def test_valid_memory_is_usable_but_never_authority():
    result = use(memory())
    assert result["state"] == "USABLE"
    assert result["allowed_for_operational_use"] is True
    assert result["blockers"] == []
    assert result["grants_permission"] is False
    assert result["grants_authority"] is False
    assert result["changes_policy"] is False
    assert result["execution_allowed"] is False
    assert result["deletes_history"] is False


def test_tenant_mismatch_blocks_memory():
    result = use(memory(), trusted_tenant_id="tenant-b")
    assert result["state"] == "BLOCKED"
    assert "TENANT_SCOPE_MISMATCH" in result["blockers"]


def test_persona_mismatch_blocks_memory():
    result = use(memory(), trusted_persona_id="trader")
    assert "PERSONA_SCOPE_MISMATCH" in result["blockers"]


def test_missing_trusted_persona_blocks_persona_memory():
    result = use(memory(), trusted_persona_id="")
    assert "TRUSTED_PERSONA_REQUIRED" in result["blockers"]


def test_missing_trusted_tenant_blocks_scoped_memory():
    result = use(memory(), trusted_tenant_id="")
    assert "TRUSTED_TENANT_REQUIRED" in result["blockers"]


def test_low_confidence_blocks_memory():
    result = use(memory(confidence="69.9"))
    assert "CONFIDENCE_BELOW_THRESHOLD" in result["blockers"]


@pytest.mark.parametrize("confidence", [None, "", "invalid", "101", "-1"])
def test_missing_or_invalid_confidence_blocks(confidence):
    result = use(memory(confidence=confidence))
    assert "CONFIDENCE_MISSING_OR_INVALID" in result["blockers"]


def test_expired_memory_is_blocked_and_marked_for_audit_tombstone():
    result = use(memory(expires_at="2026-10-04T18:59:59Z"))
    assert "MEMORY_EXPIRED" in result["blockers"]
    assert result["retention_action"] == "EXPIRE_TO_AUDIT_TOMBSTONE"
    assert result["deletes_history"] is False


def test_future_memory_is_not_yet_valid():
    result = use(memory(valid_from="2026-10-04T19:30:00Z", expires_at="2026-10-04T20:00:00Z"))
    assert "MEMORY_NOT_YET_VALID" in result["blockers"]


def test_bounded_retention_requires_expiry():
    result = use(memory(expires_at=None))
    assert "EXPIRY_REQUIRED_FOR_BOUNDED_RETENTION" in result["blockers"]


def test_long_term_memory_can_omit_expiry_if_other_evidence_is_valid():
    record = memory(retention="LONG_TERM", expires_at=None)
    result = use(record)
    assert result["state"] == "USABLE"
    assert result["retention_action"] == "KEEP"


def test_conflicting_memory_is_never_operational():
    record = memory(validation_state="CONFLICTING")
    result = use(record)
    assert "CONFLICT_BLOCKER" in result["blockers"]
    assert result["allowed_for_operational_use"] is False


@pytest.mark.parametrize("state,expected", [
    ("OUTDATED", "OUTDATED"),
    ("DOUBTFUL", "DOUBTFUL"),
    ("QUARANTINED", "QUARANTINED"),
    ("REJECTED", "REJECTED"),
    ("UNVERIFIED", "EVIDENCE_NOT_VALIDATED"),
    ("PROPOSED", "EVIDENCE_NOT_VALIDATED"),
])
def test_nonvalidated_memory_states_are_blocked(state, expected):
    record = memory(validation_state=state)
    result = use(record)
    assert expected in result["blockers"]


def test_expiry_tombstone_preserves_history_and_versions_forward():
    original = memory(expires_at="2026-10-04T18:59:59Z")
    result = build_expiry_tombstone(
        original,
        now_ts=NOW,
        reason="PROJECT_TTL_EXPIRED",
    )
    tomb = result["tombstone"]
    assert result["state"] == "TOMBSTONE_PREPARED"
    assert result["deletes_original"] is False
    assert result["audit_history_preserved"] is True
    assert result["automatic_delete"] is False
    assert result["automatic_persist"] is False
    assert tomb["tombstone"] is True
    assert tomb["version"] == original.version + 1
    assert tomb["previous_version"] == original.memory_id
    assert tomb["rollback_pointer"] == original.memory_id
    assert result["execution_allowed"] is False


def test_tombstone_cannot_be_prepared_before_expiry():
    with pytest.raises(ValueError):
        build_expiry_tombstone(memory(), now_ts=NOW)


def test_legal_hold_cannot_be_expiry_tombstoned():
    record = memory(retention="LEGAL_HOLD", expires_at="2026-10-04T18:00:00Z")
    with pytest.raises(ValueError):
        build_expiry_tombstone(record, now_ts=NOW)


def test_memory_governor_requires_typed_contract_record():
    with pytest.raises(TypeError):
        govern_memory_use(
            {"memory_id": "forged"},
            now_ts=NOW,
            trusted_tenant_id="tenant-a",
            trusted_persona_id="admin",
        )


@pytest.mark.parametrize("threshold", [True, -1, 101, "invalid"])
def test_invalid_confidence_threshold_is_rejected(threshold):
    with pytest.raises(ValueError):
        use(memory(), minimum_confidence_pct=threshold)


def test_memory_record_cannot_set_execution_flag_via_metadata():
    record = create_memory_record(
        namespace="PERSONA",
        memory_class="TENANT",
        content="attempted authority claim",
        scope={"tenant_id": "tenant-a", "persona_id": "admin"},
        provenance_ids=["PROV-1"],
        evidence_refs=["EVID-1"],
        validation_state="VALIDATED",
        retention="PROJECT",
        sensitivity="RESTRICTED",
        metadata={
            "confidence_pct": "99",
            "valid_from": "2026-10-04T18:00:00Z",
            "expires_at": "2026-10-04T20:00:00Z",
            "execution_allowed": "true",
            "authority_verified": "true",
        },
    )
    result = use(record)
    assert result["state"] == "USABLE"
    assert result["execution_allowed"] is False
    assert result["grants_authority"] is False
    assert result["grants_permission"] is False
