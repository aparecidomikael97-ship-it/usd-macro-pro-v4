import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_data_freshness import (
    CURRENT,
    INVALID,
    STALE,
    UNKNOWN,
    assess_freshness,
    summarize_freshness,
)


NOW = datetime(2026, 9, 28, 23, 45, tzinfo=timezone.utc)


class DataFreshnessTests(unittest.TestCase):
    def evidence(self, *, minutes=10, ttl=60, source="technical-cache", available_minutes=None):
        observed = NOW - timedelta(minutes=minutes)
        out = {
            "source": source,
            "observed_at": observed.isoformat(),
            "ttl_minutes": ttl,
        }
        if available_minutes is not None:
            out["available_at"] = (NOW - timedelta(minutes=available_minutes)).isoformat()
        return out

    def test_current_requires_source_timestamp_and_explicit_ttl(self):
        out = assess_freshness(self.evidence(minutes=10, ttl=60), evaluated_at=NOW)
        self.assertEqual(out["state"], CURRENT)
        self.assertTrue(out["current"])
        self.assertEqual(out["age_minutes"], 10.0)
        self.assertFalse(out["agreement_verified"])
        self.assertFalse(out["execution_authorized"])

    def test_missing_source_observed_at_or_ttl_is_unknown(self):
        cases = (
            {"observed_at": NOW.isoformat(), "ttl_minutes": 60},
            {"source": "A", "ttl_minutes": 60},
            {"source": "A", "observed_at": NOW.isoformat()},
            None,
        )
        for evidence in cases:
            with self.subTest(evidence=evidence):
                out = assess_freshness(evidence, evaluated_at=NOW)
                self.assertEqual(out["state"], UNKNOWN)
                self.assertFalse(out["current"])
                self.assertTrue(out["reasons"])

    def test_invalid_ttl_rejects_bool_zero_negative_nonfinite_and_text(self):
        for ttl in (True, False, 0, -1, float("nan"), float("inf"), "bad"):
            with self.subTest(ttl=ttl):
                out = assess_freshness(self.evidence(ttl=ttl), evaluated_at=NOW)
                self.assertEqual(out["state"], INVALID)
                self.assertIn("TTL_INVALID", out["reasons"])

    def test_future_observed_timestamp_is_invalid(self):
        evidence = self.evidence()
        evidence["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
        out = assess_freshness(evidence, evaluated_at=NOW)
        self.assertEqual(out["state"], INVALID)
        self.assertIn("OBSERVED_AT_IN_FUTURE", out["reasons"])

    def test_unaware_or_malformed_timestamp_is_invalid(self):
        for value in ("2026-09-28T23:00:00", "not-a-date", 123):
            with self.subTest(value=value):
                evidence = self.evidence()
                evidence["observed_at"] = value
                out = assess_freshness(evidence, evaluated_at=NOW)
                self.assertEqual(out["state"], INVALID)
                self.assertIn("OBSERVED_AT_INVALID", out["reasons"])

    def test_exact_ttl_boundary_is_stale(self):
        out = assess_freshness(self.evidence(minutes=60, ttl=60), evaluated_at=NOW)
        self.assertEqual(out["state"], STALE)
        self.assertFalse(out["current"])
        self.assertIn("TTL_EXPIRED", out["reasons"])

    def test_available_at_is_reference_clock_when_present(self):
        evidence = self.evidence(minutes=20, ttl=15, available_minutes=5)
        out = assess_freshness(evidence, evaluated_at=NOW)
        self.assertEqual(out["state"], CURRENT)
        self.assertEqual(out["age_minutes"], 5.0)
        self.assertIsNotNone(out["available_at"])

    def test_available_at_before_observation_or_in_future_is_invalid(self):
        before = self.evidence(minutes=10, ttl=60)
        before["available_at"] = (NOW - timedelta(minutes=20)).isoformat()
        future = self.evidence(minutes=10, ttl=60)
        future["available_at"] = (NOW + timedelta(seconds=1)).isoformat()
        for evidence, code in (
            (before, "AVAILABLE_BEFORE_OBSERVED"),
            (future, "AVAILABLE_AT_IN_FUTURE"),
        ):
            with self.subTest(code=code):
                out = assess_freshness(evidence, evaluated_at=NOW)
                self.assertEqual(out["state"], INVALID)
                self.assertIn(code, out["reasons"])

    def test_invalid_evaluation_clock_fails_closed(self):
        out = assess_freshness(self.evidence(), evaluated_at="2026-09-28T23:45:00")
        self.assertEqual(out["state"], INVALID)
        self.assertIn("EVALUATED_AT_INVALID", out["reasons"])

    def test_summary_mixed_current_and_stale_is_stale(self):
        reports = [
            assess_freshness(self.evidence(minutes=5), evaluated_at=NOW),
            assess_freshness(self.evidence(minutes=90), evaluated_at=NOW),
        ]
        out = summarize_freshness(reports)
        self.assertEqual(out["state"], STALE)
        self.assertEqual(out["current"], 1)
        self.assertEqual(out["stale"], 1)
        self.assertFalse(out["all_current"])
        self.assertFalse(out["execution_authorized"])

    def test_summary_unknown_and_invalid_fail_closed(self):
        unknown = assess_freshness({}, evaluated_at=NOW)
        invalid = assess_freshness({"source": "A", "observed_at": "bad", "ttl_minutes": 60}, evaluated_at=NOW)
        self.assertEqual(summarize_freshness([unknown])["state"], UNKNOWN)
        self.assertEqual(summarize_freshness([unknown, invalid])["state"], INVALID)

    def test_empty_summary_is_unknown(self):
        out = summarize_freshness([])
        self.assertEqual(out["state"], UNKNOWN)
        self.assertIn("NO_FRESHNESS_EVIDENCE", out["reasons"])


if __name__ == "__main__":
    unittest.main()
