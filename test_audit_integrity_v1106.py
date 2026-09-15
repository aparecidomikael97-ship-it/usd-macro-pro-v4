import sys, types, unittest
from unittest.mock import patch
import pandas as pd

if "streamlit" not in sys.modules:
    st = types.ModuleType("streamlit")
    class Cache:
        def __call__(self,*a,**k):
            def deco(fn):
                fn.clear=lambda:None
                return fn
            return deco
    st.cache_data=Cache(); st.secrets={}
    sys.modules["streamlit"]=st

import decision_integrity_v110 as di
import data_readiness_v1101 as dr
import institutional_engine_v110 as ie
import pair_intelligence_v110 as pi
import autopilot_v107 as ap
import currency_news_v107 as cn
from ict_execution_v108 import detect_fvg

class AuditIntegrityV1106(unittest.TestCase):
    def setUp(self):
        self.now=pd.Timestamp.now(tz="UTC")
        self.base=dict(side='BUY',score=92,quality=88,rank_index=82,
                       h4='🟢 CONFIRMA',h1='🟢 PULLBACK OK',m15='🟢 GATILHO',
                       ict_readiness=85,institutional_readiness=85,gate='A',gate_score=85,
                       adr_used_pct=60,event_risk='NORMAL',technical_age_min=10,
                       data_sufficient=True,data_readiness_score=100)
    def candles(self,end,n=80,freq='15min'):
        return pd.DataFrame({'datetime':pd.date_range(end=end,periods=n,freq=freq),
                             'open':1.10,'high':1.11,'low':1.09,'close':1.105})
    def scanner(self):
        n=self.now
        return {'macro_direction':'COMPRA EUR/USD','processado_em':n.timestamp(),
                **{f'{tf}_fetched_at':n.isoformat() for tf in ['h4','h1','m15']},
                'tecnico':{'h4':{'status':'🟢 CONFIRMA'},'h1':{'status':'🟢 PULLBACK OK'},'m15':{'status':'🟢 GATILHO'},
                           'ict':{'readiness':85,'side':'BUY'},'institutional':{'readiness':85,'side':'BUY'},
                           'cache_v110':{'h1':ap._serialize_tf_cache(self.candles(n-pd.Timedelta(hours=1),freq='1h'),80),
                                         'm15':ap._serialize_tf_cache(self.candles(n-pd.Timedelta(minutes=15)),80)}}}
    def mapctx(self):
        n=self.now
        return {'updated_at':n.isoformat(),'macro_direction':'COMPRA EUR/USD',
                'readiness_grade':'A','readiness_score':85,'adr_used_pct':60,'event_risk':'NORMAL'}

    def test_m15_negative_never_confirms(self):
        self.assertEqual(di._status_score('🟡 AGUARDAR GATILHO'),60)
        self.assertEqual(di._status_score('🔴 SEM GATILHO'),20)
        self.assertFalse(di.evaluate_decision_integrity(**(self.base|{'m15':'🔴 SEM GATILHO'}))['executable'])
    def test_missing_fields_fail_closed(self):
        out=di.evaluate_decision_integrity(**(self.base|dict(data_sufficient=None,data_readiness_score=None,technical_age_min=None,adr_used_pct=None,event_risk=None)))
        self.assertFalse(out['executable']); self.assertEqual(out['state'],'🔴 BLOQUEADO')
    def test_event_unknown_not_normal(self):
        self.assertEqual(di._event_level('CRITICAL'),'MAXIMO')
        self.assertEqual(di._event_level('N/D'),'DESCONHECIDO')
    def test_invalid_future_timestamps_not_fresh(self):
        for v in [pd.NA,pd.NaT,float('nan'),self.now+pd.Timedelta(days=1)]:
            age=dr._age_minutes(v,self.now)
            self.assertFalse(dr._freshness('m15',age)['fresh'])
    def test_old_map_not_ready(self):
        m=self.mapctx(); m['updated_at']=(self.now-pd.Timedelta(days=7)).isoformat()
        self.assertFalse(dr.assess_pair_data_readiness(self.scanner(),m,now=self.now)['map_ready'])
    def test_direction_mismatch_blocks(self):
        r=dr.assess_pair_data_readiness(self.scanner(),self.mapctx(),now=self.now,expected_direction='VENDA EUR/USD')
        self.assertFalse(r['sufficient']); self.assertFalse(r['direction_consistent'])
    def test_invalid_cache_not_counted(self):
        s=self.scanner(); s['tecnico']['cache_v110']={'h1':[{}]*12,'m15':[{}]*32}
        r=dr.assess_pair_data_readiness(s,self.mapctx(),now=self.now)
        self.assertFalse(r['sufficient']); self.assertEqual(r['cache_h1_bars'],0); self.assertEqual(r['cache_m15_bars'],0)
    def test_smt_requires_time_overlap(self):
        a=self.candles(self.now,n=48); b=self.candles(self.now-pd.Timedelta(days=7),n=48)
        aa,bb=ie._align_frames(a,b,48); self.assertTrue(aa.empty and bb.empty)
        self.assertEqual(ie.detect_smt(a,b,'EUR/USD','GBP/USD','BUY')['score'],0)
    def test_direction_change_api_failure_clears_old_statuses(self):
        old=self.scanner(); old['tecnico']['ict'].update({k:{'score':90,'status':'🟢 CONFIRMADO PARA BUY'} for k in ['crt','ote','amd','fvg']})
        state={'resultados':{'EUR/USD':old},'autopilot_v107':{'last_fetches':{'EUR/USD':{tf:self.now.isoformat() for tf in ['h4','h1','m15']}}}}
        row={'Par':'EUR/USD','Direção':'VENDA EUR/USD','Score final':92,'Qualidade':88,'Índice ranking':82,'Dif. macro':-10}
        with patch.object(ap,'gh_get_json',return_value=(state,'')), patch.object(ap,'forex_market_likely_open',return_value=True), patch.object(ap,'td_fetch',return_value=(pd.DataFrame(),'fail')), patch.object(ap,'PAIR_ORDER',['EUR/USD']), patch.object(ap,'_TD_DAILY_BLOCKED',False):
            scan,_,_,_=ap.scanner_update({'pairs':[row]})
        t=scan['resultados']['EUR/USD']['tecnico']
        self.assertEqual(t['h4'],{}); self.assertEqual(t['h1'],{}); self.assertEqual(t['m15'],{})
    def test_read_json_cache_signature_includes_repo(self):
        import inspect
        self.assertEqual(list(inspect.signature(pi._read_json).parameters),['path','token','repo','branch'])
    def test_news_negation(self):
        cut=cn._headline_impact('USD','Fed signals rate cuts')[0]
        no_cut=cn._headline_impact('USD','Fed rules out rate cuts')[0]
        self.assertLess(cut,0); self.assertGreater(no_cut,0)
    def test_fvg_invalidated_not_reactivated(self):
        f=pd.DataFrame([
            {'open':1.09,'high':1.10,'low':1.08,'close':1.09},
            {'open':1.09,'high':1.13,'low':1.09,'close':1.12},
            {'open':1.12,'high':1.14,'low':1.12,'close':1.13},
            {'open':1.13,'high':1.14,'low':1.04,'close':1.05},
            {'open':1.05,'high':1.115,'low':1.04,'close':1.11},
        ])
        out=detect_fvg(f,'BUY'); self.assertNotIn('EM TESTE',out['status']); self.assertIn('INVALIDADO',out['status'])
    def test_snapshot_never_uses_pre_signal_candle_as_entry(self):
        with patch.object(ap,'gh_get_csv',return_value=(pd.DataFrame(),'')), patch.object(ap,'PAIR_ORDER',['EUR/USD']), patch.object(ap,'utcnow',return_value=pd.Timestamp('2026-09-14T12:07:00Z')):
            entries,_=ap.manage_snapshots({'currencies':{}},pd.DataFrame([{'Par':'EUR/USD','Diferencial notícias':5}]),{'EUR/USD':self.candles(pd.Timestamp('2026-09-14T11:45:00Z'))})
        r=entries.iloc[0]
        self.assertTrue(pd.isna(pd.to_numeric(pd.Series([r['entry_price']]),errors='coerce').iloc[0]))
        self.assertEqual(r['validation_status'],'AGUARDANDO_PRECO_POS_SINAL')

if __name__=='__main__': unittest.main()
