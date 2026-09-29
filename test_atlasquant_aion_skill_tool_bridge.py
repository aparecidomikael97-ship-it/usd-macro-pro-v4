from __future__ import annotations

import unittest
from unittest.mock import patch

from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_skill_tool_bridge import plan_certified_skill_tool_call
from atlasquant_aion_tool_hub import default_tool_hub


TRUSTED = {"tenant_id": "tenant-a", "workspace_id": "central"}
ADMIN = {"role": "ADMIN", "username": "admin"}


def verified(refs):
    return {"state": "VERIFIED", "bound_refs": list(refs)}


def safe_manifest():
    return {
        "skill_id": "research.memory-helper",
        "version": "1.0.0",
        "tenant_scope": "CURRENT_TENANT",
        "workspace_ids": ["central"],
        "capability_ids": ["research.synthesize"],
        "tool_ids": ["aion.memory.search"],
        "allowed_roles": ["ADMIN"],
        "required_scopes": ["memory:read"],
        "network_required": False,
        "external_side_effects": False,
        "requires_human_approval": False,
        "rollback_supported": True,
        "cost_class": "FREE",
        "risk": "LOW",
        "provenance_refs": ["repo.skill.1"],
        "secret_refs": [],
    }


class AtlasQuantAionSkillToolBridgeTests(unittest.TestCase):
    def certified_plan(self, **kwargs):
        params = {
            "trusted_context": TRUSTED,
            "tool_hub": default_tool_hub(),
            "test_evidence": {"state": "PASS", "passed": True},
            "provenance_verifier": verified,
            "review_approved": True,
            "portable_core": default_portable_core(),
            "access": ADMIN,
            "source_kind": "ADMIN",
            "authenticated_admin": True,
            "scope": "Buscar memória certificada.",
            "uncertainty_pct": 0,
            "impact": "LOW",
        }
        params.update(kwargs)
        return plan_certified_skill_tool_call(
            safe_manifest(),
            "aion.memory.search",
            **params,
        )

    def test_certified_skill_can_reach_tool_preflight_without_execution(self):
        out = self.certified_plan()
        self.assertEqual(out["certification"]["state"], "CERTIFIED")
        self.assertEqual(out["state"], "READY_FOR_EXECUTOR")
        self.assertEqual(out["blockers"], [])
        self.assertFalse(out["certification_is_authority"])
        self.assertFalse(out["activates_skill"])
        self.assertFalse(out["activates_connector"])
        self.assertFalse(out["executes_tool"])
        self.assertFalse(out["tool_called"])
        self.assertFalse(out["connector_called"])
        self.assertFalse(out["expands_permissions"])
        self.assertFalse(out["creates_entitlement"])
        self.assertFalse(out["real_trading_enabled"])
        self.assertFalse(out["tool_preflight"]["tool_called"])
        self.assertFalse(out["tool_preflight"]["connector_called"])

    def test_candidate_skill_is_blocked_before_tool_hub(self):
        with patch(
            "atlasquant_aion_skill_tool_bridge.plan_tool_call"
        ) as tool_hub:
            out = plan_certified_skill_tool_call(
                safe_manifest(),
                "aion.memory.search",
                trusted_context=TRUSTED,
                tool_hub=default_tool_hub(),
                test_evidence={"state": "PASS", "passed": True},
                provenance_verifier=verified,
                review_approved=False,
                portable_core=default_portable_core(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                scope="Buscar memória.",
                uncertainty_pct=0,
                impact="LOW",
            )
        tool_hub.assert_not_called()
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("SKILL_NOT_CERTIFIED:TESTED", out["blockers"])
        self.assertIsNone(out["tool_preflight"])

    def test_certification_does_not_grant_command_authority(self):
        out = self.certified_plan(
            source_kind="EXTERNAL_AI",
            authenticated_admin=False,
        )
        self.assertEqual(out["certification"]["state"], "CERTIFIED")
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", out["blockers"])
        self.assertFalse(out["certification_is_authority"])
        self.assertFalse(out["executes_tool"])

    def test_undeclared_tool_is_blocked_before_tool_hub(self):
        with patch(
            "atlasquant_aion_skill_tool_bridge.plan_tool_call"
        ) as tool_hub:
            out = plan_certified_skill_tool_call(
                safe_manifest(),
                "aion.status.read",
                trusted_context=TRUSTED,
                tool_hub=default_tool_hub(),
                test_evidence={"state": "PASS", "passed": True},
                provenance_verifier=verified,
                review_approved=True,
                portable_core=default_portable_core(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                scope="Ler status.",
                uncertainty_pct=0,
                impact="LOW",
            )
        tool_hub.assert_not_called()
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("TOOL_NOT_DECLARED_BY_SKILL", out["blockers"])

    def test_truthy_string_review_never_reaches_tool_hub(self):
        with patch(
            "atlasquant_aion_skill_tool_bridge.plan_tool_call"
        ) as tool_hub:
            out = plan_certified_skill_tool_call(
                safe_manifest(),
                "aion.memory.search",
                trusted_context=TRUSTED,
                tool_hub=default_tool_hub(),
                test_evidence={"state": "PASS", "passed": True},
                provenance_verifier=verified,
                review_approved="true",
                portable_core=default_portable_core(),
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                scope="Buscar memória.",
                uncertainty_pct=0,
                impact="LOW",
            )
        tool_hub.assert_not_called()
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("SKILL_NOT_CERTIFIED:TESTED", out["blockers"])


if __name__ == "__main__":
    unittest.main()
