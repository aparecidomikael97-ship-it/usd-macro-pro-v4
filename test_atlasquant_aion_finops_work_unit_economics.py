from __future__ import annotations

import unittest

from atlasquant_aion_finops_metering import build_metering_ledger
from atlasquant_aion_finops_work_unit_economics import build_work_unit_economics

SCOPE = {"owner_id": "owner-a", "tenant_id": "tenant-a", "workspace_id": "business"}


def meter_event(
    event_id,
    *,
    predicted=0.1,
    actual=0.1,
    feature="managed-ops",
):
    row = {
        **SCOPE,
        "event_id": event_id,
        "user_id": "aion",
        "feature": feature,
        "model": "model-a",
        "provider": "staging-provider",
        "occurred_at": "2026-10-05T12:00:00+00:00",
        "calls": 1,
        "depth": 1,
        "input_tokens": 100,
        "output_tokens": 50,
        "predicted_cost_usd": predicted,
    }
    if actual is not None:
        row["actual_cost_usd"] = actual
    return row


def ledger(events):
    return build_metering_ledger(events, trusted_scope=SCOPE)


def work(work_id, *, state="COMPLETED", work_type="followup", **overrides):
    row = {
        **SCOPE,
        "work_id": work_id,
        "work_type": work_type,
        "state": state,
        "completed_at": "2026-10-05T12:30:00+00:00" if state == "COMPLETED" else "",
        "evidence_refs": [f"receipt:{work_id}"] if state == "COMPLETED" else [],
    }
    row.update(overrides)
    return row


