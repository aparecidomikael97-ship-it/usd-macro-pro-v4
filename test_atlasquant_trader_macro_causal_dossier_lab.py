"""Macro surprise sign cannot be mislabeled as a verified G8 FX cause."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_macro_causal_dossier_lab import (
    SCHEMA, build_macro_causal_dossier_lab,
)
from atlasquant_trader_macro_surprise_pit_lab import (
    build_macro_point_in_time_evidence_lab,
)
from atlasquant_trader_news_pair_context_lab import build_news_pair_context_lab
from test_atlasquant_trader_news_pair_context_lab import base_report, news
from test_atlasquant_trader_official_http_collection_contract_lab import NOW


def context(*, news_usd=False):
    return build_news_pair_context_lab(base_report(), [news()] if news_usd else [], at=NOW)


def macro(currency="USD", event="USD_CPI_TEST", indicator="CPI",
          actual=2.6, consensus=2.3, *, future_days=0):
    scheduled = NOW + timedelta(days=future_days) if future_days else NOW - timedelta(hours=1)
    preliminary = {
        "state": "LAB_SYNTHETIC_MACRO_PRE", "event_id": event,
        "currency": currency, "indicator_id": indicator, "unit": "PERCENT",
        "source": "SYNTHETIC_TEST_EXPECTATIONS", "previous": 2.1,
        "previous_captured_at_utc": (NOW - timedelta(days=2)).isoformat(),
        "consensus": consensus,
        "consensus_captured_at_utc": (NOW - timedelta(hours=2)).isoformat(),
        "scheduled_release_at_utc": scheduled.isoformat(),
        "deadband_predeclared": 0.05,
    }
    actual_release = None if future_days else {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL", "event_id": event,
        "source": "SYNTHETIC_TEST_PUBLISHER", "actual": actual,
        "released_at_utc": scheduled.isoformat(),
        "captured_at_utc": (NOW - timedelta(minutes=55)).isoformat(),
    }
    return build_macro_point_in_time_evidence_lab(
        preliminary, actual_release, forecast_issued_at=NOW, evaluated_at=NOW)


def pair_at(report, pair="USD/JPY", horizon="D1"):
    return next(x for x in report["rows"] if x["pair"] == pair)["horizons"][horizon]


class MacroCausalDossierLabTests(unittest.TestCase):
    def test_no_synthetic_releases_stays_28_pairs_x_three_waits(self):
        c = context()
        original = deepcopy(c)
        out = build_macro_causal_dossier_lab(c, [], at=NOW)
        self.assertEqual(c, original)
        self.assertEqual((out["schema"], out["state"]),
                         (SCHEMA, "LAB_CAUSAL_EVIDENCE_GAPS_ONLY"))
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(out["currency_count"], 8)
        self.assertEqual(set(out["currencies"]), set(CURRENCIES))
        self.assertEqual({x["pair"] for x in out["rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(out["synthetic_event_count"], 0)
        for row in out["rows"]:
            self.assertFalse(row["trade_authorized"])
            self.assertEqual(set(row["horizons"]), {"D1", "W1", "MN1"})
            for frame in row["horizons"].values():
                self.assertEqual(frame["operational_bias"], "AGUARDAR")
                self.assertEqual(frame["base_currency_strength_cause"], "NAO_COMPROVADA")
                self.assertFalse(frame["actual_values_source_attested"])
        for flag in ("published_macro_receipts_attested", "forecast_accuracy_verified",
                     "strength_causation_proven", "calendar_realtime_verified",
                     "can_feed_live_radar", "trade_authorized", "worker_enabled",
                     "scheduler_enabled", "publishable", "three_daily_updates_running"):
            self.assertFalse(out[flag])

    def test_above_consensus_usd_is_not_bullish_usd_jpy(self):
        c = context(news_usd=True)
        a = macro()
        before = deepcopy((c, a))
        out = build_macro_causal_dossier_lab(c, [a], at=NOW)
        self.assertEqual((c, a), before)
        self.assertEqual(a["state"], "LAB_MACRO_RELEASED_SYNTHETIC")
        self.assertEqual(out["state"], "LAB_CAUSAL_EVIDENCE_GAPS_ONLY")
        self.assertEqual(out["currencies"]["USD"]["released_claim_count"], 1)
        frame = pair_at(out)
        self.assertEqual(frame["news_documentary_count"], 1)
        self.assertEqual(frame["operational_bias"], "AGUARDAR")
        claim = frame["macro_surprise_claims"][0]
        self.assertEqual(claim["currency"], "USD")
        self.assertEqual(claim["surprise_class"], "ABOVE_CONSENSUS")
        self.assertAlmostEqual(claim["actual_minus_consensus"], 0.3)
        self.assertEqual(claim["strength_direction"], "AGUARDAR")
        self.assertFalse(claim["release_verified"])
        self.assertEqual(pair_at(out, "EUR/JPY")["macro_surprise_claims"], [])

    def test_below_and_above_consensus_is_not_validated_fx_contradiction(self):
        one = macro(event="USD_CPI_ABOVE")
        two = macro(event="USD_GDP_BELOW", indicator="GDP", actual=1.0)
        out = build_macro_causal_dossier_lab(context(), [one, two], at=NOW)
        frame = pair_at(out, "GBP/USD")
        self.assertTrue(frame["mixed_above_below_consensus_claims"])
        self.assertTrue(frame["mixed_surprise_signs_do_not_prove_currency_contradiction"])
        self.assertEqual({x["surprise_class"] for x in frame["macro_surprise_claims"]},
                         {"ABOVE_CONSENSUS", "BELOW_CONSENSUS"})
        self.assertEqual(frame["operational_bias"], "AGUARDAR")

    def test_future_calendar_claim_does_not_leak_as_actual_or_forecast(self):
        upcoming = macro(event="GBP_CPI_FUTURE", currency="GBP", future_days=2)
        self.assertEqual(upcoming["state"], "LAB_MACRO_FUTURE_SCHEDULE_ONLY")
        out = build_macro_causal_dossier_lab(context(), [upcoming], at=NOW)
        self.assertEqual(pair_at(out, "GBP/USD", "D1")["future_releases_claimed"], [])
        self.assertEqual(len(pair_at(out, "GBP/USD", "W1")["future_releases_claimed"]), 1)
        self.assertEqual(pair_at(out, "GBP/USD", "W1")["macro_surprise_claims"], [])
        self.assertTrue(pair_at(out, "GBP/USD", "W1")["future_releases_claimed"][0]
                        ["no_actual_observed"])
        self.assertEqual(pair_at(out, "GBP/USD", "W1")["operational_bias"], "AGUARDAR")

    def test_in_line_consensus_is_not_no_market_risk(self):
        claim = macro(currency="CHF", event="CH_RATE_NEUTRAL", indicator="POLICY_RATE",
                      actual=2.3, consensus=2.3)
        out = build_macro_causal_dossier_lab(context(), [claim], at=NOW)
        self.assertEqual(pair_at(out, "USD/CHF")["macro_surprise_claims"][0]
                         ["surprise_class"], "IN_LINE_WITH_CONSENSUS")
        self.assertFalse(pair_at(out, "USD/CHF")["policy_expectations_market_response_verified"])

    def test_released_event_past_window_does_not_enter_daily(self):
        # This report freezes at NOW, so a sample event 10 days ago can still
        # be compared in the monthly news window, never in daily/weekly.
        old = macro(event="USD_OLD")
        # Modify the *input* of the generator for an old release, not the
        # already-generated report: the immutable comparison must still hold.
        ev = deepcopy(old["freeze_evidence"])
        ev["scheduled_release_at_utc"] = (NOW - timedelta(days=10, hours=1)).isoformat()
        ev["released_at_utc"] = (NOW - timedelta(days=10, hours=1)).isoformat()
        ev["captured_at_utc"] = (NOW - timedelta(days=10)).isoformat()
        ev["previous_captured_at_utc"] = (NOW - timedelta(days=13)).isoformat()
        ev["consensus_captured_at_utc"] = (NOW - timedelta(days=11)).isoformat()
        # The original freeze allows a 48h release vs planned timestamp, so
        # reconstitute from the explicit vintage before handing it to dossier.
        pre = {"state": "LAB_SYNTHETIC_MACRO_PRE", "event_id": ev["evidence_id"],
               "currency": ev["currency"], "indicator_id": ev["indicator_id"],
               "unit": ev["unit"], "source": ev["source"],
               "previous": ev["previous"], "previous_captured_at_utc": ev["previous_captured_at_utc"],
               "consensus": ev["consensus"], "consensus_captured_at_utc": ev["consensus_captured_at_utc"],
               "scheduled_release_at_utc": ev["scheduled_release_at_utc"],
               "deadband_predeclared": ev["deadband_predeclared"]}
        act = {"state": "LAB_SYNTHETIC_MACRO_ACTUAL", "event_id": ev["evidence_id"],
               "actual": ev["actual"], "released_at_utc": ev["released_at_utc"],
               "captured_at_utc": ev["captured_at_utc"], "source": ev["actual_source"]}
        historical = build_macro_point_in_time_evidence_lab(
            pre, act, forecast_issued_at=NOW, evaluated_at=NOW)
        out = build_macro_causal_dossier_lab(context(), [historical], at=NOW)
        self.assertEqual(pair_at(out, "USD/CAD", "D1")["macro_surprise_claims"], [])
        self.assertEqual(pair_at(out, "USD/CAD", "W1")["macro_surprise_claims"], [])
        self.assertEqual(len(pair_at(out, "USD/CAD", "MN1")["macro_surprise_claims"]), 1)

    def test_duplicate_event_and_forged_directions_rejected(self):
        good = macro()
        for kind in ("duplicate", "buy_now", "provider_true", "fake_consensus",
                     "fake_surprise", "fake_timestamp", "future_actual"):
            with self.subTest(kind=kind):
                sample = deepcopy(good)
                receipts = [sample]
                if kind == "duplicate":
                    receipts = [sample, deepcopy(sample)]
                elif kind == "buy_now":
                    sample["macro_currency_direction"] = "BUY"
                elif kind == "provider_true":
                    sample["provider_attested"] = True
                elif kind == "fake_consensus":
                    sample["freeze_evidence"]["consensus"] = 100.0
                elif kind == "fake_surprise":
                    sample["surprise"] = 999.0
                elif kind == "fake_timestamp":
                    sample["freeze_evidence"]["consensus_captured_at_utc"] = "bad-date"
                else:
                    sample["freeze_evidence"]["captured_at_utc"] = (
                        NOW + timedelta(days=2)).isoformat()
                out = build_macro_causal_dossier_lab(context(), receipts, at=NOW)
                self.assertEqual(out["state"], "LAB_BLOCKED")
                self.assertFalse(out["trade_authorized"])

    def test_forged_news_context_or_missing_pair_blocks_whole_dossier(self):
        for kind in ("live_claim", "fake_news_cause", "buy_now", "duplicate",
                     "future_now", "source_origin", "forged_calendar"):
            with self.subTest(kind=kind):
                n = deepcopy(context(news_usd=True))
                if kind == "live_claim":
                    n["source_identity_independently_verified"] = True
                elif kind == "fake_news_cause":
                    n["rows"][0]["horizons"]["D1"]["base_currency_strength_reason"] = "STRONG"
                elif kind == "buy_now":
                    n["rows"][0]["horizons"]["D1"]["operational_bias"] = "ALTA"
                elif kind == "duplicate":
                    n["rows"][1]["pair"] = n["rows"][0]["pair"]
                elif kind == "future_now":
                    n["as_of_utc"] = (NOW + timedelta(hours=1)).isoformat()
                elif kind == "source_origin":
                    article = n["rows"][0]["horizons"]["D1"]["news_articles_from_supplied_feeds"]
                    if article:
                        article[0]["source_origin_verified"] = True
                    else:
                        n["rows"][0]["horizons"]["D1"]["news_not_proof_of_currency_direction"] = False
                else:
                    n["rows"][0]["horizons"]["D1"]["event_exposures_documentary"] = "fake"
                self.assertEqual(build_macro_causal_dossier_lab(n, [], at=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_article_from_wrong_currency_or_late_publication_is_rejected(self):
        for kind in ("wrong_currency", "wrong_host", "publication_after_capture"):
            with self.subTest(kind=kind):
                n = deepcopy(context(news_usd=True))
                pair = next(x for x in n["rows"] if x["pair"] == "USD/JPY")
                item = pair["horizons"]["D1"]["news_articles_from_supplied_feeds"][0]
                if kind == "wrong_currency":
                    item["currency"] = "GBP"
                elif kind == "wrong_host":
                    item["official_url_claimed"] = "https://fake.test/article"
                else:
                    item["publisher_claimed_at_utc"] = (
                        NOW + timedelta(hours=1)).isoformat()
                self.assertEqual(build_macro_causal_dossier_lab(n, [], at=NOW)["state"],
                                 "LAB_BLOCKED")

    def test_non_list_and_unbounded_receipts_rejected(self):
        for inputs in (None, "LIVE", {}, [None], [macro()] * 65):
            self.assertEqual(build_macro_causal_dossier_lab(context(), inputs, at=NOW)
                             ["state"], "LAB_BLOCKED")

    def test_no_new_work_or_network_exposure(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                patch("socket.create_connection", side_effect=AssertionError("socket")):
            out = build_macro_causal_dossier_lab(context(), [macro()], at=NOW)
            self.assertEqual(out["external_http_requests"], 0)
            self.assertEqual(out["new_cost_brl"], 0)
            self.assertFalse(out["three_daily_updates_running"])
            self.assertFalse(out["worker_enabled"])

    def test_naive_clock_and_lookahead_in_report_refused(self):
        with self.assertRaises(ValueError):
            build_macro_causal_dossier_lab(context(), [], at=NOW.replace(tzinfo=None))
        later = build_macro_causal_dossier_lab(context(), [], at=NOW - timedelta(hours=1))
        self.assertEqual(later["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
