from __future__ import annotations

import unittest

from atlasquant_aion_skill_certification import assess_skill_manifest


TRUSTED = {"tenant_id": "tenant-a", "workspace_id": "central"}


def verified(refs):
    return {"state": "VERIFIED", "bound_refs": list(refs)}


class AtlasQuantAionSkillCertificationTests(unittest.TestCase):
    def safe_manifest(self):
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
            "provenance_refs": ["repo:skill:1"],
            "secret_refs": [],
        }

    def test_safe_manifest_can_reach_certified_without_activation(self):
        out = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertEqual(out["state"], "CERTIFIED")
        self.assertEqual(out["blockers"], [])
        self.assertFalse(out["activates_skill"])
        self.assertFalse(out["activates_connector"])
        self.assertFalse(out["executes_tool"])
        self.assertFalse(out["expands_permissions"])

    def test_string_review_approval_does_not_certify(self):
        out = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved="true",
        )
        self.assertEqual(out["state"], "TESTED")
        self.assertFalse(out["review_approved"])

    def test_unknown_capability_blocks(self):
        raw = self.safe_manifest()
        raw["capability_ids"] = ["unknown.capability"]
        out = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertIn("CAPABILITY_NOT_REGISTERED:unknown.capability", out["blockers"])
        self.assertNotEqual(out["state"], "CERTIFIED")

    def test_tool_must_be_allowed_by_capability(self):
        raw = self.safe_manifest()
        raw["tool_ids"] = ["aion.status.read"]
        raw["required_scopes"] = ["status:read"]
        out = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertIn("TOOL_NOT_ALLOWED_BY_CAPABILITY:aion.status.read", out["blockers"])

    def test_role_scope_cannot_expand(self):
        raw = self.safe_manifest()
        raw["allowed_roles"] = ["ADMIN", "ROOT"]
        out = assess_skill_manifest(raw, trusted_context=TRUSTED)
        self.assertIn("ROLE_SCOPE_EXPANSION", out["blockers"])

    def test_cross_tenant_scope_is_rejected(self):
        raw = self.safe_manifest()
        raw["tenant_scope"] = "*"
        out = assess_skill_manifest(raw, trusted_context=TRUSTED)
        self.assertIn("TENANT_SCOPE_INVALID", out["blockers"])

    def test_raw_secret_is_rejected(self):
        raw = self.safe_manifest()
        raw["secret_refs"] = ["token=example-secret-value"]
        out = assess_skill_manifest(raw, trusted_context=TRUSTED)
        self.assertIn("RAW_SECRET_DETECTED", out["blockers"])

    def test_ambiguous_boolean_metadata_is_rejected(self):
        raw = self.safe_manifest()
        raw["external_side_effects"] = "false"
        out = assess_skill_manifest(raw, trusted_context=TRUSTED)
        self.assertIn("BOOLEAN_FIELD_INVALID", out["blockers"])

    def test_tool_workspace_must_stay_inside_manifest_scope(self):
        raw = self.safe_manifest()
        raw["workspace_ids"] = ["administration"]
        out = assess_skill_manifest(
            raw,
            trusted_context={"tenant_id": "tenant-a", "workspace_id": "administration"},
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertIn(
            "TOOL_WORKSPACE_OUT_OF_SCOPE:aion.memory.search",
            out["blockers"],
        )
        self.assertNotEqual(out["state"], "CERTIFIED")

    def test_connector_tool_cannot_underdeclare_network_requirement(self):
        raw = self.safe_manifest()
        raw["capability_ids"] = ["research.synthesize"]
        raw["tool_ids"] = ["external.research.read"]
        raw["required_scopes"] = ["research:read"]
        hub = {
            "tools": [{
                "tool_id": "external.research.read",
                "label": "External research",
                "workspace_id": "central",
                "connector_id": "research-api",
                "kind": "READ",
                "guardian_action": "read",
                "state": "CONFIGURED",
                "required_scopes": ["research:read"],
                "external_side_effects": False,
            }]
        }
        from atlasquant_aion_capabilities import CapabilityRegistry, default_registry
        existing = default_registry().get("research.synthesize")
        modified = existing.as_dict()
        modified["allowed_tools"] = list(existing.allowed_tools) + ["external.research.read"]
        registry = CapabilityRegistry([modified])
        out = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            capability_registry=registry,
            tool_hub=hub,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertIn(
            "NETWORK_UNDERDECLARED:external.research.read",
            out["blockers"],
        )

    def test_unverified_provenance_never_certifies(self):
        out = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            review_approved=True,
        )
        self.assertEqual(out["state"], "TESTED")
        self.assertFalse(out["provenance_verified"])


if __name__ == "__main__":
    unittest.main()
