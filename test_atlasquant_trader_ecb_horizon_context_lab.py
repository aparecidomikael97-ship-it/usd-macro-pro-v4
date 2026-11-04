"""ECB context can report past divergences, never claim a causal Forex bias."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_ecb_horizon_context_lab import (
    SCHEMA, EVIDENCE_REQUIRED_PER_CURRENCY, build_ecb_horizon_context_lab,
)
from test_atlasquant_trader_ecb_three_horizon_matrix_lab import (
    NOW, FIXES, sample, xml_history,
)


def dossier(raw=None, *, now=NOW):
    return build_ecb_horizon_context_lab(sample() if raw is None else raw, at=now)


def pair_row(out, pair):
    return next(x for x in out["pair_explanations"] if x["pair"] == pair)


class ECBHorizonContextLabTests(unittest.TestCase):
    def test_28_pairs_three_periods_and_eight_currencies(self):
        out = dossier()
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_CONTEXT_EXPOST_ONLY"))
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual({r["pair"] for r in out["pair_explanations"]},
                         set(OFFICIAL_PAIRS))
        self.assertEqual(set(out["currency_summaries"]), set(CURRENCIES))
        self.assertEqual(out["comparison_horizons"], ["D1", "W1", "MN1"])

    def test_clear_daily_weekly_monthly_disagreement_and_dates(self):
        out = dossier()
        row = pair_row(out, "EUR/USD")
        self.assertEqual(row["comparacao_d1_w1_mn1"],
                         "DIVERGENCIA_HISTORICA_ENTRE_HORIZONTES")
        self.assertEqual(row["historico"]["D1"]["relacao_passada"],
                         "COTADA_SUPEROU_NA_REFERENCIA")
        self.assertEqual(row["historico"]["W1"]["relacao_passada"],
                         "BASE_SUPEROU_NA_REFERENCIA")
        self.assertEqual(row["historico"]["MN1"]["de"], "2026-10-01")
        self.assertEqual(out["period_MN1"], "JANELA_MOVEL_30_DIAS_CORRIDOS")

    def test_reverse_pair_from_universe_keeps_correct_orientation(self):
        out = dossier()
        eurusd = pair_row(out, "EUR/USD")
        self.assertEqual((eurusd["base"], eurusd["quote"]), ("EUR", "USD"))
        self.assertLess(eurusd["historico"]["D1"]["variacao_referencia_pct"], 0)
        self.assertIn("USD", eurusd["fundamentos_a_investigar_por_moeda"])

    def test_insufficient_monthly_still_explicitly_abstains(self):
        raw = xml_history([
            ("2026-10-27", FIXES), ("2026-11-02", FIXES),
            ("2026-11-03", {**FIXES, "USD": 1.11}),
        ])
        out = dossier(raw)
        self.assertEqual(pair_row(out, "EUR/USD")["comparacao_d1_w1_mn1"],
                         "HISTORICO_INCOMPLETO")
        self.assertEqual(pair_row(out, "EUR/USD")["historico"]["MN1"]["relacao_passada"],
                         "HISTORICO_INSUFICIENTE")
        self.assertEqual(out["strongest_weakest_reference_only"]["MN1"]["state"],
                         "SEM_HISTORICO")

    def test_strongest_and_weakest_allow_ties(self):
        out = dossier()
        d = out["strongest_weakest_reference_only"]["D1"]
        self.assertEqual(d["state"], "EMPATE_DE_REFERENCIA")
        self.assertGreater(len(d["mais_fracas"]), 1)
        self.assertIn("USD", d["mais_fortes"])

    def test_stable_fixes_do_not_invent_unique_strong_currency(self):
        raw = xml_history([
            ("2026-10-01", FIXES), ("2026-10-27", FIXES),
            ("2026-11-02", FIXES), ("2026-11-03", FIXES),
        ])
        out = dossier(raw)
        for frame in ("D1", "W1", "MN1"):
            extremes = out["strongest_weakest_reference_only"][frame]
            self.assertEqual(set(extremes["mais_fortes"]), set(CURRENCIES))
            self.assertEqual(set(extremes["mais_fracas"]), set(CURRENCIES))
            self.assertEqual(pair_row(out, "EUR/USD")["historico"][frame]["relacao_passada"],
                             "SEM_DIFERENCA_NA_REFERENCIA")

    def test_no_macro_causality_or_independent_confirmation_is_inferred(self):
        out = dossier()
        self.assertFalse(out["cause_of_strength_verified"])
        self.assertFalse(out["overlapping_windows_are_independent_evidence"])
        self.assertFalse(out["independent_market_prices_verified"])
        for row in out["pair_explanations"]:
            self.assertTrue(row["janelas_sobrepostas_nao_sao_tres_confirmacoes"])
            self.assertEqual(row["porque_base_forte"], "SEM_EVIDENCIA_CAUSAL_VERIFICADA")
            self.assertTrue(row["precisa_preco_de_mercado_independente"])
            self.assertEqual(set(row["vies_operacional"].values()), {"AGUARDAR"})
            self.assertFalse(row["trade_authorized"])
        for c in out["currency_summaries"].values():
            self.assertFalse(c["fundamentals_verified"])
            self.assertEqual(c["evidencias_fundamentais_pendentes"],
                             list(EVIDENCE_REQUIRED_PER_CURRENCY))

    def test_stale_reference_clearly_labeled_not_live(self):
        late = datetime(2026, 12, 1, 20, tzinfo=timezone.utc)
        out = dossier(now=late)
        self.assertTrue(out["reference_outdated_over_four_days"])
        self.assertFalse(out["can_feed_live_radar"])
        self.assertFalse(out["publishable"])

    def test_corrupt_rate_future_fix_and_naive_clock_blocked(self):
        for raw in (b"<broken>", xml_history([
            ("2026-11-02", FIXES), ("2026-11-10", FIXES),
        ])):
            with self.subTest(raw=raw[:30]):
                out = dossier(raw)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["pair_explanations"], [])
        with self.assertRaises(ValueError):
            dossier(now=datetime(2026, 11, 4, 21))

    def test_no_cost_worker_or_trading(self):
        out = dossier()
        for flag in ("source_original_bytes_authenticated", "trade_authorized",
                     "worker_enabled", "scheduler_enabled", "publishable",
                     "can_feed_live_radar"):
            self.assertFalse(out[flag])
        self.assertEqual((out["external_http_requests"], out["new_cost_brl"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
