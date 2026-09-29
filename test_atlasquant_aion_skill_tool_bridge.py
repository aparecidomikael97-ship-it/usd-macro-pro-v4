from __future__ import annotations

import unittest
from unittest.mock import patch

from atlasquant_aion_capabilities import CapabilityRegistry
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_skill_certification import (
    assess_skill_manifest,
    transition_skill_certification,
)
from atlasquant_aion_skill_tool_bridge import plan_certified_skill_tool_call
from atlasquant_aion_tool_hub import default_tool_hub


TRUSTED = {
    "tenant_id": "tenant-a",
    "workspace_id": "central",
    "role": "ADMIN",
}
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


def certified_record():
    return assess_skill_manifest(
        safe_manifest(),
        trusted_context=TRUSTED,
        test_evidence={"state": "PASS", "passed": True},
        provenance_verifier=verified,
        review_approved=True,
    )


class AtlasQuantAionSkillToolBridgeTests(unittest.TestCase):
    def certified_plan(self, record=None, **kwargs):
        params = {
            "trusted_context": TRUSTED,
            "tool_hub": default_tool_hub(),
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
            record or certified_record(),
            "aion.memory.search",
            **params,
        )

    def test_sealed_certified_record_can_reach_tool_preflight_without_execution(self):
        out = self.certified_plan()
        self.assertTrue(out["record_gate"]["valid"])
        self.assertEqual(out["certification_record"]["state"], "CERTIFIED")
        self.assertEqual(out["state"], "READY_FOR_EXECUTOR")
        self.assertEqual(out["blockers"], [])
        self.assertEqual(out["current_policy"]["blockers"], [])
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

    def test_raw_manifest_cannot_self_certify_inside_bridge(self):
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = plan_certified_skill_tool_call(
                safe_manifest(),
                "aion.memory.search",
                trusted_context=TRUSTED,
                tool_hub=default_tool_hub(),
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
        self.assertIn("CERTIFICATION_RECORD_SCHEMA_INVALID", out["blockers"])
        self.assertIsNone(out["tool_preflight"])

    def test_tested_record_is_blocked_before_tool_hub(self):
        tested = assess_skill_manifest(
            safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=False,
        )
        self.assertEqual(tested["state"], "TESTED")
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = self.certified_plan(record=tested)
        tool_hub.assert_not_called()
        self.assertIn("SKILL_RECORD_NOT_CERTIFIED:TESTED", out["blockers"])

    def test_suspended_and_revoked_records_never_reach_tool_hub(self):
        certified = certified_record()
        suspended = transition_skill_certification(
            certified,
            action="SUSPEND",
            trusted_context=TRUSTED,
            approved=True,
            reason="Security review.",
        )
        revoked = transition_skill_certification(
            suspended,
            action="REVOKE",
            trusted_context=TRUSTED,
            approved=True,
            reason="Provenance invalidated.",
        )
        for record, expected in (
            (suspended, "SKILL_RECORD_NOT_CERTIFIED:SUSPENDED"),
            (revoked, "SKILL_RECORD_NOT_CERTIFIED:REVOKED"),
        ):
            with self.subTest(state=record["state"]), patch(
                "atlasquant_aion_skill_tool_bridge.plan_tool_call"
            ) as tool_hub:
                out = self.certified_plan(record=record)
            tool_hub.assert_not_called()
            self.assertEqual(out["state"], "BLOCK")
            self.assertIn(expected, out["blockers"])

    def test_forged_certified_state_fails_record_fingerprint(self):
        tested = assess_skill_manifest(
            safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=False,
        )
        tested["state"] = "CERTIFIED"
        tested["review_approved"] = True
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = self.certified_plan(record=tested)
        tool_hub.assert_not_called()
        self.assertIn(
            "CERTIFICATION_RECORD_FINGERPRINT_MISMATCH",
            out["blockers"],
        )

    def test_certification_does_not_grant_command_authority(self):
        out = self.certified_plan(
            source_kind="EXTERNAL_AI",
            authenticated_admin=False,
        )
        self.assertEqual(out["certification_record"]["state"], "CERTIFIED")
        self.assertEqual(out["state"], "BLOCK")
        self.assertIn("SOURCE_HAS_NO_COMMAND_AUTHORITY", out["blockers"])
        self.assertFalse(out["certification_is_authority"])
        self.assertFalse(out["executes_tool"])

    def test_undeclared_tool_is_blocked_before_tool_hub(self):
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = plan_certified_skill_tool_call(
                certified_record(),
                "aion.status.read",
                trusted_context=TRUSTED,
                tool_hub=default_tool_hub(),
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

    def test_cross_tenant_record_is_blocked_before_tool_hub(self):
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = self.certified_plan(
                trusted_context={
                    "tenant_id": "tenant-b",
                    "workspace_id": "central",
                    "role": "ADMIN",
                }
            )
        tool_hub.assert_not_called()
        self.assertIn("CERTIFICATION_SCOPE_MISMATCH", out["blockers"])

    def test_current_registry_drift_blocks_stale_certification(self):
        with patch("atlasquant_aion_skill_tool_bridge.plan_tool_call") as tool_hub:
            out = self.certified_plan(
                capability_registry=CapabilityRegistry([]),
            )
        tool_hub.assert_not_called()
        self.assertEqual(out["state"], "BLOCK")
        self.assertTrue(
            any(
                item.startswith("CURRENT_POLICY_BLOCKED:CAPABILITY_NOT_REGISTERED")
                for item in out["blockers"]
            )
        )


if __name__ == "__main__":
    unittest.main()
