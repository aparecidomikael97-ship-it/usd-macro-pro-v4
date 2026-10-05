from __future__ import annotations

import unittest

from atlasquant_aion_b2b_revops_foundation import (
    build_revops_foundation,
    normalize_revops_record,
    revops_permission,
)

SCOPE = {
    "owner_id": "owner-a",
    "tenant_id": "tenant-a",
    "workspace_id": "business",
}


def record(
    lead_id="lead-001",
    *,
    company_key="company-001",
    company_label="Empresa Exemplo",
    stage="LEAD",
    owner="sales-01",
    contact_state="EVIDENCE_PRESENT",
    updated_at="2026-10-05T12:00:00+00:00",
    next_action="Agendar diagnóstico",
    next_action_at="2026-10-06T12:00:00+00:00",
    source="referral",
    **overrides,
):
    row = {
        **SCOPE,
        "lead_id": lead_id,
        "company_key": company_key,
        "company_label": company_label,
        "stage": stage,
        "record_owner_ref": owner,
        "source": source,
        "next_action": next_action,
        "next_action_at": next_action_at,
        "updated_at": updated_at,
        "contact_state": contact_state,
        "contact_evidence_refs": (
            [f"contact:{lead_id}"]
            if contact_state == "EVIDENCE_PRESENT"
            else []
        ),
        "evidence_refs": [f"crm:{lead_id}"],
    }
    row.update(overrides)
    return row


