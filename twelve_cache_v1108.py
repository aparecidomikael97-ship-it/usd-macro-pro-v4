"""Read-only UI access to candles written by the budgeted collector."""
import base64
import json
import os
import math
import pandas as pd
import requests
import streamlit as st

SERIES_PATH='dados/twelve_series_v1108.json'
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
        try:
            limit=float(limit)
            if not math.isfinite(limit) or limit < 0: raise ValueError()
        except Exception:
            raise ValueError()
        if not history and age>=limit: return pd.DataFrame(),'Cache antigo; aguarde o Autopilot. Sem nova chamada de API.'
        df=valid_records(raw.get('records',[]),interval,now)
        if df.empty: return df,'Cache sem candles fechados válidos; aguarde o Autopilot.'
        candle_age=(now-df.iloc[-1]['datetime']).total_seconds()/60
        if candle_age < 0: raise ValueError()
        if not history and candle_age>=limit+DURATION[interval]:
            return pd.DataFrame(),'Candles antigos na fonte; não usar para execução.'
        try:
            n=int(outputsize)
            if n <= 0: raise ValueError()
        except Exception:
            raise ValueError()
        df=df.tail(n).copy()
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


def cached_series(symbol,interval,outputsize=500,history=False):
    state,err=_load(_setting('GITHUB_TOKEN_HISTORICO'),_setting('GITHUB_REPO_HISTORICO'),_setting('GITHUB_BRANCH_HISTORICO','main'))
    if err: return pd.DataFrame(),err
    return read_series(state,symbol,interval,outputsize,history=history)


def clear_shared_cache():
    _load.clear()
