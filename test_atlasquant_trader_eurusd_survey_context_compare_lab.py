"""The bridge must not infer a cross-currency rate spread from surveys."""
import unittest

from atlasquant_trader_ecb_spf_dfr_context_lab import SCHEMA as EUR_SCHEMA
from atlasquant_trader_nyfed_sme_sep2026_lab import SCHEMA as USD_SCHEMA
from atlasquant_trader_eurusd_survey_context_compare_lab import (
    compare_eurusd_survey_context_lab as compare,
)


def eur():
    return {"schema": EUR_SCHEMA, "source_id": "ECB_SPF_2026Q3",
            "currency": "EUR", "quarterly_context_parsed": True,
            "official_release_date": "2026-07-24",
            "q4_2026_modal_dfr_forecast_from_q3_pct": "2.50",
            "html_sha256": "a" * 64,
            "historical_point_in_time_eligible": False,
            "trade_authorized": False}


def usd():
    return {"schema": USD_SCHEMA, "source_id": "NYFED_SME_SEPTEMBER_2026",
            "currency": "USD", "survey_meeting_end_date": "2026-10-28",
            "aggregation_is_median_of_modal_point_forecasts": True,
            "median_target_range_midpoint_pct": "3.63",
            "source_raw_sha256": "b" * 64,
            "historical_point_in_time_eligible": False,
            "trade_authorized": False}


class EurusdSurveyBridgeTests(unittest.TestCase):
    def test_both_valid_only_admit_research_context(self):
        r = compare(eur(), usd())
        self.assertEqual(r["state"], "LAB_BILATERAL_CONTEXTS_DISTINCT_NOT_RATE_COMPARABLE")
        self.assertEqual(r["eur_horizon"], "2026Q4")
        self.assertEqual(r["usd_meeting_end_date"], "2026-10-28")
        self.assertFalse(r["same_horizon_and_policy_measure"])
        self.assertFalse(r["independent_historical_vintage_pair_verified"])
        self.assertIsNone(r["interest_rate_spread_bps"])
        self.assertIsNone(r["fx_bias"])

    def test_missing_euro_or_dollar_denied(self):
        for a, b in ((None, usd()), (eur(), None), ({}, usd()), (eur(), {})):
            self.assertEqual(compare(a, b)["state"],
                             "LAB_BILATERAL_CONTEXT_EVIDENCE_MISSING")

    def test_wrong_currency_and_schema_denied(self):
        for side, bad in (("eur", {**eur(), "currency": "USD"}),
                          ("usd", {**usd(), "schema": EUR_SCHEMA}),
                          ("usd", {**usd(), "currency": "EUR"})):
            with self.subTest(side=side, bad=bad):
                a, b = (bad, usd()) if side == "eur" else (eur(), bad)
                self.assertEqual(compare(a, b)["reason"], "SOURCE_RECEIPT_NOT_ELIGIBLE")

    def test_sha_malformed_rejected(self):
        for a, b in (({**eur(), "html_sha256": "not sha"}, usd()),
                     (eur(), {**usd(), "source_raw_sha256": "A" * 64}),
                     (eur(), {**usd(), "source_raw_sha256": None})):
            self.assertEqual(compare(a, b)["state"],
                             "LAB_BILATERAL_CONTEXT_EVIDENCE_MISSING")

    def test_upstream_true_trade_flag_must_not_pass_bridge(self):
        self.assertEqual(compare({**eur(), "trade_authorized": True}, usd())["reason"],
                         "SOURCE_RECEIPT_NOT_ELIGIBLE")
        self.assertEqual(compare(eur(), {**usd(), "historical_point_in_time_eligible": True})["reason"],
                         "SOURCE_RECEIPT_NOT_ELIGIBLE")

    def test_every_branch_is_non_operational(self):
        for a, b in ((eur(), usd()), (eur(), {}), ({}, usd())):
            r = compare(a, b)
            for key in ("bilateral_consensus_verified", "trade_authorized",
                        "can_feed_live_radar", "publishable", "worker_enabled",
                        "scheduler_enabled"):
                self.assertFalse(r[key])
            self.assertIsNone(r["interest_rate_spread_bps"])
            self.assertIsNone(r["market_surprise_bps"])
            self.assertIsNone(r["fx_bias"])
            self.assertEqual(r["operational_bias"], "AGUARDAR")
            self.assertEqual(r["new_cost_brl"], 0)


if __name__ == "__main__":
    unittest.main()
