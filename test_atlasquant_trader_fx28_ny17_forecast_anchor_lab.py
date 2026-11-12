"""Synthetic NY17 precommit checks only: no real model outputs or GitHub posts."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx_ny17_forecast_outcome_join_lab import Ny17ForecastClaim
from atlasquant_trader_fx_census_github_anchor_lab import GitHubCommentClaim
from atlasquant_trader_fx28_ny17_forecast_anchor_lab import (
    prepare_ny17_full_forecast_anchor_lab as prepare,
    inspect_ny17_forecast_github_comment_claim_lab as check_comment,
)

UTC = timezone.utc
PLAN = datetime(2026, 11, 12, 19, tzinfo=UTC)
PREPARED = datetime(2026, 11, 14, 20, tzinfo=UTC)
INSPECTED = datetime(2026, 11, 15, 20, tzinfo=UTC)
COMMENT_ID = 123456789


def claims(horizon="D1", ix=0, *, side="UP"):
    start, end = _nominal_windows(horizon)[ix]
    return [
        Ny17ForecastClaim(
            opportunity_id=f"SYNTH_{horizon}_{ix:02d}_{i:02d}",
            pair=pair, horizon=horizon,
            outcome_start_at=start, outcome_end_at=end,
            direction_claim=side,
            abstain_reason="UNVERIFIED_SOURCE" if side == "ABSTAIN" else None,
            features_cutoff_at=PREPARED - timedelta(hours=4),
            forecast_issued_at=PREPARED - timedelta(hours=1),
            model_sha256_claim="a" * 64,
            evidence_sha256_claim="b" * 64,
        ) for i, pair in enumerate(OFFICIAL_PAIRS)
    ]


def prepared(horizon="D1", rows=None, ix=0):
    start, end = _nominal_windows(horizon)[ix]
    return prepare(
        claims=claims(horizon, ix) if rows is None else rows,
        horizon=horizon, start_at_utc=start, end_at_utc=end,
        plan_declared_at_utc=PLAN, prepared_at_utc=PREPARED,
    )


def comment_for(output, **kw):
    created = PREPARED + timedelta(minutes=2)
    fields = {
        "comment_id": COMMENT_ID,
        "api_url": "https://api.github.com/repos/"
            "aparecidomikael97-ship-it/usd-macro-pro-v4/issues/comments/"
            + str(COMMENT_ID),
        "html_url": "https://github.com/"
            "aparecidomikael97-ship-it/usd-macro-pro-v4/issues/1884"
            "#issuecomment-" + str(COMMENT_ID),
        "body": output["anchor_comment_body"],
        "created_at": created, "updated_at": created,
        "retrieved_at": created + timedelta(minutes=2),
    }
    fields.update(kw)
    return GitHubCommentClaim(**fields)


def mutate_and_rehash(result, edited_payload):
    """Adversarial caller rewrites both JSON and its local SHA-256 receipt."""
    out = dict(result)
    old_digest = out["forecast_sha256"]
    raw = json.dumps(edited_payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False)
    digest = sha256(raw.encode("ascii")).hexdigest()
    out["forecast_json"] = raw
    out["forecast_sha256"] = digest
    out["anchor_comment_body"] = out["anchor_comment_body"].replace(
        "forecast_json_sha256=" + old_digest,
        "forecast_json_sha256=" + digest,
    )
    return out


class Ny17ForecastAnchorTests(unittest.TestCase):
    def no_go(self, r):
        self.assertIsNone(r["forecast_accuracy_validated"])
        self.assertIsNone(r["calibrated_probability"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        for key in (
            "github_comment_independently_authenticated",
            "real_forecast_generated_by_model_verified",
            "forecast_external_pre_event_witness_verified",
            "macro_information_point_in_time_verified",
            "broker_prices_independently_authenticated",
            "publishable", "live_alert_allowed", "trade_authorized",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertIs(r[key], False, key)
        self.assertEqual((r["http_requests"], r["file_writes"],
                          r["new_cost_brl"]), (0, 0, 0))
        self.assertTrue(r["research_only"])

    def test_daily_28_synthetic_directional_predictions_hash_but_not_posted(self):
        out = prepared()
        self.assertEqual(out["state"],
                         "LAB_NY17_FORECAST_ANCHOR_TEXT_PREPARED_NOT_POSTED")
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(out["directional_claims"], 28)
        self.assertEqual(out["abstentions"], 0)
        self.assertTrue(out["forecast_scope_locally_complete"])
        raw = out["forecast_json"]
        self.assertEqual(sha256(raw.encode("ascii")).hexdigest(), out["forecast_sha256"])
        self.assertEqual(len(json.loads(raw)["pairs"]), 28)
        self.assertIn("slots=28", out["anchor_comment_body"])
        self.no_go(out)

    def test_five_day_weekly_ny17_is_accepted_without_legacy_7_day_rule(self):
        start, end = _nominal_windows("W1")[0]
        self.assertEqual(end - start, timedelta(days=5))
        result = prepared("W1")
        self.assertEqual(result["pair_count"], 28)
        self.assertEqual(result["horizon"], "W1")
        self.no_go(result)

    def test_27_of_28_claims_cannot_prepare_digest(self):
        result = prepared(rows=claims()[:-1])
        self.assertEqual(result["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
        self.assertIsNone(result["anchor_comment_body"])
        self.no_go(result)

    def test_duplicate_pair_and_duplicate_id_rejected(self):
        for replacement in (
            replace(claims()[1], pair=OFFICIAL_PAIRS[0]),
            replace(claims()[1], opportunity_id=claims()[0].opportunity_id),
        ):
            with self.subTest(replacement=replacement):
                rows = claims()
                rows[1] = replacement
                result = prepared(rows=rows)
                self.assertEqual(result["reason"],
                                 "DUPLICATE_MISSING_LATE_OR_INCONSISTENT_FORECAST_CLAIM")
                self.no_go(result)

    def test_pre_event_cutoff_and_issuance_protection(self):
        start, _ = _nominal_windows("D1")[0]
        for changed in (
            {"forecast_issued_at": start},
            {"forecast_issued_at": PREPARED + timedelta(seconds=1)},
            {"features_cutoff_at": PREPARED},
            {"features_cutoff_at": PLAN - timedelta(seconds=1)},
            {"outcome_start_at": start + timedelta(days=1)},
        ):
            with self.subTest(changed=changed):
                rows = claims()
                rows[0] = replace(rows[0], **changed)
                r = prepared(rows=rows)
                self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
                self.no_go(r)

    def test_abstentions_counted_explicitly_not_as_directional(self):
        rows = claims()
        rows[0] = replace(rows[0], direction_claim="ABSTAIN",
                          abstain_reason="UNVERIFIED_SOURCE")
        rows[1] = replace(rows[1], direction_claim="DOWN")
        r = prepared(rows=rows)
        self.assertEqual((r["directional_claims"], r["abstentions"]), (27, 1))
        self.assertEqual(json.loads(r["forecast_json"])["pairs"][0][
            "direction_claim_unattested"], "ABSTAIN")
        self.no_go(r)

    def test_abstention_without_reason_and_direction_with_reason_rejected(self):
        for values in (
            {"direction_claim": "ABSTAIN", "abstain_reason": None},
            {"direction_claim": "UP", "abstain_reason": "UNVERIFIED_SOURCE"},
        ):
            rows = claims()
            rows[0] = replace(rows[0], **values)
            r = prepared(rows=rows)
            self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
            self.no_go(r)

    def test_off_campaign_weekly_window_and_mismatched_horizon_rejected(self):
        weekly = claims("W1")
        start, end = _nominal_windows("W1")[0]
        r = prepare(
            claims=weekly, horizon="W1",
            start_at_utc=start, end_at_utc=end + timedelta(days=2),
            plan_declared_at_utc=PLAN, prepared_at_utc=PREPARED)
        self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
        d = prepared(rows=weekly)
        self.assertEqual(d["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
        self.no_go(r)
        self.no_go(d)

    def test_documentary_comment_matching_never_authenticates_git(self):
        p = prepared()
        start = _nominal_windows("D1")[0][0]
        v = check_comment(prepared=p, start_at_utc=start,
                          comment=comment_for(p), inspected_at_utc=INSPECTED)
        self.assertEqual(v["state"],
                         "LAB_NY17_GITHUB_FORECAST_COMMENT_CHRONOLOGY_CLAIM_ONLY")
        self.assertTrue(v["comment_chronology_documentary_consistent"])
        self.assertFalse(v["forecast_external_pre_event_witness_verified"])
        self.no_go(v)

    def test_unmatched_or_edited_or_late_comment_blocks(self):
        p = prepared()
        start = _nominal_windows("D1")[0][0]
        for change in (
            {"body": "different"},
            {"updated_at": PREPARED + timedelta(minutes=3)},
            {"created_at": start},
            {"retrieved_at": start},
            {"html_url": "https://github.com/not-this-issue"},
        ):
            with self.subTest(change=change):
                r = check_comment(
                    prepared=p, start_at_utc=start,
                    comment=comment_for(p, **change),
                    inspected_at_utc=INSPECTED + timedelta(hours=3),
                )
                self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
                self.no_go(r)

    def test_tampered_full_forecast_document_fails_digest_verification(self):
        p = prepared()
        p["forecast_json"] = p["forecast_json"].replace('"UP"', '"DOWN"', 1)
        start = _nominal_windows("D1")[0][0]
        r = check_comment(prepared=p, start_at_utc=start,
                          comment=comment_for(p), inspected_at_utc=INSPECTED)
        self.assertEqual(r["reason"], "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST")
        self.no_go(r)

    def test_invalid_model_hash_fails_before_publication(self):
        rows = claims()
        rows[0] = replace(rows[0], model_sha256_claim="x" * 64)
        r = prepared(rows=rows)
        self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
        self.no_go(r)


    def test_rehashed_duplicate_pair_must_not_pass_local_inspector(self):
        p = prepared()
        payload = json.loads(p["forecast_json"])
        payload["pairs"][1]["pair"] = payload["pairs"][0]["pair"]
        changed = mutate_and_rehash(p, payload)
        start = _nominal_windows("D1")[0][0]
        r = check_comment(prepared=changed, start_at_utc=start,
                          comment=comment_for(changed), inspected_at_utc=INSPECTED)
        self.assertEqual(r["reason"], "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST")
        self.assertFalse(r["forecast_scope_locally_complete"])
        self.no_go(r)

    def test_rehashed_other_campaign_and_swapped_pair_order_fail(self):
        for mutant in ("campaign", "pair_order", "source_hash", "duplicate_id"):
            with self.subTest(mutant=mutant):
                p = prepared()
                payload = json.loads(p["forecast_json"])
                if mutant == "campaign":
                    payload["campaign_id"] = "SYNTHETIC_OTHER_CAMPAIGN"
                elif mutant == "pair_order":
                    payload["pairs"][0], payload["pairs"][1] = (
                        payload["pairs"][1], payload["pairs"][0])
                elif mutant == "source_hash":
                    payload["pairs"][0]["model_sha256_claim"] = "not-a-sha"
                else:
                    payload["pairs"][1]["opportunity_id"] = (
                        payload["pairs"][0]["opportunity_id"])
                changed = mutate_and_rehash(p, payload)
                start = _nominal_windows("D1")[0][0]
                r = check_comment(prepared=changed, start_at_utc=start,
                                  comment=comment_for(changed),
                                  inspected_at_utc=INSPECTED)
                self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
                self.no_go(r)

    def test_caller_can_not_change_abstention_totals_even_with_matching_comment(self):
        p = prepared()
        p["abstentions"] = 1
        p["directional_claims"] = 27
        p["anchor_comment_body"] = p["anchor_comment_body"].replace(
            "directional_claims=28\nabstentions=0",
            "directional_claims=27\nabstentions=1",
        )
        start = _nominal_windows("D1")[0][0]
        r = check_comment(prepared=p, start_at_utc=start,
                          comment=comment_for(p), inspected_at_utc=INSPECTED)
        self.assertEqual(r["reason"], "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST")
        self.no_go(r)

    def test_rehashed_future_preparation_time_fails(self):
        p = prepared()
        payload = json.loads(p["forecast_json"])
        payload["prepared_utc_claim"] = (
            PREPARED + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        changed = mutate_and_rehash(p, payload)
        start = _nominal_windows("D1")[0][0]
        r = check_comment(prepared=changed, start_at_utc=start,
                          comment=comment_for(changed), inspected_at_utc=INSPECTED)
        self.assertEqual(r["state"], "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED")
        self.no_go(r)

    def test_exact_comment_body_required_not_just_hash_substring(self):
        p = prepared()
        p["anchor_comment_body"] += "\nunsafe_claim=real_probability_99%"
        start = _nominal_windows("D1")[0][0]
        r = check_comment(prepared=p, start_at_utc=start,
                          comment=comment_for(p), inspected_at_utc=INSPECTED)
        self.assertEqual(r["reason"], "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST")
        self.no_go(r)


if __name__ == "__main__":
    unittest.main()
