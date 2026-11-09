"""Entirely synthetic, no-network tests of D1/W1 economic-event evidence veto."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_event_relevance_lab import EventSnapshot
from atlasquant_trader_economic_surprise_veto_lab import inspect_economic_surprise_veto_lab as review

UTC = timezone.utc
W = datetime(2026, 11, 3, 12, tzinfo=UTC)
D = datetime(2026, 11, 5, 12, tzinfo=UTC)
NOW = datetime(2026, 11, 5, 18, tzinfo=UTC)
RELEASE = datetime(2026, 11, 4, 13, 30, tzinfo=UTC)
ACTUAL_CAPTURE = RELEASE + timedelta(minutes=1)


@dataclass(frozen=True)
class Candidate:
    asset: str = "EUR/USD"
    horizon: str = "D1"
    daily: str = "ALTA"
    weekly: str = "ALTA"
    evaluated_at: datetime = D + timedelta(minutes=5)


def news(currency="USD", *, actual=None, consensus="0.3", importance="HIGH", event_id=None,
         scheduled=RELEASE, actual_captured=None, metric="CPI_MOM", unit="PERCENT_MOM_SA"):
    return EventSnapshot(
        event_id=event_id or currency + "_CPI_OCT_2026", currency=currency,
        metric=metric, target_period="2026-10", unit=unit, importance=importance,
        scheduled_release_at=scheduled,
        calendar_captured_at=W - timedelta(days=1),
        consensus_value=consensus,
        consensus_captured_at=(W - timedelta(hours=1) if consensus is not None else None),
        actual_value=actual,
        actual_published_at=(scheduled if actual is not None else None),
        actual_captured_at=(actual_captured or scheduled + timedelta(minutes=1)) if actual is not None else None,
    )


def catalog(*, actual="0.4", currency="USD", consensus="0.3", importance="HIGH"):
    return {
        "W1": [news(currency, importance=importance, consensus=consensus)],
        "D1": [news(currency, importance=importance, actual=actual, consensus=consensus)],
    }


def inspect(*, asset="EUR/USD", events=None, macro=None, cutoffs=None, candidate=None, now=NOW):
    return review(
        candidate=candidate or Candidate(asset=asset),
        events_by_horizon=catalog() if events is None else events,
        decision_at_by_horizon={"W1": W, "D1": D} if cutoffs is None else cutoffs,
        macro_captured_at_by_horizon={"W1": W-timedelta(hours=3),
                                      "D1": RELEASE+timedelta(hours=2)} if macro is None else macro,
        as_of_utc=now,
    )


class SurpriseVetoTests(unittest.TestCase):
    def safe(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertFalse(r["publishable"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["event_calendar_coverage_independently_verified"])
        self.assertFalse(r["pre_event_consensus_independently_authenticated"])
        self.assertFalse(r["actual_first_release_independently_authenticated"])
        self.assertFalse(r["surprise_direction_to_currency_independently_validated"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertIsNone(r["economic_surprise_predictive_increment_validated"])
        self.assertIsNone(r["research_direction_for_publication"])
        self.assertEqual((r["http_requests"], r["file_writes"], r["new_cost_brl"]), (0, 0, 0))

    def test_surprise_blocks_without_claiming_currency_direction(self):
        r = inspect()
        self.assertEqual(r["state"], "LAB_SURPRISE_DOCUMENTARY_VETO")
        self.assertEqual(r["blockers"], ["D1_SURPRISE_DIRECTION_NOT_INTERPRETED_OR_VALIDATED"])
        self.assertEqual(r["D1_events"][0]["surprise_documentary"], "0.1")
        self.assertIsNone(r["D1_events"][0]["directional_fx_impact"])
        self.assertEqual(r["W1_events"][0]["phase"], "PRE_RELEASE_CALENDAR_AND_CONSENSUS_CLAIM_ONLY")
        self.safe(r)

    def test_negative_surprise_not_automatically_bearish_or_bullish(self):
        r = inspect(events=catalog(actual="0.1"))
        self.assertEqual(r["D1_events"][0]["surprise_documentary"], "-0.2")
        self.assertIn("D1_SURPRISE_DIRECTION_NOT_INTERPRETED_OR_VALIDATED", r["blockers"])
        self.safe(r)

    def test_exact_consensus_does_not_become_live_signal(self):
        r = inspect(events=catalog(actual="0.3"))
        self.assertFalse(r["research_veto"])
        self.assertEqual(r["state"], "LAB_SURPRISE_NO_DOCUMENTARY_VETO_NO_GO")
        self.safe(r)

    def test_no_postrelease_actual_blocks_not_zero(self):
        r = inspect(events=catalog(actual=None))
        self.assertEqual(r["blockers"], ["D1_POST_RELEASE_ACTUAL_UNAVAILABLE"])
        self.safe(r)

    def test_actual_without_pre_event_consensus_blocks(self):
        r = inspect(events=catalog(actual="0.4", consensus=None))
        self.assertIn("D1_PRE_RELEASE_CONSENSUS_MISSING", r["blockers"])
        self.safe(r)

    def test_stale_macro_and_surprise_are_both_visible(self):
        macro = {"W1": W-timedelta(hours=3), "D1": RELEASE-timedelta(minutes=1)}
        r = inspect(macro=macro)
        self.assertEqual(r["blockers"], ["D1_MACRO_CONTEXT_PREDATES_ACTUAL_CAPTURE",
                                         "D1_SURPRISE_DIRECTION_NOT_INTERPRETED_OR_VALIDATED"])
        self.safe(r)

    def test_future_actual_cannot_leak_into_prior_weekly_decision(self):
        e = catalog()
        e["W1"] = e["D1"]
        r = inspect(events=e)
        self.assertEqual(r["blockers"], ["W1_EVENT_ROUTE_REJECTED_FUTURE_OR_INVALID"])
        self.safe(r)

    def test_pre_event_blackout_within_30_minutes(self):
        release = W + timedelta(minutes=10)
        e = {"W1": [news(scheduled=release)], "D1": [news(actual="0.3", scheduled=release)]}
        r = inspect(events=e)
        self.assertIn("W1_HIGH_IMPACT_EVENT_IMMINENT", r["blockers"])
        self.safe(r)

    def test_no_blackout_if_beyond_30_minutes(self):
        release = W + timedelta(minutes=31)
        e = {"W1": [news(scheduled=release)], "D1": [news(actual="0.3", scheduled=release)]}
        r = inspect(events=e)
        self.assertFalse(r["research_veto"])
        self.safe(r)

    def test_event_on_unrelated_currency_not_a_veto_for_this_pair(self):
        r = inspect(events=catalog(currency="GBP"))
        self.assertEqual((r["W1_event_count"], r["D1_event_count"]), (0, 0))
        self.assertFalse(r["research_veto"])
        self.safe(r)

    def test_either_side_of_cross_receives_relevant_event(self):
        for pair in ("EUR/USD", "USD/JPY", "USD/CHF", "GBP/USD"):
            with self.subTest(pair=pair):
                r = inspect(asset=pair)
                self.assertEqual(r["D1_event_count"], 1)
                self.assertTrue(r["research_veto"])
                self.safe(r)

    def test_28_pair_coverage_is_distinct_from_7_usd_crosses(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        n = sum(inspect(asset=pair)["D1_event_count"] for pair in OFFICIAL_PAIRS)
        self.assertEqual(n, 7)

    def test_medium_event_is_not_high_impact_veto(self):
        r = inspect(events=catalog(importance="MEDIUM"))
        self.assertFalse(r["research_veto"])
        self.safe(r)

    def test_duplicate_real_event_hidden_behind_two_ids_is_blocked(self):
        e = catalog(actual="0.3")
        e["D1"].append(replace(e["D1"][0], event_id="US_CPI_ANOTHER_ID"))
        r = inspect(events=e)
        self.assertIn("D1_DUPLICATE_ECONOMIC_RELEASE", r["blockers"])
        self.safe(r)

    def test_duplicate_semantic_event_with_rescheduled_time_is_not_two_events(self):
        e = catalog(actual="0.3")
        e["D1"].append(replace(e["D1"][0], event_id="US_CPI_OTHER_TIME",
                               scheduled_release_at=RELEASE + timedelta(minutes=1),
                               actual_published_at=RELEASE + timedelta(minutes=1),
                               actual_captured_at=RELEASE + timedelta(minutes=2)))
        r = inspect(events=e)
        self.assertEqual(r["blockers"], ["D1_DUPLICATE_ECONOMIC_RELEASE"])
        self.safe(r)

    def test_changed_calendar_schedule_between_horizons_is_reviewed(self):
        e = catalog(actual="0.3")
        e["D1"][0] = replace(e["D1"][0], scheduled_release_at=RELEASE+timedelta(minutes=1),
                             actual_published_at=RELEASE+timedelta(minutes=1),
                             actual_captured_at=RELEASE+timedelta(minutes=2))
        r = inspect(events=e)
        self.assertEqual(r["blockers"], ["EVENT_RELEASE_SCHEDULE_REVISED_NEEDS_REVIEW"])
        self.safe(r)

    def test_old_high_impact_surprise_not_permanent_veto(self):
        old = datetime(2026, 10, 20, 13, 30, tzinfo=UTC)
        def source():
            return replace(news(scheduled=old, actual="0.4"),
                           calendar_captured_at=old-timedelta(days=2),
                           consensus_captured_at=old-timedelta(days=1))
        event = source()
        e = {"D1": [event], "W1": [event]}
        r = inspect(events=e)
        self.assertFalse(r["research_veto"])
        self.assertTrue(r["W1_events"][0]["event_outside_research_relevance_window"])
        self.assertTrue(r["D1_events"][0]["event_outside_research_relevance_window"])
        self.safe(r)

    def test_duplicate_id_rejected_by_router(self):
        e = catalog()
        e["D1"].append(e["D1"][0])
        r = inspect(events=e)
        self.assertIn("D1_EVENT_ROUTE_REJECTED_FUTURE_OR_INVALID", r["blockers"])
        self.safe(r)

    def test_wrong_unit_invalid_metric_or_future_consensus_fail_closed(self):
        for change in ({"unit": "PERCENT_YOY_NSA"}, {"metric": "NFP_CHANGE"},
                       {"consensus_captured_at": D+timedelta(seconds=1)}):
            with self.subTest(change=change):
                e = catalog()
                e["D1"] = [replace(e["D1"][0], **change)]
                r = inspect(events=e)
                self.assertTrue(r["research_veto"])
                self.safe(r)

    def test_empty_calendars_are_not_proof_of_no_news(self):
        r = inspect(events={"D1": [], "W1": []})
        self.assertIn("W1_CALENDAR_EMPTY_COVERAGE_NOT_PROVEN", r["blockers"])
        self.assertIn("D1_CALENDAR_EMPTY_COVERAGE_NOT_PROVEN", r["blockers"])
        self.safe(r)

    def test_not_supplied_events_and_macro_clock_block(self):
        r = review(candidate=Candidate(), events_by_horizon=None,
                   decision_at_by_horizon={"D1": D, "W1": W},
                   macro_captured_at_by_horizon={"D1": D, "W1": W}, as_of_utc=NOW)
        self.assertEqual(r["blockers"], ["ECONOMIC_EVENT_SNAPSHOTS_NOT_SUPPLIED"])
        self.safe(r)
        r = inspect(macro={})
        self.assertEqual(r["blockers"], ["INVALID_D1_W1_EVENT_OR_TIME_MAP"])
        self.safe(r)

    def test_wrong_clocks_and_future_candidate_rejected(self):
        cases = [
            {"candidate": Candidate(evaluated_at=NOW+timedelta(seconds=1))},
            {"candidate": Candidate(evaluated_at=D.replace(tzinfo=None))},
            {"cutoffs": {"D1": W, "W1": D}},
            {"macro": {"D1": D + timedelta(seconds=1), "W1": W}},
            {"now": NOW.replace(tzinfo=None)},
        ]
        for args in cases:
            with self.subTest(args=args):
                r = inspect(**args)
                self.assertTrue(r["research_veto"])
                self.safe(r)

    def test_index_unsupported_and_disagreement_block(self):
        for p in ("WIN", "WDO", "US500", "NAS100", "US30", "EURUSD"):
            with self.subTest(asset=p):
                r = inspect(asset=p)
                self.assertEqual(r["reason"], "INVALID_OR_OUT_OF_SCOPE_FX_28_ASSET")
                self.safe(r)
        r = inspect(candidate=Candidate(weekly="BAIXA"))
        self.assertEqual(r["reason"], "D1_W1_DIRECTION_CONFLICT")
        self.safe(r)


if __name__ == "__main__":
    unittest.main()
