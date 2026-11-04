"""Offline research contracts for FREE official news planning, never live feeds."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from atlasquant_trader_primary_news_routes_lab import (
    SCHEMA, STATE, DENIED, SOURCES, EVENTS, SOURCE_BY_EVENT,
    build_primary_news_routes_lab as build,
)

NOW = datetime(2026, 11, 3, 14, tzinfo=timezone.utc)


class FreeOfficialNewsRoutesTests(unittest.TestCase):
    def test_five_official_public_channels_not_live(self):
        r = build(at=NOW)
        self.assertEqual(r['schema'], SCHEMA)
        self.assertEqual(r['state'], STATE)
        self.assertEqual(r['source_leads'], 5)
        self.assertEqual(r['scheduled_events'], 4)
        self.assertFalse(r['news_live'])
        self.assertFalse(r['news_realtime_guaranteed'])
        self.assertFalse(r['source_latency_verified'])
        self.assertFalse(r['source_license_for_commercial_use_verified'])

    def test_three_horizon_coverage_28_fx_and_five_indices(self):
        r = build(at=NOW)
        self.assertEqual(r['fx_rows_count'], 84)
        self.assertEqual(r['index_rows_count'], 15)
        self.assertEqual(len({(x['pair'], x['horizon']) for x in r['fx_rows']}), 84)
        self.assertEqual(len({(x['instrument'], x['horizon']) for x in r['index_rows']}), 15)

    def test_nov3_upcoming_copom_bo_e_nfp_and_us_cpi(self):
        r = build(at=NOW)
        named = {x['event_id']: x for x in r['route_rows']}
        self.assertEqual(named['BCB_COPOM_20261104']['horizons']['W1'],
                         'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')
        self.assertEqual(named['BOE_MPC_20261105']['horizons']['W1'],
                         'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')
        self.assertEqual(named['BLS_US_EMPLOYMENT_20261106']['horizons']['W1'],
                         'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')
        self.assertEqual(named['BLS_US_CPI_20261110']['horizons']['MN1'],
                         'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')
        self.assertEqual(named['BLS_US_CPI_20261110']['horizons']['W1'],
                         'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')

    def test_gbpusd_covers_boe_and_us_without_brazil(self):
        r = build(at=NOW)
        row = next(x for x in r['fx_rows'] if x['pair']=='GBP/USD' and x['horizon']=='W1')
        self.assertEqual(set(row['relevant_event_ids']),
                         {'BOE_MPC_20261105', 'BLS_US_EMPLOYMENT_20261106', 'BLS_US_CPI_20261110'})
        self.assertNotIn('BCB_COPOM_20261104', row['relevant_event_ids'])

    def test_non_us_jpy_chf_has_no_direct_curated_event(self):
        r = build(at=NOW)
        row = next(x for x in r['fx_rows'] if x['pair']=='CHF/JPY' and x['horizon']=='W1')
        self.assertEqual(row['relevant_event_ids'], [])
        self.assertEqual(row['bias'], 'AGUARDAR')

    def test_win_wdo_have_direct_brazil_and_indirect_us(self):
        r = build(at=NOW)
        for index in ('WIN','WDO'):
            row = next(x for x in r['index_rows'] if x['instrument']==index and x['horizon']=='W1')
            got = {(e['event_id'],e['channel']) for e in row['relevant_events']}
            self.assertIn(('BCB_COPOM_20261104','BR_DOMESTIC_DIRECT_CONTEXT'),got)
            self.assertIn(('BLS_US_EMPLOYMENT_20261106','US_GLOBAL_INDIRECT_CONTEXT_UNVERIFIED'),got)

    def test_us_indices_do_not_inherit_brazil_copom_direct(self):
        r = build(at=NOW)
        for index in ('SPX500','NAS100','US30'):
            row = next(x for x in r['index_rows'] if x['instrument']==index and x['horizon']=='W1')
            self.assertNotIn('BCB_COPOM_20261104', [e['event_id'] for e in row['relevant_events']])

    def test_future_actual_never_misreported_when_window_has_passed(self):
        at = datetime(2026,11,11,15,tzinfo=timezone.utc)
        r = build(at=at)
        for route in r['route_rows']:
            self.assertEqual(route['horizons']['D1'],'WINDOW_PASSED_ACTUAL_NOT_VERIFIED')
            self.assertFalse(route['actual_known'])
            self.assertFalse(route['news_ingested'])

    def test_during_copom_date_only_no_invented_hour(self):
        at = datetime(2026,11,4,15,tzinfo=timezone.utc)
        r = build(at=at)
        copom = r['route_rows'][0]
        self.assertEqual(copom['horizons']['D1'],
                         'DATE_ONLY_MAY_HAVE_ALREADY_OCCURRED_CHECK_OFFICIAL')
        self.assertEqual(copom['time_precision'],'DATE_ONLY')

    def test_event_window_edge_never_claims_known_release(self):
        at = datetime(2026,11,3,20,tzinfo=timezone.utc)
        r = build(at=at)
        self.assertEqual(r['route_rows'][0]['horizons']['D1'],'WINDOW_EDGE_UNCERTAIN')

    def test_official_urls_are_pinned_from_documentation(self):
        routes = {s['source_id']:s for s in SOURCES}
        self.assertEqual(routes['BLS_CPI_RSS']['url'],'https://www.bls.gov/feed/cpi.rss')
        self.assertEqual(routes['BLS_EMPLOYMENT_RSS']['url'],'https://www.bls.gov/feed/empsit.rss')
        self.assertEqual(routes['FED_MONETARY_RSS']['url'],'https://www.federalreserve.gov/feeds/press_monetary.xml')
        self.assertEqual(set(SOURCE_BY_EVENT),{e['event_id'] for e in EVENTS})

    def test_no_source_claims_verified_latency_or_polling(self):
        r = build(at=NOW)
        for s in r['source_rows']:
            self.assertFalse(s['live_source_reliability_verified'])
            self.assertFalse(s['publication_to_ingest_latency_measured'])
            self.assertFalse(s['automated_polling_enabled'])

    def test_reject_extra_actual_and_consensus_embedded_in_event(self):
        e = copy.deepcopy(EVENTS)
        e = [dict(x) for x in e]
        e[1]['actual'] = 0.1
        self.assertEqual(build(at=NOW,events=e)['state'],DENIED)
        e = [dict(x) for x in EVENTS]
        e[2]['consensus'] = 500
        self.assertEqual(build(at=NOW,events=e)['state'],DENIED)

    def test_reject_fake_release_earlier_than_actual_date(self):
        e = [dict(x) for x in EVENTS]
        e[0]['latest_at_utc'] = '2026-11-03T23:59:59Z'
        self.assertEqual(build(at=NOW,events=e)['state'],DENIED)

    def test_reject_fake_feed_host_or_approval_field(self):
        s = [dict(x) for x in SOURCES]
        s[0]['url'] = 'https://evil.example/feed'
        self.assertEqual(build(at=NOW,sources=s)['state'],DENIED)
        s = [dict(x) for x in SOURCES]
        s[0]['automated_polling_enabled'] = True
        self.assertEqual(build(at=NOW,sources=s)['state'],DENIED)
        s = [dict(x) for x in SOURCES]
        s[0]['licence_approved'] = True
        self.assertEqual(build(at=NOW,sources=s)['state'],DENIED)

    def test_missing_event_or_source_denied(self):
        self.assertEqual(build(at=NOW,events=EVENTS[:-1])['state'],DENIED)
        self.assertEqual(build(at=NOW,sources=SOURCES[:-1])['state'],DENIED)
        self.assertEqual(build(at=NOW,events=None,sources={})['state'],DENIED)

    def test_backdate_not_permitted_before_research(self):
        r = build(at=datetime(2026,11,2,23,tzinfo=timezone.utc))
        self.assertEqual(r['state'],DENIED)

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            build(at=datetime(2026,11,3,14))

    def test_no_trade_execution_deploy_or_paid_service_approved(self):
        r=build(at=NOW)
        for k in ('source_original_payloads_archived','actual_releases_verified',
                  'consensus_verified','can_feed_live_radar','trade_authorized',
                  'paid_provider_approved','paid_provider_charged',
                  'worker_enabled','scheduler_enabled','render_configuration_changed'):
            self.assertFalse(r[k],k)
        self.assertIsNone(r['probability_calibrated'])
        self.assertFalse(r['coverage_all_g8'])

    def test_cpi_just_outside_weekly_window_at_nov3_midnight(self):
        r = build(at=datetime(2026,11,3,0,tzinfo=timezone.utc))
        cpi = next(x for x in r['route_rows'] if x['event_id']=='BLS_US_CPI_20261110')
        self.assertEqual(cpi['horizons']['W1'],'OUTSIDE_HORIZON')
        self.assertEqual(cpi['horizons']['MN1'],'UPCOMING_DOCUMENTARY_SCHEDULE_ONLY')

    def test_expired_events_are_review_alerts_not_fake_upcoming_exposure(self):
        r=build(at=datetime(2026,11,15,0,tzinfo=timezone.utc))
        self.assertTrue(all(x['horizons']['W1']=='WINDOW_PASSED_ACTUAL_NOT_VERIFIED'
                            for x in r['route_rows']))
        self.assertTrue(all(not x['relevant_event_ids'] for x in r['fx_rows']))
        self.assertTrue(all(not x['relevant_events'] for x in r['index_rows']))

    def test_no_preset_direction_for_any_fx_or_index_horizon(self):
        r = build(at=NOW)
        self.assertTrue(all(x['bias']=='AGUARDAR' for x in r['fx_rows']))
        self.assertTrue(all(x['bias']=='AGUARDAR' for x in r['index_rows']))
        self.assertTrue(all(x['directional_impact']=='AGUARDAR' for x in r['route_rows']))


if __name__=='__main__':
    unittest.main()
