"""Synthetic offline tests: freeze-before-release, score-after, never trade."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_event_forecast_lock_lab import (
    ActualClaim, ForecastDraft, ForecastLock,
    freeze_pre_event_forecast_lab as freeze,
    score_locked_forecast_lab as score,
)

UTC = timezone.utc
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=UTC)
CUTOFF = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
AFTER = RELEASE + timedelta(hours=1)


def draft() -> ForecastDraft:
    return ForecastDraft(
        event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
        target_period="2026-10", unit="PERCENT_MOM_SA",
        scheduled_release_at=RELEASE, forecast_captured_at=CUTOFF,
        previous_value="0.6", previous_available_at=datetime(2026, 10, 14, 13, 0, tzinfo=UTC),
        consensus_value="0.3", consensus_available_at=CUTOFF - timedelta(hours=1),
        model_estimate="0.35", model_version="lab-v1.0",
        previous_source_sha256_claim="a" * 64,
        consensus_source_sha256_claim="b" * 64,
    )


def actual() -> ActualClaim:
    return ActualClaim(
        event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
        target_period="2026-10", unit="PERCENT_MOM_SA", value="0.4",
        first_published_at=RELEASE, captured_at=RELEASE + timedelta(minutes=1),
        source_sha256_claim="c" * 64,
    )


def lock() -> ForecastLock:
    return freeze(draft(), as_of_utc=CUTOFF)["lock"]


class ForecastLockTests(unittest.TestCase):
    def assert_no_go(self, result):
        self.assertIsNone(result["calibrated_direction_probability"])
        self.assertIsNone(result["validated_accuracy"])
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["fx_bias"])
        self.assertIsNone(result["index_bias"])
        self.assertFalse(result["publishable"])
        self.assertFalse(result["live_alert_allowed"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["worker_enabled"])
        self.assertFalse(result["scheduler_enabled"])
        self.assertFalse(result["forecast_origin_independently_witnessed"])
        self.assertFalse(result["source_originals_and_clock_independently_verified"])
        self.assertFalse(result["outcome_extracted_from_official_original_verified"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(result["research_only"])

    def test_pre_event_freeze_canonical_sha_and_no_go(self):
        r = freeze(draft(), as_of_utc=CUTOFF)
        self.assertEqual(r["state"], "LAB_PRE_EVENT_FORECAST_LOCKED_DOCUMENTARY_ONLY")
        self.assertIsInstance(r["lock"], ForecastLock)
        self.assertEqual(r["forecast_sha256"], sha256(
            r["lock"].canonical_payload_json.encode("ascii")).hexdigest())
        self.assertEqual(json.loads(r["lock"].canonical_payload_json)["model_estimate"], "0.35")
        self.assert_no_go(r)

    def test_repeat_freeze_deterministic_and_utc_normalization(self):
        self.assertEqual(freeze(draft(), as_of_utc=CUTOFF)["lock"], lock())
        different_zone = timezone(timedelta(hours=-4))
        d = replace(draft(), forecast_captured_at=CUTOFF.astimezone(different_zone))
        self.assertEqual(freeze(d, as_of_utc=CUTOFF)["lock"], lock())

    def test_post_event_score_is_descriptive_not_verified_accuracy(self):
        r = score(lock(), actual(), as_of_utc=AFTER)
        self.assertEqual(r["state"], "LAB_POST_EVENT_DESCRIPTIVE_SCORE_UNATTESTED")
        self.assertEqual(r["model_abs_error_documentary"], "0.05")
        self.assertEqual(r["consensus_abs_error_documentary"], "0.1")
        self.assertEqual(r["previous_abs_error_documentary"], "0.2")
        self.assertEqual(r["actual_minus_consensus_documentary"], "0.1")
        self.assertTrue(r["model_better_than_consensus_documentary"])
        self.assertEqual(len(r["scored_claim_sha256"]), 64)
        self.assert_no_go(r)

    def test_no_model_only_baselines_scored(self):
        d = replace(draft(), model_estimate=None, model_version=None)
        frozen = freeze(d, as_of_utc=CUTOFF)
        self.assertEqual(frozen["state"], "LAB_PRE_EVENT_FORECAST_LOCKED_DOCUMENTARY_ONLY")
        r = score(frozen["lock"], actual(), as_of_utc=AFTER)
        self.assertIsNone(r["model_abs_error_documentary"])
        self.assertIsNone(r["model_better_than_consensus_documentary"])
        self.assertEqual(r["consensus_abs_error_documentary"], "0.1")
        self.assert_no_go(r)

    def test_cannot_freeze_at_or_after_release(self):
        for instant in (RELEASE, AFTER):
            with self.subTest(instant=instant):
                self.assertEqual(freeze(replace(draft(), forecast_captured_at=instant),
                                        as_of_utc=instant)["state"], "LAB_FORECAST_BLOCKED")

    def test_cannot_use_future_previous_or_consensus(self):
        for change in (
            {"previous_available_at": CUTOFF + timedelta(seconds=1)},
            {"consensus_available_at": CUTOFF + timedelta(seconds=1)},
            {"forecast_captured_at": CUTOFF + timedelta(seconds=1)},
        ):
            with self.subTest(change=change):
                self.assertEqual(freeze(replace(draft(), **change),
                                        as_of_utc=CUTOFF)["state"], "LAB_FORECAST_BLOCKED")

    def test_reject_incompatible_metric_and_period(self):
        for change in (
            {"metric": "CPI_YOY"}, {"unit": "PERCENT_YOY_NSA"},
            {"metric": "NOT_A_METRIC"}, {"target_period": "2026-13"},
            {"target_period": "2026-Q4"}, {"currency": "EURUSD"},
            {"event_id": "bad event"},
        ):
            with self.subTest(change=change):
                self.assertEqual(freeze(replace(draft(), **change),
                                        as_of_utc=CUTOFF)["state"], "LAB_FORECAST_BLOCKED")

    def test_non_finite_and_bad_model_versions_rejected(self):
        for change in (
            {"previous_value": "NaN"}, {"consensus_value": "Infinity"},
            {"model_estimate": "not-a-number"}, {"model_estimate": "1000000001"},
            {"model_version": None}, {"model_version": "../../bad"},
            {"model_estimate": None},
        ):
            with self.subTest(change=change):
                self.assertEqual(freeze(replace(draft(), **change),
                                        as_of_utc=CUTOFF)["state"], "LAB_FORECAST_BLOCKED")

    def test_hash_claims_are_format_only(self):
        r = freeze(replace(draft(), previous_source_sha256_claim=None,
                           consensus_source_sha256_claim=None), as_of_utc=CUTOFF)
        self.assertEqual(r["state"], "LAB_PRE_EVENT_FORECAST_LOCKED_DOCUMENTARY_ONLY")
        self.assertFalse(r["source_originals_and_clock_independently_verified"])
        for change in ({"previous_source_sha256_claim": "A" * 64},
                       {"consensus_source_sha256_claim": "short"}):
            self.assertEqual(freeze(replace(draft(), **change),
                                    as_of_utc=CUTOFF)["state"], "LAB_FORECAST_BLOCKED")

    def test_requires_timezone_and_whole_seconds(self):
        for bad_clock in (CUTOFF.replace(tzinfo=None),
                          CUTOFF + timedelta(microseconds=1)):
            self.assertEqual(freeze(replace(draft(), forecast_captured_at=bad_clock),
                                    as_of_utc=CUTOFF)["state"], "LAB_FORECAST_BLOCKED")

    def test_tampered_lock_payload_or_digest_rejected(self):
        good = lock()
        for changed in (replace(good, canonical_payload_json=good.canonical_payload_json + " "),
                        replace(good, payload_sha256="d" * 64),
                        replace(good, payload_sha256="BAD")):
            with self.subTest(changed=changed):
                r = score(changed, actual(), as_of_utc=AFTER)
                self.assertEqual(r["state"], "LAB_FORECAST_BLOCKED")
                self.assert_no_go(r)

    def test_recomputed_self_hash_not_an_external_pre_event_witness(self):
        # A matching hash proves only self-consistency, not an independently
        # registered pre-release timestamp or the real source's publication.
        raw = json.loads(lock().canonical_payload_json)
        raw["model_estimate"] = "0.40"
        spoof = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        forged = ForecastLock(spoof, sha256(spoof.encode("ascii")).hexdigest())
        r = score(forged, actual(), as_of_utc=AFTER)
        self.assertEqual(r["state"], "LAB_POST_EVENT_DESCRIPTIVE_SCORE_UNATTESTED")
        self.assertFalse(r["forecast_origin_independently_witnessed"])
        self.assertFalse(r["model_hyperparameters_frozen_independently_verified"])
        self.assertIsNone(r["validated_accuracy"])

    def test_actual_cannot_exist_before_publication_or_after_asof(self):
        for change in (
            {"first_published_at": RELEASE - timedelta(seconds=1)},
            {"captured_at": RELEASE - timedelta(seconds=1)},
            {"captured_at": AFTER + timedelta(seconds=1)},
            {"first_published_at": AFTER + timedelta(minutes=1)},
        ):
            with self.subTest(change=change):
                r = score(lock(), replace(actual(), **change), as_of_utc=AFTER)
                self.assertEqual(r["state"], "LAB_FORECAST_BLOCKED")
                self.assert_no_go(r)

    def test_cannot_score_before_release(self):
        r = score(lock(), actual(), as_of_utc=CUTOFF)
        self.assertEqual(r["state"], "LAB_FORECAST_BLOCKED")
        self.assert_no_go(r)

    def test_post_event_mismatched_identity_metric_unit_period_rejected(self):
        for change in (
            {"event_id": "US_CPI_2026_09"}, {"currency": "EUR"},
            {"metric": "CPI_YOY"}, {"unit": "PERCENT_YOY_NSA"},
            {"target_period": "2026-09"},
        ):
            with self.subTest(change=change):
                self.assertEqual(score(lock(), replace(actual(), **change),
                                       as_of_utc=AFTER)["state"], "LAB_FORECAST_BLOCKED")

    def test_post_event_actual_value_and_hash_guards(self):
        for change in ({"value": "NaN"}, {"value": "12345678901"},
                       {"source_sha256_claim": "F" * 64}):
            with self.subTest(change=change):
                self.assertEqual(score(lock(), replace(actual(), **change),
                                       as_of_utc=AFTER)["state"], "LAB_FORECAST_BLOCKED")

    def test_scoring_is_idempotent_and_claim_hash_changes_with_actual(self):
        one = score(lock(), actual(), as_of_utc=AFTER)
        self.assertEqual(one, score(lock(), actual(), as_of_utc=AFTER))
        two = score(lock(), replace(actual(), value="0.5"), as_of_utc=AFTER)
        self.assertNotEqual(one["scored_claim_sha256"], two["scored_claim_sha256"])
        self.assertEqual(one["forecast_sha256"], two["forecast_sha256"])

    def test_arbitrary_inputs_cannot_turn_into_a_signal(self):
        for bad in (None, {}, "actual", 123):
            with self.subTest(bad=bad):
                self.assert_no_go(score(bad, actual(), as_of_utc=AFTER))
                self.assert_no_go(score(lock(), bad, as_of_utc=AFTER))


if __name__ == "__main__":
    unittest.main()
