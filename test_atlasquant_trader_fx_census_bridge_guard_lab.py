"""Synthetic-only 56-trial census-to-paired regression: no real FX outcomes."""
from dataclasses import replace
from datetime import timedelta
import json
import unittest

from test_atlasquant_trader_fx_trial_census_lab import (
    FREEZE_AT, PLAN_AT, VERSION, plan, decisions, mutate, census,
)
from atlasquant_trader_mt5_paired_outcome_bridge_lab import RecordedFxHypothesis
from atlasquant_trader_fx_census_bridge_guard_lab import reconcile_full_fx_census_paired_lab as inspect


def fixture(mode="some"):
    p=plan()["frozen"]
    rows=decisions(p)
    if mode in ("some", "all"):
        limit=56 if mode=="all" else 3
        for i in range(limit):
            rows=mutate(rows, i,
                side="ALTA" if i%2==0 else "BAIXA",
                baseline_eligible=True, regime_veto=(i%3==1),
                abstention_reason=None, evidence_sha256_claim="a"*64)
    if mode=="noneligible":
        rows=mutate(rows, 0,side="BAIXA",baseline_eligible=False,
                    regime_veto=None,abstention_reason="MACRO_CONTRADICTION",
                    evidence_sha256_claim="a"*64)
        rows=mutate(rows, 1,side="ALTA",baseline_eligible=True,
                    regime_veto=True,abstention_reason=None,evidence_sha256_claim="b"*64)
    c=census(p,rows)["frozen"]
    pdoc=json.loads(p.canonical_json)
    cdoc=json.loads(c.canonical_json)
    hyps=[]
    for slot,d in zip(pdoc["slots"],cdoc["decisions"]):
        if not d["baseline_eligible"]:
            continue
        recorded=PLAN_AT+timedelta(hours=1)
        target=int(__import__("datetime").datetime.fromisoformat(
            slot["target_open_utc"].replace("Z","+00:00")).timestamp())
        hyps.append(RecordedFxHypothesis(
            opportunity_id=slot["id"],asset=slot["asset"],horizon=slot["horizon"],
            candidate_direction=d["side"],prediction_locked_at=recorded-timedelta(minutes=1),
            decided_at=recorded,regime_observed_at=recorded-timedelta(minutes=2),
            target_open_epoch=target,baseline_eligible=True,regime_veto=d["regime_veto"],
            decision_sha256_claim="c"*64,regime_source_sha256_claim="d"*64,
        ))
    return p,c,hyps


def run(p=None,c=None,hs=None,mode="some",asof=FREEZE_AT):
    a,b,h=fixture(mode)
    return inspect(a if p is None else p,b if c is None else c,
                   h if hs is None else hs,as_of_utc=asof)


class CensusPairedGuardTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for x in ("publishable","trade_authorized","live_alert_allowed",
                  "scheduler_enabled","worker_enabled","historical_outcomes_loaded",
                  "externally_anchored_forecasts_verified",
                  "independent_broker_or_macro_evidence_verified","holdout_accuracy_verified",
                  "benchmark_sufficient_sample"):
            self.assertIs(r[x],False,x)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["new_cost_brl"],r["http_requests"],r["file_writes"]),(0,0,0))

    def test_complete_roster_with_three_baseline_and_waits(self):
        r=run()
        self.assertEqual(r["state"],"LAB_FULL_56_CENSUS_TO_PAIRED_COVERAGE_DOCUMENTARY_NO_GO")
        self.assertEqual((r["roster_slots_verified"],r["census_slots_verified"]),(56,56))
        self.assertEqual((r["awaiting_count"],r["baseline_eligible_count"],
                          r["regime_vetoed_count"],r["regime_retained_count"]),(53,3,1,2))
        self.assertEqual(len(r["expected_paired_ids"]),3)
        self.assertTrue(r["complete_declared_denominator_reconciled"])
        self.assertEqual(r["per_horizon_documentary"]["D1"]["total"],28)
        self.assertEqual(r["per_horizon_documentary"]["W1"]["AGUARDAR"],28)
        self.safe(r)

    def test_all_wait_zero_candidates_is_coverage_not_accuracy(self):
        r=run(mode="wait")
        self.assertEqual((r["awaiting_count"],r["baseline_eligible_count"],
                          r["hypotheses_count_matched"]),(56,0,0))
        self.assertEqual(r["expected_paired_ids"],[])
        self.safe(r)

    def test_all_56_eligible_requires_full_56_hypotheses(self):
        r=run(mode="all")
        self.assertTrue(r["complete_declared_denominator_reconciled"])
        self.assertEqual(r["hypotheses_count_matched"],56)
        self.assertEqual(r["per_horizon_documentary"]["D1"]["baseline_eligible"],28)
        self.assertEqual(r["per_horizon_documentary"]["W1"]["baseline_eligible"],28)
        self.safe(r)

    def test_exclude_directional_noneligible_but_count_separately(self):
        r=run(mode="noneligible")
        self.assertEqual((r["awaiting_count"],r["directional_baseline_ineligible_count"],
                          r["baseline_eligible_count"]),(54,1,1))
        self.assertEqual(r["regime_vetoed_count"],1)
        self.safe(r)

    def test_rejected_regime_cannot_disappear(self):
        p,c,h=fixture()
        r=inspect(p,c,[x for x in h if not x.regime_veto],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"BASELINE_ELIGIBLE_DENOMINATOR_MISMATCH_NO_SUBSETTING")
        self.assertFalse(r["complete_declared_denominator_reconciled"])
        self.safe(r)

    def test_missing_any_eligible_candidate_blocks(self):
        p,c,h=fixture()
        self.assertEqual(inspect(p,c,h[:-1],as_of_utc=FREEZE_AT)["state"],"LAB_CENSUS_PAIRED_COVERAGE_BLOCKED")

    def test_extra_wait_masquerading_as_candidate_blocks(self):
        p,c,h=fixture()
        h2=h+[replace(h[0],opportunity_id="LABC20261109_EURUSD_W1")]
        r=inspect(p,c,h2,as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"BASELINE_ELIGIBLE_DENOMINATOR_MISMATCH_NO_SUBSETTING")
        self.safe(r)

    def test_duplicate_candidate_blocks(self):
        p,c,h=fixture()
        r=inspect(p,c,h[:-1]+[h[0]],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"DUPLICATE_PAIRED_OPPORTUNITY_ID")
        self.safe(r)

    def test_wrong_side_blocks(self):
        p,c,h=fixture()
        r=inspect(p,c,[replace(h[0],candidate_direction="BAIXA")]+h[1:],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"PAIRED_SIDE_HORIZON_TARGET_OR_VETO_CHANGED")

    def test_wrong_regime_veto_blocks(self):
        p,c,h=fixture()
        r=inspect(p,c,[replace(h[0],regime_veto=True)]+h[1:],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"PAIRED_SIDE_HORIZON_TARGET_OR_VETO_CHANGED")

    def test_wrong_asset_timeframe_or_target_blocks(self):
        p,c,h=fixture()
        changes=[{"asset":"GBP/USD"},{"horizon":"W1"},
                 {"target_open_epoch":h[0].target_open_epoch+86400},
                 {"baseline_eligible":False}]
        for change in changes:
            with self.subTest(change=change):
                r=inspect(p,c,[replace(h[0],**change)]+h[1:],as_of_utc=FREEZE_AT)
                self.assertEqual(r["reason"],"PAIRED_SIDE_HORIZON_TARGET_OR_VETO_CHANGED")

    def test_changed_decision_timestamp_blocks(self):
        p,c,h=fixture()
        r=inspect(p,c,[replace(h[0],decided_at=h[0].decided_at+timedelta(minutes=1))]+h[1:],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"PAIRED_FORECAST_CLOCK_DIFFERS_FROM_FROZEN_CENSUS")

    def test_prediction_lock_before_roster_blocks(self):
        p,c,h=fixture()
        r=inspect(p,c,[replace(h[0],prediction_locked_at=PLAN_AT-timedelta(seconds=1))]+h[1:],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"PAIRED_FORECAST_CLOCK_DIFFERS_FROM_FROZEN_CENSUS")
        self.safe(r)

    def test_future_or_unordered_timestamps_block(self):
        p,c,h=fixture()
        cases=[{"prediction_locked_at":h[0].decided_at+timedelta(minutes=1)},
               {"regime_observed_at":h[0].decided_at+timedelta(minutes=1)},
               {"decided_at":FREEZE_AT+timedelta(days=2)},
               {"prediction_locked_at":h[0].prediction_locked_at.replace(tzinfo=None)},
               {"decided_at":h[0].decided_at+timedelta(microseconds=1)}]
        for change in cases:
            with self.subTest(change=change):
                r=inspect(p,c,[replace(h[0],**change)]+h[1:],as_of_utc=FREEZE_AT)
                self.assertEqual(r["reason"],"PAIRED_FORECAST_CLOCK_DIFFERS_FROM_FROZEN_CENSUS")

    def test_forged_or_invalid_census_blobs_rejected(self):
        p,c,h=fixture()
        self.assertEqual(inspect(p,replace(c,sha256="0"*64),h,as_of_utc=FREEZE_AT)["state"],"LAB_CENSUS_PAIRED_COVERAGE_BLOCKED")
        self.assertEqual(inspect(replace(p,canonical_json="{}"),c,h,as_of_utc=FREEZE_AT)["state"],"LAB_CENSUS_PAIRED_COVERAGE_BLOCKED")

    def test_census_frozen_later_than_now_rejected(self):
        p,c,h=fixture()
        r=inspect(p,c,h,as_of_utc=PLAN_AT)
        self.assertEqual(r["reason"],"CENSUS_NOT_FROZEN_BY_AS_OF")

    def test_bad_hashes_and_types_block(self):
        p,c,h=fixture()
        for invalid in ("bad", True, "A"*64):
            r=inspect(p,c,[replace(h[0],regime_source_sha256_claim=invalid)]+h[1:],as_of_utc=FREEZE_AT)
            self.assertEqual(r["reason"],"PAIRED_SOURCE_HASH_CLAIM_MALFORMED")
        r=inspect(p,c,[object()]+h[1:],as_of_utc=FREEZE_AT)
        self.assertEqual(r["reason"],"INVALID_PAIRED_HYPOTHESIS_TYPE")

    def test_order_independent_and_reproducible(self):
        p,c,h=fixture()
        x=inspect(p,c,h,as_of_utc=FREEZE_AT)
        y=inspect(p,c,list(reversed(h)),as_of_utc=FREEZE_AT)
        self.assertEqual(x,y)
        self.safe(y)

    def test_requires_all_slots_before_any_metric(self):
        p,c,h=fixture()
        r=inspect(p,c,h,as_of_utc=FREEZE_AT)
        self.assertFalse(r["benchmark_sufficient_sample"])
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertFalse(r["historical_outcomes_loaded"])
        self.safe(r)


if __name__ == "__main__": unittest.main()
