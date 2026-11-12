"""Synthetic, offline contract tests for MN1/W1/D1 macro coverage join."""
from datetime import datetime, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_three_horizon_coverage_lab import (
    inspect_g8_three_horizon_coverage_lab as inspect,
)
from test_atlasquant_trader_g8_macro_matrix_pit_lab import fixtures

UTC = timezone.utc
MONTH = datetime(2026, 11, 1, tzinfo=UTC)
WEEK = datetime(2026, 11, 3, 12, tzinfo=UTC)
DAY = datetime(2026, 11, 5, 12, tzinfo=UTC)
NOW = datetime(2026, 11, 8, tzinfo=UTC)


def snapshots():
    return {h: fixtures() for h in ("MN1", "W1", "D1")}


def clocks():
    return {"MN1": MONTH, "W1": WEEK, "D1": DAY}


def audit(*, receipts=None, decisions=None, as_of=NOW):
    return inspect(
        receipts_by_horizon=snapshots() if receipts is None else receipts,
        decision_at_by_horizon=clocks() if decisions is None else decisions,
        evaluated_at_utc=as_of,
    )


class ThreeHorizonCoverageTests(unittest.TestCase):
    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        for key in (
            "publishable", "trade_authorized", "live_alert_allowed",
            "worker_enabled", "scheduler_enabled",
            "source_independently_authenticated",
            "historical_point_in_time_independently_verified",
            "economic_metric_comparability_validated",
            "three_horizon_evidence_is_independent_trials",
        ):
            self.assertFalse(result[key], key)
        for key in (
            "monthly_directional_bias", "weekly_directional_bias",
            "daily_directional_bias", "calibrated_direction_probability",
            "validated_accuracy",
        ):
            self.assertIsNone(result[key], key)
        self.assertEqual(
            (result["http_requests"], result["file_writes"],
             result["new_cost_brl"]), (0, 0, 0),
        )

    def test_three_valid_claim_sets_do_not_create_direction(self):
        result = audit()
        self.assertEqual(result["state"], "LAB_THREE_HORIZON_CLAIM_COVERAGE_NO_GO")
        self.assertEqual(result["pair_count"], 28)
        self.assertEqual(result["claim_only_complete_all_horizons"], 28)
        self.assertEqual(result["pairs_with_any_missing_or_rejected_horizon"], 0)
        self.assertEqual(set(result["pairs"]), set(OFFICIAL_PAIRS))
        self.assertEqual(set(result["horizon_audits"]), {"MN1", "W1", "D1"})
        self.assertEqual(result["decision_cutoffs_utc"]["MN1"], MONTH.isoformat())
        for info in result["pairs"].values():
            self.assertTrue(info["all_three_claim_only_complete_not_attested"])
            self.assertFalse(info["directional_agreement_checked"])
            self.assertIsNone(info["directional_signal"])
            self.assertEqual(info["operational_bias"], "AGUARDAR")
        self.safe(result)

    def test_later_source_only_blocks_monthly_snapshot(self):
        rows = snapshots()
        # One receipt exists for the weekly/daily decision but was not
        # captured at the monthly cutoff.
        for h in ("MN1", "W1", "D1"):
            row = next(x for x in rows[h]["USD"] if x["indicator"] == "CPI_YOY")
            row["captured_at_utc"] = "2026-11-02T11:00:00Z"
        result = audit(receipts=rows)
        self.assertEqual(result["horizon_audits"]["MN1"]["rejected_pairs"], 7)
        self.assertEqual(result["horizon_audits"]["W1"]["rejected_pairs"], 0)
        self.assertEqual(result["horizon_audits"]["D1"]["rejected_pairs"], 0)
        self.assertEqual(result["claim_only_complete_all_horizons"], 21)
        usd = result["pairs"]["EUR/USD"]["horizons"]
        self.assertFalse(usd["MN1"]["claim_only_complete"])
        self.assertTrue(usd["W1"]["claim_only_complete"])
        self.assertTrue(usd["D1"]["claim_only_complete"])
        self.safe(result)

    def test_missing_daily_currency_remains_seven_pair_gap(self):
        rows = snapshots()
        rows["D1"]["NZD"] = []
        result = audit(receipts=rows)
        self.assertEqual(result["horizon_audits"]["D1"]["incomplete_pairs"], 7)
        self.assertEqual(result["horizon_audits"]["MN1"]["incomplete_pairs"], 0)
        self.assertEqual(result["horizon_audits"]["W1"]["incomplete_pairs"], 0)
        self.assertEqual(result["claim_only_complete_all_horizons"], 21)
        for pair, info in result["pairs"].items():
            self.assertEqual(
                info["all_three_claim_only_complete_not_attested"],
                "NZD" not in pair,
                pair,
            )
        self.safe(result)

    def test_month_rollover_does_not_force_false_horizon_order(self):
        # On Dec 1, a new monthly cutoff can be later than the prior
        # weekly cutoff (Nov 30), while D1 follows both (Dec 2).
        cutoffs = {
            "W1": datetime(2026, 11, 30, tzinfo=UTC),
            "MN1": datetime(2026, 12, 1, tzinfo=UTC),
            "D1": datetime(2026, 12, 2, tzinfo=UTC),
        }
        result = audit(
            decisions=cutoffs,
            as_of=datetime(2026, 12, 3, tzinfo=UTC),
        )
        self.assertEqual(result["state"], "LAB_THREE_HORIZON_CLAIM_COVERAGE_NO_GO")
        self.assertEqual(result["pair_count"], 28)
        self.assertEqual(result["decision_cutoffs_utc"]["MN1"],
                         cutoffs["MN1"].isoformat())
        self.safe(result)

    def test_empty_sources_cannot_mean_no_events_or_probabilities(self):
        rows = {h: {c: [] for c in CURRENCIES}
                for h in ("MN1", "W1", "D1")}
        result = audit(receipts=rows)
        self.assertEqual(result["claim_only_complete_all_horizons"], 0)
        self.assertEqual(result["pairs_with_any_missing_or_rejected_horizon"], 28)
        self.assertEqual(result["pair_count"], 28)
        self.safe(result)

    def test_missing_extra_or_m1_horizon_is_invalid(self):
        cases = (
            {"MN1": fixtures(), "D1": fixtures()},
            {"MN1": fixtures(), "W1": fixtures(), "D1": fixtures(),
             "M1": fixtures()},
        )
        for rows in cases:
            with self.subTest(keys=tuple(rows)):
                r = audit(receipts=rows)
                self.assertEqual(r["state"], "LAB_THREE_HORIZON_COVERAGE_BLOCKED")
                self.safe(r)

    def test_invalid_clock_and_post_evaluation_cutoff_fail_closed(self):
        for cutoffs, now in (
            ({"MN1": MONTH, "W1": WEEK, "D1": DAY.replace(tzinfo=None)}, NOW),
            ({"MN1": MONTH, "W1": WEEK, "D1": NOW}, DAY),
        ):
            with self.subTest(decisions=cutoffs):
                r = audit(decisions=cutoffs, as_of=now)
                self.assertEqual(r["state"], "LAB_THREE_HORIZON_COVERAGE_BLOCKED")
                self.safe(r)

    def test_semantically_invalid_horizon_blocks_entire_join(self):
        rows = snapshots()
        rows["MN1"]["EUR"][0]["currency"] = "USD"
        result = audit(receipts=rows)
        self.assertEqual(result["state"], "LAB_THREE_HORIZON_COVERAGE_BLOCKED")
        self.assertEqual(result["reason"], "MN1_INVALID_OR_REJECTED_MATRIX_INPUT")
        self.assertEqual(result["pair_count"], 0)
        self.safe(result)


if __name__ == "__main__":
    unittest.main()
