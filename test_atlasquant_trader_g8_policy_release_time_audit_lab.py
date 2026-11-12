"""Issuer release-clock research must NEVER become retroactive P-I-T evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_g8_policy_release_time_audit_lab import (
    CASEBOOK_SHA256, inspect_g8_policy_release_time_audit_lab as inspect,
)

BOOK = (Path(__file__).resolve().parent / "docs" / "continuidade" /
        "TRADER_G8_EIGHT_POLICY_DECISION_TIMES_LAB_20261108.json").read_bytes()
DAY_AFTER = datetime(2026, 11, 9, tzinfo=timezone.utc)


class PolicyReleaseClockTests(unittest.TestCase):
    def evaluate(self, raw=BOOK, at=DAY_AFTER):
        return inspect(raw, as_of_utc=at)

    def assert_fail_closed(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertEqual(result["http_requests"], 0)
        self.assertEqual(result["new_cost_brl"], 0)
        for field in (
            "independent_first_publication_instant_attested",
            "original_issuer_response_bytes_archived_at_release",
            "rates_historical_pit_verified", "decision_values_pit_verified",
            "historical_intraday_asof_proven", "historical_backtest_allowed",
            "decision_clock_can_feed_live_bias", "trade_authorized",
            "worker_enabled", "scheduler_enabled", "publishable",
        ):
            self.assertFalse(result[field], field)
        for p in result["pair_rows"]:
            self.assertFalse(p["historical_asof_safe"])
            self.assertFalse(p["trade_authorized"])
            self.assertEqual((p["D1"], p["W1"]), ("AGUARDAR", "AGUARDAR"))

    def test_eight_currency_evidence_classes_and_all_pairs(self):
        self.assertEqual(sha256(BOOK).hexdigest(), CASEBOOK_SHA256)
        result = self.evaluate()
        self.assertEqual(result["state"], "LAB_EIGHT_ISSUER_CLOCK_CLAIMS_CLASSIFIED_NOT_PIT_ATTESTED")
        self.assertEqual((result["currency_count"], result["pair_count"]), (8, 28))
        self.assertEqual(result["time_class_counts"], {
            "ISSUER_EXPLICIT_RELEASE_TIME": 2,
            "ISSUER_RECORDED_UPDATE_TIME": 1,
            "ISSUER_SCHEDULED_TIME": 4,
            "ISSUER_PATTERN_ONLY": 1,
        })
        self.assertEqual({p["pair"] for p in result["pair_rows"]}, set(OFFICIAL_PAIRS))
        self.assert_fail_closed(result)

    def test_exact_issuer_document_times_were_converted_with_real_dst(self):
        rows = {row["currency"]: row for row in self.evaluate()["currency_rows"]}
        self.assertEqual(rows["USD"]["claimed_utc_instant_for_research_only"], "2026-10-28T18:00:00Z")
        self.assertEqual(rows["JPY"]["claimed_utc_instant_for_research_only"], "2026-10-30T03:02:00Z")
        for currency in ("USD", "JPY"):
            self.assertTrue(rows[currency]["issuer_declares_release_time_in_original_decision_document"])
            self.assertFalse(rows[currency]["historical_asof_safe"])

    def test_scheduled_times_are_not_misrepresented_as_actual_publications(self):
        rows = {row["currency"]: row for row in self.evaluate()["currency_rows"]}
        expected = {
            "EUR": "2026-10-29T13:15:00Z",  # Germany after October DST ended
            "GBP": "2026-11-05T12:00:00Z",  # Britain after DST ended
            "CAD": "2026-10-28T13:45:00Z",  # Canada still on DST
            "AUD": "2026-11-03T03:30:00Z",  # Sydney on DST
        }
        for currency, utc in expected.items():
            self.assertEqual(rows[currency]["claimed_utc_instant_for_research_only"], utc)
            self.assertEqual(rows[currency]["evidence_class"], "ISSUER_SCHEDULED_TIME")
            self.assertFalse(rows[currency]["issuer_declares_release_time_in_original_decision_document"])
            self.assertFalse(rows[currency]["actual_release_instant_independently_captured"])

    def test_swiss_pattern_only_never_becomes_september_release_proof(self):
        rows = {row["currency"]: row for row in self.evaluate()["currency_rows"]}
        chf = rows["CHF"]
        self.assertEqual(chf["claimed_utc_instant_for_research_only"], "2026-09-24T07:30:00Z")
        self.assertEqual(chf["evidence_class"], "ISSUER_PATTERN_ONLY")
        self.assertFalse(chf["can_retroactively_use_as_market_information"])
        self.assert_fail_closed(self.evaluate())

    def test_new_zealand_recorded_update_is_not_original_capture(self):
        rows = {row["currency"]: row for row in self.evaluate()["currency_rows"]}
        nzd = rows["NZD"]
        self.assertEqual(nzd["claimed_utc_instant_for_research_only"], "2026-10-28T01:00:00Z")
        self.assertEqual(nzd["evidence_class"], "ISSUER_RECORDED_UPDATE_TIME")
        self.assertFalse(nzd["original_announcement_bytes_archived"])
        self.assertFalse(nzd["historical_asof_safe"])

    def test_even_pair_of_issuer_explicit_release_times_stays_blocked(self):
        rows = {r["pair"]: r for r in self.evaluate()["pair_rows"]}
        self.assertTrue(rows["USD/JPY"]["both_issuers_have_explicit_release_clock_claims"])
        self.assertFalse(rows["USD/JPY"]["historical_asof_safe"])
        self.assertEqual(rows["USD/JPY"]["D1"], "AGUARDAR")

    def test_before_research_visibility_no_hindsight_even_after_2026_decisions(self):
        when = datetime(2026, 11, 8, 23, 59, 59, tzinfo=timezone.utc)
        result = self.evaluate(at=when)
        self.assertEqual(result["state"], "LAB_RESEARCH_NOT_VISIBLE_ASOF")
        self.assertEqual((result["currency_rows"], result["pair_rows"]), ([], []))
        self.assert_fail_closed(result)

    def test_time_zone_shift_at_research_visibility_boundary(self):
        local = datetime(2026, 11, 8, 20, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.evaluate(at=local), self.evaluate())

    def test_invalid_casebook_or_clock_fails_closed(self):
        cases = (
            (BOOK + b"\n", DAY_AFTER),
            (BOOK.replace(b'"14:15"', b'"15:15"'), DAY_AFTER),
            (BOOK.replace(b'"ISSUER_PATTERN_ONLY"', b'"ISSUER_EXPLICIT_RELEASE_TIME"'), DAY_AFTER),
            (b"{}", DAY_AFTER),
            (None, DAY_AFTER),
            (BOOK, datetime(2026, 11, 9)),
            (BOOK, None),
        )
        for raw, when in cases:
            result = self.evaluate(raw, at=when)
            self.assertEqual(result["state"], "LAB_BLOCKED")
            self.assertEqual(result["currency_count"], 0)
            self.assert_fail_closed(result)

    def test_distant_future_does_not_validate_a_research_snapshot_as_pit(self):
        result = self.evaluate(at=datetime(2030, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(result["currency_count"], 8)
        self.assert_fail_closed(result)


if __name__ == "__main__":
    unittest.main()
