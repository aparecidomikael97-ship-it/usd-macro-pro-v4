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
from datetime import datetime, timezone
import json
import math
import time
from typing import Any, Mapping
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

try:
    from atlasquant_ui_v1 import (
        experience_compass_html,
        experience_mode_overview_html,
        mobile_navigation_hint_html,
    )
except Exception:
    experience_compass_html = None
    experience_mode_overview_html = None
    mobile_navigation_hint_html = None

SCHEMA="ATLASQUANT_HOME_SNAPSHOT_V1"
HOME_SNAPSHOT_PATH="dados/atlasquant_home_snapshot_v1.json"
DEFAULT_MAX_AGE_MIN=90.0
DEFAULT_MAX_RUNTIME_AGE_MIN=90.0
EXPECTED_FX_PAIRS=("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD")


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
    for key in ("ranking","fed","macro_eua","dados_moedas","usd_detalhado"):
        if not fast.get(key):
            errors.append("fast_boot."+key)
    # The Autopilot may refresh decision packs more recently than the slower
    # macro/input payload. Prefer that real runtime timestamp for Fast Home
    # freshness; older snapshots remain compatible through generated_at.
    freshness=dict(s)
    runtime_generated_at=str(s.get("runtime_generated_at") or "").strip()
    if runtime_generated_at:
        freshness["generated_at"]=runtime_generated_at
    age=snapshot_age_minutes(freshness,now=now)
    input_age=snapshot_age_minutes({"generated_at":s.get("generated_at")},now=now)
    if age is None:
        errors.append("generated_at")
    elif age>float(DEFAULT_MAX_RUNTIME_AGE_MIN if runtime_generated_at else max_age_min):
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
        "input_age_minutes":input_age,
        "snapshot":s,
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


def validated_snapshot_pair_matrix(
    snapshot:Mapping[str,Any]|None,
    *,
    max_age_min:float=DEFAULT_MAX_AGE_MIN,
    now:datetime|None=None,
)->dict[str,Any]:
    """Build a fail-closed 7-pair matrix from a validated runtime snapshot.

    This fallback is presentation/data-continuity only. It never enables real
    orders or automatic execution, and invalid/stale snapshots are rejected.
    """
    check=validate_home_snapshot(snapshot,max_age_min=max_age_min,now=now)
    empty=pd.DataFrame()
    if not check["valid"]:
        return {
            "ready":False,
            "reason":"snapshot inválido: "+",".join(check["errors"]),
            "matrix":empty,
            "source":"runtime_snapshot",
            "age_minutes":check.get("age_minutes"),
            "real_orders_enabled":False,
            "automatic_execution":False,
        }

    s=dict(check["snapshot"] or {})
    inputs=dict(s.get("inputs",{}) or {})
    raw_pairs=inputs.get("pairs")
    if not isinstance(raw_pairs,list) or not raw_pairs:
        return {
            "ready":False,"reason":"snapshot sem inputs.pairs","matrix":empty,
            "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
            "real_orders_enabled":False,"automatic_execution":False,
        }

    rows=[]
    seen=set()
    required={"Par","Direção","Score final","Qualidade"}
    for raw in raw_pairs:
        if not isinstance(raw,Mapping):
            return {
                "ready":False,"reason":"linha de par inválida","matrix":empty,
                "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
                "real_orders_enabled":False,"automatic_execution":False,
            }
        row=dict(raw)
        if not required.issubset(row):
            return {
                "ready":False,"reason":"colunas obrigatórias ausentes","matrix":empty,
                "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
                "real_orders_enabled":False,"automatic_execution":False,
            }
        pair=str(row.get("Par") or "").strip().upper()
        direction=str(row.get("Direção") or "").strip()
        if pair not in EXPECTED_FX_PAIRS or pair in seen or not direction:
            return {
                "ready":False,"reason":"universo/duplicidade de pares inválido","matrix":empty,
                "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
                "real_orders_enabled":False,"automatic_execution":False,
            }
        try:
            score=float(row.get("Score final"))
            quality=float(row.get("Qualidade"))
        except Exception:
            return {
                "ready":False,"reason":"score/qualidade inválidos","matrix":empty,
                "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
                "real_orders_enabled":False,"automatic_execution":False,
            }
        if not (math.isfinite(score) and math.isfinite(quality)):
            return {
                "ready":False,"reason":"score/qualidade não finitos","matrix":empty,
                "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
                "real_orders_enabled":False,"automatic_execution":False,
            }
        row["Par"]=pair
        row["Direção"]=direction
        row["Score final"]=score
        row["Qualidade"]=quality
        rows.append(row)
        seen.add(pair)

    if len(rows)!=len(EXPECTED_FX_PAIRS) or seen!=set(EXPECTED_FX_PAIRS):
        return {
            "ready":False,"reason":"snapshot não contém os 7 pares oficiais","matrix":empty,
            "source":"runtime_snapshot","age_minutes":check.get("age_minutes"),
            "real_orders_enabled":False,"automatic_execution":False,
        }

    matrix=pd.DataFrame(rows)
    if "Ranking" not in matrix.columns:
        matrix.insert(0,"Ranking",range(1,len(matrix)+1))
    return {
        "ready":True,
        "reason":"snapshot runtime validado",
        "matrix":matrix,
        "source":"runtime_snapshot",
        "age_minutes":check.get("age_minutes"),
        "real_orders_enabled":False,
        "automatic_execution":False,
    }