class AionB2BRevOpsFoundationTests(unittest.TestCase):
    def test_clean_dataset_is_ready(self):
        out = build_revops_foundation(
            [
                record("lead-001"),
                record(
                    "lead-002",
                    company_key="company-002",
                    stage="DIAGNOSTIC",
                    next_action="Preparar diagnóstico",
                ),
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["metrics"]["accepted_records"], 2)
        self.assertEqual(out["metrics"]["owner_coverage_pct"], 100.0)
        self.assertEqual(out["metrics"]["next_action_coverage_pct"], 100.0)
        self.assertEqual(out["metrics"]["contact_evidence_coverage_pct"], 100.0)
        self.assertFalse(out["crm_write"])
        self.assertFalse(out["executes_action"])

    def test_pipeline_matches_b2b_operating_funnel(self):
        out = build_revops_foundation(
            [
                record("l1", stage="LEAD"),
                record("l2", company_key="c2", stage="DIAGNOSTIC"),
                record("l3", company_key="c3", stage="DEMO"),
                record("l4", company_key="c4", stage="PROPOSAL"),
                record("l5", company_key="c5", stage="CONTRACT"),
                record("l6", company_key="c6", stage="PAYMENT"),
                record("l7", company_key="c7", stage="IMPLEMENTATION"),
                record("l8", company_key="c8", stage="APPROVAL"),
                record("l9", company_key="c9", stage="PUBLISHED"),
                record("l10", company_key="c10", stage="FOLLOWUP"),
                record(
                    "l11",
                    company_key="c11",
                    stage="ACTIVE_SERVICE",
                    next_action="",
                    next_action_at="",
                    contact_state="NOT_REQUIRED",
                ),
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "READY")
        self.assertEqual(out["stage_counts"]["ACTIVE_SERVICE"], 1)
        self.assertEqual(out["stage_counts"]["PROPOSAL"], 1)

    def test_cross_tenant_record_is_rejected(self):
        bad = record()
        bad["tenant_id"] = "tenant-b"
        out = build_revops_foundation(
            [bad],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "PARTIAL")
        self.assertEqual(out["metrics"]["rejected_records"], 1)
        self.assertIn(
            "RECORD_SCOPE_MISMATCH",
            out["rejected_records"][0]["blockers"],
        )

    def test_duplicate_lead_id_with_different_payload_blocks(self):
        out = build_revops_foundation(
            [
                record("lead-001"),
                record(
                    "lead-001",
                    company_label="Outra Empresa",
                    company_key="company-999",
                ),
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("LEAD_ID_CONFLICT", out["blockers"])

    def test_exact_replay_is_warning_not_double_counted(self):
        row = record("lead-001")
        out = build_revops_foundation(
            [row, dict(row)],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["metrics"]["accepted_records"], 1)
        self.assertIn("EXACT_RECORD_REPLAY", out["warnings"])
        self.assertEqual(out["state"], "READY_WITH_REVIEW")

    def test_same_company_multiple_leads_is_duplicate_candidate_not_silent_merge(self):
        out = build_revops_foundation(
            [
                record("lead-001", company_key="company-shared"),
                record("lead-002", company_key="company-shared"),
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "READY_WITH_REVIEW")
        self.assertIn("COMPANY_DUPLICATE_CANDIDATES", out["warnings"])
        self.assertEqual(
            out["duplicate_company_candidates"]["company-shared"],
            ["lead-001", "lead-002"],
        )

    def test_nonterminal_stage_requires_next_action_and_timestamp(self):
        row = normalize_revops_record(
            record(next_action="", next_action_at=""),
            trusted_scope=SCOPE,
        )
        self.assertEqual(row["state"], "REJECTED")
        self.assertIn("NEXT_ACTION_REQUIRED", row["blockers"])
        self.assertIn("NEXT_ACTION_AT_INVALID", row["blockers"])

    def test_terminal_stage_does_not_invent_next_action_requirement(self):
        row = normalize_revops_record(
            record(
                stage="ACTIVE_SERVICE",
                next_action="",
                next_action_at="",
                contact_state="NOT_REQUIRED",
            ),
            trusted_scope=SCOPE,
        )
        self.assertEqual(row["state"], "ACCEPTED")

    def test_contact_evidence_present_requires_reference(self):
        row = normalize_revops_record(
            record(contact_evidence_refs=[]),
            trusted_scope=SCOPE,
        )
        self.assertEqual(row["state"], "REJECTED")
        self.assertIn("CONTACT_EVIDENCE_REQUIRED", row["blockers"])

    def test_do_not_contact_is_preserved_and_never_auto_outreached(self):
        out = build_revops_foundation(
            [
                record(
                    "lead-001",
                    contact_state="DO_NOT_CONTACT",
                )
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["do_not_contact_lead_ids"], ["lead-001"])
        self.assertEqual(out["metrics"]["do_not_contact_count"], 1)
        self.assertFalse(out["automatic_outreach"])
        self.assertFalse(out["automatic_followup"])

    def test_unknown_contact_state_is_review_signal(self):
        out = build_revops_foundation(
            [record("lead-001", contact_state="UNKNOWN")],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertEqual(out["state"], "READY_WITH_REVIEW")
        self.assertIn("CONTACT_EVIDENCE_UNKNOWN", out["warnings"])
        self.assertEqual(out["unknown_contact_lead_ids"], ["lead-001"])

    def test_stale_record_and_due_next_action_are_visible(self):
        out = build_revops_foundation(
            [
                record(
                    "lead-001",
                    updated_at="2026-09-01T12:00:00+00:00",
                    next_action_at="2026-10-04T12:00:00+00:00",
                )
            ],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
            stale_after_days=14,
        )
        self.assertEqual(out["state"], "READY_WITH_REVIEW")
        self.assertIn("STALE_RECORDS_PRESENT", out["warnings"])
        self.assertIn("NEXT_ACTION_DUE", out["warnings"])
        self.assertEqual(out["stale_lead_ids"], ["lead-001"])
        self.assertEqual(out["due_next_action_lead_ids"], ["lead-001"])

    def test_sales_role_can_edit_pipeline_but_not_price_or_contract_commit(self):
        self.assertTrue(revops_permission("SALES", "CRM_EDIT")["eligible"])
        self.assertTrue(revops_permission("SALES", "STAGE_CHANGE")["eligible"])
        price = revops_permission("SALES", "PRICE_COMMITMENT")
        contract = revops_permission("SALES", "CONTRACT_COMMITMENT")
        self.assertFalse(price["eligible"])
        self.assertFalse(contract["eligible"])
        self.assertIn(
            "OWNER_ONLY_CRITICAL_COMMERCIAL_DECISION",
            price["blockers"],
        )

    def test_delegated_admin_is_broad_but_cannot_make_owner_only_commitment(self):
        self.assertTrue(
            revops_permission("DELEGATED_ADMIN", "ASSIGN_OWNER")["eligible"]
        )
        self.assertTrue(
            revops_permission("DELEGATED_ADMIN", "EXPORT")["eligible"]
        )
        self.assertFalse(
            revops_permission(
                "DELEGATED_ADMIN",
                "CONTRACT_COMMITMENT",
            )["eligible"]
        )

    def test_destructive_delete_is_not_supported_even_for_owner(self):
        out = revops_permission("OWNER", "DELETE")
        self.assertFalse(out["eligible"])
        self.assertIn("DESTRUCTIVE_DELETE_NOT_SUPPORTED", out["blockers"])

    def test_owner_eligibility_still_grants_no_execution_authority(self):
        out = revops_permission("OWNER", "CONTRACT_COMMITMENT")
        self.assertTrue(out["eligible"])
        self.assertTrue(out["requires_live_authority_revalidation"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])

    def test_snapshot_never_claims_legal_contact_certification(self):
        out = build_revops_foundation(
            [record()],
            trusted_scope=SCOPE,
            now="2026-10-05T13:00:00+00:00",
        )
        self.assertFalse(out["legal_contact_permission_certified"])
        self.assertFalse(out["automatic_price_commitment"])
        self.assertFalse(out["automatic_contract_commitment"])
        self.assertFalse(out["provider_called"])
        self.assertFalse(out["production_mutation"])


if __name__ == "__main__":
    unittest.main()
