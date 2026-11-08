"""Synthetic, strictly research-only checks for prior-value news nowcasts."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from atlasquant_news_previous_context_lab import (
    ConsensusEvidence,
    PastOutcome,
    PreReleaseSnapshot,
    consensus_readiness,
    estimate_with_previous_context,
    validate_snapshot,
    walk_forward_previous_context,
)

UTC = timezone.utc


def month_pair(index: int) -> tuple[str, str, datetime, datetime, datetime, datetime]:
    year = 2020 + index // 12
    month = index % 12 + 1
    previous_month = 12 if month == 1 else month - 1
    previous_year = year - 1 if month == 1 else year
    release_year = year + 1 if month == 12 else year
    release_month = 1 if month == 12 else month + 1
    previous_published = datetime(year, month, 10, 12, tzinfo=UTC)
    previous_captured = previous_published + timedelta(days=1)
    scheduled = datetime(release_year, release_month, 10, 12, tzinfo=UTC)
    captured = scheduled - timedelta(days=5)
    return (
        f"{year}-{month:02d}", f"{previous_year}-{previous_month:02d}",
        scheduled, captured, previous_published, previous_captured,
    )


def snapshot(index: int, *, gap: float = 20.0) -> PreReleaseSnapshot:
    target, prior, scheduled, captured, published, prior_captured = month_pair(index)
    consensus = 100.0 + gap
    evidence = ConsensusEvidence(
        country="US", indicator="CPI", metric="YOY", unit="PCT",
        target_period=target, value=consensus,
        source_kind="EXACT_EVENT_ANALYST_POLL",
        source_url="https://poll.example/synthetic-consensus",
        published_at=captured - timedelta(days=2),
        captured_at=captured - timedelta(days=1),
        source_sha256="c" * 64, original_verified=True,
        public_availability_independently_witnessed=True,
    )
    return PreReleaseSnapshot(
        country="US", indicator="CPI", metric="YOY", unit="PCT",
        target_period=target, previous_period=prior,
        scheduled_at=scheduled, captured_at=captured,
        consensus=consensus, previous=100.0,
        previous_published_at=published, previous_captured_at=prior_captured,
        previous_source_url="https://official.example/synthetic-cpi-vintage",
        previous_sha256="a" * 64, previous_original_verified=True,
        signal_score=0.0, tolerance=0.05, consensus_evidence=evidence,
    )


def synthetic_history(length: int = 50) -> list[PastOutcome]:
    rows = []
    for index in range(length):
        gap = 20.0 if index % 2 else 0.0
        prior = snapshot(index, gap=gap)
        surprise = 10.0 if gap == 20.0 else -10.0
        rows.append(PastOutcome(
            snapshot=prior, actual=prior.consensus + surprise,
            actual_available_at=prior.scheduled_at + timedelta(minutes=1),
            actual_sha256="b" * 64, actual_original_verified=True,
        ))
    return rows


def change_identity(row: PastOutcome, **changes) -> PastOutcome:
    observation = replace(row.snapshot, **changes)
    evidence = replace(observation.consensus_evidence, **{
        key: value for key, value in changes.items()
        if key in ("country", "indicator", "metric", "unit", "target_period")
    })
    return replace(row, snapshot=replace(observation, consensus_evidence=evidence))


class PreviousContextLabTests(unittest.TestCase):
    def test_prior_gap_changes_analog_selection_in_synthetic_history(self):
        history = synthetic_history()
        up = estimate_with_previous_context(
            snapshot(60, gap=20), history, gap_scale=20,
            min_history=30, min_analogs=10,
        )
        down = estimate_with_previous_context(
            snapshot(60, gap=0), history, gap_scale=20,
            min_history=30, min_analogs=10,
        )
        self.assertEqual(up["state"], "RESEARCH_ESTIMATE")
        self.assertEqual(up["estimate"], 130.0)
        self.assertEqual(down["estimate"], 90.0)
        self.assertEqual(up["top_class"], "ABOVE")
        self.assertEqual(down["top_class"], "BELOW")
        self.assertTrue(up["previous_feature_used"])
        self.assertAlmostEqual(sum(up["probabilities"].values()), 1)

    def test_previous_without_authenticated_original_remains_waiting(self):
        target = replace(snapshot(60), previous_original_verified=False, previous_sha256="")
        result = estimate_with_previous_context(target, synthetic_history(), gap_scale=20)
        self.assertEqual(result["state"], "WAIT_PREVIOUS_ORIGINAL")
        self.assertIsNone(result["estimate"])
        self.assertIsNone(result["probabilities"])

    def test_unverified_consensus_candidate_cannot_produce_probabilities(self):
        target = replace(snapshot(60), consensus_evidence=None)
        result = estimate_with_previous_context(target, synthetic_history(), gap_scale=20)
        self.assertEqual(result["state"], "WAIT_EVENT_CONSENSUS_PIT")
        self.assertIsNone(result["consensus"])
        self.assertEqual(result["consensus_candidate_documentary"], 120.0)
        self.assertIsNone(result["estimate"])

    def test_model_nowcast_is_not_exact_market_event_consensus(self):
        target = snapshot(60)
        model = replace(target.consensus_evidence, source_kind="MODEL_NOWCAST")
        target = replace(target, consensus_evidence=model)
        self.assertEqual(consensus_readiness(target), "WAIT_EXACT_EVENT_ANALYST_POLL")
        result = estimate_with_previous_context(target, synthetic_history(), gap_scale=20)
        self.assertEqual(result["state"], "WAIT_EXACT_EVENT_ANALYST_POLL")

    def test_original_poll_bytes_missing_waits_without_inventing_hash(self):
        target = snapshot(60)
        missing = replace(target.consensus_evidence,
                          original_verified=False, source_sha256="")
        result = estimate_with_previous_context(
            replace(target, consensus_evidence=missing), synthetic_history(), gap_scale=20,
        )
        self.assertEqual(result["state"], "WAIT_CONSENSUS_ORIGINAL")

    def test_poll_without_independent_capture_witness_stays_blocked(self):
        target = snapshot(60)
        unobserved = replace(target.consensus_evidence,
                             public_availability_independently_witnessed=False)
        result = estimate_with_previous_context(
            replace(target, consensus_evidence=unobserved), synthetic_history(), gap_scale=20,
        )
        self.assertEqual(result["state"], "WAIT_CONSENSUS_ASOF_WITNESS")

    def test_consensus_capture_after_forecast_is_rejected(self):
        target = snapshot(60)
        late = replace(target.consensus_evidence, captured_at=target.captured_at + timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "pré-evento"):
            validate_snapshot(replace(target, consensus_evidence=late))

    def test_consensus_metric_or_value_mismatch_is_rejected(self):
        target = snapshot(60)
        for wrong in (replace(target.consensus_evidence, metric="MOM"),
                      replace(target.consensus_evidence, value=9.0)):
            with self.assertRaisesRegex(ValueError, "consensus_evidence"):
                validate_snapshot(replace(target, consensus_evidence=wrong))

    def test_historical_poll_without_pit_witness_is_excluded(self):
        history = []
        for row in synthetic_history():
            evidence = replace(row.snapshot.consensus_evidence,
                               public_availability_independently_witnessed=False)
            history.append(replace(row, snapshot=replace(row.snapshot, consensus_evidence=evidence)))
        result = estimate_with_previous_context(snapshot(60), history, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")

    def test_historical_outcome_without_archive_hash_is_excluded(self):
        history = [replace(row, actual_original_verified=False, actual_sha256="")
                   for row in synthetic_history()]
        result = estimate_with_previous_context(snapshot(60), history, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")

    def test_claimed_verification_without_original_hash_is_rejected(self):
        target = replace(snapshot(60), previous_sha256="")
        with self.assertRaisesRegex(ValueError, "previous_sha256"):
            validate_snapshot(target)

    def test_string_attestation_cannot_pass_as_verified_boolean(self):
        target = replace(snapshot(60), previous_original_verified="true")
        with self.assertRaisesRegex(ValueError, "booleano"):
            validate_snapshot(target)

    def test_previous_capture_after_forecast_is_rejected(self):
        target = snapshot(60)
        future = replace(target, previous_captured_at=target.captured_at + timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "valor anterior"):
            validate_snapshot(future)

    def test_previous_publication_after_previous_capture_is_rejected(self):
        target = snapshot(60)
        revised = replace(target, previous_published_at=target.previous_captured_at + timedelta(minutes=1))
        with self.assertRaisesRegex(ValueError, "valor anterior"):
            validate_snapshot(revised)

    def test_previous_period_must_really_be_previous_calendar_month(self):
        wrong = replace(snapshot(60), previous_period="2025-01")
        with self.assertRaisesRegex(ValueError, "previous_period"):
            validate_snapshot(wrong)

    def test_no_quarterly_or_arbitrary_period_claim(self):
        wrong = replace(snapshot(60), target_period="2025-Q1", previous_period="2024-Q4")
        with self.assertRaisesRegex(ValueError, "YYYY-MM"):
            validate_snapshot(wrong)

    def test_foreign_country_or_metric_are_not_training_analogs(self):
        foreign = [change_identity(row, country="CA", metric="MOM") for row in synthetic_history()]
        result = estimate_with_previous_context(snapshot(60), foreign, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")

    def test_future_historical_actual_cannot_leak(self):
        rows = [
            replace(row, actual_available_at=snapshot(60).captured_at + timedelta(days=1))
            for row in synthetic_history()
        ]
        result = estimate_with_previous_context(snapshot(60), rows, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")
        self.assertEqual(result["history_samples"], 0)

    def test_unverified_actual_cannot_be_in_training(self):
        history = [replace(row, actual_original_verified=False) for row in synthetic_history()]
        result = estimate_with_previous_context(snapshot(60), history, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")

    def test_hash_tampering_is_rejected(self):
        bad = replace(snapshot(60), previous_sha256="not-a-hash")
        with self.assertRaisesRegex(ValueError, "previous_sha256"):
            validate_snapshot(bad)

    def test_naive_forecast_clock_is_rejected(self):
        target = snapshot(60)
        with self.assertRaisesRegex(ValueError, "fuso"):
            validate_snapshot(replace(target, captured_at=target.captured_at.replace(tzinfo=None)))

    def test_duplicate_month_cannot_inflate_training_count(self):
        history = synthetic_history()
        duplicate = [history[0], *history]
        result = estimate_with_previous_context(snapshot(60), duplicate, gap_scale=20)
        self.assertEqual(result["state"], "WAIT_DUPLICATE_HISTORY")

    def test_wrong_units_and_negative_scale_fail_closed(self):
        wrong_units = [change_identity(row, unit="THOUSANDS") for row in synthetic_history()]
        result = estimate_with_previous_context(snapshot(60), wrong_units, gap_scale=20)
        self.assertEqual(result["state"], "INSUFFICIENT_VERIFIED_HISTORY")
        with self.assertRaisesRegex(ValueError, "parâmetros"):
            estimate_with_previous_context(snapshot(60), synthetic_history(), gap_scale=-1)

    def test_probabilities_are_never_market_or_profit_claims(self):
        result = estimate_with_previous_context(snapshot(60), synthetic_history(), gap_scale=20)
        self.assertIsNone(result["pair_bias"])
        self.assertIsNone(result["profit_probability"])
        self.assertIsNone(result["confidence_0_to_10"])
        self.assertFalse(result["calibrated"])
        self.assertFalse(result["automatic_execution"])
        self.assertTrue(result["research_only"])

    def test_walk_forward_compares_consensus_and_previous_without_lookahead(self):
        result = walk_forward_previous_context(
            synthetic_history(60), gap_scale=20, min_history=20, min_analogs=8,
        )
        self.assertGreater(result["forecast_samples"], 0)
        self.assertGreater(result["skipped_samples"], 0)
        self.assertIsNotNone(result["mae_consensus"])
        self.assertIsNotNone(result["mae_previous"])
        self.assertIsNotNone(result["mae_estimate"])
        self.assertFalse(result["historical_advantage_proven"])
        self.assertFalse(result["lookahead_used"])
        self.assertTrue(all(not row["lookahead_used"] for row in result["forecasts"]))


if __name__ == "__main__":
    unittest.main()
