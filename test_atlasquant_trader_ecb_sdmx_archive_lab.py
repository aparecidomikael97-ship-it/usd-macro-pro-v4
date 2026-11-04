"""Proof that the captured ECB CSV is intact but not a trading feed."""
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_ecb_sdmx_archive_lab import (
    SCHEMA, STATE, RAW_PATH, expected_url, validate_ecb_archived_csv_lab,
)

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "docs" / "continuidade" / "TRADER_ECB_SDMX_ARCHIVE_MANIFEST_LAB_20261102.json"
NOW = datetime(2026, 11, 2, 22, tzinfo=timezone.utc)


def sample():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw = (ROOT / RAW_PATH).read_bytes()
    return raw, manifest


def check(raw=None, manifest=None, at=NOW):
    original, metadata = sample()
    return validate_ecb_archived_csv_lab(
        original if raw is None else raw,
        metadata if manifest is None else manifest,
        evaluated_at=at,
    )


def altered_text(transform):
    raw, manifest = sample()
    changed = transform(raw.decode("utf-8")).encode("utf-8")
    manifest["body_bytes"] = len(changed)
    manifest["body_sha256"] = hashlib.sha256(changed).hexdigest()
    return check(changed, manifest)


class EcbSdmxArchiveLabTests(unittest.TestCase):
    def test_direct_official_http_response_preserved_for_six_days_and_seven_currencies(self):
        result = check()
        self.assertEqual(result["state"], STATE)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["original_rows"], 42)
        self.assertEqual(result["original_eur_series"], 7)
        self.assertEqual(result["algebraic_crosses_not_independent"], 21)
        self.assertEqual(len(result["observation_dates"]), 6)
        for quotes in result["reference_quotes_by_date"].values():
            self.assertEqual(set(quotes), set(CURRENCIES) - {"EUR"})

    def test_archived_csv_hash_matches_versioned_manifest(self):
        raw, manifest = sample()
        self.assertEqual(manifest["source_url"], expected_url("2026-10-26", "2026-11-02"))
        self.assertEqual(manifest["body_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest["body_bytes"], len(raw))
        self.assertTrue(check()["raw_bytes_sha256_matched"])

    def test_two_previously_documented_dates_match_direct_ecb_csv_numerically(self):
        documented = json.loads((ROOT / "docs" / "continuidade" /
            "TRADER_ECB_TWO_DATES_DOCUMENTARY_CASE_LAB_20261102.json").read_text(encoding="utf-8"))
        actual = check()["reference_quotes_by_date"]
        for original in documented["documents"]:
            day = original["date"]
            for currency, value in original["eur_quotes"].items():
                self.assertEqual(Decimal(actual[day][currency]), Decimal(value),
                                 f"{day} {currency}")

    def test_trailing_zeros_from_web_page_are_not_fabricated_in_api_raw_values(self):
        quotes = check()["reference_quotes_by_date"]
        self.assertEqual(quotes["2026-10-30"]["GBP"], "0.8338")
        self.assertEqual(quotes["2026-11-02"]["JPY"], "177.1")

    def test_bit_tampering_is_detected_without_trusting_the_analyst(self):
        raw, manifest = sample()
        corrupted = raw.replace(b"1.1172", b"1.1173", 1)
        self.assertNotEqual(corrupted, raw)
        r = check(corrupted, manifest)
        self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")
        self.assertIn("SHA-256", r["reason"])

    def test_bad_series_key_even_with_recomputed_hash_is_denied(self):
        r = altered_text(lambda x: x.replace(
            "EXR.D.USD.EUR.SP00.A", "EXR.D.USD.USD.SP00.A", 1))
        self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_non_eur_denominator_even_with_recomputed_hash_is_denied(self):
        r = altered_text(lambda x: x.replace(",USD,EUR,SP00,A,", ",USD,USD,SP00,A,", 1))
        self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_missing_observation_is_not_silently_interpolated(self):
        def drop(text):
            return "".join(line for line in text.splitlines(keepends=True)
                if not ("EXR.D.JPY.EUR.SP00.A" in line and "2026-10-28" in line))
        self.assertEqual(altered_text(drop)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_duplicate_currency_day_is_not_accepted(self):
        def duplicate(text):
            line = next(row for row in text.splitlines(keepends=True)
                        if "EXR.D.USD.EUR.SP00.A" in row and "2026-11-02" in row)
            return text + line
        self.assertEqual(altered_text(duplicate)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_nonofficial_observation_status_is_denied(self):
        r = altered_text(lambda x: x.replace(",A,F,,,P1D", ",B,F,,,P1D", 1))
        self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_weekend_data_label_outside_official_observations_is_denied(self):
        r = altered_text(lambda x: x.replace("2026-10-30", "2026-10-31", 1))
        self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_missing_header_or_repeated_header_is_denied(self):
        for old, new in (("OBS_STATUS", "WRONG_STATUS"),
                         ("OBS_CONF", "OBS_STATUS")):
            r = altered_text(lambda x: x.replace(old, new, 1))
            self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_formula_nan_and_out_of_range_reference_are_denied(self):
        for bogus in ("=1+1", "NaN", "0", "100001"):
            r = altered_text(lambda x: x.replace(",1.1172,A,F", f",{bogus},A,F", 1))
            self.assertEqual(r["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED", bogus)

    def test_untrusted_provider_domain_is_never_followed(self):
        _, manifest = sample()
        manifest["source_url"] = "https://example.com/free/forex"
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_manifest_extra_permission_claim_is_refused(self):
        _, manifest = sample()
        manifest["trade_authorized"] = True
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_manifest_missing_day_or_reversed_calendar_is_denied(self):
        _, manifest = sample()
        manifest["expected_dates"].remove("2026-10-28")
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")
        _, manifest = sample()
        manifest["expected_dates"].reverse()
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_capture_cannot_be_backdated_before_conservative_evening_cutoff(self):
        _, manifest = sample()
        manifest["captured_at_utc"] = "2026-11-02T17:59:00Z"
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_observation_cannot_be_used_before_recorded_download(self):
        before = datetime(2026, 11, 2, 21, tzinfo=timezone.utc)
        self.assertEqual(check(at=before)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_unzoned_evaluation_is_refused(self):
        with self.assertRaises(ValueError):
            check(at=datetime(2026, 11, 2, 22))

    def test_later_http_modification_than_response_is_denied(self):
        _, manifest = sample()
        manifest["http_last_modified_utc"] = "2026-11-03T10:00:00Z"
        self.assertEqual(check(manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_absent_or_oversize_body_is_denied(self):
        _, manifest = sample()
        self.assertEqual(check(raw=b"", manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")
        self.assertEqual(check(raw=b"x"*200_001, manifest=manifest)["state"], "LAB_ECB_SDMX_ARCHIVE_REFUSED")

    def test_neither_success_nor_denial_activates_trading_or_oos(self):
        for r in (check(), check(raw=b"x")):
            self.assertIsNone(r["real_currency_strength"])
            self.assertEqual(r["independent_spot_quotes_verified"], 0)
            self.assertFalse(r["source_origin_cryptographically_verified"])
            self.assertFalse(r["publication_time_independently_verified"])
            self.assertFalse(r["capture_time_independently_attested"])
            self.assertFalse(r["historical_vintage_attested"])
            for flag in ("can_feed_live_radar", "can_feed_real_oos", "trade_authorized",
                         "worker_enabled", "scheduler_enabled",
                         "real_predictive_accuracy_proven"):
                self.assertFalse(r[flag], flag)


if __name__ == "__main__":
    unittest.main()
