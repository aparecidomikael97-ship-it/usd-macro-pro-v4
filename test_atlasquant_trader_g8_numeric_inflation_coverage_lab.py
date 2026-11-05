"""Synthetic original-response fixtures for 28-pair numeric inflation coverage."""
from datetime import datetime, timedelta, timezone
import json
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_g8_numeric_inflation_coverage_lab import (
    MISSING, OBSERVED, SUPPLIED_TEXT,
    build_g8_numeric_inflation_coverage_lab as build,
)
from test_atlasquant_trader_eurostat_eur_hicp_once_lab import (
    NOW as EUR_CAPTURE, fixture as eur_fixture, raw as eur_raw,
)
from test_atlasquant_trader_bls_us_cpiu_once_lab import (
    NOW as USD_CAPTURE, fixture as usd_fixture, raw as usd_raw,
)
from test_atlasquant_trader_ons_gbp_cpi_current_lab import raw as gbp_raw
from test_atlasquant_trader_jp_national_cpi_summary_text_lab import TEXT as JPY_TEXT
from test_atlasquant_trader_statcan_cad_cpi_table_text_lab import (
    TEXT as CAD_TEXT, ROW as CAD_ROW,
)
from test_atlasquant_trader_statsnz_nzd_cpi_quarter_text_lab import (
    TEXT as NZD_QUARTER_TEXT,
)
from test_atlasquant_trader_abs_aud_cpi_monthly_text_lab import (
    TEXT as AUD_MONTHLY_TEXT,
)

AS_OF = datetime(2026, 11, 5, 2, tzinfo=timezone.utc)


def run(eur=None, usd=None, **kwargs):
    args = dict(eur_jsonstat_raw=eur_raw() if eur is None else eur,
                usd_bls_raw=usd_raw() if usd is None else usd,
                eur_capture_utc=EUR_CAPTURE, usd_capture_utc=USD_CAPTURE,
                as_of_utc=AS_OF)
    args.update(kwargs)
    return build(**args)


def pair(report, symbol="EUR/USD"):
    return next(x for x in report["pairs"] if x["pair"] == symbol)