@st.cache_data(ttl=45,show_spinner=False)
def load_home_snapshot(
    repo:str,
    branch:str="atlasquant-runtime",
    token:str="",
    timeout:float=4.0,
)->dict[str,Any]:
    """Read one compact runtime artifact with a bounded private/public fallback."""
    repo=str(repo or "").strip()
    branch=str(branch or "atlasquant-runtime").strip()
    token=str(token or "").strip()
    if not repo or "/" not in repo:
        return {}
    timeout=max(1.0,min(float(timeout),8.0))
    started=time.perf_counter()

    def _with_obs(obj:Any, source:str)->dict[str,Any]:
        out=dict(obj) if isinstance(obj,Mapping) else {}
        if out:
            out["_fast_boot_observability"]={
                "source":source,
                "load_ms":round((time.perf_counter()-started)*1000),
            }
        return out

    if token:
        try:
            api=f"https://api.github.com/repos/{repo}/contents/{HOME_SNAPSHOT_PATH}"
            headers={
                "Authorization":f"Bearer {token}",
                "Accept":"application/vnd.github+json",
                "X-GitHub-Api-Version":"2022-11-28",
            }
            r=requests.get(api,headers=headers,params={"ref":branch},timeout=timeout)
            if r.ok:
                payload=r.json()
                encoded=str(payload.get("content") or "")
                if encoded:
                    obj=json.loads(base64.b64decode(encoded).decode("utf-8"))
                    out=_with_obs(obj,"api")
                    if out:
                        return out
        except Exception:
            pass

    raw_url=f"https://raw.githubusercontent.com/{repo}/{quote(branch,safe='')}/{HOME_SNAPSHOT_PATH}"
    try:
        r=requests.get(raw_url,timeout=timeout,headers={"User-Agent":"AtlasQuant-FastBoot/1"})
        if r.ok:
            out=_with_obs(r.json(),"raw")
            if out:
                return out
    except Exception:
        pass
    return {}


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


