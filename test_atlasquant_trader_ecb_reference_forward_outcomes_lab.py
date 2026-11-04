"""Contracts for deterministic ECB daily-reference ex-post outcome labels."""
import copy
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_ecb_reference_forward_outcomes_lab import (
    SCHEMA, STATE, DENIED, TARGET_CALENDAR_DAYS, DEADBAND_BP,
    build_ecb_reference_forward_outcomes_lab as build,
)

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "docs" / "continuidade" / "ecb_exr_g8_20261026_20261102_raw.csv"
MANIFEST = (ROOT / "docs" / "continuidade" /
            "TRADER_ECB_SDMX_ARCHIVE_MANIFEST_LAB_20261102.json")
AFTER_CAPTURE = datetime(2026, 11, 3, 0, tzinfo=timezone.utc)


def sample():
    return RAW.read_bytes(), json.loads(MANIFEST.read_text(encoding="utf-8"))


def result(anchor="2026-10-26", raw=None, manifest=None, at=AFTER_CAPTURE):
    data, record = sample()
    return build(data if raw is None else raw,
                 record if manifest is None else manifest,
                 anchor_date=anchor, evaluated_at=at)


def item(snapshot, pair, horizon):
    return next(x for x in snapshot["rows"]
                if x["pair"] == pair and x["horizon"] == horizon)


