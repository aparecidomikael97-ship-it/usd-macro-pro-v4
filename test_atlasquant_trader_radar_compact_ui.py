"""Contratos de apresentação do Trader Radar compacto, sem feeds externos."""
import re
import unittest
from datetime import datetime, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_radar_compact_ui import (
    PAGES, INDEX_GROUPS, _daily, central_entry_html, trader_radar_html,
)


def _fixture():
    return {
        "state": "VALIDATED_DAILY",
        "source": "Fixture offline",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "pairs": {
            pair: {"change_pct": index / 100, "bias": "ALTA"}
            for index, pair in enumerate(OFFICIAL_PAIRS)
        },
        "currencies": {
            code: {"change_pct": index / 10}
            for index, code in enumerate(CURRENCIES)
        },
        "indices": {
            "SPX500": {"change_pct": 0.4, "bias": "ALTA"},
            "WIN": {"change_pct": -0.2, "bias": "BAIXA"},
            "WDO": {"change_pct": 0.1, "bias": "ALTA"},
        },
    }


class TraderRadarCompactTests(unittest.TestCase):
    def test_menu_has_only_four_primary_sections(self):
        self.assertEqual(
            [label for _, label in PAGES],
            ["Início", "Radar", "Scanner Técnico", "Painel Mestre"],
        )
        self.assertIn('data-route="area:trader_radar"', central_entry_html())

    def test_no_data_is_never_presented_as_daily_quote_or_bias(self):
        html = trader_radar_html(selected="radar")
        self.assertIn("Dados diários ainda não conectados", html)
        self.assertIn("Top 10 aguardando", html)
        self.assertEqual(len(re.findall(r"<tr><td>", html)), 28)
        self.assertGreaterEqual(html.count("AGUARDANDO"), 28 + 8)
        self.assertEqual(html.count('data-state="top10-unavailable"'), 1)
        self.assertNotIn("Posição 10 · Sem par validado", html)
        self.assertNotIn("Fixture offline", html)

    def test_portuguese_ui_is_protected_from_browser_auto_translation(self):
        for page in ("home", "radar", "scanner", "master"):
            with self.subTest(page=page):
                html = trader_radar_html(selected=page)
                self.assertIn('class="ref-workspace aqr-shell notranslate"', html)
                self.assertIn('lang="pt-BR" translate="no"', html)
                self.assertIn('class="aqr-nav notranslate"', html)
                for title in ("Início", "Radar", "Scanner Técnico", "Painel Mestre"):
                    self.assertIn(title, html)
                self.assertNotIn("Não se trata de uma questão de", html)
                self.assertNotIn("Técnico de scanner", html)

    def test_compact_preview_layout_without_ten_large_empty_top_cards(self):
        html = trader_radar_html(selected="radar")
        self.assertIn("Visual v2: densidade da prévia aprovada", html)
        self.assertIn('.aqr-app{grid-template-columns:190px minmax(0,1fr)', html)
        self.assertIn(".aqr-currency{min-height:111px;padding:12px}", html)
        self.assertEqual(html.count('<article class="aqr-currency">'), 8)
        self.assertEqual(html.count('data-state="top10-unavailable"'), 1)
        self.assertNotIn("Posição 1 · Sem par validado", html)
        self.assertNotIn("class=\"aqr-tag up\"", html)
        self.assertIn("Top 10 aguardando", html)

    def test_complete_validated_universe_enables_real_ordering(self):
        data = _fixture()
        html = trader_radar_html(selected="radar", daily_data=data)
        self.assertIn("Fixture offline", html)
        self.assertIn("#1 " + OFFICIAL_PAIRS[-1], html)
        self.assertIn("#10 " + OFFICIAL_PAIRS[-10], html)
        self.assertIn("Última atualização:", html)
        self.assertEqual(len(_daily(data)["pairs"]), 28)
        self.assertEqual(len(_daily(data)["currencies"]), 8)

    def test_partial_universe_does_not_claim_top_ten(self):
        data = _fixture()
        data["pairs"].pop(OFFICIAL_PAIRS[0])
        html = trader_radar_html(selected="radar", daily_data=data)
        self.assertIn("Top 10 aguardando", html)
        self.assertNotIn("#1 ", html)

    def test_unvalidated_data_and_bad_numbers_fail_closed(self):
        data = _fixture()
        data["state"] = "UNVERIFIED"
        self.assertEqual(_daily(data)["pairs"], {})
        data["state"] = "VALIDATED_DAILY"
        data["pairs"][OFFICIAL_PAIRS[0]]["change_pct"] = float("nan")
        self.assertEqual(len(_daily(data)["pairs"]), 27)

    def test_indices_include_win_wdo_and_asia_not_ibovespa(self):
        groups = {region: {symbol for symbol, _ in assets} for region, assets in INDEX_GROUPS}
        self.assertEqual(groups["Brasil"], {"WIN", "WDO"})
        self.assertEqual(groups["Ásia"], {"NIKKEI225", "TOPIX", "HANGSENG", "CSI300", "KOSPI200"})
        html = trader_radar_html(selected="radar", daily_data=_fixture())
        self.assertIn("WIN · mini-índice", html)
        self.assertIn("WDO · minidólar", html)
        self.assertIn("Nikkei 225", html)
        self.assertNotIn("Ibovespa", html)

    def test_macro_is_global_and_impact_is_conditional(self):
        html = trader_radar_html(selected="master")
        self.assertIn("Macro", html)
        self.assertNotIn("Macro · EUA", html)
        self.assertIn("consenso", html)
        self.assertIn('data-local-tab="geo"', html)
        self.assertIn('data-local-tab="news"', html)


if __name__ == "__main__":
    unittest.main()
