"""USD Macro Pro V11.0 — Central Institucional dos 7 Pares.

Uma única tela para decisão: macro, notícias, top-down, liquidez, ICT,
fluxo institucional, técnico, ADR, evento e Gate.
Abrir esta aba NÃO chama Twelve Data.
"""
from __future__ import annotations

import base64
import json
import math
import os
import time
from typing import Any, Mapping

import numpy as np
import pandas as pd
import requests
import streamlit as st

from decision_integrity_v110 import evaluate_decision_integrity
from data_readiness_v1101 import assess_pair_data_readiness, display_component_status, premium_discount_operational

try:
    from currency_news_v107 import pair_news_table
except Exception:
    pair_news_table = None

PAIR_ORDER=("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD")
MAJORS=("USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD")
SCANNER_PATH="dados/scanner_tecnico_v934.json"
MAP_PATH="dados/master_market_map_v102.json"
NEWS_PATH="dados/currency_news_current_v107.json"
AUTO_PATH="dados/autopilot_status_v107.json"


def _safe(v, default=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _gh_cfg():
    try:
        token=st.secrets.get("GITHUB_TOKEN_HISTORICO",os.getenv("GITHUB_TOKEN_HISTORICO",""))
        repo=st.secrets.get("GITHUB_REPO_HISTORICO",os.getenv("GITHUB_REPO_HISTORICO",""))
        branch=st.secrets.get("GITHUB_BRANCH_HISTORICO",os.getenv("GITHUB_BRANCH_HISTORICO","main"))
    except Exception:
        token,repo,branch="","","main"
    return str(token),str(repo),str(branch or "main")


@st.cache_data(ttl=60,show_spinner=False)
def _read_json(path:str,_token:str,_repo:str,_branch:str):
    if not _token or not _repo:
        return {},"Persistência GitHub não configurada."
    try:
        url=f"https://api.github.com/repos/{_repo}/contents/{path}"
        headers={"Authorization":f"Bearer {_token}","Accept":"application/vnd.github+json"}
        r=requests.get(url,headers=headers,params={"ref":_branch},timeout=15)
        if r.status_code==404:
            return {},""
        r.raise_for_status()
        raw=base64.b64decode(r.json().get("content","")).decode("utf-8")
        return json.loads(raw) if raw else {},""
    except Exception as exc:
        return {},f"{type(exc).__name__}: {exc}"


def _side(direction:str)->str:
    u=str(direction).upper()
    return "BUY" if "COMPRA" in u else "SELL" if "VENDA" in u else "WAIT"


def _status_score(s:str)->float:
    u=str(s).upper()
    if "🟢" in s or "CONFIRMA" in u or "GATILHO" in u or "PULLBACK OK" in u:
        return 100
    if "🟡" in s or "PARCIAL" in u or "ALINHADO" in u or "AGUARDAR" in u or "ESTICADO" in u:
        return 60
    if "🔴" in s or "CONTRA" in u or "SEM GATILHO" in u:
        return 20
    return 45


def _trend_matches(bias:str,side:str):
    b=str(bias).upper()
    if "ALT" in b: return side=="BUY"
    if "BAIX" in b: return side=="SELL"
    return None


def _fmt_price(v,pair):
    try:
        x=float(v)
        return f"{x:.3f}" if "JPY" in pair else f"{x:.5f}"
    except Exception:
        return "—"


def _currency_score(ranking:pd.DataFrame,code:str)->float:
    if ranking is None or ranking.empty:
        return 50.0
    for col in ("Pontuação_Final","Pontuação Macro","Pontuação_Macro"):
        if col in ranking.columns:
            f=ranking[ranking["Código"].astype(str)==code]
            if not f.empty:
                return _safe(f.iloc[0][col],50)
    return 50.0


def _pair_news(news_state:Mapping[str,Any],matrix:pd.DataFrame):
    if not news_state or pair_news_table is None:
        return {}
    try:
        df=pair_news_table(news_state,matrix)
        return {str(r["Par"]):r.to_dict() for _,r in df.iterrows()}
    except Exception:
        return {}


def _age_minutes(value:Any)->float|None:
    if value in (None,"",0,0.0):
        return None
    try:
        if isinstance(value,(int,float)):
            ts=pd.Timestamp(float(value),unit="s",tz="UTC")
        else:
            ts=pd.to_datetime(value,utc=True)
        return max(0.0,(pd.Timestamp.now(tz="UTC")-ts).total_seconds()/60)
    except Exception:
        return None


def _dict_bias(v:Any)->str:
    if isinstance(v,Mapping):
        return str(v.get("bias",v.get("trend","—")))
    return str(v or "—")


def _map_normalize(ctx:Mapping[str,Any]|None,pair:str)->dict[str,Any]:
    c=dict(ctx or {})
    w1=str(c.get("w1_bias") or _dict_bias(c.get("w1")) or "—")
    d1=str(c.get("d1_bias") or _dict_bias(c.get("d1")) or "—")
    pd_raw=c.get("premium_discount",c.get("location","—"))
    if isinstance(pd_raw,Mapping):
        pd_zone=str(pd_raw.get("zone","—"))
        pd_pos=pd_raw.get("position")
    else:
        pd_zone=str(pd_raw or "—"); pd_pos=c.get("pd_position")

    latest=c.get("latest_sweep")
    sweep_type=""; sweep_level=""; sweep_price=None; sweep_rej=""; sweep_time=""
    if isinstance(latest,Mapping):
        sweep_type=str(latest.get("type","")); sweep_level=str(latest.get("level",""))
        sweep_price=latest.get("price"); sweep_rej=str(latest.get("rejection","")); sweep_time=str(latest.get("datetime",""))
    else:
        sweep_type=str(latest or "")
        sweep_level=str(c.get("latest_sweep_level","") or "")
        sweep_price=c.get("latest_sweep_price")
        sweep_rej=str(c.get("latest_sweep_rejection","") or "")
        sweep_time=str(c.get("latest_sweep_time","") or "")

    def _liq(prefix):
        name=c.get(f"{prefix}_name"); price=c.get(f"{prefix}_price")
        if name or price is not None: return str(name or prefix.upper()),price
        raw=c.get(prefix)
        if isinstance(raw,(list,tuple)) and len(raw)>=2: return str(raw[0]),raw[1]
        if isinstance(raw,Mapping): return str(raw.get("name",prefix.upper())),raw.get("price")
        return prefix.upper(),None
    bsl_name,bsl_price=_liq("bsl"); ssl_name,ssl_price=_liq("ssl")
    levels=dict(c.get("levels",{}) or {})
    return {
        "w1":w1,"d1":d1,"pd_zone":pd_zone,"pd_position":pd_pos,
        "sweep_type":sweep_type,"sweep_level":sweep_level,"sweep_price":sweep_price,
        "sweep_rejection":sweep_rej,"sweep_time":sweep_time,
        "gate":str(c.get("readiness_grade","—")),"gate_score":_safe(c.get("readiness_score",0)),
        "adr":_safe(c.get("adr_used_pct",0)),"event":str(c.get("event_risk","NORMAL")),
        "price":c.get("price"),"bsl_name":bsl_name,"bsl_price":bsl_price,
        "ssl_name":ssl_name,"ssl_price":ssl_price,"levels":levels,
    }


def _component(inst:Mapping[str,Any],key:str)->dict[str,Any]:
    return dict((inst or {}).get(key,{}) or {})


def _reason_pack(pair,row,ranking,scanner,mapctx,news,fed_tone="Neutro"):
    side=_side(row.get("Direção","")); base,quote=pair.split("/")
    base_score=_currency_score(ranking,base); quote_score=_currency_score(ranking,quote)
    macro_diff=_safe(row.get("Dif. macro",base_score-quote_score))
    score=_safe(row.get("Score final",0)); quality=_safe(row.get("Qualidade",0)); idx=_safe(row.get("Índice ranking",0))

    raw_sc=dict(scanner or {}); tec=dict(raw_sc.get("tecnico",{}) or {})
    h4=str((tec.get("h4",{}) or {}).get("status","—")); h1=str((tec.get("h1",{}) or {}).get("status","—")); m15=str((tec.get("m15",{}) or {}).get("status","—"))
    ict=dict(tec.get("ict",{}) or {}); ict_read=_safe(ict.get("readiness",0)); ict_label=str(ict.get("label","⏳ aguardando ICT"))
    inst=dict(tec.get("institutional",{}) or {}); inst_read=_safe(inst.get("readiness",0)); inst_label=str(inst.get("label","⏳ aguardando motor institucional"))
    data_ready=assess_pair_data_readiness(raw_sc,mapctx)
    age=(data_ready.get("timeframes",{}).get("m15",{}) or {}).get("age_minutes")

    mc=_map_normalize(mapctx,pair)
    w1,d1=mc["w1"],mc["d1"]
    gate,gate_score=mc["gate"],mc["gate_score"]
    pd_zone=mc["pd_zone"]; adr=mc["adr"]; event=mc["event"]
    price=mc["price"] if mc["price"] is not None else tec.get("preco_m15")

    news_diff=_safe((news or {}).get("Diferencial notícias",0)); news_align=str((news or {}).get("Alinhamento","—")); news_conv=_safe((news or {}).get("Convicção heurística",0))

    up=[]; down=[]; evidence=[]
    if macro_diff>0: up.append(f"{base} está {abs(macro_diff):.1f} pts mais forte que {quote} no macro relativo")
    elif macro_diff<0: down.append(f"{quote} está {abs(macro_diff):.1f} pts mais forte que {base} no macro relativo")
    if news_diff>=2: up.append(f"notícias favorecem a moeda base ({news_diff:+.2f})")
    elif news_diff<=-2: down.append(f"notícias favorecem a moeda cotada ({news_diff:+.2f})")

    for tf,status in (("H4",h4),("H1",h1),("M15",m15)):
        ss=_status_score(status)
        if side=="BUY" and ss>=80: up.append(f"{tf} confirma compra")
        elif side=="SELL" and ss>=80: down.append(f"{tf} confirma venda")
    for tf,bias in (("W1",w1),("D1",d1)):
        match=_trend_matches(bias,side)
        if match is True: (up if side=="BUY" else down).append(f"{tf} alinhado ao viés")

    # Sweep sem dicionário bruto.
    if mc["sweep_type"]:
        coherent=(side=="BUY" and "SSL" in mc["sweep_type"].upper()) or (side=="SELL" and "BSL" in mc["sweep_type"].upper())
        msg=f"{mc['sweep_type']} em {mc['sweep_level'] or 'nível'} ({_fmt_price(mc['sweep_price'],pair)})"
        if coherent: (up if side=="BUY" else down).append("liquidez: "+msg)
        evidence.append(msg)

    # Componentes ICT + Institucionais.
    for key,label in (("crt","CRT"),("amd","AMD/PO3"),("ote","OTE"),("fvg","FVG")):
        comp=dict(ict.get(key,{}) or {}); status=str(comp.get("status",""))
        if "🟢" in status: (up if side=="BUY" else down).append(f"{label}: {status.replace('🟢','').strip()}")
    for key,label in (("mss","MSS"),("displacement","Displacement"),("smt","SMT"),("dealing_range","Premium/Discount"),("session","Judas/Sessão"),("pd_array","Breaker/Mitigation"),("liquidity","Draw on Liquidity")):
        comp=_component(inst,key); status=str(comp.get("status",""))
        if "🟢" in status: (up if side=="BUY" else down).append(f"{label}: {status.replace('🟢','').strip()}")

    ft=str(fed_tone).upper()
    if "USD" in pair and ("RESTR" in ft or "HAWK" in ft):
        (up if base=="USD" else down).append("Fed restritivo/hawkish dá suporte estrutural ao USD")
    elif "USD" in pair and ("DOV" in ft or "EXPANS" in ft):
        (down if base=="USD" else up).append("Fed dovish reduz suporte estrutural ao USD")

    decision=evaluate_decision_integrity(
        side=side,score=score,quality=quality,rank_index=idx,h4=h4,h1=h1,m15=m15,
        ict_readiness=ict_read,institutional_readiness=inst_read,gate=gate,gate_score=gate_score,
        adr_used_pct=adr,event_risk=event,technical_age_min=age,news_alignment=news_align,
        data_sufficient=bool(data_ready.get("sufficient",False)),
        data_readiness_score=_safe(data_ready.get("score",0)),
    )
    state=decision["state"]

    reason=(up[0] if side=="BUY" and up else down[0] if side=="SELL" and down else "força relativa/confluência ainda não definiu o lado")
    target="—"
    if side=="BUY" and mc["bsl_price"] is not None: target=f"{mc['bsl_name']} {_fmt_price(mc['bsl_price'],pair)}"
    elif side=="SELL" and mc["ssl_price"] is not None: target=f"{mc['ssl_name']} {_fmt_price(mc['ssl_price'],pair)}"
    # fallback do motor institucional
    if target=="—":
        liq=_component(inst,"liquidity")
        if liq.get("target_price") is not None: target=f"{liq.get('target_type','LIQ')} {_fmt_price(liq.get('target_price'),pair)}"

    return {
        "pair":pair,"side":side,"direction":str(row.get("Direção","⚪ AGUARDAR")),"state":state,
        "priority":_safe(decision.get("priority_score",0)),"score":score,"quality":quality,"index":idx,
        "base_score":base_score,"quote_score":quote_score,"macro_diff":macro_diff,
        "h4":h4,"h1":h1,"m15":m15,"w1":w1,"d1":d1,"gate":gate,"gate_score":gate_score,
        "pd_zone":pd_zone,"pd_position":mc["pd_position"],"adr":adr,"event":event,"price":price,
        "sweep_type":mc["sweep_type"],"sweep_level":mc["sweep_level"],"sweep_price":mc["sweep_price"],"sweep_rejection":mc["sweep_rejection"],
        "levels":mc["levels"],"news_diff":news_diff,"news_align":news_align,"news_conv":news_conv,
        "ict":ict,"ict_read":ict_read,"ict_label":ict_label,"inst":inst,"inst_read":inst_read,"inst_label":inst_label,
        "up":up,"down":down,"reason":reason,"next_action":decision["next_action"],"target":target,
        "hard_blocks":decision["hard_blocks"],"soft_blocks":decision["soft_blocks"],"positives":decision["positives"],
        "executable":decision["executable"],"technical_age":age,"data_ready":data_ready,
    }


def _css():
    st.markdown("""
    <style>
      .v110-hero{padding:22px 24px;border:1px solid rgba(99,102,241,.28);border-radius:20px;background:linear-gradient(135deg,#0f172a,#172554 58%,#0f766e);color:white;margin-bottom:14px;box-shadow:0 8px 26px rgba(15,23,42,.16)}
      .v110-hero h2{margin:0 0 6px 0;color:white}.v110-hero p{margin:0;color:#dbeafe}
      .v110-badge{display:inline-block;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.12);margin:8px 6px 0 0;font-size:.85rem}
      div[data-testid="stMetric"]{border:1px solid rgba(100,116,139,.18);padding:10px;border-radius:14px}
    </style>
    """,unsafe_allow_html=True)


def _major_extremes(ranking:pd.DataFrame)->tuple[str,str]:
    if ranking is None or ranking.empty or "Código" not in ranking.columns:
        return "—","—"
    r=ranking[ranking["Código"].astype(str).isin(MAJORS)].copy()
    if r.empty: return "—","—"
    col=next((c for c in ("Pontuação_Final","Pontuação_Macro","Pontuação Macro") if c in r.columns),None)
    if col:
        r=r.sort_values(col,ascending=False)
    return str(r.iloc[0]["Código"]),str(r.iloc[-1]["Código"])


def _stack_rows(p:Mapping[str,Any])->pd.DataFrame:
    ict=p.get("ict",{}) or {}; inst=p.get("inst",{}) or {}
    rows=[
        ("Macro","Direção",p.get("direction","—"),p.get("score",0)),
        ("Macro","Força relativa",f"{p.get('macro_diff',0):+.1f} pts",None),
        ("Contexto","W1",p.get("w1","—"),None),
        ("Contexto","D1",p.get("d1","—"),None),
        ("Liquidez","Sweep",f"{p.get('sweep_type') or '—'} {p.get('sweep_level') or ''}".strip(),None),
        ("Institucional","SMT",_component(inst,"smt").get("status","—"),_component(inst,"smt").get("score")),
        ("Institucional","Displacement",_component(inst,"displacement").get("status","—"),_component(inst,"displacement").get("score")),
        ("Institucional","MSS",_component(inst,"mss").get("status","—"),_component(inst,"mss").get("score")),
        ("Institucional","Premium/Discount",_component(inst,"dealing_range").get("status",p.get("pd_zone","—")),_component(inst,"dealing_range").get("score")),
        ("Institucional","Judas/Sessão",_component(inst,"session").get("status","—"),_component(inst,"session").get("score")),
        ("Institucional","Breaker/Mitigation",_component(inst,"pd_array").get("status","—"),_component(inst,"pd_array").get("score")),
        ("ICT","CRT",_component(ict,"crt").get("status","—"),_component(ict,"crt").get("score")),
        ("ICT","OTE",_component(ict,"ote").get("status","—"),_component(ict,"ote").get("score")),
        ("ICT","AMD / PO3",_component(ict,"amd").get("status","—"),_component(ict,"amd").get("score")),
        ("ICT","FVG",_component(ict,"fvg").get("status","—"),_component(ict,"fvg").get("score")),
        ("Técnico","H4",p.get("h4","—"),_status_score(p.get("h4","—"))),
        ("Técnico","H1",p.get("h1","—"),_status_score(p.get("h1","—"))),
        ("Técnico","M15",p.get("m15","—"),_status_score(p.get("m15","—"))),
        ("Risco","ADR14",f"{p.get('adr',0):.0f}% consumido",None),
        ("Risco","Evento",p.get("event","NORMAL"),None),
        ("Gate","Gate",f"{p.get('gate','—')} · {p.get('gate_score',0):.0f}/100",p.get("gate_score")),
    ]
    return pd.DataFrame(rows,columns=["Camada","Leitura","Estado","Score"])


def render_pair_intelligence_v110(matrix:pd.DataFrame,ranking:pd.DataFrame,fed:Mapping[str,Any]|None=None,macro_context:Mapping[str,Any]|None=None):
    _css()
    st.markdown("""<div class="v110-hero"><h2>🏛️ Central Institucional dos 7 Pares — V11.0.1</h2><p>Macro → notícias → W1/D1 → liquidez → SMT → displacement → MSS → CRT/AMD/OTE/FVG → H4/H1/M15 → ADR/evento → decisão final.</p><span class="v110-badge">1 tela</span><span class="v110-badge">sem novas chamadas de API</span><span class="v110-badge">hard gates</span><span class="v110-badge">auditável</span></div>""",unsafe_allow_html=True)
    st.caption("Objetivo: reproduzir um processo disciplinado de decisão multi-camada. Não representa fluxo real de instituições. Prioridade/readiness não é probabilidade de lucro.")
    if matrix is None or matrix.empty:
        st.warning("A Matriz ainda não está disponível nesta execução."); return

    token,repo,branch=_gh_cfg()
    scanner,_=_read_json(SCANNER_PATH,token,repo,branch); mmap,_=_read_json(MAP_PATH,token,repo,branch); news_state,_=_read_json(NEWS_PATH,token,repo,branch); auto,_=_read_json(AUTO_PATH,token,repo,branch)
    news_map=_pair_news(news_state,matrix)
    scanner_rows=dict(scanner.get("resultados",{}) or {}) if isinstance(scanner,dict) else {}
    map_rows=dict(mmap.get("contexts",{}) or {}) if isinstance(mmap,dict) else {}
    fed_tone=str((fed or {}).get("tom",(fed or {}).get("tone","Neutro")))
    bypair={str(r["Par"]):r.to_dict() for _,r in matrix.iterrows() if str(r.get("Par","")) in PAIR_ORDER}
    packs=[_reason_pack(p,bypair[p],ranking,scanner_rows.get(p,{}),map_rows.get(p,{}),news_map.get(p,{}),fed_tone) for p in PAIR_ORDER if p in bypair]
    packs.sort(key=lambda x:x["priority"],reverse=True)
    if not packs: st.warning("Nenhum dos 7 pares foi encontrado na Matriz."); return

    best=next((p for p in packs if p["side"]!="WAIT" and not p["state"].startswith("🔴")),packs[0])
    strongest,weakest=_major_extremes(ranking)
    process_age=_age_minutes(auto.get("last_run"))
    process_ok=bool(auto.get("app_headless_ok",False))
    process_label=("🟢 PROCESSO OK" if process_ok and (process_age is None or process_age<=90) else "🟡 SEM RODADA RECENTE" if process_ok else "🔴 FALHA HEADLESS")
    data_ok=sum(1 for x in packs if bool((x.get("data_ready",{}) or {}).get("sufficient",False)))
    twelve_label="🟠 COTA/PLANO BLOQUEADO" if auto.get("twelve_daily_blocked") else "🟢 SEM BLOQUEIO REGISTRADO"
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Melhor contexto",best["pair"]); c2.metric("Prioridade",f"{best['priority']:.1f}/100"); c3.metric("Mais forte (G8)",strongest); c4.metric("Mais fraca (G8)",weakest); c5.metric("Estado",best["state"])
    st.markdown("### 🩺 Saúde do processo x prontidão dos dados")
    h1,h2,h3,h4=st.columns(4)
    h1.metric("Autopilot / Headless",process_label)
    h2.metric("Dados técnicos suficientes",f"{data_ok}/7")
    h3.metric("Twelve Data",twelve_label)
    h4.metric("Decisão operacional",best["state"])
    if auto.get("twelve_daily_blocked"):
        st.warning("🟠 O processo do Autopilot pode estar saudável mesmo com a fonte técnica bloqueada. A Central separa processo, fonte e frescor para evitar falso 'OK'.")

    st.markdown("### 🏁 Mesa de decisão — 7 pares")
    executive=pd.DataFrame([{
        "Par":p["pair"],"Decisão final":p["state"],"Direção":p["direction"],"Prioridade":p["priority"],"Score Mestre":p["score"],"Qualidade %":p["quality"],
        "Dados?":"SIM" if (p.get("data_ready",{}) or {}).get("sufficient") else "NÃO","Data Score":round(_safe((p.get("data_ready",{}) or {}).get("score",0)),0),
        "ICT":round(p["ict_read"],0),"Institucional":round(p["inst_read"],0) if (p.get("data_ready",{}) or {}).get("institutional_data_ready") else "N/D","H4":p["h4"],"H1":p["h1"],"M15":p["m15"],"Gate":p["gate"],"ADR %":round(p["adr"],0) if p["adr"] else None,"Evento":p["event"],"Motivo":p["reason"]
    } for p in packs])
    st.dataframe(executive,use_container_width=True,hide_index=True,height=330)
    st.bar_chart(executive[["Par","Prioridade"]].set_index("Par"),horizontal=True,height=250)

    st.markdown("### 🧩 Leitura executiva")
    for i in range(0,len(packs),2):
        cols=st.columns(2)
        for j,p in enumerate(packs[i:i+2]):
            with cols[j]:
                st.markdown(f"#### {p['pair']} · {p['state']}")
                a,b,c,d=st.columns(4); a.metric("Prioridade",f"{p['priority']:.0f}/100"); b.metric("Dados",f"{_safe((p.get('data_ready',{}) or {}).get('score',0)):.0f}/100"); c.metric("ICT",f"{p['ict_read']:.0f}"); d.metric("Institucional",f"{p['inst_read']:.0f}" if (p.get("data_ready",{}) or {}).get("institutional_data_ready") else "N/D")
                st.markdown(f"**Por quê:** {p['reason']}")
                _dr=p.get("data_ready",{}) or {}; _tf=_dr.get("timeframes",{}) or {}
                st.caption(f"H4 {p['h4']} ({(_tf.get('h4',{}) or {}).get('state','—')}) · H1 {p['h1']} ({(_tf.get('h1',{}) or {}).get('state','—')}) · M15 {p['m15']} ({(_tf.get('m15',{}) or {}).get('state','—')}) · Gate {p['gate']} · ADR {p['adr']:.0f}%")
                st.caption(f"Alvo de liquidez: {p['target']} · Próximo passo: {p['next_action']}")

    st.divider(); st.markdown("## 🔬 Raio-X institucional")
    pair=st.selectbox("Escolha o par",[p["pair"] for p in packs],key="v110_pair_deep")
    p=next(x for x in packs if x["pair"]==pair)
    _dr=p.get("data_ready",{}) or {}
    a,b,c,d,e,f=st.columns(6); a.metric("Decisão",p["state"]); b.metric("Prioridade",f"{p['priority']:.1f}/100"); c.metric("Score Mestre",f"{p['score']:.0f}/100"); d.metric("Dados",f"{_safe(_dr.get('score',0)):.0f}/100"); e.metric("ICT",f"{p['ict_read']:.0f}/100"); f.metric("Institucional",f"{p['inst_read']:.0f}/100" if _dr.get("institutional_data_ready") else "N/D")
    st.markdown("### 📡 Data Readiness — dados suficientes para decisão?")
    if _dr.get("sufficient"):
        st.success(f"✅ SIM — {_dr.get('label','')} · {_safe(_dr.get('score',0)):.0f}/100")
    else:
        st.error(f"❌ NÃO — {_dr.get('label','')} · {_safe(_dr.get('score',0)):.0f}/100")
        if _dr.get("missing"):
            st.caption("Faltando: " + " · ".join(_dr.get("missing",[])[:6]))
    _tf=_dr.get("timeframes",{}) or {}
    tfc=st.columns(3)
    for _col,_name in zip(tfc,("h4","h1","m15")):
        _x=_tf.get(_name,{}) or {}; _age=_x.get("age_minutes")
        _col.metric(_name.upper(),_x.get("state","—"),"sem timestamp" if _age is None else f"{_age:.0f} min")
    st.caption(f"Cache institucional: H1 {_dr.get('cache_h1_bars',0)} candles · M15 {_dr.get('cache_m15_bars',0)} candles")

    if p["hard_blocks"]:
        st.error("**Bloqueios duros:** " + " · ".join(p["hard_blocks"]))
    elif p["soft_blocks"]:
        st.warning("**Faltando antes da execução:** " + " · ".join(p["soft_blocks"]))
    else:
        st.success("Nenhum bloqueio principal detectado nas camadas persistidas.")

    left,right=st.columns(2)
    with left:
        st.markdown("### 🟢 Evidências de alta")
        for x in p["up"][:12]: st.markdown(f"- {x}")
        if not p["up"]: st.caption("Nenhuma evidência forte de alta.")
    with right:
        st.markdown("### 🔴 Evidências de queda")
        for x in p["down"][:12]: st.markdown(f"- {x}")
        if not p["down"]: st.caption("Nenhuma evidência forte de queda.")

    st.markdown("### 🧠 Decision Stack — tudo em uma tabela")
    st.dataframe(_stack_rows(p),use_container_width=True,hide_index=True,height=650)

    inst=p.get("inst",{}) or {}
    st.markdown("### 🏛️ Institutional Execution Engine")
    cards=[("MSS","mss"),("Displacement","displacement"),("SMT","smt"),("Premium/Discount","dealing_range"),("Judas/Sessão","session"),("Breaker/Mitigation","pd_array"),("Liquidez","liquidity")]
    for i in range(0,len(cards),4):
        cols=st.columns(min(4,len(cards)-i))
        for col,(title,key) in zip(cols,cards[i:i+4]):
            comp=_component(inst,key); _status,_text=display_component_status(comp,key,_dr); col.metric(title,_status); col.caption(_text)
    if inst:
        st.progress(min(1,max(0,p["inst_read"]/100)),text=f"Prontidão institucional: {p['inst_read']:.0f}/100 — {p['inst_label']}")
    else:
        st.info("A camada institucional será preenchida pelo próximo ciclo do Autopilot usando H1/M15 persistidos. Abrir esta aba não consome API.")

    st.markdown("### 🧠 ICT Execution Engine")
    ict=p.get("ict",{}) or {}
    icards=[("CRT","crt"),("OTE","ote"),("AMD / PO3","amd"),("FVG","fvg")]
    cols=st.columns(4)
    for col,(title,key) in zip(cols,icards):
        comp=_component(ict,key); col.metric(title,str(comp.get("status","—"))); col.caption(str(comp.get("text","")))
    if ict: st.progress(min(1,max(0,p["ict_read"]/100)),text=f"Prontidão ICT: {p['ict_read']:.0f}/100 — {p['ict_label']}")

    st.markdown("### 💧 Liquidez e contexto")
    _pdop=premium_discount_operational(p.get("side","WAIT"),_component(inst,"dealing_range"),_dr)
    x1,x2,x3,x4,x5=st.columns(5); x1.metric("W1",p["w1"]); x2.metric("D1",p["d1"]); x3.metric("Premium/Discount",_pdop.get("status","—")); x4.metric("Sweep",p["sweep_type"] or "—"); x5.metric("Evento",p["event"])
    st.caption("Premium/Discount: " + _pdop.get("text",""))
    if p["sweep_type"]:
        st.info(f"💧 {p['sweep_type']} em **{p['sweep_level'] or 'nível'}** ({_fmt_price(p['sweep_price'],pair)}). {p['sweep_rejection']}")
    levels=p.get("levels",{}) or {}
    level_rows=[]
    for name in ("PWH","PWL","PDH","PDL","Asia High","Asia Low","EQH","EQL"):
        if name in levels and levels.get(name) is not None:
            level_rows.append({"Nível":name,"Preço":_fmt_price(levels.get(name),pair)})
    if level_rows: st.dataframe(pd.DataFrame(level_rows),use_container_width=True,hide_index=True)
    st.caption(f"Alvo principal: {p['target']} · Gate {p['gate']} ({p['gate_score']:.0f}/100) · ADR {p['adr']:.0f}% · idade técnica {p['technical_age']:.0f} min" if p['technical_age'] is not None else f"Alvo principal: {p['target']} · Gate {p['gate']} ({p['gate_score']:.0f}/100) · ADR {p['adr']:.0f}%")

    st.markdown("### 🎯 Plano objetivo")
    msg=f"**Decisão:** {p['state']} · **Direção:** {p['direction']} · **Motivo dominante:** {p['reason']} · **Próximo passo:** {p['next_action']}"
    if p["state"].startswith("🟢"): st.success(msg)
    elif p["state"].startswith("🔴"): st.error(msg)
    else: st.warning(msg)

    with st.expander("📚 Como ler o V11.0.1"):
        st.markdown("""
- **Macro** escolhe o lado; execução nunca inverte o lado macro sozinha.
- **SMT** procura divergência entre EUR/USD↔GBP/USD, AUD/USD↔NZD/USD e USD/CHF↔USD/JPY.
- **Displacement + MSS** formam o núcleo de confirmação de mudança/entrega de fluxo.
- **Premium/Discount** mede a localização no dealing range H1.
- **Judas/Sessão** procura sweep/rejeição do range asiático durante Londres/NY.
- **Breaker/Mitigation** é uma heurística de zona de origem do displacement; não é ordem institucional observável.
- **CRT/OTE/AMD/FVG** continuam como camada ICT de timing/localização.
- **Data Readiness** separa processo saudável de dado operacional utilizável; sem H4/H1/M15 frescos e cache mínimo, a execução fica bloqueada.
- **Hard gates** impedem que um par apareça “executável” quando evento, ADR, H4/H1, qualidade ou frescor não permitem.
        """)
    with st.expander("🛡️ Limites do algoritmo"):
        st.markdown("""
- O sistema **não vê ordens de bancos/fundos** e não sabe o que um “big player” está fazendo de fato.
- Os modelos são inferências determinísticas sobre preço, volatilidade, estrutura, liquidez e contexto.
- Prioridade/Readiness são **scores internos**, não probabilidades de acerto ou lucro.
- A melhoria deve ser validada por amostra histórica antes de alterar pesos do Score Mestre.
        """)
