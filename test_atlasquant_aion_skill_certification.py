from __future__ import annotations

import unittest

from atlasquant_aion_capabilities import CapabilityRegistry
from atlasquant_aion_skill_certification import assess_skill_manifest, transition_skill_certification


TRUSTED = {"tenant_id": "tenant-a", "workspace_id": "central", "role": "ADMIN"}


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
        self.assertTrue(out["record_fingerprint"])
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

    def test_unverified_provenance_never_certifies(self):
        out = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            review_approved=True,
        )
        self.assertEqual(out["state"], "TESTED")
        self.assertFalse(out["provenance_verified"])


    def test_tool_workspace_must_be_inside_manifest_scope(self):
        raw = self.safe_manifest()
        hub = {
            "tools": [{
                "tool_id": "aion.memory.search",
                "label": "Memory",
                "workspace_id": "development",
                "connector_id": "",
                "kind": "SEARCH",
                "guardian_action": "search",
                "state": "LOCAL_READY",
                "required_scopes": ["memory:read"],
                "external_side_effects": False,
            }]
        }
        out = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            tool_hub=hub,
        )
        self.assertIn(
            "TOOL_WORKSPACE_OUT_OF_SCOPE:aion.memory.search",
            out["blockers"],
        )

    def test_connector_tool_requires_network_declaration(self):
        registry = CapabilityRegistry([{
            "capability_id": "research.external",
            "specialist": "research",
            "domains": ["research"],
            "description": "External research through an approved tool.",
            "inputs": ["query"],
            "outputs": ["evidence"],
            "risk": "LOW",
            "allowed_tools": ["research.external.search"],
            "allowed_roles": ["ADMIN"],
        }])
        raw = self.safe_manifest()
        raw["capability_ids"] = ["research.external"]
        raw["tool_ids"] = ["research.external.search"]
        raw["required_scopes"] = ["research:read"]
        hub = {
            "tools": [{
                "tool_id": "research.external.search",
                "label": "External research",
                "workspace_id": "central",
                "connector_id": "research-api",
                "kind": "SEARCH",
                "guardian_action": "search",
                "state": "CONFIGURED",
                "required_scopes": ["research:read"],
                "external_side_effects": False,
            }]
        }
        blocked = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            capability_registry=registry,
            tool_hub=hub,
        )
        self.assertIn(
            "NETWORK_UNDERDECLARED:research.external.search",
            blocked["blockers"],
        )
        raw["network_required"] = True
        allowed = assess_skill_manifest(
            raw,
            trusted_context=TRUSTED,
            capability_registry=registry,
            tool_hub=hub,
        )
        self.assertNotIn(
            "NETWORK_UNDERDECLARED:research.external.search",
            allowed["blockers"],
        )
        self.assertFalse(allowed["activates_connector"])
        self.assertFalse(allowed["executes_tool"])

    def test_certified_record_can_be_suspended_without_activation(self):
        certified = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        out = transition_skill_certification(
            certified,
            action="SUSPEND",
            trusted_context=TRUSTED,
            approved=True,
            reason="Incident review pending.",
        )
        self.assertEqual(out["state"], "SUSPENDED")
        self.assertTrue(out["transition_applied"])
        self.assertFalse(out["activates_skill"])
        self.assertFalse(out["activates_connector"])
        self.assertFalse(out["executes_tool"])

    def test_suspended_record_can_be_revoked_and_is_terminal(self):
        certified = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
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
        self.assertEqual(revoked["state"], "REVOKED")
        self.assertTrue(revoked["terminal"])
        self.assertTrue(revoked["transition_applied"])
        self.assertFalse(revoked["activates_skill"])

    def test_lifecycle_transition_requires_exact_admin_approval(self):
        certified = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        string_approval = transition_skill_certification(
            certified,
            action="SUSPEND",
            trusted_context=TRUSTED,
            approved="true",
            reason="Review.",
        )
        self.assertEqual(string_approval["state"], "CERTIFIED")
        self.assertIn("EXPLICIT_APPROVAL_REQUIRED", string_approval["blockers"])
        non_admin = transition_skill_certification(
            certified,
            action="SUSPEND",
            trusted_context={
                "tenant_id": "tenant-a",
                "workspace_id": "central",
                "role": "USER",
            },
            approved=True,
            reason="Review.",
        )
        self.assertIn("ADMIN_REQUIRED", non_admin["blockers"])
        self.assertFalse(non_admin["transition_applied"])

    def test_tampered_certification_state_is_detected_by_record_fingerprint(self):
        tested = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=False,
        )
        self.assertEqual(tested["state"], "TESTED")
        tested["state"] = "CERTIFIED"
        out = transition_skill_certification(
            tested,
            action="SUSPEND",
            trusted_context=TRUSTED,
            approved=True,
            reason="Forged state.",
        )
        self.assertIn(
            "CERTIFICATION_RECORD_FINGERPRINT_MISMATCH",
            out["blockers"],
        )
        self.assertFalse(out["transition_applied"])

    def test_certification_transition_is_bound_to_original_tenant_and_workspace(self):
        certified = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        self.assertEqual(certified["manifest"]["bound_tenant_id"], "tenant-a")
        self.assertEqual(certified["manifest"]["bound_workspace_id"], "central")
        crossed = transition_skill_certification(
            certified,
            action="SUSPEND",
            trusted_context={
                "tenant_id": "tenant-b",
                "workspace_id": "central",
                "role": "ADMIN",
            },
            approved=True,
            reason="Cross-tenant attempt.",
        )
        self.assertEqual(crossed["state"], "CERTIFIED")
        self.assertIn("TRUSTED_SCOPE_MISMATCH", crossed["blockers"])
        self.assertFalse(crossed["transition_applied"])

    def test_tampered_certification_record_cannot_transition(self):
        certified = assess_skill_manifest(
            self.safe_manifest(),
            trusted_context=TRUSTED,
            test_evidence={"state": "PASS", "passed": True},
            provenance_verifier=verified,
            review_approved=True,
        )
        certified["manifest"]["risk"] = "CRITICAL"
        out = transition_skill_certification(
            certified,
            action="REVOKE",
            trusted_context=TRUSTED,
            approved=True,
            reason="Tampered record.",
        )
        self.assertEqual(out["state"], "CERTIFIED")
        self.assertIn("CERTIFICATION_FINGERPRINT_MISMATCH", out["blockers"])
        self.assertFalse(out["transition_applied"])


if __name__ == "__main__":
    unittest.main()
