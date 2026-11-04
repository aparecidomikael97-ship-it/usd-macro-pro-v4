"""Synthetic-only EODHD timestamp hypothesis audit; no source/API requests."""
import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_trader_eodhd_clock_audit_lab import audit_timezone_hypotheses, SCHEMA

NOW = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
HOSTS = ["www.bls.gov", "www.bea.gov", "www.ibge.gov.br"]


def sample(n, *, basis="UTC", host=None, checked=NOW, day=None):
    # Completely fictitious clocks, not actual release evidence.
    day = day or f"2026-10-0{n}"
    raw = day + " 12:30:00"
    target_hour = 12 if basis == "UTC" else (15 if basis == "BRT" else 18)
    return {
        "event_id": f"LAB-EVENT-{n}",
        "eodhd_raw_date": raw,
        "official_release_utc": f"{day}T{target_hour:02d}:30:00+00:00",
        "official_source_url": f"https://{host or HOSTS[(n-1)%3]}/schedule/example",
        "source_checked_at_utc": checked.isoformat(),
        "reference_type": "OFFICIAL_SCHEDULE",
    }


class ClockAuditLabTests(unittest.TestCase):
    def inspect(self, samples, *, at=NOW):
        return audit_timezone_hypotheses(samples, at=at)

    def test_no_data_can_never_attest_time(self):
        r = self.inspect([])
        self.assertEqual(r["state"], "INSUFFICIENT_INDEPENDENT_SAMPLES")
        self.assertEqual(r["provider_request_count"], 0)
        self.assertFalse(r["timezone_attested"])
        self.assertFalse(r["auto_config_allowed"])

    def test_three_independent_utc_matches_only_create_review_candidate(self):
        r = self.inspect([sample(1), sample(2), sample(3)])
        self.assertEqual(r["state"], "UTC_CANDIDATE_REVIEW")
        self.assertEqual(r["matched_count"], 3)
        self.assertEqual(r["source_hosts_count"], 3)
        self.assertEqual(r["distinct_reference_days"], 3)
        self.assertFalse(r["new_economic_release_confirmed"])
        self.assertFalse(r["timezone_attested"])

    def test_brt_matches_are_an_alternative_hypothesis_not_auto_truth(self):
        r = self.inspect([sample(i, basis="BRT") for i in (1, 2, 3)])
        self.assertEqual(r["state"], "BRT_CANDIDATE_REVIEW")
        self.assertFalse(r["auto_config_allowed"])

    def test_mixed_hypotheses_are_not_accepted(self):
        x = [sample(1), sample(2, basis="BRT"), sample(3)]
        self.assertEqual(self.inspect(x)["state"],
                         "INCONSISTENT_TIMEZONE_HYPOTHESES")

    def test_unmatched_source_time_rejects_entire_batch(self):
        x = [sample(1), sample(2, basis="OTHER"), sample(3)]
        self.assertEqual(self.inspect(x)["state"],
                         "REJECTED_OR_CONFLICTING_EVIDENCE")

    def test_source_host_spoof_and_http_are_rejected(self):
        fake = sample(2, host="bls.gov.evil.com")
        x = [sample(1), fake, sample(3)]
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")
        x[1] = {**sample(2), "official_source_url": "http://www.bls.gov/path"}
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")

    def test_stale_reference_and_future_audit_are_rejected(self):
        x = [sample(1), sample(2, checked=NOW - timedelta(days=9)), sample(3)]
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")
        x[1] = sample(2, checked=NOW + timedelta(hours=1))
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")

    def test_duplicate_event_id_rejected_not_counted_twice(self):
        x = [sample(1), sample(1), sample(3)]
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")

    def test_same_host_only_is_insufficient(self):
        x = [sample(i, host="www.bls.gov") for i in (1, 2, 3)]
        self.assertEqual(self.inspect(x)["state"], "INSUFFICIENT_INDEPENDENT_SAMPLES")

    def test_same_official_day_only_is_insufficient(self):
        x = [sample(i, day="2026-10-01") for i in (1, 2, 3)]
        self.assertEqual(self.inspect(x)["state"], "INSUFFICIENT_INDEPENDENT_SAMPLES")

    def test_bad_naive_format_and_no_timezone_in_official_reference(self):
        x = [sample(1), sample(2), sample(3)]
        x[0]["eodhd_raw_date"] = "2026-10-01T12:30:00Z"
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")
        x = [sample(1), sample(2), sample(3)]
        x[0]["official_release_utc"] = "2026-10-01T12:30:00"
        self.assertEqual(self.inspect(x)["state"], "REJECTED_OR_CONFLICTING_EVIDENCE")

    def test_invalid_audit_instant_and_threshold(self):
        with self.assertRaises(ValueError):
            self.inspect([sample(1)], at=datetime(2026, 11, 2, 15))
        with self.assertRaises(ValueError):
            audit_timezone_hypotheses([], at=NOW, minimum=2)

    def test_schema_and_all_execution_guards_remain_off(self):
        r = self.inspect([sample(1), sample(2), sample(3)])
        self.assertEqual(r["schema"], SCHEMA)
        self.assertFalse(r["worker_enabled"])
        self.assertFalse(r["scheduler_enabled"])
        self.assertFalse(r["auto_config_allowed"])


if __name__ == "__main__":
    unittest.main()
