import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_quota_application_authorization import (
    QUOTA_ACKNOWLEDGEMENTS,
    REQUIRED_POST_APPLICATION_CHECKS,
    REQUIRED_QUOTA_DECISION_TOKEN,
    quota_application_authorization_requirements,
    quota_application_execution_review_packet,
    quota_application_preflight,
    record_quota_application_authorization,
)


def _review():
    return {
        "schema": "ATLASQUANT_AION_BUSINESS_QUOTA_APPLICATION_REVIEW_V1",
        "state": "QUOTA_APPLICATION_DECISION_REQUIRED",
        "capacity_review_digest": "a" * 64,
        "tenant_ids": ["tenant-001", "tenant-002"],
        "quota_application_authorized": False,
        "billing_authorized": False,
        "automatic_expansion_allowed": False,
        "client_actions_authorized": False,
        "executes_action": False,
    }


def _authorization():
    return record_quota_application_authorization(
        _review(),
        decision_token=REQUIRED_QUOTA_DECISION_TOKEN,
        acknowledgements={name: True for name in QUOTA_ACKNOWLEDGEMENTS},
        actor="Mikael",
    )


def _preflight():
    return quota_application_preflight(
        _authorization(),
        change_window_ref="change://window-001",
        monitoring_plan_ref="monitor://quota-001",
        rollback_plan_ref="rollback://quota-001",
        dry_run_verified=True,
        support_ready=True,
        incident_response_ready=True,
    )


class BusinessQuotaApplicationAuthorizationTests(unittest.TestCase):
    def test_requirements_are_fail_closed(self):
        row = quota_application_authorization_requirements()
        self.assertEqual(
            row["state"],
            "EXPLICIT_QUOTA_APPLICATION_DECISION_REQUIRED",
        )
        self.assertEqual(
            row["required_decision_token"],
            REQUIRED_QUOTA_DECISION_TOKEN,
        )
        self.assertFalse(row["generic_confirmation_is_authorization"])
        self.assertFalse(row["quota_application_authorized"])
        self.assertFalse(row["quota_application_execution_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["executes_action"])

    def test_generic_confirmation_is_blocked(self):
        row = record_quota_application_authorization(
            _review(),
            decision_token="vamos lá",
            acknowledgements={name: True for name in QUOTA_ACKNOWLEDGEMENTS},
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["authorization_recorded"])
        self.assertFalse(row["quota_application_authorized"])

    def test_exact_token_records_authorization_but_not_execution(self):
        row = _authorization()
        self.assertEqual(row["state"], "QUOTA_APPLICATION_AUTHORIZATION_RECORDED")
        self.assertTrue(row["authorization_recorded"])
        self.assertTrue(row["quota_application_authorized"])
        self.assertEqual(len(row["authorization_digest"]), 64)
        self.assertFalse(row["quota_application_execution_authorized"])
        self.assertFalse(row["billing_authorized"])
        self.assertFalse(row["automatic_quota_changes_allowed"])
        self.assertFalse(row["executes_action"])

    def test_missing_acknowledgement_blocks(self):
        acks = {name: True for name in QUOTA_ACKNOWLEDGEMENTS}
        acks["billing_changes_remain_separate"] = False
        row = record_quota_application_authorization(
            _review(),
            decision_token=REQUIRED_QUOTA_DECISION_TOKEN,
            acknowledgements=acks,
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")

    def test_forged_unbounded_tenant_packet_is_blocked(self):
        review = _review()
        review["tenant_ids"] = [f"tenant-{i}" for i in range(11)]
        row = record_quota_application_authorization(
            review,
            decision_token=REQUIRED_QUOTA_DECISION_TOKEN,
            acknowledgements={name: True for name in QUOTA_ACKNOWLEDGEMENTS},
            actor="Mikael",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertFalse(row["quota_application_authorized"])

    def test_complete_preflight_reaches_execution_review_only(self):
        row = _preflight()
        self.assertEqual(row["state"], "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED")
        self.assertEqual(
            row["required_post_application_checks"],
            list(REQUIRED_POST_APPLICATION_CHECKS),
        )
        self.assertTrue(row["quota_application_authorized"])
        self.assertFalse(row["quota_application_execution_authorized"])
        self.assertFalse(row["executes_action"])

    def test_missing_operational_guardrails_block_preflight(self):
        row = quota_application_preflight(
            _authorization(),
            change_window_ref="",
            monitoring_plan_ref="",
            rollback_plan_ref="",
            dry_run_verified=False,
            support_ready=False,
            incident_response_ready=False,
        )
        self.assertEqual(row["state"], "QUOTA_APPLICATION_PREFLIGHT_BLOCKED")
        for name in (
            "change_window_present",
            "monitoring_plan_present",
            "rollback_plan_present",
            "dry_run_verified",
            "support_ready",
            "incident_response_ready",
        ):
            self.assertIn(name, row["blockers"])

    def test_execution_review_packet_stays_non_executing(self):
        packet = quota_application_execution_review_packet(_preflight())
        self.assertEqual(
            packet["state"],
            "QUOTA_APPLICATION_EXECUTION_REVIEW_REQUIRED",
        )
        self.assertFalse(packet["quota_application_execution_authorized"])
        self.assertFalse(packet["billing_authorized"])
        self.assertFalse(packet["automatic_quota_changes_allowed"])
        self.assertFalse(packet["automatic_expansion_allowed"])
        self.assertFalse(packet["executes_action"])

    def test_forged_preflight_cannot_reach_execution_review(self):
        row = _preflight()
        row["preflight_digest"] = ""
        packet = quota_application_execution_review_packet(row)
        self.assertEqual(packet["state"], "NOT_READY")
        self.assertFalse(packet["quota_application_execution_authorized"])

    def test_admin_exposes_twenty_second_view(self):
        source = Path("atlasquant_aion_admin.py").read_text(encoding="utf-8")
        self.assertIn("22 · Autorização de aplicação de quotas", source)
        self.assertIn("business_quota_application_authorization_requirements", source)

    def test_module_has_no_network_git_process_or_runtime_executor(self):
        source = Path(
            "atlasquant_aion_business_quota_application_authorization.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in (
            "requests",
            "urllib",
            "httpx",
            "socket",
            "subprocess",
            "github",
            "paramiko",
            "docker",
            "kubernetes",
        ):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
