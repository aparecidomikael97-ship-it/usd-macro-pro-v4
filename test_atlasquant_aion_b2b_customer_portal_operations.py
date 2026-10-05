from __future__ import annotations

import unittest

from atlasquant_aion_b2b_customer_portal_operations import (
    build_customer_portal_operations,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "service-tenant-001",
    "workspace_id": "service-workspace-001",
}


def raw(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "automations": [
            {
                "automation_id": "followup",
                "name": "Follow-up comercial",
                "state": "ACTIVE",
                "last_result": "SUCCESS",
                "last_run_at": "2026-10-05T11:55:00-04:00",
                "next_review_at": "2026-10-06T09:00:00-04:00",
            },
            {
                "automation_id": "sla-watch",
                "name": "SLA Watch",
                "state": "DEGRADED",
                "last_result": "PARTIAL",
                "last_run_at": "2026-10-05T11:50:00-04:00",
                "next_review_at": "2026-10-05T13:00:00-04:00",
            },
        ],
        "tickets": [
            {
                "ticket_id": "ticket-001",
                "title": "Integração CRM degradada",
                "state": "IN_PROGRESS",
                "priority": "HIGH",
                "sla_state": "AT_RISK",
                "created_at": "2026-10-05T10:00:00-04:00",
                "updated_at": "2026-10-05T11:45:00-04:00",
            },
            {
                "ticket_id": "ticket-002",
                "title": "Dúvida sobre relatório",
                "state": "RESOLVED",
                "priority": "LOW",
                "sla_state": "ON_TRACK",
                "created_at": "2026-10-04T15:00:00-04:00",
                "updated_at": "2026-10-05T09:00:00-04:00",
            },
        ],
        "evidence_refs": ["automations:v1", "tickets:v1", "sla:v1"],
    }
    row.update(overrides)
    return row


class AionB2BCustomerPortalOperationsTests(unittest.TestCase):
    def test_valid_operations_are_ready_and_read_only(self):
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(),
        )
        self.assertEqual(out["state"], "READY")
        self.assertFalse(out["blockers"])
        self.assertEqual(out["counts"]["automation_total"], 2)
        self.assertEqual(out["counts"]["automation_degraded"], 1)
        self.assertEqual(out["counts"]["ticket_open"], 1)
        self.assertEqual(out["counts"]["ticket_sla_breached"], 0)
        self.assertTrue(out["read_only"])
        self.assertFalse(out["executes_action"])

    def test_scope_customer_and_package_mismatch_block(self):
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(
                tenant_id="other",
                customer_id="other-customer",
                package="COMPLETO",
            ),
        )
        self.assertIn("PORTAL_OPERATIONS_SCOPE_MISMATCH", out["blockers"])
        self.assertIn("PORTAL_OPERATIONS_CUSTOMER_MISMATCH", out["blockers"])
        self.assertIn("PORTAL_OPERATIONS_PACKAGE_MISMATCH", out["blockers"])

    def test_secret_or_message_content_fields_are_rejected(self):
        data = raw()
        data["tickets"][0]["message_body"] = "sensitive support transcript"
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PORTAL_OPERATIONS_SECRET_OR_CONTENT_FIELD_REJECTED", out["blockers"])
        self.assertNotIn("sensitive support transcript", str(out))

    def test_duplicate_automation_and_ticket_ids_block(self):
        data = raw()
        data["automations"].append(dict(data["automations"][0]))
        data["tickets"].append(dict(data["tickets"][0]))
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("AUTOMATION_ITEM_INVALID", out["blockers"])
        self.assertIn("TICKET_ITEM_INVALID", out["blockers"])

    def test_unknown_automation_state_blocks(self):
        data = raw()
        data["automations"][0]["state"] = "RUN_ANYTHING"
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("AUTOMATION_ITEM_INVALID", out["blockers"])

    def test_unknown_ticket_or_sla_state_blocks(self):
        data = raw()
        data["tickets"][0]["state"] = "MAGIC"
        data["tickets"][1]["sla_state"] = "IGNORE"
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("TICKET_ITEM_INVALID", out["blockers"])

    def test_critical_open_and_breached_counts_are_derived(self):
        data = raw()
        data["tickets"][0].update({
            "priority": "CRITICAL",
            "sla_state": "BREACHED",
        })
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertEqual(out["counts"]["critical_open"], 1)
        self.assertEqual(out["counts"]["ticket_sla_breached"], 1)

    def test_ticket_content_is_metadata_only(self):
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(),
        )
        row = out["tickets"][0]
        self.assertEqual(
            set(row),
            {"ticket_id", "title", "state", "priority", "sla_state", "created_at", "updated_at"},
        )
        self.assertNotIn("message", str(row).lower())

    def test_evidence_is_required(self):
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(evidence_refs=["one"]),
        )
        self.assertIn("PORTAL_OPERATIONS_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_automation_or_ticket_authority_is_granted(self):
        out = build_customer_portal_operations(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(),
        )
        for key in (
            "automation_control_exposed",
            "ticket_write_exposed",
            "message_content_exposed",
            "automatic_automation_change",
            "automatic_ticket_change",
            "automatic_customer_contact",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
