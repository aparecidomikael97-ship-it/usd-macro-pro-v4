"""AION capability registry and agentic mission planner.

This is a read-only planning layer. It maps an objective to capabilities,
dependencies, evidence gates and Guardian posture before any action is taken.

It deliberately does NOT:
- execute tools, connectors, web calls, model calls, writes or deploys;
- turn a plan into approval;
- bypass feature flags, cost policy or Guardian;
- enable real-money trading.

The result is a transparent execution map: what AION can do locally, what needs
fresh evidence, what depends on an external system, what needs explicit human
approval, and what remains blocked by design.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import hashlib
import re
import unicodedata

from atlasquant_aion_core import guardian_decision, route_context

SCHEMA = "ATLASQUANT_AION_CAPABILITY_PLANNER_V1"

CAPABILITY_STATES = (
    "AVAILABLE_LOCAL",
    "EVIDENCE_REQUIRED",
    "EXTERNAL_DEPENDENCY",
    "FEATURE_DISABLED",
    "APPROVAL_REQUIRED",
    "BLOCKED",
)

CAPABILITIES = (
    {
        "id": "memory_read",
        "label": "Memória canônica",
        "domains": ("central","secretary","development","laboratory"),
        "action": "read",
        "risk": "READ",
        "local": True,
        "feature_flag": "",
        "dependency": "",
        "evidence": ("canonical_memory",),
        "keywords": ("memoria","memória","checkpoint","historico","histórico","lembra","continuidade"),
    },
    {
        "id": "wisdom_retrieve",
        "label": "Diário de Sabedoria",
        "domains": ("central","secretary","laboratory","trading","development"),
        "action": "read",
        "risk": "READ",
        "local": True,
        "feature_flag": "",
        "dependency": "",
        "evidence": ("wisdom_journal",),
        "keywords": ("sabedoria","wisdom","aprendizado","aprendeu","lição","licao","conhecimento"),
    },
    {
        "id": "cognitive_plan",
        "label": "Conselho Cognitivo + Critic",
        "domains": ("central","trading","development","laboratory","studio","business","secretary"),
        "action": "read",
        "risk": "READ",
        "local": True,
        "feature_flag": "",
        "dependency": "",
        "evidence": ("objective",),
        "keywords": ("analisar","analise","análise","pesquisa","investigar","comparar","plano","planejar"),
    },
    {
        "id": "market_snapshot",
        "label": "Snapshot de mercado confirmado",
        "domains": ("trading",),
        "action": "read",
        "risk": "READ",
        "local": False,
        "feature_flag": "",
        "dependency": "market_live",
        "evidence": ("fresh_market_data","source_reconciliation"),
        "keywords": ("mercado","forex","radar","preco","preço","cotacao","cotação","agora","hoje","atual"),
    },
    {
        "id": "code_change_plan",
        "label": "Planejar mudança de código",
        "domains": ("development",),
        "action": "draft",
        "risk": "DRAFT",
        "local": True,
        "feature_flag": "",
        "dependency": "",
        "evidence": ("repository","tests"),
        "keywords": ("codigo","código","bug","erro","interface","github","implementar","desenvolver","ajustar"),
    },
    {
        "id": "sandbox_experiment",
        "label": "Sandbox / experimento",
        "domains": ("laboratory","trading","development"),
        "action": "draft",
        "risk": "DRAFT",
        "local": True,
        "feature_flag": "",
        "dependency": "",
        "evidence": ("test_plan","rollback_plan"),
        "keywords": ("sandbox","backtest","forward","experimento","teste","validar","simular"),
    },
    {
        "id": "checkpoint_write",
        "label": "Persistir Checkpoint Mestre",
        "domains": ("central","secretary","development","laboratory"),
        "action": "save_checkpoint",
        "risk": "WRITE",
        "local": False,
        "feature_flag": "",
        "dependency": "checkpoint_runtime",
        "evidence": ("runtime_checkpoint","expected_sha","integrity"),
        "keywords": ("salvar","persistir","checkpoint","registrar","gravar"),
    },
    {
        "id": "external_model",
        "label": "Modelo externo",
        "domains": ("central","trading","development","laboratory","studio","business","secretary"),
        "action": "",
        "risk": "PAID_EXTERNAL",
        "local": False,
        "feature_flag": "external_llm",
        "dependency": "external_model",
        "evidence": ("provider_ready","pricing","budget"),
        "keywords": ("modelo externo","ia externa","mais potente","deep research","pesquisa profunda"),
    },
    {
        "id": "social_publish",
        "label": "Publicação em rede social",
        "domains": ("studio",),
        "action": "publish_social",
        "risk": "PUBLISH",
        "local": False,
        "feature_flag": "social_publish",
        "dependency": "social_connector",
        "evidence": ("approved_asset","account_connection"),
        "keywords": ("publicar","postar","instagram","youtube","tiktok","rede social"),
    },
    {
        "id": "marketplace_publish",
        "label": "Publicação em marketplace",
        "domains": ("business",),
        "action": "publish_marketplace",
        "risk": "PUBLISH",
        "local": False,
        "feature_flag": "marketplace_publish",
        "dependency": "marketplace_connector",
        "evidence": ("approved_product","margin_review","account_connection"),
        "keywords": ("marketplace","mercado livre","tiktok shop","anuncio","anúncio","produto"),
    },
    {
        "id": "production_deploy",
        "label": "Deploy de produção",
        "domains": ("development",),
        "action": "deploy_production",
        "risk": "PRODUCTION",
        "local": False,
        "feature_flag": "production_deploy",
        "dependency": "production_connector",
        "evidence": ("quality_green","ui_smoke_green","mobile_green","rollback_plan"),
        "keywords": ("deploy","produção","producao","render","publicar sistema"),
    },
    {
        "id": "real_trade",
        "label": "Execução real em corretora",
        "domains": ("trading",),
        "action": "real_trade",
        "risk": "REAL_TRADING",
        "local": False,
        "feature_flag": "real_broker_execution",
        "dependency": "broker_connector",
        "evidence": ("broker_connection","risk_approval","live_market"),
        "keywords": ("trade real","ordem real","corretora","comprar agora","vender agora","execucao real","execução real"),
    },
)


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _system_dependencies(system_context: Mapping[str, Any] | None) -> dict[str, bool]:
    system = dict(system_context or {})
    source_mesh = system.get("source_mesh") if isinstance(system.get("source_mesh"), Mapping) else {}
    provider = system.get("provider") if isinstance(system.get("provider"), Mapping) else {}
    runtime = system.get("runtime_checkpoint") if isinstance(system.get("runtime_checkpoint"), Mapping) else {}
    integrations = system.get("integrations") if isinstance(system.get("integrations"), Mapping) else {}
    return {
        "market_live": bool(source_mesh.get("market_live_confirmed", False)),
        "checkpoint_runtime": str(runtime.get("status") or "").upper() == "CONFIRMED",
        "external_model": str(provider.get("state") or "").upper() == "EXTERNAL_READY",
        "social_connector": bool(integrations.get("social_connected", False)),
        "marketplace_connector": bool(integrations.get("marketplace_connected", False)),
        "production_connector": bool(integrations.get("production_connected", False)),
        "broker_connector": bool(integrations.get("broker_connected", False)),
    }


def capability_state(
    capability: Mapping[str, Any],
    *,
    access: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    spec = dict(capability or {})
    cid = _clean(spec.get("id"), 100)
    flags = dict(feature_flags or {})
    deps = _system_dependencies(system_context)
    feature = _clean(spec.get("feature_flag"), 100)
    dependency = _clean(spec.get("dependency"), 100)
    action = _clean(spec.get("action"), 100)
    local = bool(spec.get("local", False))

    if cid == "real_trade":
        state = "BLOCKED"
        reason = "Execução real permanece bloqueada por desenho nesta versão."
        requires_approval = True
    elif feature and not bool(flags.get(feature, False)):
        state = "FEATURE_DISABLED"
        reason = f"Feature flag {feature} está desligada."
        requires_approval = True
    elif dependency and not bool(deps.get(dependency, False)):
        if cid == "market_snapshot":
            state = "EVIDENCE_REQUIRED"
            reason = "Mercado ao vivo não está confirmado; dado fresco é obrigatório."
        else:
            state = "EXTERNAL_DEPENDENCY"
            reason = f"Dependência {dependency} não está confirmada."
        requires_approval = bool(action and action not in {"read","draft","search","summarize"})
    elif cid == "external_model":
        state = "APPROVAL_REQUIRED"
        reason = "Modelo externo exige orçamento/preço configurados e aprovação explícita por solicitação."
        requires_approval = True
    elif action:
        decision = guardian_decision(
            action,
            access,
            approved=False,
            feature_flags=flags,
        )
        if bool(decision.get("allowed", False)):
            state = "AVAILABLE_LOCAL"
            reason = str(decision.get("reason") or "")
            requires_approval = bool(decision.get("requires_explicit_approval", False))
        elif bool(decision.get("requires_explicit_approval", False)) and str(decision.get("risk") or "") != "REAL_TRADING":
            state = "APPROVAL_REQUIRED"
            reason = str(decision.get("reason") or "Aprovação explícita necessária.")
            requires_approval = True
        else:
            state = "BLOCKED"
            reason = str(decision.get("reason") or "Guardian bloqueou a capacidade.")
            requires_approval = True
    else:
        state = "AVAILABLE_LOCAL" if local else "EXTERNAL_DEPENDENCY"
        reason = "Capacidade de planejamento disponível." if local else "Dependência externa necessária."
        requires_approval = not local

    return {
        "schema": SCHEMA,
        "id": cid,
        "label": _clean(spec.get("label"), 160),
        "domains": list(spec.get("domains") or []),
        "risk": _clean(spec.get("risk"), 80),
        "state": state,
        "reason": reason,
        "feature_flag": feature,
        "dependency": dependency,
        "evidence_requirements": list(spec.get("evidence") or []),
        "requires_explicit_approval": bool(requires_approval),
        "executes_action": False,
        "approval_granted": False,
        "real_orders_enabled": False,
    }


def capability_snapshot(
    *,
    access: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [
        capability_state(
            spec,
            access=access,
            feature_flags=feature_flags,
            system_context=system_context,
        )
        for spec in CAPABILITIES
    ]
    counts = {state: 0 for state in CAPABILITY_STATES}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {
        "schema": SCHEMA,
        "capabilities": rows,
        "counts": counts,
        "total": len(rows),
        "automatic_execution": False,
        "automatic_approval": False,
        "real_orders_enabled": False,
    }


def _objective_capabilities(objective: str, domain: str) -> list[str]:
    q = _norm(objective)
    scored: list[tuple[int, str]] = []
    for spec in CAPABILITIES:
        score = 0
        if domain in tuple(spec.get("domains") or ()):
            score += 1
        for term in tuple(spec.get("keywords") or ()):
            if _norm(term) in q:
                score += 3
        if score > 0:
            scored.append((score, str(spec["id"])))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    selected = [cid for _, cid in scored[:7]]

    defaults = {
        "central": ["memory_read","wisdom_retrieve","cognitive_plan"],
        "secretary": ["memory_read","cognitive_plan"],
        "development": ["memory_read","cognitive_plan","code_change_plan"],
        "laboratory": ["memory_read","cognitive_plan","sandbox_experiment"],
        "trading": ["cognitive_plan","market_snapshot"],
        "studio": ["cognitive_plan"],
        "business": ["cognitive_plan"],
        "promotions": ["cognitive_plan"],
        "subscriptions": ["cognitive_plan"],
    }
    for cid in defaults.get(domain, ["cognitive_plan"]):
        if cid not in selected:
            selected.append(cid)

    # Objective-specific terminal capabilities must never be hidden by ranking.
    terminal_terms = (
        ("social_publish", ("publicar","postar","instagram","youtube","tiktok")),
        ("marketplace_publish", ("marketplace","mercado livre","tiktok shop","anuncio","anúncio")),
        ("production_deploy", ("deploy","render","produção","producao")),
        ("real_trade", ("trade real","ordem real","corretora","execucao real","execução real")),
        ("checkpoint_write", ("salvar checkpoint","persistir checkpoint","gravar checkpoint")),
        ("external_model", ("modelo externo","ia externa","deep research","pesquisa profunda")),
    )
    for cid, terms in terminal_terms:
        if any(_norm(term) in q for term in terms) and cid not in selected:
            selected.append(cid)
    return selected[:10]


def plan_agentic_mission(
    objective: Any,
    *,
    access: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    text = _clean(objective, 1400)
    routed = route_context(text)
    domain = str(routed.get("domain") or "central")
    snapshot = capability_snapshot(
        access=access,
        feature_flags=feature_flags,
        system_context=system_context,
    )
    by_id = {row["id"]: row for row in snapshot["capabilities"]}
    selected_ids = _objective_capabilities(text, domain)

    stages: list[dict[str, Any]] = []
    for order, cid in enumerate(selected_ids, start=1):
        row = dict(by_id[cid])
        stages.append({
            "order": order,
            "capability_id": cid,
            "label": row["label"],
            "state": row["state"],
            "reason": row["reason"],
            "evidence_requirements": list(row["evidence_requirements"]),
            "requires_explicit_approval": row["requires_explicit_approval"],
            "executes_action": False,
        })

    blocking_states = {"BLOCKED","FEATURE_DISABLED","EXTERNAL_DEPENDENCY","EVIDENCE_REQUIRED"}
    blockers = [row for row in stages if row["state"] in blocking_states]
    approvals = [row for row in stages if row["state"] == "APPROVAL_REQUIRED"]
    available = [row for row in stages if row["state"] == "AVAILABLE_LOCAL"]

    if blockers:
        readiness = "BLOCKED_OR_DEPENDENT"
    elif approvals:
        readiness = "READY_UNTIL_APPROVAL"
    else:
        readiness = "READY_FOR_LOCAL_WORK"

    mission_id = hashlib.sha256(
        (domain + "|" + text + "|" + ",".join(selected_ids)).encode("utf-8")
    ).hexdigest()[:14]
    return {
        "schema": SCHEMA,
        "mission_id": mission_id,
        "objective": text,
        "domain": domain,
        "readiness": readiness,
        "stages": stages,
        "available_local": len(available),
        "approval_gates": len(approvals),
        "blockers": len(blockers),
        "next_safe_stage": next(
            (row for row in stages if row["state"] == "AVAILABLE_LOCAL"),
            None,
        ),
        "automatic_execution": False,
        "automatic_approval": False,
        "executes_action": False,
        "real_orders_enabled": False,
    }


__all__ = [
    "SCHEMA",
    "CAPABILITY_STATES",
    "CAPABILITIES",
    "capability_state",
    "capability_snapshot",
    "plan_agentic_mission",
]
