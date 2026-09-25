"""AION external text-provider adapter.

This module is intentionally fail-closed. It supports a configured OpenAI
Responses API client, but it never runs unless the caller supplies all of:
- external feature enabled;
- provider configuration present;
- non-sensitive prompt;
- explicit approval for this request;
- a non-zero administrator budget;
- configured token pricing for preflight cost estimation.

No API key is returned, logged, or persisted. Model output is never marked as a
confirmed fact merely because a provider generated it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import json
import math
import os

import requests

from atlasquant_aion_model_router import (
    budget_decision,
    normalize_budget,
    privacy_sensitive,
)
from atlasquant_aion_observability import redact_text

SCHEMA="ATLASQUANT_AION_PROVIDER_V1"
OPENAI_RESPONSES_URL="https://api.openai.com/v1/responses"
MAX_PROMPT_CHARS=40000
DEFAULT_TIMEOUT_SECONDS=45.0


@dataclass(frozen=True)
class ProviderConfig:
    provider:str
    api_key:str
    fast_model:str
    reasoning_model:str
    input_usd_per_mtok:float
    output_usd_per_mtok:float
    max_output_tokens:int
    timeout_seconds:float

    @property
    def key_present(self)->bool:
        return bool(str(self.api_key or "").strip())

    @property
    def pricing_present(self)->bool:
        return self.input_usd_per_mtok>0 and self.output_usd_per_mtok>0

    def model_for_lane(self,lane:str)->str:
        return self.reasoning_model if str(lane).upper()=="EXTERNAL_REASONING" else self.fast_model


def _env(name:str,values:Mapping[str,Any]|None=None)->str:
    supplied=dict(values or {})
    if name in supplied:
        return str(supplied.get(name) or "").strip()
    return str(os.getenv(name,"") or "").strip()


def _float(value:Any,default:float=0.0)->float:
    try:
        return max(0.0,float(value))
    except Exception:
        return default


def _int(value:Any,default:int)->int:
    try:
        return max(1,int(float(value)))
    except Exception:
        return default


def provider_config(values:Mapping[str,Any]|None=None)->ProviderConfig:
    provider=(_env("AION_MODEL_PROVIDER",values) or "offline").casefold()
    return ProviderConfig(
        provider=provider,
        api_key=_env("OPENAI_API_KEY",values),
        fast_model=_env("AION_OPENAI_FAST_MODEL",values),
        reasoning_model=_env("AION_OPENAI_REASONING_MODEL",values),
        input_usd_per_mtok=_float(_env("AION_OPENAI_INPUT_USD_PER_MTOK",values)),
        output_usd_per_mtok=_float(_env("AION_OPENAI_OUTPUT_USD_PER_MTOK",values)),
        max_output_tokens=min(8192,_int(_env("AION_OPENAI_MAX_OUTPUT_TOKENS",values),1200)),
        timeout_seconds=min(120.0,max(5.0,_float(_env("AION_OPENAI_TIMEOUT_SECONDS",values),DEFAULT_TIMEOUT_SECONDS))),
    )


def provider_configuration_status(values:Mapping[str,Any]|None=None)->dict[str,Any]:
    cfg=provider_config(values)
    provider_supported=cfg.provider=="openai"
    models_present=bool(cfg.fast_model and cfg.reasoning_model)
    ready=bool(provider_supported and cfg.key_present and models_present and cfg.pricing_present)
    if cfg.provider in {"","offline","local","zero-cost"}:
        state="ZERO_COST_LOCAL"
    elif not provider_supported:
        state="UNSUPPORTED_PROVIDER"
    elif not cfg.key_present:
        state="MISSING_API_KEY"
    elif not models_present:
        state="MISSING_MODEL_CONFIG"
    elif not cfg.pricing_present:
        state="MISSING_PRICING_CONFIG"
    else:
        state="EXTERNAL_READY"
    return {
        "schema":SCHEMA,
        "provider":cfg.provider,
        "state":state,
        "ready":ready,
        "api_key_present":cfg.key_present,
        "fast_model":cfg.fast_model,
        "reasoning_model":cfg.reasoning_model,
        "pricing_configured":cfg.pricing_present,
        "input_usd_per_mtok":cfg.input_usd_per_mtok,
        "output_usd_per_mtok":cfg.output_usd_per_mtok,
        "max_output_tokens":cfg.max_output_tokens,
        "automatic_billing":False,
        "api_key_exposed":False,
    }


def _estimated_input_tokens(text:Any)->int:
    # Conservative dependency-free approximation for preflight only.
    chars=len(str(text or ""))
    return max(1,math.ceil(chars/3.5))


def estimate_request_cost(
    prompt:Any,
    *,
    config:ProviderConfig|None=None,
    max_output_tokens:int|None=None,
)->dict[str,Any]:
    cfg=config or provider_config()
    input_tokens=_estimated_input_tokens(prompt)
    output_tokens=min(cfg.max_output_tokens,max(1,int(max_output_tokens or cfg.max_output_tokens)))
    if not cfg.pricing_present:
        return {
            "schema":SCHEMA,
            "state":"PRICING_NOT_CONFIGURED",
            "estimable":False,
            "estimated_input_tokens":input_tokens,
            "reserved_output_tokens":output_tokens,
            "estimated_max_cost_usd":None,
        }
    cost=(input_tokens/1_000_000.0)*cfg.input_usd_per_mtok
    cost+=(output_tokens/1_000_000.0)*cfg.output_usd_per_mtok
    return {
        "schema":SCHEMA,
        "state":"ESTIMATED",
        "estimable":True,
        "estimated_input_tokens":input_tokens,
        "reserved_output_tokens":output_tokens,
        "estimated_max_cost_usd":round(cost,6),
    }


def _evidence_lines(memory_hits:Sequence[Mapping[str,Any]]|None)->list[str]:
    out=[]
    for hit in list(memory_hits or [])[:5]:
        if not isinstance(hit,Mapping):
            continue
        path=redact_text(hit.get("path"))[:180]
        excerpt=redact_text(hit.get("excerpt"))[:1200]
        if path or excerpt:
            out.append(f"- Fonte: {path or 'memória'}\n  Trecho: {excerpt}")
    return out


def build_provider_prompt(
    question:Any,
    *,
    domain:Any="central",
    memory_hits:Sequence[Mapping[str,Any]]|None=None,
    system_context:Mapping[str,Any]|None=None,
)->str:
    q=redact_text(question).strip()
    system=dict(system_context or {})
    evidence="\n".join(_evidence_lines(memory_hits)) or "- Nenhuma evidência canônica fornecida."
    source_build=redact_text(system.get("source_build"))[:80] or "não confirmado"
    environment=redact_text(system.get("environment"))[:80] or "não confirmado"
    reliability=system.get("reliability") if isinstance(system.get("reliability"),Mapping) else {}
    degraded=(
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"),Mapping)
        else {}
    )
    data_guardian=(
        reliability.get("data_guardian")
        if isinstance(reliability.get("data_guardian"),Mapping)
        else {}
    )
    reconciliation=(
        data_guardian.get("reconciliation")
        if isinstance(data_guardian.get("reconciliation"),Mapping)
        else {}
    )
    reliability_posture=redact_text(reliability.get("posture"))[:40] or "não confirmado"
    degraded_state=redact_text(degraded.get("state"))[:40] or "não confirmado"
    source_conflicts=int(reconciliation.get("conflict_count") or 0)
    live_events=(
        system.get("live_event_intelligence")
        if isinstance(system.get("live_event_intelligence"),Mapping)
        else {}
    )
    live_event_state=redact_text(live_events.get("state"))[:40] or "não confirmado"
    live_event_alerts=int(live_events.get("alert_count") or 0)
    live_event_urgent=int(live_events.get("urgent_review_count") or 0)
    top_event=""
    top_alerts=[
        x for x in list(live_events.get("top_alerts",[]) or [])
        if isinstance(x,Mapping)
    ]
    if top_alerts:
        top=top_alerts[0]
        top_event=(
            f"{redact_text(top.get('headline'))[:240]} | "
            f"truth={redact_text(top.get('truth_state'))[:30]} | "
            f"impact={redact_text(top.get('impact_truth_state'))[:30]}"
        )
    prompt=f"""Você é o AION do AtlasQuant, assistente do administrador.

