"""Synthetic regression suite — does not authenticate live news or authorize trades."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta

from atlasquant_position_event_manager import EventContext, PositionContext
from atlasquant_position_news_audit_lab import (
    NewsReleaseEvidence,
    audit_news_for_open_position,
)

UTC = timezone.utc
PUBLISHED = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)
DECIDED = datetime(2026, 9, 4, 12, 34, tzinfo=UTC)


def evidence(**changes):
    initial = NewsReleaseEvidence(
        event_id="synthetic-us-employment-2026-09",
        indicator="NFP",
        currency="USD",
        reference_period="2026-08",
        unit="milhares de empregos",
        previous=133,
        consensus=145,
        actual=160,
        tolerance=5,
        scheduled_at=PUBLISHED,
        consensus_captured_at=PUBLISHED - timedelta(hours=3),
        published_at=PUBLISHED,
        captured_at=PUBLISHED + timedelta(seconds=40),
        source_release_url="https://www.bls.gov/synthetic-only",
        source_consensus_url="https://example.org/synthetic-consensus",
        release_document_reviewed=True,
        consensus_vintage_reviewed=True,
        revisions_reviewed=True,
        economic_context_reviewed=True,
        currency_effect_reviewed=True,
        currency_effect_hypothesis="SUPPORTIVE",
    )
    return replace(initial, **changes)


def position(side="LONG", base="EUR", quote="USD"):
    return PositionContext(
        pair=base + quote, base_currency=base, quote_currency=quote,
        side=side, horizon="M15", unrealized_r=1.0,
    )


def event(currency="USD"):
    return EventContext(
        name="Synthetic NFP", currency=currency,
        impact="HIGH", minutes_to_event=-4.0,
    )


class PositionNewsAuditLabTests(unittest.TestCase):
    def run_case(self, side="LONG", *, event_currency="USD", base="EUR", quote="USD",
                 release=None, instant=DECIDED):
        return audit_news_for_open_position(
            position(side, base, quote), event(event_currency),
            release if release is not None else evidence(currency=event_currency),
            as_of=instant,
        )

    def assert_never_trades(self, report):
        self.assertIsNone(report["broker_command"])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["can_feed_live_radar"])
        self.assertIsNone(report["probability_of_move_against_position"])
        self.assertIsNone(report["market_reaction_probability"])

    def test_short_eurusd_usd_supportive_is_conditional_alignment(self):
        report = self.run_case("SHORT")
        self.assertEqual(report["economic_surprise_class"], "ABOVE")
        self.assertEqual(report["surprise_vs_consensus"], "15")
        self.assertEqual(report["conditional_thesis"], "EVENT_ALIGNED_WITH_POSITION")
        self.assertEqual(report["management_review"], "REAVALIAR_MANUTENCAO_COM_RISCO")
        self.assertEqual(report["state"], "HIPOTESE_DOCUMENTAL_PARA_REVISAO")
        self.assert_never_trades(report)

    def test_long_eurusd_usd_supportive_conflicts_requiring_review(self):
        report = self.run_case("LONG")
        self.assertEqual(report["relative_exposure"], -1)
        self.assertEqual(report["conditional_thesis"], "EVENT_CONFLICTS_WITH_POSITION")
        self.assertEqual(report["management_review"], "REAVALIAR_SAIDA_STOP_E_TESE")
        self.assert_never_trades(report)

    def test_base_currency_supportive_aligns_with_long(self):
        report = self.run_case("LONG", event_currency="USD",
                               base="USD", quote="JPY")
        self.assertEqual(report["relative_exposure"], 1)
        self.assertEqual(report["conditional_thesis"], "EVENT_ALIGNED_WITH_POSITION")
        self.assert_never_trades(report)

    def test_same_surprise_class_can_have_opposite_macro_hypothesis(self):
        report = self.run_case("LONG", release=evidence(
            currency_effect_hypothesis="ADVERSE"))
        self.assertEqual(report["economic_surprise_class"], "ABOVE")
        self.assertEqual(report["conditional_thesis"], "EVENT_ALIGNED_WITH_POSITION")
        self.assert_never_trades(report)

    def test_below_consensus_is_not_assumed_to_mean_currency_down(self):
        report = self.run_case("SHORT", release=evidence(
            actual=120, currency_effect_hypothesis="SUPPORTIVE"))
        self.assertEqual(report["economic_surprise_class"], "BELOW")
        self.assertEqual(report["conditional_thesis"], "EVENT_ALIGNED_WITH_POSITION")
        self.assert_never_trades(report)

    def test_unknown_macro_effect_has_no_fake_alignment(self):
        report = self.run_case("SHORT", release=evidence(
            currency_effect_hypothesis="UNCERTAIN"))
        self.assertEqual(report["state"], "AGUARDAR_EVIDENCIA")
        self.assertEqual(report["conditional_thesis"], "REASSESS")
        self.assertIn("DIRECAO_ECONOMICA_INDETERMINADA", report["blockers"])
        self.assert_never_trades(report)

    def test_missing_review_blocks_even_if_direction_is_supportive(self):
        report = self.run_case("SHORT", release=evidence(
            consensus_vintage_reviewed=False, revisions_reviewed=False))
        self.assertEqual(report["state"], "AGUARDAR_EVIDENCIA")
        self.assertIn("VINTAGE_CONSENSO_NAO_REVISADA", report["blockers"])
        self.assertEqual(report["conditional_thesis"], "REASSESS")
        self.assert_never_trades(report)

    def test_future_capture_cannot_backfill_earlier_decision(self):
        report = self.run_case("SHORT", instant=PUBLISHED)
        self.assertIn("ORDEM_TEMPORAL_OU_LOOKAHEAD_INVALIDO", report["blockers"])
        self.assertEqual(report["conditional_thesis"], "REASSESS")
        self.assert_never_trades(report)

    def test_consensus_observed_after_release_is_invalid(self):
        report = self.run_case("SHORT", release=evidence(
            consensus_captured_at=PUBLISHED + timedelta(seconds=1)))
        self.assertIn("CONSENSO_SEM_VINTAGE_PRE_RELEASE", report["blockers"])
        self.assertEqual(report["state"], "AGUARDAR_EVIDENCIA")
        self.assert_never_trades(report)

    def test_missing_numbers_and_nan_never_generate_direction(self):
        for value in (None, float("nan"), float("inf"), True):
            report = self.run_case("SHORT", release=evidence(actual=value))
            self.assertIn("NUMEROS_INCOMPLETOS_OU_INVALIDOS", report["blockers"])
            self.assertIsNone(report["economic_surprise_class"])
            self.assertEqual(report["conditional_thesis"], "REASSESS")
            self.assert_never_trades(report)

    def test_unrelated_event_does_not_change_thesis(self):
        report = self.run_case("LONG", event_currency="JPY",
                               release=evidence(currency="JPY"))
        self.assertEqual(report["state"], "EVENTO_NAO_DIRETAMENTE_RELACIONADO")
        self.assertEqual(report["conditional_thesis"], "NOT_RELEVANT")
        self.assert_never_trades(report)

    def test_inconsistent_pair_or_naive_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "par inconsistente"):
            audit_news_for_open_position(
                PositionContext("EURJPY", "EUR", "USD", "LONG", "M15"),
                event(), evidence(), as_of=DECIDED)
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.run_case("LONG", instant=DECIDED.replace(tzinfo=None))

    def test_invalid_source_and_event_mismatch_fail_closed(self):
        report = self.run_case("SHORT", release=evidence(
            source_consensus_url="unverified"))
        self.assertIn("FONTE_CONSENSO_NAO_DOCUMENTADA", report["blockers"])
        self.assert_never_trades(report)
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            self.run_case("SHORT", release=evidence(currency="NZD"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
