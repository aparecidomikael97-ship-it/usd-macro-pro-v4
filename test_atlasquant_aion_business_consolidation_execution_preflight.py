import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_execution_preflight import (
    build_merge_execution_preflight,
    execution_preflight_template,
)
from atlasquant_aion_business_consolidation_dry_run_v2 import SCHEMA as DRY_RUN_SCHEMA
from atlasquant_aion_business_consolidation_decision_request import (
    SCHEMA as DECISION_REQUEST_SCHEMA,
)
from atlasquant_aion_business_consolidation_authorization_record import (
    SCHEMA as AUTHORIZATION_RECORD_SCHEMA,
)


REQUEST_DIGEST = "a" * 64
RECORD_DIGEST = "b" * 64
MAIN_SHA = "c" * 40


def _runbook():
    return {
        "schema": DRY_RUN_SCHEMA,
        "state": "READY_FOR_EXPLICIT_ADMIN_DECISION",
        "requires_explicit_admin_decision": True,
        "merge_authorized": False,
    }


def _request():
    return {
        "schema": DECISION_REQUEST_SCHEMA,
        "state": "HUMAN_AUTHORIZATION_RECORD_REQUIRED",
        "eligible_for_explicit_human_authorization": True,
        "request_digest": REQUEST_DIGEST,
        "merge_authorized": False,
    }


def _authorization():
    return {
        "schema": AUTHORIZATION_RECORD_SCHEMA,
        "state": "EXPLICIT_AUTHORIZATION_RECORD_VERIFIED",
        "authorization_record_verified": True,
        "request_digest": REQUEST_DIGEST,
        "record_digest": RECORD_DIGEST,
        "merge_execution_authorized": False,
    }


def _live():
    return {
        "schema": DRY_RUN_SCHEMA,
        "state": "LIVE_REVALIDATED",
        "complete": True,
        "merge_authorized": False,
    }


class BusinessConsolidationExecutionPreflightTests(unittest.TestCase):
    def test_template_never_executes(self):
        row = execution_preflight_template()
        self.assertEqual(row["state"], "EVIDENCE_REQUIRED")
        self.assertFalse(row["merge_execution_authorized"])
        self.assertFalse(row["auto_merge_enabled"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["pilot_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_first_step_can_reach_review_only(self):
        row = build_merge_execution_preflight(
            _runbook(),
            _request(),
            _authorization(),
            _live(),
            target_pr=394,
            completed_prs=[],
            observed_main_sha=MAIN_SHA,
            expected_main_sha=MAIN_SHA,
            business_runtime_off=True,
            deploy_authority_absent=True,
        )
        self.assertEqual(row["state"], "MERGE_EXECUTION_REVIEW_REQUIRED")
        self.assertTrue(row["ready_for_separate_execution_review"])
        self.assertEqual(row["next_expected_pr"], 394)
        self.assertEqual(row["target_pr"], 394)
        self.assertEqual(row["rollback_reference_sha"], MAIN_SHA)
        self.assertFalse(row["merge_execution_authorized"])
        self.assertFalse(row["executes_action"])

    def test_sequence_must_be_exact_prefix(self):
        row = build_merge_execution_preflight(
            _runbook(), _request(), _authorization(), _live(),
            target_pr=396,
            completed_prs=[394, 396],
            observed_main_sha=MAIN_SHA,
            expected_main_sha=MAIN_SHA,
            business_runtime_off=True,
            deploy_authority_absent=True,
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("stack_prefix_valid", row["blockers"])
        self.assertIn("target_is_next_pr", row["blockers"])

    def test_cannot_skip_next_pr(self):
        row = build_merge_execution_preflight(
            _runbook(), _request(), _authorization(), _live(),
            target_pr=396,
            completed_prs=[394],
            observed_main_sha=MAIN_SHA,
            expected_main_sha=MAIN_SHA,
            business_runtime_off=True,
            deploy_authority_absent=True,
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertEqual(row["next_expected_pr"], 395)
        self.assertIn("target_is_next_pr", row["blockers"])

    def test_main_sha_runtime_or_deploy_drift_blocks(self):
        row = build_merge_execution_preflight(
            _runbook(), _request(), _authorization(), _live(),
            target_pr=394,
            completed_prs=[],
            observed_main_sha="d" * 40,
            expected_main_sha=MAIN_SHA,
            business_runtime_off="true",
            deploy_authority_absent=False,
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("main_sha_matches_expected", row["blockers"])
        self.assertIn("business_runtime_off", row["blockers"])
        self.assertIn("deploy_authority_absent", row["blockers"])

    def test_authorization_must_bind_same_request_digest(self):
        auth = _authorization()
        auth["request_digest"] = "e" * 64
        row = build_merge_execution_preflight(
            _runbook(), _request(), auth, _live(),
            target_pr=394,
            completed_prs=[],
            observed_main_sha=MAIN_SHA,
            expected_main_sha=MAIN_SHA,
            business_runtime_off=True,
            deploy_authority_absent=True,
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertIn("explicit_authorization_record_verified", row["blockers"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_execution_preflight.py").read_text(encoding="utf-8")
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
