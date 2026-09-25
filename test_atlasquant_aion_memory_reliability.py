from __future__ import annotations

import unittest

from atlasquant_aion_memory_reliability import (
    assess_canonical_memory_hits,
    default_memory_reliability,
    epistemic_assessment,
    evaluate_memory_review,
    memory_retrieval_gate,
    memory_reliability_summary,
    new_decision_snapshot,
    new_memory_review,
    normalize_memory_reliability,
)


class AtlasQuantAionMemoryReliabilityTests(unittest.TestCase):
    def test_confirmed_memory_without_provenance_or_digest_is_not_confirmed_for_use(self):
        review=new_memory_review(
            "mem:1",truth_state="CONFIRMED",source_refs=[],evidence_refs=[],
            content_digest="",
        )
        self.assertEqual(review["review_state"],"VERIFY_REQUIRED")
        self.assertEqual(review["effective_truth_state"],"UNKNOWN")
        self.assertFalse(memory_retrieval_gate(review)["context_eligible"])

    def test_conflicting_memory_fails_closed(self):
        review=new_memory_review(
            "mem:2",truth_state="CONFIRMED",source_refs=["doc:a"],
            evidence_refs=["ev:a"],content_digest="abc123",
            contradiction_refs=["mem:other"],
        )
        gate=memory_retrieval_gate(review)
        self.assertEqual(review["review_state"],"CONFLICT")
        self.assertEqual(gate["gate_state"],"BLOCKED")
        self.assertFalse(gate["action_authorized"])

    def test_expired_confirmed_memory_downgrades_to_inference(self):
        review=new_memory_review(
            "mem:3",truth_state="CONFIRMED",source_refs=["doc:a"],
            evidence_refs=["ev:a"],content_digest="abc123",
            valid_until="2026-09-20T00:00:00+00:00",
            now="2026-09-25T00:00:00+00:00",
        )
        self.assertEqual(review["review_state"],"EXPIRED")
        self.assertEqual(review["effective_truth_state"],"INFERENCE")
        self.assertEqual(
            memory_retrieval_gate(
                review,now="2026-09-25T00:00:00+00:00"
            )["gate_state"],
            "STALE_CONTEXT_ONLY",
        )

    def test_sensitive_action_requires_current_confirmed_memory(self):
        review=new_memory_review(
            "mem:4",truth_state="INFERENCE",source_refs=["doc:a"],
            evidence_refs=["ev:a"],content_digest="abc123",
        )
        gate=memory_retrieval_gate(review,sensitive_action=True)
        self.assertEqual(gate["gate_state"],"VERIFY_REQUIRED")
        self.assertFalse(gate["can_support_sensitive_action"])
        self.assertFalse(gate["action_authorized"])

    def test_superseded_memory_is_blocked(self):
        review=new_memory_review(
            "mem:5",truth_state="CONFIRMED",source_refs=["doc:a"],
            evidence_refs=["ev:a"],content_digest="abc123",
            superseded_by="mem:6",
        )
        self.assertEqual(review["review_state"],"SUPERSEDED")
        self.assertEqual(memory_retrieval_gate(review)["gate_state"],"BLOCKED")

    def test_epistemic_core_detects_conflict_and_never_authorizes_action(self):
        a=new_memory_review(
            "mem:a",truth_state="CONFIRMED",source_refs=["doc:a"],
            evidence_refs=["ev:a"],content_digest="abc123",
        )
        b=new_memory_review(
            "mem:b",truth_state="CONFIRMED",source_refs=["doc:b"],
            evidence_refs=["ev:b"],content_digest="def456",
            contradiction_refs=["mem:a"],
        )
        out=epistemic_assessment("claim",[a,b],sensitive_action=True)
        self.assertEqual(out["state"],"CONFLICT")
        self.assertIn("MEMORY_CONFLICT",out["blockers"])
        self.assertFalse(out["action_authorized"])

    def test_canonical_memory_hit_is_supported_but_not_live_market_authority(self):
        out=assess_canonical_memory_hits(
            "checkpoint decision",
            [{"path":"docs/a.md","excerpt":"Aprovado.","sha256":"a"*64}],
        )
        self.assertEqual(out["state"],"SUPPORTED")
        self.assertTrue(out["current_confirmed_refs"])
        self.assertFalse(out["action_authorized"])

    def test_decision_snapshot_is_replayable_and_nonexecuting(self):
        snap=new_decision_snapshot(
            "decision:1",domain="trading",conclusion="NO_TRADE",
            context_refs=["market:snapshot-1"],evidence_refs=["calendar:1"],
            checklist=["bias aligned","risk ok"],regime="RANGE",
            thesis="Sem gatilho válido.",stop="n/a",target="n/a",
            model_version="AION-V15",truth_state="CONFIRMED",
            created_at="2026-09-25T20:00:00+00:00",
        )
        self.assertTrue(snap["memory_replay"])
        self.assertTrue(snap["context_digest"])
        self.assertFalse(snap["executes_action"])
        self.assertFalse(snap["real_trading_enabled"])

    def test_persisted_fake_review_state_is_recomputed(self):
        raw=default_memory_reliability()
        raw["reviews"]=[{
            "memory_ref":"mem:fake",
            "truth_state":"CONFIRMED",
            "review_state":"CURRENT",
            "source_refs":[],
            "evidence_refs":[],
            "content_digest":"",
        }]
        state=normalize_memory_reliability(raw)
        self.assertEqual(state["reviews"][0]["review_state"],"VERIFY_REQUIRED")
        self.assertEqual(memory_reliability_summary(state)["verify_required"],1)


if __name__=="__main__":
    unittest.main()
