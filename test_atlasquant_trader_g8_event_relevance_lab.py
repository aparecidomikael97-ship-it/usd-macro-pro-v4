"""Synthetic checks: news relevance, source chronology and no FX signal."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_event_relevance_lab import (
    EventSnapshot, inspect_g8_event_relevance_lab as route,
)

UTC = timezone.utc
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=UTC)
BEFORE = datetime(2026, 11, 9, 12, tzinfo=UTC)
AFTER = datetime(2026, 11, 10, 14, tzinfo=UTC)


def report(*, event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
           unit="PERCENT_MOM_SA", consensus="0.3", actual=None,
           actual_published=None, actual_captured=None):
    return EventSnapshot(
        event_id=event_id, currency=currency, metric=metric,
        target_period="2026-10", unit=unit, importance="HIGH",
        scheduled_release_at=RELEASE,
        calendar_captured_at=BEFORE - timedelta(hours=2),
        consensus_value=consensus,
        consensus_captured_at=(BEFORE - timedelta(hours=1)
                               if consensus is not None else None),
        actual_value=actual, actual_published_at=actual_published,
        actual_captured_at=actual_captured,
    )


def actual_event(*, consensus="0.3", actual="0.4"):
    return report(
        consensus=consensus, actual=actual,
        actual_published=RELEASE,
        actual_captured=RELEASE + timedelta(minutes=1),
    )


def by_pair(result, pair):
    return next(x for x in result["pair_rows"] if x["pair"] == pair)


class G8EventRelevanceTests(unittest.TestCase):
    def no_live(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["event_calendar_completeness_verified"])
        self.assertFalse(result["source_original_bytes_authenticated"])
        self.assertFalse(result["pre_event_consensus_independently_attested"])
        self.assertFalse(result["post_event_actual_independently_attested"])
        self.assertFalse(result["market_reaction_direction_validated"])
        self.assertFalse(result["relative_currency_strength_available"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["worker_enabled"])
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["index_bias"])
        self.assertTrue(result["research_only"])
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))

    def test_usd_event_relevant_only_to_seven_usd_crosses(self):
        result = route([report()], as_of_utc=BEFORE)
        self.assertEqual(result["state"], "LAB_G8_EVENT_RELEVANCE_DOCUMENTARY_ONLY_NO_BIAS")
        self.assertEqual((result["currency_count"], result["pair_count"]), (8, 28))
        self.assertEqual({x["pair"] for x in result["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(sum(x["event_count"] == 1 for x in result["pair_rows"]), 7)
        self.assertEqual(sum(x["event_count"] == 0 for x in result["pair_rows"]), 21)
        self.assertEqual(by_pair(result, "EUR/USD")["relevant_events_documentary_only"][0]["role"],
                         "QUOTE")
        self.assertEqual(by_pair(result, "USD/JPY")["relevant_events_documentary_only"][0]["role"],
                         "BASE")
        self.assertEqual(by_pair(result, "AUD/NZD")["event_count"], 0)
        self.no_live(result)

    def test_all_eight_currencies_route_to_exactly_seven_pairs_each(self):
        for c in ("EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"):
            with self.subTest(currency=c):
                result = route([report(event_id=f"{c}_CPI_OCT", currency=c)],
                               as_of_utc=BEFORE)
                self.assertEqual(sum(x["event_count"] for x in result["pair_rows"]), 7)
                self.no_live(result)

    def test_two_events_can_appear_on_both_sides_of_one_cross(self):
        result = route([report(), report(event_id="GB_CPI_OCT", currency="GBP")],
                       as_of_utc=BEFORE)
        self.assertEqual(by_pair(result, "GBP/USD")["event_count"], 2)
        self.assertEqual({e["role"] for e in by_pair(result, "GBP/USD")[
            "relevant_events_documentary_only"]}, {"BASE", "QUOTE"})
        self.assertEqual(sum(x["event_count"] for x in result["pair_rows"]), 14)
        self.no_live(result)

    def test_pre_event_consensus_is_not_actual_or_surprise(self):
        result = route([report()], as_of_utc=BEFORE)
        first = result["events"][0]
        self.assertEqual(first["phase"], "PRE_RELEASE_CALENDAR_AND_CONSENSUS_CLAIM_ONLY")
        self.assertEqual(first["consensus_documentary"], "0.3")
        self.assertIsNone(first["actual_documentary"])
        self.assertIsNone(first["actual_minus_consensus_documentary"])
        self.assertFalse(first["surprise_is_currency_strength_direction"])
        self.no_live(result)

    def test_release_clock_passed_without_actual_means_await_not_zero(self):
        result = route([report()], as_of_utc=AFTER)
        self.assertEqual(result["events"][0]["phase"],
                         "RELEASE_PASSED_ACTUAL_NOT_AVAILABLE")
        self.assertTrue(by_pair(result, "EUR/USD")["needs_actual_or_source_review"])
        self.assertIsNone(result["events"][0]["actual_minus_consensus_documentary"])
        self.no_live(result)

    def test_documentary_arithmetic_after_actual_is_not_currency_direction(self):
        result = route([actual_event()], as_of_utc=AFTER)
        first = result["events"][0]
        self.assertEqual(first["phase"], "POST_RELEASE_DIFFERENCE_DOCUMENTARY_UNATTESTED")
        self.assertEqual(first["actual_minus_consensus_documentary"], "0.1")
        self.assertFalse(first["surprise_is_currency_strength_direction"])
        self.assertIsNone(by_pair(result, "EUR/USD")[
            "relevant_events_documentary_only"][0]["fx_direction_from_event"])
        self.no_live(result)

    def test_negative_surprise_is_not_automatically_bullish_or_bearish(self):
        result = route([actual_event(actual="0.1")], as_of_utc=AFTER)
        self.assertEqual(result["events"][0]["actual_minus_consensus_documentary"], "-0.2")
        self.assertIsNone(result["fx_bias"])
        self.no_live(result)

    def test_actual_without_consensus_has_no_surprise(self):
        result = route([actual_event(consensus=None)], as_of_utc=AFTER)
        self.assertEqual(result["events"][0]["phase"],
                         "POST_RELEASE_ACTUAL_WITHOUT_CONSENSUS")
        self.assertIsNone(result["events"][0]["actual_minus_consensus_documentary"])
        self.no_live(result)

    def test_consensus_captured_after_release_is_not_pre_event_consensus(self):
        bad = replace(report(), consensus_captured_at=RELEASE + timedelta(minutes=1))
        result = route([bad], as_of_utc=AFTER)
        self.assertEqual(result["reason"], "INVALID_EVENT_SEMANTICS_PIT_OR_DUPLICATE")
        self.no_live(result)

    def test_actual_captured_after_asof_must_not_leak_backwards(self):
        result = route([actual_event()], as_of_utc=BEFORE)
        self.assertEqual(result["state"], "LAB_EVENT_ROUTER_BLOCKED")
        self.no_live(result)

    def test_actual_published_before_scheduled_release_blocked(self):
        bad = replace(actual_event(), actual_published_at=RELEASE - timedelta(minutes=1))
        self.assertEqual(route([bad], as_of_utc=AFTER)["state"], "LAB_EVENT_ROUTER_BLOCKED")

    def test_calendar_not_available_asof_is_not_historical_evidence(self):
        bad = replace(report(), calendar_captured_at=AFTER)
        self.assertEqual(route([bad], as_of_utc=BEFORE)["state"], "LAB_EVENT_ROUTER_BLOCKED")

    def test_metric_unit_mismatch_or_wrong_target_period_blocked(self):
        for mutation in ({"unit": "PERCENT_YOY_NSA"},
                         {"target_period": "2026-Q5"},
                         {"target_period": "2026-Q3"},
                         {"metric": "UNSUPPORTED"},
                         {"importance": []}):
            with self.subTest(mutation=mutation):
                bad = replace(report(), **mutation)
                self.assertEqual(route([bad], as_of_utc=BEFORE)["state"],
                                 "LAB_EVENT_ROUTER_BLOCKED")

    def test_quarterly_gdp_requires_quarter_and_policy_date_must_exist(self):
        gdp = replace(report(), event_id="US_GDP_Q3", metric="GDP_QOQ",
                      unit="PERCENT_QOQ_SA", target_period="2026-Q3")
        self.assertEqual(route([gdp], as_of_utc=BEFORE)["event_count"], 1)
        bad = replace(gdp, target_period="2026-09")
        self.assertEqual(route([bad], as_of_utc=BEFORE)["state"], "LAB_EVENT_ROUTER_BLOCKED")
        policy = replace(report(), event_id="US_POLICY_NOV", metric="POLICY_RATE",
                         unit="PERCENT_POLICY_RATE", target_period="2026-11-10")
        self.assertEqual(route([policy], as_of_utc=BEFORE)["event_count"], 1)
        self.assertEqual(route([replace(policy, target_period="2026-02-31")],
                               as_of_utc=BEFORE)["state"], "LAB_EVENT_ROUTER_BLOCKED")

    def test_future_month_cannot_be_assigned_to_earlier_release(self):
        # The calendar cannot claim a CPI/PCE/NFP/unemployment measurement
        # for December was scheduled for publication in November.
        metrics = {
            "CPI_MOM": "PERCENT_MOM_SA",
            "CPI_YOY": "PERCENT_YOY_NSA",
            "PCE_MOM": "PERCENT_MOM_SA",
            "NFP_CHANGE": "PERSONS_CHANGE_SA",
            "UNEMPLOYMENT_RATE": "PERCENT_RATE",
        }
        for metric, unit in metrics.items():
            with self.subTest(metric=metric):
                future = replace(report(), metric=metric, unit=unit,
                                 target_period="2026-12")
                result = route([future], as_of_utc=BEFORE)
                self.assertEqual(result["state"], "LAB_EVENT_ROUTER_BLOCKED")
                self.no_live(result)

    def test_future_quarter_cannot_be_attached_to_earlier_gdp_release(self):
        future = replace(report(), metric="GDP_QOQ", unit="PERCENT_QOQ_SA",
                         target_period="2026-Q4")
        self.assertEqual(route([future], as_of_utc=BEFORE)["state"],
                         "LAB_EVENT_ROUTER_BLOCKED")
        rollover = replace(future, target_period="2027-Q1")
        self.assertEqual(route([rollover], as_of_utc=BEFORE)["state"],
                         "LAB_EVENT_ROUTER_BLOCKED")

    def test_same_month_flash_is_documentary_not_source_attestation(self):
        flash = replace(report(), target_period="2026-11")
        result = route([flash], as_of_utc=BEFORE)
        self.assertEqual(result["event_count"], 1)
        self.no_live(result)

    def test_invalid_numbers_are_not_a_surprise(self):
        for bad_number in ("NaN", "Inf", "1e100", "-1e100", "fifty", 0.3, True, ""):
            with self.subTest(value=bad_number):
                result = route([replace(report(), consensus_value=bad_number)],
                               as_of_utc=BEFORE)
                self.assertEqual(result["state"], "LAB_EVENT_ROUTER_BLOCKED")
                self.no_live(result)

    def test_duplicate_event_ids_rejected(self):
        result = route([report(), report(currency="EUR")], as_of_utc=BEFORE)
        self.assertEqual(result["reason"], "INVALID_EVENT_SEMANTICS_PIT_OR_DUPLICATE")
        self.no_live(result)

    def test_claimed_hash_is_not_proof_of_source_authenticity(self):
        result = route([replace(report(), original_sha256_claim="a" * 64)],
                       as_of_utc=BEFORE)
        self.assertTrue(result["events"][0]["source_hash_claim_only_not_authenticated"])
        self.no_live(result)
        bad = route([replace(report(), original_sha256_claim="invalid")],
                    as_of_utc=BEFORE)
        self.assertEqual(bad["state"], "LAB_EVENT_ROUTER_BLOCKED")

    def test_empty_calendar_means_unknown_coverage_not_no_events(self):
        result = route([], as_of_utc=BEFORE)
        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["pair_count"], 28)
        self.assertFalse(result["event_calendar_completeness_verified"])
        self.no_live(result)

    def test_invalid_clock_or_too_many_events_fail_closed(self):
        self.assertEqual(route([], as_of_utc=BEFORE.replace(tzinfo=None))["state"],
                         "LAB_EVENT_ROUTER_BLOCKED")
        self.assertEqual(route([report()] * 33, as_of_utc=BEFORE)["state"],
                         "LAB_EVENT_ROUTER_BLOCKED")
        self.assertEqual(route(None, as_of_utc=BEFORE)["state"], "LAB_EVENT_ROUTER_BLOCKED")

    def test_nfp_and_policy_units_do_not_mix_with_cpi(self):
        nfp = replace(report(event_id="US_NFP_OCT"), metric="NFP_CHANGE",
                      unit="PERSONS_CHANGE_SA", consensus_value="150000")
        policy = replace(report(event_id="UK_POLICY_NOV", currency="GBP"),
                         metric="POLICY_RATE", unit="PERCENT_POLICY_RATE",
                         consensus_value="4.0")
        result = route([nfp, policy], as_of_utc=BEFORE)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["events"][0]["unit"], "PERSONS_CHANGE_SA")
        self.assertEqual(result["events"][1]["unit"], "PERCENT_POLICY_RATE")
        self.no_live(result)


if __name__ == "__main__":
    unittest.main()
