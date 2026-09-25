"""AION executive pulse for the administrator interface.

Pure/offline presentation logic. It ranks already-known admin attention signals
without executing anything and without turning absence of evidence into health.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

SCHEMA="ATLASQUANT_AION_EXECUTIVE_PULSE_V1"

AREA_LABELS={
    "central":"🧠 Central",
    "secretary":"🗂️ Secretaria",
    "trading":"📈 Trading",
    "studio":"🎬 Studio",
    "business":"💼 Negócios",
    "laboratory":"🧪 Laboratório",
    "development":"🛠️ Desenvolvimento",
    "subscriptions":"🔐 Assinaturas",
    "promotions":"🎟️ Promoções",
    "memory":"🛠️ Desenvolvimento",
    "system":"🛠️ Desenvolvimento",
}

PRIORITY_RANK={"P0":0,"P1":1,"P2":2,"P3":3}


def _area(value:Any)->str:
    raw=str(value or "central").strip().casefold()
    return AREA_LABELS.get(raw,str(value or "🧠 Central"))


def _attention(
    priority:str,
    area:Any,
    title:Any,
    detail:Any,
    next_action:Any,
    source:Any,
)->dict[str,str]:
    p=str(priority or "P3").upper()
    if p not in PRIORITY_RANK:
        p="P3"
    return {
        "priority":p,
        "area":_area(area),
        "title":str(title or "")[:180],
        "detail":str(detail or "")[:500],
        "next_action":str(next_action or "")[:500],
        "source":str(source or "")[:180],
    }


def executive_pulse(
    *,
    runtime_result:Mapping[str,Any]|None=None,
    approval_inbox:Mapping[str,Any]|None=None,
    incident_snapshot:Mapping[str,Any]|None=None,
    status_board:Mapping[str,Any]|None=None,
    continuity_summary:Mapping[str,Any]|None=None,
    interface_validation:Mapping[str,Any]|None=None,
    publication_truth:Mapping[str,Any]|None=None,
    release_gate_snapshot:Mapping[str,Any]|None=None,
    reliability_snapshot:Mapping[str,Any]|None=None,
    live_event_snapshot:Mapping[str,Any]|None=None,
    checkpoint_dirty:bool=False,
    checkpoint_conflict:bool=False,
    foundation_diagnostics:Sequence[Mapping[str,Any]]|None=None,
)->dict[str,Any]:
    runtime=dict(runtime_result or {})
    inbox=dict(approval_inbox or {})
    incidents=dict(incident_snapshot or {})
    board=dict(status_board or {})
    continuity=dict(continuity_summary or {})
    validation=dict(interface_validation or {})
    publication=dict(publication_truth or {})
    release_gate=dict(release_gate_snapshot or {})
    reliability=dict(reliability_snapshot or {})
    live_events=dict(live_event_snapshot or {})
    diagnostics=[dict(x) for x in list(foundation_diagnostics or []) if isinstance(x,Mapping)]

    candidates=[]

    if checkpoint_conflict:
        candidates.append(_attention(
            "P0","development",
            "Conflito do Checkpoint Mestre",
            "O runtime mudou enquanto existem alterações locais pendentes.",
            "Resolver o conflito antes de qualquer tentativa de persistência.",
            "AION working checkpoint",
        ))

    integrity=runtime.get("integrity") if isinstance(runtime.get("integrity"),Mapping) else {}
    integrity_state=str(integrity.get("state") or "UNKNOWN").upper()
    if integrity_state=="MISMATCH":
        candidates.append(_attention(
            "P0","development",
            "Integridade do Checkpoint divergente",
            "Um ou mais digests persistidos não conferem.",
            "Revisar a divergência; não sobrescrever o runtime.",
            "runtime_result.integrity",
        ))

    incident_rows=[
        dict(x) for x in list(incidents.get("incidents",[]) or [])
        if isinstance(x,Mapping)
    ]
    critical=next(
        (x for x in incident_rows if str(x.get("severity") or "").upper()=="CRITICAL"),
        None,
    )
    if critical:
        candidates.append(_attention(
            "P0","laboratory",
            critical.get("title") or "Incidente crítico",
            critical.get("detail") or "Há um incidente crítico consolidado.",
            "Abrir o Centro de Segurança e revisar o plano de resposta; nenhuma contenção é automática.",
            critical.get("source") or "incident_center",
        ))

    next_items=[
        dict(x) for x in list(inbox.get("next_items",[]) or [])
        if isinstance(x,Mapping)
    ]
    if str(inbox.get("status") or "CONFIRMED").upper()!="UNKNOWN" and next_items:
        top=sorted(
            next_items,
            key=lambda x:PRIORITY_RANK.get(str(x.get("priority") or "P3").upper(),9),
        )[0]
        candidates.append(_attention(
            str(top.get("priority") or "P1"),
            top.get("area"),
            top.get("title") or top.get("item_id") or "Aprovação pendente",
            "Há uma decisão administrativa aguardando revisão.",
            "Revisar a aprovação na área indicada; nenhuma aprovação é automática.",
            "approval_inbox",
        ))

    current=continuity.get("current_mission")
    if isinstance(current,Mapping) and str(current.get("status") or "").upper()=="BLOCKED":
        candidates.append(_attention(
            "P1",
            current.get("domain"),
            current.get("title") or "Missão bloqueada",
            current.get("blocker") or "A missão atual está bloqueada.",
            current.get("next_action") or "Revisar o bloqueio registrado antes de continuar.",
            "checkpoint.continuity",
        ))

    high=next(
        (x for x in incident_rows if str(x.get("severity") or "").upper()=="HIGH"),
        None,
    )
    if high:
        candidates.append(_attention(
            "P1","laboratory",
            high.get("title") or "Incidente alto",
            high.get("detail") or "Há um incidente de alta severidade.",
            "Revisar o Centro de Segurança antes de avançar em mudanças sensíveis.",
            high.get("source") or "incident_center",
        ))

    reliability_posture=str(reliability.get("posture") or "").upper()
    degraded_mode=(
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"),Mapping)
        else {}
    )
    degraded_state=str(degraded_mode.get("state") or "").upper()
    cost_guardian=(
        reliability.get("cost_guardian")
        if isinstance(reliability.get("cost_guardian"),Mapping)
        else {}
    )
    cost_state=str(cost_guardian.get("state") or "").upper()
    if reliability_posture=="CRITICAL" and not critical:
        candidates.append(_attention(
            "P0","laboratory",
            "Reliability Guardian em fail-closed",
            "A camada de governança detectou condição crítica e restringiu capacidades sensíveis.",
            "Abrir Reliability & Governance, preservar evidências e reconciliar a causa antes de avançar.",
            "reliability_governance",
        ))
    elif reliability_posture=="DEGRADED" and not high:
        candidates.append(_attention(
            "P1" if degraded_state=="FAIL_CLOSED" else "P2",
            "laboratory",
            "AION em modo degradado governado",
            f"Estado de confiabilidade: {degraded_state or 'DEGRADED_SAFE'}.",
            "Revisar fontes, memória e gates antes de depender de capacidades degradadas.",
            "reliability_governance",
        ))

    if cost_state in {"WARNING","BLOCKED_LIMIT"}:
        candidates.append(_attention(
            "P2","laboratory",
            "Cost Guardian requer revisão",
            f"Estado de custo/quota: {cost_state}. Fallback pago automático permanece desligado.",
            "Revisar orçamento e quota; preferir rota gratuita/local quando aplicável.",
            "cost_guardian",
        ))

    live_event_state=str(live_events.get("state") or "").upper()
    live_event_alerts=int(live_events.get("alert_count") or 0)
    live_event_urgent=int(live_events.get("urgent_review_count") or 0)
    top_alerts=[
        dict(x) for x in list(live_events.get("top_alerts",[]) or [])
        if isinstance(x,Mapping)
    ]
    if live_event_urgent>0 and live_event_state=="WATCHING":
        top=top_alerts[0] if top_alerts else {}
        candidates.append(_attention(
            "P1","trading",
            "Evento de mercado urgente para revisão",
            (
                f"{live_event_urgent} evento(s) fresco(s) atingiram URGENT_REVIEW. "
                f"Topo: {str(top.get('headline') or 'evento sem título')[:180]}. "
                "Impacto permanece hipótese, não sinal."
            ),
            "Abrir Live Event Intelligence, revisar fontes e confirmar reação de preço/contexto antes de qualquer leitura operacional.",
            "live_event_intelligence",
        ))
    elif live_event_alerts>0 and live_event_state in {"WATCHING","SCHEDULE_ONLY"}:
        candidates.append(_attention(
            "P2","trading",
            "Eventos de mercado em observação",
            f"{live_event_alerts} evento(s) estão em WATCH/HIGH_REVIEW nesta leitura.",
            "Revisar o radar de eventos; nenhuma notificação ou ação de mercado é automática.",
            "live_event_intelligence",
        ))

    release_gate_state=str(release_gate.get("state") or "").upper()
    release_gate_available=bool(release_gate_state)
    if release_gate_available and release_gate_state!="COMPLETE":
        gate_priority="P1" if release_gate_state=="BLOCKED" else "P2"
        gate_title=(
            "Gate de liberação bloqueado"
            if release_gate_state=="BLOCKED"
            else "Gate de liberação pendente"
        )
        candidates.append(_attention(
            gate_priority,
            "development",
            gate_title,
            (
                f"{int(release_gate.get('confirmed_stages') or 0)}/"
                f"{int(release_gate.get('total_stages') or 4)} etapas confirmadas. "
                f"Estado: {release_gate_state}."
            ),
            release_gate.get("next_action")
            or "Revisar a próxima etapa do Gate de liberação AION.",
            "release_gate",
        ))

    publication_state=str(publication.get("state") or "").upper()
    validation_state=str(validation.get("state") or "").upper()

    # Compatibility fallback: older callers may not yet provide the unified
    # Release Gate. When it is present, it is the single administrative source
    # for build/publication readiness and prevents duplicate attention items.
    if not release_gate_available:
        if publication_state=="RUNTIME_BEHIND_OR_DIVERGED":
            candidates.append(_attention(
                "P1","development",
                "Runtime diverge da main esperada",
                "O commit em execução não coincide com a identidade da main informada.",
                publication.get("next_action")
                or "Revisar o deploy antes de afirmar que a versão atual está publicada.",
                "publication_truth",
            ))
        elif publication_state in {
            "UNKNOWN",
            "SOURCE_BUNDLE_IDENTIFIED",
            "RUNTIME_IDENTIFIED_MAIN_UNKNOWN",
            "MAIN_MATCH_PRODUCTION_UNVERIFIED",
        }:
            candidates.append(_attention(
                "P2","development",
                "Publicação ainda não confirmada",
                "Não há evidência suficiente para afirmar que a versão atual da main está validada em produção.",
                publication.get("next_action")
                or "Confirmar identidade do runtime, main e produção antes de declarar o deploy atual.",
                "publication_truth",
            ))

        if validation_state=="ATTENTION":
            candidates.append(_attention(
                "P1","development",
                "Validação da interface com falha confirmada",
                (
                    f"{int(validation.get('confirmed') or 0)}/{int(validation.get('total') or 3)} "
                    "telas críticas confirmadas no build atual; existe falha observada."
                ),
                validation.get("next_action")
                or "Usar a revalidação guiada do AION na próxima tela crítica pendente.",
                "interface_validation",
            ))
        elif validation_state in {"NOT_STARTED","IN_PROGRESS","UNKNOWN"}:
            progress=f"{int(validation.get('confirmed') or 0)}/{int(validation.get('total') or 3)}"
            candidates.append(_attention(
                "P2","development",
                "Validação do build incompleta",
                (
                    f"Progresso das telas críticas: {progress}. "
                    "Tela ainda não observada não é tratada como falha."
                ),
                validation.get("next_action")
                or "Validar as telas críticas no build atual pelo fluxo guiado do AION.",
                "interface_validation",
            ))

    if checkpoint_dirty:
        candidates.append(_attention(
            "P2","development",
            "Checkpoint com alterações locais",
            "Existem mudanças locais ainda não confirmadas como persistidas.",
            "Salvar somente pelo fluxo condicional já protegido pelo Guardian.",
            "AION working checkpoint",
        ))

    runtime_status=str(runtime.get("status") or "UNKNOWN").upper()
    if runtime_status!="CONFIRMED":
        candidates.append(_attention(
            "P2","development",
            "Runtime do Checkpoint não confirmado",
            f"Estado atual informado: {runtime_status}.",
            "Confirmar runtime/credenciais antes de confiar na persistência.",
            "runtime_result.status",
        ))

    if diagnostics:
        names=", ".join(
            str(x.get("component") or "componente") for x in diagnostics[:6]
        )
        candidates.append(_attention(
            "P2","development",
            "AION em modo degradado seguro",
            f"Camadas auxiliares com fallback: {names}.",
            "Revisar os diagnósticos sem ampliar permissões.",
            "foundation_diagnostics",
        ))

    if not candidates:
        unresolved=bool(board.get("has_unresolved"))
        if unresolved:
            candidates.append(_attention(
                "P3","central",
                "Sem urgência administrativa imediata",
                "Há estados não confirmados ou dependências externas, mas nenhum sinal crítico foi priorizado.",
                "Continuar pela Próxima Ação AION e validar somente o que tiver evidência disponível.",
                "master_status_board",
            ))
        else:
            candidates.append(_attention(
                "P3","central",
                "Nenhuma urgência administrativa detectada",
                "Os sinais internos fornecidos a esta execução não apontam prioridade crítica.",
                "Continuar pela missão registrada; isso não substitui validação externa de produção.",
                "executive_pulse",
            ))

    # Python sort is stable: for equal priority, preserve the safety-rule
    # insertion order above (conflict/integrity/critical before lower-level cues).
    candidates.sort(key=lambda x:PRIORITY_RANK.get(x["priority"],9))
    primary=candidates[0]

    if primary["priority"]=="P0":
        posture="CRITICAL"
    elif primary["priority"]=="P1":
        posture="ATTENTION"
    elif primary["priority"]=="P2":
        posture="REVIEW"
    else:
        posture="CONTROLLED" if runtime_status=="CONFIRMED" else "UNKNOWN"

    return {
        "schema":SCHEMA,
        "posture":posture,
        "primary":primary,
        "attention_items":candidates[:8],
        "attention_count":len(candidates),
        "runtime_status":runtime_status,
        "integrity_state":integrity_state,
        "approval_count":int(inbox.get("total") or 0),
        "incident_count":int(incidents.get("total") or 0),
        "critical_incidents":int(
            ((incidents.get("counts") or {}) if isinstance(incidents.get("counts"),Mapping) else {}).get("CRITICAL")
            or 0
        ),
        "active_missions":int(continuity.get("active_missions") or 0),
        "blocked_missions":int(continuity.get("blocked_missions") or 0),
        "checkpoint_dirty":bool(checkpoint_dirty),
        "checkpoint_conflict":bool(checkpoint_conflict),
        "degraded_components":len(diagnostics),
        "interface_validation_state":validation_state or "NONE",
        "interface_validation_confirmed":int(validation.get("confirmed") or 0),
        "interface_validation_total":int(validation.get("total") or 0),
        "interface_validation_remaining":int(validation.get("remaining") or 0),
        "interface_validation_complete":bool(validation.get("all_confirmed_current_build",False)),
        "publication_state":publication_state or "NONE",
        "publication_main_match":str(publication.get("main_match") or "UNKNOWN"),
        "production_verification":str(publication.get("production_verification") or "UNKNOWN"),
        "can_claim_latest_main_live":bool(publication.get("can_claim_latest_main_live",False)),
        "release_gate_state":release_gate_state or "NONE",
        "release_gate_confirmed_stages":int(release_gate.get("confirmed_stages") or 0),
        "release_gate_total_stages":int(release_gate.get("total_stages") or 0),
        "release_gate_next_stage":str(release_gate.get("next_stage") or ""),
        "release_gate_claim_allowed":bool(release_gate.get("release_claim_allowed",False)),
        "reliability_posture":reliability_posture or "NONE",
        "degraded_mode_state":degraded_state or "NONE",
        "cost_guardian_state":cost_state or "NONE",
        "live_event_state":live_event_state or "NONE",
        "live_event_alert_count":live_event_alerts,
        "live_event_urgent_review":live_event_urgent,
        "recommended_workspace":primary["area"],
        "executes_action":False,
        "real_orders_enabled":False,
    }


def compact_attention_rows(snapshot:Mapping[str,Any]|None)->list[dict[str,str]]:
    rows=[]
    for item in list((snapshot or {}).get("attention_items",[]) or [])[:8]:
        if not isinstance(item,Mapping):
            continue
        rows.append({
            "Prioridade":str(item.get("priority") or ""),
            "Área":str(item.get("area") or ""),
            "Item":str(item.get("title") or ""),
            "Próxima ação":str(item.get("next_action") or ""),
        })
    return rows


__all__=["SCHEMA","AREA_LABELS","executive_pulse","compact_attention_rows"]
