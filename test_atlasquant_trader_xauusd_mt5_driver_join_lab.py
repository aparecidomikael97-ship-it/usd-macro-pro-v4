"""Cross-module XAUUSD price/macro join using synthetic MT5 archive only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from atlasquant_mt5_xauusd_closedbar_capture_lab import (
    collect_xauusd_closedbar_snapshot_lab as collect,
)
from atlasquant_mt5_xauusd_archive_audit_lab import audit_xauusd_closedbar_archive_lab
from atlasquant_trader_xauusd_macro_readiness_lab import GoldDriverClaim
from atlasquant_trader_xauusd_mt5_driver_join_lab import (
    join_xauusd_price_archive_to_macro_claims_lab as join,
)
from test_atlasquant_mt5_xauusd_closedbar_capture_lab import (
    AT, FakeMT5, WIN_TERMINAL,
)


def four_claimed_macro_receipts():
    claims = []
    for driver, source_id, unit, value in (
        ("US_REAL_YIELD_10Y", "FRED_DFII10", "PERCENT_ANNUAL", "1.5"),
        ("US_BROAD_DOLLAR", "FRED_DTWEXBGS", "INDEX_JAN2006_100", "120"),
    ):
        for day in (8, 9):
            claims.append(GoldDriverClaim(
                driver=driver, source_id=source_id, unit=unit,
                sampling="D1", observation_label=f"2026-11-{day:02d}",
                value_claim=value,
                published_at=datetime(2026, 11, day, 20, tzinfo=timezone.utc),
                captured_at=datetime(2026, 11, 10, 10, tzinfo=timezone.utc),
                original_sha256_claim=sha256(
                    f"{driver}-{day}".encode()).hexdigest(),
            ))
    return tuple(claims)


class XauUsdPriceMacroJoinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gold_join_synthetic_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        self.api = FakeMT5()
        self.archive = self.capture(self.api)

    def capture(self, api, *, normalized_gold_fixture=True):
        if normalized_gold_fixture:
            # Synthetic prices are exact at 2 decimals; the original fake
            # creates binary float artifacts with >6 decimal places.
            api.series_by_frame[api.TIMEFRAME_M15][-2]["close"] = 3900.50
            api.series_by_frame[api.TIMEFRAME_M15][-1]["close"] = 3900.51
        r = collect(api, terminal_path=WIN_TERMINAL,
                    output_root=self.root, clock=lambda: AT)
        self.assertEqual(r["verified_local_bars"], 3700)
        return Path(r["directory"])

    def check(self, *, archive=None, macro=(), horizon="D1", decision=AT, evaluated=AT):
        return join(self.archive if archive is None else archive,
                    macro_claims=macro, horizon=horizon,
                    decision_at_utc=decision, evaluated_at_utc=evaluated)

    def assert_safeguards(self, result):
        for flag in ("trade_authorized", "publishable", "can_feed_live_radar",
                     "broker_identity_authenticated",
                     "price_capture_time_independently_authenticated",
                     "macro_release_times_independently_authenticated",
                     "historical_point_in_time_verified",
                     "out_of_sample_gold_accuracy_validated"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["gold_bias"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertIsNone(result["research_candidate_direction"])
        self.assertEqual(result["file_writes"], 0)

    def test_price_from_audited_archive_joins_but_macro_missing(self):
        r = self.check()
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_CLAIMS_ONLY_NO_GO")
        self.assertFalse(r["all_three_driver_claims_present"])
        self.assertEqual(r["audited_local_bars"], 3700)
        self.assertEqual(r["price_claims_derived"], 2)
        self.assertEqual(len(r["price_claim_rows"]), 2)
        self.assertEqual(r["price_claim_rows"][-1]["m15_open_utc_local_claim"],
                         "2026-11-10T11:45:00Z")
        self.assertEqual(r["macro_claims_supplied"], 0)
        self.assert_safeguards(r)

    def test_four_claimed_macro_receipts_complete_claims_but_not_a_gold_signal(self):
        r = self.check(macro=four_claimed_macro_receipts(), horizon="W1")
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_CLAIMS_ONLY_NO_GO")
        self.assertTrue(r["all_three_driver_claims_present"])
        self.assertEqual(r["macro_claims_supplied"], 4)
        self.assertEqual(r["macro_driver_readiness_state"],
                         "LAB_XAUUSD_THREE_DRIVER_CLAIMS_PRESENT_UNATTESTED")
        self.assert_safeguards(r)

    def test_auditor_and_join_are_read_only(self):
        before = {p.name: sha256(p.read_bytes()).hexdigest() for p in self.archive.iterdir()}
        self.assertEqual(audit_xauusd_closedbar_archive_lab(self.archive)["verified_bars"], 3700)
        self.check(macro=four_claimed_macro_receipts())
        self.assertEqual(before, {p.name: sha256(p.read_bytes()).hexdigest()
                                  for p in self.archive.iterdir()})

    def test_missing_archive_blocks_all_receipts(self):
        self.archive.joinpath("XAUUSD_M15_closedbar.csv.gz").unlink()
        r = self.check(macro=four_claimed_macro_receipts())
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_JOIN_BLOCKED")
        self.assertEqual(r["reason"], "PRICE_ARCHIVE_LOCAL_INTEGRITY_NOT_PASSED")
        self.assertEqual(r["price_claims_derived"], 0)
        self.assert_safeguards(r)

    def test_stale_archive_rejected_at_decision_time(self):
        r = self.check(decision=AT + timedelta(hours=2),
                       evaluated=AT + timedelta(hours=2))
        self.assertEqual(r["reason"], "PRICE_SNAPSHOT_NOT_PREDECISION_OR_STALE")
        self.assert_safeguards(r)

    def test_data_collected_after_decision_cannot_be_backfilled(self):
        r = self.check(decision=AT - timedelta(minutes=1))
        self.assertEqual(r["reason"], "PRICE_SNAPSHOT_NOT_PREDECISION_OR_STALE")
        self.assert_safeguards(r)

    def capture_new(self, api, *, normalized_gold_fixture=True):
        # Same expected name but a fresh scratch root avoids any overwrite.
        self.root = Path(self.tmp.name) / "another" / "AtlasQuant" / "LAB" / "MT5_Snapshots"
        return self.capture(api, normalized_gold_fixture=normalized_gold_fixture)

    def test_incomplete_last_bar_join_fails(self):
        api = FakeMT5()
        api.series_by_frame[api.TIMEFRAME_M15][-1]["time"] = int(AT.timestamp())
        archive = self.capture_new(api)
        self.assertEqual(audit_xauusd_closedbar_archive_lab(archive)["verified_bars"], 3700)
        r = self.check(archive=archive)
        self.assertEqual(r["reason"], "M15_RECENT_TWO_BARS_NOT_SEQUENTIAL_CLOSED_AND_FRESH")
        self.assert_safeguards(r)

    def test_non_adjacent_last_two_candles_rejected(self):
        api = FakeMT5()
        api.series_by_frame[api.TIMEFRAME_M15][-2]["time"] += 1
        archive = self.capture_new(api)
        self.assertEqual(audit_xauusd_closedbar_archive_lab(archive)["verified_bars"], 3700)
        r = self.check(archive=archive)
        self.assertEqual(r["reason"], "M15_RECENT_TWO_BARS_NOT_SEQUENTIAL_CLOSED_AND_FRESH")

    def test_old_latest_price_rejected_even_if_archive_intact(self):
        api = FakeMT5()
        for item in api.series_by_frame[api.TIMEFRAME_M15]:
            item["time"] -= 3600
        archive = self.capture_new(api)
        self.assertEqual(audit_xauusd_closedbar_archive_lab(archive)["verified_bars"], 3700)
        r = self.check(archive=archive)
        self.assertEqual(r["reason"], "M15_RECENT_TWO_BARS_NOT_SEQUENTIAL_CLOSED_AND_FRESH")

    def test_unsupported_float_artifact_precision_is_not_rounded(self):
        archive = self.capture_new(FakeMT5(), normalized_gold_fixture=False)
        self.assertEqual(audit_xauusd_closedbar_archive_lab(archive)["verified_bars"], 3700)
        r = self.check(archive=archive)
        self.assertEqual(r["reason"], "GOLD_PRICE_PRECISION_NOT_SUPPORTED_WITHOUT_ROUNDING")
        self.assert_safeguards(r)

    def test_reject_caller_injected_gold_claim(self):
        malicious = GoldDriverClaim(
            driver="XAUUSD_BROKER_PRICE", source_id="PEPPERSTONE_MT5_XAUUSD",
            unit="USD_PER_TROY_OUNCE", sampling="M15",
            observation_label="2026-11-10T11:45:00Z", value_claim="3900",
            published_at=AT, captured_at=AT,
            original_sha256_claim="0" * 64,
        )
        r = self.check(macro=(malicious,))
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_JOIN_BLOCKED")
        self.assertEqual(r["price_claims_derived"], 0)

    def test_future_macro_claim_cannot_pass_age_join(self):
        bad = list(four_claimed_macro_receipts())
        old = bad[0]
        bad[0] = GoldDriverClaim(**{
            **old.__dict__, "captured_at": AT + timedelta(hours=1),
        })
        r = self.check(macro=tuple(bad))
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_JOIN_BLOCKED")
        self.assertTrue(r["reason"].startswith("MACRO_READINESS_BLOCKED:"))
        self.assert_safeguards(r)

    def test_unsupported_horizon_fails(self):
        r = self.check(horizon="M1")
        self.assertEqual(r["state"], "LAB_XAUUSD_PRICE_MACRO_JOIN_BLOCKED")
        self.assert_safeguards(r)


if __name__ == "__main__":
    unittest.main()
