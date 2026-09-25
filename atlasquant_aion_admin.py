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
    guardian_posture,
    is_admin,
    mission_plan,
    route_context,
)
from atlasquant_aion_gateway import local_answer, provider_status
from atlasquant_aion_memory import (
    canonical_memory_summary,
    checkpoint_digest,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    config_from_mapping,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    merged_checkpoint,
    runtime_write_preflight,
    save_runtime_checkpoint,
    search_canonical_memory,
    update_business_checkpoint,
    update_entitlements_checkpoint,
    update_continuity_checkpoint,
    update_learning_checkpoint,
    update_wisdom_checkpoint,
    update_live_event_journal_checkpoint,
    update_operating_checkpoint,
    update_promotions_checkpoint,
    update_studio_checkpoint,
)
from atlasquant_aion_recovery import (
    list_checkpoint_revisions,
    load_checkpoint_revision,
    recovery_preflight,
    restore_checkpoint_revision,
)
from atlasquant_aion_continuity import (
    MISSION_STATUSES,
    append_handoff,
    build_session_handoff,
    continuity_briefing,
    continuity_summary,
    new_mission,
    transition_mission,
    upsert_mission,
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
from atlasquant_aion_tenant_privacy import (
    tenant_privacy_policy_snapshot,
    tenant_privacy_readiness,
)
from atlasquant_aion_incident_center import (
    collect_incidents,
    incident_center_rows,
    incident_response_plan,
)
from atlasquant_aion_executive_pulse import (
    compact_attention_rows,
    executive_pulse,
)
from atlasquant_navigation_bridge import request_surface_revalidation
from atlasquant_interface_validation import interface_validation_mission
from atlasquant_release_gate import release_gate, release_gate_rows
from atlasquant_aion_intelligence import (
    commander_briefing,
    evidence_audit,
    evidence_confidence,
    scenario_events,
    simulate_macro_scenario,
)
from atlasquant_aion_reliability import reliability_snapshot
from atlasquant_aion_fortress import (
    cyber_immune_plan,
    emergency_cutoff_posture,
    instruction_boundary,
    proof_of_safety,
    source_authority,
)
from atlasquant_aion_portable import (
    central_entry_contract,
    portable_core_summary,
)
from atlasquant_aion_vault import vault_summary
from atlasquant_aion_cognitive_orchestrator import orchestrator_snapshot
from atlasquant_aion_event_journal import (
    continuity_summary as live_event_continuity_summary,
    merge_events as merge_live_event_journal_events,
    normalize_heartbeats as normalize_live_event_heartbeats,
)
from atlasquant_aion_learning import (
    CAUSE_TAGS as LEARNING_CAUSE_TAGS,
    FORECAST_TYPES as LEARNING_FORECAST_TYPES,
    RESEARCH_KINDS as LEARNING_RESEARCH_KINDS,
    confidence_calibration,
    error_pattern_summary,
    evaluate_learning_experiment,
    learning_summary,
    new_learning_episode,
    new_learning_experiment,
    new_research_reference,
    settle_learning_episode,
    upsert_learning_episode,
    upsert_learning_experiment,
)
from atlasquant_aion_wisdom import (
    TRUTH_STATES as WISDOM_TRUTH_STATES,
    candidate_from_learning_episode,
    new_wisdom_entry,
    upsert_wisdom_entry,
    wisdom_evidence_hits,
    wisdom_review_state,
    wisdom_summary,
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
    "🔐 Assinaturas",
    "🎟️ Promoções",
)
_WORKING_CHECKPOINT_KEY = "aion_working_checkpoint_v2"
_WORKING_SOURCE_KEY = "aion_working_checkpoint_source_digest"
_WORKING_DIRTY_KEY = "aion_working_checkpoint_dirty"
_WORKING_CONFLICT_KEY = "aion_working_checkpoint_conflict"
_AION_WORKSPACE_JUMP_KEY = "aion_admin_workspace_jump"

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
.aion-workspace-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:9px 0 16px}
.aion-workspace-card{border:1px solid rgba(126,177,218,.2);border-radius:15px;padding:12px 13px;background:rgba(8,24,43,.72);min-height:104px}
.aion-workspace-card .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.aion-workspace-card strong{color:#fff;font-size:.88rem;line-height:1.2}
.aion-workspace-card p{color:#cbd9e9;font-size:.72rem;line-height:1.38;margin:7px 0 0}
.aion-state{border-radius:999px;padding:3px 7px;font-size:.61rem;font-weight:900;letter-spacing:.05em;white-space:nowrap}
.aion-state.ok{color:#73f1da;background:rgba(34,112,99,.25);border:1px solid rgba(115,241,218,.26)}
.aion-state.info{color:#b9d8ff;background:rgba(52,92,145,.25);border:1px solid rgba(137,190,255,.24)}
.aion-state.warn{color:#ffd56b;background:rgba(132,91,20,.24);border:1px solid rgba(255,213,107,.26)}
.aion-state.blocked{color:#ffc2c2;background:rgba(120,45,55,.24);border:1px solid rgba(255,160,170,.24)}
.aion-pulse{border:1px solid rgba(132,207,255,.28);border-radius:18px;padding:15px 16px;margin:8px 0 14px;background:linear-gradient(145deg,rgba(10,28,50,.96),rgba(8,20,37,.97));box-shadow:0 12px 34px rgba(0,0,0,.16)}
.aion-pulse-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.aion-pulse-kicker{color:#9fb8d7;font-size:.68rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
.aion-pulse-title{color:#fff;font-size:1rem;font-weight:950;line-height:1.25;margin-top:3px;overflow-wrap:anywhere}
.aion-pulse-detail{color:#e2edf9;font-size:.78rem;line-height:1.45;margin-top:7px}
.aion-pulse-next{color:#dffbf5;font-size:.78rem;line-height:1.45;margin-top:8px}
.aion-pulse-badge{border-radius:999px;padding:5px 9px;font-size:.66rem;font-weight:950;letter-spacing:.06em;white-space:nowrap;border:1px solid rgba(255,255,255,.16)}
.aion-pulse-badge.critical{color:#ffd6d6;background:rgba(132,38,52,.34)}
.aion-pulse-badge.attention{color:#ffe7a3;background:rgba(130,89,18,.32)}
.aion-pulse-badge.review{color:#cde7ff;background:rgba(45,87,133,.33)}
.aion-pulse-badge.controlled{color:#bff8e9;background:rgba(32,111,94,.3)}
.aion-pulse-badge.unknown{color:#e6eaf0;background:rgba(83,92,108,.32)}
.aion-pulse-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px}
.aion-pulse-stat{border:1px solid rgba(137,187,225,.18);border-radius:12px;padding:9px 10px;background:rgba(13,34,58,.72);min-width:0}
.aion-pulse-stat small{display:block;color:#c3d5e9;font-size:.63rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.aion-pulse-stat strong{display:block;color:#fff;font-size:.86rem;margin-top:3px;overflow-wrap:anywhere}
.aion-card small,.aion-workspace-card p{color:#d8e6f5}
.aion-card span{color:#e2ebf6;font-size:.76rem}
.aion-workspace-card p{font-size:.76rem}
@media (prefers-reduced-motion:reduce){.aion-orb{animation:none!important}}
@media(max-width:760px){
 .aion-shell{padding:18px 16px;border-radius:18px}.aion-orb{width:58px;height:58px;right:16px;top:20px}
 .aion-sub{padding-right:64px;font-size:.8rem}.aion-grid{grid-template-columns:1fr 1fr}.aion-card{padding:11px 12px}
 .aion-workspace-grid{grid-template-columns:1fr 1fr}.aion-workspace-card{min-height:98px;padding:10px 11px}
 .aion-pulse-grid{grid-template-columns:1fr 1fr}.aion-pulse{padding:13px 12px}.aion-pulse-top{gap:8px}
}
@media(max-width:430px){
 .aion-workspace-grid{grid-template-columns:1fr}
 .aion-pulse-grid{grid-template-columns:1fr}
 .aion-pulse-top{display:block}.aion-pulse-badge{display:inline-block;margin-top:8px}
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


def _unknown_account_entitlement_audit(error_type: str) -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_ENTITLEMENT_ACCOUNT_AUDIT_V1",
        "truth_state": "UNKNOWN",
        "reason": str(error_type or "UNKNOWN")[:120],
        "scope": "APP_ACCESS",
        "accounts_total": 0,
        "active_user_accounts": 0,
        "effective_user_accounts": 0,
        "user_accounts_without_effective_entitlement": 0,
        "duplicate_effective_user_accounts": 0,
        "orphan_effective_entitlements": 0,
        "account_rows": [],
        "orphan_rows": [],
        "enforcement_enabled": False,
        "authentication_changed": False,
        "automatic_provisioning": False,
        "automatic_revocation": False,
        "real_trading_changed": False,
    }


def _unknown_status_board(error_type: str) -> dict[str, Any]:
    item = {
        "id": "aion_foundation_degraded",
        "label": "Painel Mestre de Estado",
        "area": "central",
        "state": "UNKNOWN",
        "detail": "Painel Mestre indisponível nesta execução; nenhum estado positivo foi inferido.",
        "source": f"AION safe fallback · {str(error_type or 'UNKNOWN')[:120]}",
        "next_action": "Recarregar a área e revisar a camada auxiliar antes de qualquer ação sensível.",
        "executes_action": False,
    }
    return {
        "schema": "ATLASQUANT_AION_MASTER_STATUS_V1",
        "states": ["CONFIRMED", "BLOCKED", "EXTERNAL_DEPENDENCY", "UNKNOWN"],
        "items": [item],
        "counts": {
            "CONFIRMED": 0,
            "BLOCKED": 0,
            "EXTERNAL_DEPENDENCY": 0,
            "UNKNOWN": 1,
        },
        "attention": [item],
        "has_unresolved": True,
        "real_orders_enabled": False,
        "automatic_external_actions": False,
    }


def _unknown_approval_inbox(error_type: str) -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_APPROVAL_INBOX_V1",
        "status": "UNKNOWN",
        "reason": str(error_type or "UNKNOWN")[:120],
        "items": [],
        "total": 0,
        "by_kind": {},
        "by_priority": {},
        "has_pending": False,
        "next_items": [],
        "automatic_approval": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


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



def _workspace_overview_items(
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
) -> list[dict[str, str]]:
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    tasks = list(operating.get("tasks", []) or [])
    task_summary = queue_summary(tasks)

    studio = checkpoint.get("studio") if isinstance(checkpoint.get("studio"), Mapping) else {}
    business = checkpoint.get("business") if isinstance(checkpoint.get("business"), Mapping) else {}
    promotions = checkpoint.get("promotions") if isinstance(checkpoint.get("promotions"), Mapping) else {}
    entitlements = checkpoint.get("entitlements") if isinstance(checkpoint.get("entitlements"), Mapping) else {}

    projects = list(studio.get("projects", []) or [])
    products = list(business.get("products", []) or [])
    campaigns = list(promotions.get("campaigns", []) or [])
    records = list(entitlements.get("records", []) or [])
    runtime_status = str(runtime_result.get("status") or "UNKNOWN").upper()

    runtime_tone = "ok" if runtime_status == "CONFIRMED" else "warn"
    return [
        {
            "name": "🧠 Central",
            "state": "ATIVA",
            "tone": "ok",
            "detail": "Comando, memória, estado mestre e perguntas ao AION.",
        },
        {
            "name": "🗂️ Secretaria",
            "state": f"{int(task_summary.get('active') or 0)} ATIVAS",
            "tone": "info",
            "detail": "Tarefas, pendências, aprovações e briefing executivo.",
        },
        {
            "name": "📈 Trading",
            "state": "REAL BLOQUEADO",
            "tone": "blocked",
            "detail": "Leitura e contexto podem existir; ordens reais continuam bloqueadas.",
        },
        {
            "name": "🎬 Studio",
            "state": f"{len(projects)} PROJETOS",
            "tone": "info",
            "detail": "Conteúdo, roteiros e preparação de publicação com aprovação.",
        },
        {
            "name": "💼 Negócios",
            "state": f"{len(products)} CANDIDATOS",
            "tone": "info",
            "detail": "Produtos, margem, fornecedores e evidências de tendência.",
        },
        {
            "name": "🧪 Laboratório",
            "state": "GUARDIAN ATIVO",
            "tone": "ok",
            "detail": "Sandbox, feature flags, orçamento e testes antes de promoção.",
        },
        {
            "name": "🛠️ Desenvolvimento",
            "state": runtime_status,
            "tone": runtime_tone,
            "detail": "Missões de código e Checkpoint Mestre com persistência verificada.",
        },
        {
            "name": "🔐 Assinaturas",
            "state": f"{len(records)} REGISTROS",
            "tone": "info",
            "detail": "Entitlements, auditoria de acesso e isolamento por assinante.",
        },
        {
            "name": "🎟️ Promoções",
            "state": f"{len(campaigns)} CAMPANHAS",
            "tone": "info",
            "detail": "Cupons, trials e descontos separados do direito de acesso.",
        },
    ]


def _render_workspace_overview(
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
) -> None:
    st.markdown("#### Mapa Operacional AION")
    st.caption(
        "Visão rápida das 9 áreas administrativas. O mapa é somente leitura: "
        "não aprova, publica, cobra, provisiona acesso nem envia ordens."
    )
    cards = []
    for item in _workspace_overview_items(checkpoint, runtime_result):
        cards.append(
            '<div class="aion-workspace-card">'
            '<div class="top">'
            f'<strong>{escape(item["name"])}</strong>'
            f'<span class="aion-state {escape(item["tone"])}">{escape(item["state"])}</span>'
            '</div>'
            f'<p>{escape(item["detail"])}</p>'
            '</div>'
        )
    st.markdown(
        '<div class="aion-workspace-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )



_AION_AREA_LABELS = {
    "central": "🧠 Central",
    "secretary": "🗂️ Secretaria",
    "trading": "📈 Trading",
    "studio": "🎬 Studio",
    "business": "💼 Negócios",
    "laboratory": "🧪 Laboratório",
    "development": "🛠️ Desenvolvimento",
    "subscriptions": "🔐 Assinaturas",
    "promotions": "🎟️ Promoções",
    "memory": "🛠️ Desenvolvimento",
    "system": "🛠️ Desenvolvimento",
}


def _aion_area_label(area: Any) -> str:
    raw = str(area or "central").strip().casefold()
    return _AION_AREA_LABELS.get(raw, str(area or "🧠 Central"))


def _attention_queue(
    status_board: Mapping[str, Any] | None,
    approval_inbox: Mapping[str, Any] | None,
    critical_surfaces: Mapping[str, Any] | None = None,
    release_gate_snapshot: Mapping[str, Any] | None = None,
    *,
    limit: int = 8,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    inbox = dict(approval_inbox or {})
    if str(inbox.get("status") or "CONFIRMED").upper() != "UNKNOWN":
        for item in list(inbox.get("next_items", []) or []):
            if not isinstance(item, Mapping):
                continue
            rows.append({
                "priority": str(item.get("priority") or "P2"),
                "source": "APROVAÇÃO",
                "area": _aion_area_label(item.get("area")),
                "item": str(item.get("title") or item.get("item_id") or "Item sem título"),
                "state": str(item.get("status") or "WAITING_APPROVAL"),
                "next_action": "Revisar na área indicada; nenhuma aprovação é automática.",
            })

    gate = dict(release_gate_snapshot or {})
    gate_state = str(gate.get("state") or "").upper()
    gate_available = bool(gate_state)
    if gate_available and gate_state != "COMPLETE":
        rows.append({
            "priority": "P1" if gate_state == "BLOCKED" else "P2",
            "source": "RELEASE GATE",
            "area": "🛠️ Desenvolvimento",
            "item": str(
                gate.get("next_label")
                or "Gate de liberação AION"
            ),
            "state": gate_state,
            "next_action": str(
                gate.get("next_action")
                or "Revisar a próxima etapa do Gate de liberação AION."
            ),
        })

    # Compatibility fallback for callers that still provide only surface health.
    # When the unified release gate exists, individual surface alerts remain in
    # the diagnostic panel instead of duplicating the administrative queue.
    if not gate_available:
        surface_snapshot = dict(critical_surfaces or {})
        for item in list(surface_snapshot.get("items", []) or []):
            if not isinstance(item, Mapping):
                continue
            state = str(item.get("state") or "UNKNOWN").upper()
            if state == "OK":
                continue
            priority = "P1" if state in {"DEGRADED", "UNAVAILABLE"} else "P2"
            rows.append({
                "priority": priority,
                "source": "TELA",
                "area": "🛠️ Desenvolvimento",
                "item": str(item.get("label") or item.get("id") or "Tela crítica"),
                "state": state,
                "next_action": str(
                    item.get("next_action")
                    or "Revalidar a tela no build atual antes de concluir que está saudável."
                ),
            })

    board = dict(status_board or {})
    for item in list(board.get("attention", []) or []):
        if not isinstance(item, Mapping):
            continue
        next_action = str(item.get("next_action") or "").strip()
        if not next_action:
            continue
        state = str(item.get("state") or "UNKNOWN").upper()
        priority = "P1" if state == "UNKNOWN" else ("P2" if state == "EXTERNAL_DEPENDENCY" else "P3")
        rows.append({
            "priority": priority,
            "source": "ESTADO",
            "area": _aion_area_label(item.get("area")),
            "item": str(item.get("label") or item.get("id") or "Estado sem rótulo"),
            "state": state,
            "next_action": next_action,
        })

    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    rows.sort(key=lambda row: (
        rank.get(str(row.get("priority") or "P3"), 9),
        0 if row.get("source") == "APROVAÇÃO" else 1,
        str(row.get("area") or ""),
        str(row.get("item") or ""),
    ))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("source") or ""),
            str(row.get("area") or ""),
            str(row.get("item") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= max(1, int(limit)):
            break
    return deduped


def _render_attention_queue(
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
    critical_surfaces: Mapping[str, Any] | None = None,
    release_gate_snapshot: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("#### Próxima Ação AION")
    st.caption(
        "Fila consolidada de atenção. Ela orienta o administrador, mas não aprova, "
        "não publica, não cobra, não provisiona acesso e não executa trading."
    )
    rows = _attention_queue(
        status_board,
        approval_inbox,
        critical_surfaces,
        release_gate_snapshot,
    )
    if not rows:
        st.success(
            "Nenhuma ação administrativa imediata foi identificada nas evidências atuais. "
            "Isso não substitui validação externa de produção."
        )
        return

    first = rows[0]
    st.info(
        f"**{first['priority']} · {first['area']} · {first['item']}** — "
        f"{first['next_action']}"
    )
    st.dataframe(
        [{
            "Prioridade": row["priority"],
            "Origem": row["source"],
            "Área": row["area"],
            "Item": row["item"],
            "Estado": row["state"],
            "Próxima ação segura": row["next_action"],
        } for row in rows],
        width="stretch",
        hide_index=True,
    )


def _render_memory_security_posture(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    flags: Mapping[str, bool],
) -> None:
    st.markdown("#### Memória & Guardian")
    st.caption(
        "Auditoria somente leitura da integridade do Checkpoint e da postura de segurança. "
        "Este painel não serve como aprovação para nenhuma ação sensível."
    )

    persisted = (
        runtime_result.get("integrity")
        if isinstance(runtime_result.get("integrity"), Mapping)
        else {"state": "UNKNOWN", "matched": 0, "total": 0}
    )
    working = checkpoint_integrity_report(checkpoint)
    preflight = runtime_write_preflight(runtime_result)
    posture = guardian_posture(access, feature_flags=flags)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Integridade runtime", str(persisted.get("state") or "UNKNOWN"))
    c2.metric(
        "Memória de trabalho",
        str(working.get("state") or "UNKNOWN"),
        delta=f"V{int(working.get('checkpoint_version') or 0)}",
    )
    c3.metric("Guardian bloqueando agora", int(posture.get("blocked_now") or 0))
    c4.metric("Escrita runtime", "ELEGÍVEL" if preflight.get("allowed") else "BLOQUEADA")

    portable = portable_core_summary(
        checkpoint.get("portable_core")
        if isinstance(checkpoint.get("portable_core"), Mapping)
        else {}
    )
    vault = vault_summary(
        checkpoint.get("vault")
        if isinstance(checkpoint.get("vault"), Mapping)
        else {}
    )
    entry = central_entry_contract(authenticated_admin=is_admin(access))
    p1,p2,p3,p4 = st.columns(4)
    p1.metric("AION Portable", f"{int(portable.get('workspaces') or 0)} workspaces")
    p2.metric("Conectores prontos", int(portable.get("ready_connectors") or 0))
    p3.metric("Vault", "SEGURO" if vault.get("policy_ok") else "BLOQUEADO")
    p4.metric("Entrada única", "PRONTA" if entry.get("allowed") else "BLOQUEADA")
    st.caption(
        "AtlasQuant é um workspace do AION. O Vault armazena referências e integridade, "
        "não senha/token em texto puro. Entrada única exige sessão ADMIN."
    )

    persisted_state = str(persisted.get("state") or "UNKNOWN").upper()
    if persisted_state == "MISMATCH":
        st.error(
            "Divergência de digest detectada no Checkpoint persistido. "
            "A escrita fica bloqueada até revisão; o AION não sobrescreve esse estado automaticamente."
        )
    elif persisted_state == "MIGRATION_REQUIRED":
        st.warning(
            "Checkpoint persistido requer migração estrutural para a versão canônica atual. "
            "A migração só poderá ser salva por escrita condicional e aprovação explícita."
        )
    elif persisted_state == "CONFIRMED":
        st.success(
            f"Integridade persistida confirmada em "
            f"{int(persisted.get('matched') or 0)}/{int(persisted.get('total') or 0)} componentes."
        )
    else:
        st.info(
            "Integridade persistida ainda não está confirmada nesta execução. "
            "A memória local não será tratada como prova de persistência."
        )

    rows = []
    for item in list(posture.get("actions", []) or []):
        if not isinstance(item, Mapping):
            continue
        rows.append({
            "Ação sensível": item.get("action"),
            "Risco": item.get("risk"),
            "Estado agora": "PERMITIDA" if item.get("allowed_now") else "BLOQUEADA",
            "Flag": item.get("feature_flag") or "—",
            "Motivo": item.get("reason"),
        })
    if rows:
        with st.expander("Matriz Guardian · ações sensíveis", expanded=False):
            st.dataframe(rows, width="stretch", hide_index=True)
            st.caption(
                "A matriz é calculada com approved=False. Ela nunca reutiliza esta visualização "
                "como autorização para publicar, cobrar, fazer deploy, gravar segredo ou operar."
            )

    with st.expander("AION Portable Core & Vault", expanded=False):
        st.markdown("**Workspaces registrados:**")
        for item in list(
            ((checkpoint.get("portable_core") or {}) if isinstance(checkpoint.get("portable_core"), Mapping) else {}).get("workspaces", [])
            or []
        )[:20]:
            if isinstance(item, Mapping):
                st.caption(
                    f"{item.get('label')} · {item.get('kind')} · {item.get('state')} · "
                    f"contexto isolado: {'SIM' if item.get('isolated_context') else 'NÃO'}"
                )
        st.markdown("**Política do Vault:**")
        st.caption(
            f"Entradas: {int(vault.get('entries') or 0)} · "
            f"backend: {vault.get('backend_state','NOT_CONFIGURED')} · "
            f"segredo em texto puro: {'SIM — BLOQUEAR' if vault.get('plaintext_secrets_present') else 'NÃO'}."
        )
        st.caption(
            "O próprio AION não pode apagar o Vault, ampliar permissão ou transformar referência "
            "de segredo em valor exportável."
        )


def _render_security_incident_center(
    snapshot: Mapping[str, Any],
) -> None:
    st.markdown("#### 🛡️ Centro de Segurança & Incidentes")
    st.caption(
        "Consolida somente sinais explícitos desta execução e eventos do Checkpoint. "
        "O painel não faz contenção, rollback, rotação de segredo, alteração de conta ou trading."
    )
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Incidentes", int(snapshot.get("total") or 0))
    c2.metric("Críticos", int(counts.get("CRITICAL") or 0))
    c3.metric("Altos", int(counts.get("HIGH") or 0))
    c4.metric(
        "Rollback",
        "REVISAR" if snapshot.get("rollback_review_recommended") else "SEM SINAL CONFIRMADO",
    )

    rows = incident_center_rows(snapshot)
    if not rows:
        st.success(
            "Nenhum incidente explícito foi consolidado nesta execução. "
            "Isso não prova que produção/infraestrutura externa estejam saudáveis."
        )
        return

    st.dataframe(rows,width="stretch",hide_index=True)

    incidents=[
        dict(item)
        for item in list(snapshot.get("incidents",[]) or [])
        if isinstance(item,Mapping)
    ]
    incident_ids=[str(item.get("incident_id") or "") for item in incidents]
    labels={
        str(item.get("incident_id") or ""):
        f"{item.get('severity')} · {item.get('title')} · {str(item.get('incident_id') or '')[:10]}"
        for item in incidents
    }
    selected_id=st.selectbox(
        "Incidente para revisar",
        incident_ids,
        format_func=lambda value: labels.get(value,value),
        key="aion_incident_review_selected",
    )
    selected=next(
        (item for item in incidents if str(item.get("incident_id") or "")==selected_id),
        None,
    )
    if isinstance(selected,Mapping):
        st.write(f"**Origem:** {selected.get('source')} · **Evidência:** {selected.get('evidence_state')}")
        st.caption(str(selected.get("detail") or ""))
        plan=incident_response_plan(selected)
        with st.expander("Plano de resposta seguro",expanded=False):
            for idx,step in enumerate(plan.get("steps",[]),start=1):
                st.markdown(f"{idx}. {step}")
            st.caption(
                "Plano somente leitura · revisão humana obrigatória · rollback automático: NÃO · "
                "rotação automática de segredo: NÃO · trading real: BLOQUEADO."
            )

    if snapshot.get("rollback_review_recommended"):
        reasons=list(snapshot.get("rollback_reasons",[]) or [])
        st.warning(
            "Há sinal confirmado para **revisão humana de rollback**. "
            "Isso não dispara rollback automaticamente."
        )
        for reason in reasons[:8]:
            st.markdown(f"- {reason}")


def _render_continuity_center(
    checkpoint: Mapping[str, Any],
) -> None:
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    operating = checkpoint.get("operating") if isinstance(checkpoint.get("operating"), Mapping) else {}
    briefing = continuity_briefing(
        missions,
        handoffs,
        tasks=list(operating.get("tasks", []) or []),
        events=list(operating.get("events", []) or []),
        checkpoint_digest=checkpoint_digest(checkpoint),
    )
    summary = briefing.get("mission_summary") if isinstance(briefing.get("mission_summary"), Mapping) else {}

    st.markdown("#### 🧭 Continuidade & Handoff")
    st.caption(
        "Visão derivada do Checkpoint Mestre carregado nesta sessão. "
        "Handoff persistido tem prioridade; na ausência dele, o AION sintetiza somente a partir de missões/tarefas registradas."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Missões ativas", int(summary.get("active_missions") or 0))
    c2.metric("Concluídas", int(summary.get("done_missions") or 0))
    c3.metric("Bloqueadas", int(summary.get("blocked_missions") or 0))
    c4.metric("Handoffs", int(summary.get("handoff_count") or 0))

    source = str(briefing.get("source") or "UNKNOWN")
    if source == "PERSISTED_HANDOFF":
        st.success("Continuidade baseada no último handoff registrado no Checkpoint.")
    else:
        st.info(
            "Ainda não há handoff persistido; a visão abaixo foi sintetizada do estado estruturado atual. "
            "Ela não inventa etapas concluídas."
        )

    focus = str(briefing.get("current_focus") or "").strip()
    if focus:
        st.write(f"**Onde paramos:** {focus}")
    else:
        st.write("**Onde paramos:** nenhuma missão ativa registrada no Checkpoint.")

    completed = list(briefing.get("recent_completed") or [])
    blockers = list(briefing.get("blockers") or [])
    next_steps = list(briefing.get("next_steps") or [])
    if completed:
        with st.expander("Últimas conclusões", expanded=False):
            for item in completed[:8]:
                st.markdown(f"- {item}")
    if blockers:
        with st.expander("Bloqueios registrados", expanded=False):
            for item in blockers[:8]:
                st.markdown(f"- {item}")
    if next_steps:
        st.markdown("**Próximos passos registrados:**")
        for item in next_steps[:8]:
            st.markdown(f"- {item}")


def _render_executive_pulse(snapshot: Mapping[str, Any]) -> None:
    posture = str(snapshot.get("posture") or "UNKNOWN").upper()
    primary = snapshot.get("primary") if isinstance(snapshot.get("primary"), Mapping) else {}
    badge_class = posture.casefold() if posture.casefold() in {"critical","attention","review","controlled","unknown"} else "unknown"
    title = escape(str(primary.get("title") or "Sem prioridade definida"))
    detail = escape(str(primary.get("detail") or ""))
    next_action = escape(str(primary.get("next_action") or ""))
    area = escape(str(primary.get("area") or "🧠 Central"))
    st.markdown(
        f"""
<div class="aion-pulse">
  <div class="aion-pulse-top">
    <div>
      <div class="aion-pulse-kicker">Pulso Executivo AION · {area}</div>
      <div class="aion-pulse-title">{title}</div>
      <div class="aion-pulse-detail">{detail}</div>
      <div class="aion-pulse-next"><strong>Próxima ação segura:</strong> {next_action}</div>
    </div>
    <span class="aion-pulse-badge {badge_class}">{escape(posture)}</span>
  </div>
  <div class="aion-pulse-grid">
    <div class="aion-pulse-stat"><small>Runtime</small><strong>{escape(str(snapshot.get("runtime_status") or "UNKNOWN"))}</strong></div>
    <div class="aion-pulse-stat"><small>Integridade</small><strong>{escape(str(snapshot.get("integrity_state") or "UNKNOWN"))}</strong></div>
    <div class="aion-pulse-stat"><small>Aprovações</small><strong>{int(snapshot.get("approval_count") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Incidentes</small><strong>{int(snapshot.get("incident_count") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Missões ativas</small><strong>{int(snapshot.get("active_missions") or 0)}</strong></div>
    <div class="aion-pulse-stat"><small>Telas do build</small><strong>{int(snapshot.get("interface_validation_confirmed") or 0)}/{int(snapshot.get("interface_validation_total") or 3)}</strong></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    recommended = str(snapshot.get("recommended_workspace") or "")
    if recommended in AION_WORKSPACES and recommended != "🧠 Central":
        if st.button(
            f"↗️ Abrir área recomendada · {recommended}",
            key="aion_open_recommended_workspace",
            width="stretch",
        ):
            st.session_state[_AION_WORKSPACE_JUMP_KEY] = recommended
            st.rerun()
    rows = compact_attention_rows(snapshot)
    if len(rows) > 1:
        with st.expander("Outros itens priorizados", expanded=False):
            st.dataframe(rows, width="stretch", hide_index=True)


def _render_commander_intelligence(
    checkpoint: Mapping[str, Any],
    system_context: Mapping[str, Any],
    executive_snapshot: Mapping[str, Any],
) -> None:
    snapshot = (
        system_context.get("commander_snapshot")
        if isinstance(system_context.get("commander_snapshot"), Mapping)
        else commander_briefing(
            checkpoint=checkpoint,
            system_context=system_context,
            executive_snapshot=executive_snapshot,
        )
    )
    audit = snapshot.get("audit") if isinstance(snapshot.get("audit"), Mapping) else {}
    confidence = (
        snapshot.get("evidence_confidence")
        if isinstance(snapshot.get("evidence_confidence"), Mapping)
        else {}
    )

    st.markdown("#### 🧭 Modo Comandante")
    st.caption(
        "Organiza missão, bloqueios e próxima ação usando somente evidência disponível. "
        "Não executa reparo, deploy, publicação nem trading."
    )
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Postura", str(snapshot.get("posture") or "UNKNOWN"))
    c2.metric("Missões ativas", int(snapshot.get("active_missions") or 0))
    c3.metric("Gate", str(snapshot.get("release_gate_state") or "UNKNOWN"))
    c4.metric(
        "Confiança da evidência",
        f"{int(confidence.get('score') or 0)}/100",
        delta=str(confidence.get("label") or "SEM_EVIDENCIA"),
    )
    st.info(
        f"**Objetivo atual:** {snapshot.get('objective') or 'não confirmado'}\n\n"
        f"**Próxima ação:** {snapshot.get('next_action') or 'não confirmada'}"
    )
    blockers = list(snapshot.get("blockers") or [])
    if blockers:
        st.warning("Bloqueios confirmados: " + " · ".join(str(x) for x in blockers[:4]))

    with st.expander("🔎 AION Auditor · Evidências", expanded=False):
        counts = audit.get("counts") if isinstance(audit.get("counts"), Mapping) else {}
        a1,a2,a3,a4 = st.columns(4)
        a1.metric("Confirmadas", int(counts.get("CONFIRMED") or 0))
        a2.metric("Inferências", int(counts.get("INFERENCE") or 0))
        a3.metric("Hipóteses", int(counts.get("HYPOTHESIS") or 0))
        a4.metric("Desconhecidas", int(counts.get("UNKNOWN") or 0))
        st.caption(
            f"Fontes independentes: {int(audit.get('independent_sources') or 0)} · "
            f"conflitos: {int(audit.get('conflict_count') or 0)} · "
            "o score acima mede qualidade da evidência, não probabilidade de lucro."
        )
        rows = []
        for row in list(audit.get("rows", []) or []):
            if not isinstance(row, Mapping):
                continue
            rows.append({
                "Afirmação": str(row.get("claim") or ""),
                "Estado": str(row.get("kind") or "UNKNOWN"),
                "Fonte": str(row.get("source") or "unknown"),
                "Valor": str(row.get("value") or ""),
            })
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        if int(audit.get("conflict_count") or 0):
            st.error(
                "O Auditor encontrou evidências confirmadas conflitantes. "
                "A confiança é automaticamente limitada e o AION não escolhe um lado escondido."
            )


def _render_reliability_governance(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    reliability = (
        system.get("reliability")
        if isinstance(system.get("reliability"), Mapping)
        else {}
    )
    st.markdown("#### 🛡️ Reliability & Governance")
    st.caption(
        "Data Guardian + Source Mesh + reconciliação de fontes + Cost Guardian + proteção da memória + "
        "modo degradado + rollback consultivo. Nenhuma correção, compra, deploy ou rollback é automático."
    )
    source_mesh = (
        system.get("source_mesh")
        if isinstance(system.get("source_mesh"), Mapping)
        else {}
    )
    if source_mesh:
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Source Mesh", str(source_mesh.get("market_state") or "UNKNOWN"))
        m2.metric("Observações", int(source_mesh.get("observation_count") or 0))
        m3.metric("Confirmadas", int(source_mesh.get("confirmed_observations") or 0))
        m4.metric("Fallback/indisp.", int(source_mesh.get("fallback_or_unavailable") or 0))
        families = (
            source_mesh.get("families")
            if isinstance(source_mesh.get("families"), Mapping)
            else {}
        )
        if families:
            st.caption(
                "Famílias observadas: "
                + " · ".join(f"{name}: {count}" for name,count in sorted(families.items()))
            )
        if bool(source_mesh.get("market_live_confirmed", False)):
            st.success(
                "Mercado ao vivo confirmado pelo Source Mesh: Matriz ao vivo + Autopilot + "
                "scanner/mapa + Twelve Data passaram juntos."
            )
        else:
            st.info(
                "Mercado ao vivo NÃO foi confirmado pelo Source Mesh nesta execução. "
                "Snapshot/fallback pode manter contexto, mas não vira evidência ao vivo."
            )
    if not reliability:
        st.warning("Camada de confiabilidade não confirmada nesta execução.")
        return

    data = (
        reliability.get("data_guardian")
        if isinstance(reliability.get("data_guardian"), Mapping)
        else {}
    )
    cost = (
        reliability.get("cost_guardian")
        if isinstance(reliability.get("cost_guardian"), Mapping)
        else {}
    )
    memory = (
        reliability.get("memory_protection")
        if isinstance(reliability.get("memory_protection"), Mapping)
        else {}
    )
    degraded = (
        reliability.get("degraded_mode")
        if isinstance(reliability.get("degraded_mode"), Mapping)
        else {}
    )
    rollback = (
        reliability.get("rollback_governance")
        if isinstance(reliability.get("rollback_governance"), Mapping)
        else {}
    )
    reconciliation = (
        data.get("reconciliation")
        if isinstance(data.get("reconciliation"), Mapping)
        else {}
    )

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Postura", str(reliability.get("posture") or "UNKNOWN"))
    c2.metric("Modo", str(degraded.get("state") or "UNKNOWN"))
    c3.metric("Memória", str(memory.get("state") or "UNKNOWN"))
    c4.metric("Custo", str(cost.get("state") or "UNKNOWN"))

    conflicts = int(reconciliation.get("conflict_count") or 0)
    critical_conflicts = int(reconciliation.get("critical_conflict_count") or 0)
    advisory_bad = int(data.get("advisory_bad_sources") or 0)
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("Conflitos de fonte", conflicts)
    r2.metric("Conflitos críticos", critical_conflicts)
    r3.metric("Rollback", str(rollback.get("state") or "STANDBY"))
    r4.metric("Ordens reais", "BLOQUEADAS")
    if advisory_bad:
        st.caption(
            f"{advisory_bad} fonte(s) LOW/MEDIUM estão em aviso. "
            "Elas continuam visíveis, mas não derrubam sozinhas a postura crítica do sistema."
        )

    if str(degraded.get("state") or "").upper()=="FAIL_CLOSED":
        st.error(
            "Reliability Guardian em FAIL-CLOSED: capacidades sensíveis permanecem bloqueadas "
            "até que a evidência crítica seja reconciliada."
        )
    elif str(degraded.get("state") or "").upper()=="DEGRADED_SAFE":
        st.warning(
            "Modo degradado seguro ativo. O AION pode explicar e organizar evidências, "
            "mas não deve promover estados não confirmados."
        )
    else:
        st.success(
            "Nenhum bloqueio crítico foi consolidado por esta camada. "
            "Isso não substitui validação externa nem autorização operacional."
        )

    if conflicts:
        st.warning(
            "Há fontes confirmadas divergentes. O AION não escolhe uma delas silenciosamente; "
            "a afirmação permanece em CONFLICT até reconciliação verificável."
        )

    observations = [
        row for row in list(reconciliation.get("observations") or [])
        if isinstance(row, Mapping)
    ]
    if observations:
        with st.expander("Fontes e evidências observadas", expanded=False):
            st.dataframe([
                {
                    "Família":row.get("family"),
                    "Fonte":row.get("source"),
                    "Afirmação":row.get("claim"),
                    "Estado":row.get("state"),
                    "Verdade":row.get("truth_state"),
                    "Criticidade":row.get("criticality"),
                    "Idade min":row.get("age_minutes"),
                    "Máx. min":row.get("max_age_minutes"),
                    "Quota %":row.get("quota_remaining_pct"),
                }
                for row in observations
            ], width="stretch", hide_index=True)

    actions = [str(x) for x in list(reliability.get("next_actions") or []) if str(x).strip()]
    if actions:
        st.markdown("**Próximas ações seguras:**")
        for action in actions[:8]:
            st.markdown(f"- {action}")

    st.caption(
        "Failover automático: NÃO · reparo automático: NÃO · rollback automático: NÃO · "
        "fallback pago automático: NÃO."
    )


def _render_live_event_intelligence(
    checkpoint: Mapping[str, Any],
    system_context: Mapping[str, Any] | None,
    *,
    allow_memory_sync: bool = True,
) -> None:
    system = dict(system_context or {})
    live = (
        system.get("live_event_intelligence")
        if isinstance(system.get("live_event_intelligence"), Mapping)
        else {}
    )
    st.markdown("#### 🌐 AION Live Event Intelligence")
    st.caption(
        "Radar de eventos macro/notícias/geopolítica a partir das fontes já disponíveis no AtlasQuant. "
        "Manchete observada não vira fato confirmado automaticamente; impacto de mercado é sempre hipótese."
    )
    if not live:
        st.warning("Live Event Intelligence não foi confirmado nesta execução.")
        return

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estado", str(live.get("state") or "UNKNOWN"))
    c2.metric("Eventos", int(live.get("event_count") or 0))
    c3.metric("Alertas", int(live.get("alert_count") or 0))
    c4.metric("Urgentes p/ revisão", int(live.get("urgent_review_count") or 0))

    background_state = str(live.get("background_watch_state") or "NOT_STARTED")
    heartbeat_count = int(live.get("background_heartbeat_count") or 0)
    coverage = live.get("background_coverage_minutes")
    max_gap = live.get("background_max_gap_minutes")
    b1,b2,b3,b4 = st.columns(4)
    b1.metric("Watch background", background_state)
    b2.metric("Heartbeats", heartbeat_count)
    b3.metric(
        "Cobertura",
        "—" if coverage is None else f"{float(coverage)/60.0:.1f} h",
    )
    b4.metric(
        "Maior lacuna",
        "—" if max_gap is None else f"{float(max_gap):.0f} min",
    )
    source_state = str(live.get("news_source_state") or "UNKNOWN")
    age = live.get("news_payload_age_minutes")
    age_text = "—" if age is None else f"{float(age):.0f} min"
    st.caption(
        f"Fonte de notícias: {source_state} · idade do snapshot: {age_text} · "
        f"notícias frescas classificadas: {int(live.get('fresh_news_events') or 0)}."
    )

    if bool(live.get("continuous_runtime_confirmed", False)):
        st.success(
            "Continuidade de background por ~24h confirmada pelos heartbeats persistidos do runtime. "
            "Isso confirma o ciclo observado, não garante disponibilidade futura."
        )
    else:
        st.info(
            "Motor de alerta preparado, mas monitoramento 24/7 contínuo ainda NÃO está confirmado. "
            "A prova exige aproximadamente 24h de heartbeats persistidos, densidade mínima e sem lacunas excessivas."
        )

    top = [
        item for item in list(live.get("top_alerts", []) or [])
        if isinstance(item, Mapping)
    ]
    if not top:
        st.caption(
            "Nenhum evento fresco atingiu o limiar de alerta nesta leitura. "
            "Fonte stale ou indisponível não gera breaking alert."
        )

    for idx,item in enumerate(top[:5]):
        level = str(item.get("alert_level") or "WATCH")
        headline = str(item.get("headline") or "Evento sem título")
        truth = str(item.get("truth_state") or "UNKNOWN")
        urgency = int(item.get("urgency_score") or 0)
        category = str(item.get("category") or "OTHER")
        if level == "URGENT_REVIEW":
            st.warning(f"**{level} · {urgency}/100 · {category}** — {headline}")
        else:
            st.info(f"**{level} · {urgency}/100 · {category}** — {headline}")
        st.caption(
            f"Verdade do evento: {truth} · fontes: {int(item.get('source_count') or 0)} · "
            f"moedas relacionadas: {', '.join(item.get('currencies') or []) or 'não mapeadas'}."
        )
        with st.expander(f"Impacto hipotético · evento {idx+1}", expanded=False):
            channels = [
                row for row in list(item.get("impact_channels", []) or [])
                if isinstance(row, Mapping)
            ]
            if channels:
                st.dataframe([
                    {
                        "Ativo/canal":row.get("asset"),
                        "Possível reação":row.get("direction"),
                        "Mecanismo":row.get("mechanism"),
                        "Estado":row.get("truth_state"),
                    }
                    for row in channels
                ], width="stretch", hide_index=True)
            st.caption(
                "Isto é hipótese de transmissão de mercado, não previsão garantida nem sinal de trade. "
                "Preço, contexto e fontes adicionais precisam confirmar a leitura."
            )

    journal_count = int(live.get("journal_event_count") or 0)
    delivery_count = int(live.get("delivery_candidate_count") or 0)
    st.caption(
        f"Histórico runtime deduplicado: {journal_count} evento(s) · "
        f"fila interna de entrega futura: {delivery_count} candidato(s). "
        "Canal externo conectado: NÃO."
    )

    memory = (
        checkpoint.get("live_event_journal")
        if isinstance(checkpoint.get("live_event_journal"), Mapping)
        else {}
    )
    memory_events = list(memory.get("events", []) or [])
    memory_heartbeats = list(memory.get("heartbeats", []) or [])
    memory_watch = live_event_continuity_summary(memory_heartbeats)
    st.caption(
        f"Checkpoint Mestre: {len(memory_events)} evento(s) · "
        f"{len(memory_heartbeats)} heartbeat(s) · estado {memory_watch.get('state','NOT_STARTED')}."
    )

    if allow_memory_sync and st.button(
        "Sincronizar histórico de eventos com o Checkpoint Mestre",
        key="aion_live_event_journal_sync",
        width="stretch",
    ):
        runtime_events = [
            dict(x) for x in list(live.get("journal_events", []) or [])
            if isinstance(x, Mapping)
        ]
        runtime_heartbeats = [
            dict(x) for x in list(live.get("journal_heartbeats", []) or [])
            if isinstance(x, Mapping)
        ]
        merged_events = merge_live_event_journal_events(
            memory_events,
            runtime_events,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        heartbeat_rows = normalize_live_event_heartbeats(
            memory_heartbeats + runtime_heartbeats
        )
        updated = update_live_event_journal_checkpoint(
            checkpoint,
            events=merged_events,
            heartbeats=heartbeat_rows,
            dirty=True,
        )
        updated = _record_working_event(
            updated,
            "live_event_journal_synced",
            "Histórico Live Event sincronizado com o Checkpoint Mestre.",
            evidence={
                "events":len(merged_events),
                "heartbeats":len(heartbeat_rows),
                "external_delivery_allowed":False,
                "real_orders_enabled":False,
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success(
            "Histórico sincronizado na memória de trabalho. "
            "Salve o Checkpoint Mestre para persistir."
        )
        st.rerun()

    st.caption(
        "Fila externa: DESLIGADA · notificação automática: NÃO · "
        "autorização de trade: NÃO · ordens reais: BLOQUEADAS."
    )


def _aion_memory_hits(
    question: Any,
    checkpoint: Mapping[str, Any] | None,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Combine canonical project memory with reviewed Wisdom Journal evidence."""
    q = str(question or "").strip()
    if not q:
        return []
    canonical = [
        dict(x) for x in search_canonical_memory(q, limit=max(1, min(limit, 5)))
        if isinstance(x, Mapping)
    ]
    cp = dict(checkpoint or {})
    wisdom = cp.get("wisdom") if isinstance(cp.get("wisdom"), Mapping) else {}
    knowledge = wisdom_evidence_hits(
        q,
        list(wisdom.get("entries", []) or []),
        limit=max(1, min(limit, 4)),
    )
    combined = canonical + knowledge
    return combined[: max(1, min(int(limit or 8), 12))]


def _render_learning_pulse(checkpoint: Mapping[str, Any]) -> None:
    learning = checkpoint.get("learning") if isinstance(checkpoint.get("learning"), Mapping) else {}
    episodes = list(learning.get("episodes", []) or [])
    experiments = list(learning.get("experiments", []) or [])
    research_refs = list(learning.get("research_refs", []) or [])
    summary = learning_summary(episodes, experiments, research_refs)
    wisdom = checkpoint.get("wisdom") if isinstance(checkpoint.get("wisdom"), Mapping) else {}
    wisdom_state = wisdom_summary(list(wisdom.get("entries", []) or []))
    st.markdown("#### 🧠 Evolução Controlada")
    st.caption(
        "O AION melhora medindo previsões e resultados, não mudando regras sozinho. "
        "Toda promoção continua dependente de evidência e revisão humana."
    )
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Aprendizados", int(summary.get("episodes") or 0))
    c2.metric("Resultados fechados", int(summary.get("settled_episodes") or 0))
    c3.metric("Pesquisa vinculada", int(summary.get("research_references") or 0))
    c4.metric("Sabedoria ativa", int(wisdom_state.get("active") or 0))
    c5.metric("Challengers p/ revisão", int(summary.get("human_review_candidates") or 0))
    match_rate = summary.get("observed_match_rate_pct")
    gap = summary.get("calibration_gap_pct")
    st.caption(
        "Acerto observado: "
        + ("—" if match_rate is None else f"{float(match_rate):.1f}%")
        + " · gap de calibração: "
        + ("—" if gap is None else f"{float(gap):.1f}%")
        + f" · estado: {summary.get('calibration_state','INSUFFICIENT')}."
    )
    if int(summary.get("errors_without_confirmed_cause") or 0):
        st.info(
            f"{int(summary.get('errors_without_confirmed_cause') or 0)} erro(s) ainda sem causa confirmada. "
            "Eles permanecem como lacuna de conhecimento, não como explicação inventada."
        )
    st.caption(
        "Autoajuste de pesos: DESATIVADO · promoção automática: DESATIVADA · trading real: BLOQUEADO."
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
    if str(inbox.get("status") or "CONFIRMED").upper() == "UNKNOWN":
        st.warning(
            "A Central de Aprovações não pôde ser confirmada nesta execução. "
            "Nenhuma ausência de item será tratada como prova de que não há aprovações pendentes."
        )
        return
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



def _critical_surface_rows(system_context: Mapping[str, Any] | None) -> list[dict[str, str]]:
    system = dict(system_context or {})
    snapshot = (
        system.get("critical_surfaces")
        if isinstance(system.get("critical_surfaces"), Mapping)
        else {}
    )
    rows: list[dict[str, str]] = []
    for item in list(snapshot.get("items", []) or []):
        if not isinstance(item, Mapping):
            continue
        state = str(item.get("state") or "UNKNOWN").upper()
        if state not in {"OK", "DEGRADED", "UNAVAILABLE", "STALE_BUILD", "UNKNOWN"}:
            state = "UNKNOWN"
        rows.append({
            "Tela": str(item.get("label") or item.get("id") or "Tela não identificada"),
            "Estado": state,
            "Build observado": str(item.get("build_id") or "—"),
            "Build atual": str(item.get("current_build") or "—"),
            "Diagnóstico": str(item.get("error_type") or "—"),
            "Próxima ação": str(item.get("next_action") or "Revalidar a tela."),
        })
    return rows


def _short_commit(value: Any) -> str:
    raw = str(value or "").strip()
    return raw[:8] if raw else "—"


def _render_release_gate(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    gate = (
        system.get("release_gate")
        if isinstance(system.get("release_gate"), Mapping)
        else release_gate(
            publication_truth=(
                system.get("publication_truth")
                if isinstance(system.get("publication_truth"), Mapping)
                else {}
            ),
            interface_validation=(
                system.get("interface_validation")
                if isinstance(system.get("interface_validation"), Mapping)
                else {}
            ),
        )
    )

    st.markdown("#### Gate de liberação AION")
    st.caption(
        "Quatro provas independentes: código/bundle, telas críticas, runtime × main e produção. "
        "Uma etapa não confirma a seguinte e este painel não executa deploy."
    )
    c1,c2,c3 = st.columns(3)
    c1.metric("Gate", str(gate.get("state") or "UNKNOWN"))
    c2.metric(
        "Etapas confirmadas",
        f"{int(gate.get('confirmed_stages') or 0)}/{int(gate.get('total_stages') or 4)}",
    )
    c3.metric("Liberação", "CONFIRMADA" if gate.get("release_claim_allowed") else "PENDENTE")

    st.progress(
        min(1.0, max(0.0, float(gate.get("progress_pct") or 0.0) / 100.0)),
        text=f"Progresso do gate · {float(gate.get('progress_pct') or 0.0):.1f}%",
    )

    rows = release_gate_rows(gate)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)

    gate_state = str(gate.get("state") or "UNKNOWN").upper()
    if gate_state == "COMPLETE" and gate.get("release_claim_allowed"):
        st.success(
            "As quatro etapas possuem evidência suficiente para a afirmação de liberação. "
            "Isso não dispara nenhuma ação externa."
        )
    elif gate_state == "BLOCKED":
        st.error(
            f"Gate bloqueado em **{gate.get('next_label') or 'etapa não identificada'}**. "
            f"{gate.get('next_action') or ''}"
        )
    else:
        st.warning(
            f"Gate ainda não concluído. Próxima etapa: **{gate.get('next_label') or 'não confirmada'}**. "
            f"{gate.get('next_action') or ''}"
        )
    st.caption(
        "Deploy automático: BLOQUEADO · ordens reais: BLOQUEADAS · "
        "qualquer ação no Render continua exigindo fluxo separado."
    )


def _render_publication_truth(system_context: Mapping[str, Any] | None) -> None:
    system = dict(system_context or {})
    publication = (
        system.get("publication_truth")
        if isinstance(system.get("publication_truth"), Mapping)
        else {}
    )
    st.markdown("#### Estado de publicação")
    st.caption(
        "Separa código em execução, identidade da main e validação de produção. "
        "Merge no GitHub não é tratado como prova de que o Render já está atualizado."
    )
    if not publication:
        st.warning(
            "Não há evidência de publicação disponível nesta execução. "
            "O AION mantém produção como não confirmada."
        )
        return

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estado", str(publication.get("state") or "UNKNOWN"))
    c2.metric("Runtime", _short_commit(publication.get("runtime_commit")))
    c3.metric("Main esperada", _short_commit(publication.get("expected_main_commit")))
    c4.metric("Produção", str(publication.get("production_verification") or "UNKNOWN"))

    main_match = str(publication.get("main_match") or "UNKNOWN")
    can_claim_live = bool(publication.get("can_claim_latest_main_live", False))
    if can_claim_live:
        st.success(
            "Há identidade suficiente para afirmar que o runtime corresponde à main esperada "
            "e que a produção foi explicitamente validada."
        )
    elif main_match == "MISMATCH":
        st.error(
            "O commit em execução diverge da main esperada. "
            "AION não considera esta versão atualizada."
        )
    else:
        st.warning(
            "A versão em execução ainda não tem prova suficiente para ser chamada de "
            "última main validada em produção."
        )
    st.caption(str(publication.get("next_action") or ""))


def _render_critical_surface_health(system_context: Mapping[str, Any] | None) -> None:
    st.markdown("#### Saúde das telas críticas")
    st.caption(
        "Estado observado nesta sessão para Radar principal, Radar avançado/Central Institucional "
        "e Painel Mestre. É diagnóstico de interface, não sinal de trade nem autorização operacional."
    )
    system = dict(system_context or {})
    snapshot = (
        system.get("critical_surfaces")
        if isinstance(system.get("critical_surfaces"), Mapping)
        else {}
    )
    mission = interface_validation_mission(snapshot)
    counts = snapshot.get("counts") if isinstance(snapshot.get("counts"), Mapping) else {}
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("OK", int(counts.get("OK") or 0))
    c2.metric(
        "Com problema",
        int(counts.get("DEGRADED") or 0) + int(counts.get("UNAVAILABLE") or 0),
    )
    c3.metric("Build antigo", int(counts.get("STALE_BUILD") or 0))
    c4.metric("Não observadas", int(counts.get("UNKNOWN") or 0))

    st.caption(
        f"Missão de validação deste build: {int(mission.get('confirmed') or 0)}/"
        f"{int(mission.get('total') or 3)} telas confirmadas · "
        f"estado {str(mission.get('state') or 'UNKNOWN')}."
    )
    st.progress(
        min(1.0, max(0.0, float(mission.get("progress_pct") or 0.0) / 100.0)),
        text=(
            "Validação da interface no build atual · "
            f"{float(mission.get('progress_pct') or 0.0):.1f}%"
        ),
    )
    if mission.get("next_label") and not mission.get("all_confirmed_current_build"):
        st.info(
            f"Próxima tela da missão: **{mission.get('next_label')}** — "
            f"{mission.get('next_action') or 'revalidar no build atual.'}"
        )

    rows = _critical_surface_rows(system)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.warning(
            "A saúde das telas críticas ainda não foi informada por esta execução. "
            "O AION não assume que as telas estão saudáveis."
        )
        return

    if bool(snapshot.get("all_ok", False)):
        st.success(
            "As três telas críticas foram observadas como OK nesta sessão. "
            "Isso não substitui a validação do deploy de produção."
        )
    else:
        st.warning(
            "Existe tela degradada, indisponível, ligada a build antigo ou ainda não observada. "
            "O AION mantém o estado como pendente até nova evidência no build atual."
        )

    unresolved = [
        item for item in list(snapshot.get("items", []) or [])
        if isinstance(item, Mapping)
        and str(item.get("state") or "UNKNOWN").upper() != "OK"
    ]
    if unresolved:
        st.markdown("**Revalidação guiada**")
        st.caption(
            "Cada botão apenas registra um pedido de navegação. A tela é aberta no próximo ciclo "
            "e precisa renderizar no build atual para virar evidência nova."
        )
        build_id = str(system.get("source_build") or snapshot.get("current_build") or "")
        for item in unresolved:
            surface = str(item.get("id") or "")
            label = str(item.get("label") or surface or "Tela crítica")
            state = str(item.get("state") or "UNKNOWN").upper()
            if st.button(
                f"🧪 Revalidar · {label} · {state}",
                key=f"aion_revalidate_surface_{surface}",
                width="stretch",
            ):
                try:
                    request_surface_revalidation(
                        st.session_state,
                        surface,
                        build_id=build_id,
                    )
                    st.rerun()
                except Exception as exc:
                    st.warning(
                        "Não foi possível registrar a navegação de revalidação. "
                        f"Diagnóstico: {type(exc).__name__}."
                    )

    last_result = (
        system.get("guided_revalidation")
        if isinstance(system.get("guided_revalidation"), Mapping)
        else {}
    )
    if last_result:
        result_state = str(last_result.get("state") or "UNKNOWN")
        label = str(last_result.get("label") or last_result.get("surface") or "tela")
        if result_state == "CONFIRMED_OK":
            st.success(
                f"Última revalidação guiada: {label} confirmado no build atual."
            )
        elif result_state in {"CONFIRMED_ERROR", "BUILD_CHANGED", "NAVIGATION_BLOCKED"}:
            st.warning(
                f"Última revalidação guiada: {label} terminou em {result_state}. "
                "O AION não trata esse resultado como saudável."
            )


def _render_central(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    runtime_result: Mapping[str, Any],
    memory_summary: Mapping[str, Any],
    flags: Mapping[str, bool],
    system_context: Mapping[str, Any],
    status_board: Mapping[str, Any],
    approval_inbox: Mapping[str, Any],
    incident_snapshot: Mapping[str, Any],
    executive_snapshot: Mapping[str, Any],
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

    view_mode = st.selectbox(
        "Visualização da Central",
        ("Essencial", "Completo"),
        key="aion_central_view_mode",
        help=(
            "Essencial prioriza o que exige atenção e reduz a rolagem no celular. "
            "Completo mostra todos os painéis técnicos."
        ),
    )
    _render_executive_pulse(executive_snapshot)
    _render_commander_intelligence(checkpoint, system_context, executive_snapshot)
    _render_live_event_intelligence(checkpoint, system_context, allow_memory_sync=True)
    _render_learning_pulse(checkpoint)
    _render_reliability_governance(system_context)
    _render_release_gate(system_context)
    _render_publication_truth(system_context)
    _render_critical_surface_health(system_context)

    if view_mode == "Completo":
        _render_workspace_overview(checkpoint, runtime_result)
        _render_attention_queue(
            status_board,
            approval_inbox,
            (system_context.get("critical_surfaces") if isinstance(system_context, Mapping) else None),
            (system_context.get("release_gate") if isinstance(system_context, Mapping) else None),
        )
        _render_memory_security_posture(access, checkpoint, runtime_result, flags)
        _render_security_incident_center(incident_snapshot)
        _render_continuity_center(checkpoint)
    else:
        st.caption(
            "Modo Essencial ativo: detalhes técnicos ficam ocultos para reduzir carga e rolagem. "
            "Nenhuma evidência ou proteção é desativada."
        )
        _render_attention_queue(
            status_board,
            approval_inbox,
            (system_context.get("critical_surfaces") if isinstance(system_context, Mapping) else None),
            (system_context.get("release_gate") if isinstance(system_context, Mapping) else None),
        )
        _render_continuity_center(checkpoint)
        if int(incident_snapshot.get("total") or 0) > 0 or bool(
            incident_snapshot.get("rollback_review_recommended")
        ):
            _render_security_incident_center(incident_snapshot)

    st.markdown("#### Briefing de entrada")
    st.write(
        f"Prioridade registrada: **{(checkpoint.get('aion') or {}).get('priority','não confirmada')}**. "
        f"Checkpoint: **{checkpoint_digest(checkpoint)}**. "
        f"Runtime: **{runtime_result.get('status','UNKNOWN')}**."
    )
    if pending and view_mode == "Completo":
        st.markdown("**Próximas pendências registradas:**")
        for item in pending[:8]:
            st.markdown(f"- {item}")

    if view_mode == "Completo":
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
    hits_preview = _aion_memory_hits(question, checkpoint) if question.strip() else []
    domain_preview = route_context(question).get("domain") if question.strip() else "central"
    cognitive_preview = orchestrator_snapshot(
        question,
        domain_hint=domain_preview,
        memory_hits=hits_preview,
        system_context=system_context,
    ) if question.strip() else {}
    if cognitive_preview:
        selected = [
            x for x in list((cognitive_preview.get("routing") or {}).get("selected", []) or [])
            if isinstance(x, Mapping)
        ]
        with st.expander("🧠 Conselho Cognitivo · especialistas + Critic", expanded=False):
            c1,c2,c3 = st.columns(3)
            c1.metric("Especialistas", int((cognitive_preview.get("routing") or {}).get("selected_count") or 0))
            c2.metric("Readiness", str(cognitive_preview.get("readiness") or "UNKNOWN"))
            c3.metric("Critic", "OBRIGATÓRIO" if bool((cognitive_preview.get("critic_gate") or {}).get("required", True)) else "NÃO")
            if selected:
                st.markdown("**Especialistas selecionados:** " + " · ".join(str(x.get("name") or x.get("id")) for x in selected))
            blockers = list((cognitive_preview.get("research_plan") or {}).get("blockers", []) or [])
            if blockers:
                for blocker in blockers:
                    st.warning(str(blocker))
            stages = list((cognitive_preview.get("research_plan") or {}).get("steps", []) or [])
            if stages:
                st.dataframe([
                    {"Etapa":row.get("stage"),"Regra":row.get("instruction")}
                    for row in stages if isinstance(row, Mapping)
                ], width="stretch", hide_index=True)
            st.caption(
                "O AION não mostra raciocínio privado/chain-of-thought. Ele mostra conclusão, evidências, "
                "conflitos, lacunas e justificativa verificável."
            )
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
        hits = _aion_memory_hits(question, checkpoint)
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
        cognitive_answer = answer.get("cognitive_orchestrator")
        if isinstance(cognitive_answer, Mapping):
            routing = (
                cognitive_answer.get("routing")
                if isinstance(cognitive_answer.get("routing"), Mapping)
                else {}
            )
            selected_names = [
                str(x.get("name") or "")
                for x in list(routing.get("selected", []) or [])
                if isinstance(x, Mapping) and str(x.get("name") or "").strip()
            ]
            if selected_names:
                st.caption("Conselho usado: " + " · ".join(selected_names[:5]) + " · Critic: obrigatório")
        evidence = answer.get("evidence")
        if isinstance(evidence, list) and evidence:
            with st.expander("Evidências da memória"):
                for hit in evidence:
                    review = str(hit.get("review_state") or "").strip()
                    suffix = f" · revisão {review}" if review else ""
                    st.caption(
                        f"{hit.get('path')} · verdade {hit.get('kind') or hit.get('truth_state') or 'UNKNOWN'}"
                        f" · score {hit.get('score')}{suffix}"
                    )
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
            ["central","trading","studio","business","laboratory","secretary","development","subscriptions","promotions"],
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

    st.markdown("#### Handoff da sessão")
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    handoff_preview = build_session_handoff(
        missions,
        tasks=tasks,
        events=events,
        checkpoint_digest=checkpoint_digest(checkpoint),
        source=str(access.get("username") or "ADMIN"),
    )
    st.caption(
        "O preview é montado apenas com o estado registrado no Checkpoint. "
        "Registrar o handoff grava a continuidade na memória de trabalho; persistência definitiva ainda exige salvar o Checkpoint."
    )
    h1,h2,h3 = st.columns(3)
    h1.metric("Foco", str(handoff_preview.get("current_focus") or "sem missão ativa")[:80])
    h2.metric("Bloqueios", len(list(handoff_preview.get("blockers") or [])))
    h3.metric("Próximos passos", len(list(handoff_preview.get("next_steps") or [])))
    if handoff_preview.get("next_steps"):
        st.markdown("**Próximos passos do handoff:**")
        for item in list(handoff_preview.get("next_steps") or [])[:8]:
            st.markdown(f"- {item}")

    if st.button(
        "📌 Registrar handoff no Checkpoint",
        key="aion_register_session_handoff",
        width="stretch",
    ):
        updated_handoffs = append_handoff(handoffs, handoff_preview)
        updated = update_continuity_checkpoint(
            checkpoint,
            missions=missions,
            handoffs=updated_handoffs,
            dirty=True,
        )
        updated = _record_working_event(
            updated,
            "session_handoff_recorded",
            "Handoff estruturado da sessão registrado na memória de trabalho.",
            evidence={
                "handoff_id":handoff_preview.get("handoff_id"),
                "current_focus":handoff_preview.get("current_focus"),
                "next_steps":len(list(handoff_preview.get("next_steps") or [])),
                "automatic_execution":False,
            },
        )
        _set_working_checkpoint(updated, dirty=True)
        st.success("Handoff registrado localmente. Salve o Checkpoint Mestre para persistir entre sessões.")
        st.rerun()

    with st.expander("Observabilidade / auditoria"):
        st.caption(
            f"Eventos: {obs['total']} · warnings {obs['by_severity']['WARNING']} · "
            f"errors {obs['by_severity']['ERROR']} · críticos {obs['by_severity']['CRITICAL']}"
        )
        if events:
            st.dataframe(list(reversed(events[-30:])), width="stretch", hide_index=True)
        else:
            st.write("Nenhum evento operacional registrado nesta memória.")


def _render_trading(
    market_context: Mapping[str, Any],
    system_context: Mapping[str, Any] | None = None,
) -> None:
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

    _render_live_event_intelligence({}, system_context, allow_memory_sync=False)

    st.markdown("#### 🧪 Simulador de Cenários Macro")
    st.caption(
        "Simula mecanismos possíveis a partir de uma surpresa hipotética. "
        "Não é previsão ao vivo, não é sinal e não representa probabilidade de lucro."
    )
    c_event,c_surprise = st.columns(2)
    event = c_event.selectbox(
        "Evento",
        scenario_events(),
        format_func=lambda x: {
            "CPI":"CPI / inflação",
            "PCE":"PCE",
            "PAYROLL":"Payroll / NFP",
            "FOMC":"FOMC / Fed",
            "GEOPOLITICAL_RISK":"Risco geopolítico",
        }.get(x,x),
        key="aion_macro_scenario_event",
    )
    surprise = c_surprise.selectbox(
        "Hipótese",
        ("ABOVE","BELOW"),
        format_func=lambda x: (
            "Acima / mais forte / hawkish / escalada"
            if x=="ABOVE"
            else "Abaixo / mais fraco / dovish / desescalada"
        ),
        key="aion_macro_scenario_surprise",
    )

    live_evidence = [{
        "claim":"market_context",
        "kind":"CONFIRMED" if bool(market_context.get("fresh_confirmed",False)) else "UNKNOWN",
        "source":"market_context",
        "value":market_text,
        "note":"Contexto fornecido à tela Trading.",
    }]
    scenario = simulate_macro_scenario(
        event,
        surprise,
        evidence=live_evidence,
    )
    sc_conf = (
        scenario.get("evidence_confidence")
        if isinstance(scenario.get("evidence_confidence"), Mapping)
        else {}
    )
    s1,s2,s3 = st.columns(3)
    s1.metric("Estado", str(scenario.get("scenario_truth_kind") or "UNKNOWN"))
    s2.metric("Evidência ao vivo", f"{int(sc_conf.get('score') or 0)}/100")
    s3.metric("Sinal de trade", "NÃO")
    st.write(f"**Cenário:** {scenario.get('headline') or 'não mapeado'}")
    channels = list(scenario.get("channels") or [])
    if channels:
        st.dataframe([
            {
                "Ativo/canal":row.get("asset"),
                "Possível reação":row.get("direction"),
                "Mecanismo":row.get("mechanism"),
                "Estado":row.get("truth_kind"),
            }
            for row in channels if isinstance(row, Mapping)
        ], width="stretch", hide_index=True)
    invalidators = list(scenario.get("invalidators") or [])
    if invalidators:
        with st.expander("O que pode invalidar ou inverter esse cenário"):
            for item in invalidators:
                st.markdown(f"- {item}")
    st.warning(
        "Antes de usar este cenário em leitura real, o AION precisa confirmar o dado divulgado, "
        "consenso, revisões, componentes internos, preço e contexto atual."
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
    incident_snapshot: Mapping[str, Any] | None = None,
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

    learning = checkpoint.get("learning") if isinstance(checkpoint.get("learning"), Mapping) else {}
    episodes = list(learning.get("episodes", []) or [])
    experiments = list(learning.get("experiments", []) or [])
    research_refs = list(learning.get("research_refs", []) or [])
    learning_state = learning_summary(episodes, experiments, research_refs)
    calibration_state = confidence_calibration(episodes)
    error_state = error_pattern_summary(episodes)
    wisdom = checkpoint.get("wisdom") if isinstance(checkpoint.get("wisdom"), Mapping) else {}
    wisdom_entries = list(wisdom.get("entries", []) or [])
    wisdom_state = wisdom_summary(wisdom_entries)

    st.markdown("#### 🧠 Aprendizado Controlado AION")
    st.caption(
        "Ciclo: registrar previsão → observar resultado → medir erro/acerto → revisar causa → "
        "calibrar confiança → testar Challenger fora da amostra → Shadow Mode → revisão humana. "
        "Nada altera peso, regra ou produção automaticamente."
    )
    l1,l2,l3,l4 = st.columns(4)
    l1.metric("Episódios", int(learning_state.get("episodes") or 0))
    l2.metric("Em aberto", int(learning_state.get("open_episodes") or 0))
    l3.metric("Erros observados", int(learning_state.get("errors") or 0))
    l4.metric(
        "Gap de calibração",
        "—" if learning_state.get("calibration_gap_pct") is None
        else f"{float(learning_state.get('calibration_gap_pct')):.1f}%",
    )
    st.caption(
        f"Calibração: {learning_state.get('calibration_state','INSUFFICIENT')} · "
        f"evidências de pesquisa referenciadas: {int(learning_state.get('research_references') or 0)} · "
        f"candidatos para revisão humana: {int(learning_state.get('human_review_candidates') or 0)}."
    )

    with st.expander("Registrar previsão / decisão para aprender depois", expanded=False):
        with st.form("aion_learning_new_episode", clear_on_submit=True):
            subject = st.text_input("Assunto", placeholder="Ex.: reação do USD ao Payroll")
            forecast_type = st.selectbox(
                "Tipo",
                list(LEARNING_FORECAST_TYPES),
                key="aion_learning_forecast_type",
            )
            prediction = st.text_input("Previsão / categoria", placeholder="Ex.: USD_UP")
            confidence_pct = st.slider(
                "Confiança da previsão (não é probabilidade de lucro)",
                0, 100, 50,
            )
            model_version = st.text_input("Versão do modelo / regra", value="AION")
            context_note = st.text_area("Contexto registrado", max_chars=1200)
            refs_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                placeholder="calendar:event-1, backtest:snapshot-3",
            )
            numeric_prediction = None
            numeric_tolerance = None
            if forecast_type == "NUMERIC":
                n1,n2 = st.columns(2)
                numeric_prediction = n1.number_input(
                    "Valor previsto", value=0.0, step=0.1,
                )
                numeric_tolerance = n2.number_input(
                    "Tolerância para considerar acerto", min_value=0.0, value=0.0, step=0.1,
                )
            create_episode = st.form_submit_button("Registrar episódio", type="primary")
        if create_episode:
            try:
                episode = new_learning_episode(
                    subject,
                    forecast_type=forecast_type,
                    prediction=prediction,
                    confidence_pct=confidence_pct,
                    model_version=model_version,
                    evidence_refs=[x.strip() for x in refs_text.split(",") if x.strip()],
                    context_note=context_note,
                    numeric_prediction=numeric_prediction,
                    numeric_tolerance=numeric_tolerance,
                    source=str(access.get("username") or "ADMIN"),
                )
                episodes = upsert_learning_episode(episodes, episode)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                updated = _record_working_event(
                    updated,
                    "learning_episode_registered",
                    f"Episódio de aprendizado registrado: {episode['subject']}",
                    evidence={
                        "episode_id":episode["episode_id"],
                        "forecast_type":episode["forecast_type"],
                        "automatic_rule_change":False,
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Episódio registrado na memória de trabalho. Salve o Checkpoint Mestre para persistir.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar o episódio: {type(exc).__name__}")

    open_episodes = [
        item for item in episodes
        if isinstance(item, Mapping) and str(item.get("state") or "").upper()=="OPEN"
    ]
    if open_episodes:
        with st.expander("Registrar resultado real / fechar episódio", expanded=False):
            episode_options = {
                f"{item.get('episode_id')} · {item.get('subject')}": item
                for item in open_episodes
            }
            selected_label = st.selectbox(
                "Episódio em aberto",
                list(episode_options.keys()),
                key="aion_learning_settle_episode",
            )
            selected_episode = episode_options[selected_label]
            with st.form("aion_learning_settle_form"):
                actual_outcome = st.text_input(
                    "Resultado real / categoria observada",
                    placeholder="Ex.: USD_DOWN",
                )
                actual_numeric = None
                if str(selected_episode.get("forecast_type") or "")=="NUMERIC":
                    actual_numeric = st.number_input(
                        "Valor real observado", value=0.0, step=0.1,
                    )
                cause = st.selectbox(
                    "Causa do erro, se houver",
                    list(LEARNING_CAUSE_TAGS),
                    index=list(LEARNING_CAUSE_TAGS).index("UNKNOWN"),
                )
                cause_confirmed = st.checkbox(
                    "A causa acima tem evidência confirmada",
                    value=False,
                    help="Sem esta confirmação o AION guarda a causa como hipótese/desconhecida, não como fato.",
                )
                outcome_note = st.text_area("Observação do resultado", max_chars=1200)
                settle_episode = st.form_submit_button("Fechar episódio", type="primary")
            if settle_episode:
                try:
                    settled = settle_learning_episode(
                        selected_episode,
                        actual_outcome=actual_outcome,
                        actual_numeric=actual_numeric,
                        error_cause=cause,
                        error_cause_confirmed=cause_confirmed,
                        outcome_note=outcome_note,
                    )
                    episodes = upsert_learning_episode(episodes, settled)
                    updated = update_learning_checkpoint(
                        checkpoint,
                        episodes=episodes,
                        experiments=experiments,
                        research_refs=research_refs,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "learning_episode_settled",
                        f"Episódio de aprendizado fechado: {settled['subject']}",
                        evidence={
                            "episode_id":settled["episode_id"],
                            "evaluation":settled["evaluation"],
                            "error_cause_truth":settled["error_cause_truth"],
                            "automatic_weight_change":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success("Resultado registrado sem alterar regras ou pesos automaticamente.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível fechar o episódio: {type(exc).__name__}")

    with st.expander("Registrar evidência de Backtest / Paper / Shadow", expanded=False):
        with st.form("aion_learning_research_ref", clear_on_submit=True):
            research_kind = st.selectbox("Tipo de evidência", list(LEARNING_RESEARCH_KINDS))
            research_ref_id = st.text_input(
                "ID / referência", placeholder="Ex.: snapshot-id ou arquivo/relatório",
            )
            research_strategy = st.text_input("Operacional / estratégia")
            research_summary_text = st.text_area("Resumo da evidência", max_chars=1000)
            save_research = st.form_submit_button("Vincular evidência")
        if save_research:
            try:
                ref = new_research_reference(
                    research_kind,
                    research_ref_id,
                    strategy=research_strategy,
                    summary=research_summary_text,
                )
                known_ids = {str(x.get("research_id") or "") for x in research_refs if isinstance(x, Mapping)}
                if ref["research_id"] not in known_ids:
                    research_refs.append(ref)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Evidência vinculada por referência; nenhum resultado de pesquisa alterou o gate ao vivo.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível vincular a evidência: {type(exc).__name__}")

    with st.expander("Champion × Challenger · promoção controlada", expanded=False):
        st.caption(
            "O Challenger nunca substitui o Champion automaticamente. Primeiro precisa de OOS, "
            "não degradação, Shadow Mode e depois revisão humana."
        )
        with st.form("aion_learning_new_experiment", clear_on_submit=True):
            champion_version = st.text_input("Champion atual")
            challenger_version = st.text_input("Challenger")
            rationale = st.text_area("Hipótese de melhoria", max_chars=1200)
            create_experiment = st.form_submit_button("Criar experimento")
        if create_experiment:
            try:
                experiment = new_learning_experiment(
                    champion_version,
                    challenger_version,
                    rationale=rationale,
                )
                experiments = upsert_learning_experiment(experiments, experiment)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success("Challenger registrado como hipótese. Produção não foi alterada.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível criar o experimento: {type(exc).__name__}")

        if experiments:
            exp_options = {
                f"{item.get('experiment_id')} · {item.get('champion_version')} → {item.get('challenger_version')}": item
                for item in experiments if isinstance(item, Mapping)
            }
            selected_exp_label = st.selectbox(
                "Experimento",
                list(exp_options.keys()),
                key="aion_learning_experiment_selected",
            )
            selected_exp = exp_options[selected_exp_label]
            with st.form("aion_learning_evaluate_experiment"):
                st.markdown("**Métricas fora da amostra / Shadow**")
                c1,c2 = st.columns(2)
                champ_exp = c1.number_input("Champion · expectancy R", value=0.0, step=0.01)
                chall_exp = c2.number_input("Challenger · expectancy R", value=0.0, step=0.01)
                c3,c4 = st.columns(2)
                champ_dd = c3.number_input("Champion · drawdown R", min_value=0.0, value=0.0, step=0.1)
                chall_dd = c4.number_input("Challenger · drawdown R", min_value=0.0, value=0.0, step=0.1)
                c5,c6 = st.columns(2)
                champ_cal = c5.number_input("Champion · erro calibração %", min_value=0.0, value=0.0, step=0.5)
                chall_cal = c6.number_input("Challenger · erro calibração %", min_value=0.0, value=0.0, step=0.5)
                c7,c8 = st.columns(2)
                champ_false = c7.number_input("Champion · falso alerta %", min_value=0.0, value=0.0, step=0.5)
                chall_false = c8.number_input("Challenger · falso alerta %", min_value=0.0, value=0.0, step=0.5)
                oos_samples = st.number_input("Amostras OOS do Challenger", min_value=0, value=0, step=10)
                shadow_eligible = st.checkbox("Shadow elegível para revisão manual", value=False)
                critical_mismatches = st.number_input("Divergências críticas no Shadow", min_value=0, value=0, step=1)
                evaluate_experiment = st.form_submit_button("Avaliar Challenger")
            if evaluate_experiment:
                evaluated = evaluate_learning_experiment(
                    selected_exp,
                    champion_metrics={
                        "expectancy_r":champ_exp,
                        "max_drawdown_r":champ_dd,
                        "calibration_error_pct":champ_cal,
                        "false_alert_rate_pct":champ_false,
                    },
                    challenger_metrics={
                        "oos_samples":oos_samples,
                        "expectancy_r":chall_exp,
                        "max_drawdown_r":chall_dd,
                        "calibration_error_pct":chall_cal,
                        "false_alert_rate_pct":chall_false,
                    },
                    shadow_summary={
                        "eligible_for_manual_review":shadow_eligible,
                        "critical_mismatches":critical_mismatches,
                    },
                )
                experiments = upsert_learning_experiment(experiments, evaluated)
                updated = update_learning_checkpoint(
                    checkpoint,
                    episodes=episodes,
                    experiments=experiments,
                    research_refs=research_refs,
                    dirty=True,
                )
                _set_working_checkpoint(updated, dirty=True)
                state = str(evaluated.get("state") or "UNKNOWN")
                if state=="HUMAN_REVIEW_CANDIDATE":
                    st.success("Challenger atingiu critérios mínimos para REVISÃO HUMANA. Promoção automática continua proibida.")
                else:
                    st.warning(f"Challenger permaneceu em {state}. Champion continua oficial.")
                st.rerun()

    if episodes:
        with st.expander("Diário de aprendizado", expanded=False):
            st.dataframe([
                {
                    "ID":item.get("episode_id"),
                    "Estado":item.get("state"),
                    "Assunto":item.get("subject"),
                    "Tipo":item.get("forecast_type"),
                    "Previsão":item.get("prediction"),
                    "Confiança":item.get("forecast_confidence_pct"),
                    "Resultado":item.get("actual_outcome"),
                    "Avaliação":item.get("evaluation"),
                    "Causa":item.get("error_cause"),
                    "Causa confirmada":item.get("error_cause_truth"),
                    "Versão":item.get("model_version"),
                }
                for item in reversed(episodes[-200:]) if isinstance(item, Mapping)
            ], width="stretch", hide_index=True)

    if calibration_state.get("samples"):
        with st.expander("Calibração da confiança", expanded=False):
            st.dataframe([
                {
                    "Faixa":row.get("band"),
                    "Amostras":row.get("samples"),
                    "Confiança média %":row.get("average_confidence_pct"),
                    "Acerto observado %":row.get("observed_accuracy_pct"),
                    "Gap %":row.get("absolute_calibration_gap_pct"),
                }
                for row in list(calibration_state.get("bands") or [])
            ], width="stretch", hide_index=True)
            st.caption(
                "Auto-recalibração de pesos: DESATIVADA. A taxa observada não é probabilidade de lucro futuro."
            )

    confirmed_causes = error_state.get("confirmed_cause_counts") if isinstance(error_state.get("confirmed_cause_counts"), Mapping) else {}
    if confirmed_causes:
        st.caption(
            "Causas de erro confirmadas mais recorrentes: "
            + " · ".join(f"{k}: {v}" for k,v in list(confirmed_causes.items())[:6])
        )
    if int(error_state.get("errors_without_confirmed_cause") or 0):
        st.info(
            f"{int(error_state.get('errors_without_confirmed_cause') or 0)} erro(s) ainda sem causa confirmada. "
            "O AION não inventará causalidade para preencher essa lacuna."
        )

    st.markdown("#### 📚 Diário de Sabedoria AION")
    st.caption(
        "Transforma experiência revisada em conhecimento auditável: o que foi aprendido, "
        "origem, estado de verdade, confiança, aplicação e quando precisa ser revisado. "
        "Sabedoria não altera regra, peso ou produção automaticamente."
    )
    w1,w2,w3,w4 = st.columns(4)
    w1.metric("Lições", int(wisdom_state.get("entries") or 0))
    w2.metric("Ativas", int(wisdom_state.get("active") or 0))
    w3.metric(
        "Confirmadas",
        int((wisdom_state.get("by_truth_state") or {}).get("CONFIRMED") or 0),
    )
    w4.metric("Revisão vencida", int(wisdom_state.get("review_due") or 0))

    with st.expander("Registrar uma lição revisada", expanded=False):
        with st.form("aion_wisdom_new_entry", clear_on_submit=True):
            wisdom_topic = st.text_input("Tema da lição")
            wisdom_domain = st.text_input("Domínio", value="general")
            wisdom_insight = st.text_area("O que foi aprendido", max_chars=1400)
            wisdom_truth = st.selectbox(
                "Estado de verdade",
                list(WISDOM_TRUTH_STATES),
                index=list(WISDOM_TRUTH_STATES).index("HYPOTHESIS"),
            )
            wisdom_confidence = st.slider(
                "Confiança no conhecimento (não é probabilidade de lucro)",
                0, 100, 50,
                key="aion_wisdom_confidence",
            )
            wisdom_refs_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                placeholder="repo:test-123, calendar:cpi-1",
            )
            wisdom_applies_text = st.text_input(
                "Aplica-se a (separado por vírgula)",
                placeholder="USD, macro, CPI",
            )
            wisdom_review_due = st.text_input(
                "Revisar em (ISO opcional)",
                placeholder="2026-12-31T00:00:00+00:00",
            )
            wisdom_validation_note = st.text_area(
                "Nota de validação",
                max_chars=1200,
            )
            save_wisdom = st.form_submit_button("Registrar no Diário de Sabedoria", type="primary")
        if save_wisdom:
            try:
                entry = new_wisdom_entry(
                    wisdom_topic,
                    wisdom_insight,
                    domain=wisdom_domain,
                    truth_state=wisdom_truth,
                    confidence_pct=wisdom_confidence,
                    evidence_refs=[x.strip() for x in wisdom_refs_text.split(",") if x.strip()],
                    applies_to=[x.strip() for x in wisdom_applies_text.split(",") if x.strip()],
                    validation_note=wisdom_validation_note,
                    validated_at=datetime.now(timezone.utc).isoformat(),
                    review_due_at=wisdom_review_due,
                    created_by=str(access.get("username") or "ADMIN"),
                )
                wisdom_entries = upsert_wisdom_entry(wisdom_entries, entry)
                updated = update_wisdom_checkpoint(
                    checkpoint,
                    entries=wisdom_entries,
                    dirty=True,
                )
                updated = _record_working_event(
                    updated,
                    "wisdom_entry_registered",
                    f"Lição registrada no Diário de Sabedoria: {entry['topic']}",
                    evidence={
                        "wisdom_id":entry["wisdom_id"],
                        "truth_state":entry["truth_state"],
                        "manual_review_required":True,
                        "automatic_rule_change":False,
                    },
                )
                _set_working_checkpoint(updated, dirty=True)
                st.success(
                    "Lição registrada na memória de trabalho. "
                    "Salve o Checkpoint Mestre para persistir."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível registrar a lição: {type(exc).__name__}")

    settled_for_wisdom = [
        item for item in episodes
        if isinstance(item, Mapping) and str(item.get("state") or "").upper()=="SETTLED"
    ]
    if settled_for_wisdom:
        with st.expander("Propor sabedoria a partir de um episódio fechado", expanded=False):
            wisdom_episode_options = {
                f"{item.get('episode_id')} · {item.get('subject')}": item
                for item in settled_for_wisdom[-200:]
            }
            wisdom_episode_label = st.selectbox(
                "Episódio SETTLED",
                list(wisdom_episode_options.keys()),
                key="aion_wisdom_episode_candidate",
            )
            wisdom_candidate_due = st.text_input(
                "Revisar candidato em (ISO opcional)",
                placeholder="2026-12-31T00:00:00+00:00",
                key="aion_wisdom_candidate_due",
            )
            if st.button(
                "Criar candidato de sabedoria",
                key="aion_wisdom_candidate_create",
                width="stretch",
            ):
                try:
                    candidate = candidate_from_learning_episode(
                        wisdom_episode_options[wisdom_episode_label],
                        created_by=str(access.get("username") or "ADMIN"),
                        review_due_at=wisdom_candidate_due,
                    )
                    wisdom_entries = upsert_wisdom_entry(wisdom_entries, candidate)
                    updated = update_wisdom_checkpoint(
                        checkpoint,
                        entries=wisdom_entries,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "wisdom_candidate_created",
                        f"Candidato de sabedoria criado: {candidate['topic']}",
                        evidence={
                            "wisdom_id":candidate["wisdom_id"],
                            "truth_state":candidate["truth_state"],
                            "source_episode_ids":candidate["source_episode_ids"],
                            "automatic_promotion":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success(
                        "Candidato criado. Ele não foi promovido a CONFIRMED automaticamente."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível criar o candidato: {type(exc).__name__}")

    if wisdom_entries:
        with st.expander("Ver Diário de Sabedoria", expanded=False):
            st.dataframe([
                {
                    "ID":item.get("wisdom_id"),
                    "Estado":item.get("state"),
                    "Tema":item.get("topic"),
                    "Domínio":item.get("domain"),
                    "Verdade":item.get("truth_state"),
                    "Confiança":item.get("confidence_pct"),
                    "Revisão":wisdom_review_state(item),
                    "Revisar em":item.get("review_due_at") or "—",
                    "Origem":", ".join(item.get("source_episode_ids") or []) or "manual",
                    "Evidências":len(item.get("evidence_refs") or []),
                }
                for item in reversed(wisdom_entries[-300:])
                if isinstance(item, Mapping)
            ], width="stretch", hide_index=True)
    st.caption(
        "Confirmação automática: NÃO · alteração de regra/peso: NÃO · "
        "promoção automática: NÃO · trading real: BLOQUEADO."
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

    st.markdown("#### 🛡️ Fortaleza & Soberania")
    external_ai = source_authority("EXTERNAL_AI")
    web_instruction = instruction_boundary(
        "WEB",
        contains_action_instruction=True,
    )
    admin_source = source_authority(
        "ADMIN",
        authenticated_admin=is_admin(access),
    )
    safety_preview = proof_of_safety(
        "deploy_production",
        access,
        approved=False,
        feature_flags=flags,
        source_kind="ADMIN",
        authenticated_admin=is_admin(access),
        scope="Prévia de deploy — nenhuma execução nesta tela.",
        artifacts=[],
        tests=[],
        rollback_plan="",
        uncertainty_pct=100,
        impact="CRITICAL",
        reversible=False,
        external_side_effects=True,
    )
    f1,f2,f3,f4 = st.columns(4)
    f1.metric("Outra IA", "CONTEÚDO" if not external_ai.get("can_issue_action") else "AUTORIDADE")
    f2.metric("Instrução web", str(web_instruction.get("state") or "UNKNOWN"))
    f3.metric("Admin autenticado", str(admin_source.get("authority") or "UNKNOWN"))
    f4.metric("Proof of Safety", str(safety_preview.get("state") or "UNKNOWN"))
    st.caption(
        "Site, documento, e-mail, tool output ou outra IA não ganham autoridade para comandar ferramentas. "
        "A origem é uma barreira determinística fora do modelo; o Guardian continua sendo obrigatório."
    )
    with st.expander("Ver bloqueios da prévia de segurança", expanded=False):
        blockers = list(safety_preview.get("blockers") or [])
        if blockers:
            for item in blockers:
                st.markdown(f"- {item}")
        st.caption(
            "Esta prévia usa approved=False, incerteza alta e nenhum teste/rollback. "
            "Ela demonstra fail-closed e não pode ser reutilizada como autorização."
        )

    st.markdown("#### Segurança / resposta a incidente")
    incident_data=dict(incident_snapshot or {})
    st.caption(
        f"Incidentes consolidados: {int(incident_data.get('total') or 0)} · "
        f"severidade máxima: {incident_data.get('highest_severity','INFO')} · "
        f"rollback automático: NÃO."
    )
    if incident_data.get("has_critical"):
        st.warning(
            "Há incidente crítico consolidado. O Laboratório permanece fail-closed; "
            "nenhuma feature externa é ativada como tentativa de diagnóstico."
        )

    emergency = emergency_cutoff_posture(
        critical_incident=bool(incident_data.get("has_critical", False)),
        policy_integrity_ok=None,
        permission_integrity_ok=None,
        secret_exposure_confirmed=False,
    )
    cyber = cyber_immune_plan(
        [],
        antivirus_or_edr_present=None,
    )
    st.caption(
        f"Kill-switch advisory: {emergency.get('state')} · "
        f"Cyber Immune: {cyber.get('posture')} · "
        "contenção automática: NÃO · antivírus/EDR não é desativado pelo AION."
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

    st.markdown("#### Missões persistentes")
    continuity = checkpoint.get("continuity") if isinstance(checkpoint.get("continuity"), Mapping) else {}
    missions = list(continuity.get("missions", []) or [])
    handoffs = list(continuity.get("handoffs", []) or [])
    mission_summary = continuity_summary(missions, handoffs)
    mc1,mc2,mc3,mc4 = st.columns(4)
    mc1.metric("Total", mission_summary["total_missions"])
    mc2.metric("Ativas", mission_summary["active_missions"])
    mc3.metric("Bloqueadas", mission_summary["blocked_missions"])
    mc4.metric("Concluídas", mission_summary["done_missions"])

    with st.form("aion_persistent_mission_form", clear_on_submit=True):
        mission_title = st.text_input("Título da missão persistente")
        mission_domain = st.selectbox(
            "Área da missão",
            ["central","trading","studio","business","laboratory","secretary","development","subscriptions","promotions"],
            index=6,
        )
        mission_objective = st.text_area("Objetivo / escopo", max_chars=1600)
        mission_next = st.text_area("Próxima ação registrada", max_chars=1600)
        create_mission = st.form_submit_button("Registrar missão no Checkpoint", type="primary")

    if create_mission:
        try:
            mission = new_mission(
                mission_title,
                domain=mission_domain,
                objective=mission_objective,
                next_action=mission_next,
                source=str(access.get("username") or "ADMIN"),
            )
            missions = upsert_mission(missions, mission)
            updated = update_continuity_checkpoint(
                checkpoint,
                missions=missions,
                handoffs=handoffs,
                dirty=True,
            )
            updated = _record_working_event(
                updated,
                "mission_registered",
                f"Missão persistente registrada: {mission['title']}",
                evidence={
                    "mission_id":mission["mission_id"],
                    "domain":mission["domain"],
                    "status":mission["status"],
                },
            )
            _set_working_checkpoint(updated, dirty=True)
            st.success("Missão registrada na memória de trabalho do AION.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível registrar a missão: {type(exc).__name__}")

    if missions:
        st.dataframe(
            [{
                "ID":item.get("mission_id"),
                "Status":item.get("status"),
                "Área":item.get("domain"),
                "Missão":item.get("title"),
                "Próxima ação":item.get("next_action"),
                "Atualizada":item.get("updated_at"),
            } for item in reversed(missions[-80:])],
            width="stretch",
            hide_index=True,
        )
        mission_ids=[str(item.get("mission_id") or "") for item in missions]
        selected_mission_id=st.selectbox(
            "Missão selecionada",
            mission_ids,
            key="aion_persistent_mission_selected",
        )
        selected_mission=next(
            (item for item in missions if str(item.get("mission_id") or "")==selected_mission_id),
            None,
        )
        if isinstance(selected_mission, Mapping):
            status_index = list(MISSION_STATUSES).index(
                str(selected_mission.get("status") or "PLANNED")
                if str(selected_mission.get("status") or "PLANNED") in MISSION_STATUSES
                else "PLANNED"
            )
            next_status = st.selectbox(
                "Novo estado da missão",
                list(MISSION_STATUSES),
                index=status_index,
                key="aion_persistent_mission_status",
            )
            mission_outcome = st.text_area(
                "Resultado / conclusão registrada",
                value=str(selected_mission.get("outcome") or ""),
                key="aion_persistent_mission_outcome",
                max_chars=1600,
            )
            mission_blocker = st.text_area(
                "Bloqueio registrado",
                value=str(selected_mission.get("blocker") or ""),
                key="aion_persistent_mission_blocker",
                max_chars=1600,
            )
            mission_next_action = st.text_area(
                "Próxima ação",
                value=str(selected_mission.get("next_action") or ""),
                key="aion_persistent_mission_next",
                max_chars=1600,
            )
            evidence_text = st.text_input(
                "Referências de evidência (separadas por vírgula)",
                value=", ".join(list(selected_mission.get("evidence_refs") or [])),
                key="aion_persistent_mission_evidence",
            )
            if st.button(
                "Atualizar missão persistente",
                key="aion_persistent_mission_update",
                width="stretch",
            ):
                try:
                    evidence_refs=[x.strip() for x in evidence_text.split(",") if x.strip()]
                    missions = transition_mission(
                        missions,
                        selected_mission_id,
                        next_status,
                        outcome=mission_outcome,
                        blocker=mission_blocker,
                        next_action=mission_next_action,
                        evidence_refs=evidence_refs,
                    )
                    updated = update_continuity_checkpoint(
                        checkpoint,
                        missions=missions,
                        handoffs=handoffs,
                        dirty=True,
                    )
                    updated = _record_working_event(
                        updated,
                        "mission_updated",
                        f"Missão persistente atualizada: {selected_mission_id}",
                        evidence={
                            "mission_id":selected_mission_id,
                            "status":next_status,
                            "automatic_execution":False,
                        },
                    )
                    _set_working_checkpoint(updated, dirty=True)
                    st.success("Missão atualizada localmente no Checkpoint.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível atualizar a missão: {type(exc).__name__}")

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
    persistence_preflight = runtime_write_preflight(runtime_result)
    persistence_blocked = bool(conflict or not persistence_preflight.get("allowed"))
    if not persistence_preflight.get("allowed"):
        st.caption(
            "Persistência bloqueada em modo seguro: "
            f"{persistence_preflight.get('reason','estado runtime não confirmado')}."
        )
    if st.button(
        "💾 Salvar Checkpoint Mestre no runtime",
        key="aion_save_checkpoint",
        disabled=persistence_blocked,
        help=(
            "A escrita ocorre apenas no branch de runtime, exige estado seguro do runtime "
            "e este clique conta como aprovação explícita."
        ),
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
                expected_sha=str(persistence_preflight.get("expected_sha") or ""),
            )
            if result.get("saved") and result.get("verified"):
                saved_checkpoint = ensure_operating_checkpoint(result.get("checkpoint"))
                saved_checkpoint["operating"]["dirty"] = False
                _set_working_checkpoint(saved_checkpoint, dirty=False)
                st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(saved_checkpoint)
                st.success("Checkpoint Mestre salvo, relido e confirmado no runtime.")
                st.session_state["aion_checkpoint_save_result"] = result
            else:
                st.warning(
                    "Checkpoint não foi confirmado como persistido. "
                    f"Estado: {result.get('status')} · motivo: {result.get('reason','não informado')}. "
                    "As alterações locais continuam marcadas como pendentes."
                )

    st.divider()
    st.markdown("#### Recuperação / Rollback do Checkpoint")
    st.caption(
        "Usa o histórico versionado do Checkpoint no branch de runtime. "
        "Listar e pré-visualizar são somente leitura. Restaurar exige revisão íntegra, "
        "SHA atual, confirmação explícita e Guardian."
    )

    if st.button(
        "🔎 Carregar histórico de recuperação",
        key="aion_checkpoint_history_load",
        width="stretch",
    ):
        st.session_state["aion_checkpoint_history"] = list_checkpoint_revisions(
            cfg,
            limit=12,
        )
        st.session_state.pop("aion_recovery_candidate", None)

    history = st.session_state.get("aion_checkpoint_history")
    if isinstance(history, Mapping):
        history_status = str(history.get("status") or "UNKNOWN")
        items = [
            dict(item)
            for item in list(history.get("items", []) or [])
            if isinstance(item, Mapping)
        ]
        if history_status == "CONFIRMED":
            if items:
                st.dataframe(
                    [{
                        "Revisão": item.get("short_revision"),
                        "Data": item.get("created_at"),
                        "Mensagem": item.get("message"),
                    } for item in items],
                    width="stretch",
                    hide_index=True,
                )
                revisions = [str(item.get("revision") or "") for item in items]
                labels = {
                    str(item.get("revision") or ""):
                    f"{item.get('short_revision')} · {item.get('created_at') or 'sem data'} · {item.get('message') or 'sem mensagem'}"
                    for item in items
                }
                selected_revision = st.selectbox(
                    "Revisão para pré-visualizar",
                    revisions,
                    format_func=lambda value: labels.get(value, value),
                    key="aion_recovery_revision",
                )
                if st.button(
                    "👁️ Pré-visualizar revisão",
                    key="aion_recovery_preview",
                ):
                    st.session_state["aion_recovery_candidate"] = load_checkpoint_revision(
                        selected_revision,
                        cfg,
                    )
            else:
                st.info("Nenhuma revisão histórica do Checkpoint foi retornada.")
        else:
            st.warning(
                "Histórico de recuperação não confirmado. "
                f"Estado: {history_status} · motivo: {history.get('reason','não informado')}."
            )

    candidate = st.session_state.get("aion_recovery_candidate")
    if isinstance(candidate, Mapping):
        candidate_status = str(candidate.get("status") or "UNKNOWN")
        if candidate_status != "CONFIRMED":
            st.warning(
                "A revisão selecionada não pôde ser confirmada. "
                f"Estado: {candidate_status} · motivo: {candidate.get('reason','não informado')}."
            )
        else:
            integrity = (
                candidate.get("integrity")
                if isinstance(candidate.get("integrity"), Mapping)
                else {}
            )
            preview_preflight = recovery_preflight(runtime_result, candidate)
            rc1,rc2,rc3 = st.columns(3)
            rc1.metric("Revisão", str(candidate.get("revision") or "")[:10])
            rc2.metric("Integridade", str(integrity.get("state") or "UNKNOWN"))
            rc3.metric("Digest", str(candidate.get("digest") or "")[:16])

            local_dirty = bool(st.session_state.get(_WORKING_DIRTY_KEY, False))
            if local_dirty:
                st.warning(
                    "Há alterações locais ainda não persistidas. "
                    "Salve ou descarte essas alterações antes de restaurar uma revisão histórica."
                )
            elif not preview_preflight.get("allowed"):
                st.warning(
                    "Restauração bloqueada em modo seguro: "
                    f"{preview_preflight.get('reason','preflight não confirmado')}."
                )
            else:
                st.warning(
                    "A restauração substituirá o Checkpoint runtime atual por esta revisão histórica "
                    "através de escrita condicional no SHA atual. Não existe restauração automática."
                )
                confirm_restore = st.checkbox(
                    "Confirmo que revisei esta versão e quero restaurar o Checkpoint Mestre",
                    value=False,
                    key="aion_recovery_explicit_approval",
                )
                if st.button(
                    "↩️ Restaurar revisão selecionada",
                    key="aion_recovery_restore",
                    type="primary",
                    disabled=not bool(confirm_restore),
                    width="stretch",
                ):
                    decision = guardian_decision(
                        "restore_checkpoint",
                        access,
                        approved=True,
                        feature_flags=flags,
                    )
                    if not decision["allowed"]:
                        st.error(decision["reason"])
                    else:
                        result = restore_checkpoint_revision(
                            candidate,
                            runtime_result,
                            cfg,
                            approved=True,
                        )
                        if result.get("saved") and result.get("verified"):
                            restored = ensure_operating_checkpoint(result.get("checkpoint"))
                            restored["operating"]["dirty"] = False
                            _set_working_checkpoint(restored, dirty=False)
                            st.session_state[_WORKING_SOURCE_KEY] = checkpoint_source_digest(restored)
                            st.session_state[_WORKING_CONFLICT_KEY] = False
                            st.session_state["aion_checkpoint_recovery_result"] = result
                            st.session_state.pop("aion_recovery_candidate", None)
                            st.success(
                                "Checkpoint restaurado, relido e verificado. "
                                "O evento de recuperação foi registrado na auditoria."
                            )
                            st.rerun()
                        else:
                            st.error(
                                "A recuperação não foi confirmada. "
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
    st.markdown("### 🎟️ Promoções")
    st.caption(
        "Campanhas e códigos ficam persistidos no Checkpoint Mestre. "
        "O código completo é mostrado somente na criação; o checkpoint guarda apenas hash + últimos 4 caracteres."
    )
    _context_voice(
        "Promoções",
        (
            "Bem-vindo a Promoções. Aqui preparamos períodos gratuitos, cupons e descontos "
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




def _render_entitlements(
    access: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    flags: Mapping[str, bool],
    account_entitlement_audit: Mapping[str, Any] | None = None,
) -> None:
    st.markdown("### 🔐 Assinaturas & Entitlements")
    st.caption(
        "Área comercial de direitos de acesso. Entitlement é separado do login, do perfil USER/SALES/ADMIN, "
        "do pagamento, do cupom e de Promoções. Criar ou aprovar uma solicitação NÃO altera conta nem libera acesso."
    )
    _context_voice(
        "Assinaturas",
        (
            "Bem-vindo a Assinaturas e Entitlements. Aqui o AION separa o direito comercial de acesso "
            "de login, perfil, pagamento e cupom. Nenhuma solicitação libera acesso automaticamente."
        ),
        key="aion_entitlements_voice",
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

    st.markdown("#### 🛡️ Privacidade & ciclo de vida do AION pessoal")
    privacy_ready = tenant_privacy_readiness()
    privacy_policy = tenant_privacy_policy_snapshot()
    p1,p2,p3,p4 = st.columns(4)
    p1.metric("Classes pessoais permitidas", privacy_ready["allowed_data_classes"])
    p2.metric("Exportação", "CONTRATO PRONTO")
    p3.metric("Exclusão", "PLANO MANUAL")
    p4.metric("Exclusão automática", "DESLIGADA")

    st.caption(
        "Estas regras são controles técnicos internos de privacidade e ciclo de vida. "
        "As janelas abaixo são defaults de revisão do produto, não certificação jurídica/compliance."
    )
    class_rows = []
    review_days = privacy_policy.get("retention_review_days") or {}
    for item in privacy_policy.get("personal_data_classes") or []:
        key = str(item.get("key") or "")
        class_rows.append({
            "Classe": item.get("label"),
            "Finalidade": item.get("purpose"),
            "Sensibilidade": item.get("sensitivity"),
            "Revisão interna": (
                f"{int(review_days.get(key))} dias"
                if review_days.get(key) is not None
                else "sem janela definida"
            ),
        })
    if class_rows:
        st.dataframe(class_rows,width="stretch",hide_index=True)

    privacy_controls = [
        {"Controle":"Memória ADMIN no tenant","Estado":"BLOQUEADA"},
        {"Controle":"Documentos privados do projeto","Estado":"BLOQUEADOS"},
        {"Controle":"Cópia cross-tenant","Estado":"BLOQUEADA"},
        {"Controle":"Exportação automática","Estado":"DESLIGADA"},
        {"Controle":"Exclusão automática","Estado":"DESLIGADA"},
        {"Controle":"Limpeza após rotação de credencial","Estado":"REVISÃO MANUAL"},
        {"Controle":"Persistência pessoal","Estado":"AINDA DESLIGADA"},
        {"Controle":"Compliance legal afirmado","Estado":"NÃO"},
    ]
    st.dataframe(privacy_controls,width="stretch",hide_index=True)
    st.info(
        "Quando o AION pessoal for ativado no futuro, exportação e exclusão deverão operar somente "
        "no namespace do próprio assinante, com confirmação de identidade e auditoria. "
        "Nenhum dado pessoal é criado, exportado ou excluído por este painel."
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
    foundation_diagnostics: list[dict[str, str]] = []

    try:
        configured_account_rows = configured_users()
    except Exception as exc:
        configured_account_rows = {}
        foundation_diagnostics.append({
            "component": "account_registry",
            "error_type": type(exc).__name__,
        })

    try:
        account_entitlement_audit = audit_account_entitlements(
            configured_account_rows,
            entitlement_records,
        )
    except Exception as exc:
        account_entitlement_audit = _unknown_account_entitlement_audit(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "account_entitlement_audit",
            "error_type": type(exc).__name__,
        })

    try:
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
    except Exception as exc:
        status_board = _unknown_status_board(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "master_status_board",
            "error_type": type(exc).__name__,
        })

    try:
        approval_inbox = collect_approval_inbox(checkpoint)
    except Exception as exc:
        approval_inbox = _unknown_approval_inbox(type(exc).__name__)
        foundation_diagnostics.append({
            "component": "approval_inbox",
            "error_type": type(exc).__name__,
        })

    reliability_budget = normalize_budget(
        (checkpoint.get("aion") or {}).get("model_budget", {})
        if isinstance(checkpoint.get("aion"), Mapping)
        else {}
    )
    try:
        preliminary_reliability = reliability_snapshot(
            system_context=system,
            market_context=market,
            provider_status=provider,
            runtime_result=runtime_result,
            budget=reliability_budget,
            incident_snapshot={},
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        )
    except Exception as exc:
        preliminary_reliability = {
            "schema":"ATLASQUANT_AION_RELIABILITY_GOVERNANCE_V1",
            "posture":"UNKNOWN",
            "data_guardian":{"state":"UNKNOWN","reconciliation":{"observations":[],"conflict_count":0,"critical_conflict_count":0}},
            "cost_guardian":{"state":"UNKNOWN","automatic_billing":False,"automatic_upgrade":False},
            "memory_protection":{"state":"UNKNOWN","write_safe_precondition":False},
            "rollback_governance":{"state":"STANDBY","automatic_rollback":False},
            "degraded_mode":{"state":"DEGRADED_SAFE","can_authorize_market_action":False,"real_orders_enabled":False},
            "next_actions":["Revisar a camada Reliability & Governance."],
            "automatic_failover":False,
            "automatic_repair":False,
            "automatic_rollback":False,
            "automatic_paid_fallback":False,
            "real_orders_enabled":False,
            "executes_action":False,
        }
        foundation_diagnostics.append({
            "component":"reliability_governance_preflight",
            "error_type":type(exc).__name__,
        })
    system["reliability"] = preliminary_reliability

    try:
        incident_snapshot = collect_incidents(
            checkpoint=checkpoint,
            runtime_result=runtime_result,
            system_context=system,
            account_audit=account_entitlement_audit,
        )
    except Exception as exc:
        incident_snapshot = {
            "schema":"ATLASQUANT_AION_INCIDENT_CENTER_V1",
            "incidents":[],
            "total":0,
            "counts":{"INFO":0,"LOW":0,"MEDIUM":0,"HIGH":0,"CRITICAL":0},
            "highest_severity":"UNKNOWN",
            "has_critical":False,
            "rollback_review_recommended":False,
            "rollback_reasons":[],
            "automatic_containment":False,
            "automatic_rollback":False,
            "automatic_secret_rotation":False,
            "automatic_account_mutation":False,
            "real_orders_enabled":False,
            "executes_action":False,
            "truth_state":"UNKNOWN",
        }
        foundation_diagnostics.append({
            "component":"incident_center",
            "error_type":type(exc).__name__,
        })

    try:
        final_reliability = reliability_snapshot(
            system_context=system,
            market_context=market,
            provider_status=provider,
            runtime_result=runtime_result,
            budget=reliability_budget,
            incident_snapshot=incident_snapshot,
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        )
    except Exception as exc:
        final_reliability = preliminary_reliability
        foundation_diagnostics.append({
            "component":"reliability_governance_final",
            "error_type":type(exc).__name__,
        })
    system["reliability"] = final_reliability

    continuity_section = (
        checkpoint.get("continuity")
        if isinstance(checkpoint.get("continuity"), Mapping)
        else {}
    )
    continuity_state = continuity_summary(
        list(continuity_section.get("missions", []) or []),
        list(continuity_section.get("handoffs", []) or []),
    )
    interface_validation_state = (
        dict(system.get("interface_validation"))
        if isinstance(system.get("interface_validation"), Mapping)
        else interface_validation_mission(
            system.get("critical_surfaces")
            if isinstance(system.get("critical_surfaces"), Mapping)
            else {}
        )
    )
    publication_state = (
        dict(system.get("publication_truth"))
        if isinstance(system.get("publication_truth"), Mapping)
        else {}
    )
    release_gate_state = (
        dict(system.get("release_gate"))
        if isinstance(system.get("release_gate"), Mapping)
        else release_gate(
            publication_truth=publication_state,
            interface_validation=interface_validation_state,
        )
    )
    try:
        executive_snapshot = executive_pulse(
            runtime_result=runtime_result,
            approval_inbox=approval_inbox,
            incident_snapshot=incident_snapshot,
            status_board=status_board,
            continuity_summary=continuity_state,
            interface_validation=interface_validation_state,
            publication_truth=publication_state,
            release_gate_snapshot=release_gate_state,
            reliability_snapshot=final_reliability,
            live_event_snapshot=(
                system.get("live_event_intelligence")
                if isinstance(system.get("live_event_intelligence"), Mapping)
                else {}
            ),
            checkpoint_dirty=bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            checkpoint_conflict=bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
            foundation_diagnostics=foundation_diagnostics,
        )
    except Exception as exc:
        executive_snapshot = {
            "schema":"ATLASQUANT_AION_EXECUTIVE_PULSE_V1",
            "posture":"UNKNOWN",
            "primary":{
                "priority":"P2",
                "area":"🛠️ Desenvolvimento",
                "title":"Pulso Executivo indisponível",
                "detail":"A priorização executiva não pôde ser confirmada nesta execução.",
                "next_action":"Usar a Próxima Ação AION e o Painel Mestre até revisar esta camada.",
                "source":"safe_fallback",
            },
            "attention_items":[],
            "attention_count":0,
            "runtime_status":str(runtime_result.get("status") or "UNKNOWN"),
            "integrity_state":"UNKNOWN",
            "approval_count":int(approval_inbox.get("total") or 0),
            "incident_count":int(incident_snapshot.get("total") or 0),
            "critical_incidents":0,
            "active_missions":int(continuity_state.get("active_missions") or 0),
            "blocked_missions":int(continuity_state.get("blocked_missions") or 0),
            "checkpoint_dirty":bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
            "checkpoint_conflict":bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
            "degraded_components":len(foundation_diagnostics),
            "interface_validation_state":str(interface_validation_state.get("state") or "UNKNOWN"),
            "interface_validation_confirmed":int(interface_validation_state.get("confirmed") or 0),
            "interface_validation_total":int(interface_validation_state.get("total") or 3),
            "interface_validation_remaining":int(interface_validation_state.get("remaining") or 3),
            "interface_validation_complete":bool(interface_validation_state.get("all_confirmed_current_build",False)),
            "publication_state":str(publication_state.get("state") or "UNKNOWN"),
            "publication_main_match":str(publication_state.get("main_match") or "UNKNOWN"),
            "production_verification":str(publication_state.get("production_verification") or "UNKNOWN"),
            "can_claim_latest_main_live":bool(publication_state.get("can_claim_latest_main_live",False)),
            "release_gate_state":str(release_gate_state.get("state") or "UNKNOWN"),
            "release_gate_confirmed_stages":int(release_gate_state.get("confirmed_stages") or 0),
            "release_gate_total_stages":int(release_gate_state.get("total_stages") or 4),
            "release_gate_next_stage":str(release_gate_state.get("next_stage") or ""),
            "release_gate_claim_allowed":bool(release_gate_state.get("release_claim_allowed",False)),
            "recommended_workspace":"🛠️ Desenvolvimento",
            "executes_action":False,
            "real_orders_enabled":False,
        }
        foundation_diagnostics.append({
            "component":"executive_pulse",
            "error_type":type(exc).__name__,
        })

    try:
        commander_snapshot = commander_briefing(
            checkpoint=checkpoint,
            system_context=system,
            executive_snapshot=executive_snapshot,
        )
    except Exception as exc:
        commander_snapshot = {
            "schema":"ATLASQUANT_AION_OPERATIONAL_INTELLIGENCE_V1",
            "mode":"COMMANDER",
            "posture":"UNKNOWN",
            "objective":"Não confirmado.",
            "next_action":"Revisar a camada de inteligência operacional.",
            "blockers":[],
            "active_missions":0,
            "release_gate_state":"UNKNOWN",
            "publication_state":"UNKNOWN",
            "executive_priority":"P2",
            "executive_area":"🛠️ Desenvolvimento",
            "audit":{"status":"UNKNOWN","counts":{},"rows":[],"independent_sources":0,"conflict_count":0},
            "evidence_confidence":{"score":0,"label":"SEM_EVIDENCIA","is_profit_probability":False},
            "executes_action":False,
            "automatic_repair":False,
            "automatic_deploy":False,
            "real_orders_enabled":False,
        }
        foundation_diagnostics.append({
            "component":"aion_operational_intelligence",
            "error_type":type(exc).__name__,
        })
    system["commander_snapshot"] = commander_snapshot

    _render_header(
        access_map,
        str(runtime_result.get("status") or "UNKNOWN"),
        str(provider.get("state") or "UNKNOWN"),
        system,
    )
    _render_executive_grid(memory_summary, runtime_result, provider, market)

    if foundation_diagnostics:
        degraded = ", ".join(
            f"{item['component']} ({item['error_type']})"
            for item in foundation_diagnostics
        )
        st.warning(
            "AION abriu em modo degradado seguro nas camadas auxiliares: "
            f"{degraded}. Nenhum estado ausente foi tratado como confirmado."
        )
        st.caption(
            "A leitura completa dessas camadas não pôde ser confirmada nesta execução. "
            "Somente o tipo do erro é exibido; mensagens internas não são expostas. "
            "Nenhuma ação externa, permissão ou trading real foi habilitado pelo fallback."
        )

    jump_request = st.session_state.pop(_AION_WORKSPACE_JUMP_KEY, None)
    if jump_request in AION_WORKSPACES:
        st.session_state["aion_admin_workspace"] = jump_request

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
            _render_central(
                access_map, checkpoint, runtime_result, memory_summary, flags,
                system, status_board, approval_inbox, incident_snapshot,
                executive_snapshot,
            )
        elif selected_workspace == "🗂️ Secretaria":
            _render_secretary(access_map, checkpoint, flags, system, market, status_board, approval_inbox)
        elif selected_workspace == "📈 Trading":
            _render_trading(market, system)
        elif selected_workspace == "🎬 Studio":
            _render_studio(access_map, checkpoint, flags)
        elif selected_workspace == "💼 Negócios":
            _render_business(access_map, checkpoint, flags)
        elif selected_workspace == "🧪 Laboratório":
            _render_laboratory(access_map, checkpoint, flags, incident_snapshot)
        elif selected_workspace == "🛠️ Desenvolvimento":
            _render_development(access_map, checkpoint, source_checkpoint, runtime_result, flags)
        elif selected_workspace == "🔐 Assinaturas":
            _render_entitlements(
                access_map,
                checkpoint,
                flags,
                account_entitlement_audit,
            )
        elif selected_workspace == "🎟️ Promoções":
            _render_promotions(
                access_map,
                checkpoint,
                flags,
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
        "checkpoint_integrity_state": str(
            ((runtime_result.get("integrity") or {}) if isinstance(runtime_result.get("integrity"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "guardian_blocked_now": int(
            guardian_posture(access_map, feature_flags=flags).get("blocked_now") or 0
        ),
        "tenant_privacy_contract_ready": bool(
            tenant_privacy_readiness().get("policy_defined", False)
        ),
        "incident_center_total": int(incident_snapshot.get("total") or 0),
        "incident_center_has_critical": bool(incident_snapshot.get("has_critical", False)),
        "incident_center_rollback_review": bool(
            incident_snapshot.get("rollback_review_recommended", False)
        ),
        "executive_posture": str(executive_snapshot.get("posture") or "UNKNOWN"),
        "executive_primary_area": str(
            ((executive_snapshot.get("primary") or {}) if isinstance(executive_snapshot.get("primary"), Mapping) else {}).get("area")
            or "🧠 Central"
        ),
        "executive_attention_count": int(executive_snapshot.get("attention_count") or 0),
        "central_view_mode": str(st.session_state.get("aion_central_view_mode") or "Essencial"),
        "continuity_active_missions": int(
            continuity_summary(
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("missions", []) or []),
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("handoffs", []) or []),
            ).get("active_missions") or 0
        ),
        "continuity_handoff_count": int(
            continuity_summary(
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("missions", []) or []),
                list(((checkpoint.get("continuity") or {}) if isinstance(checkpoint.get("continuity"), Mapping) else {}).get("handoffs", []) or []),
            ).get("handoff_count") or 0
        ),
        "checkpoint_dirty": bool(st.session_state.get(_WORKING_DIRTY_KEY, False)),
        "checkpoint_conflict": bool(st.session_state.get(_WORKING_CONFLICT_KEY, False)),
        "portable_core_workspaces": int(
            portable_core_summary(
                checkpoint.get("portable_core")
                if isinstance(checkpoint.get("portable_core"), Mapping)
                else {}
            ).get("workspaces") or 0
        ),
        "vault_policy_ok": bool(
            vault_summary(
                checkpoint.get("vault")
                if isinstance(checkpoint.get("vault"), Mapping)
                else {}
            ).get("policy_ok", False)
        ),
        "task_summary": queue_summary((checkpoint.get("operating") or {}).get("tasks", [])),
        "status_board_counts": status_board.get("counts"),
        "status_board_has_unresolved": bool(status_board.get("has_unresolved")),
        "approval_inbox_total": int(approval_inbox.get("total") or 0),
        "approval_inbox_has_pending": bool(approval_inbox.get("has_pending")),
        "commercial_access_audit_needs_review": audit_requires_review(account_entitlement_audit),
        "live_event_background_state": str(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("background_watch_state")
            or "UNKNOWN"
        ),
        "live_event_continuous_24h_confirmed": bool(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("continuous_runtime_confirmed", False)
        ),
        "live_event_journal_count": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("journal_event_count")
            or 0
        ),
        "live_event_external_delivery_allowed": False,
        "foundation_status": "DEGRADED_SAFE" if foundation_diagnostics else "OK",
        "foundation_diagnostics": foundation_diagnostics,
        "selected_workspace": selected_workspace,
        "workspace_status": "ERROR_ISOLATED" if workspace_error_type else "OK",
        "workspace_error_type": workspace_error_type,
        "critical_surface_counts": (
            ((system.get("critical_surfaces") or {}) if isinstance(system.get("critical_surfaces"), Mapping) else {}).get("counts")
            or {}
        ),
        "critical_surfaces_have_unresolved": bool(
            ((system.get("critical_surfaces") or {}) if isinstance(system.get("critical_surfaces"), Mapping) else {}).get("has_unresolved", True)
        ),
        "guided_revalidation_state": str(
            ((system.get("guided_revalidation") or {}) if isinstance(system.get("guided_revalidation"), Mapping) else {}).get("state")
            or "NONE"
        ),
        "interface_validation_state": str(interface_validation_state.get("state") or "UNKNOWN"),
        "interface_validation_confirmed": int(interface_validation_state.get("confirmed") or 0),
        "interface_validation_total": int(interface_validation_state.get("total") or 3),
        "interface_validation_remaining": int(interface_validation_state.get("remaining") or 3),
        "interface_validation_complete": bool(
            interface_validation_state.get("all_confirmed_current_build", False)
        ),
        "publication_state": str(publication_state.get("state") or "UNKNOWN"),
        "publication_main_match": str(publication_state.get("main_match") or "UNKNOWN"),
        "production_verification": str(
            publication_state.get("production_verification") or "UNKNOWN"
        ),
        "can_claim_latest_main_live": bool(
            publication_state.get("can_claim_latest_main_live", False)
        ),
        "release_gate_state": str(release_gate_state.get("state") or "UNKNOWN"),
        "release_gate_progress_pct": float(
            release_gate_state.get("progress_pct") or 0.0
        ),
        "release_gate_claim_allowed": bool(
            release_gate_state.get("release_claim_allowed", False)
        ),
        "release_gate_next_stage": str(
            release_gate_state.get("next_stage") or ""
        ),
        "learning_episodes": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("episodes") or 0
        ),
        "learning_open_episodes": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("open_episodes") or 0
        ),
        "learning_human_review_candidates": int(
            learning_summary(
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("episodes", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("experiments", []) or []),
                list(((checkpoint.get("learning") or {}) if isinstance(checkpoint.get("learning"), Mapping) else {}).get("research_refs", []) or []),
            ).get("human_review_candidates") or 0
        ),
        "learning_automatic_changes": False,
        "reliability_posture": str(final_reliability.get("posture") or "UNKNOWN"),
        "reliability_degraded_mode": str(
            ((final_reliability.get("degraded_mode") or {}) if isinstance(final_reliability.get("degraded_mode"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_source_conflicts": int(
            ((((final_reliability.get("data_guardian") or {}) if isinstance(final_reliability.get("data_guardian"), Mapping) else {}).get("reconciliation") or {}) if isinstance(((final_reliability.get("data_guardian") or {}) if isinstance(final_reliability.get("data_guardian"), Mapping) else {}).get("reconciliation"), Mapping) else {}).get("conflict_count")
            or 0
        ),
        "reliability_memory_state": str(
            ((final_reliability.get("memory_protection") or {}) if isinstance(final_reliability.get("memory_protection"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_cost_state": str(
            ((final_reliability.get("cost_guardian") or {}) if isinstance(final_reliability.get("cost_guardian"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "reliability_automatic_repair": False,
        "reliability_automatic_rollback": False,
        "source_mesh_state": str(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("market_state")
            or "UNKNOWN"
        ),
        "source_mesh_live_confirmed": bool(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("market_live_confirmed", False)
        ),
        "source_mesh_observations": int(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("observation_count")
            or 0
        ),
        "source_mesh_fallbacks": int(
            ((system.get("source_mesh") or {}) if isinstance(system.get("source_mesh"), Mapping) else {}).get("fallback_or_unavailable")
            or 0
        ),
        "live_event_state": str(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("state")
            or "UNKNOWN"
        ),
        "live_event_alerts": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("alert_count")
            or 0
        ),
        "live_event_urgent_review": int(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("urgent_review_count")
            or 0
        ),
        "live_event_24x7_confirmed": bool(
            ((system.get("live_event_intelligence") or {}) if isinstance(system.get("live_event_intelligence"), Mapping) else {}).get("continuous_runtime_confirmed", False)
        ),
        "commander_posture": str(commander_snapshot.get("posture") or "UNKNOWN"),
        "commander_objective": str(commander_snapshot.get("objective") or ""),
        "commander_next_action": str(commander_snapshot.get("next_action") or ""),
        "commander_evidence_confidence": int(
            ((commander_snapshot.get("evidence_confidence") or {}) if isinstance(commander_snapshot.get("evidence_confidence"), Mapping) else {}).get("score")
            or 0
        ),
        "commander_evidence_label": str(
            ((commander_snapshot.get("evidence_confidence") or {}) if isinstance(commander_snapshot.get("evidence_confidence"), Mapping) else {}).get("label")
            or "SEM_EVIDENCIA"
        ),
        "commander_executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = ["SCHEMA", "AION_WORKSPACES", "render_aion_admin_console", "AION_ADMIN_CSS"]
