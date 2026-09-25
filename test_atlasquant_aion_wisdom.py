from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_aion_learning import new_learning_episode, settle_learning_episode
from atlasquant_aion_memory import (
    default_checkpoint,
    ensure_operating_checkpoint,
    update_wisdom_checkpoint,
)
from atlasquant_aion_wisdom import (
    candidate_from_learning_episode,
    new_wisdom_entry,
    normalize_wisdom_entry,
    search_wisdom,
    upsert_wisdom_entry,
    wisdom_digest,
    wisdom_evidence_hits,
    wisdom_review_state,
    wisdom_summary,
)


class AtlasQuantAionWisdomTests(unittest.TestCase):
    def test_confirmed_wisdom_requires_evidence(self):
        with self.assertRaises(ValueError):
            new_wisdom_entry(
                "Fonte",
                "Afirmação forte",
                truth_state="CONFIRMED",
                confidence_pct=90,
            )

    def test_normalizer_downgrades_unsupported_confirmed_claim(self):
        row = {
            "topic": "Sem fonte",
            "insight": "Não pode continuar CONFIRMED sem evidência.",
            "truth_state": "CONFIRMED",
            "confidence_pct": 99,
            "created_at": "2026-09-25T12:00:00+00:00",
        }
        out = normalize_wisdom_entry(row)
        self.assertEqual(out["truth_state"], "UNKNOWN")
        self.assertFalse(out["automatic_rule_change"])
        self.assertFalse(out["real_orders_enabled"])

    def test_learning_episode_becomes_review_candidate_not_rule(self):
        episode = new_learning_episode(
            "USD após CPI",
            prediction="USD_UP",
            confidence_pct=70,
            evidence_refs=["calendar:cpi-1"],
            model_version="AION-test",
        )
        settled = settle_learning_episode(
            episode,
            actual_outcome="USD_UP",
            outcome_note="Resultado observado.",
            settled_at="2026-09-25T12:00:00+00:00",
        )
        candidate = candidate_from_learning_episode(
            settled,
            created_by="ADMIN",
        )
        self.assertEqual(candidate["truth_state"], "INFERENCE")
        self.assertTrue(candidate["manual_review_required"])
        self.assertFalse(candidate["automatic_promotion"])
        self.assertEqual(candidate["source_episode_ids"], [settled["episode_id"]])

    def test_review_due_and_summary(self):
        now = datetime(2026, 9, 25, 15, tzinfo=timezone.utc)
        past = (now - timedelta(days=1)).isoformat()
        future = (now + timedelta(days=30)).isoformat()
        due = new_wisdom_entry(
            "Macro",
            "Revisar esta lição.",
            truth_state="INFERENCE",
            evidence_refs=["ref:1"],
            review_due_at=past,
            created_at="2026-09-20T00:00:00+00:00",
        )
        current = new_wisdom_entry(
            "Segurança",
            "Guardian continua bloqueando ação automática.",
            truth_state="CONFIRMED",
            evidence_refs=["repo:test"],
            review_due_at=future,
            created_at="2026-09-20T00:00:01+00:00",
        )
        self.assertEqual(wisdom_review_state(due, now=now.isoformat()), "DUE")
        self.assertEqual(wisdom_review_state(current, now=now.isoformat()), "CURRENT")
        summary = wisdom_summary([due, current], now=now.isoformat())
        self.assertEqual(summary["review_due"], 1)
        self.assertEqual(summary["by_truth_state"]["CONFIRMED"], 1)

    def test_wisdom_evidence_downgrades_confirmed_when_review_not_current(self):
        current = new_wisdom_entry(
            "Regra da verdade",
            "Não promover ausência de evidência a fato.",
            truth_state="CONFIRMED",
            evidence_refs=["repo:truth-test"],
            review_due_at="2026-12-31T00:00:00+00:00",
            created_at="2026-09-20T00:00:00+00:00",
        )
        overdue = new_wisdom_entry(
            "Fonte antiga",
            "Lição historicamente validada que precisa revisão.",
            truth_state="CONFIRMED",
            evidence_refs=["docs:old-source"],
            review_due_at="2026-09-01T00:00:00+00:00",
            created_at="2026-08-01T00:00:00+00:00",
        )
        now = "2026-09-25T15:00:00+00:00"
        current_hit = wisdom_evidence_hits("verdade", [current], now=now)[0]
        old_hit = wisdom_evidence_hits("fonte antiga", [overdue], now=now)[0]
        self.assertEqual(current_hit["kind"], "CONFIRMED")
        self.assertEqual(current_hit["review_state"], "CURRENT")
        self.assertEqual(old_hit["kind"], "INFERENCE")
        self.assertEqual(old_hit["original_truth_state"], "CONFIRMED")
        self.assertEqual(old_hit["review_state"], "DUE")
        self.assertFalse(old_hit["current_market_fact"])

    def test_upsert_digest_search_and_checkpoint_integration(self):
        first = new_wisdom_entry(
            "Checkpoint Mestre",
            "A sabedoria precisa preservar origem, confiança e revisão.",
            truth_state="INFERENCE",
            evidence_refs=["docs:checkpoint"],
            applies_to=["memória", "AION"],
            created_at="2026-09-25T12:00:00+00:00",
        )
        rows = upsert_wisdom_entry([], first)
        self.assertEqual(len(rows), 1)
        self.assertEqual(wisdom_digest(rows), wisdom_digest(rows))
        hits = search_wisdom("checkpoint memoria", rows)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["wisdom_id"], first["wisdom_id"])

        checkpoint = update_wisdom_checkpoint(default_checkpoint(), entries=rows)
        normalized = ensure_operating_checkpoint(checkpoint)
        self.assertEqual(
            normalized["wisdom"]["entries"][0]["wisdom_id"],
            first["wisdom_id"],
        )
        self.assertEqual(normalized["wisdom"]["digest"], wisdom_digest(rows))
        self.assertGreaterEqual(normalized["checkpoint_version"], 8)


if __name__ == "__main__":
    unittest.main()
