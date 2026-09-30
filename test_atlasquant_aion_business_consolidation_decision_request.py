import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_consolidation_decision_request import (
    DECISION_SCOPE,
    EXPECTED_REPOSITORY,
    build_decision_request,
    decision_request_template,
    verify_decision_binding,
)
from atlasquant_aion_business_consolidation_dry_run_v2 import SCHEMA as DRY_RUN_SCHEMA


CANDIDATE = "e28168cf3010451dea2c84b7fdf2f2b901b1bcf8"
BASE = "c9f82294e1e0fb39304a584d6b42403271443b87"
BUNDLE = "a" * 64
LIVE_REF = "github-actions:full-stack-live-revalidation:example"


def _runbook():
    return {
        "schema": DRY_RUN_SCHEMA,
        "state": "READY_FOR_EXPLICIT_ADMIN_DECISION",
        "requires_explicit_admin_decision": True,
        "merge_authorized": False,
    }


def _bundle():
    return {
        "state": "BUNDLE_FROZEN_FOR_REVIEW",
        "bundle_digest": BUNDLE,
    }


class BusinessConsolidationDecisionRequestTests(unittest.TestCase):
    def test_template_has_no_authority(self):
        row = decision_request_template()
        self.assertEqual(row["state"], "INPUT_REQUIRED")
        self.assertFalse(row["authorization_recorded"])
        self.assertFalse(row["merge_authorized"])
        self.assertFalse(row["deploy_authorized"])
        self.assertFalse(row["pilot_authorized"])
        self.assertFalse(row["runtime_activation_authorized"])
        self.assertFalse(row["executes_action"])

    def test_ready_runbook_builds_digest_bound_request_not_authority(self):
        request = build_decision_request(
            _runbook(),
            _bundle(),
            repository=EXPECTED_REPOSITORY,
            candidate_sha=CANDIDATE,
            base_sha=BASE,
            live_evidence_ref=LIVE_REF,
            reviewer="Mikael",
            decision_scope=DECISION_SCOPE,
        )
        self.assertEqual(request["state"], "HUMAN_AUTHORIZATION_RECORD_REQUIRED")
        self.assertTrue(request["eligible_for_explicit_human_authorization"])
        self.assertEqual(len(request["request_digest"]), 64)
        self.assertTrue(request["invalidated_by_any_binding_drift"])
        self.assertFalse(request["authorization_recorded"])
        self.assertFalse(request["merge_authorized"])
        self.assertFalse(request["executes_action"])

    def test_generic_or_incomplete_request_fails_closed(self):
        request = build_decision_request(
            {"state": "READY_FOR_EXPLICIT_ADMIN_DECISION"},
            _bundle(),
            repository=EXPECTED_REPOSITORY,
            candidate_sha=CANDIDATE,
            base_sha=BASE,
            live_evidence_ref="",
            reviewer="",
            decision_scope="MERGE_ANYTHING",
        )
        self.assertEqual(request["state"], "BLOCKED")
        self.assertFalse(request["eligible_for_explicit_human_authorization"])
        self.assertIn("dry_run_schema", request["blockers"])
        self.assertIn("live_evidence_ref", request["blockers"])
        self.assertIn("reviewer", request["blockers"])
        self.assertIn("decision_scope", request["blockers"])

    def test_candidate_or_bundle_drift_invalidates_binding(self):
        request = build_decision_request(
            _runbook(),
            _bundle(),
            repository=EXPECTED_REPOSITORY,
            candidate_sha=CANDIDATE,
            base_sha=BASE,
            live_evidence_ref=LIVE_REF,
            reviewer="Mikael",
        )
        ok = verify_decision_binding(
            request,
            repository=EXPECTED_REPOSITORY,
            candidate_sha=CANDIDATE,
            base_sha=BASE,
            bundle_digest=BUNDLE,
            live_evidence_ref=LIVE_REF,
        )
        self.assertEqual(ok["state"], "BINDING_MATCH")
        self.assertFalse(ok["merge_authorized"])

        drift = verify_decision_binding(
            request,
            repository=EXPECTED_REPOSITORY,
            candidate_sha="f" * 40,
            base_sha=BASE,
            bundle_digest="b" * 64,
            live_evidence_ref=LIVE_REF,
        )
        self.assertEqual(drift["state"], "BINDING_MISMATCH")
        self.assertIn("candidate_sha", drift["mismatches"])
        self.assertIn("bundle_digest", drift["mismatches"])
        self.assertFalse(drift["merge_authorized"])

    def test_wrong_repository_and_same_sha_are_blocked(self):
        request = build_decision_request(
            _runbook(),
            _bundle(),
            repository="other/repo",
            candidate_sha=CANDIDATE,
            base_sha=CANDIDATE,
            live_evidence_ref=LIVE_REF,
            reviewer="Mikael",
        )
        self.assertEqual(request["state"], "BLOCKED")
        self.assertIn("repository", request["blockers"])
        self.assertIn("candidate_base_same_sha", request["blockers"])

    def test_module_has_no_network_git_or_process_executor(self):
        source = Path("atlasquant_aion_business_consolidation_decision_request.py").read_text(encoding="utf-8")
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
