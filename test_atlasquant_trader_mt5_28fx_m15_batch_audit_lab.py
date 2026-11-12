"""Synthetic all-28-FX batch contracts; do not load AM12 or Pepperstone data."""
from datetime import timedelta
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_28fx_m15_batch_audit_lab import (
    inspect_28fx_m15_archive_batch_lab as audit,
)
from test_atlasquant_trader_mt5_m15_ny17_archive_join_lab import (
    EVALUATED, archive, ny,
)


class BatchFx28M15ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots = {}
        for pair in OFFICIAL_PAIRS:
            manifest, zipped, captured = archive(pair=pair)
            cls.snapshots[pair] = {
                "manifest_record": manifest,
                "compressed_csv_gz": zipped,
                "archive_captured_at_utc": captured,
            }

    def run_audit(self, data=None, horizon="D1", start=None, end=None,
                  at=EVALUATED):
        return audit(
            snapshots_by_pair=self.snapshots if data is None else data,
            horizon=horizon,
            start_at_utc=ny(8) if start is None else start,
            end_at_utc=ny(9) if end is None else end,
            evaluated_at_utc=at,
        )

    def no_trade(self, r):
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["directional_bias"])
        self.assertIsNone(r["calibrated_direction_probability"])
        for key in (
            "publishable", "can_feed_live_radar", "trade_authorized",
            "live_alert_allowed", "worker_enabled", "scheduler_enabled",
            "source_archive_hashes_independently_attested",
            "broker_identity_independently_verified",
            "broker_calendar_independently_verified",
            "broker_price_origins_independently_verified",
            "point_in_time_market_evidence_verified",
            "precommitted_biases_independently_verified",
            "historical_directional_accuracy_validated",
            "cross_pair_independence_verified",
        ):
            self.assertFalse(r[key], key)
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_all_28_have_consistent_synthetic_daily_window(self):
        r = self.run_audit()
        self.assertEqual(r["state"], "LAB_MT5_28FX_WINDOW_LOCAL_CLAIMS_ONLY_NO_GO")
        self.assertEqual(r["coverage_claim_complete_pairs"], 28)
        self.assertEqual(r["coverage_claim_blocked_pairs"], 0)
        self.assertEqual(r["expected_pair_count"], 28)
        self.assertEqual(r["received_pair_count"], 28)
        self.assertEqual(set(r["pair_results"]), set(OFFICIAL_PAIRS))
        self.assertTrue(r["all_28_local_archive_window_checks_passed"])
        for pair, row in r["pair_results"].items():
            self.assertEqual(row["window_m15_rows_found"], 96, pair)
            self.assertEqual(row["window_expected_m15_rows"], 96, pair)
            self.assertTrue(row["manifest_local_hash_consistent"], pair)
        self.no_trade(r)

    def test_all_28_have_consistent_synthetic_weekly_window(self):
        r = self.run_audit(horizon="W1", end=ny(13))
        self.assertEqual(r["coverage_claim_complete_pairs"], 28)
        self.assertEqual(r["coverage_claim_blocked_pairs"], 0)
        self.assertTrue(r["all_28_local_archive_window_checks_passed"])
        self.assertTrue(all(row["window_m15_rows_found"] == 480
                            for row in r["pair_results"].values()))
        self.no_trade(r)

    def test_one_corrupt_pair_must_fail_entire_batch_not_inflate_27_28(self):
        pair = OFFICIAL_PAIRS[9]
        snapshots = dict(self.snapshots)
        item = dict(snapshots[pair])
        item["manifest_record"] = {
            **item["manifest_record"],
            "sha256_uncompressed_csv": "f" * 64,
        }
        snapshots[pair] = item
        r = self.run_audit(data=snapshots)
        self.assertEqual(r["state"], "LAB_MT5_28FX_WINDOW_INCOMPLETE_NO_GO")
        self.assertEqual(r["coverage_claim_complete_pairs"], 27)
        self.assertEqual(r["coverage_claim_blocked_pairs"], 1)
        self.assertFalse(r["all_28_local_archive_window_checks_passed"])
        self.assertEqual(r["pair_results"][pair]["reason"],
                         "ARCHIVE_MANIFEST_LOCAL_HASH_MISMATCH")
        self.no_trade(r)

    def test_missing_pair_is_hard_block_before_a_passing_total(self):
        pair = OFFICIAL_PAIRS[0]
        data = {p: s for p, s in self.snapshots.items() if p != pair}
        r = self.run_audit(data=data)
        self.assertEqual(r["state"], "LAB_MT5_28FX_M15_BATCH_BLOCKED")
        self.assertEqual(r["reason"], "INCOMPLETE_OR_EXTRA_28FX_PAIR_INVENTORY")
        self.assertEqual(r["missing_pairs"], [pair])
        self.assertEqual(r["coverage_claim_complete_pairs"], 0)
        self.assertEqual(r["pair_results"], {})
        self.no_trade(r)

    def test_unknown_cross_or_extra_pair_hard_blocks(self):
        data = {**self.snapshots, "XAU/USD": self.snapshots[OFFICIAL_PAIRS[0]]}
        r = self.run_audit(data=data)
        self.assertEqual(r["unexpected_pairs"], ["XAU/USD"])
        self.assertEqual(r["coverage_claim_complete_pairs"], 0)
        self.assertEqual(r["pair_results"], {})
        self.no_trade(r)

    def test_one_malformed_payload_keys_blocks_without_silent_skip(self):
        pair = OFFICIAL_PAIRS[-1]
        data = dict(self.snapshots)
        data[pair] = {
            "manifest_record": self.snapshots[pair]["manifest_record"],
            "archive_captured_at_utc": self.snapshots[pair][
                "archive_captured_at_utc"],
        }
        r = self.run_audit(data=data)
        self.assertEqual(r["coverage_claim_complete_pairs"], 27)
        self.assertEqual(r["coverage_claim_blocked_pairs"], 1)
        self.assertEqual(r["pair_results"][pair]["reason"],
                         "INVALID_ARCHIVE_PAYLOAD_KEYS_OR_TYPE")
        self.no_trade(r)

    def test_future_snapshot_evaluation_blocks_all_28(self):
        r = self.run_audit(at=ny(9) + timedelta(hours=1))
        self.assertEqual(r["state"], "LAB_MT5_28FX_WINDOW_INCOMPLETE_NO_GO")
        self.assertEqual(r["coverage_claim_complete_pairs"], 0)
        self.assertEqual(r["coverage_claim_blocked_pairs"], 28)
        self.no_trade(r)

    def test_one_window_gap_blocks_one_pair_and_does_not_drop_it(self):
        pair = OFFICIAL_PAIRS[3]
        manifest, zipped, captured = archive(pair=pair, missing_at=48)
        data = dict(self.snapshots)
        data[pair] = {
            "manifest_record": manifest,
            "compressed_csv_gz": zipped,
            "archive_captured_at_utc": captured,
        }
        r = self.run_audit(data=data)
        self.assertEqual(r["coverage_claim_complete_pairs"], 27)
        self.assertIn("M15_NY17_COVERAGE_", r["pair_results"][pair]["reason"])
        self.assertFalse(r["all_28_local_archive_window_checks_passed"])
        self.no_trade(r)

    def test_no_m15_or_monthly_horizon_reuse_in_bias_batch(self):
        for horizon in ("M15", "MN1", "M1", "H1", "H4"):
            with self.subTest(horizon=horizon):
                r = self.run_audit(horizon=horizon)
                self.assertEqual(r["state"], "LAB_MT5_28FX_M15_BATCH_BLOCKED")
                self.assertEqual(r["coverage_claim_complete_pairs"], 0)
                self.no_trade(r)


if __name__ == "__main__":
    unittest.main()
