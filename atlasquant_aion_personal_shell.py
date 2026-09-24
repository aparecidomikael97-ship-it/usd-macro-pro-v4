"""Safe state model for the future subscriber-facing "Meu AION" shell.

This module does not render UI, call an AI provider, persist memory, publish,
charge, administer accounts or execute trades. It composes existing tenant,
entitlement and persistence contracts into a truth-first shell state that can
be tested before any subscriber UI is exposed.

The shell has three primary states:
- LOCKED_AUTH: no valid USER/SALES authenticated tenant session;
- LOCKED_ENTITLEMENT: valid tenant session, but no effective AION_PERSONAL right;
- READY_LOCAL: tenant identity + confirmed entitlement are valid. Only local,
  low-risk capabilities are represented; external provider and real trading
  remain disabled.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import re
import unicodedata

from atlasquant_aion_tenant import (
    TENANT_DOMAINS,
    personal_aion_eligibility,
    sanitize_tenant_memory,
    tenant_action_decision,
    tenant_memory_seed,
    tenant_namespace,
    tenant_policy_snapshot,
    tenant_prompt_contract,
)
from atlasquant_aion_tenant_store import (
    prepare_tenant_load,
    tenant_memory_source_digest,
    tenant_store_policy,
)

SCHEMA="ATLASQUANT_AION_PERSONAL_SHELL_V1"
SHELL_STATES=("LOCKED_AUTH","LOCKED_ENTITLEMENT","READY_LOCAL")
PERSONAL_ROUTES=("central","trading","academy","support","account")

_ROUTE_TERMS={
    "trading":(
        "trading","mercado","forex","dolar","dólar","euro","par","pares",
        "radar","macro","fed","inflacao","inflação","cpi","pce","nfp","pmi",
        "juros","indice","índice","nasdaq","dow","sp500","s&p","win","wdo",
    ),
    "academy":(
        "academy","aprender","estudar","aula","curso","explica","explicar",
        "indicador","ict","smc","fvg","order block","bos","wyckoff","dow",
    ),
    "support":(
        "suporte","ajuda","erro","problema","travou","funciona","instalar",
        "instalacao","instalação","plataforma","corretora",
    ),
    "account":(
        "conta","perfil","assinatura","acesso","login","senha","plano",
        "entitlement","cadastro",
    ),
}


def _norm(value:Any)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _clean_text(value:Any,limit:int=700)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]


def _market_truth(market_context:Mapping[str,Any]|None)->dict[str,Any]:
    data=dict(market_context or {})
    fresh=bool(data.get("fresh_confirmed",False))
    summary=_clean_text(data.get("summary"),900)
    source=_clean_text(data.get("source"),200)
    checked_at=_clean_text(data.get("checked_at"),80)
    if fresh and summary:
        return {
            "truth_state":"CONFIRMED",
            "summary":summary,
            "source":source,
            "checked_at":checked_at,
            "fresh_confirmed":True,
        }
    return {
        "truth_state":"UNKNOWN",
        "summary":"Sem leitura de mercado fresca e confirmada neste contexto.",
        "source":source,
        "checked_at":checked_at,
        "fresh_confirmed":False,
    }


def personal_route(text:Any)->dict[str,Any]:
    q=_norm(text)
    scores={route:0 for route in PERSONAL_ROUTES}
    for route,terms in _ROUTE_TERMS.items():
        scores[route]=sum(1 for term in terms if _norm(term) in q)
    winner=max(scores,key=scores.get) if scores else "central"
    if not q or scores.get(winner,0)<=0:
        winner="central"
    return {
        "schema":SCHEMA,
        "route":winner,
        "scores":scores,
        "executes_action":False,
        "admin_route_available":False,
    }


def _shell_state(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    now:datetime|None=None,
)->tuple[str,dict[str,Any],dict[str,Any]]:
    ns=tenant_namespace(access)
    eligibility=personal_aion_eligibility(access,entitlements,now=now)
    if not ns["ready"]:
        return "LOCKED_AUTH",ns,eligibility
    if not eligibility["eligible"]:
        return "LOCKED_ENTITLEMENT",ns,eligibility
    return "READY_LOCAL",ns,eligibility


def personal_capability_matrix(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    now:datetime|None=None,
)->list[dict[str,Any]]:
    state,_,_= _shell_state(access,entitlements,now=now)
    ready=state=="READY_LOCAL"
    specs=(
        ("central","Perguntas gerais do Meu AION","support_help"),
        ("trading","Leitura e explicação de mercado","read_market"),
        ("academy","Estudo e explicações educacionais","academy_help"),
        ("support","Ajuda de uso e suporte","support_help"),
        ("account","Leitura da própria conta","read_own_account"),
        ("account","Preferências pessoais","save_own_preferences"),
    )
    rows=[]
    for domain,label,action in specs:
        decision=tenant_action_decision(
            action,
            access,
            entitlements,
            now=now,
        ) if ready else {
            "allowed":False,
            "reason":"PERSONAL_AION_NOT_READY",
            "executes_external_action":False,
        }
        rows.append({
            "domain":domain,
            "label":label,
            "action":action,
            "available":bool(decision.get("allowed",False)),
            "reason":str(decision.get("reason") or ""),
            "external_action":False,
            "real_trading":False,
        })
    return rows


def build_personal_aion_shell(
    access:Mapping[str,Any]|None,
    entitlements:Sequence[Mapping[str,Any]]|None,
    *,
    tenant_memory:Mapping[str,Any]|None=None,
    market_context:Mapping[str,Any]|None=None,
    runtime_branch:Any="atlasquant-runtime",
    now:datetime|None=None,
)->dict[str,Any]:
    state,ns,eligibility=_shell_state(access,entitlements,now=now)
    ready=state=="READY_LOCAL"
    policy=tenant_policy_snapshot()
    store_policy=tenant_store_policy()
    market=_market_truth(market_context)

    if ready:
        expected_tenant_id=str(ns.get("tenant_id") or "")
        provided_memory=isinstance(tenant_memory,Mapping)
        provided_tenant_id=(
            str(tenant_memory.get("tenant_id") or "").strip()
            if provided_memory else ""
        )
        own_memory_provided=bool(
            provided_memory
            and provided_tenant_id
            and provided_tenant_id==expected_tenant_id
        )
        foreign_or_unbound_memory=bool(
            provided_memory and not own_memory_provided
        )
        memory=(
            sanitize_tenant_memory(tenant_memory,access)
            if own_memory_provided
            else tenant_memory_seed(access)
        )
        memory_state={
            "available_in_shell":True,
            "persistence_confirmed":False,
            "source":(
                "provided-own-tenant-memory"
                if own_memory_provided
                else "foreign-or-unbound-rejected-ephemeral-seed"
                if foreign_or_unbound_memory
                else "ephemeral-seed"
            ),
            "input_memory_rejected":foreign_or_unbound_memory,
            "digest":tenant_memory_source_digest(memory,access),
            "profile_present":bool((memory.get("profile") or {}).get("display_name")),
            "notes":len(memory.get("conversation_notes") or []),
            "watchlist":len(memory.get("watchlist") or []),
            "academy_items":len(memory.get("academy_progress") or {}),
            "admin_memory_inherited":False,
            "other_tenant_memory_visible":False,
        }
        load_plan=prepare_tenant_load(
            access,
            entitlements,
            runtime_branch=runtime_branch,
            now=now,
        )
    else:
        memory=None
        memory_state={
            "available_in_shell":False,
            "persistence_confirmed":False,
            "source":"none",
            "input_memory_rejected":False,
            "digest":"",
            "profile_present":False,
            "notes":0,
            "watchlist":0,
            "academy_items":0,
            "admin_memory_inherited":False,
            "other_tenant_memory_visible":False,
        }
        load_plan={
            "allowed":False,
            "reason":eligibility.get("reason") or ns.get("reason") or "NOT_READY",
            "executes_network":False,
            "executes_read":False,
            "admin_memory_fallback":False,
            "other_tenant_fallback":False,
        }

    return {
        "schema":SCHEMA,
        "state":state,
        "ready":ready,
        "reason":"READY_LOCAL_ONLY" if ready else str(
            eligibility.get("reason") or ns.get("reason") or "NOT_READY"
        ),
        "tenant":{
            "tenant_id":str(ns.get("tenant_id") or ""),
            "namespace":str(ns.get("namespace") or ""),
            "username":str(ns.get("username") or ""),
            "role":str(ns.get("role") or ""),
            "credential_bound":bool(ns.get("credential_bound",False)),
        },
        "eligibility":eligibility,
        "memory":memory_state,
        "market":market,
        "capabilities":personal_capability_matrix(
            access,
            entitlements,
            now=now,
        ),
        "persistence":{
            "load_plan_allowed":bool(load_plan.get("allowed",False)),
            "load_plan_reason":str(load_plan.get("reason") or ""),
            "network_io_implemented":bool(store_policy["network_io_implemented"]),
            "automatic_write":bool(store_policy["automatic_write"]),
            "automatic_overwrite":bool(store_policy["automatic_overwrite"]),
            "persistence_confirmed":False,
        },
        "policy":{
            "allowed_domains":list(TENANT_DOMAINS),
            "admin_memory_access":False,
            "project_docs_access":False,
            "other_tenant_access":False,
            "external_provider_enabled":False,
            "external_publish":False,
            "billing":False,
            "admin":False,
            "real_trading":False,
            "requires_confirmed_entitlement":bool(policy["requires_confirmed_entitlement"]),
        },
        "subscriber_ui_exposed":False,
        "executes_provider_call":False,
        "executes_external_action":False,
        "real_orders_enabled":False,
    }


def personal_prompt_packet(
    question:Any,
    shell:Mapping[str,Any]|None,
    *,
    access:Mapping[str,Any]|None=None,
    own_memory:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    state=dict(shell or {})
    if state.get("state")!="READY_LOCAL" or not bool(state.get("ready",False)):
        return {
            "schema":SCHEMA,
            "ready":False,
            "reason":"PERSONAL_AION_NOT_READY",
            "executes_provider_call":False,
        }
    tenant=state.get("tenant") if isinstance(state.get("tenant"),Mapping) else {}
    route=personal_route(question)
    allowed_domains=set(str(x) for x in ((state.get("policy") or {}).get("allowed_domains") or []))
    route_name=str(route.get("route") or "central")
    if route_name not in allowed_domains:
        route_name="central"

    safe_memory={}
    if isinstance(own_memory,Mapping) and isinstance(access,Mapping):
        # Memory contents are accepted only if they already belong to this tenant,
        # then they are normalized again before entering a future prompt packet.
        if str(own_memory.get("tenant_id") or "")==str(tenant.get("tenant_id") or ""):
            sanitized=sanitize_tenant_memory(own_memory,access)
            if str(sanitized.get("tenant_id") or "")==str(tenant.get("tenant_id") or ""):
                safe_memory={
                    "profile":dict(sanitized.get("profile") or {}),
                    "conversation_notes":list(sanitized.get("conversation_notes") or [])[:50],
                    "academy_progress":dict(sanitized.get("academy_progress") or {}),
                    "watchlist":list(sanitized.get("watchlist") or [])[:100],
                }

    contract={
        "truth_rules":[
            "Nunca inventar fatos, estados, integrações ou resultados.",
            "Não chamar dados de mercado de atuais sem confirmação de frescor.",
            "Usar apenas memória deste tenant e contexto explicitamente fornecido.",
            "Nunca revelar memória ADMIN, documentos privados do projeto ou dados de outro tenant.",
            "Nunca executar cobrança, publicação, administração, deploy ou trading real.",
        ],
        "admin_memory_access":False,
        "project_docs_access":False,
        "other_tenant_access":False,
        "external_provider_enabled":False,
        "real_trading_enabled":False,
    }
    return {
        "schema":SCHEMA,
        "ready":True,
        "route":route_name,
        "question":_clean_text(question,2000),
        "tenant_id":str(tenant.get("tenant_id") or ""),
        "market":dict(state.get("market") or {}),
        "own_memory":safe_memory,
        "contract":contract,
        "executes_provider_call":False,
        "executes_external_action":False,
    }


def personal_shell_summary(shell:Mapping[str,Any]|None)->dict[str,Any]:
    state=dict(shell or {})
    caps=[
        row for row in list(state.get("capabilities") or [])
        if isinstance(row,Mapping)
    ]
    return {
        "schema":SCHEMA,
        "state":str(state.get("state") or "LOCKED_AUTH"),
        "ready":bool(state.get("ready",False)),
        "available_capabilities":sum(1 for row in caps if bool(row.get("available",False))),
        "market_truth":str((state.get("market") or {}).get("truth_state") or "UNKNOWN"),
        "memory_available":bool((state.get("memory") or {}).get("available_in_shell",False)),
        "persistence_confirmed":bool((state.get("persistence") or {}).get("persistence_confirmed",False)),
        "subscriber_ui_exposed":bool(state.get("subscriber_ui_exposed",False)),
        "external_provider_enabled":bool((state.get("policy") or {}).get("external_provider_enabled",False)),
        "real_orders_enabled":False,
    }


def personal_shell_policy()->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "states":list(SHELL_STATES),
        "routes":list(PERSONAL_ROUTES),
        "subscriber_ui_exposed":False,
        "provider_calls_implemented":False,
        "external_provider_enabled_by_default":False,
        "admin_memory_access":False,
        "project_docs_access":False,
        "other_tenant_access":False,
        "billing":False,
        "external_publish":False,
        "real_trading":False,
    }


__all__=[
    "SCHEMA","SHELL_STATES","PERSONAL_ROUTES","personal_route",
    "personal_capability_matrix","build_personal_aion_shell",
    "personal_prompt_packet","personal_shell_summary","personal_shell_policy",
]
