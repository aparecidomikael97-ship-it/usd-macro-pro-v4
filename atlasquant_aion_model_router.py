"""AION intelligence router and budget policy.

Provider-neutral planning only. This module never calls an AI API and never
creates billing. It decides whether an external lane would be eligible under
privacy, feature-flag and administrator budget constraints.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
import re
import unicodedata

SCHEMA="ATLASQUANT_AION_MODEL_ROUTER_V1"
LANES=("LOCAL_DETERMINISTIC","EXTERNAL_FAST","EXTERNAL_REASONING")
COMPLEXITIES=("LOW","NORMAL","HIGH")

_SENSITIVE_PATTERNS=(
    re.compile(r"(?i)\b(password|senha|token|secret|segredo|credential|credencial|api[_ -]?key)\b"),
    re.compile(r"(?i)\b(cpf|cnpj|cart[aã]o|credit card|bank account|conta banc[aá]ria)\b"),
)


def _norm(value:Any)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def classify_complexity(task:Any)->str:
    text=_norm(task)
    high_terms=(
        "arquitetura","refator","debug","falha","incidente","seguranca","migration",
        "migracao","benchmark","pesquisa profunda","deep research","multi etapa",
        "reconciliar","analise complexa","estrategia",
    )
    low_terms=("resuma","resumo","listar","lista","status","onde paramos","mostrar","explique simples")
    if any(term in text for term in high_terms) or len(text)>700:
        return "HIGH"
    if any(term in text for term in low_terms) and len(text)<280:
        return "LOW"
    return "NORMAL"


def privacy_sensitive(task:Any)->bool:
    text=str(task or "")
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def normalize_budget(raw:Mapping[str,Any]|None)->dict[str,Any]:
    data=dict(raw or {})
    def _num(key:str)->float:
        try:
            return max(0.0,float(data.get(key,0) or 0))
        except Exception:
            return 0.0
    limit=_num("monthly_limit_usd")
    spent=min(_num("spent_usd"),limit) if limit>0 else 0.0
    return {
        "schema":SCHEMA,
        "allow_paid":bool(data.get("allow_paid",False)),
        "monthly_limit_usd":round(limit,4),
        "spent_usd":round(spent,4),
        "remaining_usd":round(max(0.0,limit-spent),4),
        "approved_by":str(data.get("approved_by") or "")[:80],
        "approved_at":str(data.get("approved_at") or "")[:80],
    }


def budget_decision(
    raw_budget:Mapping[str,Any]|None,
    estimated_request_cost_usd:Any,
    *,
    request_approved:bool=False,
)->dict[str,Any]:
    budget=normalize_budget(raw_budget)
    try:
        cost=max(0.0,float(estimated_request_cost_usd or 0))
    except Exception:
        cost=0.0
    if cost<=0:
        allowed=True
        reason="Solicitação sem custo estimado positivo."
    elif not budget["allow_paid"]:
        allowed=False
        reason="Uso pago não foi habilitado pelo administrador."
    elif not request_approved:
        allowed=False
        reason="Solicitação paga exige aprovação explícita."
    elif budget["monthly_limit_usd"]<=0:
        allowed=False
        reason="Teto mensal pago é zero."
    elif cost>budget["remaining_usd"]:
        allowed=False
        reason="Custo estimado excede o saldo mensal aprovado."
    else:
        allowed=True
        reason="Custo está dentro do teto e foi explicitamente aprovado."
    return {
        "schema":SCHEMA,
        "allowed":allowed,
        "estimated_request_cost_usd":round(cost,4),
        "budget":budget,
        "reason":reason,
        "executes_billing":False,
    }


def route_intelligence(
    task:Any,
    *,
    provider_state:Any="ZERO_COST_LOCAL",
    external_feature_enabled:bool=False,
    budget:Mapping[str,Any]|None=None,
    estimated_request_cost_usd:Any=0.0,
    request_approved:bool=False,
    force_private:bool=False,
)->dict[str,Any]:
    """Choose an eligible lane without making any provider call."""
    complexity=classify_complexity(task)
    sensitive=bool(force_private or privacy_sensitive(task))
    state=str(provider_state or "ZERO_COST_LOCAL").strip().upper()
    cost=budget_decision(
        budget,
        estimated_request_cost_usd,
        request_approved=request_approved,
    )

    if sensitive:
        lane="LOCAL_DETERMINISTIC"
        reason="Conteúdo sensível permanece na rota local nesta fundação."
    elif not external_feature_enabled:
        lane="LOCAL_DETERMINISTIC"
        reason="Feature flag de modelo externo está desligada."
    elif state!="EXTERNAL_READY":
        lane="LOCAL_DETERMINISTIC"
        reason="Cliente externo não está confirmado como pronto."
    elif not cost["allowed"]:
        lane="LOCAL_DETERMINISTIC"
        reason=cost["reason"]
    elif complexity=="HIGH":
        lane="EXTERNAL_REASONING"
        reason="Tarefa complexa elegível para rota de raciocínio externo."
    else:
        lane="EXTERNAL_FAST"
        reason="Tarefa elegível para rota externa rápida."

    return {
        "schema":SCHEMA,
        "lane":lane,
        "complexity":complexity,
        "privacy_sensitive":sensitive,
        "provider_state":state,
        "external_feature_enabled":bool(external_feature_enabled),
        "budget_decision":cost,
        "reason":reason,
        "executes_provider_call":False,
        "executes_billing":False,
    }


def set_budget_policy(
    checkpoint:Mapping[str,Any],
    *,
    monthly_limit_usd:Any,
    allow_paid:bool,
    approved_by:Any,
    approved_at:Any,
)->dict[str,Any]:
    """Return a checkpoint copy with an explicitly-administered budget policy."""
    payload=deepcopy(dict(checkpoint or {}))
    aion=payload.get("aion")
    if not isinstance(aion,dict):
        aion={}
        payload["aion"]=aion
    policy=normalize_budget({
        "monthly_limit_usd":monthly_limit_usd,
        "spent_usd":(aion.get("model_budget") or {}).get("spent_usd",0)
            if isinstance(aion.get("model_budget"),Mapping) else 0,
        "allow_paid":bool(allow_paid),
        "approved_by":str(approved_by or ""),
        "approved_at":str(approved_at or ""),
    })
    aion["model_budget"]=policy
    return payload
