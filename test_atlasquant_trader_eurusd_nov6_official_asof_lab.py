"""Official-page research dates are not independent historical PIT proof."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_trader_eurusd_nov6_official_asof_lab import (
    FIXED_CASEBOOK_SHA256, SCHEMA,
    inspect_eurusd_nov6_official_asof_lab as inspect,
)

CASEBOOK = Path(__file__).resolve().parent.joinpath(
    "docs/continuidade/TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json"
).read_bytes()
NOW = datetime(2026, 11, 6, 17, 0, tzinfo=timezone.utc)


def at(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def run(raw=CASEBOOK, *, when=NOW):
    return inspect(raw, as_of_utc=when)


class EurUsdOfficialAsOfDocumentaryTests(unittest.TestCase):
    def assert_no_real_fx_bias(self, r):
        for key in (
            "inflation_observation_periods_match",
            "inflation_statistical_methods_comparable",
            "policy_rate_instruments_directly_comparable",
            "future_oct2026_us_cpi_number_in_casebook",
            "source_original_bytes_independently_archived",
            "independent_historical_page_timestamp_witnessed",
            "pre_event_consensus_available_and_attested",
            "historical_macroeconomic_vintage_attested",
            "macro_surprise_quantified", "relative_usd_eur_strength_verified",
            "d1_w1_directional_accuracy_verified", "can_feed_live_radar",
            "trade_authorized", "publishable", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertIs(r[key], False, key)
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_four_doc_sources_visible_nov6_are_still_unattested(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"],
                         "LAB_FOUR_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED")
        self.assertEqual(r["visible_document_count"], 4)
        self.assertTrue(r["two_sided_inflation_and_policy_documentary_coverage"])
        self.assertEqual(r["accepted_casebook_sha256"], sha256(CASEBOOK).hexdigest())
        self.assertEqual(r["accepted_casebook_sha256"], FIXED_CASEBOOK_SHA256)
        self.assertEqual(r["not_yet_admissible_record_ids"], [])
        self.assert_no_real_fx_bias(r)

    def test_us_september_cpi_and_eu_october_flash_are_different_periods(self):
        r = run()
        p = {x["record_id"]: x for x in r["visible_documents_as_retrospective_references"]}
        self.assertEqual(p["USD_BLS_CPI_SEP2026"]["reference_period"], "2026-09")
        self.assertEqual(p["EUR_EUROSTAT_OCT2026_HICP_FLASH"]["reference_period"],
                         "2026-10")
        self.assertEqual(p["USD_BLS_CPI_SEP2026"]
                         ["reported_values_percent_document_claim"]["annual_cpi_yoy"], "3.7")
        self.assertEqual(p["EUR_EUROSTAT_OCT2026_HICP_FLASH"]
                         ["reported_values_percent_document_claim"]
                         ["annual_flash_hicp_yoy"], "4.0")
        self.assertFalse(r["inflation_statistical_methods_comparable"])

    def test_deposit_facility_is_not_federal_funds_target_range(self):
        r = run()
        p = {x["record_id"]: x for x in r["visible_documents_as_retrospective_references"]}
        self.assertEqual(p["EUR_ECB_OCT2026_POLICY_DECISION"]
                         ["reported_values_percent_document_claim"]["deposit_rate"], "2.50")
        self.assertEqual(p["USD_FED_OCT2026_FOMC"]
                         ["reported_values_percent_document_claim"],
                         {"target_lower": "3.75", "target_upper": "4.00"})
        self.assertFalse(r["policy_rate_instruments_directly_comparable"])

    def test_before_bls_oct14_embargo_does_not_leak_any_known_values(self):
        r = run(when=at(2026, 10, 14, 12, 29))
        self.assertEqual(r["visible_document_count"], 0)
        self.assertEqual(r["visible_documents_as_retrospective_references"], [])
        self.assertEqual(len(r["not_yet_admissible_record_ids"]), 4)
        self.assert_no_real_fx_bias(r)

    def test_exact_bls_embargo_allows_only_bls_document_reference(self):
        r = run(when=at(2026, 10, 14, 12, 30))
        self.assertEqual(r["visible_document_count"], 1)
        self.assertEqual(r["visible_documents_as_retrospective_references"][0]
                         ["record_id"], "USD_BLS_CPI_SEP2026")

    def test_before_oct28_fed_release_no_fed_result_visible(self):
        r = run(when=at(2026, 10, 28, 17, 59))
        self.assertEqual(r["visible_document_count"], 1)
        self.assertIn("USD_FED_OCT2026_FOMC", r["not_yet_admissible_record_ids"])

    def test_at_oct28_fed_release_only_two_us_documents(self):
        r = run(when=at(2026, 10, 28, 18))
        self.assertEqual(r["visible_document_count"], 2)
        self.assertFalse(r["two_sided_inflation_and_policy_documentary_coverage"])

    def test_ecb_date_only_not_admitted_until_conservative_oct30_floor(self):
        r = run(when=at(2026, 10, 29, 23, 59))
        self.assertEqual(r["visible_document_count"], 2)
        self.assertIn("EUR_ECB_OCT2026_POLICY_DECISION",
                      r["not_yet_admissible_record_ids"])
        r = run(when=at(2026, 10, 30, 0))
        self.assertEqual(r["visible_document_count"], 3)

    def test_eurostat_date_only_not_admitted_until_nov5_floor(self):
        r = run(when=at(2026, 11, 4, 23, 59))
        self.assertEqual(r["visible_document_count"], 3)
        self.assertIn("EUR_EUROSTAT_OCT2026_HICP_FLASH",
                      r["not_yet_admissible_record_ids"])
        r = run(when=at(2026, 11, 5, 0))
        self.assertEqual(r["visible_document_count"], 4)

    def test_nov6_cannot_preview_october_us_cpi_from_future_nov10_release(self):
        r = run()
        self.assertFalse(r["future_oct2026_us_cpi_number_in_casebook"])
        self.assertEqual(r["us_oct2026_cpi_schedule_utc"],
                         "2026-11-10T13:30:00Z")
        self.assertNotIn("USD_BLS_CPI_OCT2026_FUTURE",
                         [p["record_id"] for p in r["visible_documents_as_retrospective_references"]])

    def test_even_after_future_release_old_casebook_does_not_invent_new_value(self):
        r = run(when=at(2026, 11, 11))
        self.assertFalse(r["future_oct2026_us_cpi_number_in_casebook"])
        self.assertEqual(r["visible_document_count"], 4)
        self.assert_no_real_fx_bias(r)

    def test_mutating_any_official_value_or_date_breaks_fixed_casebook(self):
        for change in (
            ("reported_values_percent", {"annual_cpi_yoy": "4.2"}),
            ("admissibility_gate_utc", "2026-10-01T00:00:00Z"),
            ("source_url", "https://example.org/fake")
        ):
            changed = json.loads(CASEBOOK)
            changed["records"][0][change[0]] = change[1]
            r = run(json.dumps(changed).encode())
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_real_fx_bias(r)

    def test_duplicate_json_keys_are_not_accepted(self):
        raw = CASEBOOK.replace(b'"kind":', b'"kind":"FAKE","kind":', 1)
        self.assertEqual(run(raw)["state"], "LAB_BLOCKED")

    def test_naive_or_non_datetime_clock_is_refused(self):
        for when in (datetime(2026, 11, 6, 17),
                     "2026-11-06T17:00:00Z", None, {}):
            r = run(when=when)
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_nonbytes_broken_unicode_and_oversized_casebook_refused(self):
        for raw in (None, {}, b"", b"invalid", b"\xff" * 300, b"a" * 6001):
            self.assertEqual(run(raw)["state"], "LAB_BLOCKED")


if __name__ == "__main__":
    unittest.main()
