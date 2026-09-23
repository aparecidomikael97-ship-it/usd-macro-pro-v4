"""AION capability and routing contract.

AION is the administrator's general intelligent assistant inside AtlasQuant.
It can reason over AtlasQuant context, answer general questions, and request
current web research through an external research adapter when available.

This module is policy/architecture only. It does not itself call the internet,
change trading state, publish releases, move money, or place orders.
"""
from __future__ import annotations
from typing import Any,Mapping

CAPABILITY_VERSION="AION_CAPABILITIES_V1"

CAPABILITIES={
    "general_knowledge":True,
    "atlasquant_context":True,
    "market_context":True,
    "web_research_when_needed":True,
    "source_citations_for_current_research":True,
    "session_context":True,
    "document_explanation":True,
    "comparisons":True,
    "summaries":True,
    "education":True,
    "system_diagnostics":True,
    "paper_diagnostics":True,
    "voice_output_ptbr":True,
    "external_platform_connectors":True,
    "youtube_connector":True,
    "spotify_connector":True,
    "oauth_connection_manager":True,
    "direct_order_authorization":False,
    "bypass_gate_or_risk":False,
    "automatic_production_promotion":False,
    "financial_transfer":False,
}

RESEARCH_REQUIRED_HINTS=(
    "hoje","agora","atual","último","ultima","última","notícia","noticias","notícias",
    "preço","cotação","taxa","clima","resultado","lançamento","site","internet","pesquise",
    "procure","confira","verifique",
)

def aion_capabilities()->dict[str,Any]:
    return {
        "schema":CAPABILITY_VERSION,
        "assistant_name":"AION",
        "full_title":"AION — Assistente de Voz Inteligente do Atlas Code",
        "product_context":"AtlasQuant",
        "language":"pt-BR",
        "capabilities":dict(CAPABILITIES),
        "behavior":{
            "unknown_answer":"NAO_INVENTAR",
            "current_information":"PESQUISAR_QUANDO_ADAPTADOR_DISPONIVEL",
            "research_answer":"CITAR_FONTES_E_SEPARAR_FATO_DE_INFERENCIA",
            "atlasquant_answer":"USAR_FONTE_DE_VERDADE_DO_SISTEMA",
            "safety_actions":"EXIGIR_PERMISSAO_E_CONTROLES_AUTORITATIVOS",
        },
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }

def route_aion_query(question:str,*,research_adapter_available:bool,atlasquant_context_available:bool)->dict[str,Any]:
    q=" ".join(str(question or "").strip().lower().split())
    if not q:
        return {"route":"REJECTED","reason":"EMPTY_QUESTION","research_required":False,
                "real_orders_enabled":False,"voice_can_authorize_orders":False}
    research_required=any(token in q for token in RESEARCH_REQUIRED_HINTS)
    atlas_terms=("atlasquant","sistema","paper","radar","gate","risk","scanner","macro","release","admin")
    system_related=any(token in q for token in atlas_terms)
    if system_related and atlasquant_context_available:
        route="ATLASQUANT_CONTEXT"
    elif research_required and research_adapter_available:
        route="WEB_RESEARCH"
    elif research_required and not research_adapter_available:
        route="RESEARCH_UNAVAILABLE"
    else:
        route="GENERAL_AI"
    return {
        "route":route,
        "research_required":research_required,
        "system_related":system_related,
        "must_cite_sources":route=="WEB_RESEARCH",
        "must_disclose_research_unavailable":route=="RESEARCH_UNAVAILABLE",
        "real_orders_enabled":False,
        "voice_can_authorize_orders":False,
    }
