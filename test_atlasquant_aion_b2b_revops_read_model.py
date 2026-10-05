from __future__ import annotations

import unittest

from atlasquant_aion_b2b_revops_read_model import build_revops_read_model

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def snapshot(**overrides):
    row = {
        "schema": "ATLASQUANT_AION_B2B_REVOPS_FOUNDATION_V1",
        "state": "READY_WITH_REVIEW",
        "scope": dict(SCOPE),
        "warnings": ["STALE_RECORDS_PRESENT", "NEXT_ACTION_DUE"],
        "metrics": {
            "accepted_records": 25,
            "rejected_records": 0,
            "company_count": 20,
            "duplicate_company_candidate_count": 2,
            "stale_record_count": 3,
            "due_next_action_count": 4,
            "do_not_contact_count": 1,
            "unknown_contact_count": 2,
            "contact_evidence_coverage_pct": 88.0,
            "next_action_coverage_pct": 96.0,
            "owner_coverage_pct": 100.0,
        },
        "stage_counts": {
            "LEAD": 8,
            "DIAGNOSTIC": 5,
            "DEMO": 3,
            "PROPOSAL": 4,
            "CONTRACT": 2,
            "PAYMENT": 1,
            "IMPLEMENTATION": 1,
            "APPROVAL": 0,
            "PUBLISHED": 0,
            "FOLLOWUP": 1,
            "ACTIVE_SERVICE": 0,
            "CLOSED_LOST": 0,
        },
        "snapshot_digest": "sha256:revops",
        "legal_contact_permission_certified": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_price_commitment": False,
        "automatic_contract_commitment": False,
        "destructive_delete_enabled": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
        "accepted_records": [
            {
                "lead_id": "secret-lead",
                "company_label": "Empresa Secreta",
                "record_owner_ref": "sales-01",
            }
        ],
        "do_not_contact_lead_ids": ["secret-lead"],
    }
    row.update(overrides)
    return row


class AionB2BRevOpsReadModelTests(unittest.TestCase):
    def test_ready_source_projects_aggregate_metrics(self):
        out = build_revops_read_model(snapshot(), trusted_scope=SCOPE)
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["source_state"], "READY_WITH_REVIEW")
        self.assertEqual(out["metrics"]["accepted_records"], 25)
        self.assertEqual(out["metrics"]["due_next_action_count"], 4)
        self.assertEqual(out["stage_counts"]["PROPOSAL"], 4)
        self.assertEqual(
            out["review_signals"],
            ["STALE_RECORDS_PRESENT", "NEXT_ACTION_DUE"],
        )
        self.assertTrue(out["read_only"])
        self.assertFalse(out["executes_action"])

    def test_partial_source_remains_partial(self):
        source = snapshot(state="PARTIAL")
        out = build_revops_read_model(source, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "PARTIAL")
        self.assertEqual(out["source_state"], "PARTIAL")

    def test_blocked_or_empty_source_is_not_renderable(self):
        for state in ("BLOCKED", "EMPTY", ""):
            with self.subTest(state=state):
                out = build_revops_read_model(
                    snapshot(state=state),
                    trusted_scope=SCOPE,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("REVOPS_SOURCE_STATE_UNSAFE", out["blockers"])

    def test_cross_tenant_source_blocks(self):
        source = snapshot()
        source["scope"] = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-b",
            "workspace_id": "business",
        }
        out = build_revops_read_model(source, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("REVOPS_SOURCE_SCOPE_MISMATCH", out["blockers"])

    def test_missing_digest_blocks(self):
        out = build_revops_read_model(
            snapshot(snapshot_digest=""),
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("REVOPS_SOURCE_DIGEST_REQUIRED", out["blockers"])

    def test_source_action_flag_flip_blocks(self):
        for key in (
            "automatic_outreach",
            "automatic_followup",
            "automatic_stage_change",
            "automatic_owner_assignment",
            "automatic_price_commitment",
            "automatic_contract_commitment",
            "crm_write",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            with self.subTest(key=key):
                source = snapshot()
                source[key] = True
                out = build_revops_read_model(source, trusted_scope=SCOPE)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(
                    any(key.upper() in blocker for blocker in out["blockers"])
                )

    def test_raw_lead_and_company_data_are_not_projected(self):
        out = build_revops_read_model(snapshot(), trusted_scope=SCOPE)
        flat = str(out)
        self.assertNotIn("secret-lead", flat)
        self.assertNotIn("Empresa Secreta", flat)
        self.assertNotIn("sales-01", flat)
        self.assertNotIn("accepted_records", out)
        self.assertNotIn("do_not_contact_lead_ids", out)
        self.assertFalse(out["raw_records_exposed"])
        self.assertFalse(out["contact_data_exposed"])

    def test_only_whitelisted_metrics_are_projected(self):
        source = snapshot()
        source["metrics"]["private_margin_brl"] = 999999
        out = build_revops_read_model(source, trusted_scope=SCOPE)
        self.assertNotIn("private_margin_brl", out["metrics"])

    def test_non_numeric_metric_becomes_unknown_not_invented(self):
        source = snapshot()
        source["metrics"]["accepted_records"] = "25"
        out = build_revops_read_model(source, trusted_scope=SCOPE)
        self.assertIsNone(out["metrics"]["accepted_records"])

    def test_read_model_never_grants_operational_authority(self):
        out = build_revops_read_model(snapshot(), trusted_scope=SCOPE)
        for key in (
            "crm_write",
            "automatic_outreach",
            "automatic_followup",
            "automatic_stage_change",
            "automatic_owner_assignment",
            "automatic_price_commitment",
            "automatic_contract_commitment",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
