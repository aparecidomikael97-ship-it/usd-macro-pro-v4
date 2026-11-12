"""Synthetic tests: multi-cohort ledger cannot cherry-pick individual rounds."""
from dataclasses import replace
from datetime import timedelta
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_trial_census_lab import (
    freeze_fx_trial_roster_lab, freeze_full_fx_direction_census_lab,
)
from test_atlasquant_trader_fx_trial_census_lab import (
    PLAN_AT, D1_START, W1_START, VERSION, decisions, mutate,
)
from atlasquant_trader_mt5_paired_outcome_bridge_lab import RecordedFxHypothesis
from atlasquant_trader_fx_multicohort_ledger_lab import (
    FrozenFxCohort, build_full_fx_multicohort_ledger_lab as ledger,
)

NOW = PLAN_AT + timedelta(days=14 * 260)


def make_cohort(i, *, mode="selective", same_target=False, version=VERSION,
                lock_backdated=False):
    off = timedelta(days=0 if same_target else 14 * i)
    at = PLAN_AT + (timedelta(hours=6) if same_target else timedelta(days=14 * i))
    cid = f"LABC26_{i:03d}"
    ros = freeze_fx_trial_roster_lab(
        cohort_id=cid, rule_version=version, plan_frozen_at=at,
        target_windows_by_horizon={
            "D1": (D1_START + off, D1_START + off + timedelta(days=1)),
            "W1": (W1_START + off, W1_START + off + timedelta(days=7)),
        },
    )["frozen"]
    assert ros is not None
    ds = decisions(ros)
    ds = [replace(d, recorded_at=at+timedelta(hours=1), evidence_cutoff_at=at, model_version=version)
          for d in ds]
    if mode != "wait":
        chosen = range(56) if mode == "all" else (0, 1, 28)
        for j in chosen:
            ds = mutate(ds, j, side=("ALTA" if j%2==0 else "BAIXA"),
                        baseline_eligible=True, regime_veto=(j==1),
                        abstention_reason=None, evidence_sha256_claim="a"*64)
    census = freeze_full_fx_direction_census_lab(
        ros, ds, census_frozen_at=at+timedelta(hours=2))["frozen"]
    assert census is not None
    import json
    from datetime import datetime
    rs = json.loads(ros.canonical_json)["slots"]
    hs = []
    for slot, dec in zip(rs, ds):
        if not dec.baseline_eligible:
            continue
        locked = at - timedelta(minutes=1) if lock_backdated else at+timedelta(minutes=50)
        hs.append(RecordedFxHypothesis(
            opportunity_id=slot["id"], asset=slot["asset"],
            horizon=slot["horizon"], candidate_direction=dec.side,
            prediction_locked_at=locked, decided_at=dec.recorded_at,
            regime_observed_at=at+timedelta(minutes=10),
            target_open_epoch=int(datetime.fromisoformat(
                slot["target_open_utc"].replace("Z", "+00:00")).timestamp()),
            baseline_eligible=True, regime_veto=dec.regime_veto,
            decision_sha256_claim="b"*64, regime_source_sha256_claim="c"*64,
        ))
    return FrozenFxCohort(ros,census,tuple(hs)),cid


def pack(n=3, *, mode="selective"):
    rows=[make_cohort(i, mode=mode) for i in range(n)]
    return tuple(x[0] for x in rows), tuple(x[1] for x in rows)


def run(cohorts=None, ids=None, now=NOW):
    originals, manifest = pack()
    return ledger(originals if cohorts is None else cohorts,
                  expected_cohort_ids=manifest if ids is None else ids,
                  as_of_utc=now)


