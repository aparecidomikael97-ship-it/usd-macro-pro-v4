"""The Panel Mestre explanation gate must never promote synthetic inputs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_explanation_release_gate_lab import (
    SCHEMA, build_explanation_release_gate_lab,
)
from atlasquant_trader_g8_context_completeness_3x_lab import DIMENSIONS
from test_atlasquant_trader_macro_causal_dossier_lab import context, macro
from test_atlasquant_trader_g8_context_completeness_3x_lab import capture
from test_atlasquant_trader_official_http_collection_contract_lab import NOW


def build(captures=None, receipts=None, news=None):
    return build_explanation_release_gate_lab(
        context() if news is None else news,
        [] if receipts is None else receipts,
        [] if captures is None else captures,
        at=NOW,
    )


def frame(result, pair="USD/JPY", horizon="D1"):
    return next(p for p in result["cards"] if p["pair"] == pair)["horizons"][horizon]


class ExplanationGateLabTests(unittest.TestCase):
    def test_all_eight_currencies_twenty_eight_pairs_three_horizons_wait(self):
        result = build()
        self.assertEqual((result["schema"], result["state"]),
                         (SCHEMA, "LAB_EXPLANATION_GATE_CLOSED"))
        self.assertEqual((result["currency_count"], result["pair_count"],
                          result["horizon_card_count"]), (8, 28, 84))
        self.assertEqual({p["pair"] for p in result["cards"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(set(result["required_context_dimensions"]), set(DIMENSIONS))
        for card in result["cards"]:
            self.assertEqual(set(card["horizons"]), {"D1", "W1", "MN1"})
            self.assertFalse(card["trade_authorized"])
            for horizon in card["horizons"].values():
                self.assertEqual(horizon["bias"], "AGUARDAR")
                self.assertEqual(horizon["why_base_stronger_or_weaker"], "NAO_COMPROVADO")
                self.assertFalse(horizon["can_show_as_verified_bias"])
                self.assertFalse(horizon["macro_causation_verified"])

    def test_no_capture_exposes_all_nine_missing_dimensions_by_both_currencies(self):
        result = build()
        usd_jpy = frame(result)
        self.assertEqual(usd_jpy["missing_dimensions"]["USD"], list(DIMENSIONS))
        self.assertEqual(usd_jpy["missing_dimensions"]["JPY"], list(DIMENSIONS))
        self.assertIn("NENHUMA_COLETA_DOCUMENTAL_FORNECIDA", usd_jpy["blockers"])
        self.assertIn("USD_DIMENSOES_AUSENTES", usd_jpy["blockers"])
        self.assertIn("JPY_DIMENSOES_AUSENTES", usd_jpy["blockers"])
        self.assertEqual(result["daily_documentary_captures_claimed"], 0)
        self.assertEqual(len(result["planned_slots"]), 3)

    def test_synthetic_cpi_surprise_is_not_usd_jpy_bullish_or_bearish(self):
        result = build(receipts=[macro()])
        for horizon in ("D1", "W1", "MN1"):
            pair = frame(result, horizon=horizon)
            self.assertEqual(pair["macro_synthetic_release_claim_count"], 1)
            self.assertTrue(pair["synthetic_surprises_not_currency_direction"])
            self.assertEqual(pair["bias"], "AGUARDAR")
        self.assertEqual(frame(result, "EUR/JPY")["macro_synthetic_release_claim_count"], 0)

    def test_full_documentary_snapshot_does_not_mean_authenticated_sources(self):
        result = build(captures=[capture(0, all_documented=True)])
        pair = frame(result)
        self.assertEqual(result["daily_documentary_captures_claimed"], 1)
        self.assertEqual(pair["missing_dimensions"]["USD"], [])
        self.assertEqual(pair["missing_dimensions"]["JPY"], [])
        self.assertIn("ORIGEM_DAS_FONTES_NAO_AUTENTICADA", pair["blockers"])
        self.assertIn("EXECUCOES_DIARIAS_SEM_COMPROVANTE_INDEPENDENTE", pair["blockers"])
        self.assertFalse(result["source_originals_attested"])
        self.assertFalse(result["three_daily_updates_verified"])
        self.assertEqual(pair["explanation_state"], "NAO_PUBLICAVEL_COMO_FATO")

    def test_older_than_forty_eight_hours_is_not_treated_as_fresh(self):
        c = capture(0, all_documented=True)
        c["currency_dimensions"]["JPY"]["GEOPOLITICS"]["source_checked_at_utc"] = (
            "2026-11-02T08:00:00Z"
        )
        pair = frame(build(captures=[c]))
        self.assertEqual(pair["older_than_48h_checks"]["JPY"], ["GEOPOLITICS"])
        self.assertIn("JPY_FONTES_COM_VERIFICACAO_ANTIGA", pair["blockers"])

    def test_mixed_synthetic_surprises_are_not_counterevidence_verified(self):
        a = macro(event="USD_CPI_ABOVE", actual=2.6, consensus=2.3)
        b = macro(event="USD_ACTIVITY_BELOW", indicator="GDP", actual=1.0, consensus=2.3)
        result = build(receipts=[a, b])
        self.assertTrue(frame(result)["synthetic_surprise_signs_mixed"])
        self.assertEqual(frame(result)["independent_counterevidence"], "PENDENTE")
        self.assertFalse(result["contrary_evidence_independently_reviewed"])

    def test_cannot_claim_future_capture_was_completed(self):
        result = build(captures=[capture(0), capture(2)])
        self.assertEqual(result["state"], "LAB_BLOCKED")
        self.assertEqual(result["reason"], "UNSAFE_THREE_DAILY_DOCUMENTARY_COVERAGE")
        self.assertEqual(result["cards"], [])

    def test_poisoned_input_reports_and_receipts_fail_closed(self):
        fake_news = context()
        fake_news["rows"][0]["horizons"]["D1"]["operational_bias"] = "ALTA"
        bad_news = build(news=fake_news)
        self.assertEqual(bad_news["state"], "LAB_BLOCKED")
        self.assertEqual(bad_news["reason"], "UNSAFE_MACRO_CAUSAL_EVIDENCE")
        bad_receipt = macro()
        bad_receipt["trade_authorized"] = True
        self.assertEqual(build(receipts=[bad_receipt])["state"], "LAB_BLOCKED")
        bad_capture = capture(0)
        bad_capture["real_data_verified"] = True
        self.assertEqual(build(captures=[bad_capture])["state"], "LAB_BLOCKED")

    def test_garbage_and_unbounded_captures_fail_closed(self):
        for caps in ("not-a-list", [capture(0)] * 4, [{}]):
            with self.subTest(caps=caps):
                out = build(captures=caps)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["publishable"])
                self.assertFalse(out["trade_authorized"])

    def test_inputs_are_not_modified(self):
        n, m, c = context(), [macro()], [capture(0, all_documented=True)]
        before = deepcopy((n, m, c))
        result = build_explanation_release_gate_lab(n, m, c, at=NOW)
        self.assertEqual((n, m, c), before)
        self.assertEqual(result["state"], "LAB_EXPLANATION_GATE_CLOSED")

    def test_must_use_aware_datetime(self):
        with self.assertRaises(ValueError):
            build_explanation_release_gate_lab(context(), [], [],
                                               at=datetime(2026, 11, 4, 12))

    def test_zero_new_cost_no_worker_scheduler_or_live_promotion(self):
        result = build(captures=[capture(0, all_documented=True)],
                       receipts=[macro(currency="JPY", event="JPY_CPI_TEST")])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["can_feed_live_radar"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["real_time_news_verified"])
        self.assertFalse(result["real_time_calendar_verified"])
        self.assertFalse(result["relative_strength_independently_verified"])
        self.assertEqual(result["external_http_requests"], 0)
        self.assertEqual(result["new_cost_brl"], 0)


if __name__ == "__main__":
    unittest.main()
