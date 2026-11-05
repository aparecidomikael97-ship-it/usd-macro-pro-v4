"""Synthetic Japanese CPI summary text fixtures, not captured publisher bytes."""
from datetime import datetime, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_jp_national_cpi_summary_text_lab import (
    SCHEMA, SOURCE_URL, parse_jp_national_cpi_summary_text_lab as parse,
)

OBSERVED = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
TEXT = """統計局ホームページ 消費者物価指数(CPI) 全国（最新の月次結果の概要）
2025年基準　消費者物価指数　全国　2026年（令和8年）9月分（2026年10月23日公表）
≪ポイント≫
　(1)　 総合指数は2025年を100として102.2
　　　　前年同月比は2.1%の上昇
　(2)　 生鮮食品を除く総合指数は102.3
　　　　前年同月比は2.1％の上昇
　(3)　 生鮮食品及びエネルギーを除く総合指数は102.8
　　　　前年同月比は2.4%の上昇
次回の公表日は、公表予定をご覧ください。
"""


def run(text=TEXT, observed=OBSERVED):
    return parse(text.encode("utf-8") if isinstance(text, str) else text,
                 observed_at_utc=observed)


class JapanNationalCpiTextTests(unittest.TestCase):
    def assert_hard_no_go(self, r):
        for flag in (
            "tokyo_preliminary_included", "source_is_official_original_http_response",
            "parsed_text_authenticity_independently_verified",
            "individual_release_instant_verified", "historical_vintage_verified",
            "consensus_pre_event_attested", "cross_country_methods_equivalent",
            "commercial_redistribution_rights_verified", "trade_authorized",
            "can_feed_live_radar", "worker_enabled", "scheduler_enabled",
            "publishable",
        ):
            self.assertIs(r[flag], False, flag)
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertEqual((r["external_http_requests"], r["new_cost_brl"]), (0, 0))

    def test_2026_september_official_page_shaped_synthetic_text(self):
        r = run()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_JP_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED")
        self.assertEqual(r["source_page"], SOURCE_URL)
        self.assertEqual(r["reference_period"], "2026-09")
        self.assertEqual(r["release_date_japan_calendar_only"], "2026-10-23")
        self.assertEqual(r["base_year"], 2025)
        self.assertEqual((r["national_headline_all_items"]["index_2025_base_claim"],
                          r["national_headline_all_items"]["reported_yoy_percent_claim"]),
                         ("102.2", "2.1"))
        self.assertEqual(r["national_excluding_fresh_food"]["reported_yoy_percent_claim"],
                         "2.1")
        self.assertEqual(r["national_excluding_fresh_food_and_energy"][
            "reported_yoy_percent_claim"], "2.4")
        self.assertEqual(r["source_sha256"], sha256(TEXT.encode()).hexdigest())
        self.assert_hard_no_go(r)

    def test_headline_does_not_take_core_or_core_core_values(self):
        t = TEXT.replace("2.1%の上昇", "1.8%の上昇", 1)
        r = run(t)
        self.assertEqual(r["national_headline_all_items"]["reported_yoy_percent_claim"],
                         "1.8")
        self.assertEqual(r["national_excluding_fresh_food"]["reported_yoy_percent_claim"],
                         "2.1")
        self.assertEqual(r["national_excluding_fresh_food_and_energy"][
            "reported_yoy_percent_claim"], "2.4")
        self.assert_hard_no_go(r)

    def test_tokyo_only_page_not_accepted_as_national(self):
        t = TEXT.replace("消費者物価指数　全国　", "消費者物価指数　東京都区部　")
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_tokyo_preliminary_text_cannot_replace_national_rows(self):
        t = TEXT.replace("≪ポイント≫", "≪ポイント≫\n東京都区部の速報は別系列です")
        r = run(t)
        self.assertFalse(r["tokyo_preliminary_included"])
        self.assert_hard_no_go(r)

    def test_2020_base_is_not_allowed_in_2025_base_parser(self):
        t = TEXT.replace("2025年基準", "2020年基準")
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")
        t = TEXT.replace("2025年を100", "2020年を100")
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_missing_core_or_other_variant_refused(self):
        for label in ("(1)", "(2)", "(3)"):
            self.assertEqual(run(TEXT.replace(label, "(X)"))["state"], "LAB_BLOCKED")

    def test_duplicate_headline_row_refused(self):
        head = "(1)　 総合指数は2025年を100として102.2\n前年同月比は2.1%の上昇"
        r = run(TEXT.replace("(2)", head + "\n(2)"))
        self.assertEqual(r["state"], "LAB_BLOCKED")

    def test_duplicate_header_refused(self):
        header = "2025年基準　消費者物価指数　全国　2026年（令和8年）9月分（2026年10月23日公表）"
        self.assertEqual(run(TEXT + header)["state"], "LAB_BLOCKED")

    def test_duplicate_points_marker_refused(self):
        self.assertEqual(run(TEXT.replace("≪ポイント≫", "≪ポイント≫ ≪ポイント≫"))["state"],
                         "LAB_BLOCKED")

    def test_japanese_fullwidth_percent_and_ascii_accepted(self):
        r = run(TEXT.replace("2.1%", "2.1％"))
        self.assertEqual(r["state"], "LAB_JP_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED")

    def test_negative_inflation_phrase_not_turned_positive(self):
        t = TEXT.replace("2.1%の上昇", "0.4%の下落", 1)
        r = run(t)
        self.assertEqual(r["national_headline_all_items"]["reported_yoy_percent_claim"],
                         "-0.4")

    def test_flat_phrase_requires_exact_zero(self):
        t = TEXT.replace("2.1%の上昇", "0.0%の横ばい", 1)
        self.assertEqual(run(t)["national_headline_all_items"][
            "reported_yoy_percent_claim"], "0.0")
        t = TEXT.replace("2.1%の上昇", "0.1%の横ばい", 1)
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_zero_inflation_with_rise_or_fall_refused(self):
        for ending in ("0.0%の上昇", "0.0%の下落"):
            self.assertEqual(run(TEXT.replace("2.1%の上昇", ending, 1))["state"],
                             "LAB_BLOCKED")

    def test_invalid_negative_index_or_too_large_rate_refused(self):
        for bad in ("402.2", "48.2", "-1.0"):
            self.assertEqual(run(TEXT.replace("102.2", bad, 1))["state"],
                             "LAB_BLOCKED")
        self.assertEqual(run(TEXT.replace("2.1%", "51.0%", 1))["state"],
                         "LAB_BLOCKED")

    def test_era_year_mismatch_refused(self):
        self.assertEqual(run(TEXT.replace("令和8年", "令和7年"))["state"],
                         "LAB_BLOCKED")

    def test_wrong_reference_month_refused(self):
        self.assertEqual(run(TEXT.replace("9月分", "13月分"))["state"],
                         "LAB_BLOCKED")

    def test_release_month_cannot_precede_or_equal_observation_month(self):
        t = TEXT.replace("2026年10月23日公表", "2026年9月23日公表")
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")
        t = TEXT.replace("2026年10月23日公表", "2026年8月23日公表")
        self.assertEqual(run(t)["state"], "LAB_BLOCKED")

    def test_future_reported_date_after_local_japan_capture_refused(self):
        earlier = datetime(2026, 10, 22, 10, tzinfo=timezone.utc)
        self.assertEqual(run(observed=earlier)["state"], "LAB_BLOCKED")

    def test_japan_calendar_day_can_advance_ahead_of_utc(self):
        utc22 = datetime(2026, 10, 22, 23, tzinfo=timezone.utc)
        r = run(observed=utc22)
        self.assertEqual(r["state"], "LAB_JP_NATIONAL_CPI_SUPPLIED_TEXT_QUARANTINED")
        self.assert_hard_no_go(r)

    def test_nan_exponent_comma_text_not_rate(self):
        for invalid in ("NaN", "2,1", "2e0", "Infinity"):
            self.assertEqual(run(TEXT.replace("2.1%", invalid + "%", 1))["state"],
                             "LAB_BLOCKED")

    def test_invalid_utf8_embedded_html_or_null_rejected(self):
        for bad in (b"\xff" + TEXT.encode(), (TEXT + "<html>").encode(),
                    TEXT.encode() + b"\x00"):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_empty_oversized_and_non_bytes_rejected(self):
        for bad in (b"", b"x" * (64 * 1024 + 1), None, []):
            self.assertEqual(run(bad)["state"], "LAB_BLOCKED")

    def test_naive_or_missing_capture_clock_rejected(self):
        self.assertEqual(run(observed=datetime(2026, 11, 5))["state"], "LAB_BLOCKED")
        self.assertEqual(run(observed=None)["state"], "LAB_BLOCKED")

    def test_no_synthetic_input_can_authorize_market_direction(self):
        texts = (TEXT,
                 TEXT.replace("2.1%の上昇", "0.4%の下落", 1),
                 TEXT.replace("2.1%の上昇", "0.0%の横ばい", 1))
        for t in texts:
            self.assert_hard_no_go(run(t))


if __name__ == "__main__":
    unittest.main()
