"""AION V2.15 adversarial tests for signed capability scope isolation."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_authority_verifier import (
    SCHEMA as AUTH_SCHEMA,
    canonical_statement_bytes,
)
from atlasquant_aion_capabilities import CapabilityRegistry
from atlasquant_aion_capability_isolation_gate import (
    SCHEMA,
    canonical_namespace,
    canonical_scope_grant_bytes,
    verify_capability_scope,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry


NOW = "2026-10-04T18:15:00Z"
ISSUED = "2026-10-04T18:10:00Z"
EXPIRES = "2026-10-04T19:00:00Z"
BINDING = {
    "subject_id": "aion-core",
    "tenant_id": "atlasquant-owner",
    "domain": "CORE",
    "policy_id": "AION_CORE_POLICY_V1",
}
WORKSPACE = "central"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private, b64url(public)


def trust_registry(public_key_b64):
    return TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": "root-1",
            "key_version": 1,
            "algorithm": "Ed25519",
            "public_key_b64": public_key_b64,
            "status": "ACTIVE",
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    })


def parent_statement(**overrides):
    row = {
        "schema": AUTH_SCHEMA,
        "statement_id": "parent-001",
        "authority_id": "owner-control-plane",
        "subject_id": BINDING["subject_id"],
        "tenant_id": BINDING["tenant_id"],
        "domain": BINDING["domain"],
        "policy_id": BINDING["policy_id"],
        "capabilities": ["central.conversation"],
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "nonce": "cGFyZW50LW5vbmNlLTE",
        "key_id": "root-1",
        "key_version": 1,
        "grant_kind": "CAPABILITY_GRANT",
    }
    row.update(overrides)
    return row


def scope_grant(**overrides):
    row = {
        "schema": SCHEMA,
        "grant_id": "scope-001",
        "parent_statement_id": "parent-001",
        "authority_id": "owner-control-plane",
        "subject_id": BINDING["subject_id"],
        "tenant_id": BINDING["tenant_id"],
        "workspace_id": WORKSPACE,
        "domain": BINDING["domain"],
        "policy_id": BINDING["policy_id"],
        "capability_id": "central.conversation",
        "allowed_tools": [],
        "allowed_actions": ["read"],
        "max_cost_usd": 0.0,
        "namespace": canonical_namespace(BINDING["tenant_id"], WORKSPACE, BINDING["domain"]),
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "nonce": "c2NvcGUtbm9uY2UtMQ",
        "key_id": "root-1",
        "key_version": 1,
        "grant_kind": "CAPABILITY_SCOPE_GRANT",
    }
    row.update(overrides)
    return row


def sign_parent(private, row):
    return b64url(private.sign(canonical_statement_bytes(row)))


def sign_scope(private, row):
    return b64url(private.sign(canonical_scope_grant_bytes(row)))


def fixture(tmp_path):
    private, public = keypair()
    roots = trust_registry(public)
    nonces = PersistentNonceRegistry(tmp_path / "nonces.sqlite3")
    return private, roots, nonces


def verify(tmp_path, *, parent=None, scope=None, binding=None, workspace=WORKSPACE,
           role="ADMIN", requested_tool="", requested_action="read", registry=None):
    private, roots, nonces = fixture(tmp_path)
    p = parent or parent_statement()
    s = scope or scope_grant()
    return verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(private, p),
        scope_grant=s,
        scope_signature_b64=sign_scope(private, s),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=binding or BINDING,
        expected_workspace_id=workspace,
        actor_role=role,
        requested_tool=requested_tool,
        requested_action=requested_action,
        registry=registry,
    )


def test_valid_scope_is_verified_but_not_executable(tmp_path):
    result = verify(tmp_path)
    assert result["state"] == "SCOPE_VERIFIED"
    assert result["parent_authority_verified"] is True
    assert result["scope_signature_verified"] is True
    assert result["capability_scope_verified"] is True
    assert result["tenant_isolated"] is True
    assert result["workspace_isolated"] is True
    assert result["domain_isolated"] is True
    assert result["namespace_verified"] is True
    assert result["execution_allowed"] is False
    assert result["approval_implied"] is False
    assert result["permissions_expanded"] is False
    assert result["executes_action"] is False


def test_parent_tenant_mismatch_blocks_before_scope(tmp_path):
    result = verify(
        tmp_path,
        binding={**BINDING, "tenant_id": "other-tenant"},
    )
    assert result["state"] == "BLOCKED"
    assert result["parent_authority_verified"] is False
    assert "PARENT_AUTHORITY_NOT_VERIFIED" in result["blockers"]


def test_workspace_is_cryptographically_bound(tmp_path):
    result = verify(tmp_path, workspace="other-workspace")
    assert result["state"] == "BLOCKED"
    assert "SCOPE_WORKSPACE_MISMATCH" in result["blockers"]


def test_namespace_mismatch_blocks(tmp_path):
    result = verify(
        tmp_path,
        scope=scope_grant(namespace="tenant/forged/workspace/central/domain/CORE"),
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_NAMESPACE_MISMATCH" in result["blockers"]


def test_cross_domain_capability_is_blocked_even_when_parent_lists_it(tmp_path):
    parent = parent_statement(capabilities=["business.analyze"])
    scope = scope_grant(capability_id="business.analyze")
    result = verify(tmp_path, parent=parent, scope=scope)
    assert result["state"] == "BLOCKED"
    assert "SCOPE_CAPABILITY_CROSS_DOMAIN" in result["blockers"]


def test_child_capability_must_exist_in_parent_grant(tmp_path):
    scope = scope_grant(capability_id="risk.assess")
    result = verify(tmp_path, scope=scope)
    assert result["state"] == "BLOCKED"
    assert "SCOPE_CAPABILITY_NOT_GRANTED_BY_PARENT" in result["blockers"]


def test_role_escalation_is_blocked(tmp_path):
    parent = parent_statement(
        domain="BUSINESS",
        policy_id="BUSINESS_POLICY_V1",
        capabilities=["business.analyze"],
    )
    binding = {
        "subject_id": "aion-core",
        "tenant_id": "atlasquant-owner",
        "domain": "BUSINESS",
        "policy_id": "BUSINESS_POLICY_V1",
    }
    scope = scope_grant(
        domain="BUSINESS",
        policy_id="BUSINESS_POLICY_V1",
        workspace_id="business",
        capability_id="business.analyze",
        namespace=canonical_namespace("atlasquant-owner", "business", "BUSINESS"),
    )
    result = verify(
        tmp_path,
        parent=parent,
        scope=scope,
        binding=binding,
        workspace="business",
        role="USER",
        requested_action="read",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_ROLE_NOT_ALLOWED" in result["blockers"]


def test_tool_escalation_is_blocked(tmp_path):
    scope = scope_grant(allowed_tools=["aion.memory.search"])
    result = verify(
        tmp_path,
        scope=scope,
        requested_tool="aion.memory.search",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_TOOL_GRANT_EXCEEDS_PROFILE" in result["blockers"]


def test_requested_tool_must_be_in_signed_child_grant(tmp_path):
    result = verify(tmp_path, requested_tool="repository.read")
    assert result["state"] == "BLOCKED"
    assert "SCOPE_REQUESTED_TOOL_NOT_GRANTED" in result["blockers"]


def test_action_escalation_is_blocked(tmp_path):
    scope = scope_grant(allowed_actions=["deploy"])
    result = verify(tmp_path, scope=scope, requested_action="deploy")
    assert result["state"] == "BLOCKED"
    assert "SCOPE_ACTION_GRANT_EXCEEDS_PROFILE" in result["blockers"]


def test_requested_action_must_be_in_signed_child_grant(tmp_path):
    result = verify(tmp_path, requested_action="coordinate")
    assert result["state"] == "BLOCKED"
    assert "SCOPE_REQUESTED_ACTION_NOT_GRANTED" in result["blockers"]


def test_budget_ceiling_blocks_capability_cost(tmp_path):
    registry = CapabilityRegistry([{
        "capability_id": "central.conversation",
        "specialist": "core",
        "domains": ["central", "conversation"],
        "description": "fixture",
        "inputs": ["question"],
        "outputs": ["answer"],
        "allowed_roles": ["ADMIN"],
        "estimated_cost_usd": 5.0,
        "execution_mode": "READ_ONLY",
    }])
    result = verify(
        tmp_path,
        registry=registry,
        scope=scope_grant(max_cost_usd=1.0),
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_COST_CEILING_EXCEEDED" in result["blockers"]


@pytest.mark.parametrize("cost", [-1, True, "1.0", float("inf"), float("nan")])
def test_invalid_budget_ceiling_blocks(tmp_path, cost):
    private, roots, nonces = fixture(tmp_path)
    p = parent_statement()
    s = scope_grant(max_cost_usd=cost)
    # NaN/inf cannot be canonical JSON signed by the strict helper; feed a
    # placeholder signature and prove the shape/cost gate fails first.
    try:
        scope_sig = sign_scope(private, s)
    except ValueError:
        scope_sig = "AA"
    result = verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(private, p),
        scope_grant=s,
        scope_signature_b64=scope_sig,
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_COST_LIMIT_INVALID" in result["blockers"]


def test_scope_tamper_after_signature_is_blocked(tmp_path):
    private, roots, nonces = fixture(tmp_path)
    p = parent_statement()
    original = scope_grant()
    sig = sign_scope(private, original)
    tampered = dict(original)
    tampered["allowed_actions"] = ["coordinate"]
    result = verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(private, p),
        scope_grant=tampered,
        scope_signature_b64=sig,
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="coordinate",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_SIGNATURE_INVALID" in result["blockers"]


def test_wrong_scope_signing_key_is_blocked(tmp_path):
    private, roots, nonces = fixture(tmp_path)
    attacker, _ = keypair()
    p = parent_statement()
    s = scope_grant()
    result = verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(private, p),
        scope_grant=s,
        scope_signature_b64=sign_scope(attacker, s),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_SIGNATURE_INVALID" in result["blockers"]


def test_child_scope_cannot_outlive_parent(tmp_path):
    result = verify(
        tmp_path,
        scope=scope_grant(expires_at="2026-10-04T19:30:00Z"),
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_WINDOW_EXCEEDS_PARENT" in result["blockers"]


def test_scope_nonce_replay_blocked_across_new_parent(tmp_path):
    private, roots, nonces = fixture(tmp_path)

    p1 = parent_statement()
    s1 = scope_grant()
    first = verify_capability_scope(
        p1,
        parent_signature_b64=sign_parent(private, p1),
        scope_grant=s1,
        scope_signature_b64=sign_scope(private, s1),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert first["state"] == "SCOPE_VERIFIED"

    p2 = parent_statement(
        statement_id="parent-002",
        nonce="cGFyZW50LW5vbmNlLTI",
    )
    s2 = scope_grant(
        grant_id="scope-002",
        parent_statement_id="parent-002",
        # deliberately reuse the child nonce in the same capability scope
        nonce=s1["nonce"],
    )
    second = verify_capability_scope(
        p2,
        parent_signature_b64=sign_parent(private, p2),
        scope_grant=s2,
        scope_signature_b64=sign_scope(private, s2),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert second["state"] == "BLOCKED"
    assert "SCOPE_NONCE_REPLAYED" in second["blockers"]


def test_parent_replay_is_blocked(tmp_path):
    private, roots, nonces = fixture(tmp_path)
    p = parent_statement()
    s = scope_grant()
    kwargs = dict(
        parent_signature_b64=sign_parent(private, p),
        scope_grant=s,
        scope_signature_b64=sign_scope(private, s),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert verify_capability_scope(p, **kwargs)["state"] == "SCOPE_VERIFIED"
    second = verify_capability_scope(p, **kwargs)
    assert second["state"] == "BLOCKED"
    assert "PARENT_AUTHORITY_NOT_VERIFIED" in second["blockers"]


def test_scope_unknown_field_is_rejected(tmp_path):
    private, roots, nonces = fixture(tmp_path)
    p = parent_statement()
    s = scope_grant()
    s["execution_allowed"] = True
    result = verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(private, p),
        scope_grant=s,
        scope_signature_b64="AA",
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_GRANT_SHAPE_MISMATCH" in result["blockers"]


def test_canonical_namespace_separates_workspace_domain_and_tenant():
    a = canonical_namespace("tenant-a", "central", "CORE")
    b = canonical_namespace("tenant-b", "central", "CORE")
    c = canonical_namespace("tenant-a", "business", "CORE")
    d = canonical_namespace("tenant-a", "central", "BUSINESS")
    assert len({a, b, c, d}) == 4


def test_verified_scope_never_calls_tool_or_expands_permissions(tmp_path):
    result = verify(tmp_path)
    assert result["permissions_expanded"] is False
    assert result["tool_called"] is False
    assert result["external_action_executed"] is False
    assert result["real_trading_enabled"] is False
    assert result["execution_allowed"] is False


def test_child_cannot_switch_to_another_active_trust_root(tmp_path):
    parent_private, parent_public = keypair()
    child_private, child_public = keypair()
    roots = TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [
            {
                "key_id": "root-1", "key_version": 1, "algorithm": "Ed25519",
                "public_key_b64": parent_public, "status": "ACTIVE",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2027-10-01T00:00:00Z",
            },
            {
                "key_id": "root-2", "key_version": 1, "algorithm": "Ed25519",
                "public_key_b64": child_public, "status": "ACTIVE",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2027-10-01T00:00:00Z",
            },
        ],
        "revoked_key_ids": [],
    })
    nonces = PersistentNonceRegistry(tmp_path / "nonces.sqlite3")
    p = parent_statement()
    s = scope_grant(key_id="root-2")
    result = verify_capability_scope(
        p,
        parent_signature_b64=sign_parent(parent_private, p),
        scope_grant=s,
        scope_signature_b64=sign_scope(child_private, s),
        trust_roots=roots,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
        expected_workspace_id=WORKSPACE,
        actor_role="ADMIN",
        requested_action="read",
    )
    assert result["state"] == "BLOCKED"
    assert "SCOPE_SIGNER_MISMATCH_PARENT" in result["blockers"]
