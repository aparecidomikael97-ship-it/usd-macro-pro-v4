import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_business_team_access_step1_provider_receipt_review import (
    PROVIDER_RECEIPT_SCHEMA,
    provider_receipt_review_policy,
    validate_provider_receipt_and_preview_ledger,
    verify_provider_receipt_review,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
)
from atlasquant_aion_business_team_access_sandbox_lifecycle_materialization import (
    SCHEMA as MATERIALIZATION_SCHEMA,
)


def _materialization():
    return {
        "schema": MATERIALIZATION_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_PLAN_REVIEW",
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "d" * 64,
        "materialization_digest": "3" * 64,
        "plan": {
            "plan_digest": "b" * 64,
            "baseline_evidence_digest": "d" * 64,
        },
    }


def _auth():
    return {
        "record_digest": "1" * 64,
        "authorization_package_digest": "2" * 64,
        "materialization_digest": "3" * 64,
    }


def _packet():
    return {
        "ledger": {
            "state": "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "completed_count": 0,
            "entries": [],
            "chain_head_digest": GENESIS_DIGEST,
            "next_expected_step_order": 1,
            "next_expected_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        }
    }


def _envelope():
    return {
        "execution_envelope_digest": "e" * 64,
        "materialization_digest": "3" * 64,
        "plan_digest": "b" * 64,
    }


def _apply_plan():
    return {
        "apply_plan_digest": "a" * 64,
        "plan_digest": "b" * 64,
        "target_username": "sandbox.operador.demo",
    }


def _runner():
    return {
        "state": "READY_FOR_EXPLICIT_MANUAL_STEP1_PROVIDER_APPLY",
        "apply_requested": True,
        "physical_apply_authorized": True,
        "runner_preflight_digest": "f" * 64,
        "evaluated_at": "2026-09-30T22:40:00+00:00",
    }


def _receipt():
    return {
        "schema": PROVIDER_RECEIPT_SCHEMA,
        "version": "1",
        "state": "STEP1_PROVIDER_APPLY_EXECUTED_PENDING_LEDGER_REVIEW",
        "apply_plan_digest": "a" * 64,
        "runner_preflight_digest": "f" * 64,
        "execution_envelope_digest": "e" * 64,
        "operator_session_id": "c" * 32,
        "baseline_evidence_digest": "d" * 64,
        "target_step_order": 1,
        "target_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        "target_username": "sandbox.operador.demo",
        "provider": "KEYCLOAK",
        "realm": "atlasquant-sandbox",
        "provider_user_id": "11111111-2222-3333-4444-555555555555",
        "http_status": 201,
        "exact_readback_verified": True,
        "executed_at": "2026-09-30T22:41:00+00:00",
        "secret_material_included": False,
        "access_token_included": False,
        "authorization_token_included": False,
        "ledger_append_authorized": False,
        "automatic_ledger_append": False,
        "production_targeted": False,
    }


def _canonical_receipt():
    return {
        "state": "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY",
        "receipt_digest": "9" * 64,
        "step_order": 1,
        "step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
    }


def _ledger_preview():
    return {
        "state": "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP",
        "completed_count": 1,
        "next_expected_step_order": 2,
        "next_expected_step_id": "ENROLL_STRONG_AUTH",
        "ledger_digest": "8" * 64,
        "automatic_next_step_authorized": False,
        "executor_enabled": False,
        "production_authorized": False,
        "executes_action": False,
    }


class TeamAccessStep1ProviderReceiptReviewTests(unittest.TestCase):
    def setUp(self):
        targets = [
            "verify_materialized_authorization_binding",
            "verify_step1_preflight_package",
            "verify_step1_execution_envelope",
            "verify_step1_apply_plan",
            "verify_step1_apply_plan_source_binding",
            "verify_provider_runner_preflight",
        ]
        self.patchers = [
            patch(
                "atlasquant_aion_business_team_access_step1_provider_receipt_review."
                + target,
                return_value={"binding_match": True},
            )
            for target in targets
        ]
        self.patchers += [
            patch(
                "atlasquant_aion_business_team_access_step1_provider_receipt_review."
                "build_evidence_receipt",
                return_value=_canonical_receipt(),
            ),
            patch(
                "atlasquant_aion_business_team_access_step1_provider_receipt_review."
                "build_lifecycle_evidence_ledger",
                return_value=_ledger_preview(),
            ),
        ]
        for item in self.patchers:
            item.start()

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()

    def _run(self, receipt=None, packet=None):
        return validate_provider_receipt_and_preview_ledger(
            _materialization(),
            _auth(),
            packet or _packet(),
            _envelope(),
            _apply_plan(),
            _runner(),
            receipt or _receipt(),
        )

    def test_policy_keeps_ledger_append_separate(self):
        policy = provider_receipt_review_policy()
        self.assertTrue(policy["provider_receipt_required"])
        self.assertTrue(policy["canonical_lifecycle_receipt_required"])
        self.assertTrue(policy["ledger_preview_only"])
        self.assertFalse(policy["ledger_append_authorized"])
        self.assertFalse(policy["ledger_append_performed"])
        self.assertFalse(policy["step2_execution_authorized"])
        self.assertFalse(policy["automatic_ledger_append"])
        self.assertFalse(policy["production_authorized"])

    def test_valid_receipt_reaches_ledger_append_review_only(self):
        result = self._run()
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_STEP1_LEDGER_APPEND_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["provider_evidence_digest"])
        self.assertTrue(result["receipt_review_digest"])
        self.assertEqual(
            result["canonical_lifecycle_receipt"]["receipt_digest"],
            "9" * 64,
        )
        self.assertEqual(
            result["ledger_preview"]["completed_count"], 1
        )
        self.assertEqual(
            result["ledger_preview"]["next_expected_step_order"], 2
        )
        self.assertFalse(result["ledger_append_authorized"])
        self.assertFalse(result["ledger_append_performed"])
        self.assertFalse(result["step2_execution_authorized"])
        self.assertFalse(result["automatic_ledger_append"])
        self.assertFalse(result["executor_enabled"])
        self.assertFalse(result["production_authorized"])

    def test_materialization_or_plan_drift_blocks(self):
        materialization = _materialization()
        materialization["materialization_digest"] = "6" * 64
        result = validate_provider_receipt_and_preview_ledger(
            materialization,
            _auth(),
            _packet(),
            _envelope(),
            _apply_plan(),
            _runner(),
            _receipt(),
        )
        self.assertIn(
            "materialization_digest_matches_authorization",
            result["blockers"],
        )

        apply_plan = _apply_plan()
        apply_plan["plan_digest"] = "7" * 64
        result = validate_provider_receipt_and_preview_ledger(
            _materialization(),
            _auth(),
            _packet(),
            _envelope(),
            apply_plan,
            _runner(),
            _receipt(),
        )
        self.assertIn("plan_digest_matches_apply_plan", result["blockers"])

    def test_ready_review_has_recomputable_integrity(self):
        result = self._run()
        binding = verify_provider_receipt_review(result)
        self.assertTrue(binding["binding_match"])
        self.assertEqual(
            binding["state"],
            "STEP1_PROVIDER_RECEIPT_REVIEW_BINDING_MATCH",
        )
        self.assertEqual(
            binding["receipt_review_digest"],
            result["receipt_review_digest"],
        )

        result["provider_user_id"] = "tampered-user"
        binding = verify_provider_receipt_review(result)
        self.assertFalse(binding["binding_match"])
        self.assertIn("review_digest_integrity", binding["blockers"])

    def test_receipt_digest_binding_drift_blocks(self):
        receipt = _receipt()
        receipt["runner_preflight_digest"] = "7" * 64
        result = self._run(receipt=receipt)
        self.assertEqual(
            result["state"],
            "TEAM_ACCESS_STEP1_PROVIDER_RECEIPT_REVIEW_BLOCKED",
        )
        self.assertIn(
            "runner_preflight_digest_matches", result["blockers"]
        )
        self.assertEqual(result["receipt_review_digest"], "")

    def test_execution_too_far_after_runner_preflight_blocks(self):
        receipt = _receipt()
        receipt["executed_at"] = "2026-09-30T22:43:01+00:00"
        result = self._run(receipt=receipt)
        self.assertIn(
            "execution_near_runner_preflight", result["blockers"]
        )

    def test_non_empty_source_ledger_blocks_duplicate_append_path(self):
        packet = _packet()
        packet["ledger"]["completed_count"] = 1
        packet["ledger"]["entries"] = [{"step_order": 1}]
        result = self._run(packet=packet)
        self.assertIn("source_ledger_was_empty", result["blockers"])

    def test_secret_or_token_material_in_receipt_blocks(self):
        receipt = _receipt()
        receipt["secret_material_included"] = True
        receipt["access_token_included"] = True
        result = self._run(receipt=receipt)
        self.assertIn("secret_material_absent", result["blockers"])
        self.assertIn("access_token_absent", result["blockers"])

    def test_ledger_preview_must_land_exactly_on_step2(self):
        with patch(
            "atlasquant_aion_business_team_access_step1_provider_receipt_review."
            "build_lifecycle_evidence_ledger",
            return_value={
                **_ledger_preview(),
                "completed_count": 2,
                "next_expected_step_order": 3,
            },
        ):
            result = self._run()
        self.assertIn("ledger_preview", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_provider_receipt_review.py"
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
