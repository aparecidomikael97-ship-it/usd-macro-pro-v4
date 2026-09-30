import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_team_access_windows_operator_handoff import (
    build_operator_baseline_handoff,
    operator_handoff_policy,
)
from atlasquant_aion_business_team_access_windows_operator_kit import (
    SCHEMA as OPERATOR_SCHEMA,
)
from atlasquant_aion_business_team_access_sandbox_evidence import (
    SCHEMA as BASELINE_SCHEMA,
)


SESSION = "a" * 32


def _readiness():
    return {
        "schema": OPERATOR_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_WINDOWS_SANDBOX_START_DECISION",
        "readiness_digest": "b" * 64,
        "captured_at": "2026-09-30T21:00:00+00:00",
        "operator_session_id": SESSION,
        "sandbox_start_authorized": False,
        "baseline_collection_authorized": False,
        "lifecycle_execution_authorized": False,
        "production_authorized": False,
        "executes_action": False,
    }


def _baseline():
    return {
        "schema": BASELINE_SCHEMA,
        "state": "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW",
        "evidence_digest": "c" * 64,
        "captured_at": "2026-09-30T21:05:00+00:00",
        "operator_session_id": SESSION,
        "lifecycle_mutation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


class TeamAccessWindowsOperatorHandoffTests(unittest.TestCase):
    def test_policy_keeps_handoff_non_authorizing(self):
        policy = operator_handoff_policy()
        self.assertTrue(policy["same_operator_session_required"])
        self.assertTrue(policy["readiness_before_baseline_required"])
        self.assertFalse(policy["lifecycle_authorization_created"])
        self.assertFalse(policy["production_authorized"])
        self.assertFalse(policy["executes_action"])

    def test_same_session_builds_review_packet_only(self):
        result = build_operator_baseline_handoff(
            _readiness(), _baseline(), reviewed_by="admin.demo"
        )
        self.assertEqual(
            result["state"],
            "READY_FOR_ADMIN_TEAM_ACCESS_REAL_BASELINE_ACCEPTANCE_REVIEW",
        )
        self.assertTrue(all(result["gates"].values()))
        self.assertTrue(result["handoff_digest"])
        self.assertEqual(result["operator_session_id"], SESSION)
        self.assertFalse(result["baseline_accepted"])
        self.assertFalse(result["lifecycle_plan_authorized"])
        self.assertFalse(result["lifecycle_execution_authorized"])
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["executes_action"])

    def test_mixed_sessions_fail_closed(self):
        baseline = _baseline()
        baseline["operator_session_id"] = "d" * 32
        result = build_operator_baseline_handoff(
            _readiness(), baseline, reviewed_by="admin.demo"
        )
        self.assertEqual(
            result["state"], "TEAM_ACCESS_WINDOWS_OPERATOR_HANDOFF_BLOCKED"
        )
        self.assertIn("same_operator_session", result["blockers"])
        self.assertEqual(result["handoff_digest"], "")

    def test_baseline_before_readiness_fails_closed(self):
        baseline = _baseline()
        baseline["captured_at"] = "2026-09-30T20:59:59+00:00"
        result = build_operator_baseline_handoff(
            _readiness(), baseline, reviewed_by="admin.demo"
        )
        self.assertIn("baseline_not_before_readiness", result["blockers"])

    def test_module_has_no_network_process_or_executor_imports(self):
        source = Path(
            "atlasquant_aion_business_team_access_windows_operator_handoff.py"
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
