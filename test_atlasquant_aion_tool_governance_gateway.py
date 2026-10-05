from __future__ import annotations

from pathlib import Path
import unittest

from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_governance_gateway import tool_governance_gateway
from atlasquant_aion_tool_hub import default_tool_hub


def admin():
    return {"role": "ADMIN", "username": "admin"}


def scope(workspace="central"):
    return {
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": workspace,
    }


def budget(
    *,
    workspace="administration",
    transaction_id="tx-001",
    authority_budget_ref="budget-001",
    allowed=True,
):
    return {
        "schema": "ATLASQUANT_AION_CUMULATIVE_AUTHORITY_BUDGET_V1",
        "allowed": allowed,
        "reason": "ALLOW" if allowed else "BLOCK",
        "authority_budget_ref": authority_budget_ref,
        "transaction_id": transaction_id,
        "policy_version": "policy-v1",
        "policy_digest": "sha256:policy",
        "scope": scope(workspace),
        "grants_authority": False,
        "execution_allowed_by_this_component": False,
        "executes_action": False,
    }


class AionToolGovernanceGatewayTests(unittest.TestCase):
    def test_local_read_tool_can_reach_handoff_without_execution(self):
        out = tool_governance_gateway(
            tool_id="aion.memory.search",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("central"),
            trusted_granted_scopes=["memory:read"],
            transaction_id="tx-read-001",
            source_kind="ADMIN",
            authenticated_admin=True,
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(out["state"], "READY_FOR_EXECUTOR")
        self.assertTrue(out["receipt_required"])
        self.assertFalse(out["handoff_grants_authority"])
        self.assertFalse(out["tool_called"])
        self.assertFalse(out["network_called"])
        self.assertFalse(out["executes_action"])

    def test_missing_required_scope_blocks(self):
        out = tool_governance_gateway(
            tool_id="aion.memory.search",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("central"),
            trusted_granted_scopes=[],
            transaction_id="tx-read-002",
            source_kind="ADMIN",
            authenticated_admin=True,
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("MISSING_SCOPE:memory:read", out["blockers"])

    def test_cross_workspace_tool_use_blocks(self):
        out = tool_governance_gateway(
            tool_id="aion.memory.search",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["memory:read"],
            transaction_id="tx-read-003",
            source_kind="ADMIN",
            authenticated_admin=True,
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("TOOL_WORKSPACE_SCOPE_MISMATCH", out["blockers"])

    def test_transport_mismatch_blocks_local_tool(self):
        out = tool_governance_gateway(
            tool_id="aion.memory.search",
            transport="MCP",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("central"),
            trusted_granted_scopes=["memory:read"],
            transaction_id="tx-read-004",
            source_kind="ADMIN",
            authenticated_admin=True,
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("TRANSPORT_CONNECTOR_MISMATCH", out["blockers"])

    def test_external_source_cannot_gain_authority_through_gateway(self):
        out = tool_governance_gateway(
            tool_id="aion.memory.search",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("central"),
            trusted_granted_scopes=["memory:read"],
            transaction_id="tx-read-005",
            source_kind="EXTERNAL_AI",
            authenticated_admin=False,
            uncertainty_pct=0,
            impact="LOW",
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", out["blockers"])
        self.assertFalse(out["handoff_grants_authority"])

    def test_checkpoint_write_requires_approval_evidence_rollback_and_budget(self):
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=budget(),
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            approval_refs=["approval:owner:001"],
            evidence_refs=["tests:pass", "checkpoint:diff"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "READY_FOR_EXECUTOR")
        self.assertTrue(out["side_effect"])
        self.assertEqual(out["authority_budget_state"], "VERIFIED")
        self.assertTrue(out["receipt_required"])
        self.assertFalse(out["production_mutation"])

    def test_truthy_approval_string_does_not_approve_side_effect(self):
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=budget(),
            source_kind="ADMIN",
            authenticated_admin=True,
            approved="true",
            approval_refs=["approval:owner:001"],
            evidence_refs=["tests:pass"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("EXPLICIT_HUMAN_APPROVAL_REQUIRED", out["blockers"])

    def test_side_effect_without_approval_ref_is_blocked(self):
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=budget(),
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            approval_refs=[],
            evidence_refs=["tests:pass"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("APPROVAL_REFERENCE_REQUIRED", out["blockers"])

    def test_side_effect_without_evidence_or_recovery_ref_is_blocked(self):
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=budget(),
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            approval_refs=["approval:owner:001"],
            evidence_refs=[],
            rollback_ref="",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("EVIDENCE_REFERENCE_REQUIRED", out["blockers"])
        self.assertIn("ROLLBACK_OR_RECOVERY_REFERENCE_REQUIRED", out["blockers"])

    def test_budget_scope_transaction_and_ref_are_bound(self):
        bad = budget(
            workspace="central",
            transaction_id="other-tx",
            authority_budget_ref="other-budget",
        )
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=bad,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            approval_refs=["approval:owner:001"],
            evidence_refs=["tests:pass"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("AUTHORITY_BUDGET_TRANSACTION_MISMATCH", out["blockers"])
        self.assertIn("AUTHORITY_BUDGET_REF_MISMATCH", out["blockers"])
        self.assertIn("AUTHORITY_BUDGET_SCOPE_MISMATCH", out["blockers"])

    def test_budget_component_cannot_claim_authority_or_execution(self):
        bad = budget()
        bad["grants_authority"] = True
        bad["executes_action"] = True
        out = tool_governance_gateway(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=bad,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            approval_refs=["approval:owner:001"],
            evidence_refs=["tests:pass"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("AUTHORITY_BUDGET_COMPONENT_UNSAFE", out["blockers"])
        self.assertIn("AUTHORITY_BUDGET_EXECUTION_UNSAFE", out["blockers"])

    def test_handoff_digest_is_deterministic_and_bound_to_approval(self):
        kwargs = dict(
            tool_id="aion.checkpoint.prepare_save",
            transport="LOCAL",
            hub=default_tool_hub(),
            portable_core=default_portable_core(),
            access=admin(),
            trusted_scope=scope("administration"),
            trusted_granted_scopes=["checkpoint:write"],
            transaction_id="tx-001",
            authority_budget_ref="budget-001",
            authority_budget_evidence=budget(),
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
            evidence_refs=["tests:pass"],
            rollback_ref="checkpoint:previous-version",
            tests=[{"state": "PASS"}],
            uncertainty_pct=0,
            impact="MEDIUM",
            reversible=True,
        )
        first = tool_governance_gateway(
            **kwargs,
            approval_refs=["approval:owner:001"],
        )
        second = tool_governance_gateway(
            **kwargs,
            approval_refs=["approval:owner:001"],
        )
        changed = tool_governance_gateway(
            **kwargs,
            approval_refs=["approval:owner:002"],
        )
        self.assertEqual(first["handoff_digest"], second["handoff_digest"])
        self.assertNotEqual(first["handoff_digest"], changed["handoff_digest"])

    def test_gateway_has_no_executor_network_or_subprocess_implementation(self):
        source = Path("atlasquant_aion_tool_governance_gateway.py").read_text(
            encoding="utf-8"
        )
        for banned in (
            "requests.",
            "socket.",
            "subprocess.",
            "os.system(",
            "adapter.send(",
            "execute_tool(",
            "run_tool(",
            "CredentialProxy(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