REGRAS OBRIGATÓRIAS:
1. Não invente fatos, integrações, resultados, clientes, mercado, deploys ou ações.
2. Separe claramente fato confirmado, inferência, hipótese e desconhecido.
3. Se a evidência não sustentar uma afirmação factual, diga que não está confirmado.
4. Não trate score de trading como probabilidade de lucro.
5. Não afirme que publicou, cobrou, executou, mesclou ou fez deploy.
6. Não autorize trading real.
7. Responda em português do Brasil, direto e operacional.
8. O texto do modelo é aconselhamento/explicação; ações externas continuam sob Guardian.

Contexto roteado: {redact_text(domain)[:80]}
Build informado pelo app: {source_build}
Ambiente informado pelo app: {environment}
Reliability posture: {reliability_posture}
Modo degradado: {degraded_state}
Conflitos de fonte confirmados: {source_conflicts}
Live Event Intelligence: {live_event_state}
Alertas de evento: {live_event_alerts}
Urgentes para revisão: {live_event_urgent}
Evento no topo: {top_event or "nenhum evento fresco fornecido"}

Se houver evento de notícia, trate a manchete como evidência de reportagem (INFERENCE/UNKNOWN)
a menos que a própria evidência fornecida confirme o fato. Impactos de mercado do Event Intelligence
são HYPOTHESIS e nunca autorização/sinal de trade.

