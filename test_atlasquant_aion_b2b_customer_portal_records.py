from __future__ import annotations

import unittest

from atlasquant_aion_b2b_customer_portal_records import (
    build_customer_portal_records,
)

SCOPE = {"owner_id": "owner-a", "tenant_id": "service-tenant-001", "workspace_id": "service-workspace-001"}


def raw(**overrides):
    row = {
        **SCOPE,
        "customer_id": "customer-001",
        "package": "PROFISSIONAL",
        "integrations": [
            {
                "integration_id": "crm",
                "name": "CRM",
                "state": "CONNECTED",
                "last_checked_at": "2026-10-05T12:10:00-04:00",
            },
            {
                "integration_id": "email",
                "name": "E-mail",
                "state": "DEGRADED",
                "last_checked_at": "2026-10-05T12:10:00-04:00",
            },
        ],
        "crm": {
            "enabled": True,
            "contacts": 120,
            "open_opportunities": 14,
            "open_tasks": 7,
            "won_this_cycle": 3,
        },
        "documents": [
            {
                "document_id": "contract-001",
                "title": "Contrato de Operação",
                "type": "CONTRACT",
                "state": "SIGNED",
                "issued_at": "2026-10-01",
                "version": "v1",
            },
            {
                "document_id": "report-001",
                "title": "Relatório de Valor",
                "type": "REPORT",
                "state": "ISSUED",
                "issued_at": "2026-10-05",
                "version": "v1",
            },
        ],
        "billing": {
            "subscription_state": "ACTIVE",
            "payment_state": "PAID",
            "next_due_date": "2026-11-05",
            "amount_due_brl": 0.0,
        },
        "evidence_refs": ["integrations:v1", "crm:v1", "docs:v1", "billing:v1"],
    }
    row.update(overrides)
    return row


class AionB2BCustomerPortalRecordsTests(unittest.TestCase):
    def test_valid_records_are_ready_and_read_only(self):
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(),
        )
        self.assertEqual(out["state"], "READY")
        self.assertFalse(out["blockers"])
        self.assertEqual(out["billing"]["subscription_state"], "ACTIVE")
        self.assertEqual(out["billing"]["payment_state"], "PAID")
        self.assertEqual(len(out["integrations"]), 2)
        self.assertEqual(out["crm"]["contacts"], 120)
        self.assertEqual(len(out["documents"]), 2)
        self.assertTrue(out["read_only"])
        self.assertFalse(out["executes_action"])

    def test_scope_customer_and_package_mismatch_fail_closed(self):
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(tenant_id="other", customer_id="other-customer", package="COMPLETO"),
        )
        self.assertIn("PORTAL_RECORD_SCOPE_MISMATCH", out["blockers"])
        self.assertIn("PORTAL_RECORD_CUSTOMER_MISMATCH", out["blockers"])
        self.assertIn("PORTAL_RECORD_PACKAGE_MISMATCH", out["blockers"])

    def test_secret_like_fields_are_rejected_recursively(self):
        data = raw()
        data["integrations"][0]["api_token"] = "do-not-expose"
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PORTAL_RECORD_SECRET_LIKE_FIELD_REJECTED", out["blockers"])
        self.assertNotIn("api_token", str(out))

    def test_invalid_integration_state_blocks(self):
        data = raw()
        data["integrations"][0]["state"] = "MAGIC"
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("INTEGRATION_ITEM_INVALID", out["blockers"])

    def test_crm_is_summary_only_and_nonnegative(self):
        data = raw()
        data["crm"]["contacts"] = -1
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("CRM_CONTACTS_INVALID", out["blockers"])
        self.assertNotIn("email_address", out["crm"])
        self.assertNotIn("phone", out["crm"])

    def test_duplicate_document_id_blocks(self):
        data = raw()
        data["documents"].append(dict(data["documents"][0]))
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("DOCUMENT_ITEM_INVALID", out["blockers"])

    def test_due_or_overdue_payment_requires_due_date(self):
        for state in ("DUE", "OVERDUE"):
            with self.subTest(state=state):
                data = raw()
                data["billing"] = {
                    "subscription_state": "ACTIVE",
                    "payment_state": state,
                    "next_due_date": "",
                    "amount_due_brl": 500.0,
                }
                out = build_customer_portal_records(
                    trusted_scope=SCOPE,
                    customer_id="customer-001",
                    package="PROFISSIONAL",
                    raw=data,
                )
                self.assertIn("NEXT_DUE_DATE_REQUIRED", out["blockers"])

    def test_negative_amount_due_blocks(self):
        data = raw()
        data["billing"]["amount_due_brl"] = -1
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=data,
        )
        self.assertIn("AMOUNT_DUE_INVALID", out["blockers"])

    def test_evidence_is_required(self):
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(evidence_refs=["one"]),
        )
        self.assertIn("PORTAL_RECORD_EVIDENCE_INSUFFICIENT", out["blockers"])

    def test_no_external_or_financial_authority_is_granted(self):
        out = build_customer_portal_records(
            trusted_scope=SCOPE,
            customer_id="customer-001",
            package="PROFISSIONAL",
            raw=raw(),
        )
        for key in (
            "secret_material_exposed",
            "payment_link_created",
            "document_signed",
            "automatic_billing",
            "automatic_subscription_change",
            "automatic_crm_write",
            "automatic_integration_change",
            "provider_called",
            "production_mutation",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
