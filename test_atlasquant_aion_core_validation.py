import ast
import unittest
from copy import deepcopy
from pathlib import Path

from atlasquant_aion_core_validation import (
    BUSINESS_REQUIRED_GATES,
    SCHEMA,
    business_certification_readiness,
    checkpoint_master_validation_gate,
    core_validation_summary,
    production_identity_gate,
    sandbox_checkpoint_restore_drill,
)


SHA = "92978f6b453b4134bf16c754ab525268956f34ab"


class AionCoreValidationTests(unittest.TestCase):
    def test_production_identity_requires_observed_non_local_exact_match(self):
        observed = {
            "commit_sha": SHA,
            "commit_observed": True,
            "environment": "render",
        }
        verified = production_identity_gate(
            SHA,
            observed,
            target_url="https://atlasquant-private.onrender.com",
        )
        self.assertTrue(verified["verified"])
        self.assertTrue(verified["proves_production"])
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertFalse(verified["provider_called"])
        local = production_identity_gate(
            SHA,
            observed,
            target_url="http://127.0.0.1:8501",
        )
        self.assertFalse(local["verified"])
        self.assertTrue(local["target_is_local"])
        mismatch = production_identity_gate(
            "a" * 40,
            observed,
            target_url="https://atlasquant-private.onrender.com",
        )
        self.assertFalse(mismatch["verified"])

    def test_sandbox_restore_is_in_memory_and_digest_bound(self):
        checkpoint = {"schema": "EXAMPLE", "version": 1, "data": {"x": [1, 2, 3]}}
        original = deepcopy(checkpoint)
        first = sandbox_checkpoint_restore_drill(checkpoint)
        self.assertEqual(first["state"], "RESTORED_VERIFIED")
        self.assertTrue(first["passed"])
        self.assertEqual(checkpoint, original)
        self.assertFalse(first["external_write"])
        self.assertFalse(first["runtime_mutated"])
        bound = sandbox_checkpoint_restore_drill(
            checkpoint,
            expected_digest=first["source_digest"],
        )
        self.assertTrue(bound["passed"])
        wrong = sandbox_checkpoint_restore_drill(
            checkpoint,
            expected_digest="0" * 64,
        )
        self.assertFalse(wrong["passed"])
        self.assertEqual(wrong["reason"], "DIGEST_MISMATCH")
        malformed = sandbox_checkpoint_restore_drill(
            checkpoint,
            expected_digest="yes",
        )
        self.assertFalse(malformed["passed"])

    def test_checkpoint_validation_is_fail_closed(self):
        observed = {
            "commit_sha": SHA,
            "commit_observed": True,
            "environment": "render",
        }
        production = production_identity_gate(
            SHA,
            observed,
            target_url="https://atlasquant-private.onrender.com",
        )
        checkpoint = {"schema": "EXAMPLE", "version": 1, "data": {"safe": True}}
        rollback = sandbox_checkpoint_restore_drill(checkpoint)
        evidence = {
            "checkpoint_integrity_verified": True,
            "checkpoint_ref": "checkpoint:master:v18",
            "checkpoint_digest": rollback["source_digest"],
            "production_identity": production,
            "rollback_drill": rollback,
            "human_validation_approved": True,
            "evidence_refs": [
                "docs/aion/ARCHITECTURE.md",
                "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md",
            ],
        }
        validated = checkpoint_master_validation_gate(evidence)
        self.assertEqual(validated["state"], "VALIDADO")
        self.assertTrue(validated["validated"])
        self.assertFalse(validated["persists_checkpoint"])
        self.assertFalse(validated["authorizes_deploy"])
        lookalike = deepcopy(evidence)
        lookalike["human_validation_approved"] = "true"
        blocked = checkpoint_master_validation_gate(lookalike)
        self.assertFalse(blocked["validated"])
        self.assertIn("human_validation_approved", blocked["blockers"])
        no_production = deepcopy(evidence)
        no_production["production_identity"] = {"schema": SCHEMA, "verified": False}
        self.assertFalse(checkpoint_master_validation_gate(no_production)["validated"])

    def test_business_readiness_prepares_review_but_never_certifies_or_activates(self):
        evidence = {name: True for name in BUSINESS_REQUIRED_GATES}
        evidence["evidence_refs"] = [
            "docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md",
            "docs/aion/ARCHITECTURE.md",
        ]
        ready = business_certification_readiness(evidence)
        self.assertTrue(ready["ready_for_certification_review"])
        self.assertEqual(ready["state"], "READY_FOR_CERTIFICATION_REVIEW")
        self.assertEqual(ready["certification_state"], "NOT_CERTIFIED")
        self.assertFalse(ready["runtime_activated"])
        self.assertFalse(ready["payment_executed"])
        self.assertFalse(ready["publication_executed"])
        not_ready = dict(evidence)
        not_ready["demo_sandbox_passed"] = "true"
        blocked = business_certification_readiness(not_ready)
        self.assertFalse(blocked["ready_for_certification_review"])
        self.assertIn("demo_sandbox_passed", blocked["missing"])

    def test_summary_cannot_authorize_sensitive_actions(self):
        summary = core_validation_summary(
            checkpoint={"state": "VALIDADO", "validated": True},
            business={"state": "READY_FOR_CERTIFICATION_REVIEW"},
        )
        self.assertTrue(summary["checkpoint_validated"])
        self.assertEqual(summary["business_certification_state"], "NOT_CERTIFIED")
        self.assertFalse(summary["business_runtime_activated"])
        self.assertFalse(summary["real_trading_enabled"])
        self.assertFalse(summary["payment_enabled"])
        self.assertFalse(summary["publication_enabled"])
        self.assertFalse(summary["merge_authorized"])
        self.assertFalse(summary["deploy_authorized"])

    def test_module_has_no_network_or_process_imports(self):
        source = Path("atlasquant_aion_core_validation.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
