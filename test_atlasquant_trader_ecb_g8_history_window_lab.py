"""Offline ECB history window contracts; fixture values are SYNTHETIC, not ECB."""
import copy
import hashlib
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from atlasquant_trader_ecb_sdmx_archive_lab import SCHEMA as ARCHIVE_SCHEMA, STATE as ARCHIVE_STATE, expected_url
from atlasquant_trader_ecb_g8_history_window_lab import (
    SCHEMA, STATE, PLAN_ONLY, DENIED, archive_path,
    plan_ecb_g8_history_window_lab as plan,
    validate_ecb_g8_history_window_lab as validate,
    build_ecb_g8_history_outcomes_lab as outcomes,
)

NOW = datetime(2026, 11, 3, 5, tzinfo=timezone.utc)
START = "2026-09-01"
END = "2026-11-02"
CURRENCIES = ("USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD")
BASE = {
    "USD": Decimal("1.10000"), "GBP": Decimal("0.83000"),
    "JPY": Decimal("175.00000"), "CHF": Decimal("0.92000"),
    "AUD": Decimal("1.65000"), "CAD": Decimal("1.55000"),
    "NZD": Decimal("1.90000"),
}


def synthetic_fixture():
    # Generated for a contract test, with fabricated quotes on ALL weekdays.
    # This is NOT original ECB material and must never be promoted to real OOS.
    first, last = date.fromisoformat(START), date.fromisoformat(END)
    days = []
    cursor = first
    while cursor <= last:
        if cursor.weekday() < 5:
            days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    rows = [
        "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,OBS_STATUS"
    ]
    for i, day in enumerate(days):
        for currency in CURRENCIES:
            rate = BASE[currency] * (Decimal("1") + Decimal(i) * Decimal("0.0003"))
            rows.append(f"EXR.D.{currency}.EUR.SP00.A,D,{currency},EUR,SP00,A,"
                        f"{day},{rate:.8f},A")
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    record = {
        "schema": ARCHIVE_SCHEMA,
        "state": ARCHIVE_STATE,
        "source_url": expected_url(START, END),
        "query_start": START,
        "query_end": END,
        "captured_at_utc": "2026-11-03T03:00:00Z",
        "http_date_utc": "2026-11-03T02:00:00Z",
        "http_last_modified_utc": "2026-11-02T19:00:00Z",
        "http_status": 200,
        "content_type": "text/csv",
        "body_bytes": len(raw),
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_path": archive_path(START, END),
        "expected_dates": days,
    }
    return raw, record


def audit(raw=None, manifest=None, at=NOW):
    data, record = synthetic_fixture()
    return validate(data if raw is None else raw,
                    record if manifest is None else manifest,
                    evaluated_at=at)


