"""USD Macro Pro V10.8 — Central Inteligente dos 7 Pares.

Consolida Matriz, notícias, scanner, Market Map e ICT persistido.
Abrir esta aba não chama Twelve Data.
"""
from __future__ import annotations

import base64
import json
import math
import os
from typing import Any, Mapping

import numpy as np
import pandas as pd
import requests
import streamlit as st
from atlasquant_runtime_store import resolve_runtime_branch

try:
    from currency_news_v107 import pair_news_table
except Exception:
    pair_news_table = None

PAIR_ORDER=("EUR/USD","GBP/USD","AUD/USD","NZD/USD","USD/JPY","USD/CHF","USD/CAD")
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
        branch=resolve_runtime_branch(
            st.secrets.get("GITHUB_DATA_BRANCH",os.getenv("GITHUB_DATA_BRANCH","")),
            st.secrets.get("GITHUB_BRANCH_HISTORICO",os.getenv("GITHUB_BRANCH_HISTORICO","")),
        )
    except Exception:
        token,repo,branch="","",resolve_runtime_branch()
    return str(token),str(repo),str(branch)


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
    if "🟡" in s or "PARCIAL" in u or "ALINHADO" in u or "AGUARDAR" in u:
        return 60
    if "🔴" in s or "CONTRA" in u or "SEM GATILHO" in u:
        return 20
    return 45


def _trend_matches(bias:str,side:str):
    b=str(bias).upper()
    if "ALT" in b:
        return side=="BUY"
    if "BAIX" in b:
        return side=="SELL"
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


