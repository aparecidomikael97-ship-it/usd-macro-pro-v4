from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
import unittest
import pandas as pd
import requests
import autopilot_v107 as ap
from twelve_budget_v1108 import Budget, BudgetUnavailable, classify_limit, DAILY_LIMIT
from twelve_cache_v1108 import read_series, cached_series

NOW=datetime(2026,9,15,12,0,tzinfo=timezone.utc)

class Store:
    def __init__(self,state=None): self.state=state or {}; self.revision=0; self.writes=0
    def load(self): return deepcopy(self.state),self.revision
    def save(self,state,revision):
        if revision!=self.revision: return False
        self.state=deepcopy(state); self.revision+=1; self.writes+=1
        return True

def records(now=NOW,n=100):
    idx=pd.date_range(end=pd.Timestamp(now)-pd.Timedelta(minutes=15),periods=n,freq='15min')
    return [{'datetime':str(t),'open':1.1,'high':1.2,'low':1.0,'close':1.15} for t in idx]

class BudgetTests(unittest.TestCase):
    def test_daily_and_minute_distinct(self):
        self.assertEqual(classify_limit('You have run out of API credits for the current minute. 12 API credits were used'),'LIMITE_MINUTO')
        self.assertEqual(classify_limit('You have run out of API credits for the day. 1053 API credits were used'),'COTA_DIARIA')
        self.assertEqual(classify_limit('API credits exhausted'),'COTA_OU_PLANO')

    def test_limit_survives_new_instance(self):
        store=Store({'day':'2026-09-15','used':479,'hours':{},'recent':[]})
        late=NOW.replace(hour=23)
        self.assertTrue(Budget(store).reserve(late)[0])
        self.assertEqual(Budget(store).reserve(late)[1],'ORCAMENTO_DIARIO')
        self.assertEqual(store.state['used'],480)

    def test_daily_block_is_persistent_and_no_probe_next_run(self):
        s=Store(); Budget(s).block('1053 API credits were used for the day',NOW)
        b=Budget(s)
        self.assertEqual(b.reserve(NOW+timedelta(hours=1))[1],'COTA_DIARIA')
        self.assertEqual(b.summary(NOW)['remaining'],0)
        self.assertEqual(b.summary(NOW)['reset_at'],'2026-09-16T00:00:00+00:00')

    def test_reset_at_midnight_utc_only(self):
        s=Store(); b=Budget(s); b.block('daily limit reached',NOW)
        self.assertFalse(b.reserve(NOW.replace(hour=23,minute=59))[0])
        self.assertTrue(b.reserve(NOW.replace(hour=0)+timedelta(days=1))[0])
        self.assertEqual(s.state['used'],1)

    def test_minute_block_does_not_become_day_block(self):
        s=Store(); b=Budget(s); b.block('current minute API credits exhausted',NOW)
        self.assertFalse(Budget(s).reserve(NOW+timedelta(seconds=61))[0])
        self.assertTrue(Budget(s).reserve(NOW+timedelta(seconds=63))[0])

    def test_rolling_minute_gate_across_runs(self):
        s=Store()
        for i in range(6): self.assertTrue(Budget(s).reserve(NOW+timedelta(seconds=i))[0])
        self.assertEqual(Budget(s).reserve(NOW+timedelta(seconds=6))[1],'LIMITE_MINUTO')
        self.assertTrue(Budget(s).reserve(NOW+timedelta(seconds=63))[0])

    def test_hourly_and_daily_pacing(self):
        s=Store(); b=Budget(s); midnight=NOW.replace(hour=0)
        for i in range(28): self.assertTrue(b.reserve(midnight+timedelta(seconds=i*63))[0])
        self.assertEqual(b.reserve(midnight+timedelta(minutes=40))[1],'RITMO_DIARIO')
        self.assertTrue(b.reserve(midnight+timedelta(hours=1))[0])

    def test_whole_day_never_exceeds_480(self):
        s=Store(); b=Budget(s); midnight=NOW.replace(hour=0)
        permitted=sum(b.reserve(midnight+timedelta(minutes=i))[0] for i in range(1440))
        self.assertEqual(permitted,480)
        self.assertEqual(s.state['used'],480)

    def test_failed_save_never_authorizes(self):
        s=Store(); s.save=Mock(side_effect=BudgetUnavailable('disk/API'))
        with self.assertRaises(BudgetUnavailable): Budget(s).reserve(NOW)
        self.assertEqual(s.state,{})

    def test_conflict_reloads_fresh_count(self):
        s=Store(); original=s.save
        def conflict(state,revision):
            if s.revision==0:
                s.state={**state,'used':479}; s.revision=1
                return False
            return original(state,revision)
        s.save=conflict
        self.assertTrue(Budget(s).reserve(NOW.replace(hour=23))[0])
        self.assertEqual(s.state['used'],480)

    def test_corrupt_or_future_day_fails_closed(self):
        for state in ({'used':0},{'day':'2026-09-16','used':0},{'day':'2026-09-15','used':-1}):
            with self.assertRaises(BudgetUnavailable): Budget(Store(state)).reserve(NOW)

    def test_migration_keeps_reported_exhaustion(self):
        s=Store(); b=Budget(s)
        status={'last_run':NOW.isoformat(),'twelve_daily_blocked':True,
                'twelve_daily_block_reason':'1053 API credits were used for the day'}
        b.bootstrap(status,{},NOW)
        self.assertEqual(b.reserve(NOW)[1],'COTA_DIARIA')
        b.bootstrap(status,{},NOW+timedelta(minutes=10))
        self.assertEqual(s.state['used'],1053)

    def test_yesterday_status_does_not_block_today(self):
        b=Budget(Store())
        b.bootstrap({'last_run':(NOW-timedelta(days=1)).isoformat(),'twelve_daily_blocked':True,'twelve_daily_block_reason':'daily limit reached'},{},NOW)
        self.assertTrue(b.reserve(NOW)[0])

