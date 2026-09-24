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
    update_business_checkpoint,
    update_entitlements_checkpoint,
    update_operating_checkpoint,
    update_promotions_checkpoint,
    update_studio_checkpoint,
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
    record_model_spend_estimate,
    route_intelligence,
    set_budget_policy,
)
from atlasquant_aion_provider import (
    build_provider_prompt,
    estimate_request_cost,
    execute_openai_answer,
    provider_config,
)
from atlasquant_aion_studio import (
    FORMATS as STUDIO_FORMATS,
    PLATFORMS as STUDIO_PLATFORMS,
    approve_project,
    new_content_project,
    publication_preflight,
    script_blueprint,
    studio_summary,
    upsert_project,
)
from atlasquant_aion_business import (
    CHANNELS as BUSINESS_CHANNELS,
    TRUTH_STATES as BUSINESS_TRUTH_STATES,
    approve_product,
    business_summary,
    coverage_snapshot,
    marketplace_preflight,
    new_product_candidate,
    trend_assessment,
    upsert_product,
)
from atlasquant_aion_promotions import (
    BENEFIT_TYPES as PROMO_BENEFIT_TYPES,
    activation_preflight,
    approve_campaign,
    new_campaign,
    promotions_summary,
    upsert_campaign,
)
from atlasquant_aion_entitlements import (
    SOURCE_KINDS as ENTITLEMENT_SOURCE_KINDS,
    approve_entitlement_request,
    entitlement_activation_preflight,
    entitlement_summary,
    new_entitlement_request,
    upsert_entitlement,
)
from atlasquant_access_panel import configured_users
from atlasquant_entitlement_account_audit import (
    audit_account_entitlements,
    audit_requires_review,
)
from atlasquant_aion_status_board import (
    build_master_status_board,
    status_rows,
)
from atlasquant_aion_approval_inbox import (
    collect_approval_inbox,
    approval_rows,
)
from atlasquant_aion_tenant import (
    tenant_policy_snapshot,
    tenant_readiness_summary,
)

try:
    from atlasquant_neural_voice_ui import render_neural_voice_player
except Exception:
    render_neural_voice_player = None

SCHEMA = "ATLASQUANT_AION_ADMIN_V1"
AION_WORKSPACES = (
    "🧠 Central",
    "🗂️ Secretaria",
    "📈 Trading",
    "🎬 Studio",
    "💼 Negócios",
    "🧪 Laboratório",
    "🛠️ Desenvolvimento",
    "🎟️ Promoções",
)
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


def _provider_env() -> dict[str, str]:
    names = (
        "AION_MODEL_PROVIDER",
        "OPENAI_API_KEY",
        "AION_OPENAI_FAST_MODEL",
        "AION_OPENAI_REASONING_MODEL",
        "AION_OPENAI_INPUT_USD_PER_MTOK",
        "AION_OPENAI_OUTPUT_USD_PER_MTOK",
        "AION_OPENAI_MAX_OUTPUT_TOKENS",
        "AION_OPENAI_TIMEOUT_SECONDS",
    )
    return {name: _secret(name) for name in names}


def _context_voice(area: str, transcript: str, *, key: str) -> None:
    if render_neural_voice_player is None:
        return
    with st.expander(f"🔊 Assistente de voz · {area}", expanded=False):
        st.caption(
            "A voz é opcional e nunca toca sozinha. Se houver provedor de voz pago configurado, "
            "o clique para gerar áudio pode consumir esse serviço."
        )
        render_neural_voice_player(
            transcript,
            key=key,
            button_label=f"🔊 Ouvir AION · {area}",
        )


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