def _reason_pack(pair,row,ranking,scanner,mapctx,news,fed_tone="Neutro"):
    side=_side(row.get("Direção",""))
    base,quote=pair.split("/")
    base_score=_currency_score(ranking,base)
    quote_score=_currency_score(ranking,quote)
    macro_diff=_safe(row.get("Dif. macro",base_score-quote_score))
    score=_safe(row.get("Score final",0))
    quality=_safe(row.get("Qualidade",0))
    idx=_safe(row.get("Índice ranking",0))

    tec=dict((scanner or {}).get("tecnico",{}) or {})
    h4=str((tec.get("h4",{}) or {}).get("status","—"))
    h1=str((tec.get("h1",{}) or {}).get("status","—"))
    m15=str((tec.get("m15",{}) or {}).get("status","—"))
    ict=dict(tec.get("ict",{}) or {})
    ict_read=_safe(ict.get("readiness",0))
    ict_label=str(ict.get("label","⏳ aguardando atualização ICT"))

    w1=str((mapctx or {}).get("w1_bias","—"))
    d1=str((mapctx or {}).get("d1_bias","—"))
    gate=str((mapctx or {}).get("readiness_grade","—"))
    gate_score=_safe((mapctx or {}).get("readiness_score",0))
    pd_zone=str((mapctx or {}).get("location","—"))
    sweep=str((mapctx or {}).get("latest_sweep",""))
    sweep_level=str((mapctx or {}).get("latest_sweep_level",""))
    adr=_safe((mapctx or {}).get("adr_used_pct",0))
    event=str((mapctx or {}).get("event_risk","NORMAL"))
    price=(mapctx or {}).get("price",tec.get("preco_m15"))

    news_diff=_safe((news or {}).get("Diferencial notícias",0))
    news_align=str((news or {}).get("Alinhamento","—"))
    news_conv=_safe((news or {}).get("Convicção heurística",0))

    up=[]; down=[]; blockers=[]
    if macro_diff>0:
        up.append(f"{base} está {abs(macro_diff):.1f} pts mais forte que {quote} no macro relativo")
    elif macro_diff<0:
        down.append(f"{quote} está {abs(macro_diff):.1f} pts mais forte que {base} no macro relativo")

    if news_diff>=2:
        up.append(f"notícias favorecem a moeda base ({news_diff:+.2f})")
    elif news_diff<=-2:
        down.append(f"notícias favorecem a moeda cotada ({news_diff:+.2f})")

    for tf,status in (("H4",h4),("H1",h1),("M15",m15)):
        ss=_status_score(status)
        if side=="BUY" and ss>=80:
            up.append(f"{tf} confirma compra")
        elif side=="SELL" and ss>=80:
            down.append(f"{tf} confirma venda")
        elif ss<=25:
            blockers.append(f"{tf} está contra/sem gatilho")

    for tf,bias in (("W1",w1),("D1",d1)):
        match=_trend_matches(bias,side)
        if match is True:
            (up if side=="BUY" else down).append(f"{tf} alinhado ao viés")
        elif match is False:
            blockers.append(f"{tf} está contra o viés macro")

    for key,label in (("crt","CRT"),("amd","AMD/PO3"),("ote","OTE"),("fvg","FVG")):
        comp=dict(ict.get(key,{}) or {})
        status=str(comp.get("status",""))
        if "🟢" in status:
            (up if side=="BUY" else down).append(f"{label}: {status.replace('🟢','').strip()}")
        elif "🟡" in status:
            blockers.append(f"{label} ainda em preparação")

    if adr>=100:
        blockers.append(f"ADR14 já consumiu {adr:.0f}%: movimento esticado")
    elif adr>=85:
        blockers.append(f"ADR14 em {adr:.0f}%: pouco espaço antes de perseguir preço")
    if event.upper() in ("MÁXIMO","MAXIMO","ALTO"):
        blockers.append(f"risco de evento {event}")

    ft=str(fed_tone).upper()
    if "USD" in pair and ("RESTR" in ft or "HAWK" in ft):
        if base=="USD":
            up.append("Fed restritivo/hawkish dá suporte estrutural ao USD")
        else:
            down.append("Fed restritivo/hawkish dá suporte ao USD, pressionando a cotação")
    elif "USD" in pair and ("DOV" in ft or "EXPANS" in ft):
        if base=="USD":
            down.append("Fed dovish reduz suporte estrutural ao USD")
        else:
            up.append("Fed dovish reduz suporte ao USD e favorece a moeda base")

    tech_avg=np.mean([_status_score(h4),_status_score(h1),_status_score(m15)])
    map_component=gate_score if gate_score else 50
    news_component=min(100,50+abs(news_diff)*8) if news else 50
    ict_component=ict_read if ict else 45
    unified=float(np.clip(idx*.38 + tech_avg*.22 + map_component*.18 + news_component*.10 + ict_component*.12,0,100))

    if side=="WAIT":
        state="⚪ AGUARDAR DIREÇÃO"
    elif any("contra" in b.lower() for b in blockers[:2]):
        state="🔴 BLOQUEADO / CONTRA"
    elif unified>=78 and _status_score(h4)>=80 and _status_score(h1)>=80 and _status_score(m15)>=80:
        state="🟢 EXECUÇÃO CONFIRMADA"
    elif unified>=68 and _status_score(h4)>=60 and _status_score(h1)>=60:
        state="🟡 QUASE PRONTO"
    else:
        state="🟠 EM OBSERVAÇÃO"

    if side=="BUY":
        current_reason=up[0] if up else "viés comprador do motor"
        next_action="Esperar/confirmar M15 e localização ICT antes de executar." if "CONFIRMADA" not in state else "Contexto alinhado; aplicar plano de risco e invalidação."
    elif side=="SELL":
        current_reason=down[0] if down else "viés vendedor do motor"
        next_action="Esperar/confirmar M15 e localização ICT antes de executar." if "CONFIRMADA" not in state else "Contexto alinhado; aplicar plano de risco e invalidação."
    else:
        current_reason="força relativa/confluência ainda não definiu BUY ou SELL"
        next_action="Não antecipar. Aguardar o motor sair de AGUARDAR/NEUTRO."

    target="—"
    if side=="BUY" and mapctx:
        target=f"{mapctx.get('bsl_name','BSL')} {_fmt_price(mapctx.get('bsl_price'),pair)}"
    elif side=="SELL" and mapctx:
        target=f"{mapctx.get('ssl_name','SSL')} {_fmt_price(mapctx.get('ssl_price'),pair)}"

    return {
        "pair":pair,"side":side,"direction":str(row.get("Direção","⚪ AGUARDAR")),"state":state,
        "unified":round(unified,1),"score":score,"quality":quality,"index":idx,
        "base_score":base_score,"quote_score":quote_score,"macro_diff":macro_diff,
        "h4":h4,"h1":h1,"m15":m15,"w1":w1,"d1":d1,"gate":gate,"gate_score":gate_score,
        "pd_zone":pd_zone,"sweep":sweep,"sweep_level":sweep_level,"adr":adr,"event":event,"price":price,
        "news_diff":news_diff,"news_align":news_align,"news_conv":news_conv,
        "ict":ict,"ict_read":ict_read,"ict_label":ict_label,
        "up":up,"down":down,"blockers":blockers,"reason":current_reason,"next_action":next_action,"target":target,
    }


def _css():
    st.markdown("""
    <style>
      .v108-hero{padding:20px 22px;border:1px solid rgba(100,116,139,.22);border-radius:18px;background:linear-gradient(135deg,rgba(15,23,42,.96),rgba(30,64,175,.88));color:white;margin-bottom:14px}
      .v108-hero h2{margin:0 0 5px 0;color:white}.v108-hero p{margin:0;color:#dbeafe}
      div[data-testid="stMetric"]{border:1px solid rgba(100,116,139,.18);padding:10px;border-radius:14px}
    </style>
    """,unsafe_allow_html=True)


