"""Synthetic offline tests of GitHub-style forecast hash anchor guard."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_event_forecast_lock_lab import (
    ForecastDraft, ForecastLock, freeze_pre_event_forecast_lab,
)
from atlasquant_trader_forecast_anchor_lab import (
    AnchorTarget, ClaimedGitHubComment,
    assess_claimed_github_anchor_lab as assess,
    prepare_pre_event_anchor_lab as prepare,
)

UTC = timezone.utc
CAPTURED = datetime(2026, 11, 8, 17, 0, tzinfo=UTC)
RELEASE = datetime(2026, 11, 10, 13, 30, tzinfo=UTC)
COMMENT_TIME = CAPTURED + timedelta(minutes=2)
PR = AnchorTarget("aparecidomikael97-ship-it/usd-macro-pro-v4", 1851)
COMMENT_ID = 123456


def lock() -> ForecastLock:
    d = ForecastDraft(
        event_id="US_CPI_2026_10", currency="USD", metric="CPI_MOM",
        target_period="2026-10", unit="PERCENT_MOM_SA",
        scheduled_release_at=RELEASE, forecast_captured_at=CAPTURED,
        previous_value="0.6", previous_available_at=CAPTURED-timedelta(days=10),
        consensus_value="0.3", consensus_available_at=CAPTURED-timedelta(hours=1),
        model_estimate="0.35", model_version="v1.0",
        previous_source_sha256_claim="a"*64,
        consensus_source_sha256_claim="b"*64,
    )
    return freeze_pre_event_forecast_lab(d, as_of_utc=CAPTURED)["lock"]


def comment(*, post: datetime = COMMENT_TIME, edited: datetime = COMMENT_TIME,
            fetched: datetime | None = None) -> ClaimedGitHubComment:
    prepared = prepare(lock(), PR, as_of_utc=CAPTURED)
    return ClaimedGitHubComment(
        comment_id=COMMENT_ID,
        api_url=("https://api.github.com/repos/aparecidomikael97-ship-it/"
                 "usd-macro-pro-v4/issues/comments/123456"),
        html_url=("https://github.com/aparecidomikael97-ship-it/"
                  "usd-macro-pro-v4/pull/1851#issuecomment-123456"),
        body=prepared["anchor_body_documentary"], created_at=post,
        updated_at=edited, fetched_at=fetched or COMMENT_TIME + timedelta(seconds=10),
    )


class GitHubAnchorGuardTests(unittest.TestCase):
    def assert_no_go(self, output):
        self.assertFalse(output["github_api_response_independently_authenticated"])
        self.assertFalse(output["github_server_clock_independently_verified"])
        self.assertFalse(output["pre_event_forecast_provenance_verified"])
        self.assertFalse(output["consensus_source_independently_verified"])
        self.assertFalse(output["trade_authorized"])
        self.assertFalse(output["publishable"])
        self.assertFalse(output["live_alert_allowed"])
        self.assertFalse(output["worker_enabled"])
        self.assertFalse(output["scheduler_enabled"])
        self.assertEqual(output["validated_prediction_count"], 0)
        self.assertIsNone(output["validated_accuracy"])
        self.assertIsNone(output["calibrated_direction_probability"])
        self.assertIsNone(output["fx_bias"])
        self.assertIsNone(output["index_bias"])
        self.assertEqual(output["operational_bias"], "AGUARDAR")
        self.assertEqual((output["http_requests"], output["file_writes"],
                          output["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(output["research_only"])

    def test_prepares_only_hash_not_private_estimate(self):
        r = prepare(lock(), PR, as_of_utc=CAPTURED)
        self.assertEqual(r["state"], "LAB_ANCHOR_TEXT_PREPARED_NOT_POSTED")
        body = r["anchor_body_documentary"]
        self.assertIn("forecast_payload_sha256=" + lock().payload_sha256, body)
        self.assertIn("not_a_trading_signal=true", body)
        self.assertNotIn("0.35", body)
        self.assertNotIn("0.6", body)
        self.assertNotIn("0.3", body)
        self.assertIsNone(r["anchor_comment_id_claim"])
        self.assert_no_go(r)

    def test_repeated_prepare_has_same_commitment(self):
        self.assertEqual(prepare(lock(), PR, as_of_utc=CAPTURED),
                         prepare(lock(), PR, as_of_utc=CAPTURED))

    def test_does_not_generate_new_anchor_text_after_release(self):
        for now in (RELEASE, RELEASE + timedelta(minutes=1)):
            with self.subTest(now=now):
                r = prepare(lock(), PR, as_of_utc=now)
                self.assertEqual(r["state"], "LAB_ANCHOR_BLOCKED")
                self.assertIsNone(r["anchor_body_documentary"])
                self.assert_no_go(r)

    def test_reject_future_or_naive_asof(self):
        for now in (CAPTURED - timedelta(seconds=1),
                    CAPTURED.replace(tzinfo=None),
                    CAPTURED + timedelta(microseconds=1)):
            with self.subTest(now=now):
                self.assertEqual(prepare(lock(), PR, as_of_utc=now)["state"],
                                 "LAB_ANCHOR_BLOCKED")

    def test_invalid_target_not_assumed_safe(self):
        for target in (None, {}, AnchorTarget("bad/repo/extra", 1851),
                       AnchorTarget("owner/repo", 0),
                       AnchorTarget("owner/repo", True)):
            with self.subTest(target=target):
                self.assertEqual(prepare(lock(), target, as_of_utc=CAPTURED)["state"],
                                 "LAB_ANCHOR_BLOCKED")

    def test_valid_chronology_still_unverified_not_a_signal(self):
        r = assess(lock(), PR, comment(), as_of_utc=COMMENT_TIME + timedelta(hours=1))
        self.assertEqual(r["state"],
                         "LAB_COMMENT_ANCHOR_CHRONOLOGY_CANDIDATE_UNATTESTED")
        self.assertTrue(r["timestamp_order_self_consistent_only"])
        self.assertEqual(r["anchor_comment_id_claim"], COMMENT_ID)
        self.assert_no_go(r)

    def test_a_real_witness_could_be_rechecked_after_release(self):
        r = assess(lock(), PR, replace(comment(),
                   fetched_at=RELEASE + timedelta(hours=2)),
                   as_of_utc=RELEASE + timedelta(hours=2))
        self.assertEqual(r["state"],
                         "LAB_COMMENT_ANCHOR_CHRONOLOGY_CANDIDATE_UNATTESTED")
        self.assert_no_go(r)

    def test_posterior_comment_or_edit_is_rejected(self):
        for c in (
            comment(post=RELEASE, edited=RELEASE, fetched=RELEASE + timedelta(seconds=1)),
            comment(post=COMMENT_TIME, edited=RELEASE,
                    fetched=RELEASE + timedelta(seconds=1)),
        ):
            with self.subTest(c=c):
                r = assess(lock(), PR, c, as_of_utc=RELEASE + timedelta(hours=1))
                self.assertEqual(r["state"], "LAB_ANCHOR_BLOCKED")
                self.assert_no_go(r)

    def test_comment_claim_cannot_precede_forecast_capture(self):
        c = comment(post=CAPTURED - timedelta(seconds=1),
                    edited=CAPTURED - timedelta(seconds=1))
        self.assertEqual(assess(lock(), PR, c,
                               as_of_utc=COMMENT_TIME + timedelta(hours=1))["state"],
                         "LAB_ANCHOR_BLOCKED")

    def test_ordered_publication_edit_and_fetch_times_required(self):
        base = comment()
        for change in (
            {"updated_at": COMMENT_TIME - timedelta(seconds=1)},
            {"fetched_at": COMMENT_TIME - timedelta(seconds=1)},
            {"fetched_at": COMMENT_TIME + timedelta(days=3)},
            {"created_at": COMMENT_TIME.replace(tzinfo=None)},
            {"updated_at": COMMENT_TIME + timedelta(microseconds=1)},
        ):
            with self.subTest(change=change):
                self.assertEqual(assess(lock(), PR, replace(base, **change),
                                 as_of_utc=COMMENT_TIME + timedelta(hours=1))["state"],
                                 "LAB_ANCHOR_BLOCKED")

    def test_comment_identity_urls_and_body_are_exact(self):
        base = comment()
        for change in (
            {"comment_id": COMMENT_ID + 1},
            {"comment_id": True},
            {"api_url": base.api_url.replace("api.github.com", "api.githüb.com")},
            {"html_url": base.html_url.replace("/pull/1851", "/pull/1852")},
            {"body": base.body.replace("US_CPI_2026_10", "US_CPI_2026_09")},
            {"body": base.body + "\nextra"},
        ):
            with self.subTest(change=change):
                self.assertEqual(assess(lock(), PR, replace(base, **change),
                                 as_of_utc=COMMENT_TIME + timedelta(hours=1))["state"],
                                 "LAB_ANCHOR_BLOCKED")

    def test_issue_and_pr_form_urls_allowed(self):
        c = comment()
        c = replace(c, html_url=c.html_url.replace("/pull/1851", "/issues/1851"))
        self.assertTrue(assess(lock(), PR, c, as_of_utc=COMMENT_TIME+timedelta(hours=1))
                        ["timestamp_order_self_consistent_only"])

    def test_tampered_hash_or_payload_lock_is_blocked(self):
        valid = lock()
        for bad in (
            replace(valid, payload_sha256="a"*64),
            replace(valid, canonical_payload_json=valid.canonical_payload_json + " "),
        ):
            with self.subTest(bad=bad):
                self.assertEqual(prepare(bad, PR, as_of_utc=CAPTURED)["state"],
                                 "LAB_ANCHOR_BLOCKED")
                self.assertEqual(assess(bad, PR, comment(),
                                 as_of_utc=COMMENT_TIME+timedelta(hours=1))["state"],
                                 "LAB_ANCHOR_BLOCKED")

    def test_rehash_of_forged_forecast_is_not_independently_detectable(self):
        # The code consciously DOES NOT say that an internally consistent
        # self-hashed payload was objectively generated before the event.
        raw = json.loads(lock().canonical_payload_json)
        raw["model_estimate"] = "0.4"
        changed = json.dumps(raw, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True)
        forged = ForecastLock(changed, sha256(changed.encode("ascii")).hexdigest())
        r = prepare(forged, PR, as_of_utc=CAPTURED)
        self.assertEqual(r["state"], "LAB_ANCHOR_TEXT_PREPARED_NOT_POSTED")
        self.assertFalse(r["pre_event_forecast_provenance_verified"])
        self.assertFalse(r["github_server_clock_independently_verified"])

    def test_arbitrary_objects_are_blocked_with_no_go(self):
        for value in (None, {}, "lock", 42):
            with self.subTest(value=value):
                self.assert_no_go(prepare(value, PR, as_of_utc=CAPTURED))
                self.assert_no_go(assess(value, PR, comment(),
                                  as_of_utc=COMMENT_TIME+timedelta(hours=1)))


if __name__ == "__main__":
    unittest.main()
