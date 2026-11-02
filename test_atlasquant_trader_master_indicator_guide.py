"""Indicator-specific macro explanations, scenario polarity and safe unknowns."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_master_indicator_guide import indicator_guide
from atlasquant_trader_economic_calendar import normalize_events, explanation
from atlasquant_trader_calendar_ui import calendar_html
from atlasquant_trader_master_briefing_v2 import build_master_briefing
from atlasquant_trader_master_briefing_ui import master_week_html

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 2, 8, 45, tzinfo=BRT)


def _row(title, *, when=None, country="US", consensus=3.2, previous=3.1, actual=None):
    stamp = when or NOW.replace(hour=9, minute=30)
    return {
        "type": title, "country": country, "comparison": "yoy",
        "period": "Teste", "estimate": consensus, "previous": previous,
        "actual": actual, "date": stamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _normalize(*rows, at=NOW):
    return normalize_events({"ok": True, "fetched_at": at.isoformat(),
                             "data": list(rows)}, at=at)


class IndicatorSpecificGuideTests(unittest.TestCase):
    def test_specific_indicators_not_mistaken_for_generic_ones(self):
        examples = [
            ("Core CPI", "us_core_inflation"),
            ("Core PCE", "us_core_inflation"),
            ("PCE Price Index", "pce"),
            ("Consumer Price Index CPI", "cpi"),
            ("Producer Price Index PPI", "producer_prices"),
            ("IPCA-15", "ipca"),
            ("HICP", "hicp"),
            ("Unemployment Rate", "unemployment"),
            ("Initial Jobless Claims", "jobless_claims"),
            ("Nonfarm Payrolls", "nfp"),
            ("ADP Employment Change", "adp"),
            ("JOLTS Job Openings", "jolts"),
            ("Average Hourly Earnings", "wages"),
            ("FOMC Interest Rate Decision", "fomc"),
            ("COPOM Selic", "selic"),
            ("ECB Interest Rate Decision", "bank_rates"),
            ("ISM Manufacturing PMI", "pmi"),
            ("GDP QoQ", "gdp"),
            ("Retail Sales", "retail"),
            ("Industrial Production", "industrial"),
            ("Durable Goods Orders", "durables"),
            ("Housing Starts", "housing"),
            ("Consumer Confidence", "confidence"),
            ("Trade Balance", "trade_balance"),
            ("EIA Crude Oil Inventories", "oil_inventory"),
        ]
        for name, expected in examples:
            with self.subTest(name=name):
                guide = indicator_guide(name)
                self.assertEqual(guide["key"], expected)
                self.assertTrue(guide["mechanism"])
                self.assertTrue(guide["watch"])
                self.assertTrue(guide["caution"])

    def test_unemployment_and_jobless_claims_higher_not_positive_employment(self):
        for name in ("Unemployment Rate", "Initial Jobless Claims"):
            with self.subTest(name=name):
                guide = indicator_guide(name)
                self.assertIn("fraco", guide["above"].lower())
                self.assertNotIn("emprego mais forte", guide["above"].lower())

    def test_pmi_surprise_is_not_expansion_above_50(self):
        guide = indicator_guide("ISM Manufacturing PMI")
        self.assertIn("50", guide["mechanism"])
        self.assertIn("não significa expansão", guide["caution"])

    def test_trade_balance_ambiguous_even_if_above_consensus(self):
        guide = indicator_guide("Trade Balance")
        self.assertIn("não implica moeda mais forte", guide["above"])
        self.assertIn("INDETERMINADA", guide["caution"])

    def test_adp_does_not_fabricate_nfp_outcome(self):
        guide = indicator_guide("ADP Employment Change")
        self.assertIn("não é o Payroll oficial", guide["mechanism"])
        self.assertIn("não autoriza antecipar", guide["above"])

    def test_unrecognized_remains_indeterminate(self):
        guide = indicator_guide("XYZ Synthetic Unknown Metric")
        self.assertEqual(guide["key"], "unknown")
        self.assertIn("Não há efeito direcional", guide["above"])
        self.assertEqual(guide["certainty"], "CONDICIONAL · SEM VIÉS")

    def test_known_cpi_keeps_numeric_surprise_and_usd_context(self):
        at = NOW.replace(hour=9, minute=42)
        model = _normalize(_row("Consumer Price Index CPI", actual=3.5), at=at)
        event = model["events"][0]
        self.assertAlmostEqual(event["surprise"], 0.3)
        guide = explanation(event)
        self.assertEqual(guide["guide_key"], "cpi")
        self.assertIn("USD", guide["result"])
        self.assertIn("Treasury", guide["dollar"])
        self.assertIn("Como este indicador funciona", calendar_html(model)
                      if False else "Como este indicador funciona")
        markup = calendar_html(model)
        self.assertIn("Como este indicador funciona", markup)
        self.assertIn("O que acompanhar", markup)
        self.assertIn("Limite da interpretação", markup)
        self.assertNotIn("recomendação de compra", markup.lower())

    def test_unknown_html_never_makes_directional_claim(self):
        data = _normalize(_row("Unknown Metric ABC"))
        expl = explanation(data["events"][0])
        self.assertEqual(expl["guide_key"], "unknown")
        self.assertIn("Não há efeito direcional", expl["above"])
        self.assertIn("SEM VIÉS", expl["certainty"])

    def test_weekly_evidence_contains_specific_mechanics(self):
        data = _normalize(_row("ISM Manufacturing PMI", when=NOW + timedelta(days=1)))
        model = build_master_briefing(data, at=NOW)
        self.assertEqual(model["state"], "VALIDADO")
        self.assertEqual(model["week_preview"][0]["mechanism"],
                         indicator_guide("ISM Manufacturing PMI")["mechanism"])
        html = master_week_html(data, at=NOW)
        self.assertIn("O que mede:", html)
        self.assertIn("O que observar:", html)
        self.assertIn("Acima do consenso:", html)

    def test_no_live_feed_no_fabricated_market_numbers(self):
        guide = indicator_guide("IPCA")
        self.assertNotIn("IPCA atual:", guide["mechanism"])
        self.assertNotIn("85%", str(guide))
        self.assertNotIn("ordem", str(guide).lower())


if __name__ == "__main__":
    unittest.main()
