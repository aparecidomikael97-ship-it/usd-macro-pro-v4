"""AION model gateway contract.

Version 1 intentionally keeps external model execution disabled by default.
It provides deterministic routing and a truthful zero-cost local fallback so the
UI can work before any paid AI API is approved.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import os

from atlasquant_aion_core import feature_flag_snapshot, route_context
from atlasquant_aion_continuity import continuity_briefing
from atlasquant_aion_provider import provider_configuration_status
from atlasquant_aion_intelligence import evidence_audit, evidence_confidence
from atlasquant_aion_cognitive_orchestrator import orchestrator_snapshot

SCHEMA = "ATLASQUANT_AION_GATEWAY_V1"


def provider_status(
    *,
    feature_flags: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    flags = feature_flag_snapshot(feature_flags)
    config = provider_configuration_status(env)
    external_requested = str(config.get("provider") or "").casefold() not in {
        "", "offline", "local", "zero-cost"
    }
    feature_enabled = bool(flags.get("external_llm", False))

    if not external_requested:
        state = "ZERO_COST_LOCAL"
        route_enabled = False
    elif not feature_enabled:
        state = "BLOCKED_BY_FEATURE_FLAG"
        route_enabled = False
    elif bool(config.get("ready")):
        state = "EXTERNAL_READY"
        route_enabled = True
    else:
        state = str(config.get("state") or "CONFIG_INCOMPLETE")
        route_enabled = False

    return {
        "schema": SCHEMA,
        "provider": config.get("provider") or "offline",
        "state": state,
        "external_enabled": route_enabled,
        "feature_enabled": feature_enabled,
        "provider_configuration": config,
        "cost_mode": "ZERO_COST_DEFAULT",
        "automatic_billing": False,
    }


def route_model(
    task: object,
    *,
    complexity: str = "normal",
    feature_flags: Mapping[str, Any] | None = None,
    env: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    status = provider_status(feature_flags=feature_flags, env=env)
    context = route_context(task)
    complexity_norm = str(complexity or "normal").strip().lower()
    lane = "external_provider" if status["external_enabled"] else "local_deterministic"
    return {
        "schema": SCHEMA,
        "lane": lane,
        "domain": context["domain"],
        "complexity": complexity_norm,
        "provider": status["provider"],
        "provider_state": status["state"],
        "executes_action": False,
    }


def _checkpoint_line(checkpoint: Mapping[str, Any] | None) -> str:
    cp = dict(checkpoint or {})
    aion = cp.get("aion") if isinstance(cp.get("aion"), Mapping) else {}
    priority = str((aion or {}).get("priority") or "não registrada")
    pending = cp.get("pending")
    count = len(pending) if isinstance(pending, list) else 0
    return f"Prioridade registrada: {priority}. Pendências registradas: {count}."


def local_answer(
    question: object,
    *,
    checkpoint: Mapping[str, Any] | None = None,
    memory_hits: Sequence[Mapping[str, Any]] | None = None,
    system_context: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Truthful local response when no external LLM has been approved.

    It never pretends to be a general-purpose model. Evidence is returned
    separately so the UI can show provenance.
    """
    q = str(question or "").strip()
    route = route_context(q)
    hits = [dict(x) for x in list(memory_hits or [])[:5] if isinstance(x, Mapping)]
    system = dict(system_context or {})
    provider = provider_status(feature_flags=feature_flags)
    cp = dict(checkpoint or {})
    continuity = cp.get("continuity") if isinstance(cp.get("continuity"), Mapping) else {}
    operating = cp.get("operating") if isinstance(cp.get("operating"), Mapping) else {}
    continuity_view = continuity_briefing(
        list(continuity.get("missions", []) or []),
        list(continuity.get("handoffs", []) or []),
        tasks=list(operating.get("tasks", []) or []),
        events=list(operating.get("events", []) or []),
    )
    q_fold = q.casefold()
    asks_continuity = any(term in q_fold for term in (
        "onde paramos",
        "onde parou",
        "retomar",
        "continuidade",
        "próximo bloco",
        "proximo bloco",
        "o que ficou pendente",
        "o que falta",
    ))

    if not q:
        answer = "Escreva uma pergunta ou missão para o AION."
    elif asks_continuity:
        focus = str(continuity_view.get("current_focus") or "").strip()
        next_steps = list(continuity_view.get("next_steps") or [])
        blockers = list(continuity_view.get("blockers") or [])
        completed = list(continuity_view.get("recent_completed") or [])
        source = str(continuity_view.get("source") or "UNKNOWN")
        parts = []
        if focus:
            parts.append(f"No Checkpoint carregado, o foco atual é: {focus}.")
        else:
            parts.append("O Checkpoint carregado não tem uma missão ativa registrada.")
        if next_steps:
            parts.append("Próximo passo registrado: " + str(next_steps[0]) + ".")
        if blockers:
            parts.append("Há bloqueio registrado: " + str(blockers[0]) + ".")
        if completed:
            parts.append("Conclusão recente: " + str(completed[0]) + ".")
        parts.append(
            "Fonte de continuidade: último handoff persistido."
            if source == "PERSISTED_HANDOFF"
            else "Fonte de continuidade: síntese do estado estruturado atual do Checkpoint."
        )
        parts.append("Nenhum próximo passo é executado automaticamente por esta resposta.")
        answer = " ".join(parts)
    elif route["domain"] == "development":
        answer = (
            "Entendi como Desenvolvimento. "
            + _checkpoint_line(checkpoint)
            + " Nesta fundação eu consigo consultar o Checkpoint Mestre e organizar a missão. "
            "Alterações de código, deploy ou merge continuam protegidas pelo Guardian."
        )
    elif route["domain"] == "studio":
        answer = (
            "Entendi como Studio. Posso organizar roteiro, imagem, vídeo, legenda, capa e plano de publicação. "
            "Publicação automática permanece desligada até existir integração aprovada e feature flag liberada."
        )
    elif route["domain"] == "business":
        answer = (
            "Entendi como Negócios. Posso estruturar pesquisa de produto, tendência, margem, fornecedor e meta de receita. "
            "Compra, anúncio ou publicação em marketplace não é executada sem integração e aprovação."
        )
    elif route["domain"] == "promotions":
        answer = (
            "Entendi como Promoções. Posso preparar regras de cupom, dias grátis, desconto e limites de uso. "
            "Ativação real depende do provedor comercial e de aprovação explícita."
        )
    elif route["domain"] == "laboratory":
        answer = (
            "Entendi como Laboratório. A regra é testar em Sandbox, medir, registrar evidência e só promover depois de validação. "
            "Backtest ou forward test não autoriza operação real."
        )
    elif route["domain"] == "secretary":
        answer = (
            "Entendi como Secretaria. Posso consolidar prioridades, pendências, aprovações e checkpoints. "
            "Agenda e clientes só são afirmados quando houver uma fonte realmente conectada."
        )
    elif route["domain"] == "trading":
        market_state = str(system.get("market_status") or "não confirmado nesta tela")
        answer = (
            f"Entendi como Trading. Estado de mercado disponível para esta resposta: {market_state}. "
            "Sem dado fresco confirmado, o AION não inventa direção nem oportunidade."
        )
    else:
        answer = (
            "Estou na Central AION. Posso encaminhar a pergunta para Trading, Studio, Negócios, "
            "Laboratório, Secretaria, Desenvolvimento ou Promoções."
        )

    cognitive = orchestrator_snapshot(
        q,
        domain_hint=route["domain"],
        memory_hits=hits,
        system_context=system,
    )
    reliability = system.get("reliability") if isinstance(system.get("reliability"), Mapping) else {}
    degraded = (
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"), Mapping)
        else {}
    )
    data_guardian = (
        reliability.get("data_guardian")
        if isinstance(reliability.get("data_guardian"), Mapping)
        else {}
    )
    reconciliation = (
        data_guardian.get("reconciliation")
        if isinstance(data_guardian.get("reconciliation"), Mapping)
        else {}
    )
    reliability_posture = str(reliability.get("posture") or "").upper()
    degraded_state = str(degraded.get("state") or "").upper()
    source_conflicts = int(reconciliation.get("conflict_count") or 0)
    live_events = (
        system.get("live_event_intelligence")
        if isinstance(system.get("live_event_intelligence"), Mapping)
        else {}
    )
    live_event_state = str(live_events.get("state") or "").upper()
    live_event_alerts = int(live_events.get("alert_count") or 0)
    live_event_urgent = int(live_events.get("urgent_review_count") or 0)
    if source_conflicts:
        answer += (
            f" Reliability Guardian registra {source_conflicts} conflito(s) de fonte; "
            "não vou escolher uma versão silenciosamente antes da reconciliação."
        )
    if degraded_state == "FAIL_CLOSED":
        answer += (
            " O AION está em FAIL-CLOSED para capacidades sensíveis nesta execução; "
            "posso explicar e organizar evidências, mas não promover o estado dependente como saudável."
        )
    elif degraded_state == "DEGRADED_SAFE":
        answer += (
            " O AION está em modo degradado seguro nesta execução; estados ausentes ou frágeis "
            "continuam não confirmados."
        )

    if live_event_urgent > 0 and live_event_state == "WATCHING":
        top_alerts = [
            x for x in list(live_events.get("top_alerts", []) or [])
            if isinstance(x, Mapping)
        ]
        top = top_alerts[0] if top_alerts else {}
        headline = str(top.get("headline") or "evento sem título")[:220]
        truth = str(top.get("truth_state") or "UNKNOWN")
        answer += (
            f" Live Event Intelligence registra {live_event_urgent} evento(s) urgente(s) para revisão. "
            f"Topo: {headline} [verdade: {truth}]. "
            "O impacto de mercado associado permanece hipótese, não sinal de trade."
        )
    elif live_event_alerts > 0:
        answer += (
            f" Live Event Intelligence mantém {live_event_alerts} evento(s) em observação; "
            "nenhuma notificação externa ou ação de mercado é automática."
        )

    selected_names = [
        str(x.get("name") or "")
        for x in list((cognitive.get("routing") or {}).get("selected", []) or [])
        if isinstance(x, Mapping) and str(x.get("name") or "").strip()
    ]
    research_blockers = list((cognitive.get("research_plan") or {}).get("blockers", []) or [])
    if selected_names:
        answer += " Conselho cognitivo selecionado: " + ", ".join(selected_names[:5]) + "."
    if research_blockers:
        answer += " Antes de uma conclusão forte, falta resolver: " + str(research_blockers[0])
    if hits:
        answer += f" Encontrei {len(hits)} referência(s) na memória canônica para apoiar a resposta."
    if provider["state"] == "ZERO_COST_LOCAL":
        answer += " O modo atual é local e custo zero; um modelo externo mais potente ainda não foi ativado."

    response_evidence = [{
        "claim":"route",
        "kind":"CONFIRMED",
        "source":"aion_local_router",
        "value":route["domain"],
        "note":"Roteamento determinístico local.",
    }]
    system_truth = str(system.get("truth_state") or "UNKNOWN").upper()
    response_evidence.append({
        "claim":"system_context",
        "kind":system_truth if system_truth in {"CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN"} else "UNKNOWN",
        "source":"system_context",
        "value":system.get("source_build") or system.get("market_status") or "UNKNOWN",
        "note":"Contexto fornecido pelo aplicativo; ausência não é promovida.",
    })
    for index, hit in enumerate(hits):
        kind = str(hit.get("kind") or hit.get("truth_state") or "UNKNOWN").upper()
        if kind not in {"CONFIRMED","INFERENCE","HYPOTHESIS","UNKNOWN"}:
            kind = "UNKNOWN"
        response_evidence.append({
            "claim":str(hit.get("title") or hit.get("path") or f"memory_hit_{index+1}"),
            "kind":kind,
            "source":str(hit.get("source") or hit.get("path") or "canonical_memory"),
            "value":str(hit.get("excerpt") or hit.get("content") or "")[:500],
            "note":"Referência recuperada da memória canônica.",
        })
    response_audit = evidence_audit(response_evidence)
    response_confidence = evidence_confidence(response_audit)

    return {
        "schema": SCHEMA,
        "answer": answer,
        "domain": route["domain"],
        "provider": provider,
        "evidence": hits,
        "evidence_audit": response_audit,
        "evidence_confidence": response_confidence,
        "truth_state": "CONFIRMED_LOCAL_CONTRACT",
        "confidence_basis": "EVIDENCE_QUALITY_NOT_PROFIT_PROBABILITY",
        "reliability_posture": reliability_posture or "UNKNOWN",
        "degraded_mode_state": degraded_state or "UNKNOWN",
        "source_conflicts": source_conflicts,
        "cognitive_orchestrator": cognitive,
        "cognitive_readiness": str(cognitive.get("readiness") or "UNKNOWN"),
        "cognitive_specialists": int((cognitive.get("routing") or {}).get("selected_count") or 0),
        "critic_required": bool((cognitive.get("critic_gate") or {}).get("required", True)),
        "live_event_state": live_event_state or "UNKNOWN",
        "live_event_alerts": live_event_alerts,
        "live_event_urgent_review": live_event_urgent,
        "executes_action": False,
        "real_orders_enabled": False,
    }
