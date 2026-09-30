import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_authorization_record import (
    DECISION_TOKEN,
    REQUIRED_ACKNOWLEDGEMENTS,
    SCHEMA,
    authorization_record_requirements,
    authorization_record_template,
    validate_authorization_record,
    verify_authorization_record_binding,
)
from atlasquant_aion_business_consolidation_decision_request import (
    DECISION_SCOPE,
    SCHEMA as DECISION_REQUEST_SCHEMA,
)


REQUEST_DIGEST = "a" * 64


def _request():
    return {
        "schema": DECISION_REQUEST_SCHEMA,
        "state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED",
        "eligible_for_explicit_human_authorization": True,
        "request_digest": REQUEST_DIGEST,
        "reviewer": "Mikael",
        "decision_scope": DECISION_SCOPE,
        "authorization_recorded": False,
        "merge_authorized": False,
    }


def _record():
    return {
        "schema": SCHEMA,
        "decision": DECISION_TOKEN,
        "request_digest": REQUEST_DIGEST,
        "decision_scope": DECISION_SCOPE,
        "approved_by": "Mikael",
        "approved_at": "2026-09-30T12:30:00Z",
        "acknowledgements": {name: True for name in REQUIRED_ACKNOWLEDGEMENTS},
    }


class BusinessConsolidationAuthorizationRecordTests(unittest.TestCase):
    def test_requirements_do_not_grant_authority(self):
        row = authorization_record_requirements()
        self.assertEqual(row["state"], "AUTHORIZATION_INPUT_REQUIRED")
        self.assertFalse(row["generic_language_is_authorization"])
        self.assertFalse(row["authorization_record_verified"])
        self.assertFalse(row["merge_execution_authorized"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["pilot_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_template_requires_digest_bound_decision_request(self):
        good = authorization_record_template(_request())
        self.assertEqual(good["state"], "AUTHORIZATION_INPUT_REQUIRED")
        self.assertEqual(good["request_digest"], REQUEST_DIGEST)
        self.assertEqual(good["expected_approved_by"], "Mikael")
        bad = authorization_record_template({"state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED"})
        self.assertEqual(bad["state"], "BLOCKED")

    def test_exact_explicit_record_can_be_verified_but_never_executes(self):
        result = validate_authorization_record(_request(), _record())
        self.assertEqual(result["state"], "EXPLICIT_AUTHORIZATION_RECORD_VERIFIED")
        self.assertTrue(result["authorization_record_verified"])
        self.assertEqual(len(result["record_digest"]), 64)
        self.assertFalse(result["merge_execution_authorized"])
        self.assertFalse(result["auto_merge_enabled"])
        self.assertFalse(result["deploy_authorized"])
        self.assertFalse(result["pilot_authorized"])
        self.assertFalse(result["runtime_activation_authorized"])
        self.assertFalse(result["executes_action"])

        binding = verify_authorization_record_binding(_request(), result)
        self.assertEqual(binding["state"], "AUTHORIZATION_BINDING_MATCH")
        self.assertTrue(binding["binding_match"])
        self.assertFalse(binding["merge_execution_authorized"])

    def test_generic_language_is_rejected(self):
        for decision in ("ok", "pode seguir", "vamos lá", "autorizo", "yes", True, 1, None):
            with self.subTest(decision=decision):
                record = _record()
                record["decision"] = decision
                result = validate_authorization_record(_request(), record)
                self.assertEqual(result["state"], "REJECTED")
                self.assertIn("decision_token", result["blockers"])
                self.assertFalse(result["authorization_record_verified"])

    def test_request_digest_replay_and_wrong_reviewer_are_rejected(self):
        record = _record()
        record["request_digest"] = "b" * 64
        record["approved_by"] = "Outro"
        result = validate_authorization_record(_request(), record)
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("request_digest", result["blockers"])
        self.assertIn("approved_by", result["blockers"])

    def test_missing_acknowledgement_fails_closed(self):
        record = _record()
        record["acknowledgements"]["runtime_remains_off"] = False
        result = validate_authorization_record(_request(), record)
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("acknowledgements", result["blockers"])
        self.assertIn("runtime_remains_off", result["missing_acknowledgements"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_authorization_record.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "github"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
