"""PPI x FX7 documentary reconciliation: synthetic, no historical 2026 PPI actual."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_ppi_surprise_fx7_reconciliation_lab import (
    reconcile_ppi_surprise_fx7_lab as reconcile,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    _no_go, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC, USD_FX, WINDOWS,
)
from atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    inspect_ppi_oct2026_first_print_lab as extract,
    compare_ppi_actual_to_frozen_consensus_lab as compare,
)
from test_atlasquant_trader_us_ppi_oct2026_actual_table_guard_lab import (
    raw, receipt, td, te, AFTER,
)

UTC = timezone.utc
NOW = LAST_REQUIRED_CLOSE_UTC + timedelta(hours=1)


def mock_comparison(*, headline="0.5", core="0.2"):
    """Made-up synthetic official HTML values: NEVER real PPI 2026 actual."""
    content = raw(head=headline, core=core)
    candidate = extract(raw_html=content, receipt=receipt(content), as_of_utc=AFTER)
    return compare(actual=candidate, td_snapshot=td(), te_snapshot=te())


def mock_fx7():
    """Synthetic price reaction report, no MT5 or archive claims authenticated."""
    doc = _no_go(
        "LOCAL_PRICE_BYTES_RESEARCH_ONLY_NO_CAUSALITY_OR_BROKER_ATTESTATION",
        state="LAB_PPI_FX_7PAIR_FORWARD_REACTION_DOCUMENTARY_NO_GO")
    doc["price_reactions_usd_normalized_bps"] = {
        symbol: {name: (
            "3.00" if i < 4 else "-2.00" if i < 6 else "0.00")
            for name, _ in WINDOWS}
        for i, symbol in enumerate(USD_FX)}
    doc["archive_captured_at_utc_claim"] = (
        LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=3)).isoformat()
    doc["local_seven_file_hashes_match"] = True
    doc["independent_economic_event_sample_count"] = 1
    return doc


class PpiFx7ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.ppi = mock_comparison()
        self.fx = mock_fx7()

    def run_join(self, *, ppi=None, fx=None, clock=NOW):
        return reconcile(
            ppi_comparison=self.ppi if ppi is None else ppi,
            fx7_reaction=self.fx if fx is None else fx,
            as_of_utc=clock)

    def safe(self, r):
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["publishable"])
        self.assertFalse(r["live_alert_allowed"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["official_ppi_first_print_independently_authenticated"])
        self.assertFalse(r["two_consensus_sources_independently_attested"])
        self.assertFalse(r["ppi_actual_available_at_original_release_independently_attested"])
        self.assertFalse(r["fx_prices_broker_pit_provenance_authenticated"])
        self.assertFalse(r["broker_bidask_spread_and_slippage_verified"])
        self.assertFalse(r["causal_event_impact_identified"])
        self.assertIsNone(r["historical_out_of_sample_accuracy"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertIsNone(r["directional_forecast"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual(r["independent_directional_predictions_validated"], 0)
        self.assertEqual(r["files_written"], 0)
        self.assertEqual(r["http_requests"], 0)
        self.assertEqual(r["new_cost_brl"], 0)

    def test_synthetic_join_counts_only_observed_fx_direction(self):
        r = self.run_join()
        self.safe(r)
        self.assertEqual(r["state"],
                         "LAB_PPI_SURPRISE_FX7_OBSERVED_JOINT_RESEARCH_NO_GO")
        self.assertEqual(r["headline_surprise_pp"], "0.1")
        self.assertEqual(r["core_surprise_pp"], "-0.1")
        self.assertEqual(r["headline_relative_to_consensus"], "ABOVE_CONSENSUS")
        self.assertEqual(r["core_relative_to_consensus"], "BELOW_CONSENSUS")
        self.assertFalse(r["surprises_same_nonzero_direction"])
        self.assertEqual(r["independent_economic_event_sample_count"], 1)
        self.assertEqual(set(r["usd_normalized_fx7_observed_reactions"]),
                         {"M15", "H1", "H4"})
        for label in ("M15", "H1", "H4"):
            row = r["usd_normalized_fx7_observed_reactions"][label]
            self.assertEqual(row["usd_stronger_in_observed_close_count"], 4)
            self.assertEqual(row["usd_weaker_in_observed_close_count"], 2)
            self.assertEqual(row["unchanged_in_observed_close_count"], 1)
            self.assertTrue(row["correlated_currency_pairs_not_independent_events"])
            self.assertFalse(row["causality_not_established"] is False)

    def test_both_macro_surprises_above_still_no_signal(self):
        r = self.run_join(ppi=mock_comparison(headline="0.6", core="0.5"))
        self.safe(r)
        self.assertTrue(r["surprises_same_nonzero_direction"])
        self.assertEqual(r["headline_relative_to_consensus"], "ABOVE_CONSENSUS")
        self.assertEqual(r["core_relative_to_consensus"], "ABOVE_CONSENSUS")
        self.assertEqual(r["state"],
                         "LAB_PPI_SURPRISE_FX7_OBSERVED_JOINT_RESEARCH_NO_GO")

    def test_both_macro_surprises_below_still_no_signal(self):
        r = self.run_join(ppi=mock_comparison(headline="0.2", core="0.1"))
        self.safe(r)
        self.assertTrue(r["surprises_same_nonzero_direction"])
        self.assertEqual(r["headline_relative_to_consensus"], "BELOW_CONSENSUS")

    def test_no_lookahead_before_release_and_before_h4_close(self):
        for when, reason in (
            (EVENT_UTC - timedelta(seconds=1), "PPI_EVENT_NOT_YET_RELEASED"),
            (EVENT_UTC, "PPI_FX_H4_WINDOW_NOT_YET_CLOSED"),
            (LAST_REQUIRED_CLOSE_UTC - timedelta(microseconds=1),
             "PPI_FX_H4_WINDOW_NOT_YET_CLOSED"),
        ):
            with self.subTest(now=when):
                r = self.run_join(clock=when)
                self.safe(r)
                self.assertEqual(r["reason"], reason)
                self.assertIsNone(r["usd_normalized_fx7_observed_reactions"])

    def test_early_capture_claim_and_future_capture_claim_rejected(self):
        for when in (
            LAST_REQUIRED_CLOSE_UTC - timedelta(microseconds=1),
            NOW + timedelta(microseconds=1),
        ):
            with self.subTest(claim=when):
                fx = deepcopy(self.fx)
                fx["archive_captured_at_utc_claim"] = when.isoformat()
                r = self.run_join(fx=fx)
                self.safe(r)
                self.assertEqual(r["reason"], "FX7_ARCHIVE_CAPTURE_CLAIM_AFTER_H4_REQUIRED")

    def test_wrong_actual_schema_or_state_and_missing_source(self):
        for key, bad in (
            ("schema", "FORGED"),
            ("state", "LAB_WAIT_BLS_PPI_OCT2026_RELEASE"),
            ("official_source_url", "https://example.com/ppi"),
            ("source_sha256", "abc"),
        ):
            with self.subTest(key=key):
                ppi = deepcopy(self.ppi)
                ppi[key] = bad
                r = self.run_join(ppi=ppi)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_PPI_MACRO_FX7_RECONCILIATION_BLOCKED")

    def test_ppi_cannot_be_promoted_by_caller_authentication_flags(self):
        for key in ("official_actual_independently_attested",
                    "trade_authorized", "publishable"):
            ppi = deepcopy(self.ppi)
            ppi[key] = True
            r = self.run_join(ppi=ppi)
            self.safe(r)
            self.assertEqual(r["reason"],
                             "PPI_CLAIM_UNEXPECTEDLY_PROMOTED_TO_AUTHENTICATED_OR_TRADE")

    def test_consensus_cannot_be_replaced_or_mixed(self):
        for key in ("pre_event_source_hashes", "pre_event_consensus_mom_pct_claim"):
            fx = deepcopy(self.fx)
            fx[key] = {}
            r = self.run_join(fx=fx)
            self.safe(r)
            self.assertEqual(r["reason"], "FROZEN_CONSENSUS_MISMATCH")

    def test_altered_or_nonnumeric_surprise_block(self):
        for field, bad in (
            ("headline_vs_td_pre_event_diff_pp", "0.2"),
            ("core_vs_td_pre_event_diff_pp", "NaN"),
            ("core_ex_food_energy_sa_mom_pct_body_claim", "0.3333"),
        ):
            ppi = deepcopy(self.ppi)
            ppi[field] = bad
            r = self.run_join(ppi=ppi)
            self.safe(r)
            self.assertEqual(r["state"],
                             "LAB_PPI_MACRO_FX7_RECONCILIATION_BLOCKED")

    def test_malformed_fx_reactions_fail_entire_cohort_not_six_pairs(self):
        for mutation in ("missing_pair", "extra_pair", "missing_window", "bad_number",
                         "infinite", "out_of_range", "wrong_type"):
            with self.subTest(mutation=mutation):
                fx = deepcopy(self.fx)
                data = fx["price_reactions_usd_normalized_bps"]
                if mutation == "missing_pair":
                    data.pop("NZDUSD")
                elif mutation == "extra_pair":
                    data["XAUUSD"] = {name: "0.00" for name, _ in WINDOWS}
                elif mutation == "missing_window":
                    data["EURUSD"].pop("H4")
                elif mutation == "bad_number":
                    data["GBPUSD"]["M15"] = "NA"
                elif mutation == "infinite":
                    data["USDJPY"]["H1"] = "Infinity"
                elif mutation == "out_of_range":
                    data["USDCAD"]["H4"] = "9500.00"
                else:
                    data["USDCHF"]["M15"] = 3.14
                r = self.run_join(fx=fx)
                self.safe(r)
                self.assertEqual(r["state"],
                                 "LAB_PPI_MACRO_FX7_RECONCILIATION_BLOCKED")
                self.assertIsNone(r["usd_normalized_fx7_observed_reactions"])
                self.assertEqual(r["independent_economic_event_sample_count"], 0)

    def test_false_broker_attestation_and_fake_independent_events_rejected(self):
        for field, value in (
            ("source_broker_independently_authenticated", True),
            ("independent_economic_event_sample_count", 7),
            ("trade_authorized", True),
            ("local_seven_file_hashes_match", False),
        ):
            fx = deepcopy(self.fx)
            fx[field] = value
            r = self.run_join(fx=fx)
            self.safe(r)
            self.assertEqual(r["reason"], "FX7_RECEIPT_OR_NO_TRADE_CONTRACT_UNEXPECTED")

    def test_fx_series_timestamps_and_window_inventory_must_be_frozen(self):
        for field, value in (
            ("cohort_symbols", list(USD_FX)[:-1]),
            ("window_minutes", [15, 60]),
            ("event_release_utc", EVENT_UTC.isoformat().replace("+00:00", "Z")),
        ):
            fx = deepcopy(self.fx)
            fx[field] = value
            r = self.run_join(fx=fx)
            self.safe(r)
            self.assertEqual(r["reason"], "FX7_RECEIPT_OR_NO_TRADE_CONTRACT_UNEXPECTED")

    def test_naive_clock_or_missing_evidence_never_accept(self):
        for clock in (NOW.replace(tzinfo=None), "2026-11-13T19:00:00Z"):
            r = self.run_join(clock=clock)
            self.safe(r)
            self.assertEqual(r["reason"], "INVALID_AS_OF_CLOCK")
        for value, expected_reason in (
            ({}, "PPI_ACTUAL_VS_CONSENSUS_NOT_ACCEPTED"),
            (None, "REQUIRED_DOCUMENTARY_SOURCE_REPORTS_MISSING"),
        ):
            r = self.run_join(ppi=value)
            self.safe(r)
            self.assertEqual(r["reason"], expected_reason)


if __name__ == "__main__":
    unittest.main()
