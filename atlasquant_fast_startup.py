"""AtlasQuant fast startup shell.

Interactive beginner mode reads one precomputed runtime snapshot and renders only
the requested beginner page. Heavy providers/backtests remain outside startup.
Autopilot/headless runs never use this shell, so background evidence generation
continues to execute the full application.

Safety: snapshot freshness is validated; stale/invalid data fails back to the
full app. This module never sends orders, changes gates, weights or providers.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from typing import Any, Mapping
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

SCHEMA="ATLASQUANT_HOME_SNAPSHOT_V1"
HOME_SNAPSHOT_PATH="dados/atlasquant_home_snapshot_v1.json"
DEFAULT_MAX_AGE_MIN=90.0
LEGACY_RUNTIME_PATHS={
    "inputs":"dados/autopilot_inputs_v107.json",
    "scanner":"dados/scanner_tecnico_v934.json",
    "master":"dados/master_market_map_v102.json",
    "news":"dados/currency_news_current_v107.json",
}


def _finite(value:Any, default:float=0.0)->float:
    try:
        x=float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def snapshot_age_minutes(snapshot:Mapping[str,Any]|None, *, now:datetime|None=None)->float|None:
    raw=str(dict(snapshot or {}).get("generated_at") or "").strip()
    if not raw:
        return None
    try:
        ts=pd.to_datetime(raw,utc=True,errors="raise")
        current=pd.Timestamp(now or datetime.now(timezone.utc))
        current=current.tz_localize("UTC") if current.tzinfo is None else current.tz_convert("UTC")
        age=(current-pd.Timestamp(ts)).total_seconds()/60.0
        return None if age<0 else float(age)
    except Exception:
        return None


def validate_home_snapshot(
    snapshot:Mapping[str,Any]|None,
    *,
    max_age_min:float=DEFAULT_MAX_AGE_MIN,
    now:datetime|None=None,
)->dict[str,Any]:
    s=dict(snapshot or {})
    errors=[]
    if str(s.get("schema") or "")!=SCHEMA:
        errors.append("schema")
    packs=s.get("packs")
    inputs=s.get("inputs")
    if not isinstance(packs,list) or not packs:
        errors.append("packs")
    if not isinstance(inputs,Mapping):
        errors.append("inputs")
    fast=dict((inputs or {}).get("fast_boot",{}) or {}) if isinstance(inputs,Mapping) else {}
    macro=dict((inputs or {}).get("macro_context",{}) or {}) if isinstance(inputs,Mapping) else {}
    if not macro:
        errors.append("macro_context")
    for key in ("ranking","fed","usd_detalhado"):
        if not fast.get(key):
            errors.append("fast_boot."+key)
    age=snapshot_age_minutes(s,now=now)
    if age is None:
        errors.append("generated_at")
    elif age>float(max_age_min):
        errors.append("stale")
    safety=dict(s.get("safety",{}) or {})
    if safety.get("real_orders") is not False:
        errors.append("real_orders")
    if safety.get("automatic_execution") is not False:
        errors.append("automatic_execution")
    return {
        "valid":not errors,
        "errors":errors,
        "age_minutes":age,
        "snapshot":s,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def legacy_ranking_rows(inputs:Mapping[str,Any]|None)->list[dict[str,Any]]:
    """Recover G8 relative-strength rows from the persisted 7-pair matrix."""
    src=dict(inputs or {}) if isinstance(inputs,Mapping) else {}
    macro=dict(src.get("macro_context",{}) or {})
    usd=max(0.0,min(100.0,_finite(macro.get("usd_score"),50.0)))
    scores={"USD":usd}
    for raw in list(src.get("pairs",[]) or []):
        row=dict(raw or {}) if isinstance(raw,Mapping) else {}
        pair=str(row.get("Par") or "").strip().upper()
        if "/" not in pair:
            continue
        base,quote=pair.split("/",1)
        diff=_finite(row.get("Dif. macro"),0.0)
        if quote=="USD" and base:
            scores[base]=max(0.0,min(100.0,usd+diff))
        elif base=="USD" and quote:
            scores[quote]=max(0.0,min(100.0,usd-diff))
    return [
        {
            "Código":code,
            "Moeda":code,
            "Pontuação_Macro":round(score,4),
            "Influência_Fed":0.0,
            "Pontuação_Final":round(score,4),
        }
        for code,score in sorted(scores.items(),key=lambda x:x[1],reverse=True)
    ]


def build_legacy_home_snapshot(
    inputs:Mapping[str,Any]|None,
    scanner:Mapping[str,Any]|None,
    master:Mapping[str,Any]|None,
    news:Mapping[str,Any]|None,
)->dict[str,Any]:
    """Build the fast Home from runtime artifacts that already exist today."""
    src=dict(inputs or {}) if isinstance(inputs,Mapping) else {}
    matrix=pd.DataFrame(list(src.get("pairs",[]) or []))
    ranking_rows=legacy_ranking_rows(src)
    ranking=pd.DataFrame(ranking_rows)
    macro=dict(src.get("macro_context",{}) or {})
    fed={
        "tom":str(macro.get("fed_tone") or "Neutro"),
        "forca":_finite(macro.get("fed_strength"),0.0),
    }
    packs=[]
    if not matrix.empty:
        try:
            from pair_intelligence_v110 import build_pair_intelligence_packs
            packs=build_pair_intelligence_packs(
                matrix,
                ranking,
                scanner_state=dict(scanner or {}),
                map_state=dict(master or {}),
                news_state=dict(news or {}),
                fed_tone=fed["tom"],
                weights=None,
            )
        except Exception:
            packs=[]

    enriched=dict(src)
    fast=dict(enriched.get("fast_boot",{}) or {})
    fast.setdefault("ranking",ranking_rows)
    fast.setdefault("fed",fed)
    fast.setdefault("usd_detalhado",{"score":_finite(macro.get("usd_score"),50.0)})
    fast["source"]="legacy-runtime-cache"
    enriched["fast_boot"]=fast
    return {
        "schema":SCHEMA,
        "generated_at":str(src.get("generated_at") or ""),
        "runtime_generated_at":str(src.get("generated_at") or ""),
        "engine_version":str(src.get("app_version") or "AtlasQuant Runtime"),
        "inputs":enriched,
        "packs":packs,
        "runtime":{
            "market_open":None,
            "scanner_pairs":len(dict(dict(scanner or {}).get("resultados",{}) or {})),
            "market_map_pairs":len(dict(dict(master or {}).get("contexts",{}) or {})),
            "news_available":bool(news),
            "fallback_source":"legacy-runtime-cache",
        },
        "safety":{
            "real_orders":False,
            "automatic_execution":False,
            "automatic_gate_change":False,
            "automatic_weight_change":False,
            "automatic_promotion":False,
        },
    }


def _runtime_json(
    repo:str,
    branch:str,
    token:str,
    path:str,
    timeout:float,
)->dict[str,Any]:
    repo=str(repo or "").strip()
    branch=str(branch or "atlasquant-runtime").strip()
    token=str(token or "").strip()
    path=str(path or "").lstrip("/")
    if not repo or "/" not in repo or not path:
        return {}
    raw_url=f"https://raw.githubusercontent.com/{repo}/{quote(branch,safe='')}/{path}"
    try:
        r=requests.get(raw_url,timeout=timeout,headers={"User-Agent":"AtlasQuant-FastBoot/1"})
        if r.ok:
            obj=r.json()
            return dict(obj) if isinstance(obj,Mapping) else {}
    except Exception:
        pass
    if not token:
        return {}
    try:
        api=f"https://api.github.com/repos/{repo}/contents/{path}"
        headers={
            "Authorization":f"Bearer {token}",
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
        }
        r=requests.get(api,headers=headers,params={"ref":branch},timeout=timeout)
        if not r.ok:
            return {}
        payload=r.json()
        encoded=str(payload.get("content") or "")
        if not encoded:
            return {}
        obj=json.loads(base64.b64decode(encoded).decode("utf-8"))
        return dict(obj) if isinstance(obj,Mapping) else {}
    except Exception:
        return {}


@st.cache_data(ttl=45,show_spinner=False)
def load_home_snapshot(
    repo:str,
    branch:str="atlasquant-runtime",
    token:str="",
    timeout:float=2.5,
)->dict[str,Any]:
    """One compact read when available; parallel legacy-cache fallback otherwise."""
    repo=str(repo or "").strip()
    branch=str(branch or "atlasquant-runtime").strip()
    token=str(token or "").strip()
    timeout=max(0.75,min(float(timeout),4.0))
    compact=_runtime_json(repo,branch,token,HOME_SNAPSHOT_PATH,timeout)
    if validate_home_snapshot(compact).get("valid"):
        return compact

    def get_item(item):
        key,path=item
        return key,_runtime_json(repo,branch,token,path,timeout)

    data={}
    try:
        with ThreadPoolExecutor(max_workers=len(LEGACY_RUNTIME_PATHS)) as pool:
            for key,obj in pool.map(get_item,LEGACY_RUNTIME_PATHS.items()):
                data[key]=obj
    except Exception:
        return compact
    legacy=build_legacy_home_snapshot(
        data.get("inputs",{}),
        data.get("scanner",{}),
        data.get("master",{}),
        data.get("news",{}),
    )
    return legacy if validate_home_snapshot(legacy).get("valid") else compact


def _brief_rows(snapshot:Mapping[str,Any])->list[dict[str,Any]]:
    fast=dict(dict(snapshot.get("inputs",{}) or {}).get("fast_boot",{}) or {})
    rows=[]
    for raw in list(fast.get("ranking",[]) or []):
        r=dict(raw or {})
        code=str(r.get("Código") or r.get("codigo") or "").strip()
        if not code:
            continue
        rows.append({
            "currency":code,
            "score":_finite(r.get("Pontuação_Final",r.get("score",50)),50),
            "data_ready":True,
            "quality":"snapshot",
        })
    return rows


def _brief_events(snapshot:Mapping[str,Any])->list[dict[str,Any]]:
    inputs=dict(snapshot.get("inputs",{}) or {})
    macro=dict(inputs.get("macro_context",{}) or {})
    event=dict(macro.get("event",{}) or {})
    if not event or not event.get("disponivel"):
        return []
    return [{
        "event":str(event.get("evento") or "Evento macro"),
        "currency":"USD",
        "datetime":str(event.get("data_txt") or event.get("data") or ""),
        "impact":str(event.get("impacto") or ""),
        "data_ready":True,
        "quality":"snapshot",
    }]


def render_beginner_shell(
    snapshot:Mapping[str,Any],
    *,
    access:Mapping[str,Any]|None=None,
    app_version:str="",
    environment:str="",
)->dict[str,Any]:
    """Render one beginner page only. Caller should st.stop() when handled=True."""
    current=str(st.session_state.get("atlasquant_experience_mode","Iniciante") or "Iniciante")
    if current.casefold().startswith("avan"):
        return {"handled":False,"mode":"Avançado"}

    check=validate_home_snapshot(snapshot)
    if not check["valid"]:
        return {"handled":False,"mode":"Iniciante","snapshot_valid":False,"errors":check["errors"]}

    mode=st.radio(
        "Experiência",
        ["Iniciante","Avançado"],
        index=0,
        horizontal=True,
        key="atlasquant_experience_mode",
        help="Iniciante abre rápido e mostra só o essencial. Avançado libera todos os diagnósticos.",
    )
    if str(mode).casefold().startswith("avan"):
        st.rerun()

    age=float(check["age_minutes"] or 0.0)
    st.markdown(
        """<div style="border:1px solid rgba(137,170,210,.18);border-radius:16px;padding:13px 16px;
        background:linear-gradient(120deg,rgba(17,43,72,.96),rgba(8,25,43,.94));margin:2px 0 10px">
        <strong style="font-size:1.15rem">🧭 AtlasQuant</strong><br>
        <span style="opacity:.72;font-size:.78rem">Modo Iniciante · carregamento rápido por snapshot validado</span>
        </div>""",
        unsafe_allow_html=True,
    )
    c1,c2=st.columns([4,1])
    with c1:
        st.caption(f"Dados calculados há {age:.0f} min · {environment or 'AtlasQuant'} · Engine {app_version}")
    with c2:
        if st.button("↻ Atualizar",key="aq_fast_refresh",width="stretch"):
            load_home_snapshot.clear()
            st.rerun()

    pages=["🎯 Radar","🎙️ Macro","🎓 Aprender","👤 Conta","📱 Instalar","🛟 Suporte"]
    page=st.radio("Área",pages,horizontal=True,key="aq_beginner_page",label_visibility="collapsed")

    if page=="🎯 Radar":
        from atlasquant_home_radar import render_home_radar
        _inputs=dict(snapshot.get("inputs",{}) or {})
        _macro=dict(_inputs.get("macro_context",{}) or {})
        _fast=dict(_inputs.get("fast_boot",{}) or {})
        _macro["fed"]=dict(_fast.get("fed",{}) or {})
        render_home_radar(
            list(snapshot.get("packs",[]) or []),
            experience_mode="Iniciante",
            macro_context=_macro,
        )
    elif page=="🎙️ Macro":
        from atlasquant_macro_briefing_panel import render_macro_briefing_panel
        fast=dict(dict(snapshot.get("inputs",{}) or {}).get("fast_boot",{}) or {})
        fed=dict(fast.get("fed",{}) or {})
        banks=[{
            "bank":"Federal Reserve",
            "tone":str(fed.get("tom") or "Neutro"),
            "data_ready":True,
            "quality":"snapshot",
        }]
        render_macro_briefing_panel(_brief_rows(snapshot),_brief_events(snapshot),banks)
    elif page=="🎓 Aprender":
        from atlasquant_academy import render_academy_panel
        render_academy_panel()
    elif page=="👤 Conta":
        from atlasquant_account_portal import render_account_portal
        render_account_portal(dict(access or {}))
    elif page=="📱 Instalar":
        from atlasquant_platform_center import render_platform_center
        render_platform_center()
    else:
        from atlasquant_support_center import render_support_center
        render_support_center()

    st.caption("Modo Iniciante não conecta corretora e não envia ordens reais.")
    return {
        "handled":True,
        "mode":"Iniciante",
        "page":page,
        "snapshot_valid":True,
        "snapshot_age_minutes":age,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


__all__=[
    "SCHEMA","HOME_SNAPSHOT_PATH","DEFAULT_MAX_AGE_MIN","LEGACY_RUNTIME_PATHS",
    "snapshot_age_minutes","legacy_ranking_rows","build_legacy_home_snapshot",
    "validate_home_snapshot","load_home_snapshot","render_beginner_shell",
]
