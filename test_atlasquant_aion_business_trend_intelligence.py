import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_business_trend_intelligence import (
    evaluate_opportunity,
    improvement_review,
    normalize_evidence,
    rank_opportunities,
    trend_watch_posture,
)


NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _opportunity(**updates):
    data = {
        "name": "Recuperação de leads por IA",
        "segment": "Clínica",
        "problem": "Leads pedem informação e somem sem follow-up.",
        "offer": "Qualificação + follow-up + Radar de conversão.",
        "demand_signal": 82,
        "pain_intensity": 88,
        "recurring_revenue_fit": 90,
        "margin_potential": 76,
        "implementation_complexity": 45,
        "support_load": 35,
        "strategic_fit": 92,
    }
    data.update(updates)
    return data


def _evidence(source, confidence=80, source_kind="PUBLIC_WEB", observed_at="2026-09-28T12:00:00Z"):
    return {
        "source_kind": source_kind,
        "source": source,
        "claim": "Há demanda observável por resposta e follow-up mais rápidos.",
        "segment": "Clínica",
        "observed_at": observed_at,
        "confidence": confidence,
    }


class BusinessTrendOpportunityIntelligenceTests(unittest.TestCase):
    def test_fresh_supported_evidence_is_normalized(self):
        row = normalize_evidence(_evidence("Fonte A"), now=NOW)
        self.assertEqual(row["truth_state"], "EVIDENCE_SUPPORTED")
        self.assertTrue(row["fresh"])
        self.assertTrue(row["complete"])
        self.assertFalse(row["demo"])

    def test_stale_or_incomplete_evidence_cannot_be_supported(self):
        stale = normalize_evidence(_evidence("Fonte A", observed_at="2026-07-01T12:00:00Z"), now=NOW)
        self.assertEqual(stale["truth_state"], "STALE")
        self.assertFalse(stale["fresh"])
        incomplete = normalize_evidence({"source_kind": "PUBLIC_WEB"}, now=NOW)
        self.assertEqual(incomplete["truth_state"], "INSUFFICIENT")
        self.assertFalse(incomplete["complete"])

    def test_strong_candidate_requires_good_score_and_supported_sources(self):
        result = evaluate_opportunity(
            _opportunity(),
            [_evidence("Fonte A"), _evidence("Fonte B", confidence=75)],
            now=NOW,
        )
        self.assertEqual(result["state"], "STRONG_CANDIDATE")
        self.assertEqual(result["truth_state"], "EVIDENCE_SUPPORTED")
        self.assertGreaterEqual(result["score"], 80)
        self.assertEqual(result["supported_source_count"], 2)
        self.assertFalse(result["automatic_launch"])
        self.assertFalse(result["automatic_spend"])
        self.assertFalse(result["automatic_publication"])
        self.assertFalse(result["automatic_client_contact"])
        self.assertFalse(result["runtime_activated"])
        self.assertFalse(result["executes_action"])

    def test_demo_fixture_can_rank_for_training_but_remains_demo_truth(self):
        result = evaluate_opportunity(
            _opportunity(),
            [_evidence("Fixture", source_kind="DEMO_FIXTURE")],
            now=NOW,
        )
        self.assertIn(result["state"], {"CANDIDATE", "STRONG_CANDIDATE"})
        self.assertEqual(result["truth_state"], "DEMO")
        self.assertEqual(result["evidence_quality"], "DEMO_ONLY")
        self.assertEqual(result["supported_source_count"], 0)
        self.assertEqual(result["demo_source_count"], 1)

    def test_missing_evidence_blocks_confirmation_even_with_high_raw_signals(self):
        result = evaluate_opportunity(_opportunity(), [], now=NOW)
        self.assertIn(result["state"], {"WATCH", "BLOCKED"})
        self.assertEqual(result["truth_state"], "INSUFFICIENT")
        self.assertFalse(result["automatic_launch"])

    def test_incomplete_opportunity_fails_closed(self):
        result = evaluate_opportunity({"name": "x"}, [], now=NOW)
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "INCOMPLETE_OPPORTUNITY")
        self.assertIsNone(result["score"])

    def test_ranking_prefers_state_then_score(self):
        a = evaluate_opportunity(_opportunity(name="A"), [_evidence("A1"), _evidence("A2")], now=NOW)
        b = evaluate_opportunity(_opportunity(name="B", demand_signal=60), [_evidence("B1")], now=NOW)
        ranked = rank_opportunities([b, a])
        self.assertEqual(ranked[0]["opportunity"]["name"], "A")
        self.assertGreaterEqual(len(ranked), 1)

    def test_improvement_requires_sample_and_never_promotes_automatically(self):
        insufficient = improvement_review(
            hypothesis="Follow-up mais rápido melhora agendamento.",
            metric_name="agendamentos",
            before_value=10,
            after_value=15,
            sample_size=5,
        )
        self.assertEqual(insufficient["state"], "INSUFFICIENT_EVIDENCE")
        supported = improvement_review(
            hypothesis="Follow-up mais rápido melhora agendamento.",
            metric_name="agendamentos",
            before_value=100,
            after_value=112,
            sample_size=80,
        )
        self.assertEqual(supported["state"], "IMPROVEMENT_SUPPORTED")
        self.assertTrue(supported["eligible_for_promotion_review"])
        self.assertFalse(supported["automatic_promotion"])
        self.assertFalse(supported["automatic_deploy"])
        self.assertFalse(supported["executes_action"])

    def test_regression_is_detected_for_lower_is_better_metric(self):
        result = improvement_review(
            hypothesis="Automação reduz tempo de resposta.",
            metric_name="tempo_resposta_min",
            before_value=10,
            after_value=15,
            sample_size=100,
            higher_is_better=False,
        )
        self.assertEqual(result["state"], "REGRESSION_OBSERVED")
        self.assertFalse(result["eligible_for_promotion_review"])

    def test_watch_posture_requires_future_authorized_collector(self):
        result = evaluate_opportunity(
            _opportunity(),
            [_evidence("Fonte A"), _evidence("Fonte B")],
            now=NOW,
        )
        posture = trend_watch_posture([result])
        self.assertEqual(posture["state"], "REVIEW_AVAILABLE")
        self.assertTrue(posture["continuous_monitoring_desired"])
        self.assertFalse(posture["current_runtime_monitoring_enabled"])
        self.assertTrue(posture["requires_authorized_upstream_collector"])
        self.assertFalse(posture["automatic_launch"])

    def test_module_has_no_network_provider_or_ui_imports(self):
        source = Path("atlasquant_aion_business_trend_intelligence.py").read_text(encoding="utf-8")
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