class CacheTests(unittest.TestCase):
    def state(self):
        return {'series':{'EUR/USD|15min':{'fetched_at':NOW.isoformat(),'records':records()}}}

    def test_cache_does_not_change_source_timestamp(self):
        d,e=read_series(self.state(),'EUR/USD','15min',100,now=NOW+timedelta(minutes=10))
        self.assertFalse(e); self.assertEqual(d.attrs['source_fetched_at'],NOW.isoformat())

    def test_old_and_future_fetch_rejected(self):
        for now in (NOW-timedelta(seconds=1),NOW+timedelta(minutes=56)):
            d,e=read_series(self.state(),'EUR/USD','15min',100,now=now)
            self.assertTrue(d.empty); self.assertTrue(e)

    def test_old_candles_cannot_be_relabelled_fresh(self):
        s=self.state(); s['series']['EUR/USD|15min']['fetched_at']=(NOW+timedelta(hours=3)).isoformat()
        d,e=read_series(s,'EUR/USD','15min',100,now=NOW+timedelta(hours=3))
        self.assertTrue(d.empty)

    def test_invalid_geometry_and_open_candles_excluded(self):
        s=self.state(); items=s['series']['EUR/USD|15min']['records']
        items[-1]['high']=.1
        items.append({'datetime':NOW.isoformat(),'open':1,'high':2,'low':.5,'close':1.1})
        d,e=read_series(s,'EUR/USD','15min',100,now=NOW)
        self.assertEqual(len(d),99)

    def test_history_can_read_old_closed_data_but_not_for_execution(self):
        s=self.state(); later=NOW+timedelta(days=2)
        self.assertTrue(read_series(s,'EUR/USD','15min',100,now=later)[0].empty)
        self.assertEqual(len(read_series(s,'EUR/USD','15min',100,now=later,history=True)[0]),100)

    def test_ui_repeated_reads_have_no_provider_fallback(self):
        import twelve_cache_v1108 as cache
        with patch.object(cache,'_load',return_value=(self.state(),'')), patch.object(cache,'_setting',return_value='x'), patch.object(requests,'get',side_effect=AssertionError('network')):
            for _ in range(30): cached_series('EUR/USD','15min')


    def test_exact_cache_boundaries_and_invalid_limits_fail_closed(self):
        d,e=read_series(self.state(),'EUR/USD','15min',100,now=NOW+timedelta(minutes=55))
        self.assertTrue(d.empty); self.assertTrue(e)
        for bad in (float("nan"),float("inf"),float("-inf"),-1):
            with self.subTest(limit=bad):
                d,e=read_series(self.state(),'EUR/USD','15min',100,now=NOW+timedelta(minutes=10),max_age=bad)
                self.assertTrue(d.empty); self.assertTrue(e)

    def test_invalid_outputsize_fails_closed(self):
        for bad in (0,-1,'bad'):
            with self.subTest(outputsize=bad):
                d,e=read_series(self.state(),'EUR/USD','15min',bad,now=NOW+timedelta(minutes=10))
                self.assertTrue(d.empty); self.assertTrue(e)

