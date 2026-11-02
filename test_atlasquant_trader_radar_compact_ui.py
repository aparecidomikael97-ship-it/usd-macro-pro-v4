"""Contratos de apresentação do Trader Radar compacto, sem feeds externos."""
import re
import unittest
from datetime import datetime, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_radar_compact_ui import (
    PAGES, _daily, central_entry_html, trader_radar_html,
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
            "IBOV": {"change_pct": -0.2, "bias": "BAIXA"},
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
        self.assertGreaterEqual(html.count("AGUARDANDO"), 28 + 8 + 10)
        self.assertNotIn("Fixture offline", html)

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

    def test_macro_is_global_and_impact_is_conditional(self):
        html = trader_radar_html(selected="master")
        self.assertIn("Macro", html)
        self.assertNotIn("Macro · EUA", html)
        self.assertIn("consenso", html)
        self.assertIn('data-local-tab="geo"', html)
        self.assertIn('data-local-tab="news"', html)


if __name__ == "__main__":
    unittest.main()
