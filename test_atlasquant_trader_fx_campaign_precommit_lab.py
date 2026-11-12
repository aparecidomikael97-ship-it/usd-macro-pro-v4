"""Synthetic P0 checks: campaign plan before cohorts, no trading or price IO."""
from dataclasses import replace
from datetime import timedelta, timezone
import json
import unittest

from test_atlasquant_trader_fx_multicohort_ledger_lab import (
    NOW, PLAN_AT, VERSION, pack, make_cohort,
)
from atlasquant_trader_fx_trial_census_lab import FrozenBlob
from atlasquant_trader_fx_campaign_precommit_lab import (
    PlannedFxCohort, freeze_fx_campaign_schedule_lab as freeze,
    prepare_campaign_github_anchor_lab as anchor,
    bind_campaign_to_fx_ledger_lab as bind,
)

CAMPAIGN_AT = PLAN_AT - timedelta(hours=5)


def schedule_for(cohorts, *, at=CAMPAIGN_AT, version=VERSION):
    slots = []
    for packet in cohorts:
        doc = json.loads(packet.roster.canonical_json)
        d = doc['slots'][0]
        w = doc['slots'][28]
        def iso(t):
            return __import__('datetime').datetime.fromisoformat(t.replace('Z','+00:00'))
        slots.append(PlannedFxCohort(
            doc['cohort_id'], iso(d['target_open_utc']), iso(d['target_close_utc']),
            iso(w['target_open_utc']), iso(w['target_close_utc'])))
    return freeze(campaign_id='CAMPAIGN26A',rule_version=version,
                  scheduled=slots,frozen_at=at)


