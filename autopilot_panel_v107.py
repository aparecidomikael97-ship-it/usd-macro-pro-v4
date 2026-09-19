"""USD Macro Pro V10.7 — Autopilot health panel."""
from __future__ import annotations
import base64, json, os
from typing import Any
import pandas as pd
import requests
import streamlit as st
from atlasquant_runtime_store import resolve_runtime_branch

STATUS_PATH="dados/autopilot_status_v107.json"

def _cfg():
    try:
        token=st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO",""))
        repo=st.secrets.get("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPO_HISTORICO",""))
        branch=resolve_runtime_branch(
            st.secrets.get("GITHUB_DATA_BRANCH", os.getenv("GITHUB_DATA_BRANCH","")),
            st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO","")),
        )
    except Exception:
        token,repo,branch="","",resolve_runtime_branch()
    return str(token),str(repo),str(branch)

def _load_status() -> tuple[dict[str,Any],str]:
    token,repo,branch=_cfg()
    if not token or not repo: return {},"Persistência GitHub não configurada."
    try:
        r=requests.get(
            f"https://api.github.com/repos/{repo}/contents/{STATUS_PATH}",
            headers={"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json"},
            params={"ref":branch},timeout=15
        )
        if r.status_code==404: return {},"Autopilot ainda não executou."
        r.raise_for_status()
        return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8")),""
    except Exception as exc:
        return {},f"{type(exc).__name__}: {exc}"

def _age_min(value):
    try:
        ts=pd.to_datetime(value,utc=True)
        age=(pd.Timestamp.now(tz="UTC")-ts).total_seconds()/60
        return None if age < 0 else age
    except Exception: return None

def autopilot_status_summary(status: dict[str,Any] | None) -> dict[str,str]:
    s=dict(status or {})
    readiness=str(s.get("operational_readiness","") or "").upper()
    market_open=bool(s.get("forex_market_open",False))
    if readiness=="MARKET_CLOSED" or not market_open:
        return {"label":"EM ESPERA","tone":"info","detail":"Mercado FX fechado"}
    if bool(s.get("healthy",False)) and readiness in ("","READY"):
        return {"label":"SAUDÁVEL","tone":"good","detail":"Dados e serviços dentro dos gates"}
    if not bool(s.get("app_headless_ok",False)):
        return {"label":"BLOQUEADO","tone":"bad","detail":"Atualização headless indisponível"}
    return {"label":"ATENÇÃO","tone":"warn","detail":"Há gates ou dados aguardando validação"}

def _render_status_strip(status: dict[str,Any]) -> None:
    s=autopilot_status_summary(status)
    st.markdown(
        f"""<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 14px;
        border:1px solid rgba(137,170,210,.18);border-radius:13px;background:rgba(11,27,47,.62);margin:4px 0 14px">
        <strong style="font-size:.82rem">AUTOPILOT</strong>
        <span style="font-weight:850">{s['label']}</span>
        <span style="opacity:.72;font-size:.78rem">{s['detail']}</span>
        <span style="margin-left:auto;font-size:.72rem;opacity:.72">Safety Core ativo · execução real desativada</span>
        </div>""", unsafe_allow_html=True,
    )

