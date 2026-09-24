"""AtlasQuant AION — official administrator command center.

Presentation/orchestration layer only. All irreversible or external actions are
guarded and feature-flagged. The initial release works in zero-cost local mode
without pretending that external AI/social/marketplace/payment integrations are
already active.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping
import os

import streamlit as st

from atlasquant_aion_core import (
    AION_VERSION,
    RISKY_EXTERNAL_FEATURES,
    ZERO_COST_RULES,
    TRUTH_RULES,
    feature_flag_snapshot,
    guardian_decision,
    is_admin,
    mission_plan,
    route_context,
)
from atlasquant_aion_gateway import local_answer, provider_status
from atlasquant_aion_memory import (
    canonical_memory_summary,
    checkpoint_digest,
    checkpoint_source_digest,
    config_from_mapping,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    merged_checkpoint,
    save_runtime_checkpoint,
    search_canonical_memory,
    update_operating_checkpoint,
)
from atlasquant_aion_operations import (
    ACTIONS,
    PRIORITIES,
    STATUSES,
    approve_task,
    approval_requirement,
    new_task,
    queue_summary,
    transition_task,
    upsert_task,
)
from atlasquant_aion_observability import (
    append_event,
    new_event,
    observability_summary,
)
from atlasquant_aion_secretary import executive_briefing
from atlasquant_aion_model_router import (
    normalize_budget,
    route_intelligence,
    set_budget_policy,
)

try:
    from atlasquant_neural_voice_ui import render_neural_voice_player
except Exception:
    render_neural_voice_player = None

SCHEMA = "ATLASQUANT_AION_ADMIN_V1"
_WORKING_CHECKPOINT_KEY = "aion_working_checkpoint_v2"
_WORKING_SOURCE_KEY = "aion_working_checkpoint_source_digest"
_WORKING_DIRTY_KEY = "aion_working_checkpoint_dirty"
_WORKING_CONFLICT_KEY = "aion_working_checkpoint_conflict"

AION_ADMIN_CSS = r"""
<style>
.aion-shell{
  position:relative;overflow:hidden;border:1px solid rgba(111,220,255,.28);
  border-radius:24px;padding:24px 26px;margin:4px 0 16px;
  background:
    radial-gradient(circle at 86% 8%,rgba(91,119,255,.22),transparent 30%),
    radial-gradient(circle at 8% 95%,rgba(45,225,198,.12),transparent 34%),
    linear-gradient(135deg,rgba(7,16,32,.98),rgba(10,30,50,.96) 58%,rgba(8,20,39,.98));
  box-shadow:0 24px 70px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.05);
  isolation:isolate;
}
.aion-shell:before{
  content:"";position:absolute;inset:-40%;z-index:-2;opacity:.16;
  background-image:linear-gradient(rgba(89,188,255,.18) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(89,188,255,.18) 1px,transparent 1px);
  background-size:34px 34px;transform:perspective(480px) rotateX(58deg) translateY(34%);
  transform-origin:center bottom;
}
.aion-orb{
  position:absolute;right:34px;top:28px;width:92px;height:92px;border-radius:50%;
  background:radial-gradient(circle at 35% 32%,#dffcff 0 7%,#7fe8ff 13%,#5574ff 38%,rgba(28,32,80,.2) 68%,transparent 72%);
  box-shadow:0 0 22px rgba(94,222,255,.58),0 0 70px rgba(81,99,255,.25);
  animation:aionPulse 4.2s ease-in-out infinite;
}
@keyframes aionPulse{0%,100%{transform:scale(.96);filter:brightness(.94)}50%{transform:scale(1.04);filter:brightness(1.12)}}
.aion-kicker{color:#73f1da;font-size:.72rem;font-weight:900;letter-spacing:.2em;text-transform:uppercase}
.aion-title{color:#fff;font-size:clamp(1.8rem,4vw,3rem);font-weight:950;letter-spacing:-.045em;line-height:1;margin-top:4px}
.aion-sub{color:#d9e8fa;max-width:820px;font-size:.9rem;line-height:1.5;margin-top:8px;padding-right:112px}
.aion-chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}
.aion-chip{border:1px solid rgba(133,196,235,.28);background:rgba(9,24,45,.58);color:#eef8ff;border-radius:999px;padding:5px 10px;font-size:.7rem;font-weight:800}
.aion-chip.ok{color:#73f1da}.aion-chip.warn{color:#ffd56b}.aion-chip.off{color:#c7d2e3}
.aion-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:10px 0 16px}
.aion-card{position:relative;border:1px solid rgba(126,177,218,.22);border-radius:16px;padding:13px 14px;background:linear-gradient(160deg,rgba(18,42,70,.86),rgba(8,23,42,.88));box-shadow:0 10px 30px rgba(0,0,0,.15)}
.aion-card small{display:block;color:#bcd0e8;font-size:.66rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
.aion-card strong{display:block;color:#fff;font-size:.94rem;margin-top:4px;overflow-wrap:anywhere}
.aion-card span{display:block;color:#d3deec;font-size:.72rem;line-height:1.35;margin-top:3px}
.aion-truth{border-left:3px solid #73f1da;border-radius:10px;padding:10px 12px;background:rgba(27,69,73,.28);color:#e9fffb;font-size:.78rem;margin:8px 0 14px}
.aion-panel{border:1px solid rgba(126,177,218,.18);border-radius:16px;padding:14px 15px;background:rgba(9,24,43,.62);margin:8px 0 12px}
.aion-panel h4{color:#fff;margin:.1rem 0 .5rem}.aion-panel p{color:#dce7f5;margin:.2rem 0;font-size:.82rem}
@media (prefers-reduced-motion:reduce){.aion-orb{animation:none!important}}
@media(max-width:760px){
 .aion-shell{padding:18px 16px;border-radius:18px}.aion-orb{width:58px;height:58px;right:16px;top:20px}
 .aion-sub{padding-right:64px;font-size:.8rem}.aion-grid{grid-template-columns:1fr 1fr}.aion-card{padding:11px 12px}
}
</style>
"""


def _secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except Exception:
        value = os.getenv(name, default)
    return str(value or default).strip()


def _runtime_config():
    values = {
        "GITHUB_TOKEN_HISTORICO": _secret("GITHUB_TOKEN_HISTORICO"),
        "GITHUB_REPO_HISTORICO": _secret("GITHUB_REPO_HISTORICO"),
        "GITHUB_DATA_BRANCH": _secret("GITHUB_DATA_BRANCH"),
        "GITHUB_BRANCH_HISTORICO": _secret("GITHUB_BRANCH_HISTORICO"),
    }
    return config_from_mapping(values)


def _display_name(access: Mapping[str, Any]) -> str:
    configured = _secret("AION_ADMIN_DISPLAY_NAME")
    if configured:
        return configured[:64]
    username = str(access.get("username") or "").strip()
    return username[:64] if username else "Administrador"


def _flag_overrides() -> dict[str, bool]:
    out: dict[str, bool] = {}
    for key in RISKY_EXTERNAL_FEATURES:
        raw = _secret(f"AION_FF_{key.upper()}")
        if raw:
            out[key] = raw.casefold() in {"1", "true", "yes", "on", "sim"}
    return out


def _status_chip(runtime_status: str, provider_state: str) -> str:
    runtime_ok = runtime_status == "CONFIRMED"
    provider_local = provider_state == "ZERO_COST_LOCAL"
    return (
        f'<span class="aion-chip {"ok" if runtime_ok else "warn"}">MEMÓRIA {runtime_status}</span>'
        f'<span class="aion-chip {"ok" if provider_local else "warn"}">IA {provider_state}</span>'
        '<span class="aion-chip ok">GUARDIAN ATIVO</span>'
        '<span class="aion-chip ok">CUSTO ZERO PADRÃO</span>'
    )


def _render_header(
    access: Mapping[str, Any],
    runtime_status: str,
    provider_state: str,
    system_context: Mapping[str, Any],
) -> None:
    name = escape(_display_name(access))
    build = escape(str(system_context.get("source_build") or "não confirmado"))
    env = escape(str(system_context.get("environment") or "LOCAL"))
    st.markdown(AION_ADMIN_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="aion-shell">
  <div class="aion-orb" aria-hidden="true"></div>
  <div class="aion-kicker">Administrator Intelligence Operating Network</div>
  <div class="aion-title">AION // COMMAND CENTER</div>
  <div class="aion-sub">
    {name}, esta é a central administrativa do AtlasQuant. O AION organiza contexto,
    memória, desenvolvimento, Studio, Negócios e Laboratório sem ultrapassar o Guardian.
    Build informado pelo app: <strong>{build}</strong> · ambiente <strong>{env}</strong>.
  </div>
  <div class="aion-chips">{_status_chip(runtime_status, provider_state)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="aion-truth"><strong>Regra da Verdade:</strong> '
        'se a fonte não estiver confirmada, o AION declara que não sabe ou que precisa verificar. '
        'Nenhum estado externo é inventado.</div>',
        unsafe_allow_html=True,
    )


def _working_checkpoint(source: Mapping[str, Any]) -> dict[str, Any]:
    seed = ensure_operating_checkpoint(source)
    source_digest = checkpoint_source_digest(seed)
    current = st.session_state.get(_WORKING_CHECKPOINT_KEY)
    dirty = bool(st.session_state.get(_WORKING_DIRTY_KEY, False))
    known_source = str(st.session_state.get(_WORKING_SOURCE_KEY) or "")
    if not isinstance(current, Mapping) or (known_source != source_digest and not dirty):
        st.session_state[_WORKING_CHECKPOINT_KEY] = deepcopy(seed)
        st.session_state[_WORKING_SOURCE_KEY] = source_digest
        st.session_state[_WORKING_DIRTY_KEY] = False
        st.session_state[_WORKING_CONFLICT_KEY] = False
    else:
        st.session_state[_WORKING_CONFLICT_KEY] = bool(
            dirty and known_source and known_source != source_digest
        )
    return ensure_operating_checkpoint(st.session_state[_WORKING_CHECKPOINT_KEY])


def _set_working_checkpoint(checkpoint: Mapping[str, Any], *, dirty: bool = True) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    payload["operating"]["dirty"] = bool(dirty)
    st.session_state[_WORKING_CHECKPOINT_KEY] = payload
    st.session_state[_WORKING_DIRTY_KEY] = bool(dirty)
    return payload


def _record_working_event(
    checkpoint: Mapping[str, Any],
    event_type: str,
    message: str,
    *,
    severity: str = "INFO",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    operating = payload["operating"]
    events = append_event(
        operating.get("events", []),
        new_event(
            event_type,
            message,
            severity=severity,
            source="AION_ADMIN",
            truth_state="CONFIRMED",
            evidence=evidence or {},
        ),
    )
    return update_operating_checkpoint(payload, events=events, dirty=True)


def _safe_market_state(market_context: Mapping[str, Any]) -> tuple[str, str]:
    fresh = bool(market_context.get("fresh_confirmed", False))
    summary = str(market_context.get("summary") or "").strip()
    if fresh and summary:
        return summary, "CONFIRMADO"
    return "Sem leitura fresca confirmada nesta tela.", "NÃO CONFIRMADO"


def _render_executive_grid(
    memory_summary: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    provider: Mapping[str, Any],
    market_context: Mapping[str, Any],
) -> None:
    market_text, market_truth = _safe_market_state(market_context)
    docs = int(memory_summary.get("document_count") or 0)
    runtime_status = str(runtime_result.get("status") or "UNKNOWN")
    st.markdown(
        f"""
<div class="aion-grid">
 <div class="aion-card"><small>Memória canônica</small><strong>{docs} fontes</strong><span>Documentos versionados do projeto + fundação AION.</span></div>
 <div class="aion-card"><small>Checkpoint runtime</small><strong>{runtime_status}</strong><span>Persistência mutável só é afirmada quando confirmada.</span></div>
 <div class="aion-card"><small>Modelo</small><strong>{provider.get("state","UNKNOWN")}</strong><span>Sem cobrança automática; modelo externo desligado por padrão.</span></div>
 <div class="aion-card"><small>Mercado</small><strong>{market_truth}</strong><span>{market_text}</span></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _render_central(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    memory_summary: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
) -> None:
    st.markdown("### 🧠 Central AION")
    pending = checkpoint.get("pending") if isinstance(checkpoint.get("pending"), list) else []
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = operating.get("tasks", []) if isinstance(operating, Mapping) else []
    summary = queue_summary(tasks)
    cols = st.columns(4)
    cols[0].metric("Versão AION", AION_VERSION)
    cols[1].metric("Tarefas ativas", summary["active"])
    cols[2].metric("Aguardando aprovação", summary["waiting_approval"])
    cols[3].metric("Ordens reais", "BLOQUEADAS")

    st.markdown("#### Briefing de entrada")
    st.write(
        f"Prioridade registrada: **{(checkpoint.get('aion') or {}).get('priority','não confirmada')}**. "
        f"Checkpoint: **{checkpoint_digest(checkpoint)}**. "
        f"Runtime: **{runtime_result.get('status','UNKNOWN')}**."
    )
    if pending:
        st.markdown("**Próximas pendências registradas:**")
        for item in pending[:8]:
            st.markdown(f"- {item}")

    st.markdown("#### Pergunte ao AION")
    question = st.text_input(
        "Pergunta ou missão",
        key="aion_admin_question",
        placeholder="Ex.: AION, onde paramos no sistema? / como está o Studio? / o que falta validar?",
    )
    if st.button("Analisar com AION", key="aion_admin_ask", type="primary", width="stretch"):
        hits = search_canonical_memory(question)
        provider = provider_status(feature_flags=flags)
        budget = normalize_budget((checkpoint.get("aion") or {}).get("model_budget", {}))
        route = route_intelligence(
            question,
            provider_state=provider.get("state"),
            external_feature_enabled=bool(flags.get("external_llm", False)),
            budget=budget,
            estimated_request_cost_usd=0.0,
            request_approved=False,
        )
        answer = local_answer(
            question,
            checkpoint=checkpoint,
            memory_hits=hits,
            system_context=dict(system_context),
            feature_flags=flags,
        )
        st.session_state["aion_last_route"] = route
        st.session_state["aion_last_answer"] = answer

    route = st.session_state.get("aion_last_route")
    if isinstance(route, Mapping):
        st.caption(
            f"Roteamento: {route.get('lane')} · complexidade {route.get('complexity')} · "
            f"{route.get('reason')}"
        )

    answer = st.session_state.get("aion_last_answer")
    if isinstance(answer, Mapping):
        st.markdown("#### Resposta AION")
        st.write(str(answer.get("answer", "")))
        evidence = answer.get("evidence")
        if isinstance(evidence, list) and evidence:
            with st.expander("Evidências da memória"):
                for hit in evidence:
                    st.caption(f"{hit.get('path')} · score {hit.get('score')}")
                    st.write(hit.get("excerpt"))

    if render_neural_voice_player is not None:
        spoken = (
            f"Bem-vindo à Central AION. A prioridade atual é "
            f"{(checkpoint.get('aion') or {}).get('priority','revisar o checkpoint')}. "
            "AION está em modo custo zero e ordens reais continuam bloqueadas."
        )
        render_neural_voice_player(
            spoken,
            key="aion_admin_welcome_voice",
            button_label="🔊 Ouvir briefing do AION",
        )

    st.markdown("#### Secretaria executiva")
    st.caption(
        "AION consolida tarefas, pendências e aprovações. Agenda, e-mail e clientes externos "
        "só entram como confirmados quando a fonte correspondente estiver conectada."
    )
    if bool(st.session_state.get(_WORKING_DIRTY_KEY, False)):
        st.warning("Há alterações locais no Checkpoint Mestre aguardando salvamento no runtime.")


def _render_secretary(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    market_context: Mapping[str, Any],
) -> None:
    st.markdown("### 🗂️ Secretaria AION")
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = list(operating.get("tasks", []) or [])
    events = list(operating.get("events", []) or [])
    summary = queue_summary(tasks)
    obs = observability_summary(events)
    brief = executive_briefing(
        tasks=tasks,
        events=events,
        system_context=system_context,
        market_context=market_context,
        clients_context={"truth_state":"UNKNOWN"},
        content_context={"truth_state":"UNKNOWN"},
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Ativas", summary["active"])
    c2.metric("Aprovação", summary["waiting_approval"])
    c3.metric("Bloqueadas", summary["blocked"])
    c4.metric("Alertas", obs["by_severity"]["WARNING"] + obs["by_severity"]["ERROR"] + obs["by_severity"]["CRITICAL"])

    st.markdown("#### Briefing executivo")
    st.write(brief["system"]["message"])
    st.write(brief["market"]["message"])
    st.write(brief["clients"]["message"])
    st.write(brief["content"]["message"])

    st.markdown("#### Nova tarefa")
    with st.form("aion_secretary_new_task", clear_on_submit=True):
        title = st.text_input("Tarefa")
        cdom,cprio = st.columns(2)
        domain = cdom.selectbox(
            "Área",
            ["central","trading","studio","business","laboratory","secretary","development","promotions"],
        )
        priority = cprio.selectbox("Prioridade", list(PRIORITIES), index=2)
        action = st.selectbox("Tipo de ação", list(ACTIONS), index=0)
        note = st.text_area("Observação", max_chars=1200)
        cost = st.number_input("Custo mensal estimado (USD)", min_value=0.0, value=0.0, step=1.0)
        submit = st.form_submit_button("Adicionar à fila", type="primary")
    if submit:
        try:
            task = new_task(
                title,
                domain=domain,
                priority=priority,
                action=action,
                note=note,
                estimated_monthly_cost_usd=cost,
                source=str(access.get("username") or "ADMIN"),
            )
            requirement = approval_requirement(task, access, feature_flags=flags)
            if requirement["required"]:
                task["status"] = "WAITING_APPROVAL"
                task["approval"]["required"] = True
            tasks = upsert_task(tasks, task)
            updated = update_operating_checkpoint(checkpoint, tasks=tasks, events=events, dirty=True)
            updated = _record_working_event(
                updated,
                "task_created",
                f"Tarefa criada: {task['title']}",
                evidence={"task_id":task["task_id"],"action":task["action"],"priority":task["priority"]},
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Tarefa adicionada à memória operacional local.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a tarefa: {type(exc).__name__}")

    if tasks:
        rows = [{
            "ID":x.get("task_id"),
            "Prioridade":x.get("priority"),
            "Status":x.get("status"),
            "Área":x.get("domain"),
            "Ação":x.get("action"),
            "Tarefa":x.get("title"),
            "Custo USD":x.get("estimated_monthly_cost_usd"),
        } for x in tasks]
        st.dataframe(rows, width="stretch", hide_index=True)

        options=[str(x.get("task_id")) for x in tasks]
        selected_id=st.selectbox("Tarefa selecionada", options, key="aion_secretary_selected_task")
        selected=next((x for x in tasks if str(x.get("task_id"))==selected_id),None)
        if isinstance(selected,Mapping):
            st.caption(
                f"{selected.get('priority')} · {selected.get('status')} · {selected.get('domain')} · "
                f"ação {selected.get('action')}"
            )
            b1,b2,b3,b4=st.columns(4)
            if b1.button("▶️ Iniciar", key="aion_task_start"):
                tasks=transition_task(tasks,selected_id,"IN_PROGRESS")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_started",f"Tarefa iniciada: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
            if b2.button("✅ Aprovar", key="aion_task_approve"):
                try:
                    tasks=approve_task(tasks,selected_id,access,feature_flags=flags)
                    updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                    _set_working_checkpoint(_record_working_event(updated,"task_approved",f"Aprovação registrada: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")
            if b3.button("✔️ Concluir", key="aion_task_done"):
                tasks=transition_task(tasks,selected_id,"DONE")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_done",f"Tarefa concluída manualmente: {selected_id}",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
            if b4.button("⛔ Cancelar", key="aion_task_cancel"):
                tasks=transition_task(tasks,selected_id,"CANCELED")
                updated=update_operating_checkpoint(checkpoint,tasks=tasks,events=events,dirty=True)
                _set_working_checkpoint(_record_working_event(updated,"task_canceled",f"Tarefa cancelada: {selected_id}",severity="NOTICE",evidence={"task_id":selected_id}),dirty=True)
                st.rerun()
    else:
        st.info("A fila operacional do AION está vazia.")

    with st.expander("Observabilidade / auditoria"):
        st.caption(
            f"Eventos: {obs['total']} · warnings {obs['by_severity']['WARNING']} · "
            f"errors {obs['by_severity']['ERROR']} · críticos {obs['by_severity']['CRITICAL']}"
        )
        if events:
            st.dataframe(list(reversed(events[-30:])), width="stretch", hide_index=True)
        else:
            st.write("Nenhum evento operacional registrado nesta memória.")


def _render_trading(market_context: Mapping[str, Any]) -> None:
    st.markdown("### 📈 Trading · leitura segura")
    market_text, market_truth = _safe_market_state(market_context)
    st.info(f"Estado: {market_truth} — {market_text}")
    st.markdown(
        "- AION pode explicar Radar, Macro, dados, filtros, Gate e evidências já calculadas.\n"
        "- AION não converte score em promessa de lucro.\n"
        "- AION não habilita corretora nem execução real.\n"
        "- Backtest/Paper/Forward continuam separados de produção real."
    )


def _render_studio(flags: Mapping[str, bool]) -> None:
    st.markdown("### 🎬 AION Studio")
    st.write(
        "Pipeline preparado para **ideia → roteiro → imagem/capa → vídeo → legenda → revisão → publicação**."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Instagram", "PREPARAR")
    c2.metric("TikTok", "PREPARAR")
    c3.metric("YouTube", "PREPARAR")
    publish = flags.get("social_publish", False)
    st.warning(
        "Publicação automática está " + ("LIGADA por configuração." if publish else "DESLIGADA por feature flag.")
    )
    idea = st.text_area(
        "Ideia de conteúdo",
        key="aion_studio_idea",
        placeholder="Ex.: vídeo de 60 segundos mostrando como o Radar organiza as melhores oportunidades.",
    )
    if st.button("Criar briefing de produção", key="aion_studio_brief"):
        route = route_context(idea)
        st.session_state["aion_studio_briefing"] = {
            "tema": idea.strip(),
            "formato": "vertical 9:16 + adaptação 16:9",
            "duracao": "60–70s",
            "etapas": ["gancho", "demonstração", "prova/explicação", "CTA"],
            "dominio": route["domain"],
            "publicacao_automatica": False,
        }
    brief = st.session_state.get("aion_studio_briefing")
    if isinstance(brief, Mapping):
        st.json(dict(brief))


def _render_business(flags: Mapping[str, bool]) -> None:
    st.markdown("### 💼 AION Negócios")
    st.write(
        "Área separada do trading para pesquisa de produtos, tendências, fornecedores, margem, "
        "estoque, anúncios e acompanhamento de receita."
    )
    cost = st.number_input(
        "Custo mensal alvo do ecossistema (USD)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="aion_business_cost",
    )
    revenue = st.number_input(
        "Lucro líquido de vendas acumulado no mês (USD)",
        min_value=0.0,
        value=0.0,
        step=10.0,
        key="aion_business_revenue",
    )
    coverage = 0.0 if cost <= 0 else min(999.0, (revenue / cost) * 100.0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Custo alvo", f"US$ {cost:,.2f}")
    c2.metric("Lucro informado", f"US$ {revenue:,.2f}")
    c3.metric("Cobertura", "N/D" if cost <= 0 else f"{coverage:.1f}%")
    st.progress(0 if cost <= 0 else min(100, int(round(coverage))))
    st.caption(
        "Valores acima são informados pelo administrador nesta tela; não representam vendas confirmadas "
        "do Mercado Livre/TikTok Shop enquanto essas integrações não estiverem conectadas."
    )
    st.warning(
        "Publicação em marketplace está "
        + ("LIGADA por configuração." if flags.get("marketplace_publish") else "DESLIGADA por feature flag.")
    )


def _render_laboratory(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 🧪 Laboratório / Sandbox")
    st.write(
        "Toda novidade nasce aqui, com isolamento, teste, evidência e rollback antes de qualquer promoção."
    )
    st.markdown("#### Feature Flags externas")
    rows = [
        {"feature": key, "enabled": bool(value), "default": "OFF"}
        for key, value in sorted(flags.items())
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.markdown("#### Guardian")
    for action in ("read", "save_checkpoint", "publish_social", "deploy_production", "real_trade"):
        decision = guardian_decision(action, {"role": "ADMIN"}, approved=False, feature_flags=flags)
        st.caption(
            f"{action}: {'PERMITIDO' if decision['allowed'] else 'BLOQUEADO'} · "
            f"{decision['risk']} · {decision['reason']}"
        )

    st.markdown("#### Roteador de inteligência / orçamento")
    current_budget = normalize_budget((checkpoint.get("aion") or {}).get("model_budget", {}))
    provider = provider_status(feature_flags=flags)
    c1,c2,c3 = st.columns(3)
    c1.metric("Rota atual", provider.get("state","UNKNOWN"))
    c2.metric("Teto mensal", f"US$ {current_budget['monthly_limit_usd']:.2f}")
    c3.metric("Saldo aprovado", f"US$ {current_budget['remaining_usd']:.2f}")
    st.caption(
        "Definir teto não gera cobrança. Mesmo com teto positivo, cada solicitação paga continua "
        "exigindo aprovação explícita e um cliente externo realmente implementado."
    )
    with st.form("aion_model_budget_form"):
        monthly_limit = st.number_input(
            "Teto mensal máximo para IA externa (USD)",
            min_value=0.0,
            value=float(current_budget["monthly_limit_usd"]),
            step=1.0,
        )
        allow_paid = st.checkbox(
            "Permitir solicitações pagas dentro do teto",
            value=bool(current_budget["allow_paid"]),
        )
        save_budget = st.form_submit_button("Salvar política de orçamento")
    if save_budget:
        updated = set_budget_policy(
            checkpoint,
            monthly_limit_usd=monthly_limit,
            allow_paid=allow_paid,
            approved_by=str(access.get("username") or "ADMIN"),
            approved_at=datetime.now(timezone.utc).isoformat(),
        )
        updated = update_operating_checkpoint(updated, dirty=True)
        updated = _record_working_event(
            updated,
            "model_budget_policy_updated",
            "Política de orçamento da IA atualizada pelo administrador.",
            evidence={
                "monthly_limit_usd": monthly_limit,
                "allow_paid": allow_paid,
                "external_feature_enabled": bool(flags.get("external_llm", False)),
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success("Política de orçamento atualizada localmente; salve o Checkpoint Mestre para persistir.")
        st.rerun()

    preview = route_intelligence(
        "análise complexa de arquitetura do AtlasQuant",
        provider_state=provider.get("state"),
        external_feature_enabled=bool(flags.get("external_llm", False)),
        budget=current_budget,
        estimated_request_cost_usd=0.01,
        request_approved=False,
    )
    st.caption(
        f"Teste do roteador: {preview['lane']} · {preview['complexity']} · {preview['reason']}"
    )


def _render_development(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    source_checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 🛠️ AION Desenvolvedor")
    objective = st.text_area(
        "Missão de desenvolvimento",
        key="aion_dev_mission",
        placeholder="Ex.: revisar a interface do Administrador e corrigir contraste sem alterar o motor.",
    )
    if st.button("Montar missão segura", key="aion_dev_plan"):
        st.session_state["aion_dev_plan_result"] = mission_plan(objective)
    plan = st.session_state.get("aion_dev_plan_result")
    if isinstance(plan, Mapping):
        st.write(f"**Missão:** {plan.get('mission_id')} · domínio {plan.get('domain')}")
        for idx, step in enumerate(plan.get("steps", []), start=1):
            st.markdown(f"{idx}. {step}")

    st.markdown("#### Checkpoint Mestre")
    st.caption(
        f"Proveniência ativa: {runtime_result.get('source') or runtime_result.get('status')}. "
        f"Digest local: {checkpoint_digest(checkpoint)}."
    )
    conflict = bool(st.session_state.get(_WORKING_CONFLICT_KEY, False))
    if conflict:
        st.error(
            "Conflito detectado: o Checkpoint Mestre do runtime mudou enquanto existem alterações locais. "
            "O AION não vai sobrescrever a versão nova automaticamente."
        )
        if st.button("↩️ Descartar alterações locais e recarregar runtime", key="aion_reload_runtime_checkpoint"):
            _set_working_checkpoint(source_checkpoint, dirty=False)
            st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(source_checkpoint)
            st.session_state[_WORKING_CONFLICT_KEY] = False
            st.rerun()

    cfg = _runtime_config()
    if st.button(
        "💾 Salvar Checkpoint Mestre no runtime",
        key="aion_save_checkpoint",
        disabled=conflict,
        help="A escrita ocorre apenas no branch de runtime e este clique conta como aprovação explícita.",
    ):
        decision = guardian_decision(
            "save_checkpoint",
            access,
            approved=True,
            feature_flags=flags,
        )
        if not decision["allowed"]:
            st.error(decision["reason"])
        else:
            result = save_runtime_checkpoint(
                deepcopy(checkpoint),
                cfg,
                approved=True,
                expected_sha=str(runtime_result.get("sha") or ""),
            )
            if result.get("saved"):
                saved_checkpoint = ensure_operating_checkpoint(checkpoint)
                saved_checkpoint["operating"]["dirty"] = False
                _set_working_checkpoint(saved_checkpoint, dirty=False)
                st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(saved_checkpoint)
                st.success("Checkpoint Mestre salvo e confirmado no runtime.")
                st.session_state["aion_checkpoint_save_result"] = result
            else:
                st.warning(
                    "Checkpoint não foi confirmado como salvo. "
                    f"Estado: {result.get('status')} · motivo: {result.get('reason','não informado')}."
                )

    st.markdown("#### Camada de Verdade")
    for item in TRUTH_RULES:
        st.markdown(f"- {item}")


def _render_promotions(flags: Mapping[str, bool]) -> None:
    st.markdown("### 🎟️ Assinaturas & Promoções")
    st.caption("Primeira etapa: criar rascunho auditável. Ativação real continua desligada.")
    name = st.text_input("Nome da campanha", key="aion_promo_name")
    kind = st.selectbox(
        "Benefício",
        ["7 dias grátis", "30 dias grátis", "Desconto percentual", "Desconto fixo"],
        key="aion_promo_kind",
    )
    max_uses = st.number_input(
        "Limite de usos", min_value=1, max_value=100000, value=100, step=1, key="aion_promo_uses"
    )
    if st.button("Gerar rascunho de promoção", key="aion_promo_draft"):
        st.session_state["aion_promo_draft_result"] = {
            "campaign": name.strip() or "Campanha sem nome",
            "benefit": kind,
            "max_uses": int(max_uses),
            "status": "DRAFT_ONLY",
            "activation_enabled": bool(flags.get("promotion_activation", False)),
            "payment_provider_enabled": bool(flags.get("payment_provider", False)),
        }
    draft = st.session_state.get("aion_promo_draft_result")
    if isinstance(draft, Mapping):
        st.json(dict(draft))
    st.warning(
        "Ativação automática está "
        + ("LIGADA por configuração." if flags.get("promotion_activation") else "DESLIGADA por feature flag.")
    )


def render_aion_admin_console(
    access: Mapping[str, Any] | None,
    *,
    market_context: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    access_map = dict(access or {})
    market = dict(market_context or {})
    system = dict(system_context or {})

    if not is_admin(access_map):
        st.error("AION oficial do administrador está bloqueado para esta sessão.")
        return {
            "schema": SCHEMA,
            "allowed": False,
            "reason": "ADMIN_REQUIRED",
        }

    flags = feature_flag_snapshot(_flag_overrides())
    provider = provider_status(feature_flags=flags)
    memory_summary = canonical_memory_summary()
    cfg = _runtime_config()
    runtime_result = load_runtime_checkpoint(cfg, timeout=6.0)
    merged = merged_checkpoint(runtime_result)
    source_checkpoint = merged["checkpoint"]
    checkpoint = _working_checkpoint(source_checkpoint)

    _render_header(
        access_map,
        str(runtime_result.get("status") or "UNKNOWN"),
        str(provider.get("state") or "UNKNOWN"),
        system,
    )
    _render_executive_grid(memory_summary, runtime_result, provider, market)

    tabs = st.tabs([
        "🧠 Central",
        "🗂️ Secretaria",
        "📈 Trading",
        "🎬 Studio",
        "💼 Negócios",
        "🧪 Laboratório",
        "🛠️ Desenvolvimento",
        "🎟️ Promoções",
    ])
    with tabs[0]:
        _render_central(access_map, checkpoint, runtime_result, memory_summary, flags, system)
    with tabs[1]:
        _render_secretary(access_map, checkpoint, flags, system, market)
    with tabs[2]:
        _render_trading(market)
    with tabs[3]:
        _render_studio(flags)
    with tabs[4]:
        _render_business(flags)
    with tabs[5]:
        _render_laboratory(access_map, checkpoint, flags)
    with tabs[6]:
        _render_development(access_map, checkpoint, source_checkpoint, runtime_result, flags)
    with tabs[7]:
        _render_promotions(flags)

    with st.expander("Política Custo Zero"):
        for item in ZERO_COST_RULES:
            st.markdown(f"- {item}")

    return {
        "schema": SCHEMA,
        "allowed": True,
        "runtime_status": runtime_result.get("status"),
        "runtime_confirmed": bool(merged.get("runtime_confirmed")),
        "memory_documents": memory_summary.get("document_count"),
        "provider_state": provider.get("state"),
        "feature_flags": flags,
        "checkpoint_digest": checkpoint_digest(checkpoint),
        "checkpoint_dirty": bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
        "checkpoint_conflict": bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        "task_summary": queue_summary((checkpoint.get("operating") or {}).get("tasks", [])),
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "render_aion_admin_console", "AION_ADMIN_CSS"]