class ProspectiveCampaignTests(unittest.TestCase):
    def safe(self, r):
        for key in ('external_campaign_precommitment_verified',
                    'external_cohort_manifest_precommitted',
                    'broker_calendar_authenticated',
                    'genuine_forecasts_pre_event_verified','source_vintages_authenticated',
                    'trade_authorized','publishable','live_alert_allowed',
                    'worker_enabled','scheduler_enabled'):
            self.assertFalse(r[key],key)
        self.assertIsNone(r['validated_directional_accuracy'])
        self.assertIsNone(r['calibrated_direction_probability'])
        self.assertEqual(r['operational_bias'],'AGUARDAR')
        self.assertEqual((r['http_requests'],r['file_writes'],r['new_cost_brl']),(0,0,0))

    def test_freeze_three_cohorts_before_first_roster(self):
        cs,_=pack(); s=schedule_for(cs)
        self.assertEqual(s['state'],'LAB_CAMPAIGN_SCHEDULE_HASHED_UNATTESTED')
        self.assertEqual((s['scheduled_cohorts'],s['declared_slots']),(3,168))
        self.assertEqual(len(s['sha256']),64)
        self.safe(s)

    def test_binding_passes_only_when_all_cohorts_match_schedule(self):
        cs,_=pack(); schedule=schedule_for(cs)['frozen']
        r=bind(schedule,cs,as_of_utc=NOW)
        self.assertEqual(r['state'],'LAB_FROZEN_CAMPAIGN_MATCHES_ALL_COHORTS_DOCUMENTARY_NO_GO')
        self.assertEqual(r['ledger']['slots_verified'],168)
        self.assertEqual(len(r['ledger']['groups']),56)
        self.assertEqual(r['ledger']['baseline_eligible_count'],9)
        self.assertTrue(r['campaign_schedule_bound'])
        self.safe(r)

    def test_campaign_lock_earlier_than_first_roster_enforced(self):
        cs,_=pack(); s=schedule_for(cs,at=PLAN_AT)['frozen']
        self.assertEqual(bind(s,cs,as_of_utc=NOW)['reason'],
                         'CAMPAIGN_NOT_FROZEN_BEFORE_FIRST_ROSTER')

    def test_missing_cohort_does_not_rebase_expected_ids(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        r=bind(s,cs[:-1],as_of_utc=NOW)
        self.assertEqual(r['reason'],'COHORT_MISSING_OR_EXTRA_VS_FROZEN_CAMPAIGN')
        self.safe(r)

    def test_extra_cohort_blocks(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        self.assertEqual(bind(s,cs+(cs[-1],),as_of_utc=NOW)['reason'],
                         'COHORT_MISSING_OR_EXTRA_VS_FROZEN_CAMPAIGN')

    def test_reordering_cohort_fails(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        self.assertEqual(bind(s,tuple(reversed(cs)),as_of_utc=NOW)['reason'],
                         'COHORT_ID_OR_ROSTER_INVALID_AGAINST_FROZEN_CAMPAIGN')

    def test_different_cohort_id_fails(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        cs2=list(cs);cs2[1],_=make_cohort(4)
        self.assertEqual(bind(s,cs2,as_of_utc=NOW)['reason'],
                         'COHORT_ID_OR_ROSTER_INVALID_AGAINST_FROZEN_CAMPAIGN')

    def test_target_rewrite_under_same_cohort_id_fails(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        alternate,_=make_cohort(1,same_target=True)
        cs2=(cs[0],alternate,cs[2])
        self.assertEqual(bind(s,cs2,as_of_utc=NOW)['reason'],
                         'TARGET_WINDOW_CHANGED_SINCE_CAMPAIGN_SCHEDULE')

    def test_changed_rule_version_fails(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        alternate,_=make_cohort(1,version='atlasquant-research-v2')
        self.assertEqual(bind(s,(cs[0],alternate,cs[2]),as_of_utc=NOW)['reason'],
                         'COHORT_RULE_VERSION_DIFFERS_FROM_CAMPAIGN')

    def test_vetoed_baseline_candidate_cannot_disappear(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        bad=replace(cs[1], hypotheses=tuple(h for h in cs[1].hypotheses if not h.regime_veto))
        r=bind(s,(cs[0],bad,cs[2]),as_of_utc=NOW)
        self.assertTrue(r['reason'].startswith('CAMPAIGN_COHORT_LEDGER_REJECTED'))
        self.safe(r)

    def test_tampered_frozen_json_or_hash_blocks(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        for bad in (replace(s,sha256='0'*64),replace(s,canonical_json='{}'),
                    FrozenBlob(s.canonical_json+' ',s.sha256)):
            self.assertEqual(bind(bad,cs,as_of_utc=NOW)['state'],'LAB_CAMPAIGN_SCHEDULE_BLOCKED')

    def test_modified_schedule_content_even_rehashed_revalidated(self):
        cs,_=pack();s=schedule_for(cs)['frozen']
        altered=json.loads(s.canonical_json)
        altered['cohorts'][1]['W1']['open_utc']=altered['cohorts'][0]['W1']['open_utc']
        import hashlib
        raw=json.dumps(altered,sort_keys=True,separators=(',',':'),ensure_ascii=True)
        forged=FrozenBlob(raw,hashlib.sha256(raw.encode('ascii')).hexdigest())
        self.assertEqual(bind(forged,cs,as_of_utc=NOW)['state'],'LAB_CAMPAIGN_SCHEDULE_BLOCKED')

    def test_duplicate_cohort_id_rejected(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];doc=json.loads(s.canonical_json)
        first=doc['cohorts'][0];second=doc['cohorts'][1]
        rows=[PlannedFxCohort(x['cohort_id'],
            __import__('datetime').datetime.fromisoformat(x['D1']['open_utc'].replace('Z','+00:00')),
            __import__('datetime').datetime.fromisoformat(x['D1']['close_utc'].replace('Z','+00:00')),
            __import__('datetime').datetime.fromisoformat(x['W1']['open_utc'].replace('Z','+00:00')),
            __import__('datetime').datetime.fromisoformat(x['W1']['close_utc'].replace('Z','+00:00')))
            for x in (first,second)]
        rows[1]=replace(rows[1],cohort_id=rows[0].cohort_id)
        self.assertEqual(freeze(campaign_id='CAMPAIGN26A',rule_version=VERSION,
                    scheduled=rows,frozen_at=CAMPAIGN_AT)['reason'],
                         'INVALID_OR_DUPLICATED_COHORT_ID')

    def test_out_of_order_targets_block(self):
        cs,_=pack();p=schedule_for(cs)['frozen'];doc=json.loads(p.canonical_json)
        rows=schedule_for(cs)['frozen']
        import datetime
        def conv(x):return datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
        slots=[PlannedFxCohort(x['cohort_id'],conv(x['D1']['open_utc']),conv(x['D1']['close_utc']),conv(x['W1']['open_utc']),conv(x['W1']['close_utc'])) for x in doc['cohorts']]
        swapped=[slots[1],slots[0],slots[2]]
        self.assertEqual(freeze(campaign_id='CAMPAIGN26A',rule_version=VERSION,
                scheduled=swapped,frozen_at=CAMPAIGN_AT)['reason'],
                         'INVALID_LATE_OVERLAPPING_OR_UNSORTED_TARGET_WINDOW')

    def test_overlapping_horizon_target_blocked(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];doc=json.loads(s.canonical_json)
        import datetime
        def conv(x):return datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
        rows=[PlannedFxCohort(x['cohort_id'],conv(x['D1']['open_utc']),conv(x['D1']['close_utc']),conv(x['W1']['open_utc']),conv(x['W1']['close_utc'])) for x in doc['cohorts']]
        rows[1]=replace(rows[1],w1_open_at=rows[0].w1_open_at+timedelta(days=1),w1_close_at=rows[0].w1_close_at+timedelta(days=1))
        self.assertEqual(freeze(campaign_id='CAMPAIGN26A',rule_version=VERSION,
                scheduled=rows,frozen_at=CAMPAIGN_AT)['reason'],
                'INVALID_LATE_OVERLAPPING_OR_UNSORTED_TARGET_WINDOW')

    def test_dst_boundary_is_not_silently_widened(self):
        cs,_=pack();doc=json.loads(cs[0].roster.canonical_json);import datetime
        u=lambda x:datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
        s=PlannedFxCohort('LABC26_000',u('2026-03-04T22:00:00Z'),u('2026-03-05T22:00:00Z'),
            u('2026-03-01T22:00:00Z'),u('2026-03-08T22:00:00Z'))
        r=freeze(campaign_id='CAMPAIGN26A',rule_version=VERSION,
                 scheduled=(s,),frozen_at=u('2026-02-25T00:00:00Z'))
        self.assertEqual(r['reason'],'W1_DST_OR_CLOCK_CONVENTION_REQUIRES_BROKER_REVIEW')
        self.safe(r)

    def test_naive_and_future_campaign_clock_block(self):
        cs,_=pack();s=schedule_for(cs)
        self.assertEqual(freeze(campaign_id='CAMPAIGN26A',rule_version=VERSION,
                    scheduled=(),frozen_at=CAMPAIGN_AT)['state'],'LAB_CAMPAIGN_SCHEDULE_BLOCKED')
        self.assertEqual(schedule_for(cs,at=CAMPAIGN_AT.replace(tzinfo=None))['state'],
                         'LAB_CAMPAIGN_SCHEDULE_BLOCKED')
        self.assertEqual(schedule_for(cs,at=PLAN_AT+timedelta(days=100))['state'],
                         'LAB_CAMPAIGN_SCHEDULE_BLOCKED')

    def test_anchor_only_prepares_unpublished_text(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];r=anchor(s,repository_full_name='owner/repo',issue_number=1851,
                        prepared_at=CAMPAIGN_AT+timedelta(minutes=1))
        self.assertEqual(r['state'],'LAB_CAMPAIGN_ANCHOR_TEXT_PREPARED_NOT_POSTED')
        self.assertIn('schedule_sha256='+s.sha256,r['anchor_body'])
        self.assertIn('slots_expected=168',r['anchor_body'])
        self.safe(r)

    def test_anchor_after_first_target_rejected(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];
        r=anchor(s,repository_full_name='owner/repo',issue_number=1851,
                        prepared_at=PLAN_AT+timedelta(days=2))
        self.assertEqual(r['state'],'LAB_CAMPAIGN_SCHEDULE_BLOCKED')
        self.safe(r)

    def test_anchor_invalid_repo_and_issue_blocked(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];
        for repo,issue in (('bad',1851),('owner/repo',True),('owner/repo',0)):
            r=anchor(s,repository_full_name=repo,issue_number=issue,prepared_at=CAMPAIGN_AT)
            self.assertEqual(r['state'],'LAB_CAMPAIGN_SCHEDULE_BLOCKED')

    def test_broker_session_remains_unverified_on_full_documentary_match(self):
        cs,_=pack();s=schedule_for(cs)['frozen'];r=bind(s,cs,as_of_utc=NOW)
        self.assertTrue(r['campaign_schedule_bound'])
        self.assertFalse(r['external_campaign_precommitment_verified'])
        self.assertFalse(r['broker_calendar_authenticated'])
        self.safe(r)

if __name__=='__main__':unittest.main()
