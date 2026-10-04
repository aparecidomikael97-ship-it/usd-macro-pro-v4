"""AION V2.20 Core Certification + synthetic stress/red-team."""
from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_core_certification import (
    REQUIRED_DIMENSIONS,
    canonical_evidence_attestation_bytes,
    certification_evidence_digest,
    certify_core,
    normalize_evidence,
    synthetic_evidence_row,
    verify_evidence_attestation,
)
from atlasquant_aion_memory_contract import create_memory_record
from atlasquant_aion_model_gateway_v2 import (
    ProviderNeutralModelRegistry,
    endpoint_from_mapping,
    route_model_request,
)
from atlasquant_aion_multiagent_memory_governor import (
    govern_memory_use,
    govern_multiagent_session,
)
from atlasquant_aion_operational_resilience_kernel import build_trace_context
from atlasquant_aion_policy_kernel import evaluate_policy_intent
from atlasquant_aion_durable_execution_kernel import canonical_execution_id
from atlasquant_aion_trust_root import TrustRootRegistry


TARGET = "a" * 40
NOW = "2026-10-04T20:00:00Z"
ISSUED = "2026-10-04T19:00:00Z"
EXPIRES = "2026-10-04T21:00:00Z"
KEY_ID = "test-certification-key"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def new_keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private, b64url(public)


PRIVATE_KEY, PUBLIC_KEY_B64 = new_keypair()
TRUST_ROOTS = TrustRootRegistry.from_mapping({
    "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
    "roots": [{
        "key_id": KEY_ID,
        "key_version": 1,
        "algorithm": "Ed25519",
        "public_key_b64": PUBLIC_KEY_B64,
        "status": "ACTIVE",
        "not_before": "2026-10-01T00:00:00Z",
        "not_after": "2027-10-01T00:00:00Z",
    }],
    "revoked_key_ids": [],
})


