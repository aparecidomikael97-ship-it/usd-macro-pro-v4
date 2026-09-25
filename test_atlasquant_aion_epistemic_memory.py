from __future__ import annotations

import unittest

from atlasquant_aion_epistemic_memory import (
    assess_memory_record,
    default_epistemic_memory,
    epistemic_gate,
    new_decision_replay,
    new_memory_record,
    normalize_memory_record,
    reconcile_memory_subject,
)


class AtlasQuantAionEpistemicMemoryTests(unittest.TestCase):
    def _confirmed(self,claim="Fed target range 5.25-5.50",mid=None):
        row=new_memory_record(
            "fed-policy",
            claim,
            layer="SEMANTIC",
            truth_state="CONFIRMED",
            source_ref="official:fomc",
            source_version="2026-09-25",
            evidence_refs=["official:fomc:statement"],
            observed_at="2026-09-25T14:00:00+00:00",
            review_due_at="2026-10-01T00:00:00+00:00",
            created_at="2026-09-25T14:05:00+00:00",
        )
        if mid:
            row["memory_id"]=mid
        return row

    def test_confirmed_memory_requires_source_version_and_evidence(self):
        with self.assertRaises(ValueError):
            new_memory_record(
                "x","y",truth_state="CONFIRMED",
                source_ref="official:x",source_version="",evidence_refs=["e:1"],
            )

    def test_persisted_fake_confirmed_label_is_downgraded(self):
        raw={
            "memory_id":"MEM-X",
            "subject":"x","claim":"y","layer":"SEMANTIC",
            "truth_state":"CONFIRMED",
            "source_ref":"","source_version":"","evidence_refs":[],
            "created_at":"2026-09-25T12:00:00+00:00",
        }
        out=normalize_memory_record(raw)
        self.assertEqual(out["truth_state"],"UNKNOWN")
        self.assertEqual(assess_memory_record(out)["reliability_state"],"UNKNOWN")

    def test_fresh_confirmed_versioned_memory_is_trusted(self):
        row=self._confirmed()
        out=assess_memory_record(row,now="2026-09-25T15:00:00+00:00")
        self.assertEqual(out["reliability_state"],"TRUSTED")
        self.assertTrue(out["safe_for_sensitive_decision"])

    def test_due_memory_becomes_stale_without_changing_truth_label(self):
        row=self._confirmed()
        out=assess_memory_record(row,now="2026-10-02T00:00:00+00:00")
        self.assertEqual(out["truth_state"],"CONFIRMED")
        self.assertEqual(out["reliability_state"],"STALE")
        self.assertFalse(out["safe_for_sensitive_decision"])

    def test_two_current_confirmed_conflicting_claims_are_not_silently_resolved(self):
        a=self._confirmed("Fed target range A","MEM-A")
        b=self._confirmed("Fed target range B","MEM-B")
        out=reconcile_memory_subject([a,b],"fed-policy",now="2026-09-25T15:00:00+00:00")
        self.assertEqual(out["epistemic_state"],"CONFLICTED")
        self.assertTrue(out["conflict"])
        self.assertFalse(out["automatic_conflict_resolution"])

    def test_explicit_supersession_removes_old_record_from_current_conflict(self):
        a=self._confirmed("Old policy","MEM-A")
        b=self._confirmed("New policy","MEM-B")
        b["supersedes"]=["MEM-A"]
        out=reconcile_memory_subject([a,b],"fed-policy",now="2026-09-25T15:00:00+00:00")
        self.assertEqual(out["epistemic_state"],"KNOWN")
        old=next(x for x in out["assessments"] if x["memory_id"]=="MEM-A")
        self.assertEqual(old["reliability_state"],"SUPERSEDED")

    def test_sensitive_gate_blocks_unknown_stale_or_conflicted_memory(self):
        gate=epistemic_gate([
            {"epistemic_state":"KNOWN"},
            {"epistemic_state":"STALE"},
        ],sensitive=True)
        self.assertEqual(gate["state"],"BLOCK_SENSITIVE")
        self.assertIn("STALE_MEMORY",gate["blockers"])
        self.assertFalse(gate["grants_permission"])

    def test_all_known_is_safe_to_use_but_does_not_grant_permission(self):
        gate=epistemic_gate([
            {"epistemic_state":"KNOWN"},
            {"epistemic_state":"KNOWN"},
        ],sensitive=True)
        self.assertEqual(gate["state"],"SAFE_TO_USE")
        self.assertFalse(gate["grants_permission"])

    def test_decision_replay_is_complete_only_with_exact_reference_set(self):
        replay=new_decision_replay(
            "TRADE-1",
            decided_at="2026-09-25T15:30:00+00:00",
            domain="trading",
            decision_summary="No trade: checklist incomplete.",
            model_version="AION-v15",
            rule_version="setup-v3",
            memory_record_ids=["MEM-A"],
            evidence_refs=["calendar:nfp"],
            data_snapshot_refs=["market:snapshot:123"],
            context_digest="ctx123",
            created_at="2026-09-25T15:31:00+00:00",
        )
        self.assertEqual(replay["state"],"COMPLETE_REFERENCE_SET")
        self.assertTrue(replay["reconstructs_only_recorded_state"])
        self.assertFalse(replay["invent_missing_context"])

    def test_replay_with_missing_snapshot_does_not_pretend_complete(self):
        replay=new_decision_replay(
            "TRADE-2",
            decided_at="2026-09-25T15:30:00+00:00",
            domain="trading",
            decision_summary="Decision",
            model_version="AION-v15",
            memory_record_ids=["MEM-A"],
            evidence_refs=["e:1"],
            data_snapshot_refs=[],
        )
        self.assertEqual(replay["state"],"INCOMPLETE_REFERENCE_SET")
        self.assertIn("DATA_SNAPSHOT_REFS_MISSING",replay["blockers"])

    def test_default_never_claims_photographic_memory(self):
        state=default_epistemic_memory()
        self.assertFalse(state["photographic_memory_claimed"])
        self.assertFalse(state["real_trading_enabled"])


if __name__=="__main__":
    unittest.main()
