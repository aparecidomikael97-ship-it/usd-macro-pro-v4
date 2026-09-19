"""AtlasQuant SALES portal.

Commercial/onboarding presentation only. No payments, billing, broker access,
live-order permissions or automatic user activation are performed here.
"""
from __future__ import annotations

from typing import Any, Mapping
import streamlit as st

from atlasquant_platform_center import pwa_asset_audit, PWA_URL
from atlasquant_commercial_launch_guard import CommercialEvidence, assess_commercial_launch
from atlasquant_commercial_security_evidence import collect_commercial_security_evidence

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
    security=collect_commercial_security_evidence()
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
        "sales_role_isolation_verified":bool(security.get("sales_role_isolated_ok",False)),
        "account_revocation_verified":bool(security.get("account_revocation_ok",False)),
        "account_admin_verified":bool(security.get("account_admin_ok",False)),
        "audit_manifest_verified":bool(security.get("audit_manifest_ok",False)),
    }


def sales_launch_summary(status:Mapping[str,Any]|None)->dict[str,str]:
    s=dict(status or {})
    security_ok=all(bool(s.get(k,False)) for k in (
        "sales_role_isolation_verified",
        "account_revocation_verified",
        "account_admin_verified",
        "audit_manifest_verified",
    ))
    if not security_ok:
        return {"label":"SEGURANÇA A REVISAR","detail":"Um ou mais contratos internos de acesso/auditoria não foram verificados"}
    if not bool(s.get("pwa_ready",False)):
        return {"label":"DISTRIBUIÇÃO BLOQUEADA","detail":"PWA ainda não passou no checklist de instalação"}
    if bool(s.get("payments_integrated",False)) and bool(s.get("academy_ready",False)):
        return {"label":"REVISÃO COMERCIAL","detail":"Infraestrutura principal pronta; lançamento continua manual"}
    return {"label":"PRÉ-LANÇAMENTO","detail":"Segurança interna e PWA verificadas; itens externos/comerciais continuam pendentes"}


def render_sales_center(access:Mapping[str,Any]|None)->dict[str,Any]:
    st.subheader("💼 Portal Comercial")
    if not sales_access_allowed(access):
        st.error("Área comercial restrita aos perfis SALES e ADMIN autenticados.")
        return {"allowed":False,"schema":SCHEMA}

    status=commercial_readiness(access)
    visual=sales_launch_summary(status)
    st.markdown(
        f"""<div style="padding:11px 13px;border:1px solid rgba(137,170,210,.18);border-radius:12px;margin:4px 0 13px">
        <strong>COMERCIAL · {visual['label']}</strong><br>
        <span style="opacity:.74;font-size:.78rem">{visual['detail']}</span>
        </div>""", unsafe_allow_html=True,
    )
    st.caption(
        "Onboarding e preparação comercial. Esta área não processa pagamentos, "
        "não ativa broker e não concede permissão de trading real."
    )

    c1,c2,c3,c4=st.columns(4)
    c1.metric("PWA","PRONTA" if status["pwa_ready"] else "BLOQUEADA")
    c2.metric("Contas ativas",status["active_accounts"])
    c3.metric("Academy","PLANEJADA")
    c4.metric("Trading real","DESATIVADO")
    security_ok=all(bool(status.get(k,False)) for k in (
        "sales_role_isolation_verified","account_revocation_verified",
        "account_admin_verified","audit_manifest_verified",
    ))
    st.caption("Segurança interna: "+("✅ contratos verificados" if security_ok else "⚠️ revisão necessária"))

    st.markdown("### Fluxo de onboarding")
    st.dataframe(onboarding_steps(),width="stretch",hide_index=True)

    st.link_button("Abrir PWA do AtlasQuant",PWA_URL,width="stretch")

    st.markdown("### Checklist antes da venda")
    checklist=[
        ("Login e perfis","PRONTO"),
        ("Portal ADMIN / SALES","PRONTO"),
        ("Isolamento SALES","VERIFICADO" if status["sales_role_isolation_verified"] else "REVISAR"),
        ("Revogação de conta/sessão","VERIFICADA" if status["account_revocation_verified"] else "REVISAR"),
        ("Auditoria administrativa","VERIFICADA" if status["audit_manifest_verified"] else "REVISAR"),
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
        private_access_ok=sales_access_allowed(access),
        account_admin_ok=bool(status.get("account_admin_verified",False)),
        distribution_ok=bool(status["pwa_ready"]),
        terms_privacy_ok=False,
        data_licensing_ok=False,
        support_ok=False,
        academy_minimum_ok=bool(status["academy_ready"]),
        billing_ok=bool(status["payments_integrated"]),
        sales_role_isolated_ok=bool(status["sales_role_isolation_verified"]),
        account_revocation_ok=bool(status["account_revocation_verified"]),
        audit_manifest_ok=bool(status["audit_manifest_verified"]),
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
