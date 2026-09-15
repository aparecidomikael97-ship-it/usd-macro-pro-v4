"""Provas offline. Uso: python reproduzir_auditoria.py PASTA_DO_SISTEMA.
Nao altera o sistema e substitui acessos HTTP/GitHub por mocks.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
import copy
import json
import base64
from unittest.mock import patch, Mock
import types

# Stub mínimo de Streamlit para auditoria offline das funções puras.
_st = types.ModuleType("streamlit")
class _Secrets(dict):
    def get(self, k, default=None): return super().get(k, default)
_st.secrets = _Secrets()
_st.session_state = {}
def _cache_data(*args, **kwargs):
    def deco(fn):
        fn.clear = lambda: None
        return fn
    return deco
_st.cache_data = _cache_data
sys.modules.setdefault("streamlit", _st)

import pandas as pd
import decision_integrity_v110 as di
import data_readiness_v1101 as dr
import institutional_engine_v110 as ie
import pair_intelligence_v110 as pi
import autopilot_v107 as ap
import currency_news_v107 as cn

results = {}
base = dict(side='BUY', score=92, quality=88, rank_index=82,
            h4='🟢 CONFIRMA', h1='🟢 PULLBACK OK', m15='🟢 GATILHO',
            ict_readiness=85, institutional_readiness=85, gate='A', gate_score=85,
            adr_used_pct=60, event_risk='NORMAL', technical_age_min=10,
            data_sufficient=True, data_readiness_score=100)
results['01_status_m15'] = {}
for value in ['🟢 GATILHO', '🟡 AGUARDAR GATILHO', '🔴 SEM GATILHO']:
    out = di.evaluate_decision_integrity(**(base | {'m15': value}))
    results['01_status_m15'][value] = {'status_score': di._status_score(value), 'executable': out['executable'], 'soft_blocks': out['soft_blocks']}
results['02_campos_ausentes'] = di.evaluate_decision_integrity(**(base | dict(data_sufficient=None, data_readiness_score=None, technical_age_min=None, adr_used_pct=None, event_risk=None)))['state']
results['03_risco_nao_reconhecido'] = {v: di._event_level(v) for v in ['MUITO ALTO', 'CRITICAL', 'ATENÇÃO', 'N/D', 'ALTO']}
now = pd.Timestamp.now(tz='UTC')
results['04_timestamps'] = {}
for label, value in [('pd.NA', pd.NA), ('pd.NaT', pd.NaT), ('NaN', float('nan')), ('future', (now + pd.Timedelta(days=1)).isoformat())]:
    try:
        age = dr._age_minutes(value, now)
        results['04_timestamps'][label] = {'age': age, 'fresh': dr._freshness('m15', age)['fresh']}
    except Exception as exc:
        results['04_timestamps'][label] = type(exc).__name__ + ': ' + str(exc)

def candles(end, n=80, freq='15min'):
    return pd.DataFrame({'datetime': pd.date_range(end=end, periods=n, freq=freq),
                         'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105})

row = {'Direção': 'COMPRA EUR/USD', 'Score final': 92, 'Qualidade': 88, 'Índice ranking': 82, 'Dif. macro': 10}
scanner = {'macro_direction': 'COMPRA EUR/USD', 'processado_em': now.timestamp(),
           **{f'{tf}_fetched_at': now.isoformat() for tf in ['h4', 'h1', 'm15']},
           'tecnico': {'h4': {'status': '🟢 CONFIRMA'}, 'h1': {'status': '🟢 PULLBACK OK'}, 'm15': {'status': '🟢 GATILHO'},
                       'ict': {'readiness': 85, 'side': 'BUY'}, 'institutional': {'readiness': 85, 'side': 'BUY', 'mss': {'status':'🟢 MSS CONFIRMADO'}},
                       'cache_v110': {'h1': ap._serialize_tf_cache(candles(now-pd.Timedelta(hours=1),freq='1h'),80), 'm15': ap._serialize_tf_cache(candles(now-pd.Timedelta(minutes=15)),80)}}}
mapctx = {'updated_at': (now-pd.Timedelta(days=7)).isoformat(), 'macro_direction': 'COMPRA EUR/USD', 'readiness_grade':'A', 'readiness_score':85, 'adr_used_pct':60, 'event_risk':'NORMAL'}
def pack(s=scanner, m=mapctx, r=row):
    return pi._reason_pack('EUR/USD',r,pd.DataFrame(),s,m,{})
results['05_mapa_7_dias'] = {'state':pack()['state'], 'map_ready':pack()['data_ready']['map_ready']}
results['06_direcao_trocada'] = pack(r=row | {'Direção':'VENDA EUR/USD'})['state']
bad = copy.deepcopy(scanner)
bad['tecnico']['cache_v110'] = {'h1':[{}]*12,'m15':[{}]*32}
results['07_cache_invalido'] = {'data_sufficient':dr.assess_pair_data_readiness(bad)['sufficient'], 'state':pack(s=bad)['state']}
stale = copy.deepcopy(scanner)
for tf in ['h4','h1','m15']:
    stale[f'{tf}_fetched_at'] = (now-pd.Timedelta(days=1)).isoformat()
stale_pack = pack(s=stale)
results['08_evidencias_antigas'] = {'state':stale_pack['state'],'up':stale_pack['up'],'positives':stale_pack['positives']}
results['09_adr_ausente_mapa'] = pi._map_normalize({'readiness_grade':'A','readiness_score':85},'EUR/USD')

a = candles(now, n=48)
b = candles(now-pd.Timedelta(days=7),n=48)
a.loc[40:, 'low'] = 1.08
aa,bb = ie._align_frames(a,b,48)
results['10_smt_sem_sincronia'] = {'matched_times':len(set(a.datetime)&set(b.datetime)), 'aligned_rows':len(aa),'result':ie.detect_smt(a,b,'EUR/USD','GBP/USD','BUY')}

old = copy.deepcopy(scanner)
old['tecnico']['ict'].update({k:{'score':90,'status':'🟢 CONFIRMADO PARA BUY'} for k in ['crt','ote','amd','fvg']})
state = {'resultados':{'EUR/USD':old}, 'autopilot_v107':{'last_fetches':{'EUR/USD':{tf:now.isoformat() for tf in ['h4','h1','m15']}}}}
with patch.object(ap,'gh_get_json',return_value=(state,'')), patch.object(ap,'forex_market_likely_open',return_value=True), patch.object(ap,'td_fetch',return_value=(pd.DataFrame(),'simulated failure')), patch.object(ap,'PAIR_ORDER',['EUR/USD']), patch.object(ap,'_TD_DAILY_BLOCKED',False):
    scan,_,errs,_ = ap.scanner_update({'pairs':[row|{'Par':'EUR/USD','Direção':'VENDA EUR/USD'}]})
    saved = scan['resultados']['EUR/USD']
    results['11_troca_direcao_api_falha'] = {'macro_direction':saved['macro_direction'], 'h4':saved['tecnico']['h4'], 'h1':saved['tecnico']['h1'], 'm15':saved['tecnico']['m15'], 'ict_side':saved['tecnico']['ict'].get('side'),'ict_readiness':saved['tecnico']['ict'].get('readiness'), 'errors':errs}

response = Mock()
response.status_code = 200
response.json.return_value = {'content':base64.b64encode(b'{"origin":"repo-A"}').decode()}
pi._read_json.clear()
with patch.object(pi.requests,'get',return_value=response) as mocked:
    first = pi._read_json('dados/audit.json','dummy-A','repo-A','main')
    second = pi._read_json('dados/audit.json','dummy-B','repo-B','other')
    results['12_cache_repositorios'] = {'http_calls':mocked.call_count,'first':first,'second':second}
pi._read_json.clear()
results['13_negacao_noticias'] = {s:cn._headline_impact('USD',s) for s in ['Fed signals rate cuts', 'Fed rules out rate cuts']}
from ict_execution_v108 import detect_fvg
fvg = pd.DataFrame([
    {'open':1.09,'high':1.10,'low':1.08,'close':1.09},
    {'open':1.09,'high':1.13,'low':1.09,'close':1.12},
    {'open':1.12,'high':1.14,'low':1.12,'close':1.13},
    {'open':1.13,'high':1.14,'low':1.04,'close':1.05},
    {'open':1.05,'high':1.115,'low':1.04,'close':1.11},
])
results['14_fvg_invalidado_e_revisitado'] = detect_fvg(fvg,'BUY')
with patch.object(ap,'gh_get_csv',return_value=(pd.DataFrame(),'')),patch.object(ap,'PAIR_ORDER',['EUR/USD']),patch.object(ap,'utcnow',return_value=pd.Timestamp('2026-09-14T12:07:00Z')):
    entries,_ = ap.manage_snapshots({'currencies':{}},pd.DataFrame([{'Par':'EUR/USD','Diferencial notícias':5}]),{'EUR/USD':candles(pd.Timestamp('2026-09-14T11:45:00Z'))})
    results['15_preco_anterior_ao_sinal'] = entries[['entry_time','m15_candle_time','signal_frozen_at','entry_price']].to_dict('records')
print(json.dumps(results,ensure_ascii=False,indent=2,default=str))
