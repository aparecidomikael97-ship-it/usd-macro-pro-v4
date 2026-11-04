"""28-pair news+calendar bias context must not invent FX strength causality."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_bias_calendar_exposure_link_lab import (
    build_bias_calendar_exposure_link_lab,
)
from atlasquant_trader_news_pair_context_lab import (
    SCHEMA, build_news_pair_context_lab,
)
from atlasquant_trader_official_http_collection_contract_lab import (
    plan_official_feed_request_lab, reconcile_official_feed_response_lab,
)
from atlasquant_trader_macro_event_exposure_v2_lab import (
    build_macro_event_exposure_v2_lab,
)
from test_atlasquant_trader_bias_calendar_exposure_link_lab import reports
from test_atlasquant_trader_official_http_collection_contract_lab import (
    NOW, RSS, SOURCE, URL, response,
)
from test_atlasquant_trader_official_rss_capture_lab import atom


def base_report(v2=False):
    bias, calendar = reports()
    if v2:
        calendar = build_macro_event_exposure_v2_lab(at=NOW)
    return build_bias_calendar_exposure_link_lab(bias, calendar, at=NOW)


def news(source=SOURCE, xml=RSS, at=NOW, status=200, prior=None):
    plan = plan_official_feed_request_lab(source, planned_at=at,
                                         previous_cache=prior)
    url = plan["url"]
    headers = {"Content-Type": "application/rss+xml", "ETag": '"v1"'}
    return reconcile_official_feed_response_lab(
        plan, response(xml=xml, headers=headers, status=status, url=url),
        received_at=at, previous_cache=prior)


def at_pair(book, pair="USD/JPY", horizon="D1"):
    return next(row for row in book["rows"] if row["pair"] == pair)["horizons"][horizon]


class NewsPairContextLabTests(unittest.TestCase):
    def test_no_feed_is_still_28_pairs_three_aguardar_horizons(self):
        original = base_report()
        copy = deepcopy(original)
        out = build_news_pair_context_lab(original, [], at=NOW)
        self.assertEqual(original, copy)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_NEWS_CONTEXT_FOR_REVIEW_ONLY"))
        self.assertEqual((out["pair_count"], out["currency_count"]), (28, 8))
        self.assertEqual(set(out["currency_news_coverage"]), set(CURRENCIES))
        self.assertEqual({r["pair"] for r in out["rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(out["currency_news_coverage"]["USD"]["pilot_source_count"], 3)
        self.assertEqual(out["currency_news_coverage"]["EUR"]["pilot_source_count"], 2)
        self.assertEqual(out["currency_news_coverage"]["JPY"]["pilot_source_count"], 2)
        self.assertEqual(out["currency_news_coverage"]["NZD"]["pilot_source_count"], 0)
        self.assertFalse(out["g8_official_news_coverage_complete"])
        for p in out["rows"]:
            self.assertFalse(p["trade_authorized"])
            self.assertEqual(set(p["horizons"]), {"D1", "W1", "MN1"})
            for frame in p["horizons"].values():
                self.assertEqual(frame["operational_bias"], "AGUARDAR")
                self.assertEqual(frame["base_currency_strength_reason"], "NAO_COMPROVADO")
                self.assertEqual(frame["news_articles_from_supplied_feeds"], [])

    def test_offline_usd_news_only_routes_to_seven_pairs_without_direction(self):
        b, raw = base_report(v2=True), news()
        out = build_news_pair_context_lab(b, [raw], at=NOW)
        self.assertEqual(out["supplied_official_news_sources"], [SOURCE])
        self.assertEqual(len(at_pair(out, "USD/JPY")["news_articles_from_supplied_feeds"]), 1)
        self.assertEqual(at_pair(out, "EUR/JPY")["news_article_count"], 0)
        self.assertEqual(at_pair(out, "GBP/USD", "MN1")["news_article_count"], 1)
        self.assertEqual(at_pair(out, "USD/CAD", "W1")["news_article_count"], 1)
        self.assertEqual(len(at_pair(out, "USD/CAD", "W1")["event_exposures_documentary"]), 4)
        lead = at_pair(out)["news_articles_from_supplied_feeds"][0]
        self.assertEqual(lead["currency"], "USD")
        self.assertEqual(lead["topic"], "EMPLOYMENT")
        self.assertFalse(lead["source_origin_verified"])
        self.assertEqual(lead["directional_inference"], "AGUARDAR")
        self.assertFalse(out["currency_news_coverage"]["USD"]["currency_strength_explained"])

    def test_two_feed_sources_usd_eur_do_not_imply_other_g8_covered(self):
        usd = news()
        euro = news(source="EU_ECB_PRESS", xml=atom())
        out = build_news_pair_context_lab(base_report(), [usd, euro], at=NOW)
        self.assertEqual(at_pair(out, "EUR/USD")["news_article_count"], 2)
        self.assertEqual(at_pair(out, "EUR/JPY")["news_article_count"], 1)
        self.assertEqual(out["currency_news_coverage"]["EUR"]["supplied_source_count"], 1)
        self.assertIn("UK_BOE_NEWS",
                      out["currency_news_coverage"]["GBP"]["missing_pilot_sources"])
        self.assertFalse(out["currency_news_coverage"]["GBP"]["news_coverage_complete"])
        self.assertFalse(out["cause_of_currency_strength_verified"])

    def test_one_usd_claim_visible_as_d1_w1_mn1_news_not_candle_forecast(self):
        out = build_news_pair_context_lab(base_report(), [news()], at=NOW)
        for horizon in ("D1", "W1", "MN1"):
            frame = at_pair(out, "USD/JPY", horizon)
            self.assertEqual(frame["news_article_count"], 1)
            self.assertTrue(frame["trailing_news_window_not_candle_forecast"])
            self.assertTrue(frame["news_not_proof_of_currency_direction"])
            self.assertEqual(frame["counterevidence"], "NAO_AUTENTICADA")

    def test_http_304_does_not_reuse_stale_news_as_fresh(self):
        first = news()
        stale = news(status=304, xml=b"", prior=first["cache"])
        # A real 304 would arrive later, but this frozen documentary stage
        # can only accept a past/at-now caller response, never a future one.
        self.assertEqual(stale["state"], "LAB_UNATTESTED_NOT_MODIFIED_CLAIM")
        out = build_news_pair_context_lab(base_report(), [stale], at=NOW)
        self.assertEqual(at_pair(out)["news_article_count"], 0)
        self.assertEqual(out["currency_news_coverage"]["USD"]["source_states"][SOURCE],
                         "LAB_UNATTESTED_NOT_MODIFIED_CLAIM")

    def test_rate_limited_source_exposes_gap_not_old_news(self):
        p = plan_official_feed_request_lab(SOURCE, planned_at=NOW)
        rate = reconcile_official_feed_response_lab(
            p, response(status=429, xml=b"", headers={}), received_at=NOW)
        out = build_news_pair_context_lab(base_report(), [rate], at=NOW)
        self.assertEqual(out["state"], "LAB_NEWS_CONTEXT_FOR_REVIEW_ONLY")
        self.assertEqual(at_pair(out)["news_article_count"], 0)
        self.assertFalse(out["can_feed_live_radar"])

    def test_duplicate_or_forged_http_source_refused(self):
        source = news()
        for bad in ([source, source], [{**source, "live_news": True}],
                    [{**source, "source_id": "EU_ECB_PRESS"}],
                    [{**source, "external_http_requests": 1}]):
            with self.subTest(bad=bad[0].get("state")):
                out = build_news_pair_context_lab(base_report(), bad, at=NOW)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertEqual(out["rows"], [])

    def test_replaced_snapshot_article_url_hash_and_timestamp_refused(self):
        for kind in ("foreign_article", "fake_revision", "future_capture",
                     "buy_now", "missing_item", "wrong_topic", "fake_http_status",
                     "post_capture_publication"):
            with self.subTest(kind=kind):
                batch = deepcopy(news())
                item = batch["snapshot"]["items"][0]
                if kind == "foreign_article":
                    item["publisher_url"] = "https://bls.gov.attacker.test/news"
                elif kind == "fake_revision":
                    item["revision_sha256"] = "not-sha"
                elif kind == "future_capture":
                    batch["received_at_utc"] = (NOW + timedelta(days=1)).isoformat()
                elif kind == "buy_now":
                    item["market_direction"] = "BUY_NOW"
                elif kind == "missing_item":
                    batch["snapshot"]["items"].pop()
                elif kind == "fake_http_status":
                    batch["status_code"] = 503
                elif kind == "post_capture_publication":
                    item["publisher_claimed_at_utc"] = (NOW + timedelta(hours=1)).isoformat()
                else:
                    batch["snapshot"]["topic"] = "FOREX_SIGNAL"
                out = build_news_pair_context_lab(base_report(), [batch], at=NOW)
                self.assertEqual(out["state"], "LAB_BLOCKED")

    def test_forged_calendar_event_and_operational_bias_refused(self):
        for kind in ("fake_event", "bias_buy", "fake_source", "fake_realtime",
                     "duplicate_pair", "remove_horizon"):
            with self.subTest(kind=kind):
                b = deepcopy(base_report())
                if kind == "fake_event":
                    b["rows"][0]["horizons"]["D1"]["event_exposures"].append({"BUY": "now"})
                elif kind == "bias_buy":
                    b["rows"][0]["horizons"]["D1"]["operational_bias"] = "ALTA"
                elif kind == "fake_source":
                    b["real_sources_attested"] = True
                elif kind == "fake_realtime":
                    b["can_feed_live_radar"] = True
                elif kind == "duplicate_pair":
                    b["rows"][1]["pair"] = b["rows"][0]["pair"]
                else:
                    b["rows"][0]["horizons"].pop("MN1")
                out = build_news_pair_context_lab(b, [], at=NOW)
                self.assertEqual(out["state"], "LAB_BLOCKED")

    def test_untrusted_or_unbounded_http_batches_refused(self):
        b = base_report()
        for inp in (None, "live", {}, [None], [news()] * 6):
            out = build_news_pair_context_lab(b, inp, at=NOW)
            self.assertEqual(out["state"], "LAB_BLOCKED")

    def test_naive_clock_or_future_caller_report_not_allowed(self):
        with self.assertRaises(ValueError):
            build_news_pair_context_lab(base_report(), [], at=NOW.replace(tzinfo=None))
        out = build_news_pair_context_lab(base_report(), [], at=NOW - timedelta(hours=1))
        self.assertEqual(out["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