class MultiCohortLedgerTests(unittest.TestCase):
    def safe(self,r):
        self.assertEqual(r["operational_bias"],"AGUARDAR")
        for f in ("trade_authorized","publishable","live_alert_allowed",
                  "external_cohort_manifest_precommitted",
                  "external_roster_or_census_anchors_verified",
                  "macro_source_vintages_authenticated","mt5_prices_loaded",
                  "paired_outcomes_evaluated","broker_calendar_authenticated"):
            self.assertFalse(r[f],f)
        self.assertIsNone(r["validated_directional_accuracy"])
        self.assertIsNone(r["calibrated_direction_probability"])
        self.assertEqual((r["http_requests"],r["file_writes"],r["new_cost_brl"]),(0,0,0))

    def test_three_cohorts_full_168_slots_even_with_waits(self):
        r=run()
        self.assertEqual(r["state"],"LAB_ALL_DECLARED_FX_COHORTS_RECONCILED_DOCUMENTARY_NO_GO")
        self.assertEqual((r["cohorts_verified"],r["slots_verified"],r["slots_expected"]),(3,168,168))
        self.assertEqual((r["awaiting_count"],r["baseline_eligible_count"],r["regime_vetoed_count"]),(159,9,3))
        self.assertEqual(len(r["groups"]),56)
        self.assertTrue(r["full_declared_cohort_manifest_reconciled"])
        self.safe(r)

    def test_group_separates_forex_and_timeframes(self):
        r=run()
        a=next(g for g in r["groups"] if g.asset==OFFICIAL_PAIRS[0] and g.horizon=="D1")
        b=next(g for g in r["groups"] if g.asset==OFFICIAL_PAIRS[0] and g.horizon=="W1")
        self.assertEqual((len(a.hypotheses),len(b.hypotheses)),(3,3))
        self.assertEqual(len(a.expected_opportunity_ids),3)
        self.assertTrue(all(h.horizon=="D1" for h in a.hypotheses))
        self.assertEqual(len({h.target_open_epoch for h in a.hypotheses}),3)
        self.assertEqual(len({(g.asset,g.horizon) for g in r["groups"]}),56)
        self.safe(r)

    def test_vetoed_candidates_preserved(self):
        r=run()
        self.assertEqual(r["regime_vetoed_count"],3)
        self.assertEqual(r["regime_retained_count"],6)
        groups=[g for g in r["groups"] if g.regime_vetoed_count]
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0].hypotheses),3)
        self.safe(r)

    def test_all_waits_counted_and_zero_accuracy(self):
        cs, ids=pack(mode="wait")
        r=run(cs,ids)
        self.assertEqual(r["state"],"LAB_ALL_DECLARED_FX_COHORTS_RECONCILED_DOCUMENTARY_NO_GO")
        self.assertEqual((r["awaiting_count"],r["baseline_eligible_count"]),(168,0))
        self.assertTrue(all(not g.hypotheses for g in r["groups"]))
        self.safe(r)

    def test_all_eligible_has_168_candidates(self):
        cs,ids=pack(mode="all")
        r=run(cs,ids)
        self.assertEqual(r["baseline_eligible_count"],168)
        self.assertEqual(sum(len(g.hypotheses) for g in r["groups"]),168)
        self.safe(r)

    def test_missed_cohort_blocked(self):
        cs,ids=pack()
        r=run(cs[:-1],ids)
        self.assertEqual(r["reason"],"INVALID_OR_INCOMPLETE_DECLARED_COHORT_MANIFEST")
        self.safe(r)

    def test_undeclared_cohort_blocked(self):
        cs,ids=pack()
        self.assertEqual(run(cs,ids[:-1]+("OTHER123",))["reason"],"UNKNOWN_OR_DUPLICATE_COHORT")

    def test_repeated_id_blocked(self):
        cs,ids=pack()
        r=run(cs,ids[:2]+(ids[1],))
        self.assertEqual(r["reason"],"INVALID_OR_INCOMPLETE_DECLARED_COHORT_MANIFEST")

    def test_manifest_order_must_match_actual_sequence(self):
        cs,ids=pack()
        self.assertEqual(run(cs,tuple(reversed(ids)))["reason"],"DECLARED_COHORT_SEQUENCE_MISMATCH")

    def test_reused_entire_cohort_blocked(self):
        cs,ids=pack()
        self.assertEqual(run(cs[:2]+(cs[1],),ids)["reason"],"UNKNOWN_OR_DUPLICATE_COHORT")

    def test_reordering_cohorts_blocked_not_silently_sorted(self):
        cs,ids=pack()
        self.assertEqual(run(tuple(reversed(cs)),ids)["reason"],"DECLARED_COHORT_SEQUENCE_MISMATCH")

    def test_removed_vetoed_candidate_blocks_all(self):
        cs,ids=pack()
        changed=replace(cs[1],hypotheses=tuple(h for h in cs[1].hypotheses if not h.regime_veto))
        r=run((cs[0],changed,cs[2]),ids)
        self.assertEqual(r["reason"],"INDIVIDUAL_COHORT_CENSUS_OR_PAIRED_MISMATCH")
        self.safe(r)

    def test_changed_rule_version_blocks(self):
        cs,ids=pack()
        replacement,_=make_cohort(1,version="atlasquant-research-v2")
        self.assertEqual(run((cs[0],replacement,cs[2]),ids)["reason"],"RULE_VERSION_CHANGED_WITHIN_FIXED_COHORT_SET")

    def test_reused_target_date_even_under_new_id_blocks(self):
        # Distinct plans created on different dates, but retargeting a prior
        # D1/W1 candle is forbidden within this campaign.
        cs,ids=pack()
        revised,_=make_cohort(1,same_target=True)
        self.assertEqual(run((cs[0],revised,cs[2]),ids)["reason"],"DUPLICATE_TARGET_CANDLE_ACROSS_COHORTS")

    def test_future_plan_blocks(self):
        cs,ids=pack()
        self.assertEqual(run(cs,ids,now=PLAN_AT)["state"],"LAB_MULTI_COHORT_LEDGER_BLOCKED")

    def test_prediction_lock_before_plan_blocks_all(self):
        cs,ids=pack()
        bad,_=make_cohort(2,lock_backdated=True)
        r=run((cs[0],cs[1],bad),ids)
        self.assertEqual(r["reason"],"INDIVIDUAL_COHORT_CENSUS_OR_PAIRED_MISMATCH")

    def test_invalid_clock_and_manifest_types(self):
        cs,ids=pack()
        for now in (None, NOW.replace(tzinfo=None),"2026-11-09", NOW+timedelta(microseconds=1)):
            self.assertEqual(run(cs,ids,now=now)["state"],"LAB_MULTI_COHORT_LEDGER_BLOCKED")
        for bad in ([],["x"],tuple([ids[0],ids[0],ids[2]])):
            self.assertEqual(run(cs,bad)["state"],"LAB_MULTI_COHORT_LEDGER_BLOCKED")
        self.safe(run(cs,ids))

    def test_corrupt_census_blocks_full_campaign(self):
        cs,ids=pack()
        bad=replace(cs[1],census=replace(cs[1].census,sha256="0"*64))
        r=run((cs[0],bad,cs[2]),ids)
        self.assertEqual(r["reason"],"INDIVIDUAL_COHORT_CENSUS_OR_PAIRED_MISMATCH")

    def test_hypothesis_order_deterministic(self):
        cs,ids=pack()
        reversed_packet=replace(cs[1],hypotheses=tuple(reversed(cs[1].hypotheses)))
        a=run(cs,ids)
        b=run((cs[0],reversed_packet,cs[2]),ids)
        self.assertEqual(a,b)
        self.safe(b)

    def test_more_than_40_cohorts_supported_for_future_sample_size(self):
        cs,ids=pack(41,mode="wait")
        r=run(cs,ids)
        self.assertEqual(r["state"],"LAB_ALL_DECLARED_FX_COHORTS_RECONCILED_DOCUMENTARY_NO_GO")
        self.assertEqual(r["slots_verified"],41*56)
        self.assertEqual(len(r["groups"]),56)
        self.safe(r)

    def test_max_cohorts_blocks(self):
        cs,ids=pack()
        r=run(cs*81,ids*81)
        self.assertEqual(r["state"],"LAB_MULTI_COHORT_LEDGER_BLOCKED")

if __name__ == "__main__":
    unittest.main()
