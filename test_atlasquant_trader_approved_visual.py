"""Contratos de paridade visual AtlasQuant Trader e segurança do filtro de abertura."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_radar_compact_ui import (
    _opening_score, trader_radar_html,
)


class TraderApprovedVisualTests(unittest.TestCase):
    def test_all_four_pages_use_approved_sidebar_and_hero(self):
        expected = {
            "home": "Seu mercado. Uma visão clara.",
            "radar": "Onde o mercado está se movendo.",
            "scanner": "Do contexto à oportunidade.",
            "master": "Entenda o porquê do movimento.",
        }
        for page, title in expected.items():
            with self.subTest(page=page):
                html = trader_radar_html(selected=page, name="M")
                self.assertIn('data-visual-reference="approved-20261102-v1"', html)
                self.assertIn('class="aqr-aside"', html)
                self.assertIn("PAINEL DE CONTROLE", html)
                self.assertIn("PRÉVIA PRIVADA", html)
                self.assertIn("DADOS NÃO CONECTADOS", html)
                self.assertIn("VISUALIZAÇÃO", html)
                self.assertIn("28 PARES FOREX", html)
                self.assertIn("8 MOEDAS", html)
                self.assertIn(title, html)
                for route in ("home", "radar", "scanner", "master"):
                    self.assertIn('data-route="' + route + '"', html)
                self.assertNotIn("Execução automática habilitada", html)

    def test_home_has_reference_panorama_and_flow(self):
        html = trader_radar_html(selected="home")
        for label in ("Panorama do mercado", "Fluxo de análise",
                      "Moeda mais forte", "Melhor par do dia",
                      "Próximo evento", "Avisos econômicos"):
            self.assertIn(label, html)

    def test_radar_region_filters_and_opening_under_brazil(self):
        html = trader_radar_html(selected="radar")
        for key in ("all", "us", "br", "eu", "asia"):
            self.assertIn('data-local-tab="' + key + '"', html)
            self.assertIn('data-tab-panel="' + key + '"', html)
        brazil_start = html.index('<h3>Brasil</h3>')
        win = html.index("WIN · mini-índice", brazil_start)
        wdo = html.index("WDO · minidólar", win)
        opening = html.index("Estratégia de Abertura", wdo)
        self.assertLess(brazil_start, win)
        self.assertLess(win, wdo)
        self.assertLess(wdo, opening)
        self.assertIn("Índice de Volatilidade S&amp;P 500", html)
        self.assertIn("SGX IODEX Iron Ore Futures", html)
        self.assertIn("Futuros de petróleo leve bruto", html)
        self.assertIn("WDO:</strong>", html)
        self.assertIn("− variação % do VIX", html)
        self.assertNotIn("Ibovespa", html)
        self.assertNotIn("Score: +", html)

    def test_opening_score_fails_closed(self):
        stamp = datetime(2026, 11, 2, 8, 55, tzinfo=timezone(timedelta(hours=-3)))
        valid = {
            "state": "VALIDATED_OPENING", "source": "Laboratório offline",
            "as_of": stamp.isoformat(), "vix_pct": -0.5,
            "iron_pct": 1.2, "oil_pct": 2.0,
        }
        self.assertIsNone(_opening_score(None, at=stamp))
        self.assertIsNone(_opening_score({**valid, "state": "DRAFT"}, at=stamp))
        self.assertIsNone(_opening_score({**valid, "source": ""}, at=stamp))
        self.assertIsNone(_opening_score({**valid, "oil_pct": float("nan")}, at=stamp))
        self.assertIsNone(_opening_score({**valid, "as_of": "sem fuso"}, at=stamp))
        self.assertIsNone(_opening_score(valid, at=stamp + timedelta(hours=7)))
        self.assertIsNone(_opening_score(valid, at=stamp - timedelta(minutes=6)))
        wrong_time = stamp.replace(hour=10)
        self.assertIsNone(_opening_score({**valid, "as_of": wrong_time.isoformat()}, at=wrong_time))

    def test_opening_score_is_exploratory_and_vix_is_inverted(self):
        stamp = datetime(2026, 11, 2, 8, 55, tzinfo=timezone(timedelta(hours=-3)))
        valid = {
            "state": "VALIDATED_OPENING", "source": "Laboratório offline",
            "as_of": stamp.isoformat(), "vix_pct": -0.5,
            "iron_pct": 1.2, "oil_pct": 2.0,
        }
        score = _opening_score(valid, at=stamp)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score["score"], 3.7)
        self.assertEqual(score["side"], "Comprador")
        self.assertEqual(score["level"], "Moderado")
        valid["vix_pct"] = 7.0
        negative = _opening_score(valid, at=stamp)
        self.assertAlmostEqual(negative["score"], -3.8)
        self.assertEqual(negative["side"], "Vendedor")

    def test_master_keeps_macro_micro_geo_news_and_calendar(self):
        html = trader_radar_html(selected="master")
        for title in ("Cenário macro", "Bancos centrais",
                      "Risco geopolítico", "Notícias relevantes",
                      "Economia global", "Setores e empresas",
                      "Calendário econômico", "Guia de impacto"):
            self.assertIn(title, html)
        self.assertIn('data-local-tab="geo"', html)
        self.assertIn('data-local-tab="news"', html)


if __name__ == "__main__":
    unittest.main()