class AionFinOpsWorkUnitEconomicsTests(unittest.TestCase):
    def test_confirmed_fully_loaded_cost_includes_failed_attempts(self):
        out = build_work_unit_economics(
            ledger([
                meter_event("e1", predicted=0.6, actual=0.6),
                meter_event("e2", predicted=0.4, actual=0.4),
                meter_event("e3", predicted=0.2, actual=0.2),
            ]),
            work_units=[
                work("w1", work_type="followup"),
                work("w2", work_type="proposal"),
                work("w3", state="FAILED", work_type="followup"),
            ],
            allocations=[
                {"event_id": "e1", "work_id": "w1"},
                {"event_id": "e2", "work_id": "w2"},
                {"event_id": "e3", "work_id": "w3"},
            ],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "CONFIRMED")
        self.assertEqual(out["work_counts"]["completed"], 2)
        self.assertEqual(out["work_counts"]["failed"], 1)
        self.assertEqual(out["economics"]["observed_completed_actual_cost_usd"], 1.0)
        self.assertEqual(out["economics"]["observed_operating_actual_cost_usd"], 1.2)
        self.assertEqual(
            out["economics"]["confirmed_fully_loaded_actual_cost_per_completed_work_usd"],
            0.6,
        )
        self.assertTrue(out["coverage"]["fully_covered"])

    def test_completed_work_without_cost_evidence_is_partial_not_zero(self):
        out = build_work_unit_economics(
            ledger([]),
            work_units=[work("w1")],
            allocations=[],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "PARTIAL")
        self.assertIn("COMPLETED_WORK_WITHOUT_COST_EVIDENCE", out["warnings"])
        self.assertIsNone(
            out["economics"]["confirmed_fully_loaded_actual_cost_per_completed_work_usd"]
        )
        self.assertFalse(out["missing_cost_is_zero"])

    def test_unallocated_meter_event_prevents_confirmed_unit_cost(self):
        out = build_work_unit_economics(
            ledger([
                meter_event("e1", actual=0.2),
                meter_event("e2", actual=0.3),
            ]),
            work_units=[work("w1")],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "PARTIAL")
        self.assertEqual(out["allocation"]["unallocated_events"], 1)
        self.assertIn("METER_EVENTS_UNALLOCATED", out["warnings"])
        self.assertIsNone(
            out["economics"]["confirmed_fully_loaded_actual_cost_per_completed_work_usd"]
        )

    def test_missing_actual_cost_keeps_snapshot_partial(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1", predicted=0.2, actual=None)]),
            work_units=[work("w1")],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "PARTIAL")
        self.assertIn("COMPLETED_WORK_ACTUAL_COST_INCOMPLETE", out["warnings"])
        self.assertIn("OPERATING_ACTUAL_COST_INCOMPLETE", out["warnings"])
        self.assertEqual(
            out["coverage"]["completed_work_actual_cost_coverage_pct"],
            0.0,
        )

    def test_in_progress_work_prevents_closed_cohort_confirmation(self):
        out = build_work_unit_economics(
            ledger([
                meter_event("e1", actual=0.2),
                meter_event("e2", actual=0.1),
            ]),
            work_units=[
                work("w1"),
                work("w2", state="IN_PROGRESS"),
            ],
            allocations=[
                {"event_id": "e1", "work_id": "w1"},
                {"event_id": "e2", "work_id": "w2"},
            ],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "PARTIAL")
        self.assertIn("IN_PROGRESS_WORK_PRESENT", out["warnings"])
        self.assertIsNone(
            out["economics"]["confirmed_fully_loaded_actual_cost_per_completed_work_usd"]
        )

    def test_no_completed_work_is_explicit(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1", actual=0.2)]),
            work_units=[work("w1", state="FAILED")],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "NO_COMPLETED_WORK")
        self.assertEqual(out["work_counts"]["completed"], 0)
        self.assertIsNone(
            out["economics"]["confirmed_fully_loaded_actual_cost_per_completed_work_usd"]
        )

    def test_duplicate_work_id_blocks(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1")]),
            work_units=[work("w1"), work("w1")],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WORK_ID_DUPLICATE", out["blockers"])

    def test_meter_event_cannot_be_allocated_more_than_once(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1")]),
            work_units=[work("w1"), work("w2")],
            allocations=[
                {"event_id": "e1", "work_id": "w1"},
                {"event_id": "e1", "work_id": "w2"},
            ],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("METER_EVENT_ALLOCATED_MORE_THAN_ONCE", out["blockers"])

    def test_allocation_must_reference_known_ledger_event_and_work(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1")]),
            work_units=[work("w1")],
            allocations=[
                {"event_id": "missing", "work_id": "w1"},
                {"event_id": "e1", "work_id": "missing-work"},
            ],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("ALLOCATION_EVENT_NOT_IN_LEDGER", out["blockers"])
        self.assertIn("ALLOCATION_WORK_NOT_FOUND", out["blockers"])

    def test_cross_scope_work_is_blocked(self):
        foreign = work("w1")
        foreign["tenant_id"] = "tenant-b"
        out = build_work_unit_economics(
            ledger([meter_event("e1")]),
            work_units=[foreign],
            allocations=[],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("WORK_SCOPE_MISMATCH", out["blockers"])

    def test_cross_scope_ledger_is_blocked(self):
        other_scope = dict(SCOPE)
        other_scope["workspace_id"] = "other"
        foreign_ledger = build_metering_ledger(
            [{
                **meter_event("e1"),
                "workspace_id": "other",
            }],
            trusted_scope=other_scope,
        )
        out = build_work_unit_economics(
            foreign_ledger,
            work_units=[work("w1")],
            allocations=[],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("METERING_LEDGER_SCOPE_MISMATCH", out["blockers"])

    def test_completed_work_requires_completion_evidence(self):
        bad = work("w1")
        bad["evidence_refs"] = []
        out = build_work_unit_economics(
            ledger([]),
            work_units=[bad],
            allocations=[],
            trusted_scope=SCOPE,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("COMPLETION_EVIDENCE_REQUIRED", out["blockers"])

    def test_by_work_type_separates_completed_and_costed_counts(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1", actual=0.2)]),
            work_units=[
                work("w1", work_type="followup"),
                work("w2", work_type="followup"),
            ],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        bucket = out["by_work_type"]["followup"]
        self.assertEqual(bucket["completed"], 2)
        self.assertEqual(bucket["costed_completed"], 1)

    def test_snapshot_never_becomes_billing_or_automatic_action_authority(self):
        out = build_work_unit_economics(
            ledger([meter_event("e1", actual=0.2)]),
            work_units=[work("w1")],
            allocations=[{"event_id": "e1", "work_id": "w1"}],
            trusted_scope=SCOPE,
        )
        self.assertFalse(out["source_of_truth_for_billing"])
        self.assertFalse(out["automatic_charge"])
        self.assertFalse(out["automatic_pricing_change"])
        self.assertFalse(out["automatic_budget_change"])
        self.assertFalse(out["automatic_provider_switch"])
        self.assertFalse(out["grants_authority"])
        self.assertFalse(out["executes_action"])


if __name__ == "__main__":
    unittest.main()