def render_autopilot_v107():
    st.subheader("Autopilot — saúde e atualização")
    st.caption(
        "Macro/FRED → Matriz → Notícias 8 moedas → Scanner H4/H1/M15 → Market Map "
        "→ snapshots → validação 1H/4H/24H. Rodando em background pelo GitHub Actions."
    )
    status,err=_load_status()
    if err and not status:
        st.warning(err)
        st.info("Depois de ativar o workflow Autopilot V10.7, esta tela passa a mostrar a saúde automática.")
        return

    _render_status_strip(status)

    age=_age_min(status.get("last_run"))
    healthy=bool(status.get("healthy",False))
    readiness=str(status.get("operational_readiness","") or "").upper()
    market_open=bool(status.get("forex_market_open",False))
    errors = status.get("errors", []) or []
    daily_blocked = bool(status.get("twelve_daily_blocked", False))
    has_429 = any("HTTP 429" in str(x) for x in errors)
    headless_bad = not bool(status.get("app_headless_ok", False))

    if readiness=="MARKET_CLOSED" or not market_open:
        st.info("🌙 MERCADO FX FECHADO — AUTOPILOT EM ESPERA SEGURA")
    elif healthy and readiness in ("","READY"):
        st.success("🟢 AUTOPILOT SAUDÁVEL")
    elif headless_bad:
        st.error("🔴 AUTOPILOT: APP HEADLESS NÃO ATUALIZOU A MATRIZ")
    elif daily_blocked:
        block_type = str(status.get("twelve_block_type", "") or "")
        reason = str(status.get("twelve_daily_block_reason", "")).lower()
        if block_type in ('RITMO_DIARIO','ORCAMENTO_DIARIO'):
            st.info("Orçamento protegido: o coletor adiou consultas para respeitar a distribuição diária.")
        elif block_type == 'CONTROLE_INDISPONIVEL':
            st.warning("Coleta pausada: não foi possível confirmar o orçamento persistido.")
        elif block_type == 'LIMITE_MINUTO' or "current minute" in reason or "per minute" in reason:
            st.warning("🟠 TWELVE DATA: LIMITE POR MINUTO — consultas interrompidas nesta rodada")
        elif block_type == "COTA_DIARIA":
            st.warning("🟠 TWELVE DATA: COTA DIÁRIA/CRÉDITOS ESGOTADOS — o Autopilot parou novas consultas nesta rodada")
        else:
            st.warning("🟠 TWELVE DATA: COTA/PLANO BLOQUEOU CONSULTAS — o Autopilot parou após o primeiro 429")
    elif has_429:
        st.warning("🟠 AUTOPILOT: TWELVE DATA LIMITOU CONSULTAS (HTTP 429)")
    else:
        st.warning("🟡 AUTOPILOT COM ATENÇÃO")
    if age is not None:
        st.caption(f"Última execução há {age:.0f} min · {status.get('last_run','')}")

    budget=status.get('twelve_budget',{}) or {}
    if budget and not budget.get('error'):
        st.markdown('### Orçamento diário — última rodada')
        b1,b2,b3=st.columns(3)
        b1.metric('Créditos contabilizados',int(budget.get('used',0)))
        b2.metric('Limite do aplicativo',int(budget.get('limit',480)))
        b3.metric('Saldo protegido',int(budget.get('remaining',0)))
        st.caption('Contagem conservadora: inclui tentativas com falha e uso diário informado pela API. Consultas feitas fora deste aplicativo não são controladas aqui.')
        for label,key in [('Renovação diária','reset_at'),('Pausa registrada até','blocked_until')]:
            value=budget.get(key)
            if value:
                stamp=pd.to_datetime(value,utc=True,errors='coerce')
                if pd.notna(stamp):
                    local=stamp.tz_convert('America/Cuiaba')
                    st.caption(f'{label}: {local:%d/%m %H:%M} (Cuiabá) · {stamp:%H:%M UTC}')
        retry=status.get('twelve_retry_after')
        if retry and not budget.get('blocked_until'):
            stamp=pd.to_datetime(retry,utc=True,errors='coerce')
            if pd.notna(stamp): st.caption(f'Nova consulta permitida a partir de {stamp.tz_convert("America/Cuiaba"):%d/%m %H:%M}. A coleta depende da próxima rodada do Autopilot.')

    a,b,c,d=st.columns(4)
    a.metric("Scanner fresco",f"{int(status.get('scanner_fresh',0))}/7")
    b.metric("Market Map fresco",f"{int(status.get('market_map_fresh',0))}/7")
    c.metric("Validações pendentes",int(status.get("validation_pending",0)))
    d.metric("Validações completas",int(status.get("validation_complete",0)))

    e,f,g,h=st.columns(4)
    e.metric("Histórias únicas",int(status.get("news_unique_stories",0) or 0))
    f.metric("Snapshots",int(status.get("validation_rows",0)))
    g.metric("Consultas nesta rodada",int(status.get("twelve_calls_this_run",0)), "externas reais")
    h.metric("Mercado FX", "ABERTO" if market_open else "FECHADO")
    st.caption(
        "Prontidão operacional: "
        + ("MERCADO FECHADO" if readiness=="MARKET_CLOSED" else readiness or "N/D")
        + f" · Scanner pronto: {'SIM' if status.get('scanner_ready') else 'NÃO'}"
        + f" · Market Map pronto: {'SIM' if status.get('market_map_ready') else 'NÃO'}"
    )

    quota_shadow=dict(status.get("quota_shadow",{}) or {})
    if quota_shadow:
        st.markdown("### 🌐 28FX — Quota Shadow")
        st.caption(
            "Telemetria observacional para validar a expansão adaptativa 7→28. "
            "Não altera PAIR_ORDER, cadência, quota nem libera novos pares."
        )
        q1,q2,q3,q4=st.columns(4)
        q1.metric(
            "Rodadas mercado aberto",
            f"{int(quota_shadow.get('market_open_runs',0))}/{int(quota_shadow.get('min_market_runs',20))}",
        )
        q2.metric(
            "Bloqueios do provedor",
            int(quota_shadow.get("provider_blocked_runs",0)),
        )
        q3.metric(
            "Plano cabe no cap",
            "SIM" if quota_shadow.get("adaptive_plan_fit_all_samples") else "NÃO",
        )
        q4.metric(
            "Revisão manual",
            "ELEGÍVEL" if quota_shadow.get("eligible_for_manual_review") else "AGUARDANDO",
        )
        if quota_shadow.get("quota_shadow_validated"):
            st.success(
                "Quota Shadow atingiu a amostra mínima sem bloqueios registrados. "
                "Isso habilita apenas revisão manual da expansão; expansão automática continua desativada."
            )
        else:
            st.info(
                "Quota Shadow ainda está acumulando evidência real. "
                "Nenhuma expansão automática é permitida."
            )
        st.caption(
            "Auto-expansão: DESATIVADA · "
            f"persistência: {'OK' if quota_shadow.get('persisted') else 'aguardando/indisponível'}"
        )

    st.markdown("### ⚙️ O que ficou automático")
    st.markdown(
        "- ✅ execução headless do app para atualizar macro/FRED e Matriz\n"
        "- ✅ notícias globais USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD\n"
        "- ✅ M15 ~30–60min, H1 ~1–2h e H4 ~4h, sujeitos a orçamento e agendamento\n- ✅ limite persistido de 480 créditos/dia, com distribuição por hora\n"
        "- ✅ W1/D1/liquidez/ADR/Market Map em background\n"
        "- ✅ 1 snapshot por par/dia sem duplicidade\n"
        "- ✅ Timing Integrity: entry_time = momento real do congelamento\n"
        "- ✅ validação 1H/4H/24H sem clicar\n"
        "- ✅ fim de semana reduz consultas técnicas automaticamente"
    )
    st.info(
        "As telas reutilizam o cache, sem novas consultas à Twelve Data. "
        "A coleta externa é exclusiva do Autopilot. Atualizar a página não renova a cota."
    )

    if daily_blocked:
        with st.expander("🧯 Motivo do bloqueio Twelve Data"):
            st.write(status.get("twelve_daily_block_reason", "HTTP 429"))
            st.caption(
                "V10.7.7: após identificar cota/quota bloqueada, nenhuma nova chamada externa "
                "é feita nesta execução."
            )

    stats=status.get("snapshot_stats",{}) or {}
    st.markdown("### 🧪 Última rodada")
    st.json({
        "novos_snapshots":stats.get("added",0),
        "sinais_congelados":stats.get("frozen",0),
        "horizontes_validados":stats.get("validated_horizons",0),
        "timings_migrados":stats.get("migrated",0),
        "app_headless_ok":status.get("app_headless_ok"),
    })

    errors=status.get("errors",[]) or []
    if errors:
        with st.expander(f"⚠️ Diagnóstico ({len(errors)} ocorrência(s))"):
            for x in errors:
                st.write("•",x)
    else:
        st.success("Nenhum erro registrado na última rodada.")