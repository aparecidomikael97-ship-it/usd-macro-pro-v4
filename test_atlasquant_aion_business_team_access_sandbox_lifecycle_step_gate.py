import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_sandbox_lifecycle_authorization import (
    SCHEMA as AUTH_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
    build_evidence_receipt,
    build_lifecycle_evidence_ledger,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_plan import (
    LIFECYCLE_STEP_IDS,
    SCHEMA as PLAN_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_step_gate import (
    build_step_execution_preflight,
    review_post_step_receipt,
    step_gate_policy,
)


def _plan():
    mutation_steps = {1, 2, 4, 6, 7, 8}
    steps = []
    for index, step_id in enumerate(LIFECYCLE_STEP_IDS, start=1):
        steps.append({
            "order": index,
            "id": step_id,
            "mutation": index in mutation_steps,
            "requires_manual_apply": True,
            "evidence_required": ["proof"],
        })
    return {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_EXECUTION_DECISION",
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "requested_by": "admin.demo",
        "steps": steps,
        "executes_action": False,
    }


def _auth():
    return {
        "schema": AUTH_SCHEMA,
        "state": "EXPLICIT_SANDBOX_LIFECYCLE_AUTHORIZATION_RECORD_VERIFIED",
        "authorization_record_verified": True,
        "sandbox_lifecycle_manual_execution_authorized": True,
        "automatic_execution_authorized": False,
        "plan_digest": "a" * 64,
        "baseline_evidence_digest": "b" * 64,
        "record_digest": "c" * 64,
        "approved_by": "admin.demo",
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


def _ledger():
    return build_lifecycle_evidence_ledger(_plan(), _auth(), [])


class TeamAccessSandboxLifecycleStepGateTests(unittest.TestCase):
    def test_policy_is_one_step_non_executing(self):
        policy = step_gate_policy()
        self.assertTrue(policy["one_step_at_a_time"])
        self.assertTrue(policy["explicit_step_decision_required"])
        self.assertFalse(policy["automatic_step_execution"])
        self.assertFalse(policy["automatic_ledger_append"])
        self.assertFalse(policy["executes_action"])

    def test_first_step_preflight_reaches_explicit_step_decision_only(self):
        result = build_step_execution_preflight(
            _plan(),
            _auth(),
            _ledger(),
            target_step_order=1,
            baseline_evidence_digest_observed="b" * 64,
            sandbox_health_verified=True,
            oidc_verified=True,
            registry_schema_verified=True,
            secrets_local=True,
            production_targets_absent=True,
            cleanup_path_ready=True,
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_EXPLICIT_MANUAL_SANDBOX_STEP_DECISION",
        )
        self.assertEqual(result["target_step_order"], 1)
        self.assertEqual(result["target_step_id"], LIFECYCLE_STEP_IDS[0])
        self.assertTrue(result["preflight_digest"])
        self.assertTrue(result["required_step_decision_token"].startswith(
            "AUTHORIZE_SANDBOX_LIFECYCLE_STEP_1_"
        ))
        self.assertFalse(result["step_execution_authorized"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_drift_or_wrong_step_blocks(self):
        result = build_step_execution_preflight(
            _plan(),
            _auth(),
            _ledger(),
            target_step_order=2,
            baseline_evidence_digest_observed="d" * 64,
            sandbox_health_verified=True,
            oidc_verified=True,
            registry_schema_verified=True,
            secrets_local=True,
            production_targets_absent=True,
            cleanup_path_ready=True,
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"], "SANDBOX_LIFECYCLE_STEP_PREFLIGHT_BLOCKED"
        )
        self.assertIn("target_is_next_step", result["blockers"])
        self.assertIn("baseline_digest_unchanged", result["blockers"])

    def test_ledger_from_different_plan_is_rejected(self):
        ledger = _ledger()
        ledger["plan_digest"] = "d" * 64
        result = build_step_execution_preflight(
            _plan(),
            _auth(),
            ledger,
            target_step_order=1,
            baseline_evidence_digest_observed="b" * 64,
            sandbox_health_verified=True,
            oidc_verified=True,
            registry_schema_verified=True,
            secrets_local=True,
            production_targets_absent=True,
            cleanup_path_ready=True,
            requested_by="admin.demo",
        )
        self.assertEqual(
            result["state"], "SANDBOX_LIFECYCLE_STEP_PREFLIGHT_BLOCKED"
        )
        self.assertIn("ledger_ready_for_next", result["blockers"])

    def test_valid_receipt_can_reach_manual_append_review_only(self):
        ledger = _ledger()
        receipt = build_evidence_receipt(
            _plan(),
            _auth(),
            step_order=1,
            step_id=LIFECYCLE_STEP_IDS[0],
            evidence_digest="d" * 64,
            observed_at="2026-09-30T21:30:00+00:00",
            previous_entry_digest=GENESIS_DIGEST,
            mutation_observed=True,
            sandbox_only=True,
            production_targeted=False,
            secret_material_included=False,
        )
        review = review_post_step_receipt(
            _plan(), _auth(), ledger, receipt
        )
        self.assertEqual(
            review["state"], "READY_FOR_MANUAL_LEDGER_APPEND_REVIEW"
        )
        self.assertTrue(review["review_digest"])
        self.assertFalse(review["ledger_append_authorized"])
        self.assertFalse(review["automatic_next_step_authorized"])
        self.assertFalse(review["executes_action"])

    def test_tampered_receipt_blocks_post_step_review(self):
        ledger = _ledger()
        receipt = build_evidence_receipt(
            _plan(),
            _auth(),
            step_order=1,
            step_id=LIFECYCLE_STEP_IDS[0],
            evidence_digest="d" * 64,
            observed_at="2026-09-30T21:30:00+00:00",
            previous_entry_digest=GENESIS_DIGEST,
            mutation_observed=True,
            sandbox_only=True,
            production_targeted=False,
            secret_material_included=False,
        )
        receipt["receipt_digest"] = "e" * 64
        review = review_post_step_receipt(
            _plan(), _auth(), ledger, receipt
        )
        self.assertEqual(
            review["state"], "POST_STEP_RECEIPT_REVIEW_BLOCKED"
        )
        self.assertIn("receipt_integrity_verified", review["blockers"])

    def test_module_has_no_network_process_or_provider_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_sandbox_lifecycle_step_gate.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(
            imported.intersection(
                {"requests", "httpx", "socket", "subprocess", "docker"}
            )
        )


if __name__ == "__main__":
    unittest.main()
