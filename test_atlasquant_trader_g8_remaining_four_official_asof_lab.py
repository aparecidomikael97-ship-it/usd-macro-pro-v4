"""Source gates and every G8 pair, deliberately without trading authority."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_remaining_four_official_asof_lab import (
    FIXED_CASEBOOK_SHA256, inspect_g8_remaining_four_official_asof_lab as inspect,
)
from atlasquant_trader_g8_eight_currency_doc_coverage_lab import (
    inspect_g8_eight_currency_documentary_coverage_lab as inspect_g8,
)

DOCS = Path(__file__).resolve().parent / "docs" / "continuidade"
OTHER = (DOCS / "TRADER_G8_CHF_AUD_CAD_NZD_20261106_OFFICIAL_ASOF_CASE_LAB.json").read_bytes()
EURUSD = (DOCS / "TRADER_EURUSD_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
GBPJPY = (DOCS / "TRADER_GBPJPY_20261106_FOUR_OFFICIAL_DOCUMENTS_ASOF_CASE_LAB.json").read_bytes()
NOW = datetime(2026, 11, 6, 17, tzinfo=timezone.utc)


def at(month, day, hour=0, minute=0):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


def run(when=NOW, raw=OTHER):
    return inspect(raw, as_of_utc=when)


def run_g8(when=NOW, *, other=OTHER, eurusd=EURUSD, gbpjpy=GBPJPY):
    return inspect_g8(
        eurusd_casebook_raw=eurusd, gbpjpy_casebook_raw=gbpjpy,
        remaining_four_casebook_raw=other, as_of_utc=when,
    )


class G8RemainingFourDocumentaryTests(unittest.TestCase):
    def assert_no_trading(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        for name in ("can_feed_live_radar", "trade_authorized", "publishable",
                     "worker_enabled", "scheduler_enabled"):
            self.assertIs(result[name], False, name)
        self.assertEqual((result["http_requests"], result["new_cost_brl"]), (0, 0))

    def test_eight_documents_visible_nov6_with_fixed_sha(self):
        r = run()
        self.assertEqual(r["state"],
                         "LAB_EIGHT_DOCUMENT_REFERENCES_VISIBLE_BUT_PIT_UNATTESTED")
        self.assertEqual(r["visible_document_count"], 8)
        self.assertEqual(r["accepted_casebook_sha256"], FIXED_CASEBOOK_SHA256)
        self.assertEqual(r["accepted_casebook_sha256"], sha256(OTHER).hexdigest())
        self.assertTrue(r["four_currency_two_family_documentary_coverage"])
        self.assert_no_trading(r)

    def test_switzerland_monthly_october_cpi_not_policy_forecast(self):
        d = {x["record_id"]: x for x in run()["visible_documents_as_retrospective_references"]}
        self.assertEqual(d["CHF_FSO_CPI_OCT2026"]["reference_period"], "2026-10")
        self.assertEqual(d["CHF_FSO_CPI_OCT2026"]["reported_values_percent_document_claim"],
                         {"monthly_cpi_change": "0.2", "annual_cpi_yoy": "1.5"})
        self.assertEqual(d["CHF_SNB_SEP2026_POLICY"]["reported_values_percent_document_claim"],
                         {"snb_policy_rate": "0.00"})

    def test_australia_monthly_original_not_seasonally_adjusted(self):
        d = {x["record_id"]: x for x in run()["visible_documents_as_retrospective_references"]}
        self.assertIn("ORIGINAL_NOT_SEASONALLY_ADJUSTED",
                      d["AUD_ABS_CPI_SEP2026"]["measurement_kind"])
        self.assertEqual(d["AUD_ABS_CPI_SEP2026"]["reported_values_percent_document_claim"],
                         {"monthly_cpi_original": "0.8", "annual_cpi_yoy": "4.3"})
        self.assertEqual(d["AUD_RBA_NOV2026_CASH_RATE"]["reported_values_percent_document_claim"],
                         {"cash_rate_target": "4.85"})

    def test_canada_unadjusted_all_items_and_target_not_bank_rate(self):
        d = {x["record_id"]: x for x in run()["visible_documents_as_retrospective_references"]}
        self.assertIn("NOT_SEASONALLY_ADJUSTED", d["CAD_STATCAN_CPI_SEP2026"]["measurement_kind"])
        self.assertEqual(d["CAD_STATCAN_CPI_SEP2026"]["reported_values_percent_document_claim"],
                         {"monthly_cpi_change": "0.1", "annual_cpi_yoy": "3.1"})
        self.assertIn("NOT_BANK_RATE_OR_DEPOSIT_RATE",
                      d["CAD_BOC_OCT2026_OVERNIGHT_TARGET"]["measurement_kind"])
        self.assertEqual(d["CAD_BOC_OCT2026_OVERNIGHT_TARGET"]["reported_values_percent_document_claim"],
                         {"overnight_rate_target": "2.50"})

    def test_new_zealand_quarterly_not_monthly_and_ocr(self):
        d = {x["record_id"]: x for x in run()["visible_documents_as_retrospective_references"]}
        self.assertEqual(d["NZD_STATSNZ_CPI_SEP2026_QUARTER"]["reference_period"], "2026-Q3")
        self.assertIn("NOT_MONTHLY_OBSERVATION",
                      d["NZD_STATSNZ_CPI_SEP2026_QUARTER"]["measurement_kind"])
        self.assertEqual(d["NZD_STATSNZ_CPI_SEP2026_QUARTER"]["reported_values_percent_document_claim"],
                         {"annual_quarterly_cpi_yoy": "3.7"})
        self.assertEqual(d["NZD_RBNZ_OCT2026_OCR"]["reported_values_percent_document_claim"],
                         {"official_cash_rate": "2.75"})

    def test_early_september_no_document_visible(self):
        self.assertEqual(run(when=at(9, 24))["visible_document_count"], 0)
        self.assertEqual(run(when=at(9, 25))["visible_document_count"], 1)

    def test_canada_cpi_calendar_day_after_floor(self):
        self.assertEqual(run(when=at(10, 19, 23, 59))["visible_document_count"], 1)
        self.assertEqual(run(when=at(10, 20))["visible_document_count"], 2)

    def test_new_zealand_cpi_conservative_gate(self):
        self.assertEqual(run(when=at(10, 22, 23, 59))["visible_document_count"], 2)
        self.assertEqual(run(when=at(10, 23))["visible_document_count"], 3)

    def test_abs_exact_aedt_utc_conversion_and_no_early_leak(self):
        self.assertEqual(run(when=at(10, 28, 0, 29))["visible_document_count"], 3)
        self.assertEqual(run(when=at(10, 28, 0, 30))["visible_document_count"], 4)

    def test_rbnz_exact_nzdt_utc_conversion_and_no_early_leak(self):
        self.assertEqual(run(when=at(10, 28, 0, 59))["visible_document_count"], 4)
        self.assertEqual(run(when=at(10, 28, 1))["visible_document_count"], 5)

    def test_boc_policy_conservative_after_calendar_day(self):
        self.assertEqual(run(when=at(10, 28, 23, 59))["visible_document_count"], 5)
        self.assertEqual(run(when=at(10, 29))["visible_document_count"], 6)

    def test_rba_exact_aedt_utc_gate(self):
        self.assertEqual(run(when=at(11, 3, 3, 29))["visible_document_count"], 6)
        self.assertEqual(run(when=at(11, 3, 3, 30))["visible_document_count"], 7)

    def test_fso_oct_cpi_conservative_after_nov3_calendar_day(self):
        self.assertEqual(run(when=at(11, 3, 23, 59))["visible_document_count"], 7)
        self.assertEqual(run(when=at(11, 4))["visible_document_count"], 8)

    def test_time_zone_offset_is_normalized(self):
        clock = NOW.astimezone(timezone(timedelta(hours=-4)))
        self.assertEqual(run(when=clock)["visible_document_count"], 8)

    def test_no_source_archival_or_consensus_claims(self):
        r = run()
        for name in ("official_original_http_bytes_archived",
                     "independent_historical_publication_time_witnessed",
                     "historical_macroeconomic_vintage_attested",
                     "pre_event_consensus_attested", "macro_surprise_quantified",
                     "inflation_methods_harmonized", "policy_instruments_directly_comparable",
                     "future_abs_oct2026_cpi_value_in_casebook",
                     "future_rbnz_dec2026_ocr_value_in_casebook"):
            self.assertIs(r[name], False, name)
        self.assertTrue(r["mixed_monthly_and_quarterly_inflation_periodicity"])
        self.assert_no_trading(r)

    def test_hash_refuses_fake_rate_time_and_source(self):
        for key, value in (("reported_values_percent", {"cash_rate_target": "99"}),
                           ("admissibility_gate_utc", "2026-01-01T00:00:00Z"),
                           ("source_url", "https://example.com/not-official"),
                           ("reference_period", "2026-11")):
            case = json.loads(OTHER)
            case["records"][3][key] = value
            self.assertEqual(run(raw=json.dumps(case).encode())["state"], "LAB_BLOCKED")

    def test_invalid_clock_raw_or_duplicate_key_rejected(self):
        self.assertEqual(run(when=datetime(2026, 11, 6, 17))["state"], "LAB_BLOCKED")
        for bad in (None, "text", b"", b"{bad json", b"\xff" * 600,
                    b"x" * 14001,
                    OTHER.replace(b'"kind":', b'"kind":"fake", "kind":', 1)):
            self.assertEqual(run(raw=bad)["state"], "LAB_BLOCKED")
            self.assert_no_trading(run(raw=bad))

    def test_bridge_has_16_page_references_all_28_pairs_but_no_bias(self):
        r = run_g8()
        self.assertEqual(r["state"], "LAB_G8_28_PAIR_DOCUMENTARY_COVERAGE_NO_DIRECTIONAL_BIAS")
        self.assertEqual((r["currency_count"], r["pair_count"], r["document_references_visible"]),
                         (8, 28, 16))
        self.assertTrue(r["complete_8_currency_16_source_documentary_coverage"])
        self.assertEqual(set(r["currencies_with_both_families_documented_claim_only"]),
                         {"EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD"})
        self.assertEqual(r["pair_count_with_two_sided_four_family_documents"], 28)
        self.assertEqual(set(r["pairs_with_both_sides_documented_claim_only"]),
                         set(OFFICIAL_PAIRS))
        self.assertEqual({x["pair"] for x in r["pairs"]}, set(OFFICIAL_PAIRS))
        for pair in r["pairs"]:
            self.assertEqual((pair["D1"], pair["W1"]), ("AGUARDAR", "AGUARDAR"))
            self.assertFalse(pair["trade_authorized"])
            self.assertFalse(pair["direct_statistical_or_rate_comparability_verified"])
        self.assert_no_trading(r)

    def test_documentary_coverage_is_not_verified_currency_strength(self):
        r = run_g8()
        for flag in ("official_document_original_bytes_attested",
                     "source_publication_times_independently_witnessed",
                     "vintage_and_statistical_method_comparability_verified",
                     "independent_currency_strength_ranking_verified",
                     "all_28_pairs_directionally_verified"):
            self.assertIs(r[flag], False, flag)
        self.assert_no_trading(r)

    def test_before_abs_and_boc_new_records_not_stuffed_into_past(self):
        r = run_g8(when=at(10, 28, 0, 29))
        self.assertEqual(r["document_references_visible"], 6)
        self.assertNotIn("AUD", r["currencies_with_both_families_documented_claim_only"])
        self.assertNotIn("CAD", r["currencies_with_both_families_documented_claim_only"])
        self.assertLess(r["pair_count_with_two_sided_four_family_documents"], 28)
        self.assert_no_trading(r)

    def test_before_uk_boe_nov6_no_all_28_coverage(self):
        r = run_g8(when=at(11, 5, 0, 0))
        self.assertEqual(r["document_references_visible"], 15)
        self.assertFalse(r["complete_8_currency_16_source_documentary_coverage"])
        self.assertEqual(r["pair_count_with_two_sided_four_family_documents"], 21)
        self.assert_no_trading(r)

    def test_tampered_any_one_of_three_casebooks_blocks_all(self):
        for kwargs in ({"eurusd": b"fake"}, {"gbpjpy": None},
                       {"other": b"wrong"}):
            r = run_g8(**kwargs)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trading(r)

    def test_g8_rejects_naive_clock(self):
        r = run_g8(when=datetime(2026, 11, 6, 17))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_trading(r)


if __name__ == "__main__":
    unittest.main()
