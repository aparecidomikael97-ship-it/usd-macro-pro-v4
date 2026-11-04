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
    def test_menu_has_only_three_primary_sections(self):
        self.assertEqual(
            [label for _, label in PAGES],
            ["Início", "Radar", "Painel Mestre"],
        )
        for page in ("home", "radar", "master"):
            self.assertNotIn('data-route="scanner"', trader_radar_html(selected=page))
        self.assertIn('data-route="area:trader_radar"', central_entry_html())

    def test_no_data_is_never_presented_as_daily_quote_or_bias(self):
        html = trader_radar_html(selected="radar")
        self.assertIn("Dados diários ainda não conectados", html)
        self.assertIn("Top 10 aguardando", html)
        self.assertEqual(len(re.findall(r"<tr><td>", html)), 28)  # apenas 28 linhas na matriz recolhível
        self.assertIn('<details class="aqr-section aqr-matrix"', html)
        self.assertNotIn("Os 28 pares Forex", html)
        self.assertEqual(html.count('data-state="top10-unavailable"'), 1)
        self.assertNotIn("Posição 10 · Sem par validado", html)
        self.assertNotIn("Fixture offline", html)

    def test_portuguese_ui_is_protected_from_browser_auto_translation(self):
        for page in ("home", "radar", "master"):
            with self.subTest(page=page):
                html = trader_radar_html(selected=page)
                self.assertIn('class="ref-workspace aqr-shell notranslate"', html)
                self.assertIn('lang="pt-BR" translate="no"', html)
                self.assertIn('class="aqr-nav notranslate"', html)
                for title in ("Início", "Radar", "Painel Mestre"):
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

    def test_partial_28_universe_blocks_complete_g8_strength_display(self):
        from atlasquant_trader_radar_compact_ui import _currencies_approved
        data = _fixture()
        data["pairs"].pop(OFFICIAL_PAIRS[0])
        panel = _currencies_approved(_daily(data))
        self.assertEqual(panel.count("AGUARDANDO"), 8)
        self.assertNotIn("VALIDADO", panel)
        self.assertNotIn("+0,70%", panel)

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

    def test_reference_routes_all_four_evidence_inputs_to_master(self):
        """Protect the exact parameter bridge reconciled from main and PR 1803."""
        from unittest.mock import patch
        from atlasquant_reference_ui import reference_html

        daily = {"state": "NO_DATA"}
        calendar = {"state": "UNVERIFIED"}
        bias = {"state": "NO_DATA"}
        news = {"state": "UNVERIFIED"}
        official = {"state": "UNVERIFIED"}
        with patch("atlasquant_trader_radar_compact_ui.trader_radar_html",
                   return_value="LAB_MASTER_VIEW") as renderer:
            result = reference_html(
                "trader_radar", selected="master", name="Teste",
                show_central=False, daily_data=daily, calendar_data=calendar,
                bias_evidence=bias, news_data=news, official_data=official,
            )
        self.assertEqual(result, "LAB_MASTER_VIEW")
        renderer.assert_called_once_with(
            selected="master", name="Teste", show_central=False,
            daily_data=daily, calendar_data=calendar,
            bias_evidence=bias, news_data=news, official_data=official,
        )

    def test_merged_trader_keeps_three_pages_win_and_evidence_panel(self):
        """No phantom fourth navigation, no automatic execution claims."""
        from atlasquant_reference_ui import reference_html

        radar = reference_html("trader_radar", selected="radar", name="Teste",
                               show_central=False)
        master = reference_html("trader_radar", selected="master", name="Teste",
                                show_central=False)
        self.assertEqual([key for key, _ in PAGES], ["home", "radar", "master"])
        for view in (radar, master):
            self.assertIn('data-route="home"', view)
            self.assertIn('data-route="radar"', view)
            self.assertIn('data-route="master"', view)
            self.assertNotIn('data-route="scanner"', view)
            self.assertIn('aria-label="Qualidade das evidências"', view)
            self.assertIn("Por que não operar?", view)
            self.assertNotIn("OPERAR AGORA", view)
        self.assertIn("Estratégia de Abertura", radar)
        self.assertIn("MATRIZ DE VIÉS", radar)
        self.assertIn("Top 10 aguardando", radar)
        self.assertIn("Calendário econômico", master)
        self.assertIn("Bancos centrais", master)
        self.assertIn('data-local-tab="geo"', master)


if __name__ == "__main__":
    unittest.main()
