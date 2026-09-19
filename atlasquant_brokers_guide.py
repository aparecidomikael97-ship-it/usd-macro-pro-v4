"""AtlasQuant Brokers & Platforms Guide.

Educational/commercial guidance only. This module does not connect accounts,
store credentials, recommend a specific broker, route orders or enable live trading.
"""
from __future__ import annotations
from typing import Any
import streamlit as st

SCHEMA="ATLASQUANT_BROKERS_GUIDE_V1"

SECTIONS=(
    {"id":"difference","title":"Corretora × plataforma × provedor de dados","items":(
        "Corretora mantém a conta e recebe ordens quando uma integração real existe.",
        "Plataforma é a interface usada para gráficos, análise ou execução.",
        "Provedor de dados entrega cotações e informações; isso não significa que execute ordens.",
    )},
    {"id":"compatibility","title":"Como avaliar compatibilidade","items":(
        "Confirme instrumentos Forex disponíveis, símbolos, fuso e especificação de contrato.",
        "Verifique documentação oficial de API, ambiente demo/paper e limites de uso.",
        "Compare latência, qualidade de dados, custos, spread e regras da sua jurisdição antes de qualquer integração.",
    )},
    {"id":"paper","title":"Comece em Paper / Demo","items":(
        "Valide leitura de símbolos, preços e horários sem dinheiro real.",
        "Teste rejeições, mercado fechado, dados stale e perda de conexão.",
        "Resultados simulados não garantem resultados em conta real.",
    )},
    {"id":"credentials","title":"Credenciais e segurança","items":(
        "Nunca cole senha, token, secret ou chave privada em suporte, código-fonte ou commit.",
        "Use armazenamento de secrets e permissões mínimas quando uma integração for aprovada.",
        "Chaves de leitura e de negociação devem ser tratadas como capacidades diferentes.",
    )},
    {"id":"live","title":"Estado do AtlasQuant","items":(
        "O guia não representa conexão ativa com nenhuma corretora.",
        "Trading real permanece desativado; USER, SALES e ADMIN não concedem permissão de ordens reais.",
        "Qualquer integração futura deve passar por testes, safety gates e revisão humana antes de produção.",
    )},
)

def brokers_guide_catalog()->list[dict[str,Any]]:
    return [{"id":x["id"],"title":x["title"],"items":tuple(x["items"])} for x in SECTIONS]

def brokers_guide_minimum_ready()->bool:
    required={"difference","compatibility","paper","credentials","live"}
    ids={str(x["id"]) for x in SECTIONS}
    text=" ".join(item for x in SECTIONS for item in x["items"]).casefold()
    safety=("trading real permanece desativado" in text and "não representa conexão ativa" in text)
    return required.issubset(ids) and safety and all(bool(x["items"]) for x in SECTIONS)

def render_brokers_guide()->dict[str,Any]:
    st.subheader("🔌 Corretoras & Plataformas")
    st.caption("Guia de compatibilidade e segurança. Não conecta contas e não habilita trading real.")
    for section in SECTIONS:
        with st.expander(section["title"],expanded=section["id"]=="difference"):
            for item in section["items"]:
                st.markdown(f"- {item}")
    st.warning("Status: guia informativo pronto · conexão com corretora e execução real NÃO habilitadas.")
    return {"schema":SCHEMA,"ready":brokers_guide_minimum_ready(),"broker_connected":False,"real_orders_enabled":False}

__all__=["SCHEMA","SECTIONS","brokers_guide_catalog","brokers_guide_minimum_ready","render_brokers_guide"]
