"""Synthetic contract tests: no actual FX forecasts, price data or timestamps."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_trial_census_lab import (
    FrozenBlob, TrialDecision, freeze_fx_trial_roster_lab,
    freeze_full_fx_direction_census_lab, verify_frozen_fx_census_lab,
)

UTC = timezone.utc
PLAN_AT = datetime(2026, 11, 9, 9, tzinfo=UTC)
DECISION_AT = PLAN_AT + timedelta(hours=1)
FREEZE_AT = PLAN_AT + timedelta(hours=2)
D1_START = PLAN_AT + timedelta(days=1)
W1_START = PLAN_AT + timedelta(days=7)
VERSION = "atlasquant-research-v1"
COHORT = "LABC20261109"


def windows():
    return {"D1": (D1_START, D1_START + timedelta(days=1)),
            "W1": (W1_START, W1_START + timedelta(days=7))}


def plan(**changes):
    arguments = dict(cohort_id=COHORT, target_windows_by_horizon=windows(),
                     plan_frozen_at=PLAN_AT, rule_version=VERSION)
    arguments.update(changes)
    return freeze_fx_trial_roster_lab(**arguments)


def decisions(locked):
    rows = json.loads(locked.canonical_json)["slots"]
    return [TrialDecision(
        opportunity_id=row["id"], side="AGUARDAR",
        recorded_at=DECISION_AT, evidence_cutoff_at=PLAN_AT,
        baseline_eligible=False, regime_veto=None,
        abstention_reason="MISSING_DATA", evidence_sha256_claim=None,
        model_version=VERSION,
    ) for row in rows]


def census(locked, ds=None, at=FREEZE_AT):
    return freeze_full_fx_direction_census_lab(
        locked, decisions(locked) if ds is None else ds, census_frozen_at=at)


def mutate(ds, idx=0, **changes):
    new = list(ds)
    new[idx] = replace(new[idx], **changes)
    return new


class TrialCensusTests(unittest.TestCase):
    def setUp(self):
        self.roster_out = plan()
        self.roster = self.roster_out["frozen"]
        self.ds = decisions(self.roster)

    def safe(self, out):
        self.assertEqual(out["operational_bias"], "AGUARDAR")
        self.assertFalse(out["publishable"])
        self.assertFalse(out["trade_authorized"])
        self.assertFalse(out["live_alert_allowed"])
        self.assertFalse(out["worker_enabled"])
        self.assertFalse(out["scheduler_enabled"])
        self.assertFalse(out["external_precommit_timestamp_verified"])
        self.assertFalse(out["source_vintages_authenticated"])
        self.assertFalse(out["real_market_outcomes_loaded"])
        self.assertFalse(out["directional_accuracy_validated"])
        self.assertIsNone(out["validated_accuracy"])
        self.assertIsNone(out["calibrated_direction_probability"])
        self.assertEqual((out["http_requests"], out["file_writes"], out["new_cost_brl"]), (0, 0, 0))

    def test_canonical_complete_56_roster(self):
        self.assertEqual(self.roster_out["state"], "LAB_ROSTER_HASHED_UNATTESTED")
        doc = json.loads(self.roster.canonical_json)
        self.assertEqual(len(doc["slots"]), 56)
        self.assertEqual({r["asset"] for r in doc["slots"]}, set(OFFICIAL_PAIRS))
        self.assertEqual({(r["asset"], r["horizon"]) for r in doc["slots"]},
                         {(p, t) for p in OFFICIAL_PAIRS for t in ("D1", "W1")})
        self.assertEqual(len({r["id"] for r in doc["slots"]}), 56)
        self.safe(self.roster_out)

    def test_repeat_deterministic_hash(self):
        self.assertEqual(self.roster, plan()["frozen"])
        self.assertEqual(self.roster.sha256, sha256(self.roster.canonical_json.encode()).hexdigest())

    def test_roster_different_dates_different_hash(self):
        changed = windows()
        changed["W1"] = (W1_START + timedelta(days=7), W1_START + timedelta(days=14))
        self.assertNotEqual(self.roster.sha256,
                            plan(target_windows_by_horizon=changed)["sha256"])

    def test_roster_different_version_different_hash(self):
        self.assertNotEqual(self.roster.sha256, plan(rule_version="atlasquant-research-v2")["sha256"])

    def test_roster_different_campaign_different_hash(self):
        self.assertNotEqual(self.roster.sha256, plan(cohort_id="LABC20261110")["sha256"])

    def test_plan_invalid_schemas(self):
        for wrong in ({"D1": windows()["D1"]}, {}, None, [], "D1"):
            with self.subTest(wrong=wrong):
                v=plan(target_windows_by_horizon=wrong)
                self.assertEqual(v["state"], "LAB_BLOCKED")
                self.safe(v)

    def test_invalid_plan_clock(self):
        for wrong in (PLAN_AT.replace(tzinfo=None), "2026-11-09", PLAN_AT.replace(microsecond=1)):
            self.assertEqual(plan(plan_frozen_at=wrong)["state"], "LAB_BLOCKED")

    def test_invalid_roster_ids_and_versions(self):
        for change in ({"cohort_id": "bad lowercase"}, {"cohort_id": "AA"},
                       {"rule_version": ""}, {"rule_version": "v"},
                       {"rule_version": []}):
            with self.subTest(change=change):
                self.assertEqual(plan(**change)["state"], "LAB_BLOCKED")

    def test_roster_durations_and_order(self):
        for change in (
            {"D1": (D1_START, D1_START + timedelta(hours=23)), "W1": windows()["W1"]},
            {"D1": (PLAN_AT, PLAN_AT + timedelta(days=1)), "W1": windows()["W1"]},
            {"D1": (D1_START, D1_START + timedelta(days=1)), "W1": (W1_START, W1_START)},
        ):
            self.assertEqual(plan(target_windows_by_horizon=change)["state"], "LAB_BLOCKED")

    def test_complete_abstention_counting(self):
        out=census(self.roster)
        self.assertEqual(out["state"], "LAB_FULL_CENSUS_HASHED_UNATTESTED")
        self.assertEqual((out["slots_recorded"], out["awaiting_count"],
                          out["hypotheses_count"]), (56,56,0))
        self.assertEqual(out["per_horizon"]["D1"]["AGUARDAR"], 28)
        self.assertEqual(out["per_horizon"]["W1"]["AGUARDAR"], 28)
        self.assertTrue(out["full_28fx_d1_w1_roster_checked"])
        self.safe(out)

    def test_full_census_verify_against_roster(self):
        out=census(self.roster)
        other=verify_frozen_fx_census_lab(self.roster, out["frozen"])
        self.assertEqual(other["sha256"], out["sha256"])
        self.assertEqual(other["state"], out["state"])
        self.safe(other)

    def test_reordered_input_is_canonical(self):
        self.assertEqual(census(self.roster, self.ds)["sha256"],
                         census(self.roster, list(reversed(self.ds)))["sha256"])

    def test_single_missing_slot_blocks_everything(self):
        out=census(self.roster,self.ds[:-1])
        self.assertEqual(out["reason"], "MISSING_OR_EXTRA_CENSUS_SLOT")
        self.assertIsNone(out["frozen"])
        self.safe(out)

    def test_duplicate_id_blocks_even_56_rows(self):
        out=census(self.roster,self.ds[:-1]+[self.ds[0]])
        self.assertEqual(out["reason"], "DUPLICATE_OR_INVALID_SLOT_DECISION")
        self.safe(out)

    def test_fake_id_not_same_roster(self):
        bad=mutate(self.ds,opportunity_id="LABC20261109_EURUSD_M15")
        out=census(self.roster,bad)
        self.assertEqual(out["reason"], "CENSUS_IDS_DIFFER_FROM_PREDECLARED_ROSTER")
        self.safe(out)

    def test_recorded_time_after_freeze_blocks(self):
        out=census(self.roster,mutate(self.ds,recorded_at=FREEZE_AT+timedelta(seconds=1)))
        self.assertEqual(out["reason"],"INVALID_OR_LATE_DECISION_OR_EVIDENCE")
        self.safe(out)

    def test_recorded_before_plan_blocks(self):
        out=census(self.roster,mutate(self.ds,recorded_at=PLAN_AT-timedelta(seconds=1)))
        self.assertEqual(out["state"],"LAB_BLOCKED")

    def test_evidence_after_decision_blocks(self):
        out=census(self.roster,mutate(self.ds,evidence_cutoff_at=FREEZE_AT+timedelta(seconds=1)))
        self.assertEqual(out["state"],"LAB_BLOCKED")

    def test_no_freeze_after_target_began(self):
        out=census(self.roster,at=D1_START)
        self.assertEqual(out["reason"],"INVALID_OR_LATE_DECISION_OR_EVIDENCE")

    def test_naive_and_microsecond_clock_blocks(self):
        for changes in ({"recorded_at":DECISION_AT.replace(tzinfo=None)},
                        {"recorded_at":DECISION_AT.replace(microsecond=13)},
                        {"evidence_cutoff_at":"2026-11-09"}):
            with self.subTest(changes=changes):
                self.assertEqual(census(self.roster,mutate(self.ds,**changes))["state"],"LAB_BLOCKED")

    def test_wait_reason_mandatory(self):
        for wrong in (None,"", "BROKER_IS_GOOD", [], True):
            with self.subTest(wrong=wrong):
                self.assertEqual(census(self.roster,mutate(self.ds,abstention_reason=wrong))["state"],"LAB_BLOCKED")

    def test_wait_cannot_claim_eligibility_or_regime(self):
        for changes in ({"baseline_eligible":True}, {"regime_veto":True}):
            with self.subTest(changes=changes):
                self.assertEqual(census(self.roster,mutate(self.ds,**changes))["state"],"LAB_BLOCKED")

    def test_direction_must_have_source_hash(self):
        for wrong in (None,"bad", "A"*64, [], True):
            with self.subTest(wrong=wrong):
                out=census(self.roster,mutate(self.ds,side="ALTA",baseline_eligible=True,
                                              regime_veto=False,abstention_reason=None,
                                              evidence_sha256_claim=wrong))
                self.assertEqual(out["state"],"LAB_BLOCKED")

    def test_direction_success_and_full_coverage(self):
        ds=mutate(self.ds,side="ALTA",baseline_eligible=True,regime_veto=False,
                  abstention_reason=None,evidence_sha256_claim="a"*64)
        ds=mutate(ds,1,side="BAIXA",baseline_eligible=True,regime_veto=True,
                  abstention_reason=None,evidence_sha256_claim="b"*64)
        out=census(self.roster,ds)
        self.assertEqual((out["awaiting_count"],out["hypotheses_count"],
                          out["baseline_eligible_count"],out["regime_veto_count"]),
                         (54,2,2,1))
        self.assertEqual(out["per_horizon"]["D1"]["ALTA"],1)
        self.assertEqual(out["per_horizon"]["D1"]["BAIXA"],1)
        self.assertEqual(verify_frozen_fx_census_lab(self.roster,out["frozen"])["state"],out["state"])
        self.safe(out)

    def test_noneligible_direction_requires_reason_and_no_veto(self):
        args=dict(side="ALTA",baseline_eligible=False,regime_veto=None,
                  evidence_sha256_claim="a"*64,abstention_reason="MACRO_CONTRADICTION")
        out=census(self.roster,mutate(self.ds,**args))
        self.assertEqual(out["state"],"LAB_FULL_CENSUS_HASHED_UNATTESTED")
        for changes in ({"abstention_reason":None}, {"regime_veto":False}):
            self.assertEqual(census(self.roster,mutate(self.ds,**{**args,**changes}))["state"],"LAB_BLOCKED")

    def test_version_cannot_change(self):
        self.assertEqual(census(self.roster,mutate(self.ds,model_version="changed"))["state"],"LAB_BLOCKED")

    def test_invalid_types_fail_closed(self):
        for changes in ({"side":[]}, {"baseline_eligible":1},
                        {"regime_veto":0}, {"opportunity_id":[]},
                        {"recorded_at":None}, {"evidence_sha256_claim":["a"]}):
            with self.subTest(changes=changes):
                self.assertEqual(census(self.roster,mutate(self.ds,**changes))["state"],"LAB_BLOCKED")

    def test_census_body_byte_tampering(self):
        original=census(self.roster)["frozen"]
        changed=original.canonical_json.replace("MISSING_DATA","STALE_DATA",1)
        self.assertEqual(verify_frozen_fx_census_lab(self.roster,FrozenBlob(changed,original.sha256))["state"],"LAB_BLOCKED")

    def test_even_rehashed_tamper_cannot_hide_noncanonical_order(self):
        original=census(self.roster)["frozen"]
        changed=original.canonical_json.replace('"abstention_reason":"MISSING_DATA"',
                                                 '"abstention_reason": "MISSING_DATA"',1)
        forged=FrozenBlob(changed,sha256(changed.encode()).hexdigest())
        self.assertEqual(verify_frozen_fx_census_lab(self.roster,forged)["state"],"LAB_BLOCKED")

    def test_rehash_of_edited_valid_census_cannot_prove_old_timestamp(self):
        original=census(self.roster)["frozen"]
        data=json.loads(original.canonical_json)
        data["decisions"][0]["abstention_reason"]="STALE_DATA"
        forged_json=json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=True)
        forged=FrozenBlob(forged_json,sha256(forged_json.encode()).hexdigest())
        # This is structurally consistent and MUST NOT be called independently witnessed.
        result=verify_frozen_fx_census_lab(self.roster,forged)
        self.assertEqual(result["state"],"LAB_FULL_CENSUS_HASHED_UNATTESTED")
        self.assertFalse(result["external_precommit_timestamp_verified"])
        self.assertNotEqual(forged.sha256,original.sha256)

    def test_wrong_roster_rejects_census_even_if_both_valid(self):
        original=census(self.roster)["frozen"]
        different=plan(cohort_id="LABC20261110")["frozen"]
        self.assertEqual(verify_frozen_fx_census_lab(different,original)["state"],"LAB_BLOCKED")

    def test_roster_tamper_rejected(self):
        damaged=FrozenBlob(self.roster.canonical_json.replace("EURUSD","GBPUSD",1),self.roster.sha256)
        self.assertEqual(census(damaged)["state"],"LAB_BLOCKED")

    def test_invalid_census_input(self):
        for wrong in (None,{},"forecast",FrozenBlob("[]","a"*64)):
            with self.subTest(wrong=wrong):
                self.assertEqual(verify_frozen_fx_census_lab(self.roster,wrong)["state"],"LAB_BLOCKED")

    def test_no_real_accuracy_just_registry(self):
        out=census(self.roster)
        self.assertIsNone(out["validated_accuracy"])
        self.assertFalse(out["real_market_outcomes_loaded"])
        self.assertFalse(out["external_precommit_timestamp_verified"])
        self.assertTrue(out["research_only"])
        self.safe(out)


    def test_weekly_dst_168_hour_target_is_blocked_before_any_decisions(self):
        examples = (
            ("2026-03-01T22:00:00+00:00", "2026-02-27T12:00:00+00:00"),
            ("2026-10-25T21:00:00+00:00", "2026-10-23T12:00:00+00:00"),
        )
        for weekly_text, plan_text in examples:
            with self.subTest(weekly=weekly_text):
                weekly = datetime.fromisoformat(weekly_text)
                planned = datetime.fromisoformat(plan_text)
                schedule = {
                    "D1": (weekly + timedelta(days=10), weekly + timedelta(days=11)),
                    "W1": (weekly, weekly + timedelta(days=7)),
                }
                outcome = plan(target_windows_by_horizon=schedule, plan_frozen_at=planned)
                self.assertEqual(outcome["reason"],
                                 "W1_NY17_DST_CLOSE_REQUIRES_BROKER_VERIFICATION")
                self.assertIsNone(outcome["frozen"])
                self.safe(outcome)


if __name__ == "__main__":
    unittest.main()
