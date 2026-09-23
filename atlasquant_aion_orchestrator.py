"""AION conversational orchestrator.

Routes administrator questions between AtlasQuant authoritative context,
external platforms, current web research and a general-AI adapter.

Adapters are dependency-injected callables. If an adapter is absent, AION says
so explicitly instead of fabricating capability.
"""
from __future__ import annotations
from typing import Any,Callable,Mapping,Sequence
from atlasquant_aion_capabilities import route_aion_query
from atlasquant_aion_platform_intent import evaluate_platform_intent
from atlasquant_aion_research_contract import validate_research_response,research_unavailable_message
from atlasquant_aion_action_approval import build_pending_action
from atlasquant_admin_voice_qa import answer_admin_question

Adapter=Callable[...,Any]

def _normalize_general_response(raw:Any)->dict[str,Any]:
    if isinstance(raw,Mapping):
        answer=" ".join(str(raw.get("answer") or raw.get("text") or "").strip().split())
        meta=dict(raw.get("metadata",{}) or {})
    else:
        answer=" ".join(str(raw or "").strip().split())
        meta={}
    if not answer:
        return {"ok":False,"answer":"O motor geral do AION não retornou uma resposta válida.","metadata":{}}
    return {"ok":True,"answer":answer,"metadata":meta}

def answer_aion(
    question:str,*,
    admin_state:Mapping[str,Any]|None=None,
    changes:Sequence[Any]|None=None,
    macro_summary:Sequence[Any]|None=None,
    opportunities:Sequence[Mapping[str,Any]]|None=None,
    paper_summary:Mapping[str,Any]|None=None,
    memory:Sequence[Mapping[str,Any]]|None=None,
    connections:Mapping[str,Any]|None=None,
    general_ai_adapter:Adapter|None=None,
    web_research_adapter:Adapter|None=None,
    connector_adapter:Adapter|None=None,
)->dict[str,Any]:
    q=" ".join(str(question or "").strip().split())
    if not q:
        return {
            "ok":False,"route":"REJECTED","answer":"Faça uma pergunta para o AION.",
            "sources":[],"confirmation_required":False,
            "real_orders_enabled":False,"voice_can_authorize_orders":False,
        }

    platform=evaluate_platform_intent(q,connections)
    if platform.get("matched"):
        provider=platform.get("provider")
        if not platform.get("allowed"):
            answer=(
                f"O conector {provider} ainda não está conectado ao AION."
                if platform.get("reason")=="CONNECTOR_NOT_CONNECTED"
                else f"Essa ação em {provider} não está liberada."
            )
            return {
                "ok":False,"route":"EXTERNAL_PLATFORM","answer":answer,"sources":[],
                "platform":platform,"confirmation_required":bool(platform.get("confirmation_required")),
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        if platform.get("confirmation_required"):
            pending=build_pending_action(
                provider=str(provider),
                action_class=str(platform.get("action_class") or "WRITE"),
                payload={"question":q},
            )
            return {
                "ok":True,"route":"EXTERNAL_PLATFORM_CONFIRMATION",
                "answer":f"Posso preparar essa ação em {provider}, mas preciso da sua confirmação antes de executar.",
                "sources":[],"platform":platform,"pending_action":pending,
                "confirmation_required":True,
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        if connector_adapter is None:
            return {
                "ok":False,"route":"EXTERNAL_PLATFORM_ADAPTER_UNAVAILABLE",
                "answer":f"O conector {provider} está autorizado na conta, mas o adaptador de execução ainda não está conectado ao runtime do AION.",
                "sources":[],"platform":platform,"confirmation_required":False,
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        try:
            raw=connector_adapter(
                provider=str(provider),
                action_class="READ",
                payload={"question":q},
            )
        except Exception as exc:
            return {
                "ok":False,"route":"EXTERNAL_PLATFORM_ERROR",
                "answer":f"Não consegui consultar {provider} agora. O AION não vai fingir que a consulta foi concluída.",
                "sources":[],"platform":platform,"adapter_error":type(exc).__name__,
                "confirmation_required":False,
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        data=dict(raw or {}) if isinstance(raw,Mapping) else {}
        answer=" ".join(str(data.get("answer") or data.get("summary") or "").strip().split())
        if not answer:
            answer=f"Consulta em {provider} concluída pelo adaptador. Os dados estruturados ficaram disponíveis para o AION."
        return {
            "ok":bool(data.get("ok",True)),"route":"EXTERNAL_PLATFORM_READ",
            "answer":answer,"sources":list(data.get("sources",[]) or []),
            "platform":platform,"connector_result":data,"confirmation_required":False,
            "source_of_truth":"EXTERNAL_PLATFORM",
            "real_orders_enabled":False,"voice_can_authorize_orders":False,
        }

    atlas_available=bool(admin_state)
    route=route_aion_query(
        q,
        research_adapter_available=web_research_adapter is not None,
        atlasquant_context_available=atlas_available,
    )
    selected=route.get("route")

    if selected=="ATLASQUANT_CONTEXT":
        out=answer_admin_question(
            q,admin_state=admin_state,changes=changes,macro_summary=macro_summary,
            opportunities=opportunities,paper_summary=paper_summary,
        )
        return {
            "ok":True,"route":selected,"answer":out["answer"],"sources":[],
            "confirmation_required":False,"source_of_truth":"ATLASQUANT",
            "real_orders_enabled":False,"voice_can_authorize_orders":False,
        }

    if selected=="WEB_RESEARCH":
        try:
            raw=web_research_adapter(question=q,memory=list(memory or []))
        except Exception as exc:
            return {
                **research_unavailable_message(),
                "route":"WEB_RESEARCH_ERROR",
                "adapter_error":type(exc).__name__,
                "confirmation_required":False,
            }
        validated=validate_research_response(raw if isinstance(raw,Mapping) else {})
        return {
            **validated,
            "route":"WEB_RESEARCH",
            "confirmation_required":False,
            "source_of_truth":"WEB_SOURCES",
        }

    if selected=="RESEARCH_UNAVAILABLE":
        return {
            **research_unavailable_message(),
            "route":"RESEARCH_UNAVAILABLE",
            "confirmation_required":False,
        }

    if selected=="GENERAL_AI":
        if general_ai_adapter is None:
            return {
                "ok":False,"route":"GENERAL_AI_UNAVAILABLE",
                "answer":"Essa pergunta é geral. O núcleo conversacional amplo do AION ainda precisa ser conectado ao runtime para eu responder dentro do AtlasQuant sem inventar.",
                "sources":[],"confirmation_required":False,
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        try:
            normalized=_normalize_general_response(
                general_ai_adapter(question=q,memory=list(memory or []))
            )
        except Exception as exc:
            return {
                "ok":False,"route":"GENERAL_AI_ERROR",
                "answer":"O núcleo geral do AION encontrou um erro e não vou inventar uma resposta.",
                "sources":[],"adapter_error":type(exc).__name__,
                "confirmation_required":False,
                "real_orders_enabled":False,"voice_can_authorize_orders":False,
            }
        return {
            **normalized,"route":"GENERAL_AI","sources":[],
            "confirmation_required":False,"source_of_truth":"GENERAL_AI",
            "real_orders_enabled":False,"voice_can_authorize_orders":False,
        }

    return {
        "ok":False,"route":"REJECTED","answer":"Não consegui classificar essa solicitação com segurança.",
        "sources":[],"confirmation_required":False,
        "real_orders_enabled":False,"voice_can_authorize_orders":False,
    }
