"""No live forecasts: all Github metadata and directions in tests are synthetic."""
from dataclasses import replace
from hashlib import sha256
import json
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    PairForecastClaim, GithubWitnessClaim, WindowForecastWitnessClaim,
    prepare_window_witness_body_lab as prepare,
    inspect_prospective_fx28_witness_census_lab as inspect,
    PREWINDOW_LOOKBACK,
)

UTC = timezone.utc
FIRST_START, FIRST_END = _nominal_windows("D1")[0]
CREATED = FIRST_START - timedelta(hours=2)
RETRIEVED = CREATED + timedelta(minutes=1)
ISSUED = CREATED - timedelta(hours=1)
CUTOFF = ISSUED - timedelta(hours=1)
AFTER_DUE = FIRST_START + timedelta(minutes=1)
BEFORE_DUE = datetime(2026, 11, 12, 20, tzinfo=UTC)
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"


def make_claim(*, horizon="D1", index=0, comment_id=314159, direction="UP"):
    start, end = _nominal_windows(horizon)[index]
    created = start - timedelta(hours=2)
    issued = created - timedelta(hours=1)
    features = issued - timedelta(hours=1)
    roster = tuple(PairForecastClaim(
        pair=pair, direction=direction,
        abstain_reason="LOW_CONFIDENCE" if direction == "ABSTAIN" else None,
        feature_cutoff_at=features,
        forecast_issued_at=issued,
        model_sha256_claim="a" * 64,
        evidence_sha256_claim="b" * 64,
    ) for pair in OFFICIAL_PAIRS)
    prepared = prepare(
        horizon=horizon, start_at=start, end_at=end,
        forecast_roster=roster, prepared_at=created,
    )
    assert prepared["state"] == "LAB_WITNESS_BODY_PREPARED_NOT_POSTED", prepared
    witness = GithubWitnessClaim(
        comment_id=comment_id,
        comment_body=prepared["body"],
        api_url=f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}",
        html_url=f"https://github.com/{REPO}/issues/1884#issuecomment-{comment_id}",
        created_at=created, updated_at=created,
        retrieved_at=created + timedelta(minutes=1),
    )
    return WindowForecastWitnessClaim(horizon, start, end, roster, witness)