class EcbReferenceForwardOutcomesLabTests(unittest.TestCase):
    def test_six_day_sample_is_not_a_verified_forecast_or_oos(self):
        snap = result()
        self.assertEqual((snap["schema"], snap["state"]), (SCHEMA, STATE))
        self.assertEqual(len(snap["observation_dates"]), 6)
        self.assertEqual(snap["reference_original_eur_series"], 7)
        self.assertEqual(snap["algebraic_crosses_not_independent"], 21)
        for denied_key in (
            "reference_rate_origin_independently_verified",
            "historical_point_in_time_available_proven",
            "can_feed_live_bias", "can_feed_real_oos",
            "forecast_accuracy_proven", "probability_calibrated",
            "trade_authorized", "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(snap[denied_key], denied_key)
        self.assertEqual(snap["independent_broker_spot_quotes_verified"], 0)

    def test_84_deterministic_views_cover_28_pairs_and_three_horizons(self):
        snap = result()
        self.assertEqual(len(snap["rows"]), 84)
        self.assertEqual(
            {(x["pair"], x["horizon"]) for x in snap["rows"]},
            {(pair, h) for pair in OFFICIAL_PAIRS for h in ("D1", "W1", "MN1")},
        )
        self.assertEqual(snap["fixed_target_calendar_days"], TARGET_CALENDAR_DAYS)
        self.assertEqual(snap["fixed_neutral_band_bp"], str(DEADBAND_BP))

    def test_first_anchor_d1_and_w1_have_28_outcomes_but_monthly_zero(self):
        snap = result()
        by = snap["counts_by_horizon"]
        self.assertEqual(by["D1"]["with_reference_outcome"], 28)
        self.assertEqual(by["W1"]["with_reference_outcome"], 28)
        self.assertEqual(by["MN1"]["with_reference_outcome"], 0)
        self.assertEqual(by["MN1"]["awaiting_history"], 28)
        self.assertEqual(item(snap, "EUR/USD", "D1")["actual_reference_date"], "2026-10-27")
        self.assertEqual(item(snap, "EUR/USD", "W1")["actual_reference_date"], "2026-11-02")

    def test_unpublished_future_month_is_not_filled_or_interpolated(self):
        row = item(result(), "USD/JPY", "MN1")
        self.assertEqual(row["predeclared_target_date"], "2026-11-25")
        self.assertIsNone(row["actual_reference_date"])
        self.assertIsNone(row["realized_side"])
        self.assertIsNone(row["reference_return_bp"])
        self.assertEqual(row["state"], "AGUARDANDO_HISTORICO")

    def test_w1_does_not_shift_target_earlier_to_force_an_outcome(self):
        row = item(result("2026-10-27"), "GBP/USD", "W1")
        self.assertEqual(row["predeclared_target_date"], "2026-11-03")
        self.assertEqual(row["state"], "AGUARDANDO_HISTORICO")
        self.assertIsNone(row["actual_reference_date"])

    def test_friday_d1_uses_monday_reference_without_faking_weekend_data(self):
        row = item(result("2026-10-30"), "EUR/USD", "D1")
        self.assertEqual(row["predeclared_target_date"], "2026-10-31")
        self.assertEqual(row["actual_reference_date"], "2026-11-02")
        self.assertEqual(row["elapsed_calendar_days"], 3)

    def test_final_date_has_no_future_reference_outcomes(self):
        snap = result("2026-11-02")
        self.assertEqual(len(snap["rows"]), 84)
        for h in ("D1", "W1", "MN1"):
            self.assertEqual(snap["counts_by_horizon"][h]["awaiting_history"], 28)

    def test_usd_jpy_derived_algebra_uses_correct_quotation_direction(self):
        raw, manifest = sample()
        snap = result()
        from atlasquant_trader_ecb_sdmx_archive_lab import validate_ecb_archived_csv_lab
        old = validate_ecb_archived_csv_lab(raw, manifest, evaluated_at=AFTER_CAPTURE)
        quotes = old["reference_quotes_by_date"]
        with localcontext() as ctx:
            ctx.prec = 40
            start = (Decimal(quotes["2026-10-26"]["JPY"]) /
                     Decimal(quotes["2026-10-26"]["USD"]))
            end = (Decimal(quotes["2026-10-27"]["JPY"]) /
                   Decimal(quotes["2026-10-27"]["USD"]))
            expected = (end / start - 1) * Decimal("10000")
        actual = Decimal(item(snap, "USD/JPY", "D1")["reference_return_bp"])
        self.assertLessEqual(abs(actual - expected), Decimal("0.0051"))

    def test_eur_usd_is_direct_original_series_not_reversed(self):
        raw, manifest = sample()
        snap = result()
        from atlasquant_trader_ecb_sdmx_archive_lab import validate_ecb_archived_csv_lab
        quotes = validate_ecb_archived_csv_lab(
            raw, manifest, evaluated_at=AFTER_CAPTURE
        )["reference_quotes_by_date"]
        expected = (Decimal(quotes["2026-10-27"]["USD"]) /
                    Decimal(quotes["2026-10-26"]["USD"]) - 1) * 10000
        actual = Decimal(item(snap, "EUR/USD", "D1")["reference_return_bp"])
        self.assertLessEqual(abs(actual - expected), Decimal("0.0051"))

    def test_all_observed_labels_use_fixed_five_bp_deadband(self):
        for row in result()["rows"]:
            if row["state"] == "EXPOST_REFERENCE_ONLY":
                delta = Decimal(row["reference_return_bp"])
                # Rounding by 0.01 bp is smaller than the fixed threshold.
                if delta > 5.01:
                    self.assertEqual(row["realized_side"], "ALTA")
                elif delta < -5.01:
                    self.assertEqual(row["realized_side"], "BAIXA")
                elif abs(delta) < 4.99:
                    self.assertEqual(row["realized_side"], "NEUTRO")
                self.assertFalse(row["direction_is_forecast"])

    def test_all_rows_explicitly_refuse_transaction_spot_interpretation(self):
        for row in result()["rows"]:
            self.assertEqual(row["source_type"], "ECB_EUR_REFERENCE_NOT_EXECUTABLE_SPOT")
            self.assertNotIn("confidence_pct", row)
            self.assertNotIn("forecast_bias", row)
            self.assertNotIn("expected_return", row)

    def test_corrupted_bytes_fail_closed(self):
        raw, manifest = sample()
        snap = result(raw=raw.replace(b"1.1172", b"1.1173", 1), manifest=manifest)
        self.assertEqual(snap["state"], DENIED)
        self.assertEqual(snap["rows"], [])
        self.assertFalse(snap["can_feed_real_oos"])

    def test_invented_future_capture_fails_closed(self):
        raw, manifest = sample()
        bad = copy.deepcopy(manifest)
        bad["captured_at_utc"] = "2026-11-04T00:00:00Z"
        self.assertEqual(result(raw=raw, manifest=bad)["state"], DENIED)

    def test_anchor_not_in_actual_observations_is_rejected(self):
        self.assertEqual(result("2026-10-31")["state"], DENIED)
        self.assertEqual(result("2026-10-25")["state"], DENIED)
        self.assertEqual(result("2027-01-01")["state"], DENIED)

    def test_invalid_anchor_dates_fail_closed(self):
        for anchor in ("2026-2-1", "2026-99-99", "", "garbage", None, 100):
            with self.subTest(anchor=anchor):
                self.assertEqual(result(anchor)["state"], DENIED)

    def test_naive_evaluation_clock_rejected(self):
        with self.assertRaises(ValueError):
            result(at=datetime(2026, 11, 3))

    def test_evaluation_before_archive_capture_rejected(self):
        self.assertEqual(result(at=datetime(2026, 11, 2, 20,
                                            tzinfo=timezone.utc))["state"], DENIED)

    def test_no_false_accuracy_claims_despite_valid_arithmetic(self):
        snap = result()
        self.assertTrue(snap["raw_bytes_sha256_matched"])
        self.assertEqual(snap["archive_body_sha256"], sample()[1]["body_sha256"])
        self.assertIn("retrospectively", snap["research_note"])
        self.assertFalse(snap["can_feed_real_oos"])
        self.assertFalse(snap["probability_calibrated"])


if __name__ == "__main__":
    unittest.main()
