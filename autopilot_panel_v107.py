"""USD Macro Pro V10.7 — Autopilot health panel."""
from __future__ import annotations
import base64, json, os
from typing import Any
import pandas as pd
import requests
import streamlit as st

STATUS_PATH="dados/autopilot_status_v107.json"

def _cfg():
    return (
        str(st.secrets.get("GITHUB_TOKEN_HISTORICO", os.getenv("GITHUB_TOKEN_HISTORICO",""))),
        str(st.secrets.get("GITHUB_REPO_HISTORICO", os.getenv("GITHUB_REPO_HISTORICO",""))),
        str(st.secrets.get("GITHUB_BRANCH_HISTORICO", os.getenv("GITHUB_BRANCH_HISTORICO","main")) or "main"),
    )

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
        return max(0,(pd.Timestamp.now(tz="UTC")-ts).total_seconds()/60)
    except Exception: return None

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

    age=_age_min(status.get("last_run"))
    healthy=bool(status.get("healthy",False))
    errors = status.get("errors", []) or []
    daily_blocked = bool(status.get("twelve_daily_blocked", False))
    has_429 = any("HTTP 429" in str(x) for x in errors)
    headless_bad = not bool(status.get("app_headless_ok", False))

    if healthy:
        st.success("🟢 AUTOPILOT SAUDÁVEL")
    elif headless_bad:
        st.error("🔴 AUTOPILOT: APP HEADLESS NÃO ATUALIZOU A MATRIZ")
    elif daily_blocked:
        block_type = str(status.get("twelve_block_type", "") or "")
        reason = str(status.get("twelve_daily_block_reason", "")).lower()
        if "current minute" in reason or "per minute" in reason:
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

    a,b,c,d=st.columns(4)
    a.metric("Scanner fresco",f"{int(status.get('scanner_fresh',0))}/7")
    b.metric("Market Map fresco",f"{int(status.get('market_map_fresh',0))}/7")
    c.metric("Validações pendentes",int(status.get("validation_pending",0)))
    d.metric("Validações completas",int(status.get("validation_complete",0)))

    e,f,g,h=st.columns(4)
    e.metric("Histórias únicas",int(status.get("news_unique_stories",0) or 0))
    f.metric("Snapshots",int(status.get("validation_rows",0)))
    g.metric("Calls Twelve/run",int(status.get("twelve_calls_this_run",0)), "externas reais")
    h.metric("Mercado FX", "ABERTO" if status.get("forex_market_open") else "FECHADO")

    st.markdown("### ⚙️ O que ficou automático")
    st.markdown(
        "- ✅ execução headless do app para atualizar macro/FRED e Matriz\n"
        "- ✅ notícias globais USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD\n"
        "- ✅ scanner M15 ~30min, H1 ~1h e H4 ~4h\n- ✅ limitador automático distribui as consultas Twelve Data no tempo\n"
        "- ✅ W1/D1/liquidez/ADR/Market Map em background\n"
        "- ✅ 1 snapshot por par/dia sem duplicidade\n"
        "- ✅ Timing Integrity: entry_time = momento real do congelamento\n"
        "- ✅ validação 1H/4H/24H sem clicar\n"
        "- ✅ fim de semana reduz consultas técnicas automaticamente"
    )
    st.info(
        "Os botões manuais continuam no app apenas como contingência. "
        "O fluxo normal da V10.7 não depende deles."
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
