"""Existing currency-news V10.6.2 reuse: provenance, security, freshness, UI."""
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from atlasquant_trader_master_legacy_news import (
    build_legacy_news_read_model,
)
from atlasquant_trader_master_news_ui import master_news_html
from atlasquant_trader_master_briefing_ui import master_overview_cards
from atlasquant_trader_radar_compact_ui import trader_radar_html

BRT = timezone(timedelta(hours=-3))
NOW = datetime(2026, 11, 2, 12, 15, tzinfo=timezone.utc)


def _article(*, title="US Treasury yields shift after a CPI release",
             source="Example Financial Press", when=NOW, link="https://example.com/story",
             provider="Google News RSS"):
    return {
        "title": title, "source": source, "published_at": when.isoformat(),
        "link": link, "provider": provider,
        "weighted_impact": 0.95, "direction": "COMPRA CERTA",
        "news_score": 9999,
    }


def _snapshot(*articles, currencies=("USD",), updated=NOW):
    return {
        "updated_at": updated.isoformat(),
        "currencies": {
            code: {"articles": list(articles), "bias": "COMPRA CERTA",
                   "net_impact": 1.0, "news_score": 100.0}
            for code in currencies
        }
    }


class MasterLegacyNewsTests(unittest.TestCase):
    def test_no_snapshot_is_safe(self):
        model = build_legacy_news_read_model(None, at=NOW)
        self.assertEqual(model["state"], "SEM FEED")
        self.assertEqual(model["total"], 0)
        self.assertFalse(model["new_network_calls"])
        self.assertFalse(model["signals_enabled"])
        self.assertIn("Aguardando manchetes", master_news_html(model))

    def test_existing_legacy_snapshot_reads_without_network(self):
        model = build_legacy_news_read_model(
            _snapshot(_article(), currencies=("USD","EUR")), at=NOW)
        self.assertEqual(model["state"], "OBSERVACIONAL")
        self.assertEqual(model["total"], 1)
        self.assertEqual(model["covered_currencies"], ["EUR", "USD"])
        item = model["articles"][0]
        self.assertFalse(item["trade_signal"])
        self.assertFalse(item["verified_fact"])
        self.assertEqual(item["time_brt"], "02/11 09:15")
        self.assertTrue(item["url"].startswith("https://"))
        self.assertIn("Currency News Intelligence", model["source"])

    def test_stale_snapshot_or_article_not_treated_as_current(self):
        old = _snapshot(_article(), updated=NOW - timedelta(hours=4))
        self.assertEqual(build_legacy_news_read_model(old, at=NOW)["state"], "SEM FEED")
        old_item = _snapshot(_article(when=NOW - timedelta(hours=49)))
        self.assertEqual(build_legacy_news_read_model(old_item, at=NOW)["state"], "SEM FEED")
        future = _snapshot(_article(when=NOW + timedelta(minutes=10)))
        self.assertEqual(build_legacy_news_read_model(future, at=NOW)["state"], "SEM FEED")

    def test_rfc2822_news_timestamp_reuse(self):
        article = _article()
        article["published_at"] = format_datetime(NOW)
        model = build_legacy_news_read_model(_snapshot(article), at=NOW)
        self.assertEqual(model["state"], "OBSERVACIONAL")

    def test_no_unattributed_or_empty_articles(self):
        rows = (
            _article(source="Fonte não identificada"),
            _article(source=""),
            _article(title=""),
        )
        self.assertEqual(
            build_legacy_news_read_model(_snapshot(*rows), at=NOW)["state"],
            "SEM FEED",
        )

    def test_risky_links_cannot_be_rendered_as_action(self):
        bad = [
            "javascript:alert(document.cookie)",
            "http://example.com/story",
            "https://user:password@example.com/story",
            "https://example.com:444/unsafe",
        ]
        for url in bad:
            with self.subTest(url=url):
                model = build_legacy_news_read_model(
                    _snapshot(_article(link=url)), at=NOW)
                markup = master_news_html(model)
                self.assertNotIn('href="' + url + '"', markup)
                self.assertIn("US Treasury", markup)

    def test_external_titles_escaped_and_scores_never_rendered(self):
        article = _article(
            title="<script>alert('x')</script> currency central bank",
            source="<iframe>Example Publisher"
        )
        model = build_legacy_news_read_model(_snapshot(article), at=NOW)
        markup = master_news_html(model)
        self.assertNotIn("<script>", markup)
        self.assertNotIn("<iframe>", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("COMPRA CERTA", markup)
        self.assertNotIn("9999", markup)

    def test_geopolitical_keywords_are_not_independent_fact_verification(self):
        article = _article(title="Tariffs and trade war debated by policymakers")
        model = build_legacy_news_read_model(_snapshot(article), at=NOW)
        self.assertEqual(model["geo_count"], 1)
        self.assertEqual(model["articles"][0]["type"], "GEOPOLÍTICA EM MANCHETE")
        self.assertFalse(model["facts_verified"])
        self.assertIn("não foi verificado independentemente", master_news_html(model))

    def test_master_cards_counts_are_observations_not_signals(self):
        model = build_legacy_news_read_model(
            _snapshot(_article(title="Trade war policy proposal today")), at=NOW)
        cards = master_overview_cards(None, news_model=model, at=NOW)
        self.assertIn("Risco geopolítico", cards)
        self.assertIn("Notícias relevantes", cards)
        self.assertIn("OBSERVACIONAL · NÃO VERIFICADO", cards)
        self.assertIn("Manchetes", cards)
        self.assertNotIn("COMPRA CERTA", cards)
        live = datetime.now(timezone.utc)
        html = trader_radar_html(
            selected="master", news_data=_snapshot(_article(when=live), updated=live),
            calendar_data=None)
        self.assertIn("US Treasury yields", html)
        self.assertIn("NÃO É SINAL", html)
        self.assertIn('data-visual-reference="approved-20261102-v1"', html)

    def test_no_real_feed_no_invention(self):
        model = build_legacy_news_read_model(_snapshot(), at=NOW)
        self.assertEqual(model["state"], "SEM FEED")
        self.assertEqual(model["articles"], [])


if __name__ == "__main__":
    unittest.main()
