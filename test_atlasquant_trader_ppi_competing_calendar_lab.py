"""Synthetic contract tests: competing calendar never becomes causality/bias."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_ppi_competing_calendar_lab import (
    CompetingEventClaim as Event, PreEventCalendarClaim as Snapshot,
    audit_ppi_competing_calendar_lab as audit,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC,
)

OBSERVED = LAST_REQUIRED_CLOSE_UTC + timedelta(minutes=15)
SOURCE_HASH = "a" * 64


def claim(root="US_CPI_OTHER", minute_offset=0, *, currency="USD",
          category="MACRO_DATA", impact="HIGH"):
    return Event(root, EVENT_UTC + timedelta(minutes=minute_offset),
                 currency, category, impact)


def sample(*events):
    return Snapshot(
        captured_at_utc=EVENT_UTC-timedelta(days=1),
        covered_from_utc=BASELINE_OPEN_UTC-timedelta(hours=1),
        covered_until_utc=LAST_REQUIRED_CLOSE_UTC+timedelta(hours=1),
        source_sha256_claim=SOURCE_HASH,
        claims_complete_for_covered_period=True,
        events=tuple(events),
    )


class PpiCompetingCalendarTests(unittest.TestCase):
    def run_lab(self, value=None, *, now=OBSERVED):
        result = audit(calendar=value, as_of_utc=now)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["causal_isolation_of_ppi_verified"])
        self.assertFalse(result["clean_event_window_independently_verified"])
        self.assertFalse(result["calendar_source_and_actual_event_times_authenticated"])
        self.assertFalse(result["no_competing_events_proven"])
        self.assertTrue(result["missing_or_uncertain_calendar_requires_review"])
        self.assertIsNone(result["price_or_macro_bias"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual(result["economic_event_count"], 1)
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))
        return result

    def test_without_snapshot_is_unknown_not_clean(self):
        r = self.run_lab()
        self.assertEqual(r["state"], "LAB_PPI_COMPETING_CALENDAR_UNKNOWN_REVIEW_REQUIRED")
        self.assertIsNone(r["candidate_competing_root_count_documentary"])
        self.assertFalse(r["calendar_period_claims_complete_unattested"])

    def test_empty_complete_claim_is_still_not_proven_clean(self):
        r = self.run_lab(sample())
        self.assertEqual(r["state"], "LAB_PPI_EMPTY_COMPETING_LIST_UNATTESTED_REVIEW_REQUIRED")
        self.assertEqual(r["candidate_competing_root_count_documentary"], 0)
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"],
                         {"M15": [], "H1": [], "H4": []})
        self.assertTrue(r["calendar_period_claims_complete_unattested"])
        self.assertFalse(r["no_competing_events_proven"])

    def test_other_usd_release_same_minute_confounds_all_windows(self):
        r = self.run_lab(sample(claim("US_OTHER_1", 0), claim("US_PPI_OCT2026", 0)))
        self.assertEqual(r["candidate_competing_root_count_documentary"], 1)
        self.assertEqual(r["state"], "LAB_PPI_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED")
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"],
                         {"M15": ["US_OTHER_1"], "H1": ["US_OTHER_1"],
                          "H4": ["US_OTHER_1"]})

    def test_10_minute_event_affects_m15_h1_h4_not_the_baseline(self):
        r = self.run_lab(sample(claim("FED_SPEECH_1", 10, category="POLICY_SPEECH")))
        self.assertEqual(r["candidate_baseline_contamination_roots_documentary"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["M15"],
                         ["FED_SPEECH_1"])
        self.assertEqual(len(r["candidate_competing_events_detail"]), 1)

    def test_after_15_minute_boundary_only_h1_h4_not_m15(self):
        r = self.run_lab(sample(claim("BANK_UPDATE_1", 15, currency="EUR",
                                      category="CENTRAL_BANK")))
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["M15"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["H1"],
                         ["BANK_UPDATE_1"])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["H4"],
                         ["BANK_UPDATE_1"])

    def test_after_hour_boundary_is_only_h4(self):
        r = self.run_lab(sample(claim("GLOBAL_HEADLINE_1", 60,
                                      currency="GLOBAL", category="GEOPOLITICAL")))
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["M15"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["H1"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["H4"],
                         ["GLOBAL_HEADLINE_1"])

    def test_baseline_event_is_distinguished_from_post_release(self):
        r = self.run_lab(sample(claim("RISK_NOTE_1", -10, currency="JPY",
                                      category="OTHER_MARKET_CATALYST")))
        self.assertEqual(r["candidate_baseline_contamination_roots_documentary"],
                         ["RISK_NOTE_1"])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"],
                         {"M15": [], "H1": [], "H4": []})

    def test_duplicate_metric_under_one_root_is_not_two_events(self):
        event = claim("US_JOBS_1", 0)
        r = self.run_lab(sample(event, event, claim("US_PPI_OCT2026", 0)))
        self.assertEqual(r["candidate_competing_root_count_documentary"], 1)
        self.assertEqual(r["economic_event_count"], 1)
        self.assertTrue(r["candidate_competing_events_detail"][0]
                        ["occurrence_and_market_relevance_not_confirmed"])

    def test_same_root_with_conflicting_metadata_blocks(self):
        r = self.run_lab(sample(claim("US_JOBS_1", 0),
                                claim("US_JOBS_1", 1)))
        self.assertEqual(r["reason"], "SAME_ROOT_WITH_CONFLICTING_TIME_OR_METADATA")
        self.assertIsNone(r["candidate_competing_roots_by_reaction_window"])

    def test_ppi_root_wrong_time_or_currency_cannot_be_hidden(self):
        for item in (claim("US_PPI_OCT2026", 1),
                     claim("US_PPI_OCT2026", 0, currency="EUR")):
            with self.subTest(item=item):
                r = self.run_lab(sample(item))
                self.assertEqual(r["reason"], "PPI_ROOT_RELABELED_OR_WRONG_RELEASE_TIME")

    def test_missing_completeness_or_broken_coverage_blocks_not_empty(self):
        base = sample()
        for changed in (
            replace(base, covered_from_utc=EVENT_UTC),
            replace(base, covered_until_utc=EVENT_UTC + timedelta(hours=1)),
            replace(base, source_sha256_claim="not-a-hash"),
        ):
            with self.subTest(changed=changed):
                r = self.run_lab(changed)
                self.assertEqual(r["reason"],
                                 "PRE_EVENT_CALENDAR_CAPTURE_COVERAGE_OR_HASH_INVALID")
                self.assertIsNone(r["candidate_competing_root_count_documentary"])

    def test_partial_official_source_set_is_not_a_full_market_calendar(self):
        # These UTC schedule times were checked against pre-event official
        # EIA, Fed Board and SF Fed pages. This is not market impact proof.
        ev = (
            claim("US_EIA_NATGAS_STORAGE_20261113", 120,
                  currency="USD", category="MACRO_DATA", impact="UNASSESSED"),
            claim("US_FED_BOWMAN_DISCUSSION_20261113", 140,
                  currency="USD", category="POLICY_SPEECH", impact="UNASSESSED"),
            claim("US_SF_FED_DALY_UNLV_20261113", 210,
                  currency="USD", category="POLICY_SPEECH", impact="UNASSESSED"),
        )
        calendar = replace(sample(*ev), claims_complete_for_covered_period=False)
        r = self.run_lab(calendar)
        self.assertEqual(r["state"],
                         "LAB_PPI_PARTIAL_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED")
        self.assertEqual(r["candidate_competing_root_count_documentary"], 3)
        self.assertFalse(r["calendar_period_claims_complete_unattested"])
        self.assertEqual(r["candidate_baseline_contamination_roots_documentary"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["M15"], [])
        self.assertEqual(r["candidate_competing_roots_by_reaction_window"]["H1"], [])
        self.assertEqual(len(r["candidate_competing_roots_by_reaction_window"]["H4"]), 3)
        self.assertFalse(r["causal_isolation_of_ppi_verified"])

    def test_empty_partial_calendar_not_a_no_news_claim(self):
        r = self.run_lab(replace(
            sample(), claims_complete_for_covered_period=False))
        self.assertEqual(r["state"],
                         "LAB_PPI_PARTIAL_COMPETING_LIST_UNATTESTED_REVIEW_REQUIRED")
        self.assertFalse(r["calendar_period_claims_complete_unattested"])
        self.assertEqual(r["candidate_competing_root_count_documentary"], 0)
        self.assertFalse(r["no_competing_events_proven"])

    def test_nonboolean_completeness_claim_is_rejected(self):
        for wrong in (None, 1, "true"):
            with self.subTest(wrong=wrong):
                r = self.run_lab(replace(
                    sample(), claims_complete_for_covered_period=wrong))
                self.assertEqual(r["reason"],
                                 "PRE_EVENT_CALENDAR_CAPTURE_COVERAGE_OR_HASH_INVALID")

    def test_realistic_capture_and_inspection_microseconds_are_allowed(self):
        base = sample(claim("US_EIA_NATGAS_STORAGE_20261113", 120))
        partial = replace(
            base, claims_complete_for_covered_period=False,
            captured_at_utc=base.captured_at_utc.replace(microsecond=488940))
        r = self.run_lab(
            partial, now=OBSERVED.replace(microsecond=789123))
        self.assertEqual(
            r["state"], "LAB_PPI_PARTIAL_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED")
        self.assertEqual(r["candidate_competing_root_count_documentary"], 1)
        self.assertFalse(r["no_competing_events_proven"])

    def test_subsecond_scheduled_release_still_rejected(self):
        bad = replace(
            claim("US_EIA_NATGAS_STORAGE_20261113", 120),
            scheduled_at_utc=EVENT_UTC.replace(microsecond=1))
        r = self.run_lab(sample(bad))
        self.assertEqual(r["reason"], "INVALID_EVENT_ID_CURRENCY_CATEGORY_OR_TIME")

    def test_subsecond_coverage_boundary_still_rejected(self):
        x = replace(
            sample(), covered_from_utc=BASELINE_OPEN_UTC.replace(microsecond=1))
        self.assertEqual(
            self.run_lab(x)["reason"],
            "PRE_EVENT_CALENDAR_CAPTURE_COVERAGE_OR_HASH_INVALID")

    def test_post_release_calendar_cannot_be_recast_as_pre_event(self):
        for changed in (
            replace(sample(), captured_at_utc=EVENT_UTC),
            replace(sample(), captured_at_utc=EVENT_UTC+timedelta(seconds=1)),
        ):
            with self.subTest(stamp=changed.captured_at_utc):
                self.assertEqual(self.run_lab(changed)["state"],
                                 "LAB_PPI_COMPETING_CALENDAR_BLOCKED")

    def test_bad_event_time_currency_type_category_and_outside_span_block(self):
        for event in (
            claim(currency="BTC"),
            claim(category="INVALID"),
            claim(impact="EXTREME"),
            claim(root="bad name"),
            claim(minute_offset=300),
            replace(claim(), scheduled_at_utc=EVENT_UTC.replace(tzinfo=None)),
        ):
            with self.subTest(event=event):
                r = self.run_lab(sample(event))
                self.assertEqual(r["state"], "LAB_PPI_COMPETING_CALENDAR_BLOCKED")

    def test_naive_or_wrong_inspection_clock_and_wrong_type_rejected(self):
        for now in (None, "2026-11-11", OBSERVED.replace(tzinfo=None)):
            self.assertEqual(self.run_lab(sample(), now=now)["reason"],
                             "INVALID_INSPECTION_CLOCK")
        self.assertEqual(self.run_lab({"events": []})["reason"],
                         "INVALID_CALENDAR_CLAIM_TYPE")

    def test_record_cannot_make_any_directional_market_claim(self):
        r = self.run_lab(sample(claim("ANOTHER_EVENT", 5)))
        self.assertFalse(r["causal_isolation_of_ppi_verified"])
        self.assertFalse(r["clean_event_window_independently_verified"])
        self.assertFalse(r["no_competing_events_proven"])
        self.assertIsNone(r["price_or_macro_bias"])


if __name__ == "__main__":
    unittest.main()