class EcbG8HistoryWindowLabTests(unittest.TestCase):
    def test_exact_manual_plan_no_download_or_authority(self):
        r = plan(START, END, planned_at=NOW)
        self.assertEqual(r["state"], PLAN_ONLY)
        self.assertFalse(r["http_performed"])
        self.assertFalse(r["data_downloaded"])
        self.assertTrue(r["manual_capture_required"])
        self.assertEqual(r["required_raw_path"],
                         "docs/continuidade/ecb_exr_g8_20260901_20261102_raw.csv")
        self.assertEqual(r["expected_official_url"], expected_url(START, END))
        self.assertEqual(r["required_original_currencies_per_day"], 7)
        self.assertFalse(r["can_feed_real_oos"])

    def test_no_arbitrary_host_or_path_accepted_by_planner(self):
        self.assertNotIn("example.com", plan(START, END, planned_at=NOW)["expected_official_url"])
        with self.assertRaises(ValueError):
            archive_path("../etc/passwd", END)

    def test_weekend_endpoint_is_rejected(self):
        self.assertEqual(plan("2026-09-05", END, planned_at=NOW)["state"], DENIED)
        self.assertEqual(plan(START, "2026-10-31", planned_at=NOW)["state"], DENIED)

    def test_short_and_oversized_intervals_denied(self):
        self.assertEqual(plan("2026-10-26", END, planned_at=NOW)["state"], DENIED)
        self.assertEqual(plan("2026-01-02", END, planned_at=NOW)["state"], DENIED)
        self.assertEqual(plan(END, START, planned_at=NOW)["state"], DENIED)

    def test_future_window_denied(self):
        self.assertEqual(plan(START, END, planned_at=datetime(2026, 10, 31,
            23, tzinfo=timezone.utc))["state"], DENIED)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            plan(START, END, planned_at=datetime(2026, 11, 3))
        with self.assertRaises(ValueError):
            audit(at=datetime(2026, 11, 3))

    def test_synthetic_weekdays_can_verify_only_internal_archive_consistency(self):
        r = audit()
        self.assertEqual((r["schema"], r["state"]), (SCHEMA, STATE))
        self.assertTrue(r["archive_hash_internally_matched"])
        self.assertEqual(r["original_eur_series"], 7)
        self.assertEqual(r["derived_crosses_not_independent"], 21)
        self.assertEqual(len(r["observation_dates"]), 45)
        self.assertEqual(len(r["reference_quotes_by_date"]), 45)
        self.assertEqual(r["raw_path"], archive_path(START, END))
        self.assertIn("Caller-declared", r["archive_timestamp_evidence"])

    def test_later_monthly_outcomes_become_mathematically_available(self):
        data, manifest = synthetic_fixture()
        lab = outcomes(data, manifest, anchor_date=START, evaluated_at=NOW)
        self.assertEqual(lab["history_archive_state"], STATE)
        self.assertEqual(len(lab["rows"]), 84)
        self.assertEqual(lab["counts_by_horizon"]["MN1"]["with_reference_outcome"], 28)
        self.assertEqual(lab["counts_by_horizon"]["D1"]["with_reference_outcome"], 28)
        self.assertEqual(lab["counts_by_horizon"]["W1"]["with_reference_outcome"], 28)
        self.assertEqual(lab["history_original_raw_path"], archive_path(START, END))
        self.assertFalse(lab["can_feed_real_oos"])
        self.assertFalse(lab["history_origin_independently_attested"])

    def test_end_of_history_still_has_no_future_settlement(self):
        data, manifest = synthetic_fixture()
        r = outcomes(data, manifest, anchor_date=END, evaluated_at=NOW)
        self.assertEqual(r["counts_by_horizon"]["MN1"]["awaiting_history"], 28)
        self.assertFalse(r["forecast_accuracy_proven"])

    def test_monthly_coverage_does_not_certify_real_predictive_skill(self):
        r = audit()
        self.assertGreater(r["monthly_outcome_anchors_possible_expost"], 0)
        self.assertGreater(len(r["monthly_outcome_anchor_dates"]), 0)
        self.assertFalse(r["accuracy_90_proven"])
        self.assertFalse(r["probability_calibrated"])
        self.assertFalse(r["historical_as_of_capture_independently_attested"])
        self.assertFalse(r["official_origin_cryptographically_verified"])
        self.assertFalse(r["official_daily_revisions_tracked"])
        self.assertEqual(r["independent_spot_quotes_verified"], 0)
        self.assertFalse(r["can_feed_live_bias"])
        self.assertFalse(r["can_feed_real_oos"])
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["trade_authorized"])

    def test_corrupted_bytes_without_rehash_fail_closed(self):
        raw, m = synthetic_fixture()
        modified = raw.replace(b"1.10000000", b"1.10000001", 1)
        self.assertNotEqual(modified, raw)
        self.assertEqual(audit(raw=modified, manifest=m)["state"], DENIED)

    def test_wrong_raw_path_even_with_valid_data_and_hash_denied(self):
        raw, m = synthetic_fixture()
        m["raw_path"] = "docs/continuidade/ecb_exr_g8_20260902_20261102_raw.csv"
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)
        m["raw_path"] = "../../data.csv"
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)

    def test_wrong_endpoint_is_rejected(self):
        raw, m = synthetic_fixture()
        m["source_url"] = "https://attacker.example/service/data/EXR"
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)

    def test_reported_capture_chronology_is_constrained(self):
        raw, m = synthetic_fixture()
        m["captured_at_utc"] = "2026-11-04T05:00:00Z"
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)

    def test_incomplete_currency_day_denied_with_matching_new_hash(self):
        raw, m = synthetic_fixture()
        lines = raw.splitlines(keepends=True)
        filtered = b"".join(x for x in lines
                            if not (b"EXR.D.JPY.EUR.SP00.A" in x and b"2026-09-01" in x))
        m["body_bytes"] = len(filtered)
        m["body_sha256"] = hashlib.sha256(filtered).hexdigest()
        self.assertEqual(audit(raw=filtered, manifest=m)["state"], DENIED)

    def test_extra_manifest_fields_denied_by_core(self):
        raw, m = synthetic_fixture()
        m["i_am_official_signature"] = True
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)

    def test_cannot_use_the_legacy_six_day_archive_as_monthly_evidence(self):
        raw, m = synthetic_fixture()
        m["query_start"] = "2026-10-26"
        m["query_end"] = "2026-11-02"
        self.assertEqual(audit(raw=raw, manifest=m)["state"], DENIED)

    def test_outcomes_fail_closed_on_forged_raw_path(self):
        raw, m = synthetic_fixture()
        m["raw_path"] = "fake.csv"
        r = outcomes(raw, m, anchor_date=START, evaluated_at=NOW)
        self.assertEqual(r["state"], DENIED)
        self.assertFalse(r["can_feed_real_oos"])


if __name__ == "__main__":
    unittest.main()
