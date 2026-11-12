"""Offline synthetic-only test of policy expectations -> D1/W1 FX research veto."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_policy_expectations_conflict_lab import RateExpectationVintage
from atlasquant_trader_policy_join_veto_lab import inspect_policy_veto_for_fx_join_lab as review

UTC=timezone.utc
W=datetime(2026,11,3,12,tzinfo=UTC)
D=datetime(2026,11,5,12,tzinfo=UTC)
NOW=datetime(2026,11,5,18,tzinfo=UTC)

@dataclass(frozen=True)
class Candidate:
    asset: str="EUR/USD"
    horizon: str="D1"
    daily: str="ALTA"
    weekly: str="ALTA"
    evaluated_at: datetime=NOW


def vintages(currency, change, cutoff):
    old=cutoff-timedelta(days=4)
    new=cutoff-timedelta(days=1)
    def v(at, value, sha):
        return RateExpectationVintage(
            currency,at,at+timedelta(minutes=5),"2027-02",3,str(value),
            f"{currency}:OIS3M", "IMPLIED_POLICY_RATE_3M_BPS_RESEARCH_CLAIM",sha*64)
    return [v(old,300,"a"),v(new,300+change,"b")]

def rates(usd_move=20, eur_move=0):
    snapshots={}
    for h,cutoff in (("W1",W),("D1",D)):
        snapshots[h]={c:vintages(c, usd_move if c=="USD" else eur_move if c=="EUR" else 0, cutoff) for c in CURRENCIES}
    return snapshots

class JoinTests(unittest.TestCase):
    def case(self, candidate=None, snapshots=None, **kw):
        return review(candidate=candidate or Candidate(),
                      snapshots_by_horizon=rates() if snapshots is None else snapshots,
                      decision_at_by_horizon={"W1":W,"D1":D},as_of_utc=NOW,**kw)
    def safety(self, result):
        self.assertEqual(result['operational_bias'],'AGUARDAR')
        self.assertFalse(result['publishable'])
        self.assertFalse(result['live_alert_allowed'])
        self.assertFalse(result['trade_authorized'])
        self.assertFalse(result['worker_enabled'])
        self.assertFalse(result['scheduler_enabled'])
        self.assertFalse(result['rate_path_source_independently_authenticated'])
        self.assertFalse(result['rate_instruments_independently_comparable'])
        self.assertFalse(result['historical_rate_vintages_point_in_time_verified'])
        self.assertIsNone(result['incremental_direction_accuracy_validated'])
        self.assertIsNone(result['calibrated_direction_probability'])
        self.assertIsNone(result['research_direction_for_publication'])
        self.assertFalse(result['documentary_alignment_is_authorization'])
        self.assertEqual((result['http_requests'],result['file_writes'],result['new_cost_brl']),(0,0,0))

    def test_contradiction_blocks(self):
        r=self.case()
        self.assertEqual(r['state'],'LAB_POLICY_JOIN_RESEARCH_VETO')
        self.assertIn('RATE_EXPECTATIONS_CONTRADICT_RESEARCH_DIRECTION',r['blockers'])
        self.assertTrue(r['research_veto'])
        self.safety(r)

    def test_agreement_does_not_authorize(self):
        r=self.case(snapshots=rates(0,20))
        self.assertEqual(r['state'],'LAB_POLICY_JOIN_NO_DOCUMENTARY_CONFLICT_NO_GO')
        self.assertFalse(r['research_veto'])
        self.safety(r)

    def test_no_rate_input_is_a_veto(self):
        r=self.case(snapshots={})
        self.assertTrue(r['research_veto'])
        self.safety(r)
        r=review(candidate=Candidate(),snapshots_by_horizon=None,
                 decision_at_by_horizon={'D1':D,'W1':W},as_of_utc=NOW)
        self.assertEqual(r['blockers'],['RATE_EXPECTATION_SNAPSHOTS_NOT_SUPPLIED'])
        self.safety(r)

    def test_missing_eur_only_vetoes_its_pair(self):
        s=rates();s['D1']['EUR']=[]
        r=self.case(snapshots=s)
        self.assertIn('RATE_EXPECTATIONS_MISSING_STALE_OR_INCOMPARABLE',r['blockers'])
        self.safety(r)
        r=self.case(candidate=Candidate(asset='USD/JPY'), snapshots=s)
        self.assertFalse(r['research_veto'])
        self.safety(r)

    def test_conflict_and_missing_are_both_reported(self):
        s=rates();s['D1']['EUR']=[]
        r=self.case(snapshots=s)
        self.assertEqual(len(r['blockers']),2)
        self.safety(r)

    def test_reused_future_daily_snapshot_cannot_validate_weekly(self):
        s=rates()
        s['W1']['EUR']=s['D1']['EUR']
        r=self.case(snapshots=s)
        self.assertTrue(r['research_veto'])
        self.assertIn('RATE_EXPECTATIONS_MISSING_STALE_OR_INCOMPARABLE',r['blockers'])
        self.safety(r)

    def test_misaligned_direction_vetoes_before_rates(self):
        r=self.case(candidate=Candidate(weekly='BAIXA'))
        self.assertEqual(r['blockers'],['D1_W1_DIRECTION_CONTRADICTION'])
        self.safety(r)

    def test_reject_naive_future_invalid_timeline(self):
        for candidate in (Candidate(evaluated_at=NOW+timedelta(seconds=1)), Candidate(evaluated_at=NOW.replace(tzinfo=None))):
            with self.subTest(candidate=candidate):
                self.safety(self.case(candidate=candidate))
        r=review(candidate=Candidate(),snapshots_by_horizon=rates(),
                 decision_at_by_horizon={'D1':W,'W1':D},as_of_utc=NOW)
        self.assertIn('RATE_HORIZON_CUTOFF_ORDER_OR_FUTURE',r['blockers'])
        self.safety(r)

    def test_all_28_pairs_always_no_live_direction(self):
        for asset in OFFICIAL_PAIRS:
            with self.subTest(asset=asset):
                r=self.case(candidate=Candidate(asset=asset))
                self.safety(r)
        for asset in ('WIN','WDO','US500','NAS100','US30'):
            self.assertEqual(self.case(candidate=Candidate(asset=asset))['reason'],
                             'OUTSIDE_FX_28_OR_INDEX_REQUIRES_OWN_MODEL')

    def test_neutral_and_bad_payload_veto(self):
        for bad in ('NEUTRO',None, 123):
            with self.subTest(v=bad):
                self.safety(self.case(candidate=Candidate(daily=bad)))
        self.safety(self.case(snapshots={'D1':None,'W1':None}))

    def test_exact_differential_threshold_and_small_change(self):
        r=self.case(snapshots=rates(5,0))
        self.assertTrue(r['research_veto'])
        self.safety(r)
        r=self.case(snapshots=rates(4,0))
        self.assertFalse(r['research_veto'])  # no documentary conflict, not a live signal
        self.safety(r)

if __name__=='__main__':unittest.main()
