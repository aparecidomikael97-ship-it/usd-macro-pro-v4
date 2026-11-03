"""Contracts for real pre-event policy SURVEY freeze, not a trade forecast."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from atlasquant_trader_copom_pre_event_lock_lab import (
    SCHEMA, STATE, DENIED, EXPECTED, EARLIEST_RELEASE, RESEARCH_CUTOFF,
    FREEZE_DEADLINE, freeze_pre_copom_snapshot_lab as build,
)

PATH = (Path(__file__).resolve().parent / "docs" / "continuidade"
        / "TRADER_COPOM_20261104_FROZEN_PRE_EVENT_20261103.json")
NOW = datetime(2026, 11, 3, 17, tzinfo=timezone.utc)


def fixture():
    return json.loads(PATH.read_text(encoding="utf-8"))


def evaluate(value=None, *, at=NOW):
    return build(fixture() if value is None else value, evaluated_at=at)


class CopomPreEventLockTests(unittest.TestCase):
    def test_frozen_doc_exact_identity_and_source_levels(self):
        r = evaluate()
        self.assertEqual((r["schema"], r["state"]), (SCHEMA, STATE))
        self.assertEqual(fixture(), EXPECTED)
        self.assertTrue(r["snapshot_is_exact_pinned_record"])
        self.assertEqual(r["focus_year_end_2026_pct"], "13.50")
        self.assertEqual(r["focus_november_month_end_pct"], "13.50")
        self.assertEqual(r["monetary_policy_level_before_event_pct"], "13.75")

    def test_pre_event_research_date_and_meeting_days(self):
        r = evaluate()
        self.assertEqual(r["research_day_utc"], "2026-11-03")
        self.assertEqual(r["meeting_dates"], ["2026-11-03", "2026-11-04"])
        self.assertEqual(r["official_decision_day"], "2026-11-04")

    def test_copom_announcement_is_earliest_not_exact_time(self):
        r = evaluate()
        self.assertEqual(r["earliest_scheduled_announcement_utc"], "2026-11-04T21:30:00+00:00")
        self.assertEqual(EARLIEST_RELEASE.hour, 21)
        self.assertFalse(r["announcement_clock_is_exact"])

    def test_economist_respondent_share_is_not_market_probability(self):
        r = evaluate()
        self.assertEqual((r["economist_hold_responses"],r["economist_poll_respondents"]), (33,48))
        self.assertEqual(Decimal(r["economist_hold_respondent_share_pct"]),Decimal("68.75"))
        self.assertFalse(r["survey_respondent_share_is_probability"])
        self.assertIsNone(r["market_policy_probability"])

    def test_frozen_rate_scenarios_are_conditional_only(self):
        r = evaluate()
        cases = {x["id"]:x["rate_pct"] for x in r["conditional_scenarios_not_price_forecasts"]}
        self.assertEqual(cases, {"HOLD_13_75":"13.75", "CUT_25BP_13_50":"13.50", "OTHER":None})
        self.assertFalse(r["non_hold_respondents_all_predicted_25bp_cut"])
        self.assertTrue(r["other_outcomes_possible"])

    def test_fifteen_nonhold_responses_not_silently_assigned_to_cut(self):
        r = evaluate()
        self.assertEqual(r["economist_poll_respondents"] - r["economist_hold_responses"],15)
        self.assertFalse(r["non_hold_respondents_all_predicted_25bp_cut"])

    def test_focus_year_end_is_not_next_policy_probability(self):
        r = evaluate()
        self.assertFalse(r["focus_targets_are_next_meeting_distribution"])
        self.assertIn("different policy horizon",r["why_no_market_bias"])

    def test_win_wdo_and_no_directional_forecast(self):
        r = evaluate()
        self.assertEqual(r["instruments_to_research"],["WIN","WDO"])
        self.assertEqual(r["win_wdo_directional_bias"],"AGUARDAR")
        self.assertEqual(r["fx_directional_bias"],"AGUARDAR")
        self.assertIsNone(r["forecast_hit_rate"])

    def test_never_asserts_observed_copom_result_in_advance(self):
        r = evaluate()
        self.assertFalse(r["post_event_actual_known"])
        self.assertIsNone(r["actual_policy_rate"])
        self.assertFalse(r["real_oos_accuracy_proven"])

    def test_digest_identifies_exact_content_but_not_independent_receipt(self):
        r = evaluate()
        self.assertEqual(len(r["checkpoint_digest_sha256"]),64)
        self.assertTrue(all(c in "0123456789abcdef" for c in r["checkpoint_digest_sha256"]))
        self.assertFalse(r["independent_pre_event_publication_receipt_verified"])
        self.assertFalse(r["github_push_time_independently_verified_by_module"])

    def test_frozen_payload_does_not_claim_raw_pdf_archive(self):
        r = evaluate()
        self.assertFalse(r["source_original_pdf_bytes_archived"])
        self.assertIsNone(r["original_pdf_sha256"])

    def test_blocks_backdating_before_research_cutoff(self):
        r = evaluate(at=datetime(2026,11,3,14,59,tzinfo=timezone.utc))
        self.assertEqual(r["state"],DENIED)
        self.assertIsNone(r["checkpoint_digest_sha256"])
        self.assertEqual(RESEARCH_CUTOFF.hour,15)

    def test_new_issue_only_allowed_before_midnight_nov3_utc(self):
        self.assertEqual(evaluate(at=FREEZE_DEADLINE)["state"], DENIED)
        self.assertEqual(evaluate(at=datetime(2026,11,4,22,tzinfo=timezone.utc))["state"],DENIED)

    def test_tz_offset_research_cutoff_normalized_utc(self):
        t = datetime.fromisoformat("2026-11-03T13:00:00-04:00")
        self.assertEqual(evaluate(at=t)["state"],STATE)

    def test_naive_evaluation_time_rejected(self):
        with self.assertRaises(ValueError):
            evaluate(at=datetime(2026,11,3,16))

    def test_tampered_policy_rate_and_focus_horizons_rejected(self):
        for field,changed in [
            ("current_selic_pct","13.50"),
            ("focus_2026_year_end_selic_pct","13.75"),
            ("focus_2026_november_month_end_selic_pct","13.75"),
            ("focus_2027_year_end_selic_pct","13.50"),
        ]:
            with self.subTest(field=field):
                x=fixture();x[field]=changed
                self.assertEqual(evaluate(x)["state"],DENIED)

    def test_reuters_poll_counts_and_false_odds_rejected(self):
        for field,value in [
            ("reuters_poll_hold_responses",34),
            ("reuters_poll_total_respondents",50),
            ("reuters_poll_total_respondents",True),
            ("market_implied_probability","68.75"),
            ("other_poll_responses_not_assumed_to_all_predict_cut",False),
        ]:
            with self.subTest(field=field):
                x=fixture();x[field]=value
                self.assertEqual(evaluate(x)["state"],DENIED)

    def test_fake_source_urls_event_dates_and_precise_release_rejected(self):
        for field,changed in [
            ("source_focus_pdf","https://another.example"),
            ("source_reuters_poll","https://another.example"),
            ("source_bcb_calendar","https://another.example"),
            ("official_decision_day","2026-11-03"),
            ("scheduled_announcement_not_before_utc","2026-11-04T20:30:00Z"),
            ("announcement_time_is_exact",True),
        ]:
            x=fixture();x[field]=changed
            self.assertEqual(evaluate(x)["state"],DENIED,field)

    def test_missing_extra_and_duplicate_instrument_rejected(self):
        x=fixture();x.pop("reuters_poll_hold_responses")
        self.assertEqual(evaluate(x)["state"],DENIED)
        x=fixture();x["new_probability"]=99
        self.assertEqual(evaluate(x)["state"],DENIED)
        x=fixture();x["financial_assets"]=["WIN","WIN"]
        self.assertEqual(evaluate(x)["state"],DENIED)

    def test_forged_after_event_actual_cannot_be_injected(self):
        x=fixture();x["event_actual_known"]=True
        self.assertEqual(evaluate(x)["state"],DENIED)
        x=fixture();x["actual_selic_pct"]="13.75"
        self.assertEqual(evaluate(x)["state"],DENIED)

    def test_no_non_lab_activation_render_subscription_worker_trade(self):
        r=evaluate()
        for flag in ("can_feed_live_radar","trade_authorized","worker_enabled",
                     "scheduler_enabled","render_configuration_changed",
                     "paid_provider_approved","market_implied_repricing_verified"):
            self.assertFalse(r[flag],flag)

    def test_malformed_input_values_rejected(self):
        for inp in ({},[],"snapshot",None,123):
            with self.subTest(input_type=str(type(inp))):
                if inp is None:
                    self.assertEqual(build(inp,evaluated_at=NOW)["state"],DENIED)
                else:
                    self.assertEqual(evaluate(inp)["state"],DENIED)


if __name__=="__main__":
    unittest.main()