def render_pair_intelligence_v108(matrix:pd.DataFrame,ranking:pd.DataFrame,fed:Mapping[str,Any]|None=None,macro_context:Mapping[str,Any]|None=None):
    _css()
    st.markdown("""<div class="v108-hero"><h2>🎯 Central Inteligente dos 7 Pares — V10.8</h2><p>Uma única tela para responder: qual par está melhor, por que tende a subir ou cair, o que confirma, o que bloqueia e qual é o próximo passo.</p></div>""",unsafe_allow_html=True)
    st.caption("Esta é a aba principal de decisão. Ela consolida o que já existe no app e NÃO transforma índice em probabilidade de lucro.")

    if matrix is None or matrix.empty:
        st.warning("A Matriz ainda não está disponível nesta execução.")
        return

    token,repo,branch=_gh_cfg()
    scanner,_=_read_json(SCANNER_PATH,token,repo,branch)
    mmap,_=_read_json(MAP_PATH,token,repo,branch)
    news_state,_=_read_json(NEWS_PATH,token,repo,branch)
    auto,_=_read_json(AUTO_PATH,token,repo,branch)
    news_map=_pair_news(news_state,matrix)
    scanner_rows=dict(scanner.get("resultados",{}) or {}) if isinstance(scanner,dict) else {}
    map_rows=dict(mmap.get("contexts",{}) or {}) if isinstance(mmap,dict) else {}
    fed_tone=str((fed or {}).get("tom",(fed or {}).get("tone","Neutro")))

    bypair={str(r["Par"]):r.to_dict() for _,r in matrix.iterrows() if str(r.get("Par","")) in PAIR_ORDER}
    packs=[]
    for pair in PAIR_ORDER:
        if pair in bypair:
            packs.append(_reason_pack(pair,bypair[pair],ranking,scanner_rows.get(pair,{}),map_rows.get(pair,{}),news_map.get(pair,{}),fed_tone))
    packs.sort(key=lambda x:x["unified"],reverse=True)
    if not packs:
        st.warning("Nenhum dos 7 pares foi encontrado na Matriz.")
        return

    best=next((p for p in packs if p["side"]!="WAIT"),packs[0])
    strongest=str(ranking.iloc[0]["Código"]) if ranking is not None and not ranking.empty else "—"
    weakest=str(ranking.iloc[-1]["Código"]) if ranking is not None and not ranking.empty else "—"
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Melhor contexto",best["pair"])
    c2.metric("Índice unificado",f"{best['unified']:.1f}/100")
    c3.metric("Moeda mais forte",strongest)
    c4.metric("Moeda mais fraca",weakest)
    c5.metric("Autopilot","🟢 OK" if auto.get("healthy") else "🟡 ATENÇÃO")
    if auto.get("twelve_daily_blocked"):
        st.warning("🟠 A Twelve Data está com cota/plano bloqueado. Esta aba continua mostrando a última leitura persistida sem gastar novas chamadas.")

    st.markdown("### 🏁 Ranking executivo — todos os pares")
    executive=pd.DataFrame([{
        "Par":p["pair"],"Direção":p["direction"],"Estado":p["state"],"Índice":p["unified"],
        "Score":p["score"],"Qualidade %":p["quality"],"H4":p["h4"],"H1":p["h1"],"M15":p["m15"],
        "ICT":p["ict_label"],"Gate":p["gate"],"Notícias":p["news_align"],"ADR %":round(p["adr"],0) if p["adr"] else None,
        "Motivo dominante":p["reason"],
    } for p in packs])
    st.dataframe(executive,width="stretch",hide_index=True,height=320)
    st.bar_chart(executive[["Par","Índice"]].set_index("Par"),horizontal=True,height=250)

    st.markdown("### 🧩 Leitura rápida dos 7 pares")
    for i in range(0,len(packs),2):
        cols=st.columns(2)
        for j,p in enumerate(packs[i:i+2]):
            with cols[j]:
                st.markdown(f"#### {p['pair']} · {p['state']}")
                m1,m2,m3=st.columns(3)
                m1.metric("Índice",f"{p['unified']:.0f}/100")
                m2.metric("Score",f"{p['score']:.0f}/100")
                m3.metric("Qualidade",f"{p['quality']:.0f}%")
                st.markdown(f"**Motivo agora:** {p['reason']}")
                st.caption(f"H4 {p['h4']} · H1 {p['h1']} · M15 {p['m15']}")
                st.caption(f"ICT: {p['ict_label']} · {p['ict_read']:.0f}/100" if p['ict'] else "ICT: aguardando próxima atualização técnica")
                st.caption(f"Alvo: {p['target']} · Gate {p['gate']}" + (f" · ADR {p['adr']:.0f}%" if p['adr'] else ""))

    st.divider()
    st.markdown("## 🔬 Raio-X didático de um par")
    pair=st.selectbox("Escolha o par",[p['pair'] for p in packs],index=0,key="v108_pair_deep")
    p=next(x for x in packs if x['pair']==pair)

    a,b,c,d=st.columns(4)
    a.metric("Direção oficial",p['direction'])
    b.metric("Índice unificado",f"{p['unified']:.1f}/100")
    c.metric("Gate",f"{p['gate']} · {p['gate_score']:.0f}/100")
    d.metric("Preço técnico",_fmt_price(p['price'],pair))

    left,right=st.columns(2)
    with left:
        st.markdown("### 🟢 O que favorece ALTA")
        if p['up']:
            for x in p['up'][:8]: st.markdown(f"- {x}")
        else:
            st.caption("Nenhuma evidência forte de alta na leitura consolidada.")
    with right:
        st.markdown("### 🔴 O que favorece QUEDA")
        if p['down']:
            for x in p['down'][:8]: st.markdown(f"- {x}")
        else:
            st.caption("Nenhuma evidência forte de queda na leitura consolidada.")

    st.markdown("### 🚧 O que pode invalidar / por que NÃO entrar agora")
    if p['blockers']:
        for x in p['blockers'][:8]: st.markdown(f"- ⚠️ {x}")
    else:
        st.success("Nenhum bloqueio principal detectado nas camadas persistidas.")

    st.markdown("### 🧠 ICT Execution Engine — CRT + OTE + Power of Three / AMD")
    if not p['ict']:
        st.info("A leitura ICT será preenchida automaticamente na próxima atualização técnica que conseguir H1/M15. Esta aba não faz consultas extras à API.")
    else:
        ict=p['ict']
        ic1,ic2,ic3,ic4=st.columns(4)
        for col,key,title in ((ic1,'crt','CRT'),(ic2,'ote','OTE'),(ic3,'amd','AMD / PO3'),(ic4,'fvg','FVG')):
            comp=dict(ict.get(key,{}) or {})
            col.metric(title,str(comp.get('status','—')))
            col.caption(str(comp.get('text','')))
        st.progress(min(1.0,max(0.0,p['ict_read']/100.0)),text=f"Prontidão ICT: {p['ict_read']:.0f}/100 — {p['ict_label']}")

    st.markdown("### 🗺️ Contexto de mercado e liquidez")
    x1,x2,x3,x4,x5=st.columns(5)
    x1.metric("W1",p['w1']); x2.metric("D1",p['d1']); x3.metric("Premium/Discount",p['pd_zone']); x4.metric("Sweep",p['sweep'] or '—'); x5.metric("Evento",p['event'])
    st.caption(f"Sweep nível: {p['sweep_level'] or '—'} · alvo principal: {p['target']} · notícias: {p['news_align']} ({p['news_diff']:+.2f})")

    st.markdown("### 🎯 Plano objetivo")
    msg=f"**Cenário:** {p['state']} · **Direção:** {p['direction']} · **Motivo:** {p['reason']} · **Próximo passo:** {p['next_action']}"
    if p['state'].startswith('🟢'):
        st.success(msg)
    elif p['state'].startswith('🔴'):
        st.error(msg)
    else:
        st.warning(msg)

    with st.expander("📚 Entenda CRT, OTE e AMD/Power of Three nesta tela"):
        st.markdown("""
- **CRT:** procura um candle-range H1, uma varredura de liquidez em um extremo e fechamento de volta ao range; a vela seguinte confirma ou não a distribuição.
- **OTE:** usa o impulso H1 mais recente e mede a retração. A zona observada é **62%–79%**, com **70,5%** como referência central. OTE não cria direção sozinho.
- **Power of Three / AMD:** classifica o M15 em **Acumulação → Manipulação → Distribuição**. Para compra, a manipulação esperada é uma varredura de SSL; para venda, uma varredura de BSL.
- **FVG:** procura desequilíbrio recente de três candles M15 no mesmo lado do viés.
- **Regra principal:** o macro escolhe o lado; ICT melhora **localização e timing**. Se macro e execução discordarem, o sistema manda aguardar.
        """)

    with st.expander("🛡️ Limites e segurança da leitura"):
        st.markdown("""
- Índice Unificado = ranking interno de prioridade, **não probabilidade de lucro**.
- Esta aba não envia ordens e não altera o Score Mestre.
- A camada ICT usa candles já obtidos pelo scanner; abrir esta aba **não consome Twelve Data**.
- Dados antigos permanecem visíveis com seus estados; decisões novas devem considerar frescor, evento e ADR.
- CRT/OTE/AMD são modelos de execução e contexto, não garantias de resultado.
        """)
