"""Research-only G8 source lead directory cannot claim live market readiness."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_official_feed_registry_lab import (
    DIRECTORY_LINKED_LEADS, PENDING_LEADS, SCHEMA,
    audit_g8_official_feed_leads_lab,
)
from atlasquant_trader_official_rss_capture_lab import SOURCES

AT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


class G8OfficialFeedDirectoryLabTests(unittest.TestCase):
    def test_researched_g8_directory_is_not_a_live_data_source(self):
        snapshot = deepcopy((DIRECTORY_LINKED_LEADS, PENDING_LEADS))
        report = audit_g8_official_feed_leads_lab(at=AT)
        self.assertEqual((DIRECTORY_LINKED_LEADS, PENDING_LEADS), snapshot)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["state"], "LAB_PUBLISHER_DIRECTORY_RESEARCH_ONLY")
        self.assertEqual(set(report["currency_coverage"]), set(CURRENCIES))
        self.assertEqual(report["research_directory_count"], 9)
        self.assertEqual(report["pending_endpoint_count"], 1)
        self.assertEqual(len(report["eligible_sources"]), 9)
        self.assertFalse(report["all_8_currency_feeds_verified"])
        self.assertFalse(report["live_news_verified"])
        self.assertFalse(report["source_payload_authenticated"])
        self.assertEqual(report["external_http_requests"], 0)
        self.assertEqual(report["new_cost_brl"], 0)
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["trade_authorized"])

    def test_5_more_currencies_are_directory_linked(self):
        report = audit_g8_official_feed_leads_lab(at=AT)
        for currency in ("GBP", "JPY", "CHF", "AUD", "CAD"):
            with self.subTest(currency=currency):
                available = report["currency_coverage"][currency][
                    "publisher_directory_linked_leads"]
                self.assertGreater(len(available), 0)
                self.assertFalse(report["currency_coverage"][currency][
                    "currency_strength_cause_verified"])
        self.assertEqual(report["currency_coverage"]["NZD"][
            "publisher_directory_linked_leads"], [])

    def test_nzd_xml_lead_is_explicitly_pending_and_not_allowlisted(self):
        report = audit_g8_official_feed_leads_lab(at=AT)
        nz = report["currency_coverage"]["NZD"]
        self.assertEqual(nz["unconfirmed_official_host_leads"],
                         ["NZ_RBNZ_NEWS_PENDING"])
        self.assertNotIn("NZ_RBNZ_NEWS_PENDING", SOURCES)
        self.assertFalse(report["pending_sources"]["NZ_RBNZ_NEWS_PENDING"][
            "can_activate_collection"])
        self.assertEqual(len(report["nz_fallback_pages"]), 2)

    def test_every_directory_lead_is_only_offline_parser_candidate(self):
        report = audit_g8_official_feed_leads_lab(at=AT)
        for key, lead in report["eligible_sources"].items():
            with self.subTest(source=key):
                self.assertIn(key, SOURCES)
                self.assertEqual(lead["feed_url"], SOURCES[key]["feed_url"])
                self.assertFalse(lead["technical_parser_tested_on_real_feed"])
                self.assertFalse(lead["publisher_terms_verified_for_product"])
                self.assertFalse(lead["can_activate_collection"])
                self.assertTrue(lead["directory_url"].startswith("https://"))

    def test_no_retroactive_research_and_no_naive_clock(self):
        before = audit_g8_official_feed_leads_lab(at=AT - timedelta(days=1))
        self.assertEqual(before["state"], "LAB_BLOCKED")
        self.assertEqual(before["eligible_sources"], {})
        with self.assertRaises(ValueError):
            audit_g8_official_feed_leads_lab(at=AT.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
