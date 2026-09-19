"""AtlasQuant SALES portal.

Commercial/onboarding presentation only. No payments, billing, broker access,
live-order permissions or automatic user activation are performed here.
"""
from __future__ import annotations

from typing import Any, Mapping
import streamlit as st

from atlasquant_platform_center import pwa_asset_audit, PWA_URL
from atlasquant_commercial_launch_guard import CommercialEvidence, assess_commercial_launch

SCHEMA="ATLASQUANT_SALES_CENTER_V1"

def sales_access_allowed(access:Mapping[str,Any]|None)->bool:
    if not isinstance(access,Mapping):
        return False
    role=str(access.get("role") or "").strip().upper()
    session=access.get("session")
    if role not in ("SALES","ADMIN") or not isinstance(session,Mapping):
        return False
    session_role=str(session.get("role") or "").strip().upper()
    username=str(session.get("username") or "").strip()
    return bool(username and session_role==role)

def onboarding_steps()->list[dict[str,str]]:
    return [
        {"Etapa":"1","Item":"Conta","Status":"PRONTO","Descrição":"Criar USER/SALES/ADMIN e validar acesso."},
        {"Etapa":"2","Item":"Instalação","Status":"PRONTO — PWA","Descrição":"Android, iOS/iPadOS, Windows, macOS e Linux via PWA."},
        {"Etapa":"3","Item":"Primeiro acesso","Status":"PRONTO","Descrição":"Entrar, revisar viés e qualidade dos dados."},
        {"Etapa":"4","Item":"Academy","Status":"PLANEJADO","Descrição":"Vídeos e trilhas serão produzidos após estabilização das telas."},
        {"Etapa":"5","Item":"Assistente de voz","Status":"PLANEJADO","Descrição":"Briefing diário/semanal e explicação do viés."},
        {"Etapa":"6","Item":"Corretoras & plataformas","Status":"PLANEJADO","Descrição":"Guia comparativo revisado próximo ao lançamento comercial."},
    ]

def commercial_readiness(access:Mapping[str,Any]|None=None)->dict[str,Any]:
    audit=pwa_asset_audit()
    registry=(access or {}).get("registry") if isinstance(access,Mapping) else {}
    if not isinstance(registry,Mapping):
        registry={}
    total=registry.get("TOTAL",0)
    try:
        if isinstance(total,bool):
            raise ValueError("boolean count")
        total=float(total)
        if not total.is_integer() or total<0 or total!=total or total in (float("inf"),float("-inf")):
            raise ValueError("invalid count")
        total=int(total)
    except Exception:
        total=0
    return {
        "schema":SCHEMA,
        "pwa_ready":bool(audit.get("pwa_ready")),
        "active_accounts":total,
        "academy_ready":False,
        "voice_ready":False,
        "brokers_guide_ready":False,
        "native_stores_ready":False,
        "payments_integrated":False,
        "broker_execution_enabled":False,
        "real_orders_enabled":False,
    }

def render_sales_center(access:Mapping[str,Any]|None)->dict[str,Any]:
    st.subheader("💼 Portal Comercial")
    if not sales_access_allowed(access):
        st.error("Área comercial restrita aos perfis SALES e ADMIN autenticados.")
        return {"allowed":False,"schema":SCHEMA}

    status=commercial_readiness(access)
    st.caption(
        "Onboarding e preparação comercial. Esta área não processa pagamentos, "
        "não ativa broker e não concede permissão de trading real."
    )

    c1,c2,c3,c4=st.columns(4)
    c1.metric("PWA","PRONTA" if status["pwa_ready"] else "BLOQUEADA")
    c2.metric("Contas ativas",status["active_accounts"])
    c3.metric("Academy","PLANEJADA")
    c4.metric("Trading real","DESATIVADO")

    st.markdown("### Fluxo de onboarding")
    st.dataframe(onboarding_steps(),width="stretch",hide_index=True)

    st.link_button("Abrir PWA do AtlasQuant",PWA_URL,width="stretch")

    st.markdown("### Checklist antes da venda")
    checklist=[
        ("Login e perfis","PRONTO"),
        ("Portal ADMIN / SALES","PRONTO"),
        ("PWA instalável","PRONTO" if status["pwa_ready"] else "BLOQUEADO"),
        ("Academy e vídeos","PENDENTE"),
        ("Assistente de voz","PENDENTE"),
        ("Guia de corretoras","PENDENTE"),
        ("Termos / privacidade / riscos","PENDENTE"),
        ("Licenciamento comercial de dados","PENDENTE"),
        ("Pagamento / assinatura","PENDENTE"),
        ("Play Store / App Store","PENDENTE"),
    ]
    st.dataframe(
        [{"Item":item,"Estado":state} for item,state in checklist],
        width="stretch",
        hide_index=True,
    )
    launch=assess_commercial_launch(CommercialEvidence(
        private_access_ok=True,
        account_admin_ok=True,
        distribution_ok=bool(status["pwa_ready"]),
        terms_privacy_ok=False,
        data_licensing_ok=False,
        support_ok=False,
        academy_minimum_ok=bool(status["academy_ready"]),
        billing_ok=bool(status["payments_integrated"]),
    ))
    if launch["status"]=="BLOCKED":
        st.warning("Venda pública ainda BLOQUEADA pelo guard comercial.")
        st.caption(" · ".join(launch["blockers"]))
    else:
        st.success("Pré-requisitos comerciais completos para revisão humana final.")
    st.info(
        "O produto ainda não deve ser marcado como pronto para venda pública "
        "enquanto itens comerciais/regulatórios essenciais permanecerem pendentes."
    )
    return {"allowed":True,**status,"launch_guard":launch}
