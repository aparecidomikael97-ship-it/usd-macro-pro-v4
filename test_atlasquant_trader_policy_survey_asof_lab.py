"""Documentary official policy-survey as-of and anti-lookahead tests, LAB."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_policy_survey_asof_lab import (
    SCHEMA, audit_official_policy_surveys_lab,
)

CASE = (Path(__file__).resolve().parent / "docs" / "continuidade"
        / "TRADER_POLICY_SURVEY_DOCUMENTARY_CASE_20261103.json")


def when(day: str) -> datetime:
    return datetime.fromisoformat(day.replace("Z", "+00:00"))


def book() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def run(document=None, at="2026-11-03T12:00:00Z"):
    return audit_official_policy_surveys_lab(
        book() if document is None else document, evaluated_at=when(at),
    )


def row(out, code: str) -> dict:
    return next(x for x in out["records"] if x["currency"] == code)


class PolicySurveyAsOfTests(unittest.TestCase):
    def test_real_documentary_triple_is_quarantined(self):
        out = run()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_DOCUMENTARY_POLICY_AVAILABILITY_ONLY")
        self.assertEqual(len(out["records"]), 3)
        self.assertEqual(out["currency_coverage"], [])
        self.assertEqual(row(out, "GBP")["status"], "PRE_EVENT_BUT_STALE")
        self.assertEqual(row(out, "GBP")["document_age_days"], 46)
        self.assertEqual(row(out, "GBP")["documentary_median_policy_rate_pct"], "3.75")
        self.assertEqual(row(out, "EUR")["status"], "TIMETABLE_ONLY_NOT_ATTESTED")
        self.assertEqual(row(out, "USD")["status"], "RESULT_NOT_PUBLICLY_OBSERVED")

    def test_boe_fresh_between_publication_and_event(self):
        out = run(at="2026-09-19T00:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "PRE_EVENT_DOCUMENTARY_CURRENT")
        self.assertEqual(out["currency_coverage"], ["GBP"])
        self.assertTrue(row(out, "GBP")["fresh_under_lab_policy"])
        self.assertIsNone(out["cross_currency_policy_bias"])

    def test_date_only_publication_not_available_same_day(self):
        out = run(at="2026-09-18T23:59:59Z")
        self.assertEqual(row(out, "GBP")["status"], "NOT_YET_AVAILABLE_CONSERVATIVE_UTC")
        self.assertIsNone(row(out, "GBP")["documentary_median_policy_rate_pct"])

    def test_before_publication_is_not_available(self):
        out = run(at="2026-09-17T12:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "NOT_YET_AVAILABLE_CONSERVATIVE_UTC")

    def test_freshness_boundary_day_30(self):
        out = run(at="2026-10-18T20:00:00Z")
        self.assertEqual(row(out, "GBP")["document_age_days"], 30)
        self.assertTrue(row(out, "GBP")["fresh_under_lab_policy"])

    def test_freshness_boundary_day_31(self):
        out = run(at="2026-10-19T00:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "PRE_EVENT_BUT_STALE")
        self.assertFalse(row(out, "GBP")["fresh_under_lab_policy"])

    def test_target_event_day_blocked_entire_day(self):
        out = run(at="2026-11-05T00:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "TARGET_EVENT_DAY_OR_PASSED")
        self.assertIsNone(row(out, "GBP")["documentary_median_policy_rate_pct"])

    def test_target_event_past_blocked(self):
        out = run(at="2026-11-07T00:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "TARGET_EVENT_DAY_OR_PASSED")

    def test_published_after_event_cannot_relabel_as_prediction(self):
        doc = book()
        r = doc["records"][0]
        r["published_on"] = "2026-11-06"
        r["collected_through"] = "2026-11-05"
        out = run(doc, at="2026-11-08T12:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "POST_EVENT_LEAK_BLOCKED")

    def test_published_on_event_day_is_leak_blocked(self):
        doc = book()
        doc["records"][0]["published_on"] = "2026-11-05"
        out = run(doc, at="2026-11-06T12:00:00Z")
        self.assertEqual(row(out, "GBP")["status"], "POST_EVENT_LEAK_BLOCKED")

    def test_conservative_utc_from_offset(self):
        doc = book()
        timestamp = when("2026-09-18T22:30:00-04:00")
        out = audit_official_policy_surveys_lab(doc, evaluated_at=timestamp)
        self.assertEqual(row(out, "GBP")["status"], "PRE_EVENT_DOCUMENTARY_CURRENT")
        self.assertEqual(out["evaluated_at_utc"], "2026-09-19T02:30:00+00:00")

    def test_no_credentials_or_forged_host(self):
        doc = book()
        doc["records"][0]["source_url"] = "https://www.bankofengland.co.uk.evil.invalid/data"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_http_source_blocked(self):
        doc = book()
        doc["records"][0]["source_url"] = doc["records"][0]["source_url"].replace(
            "https://", "http://",
        )
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_url_with_credentials_blocked(self):
        doc = book()
        doc["records"][0]["source_url"] = "https://user:pass@www.bankofengland.co.uk/data"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_url_with_query_is_blocked(self):
        doc = book()
        doc["records"][0]["source_url"] += "?foo=bar"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_authority_currency_mismatch_blocked(self):
        doc = book()
        doc["records"][0]["currency"] = "USD"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_unknown_publication_state_rejected(self):
        doc = book()
        doc["records"][0]["publication_state"] = "LIVE_MARKET_CONSENSUS"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_schedule_not_falsely_published(self):
        doc = book()
        doc["records"][1]["median_pct"] = "2.50"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_timetable_missing_scheduled_date(self):
        doc = book()
        doc["records"][1]["scheduled_publication_on"] = None
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_unobserved_cannot_claim_publish_day(self):
        doc = book()
        doc["records"][2]["published_on"] = "2026-10-30"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_wrong_quantile_order_rejected(self):
        doc = book()
        doc["records"][0]["p25_pct"] = "4.00"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_float_median_rejected(self):
        doc = book()
        doc["records"][0]["median_pct"] = 3.75
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_bad_date_rejected(self):
        doc = book()
        doc["records"][0]["published_on"] = "2026-13-40"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_bad_collection_order_rejected(self):
        doc = book()
        doc["records"][0]["collected_through"] = "2026-09-19"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_missing_field_rejected(self):
        doc = book()
        del doc["records"][0]["respondents"]
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_extra_field_rejected(self):
        doc = book()
        doc["records"][0]["trading_signal"] = "BUY"
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_duplicate_identity_rejected(self):
        doc = book()
        doc["records"].append(deepcopy(doc["records"][0]))
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_boolean_respondents_rejected(self):
        doc = book()
        doc["records"][0]["respondents"] = True
        self.assertEqual(run(doc)["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")

    def test_naive_evaluation_time_rejected(self):
        with self.assertRaises(ValueError):
            audit_official_policy_surveys_lab(book(), evaluated_at=datetime(2026, 11, 3))

    def test_complete_gate_never_authorizes_operation(self):
        for time in ("2026-09-19T12:00:00Z", "2026-11-03T12:00:00Z",
                     "2026-11-06T12:00:00Z"):
            out = run(at=time)
            self.assertIsNone(out["cross_currency_policy_bias"])
            self.assertIsNone(out["policy_probability"])
            self.assertFalse(out["accuracy_90_proven"])
            self.assertFalse(out["independent_historical_receipt"])
            self.assertFalse(out["can_feed_live_radar"])
            self.assertFalse(out["trade_authorized"])
            self.assertFalse(out["worker_enabled"])
            self.assertFalse(out["scheduler_enabled"])
            self.assertTrue(all(
                not r["historical_capture_receipt_verified"]
                and not r["cross_currency_signal_authorized"] for r in out["records"]
            ))

    def test_reject_mode_also_never_authorizes_operation(self):
        out = run({"schema": "forged", "records": []})
        self.assertEqual(out["state"], "LAB_DOCUMENTARY_POLICY_AUDIT_REJECTED")
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["can_feed_live_radar"])


if __name__ == "__main__":
    unittest.main()