def signed_evidence_row(
    dimension,
    *,
    commit_sha=TARGET,
    run_id="run",
    test_count=100,
    source="TEST_SUITE",
    private_key=PRIVATE_KEY,
    key_id=KEY_ID,
    issued_at=ISSUED,
    expires_at=EXPIRES,
):
    row = synthetic_evidence_row(
        dimension,
        commit_sha=commit_sha,
        run_id=run_id,
        test_count=test_count,
        source=source,
        key_id=key_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    row["signature_b64"] = b64url(
        private_key.sign(canonical_evidence_attestation_bytes(dimension, row))
    )
    return row


def evidence(commit=TARGET, count=100):
    return {
        dimension: signed_evidence_row(
            dimension,
            commit_sha=commit,
            run_id=f"run-{index:02d}",
            test_count=count,
        )
        for index, dimension in enumerate(REQUIRED_DIMENSIONS, 1)
    }


def certificate(rows=None, **overrides):
    kwargs = {
        "evidence": rows if rows is not None else evidence(),
        "target_commit_sha": TARGET,
        "canonical_gates_green": True,
        "global_worker_readiness_green": True,
        "certification_trust_roots": TRUST_ROOTS,
        "now_ts": NOW,
        "core_freeze_authorized": False,
    }
    kwargs.update(overrides)
    return certify_core(**kwargs)


def local_endpoint():
    return endpoint_from_mapping({
        "provider_id": "local-runtime",
        "model_id": "local-safe",
        "lane": "LOCAL_DETERMINISTIC",
        "health_state": "HEALTHY",
        "local": True,
        "zero_cost": True,
        "enabled": True,
        "priority": 100,
        "capabilities": ["chat", "reasoning", "private"],
        "estimated_request_cost_usd": 0.0,
    })


def external_endpoint(provider, model, priority):
    return endpoint_from_mapping({
        "provider_id": provider,
        "model_id": model,
        "lane": "EXTERNAL_FAST",
        "health_state": "HEALTHY",
        "local": False,
        "zero_cost": False,
        "enabled": True,
        "priority": priority,
        "capabilities": ["chat"],
        "estimated_request_cost_usd": 0.01,
    })


def test_all_dimensions_produce_candidate_but_never_freeze():
    result = certificate()
    assert result["state"] == "CERTIFICATION_CANDIDATE"
    assert result["certification_candidate"] is True
    assert result["core_complete_candidate"] is True
    assert result["core_complete_claim_allowed"] is False
    assert result["owner_core_complete_review_required"] is True
    assert result["total_evidence_test_count"] == 1500
    assert result["core_frozen"] is False
    assert result["core_freeze_authorized_by_this_module"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["executes_action"] is False


def test_even_explicit_freeze_request_does_not_freeze():
    result = certificate(core_freeze_authorized=True)
    assert result["certification_candidate"] is True
    assert result["core_freeze_requested"] is True
    assert result["core_freeze_authorized_by_this_module"] is False
    assert result["core_frozen"] is False


@pytest.mark.parametrize("dimension", REQUIRED_DIMENSIONS)
def test_each_missing_dimension_blocks_certification(dimension):
    rows = evidence()
    del rows[dimension]
    result = certificate(rows)
    assert result["state"] == "BLOCKED"
    assert f"DIMENSION_NOT_CERTIFIED:{dimension}" in result["blockers"]


@pytest.mark.parametrize("dimension", REQUIRED_DIMENSIONS)
def test_each_dimension_must_match_target_commit(dimension):
    rows = evidence()
    rows[dimension] = signed_evidence_row(
        dimension,
        commit_sha="b" * 40,
        run_id="other-run",
        test_count=100,
    )
    result = certificate(rows)
    assert f"DIMENSION_COMMIT_MISMATCH:{dimension}" in result["blockers"]


@pytest.mark.parametrize("mutation,blocker", [
    ({"state": "FAILED"}, "EVIDENCE_STATE_NOT_VERIFIED"),
    ({"source": "USER"}, "EVIDENCE_SOURCE_INVALID"),
    ({"run_id": ""}, "EVIDENCE_RUN_ID_REQUIRED"),
    ({"commit_sha": "short"}, "EVIDENCE_COMMIT_SHA_INVALID"),
    ({"evidence_digest": "sha256:abc"}, "EVIDENCE_DIGEST_INVALID"),
    ({"test_count": 0}, "EVIDENCE_TEST_COUNT_INVALID"),
    ({"verified": 1}, "EVIDENCE_NOT_VERIFIED"),
])
def test_evidence_truth_is_strict(mutation, blocker):
    row = signed_evidence_row(
        "LOAD",
        commit_sha=TARGET,
        run_id="run-load",
        test_count=100,
    )
    row.update(mutation)
    normalized = normalize_evidence("LOAD", row)
    assert normalized["eligible"] is False
    assert blocker in normalized["blockers"]


def test_evidence_digest_must_match_evidence_content():
    rows = evidence()
    rows["LOAD"]["run_id"] = "tampered-run-id"
    result = certificate(rows)
    assert result["state"] == "BLOCKED"
    assert "DIMENSION_NOT_CERTIFIED:LOAD" in result["blockers"]
    normalized = normalize_evidence("LOAD", rows["LOAD"])
    assert "EVIDENCE_DIGEST_MISMATCH" in normalized["blockers"]


def test_unknown_evidence_dimension_blocks():
    rows = evidence()
    rows["MAGIC"] = synthetic_evidence_row(
        "LOAD",
        commit_sha=TARGET,
        run_id="run-extra",
        test_count=100,
    )
    result = certificate(rows)
    assert "UNEXPECTED_EVIDENCE_DIMENSION" in result["blockers"]


def test_canonical_gates_are_required():
    result = certificate(canonical_gates_green=False)
    assert "CANONICAL_GATES_NOT_GREEN" in result["blockers"]


def test_global_worker_readiness_is_required_but_does_not_arm():
    result = certificate(global_worker_readiness_green=False)
    assert "GLOBAL_WORKER_READINESS_NOT_GREEN" in result["blockers"]
    assert result["worker_armed"] is False


def test_minimum_test_volume_is_enforced():
    rows = evidence(count=1)
    result = certificate(rows)
    assert result["total_evidence_test_count"] == len(REQUIRED_DIMENSIONS)
    assert "CERTIFICATION_TEST_VOLUME_BELOW_MINIMUM" in result["blockers"]


@pytest.mark.parametrize("field,value", [
    ("canonical_gates_green", 1),
    ("global_worker_readiness_green", "true"),
    ("core_freeze_authorized", None),
])
def test_certification_security_booleans_are_exact(field, value):
    with pytest.raises(ValueError):
        certificate(**{field: value})


def test_certification_manifest_is_deterministic():
    a = certificate()
    b = certificate()
    assert a["manifest_digest"] == b["manifest_digest"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_evidence_digest_is_deterministic():
    rows = evidence()
    assert certification_evidence_digest(
        rows,
        certification_trust_roots=TRUST_ROOTS,
        now_ts=NOW,
    ) == certification_evidence_digest(
        rows,
        certification_trust_roots=TRUST_ROOTS,
        now_ts=NOW,
    )


def test_synthetic_evidence_helper_rejects_unknown_dimension():
    with pytest.raises(ValueError):
        synthetic_evidence_row(
            "UNKNOWN",
            commit_sha=TARGET,
            run_id="run",
            test_count=1,
        )


def test_stress_5000_trace_contexts_are_deterministic_and_action_free():
    seen = set()
    for i in range(5000):
        value = build_trace_context(
            request_id=f"req-{i}",
            task_id=f"task-{i}",
            execution_id=f"exe-{i}",
        )
        assert value["executes_action"] is False
        assert value["contains_secret_material"] is False
        seen.add(value["trace_id"])
    assert len(seen) == 5000


def test_stress_3000_provider_routes_never_call_provider():
    reg = ProviderNeutralModelRegistry([
        local_endpoint(),
        external_endpoint("provider-a", "fast-a", 10),
        external_endpoint("provider-b", "fast-b", 20),
    ])
    external = 0
    local = 0
    for i in range(3000):
        private = i % 3 == 0
        result = route_model_request(
            reg,
            task_class="PRIVATE" if private else "GENERAL",
            required_capabilities=["private"] if private else ["chat"],
            privacy_sensitive=private,
            offline_required=False,
            external_models_enabled=True,
            budget_remaining_usd=10.0,
            max_request_cost_usd=0.05,
        )
        assert result["provider_called"] is False
        assert result["billing_executed"] is False
        assert result["execution_allowed"] is False
        assert result["executes_action"] is False
        if result["selected"]["local"]:
            local += 1
        else:
            external += 1
    assert local == 1000
    assert external == 2000


def test_stress_2000_policy_decisions_never_become_execution():
    authority = {
        "state": "VERIFIED",
        "authority_verified": True,
        "execution_allowed": False,
        "executes_action": False,
    }
    scope = {
        "state": "SCOPE_VERIFIED",
        "capability_scope_verified": True,
        "tenant_id": "tenant-a",
        "domain": "CORE",
        "max_cost_usd": 1.0,
        "execution_allowed": False,
        "executes_action": False,
    }
    resilience = {
        "posture": "NORMAL_MONITORED",
        "kill_switch_engaged": False,
        "execution_allowed": False,
        "executes_action": False,
    }
    governance = {
        "state": "WITHIN_GOVERNANCE",
        "execution_allowed": False,
    }
    for i in range(2000):
        result = evaluate_policy_intent(
            action="DRAFT",
            trusted_tenant_id="tenant-a",
            trusted_domain="CORE",
            authority_verification=authority,
            capability_scope=scope,
            operational_resilience=resilience,
            multiagent_governance=governance,
            durable_execution=None,
            requested_cost_usd=0.0,
            budget_remaining_usd=10.0,
            kill_switch_engaged=False,
            privacy_review_verified=False,
            real_trading_enabled=False,
        )
        assert result["state"] == "POLICY_PERMITS_PROGRESS"
        assert result["execution_allowed"] is False
        assert result["executes_action"] is False


def test_stress_1000_multiagent_governance_decisions_are_bounded():
    for i in range(1000):
        result = govern_multiagent_session(
            [
                {
                    "node_id": "aion-core",
                    "parent_id": "",
                    "delegated_by": "",
                    "requested_capability": "core.plan",
                    "deadline_at": "2026-10-04T20:00:00Z",
                    "estimated_cost_usd": 0.01,
                    "guardian_risk": "READ",
                    "impact": "LOW",
                    "uncertainty_pct": 0,
                    "reversible": False,
                    "external_side_effects": False,
                },
                {
                    "node_id": f"child-{i}",
                    "parent_id": "aion-core",
                    "delegated_by": "aion-core",
                    "requested_capability": "core.read",
                    "deadline_at": "2026-10-04T20:00:00Z",
                    "estimated_cost_usd": 0.01,
                    "guardian_risk": "READ",
                    "impact": "LOW",
                    "uncertainty_pct": 0,
                    "reversible": False,
                    "external_side_effects": False,
                },
            ],
            trusted_context={"tenant_id": "tenant-a", "workspace_id": "workspace-a"},
            supervisor_id="aion-core",
            allowed_capabilities=["core.plan", "core.read"],
            now_ts="2026-10-04T19:00:00Z",
            session_deadline_at="2026-10-04T21:00:00Z",
            cost_limit_usd=10.0,
            cost_used_usd=0.0,
        )
        assert result["state"] == "WITHIN_GOVERNANCE"
        assert result["execution_allowed"] is False
        assert result["starts_agent"] is False


def test_stress_1000_memory_reads_never_grant_authority():
    record = create_memory_record(
        namespace="PERSONA",
        memory_class="TENANT",
        content="validated memory",
        scope={"tenant_id": "tenant-a", "persona_id": "admin"},
        provenance_ids=["PROV-1"],
        evidence_refs=["EVID-1"],
        validation_state="VALIDATED",
        retention="PROJECT",
        sensitivity="RESTRICTED",
        created_at="2026-10-04T18:00:00Z",
        metadata={
            "confidence_pct": "99",
            "valid_from": "2026-10-04T18:00:00Z",
            "expires_at": "2026-10-04T22:00:00Z",
        },
    )
    for _ in range(1000):
        result = govern_memory_use(
            record,
            now_ts="2026-10-04T19:00:00Z",
            trusted_tenant_id="tenant-a",
            trusted_persona_id="admin",
        )
        assert result["state"] == "USABLE"
        assert result["grants_permission"] is False
        assert result["grants_authority"] is False
        assert result["execution_allowed"] is False


def test_stress_10000_canonical_execution_ids_do_not_collide():
    ids = {
        canonical_execution_id(
            f"task-{i}",
            f"step-{i % 7}",
            f"idem-{i}",
            f"{i:064x}"[-64:],
        )
        for i in range(10000)
    }
    assert len(ids) == 10000