Se Reliability estiver DEGRADED/CRITICAL ou o modo estiver DEGRADED_SAFE/FAIL_CLOSED,
não apresente a capacidade dependente como saudável. Se houver conflito de fonte,
descreva o conflito e peça/recomende reconciliação; não escolha uma fonte escondido.

EVIDÊNCIAS CANÔNICAS DISPONÍVEIS:
{evidence}

PERGUNTA DO ADMINISTRADOR:
{q}
"""
    return prompt[:MAX_PROMPT_CHARS]


def _extract_text(payload:Mapping[str,Any])->str:
    # Raw Responses API payload: collect output_text content blocks.
    pieces=[]
    output=payload.get("output")
    if isinstance(output,list):
        for item in output:
            if not isinstance(item,Mapping):
                continue
            content=item.get("content")
            if not isinstance(content,list):
                continue
            for block in content:
                if not isinstance(block,Mapping):
                    continue
                if str(block.get("type") or "")=="output_text":
                    text=block.get("text")
                    if isinstance(text,str) and text.strip():
                        pieces.append(text.strip())
    if pieces:
        return "\n".join(pieces).strip()
    # Some proxies/wrappers may expose a convenience output_text field.
    convenience=payload.get("output_text")
    return str(convenience or "").strip()


def _usage_cost(payload:Mapping[str,Any],cfg:ProviderConfig)->dict[str,Any]:
    usage=payload.get("usage") if isinstance(payload.get("usage"),Mapping) else {}
    try:
        input_tokens=max(0,int(usage.get("input_tokens") or 0))
    except Exception:
        input_tokens=0
    try:
        output_tokens=max(0,int(usage.get("output_tokens") or 0))
    except Exception:
        output_tokens=0
    actual=None
    if cfg.pricing_present and (input_tokens or output_tokens):
        actual=(input_tokens/1_000_000.0)*cfg.input_usd_per_mtok
        actual+=(output_tokens/1_000_000.0)*cfg.output_usd_per_mtok
        actual=round(actual,6)
    return {
        "input_tokens":input_tokens,
        "output_tokens":output_tokens,
        "actual_cost_usd_estimate":actual,
    }


def execute_openai_answer(
    prompt:Any,
    *,
    lane:Any,
    budget:Mapping[str,Any]|None,
    external_feature_enabled:bool,
    request_approved:bool,
    values:Mapping[str,Any]|None=None,
    session:requests.Session|None=None,
)->dict[str,Any]:
    """Call the configured provider only after every preflight gate passes."""
    cfg=provider_config(values)
    status=provider_configuration_status(values)
    clean_prompt=str(prompt or "").strip()[:MAX_PROMPT_CHARS]

    if privacy_sensitive(clean_prompt):
        return {
            "schema":SCHEMA,"state":"BLOCKED_PRIVACY","called":False,
            "reason":"Prompt contém sinal de dado sensível e permanece local.",
        }
    if not external_feature_enabled:
        return {
            "schema":SCHEMA,"state":"BLOCKED_FEATURE_FLAG","called":False,
            "reason":"Feature flag de modelo externo está desligada.",
        }
    if not status["ready"]:
        return {
            "schema":SCHEMA,"state":"BLOCKED_PROVIDER_CONFIG","called":False,
            "reason":status["state"],"provider_status":status,
        }
    if not request_approved:
        return {
            "schema":SCHEMA,"state":"BLOCKED_APPROVAL","called":False,
            "reason":"Solicitação externa exige aprovação explícita.",
        }

    estimate=estimate_request_cost(clean_prompt,config=cfg)
    if not estimate["estimable"] or estimate["estimated_max_cost_usd"] is None:
        return {
            "schema":SCHEMA,"state":"BLOCKED_COST_UNKNOWN","called":False,
            "reason":"Preço por token não está configurado; chamada bloqueada.",
            "estimate":estimate,
        }
    cost=budget_decision(
        normalize_budget(budget),
        estimate["estimated_max_cost_usd"],
        request_approved=True,
    )
    if not cost["allowed"]:
        return {
            "schema":SCHEMA,"state":"BLOCKED_BUDGET","called":False,
            "reason":cost["reason"],"estimate":estimate,"budget_decision":cost,
        }

    model=cfg.model_for_lane(str(lane))
    if not model:
        return {
            "schema":SCHEMA,"state":"BLOCKED_MODEL","called":False,
            "reason":"Modelo da rota não foi configurado.",
        }

    body={
        "model":model,
        "input":clean_prompt,
        "max_output_tokens":cfg.max_output_tokens,
    }
    headers={
        "Authorization":f"Bearer {cfg.api_key}",
        "Content-Type":"application/json",
    }
    client=session or requests
    try:
        response=client.post(
            OPENAI_RESPONSES_URL,
            headers=headers,
            json=body,
            timeout=cfg.timeout_seconds,
        )
    except Exception as exc:
        return {
            "schema":SCHEMA,"state":"PROVIDER_NETWORK_ERROR","called":True,
            "reason":type(exc).__name__,"model":model,
            "estimate":estimate,
        }

    if int(getattr(response,"status_code",0) or 0)>=400:
        return {
            "schema":SCHEMA,"state":"PROVIDER_HTTP_ERROR","called":True,
            "http_status":int(getattr(response,"status_code",0) or 0),
            "reason":"Provider returned non-success HTTP status.",
            "model":model,"estimate":estimate,
        }
    try:
        payload=response.json()
    except Exception:
        return {
            "schema":SCHEMA,"state":"PROVIDER_INVALID_JSON","called":True,
            "reason":"Provider response was not valid JSON.","model":model,
            "estimate":estimate,
        }
    if not isinstance(payload,Mapping):
        return {
            "schema":SCHEMA,"state":"PROVIDER_INVALID_PAYLOAD","called":True,
            "reason":"Provider response was not an object.","model":model,
            "estimate":estimate,
        }
    answer=_extract_text(payload)
    if not answer:
        return {
            "schema":SCHEMA,"state":"PROVIDER_EMPTY_OUTPUT","called":True,
            "reason":"Provider returned no output text.","model":model,
            "estimate":estimate,
            "usage":_usage_cost(payload,cfg),
        }

    return {
        "schema":SCHEMA,
        "state":"ANSWER_READY",
        "called":True,
        "answer":answer,
        "model":model,
        "response_id":str(payload.get("id") or "")[:160],
        "truth_state":"MODEL_OUTPUT_UNVERIFIED",
        "estimate":estimate,
        "usage":_usage_cost(payload,cfg),
        "executes_action":False,
        "real_orders_enabled":False,
    }


__all__=[
    "SCHEMA","ProviderConfig","provider_config","provider_configuration_status",
    "estimate_request_cost","build_provider_prompt","execute_openai_answer",
]