def _render_beginner_chrome(app_version:str, environment:str, access:Mapping[str,Any]|None=None)->None:
    """Show the shared AtlasQuant surface before the fast shell stops the script."""
    try:
        from atlasquant_ui_v1 import (
            apply_atlasquant_theme,
            render_account_identity,
            render_atlasquant_header,
        )
        apply_atlasquant_theme()
        render_atlasquant_header(
            app_version or "AtlasQuant",
            environment or "LOCAL",
            build_id=str(st.session_state.get("atlasquant_visible_build") or ""),
        )
        render_account_identity(dict(access) if isinstance(access,Mapping) else None)
    except Exception:
        st.markdown("## 🧭 AtlasQuant")


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
        mode=st.radio(
            "Experiência",["Iniciante","Avançado"],index=0,horizontal=True,
            key="atlasquant_experience_mode",
            help="Iniciante aguarda snapshot válido. Avançado abre os diagnósticos completos.",
        )
        st.session_state["_aq_experience_switch_mounted"] = True
        if str(mode).casefold().startswith("avan"):
            return {
                "handled":False,"mode":"Avançado","snapshot_valid":False,
                "errors":check["errors"],"real_orders_enabled":False,
                "automatic_execution":False,
            }
        _render_beginner_chrome(app_version, environment, access)
        st.warning("Radar temporariamente aguardando dados válidos.")
        st.caption("O snapshot não passou na validação de frescor/segurança. Nenhuma oportunidade é exibida até a próxima atualização válida.")
        if st.button("↻ Tentar atualizar",key="aq_fast_invalid_refresh",width="stretch"):
            load_home_snapshot.clear()
            st.rerun()
        return {
            "handled":True,
            "mode":"Iniciante",
            "page":"SAFE_WAIT",
            "snapshot_valid":False,
            "errors":check["errors"],
            "real_orders_enabled":False,
            "automatic_execution":False,
        }

    mode=st.radio(
        "Experiência",
        ["Iniciante","Avançado"],
        index=0,
        horizontal=True,
        key="atlasquant_experience_mode",
        help="Iniciante abre rápido e mostra só o essencial. Avançado libera todos os diagnósticos.",
    )
    st.session_state["_aq_experience_switch_mounted"] = True
    if str(mode).casefold().startswith("avan"):
        # The widget interaction already updates session state. Continue into the
        # full app in this same run instead of forcing a second React/Streamlit
        # rerender at the mobile mode-switch boundary.
        return {
            "handled":False,
            "mode":"Avançado",
            "snapshot_valid":True,
            "snapshot_age_minutes":float(check["age_minutes"] or 0.0),
            "real_orders_enabled":False,
            "automatic_execution":False,
        }

    _fast_pages=["🎯 Radar","🎙️ Macro","🎓 Aprender","👤 Conta","📱 Instalar","💰 Investir","🛟 Suporte"]
    try:
        from atlasquant_premium_shell import (
            consume_premium_navigation,
            render_premium_catalog,
            workspace_welcome_html,
        )
        consume_premium_navigation(
            st.session_state,
            mode="Iniciante",
            available_pages=_fast_pages,
            fast=True,
        )
    except Exception:
        render_premium_catalog = None
        workspace_welcome_html = None

    age=float(check["age_minutes"] or 0.0)
    _obs=dict(snapshot.get("_fast_boot_observability",{}) or {})
    st.session_state["atlasquant_fast_boot_observability"]={
        "source":str(_obs.get("source") or "unknown"),
        "load_ms":int(_finite(_obs.get("load_ms"),0)),
        "snapshot_age_minutes":round(age,2),
        "input_age_minutes":check.get("input_age_minutes"),
        "snapshot_valid":True,
        "mode":"Iniciante",
    }
    _render_beginner_chrome(app_version, environment, access)
    _dock_pages=list(_fast_pages)
    if str(dict(access or {}).get("role") or "").upper()=="ADMIN":
        _dock_pages.append("🧠 AION")
    try:
        from atlasquant_voice_assistant import render_top_voice_access
        render_top_voice_access(st.session_state, pages=_dock_pages, fast=True)
    except Exception:
        pass
    pages=_fast_pages
    _aq_fast_active_page=str(st.session_state.get("aq_beginner_page") or "🎯 Radar")
    _aq_fast_catalog_home=bool(
        render_premium_catalog is not None
        and _aq_fast_active_page=="🎯 Radar"
    )

    input_age=check.get("input_age_minutes")
    age_label=f"Runtime atualizado há {age:.0f} min"
    if isinstance(input_age,(int,float)) and input_age>age+1:
        age_label+=f" · base macro há {float(input_age):.0f} min"

    if _aq_fast_catalog_home:
        # O Radar já mostra estado, idade, atualização e origem na faixa de frescor.
        # Mantém aqui somente a ação manual para evitar repetir telemetria no topo.
        _spacer,_refresh=st.columns([4,1])
        with _refresh:
            if st.button("↻ Atualizar",key="aq_fast_refresh",width="stretch"):
                load_home_snapshot.clear()
                st.rerun()
    else:
        # Fora da home, os detalhes técnicos seguem disponíveis sob demanda sem
        # ocupar permanentemente o topo de cada workspace.
        with st.expander("Dados do snapshot",expanded=False):
            st.caption(f"{age_label} · {environment or 'AtlasQuant'} · Engine {app_version}")
            if st.button("↻ Atualizar",key="aq_fast_refresh",width="stretch"):
                load_home_snapshot.clear()
                st.rerun()
    _aq_fast_ticker_items=[]
    if _aq_fast_catalog_home:
        try:
            _aq_fast_boot=dict(dict(snapshot.get("inputs",{}) or {}).get("fast_boot",{}) or {})
            for _aq_tick in list(_aq_fast_boot.get("ranking",[]) or [])[:8]:
                if not isinstance(_aq_tick,dict):
                    continue
                _aq_code=str(_aq_tick.get("Código") or _aq_tick.get("currency") or "").strip()
                if not _aq_code:
                    continue
                _aq_fast_ticker_items.append({
                    "label":_aq_code,
                    "score":_finite(_aq_tick.get("Pontuação_Final",_aq_tick.get("score",50)),50),
                })
        except Exception:
            _aq_fast_ticker_items=[]
    if render_premium_catalog is not None:
        render_premium_catalog(
            mode="Iniciante",
            available_pages=pages,
            fast=True,
            active_page=_aq_fast_active_page,
            ticker_items=_aq_fast_ticker_items,
        )
    if _aq_fast_catalog_home:
        with st.expander("Navegação alternativa",expanded=False):
            st.caption("Use o seletor clássico se preferir. O cockpit continua sendo a entrada visual principal da home.")
            page=st.radio("Área",pages,horizontal=True,key="aq_beginner_page",label_visibility="collapsed")
    else:
        page=st.radio("Área",pages,horizontal=True,key="aq_beginner_page",label_visibility="collapsed")
    if workspace_welcome_html is not None and page != "🎯 Radar":
        _welcome = workspace_welcome_html(page, mode="Iniciante")
        if _welcome:
            st.markdown(_welcome, unsafe_allow_html=True)
    if experience_compass_html is not None and page != "🎯 Radar":
        st.markdown(
            experience_compass_html("Iniciante", page),
            unsafe_allow_html=True,
        )

    if page=="🎯 Radar":
        from atlasquant_home_radar import render_home_radar
        _inputs=dict(snapshot.get("inputs",{}) or {})
        _macro=dict(_inputs.get("macro_context",{}) or {})
        _fast=dict(_inputs.get("fast_boot",{}) or {})
        _macro["fed"]=dict(_fast.get("fed",{}) or {})
        _transport=str(_obs.get("source") or "").strip()
        _freshness={
            "state":"VALIDATED_SNAPSHOT",
            "generated_at":str(snapshot.get("runtime_generated_at") or snapshot.get("generated_at") or ""),
            "age_minutes":age,
            "refresh_status":"carregamento rápido concluído",
            "source":"runtime snapshot" + (f" · {_transport}" if _transport else ""),
        }
        render_home_radar(
            list(snapshot.get("packs",[]) or []),
            experience_mode="Iniciante",
            macro_context=_macro,
            ranking=list(_fast.get("ranking",[]) or []),
            separate_observations={
                "indices": list(_fast.get("indices",[]) or []),
                "cryptos": list(_fast.get("cryptos",[]) or []),
            },
            freshness=_freshness,
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
    elif page=="💰 Investir":
        from atlasquant_investment_panel import render_investment_center
        render_investment_center("Iniciante")
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
    "SCHEMA","HOME_SNAPSHOT_PATH","DEFAULT_MAX_AGE_MIN","DEFAULT_MAX_RUNTIME_AGE_MIN","snapshot_age_minutes",
    "validate_home_snapshot","validated_snapshot_pair_matrix","EXPECTED_FX_PAIRS","load_home_snapshot","render_beginner_shell",
]