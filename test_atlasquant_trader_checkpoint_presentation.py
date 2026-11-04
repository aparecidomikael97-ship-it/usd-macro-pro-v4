"""Approved Trader screen contract with checkpoint evidence transparency."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_radar_compact_ui import PAGES, _daily, trader_radar_html


class TraderCheckpointPresentationTests(unittest.TestCase):
    def test_four_pages_keep_approved_shell_and_evidence(self):
        for page, _ in PAGES:
            with self.subTest(page=page):
                html = trader_radar_html(selected=page)
                self.assertIn('data-visual-reference="approved-20261102-v1"', html)
                self.assertIn('class="aqr-aside"', html)
                self.assertIn('aria-label="Qualidade das evidências"', html)
                self.assertIn("Por que não operar?", html)
                self.assertIn("Somente leitura", html)
                self.assertIn("Risco:", html)
                self.assertNotIn("OPERAR AGORA", html)

    def test_html_escapes_provider_source_in_evidence(self):
        at = datetime.now(timezone.utc)
        daily = {
            "state": "VALIDATED_DAILY", "as_of": at.isoformat(),
            "source": "<script>alert(1)</script>", "pairs": {},
            "currencies": {},
        }
        html = trader_radar_html(selected="radar", daily_data=daily)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_stale_daily_returns_empty_and_never_orders_top10(self):
        daily = {
            "state": "VALIDATED_DAILY",
            "as_of": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
            "source": "Fonte expirada",
            "pairs": {p: {"change_pct": 1.0, "bias": "ALTA"} for p in OFFICIAL_PAIRS},
            "currencies": {c: {"change_pct": 0.4} for c in CURRENCIES},
        }
        self.assertEqual(_daily(daily)["pairs"], {})
        html = trader_radar_html(selected="radar", daily_data=daily)
        self.assertIn("Top 10 aguardando", html)
        self.assertIn("ATRASADO", html)
        self.assertNotIn("#1 ", html)


    def test_daily_reading_freshness_window_is_at_most_twenty_minutes(self):
        pair = OFFICIAL_PAIRS[0]

        def document(age_minutes):
            return {
                "state": "VALIDATED_DAILY",
                "source": "Fixture LAB de teste",
                "as_of": (datetime.now(timezone.utc)
                          - timedelta(minutes=age_minutes)).isoformat(),
                "pairs": {pair: {"change_pct": 0.8, "bias": "ALTA"}},
                "currencies": {},
            }

        self.assertIn(pair, _daily(document(19))["pairs"])
        self.assertEqual(_daily(document(21))["pairs"], {})


if __name__ == "__main__":
    unittest.main()
