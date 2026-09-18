"""Shared Twelve Data access. Cloud stays read-only; Windows local can refresh its own protected cache."""
import base64
import json
import os
import math
import pandas as pd
import requests
import streamlit as st

SERIES_PATH='dados/twelve_series_v1108.json'
LOCAL_SERIES_PATH='dados/twelve_series_local.json'
LOCAL_BUDGET_PATH='dados/twelve_local_budget.json'
LOCAL_DAILY_LIMIT=180
MAX_AGE={'15min':55,'1h':115,'4h':235,'1day':1500}
DURATION={'15min':15,'1h':60,'4h':240,'1day':1440}


def valid_records(records, interval, now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if now.tzinfo is None: raise ValueError('UTC required')
    d=pd.DataFrame(records)
    cols=['datetime','open','high','low','close']
    if interval not in DURATION or not set(cols).issubset(d.columns): return pd.DataFrame()
    d=d[cols].copy()
    d['datetime']=pd.to_datetime(d['datetime'],utc=True,errors='coerce')
    for c in cols[1:]: d[c]=pd.to_numeric(d[c],errors='coerce')
    good=d['datetime'].notna()
    for c in cols[1:]: good &= d[c].map(lambda v: pd.notna(v) and math.isfinite(v) and v>0)
    good &= (d['high']>=d[['open','low','close']].max(axis=1)) & (d['low']<=d[['open','high','close']].min(axis=1))
    # D1 cache may include today's live candle; daily consumers exclude it themselves.
    good &= d['datetime']<=now
    if interval!='1day': good &= d['datetime']+pd.Timedelta(minutes=DURATION[interval])<=now
    return d.loc[good].sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)


def read_series(state, symbol, interval, outputsize, now=None, max_age=None, history=False):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.Timestamp(now)
    if interval not in MAX_AGE: return pd.DataFrame(),'Intervalo fora do cache compartilhado.'
    raw=((state or {}).get('series',{}) or {}).get(f'{symbol}|{interval}',{}) or {}
    try:
        stamp=pd.to_datetime(raw.get('fetched_at'),utc=True,errors='coerce')
        if pd.isna(stamp): raise ValueError()
        age=(now-stamp).total_seconds()/60
        if age<0: raise ValueError()
        limit=MAX_AGE[interval] if max_age is None else max_age
        if not history and age>limit: return pd.DataFrame(),'Cache antigo; aguarde o Autopilot. Sem nova chamada de API.'
        df=valid_records(raw.get('records',[]),interval,now)
        if df.empty: return df,'Cache sem candles fechados válidos; aguarde o Autopilot.'
        candle_age=(now-df.iloc[-1]['datetime']).total_seconds()/60
        if not history and candle_age>limit+DURATION[interval]:
            return pd.DataFrame(),'Candles antigos na fonte; não usar para execução.'
        df=df.tail(int(outputsize)).copy()
        df.attrs['source_fetched_at']=stamp.isoformat()
        df.attrs['cache_only']=True
        return df,''
    except Exception:
        return pd.DataFrame(),'Cache ausente ou timestamp inválido; aguarde o Autopilot.'


def _setting(key, default=''):
    try: return str(st.secrets.get(key,os.getenv(key,default)))
    except Exception: return os.getenv(key,default)


@st.cache_data(ttl=30,show_spinner=False)
def _load(token,repo,branch):
    if not token or not repo: return {},'Persistência GitHub não configurada.'
    try:
        r=requests.get(f'https://api.github.com/repos/{repo}/contents/{SERIES_PATH}',
                       params={'ref':branch},headers={'Authorization':f'Bearer {token}'},timeout=20)
        if r.status_code==404: return {},'Cache ainda não criado pelo Autopilot.'
        if r.status_code!=200: return {},f'Leitura do cache: HTTP {r.status_code}'
        return json.loads(base64.b64decode(r.json()['content']).decode('utf-8')),''
    except Exception: return {},'Não foi possível ler o cache persistido.'


def _read_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path,'r',encoding='utf-8') as fh:
            data=json.load(fh)
        return data if isinstance(data,dict) else default
    except Exception:
        return default


