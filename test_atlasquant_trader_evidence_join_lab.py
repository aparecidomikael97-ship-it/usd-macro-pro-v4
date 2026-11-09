"""Synthetic-only cross-layer chronology and abstention tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_evidence_join_lab import inspect_fx_evidence_join_lab as join
from atlasquant_trader_g8_event_relevance_lab import EventSnapshot
from atlasquant_trader_market_regime_veto_lab import ClosedMarketBar
from atlasquant_trader_selective_bias_gate_lab import (
    BiasObservation, HoldoutWindow, SelectiveAuditClaims,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)
WHEN = NOW - timedelta(minutes=5)
FLAGS = SelectiveAuditClaims(True, True, True, True, True, True)


def epoch(y, m, d):
    return int(datetime(y, m, d, tzinfo=UTC).timestamp())


def candidate(asset="EUR/USD", when=WHEN):
    return BiasObservation(
        asset=asset, horizon="D1", evaluated_at=when, weekly="ALTA",
        daily="ALTA", grade_0_to_10=8,
        macro_captured_at=when - timedelta(hours=1),
        snapshot_sha256="a" * 64,
    )


def prior(c):
    return [replace(c, evaluated_at=WHEN - timedelta(minutes=30),
                    macro_captured_at=WHEN - timedelta(hours=2),
                    snapshot_sha256="b" * 64)]


def holdout(c):
    return [HoldoutWindow(c.asset, c.horizon, c.daily,
                          datetime(2024, 1 + 2 * i, 1, tzinfo=UTC),
                          datetime(2024, 2 + 2 * i, 15, tzinfo=UTC),
                          40, 38) for i in range(3)]


def receipts():
    result = {}
    for curr in CURRENCIES:
        result[curr] = [
            {
                "currency": curr, "indicator": indicator,
                "observation_period": "2026-09", "value": "2.0",
                "published_at_utc": "2026-10-29T12:00:00Z",
                "captured_at_utc": "2026-10-29T12:05:00Z",
                "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                                else "OFFICIAL_STATISTICS_OFFICE"),
                "source_sha256": "a" * 64,
            } for indicator in ("CPI_YOY", "POLICY_RATE")
        ]
    return result


def prices():
    return {
        "D1": {"times": [epoch(2026, 11, 3), epoch(2026, 11, 4),
                         epoch(2026, 11, 5)], "first": 0, "last": 2},
        "W1": {"times": [epoch(2026, 10, 19), epoch(2026, 10, 26)],
               "first": 0, "last": 1},
    }


class EvidenceJoinTests(unittest.TestCase):
    def case(self, c=None, **changes):
        c = c or candidate()
        opts = {
            "candidate": c,
            "previous_confirmations": prior(c) if isinstance(c, BiasObservation) else [],
            "holdout_windows": holdout(c) if isinstance(c, BiasObservation) else [],
            "audit_claims": FLAGS,
            "receipts_by_currency": receipts(),
            "macro_decision_at": {
                "D1": datetime(2026, 11, 5, 12, tzinfo=UTC),
                "W1": datetime(2026, 11, 3, 12, tzinfo=UTC),
            },
            "price_windows": prices(), "now": NOW,
        }
        opts.update(changes)
        return join(**opts)

    def no_live(self, data):
        self.assertEqual(data["operational_bias"], "AGUARDAR")
        self.assertFalse(data["publishable"])
        self.assertFalse(data["live_alert_allowed"])
        self.assertFalse(data["trade_authorized"])
        self.assertFalse(data["worker_enabled"])
        self.assertFalse(data["scheduler_enabled"])
        self.assertFalse(data["economic_originals_authenticated"])
        self.assertFalse(data["macro_bilateral_values_comparable"])
        self.assertFalse(data["event_forecast_validated"])
        self.assertFalse(data["market_data_historical_pit_verified"])
        self.assertFalse(data["regime_source_independently_authenticated"])
        self.assertIsNone(data["candidate_direction_for_publication"])
        self.assertIsNone(data["calibrated_direction_probability"])
        self.assertIsNone(data["validated_directional_accuracy"])
        self.assertTrue(data["research_only"])
        self.assertEqual((data["http_requests"], data["new_cost_brl"]), (0, 0))

    def test_full_synthetic_alignment_is_only_missing_proof_diagnostic(self):
        data = self.case()
        self.assertEqual(data["state"], "LAB_CROSS_LAYER_EVIDENCE_DIAGNOSTIC_NO_GO")
        self.assertEqual(data["macro_metadata_claims"], {"D1": True, "W1": True})
        self.assertEqual(data["price_calendar_contiguous_claims"], {"D1": True, "W1": True})
        self.assertEqual(data["selective_research_state"],
                         "LAB_INTERNAL_RESEARCH_CANDIDATE_NOT_LIVE")
        self.assertEqual(len(data["blockers"]), 7)
        self.assertIn("REGIME_MARKET_REGIME_BARS_MISSING_OR_WRONG_HORIZONS", data["blockers"])
        self.assertTrue(data["regime_research_veto"])
        self.assertIn("NEWS_ECONOMIC_EVENT_SNAPSHOTS_NOT_SUPPLIED", data["blockers"])
        self.assertTrue(data["news_surprise_research_veto"])
        self.assertIn("POLICY_RATE_EXPECTATION_SNAPSHOTS_NOT_SUPPLIED", data["blockers"])
        self.assertTrue(data["rate_path_research_veto"])
        self.no_live(data)

    def test_pair_scope_uses_g8_28_not_index_reinterpretation(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for asset, reason in (("WIN", "INDEX_REQUIRES_SEPARATE_MACRO_AND_PRICE_MODEL"),
                              ("US500", "INDEX_REQUIRES_SEPARATE_MACRO_AND_PRICE_MODEL"),
                              ("EURUSD", "OUTSIDE_CANONICAL_28_FX_PAIRS")):
            with self.subTest(asset=asset):
                data = self.case(candidate(asset))
                self.assertEqual(data["reason"], reason)
                self.no_live(data)

    def test_all_28_pairs_share_report_logic_without_a_market_direction(self):
        for asset in OFFICIAL_PAIRS:
            with self.subTest(asset=asset):
                data = self.case(candidate(asset))
                self.assertTrue(data["macro_metadata_claims"]["D1"])
                self.assertTrue(data["macro_metadata_claims"]["W1"])
                self.no_live(data)

    def test_missing_currency_document_blocks_its_crosses_only(self):
        source = receipts()
        source["NZD"] = source["NZD"][1:]
        data = self.case(candidate("NZD/USD"), receipts_by_currency=source)
        self.assertFalse(data["macro_metadata_claims"]["D1"])
        self.assertFalse(data["macro_metadata_claims"]["W1"])
        self.assertIn("D1_PAIR_MACRO_MISSING_STALE_OR_REJECTED", data["blockers"])
        self.no_live(data)

    def test_release_after_daily_cutoff_cannot_be_inserted_retroactively(self):
        source = receipts()
        source["EUR"][0]["published_at_utc"] = "2026-11-05T12:00:01Z"
        source["EUR"][0]["captured_at_utc"] = "2026-11-05T12:00:02Z"
        data = self.case(receipts_by_currency=source)
        self.assertFalse(data["macro_metadata_claims"]["D1"])
        self.assertFalse(data["macro_metadata_claims"]["W1"])
        self.no_live(data)

    def test_decision_order_and_no_future_macro(self):
        for clocks in (
            {"D1": NOW + timedelta(minutes=1), "W1": NOW},
            {"D1": NOW - timedelta(days=4), "W1": NOW - timedelta(days=1)},
            {"D1": datetime(2026, 11, 5), "W1": NOW - timedelta(days=5)},
        ):
            with self.subTest(clocks=clocks):
                data = self.case(macro_decision_at=clocks)
                self.assertEqual(data["reason"], "MACRO_DECISIONS_AFTER_PRICE_OR_WRONG_ORDER")
                self.no_live(data)

    def test_d1_weekend_gap_remains_blocked_even_with_good_macro(self):
        p = prices()
        p["D1"]["times"] = [epoch(2026, 11, 3), epoch(2026, 11, 5)]
        p["D1"]["last"] = 1
        data = self.case(price_windows=p)
        self.assertIn("D1_PRICE_GAP_REQUIRES_CALENDAR_REVIEW", data["blockers"])
        self.assertFalse(data["price_calendar_contiguous_claims"]["D1"])
        self.no_live(data)

    def test_latest_d1_or_w1_open_bar_is_not_a_closed_confirmation(self):
        for tf, values in (("D1", [epoch(2026, 11, 7), epoch(2026, 11, 8)]),
                           ("W1", [epoch(2026, 10, 26), epoch(2026, 11, 2)])):
            with self.subTest(tf=tf):
                p = prices()
                p[tf]["times"] = values
                p[tf]["last"] = 1
                data = self.case(price_windows=p)
                self.assertIn(f"{tf}_PRICE_BAR_NOT_YET_CLOSED_ASOF", data["blockers"])
                self.no_live(data)

    def test_broken_or_unbounded_price_list_abstains(self):
        for bad in (None, [], [123], list(range(10001))):
            p = prices()
            p["W1"]["times"] = bad
            data = self.case(price_windows=p)
            self.assertIn("W1_PRICE_WINDOW_INVALID", data["blockers"])
            self.no_live(data)

    def test_event_released_after_macro_snapshot_invalidates_selective(self):
        data = self.case(high_impact_events=[NOW - timedelta(minutes=45)])
        self.assertIn("SELECTIVE_GATE_MACRO_CONTEXT_PREDATES_HIGH_IMPACT_RELEASE",
                      data["blockers"])
        self.no_live(data)

    def test_unverified_event_actual_invalidates_selective(self):
        data = self.case(unverified_event_actual_pending=True)
        self.assertIn("SELECTIVE_GATE_EVENT_ACTUAL_NOT_VERIFIED", data["blockers"])
        self.no_live(data)

    def test_high_grade_cannot_overcome_missing_confirmations(self):
        c = replace(candidate(), grade_0_to_10=10)
        data = self.case(c, previous_confirmations=[])
        self.assertIn("SELECTIVE_GATE_INSUFFICIENT_DISTINCT_CONFIRMATIONS", data["blockers"])
        self.no_live(data)

    def test_no_80_percent_accuracy_claim_even_with_fictitious_success(self):
        data = self.case()
        self.assertIsNone(data["validated_directional_accuracy"])
        self.assertIsNone(data["calibrated_direction_probability"])
        self.assertNotIn("research_candidate_direction", data)
        self.no_live(data)

    def test_bad_candidate_or_untrusted_price_structure_fails_closed(self):
        self.assertEqual(self.case(now=None)["reason"], "INVALID_CANDIDATE_OR_CLOCK")
        self.assertEqual(self.case(c=object())["reason"], "INVALID_CANDIDATE_OR_CLOCK")
        self.assertEqual(self.case(price_windows={})["reason"],
                         "INVALID_HORIZON_OR_LAYER_INPUTS")
        self.assertEqual(self.case(candidate(when=NOW + timedelta(seconds=1)))["reason"],
                         "FUTURE_OR_INVALID_CANDIDATE")


    def test_high_impact_surprise_is_an_explicit_d1_veto_not_currency_direction(self):
        release = datetime(2026, 11, 4, 13, 30, tzinfo=UTC)
        pre = EventSnapshot(
            event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
            target_period="2026-10", unit="PERCENT_MOM_SA", importance="HIGH",
            scheduled_release_at=release,
            calendar_captured_at=datetime(2026, 11, 2, 10, tzinfo=UTC),
            consensus_value="0.3",
            consensus_captured_at=datetime(2026, 11, 2, 11, tzinfo=UTC),
        )
        post = replace(
            pre, actual_value="0.4", actual_published_at=release,
            actual_captured_at=release + timedelta(minutes=1),
        )
        kwargs = {
            "news_events_by_horizon": {"W1": [pre], "D1": [post]},
            "news_macro_captured_at_by_horizon": {
                "W1": datetime(2026, 11, 3, 10, tzinfo=UTC),
                "D1": datetime(2026, 11, 4, 15, tzinfo=UTC),
            },
        }
        result = self.case(**kwargs)
        self.assertTrue(result["news_surprise_research_veto"])
        self.assertIn("NEWS_D1_SURPRISE_DIRECTION_NOT_INTERPRETED_OR_VALIDATED",
                      result["blockers"])
        self.assertEqual(result["news_surprise_D1_events"][0]["surprise_documentary"],
                         "0.1")
        self.assertIsNone(result["news_surprise_D1_events"][0]["directional_fx_impact"])
        self.no_live(result)

        no_surprise = self.case(**{**kwargs, "news_events_by_horizon": {
            "W1": [pre], "D1": [replace(post, actual_value="0.3")]}})
        self.assertFalse(no_surprise["news_surprise_research_veto"])
        self.assertEqual(no_surprise["news_surprise_research_state"],
                         "LAB_SURPRISE_NO_DOCUMENTARY_VETO_NO_GO")
        self.no_live(no_surprise)

    def test_news_actual_from_daily_cannot_leak_to_weekly_cutoff(self):
        release = datetime(2026, 11, 4, 13, 30, tzinfo=UTC)
        event = EventSnapshot(
            event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
            target_period="2026-10", unit="PERCENT_MOM_SA", importance="HIGH",
            scheduled_release_at=release,
            calendar_captured_at=datetime(2026, 11, 2, 10, tzinfo=UTC),
            consensus_value="0.3",
            consensus_captured_at=datetime(2026, 11, 2, 11, tzinfo=UTC),
            actual_value="0.4", actual_published_at=release,
            actual_captured_at=release + timedelta(minutes=1),
        )
        result = self.case(
            news_events_by_horizon={"W1": [event], "D1": [event]},
            news_macro_captured_at_by_horizon={
                "W1": datetime(2026, 11, 3, 10, tzinfo=UTC),
                "D1": datetime(2026, 11, 4, 15, tzinfo=UTC),
            },
        )
        self.assertIn("NEWS_W1_EVENT_ROUTE_REJECTED_FUTURE_OR_INVALID",
                      result["blockers"])
        self.assertTrue(result["news_surprise_research_veto"])
        self.no_live(result)


    def test_regime_complete_aligned_synthetic_bars_never_unlock_cross_layer(self):
        def bars(horizon):
            interval = timedelta(days=7 if horizon == "W1" else 1)
            anchor = (datetime(2026, 10, 26, tzinfo=UTC) if horizon == "W1"
                      else datetime(2026, 11, 3, tzinfo=UTC))
            records = []
            for i in range(46):
                opened = anchor - (45-i)*interval
                p = 100 + i
                records.append(ClosedMarketBar(
                    opened_at=opened, closed_at=opened+interval,
                    recorded_at=opened+interval+timedelta(minutes=1),
                    open=str(p), high=str(p+1.2), low=str(p-0.2),
                    close=str(p+1), source_sha256_claim="d"*64,
                ))
            return records

        data = self.case(regime_bars_by_horizon={"W1": bars("W1"), "D1": bars("D1")})
        self.assertFalse(data["regime_research_veto"])
        self.assertEqual(data["regime_research_state"], "LAB_REGIME_ALIGNMENT_DOCUMENTARY_NOT_LIVE")
        self.assertEqual(data["regime_D1"]["regime"], "TREND")
        self.assertEqual(data["regime_W1"]["regime"], "TREND")
        self.assertEqual(data["state"], "LAB_CROSS_LAYER_EVIDENCE_DIAGNOSTIC_NO_GO")
        self.assertIn("ORIGINAL_ECONOMIC_SOURCES_AND_BILATERAL_VALUES_UNATTESTED", data["blockers"])
        self.no_live(data)

    def test_regime_range_adds_veto_without_fabricating_probabilities(self):
        def bars(horizon, lateral=False):
            interval = timedelta(days=7 if horizon == "W1" else 1)
            anchor = (datetime(2026, 10, 26, tzinfo=UTC) if horizon == "W1"
                      else datetime(2026, 11, 3, tzinfo=UTC))
            records = []
            prior = 100
            for i in range(46):
                opened = anchor - (45-i)*interval
                next_close = (100 + (1 if i % 2 else 0)) if lateral else prior + 1
                records.append(ClosedMarketBar(
                    opened_at=opened, closed_at=opened+interval,
                    recorded_at=opened+interval+timedelta(minutes=1),
                    open=str(prior), high=str(max(prior, next_close)+0.2),
                    low=str(min(prior, next_close)-0.2),
                    close=str(next_close), source_sha256_claim="d"*64,
                ))
                prior = next_close
            return records

        data = self.case(regime_bars_by_horizon={"W1": bars("W1"), "D1": bars("D1", lateral=True)})
        self.assertTrue(data["regime_research_veto"])
        self.assertEqual(data["regime_D1"]["regime"], "RANGE")
        self.assertIn("REGIME_D1_RANGE_DOES_NOT_SUPPORT_DIRECTIONAL_RESEARCH", data["blockers"])
        self.no_live(data)


if __name__ == "__main__":
    unittest.main()
