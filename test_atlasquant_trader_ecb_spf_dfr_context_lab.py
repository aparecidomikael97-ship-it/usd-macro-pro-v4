"""Strict synthetic checks only; independent vintage is never claimed."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from atlasquant_trader_ecb_spf_dfr_context_lab import (
    audit_ecb_spf_dfr_context_lab as audit,
)

UTC = timezone.utc
Q3_TITLE = "The ECB Survey of Professional Forecasters - Third quarter of 2026"
Q4_TITLE = "The ECB Survey of Professional Forecasters - Fourth quarter of 2026"
Q3_PARA = (
    "For the third quarter of 2026, the modal expectation remained at 2.25%, "
    "reported by 61% of respondents. The modal expectation rising to 2.50% "
    "in the fourth quarter of 2026 and the first quarter of 2027."
)
Q4_PARA = (
    "For the fourth quarter of 2026 the modal expectation for the DFR "
    "remains at 2.50%, as reported by 48% of respondents."
)


def doc(title: str = Q3_TITLE, para: str = Q3_PARA) -> bytes:
    return ("<html><head><title>Ignored duplicate heading</title><script>" +
            "For the third quarter of 2026, the modal expectation remained " +
            "at 99.00%, reported by 99% of respondents.</script></head><body>" +
            "<h1>" + title + "</h1><p>" + para + "</p></body></html>").encode()


def dt(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 18, tzinfo=UTC)


def case(**changes):
    opts = {
        "source_id": "ECB_SPF_2026Q3",
        "event_date": "2026-10-29",
        "captured_at_utc": dt(11, 5),
        "as_of_utc": dt(11, 5),
        "raw_html": doc(),
    }
    opts.update(changes)
    return audit(**opts)


class EcbSpfQuarterlyContextTests(unittest.TestCase):
    def test_q3_before_october_meeting_is_context_not_meeting_consensus(self):
        r = case()
        self.assertEqual(r["state"], "LAB_QUARTERLY_CONTEXT_DATE_PRECEDES_EVENT_UNVERIFIED")
        self.assertEqual(r["official_release_date"], "2026-07-24")
        self.assertEqual(r["survey_quarter_modal_dfr_pct"], "2.25")
        self.assertEqual(r["survey_quarter_modal_share_pct"], 61)
        self.assertEqual(r["q4_2026_modal_dfr_forecast_from_q3_pct"], "2.50")
        self.assertTrue(r["capture_after_event_date"])
        self.assertTrue(r["quarterly_context_parsed"])
        self.assertEqual(len(r["html_sha256"]), 64)
        self.assertFalse(r["immutable_historical_vintage_verified"])
        self.assertFalse(r["historical_point_in_time_eligible"])
        self.assertFalse(r["pre_event_meeting_consensus_verified"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertIsNone(r["fx_bias"])
        self.assertIsNone(r["market_surprise_bps"])
        self.assertFalse(r["trade_authorized"])

    def test_q4_published_after_october_meeting_is_lookahead(self):
        r = case(source_id="ECB_SPF_2026Q4", raw_html=doc(Q4_TITLE, Q4_PARA))
        self.assertEqual(r["reason"], "SPF_RELEASE_DATED_AFTER_EVENT")
        self.assertEqual(r["official_release_date"], "2026-10-30")
        self.assertEqual(r["survey_quarter_modal_dfr_pct"], "2.50")
        self.assertEqual(r["survey_quarter_modal_share_pct"], 48)
        self.assertIsNone(r["q4_2026_modal_dfr_forecast_from_q3_pct"])
        self.assertFalse(r["historical_point_in_time_eligible"])

    def test_q4_can_be_context_for_later_event_but_not_a_signal(self):
        r = case(source_id="ECB_SPF_2026Q4", raw_html=doc(Q4_TITLE, Q4_PARA),
                 event_date="2026-12-17")
        self.assertEqual(r["state"], "LAB_QUARTERLY_CONTEXT_DATE_PRECEDES_EVENT_UNVERIFIED")
        self.assertFalse(r["trade_authorized"])

    def test_same_day_report_refuses_intraday_order_claim(self):
        r = case(event_date="2026-07-24", captured_at_utc=dt(7, 24),
                 as_of_utc=dt(7, 24))
        self.assertEqual(r["reason"], "SPF_SAME_DAY_EVENT_INSTANT_UNKNOWN")

    def test_q3_report_is_not_available_before_its_release(self):
        r = case(event_date="2026-07-23", captured_at_utc=dt(7, 23),
                 as_of_utc=dt(7, 23))
        self.assertEqual(r["reason"], "SPF_RELEASE_DATED_AFTER_EVENT")

    def test_q3_can_have_pre_event_capture_but_vintage_remains_unverified(self):
        r = case(captured_at_utc=dt(10, 28), as_of_utc=dt(10, 28))
        self.assertFalse(r["capture_after_event_date"])
        self.assertFalse(r["immutable_historical_vintage_verified"])

    def test_wrong_survey_title_rejected(self):
        r = case(raw_html=doc(Q4_TITLE, Q3_PARA))
        self.assertEqual(r["reason"], "SPF_RELEASE_TITLE_MISSING_OR_DUPLICATED")

    def test_duplicate_title_rejected(self):
        r = case(raw_html=doc(Q3_TITLE, Q3_TITLE + " " + Q3_PARA))
        self.assertEqual(r["reason"], "SPF_RELEASE_TITLE_MISSING_OR_DUPLICATED")

    def test_duplicate_dfr_paragraph_rejected(self):
        r = case(raw_html=doc(Q3_TITLE, Q3_PARA + " " + Q3_PARA))
        self.assertEqual(r["reason"], "SPF_DFR_CONTEXT_MISSING_OR_AMBIGUOUS")

    def test_missing_future_q4_horizon_rejected(self):
        r = case(raw_html=doc(Q3_TITLE, Q3_PARA.split(" The modal")[0]))
        self.assertEqual(r["reason"], "SPF_DFR_CONTEXT_MISSING_OR_AMBIGUOUS")

    def test_non_utf8_rejected(self):
        r = case(raw_html=b"\xff\xfe\xfa")
        self.assertEqual(r["reason"], "HTML_NOT_STRICTLY_READABLE")

    def test_out_of_bounds_values_rejected(self):
        for para in (Q3_PARA.replace("61%", "101%"),
                     Q3_PARA.replace("2.25%", "99.99%")):
            with self.subTest(para=para):
                r = case(raw_html=doc(Q3_TITLE, para))
                self.assertEqual(r["reason"], "SPF_DFR_VALUE_INVALID")

    def test_bad_metadata_fails_closed(self):
        for change in ({"source_id": "ECB_SPF_2026Q5"},
                       {"source_id": ["ECB_SPF_2026Q3"]},
                       {"event_date": "2026-10-35"},
                       {"event_date": "2026-10-9"},
                       {"captured_at_utc": None},
                       {"captured_at_utc": dt(11, 5).replace(tzinfo=None)},
                       {"as_of_utc": dt(11, 5).replace(tzinfo=None)},
                       {"as_of_utc": dt(11, 4)},
                       {"raw_html": None}, {"raw_html": b""},
                       {"raw_html": b"x" * (512 * 1024 + 1)}):
            with self.subTest(change=str(change)[:50]):
                self.assertEqual(case(**change)["reason"], "INVALID_INPUT")

    def test_no_code_path_enables_trade_or_radars(self):
        for r in (case(), case(source_id="ECB_SPF_2026Q4",
                               raw_html=doc(Q4_TITLE, Q4_PARA))):
            for flag in ("trade_authorized", "publishable", "can_feed_live_radar",
                         "worker_enabled", "scheduler_enabled",
                         "pre_event_meeting_consensus_verified"):
                self.assertFalse(r[flag])
            self.assertEqual(r["new_cost_brl"], 0)


if __name__ == "__main__":
    unittest.main()
