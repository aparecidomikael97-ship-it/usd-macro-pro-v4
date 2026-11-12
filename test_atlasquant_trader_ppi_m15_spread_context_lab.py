"""Synthetic spread context tests: not real MT5 prices or executable spreads."""
from __future__ import annotations

import csv
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, FIELDS, LAST_REQUIRED_CLOSE_UTC,
    USD_FX, ClaimedLocalPriceArchive,
)
from atlasquant_trader_ppi_m15_spread_context_lab import (
    PASS, inspect_ppi_m15_spread_context_lab as inspect,
)

NOW = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=15)


class PpiM15SpreadContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.rows = {}
        for sym in USD_FX:
            rows = []
            for i in range(17):
                value = Decimal("1.1") + Decimal(i) / 10000
                rows.append({
                    "time_utc_epoch": str(int(BASELINE_OPEN_UTC.timestamp()) + i * 900),
                    "open": str(value), "high": str(value+Decimal("0.001")),
                    "low": str(value-Decimal("0.001")), "close": str(value),
                    "tick_volume": "22", "spread": "11", "real_volume": "0",
                })
            self.rows[sym] = rows
        self.receipt = self.write()

    def write(self):
        hashes = {}
        for sym, rows in self.rows.items():
            file = self.root / f"{sym}_PPI_20261113_M15.csv"
            with file.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            hashes[sym] = sha256(file.read_bytes()).hexdigest()
        return ClaimedLocalPriceArchive(NOW, hashes)

    def run_audit(self, *, now=NOW, receipt=None):
        out = inspect(archive_root=self.root, receipt=receipt or self.receipt,
                      as_of_utc=now)
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["publishable"])
        self.assertFalse(out["broker_execution_spread_verified"])
        self.assertFalse(out["historical_bid_ask_quotes_independently_verified"])
        self.assertFalse(out["profit_or_net_return_calculated"])
        self.assertIsNone(out["validated_accuracy"])
        self.assertIsNone(out["calibrated_probability"])
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertEqual((out["http_requests"], out["file_writes"], out["new_cost_brl"]), (0,0,0))
        return out

    def test_seven_pairs_completely_verified_but_unexecutable(self):
        out = self.run_audit()
        self.assertEqual(out["state"], PASS)
        self.assertEqual(out["pair_count_documentary"],7)
        self.assertTrue(out["all_seven_price_hashes_revalidated"])
        self.assertFalse(out["any_pair_all_17_spread_samples_zero"])
        for sym in USD_FX:
            row = out["per_pair_m15_spread_samples_points"][sym]
            self.assertEqual(row["baseline_m15_bar_spread_sample_points"], 11)
            self.assertEqual(row["max_of_16_post_release_m15_bar_spread_samples_points"], 11)
            self.assertEqual(row["median_of_16_post_release_m15_bar_spread_samples_points"], "11")
            self.assertEqual(row["max_sample_over_baseline_sample_same_pair_only"], "1.000")

    def test_event_spread_peak_is_recorded_per_pair_not_market_return(self):
        self.rows["EURUSD"][1]["spread"] = "60"
        self.rows["EURUSD"][4]["spread"] = "45"
        self.rows["USDJPY"][1]["spread"] = "160"
        self.receipt = self.write()
        out = self.run_audit()
        eur, jpy = (out["per_pair_m15_spread_samples_points"][s] for s in ("EURUSD","USDJPY"))
        self.assertEqual(eur["first_post_release_m15_bar_spread_sample_points"],60)
        self.assertEqual(eur["max_of_16_post_release_m15_bar_spread_samples_points"],60)
        self.assertEqual(eur["max_sample_over_baseline_sample_same_pair_only"],"5.455")
        self.assertEqual(jpy["max_of_16_post_release_m15_bar_spread_samples_points"],160)
        self.assertNotIn("net_pnl",out)

    def test_all_zero_spread_values_remain_uncertain_not_zero_execution_cost(self):
        for row in self.rows["EURUSD"]:
            row["spread"] = "0"
        self.receipt = self.write()
        out = self.run_audit()
        self.assertEqual(out["state"],PASS)
        self.assertTrue(out["any_pair_all_17_spread_samples_zero"])
        self.assertEqual(out["per_pair_m15_spread_samples_points"]["EURUSD"]["zero_bar_spread_samples_in_17_candles"],17)
        self.assertIsNone(out["per_pair_m15_spread_samples_points"]["EURUSD"]["max_sample_over_baseline_sample_same_pair_only"])
        self.assertFalse(out["broker_execution_spread_verified"])

    def test_max_of_bar_samples_does_not_pretend_to_be_intrabar_peak(self):
        self.rows["EURUSD"][3]["spread"] = "99"
        self.receipt = self.write()
        out = self.run_audit()
        samples = out["per_pair_m15_spread_samples_points"]["EURUSD"]
        self.assertEqual(samples["max_of_16_post_release_m15_bar_spread_samples_points"], 99)
        self.assertFalse(out["intrabar_peak_spread_verified"])
        self.assertFalse(out["bar_spread_aggregation_method_verified"])
        self.assertFalse(out["timestamped_bid_ask_quotes_verified"])
        self.assertIn("BAR_SPREAD_FIELD", out["spread_observation_kind"])
        self.assertNotIn("intrabar_peak_spread_points", samples)
        self.assertNotIn("executable_spread_points", samples)

    def test_one_zero_sample_requires_review_even_if_not_all_zero(self):
        self.rows["GBPUSD"][8]["spread"] = "0"
        self.receipt = self.write()
        out = self.run_audit()
        self.assertFalse(out["any_pair_all_17_spread_samples_zero"])
        self.assertEqual(out["per_pair_m15_spread_samples_points"]["GBPUSD"]
                         ["zero_bar_spread_samples_in_17_candles"], 1)
        self.assertTrue(out["per_pair_m15_spread_samples_points"]["GBPUSD"]
                        ["zero_bar_spread_sample_requires_review"])

    def test_before_h4_close_cannot_claim_spread_context(self):
        out = self.run_audit(now=LAST_REQUIRED_CLOSE_UTC-timedelta(seconds=1))
        self.assertEqual(out["reason"],"SPREAD_WINDOW_NOT_CLOSED_OR_INVALID_CLOCK")
        self.assertIsNone(out["per_pair_m15_spread_samples_points"])

    def test_tampered_archive_rejected(self):
        path=self.root / "EURUSD_PPI_20261113_M15.csv"
        path.write_bytes(path.read_bytes()+b"\n")
        out=self.run_audit()
        self.assertEqual(out["reason"],"SEVEN_PAIR_M15_OHLC_OR_HASH_GATE_REJECTED")

    def test_missing_pair_is_not_a_six_pair_research_result(self):
        (self.root / "GBPUSD_PPI_20261113_M15.csv").unlink()
        out=self.run_audit()
        self.assertEqual(out["state"],"LAB_PPI_SPREAD_CONTEXT_BLOCKED")
        self.assertEqual(out["pair_count_documentary"],0)

    def test_invalid_negative_or_non_numeric_spread_rejected(self):
        for bad in ("-1","999x",""):
            with self.subTest(bad=bad):
                self.rows["USDCHF"][2]["spread"] = bad
                self.receipt = self.write()
                out=self.run_audit()
                self.assertEqual(out["reason"],"SEVEN_PAIR_M15_OHLC_OR_HASH_GATE_REJECTED")

    def test_wrong_captured_timestamp_rejected(self):
        bad=replace(self.receipt,captured_at_utc=EVENT_UTC)
        out=self.run_audit(receipt=bad)
        self.assertEqual(out["reason"],"SEVEN_PAIR_M15_OHLC_OR_HASH_GATE_REJECTED")

    def test_archive_with_symlink_rejected(self):
        path=self.root / "USDCHF_PPI_20261113_M15.csv"
        target=self.root / "cached.csv"
        path.rename(target)
        path.symlink_to(target)
        out=self.run_audit()
        self.assertEqual(out["reason"],"SEVEN_PAIR_M15_OHLC_OR_HASH_GATE_REJECTED")


if __name__ == "__main__":
    unittest.main()