class NumericCoverageTests(unittest.TestCase):
    def assert_no_trading(self, report):
        for key in ("authentic_release_instant_verified",
                    "point_in_time_vintage_verified", "consensus_pre_event_attested",
                    "historical_backtest_accuracy_verified",
                    "cross_source_methodologically_comparable", "trade_authorized",
                    "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
                    "publishable"):
            self.assertIs(report[key], False, key)
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertIsNone(report["fx_bias"])
        self.assertEqual((report["external_http_requests"], report["new_cost_brl"]), (0, 0))

    def test_28_pairs_show_two_one_zero_currency_observation_coverage(self):
        r = run()
        self.assertEqual(r["state"], "LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY")
        self.assertEqual((r["currency_count"], r["pair_count"]), (8, 28))
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 15, "1": 12, "2": 1})
        self.assertEqual({p["pair"] for p in r["pairs"]}, set(OFFICIAL_PAIRS))
        self.assertEqual(set(r["currencies"]), set(CURRENCIES))
        self.assert_no_trading(r)

    def test_eurusd_two_sides_but_months_and_methods_incompatible(self):
        r = pair(run())
        self.assertEqual(r["numeric_observation_sides"], 2)
        self.assertEqual((r["base_latest_month"], r["quote_latest_month"]),
                         ("2026-10", "2026-09"))
        self.assertFalse(r["observation_months_aligned_if_both"])
        self.assertIn("OBSERVATION_MONTHS_DIFFER", r["comparison_blockers"])
        self.assertIn("HICP_AND_CPI_U_METHODS_NOT_IDENTICAL", r["comparison_blockers"])
        self.assertIsNone(r["inflation_difference_percentage_points"])
        self.assertIsNone(r["currency_strength_rank"])
        self.assertIsNone(r["fx_bias"])
        self.assertFalse(r["trade_authorized"])

    def test_original_rate_is_distinct_and_estimate_not_final(self):
        currencies = run()["currencies"]
        self.assertEqual(currencies["EUR"]["rate_yoy_percent_claim"], 4.0)
        self.assertTrue(currencies["EUR"]["estimated_observation"])
        self.assertEqual(currencies["USD"]["rate_yoy_percent_claim"], "5.2938")
        self.assertTrue(currencies["USD"]["has_valid_same_month_prior_year"])
        self.assertEqual(currencies["EUR"]["series_kind"], "EUROSTAT_HICP_YOY_ECOICOP_V2")
        self.assertEqual(currencies["USD"]["series_kind"], "BLS_CPI_U_NSA_INDEX_YOY_DERIVED")

    def test_missing_six_are_not_synthesized_from_eur_usd(self):
        currencies = run()["currencies"]
        for cur in ("GBP", "JPY", "CHF", "AUD", "CAD", "NZD"):
            self.assertEqual(currencies[cur]["status"], MISSING)
            self.assertIsNone(currencies[cur]["rate_yoy_percent_claim"])
            self.assertIsNone(currencies[cur]["observation_month"])
            self.assertFalse(currencies[cur]["original_source_authenticity_independently_verified"])

    def test_one_side_missing_on_eurgbp(self):
        row = pair(run(), "EUR/GBP")
        self.assertEqual(row["numeric_observation_sides"], 1)
        self.assertIn("QUOTE_INFLATION_DATA_MISSING", row["comparison_blockers"])
        self.assertIsNone(row["observation_months_aligned_if_both"])
        self.assertEqual(row["D1"], "AGUARDAR")

    def test_both_missing_on_cadjpy(self):
        row = pair(run(), "CAD/JPY")
        self.assertEqual(row["numeric_observation_sides"], 0)
        self.assertIn("BASE_INFLATION_DATA_MISSING", row["comparison_blockers"])
        self.assertIn("QUOTE_INFLATION_DATA_MISSING", row["comparison_blockers"])

    def test_no_data_yet_means_twenty_eight_pairs_wait(self):
        r = run(eur_jsonstat_raw=None, usd_bls_raw=None,
                eur_capture_utc=None, usd_capture_utc=None)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 28, "1": 0, "2": 0})
        self.assertTrue(all(x["numeric_observation_sides"] == 0 for x in r["pairs"]))
        self.assert_no_trading(r)

    def test_eur_only_covers_exactly_seven_pairs_one_side(self):
        r = run(usd_bls_raw=None, usd_capture_utc=None)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 21, "1": 7, "2": 0})
        self.assertEqual(r["currencies"]["EUR"]["status"], OBSERVED)
        self.assertEqual(r["currencies"]["USD"]["status"], MISSING)

    def test_usd_only_covers_exactly_seven_pairs_one_side(self):
        r = run(eur_jsonstat_raw=None, eur_capture_utc=None)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 21, "1": 7, "2": 0})
        self.assertEqual(r["currencies"]["USD"]["status"], OBSERVED)
        self.assertEqual(r["currencies"]["EUR"]["status"], MISSING)

    def test_aligned_months_do_not_confer_method_comparability(self):
        fixture = usd_fixture()
        for row in fixture["Results"]["series"][0]["data"]:
            if row["year"] == "2026" and row["period"] == "M09":
                row["period"] = "M10"
            elif row["year"] == "2025" and row["period"] == "M09":
                row["period"] = "M10"
        r = run(usd_bls_raw=json.dumps(fixture).encode())
        row = pair(r)
        self.assertTrue(row["observation_months_aligned_if_both"])
        self.assertFalse(row["methods_comparable"])
        self.assertIn("HICP_AND_CPI_U_METHODS_NOT_IDENTICAL", row["comparison_blockers"])
        self.assertIsNone(row["inflation_difference_percentage_points"])

    def test_no_prior_year_rate_is_missing_not_zero(self):
        fixture = usd_fixture()
        fixture["Results"]["series"][0]["data"] = [
            x for x in fixture["Results"]["series"][0]["data"]
            if x["year"] == "2026"
        ]
        r = run(usd_bls_raw=json.dumps(fixture).encode())
        self.assertEqual(r["state"], "LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY")
        self.assertIsNone(r["currencies"]["USD"]["rate_yoy_percent_claim"])
        self.assertFalse(r["currencies"]["USD"]["has_valid_same_month_prior_year"])
        self.assertIn("ANNUAL_RATE_DENOMINATOR_MISSING", pair(r)["comparison_blockers"])

    def test_valid_raw_content_hash_is_not_official_release_authentication(self):
        from hashlib import sha256
        r = run()
        self.assertEqual(r["currencies"]["EUR"]["source_raw_sha256"],
                         sha256(eur_raw()).hexdigest())
        for currency in r["currencies"].values():
            self.assertFalse(currency["release_instant_attested"])
            self.assertFalse(currency["pre_event_vintage_attested"])
            self.assertFalse(currency["commercial_redistribution_rights_verified"])

    def test_bad_content_blocks_entire_matrix(self):
        for changes in ({"eur_jsonstat_raw": b"not json"},
                        {"usd_bls_raw": b"not json"},
                        {"eur_jsonstat_raw": "pretend"},
                        {"usd_bls_raw": {"status": "REQUEST_SUCCEEDED"}}):
            self.assertEqual(run(**changes)["state"], "LAB_BLOCKED")

    def test_capture_must_have_utc_and_never_exceed_asof(self):
        for args in ({"as_of_utc": AS_OF.replace(tzinfo=None)},
                     {"eur_capture_utc": AS_OF + timedelta(minutes=1)},
                     {"usd_capture_utc": AS_OF + timedelta(minutes=1)},
                     {"usd_capture_utc": None}):
            self.assertEqual(run(**args)["state"], "LAB_BLOCKED")

    def test_missing_raw_with_claimed_timestamp_is_rejected(self):
        self.assertEqual(run(eur_jsonstat_raw=None)["state"], "LAB_BLOCKED")
        self.assertEqual(run(usd_bls_raw=None)["state"], "LAB_BLOCKED")

    def test_all_pairs_suppress_signals_at_all_horizons(self):
        r = run()
        for x in r["pairs"]:
            self.assertEqual((x["D1"], x["W1"], x["MN1"]),
                             ("AGUARDAR", "AGUARDAR", "AGUARDAR"))
            self.assertFalse(x["trade_authorized"])
            self.assertIsNone(x["fx_bias"])
            self.assertFalse(x["methods_comparable"])

    def test_gbp_source_expands_two_currency_coverage_to_three_pairs(self):
        r = run(gbp_ons_raw=gbp_raw(),
                gbp_capture_utc=datetime(2026, 11, 5, 1, 30, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY")
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 10, "1": 15, "2": 3})
        self.assertEqual(r["currencies"]["GBP"]["observation_month"], "2026-09")
        self.assertEqual(r["currencies"]["GBP"]["rate_yoy_percent_claim"], "3.5")
        self.assertEqual(r["currencies"]["GBP"]["series_kind"],
                         "ONS_D7G7_CPI_ALL_ITEMS_YOY_DIRECT")
        for symbol in ("EUR/USD", "EUR/GBP", "GBP/USD"):
            self.assertEqual(pair(r, symbol)["numeric_observation_sides"], 2)
            self.assertFalse(pair(r, symbol)["methods_comparable"])
        self.assert_no_trading(r)

    def test_gbp_usd_same_month_still_cannot_be_ranked_or_traded(self):
        r = run(gbp_ons_raw=gbp_raw(),
                gbp_capture_utc=datetime(2026, 11, 5, 1, 30, tzinfo=timezone.utc))
        row = pair(r, "GBP/USD")
        self.assertTrue(row["observation_months_aligned_if_both"])
        self.assertIn("CROSS_COUNTRY_INFLATION_METHODS_NOT_HARMONIZED",
                      row["comparison_blockers"])
        self.assertIsNone(row["currency_strength_rank"])
        self.assertIsNone(row["inflation_difference_percentage_points"])

    def test_invalid_gbp_payload_denies_entire_matrix(self):
        r = run(gbp_ons_raw=b"not an ONS response",
                gbp_capture_utc=datetime(2026, 11, 5, 1, 30, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_gbp_capture_future_or_missing_clock_blocks(self):
        for stamp in (None, AS_OF + timedelta(minutes=1),
                      datetime(2026, 11, 5, 1, 30)):
            r = run(gbp_ons_raw=gbp_raw(), gbp_capture_utc=stamp)
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_optional_jpy_text_is_not_misrepresented_as_original_api_response(self):
        r = run(jpy_national_page_text_raw=JPY_TEXT.encode(),
                jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["currencies"]["JPY"]["status"], SUPPLIED_TEXT)
        self.assertEqual(r["currencies"]["JPY"]["rate_yoy_percent_claim"], "2.1")
        self.assertEqual(r["currencies"]["JPY"]["observation_month"], "2026-09")
        self.assertEqual(r["currencies"]["JPY"]["series_kind"],
                         "JP_NATIONAL_CPI_ALL_ITEMS_2025_BASE_YOY_TRANSCRIBED_TEXT")
        self.assertFalse(r["currencies"]["JPY"][
            "original_source_authenticity_independently_verified"])
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 10, "1": 15, "2": 3})
        self.assert_no_trading(r)

    def test_eur_usd_gbp_jpy_synthetic_four_currency_coverage_not_bias(self):
        r = run(gbp_ons_raw=gbp_raw(),
                gbp_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc),
                jpy_national_page_text_raw=JPY_TEXT.encode(),
                jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 6, "1": 16, "2": 6})
        for symbol in ("EUR/USD", "EUR/GBP", "GBP/USD", "USD/JPY",
                       "EUR/JPY", "GBP/JPY"):
            row = pair(r, symbol)
            self.assertEqual(row["numeric_observation_sides"], 2)
            self.assertFalse(row["methods_comparable"])
            self.assertIsNone(row["inflation_difference_percentage_points"])
            self.assertIsNone(row["fx_bias"])
        self.assert_no_trading(r)

    def test_usdjpy_equal_month_does_not_justify_cross_country_rank(self):
        r = run(jpy_national_page_text_raw=JPY_TEXT.encode(),
                jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        row = pair(r, "USD/JPY")
        self.assertTrue(row["observation_months_aligned_if_both"])
        self.assertIn("CROSS_COUNTRY_INFLATION_METHODS_NOT_HARMONIZED",
                      row["comparison_blockers"])
        self.assertIsNone(row["currency_strength_rank"])
        self.assert_no_trading(r)

    def test_invalid_or_tokyo_only_jpy_text_blocks_entire_matrix(self):
        for content in (b"not official", JPY_TEXT.replace("指数　全国", "指数　東京都区部").encode(),
                        "transcribed text"):
            r = run(jpy_national_page_text_raw=content,
                    jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_jpy_missing_future_or_naive_clock_blocks(self):
        for clock in (None, AS_OF + timedelta(minutes=1), datetime(2026, 11, 5, 1)):
            r = run(jpy_national_page_text_raw=JPY_TEXT.encode(),
                    jpy_capture_utc=clock)
            self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_jpy_headline_not_inferred_from_fresh_food_exclusion(self):
        txt = JPY_TEXT.replace("2.1%の上昇", "1.7%の上昇", 1)
        r = run(jpy_national_page_text_raw=txt.encode(),
                jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["currencies"]["JPY"]["rate_yoy_percent_claim"], "1.7")
        self.assert_no_trading(r)

    def test_optional_cad_table_text_stays_explicitly_unattested(self):
        r = run(cad_nsa_table_text_raw=CAD_TEXT.encode(),
                cad_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["currencies"]["CAD"]["status"], SUPPLIED_TEXT)
        self.assertEqual(r["currencies"]["CAD"]["observation_month"], "2026-09")
        self.assertEqual(r["currencies"]["CAD"]["rate_yoy_percent_claim"], "3.1")
        self.assertEqual(r["currencies"]["CAD"]["series_kind"],
                         "STATCAN_CAD_CPI_ALL_ITEMS_NSA_2002_BASE_YOY_TRANSCRIBED_TEXT")
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 10, "1": 15, "2": 3})
        self.assertFalse(r["currencies"]["CAD"][
            "original_source_authenticity_independently_verified"])
        self.assert_no_trading(r)

    def test_five_currencies_are_ten_two_sided_pairs_synthetic_only(self):
        r = run(gbp_ons_raw=gbp_raw(),
                gbp_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc),
                jpy_national_page_text_raw=JPY_TEXT.encode(),
                jpy_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc),
                cad_nsa_table_text_raw=CAD_TEXT.encode(),
                cad_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 3, "1": 15, "2": 10})
        for symbol in ("EUR/USD", "EUR/GBP", "GBP/USD", "EUR/JPY",
                       "USD/JPY", "GBP/JPY", "EUR/CAD", "USD/CAD",
                       "GBP/CAD", "CAD/JPY"):
            x = pair(r, symbol)
            self.assertEqual(x["numeric_observation_sides"], 2)
            self.assertFalse(x["methods_comparable"])
            self.assertIsNone(x["currency_strength_rank"])
            self.assertIsNone(x["inflation_difference_percentage_points"])
        self.assert_no_trading(r)

    def test_usdcad_equal_month_does_not_allow_a_currency_rank(self):
        r = run(cad_nsa_table_text_raw=CAD_TEXT.encode(),
                cad_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        x = pair(r, "USD/CAD")
        self.assertTrue(x["observation_months_aligned_if_both"])
        self.assertIn("CROSS_COUNTRY_INFLATION_METHODS_NOT_HARMONIZED",
                      x["comparison_blockers"])
        self.assertIsNone(x["fx_bias"])

    def test_invalid_or_wrongly_adjusted_cad_text_blocks_matrix(self):
        for content in (b"not official", "pretend text",
                        CAD_TEXT.replace("Not seasonally adjusted", "Seasonally adjusted").encode()):
            x = run(cad_nsa_table_text_raw=content,
                    cad_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
            self.assertEqual(x["state"], "LAB_BLOCKED")

    def test_cad_missing_future_or_naive_capture_clock_blocks(self):
        for stamp in (None, AS_OF + timedelta(minutes=1), datetime(2026, 11, 5, 1)):
            x = run(cad_nsa_table_text_raw=CAD_TEXT.encode(), cad_capture_utc=stamp)
            self.assertEqual(x["state"], "LAB_BLOCKED")

    def test_cad_annual_headline_is_not_its_monthly_rate(self):
        altered = CAD_TEXT.replace(CAD_ROW,
                                   "All-items | 164.9 | 169.8 | 170.0 | 0.5 | 3.1")
        x = run(cad_nsa_table_text_raw=altered.encode(),
                cad_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(x["currencies"]["CAD"]["rate_yoy_percent_claim"], "3.1")
        self.assert_no_trading(x)

    def test_optional_nzd_quarterly_text_adds_three_pairs_without_monthly_invention(self):
        r = run(nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(),
                nzd_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 10, "1": 15, "2": 3})
        nzd = r["currencies"]["NZD"]
        self.assertEqual(nzd["status"], SUPPLIED_TEXT)
        self.assertEqual(nzd["rate_yoy_percent_claim"], "3.7")
        self.assertEqual(nzd["observation_frequency"], "QUARTERLY")
        self.assertEqual(nzd["observation_period"], "2026-Q3")
        self.assertIsNone(nzd["observation_month"])
        self.assertEqual(nzd["series_kind"],
                         "STATS_NZ_CPI_ALL_GROUPS_QUARTERLY_YOY_TRANSCRIBED_TEXT")
        self.assertFalse(nzd["original_source_authenticity_independently_verified"])
        self.assert_no_trading(r)

    def test_nzd_usd_quarterly_vs_monthly_is_not_same_september_observation(self):
        r = run(nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(),
                nzd_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        x = pair(r, "NZD/USD")
        self.assertEqual(x["numeric_observation_sides"], 2)
        self.assertEqual((x["base_latest_month"], x["quote_latest_month"]),
                         (None, "2026-09"))
        self.assertEqual((x["base_latest_period"], x["quote_latest_period"]),
                         ("2026-Q3", "2026-09"))
        self.assertEqual((x["base_frequency"], x["quote_frequency"]),
                         ("QUARTERLY", "MONTHLY"))
        self.assertFalse(x["observation_frequencies_aligned_if_both"])
        self.assertFalse(x["observation_periods_aligned_if_both"])
        self.assertFalse(x["observation_months_aligned_if_both"])
        self.assertIn("OBSERVATION_FREQUENCIES_DIFFER", x["comparison_blockers"])
        self.assertIn("QUARTERLY_CPI_MUST_NOT_MASQUERADE_AS_MONTHLY",
                      x["comparison_blockers"])
        self.assertIsNone(x["inflation_difference_percentage_points"])
        self.assertIsNone(x["currency_strength_rank"])
        self.assert_no_trading(r)

    def test_six_synthetic_currency_sources_cover_fifteen_two_sided_pairs(self):
        stamp = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
        r = run(gbp_ons_raw=gbp_raw(), gbp_capture_utc=stamp,
                jpy_national_page_text_raw=JPY_TEXT.encode(), jpy_capture_utc=stamp,
                cad_nsa_table_text_raw=CAD_TEXT.encode(), cad_capture_utc=stamp,
                nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(), nzd_capture_utc=stamp)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 1, "1": 12, "2": 15})
        for symbol in ("EUR/NZD", "GBP/NZD", "NZD/USD", "NZD/JPY", "NZD/CAD"):
            x = pair(r, symbol)
            self.assertEqual(x["numeric_observation_sides"], 2)
            self.assertIn("OBSERVATION_FREQUENCIES_DIFFER", x["comparison_blockers"])
            self.assertIn("QUARTERLY_CPI_MUST_NOT_MASQUERADE_AS_MONTHLY",
                          x["comparison_blockers"])
            self.assertIsNone(x["fx_bias"])
            self.assertIsNone(x["currency_strength_rank"])
        self.assert_no_trading(r)

    def test_missing_nzd_does_not_change_monthly_eur_usd_contract(self):
        r = run()
        self.assertEqual(r["currencies"]["NZD"]["status"], MISSING)
        self.assertIsNone(r["currencies"]["NZD"]["observation_frequency"])
        x = pair(r)
        self.assertEqual((x["base_frequency"], x["quote_frequency"]),
                         ("MONTHLY", "MONTHLY"))
        self.assertTrue(x["observation_frequencies_aligned_if_both"])
        self.assertFalse(x["observation_months_aligned_if_both"])

    def test_wrongly_monthly_nzd_or_wrong_quarter_refuses_entire_matrix(self):
        for bad in (NZD_QUARTER_TEXT.replace("Quarterly percentage change",
                                               "Monthly percentage change"),
                    NZD_QUARTER_TEXT.replace("September 2026 quarter",
                                             "June 2026 quarter", 1),
                    NZD_QUARTER_TEXT.replace("CPI all groups | 0.7 | 3.7",
                                             "CPI all groups | 0.7 | N/A")):
            r = run(nzd_quarter_page_text_raw=bad.encode(),
                    nzd_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trading(r)

    def test_nzd_future_missing_or_naive_capture_clock_blocks(self):
        for stamp in (None, AS_OF + timedelta(minutes=1), datetime(2026, 11, 5, 1)):
            r = run(nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(),
                    nzd_capture_utc=stamp)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trading(r)

    def test_nzd_annual_rate_is_not_quarterly_change(self):
        changed = NZD_QUARTER_TEXT.replace("CPI all groups | 0.7 | 3.7",
                                           "CPI all groups | 0.2 | 3.7")
        r = run(nzd_quarter_page_text_raw=changed.encode(),
                nzd_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["currencies"]["NZD"]["rate_yoy_percent_claim"], "3.7")
        self.assertIsNone(r["currencies"]["NZD"]["observation_month"])
        self.assert_no_trading(r)

    def test_optional_aud_monthly_source_is_explicitly_unattested(self):
        r = run(aud_monthly_page_text_raw=AUD_MONTHLY_TEXT.encode(),
                aud_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 10, "1": 15, "2": 3})
        aud = r["currencies"]["AUD"]
        self.assertEqual(aud["status"], SUPPLIED_TEXT)
        self.assertEqual(aud["rate_yoy_percent_claim"], "4.3")
        self.assertEqual(aud["observation_frequency"], "MONTHLY")
        self.assertEqual(aud["observation_month"], "2026-09")
        self.assertEqual(aud["observation_period"], "2026-09")
        self.assertEqual(aud["series_kind"],
                         "ABS_AUD_CPI_ALL_GROUPS_ORIGINAL_MONTHLY_YOY_TRANSCRIBED_TEXT")
        self.assertFalse(aud["original_source_authenticity_independently_verified"])
        self.assert_no_trading(r)

    def test_aud_usd_same_month_still_not_methodologically_harmonized(self):
        r = run(aud_monthly_page_text_raw=AUD_MONTHLY_TEXT.encode(),
                aud_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
        x = pair(r, "AUD/USD")
        self.assertEqual(x["numeric_observation_sides"], 2)
        self.assertEqual((x["base_frequency"], x["quote_frequency"]),
                         ("MONTHLY", "MONTHLY"))
        self.assertTrue(x["observation_frequencies_aligned_if_both"])
        self.assertTrue(x["observation_months_aligned_if_both"])
        self.assertIn("CROSS_COUNTRY_INFLATION_METHODS_NOT_HARMONIZED",
                      x["comparison_blockers"])
        self.assertIsNone(x["inflation_difference_percentage_points"])
        self.assertIsNone(x["currency_strength_rank"])
        self.assert_no_trading(r)

    def test_aud_nzd_must_keep_monthly_quarterly_separation(self):
        stamp = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
        r = run(aud_monthly_page_text_raw=AUD_MONTHLY_TEXT.encode(), aud_capture_utc=stamp,
                nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(), nzd_capture_utc=stamp)
        x = pair(r, "AUD/NZD")
        self.assertEqual(x["numeric_observation_sides"], 2)
        self.assertEqual((x["base_frequency"], x["quote_frequency"]),
                         ("MONTHLY", "QUARTERLY"))
        self.assertEqual((x["base_latest_month"], x["quote_latest_month"]),
                         ("2026-09", None))
        self.assertFalse(x["observation_frequencies_aligned_if_both"])
        self.assertFalse(x["observation_months_aligned_if_both"])
        self.assertIn("OBSERVATION_FREQUENCIES_DIFFER", x["comparison_blockers"])
        self.assertIn("QUARTERLY_CPI_MUST_NOT_MASQUERADE_AS_MONTHLY",
                      x["comparison_blockers"])
        self.assert_no_trading(r)

    def test_seven_synthetic_currency_sources_cover_twenty_one_two_sided_pairs(self):
        stamp = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
        r = run(gbp_ons_raw=gbp_raw(), gbp_capture_utc=stamp,
                jpy_national_page_text_raw=JPY_TEXT.encode(), jpy_capture_utc=stamp,
                cad_nsa_table_text_raw=CAD_TEXT.encode(), cad_capture_utc=stamp,
                nzd_quarter_page_text_raw=NZD_QUARTER_TEXT.encode(), nzd_capture_utc=stamp,
                aud_monthly_page_text_raw=AUD_MONTHLY_TEXT.encode(), aud_capture_utc=stamp)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 0, "1": 7, "2": 21})
        self.assertEqual(r["currencies"]["CHF"]["status"], MISSING)
        for symbol in ("AUD/NZD", "AUD/USD", "EUR/AUD", "GBP/AUD", "AUD/JPY",
                       "AUD/CAD"):
            x = pair(r, symbol)
            self.assertEqual(x["numeric_observation_sides"], 2)
            self.assertIsNone(x["fx_bias"])
            self.assertIsNone(x["currency_strength_rank"])
        self.assert_no_trading(r)

    def test_invalid_aud_original_vs_adjusted_blocks_entire_matrix(self):
        for bad in (b"not ABS", AUD_MONTHLY_TEXT.replace("Sep-26 | 0.8 | 4.3",
                                                          "Sep-26 | 0.6 | 4.4").encode()):
            r = run(aud_monthly_page_text_raw=bad,
                    aud_capture_utc=datetime(2026, 11, 5, 1, tzinfo=timezone.utc))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trading(r)

    def test_aud_missing_future_or_naive_clock_blocks(self):
        for stamp in (None, AS_OF + timedelta(minutes=1), datetime(2026, 11, 5, 1)):
            r = run(aud_monthly_page_text_raw=AUD_MONTHLY_TEXT.encode(),
                    aud_capture_utc=stamp)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_trading(r)

    def test_aud_default_missing_preserves_old_pair_contract(self):
        r = run()
        self.assertEqual(r["currencies"]["AUD"]["status"], MISSING)
        self.assertEqual(r["pair_count_by_numeric_sides"], {"0": 15, "1": 12, "2": 1})
        self.assert_no_trading(r)


if __name__ == "__main__":
    unittest.main()