def _atomic_write_json(path, data):
    folder=os.path.dirname(path)
    if folder:
        os.makedirs(folder,exist_ok=True)
    tmp=path+'.tmp'
    with open(tmp,'w',encoding='utf-8') as fh:
        json.dump(data,fh,ensure_ascii=False,indent=2,default=str)
    os.replace(tmp,path)


def _local_budget_reserve():
    today=pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')
    state=_read_json_file(LOCAL_BUDGET_PATH,{'date':today,'used':0})
    if str(state.get('date',''))!=today:
        state={'date':today,'used':0}
    used=int(state.get('used',0) or 0)
    if used>=LOCAL_DAILY_LIMIT:
        return False,f'Limite local diário protegido atingido ({used}/{LOCAL_DAILY_LIMIT}).'
    state['used']=used+1
    _atomic_write_json(LOCAL_BUDGET_PATH,state)
    return True,''


def _serialize_records(df):
    rows=[]
    for row in df[['datetime','open','high','low','close']].to_dict('records'):
        dt=pd.Timestamp(row['datetime'])
        if dt.tzinfo is None:
            dt=dt.tz_localize('UTC')
        else:
            dt=dt.tz_convert('UTC')
        rows.append({
            'datetime':dt.strftime('%Y-%m-%d %H:%M:%S'),
            'open':float(row['open']),
            'high':float(row['high']),
            'low':float(row['low']),
            'close':float(row['close']),
        })
    return rows


def _local_series(symbol,interval,outputsize=500,history=False):
    if interval not in MAX_AGE:
        return pd.DataFrame(),'Intervalo fora do cache compartilhado.'

    state=_read_json_file(LOCAL_SERIES_PATH,{'series':{}})
    state.setdefault('series',{})

    cached,err=read_series(state,symbol,interval,outputsize,history=history)
    if not err:
        cached.attrs['local_mode']=True
        return cached,''

    if history:
        return cached,err

    api_key=_setting('CHAVE_TWELVE_DATA').strip()
    if not api_key:
        return pd.DataFrame(),'CHAVE_TWELVE_DATA ausente.'

    ok,budget_err=_local_budget_reserve()
    if not ok:
        return pd.DataFrame(),budget_err

    try:
        r=requests.get(
            'https://api.twelvedata.com/time_series',
            params={
                'symbol':symbol,
                'interval':interval,
                'outputsize':int(outputsize),
                'apikey':api_key,
                'timezone':'UTC',
                'format':'JSON',
                'order':'ASC',
            },
            timeout=25,
        )
        try:
            js=r.json()
        except Exception:
            return pd.DataFrame(),f'Twelve Data respondeu HTTP {r.status_code} sem JSON.'

        message=str(js.get('message','')) if isinstance(js,dict) else ''
        if r.status_code!=200 or (isinstance(js,dict) and js.get('status')=='error'):
            return pd.DataFrame(),f'Twelve Data HTTP {r.status_code}: {message[:300]}'

        now=pd.Timestamp.now(tz='UTC')
        df=valid_records(js.get('values',[]) if isinstance(js,dict) else [],interval,now=now)
        if df.empty:
            return df,'Twelve Data não retornou candles fechados válidos.'

        observed=now.isoformat()
        state['series'][f'{symbol}|{interval}']={
            'fetched_at':observed,
            'records':_serialize_records(df.tail(int(outputsize))),
        }
        _atomic_write_json(LOCAL_SERIES_PATH,state)

        out=df.tail(int(outputsize)).copy()
        out.attrs['source_fetched_at']=observed
        out.attrs['cache_only']=False
        out.attrs['local_mode']=True
        return out,''
    except Exception as exc:
        return pd.DataFrame(),f'Falha na consulta local Twelve Data: {type(exc).__name__}: {exc}'


def cached_series(symbol,interval,outputsize=500,history=False):
    token=_setting('GITHUB_TOKEN_HISTORICO').strip()
    repo=_setting('GITHUB_REPO_HISTORICO').strip()
    branch=_setting('GITHUB_BRANCH_HISTORICO','main').strip() or 'main'

    if not token or not repo:
        return _local_series(symbol,interval,outputsize,history=history)

    state,err=_load(token,repo,branch)
    if err: return pd.DataFrame(),err
    return read_series(state,symbol,interval,outputsize,history=history)


def clear_shared_cache():
    _load.clear()
