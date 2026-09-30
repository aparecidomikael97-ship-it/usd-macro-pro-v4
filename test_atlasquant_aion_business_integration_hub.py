import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_integration_hub import (
    INTEGRATIONS,
    connection_review_packet,
    hub_snapshot,
    integration_health,
    integration_record,
    minimum_scope_plan,
    secret_handling_policy,
)


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


class BusinessIntegrationHubReadinessTests(unittest.TestCase):
    def test_record_never_contains_real_secret_or_connection(self):
        row = integration_record(
            integration="WHATSAPP_BUSINESS",
            display_name="WhatsApp Demo",
            purpose="Atendimento",
            account_reference="wa-demo",
            config_complete=True,
            auth_review_complete=True,
            read_probe_ok=True,
            last_check_at="2026-09-30T11:00:00Z",
        )
        self.assertEqual(row["state"], "HEALTHY_READ_ONLY_DEMO")
        self.assertIsNone(row["credential_value"])
        self.assertFalse(row["secret_present"])
        self.assertFalse(row["stores_secret"])
        self.assertFalse(row["connects_external_system"])
        self.assertFalse(row["write_scope_granted"])
        self.assertFalse(row["runtime_activated"])
        self.assertFalse(row["executes_action"])

    def test_unknown_integration_fails_closed(self):
        row = integration_record(
            integration="UNKNOWN_SYSTEM",
            display_name="x",
            purpose="x",
        )
        self.assertEqual(row["state"], "BLOCKED")
        self.assertEqual(row["reason"], "UNKNOWN_INTEGRATION")
        self.assertFalse(row["connects_external_system"])

    def test_whatsapp_scope_is_read_draft_and_future_send(self):
        plan = minimum_scope_plan("WHATSAPP_BUSINESS", use_case="Atendimento")
        self.assertEqual(plan["principle"], "LEAST_PRIVILEGE")
        self.assertEqual(plan["scopes"]["read_inbound"], "READ_ONLY")
        self.assertEqual(plan["scopes"]["draft_reply"], "DRAFT_ONLY")
        self.assertEqual(plan["scopes"]["send_reply"], "FUTURE_APPROVAL_REQUIRED")
        self.assertEqual(plan["dangerous_capabilities_granted"], [])
        self.assertFalse(plan["stores_secret"])
        self.assertFalse(plan["executes_action"])

    def test_payments_never_grants_charge_or_refund_in_demo(self):
        plan = minimum_scope_plan("PAYMENTS")
        self.assertEqual(plan["scopes"]["read_invoice_status"], "READ_ONLY")
        self.assertEqual(plan["scopes"]["draft_invoice"], "DRAFT_ONLY")
        self.assertEqual(plan["scopes"]["charge_payment"], "PROHIBITED_IN_DEMO")
        self.assertEqual(plan["scopes"]["refund_payment"], "PROHIBITED_IN_DEMO")

    def test_connection_packet_only_requests_auth_review(self):
        record = integration_record(
            integration="CRM",
            display_name="CRM Demo",
            purpose="Pipeline",
            config_complete=True,
        )
        plan = minimum_scope_plan("CRM")
        packet = connection_review_packet(record, plan, requested_by="Mikael")
        self.assertEqual(packet["state"], "AUTH_REVIEW_REQUIRED")
        self.assertEqual(packet["approval_scope"], "CONNECTION_AUTH_ONLY")
        self.assertFalse(packet["human_approval_recorded"])
        self.assertFalse(packet["oauth_executed"])
        self.assertFalse(packet["credential_stored"])
        self.assertFalse(packet["write_scope_granted"])
        self.assertFalse(packet["runtime_activated"])
        self.assertFalse(packet["executes_action"])

    def test_health_requires_fresh_read_only_probe(self):
        record = integration_record(
            integration="EMAIL",
            display_name="Email Demo",
            purpose="Atendimento",
            config_complete=True,
            auth_review_complete=True,
            read_probe_ok=True,
            last_check_at="2026-09-30T11:30:00Z",
        )
        health = integration_health(record, now=NOW)
        self.assertEqual(health["state"], "HEALTHY_READ_ONLY_DEMO")
        self.assertTrue(health["fresh"])
        self.assertTrue(health["read_only"])
        self.assertFalse(health["write_enabled"])
        stale = integration_health(
            {**record, "last_check_at": "2026-09-20T11:30:00+00:00"},
            now=NOW,
        )
        self.assertEqual(stale["state"], "DEGRADED_DEMO")
        self.assertFalse(stale["fresh"])

    def test_hub_snapshot_reports_missing_and_no_real_connections(self):
        rows = [
            integration_record(
                integration="EMAIL",
                display_name="Email",
                purpose="Atendimento",
                config_complete=True,
                auth_review_complete=True,
                read_probe_ok=True,
                last_check_at="2026-09-30T11:00:00Z",
            ),
            integration_record(
                integration="CRM",
                display_name="CRM",
                purpose="Pipeline",
                config_complete=True,
            ),
        ]
        snap = hub_snapshot(rows)
        self.assertEqual(snap["configured_count"], 2)
        self.assertGreater(len(snap["missing_integrations"]), 0)
        self.assertEqual(snap["real_connections_active"], 0)
        self.assertEqual(snap["write_integrations_active"], 0)
        self.assertFalse(snap["payment_execution_active"])
        self.assertFalse(snap["publication_execution_active"])
        self.assertFalse(snap["runtime_activated"])

    def test_secret_policy_is_explicit(self):
        policy = secret_handling_policy()
        self.assertEqual(policy["policy"], "NO_RAW_SECRETS_IN_DEMO")
        self.assertFalse(policy["raw_secret_input_allowed"])
        self.assertFalse(policy["secret_logging_allowed"])
        self.assertFalse(policy["secret_in_checkpoint_allowed"])
        self.assertFalse(policy["secret_in_ui_state_allowed"])
        self.assertEqual(policy["future_secret_storage"], "DEDICATED_SECRET_STORE_REQUIRED")
        self.assertTrue(policy["rotation_required"])
        self.assertTrue(policy["least_privilege_required"])

    def test_catalog_has_required_business_integrations(self):
        for name in (
            "WHATSAPP_BUSINESS", "EMAIL", "FORMS", "CALENDAR", "CRM",
            "PAYMENTS", "SOCIAL_MEDIA", "ANALYTICS",
        ):
            self.assertIn(name, INTEGRATIONS)

    def test_module_has_no_external_io_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_integration_hub.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai", "streamlit"):
            self.assertNotIn(banned, imported)


if __name__ == "__main__":
    unittest.main()
