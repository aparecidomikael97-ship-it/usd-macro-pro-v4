from __future__ import annotations

import unittest

from atlasquant_aion_b2b_revops_cleanup_plan import build_revops_cleanup_plan

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
        "snapshot_digest": "sha256:revops-source",
        "duplicate_company_candidates": {
            "company-01": ["lead-001", "lead-002"],
        },
        "stale_lead_ids": ["lead-003"],
        "due_next_action_lead_ids": ["lead-004"],
        "unknown_contact_lead_ids": ["lead-005"],
        "do_not_contact_lead_ids": ["lead-006"],
        "rejected_records": [],
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_price_commitment": False,
        "automatic_contract_commitment": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }
    row.update(overrides)
    return row


class AionB2BRevOpsCleanupPlanTests(unittest.TestCase):
    def test_quality_signals_become_human_review_tasks(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        self.assertEqual(out["state"], "READY_FOR_HUMAN_REVIEW")
        self.assertEqual(out["total_tasks"], 5)
        self.assertEqual(out["task_counts"]["REVIEW_COMPANY_DUPLICATE"], 1)
        self.assertEqual(out["task_counts"]["REVIEW_STALE_RECORD"], 1)
        self.assertEqual(out["task_counts"]["REVIEW_DUE_NEXT_ACTION"], 1)
        self.assertEqual(out["task_counts"]["REVIEW_CONTACT_EVIDENCE"], 1)
        self.assertEqual(out["task_counts"]["PRESERVE_DO_NOT_CONTACT"], 1)
        self.assertTrue(out["human_review_required"])
        self.assertFalse(out["executes_action"])

    def test_duplicate_candidate_never_auto_merges(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        task = next(
            row
            for row in out["tasks"]
            if row["kind"] == "REVIEW_COMPANY_DUPLICATE"
        )
        self.assertEqual(task["record_refs"], ["lead-001", "lead-002"])
        self.assertFalse(task["automatic_merge"])
        self.assertFalse(task["destructive_delete"])
        self.assertFalse(task["crm_write"])

    def test_do_not_contact_generates_preservation_task_not_outreach(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        task = next(
            row
            for row in out["tasks"]
            if row["kind"] == "PRESERVE_DO_NOT_CONTACT"
        )
        self.assertEqual(task["record_refs"], ["lead-006"])
        self.assertFalse(task["outreach"])
        self.assertFalse(out["automatic_outreach"])
        self.assertFalse(out["automatic_followup"])

    def test_due_next_action_does_not_trigger_followup(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        task = next(
            row
            for row in out["tasks"]
            if row["kind"] == "REVIEW_DUE_NEXT_ACTION"
        )
        self.assertTrue(task["human_review_required"])
        self.assertFalse(task["automatic_execution"])
        self.assertFalse(task["outreach"])

    def test_unknown_contact_requires_evidence_review(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        task = next(
            row
            for row in out["tasks"]
            if row["kind"] == "REVIEW_CONTACT_EVIDENCE"
        )
        self.assertEqual(task["priority"], "HIGH")
        self.assertEqual(task["required_capability"], "CRM_EDIT")
        self.assertIn("UNKNOWN", task["rationale"])
        self.assertFalse(task["outreach"])

    def test_rejected_records_are_counted_without_copying_raw_payloads(self):
        source = snapshot(
            rejected_records=[
                {"state": "REJECTED", "lead_id": "bad-1", "secret_note": "private"},
                {"state": "REJECTED", "lead_id": "bad-2", "secret_note": "private2"},
            ]
        )
        out = build_revops_cleanup_plan(source, trusted_scope=SCOPE)
        task = next(
            row
            for row in out["tasks"]
            if row["kind"] == "REVIEW_REJECTED_RECORDS"
        )
        self.assertIn("2 registro(s)", task["rationale"])
        self.assertEqual(task["record_refs"], [])
        self.assertNotIn("bad-1", str(task))
        self.assertNotIn("private", str(task))

    def test_plan_is_deterministic_for_same_snapshot(self):
        first = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        second = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        self.assertEqual(first["tasks"], second["tasks"])

    def test_cross_tenant_source_blocks_with_no_tasks(self):
        source = snapshot()
        source["scope"] = {
            "owner_id": "owner-a",
            "tenant_id": "tenant-b",
            "workspace_id": "business",
        }
        out = build_revops_cleanup_plan(source, trusted_scope=SCOPE)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("REVOPS_SOURCE_SCOPE_MISMATCH", out["blockers"])
        self.assertEqual(out["tasks"], [])

    def test_blocked_or_empty_source_cannot_create_cleanup_plan(self):
        for state in ("BLOCKED", "EMPTY", ""):
            with self.subTest(state=state):
                out = build_revops_cleanup_plan(
                    snapshot(state=state),
                    trusted_scope=SCOPE,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn("REVOPS_SOURCE_STATE_UNSAFE", out["blockers"])
                self.assertEqual(out["tasks"], [])

    def test_missing_source_digest_blocks(self):
        out = build_revops_cleanup_plan(
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
                out = build_revops_cleanup_plan(source, trusted_scope=SCOPE)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(
                    any(key.upper() in blocker for blocker in out["blockers"])
                )

    def test_plan_never_enables_destructive_or_automatic_cleanup(self):
        out = build_revops_cleanup_plan(snapshot(), trusted_scope=SCOPE)
        for key in (
            "automatic_cleanup",
            "automatic_merge",
            "destructive_delete_enabled",
            "automatic_outreach",
            "automatic_followup",
            "automatic_stage_change",
            "automatic_owner_assignment",
            "crm_write",
            "provider_called",
            "production_mutation",
            "grants_authority",
            "executes_action",
        ):
            self.assertFalse(out[key], key)


if __name__ == "__main__":
    unittest.main()
