"""Synthetic BLS release HTML and retrospective claims only; NOT an event replay."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest

from atlasquant_trader_us_oct2026_cpi_release_text_guard_lab import (
    ClaimedBLSHtmlReceipt, RELEASE_FLOOR_UTC, URL,
)
from atlasquant_trader_us_oct2026_cpi_documentary_comparison_lab import (
    ReportedPreviewClaim, PREVIEW_URL, PREVIEW_PUBLISHED_CLOCK_CLAIM,
    DOCUMENTARY_RESEARCH_VISIBLE_FROM_UTC,
    inspect_oct2026_cpi_documentary_comparison_lab as inspect,
)
UTC = timezone.utc
NOW = datetime(2026, 11, 11, 2, 0, tzinfo=UTC)
CAPTURE = datetime(2026, 11, 11, 0, 11, 11, tzinfo=UTC)


def html(head="0.4", core="0.3"):
    return ("<html><body>USDL-26-1685 Tuesday, November 10, 2026 "
            "CONSUMER PRICE INDEX - OCTOBER 2026 "
            "The Consumer Price Index for All Urban Consumers (CPI-U) increased "
            + head + " percent on a seasonally adjusted basis in October. "
            "The index for all items less food and energy rose "
            + core + " percent in October. "
            "BLS did not collect survey data for October 2025. "
            "BLS cannot publish 12-month percent changes for October 2026. "
            "</body></html>").encode("utf-8")


def preview():
    return ReportedPreviewClaim(
        source_url=PREVIEW_URL, published_at_utc_claim=PREVIEW_PUBLISHED_CLOCK_CLAIM,
        metric="CPI_U_SA_MONTH_OVER_MONTH_PERCENT_CHANGE",
        headline_consensus_pct_claim="0.3", core_consensus_pct_claim="0.2")


def receipt(b):
    return ClaimedBLSHtmlReceipt(source_url=URL, http_status=200,
        content_type="text/html", captured_at_utc=CAPTURE,
        body_sha256_claim=sha256(b).hexdigest())


class DocumentaryCpiTests(unittest.TestCase):
    def case(self, b=None, rec=None, p=None, now=NOW):
        b = html() if b is None else b
        return inspect(raw_bls_html=b, bls_receipt=receipt(b) if rec is None else rec,
                       preview=preview() if p is None else p, as_of_utc=now)

    def no_signal(self, o):
        for k in ("statistically_verified_surprise", "directional_usd_signal",
                  "eurusd_directional_bias", "direction_probability", "validated_accuracy",
                  "official_yoy_headline_2026_10", "official_yoy_core_2026_10"):
            self.assertIsNone(o[k], k)
        for k in ("preview_first_publication_independently_attested", "preview_bytes_preserved_pre_event",
                  "pre_event_poll_methodology_witnessed", "actual_BLS_first_release_attested",
                  "can_feed_live_radar", "historical_point_in_time_verified", "backtest_eligible",
                  "trade_authorized", "publishable", "worker_enabled", "scheduler_enabled"):
            self.assertIs(o[k], False, k)
        self.assertEqual(o["operational_bias"], "AGUARDAR")
        self.assertEqual(o["http_requests"], 0)
        self.assertEqual(o["new_cost_brl"], 0)

    def test_documentary_actual_forecast_diffs_both_plus_point_one(self):
        o=self.case()
        self.assertEqual(o["state"], "LAB_RETROSPECTIVE_DOCUMENTARY_DIFFERENCE_NO_PIT_SIGNAL")
        self.assertEqual((o["headline_retrospective_difference_pp_claim"],
                          o["core_retrospective_difference_pp_claim"]), ("0.1", "0.1"))
        self.assertEqual((o["headline_actual_monthly_sa_pct_document_claim"],
                          o["core_actual_monthly_sa_pct_document_claim"]), ("0.4", "0.3"))
        self.no_signal(o)

    def test_not_backdated_into_release_moment(self):
        for now in (RELEASE_FLOOR_UTC, DOCUMENTARY_RESEARCH_VISIBLE_FROM_UTC-timedelta(seconds=1),
                    datetime(2026, 11, 9, tzinfo=UTC)):
            with self.subTest(now=now):
                o=self.case(now=now)
                self.assertEqual(o["state"], "LAB_DOCUMENTARY_COMPARISON_BLOCKED")
                self.assertIsNone(o["headline_retrospective_difference_pp_claim"])
                self.no_signal(o)

    def test_wrong_preview_source_or_published_after_event_blocks(self):
        for pp in (replace(preview(), source_url="https://fake.example/p"),
                   replace(preview(), published_at_utc_claim=RELEASE_FLOOR_UTC+timedelta(seconds=1)),
                   replace(preview(), published_at_utc_claim=PREVIEW_PUBLISHED_CLOCK_CLAIM.replace(tzinfo=None))):
            with self.subTest(pp=pp):
                o=self.case(p=pp)
                self.assertEqual(o["reason"], "PREVIEW_SOURCE_CLOCK_METRIC_OR_PROVENANCE_UNSUPPORTED")
                self.no_signal(o)

    def test_yoy_or_raw_index_not_monthly_seasonally_adjusted(self):
        for metric in ("CPI_U_NSA_YEAR_OVER_YEAR_PERCENT_CHANGE", "CPI_U_INDEX_LEVEL", "CPI_U_NSA_MOM"):
            with self.subTest(metric=metric):
                o=self.case(p=replace(preview(),metric=metric))
                self.assertEqual(o["state"], "LAB_DOCUMENTARY_COMPARISON_BLOCKED")
                self.no_signal(o)

    def test_forecast_claim_other_than_published_preview_does_not_pass(self):
        for p in (replace(preview(), headline_consensus_pct_claim="0.4"),
                  replace(preview(), core_consensus_pct_claim="0.3"),
                  replace(preview(), headline_consensus_pct_claim="nan")):
            with self.subTest(p=p):
                o=self.case(p=p)
                self.assertEqual(o["reason"], "REPORTED_PRE_EVENT_CONSENSUS_VALUES_NOT_MATCHING_DOCUMENTED_PREVIEW")
                self.no_signal(o)

    def test_cannot_falsely_mark_source_independently_attested(self):
        for p in (replace(preview(),source_bytes_archived_before_event=True),
                  replace(preview(),first_publication_attested=True),
                  replace(preview(),Reuters_poll_witnessed_before_event=True)):
            with self.subTest(p=p):
                o=self.case(p=p)
                self.assertEqual(o["state"], "LAB_DOCUMENTARY_COMPARISON_BLOCKED")
                self.no_signal(o)

    def test_bls_forged_url_hash_or_release_day_not_eligible(self):
        b=html()
        for rec in (replace(receipt(b),source_url="https://fake.example/"),
                    replace(receipt(b),body_sha256_claim="a"*64),
                    replace(receipt(b),captured_at_utc=RELEASE_FLOOR_UTC-timedelta(seconds=1))):
            with self.subTest(rec=rec):
                o=self.case(b=b,rec=rec)
                self.assertEqual(o["reason"], "BLS_RAW_HTML_OR_MONTHLY_METRICS_NOT_ADMISSIBLE")
                self.no_signal(o)

    def test_bls_duplicate_inconsistent_core_fails(self):
        b=html().replace(b"</body>",
            b"The index for all items less food and energy rose 2.3 percent in October. </body>")
        o=self.case(b=b)
        self.assertEqual(o["reason"], "BLS_RAW_HTML_OR_MONTHLY_METRICS_NOT_ADMISSIBLE")
        self.no_signal(o)

    def test_missing_official_yearly_baseline_never_filled(self):
        b=html().replace(b"BLS cannot publish 12-month percent changes for October 2026.",b"")
        o=self.case(b=b)
        self.assertEqual(o["state"], "LAB_DOCUMENTARY_COMPARISON_BLOCKED")
        self.assertIsNone(o["headline_retrospective_difference_pp_claim"])
        self.no_signal(o)

    def test_unrelated_21_g8_pairs_have_no_directional_output(self):
        o=self.case()
        self.assertIsNone(o["eurusd_directional_bias"])
        self.no_signal(o)


if __name__ == "__main__":
    unittest.main()