class ProspectiveWitnessCensusTests(unittest.TestCase):
    def audit(self, records=(), *, now=AFTER_DUE):
        return inspect(window_claims=records, inspected_at_utc=now)

    def safe(self, result):
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_directional_accuracy"])
        self.assertIsNone(result["calibrated_direction_probability"])
        for flag in (
            "github_comments_independently_authenticated",
            "pre_event_forecasts_independently_witnessed",
            "point_in_time_macro_authenticated",
            "broker_price_source_authenticated",
            "out_of_sample_accuracy_validated",
            "publishable", "live_alert_allowed", "trade_authorized",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(result[flag], flag)
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def test_before_campaign_every_slot_is_future_not_missing(self):
        result = self.audit(now=BEFORE_DUE)
        self.assertEqual(result["state"],
                         "LAB_PROSPECTIVE_WITNESS_CENSUS_CLAIM_ONLY_NO_GO")
        self.assertEqual(result["not_yet_due_slots"], 672)
        self.assertEqual(result["due_missing_witness_slots"], 0)
        self.assertEqual(result["due_witness_claim_only_slots"], 0)
        self.assertEqual(len(result["windows"]), 24)
        self.assertEqual(result["per_horizon"]["D1"]["slots_expected"], 560)
        self.assertEqual(result["per_horizon"]["W1"]["slots_expected"], 112)
        self.safe(result)

    def test_first_day_due_without_forecast_counts_both_horizons_missing(self):
        result = self.audit()
        self.assertEqual(result["due_missing_witness_slots"], 56)
        self.assertEqual(result["not_yet_due_slots"], 616)
        self.assertEqual(result["due_witness_claim_only_slots"], 0)
        self.assertTrue(result["all_nominal_opportunities_accounted"])
        self.safe(result)

    def test_one_d1_28fx_claim_does_not_hide_missing_weekly_forecasts(self):
        claim = make_claim()
        result = self.audit((claim,))
        self.assertEqual(result["due_missing_witness_slots"], 28)
        self.assertEqual(result["due_witness_claim_only_slots"], 28)
        self.assertEqual(result["due_directional_claim_only_slots"], 28)
        self.assertEqual(result["not_yet_due_slots"], 616)
        self.assertFalse(result["pre_event_forecasts_independently_witnessed"])
        self.safe(result)

    def test_abstentions_are_not_directional_guesses(self):
        claim = make_claim(direction="ABSTAIN")
        result = self.audit((claim,))
        self.assertEqual(result["due_abstention_claim_only_slots"], 28)
        self.assertEqual(result["due_directional_claim_only_slots"], 0)
        self.safe(result)

    def test_two_horizons_require_distinct_claimed_comment_ids(self):
        daily = make_claim()
        weekly = make_claim(horizon="W1", comment_id=271828)
        result = self.audit((daily, weekly))
        self.assertEqual(result["due_missing_witness_slots"], 0)
        self.assertEqual(result["due_witness_claim_only_slots"], 56)
        self.assertEqual(result["not_yet_due_slots"], 616)
        self.assertEqual(result["future_witness_claim_only_slots"], 0)
        self.safe(result)
        duplicated_id = replace(weekly, github_witness=replace(
            weekly.github_witness, comment_id=daily.github_witness.comment_id))
        altered = self.audit((daily, duplicated_id))
        self.assertEqual(altered["state"], "LAB_WITNESS_CENSUS_BLOCKED")
        self.safe(altered)

    def test_27_of_28_forecasts_cannot_claim_to_cover_one_session(self):
        claim = make_claim()
        partial = replace(claim, forecast_roster=claim.forecast_roster[:-1])
        result = self.audit((partial,))
        self.assertEqual(result["reason"],
                         "INCOMPLETE_DUPLICATE_POST_EVENT_OR_INVALID_28FX_FORECASTS")
        self.safe(result)

    def test_duplicate_pair_even_with_28_rows_is_blocked(self):
        claim = make_claim()
        dup = replace(claim, forecast_roster=claim.forecast_roster[:-1] +
                      (claim.forecast_roster[0],))
        report = self.audit((dup,))
        self.assertEqual(report["state"], "LAB_WITNESS_CENSUS_BLOCKED")
        self.safe(report)

    def test_after_start_or_future_claimed_issuance_fails(self):
        claim = make_claim()
        for issued in (FIRST_START, FIRST_START + timedelta(minutes=1),
                       AFTER_DUE + timedelta(days=2)):
            with self.subTest(issued=issued):
                first = replace(claim.forecast_roster[0], forecast_issued_at=issued)
                altered = replace(claim, forecast_roster=(first,) + claim.forecast_roster[1:])
                result = self.audit((altered,))
                self.assertEqual(result["state"], "LAB_WITNESS_CENSUS_BLOCKED")
                self.safe(result)

    def test_retrieval_after_target_cannot_be_retroactively_pre_event(self):
        claim = make_claim()
        altered = replace(claim, github_witness=replace(
            claim.github_witness, retrieved_at=FIRST_START))
        result = self.audit((altered,), now=FIRST_START + timedelta(hours=2))
        self.assertEqual(result["reason"],
                         "LATE_EDITED_UNOBSERVED_OR_FAKE_GITHUB_COMMENT_FIELDS")
        self.safe(result)

    def test_edited_comment_cannot_be_used_as_original_commitment(self):
        claim = make_claim()
        altered = replace(claim, github_witness=replace(
            claim.github_witness, updated_at=CREATED + timedelta(seconds=1)))
        result = self.audit((altered,))
        self.assertEqual(result["reason"],
                         "LATE_EDITED_UNOBSERVED_OR_FAKE_GITHUB_COMMENT_FIELDS")
        self.safe(result)

    def test_witness_body_must_hash_all_28_full_forecasts(self):
        claim = make_claim()
        altered = replace(claim, github_witness=replace(
            claim.github_witness, comment_body=claim.github_witness.comment_body + "X"))
        result = self.audit((altered,))
        self.assertEqual(result["reason"],
                         "COMMENT_BODY_NOT_BOUND_TO_ALL_28_FORECASTS")
        self.safe(result)

    def test_witness_wrong_issue_url_is_blocked(self):
        claim = make_claim()
        altered = replace(claim, github_witness=replace(
            claim.github_witness, html_url="https://github.com/elsewhere/issue/1884"))
        result = self.audit((altered,))
        self.assertEqual(result["reason"],
                         "LATE_EDITED_UNOBSERVED_OR_FAKE_GITHUB_COMMENT_FIELDS")
        self.safe(result)

    def test_repeat_same_session_cannot_multiply_observations(self):
        claim = make_claim()
        result = self.audit((claim, claim))
        self.assertEqual(result["reason"], "DUPLICATE_UNKNOWN_OR_WRONG_NY17_WINDOW")
        self.safe(result)

    def test_future_witness_28_slots_still_not_success_or_accuracy(self):
        claim = make_claim()
        now = CREATED + timedelta(minutes=2)
        result = self.audit((claim,), now=now)
        self.assertEqual(result["future_witness_claim_only_slots"], 28)
        self.assertEqual(result["not_yet_due_slots"], 672)
        self.assertEqual(result["due_witness_claim_only_slots"], 0)
        self.safe(result)

    def test_canonical_28_forecasts_are_returned_for_external_preservation(self):
        claim = make_claim()
        receipt = prepare(horizon=claim.horizon, start_at=claim.start_at,
                          end_at=claim.end_at,
                          forecast_roster=claim.forecast_roster,
                          prepared_at=CREATED)
        raw = receipt["canonical_forecast_json"]
        self.assertIsInstance(raw, str)
        self.assertEqual(sha256(raw.encode("ascii")).hexdigest(),
                         receipt["forecast_roster_sha256"])
        self.assertEqual(len(json.loads(raw)["pairs"]), 28)
        self.assertFalse(receipt["canonical_forecast_payload_retained_externally"])
        self.assertFalse(receipt["body_posted_on_github"])

    def test_changing_one_forecast_changes_public_witness_digest(self):
        claim = make_claim()
        first = prepare(horizon=claim.horizon, start_at=claim.start_at,
                        end_at=claim.end_at,
                        forecast_roster=claim.forecast_roster,
                        prepared_at=CREATED)
        different = replace(claim.forecast_roster[0], direction="DOWN")
        altered = prepare(horizon=claim.horizon, start_at=claim.start_at,
                          end_at=claim.end_at,
                          forecast_roster=(different,) + claim.forecast_roster[1:],
                          prepared_at=CREATED)
        self.assertNotEqual(first["forecast_roster_sha256"],
                            altered["forecast_roster_sha256"])
        self.assertNotEqual(first["canonical_forecast_json"],
                            altered["canonical_forecast_json"])

    def test_weekly_ny17_session_is_five_days_and_anchor_is_accepted(self):
        claim = make_claim(horizon="W1", comment_id=7007)
        self.assertEqual(claim.end_at - claim.start_at, timedelta(days=5))
        receipt = prepare(horizon="W1", start_at=claim.start_at,
                          end_at=claim.end_at,
                          forecast_roster=claim.forecast_roster,
                          prepared_at=claim.github_witness.created_at)
        self.assertEqual(receipt["state"], "LAB_WITNESS_BODY_PREPARED_NOT_POSTED")
        self.assertEqual(len(json.loads(receipt["canonical_forecast_json"])["pairs"]), 28)
        self.assertFalse(receipt["external_precommit_verified"])

    def test_prepare_only_never_claims_published_comment(self):
        claim = make_claim()
        value = prepare(horizon=claim.horizon, start_at=claim.start_at,
                        end_at=claim.end_at,
                        forecast_roster=claim.forecast_roster,
                        prepared_at=CREATED)
        self.assertTrue(value["body"].startswith(
            "ATLASQUANT_FX28_NY17_WINDOW_PRE_EVENT_COMMITMENT_LAB_V1"))
        self.assertEqual(len(value["forecast_roster_sha256"]), 64)
        self.assertFalse(value["body_posted_on_github"])
        self.assertFalse(value["external_precommit_verified"])

    def test_missing_forecast_in_one_week_cannot_be_backfilled(self):
        now = _nominal_windows("W1")[1][0] + timedelta(minutes=1)
        # Forecast claims for first week only; all earlier nominal windows remain.
        report = self.audit((make_claim(horizon="W1", comment_id=2001),), now=now)
        self.assertGreater(report["due_missing_witness_slots"], 28)
        self.assertEqual(report["due_witness_claim_only_slots"], 28)
        self.safe(report)

    def test_prewindow_exact_12_hours_is_accepted_for_hash_preparation_only(self):
        self.assertEqual(PREWINDOW_LOOKBACK, timedelta(hours=12))
        base = make_claim()
        first = FIRST_START - PREWINDOW_LOOKBACK
        roster = tuple(replace(record, feature_cutoff_at=first,
                               forecast_issued_at=first)
                       for record in base.forecast_roster)
        prepared = prepare(horizon="D1", start_at=FIRST_START,
                           end_at=FIRST_END, forecast_roster=roster,
                           prepared_at=first)
        self.assertEqual(prepared["state"],
                         "LAB_WITNESS_BODY_PREPARED_NOT_POSTED")
        self.assertFalse(prepared["body_posted_on_github"])
        self.assertFalse(prepared["external_precommit_verified"])

    def test_prewindow_one_second_stale_issuance_cannot_be_hash_published(self):
        base = make_claim()
        old = FIRST_START - PREWINDOW_LOOKBACK - timedelta(seconds=1)
        roster = tuple(replace(record, feature_cutoff_at=old,
                               forecast_issued_at=old)
                       for record in base.forecast_roster)
        prepared = prepare(horizon="D1", start_at=FIRST_START,
                           end_at=FIRST_END, forecast_roster=roster,
                           prepared_at=FIRST_START - timedelta(hours=1))
        self.assertEqual(prepared["state"], "LAB_WITNESS_BODY_BLOCKED")
        self.assertIsNone(prepared["body"])

    def test_prewindow_old_feature_cutoff_rejected_even_if_issued_recently(self):
        claim = make_claim()
        old = FIRST_START - PREWINDOW_LOOKBACK - timedelta(seconds=1)
        row = replace(claim.forecast_roster[0], feature_cutoff_at=old)
        altered = replace(claim, forecast_roster=(row,) + claim.forecast_roster[1:])
        value = self.audit((altered,))
        self.assertEqual(value["reason"],
                         "INCOMPLETE_DUPLICATE_POST_EVENT_OR_INVALID_28FX_FORECASTS")
        self.safe(value)

    def test_prewindow_old_body_preparation_cannot_commit_28_roster(self):
        claim = make_claim()
        old = FIRST_START - PREWINDOW_LOOKBACK - timedelta(seconds=1)
        prepared = prepare(horizon=claim.horizon, start_at=claim.start_at,
                           end_at=claim.end_at, forecast_roster=claim.forecast_roster,
                           prepared_at=old)
        self.assertEqual(prepared["state"], "LAB_WITNESS_BODY_BLOCKED")
        self.assertIsNone(prepared["forecast_roster_sha256"])

    def test_prewindow_old_comment_time_not_recast_as_pre_event_witness(self):
        claim = make_claim()
        created = FIRST_START - PREWINDOW_LOOKBACK - timedelta(seconds=1)
        altered = replace(claim, github_witness=replace(
            claim.github_witness, created_at=created, updated_at=created,
            retrieved_at=created))
        value = self.audit((altered,))
        self.assertEqual(value["reason"],
                         "LATE_EDITED_UNOBSERVED_OR_FAKE_GITHUB_COMMENT_FIELDS")
        self.safe(value)

    def test_prewindow_last_second_genuine_claim_only_not_forecast_proof(self):
        claim = make_claim()
        issued = FIRST_START - timedelta(seconds=2)
        comment_at = FIRST_START - timedelta(seconds=1)
        roster = tuple(replace(record, feature_cutoff_at=issued,
                               forecast_issued_at=issued)
                       for record in claim.forecast_roster)
        prepared = prepare(horizon="D1", start_at=FIRST_START,
                           end_at=FIRST_END, forecast_roster=roster,
                           prepared_at=comment_at)
        self.assertEqual(prepared["state"], "LAB_WITNESS_BODY_PREPARED_NOT_POSTED")
        witness = replace(claim.github_witness, created_at=comment_at,
                          updated_at=comment_at, retrieved_at=comment_at,
                          comment_body=prepared["body"])
        value = self.audit((replace(claim, forecast_roster=roster,
                                   github_witness=witness),))
        self.assertEqual(value["state"],
                         "LAB_PROSPECTIVE_WITNESS_CENSUS_CLAIM_ONLY_NO_GO")
        self.assertFalse(value["pre_event_forecasts_independently_witnessed"])
        self.safe(value)


if __name__ == "__main__":
    unittest.main()
