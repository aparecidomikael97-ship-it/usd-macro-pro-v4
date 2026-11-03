"""Pre-event BoE policy survey: real document, stale, never an FX forecast."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import unittest

from atlasquant_trader_boe_mpc_prospective_lab import (
    SCHEMA, inspect_boe_mpc_prospective_freeze_lab,
)

CASE = Path(__file__).resolve().parent / "docs" / "continuidade" / "TRADER_BOE_MPC_NOV5_PROSPECTIVE_FREEZE_20261103.json"
BEFORE = datetime(2026, 11, 3, 11, 15, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)


def book():
    return json.loads(CASE.read_text(encoding="utf-8"))


def eval_case(data=None, when=BEFORE, later=None):
    return inspect_boe_mpc_prospective_freeze_lab(
        book() if data is None else data, evaluated_at=when, later_actual=later,
    )


def hypothetical_actual(rate="3.75"):
    return {
        "state": "LAB_CALLER_SUPPLIED_ACTUAL_UNATTESTED",
        "source_url": "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes/2026/november-2026",
        "published_at_utc": "2026-11-05T12:00:00Z",
        "captured_at_utc": "2026-11-05T12:15:00Z",
        "official_bank_rate_pct": rate,
    }


class BoEProspectiveFreezeTests(unittest.TestCase):
    def test_stale_real_document_precedes_event(self):
        out = eval_case()
        self.assertEqual(out["schema"], SCHEMA)
        self.assertEqual(out["state"], "LAB_STALE_SURVEY_DOCUMENTED_BEFORE_MPC")
        self.assertEqual(out["historical_survey_median_pct"], "3.75")
        self.assertEqual(out["survey_age_days"], 46)
        self.assertFalse(out["survey_is_fresh"])
        self.assertTrue(out["recorded_before_meeting"])

    def test_original_survey_has_92_responses_and_quantiles(self):
        d = book()
        self.assertEqual(d["respondents"], 92)
        self.assertEqual(d["p25_policy_rate_pct"], "3.75")
        self.assertEqual(d["median_policy_rate_pct"], "3.75")
        self.assertEqual(d["p75_policy_rate_pct"], "3.81")

    def test_hash_deterministic(self):
        self.assertEqual(eval_case()["freeze_sha256"], eval_case()["freeze_sha256"])
        self.assertEqual(len(eval_case()["freeze_sha256"]), 64)

    def test_hash_is_not_independent_receipt(self):
        out = eval_case()
        self.assertFalse(out["source_receipt_verified"])
        self.assertFalse(out["real_oos_verified"])

    def test_observation_cannot_be_used_in_prior_hour(self):
        out = eval_case(when=datetime(2026, 11, 3, 11, 5, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_naive_time_is_rejected(self):
        with self.assertRaises(ValueError):
            eval_case(when=datetime(2026, 11, 3, 12, 0))

    def test_actual_forbidden_before_event(self):
        out = eval_case(later=hypothetical_actual())
        self.assertEqual(out["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_event_day_waits_for_actual(self):
        out = eval_case(when=datetime(2026, 11, 5, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(out["state"], "LAB_BOE_MPC_PASSED_NO_VERIFIED_ACTUAL")

    def test_next_day_still_waits_for_actual(self):
        out = eval_case(when=AFTER)
        self.assertEqual(out["state"], "LAB_BOE_MPC_PASSED_NO_VERIFIED_ACTUAL")

    def test_post_event_caller_supplied_zero_error_not_homologated(self):
        out = eval_case(when=AFTER, later=hypothetical_actual("3.75"))
        self.assertEqual(out["state"], "LAB_CALLER_SUPPLIED_OUTCOME_COMPARISON_UNVERIFIED")
        self.assertEqual(out["caller_supplied_absolute_error_pp"], "0.00")
        self.assertIsNone(out["real_actual_rate_pct"])
        self.assertFalse(out["real_oos_verified"])

    def test_post_event_caller_supplied_quarter_point_error(self):
        out = eval_case(when=AFTER, later=hypothetical_actual("4.00"))
        self.assertEqual(out["caller_supplied_absolute_error_pp"], "0.25")

    def test_future_actual_published_after_evaluation_rejected(self):
        a = hypothetical_actual()
        a["published_at_utc"] = "2026-11-07T12:00:00Z"
        a["captured_at_utc"] = "2026-11-07T12:15:00Z"
        out = eval_case(when=AFTER, later=a)
        self.assertEqual(out["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_actual_capture_before_publication_rejected(self):
        a = hypothetical_actual()
        a["captured_at_utc"] = "2026-11-05T11:59:00Z"
        out = eval_case(when=AFTER, later=a)
        self.assertEqual(out["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_actual_not_from_boe_rejected(self):
        a = hypothetical_actual()
        a["source_url"] = "https://finance.example/decision"
        out = eval_case(when=AFTER, later=a)
        self.assertEqual(out["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_actual_boe_subdomain_attack_rejected(self):
        a = hypothetical_actual()
        a["source_url"] = "https://www.bankofengland.co.uk.attack.invalid/monetary-policy-summary-and-minutes/a"
        self.assertEqual(eval_case(when=AFTER, later=a)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_actual_wrong_path_rejected(self):
        a = hypothetical_actual()
        a["source_url"] = "https://www.bankofengland.co.uk/markets/daily"
        self.assertEqual(eval_case(when=AFTER, later=a)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_missing_actual_field_rejected(self):
        a = hypothetical_actual()
        del a["captured_at_utc"]
        self.assertEqual(eval_case(when=AFTER, later=a)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_wrong_actual_state_rejected(self):
        a = hypothetical_actual()
        a["state"] = "OFFICIAL_ATTESTED"
        self.assertEqual(eval_case(when=AFTER, later=a)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_nan_actual_rejected(self):
        self.assertEqual(
            eval_case(when=AFTER, later=hypothetical_actual("NaN"))["state"],
            "LAB_BOE_SURVEY_FREEZE_REFUSED",
        )

    def test_bool_actual_rejected(self):
        self.assertEqual(
            eval_case(when=AFTER, later=hypothetical_actual(True))["state"],
            "LAB_BOE_SURVEY_FREEZE_REFUSED",
        )

    def test_wrong_median_rejected(self):
        d = book()
        d["median_policy_rate_pct"] = "3.50"
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_wrong_quantile_rejected(self):
        d = book()
        d["p75_policy_rate_pct"] = "4.00"
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_source_forgery_rejected(self):
        d = book()
        d["source_url"] = "https://fake.example/polls"
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_change_survey_timestamp_cannot_claim_older_observation(self):
        d = book()
        d["observed_at_utc"] = "2026-09-18T08:00:00Z"
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_changed_target_meeting_rejected(self):
        d = book()
        d["target_mpc_on"] = "2026-11-04"
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_added_signal_field_rejected(self):
        d = book()
        d["buy_gbpusd"] = True
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_removed_flag_rejected(self):
        d = book()
        del d["source_original_bytes_archived"]
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_real_receipt_claim_rejected(self):
        d = book()
        d["source_receipt_independently_attested"] = True
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_not_a_market_priced_probability(self):
        d = book()
        d["market_priced_probability"] = 0.9
        self.assertEqual(eval_case(d)["state"], "LAB_BOE_SURVEY_FREEZE_REFUSED")

    def test_all_paths_preserve_no_go(self):
        for kw in ({}, {"when": AFTER}, {"when": AFTER, "later": hypothetical_actual("4.0")}):
            out = eval_case(**kw)
            self.assertIsNone(out["fx_bias"])
            self.assertIsNone(out["fx_probability"])
            self.assertFalse(out["accuracy_90_proven"])
            self.assertFalse(out["can_feed_live_radar"])
            self.assertFalse(out["trade_authorized"])
            self.assertFalse(out["worker_enabled"])
            self.assertFalse(out["scheduler_enabled"])



if __name__ == "__main__":
    unittest.main()
