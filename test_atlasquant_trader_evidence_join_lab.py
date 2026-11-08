"""Synthetic-only cross-layer chronology and abstention tests."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_evidence_join_lab import inspect_fx_evidence_join_lab as join
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
        self.assertEqual(len(data["blockers"]), 4)
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


if __name__ == "__main__":
    unittest.main()
