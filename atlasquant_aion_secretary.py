"""AION secretary briefing and inbox synthesis.

Pure/offline. It summarizes only the context supplied by callers and labels
uncertain sections instead of filling gaps with guesses.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_operations import queue_summary
from atlasquant_aion_observability import observability_summary

SCHEMA="ATLASQUANT_AION_SECRETARY_V1"


def _confirmed_payload(raw:Mapping[str,Any]|None)->tuple[bool,dict[str,Any]]:
    data=dict(raw or {})
    state=str(data.get("truth_state") or "").strip().upper()
    return state=="CONFIRMED",data


def executive_briefing(
    *,
    tasks:Sequence[Mapping[str,Any]]|None=None,
    events:Sequence[Mapping[str,Any]]|None=None,
    system_context:Mapping[str,Any]|None=None,
    market_context:Mapping[str,Any]|None=None,
    clients_context:Mapping[str,Any]|None=None,
    content_context:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    task_summary=queue_summary(tasks)
    event_summary=observability_summary(events)
    system=dict(system_context or {})

    market_ok, market = _confirmed_payload(market_context)
    clients_ok, clients = _confirmed_payload(clients_context)
    content_ok, content = _confirmed_payload(content_context)

    system_state=str(system.get("truth_state") or "UNKNOWN").upper()
    system_confirmed=system_state=="CONFIRMED"

    return {
        "schema":SCHEMA,
        "system":{
            "truth_state":"CONFIRMED" if system_confirmed else "UNKNOWN",
            "build":system.get("source_build") if system_confirmed else None,
            "environment":system.get("environment") if system_confirmed else None,
            "message":(
                "Estado de sistema confirmado pela fonte fornecida."
                if system_confirmed else
                "Estado completo do sistema não foi confirmado nesta execução."
            ),
        },
        "tasks":{
            "truth_state":"CONFIRMED",
            "active":task_summary["active"],
            "waiting_approval":task_summary["waiting_approval"],
            "blocked":task_summary["blocked"],
            "next_actions":task_summary["next_actions"],
        },
        "market":{
            "truth_state":"CONFIRMED" if market_ok else "UNKNOWN",
            "summary":str(market.get("summary") or "") if market_ok else "",
            "message":(
                "Leitura de mercado recebida com confirmação explícita."
                if market_ok else
                "Sem leitura fresca de mercado confirmada para o briefing."
            ),
        },
        "clients":{
            "truth_state":"CONFIRMED" if clients_ok else "UNKNOWN",
            "new_clients":int(clients.get("new_clients") or 0) if clients_ok else None,
            "message":(
                "Clientes reportados por fonte confirmada."
                if clients_ok else
                "Sem fonte conectada/confirmada de novos clientes."
            ),
        },
        "content":{
            "truth_state":"CONFIRMED" if content_ok else "UNKNOWN",
            "waiting_approval":int(content.get("waiting_approval") or 0) if content_ok else None,
            "message":(
                "Fila de conteúdo recebida por fonte confirmada."
                if content_ok else
                "Fila externa de conteúdo não confirmada nesta execução."
            ),
        },
        "observability":{
            "truth_state":"CONFIRMED",
            "warnings":event_summary["by_severity"]["WARNING"],
            "errors":event_summary["by_severity"]["ERROR"],
            "critical":event_summary["by_severity"]["CRITICAL"],
            "important_recent":event_summary["important_recent"],
        },
        "real_orders_enabled":False,
    }