class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(); self.budget=Budget(self.store)
        self.patches=[patch.object(ap,'TD_KEY','test'),patch.object(ap,'_TD_BUDGET',self.budget),
                      patch.object(ap,'_TD_SERIES',{'series':{}}),patch.object(ap,'_TD_DAILY_BLOCKED',False),
                      patch.object(ap,'_TD_HTTP_CALLS',0),patch.object(ap,'_TD_CACHE_HITS',0),
                      patch.object(ap,'_td_rate_gate'),patch.object(ap,'utcnow',return_value=pd.Timestamp(NOW))]
        for p in self.patches: p.start(); self.addCleanup(p.stop)

    def response(self,code=200,body=None):
        return Mock(status_code=code,json=Mock(return_value=body or {'values':records()}))

    def test_reservation_precedes_http_and_duplicate_reuses(self):
        def send(*a,**k):
            self.assertEqual(self.store.state['used'],1)
            return self.response()
        with patch.object(ap.requests,'get',side_effect=send) as get:
            d,e=ap.td_fetch('EUR/USD','15min',100)
            d2,e2=ap.td_fetch('EUR/USD','15min',100)
        self.assertFalse(e); self.assertFalse(e2); self.assertEqual(get.call_count,1)
        self.assertEqual(ap._TD_HTTP_CALLS,1); self.assertEqual(ap._TD_CACHE_HITS,1)

    def test_timeout_still_consumes_reserved_credit(self):
        with patch.object(ap.requests,'get',side_effect=requests.Timeout()):
            d,e=ap.td_fetch('EUR/USD','15min',100)
        self.assertTrue(e); self.assertEqual(self.store.state['used'],1)

    def test_daily_error_stops_and_persists(self):
        response=self.response(429,{'message':'1053 API credits were used for the day'})
        with patch.object(ap.requests,'get',return_value=response) as get:
            ap.td_fetch('EUR/USD','15min',100); ap.td_fetch('GBP/USD','1h',100)
        self.assertEqual(get.call_count,1)
        self.assertEqual(Budget(self.store).reserve(NOW+timedelta(hours=1))[1],'COTA_DIARIA')

    def test_http200_quota_error_also_stops(self):
        with patch.object(ap.requests,'get',return_value=self.response(200,{'status':'error','code':429,'message':'daily limit reached'})):
            ap.td_fetch('EUR/USD','15min',100)
        self.assertEqual(self.store.state['block_type'],'COTA_DIARIA')

    def test_non_json_429_stops_without_guessing_day(self):
        response=Mock(status_code=429,json=Mock(side_effect=ValueError()))
        with patch.object(ap.requests,'get',return_value=response) as get:
            ap.td_fetch('EUR/USD','15min',100); ap.td_fetch('GBP/USD','1h',100)
        self.assertEqual(get.call_count,1)
        self.assertEqual(self.store.state['block_type'],'COTA_OU_PLANO')

    def test_no_http_if_reservation_cannot_be_saved(self):
        self.store.save=Mock(side_effect=BudgetUnavailable('fail'))
        with patch.object(ap.requests,'get',side_effect=AssertionError('must not call')):
            d,e=ap.td_fetch('EUR/USD','15min',100)
        self.assertTrue(d.empty); self.assertTrue(e)

    def test_invalid_outputsize_never_reserves_or_calls_provider(self):
        for bad in (0,-1,5001,'bad'):
            with self.subTest(outputsize=bad), patch.object(ap.requests,'get',side_effect=AssertionError('must not call')):
                d,e=ap.td_fetch('EUR/USD','15min',bad)
                self.assertTrue(d.empty); self.assertTrue(e)
        self.assertEqual(self.store.writes,0)

    def test_batch_symbols_cannot_bypass_credit_weight(self):
        with patch.object(ap.requests,'get',side_effect=AssertionError('must not call')):
            d,e=ap.td_fetch('EUR/USD,GBP/USD','15min',100)
        self.assertTrue(e); self.assertEqual(self.store.writes,0)

if __name__=='__main__': unittest.main()