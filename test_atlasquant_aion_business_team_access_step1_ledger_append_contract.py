import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from atlasquant_aion_business_team_access_sandbox_lifecycle_evidence_ledger import (
    GENESIS_DIGEST,
)
from atlasquant_aion_business_team_access_step1_ledger_append_contract import (
    REQUIRED_ACKNOWLEDGEMENTS,
    build_ledger_append_decision_request,
    ledger_append_contract_policy,
    validate_ledger_append_decision,
)


def _packet():
    return {
        "observation_observed_by": "admin.demo",
        "ledger": {
            "state": "READY_FOR_FIRST_SANDBOX_LIFECYCLE_STEP",
            "ledger_digest": "a" * 64,
            "completed_count": 0,
            "entries": [],
            "chain_head_digest": GENESIS_DIGEST,
            "next_expected_step_order": 1,
            "next_expected_step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
        },
    }


def _review():
    return {
        "receipt_review_digest": "b" * 64,
        "canonical_lifecycle_receipt": {
            "state": "SANDBOX_LIFECYCLE_STEP_EVIDENCE_RECEIPT_READY",
            "receipt_digest": "c" * 64,
            "step_order": 1,
            "step_id": "CREATE_INDIVIDUAL_SANDBOX_ACCOUNT",
            "previous_entry_digest": GENESIS_DIGEST,
            "mutation_observed": True,
            "sandbox_only": True,
            "production_targeted": False,
            "secret_material_included": False,
        },
        "ledger_preview": {
            "state": "READY_FOR_NEXT_SANDBOX_LIFECYCLE_STEP",
            "ledger_digest": "d" * 64,
            "completed_count": 1,
            "next_expected_step_order": 2,
            "next_expected_step_id": "ENROLL_STRONG_AUTH",
            "automatic_next_step_authorized": False,
            "executor_enabled": False,
            "production_authorized": False,
            "executes_action": False,
        },
        "ledger_append_authorized": False,
        "ledger_append_performed": False,
        "automatic_ledger_append": False,
        "step2_execution_authorized": False,
    }


class Step1LedgerAppendContractTests(unittest.TestCase):
    def setUp(self):
        self.p1 = patch(
            "atlasquant_aion_business_team_access_step1_ledger_append_contract."
            "verify_step1_preflight_package",
            return_value={"binding_match": True},
        )
        self.p2 = patch(
            "atlasquant_aion_business_team_access_step1_ledger_append_contract."
            "verify_provider_receipt_review",
            return_value={"binding_match": True},
        )
        self.p1.start()
        self.p2.start()

    def tearDown(self):
        self.p2.stop()
        self.p1.stop()

    def test_policy_keeps_append_and_step2_separate(self):
        policy = ledger_append_contract_policy()
        self.assertTrue(policy["exact_token_required"])
        self.assertFalse(policy["generic_language_is_authorization"])
        self.assertFalse(policy["ledger_append_authorized"])
        self.assertFalse(policy["ledger_append_performed"])
        self.assertFalse(policy["step2_execution_authorized"])
        self.assertFalse(policy["production_authorized"])

    def test_valid_sources_build_exact_append_decision_request(self):
        request = build_ledger_append_decision_request(
            _packet(), _review()
        )
        self.assertEqual(
            request["state"],
            "READY_FOR_EXPLICIT_STEP1_LEDGER_APPEND_DECISION",
        )
        self.assertTrue(all(request["gates"].values()))
        self.assertTrue(request["decision_request_digest"])
        self.assertTrue(
            request["required_decision_token"].startswith(
                "APPEND_SANDBOX_STEP1_LEDGER_"
            )
        )
        self.assertFalse(request["ledger_append_authorized"])
        self.assertFalse(request["step2_execution_authorized"])

    def test_exact_record_verifies_append_only(self):
        request = build_ledger_append_decision_request(
            _packet(), _review()
        )
        record = {
            "decision": request["required_decision_token"],
            "receipt_review_digest": request[
                "receipt_review_digest"
            ],
            "canonical_receipt_digest": request[
                "canonical_receipt_digest"
            ],
            "source_ledger_digest": request["source_ledger_digest"],
            "target_ledger_digest": request["target_ledger_digest"],
            "decided_by": "admin.demo",
            "decided_at": "2026-09-30T23:00:00+00:00",
            "sandbox_only": True,
            "production_targeted": False,
            "automatic_ledger_append_requested": False,
            "step2_execution_requested": False,
            "secret_material_included": False,
            "acknowledgements": {
                name: True for name in REQUIRED_ACKNOWLEDGEMENTS
            },
        }
        result = validate_ledger_append_decision(request, record)
        self.assertEqual(
            result["state"],
            "EXPLICIT_STEP1_LEDGER_APPEND_DECISION_VERIFIED",
        )
        self.assertTrue(result["ledger_append_decision_verified"])
        self.assertTrue(result["ledger_append_authorized"])
        self.assertFalse(result["ledger_append_performed"])
        self.assertFalse(result["automatic_ledger_append"])
        self.assertFalse(result["step2_execution_authorized"])
        self.assertFalse(result["production_authorized"])

    def test_generic_language_or_digest_drift_rejects(self):
        request = build_ledger_append_decision_request(
            _packet(), _review()
        )
        record = {
            "decision": "vamos lá",
            "receipt_review_digest": "f" * 64,
            "canonical_receipt_digest": request[
                "canonical_receipt_digest"
            ],
            "source_ledger_digest": request["source_ledger_digest"],
            "target_ledger_digest": request["target_ledger_digest"],
            "decided_by": "admin.demo",
            "decided_at": "2026-09-30T23:00:00+00:00",
            "sandbox_only": True,
            "production_targeted": False,
            "automatic_ledger_append_requested": False,
            "step2_execution_requested": False,
            "secret_material_included": False,
            "acknowledgements": {
                name: True for name in REQUIRED_ACKNOWLEDGEMENTS
            },
        }
        result = validate_ledger_append_decision(request, record)
        self.assertEqual(
            result["state"], "STEP1_LEDGER_APPEND_DECISION_REJECTED"
        )
        self.assertIn("decision_token_exact", result["blockers"])
        self.assertIn("receipt_review_digest_exact", result["blockers"])
        self.assertFalse(result["ledger_append_authorized"])

    def test_non_genesis_source_or_bad_target_blocks_request(self):
        packet = _packet()
        packet["ledger"]["completed_count"] = 1
        request = build_ledger_append_decision_request(
            packet, _review()
        )
        self.assertIn(
            "source_ledger_exact_genesis", request["blockers"]
        )

        review = _review()
        review["ledger_preview"]["next_expected_step_order"] = 3
        request = build_ledger_append_decision_request(
            _packet(), review
        )
        self.assertIn(
            "target_ledger_exact_step1_only", request["blockers"]
        )

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_step1_ledger_append_contract.py"
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