def _render_master_status(board: Mapping[str, Any]) -> None:
    counts = board.get("counts") if isinstance(board.get("counts"), Mapping) else {}
    st.markdown("#### Painel Mestre de Estado")
    st.caption(
        "CONFIRMADO exige evidência desta execução. BLOQUEADO é uma proteção/flag. "
        "DEPENDÊNCIA EXTERNA exige conector/prova. DESCONHECIDO não é tratado como pronto."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Confirmados", int(counts.get("CONFIRMED") or 0))
    c2.metric("Bloqueados", int(counts.get("BLOCKED") or 0))
    c3.metric("Dependência externa", int(counts.get("EXTERNAL_DEPENDENCY") or 0))
    c4.metric("Desconhecidos", int(counts.get("UNKNOWN") or 0))
    rows = status_rows(board)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_approval_inbox(inbox: Mapping[str, Any]) -> None:
    st.markdown("#### Central de Aprovações")
    st.caption(
        "Somente itens que realmente chegaram a um estágio de decisão aparecem aqui. "
        "Esta visão não aprova nem executa ações; a decisão continua explícita na área de origem."
    )
    by_kind = inbox.get("by_kind") if isinstance(inbox.get("by_kind"), Mapping) else {}
    by_priority = inbox.get("by_priority") if isinstance(inbox.get("by_priority"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Pendentes", int(inbox.get("total") or 0))
    c2.metric("P0", int(by_priority.get("P0") or 0))
    c3.metric("P1", int(by_priority.get("P1") or 0))
    c4.metric("Tarefas", int(by_kind.get("TASK") or 0))
    rows = approval_rows(inbox)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
        st.info(
            "Para aprovar, abra a área indicada no item. "
            "A Central não transforma visibilidade em autorização automática."
        )
    else:
        st.success("Nenhum item chegou a um estágio que exija aprovação administrativa nesta memória.")


def _render_central(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    memory_summary: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
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

    _render_master_status(status_board)
    _render_approval_inbox(approval_inbox)

    st.markdown("#### Pergunte ao AION")
    question = st.text_input(
        "Pergunta ou missão",
        key="aion_admin_question",
        placeholder="Ex.: AION, onde paramos no sistema? / como está o Studio? / o que falta validar?",
    )

    provider_env = _provider_env()
    provider = provider_status(feature_flags=flags, env=provider_env)
    budget = normalize_budget((checkpoint.get("aion") or {}).get("model_budget", {}))
    hits_preview = search_canonical_memory(question) if question.strip() else []
    domain_preview = route_context(question).get("domain") if question.strip() else "central"
    prompt_preview = build_provider_prompt(
        question,
        domain=domain_preview,
        memory_hits=hits_preview,
        system_context=system_context,
    ) if question.strip() else ""
    estimate = estimate_request_cost(
        prompt_preview,
        config=provider_config(provider_env),
    ) if prompt_preview else {
        "estimable": False,
        "estimated_max_cost_usd": None,
        "state": "NO_PROMPT",
    }

    external_ready = bool(
        provider.get("state") == "EXTERNAL_READY"
        and flags.get("external_llm", False)
        and budget.get("allow_paid", False)
        and estimate.get("estimable", False)
    )
    use_external = st.checkbox(
        "Usar inteligência externa nesta pergunta",
        value=False,
        disabled=not external_ready,
        key="aion_use_external_model",
        help=(
            "Só fica disponível quando feature flag, provedor, preços e orçamento estão configurados. "
            "Desmarcado = resposta local/custo zero."
        ),
    )
    approve_external = False
    if use_external:
        estimated_cost = estimate.get("estimated_max_cost_usd")
        st.warning(
            f"Custo máximo estimado desta solicitação: US$ {float(estimated_cost or 0):.6f}. "
            "É uma estimativa técnica; a cobrança real pertence ao provedor."
        )
        approve_external = st.checkbox(
            "Aprovo esta solicitação externa dentro do teto informado",
            value=False,
            key="aion_external_request_approval",
        )
    elif provider.get("state") != "ZERO_COST_LOCAL":
        st.caption(
            f"IA externa: {provider.get('state')} · "
            "nenhuma chamada paga será feita sem configuração e aprovação."
        )

    if st.button("Analisar com AION", key="aion_admin_ask", type="primary", width="stretch"):
        hits = search_canonical_memory(question)
        estimated_cost = float(estimate.get("estimated_max_cost_usd") or 0.0)
        route = route_intelligence(
            question,
            provider_state=provider.get("state"),
            external_feature_enabled=bool(flags.get("external_llm", False)),
            budget=budget,
            estimated_request_cost_usd=estimated_cost,
            request_approved=bool(use_external and approve_external),
        )

        answer = None
        if use_external and approve_external and str(route.get("lane") or "").startswith("EXTERNAL_"):
            prompt = build_provider_prompt(
                question,
                domain=route_context(question).get("domain"),
                memory_hits=hits,
                system_context=system_context,
            )
            external = execute_openai_answer(
                prompt,
                lane=route.get("lane"),
                budget=budget,
                external_feature_enabled=bool(flags.get("external_llm", False)),
                request_approved=True,
                values=provider_env,
            )
            st.session_state["aion_last_external_state"] = external
            if external.get("state") == "ANSWER_READY":
                answer = {
                    "schema": "ATLASQUANT_AION_EXTERNAL_ANSWER_V1",
                    "answer": external.get("answer"),
                    "domain": route_context(question).get("domain"),
                    "provider": provider,
                    "evidence": hits,
                    "truth_state": external.get("truth_state"),
                    "executes_action": False,
                    "real_orders_enabled": False,
                }
                usage = external.get("usage") if isinstance(external.get("usage"), Mapping) else {}
                tracked_cost = usage.get("actual_cost_usd_estimate")
                if tracked_cost is None:
                    tracked_cost = estimated_cost
                updated = record_model_spend_estimate(checkpoint, tracked_cost)
                updated = update_operating_checkpoint(updated, dirty=True)
                updated = _record_working_event(
                    updated,
                    "external_model_answer",
                    "AION recebeu uma resposta de modelo externo para uma consulta aprovada.",
                    evidence={
                        "lane": route.get("lane"),
                        "model": external.get("model"),
                        "tracked_cost_usd_estimate": tracked_cost,
                        "truth_state": external.get("truth_state"),
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
            else:
                st.warning(
                    "A chamada externa não foi concluída. "
                    f"Estado: {external.get('state')} · motivo: {external.get('reason','não informado')}."
                )

        if answer is None:
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

    spoken = (
        f"Bem-vindo à Central AION. A prioridade atual é "
        f"{(checkpoint.get('aion') or {}).get('priority','revisar o checkpoint')}. "
        "O AION trabalha com regra da verdade, custo controlado e ordens reais bloqueadas."
    )
    _context_voice("Central", spoken, key="aion_admin_welcome_voice")

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
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
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
    if bool(approval_inbox.get("has_pending")):
        st.warning(
            f"Central de Aprovações: {int(approval_inbox.get('total') or 0)} item(ns) aguardam decisão administrativa."
        )
    else:
        st.caption("Central de Aprovações: nenhuma decisão pendente nesta memória.")
    attention = status_board.get("attention") if isinstance(status_board.get("attention"), list) else []
    with st.expander("Pendências do Painel Mestre", expanded=False):
        if attention:
            for item in attention[:10]:
                st.markdown(
                    f"- **{item.get('state')} · {item.get('label')}** — "
                    f"{item.get('detail')}"
                )
                if item.get("next_action"):
                    st.caption("Próxima ação: " + str(item.get("next_action")))
        else:
            st.write("Nenhuma pendência foi fornecida pelo Painel Mestre nesta execução.")
    _context_voice(
        "Secretaria",
        (
            f"Bem-vindo à Secretaria AION. Existem {summary['active']} tarefas ativas, "
            f"{summary['waiting_approval']} aguardando aprovação e {summary['blocked']} bloqueadas. "
            "Mercado, clientes e conteúdo só são anunciados quando a fonte está confirmada."
        ),
        key="aion_secretary_voice",
    )

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
    _context_voice(
        "Trading",
        (
            "Bem-vindo ao Trading do AION. Aqui eu explico Radar, Macro e evidências já calculadas. "
            f"O estado de mercado nesta tela é {market_truth}. Ordens reais permanecem bloqueadas."
        ),
        key="aion_trading_voice",
    )


def _render_studio(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 🎬 AION Studio")
    st.write(
        "Pipeline persistente para **ideia → roteiro → imagem/capa → vídeo → revisão → aprovação → publicação**."
    )
    _context_voice(
        "Studio",
        (
            "Bem-vindo ao AION Studio. Aqui organizamos ideias, roteiros, imagens, vídeos, legendas e capas. "
            "Todo conteúdo fica registrado no Checkpoint Mestre e publicação externa exige aprovação."
        ),
        key="aion_studio_voice",
    )

    studio = checkpoint.get("studio") if isinstance(checkpoint.get("studio"), Mapping) else {}
    projects = list(studio.get("projects", []) or [])
    summary = studio_summary(projects)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Projetos", summary["total"])
    c2.metric("Em revisão", summary["in_review"])
    c3.metric("Aprovados", summary["approved"])
    c4.metric("Publicados confirmados", summary["published"])

    publish = bool(flags.get("social_publish", False))
    st.warning(
        "Publicação automática está "
        + ("HABILITADA POR FLAG, mas ainda depende do Guardian e de integração real." if publish else "DESLIGADA por feature flag.")
    )

    st.markdown("#### Novo projeto de conteúdo")
    with st.form("aion_studio_new_project", clear_on_submit=True):
        title = st.text_input("Título / ideia")
        objective = st.text_area("Objetivo do conteúdo", max_chars=1200)
        platforms = st.multiselect(
            "Canais",
            list(STUDIO_PLATFORMS),
            default=["Instagram","TikTok"],
        )
        cfmt,cdur = st.columns(2)
        ratio = cfmt.selectbox("Formato", list(STUDIO_FORMATS), index=0)
        duration = cdur.number_input("Duração alvo (segundos)", min_value=10, max_value=600, value=60, step=5)
        audience = st.text_input("Público")
        cta = st.text_input("CTA")
        create_project = st.form_submit_button("Criar projeto no Studio", type="primary")
    if create_project:
        try:
            project = new_content_project(
                title,
                objective=objective,
                platforms=platforms,
                format_ratio=ratio,
                duration_seconds=duration,
                audience=audience,
                cta=cta,
                source=str(access.get("username") or "ADMIN"),
            )
            projects = upsert_project(projects, project)
            updated = update_studio_checkpoint(checkpoint, projects=projects, dirty=True)
            updated = _record_working_event(
                updated,
                "studio_project_created",
                f"Projeto de conteúdo criado: {project['title']}",
                evidence={
                    "content_id":project["content_id"],
                    "platforms":",".join(project["platforms"]),
                    "status":project["status"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Projeto salvo na memória de trabalho do AION Studio.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar o projeto: {type(exc).__name__}")

    if projects:
        rows=[{
            "ID":p.get("content_id"),
            "Status":p.get("status"),
            "Título":p.get("title"),
            "Canais":", ".join(p.get("platforms",[])),
            "Formato":p.get("format_ratio"),
            "Duração":p.get("duration_seconds"),
            "Aprovado":bool((p.get("approval") or {}).get("approved",False)),
            "Publicado":bool((p.get("publication") or {}).get("executed",False)),
        } for p in projects]
        st.dataframe(rows, width="stretch", hide_index=True)
        selected_id=st.selectbox(
            "Projeto selecionado",
            [str(p.get("content_id")) for p in projects],
            key="aion_studio_selected_project",
        )
        selected=next((p for p in projects if str(p.get("content_id"))==selected_id),None)
        if isinstance(selected, Mapping):
            blueprint=script_blueprint(selected)
            with st.expander("Roteiro-base / storyboard", expanded=True):
                st.write(f"**{blueprint['title']} · {blueprint['total_seconds']}s**")
                for segment in blueprint["segments"]:
                    st.markdown(
                        f"- **{segment['name']} ({segment['seconds']}s):** {segment['instruction']}"
                    )
                st.caption("Roteiro-base determinístico; não afirma resultados nem recursos inexistentes.")

            p1,p2=st.columns(2)
            if p1.button("✅ Aprovar conteúdo", key="aion_studio_approve"):
                try:
                    approved=approve_project(selected,access)
                    projects=upsert_project(projects,approved)
                    updated=update_studio_checkpoint(checkpoint,projects=projects,dirty=True)
                    updated=_record_working_event(
                        updated,
                        "studio_project_approved",
                        f"Conteúdo aprovado: {approved['content_id']}",
                        evidence={"content_id":approved["content_id"]},
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight=publication_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            if preflight["allowed"]:
                st.success("Pré-requisitos de publicação disponíveis; execução ainda não ocorre nesta tela.")
            else:
                st.caption(f"Publicação: BLOQUEADA · {preflight['reason']}")
    else:
        st.info("Nenhum projeto de conteúdo registrado no Studio.")


def _render_business(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("### 💼 AION Negócios")
    st.write(
        "Área separada do trading para pesquisa de produtos, tendências, fornecedores, margem, "
        "estoque, anúncios e acompanhamento de receita."
    )
    _context_voice(
        "Negócios",
        (
            "Bem-vindo ao AION Negócios. Aqui pesquisamos candidatos de produto, registramos evidências "
            "e calculamos margem. Nenhum produto é chamado de tendência ou mais vendido sem fonte confirmada."
        ),
        key="aion_business_voice",
    )

    business = checkpoint.get("business") if isinstance(checkpoint.get("business"), Mapping) else {}
    products = list(business.get("products", []) or [])
    summary = business_summary(products)

    st.markdown("#### Sustentabilidade do AtlasQuant")
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
    coverage=coverage_snapshot(cost,revenue)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Produtos pesquisados",summary["total"])
    c2.metric("Margem positiva",summary["positive_margin_candidates"])
    c3.metric("Tendências confirmadas",summary["confirmed_trends"])
    c4.metric("Cobertura", "N/D" if coverage["coverage_pct"] is None else f"{coverage['coverage_pct']:.1f}%")
    st.progress(0 if coverage["coverage_pct"] is None else min(100,int(round(coverage["coverage_pct"]))))
    st.caption(
        "Custos e lucros acima são informados pelo administrador; não representam vendas confirmadas "
        "do Mercado Livre/TikTok Shop enquanto integrações de pedidos não estiverem conectadas."
    )

    st.markdown("#### Candidato de produto")
    with st.form("aion_business_new_product", clear_on_submit=True):
        name=st.text_input("Produto")
        channel=st.selectbox("Canal",list(BUSINESS_CHANNELS))
        supplier=st.text_input("Fornecedor / referência")
        ev1,ev2=st.columns(2)
        evidence_source=ev1.text_input("Fonte da pesquisa")
        evidence_truth=ev2.selectbox("Estado da evidência",list(BUSINESS_TRUTH_STATES),index=3)
        evidence_url=st.text_input("URL / referência da fonte")
        trend_note=st.text_area(
            "O que a fonte mostra sobre tendência/demanda",
            max_chars=1200,
            help="Se a fonte não confirmar, use UNKNOWN/INFERENCE/HYPOTHESIS.",
        )
        cprice,ccost=st.columns(2)
        sale_price=cprice.number_input("Preço de venda estimado (R$)",min_value=0.0,value=0.0,step=1.0)
        unit_cost=ccost.number_input("Custo unitário (R$)",min_value=0.0,value=0.0,step=1.0)
        cfee,cship,ctax=st.columns(3)
        fee=cfee.number_input("Taxa plataforma (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5)
        shipping=cship.number_input("Frete/custo logístico (R$)",min_value=0.0,value=0.0,step=1.0)
        tax=ctax.number_input("Impostos estimados (%)",min_value=0.0,max_value=100.0,value=0.0,step=0.5)
        other=st.number_input("Outros custos por unidade (R$)",min_value=0.0,value=0.0,step=1.0)
        create_product=st.form_submit_button("Adicionar à pesquisa de produtos",type="primary")
    if create_product:
        try:
            product=new_product_candidate(
                name,
                channel=channel,
                evidence_source=evidence_source,
                evidence_url=evidence_url,
                evidence_truth=evidence_truth,
                trend_note=trend_note,
                supplier=supplier,
                sale_price=sale_price,
                unit_cost=unit_cost,
                platform_fee_pct=fee,
                shipping_cost=shipping,
                tax_pct=tax,
                other_cost=other,
                source=str(access.get("username") or "ADMIN"),
            )
            products=upsert_product(products,product)
            updated=update_business_checkpoint(checkpoint,products=products,dirty=True)
            updated=_record_working_event(
                updated,
                "business_product_added",
                f"Produto adicionado à pesquisa: {product['name']}",
                evidence={
                    "product_id":product["product_id"],
                    "channel":product["channel"],
                    "truth_state":product["research"]["truth_state"],
                },
            )
            _set_working_checkpoint(updated,dirty=True)
            st.success("Produto salvo na memória de trabalho de Negócios.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível salvar o produto: {type(exc).__name__}")

    if products:
        rows=[]
        for product in products:
            econ=product.get("economics") or {}
            trend=trend_assessment(product)
            rows.append({
                "ID":product.get("product_id"),
                "Status":product.get("status"),
                "Produto":product.get("name"),
                "Canal":product.get("channel"),
                "Evidência":(product.get("research") or {}).get("truth_state"),
                "Tendência confirmada":trend.get("can_call_trending"),
                "Lucro/unid. R$":econ.get("net_profit"),
                "Margem %":econ.get("net_margin_pct"),
            })
        st.dataframe(rows,width="stretch",hide_index=True)
        selected_id=st.selectbox(
            "Produto selecionado",
            [str(p.get("product_id")) for p in products],
            key="aion_business_selected_product",
        )
        selected=next((p for p in products if str(p.get("product_id"))==selected_id),None)
        if isinstance(selected,Mapping):
            trend=trend_assessment(selected)
            econ=selected.get("economics") or {}
            st.write(
                f"**Economia unitária:** lucro R$ {float(econ.get('net_profit') or 0):.2f} · "
                f"margem {float(econ.get('net_margin_pct') or 0):.2f}% · "
                f"ROI sobre custo {float(econ.get('roi_on_unit_cost_pct') or 0):.2f}%."
            )
            if trend["can_call_trending"]:
                st.success(f"Tendência confirmada pela fonte registrada: {trend['message']}")
            else:
                st.warning(trend["message"])

            if st.button("✅ Aprovar produto para próxima etapa",key="aion_business_approve"):
                try:
                    approved=approve_product(selected,access)
                    products=upsert_product(products,approved)
                    updated=update_business_checkpoint(checkpoint,products=products,dirty=True)
                    updated=_record_working_event(
                        updated,
                        "business_product_approved",
                        f"Produto aprovado para próxima etapa: {approved['product_id']}",
                        evidence={"product_id":approved["product_id"]},
                    )
                    _set_working_checkpoint(updated,dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight=marketplace_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            st.caption(
                f"Marketplace: {'PRONTO PARA CONECTOR' if preflight['allowed'] else 'BLOQUEADO'} · "
                f"{preflight['reason']}"
            )
    else:
        st.info("Nenhum candidato de produto registrado.")

    st.warning(
        "Publicação em marketplace está "
        + ("HABILITADA POR FLAG, mas ainda exige Guardian e conector real." if flags.get("marketplace_publish") else "DESLIGADA por feature flag.")
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
    _context_voice(
        "Laboratório",
        (
            "Bem-vindo ao Laboratório AION. Toda novidade passa por Sandbox, teste, evidência e rollback "
            "antes de avançar. Feature flags externas começam desligadas."
        ),
        key="aion_laboratory_voice",
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
    provider = provider_status(feature_flags=flags, env=_provider_env())
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Rota atual", provider.get("state","UNKNOWN"))
    c2.metric("Teto mensal", f"US$ {current_budget['monthly_limit_usd']:.2f}")
    c3.metric("Uso estimado", f"US$ {current_budget['spent_usd_estimate']:.4f}")
    c4.metric("Saldo estimado", f"US$ {current_budget['remaining_usd']:.4f}")
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
    _context_voice(
        "Desenvolvimento",
        (
            "Bem-vindo ao AION Desenvolvedor. As missões de código seguem branch ou Sandbox, testes, "
            "checkpoint, revisão e Guardian. Mudanças críticas não são publicadas silenciosamente."
        ),
        key="aion_development_voice",
    )
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


def _render_promotions(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    account_entitlement_audit: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🎟️ Assinaturas & Promoções")
    st.caption(
        "Campanhas e códigos ficam persistidos no Checkpoint Mestre. "
        "O código completo é mostrado somente na criação; o checkpoint guarda apenas hash + últimos 4 caracteres."
    )
    _context_voice(
        "Promoções",
        (
            "Bem-vindo a Assinaturas e Promoções. Aqui preparamos períodos gratuitos, cupons e descontos "
            "com limite de uso e auditoria. Criar ou aprovar um código não concede acesso automaticamente."
        ),
        key="aion_promotions_voice",
    )

    promo = checkpoint.get("promotions") if isinstance(checkpoint.get("promotions"), Mapping) else {}
    campaigns = list(promo.get("campaigns", []) or [])
    redemptions = list(promo.get("redemptions", []) or [])
    summary = promotions_summary(campaigns, redemptions)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Campanhas", summary["campaigns"])
    c2.metric("Aprovadas", summary["approved"])
    c3.metric("Ativas confirmadas", summary["active"])
    c4.metric("Resgates confirmados", summary["confirmed_redemptions"])

    st.markdown("#### Criar campanha")
    benefit_labels = {
        "TRIAL_DAYS": "Período grátis (dias)",
        "PERCENT_OFF": "Desconto percentual",
        "FIXED_DISCOUNT": "Desconto fixo",
    }
    with st.form("aion_promo_campaign_form", clear_on_submit=True):
        name = st.text_input("Nome da campanha")
        benefit_type = st.selectbox(
            "Tipo de benefício",
            list(PROMO_BENEFIT_TYPES),
            format_func=lambda x: benefit_labels.get(x, x),
        )
        if benefit_type == "TRIAL_DAYS":
            benefit_value = st.number_input("Dias grátis", min_value=1, max_value=365, value=7, step=1)
        elif benefit_type == "PERCENT_OFF":
            benefit_value = st.number_input("Desconto (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
        else:
            benefit_value = st.number_input("Desconto fixo", min_value=0.01, value=10.0, step=1.0)
        max_uses = st.number_input("Limite máximo de usos", min_value=1, max_value=1000000, value=100, step=1)
        starts_at = st.text_input("Início ISO opcional", placeholder="2026-10-01T00:00:00-04:00")
        expires_at = st.text_input("Expiração ISO opcional", placeholder="2026-10-31T23:59:59-04:00")
        create_campaign = st.form_submit_button("Gerar campanha e código", type="primary")

    if create_campaign:
        try:
            campaign, plain_code = new_campaign(
                name,
                benefit_type=benefit_type,
                benefit_value=benefit_value,
                max_uses=max_uses,
                starts_at=starts_at,
                expires_at=expires_at,
                source=str(access.get("username") or "ADMIN"),
            )
            campaigns = upsert_campaign(campaigns, campaign)
            updated = update_promotions_checkpoint(
                checkpoint,
                campaigns=campaigns,
                redemptions=redemptions,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "promotion_campaign_created",
                f"Campanha criada: {campaign['name']}",
                evidence={
                    "campaign_id": campaign["campaign_id"],
                    "benefit_type": campaign["benefit"]["type"],
                    "max_uses": campaign["limits"]["max_uses"],
                    "code_last4": campaign["code"]["last4"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.session_state["aion_last_plain_promo_code"] = {
                "campaign_id": campaign["campaign_id"],
                "code": plain_code,
            }
            st.success("Campanha criada. Copie o código abaixo agora; ele não será persistido em texto puro.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a campanha: {type(exc).__name__}")

    last_code = st.session_state.get("aion_last_plain_promo_code")
    if isinstance(last_code, Mapping):
        st.markdown("#### Código recém-gerado · exibição única da sessão")
        st.code(str(last_code.get("code") or ""))
        st.caption(
            f"Campanha {last_code.get('campaign_id')}. "
            "O Checkpoint Mestre armazena somente o hash do código; perder este texto exige criar outro código/campanha."
        )
        if st.button("Ocultar código da sessão", key="aion_hide_plain_promo_code"):
            st.session_state.pop("aion_last_plain_promo_code", None)
            st.rerun()

    if campaigns:
        rows = []
        for campaign in campaigns:
            benefit = campaign.get("benefit") or {}
            rows.append({
                "ID": campaign.get("campaign_id"),
                "Status": campaign.get("status"),
                "Campanha": campaign.get("name"),
                "Benefício": f"{benefit.get('type')} · {benefit.get('value')}",
                "Código": "••••" + str((campaign.get("code") or {}).get("last4") or ""),
                "Usos": f"{(campaign.get('limits') or {}).get('confirmed_uses',0)}/{(campaign.get('limits') or {}).get('max_uses',0)}",
                "Aprovada": bool((campaign.get("approval") or {}).get("approved",False)),
                "Ativa confirmada": bool((campaign.get("provider_activation") or {}).get("confirmed",False)),
            })
        st.dataframe(rows, width="stretch", hide_index=True)
        selected_id = st.selectbox(
            "Campanha selecionada",
            [str(c.get("campaign_id")) for c in campaigns],
            key="aion_selected_promo_campaign",
        )
        selected = next((c for c in campaigns if str(c.get("campaign_id")) == selected_id), None)
        if isinstance(selected, Mapping):
            benefit = selected.get("benefit") or {}
            st.write(
                f"**{selected.get('name')}** · {benefit.get('type')} = {benefit.get('value')} · "
                f"status **{selected.get('status')}**."
            )
            if st.button("✅ Aprovar campanha", key="aion_promo_approve"):
                try:
                    approved = approve_campaign(selected, access)
                    campaigns = upsert_campaign(campaigns, approved)
                    updated = update_promotions_checkpoint(
                        checkpoint,
                        campaigns=campaigns,
                        redemptions=redemptions,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "promotion_campaign_approved",
                        f"Campanha aprovada: {approved['campaign_id']}",
                        evidence={"campaign_id":approved["campaign_id"]},
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            preflight = activation_preflight(
                selected,
                access,
                feature_flags=flags,
                approved=False,
            )
            st.caption(
                f"Ativação comercial: {'ELEGÍVEL PARA CONECTOR' if preflight['allowed'] else 'BLOQUEADA'} · "
                f"{preflight['reason']}"
            )
            if bool((selected.get("approval") or {}).get("approved",False)) and flags.get("promotion_activation"):
                st.info(
                    "A feature flag de promoção está ligada, mas esta tela ainda não ativa acesso real. "
                    "Status ACTIVE só será aceito quando um provedor/registro de assinaturas devolver evidência confirmada."
                )
    else:
        st.info("Nenhuma campanha registrada.")

    st.warning(
        "Ativação real de promoção está "
        + (
            "HABILITADA POR FLAG, mas ainda exige Guardian e provedor/registro real."
            if flags.get("promotion_activation")
            else "DESLIGADA por feature flag."
        )
    )

    st.divider()
    st.markdown("### 🔐 Registro de Entitlements")
    st.caption(
        "Entitlement é o direito comercial de acesso, separado do login, do perfil USER/SALES/ADMIN, "
        "do pagamento e do cupom. Criar ou aprovar uma solicitação NÃO altera conta nem libera acesso."
    )
    entitlement_block = (
        checkpoint.get("entitlements")
        if isinstance(checkpoint.get("entitlements"), Mapping)
        else {}
    )
    entitlements = list(entitlement_block.get("records", []) or [])
    ent_summary = entitlement_summary(entitlements)

    e1,e2,e3,e4 = st.columns(4)
    e1.metric("Solicitações", ent_summary["records"])
    e2.metric("Aprovadas", ent_summary["approved"])
    e3.metric("Ativas confirmadas", ent_summary["active_confirmed"])
    e4.metric("Efetivas agora", ent_summary["effective_now"])

    with st.form("aion_entitlement_request_form", clear_on_submit=True):
        subject_ref = st.text_input(
            "Referência do cliente/conta",
            placeholder="ex.: cliente.01 ou customer_ref",
        )
        scope = st.text_input(
            "Escopo do direito",
            value="APP_ACCESS",
            help="Identificador técnico, sem definir preço ou plano comercial.",
        )
        source_kind = st.selectbox(
            "Origem da solicitação",
            list(ENTITLEMENT_SOURCE_KINDS),
        )
        source_ref = st.text_input(
            "Referência externa opcional",
            placeholder="ID de evento, campanha ou pedido — se existir",
        )
        ent_starts_at = st.text_input(
            "Início ISO opcional",
            key="aion_entitlement_starts_at",
            placeholder="2026-10-01T00:00:00-04:00",
        )
        ent_expires_at = st.text_input(
            "Expiração ISO opcional",
            key="aion_entitlement_expires_at",
            placeholder="2026-11-01T00:00:00-04:00",
        )
        ent_note = st.text_area(
            "Nota administrativa",
            key="aion_entitlement_note",
            placeholder="Motivo da solicitação. Não use este campo como prova de pagamento.",
        )
        create_entitlement = st.form_submit_button(
            "Criar solicitação de entitlement",
            type="primary",
        )

    if create_entitlement:
        try:
            item = new_entitlement_request(
                subject_ref,
                scope=scope,
                source_kind=source_kind,
                source_ref=source_ref,
                starts_at=ent_starts_at,
                expires_at=ent_expires_at,
                note=ent_note,
            )
            entitlements = upsert_entitlement(entitlements, item)
            updated = update_entitlements_checkpoint(
                checkpoint,
                records=entitlements,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "entitlement_request_created",
                f"Entitlement solicitado: {item['entitlement_id']}",
                evidence={
                    "entitlement_id": item["entitlement_id"],
                    "subject_ref": item["subject_ref"],
                    "scope": item["scope"],
                    "source_kind": item["source"]["kind"],
                    "account_registry_changed": False,
                    "role_changed": False,
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success(
                "Solicitação criada. Nenhuma conta, perfil, pagamento ou acesso foi alterado."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível criar a solicitação: {type(exc).__name__}")

    if entitlements:
        ent_rows=[]
        for item in entitlements:
            evidence=item.get("provider_evidence") or {}
            ent_rows.append({
                "ID":item.get("entitlement_id"),
                "Cliente/conta":item.get("subject_ref"),
                "Escopo":item.get("scope"),
                "Origem":(item.get("source") or {}).get("kind"),
                "Status":item.get("status"),
                "Aprovado":bool((item.get("approval") or {}).get("approved",False)),
                "Evidência externa":bool(evidence.get("confirmed",False)),
            })
        st.dataframe(ent_rows,width="stretch",hide_index=True)
        entitlement_id = st.selectbox(
            "Entitlement selecionado",
            [str(x.get("entitlement_id")) for x in entitlements],
            key="aion_selected_entitlement",
        )
        selected_entitlement = next(
            (x for x in entitlements if str(x.get("entitlement_id")) == entitlement_id),
            None,
        )
        if isinstance(selected_entitlement, Mapping):
            st.write(
                f"**{selected_entitlement.get('subject_ref')}** · "
                f"{selected_entitlement.get('scope')} · "
                f"status **{selected_entitlement.get('status')}**."
            )
            if st.button(
                "✅ Aprovar solicitação de entitlement",
                key="aion_entitlement_approve",
            ):
                try:
                    approved_entitlement = approve_entitlement_request(
                        selected_entitlement,
                        access,
                    )
                    entitlements = upsert_entitlement(
                        entitlements,
                        approved_entitlement,
                    )
                    updated = update_entitlements_checkpoint(
                        checkpoint,
                        records=entitlements,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "entitlement_request_approved",
                        f"Entitlement aprovado: {approved_entitlement['entitlement_id']}",
                        evidence={
                            "entitlement_id": approved_entitlement["entitlement_id"],
                            "account_registry_changed": False,
                            "role_changed": False,
                            "executes_entitlement": False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aprovação não registrada: {type(exc).__name__}")

            explicit_preflight = st.checkbox(
                "Aprovo somente o preflight deste entitlement (não libera acesso)",
                key=f"aion_entitlement_preflight_{entitlement_id}",
            )
            ent_preflight = entitlement_activation_preflight(
                selected_entitlement,
                access,
                feature_flags=flags,
                approved=bool(explicit_preflight),
            )
            st.caption(
                f"Entitlement: {'ELEGÍVEL PARA CONECTOR' if ent_preflight['allowed'] else 'BLOQUEADO'} · "
                f"{ent_preflight['reason']}"
            )
            st.info(
                "Mesmo quando o preflight ficar elegível, esta tela não altera ATLASQUANT_USERS_JSON, "
                "não muda USER/SALES/ADMIN e não cria acesso efetivo. "
                "ACTIVE_CONFIRMED exige evidência concreta de um futuro registro/provedor."
            )
    else:
        st.info("Nenhuma solicitação de entitlement registrada.")

    st.warning(
        "Ativação real de entitlement está "
        + (
            "HABILITADA POR FLAG para preflight, mas ainda não existe conector que conceda acesso."
            if flags.get("entitlement_activation")
            else "DESLIGADA por feature flag."
        )
    )

    st.markdown("#### Auditoria Conta × Entitlement · somente leitura")
    st.caption(
        "Esta auditoria compara contas USER com entitlements APP_ACCESS confirmados. "
        "ADMIN e SALES são perfis internos e ficam isentos desta expectativa comercial. "
        "O resultado não participa do login e não revoga nem concede acesso."
    )
    account_audit = dict(account_entitlement_audit or {})
    if account_audit.get("schema") != "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1":
        account_audit = audit_account_entitlements(
            configured_users(),
            entitlements,
        )
    a1,a2,a3,a4 = st.columns(4)
    a1.metric("USER ativos", account_audit["active_user_accounts"])
    a2.metric("Com direito efetivo", account_audit["effective_user_accounts"])
    a3.metric(
        "Sem direito efetivo",
        account_audit["user_accounts_without_effective_entitlement"],
    )
    a4.metric(
        "Entitlements órfãos",
        account_audit["orphan_effective_entitlements"],
    )

    if account_audit["account_rows"]:
        audit_rows=[]
        labels={
            "ENTITLEMENT_EFFECTIVE":"OK · direito confirmado",
            "NO_EFFECTIVE_ENTITLEMENT":"REVISAR · sem direito confirmado",
            "DUPLICATE_EFFECTIVE_ENTITLEMENTS":"REVISAR · duplicidade",
            "INTERNAL_ROLE_EXEMPT":"INTERNO · isento",
            "ACCOUNT_INACTIVE":"CONTA INATIVA",
        }
        for row in account_audit["account_rows"]:
            audit_rows.append({
                "Conta":row["username"],
                "Perfil":row["role"],
                "Conta ativa":row["account_active"],
                "Entitlements efetivos":row["effective_entitlements"],
                "Auditoria":labels.get(row["state"],row["state"]),
            })
        st.dataframe(audit_rows,width="stretch",hide_index=True)
    else:
        st.info(
            "Nenhuma conta segura configurada foi encontrada para a auditoria. "
            "Isso não é tratado como cliente confirmado."
        )

    if account_audit["orphan_rows"]:
        with st.expander("Entitlements efetivos sem conta correspondente",expanded=False):
            st.dataframe(
                [{
                    "Entitlement":row["entitlement_id"],
                    "Referência":row["subject_ref"],
                    "Escopo":row["scope"],
                    "Estado":row["state"],
                } for row in account_audit["orphan_rows"]],
                width="stretch",
                hide_index=True,
            )

    if audit_requires_review(account_audit):
        st.warning(
            "A auditoria encontrou divergências para revisão administrativa. "
            "Nenhuma correção automática foi executada."
        )
    else:
        st.success(
            "Auditoria sem divergências comerciais detectadas no escopo APP_ACCESS. "
            "Enforcement continua desligado."
        )
    st.caption(
        "Enforcement: DESLIGADO · autenticação alterada: NÃO · provisionamento automático: NÃO · "
        "revogação automática: NÃO."
    )

    st.divider()
    st.markdown("#### 🧩 AION pessoal · isolamento por assinante")
    tenant_ready = tenant_readiness_summary(entitlements)
    tenant_policy = tenant_policy_snapshot()

    t1,t2,t3,t4 = st.columns(4)
    t1.metric("AION_PERSONAL", tenant_ready["personal_entitlements"])
    t2.metric("Ativos confirmados", tenant_ready["effective_confirmed"])
    t3.metric("Assinantes elegíveis", tenant_ready["effective_subjects"])
    t4.metric("Cross-tenant", "BLOQUEADO")

    duplicate_subjects = tenant_ready.get("duplicate_effective_subjects") or []
    if duplicate_subjects:
        st.warning(
            f"{len(duplicate_subjects)} referência(s) possuem mais de um entitlement AION_PERSONAL efetivo. "
            "Revisar duplicidade antes de qualquer ativação futura."
        )

    st.info(
        "Meu AION ainda NÃO está ativado para assinantes nesta tela. "
        "Este painel apenas audita a prontidão do isolamento; não cria tenant, não grava memória pessoal "
        "e não provisiona acesso."
    )
    readiness_rows=[
        {"Controle":"Entitlement AION_PERSONAL confirmado","Estado":f"{tenant_ready['effective_confirmed']} efetivo(s)"},
        {"Controle":"Memória ADMIN herdada","Estado":"NÃO" if not tenant_policy["admin_memory_inherited"] else "REVISAR"},
        {"Controle":"Documentos privados do projeto herdados","Estado":"NÃO" if not tenant_policy["project_docs_inherited"] else "REVISAR"},
        {"Controle":"Acesso a outro tenant","Estado":"BLOQUEADO" if not tenant_policy["cross_tenant_access"] else "REVISAR"},
        {"Controle":"Persistência pessoal em produção","Estado":"NÃO CONFIRMADA"},
        {"Controle":"Provedor externo automático","Estado":"DESLIGADO" if not tenant_policy["external_provider_enabled_by_default"] else "REVISAR"},
        {"Controle":"Cobrança automática","Estado":"DESLIGADA" if not tenant_policy["billing_enabled"] else "REVISAR"},
        {"Controle":"Trading real","Estado":"BLOQUEADO" if not tenant_policy["real_trading_enabled"] else "REVISAR"},
    ]
    st.dataframe(readiness_rows,width="stretch",hide_index=True)
    st.caption(
        "Prontidão somente leitura · subscriber shell: DESLIGADO · persistência runtime pessoal: NÃO CONFIRMADA · "
        "provisionamento automático: NÃO."
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
    provider = provider_status(feature_flags=flags, env=_provider_env())
    memory_summary = canonical_memory_summary()
    cfg = _runtime_config()
    runtime_result = load_runtime_checkpoint(cfg, timeout=6.0)
    merged = merged_checkpoint(runtime_result)
    source_checkpoint = merged["checkpoint"]
    checkpoint = _working_checkpoint(source_checkpoint)
    entitlement_section = (
        checkpoint.get("entitlements")
        if isinstance(checkpoint.get("entitlements"), Mapping)
        else {}
    )
    entitlement_records = list(entitlement_section.get("records", []) or [])
    account_entitlement_audit = audit_account_entitlements(
        configured_users(),
        entitlement_records,
    )
    status_board = build_master_status_board(
        checkpoint=checkpoint,
        runtime_result=runtime_result,
        provider=provider,
        feature_flags=flags,
        system_context=system,
        market_context=market,
        account_entitlement_audit=account_entitlement_audit,
        working_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
    )
    approval_inbox = collect_approval_inbox(checkpoint)

    _render_header(
        access_map,
        str(runtime_result.get("status") or "UNKNOWN"),
        str(provider.get("state") or "UNKNOWN"),
        system,
    )
    _render_executive_grid(memory_summary, runtime_result, provider, market)

    selected_workspace = st.selectbox(
        "Área AION",
        AION_WORKSPACES,
        key="aion_admin_workspace",
        help=(
            "Carrega uma área administrativa por vez. Isso reduz a carga da interface "
            "e evita montar workspaces não selecionados no celular."
        ),
    )
    st.caption("AION Admin · navegação estável · uma área por vez · Guardian permanece ativo.")

    workspace_error_type = ""
    try:
        if selected_workspace == "🧠 Central":
            _render_central(access_map, checkpoint, runtime_result, memory_summary, flags, system, status_board, approval_inbox)
        elif selected_workspace == "🗂️ Secretaria":
            _render_secretary(access_map, checkpoint, flags, system, market, status_board, approval_inbox)
        elif selected_workspace == "📈 Trading":
            _render_trading(market)
        elif selected_workspace == "🎬 Studio":
            _render_studio(access_map, checkpoint, flags)
        elif selected_workspace == "💼 Negócios":
            _render_business(access_map, checkpoint, flags)
        elif selected_workspace == "🧪 Laboratório":
            _render_laboratory(access_map, checkpoint, flags)
        elif selected_workspace == "🛠️ Desenvolvimento":
            _render_development(access_map, checkpoint, source_checkpoint, runtime_result, flags)
        elif selected_workspace == "🎟️ Promoções":
            _render_promotions(
                access_map,
                checkpoint,
                flags,
                account_entitlement_audit,
            )
    except Exception as exc:
        workspace_error_type = type(exc).__name__
        st.error(
            "Esta área do AION encontrou um erro isolado. "
            "A Central e as demais áreas continuam disponíveis."
        )
        st.caption(
            f"Diagnóstico seguro: {workspace_error_type}. "
            "Nenhuma permissão operacional foi ampliada e nenhuma ação externa foi executada."
        )

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
        "status_board_counts": status_board.get("counts"),
        "status_board_has_unresolved": bool(status_board.get("has_unresolved")),
        "approval_inbox_total": int(approval_inbox.get("total") or 0),
        "approval_inbox_has_pending": bool(approval_inbox.get("has_pending")),
        "commercial_access_audit_needs_review": audit_requires_review(account_entitlement_audit),
        "selected_workspace": selected_workspace,
        "workspace_status": "ERROR_ISOLATED" if workspace_error_type else "OK",
        "workspace_error_type": workspace_error_type,
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "AION_WORKSPACES", "render_aion_admin_console", "AION_ADMIN_CSS"]
