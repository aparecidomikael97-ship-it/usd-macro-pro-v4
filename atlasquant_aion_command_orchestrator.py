"""Safe local command bridge for AION.

This layer turns a user-initiated AION command into one safe local Tool Hub call
or, for explicit compound read requests, a bounded bundle of up to three local
READ/SEARCH calls. Selection is deterministic. Execution is opt-in, defaults
off, and every selected tool still has to pass execute_local_tool(), which owns
the Tool Hub preflight and Guardian enforcement.

DRAFT remains single-tool only. Bundles never include WRITE, PUBLISH,
PRODUCTION, SECRETS, FINANCIAL, connectors, providers, subprocesses, network,
deployments, publishers, payment rails, brokers, or real trading.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_local_executor import execute_local_tool, local_allowlist
from atlasquant_aion_local_synthesis import synthesize_local_tool_results
from atlasquant_aion_local_response import compose_local_executive_response
from atlasquant_aion_local_traceability import build_local_traceability
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_hub import default_tool_hub

SCHEMA = "ATLASQUANT_AION_LOCAL_COMMAND_V1"
BUNDLE_SCHEMA = "ATLASQUANT_AION_LOCAL_COMMAND_BUNDLE_V1"
SAFE_KINDS = frozenset({"READ", "SEARCH", "DRAFT"})
BUNDLE_SAFE_KINDS = frozenset({"READ", "SEARCH"})
MAX_BUNDLE_TOOLS = 3

_RULES = (
    ("aion.durable.summary", (
        "tarefas duraveis", "tarefa duravel", "durable tasks", "durable task",
    )),
    ("aion.approvals.summary", (
        "caixa de aprovacoes", "resumo de aprovacoes", "aprovacoes pendentes",
        "approval inbox", "pending approvals",
    )),
    ("aion.missions.summary", (
        "resumo de missoes", "minhas missoes", "missoes ativas", "mission summary",
    )),
    ("aion.tasks.summary", (
        "resumo de tarefas", "minhas tarefas", "tarefas pendentes", "pendencias",
        "fila de tarefas", "o que falta", "task summary",
    )),
    ("aion.events.summary", (
        "resumo de eventos", "eventos locais", "observabilidade", "logs locais",
        "event summary",
    )),
    ("aion.checkpoint.inspect", (
        "inspecionar checkpoint", "inspecione o checkpoint", "integridade do checkpoint",
        "estado do checkpoint", "versao do checkpoint", "digest do checkpoint",
        "checkpoint mestre",
    )),
    ("aion.status.read", (
        "como esta o sistema", "estado do sistema", "status geral", "status do aion",
        "painel mestre", "quadro de status",
    )),
    ("aion.memory.recall", (
        "recall da memoria", "memoria em camadas", "camadas de memoria",
        "layered memory", "memory recall",
    )),
    ("aion.memory.search", (
        "buscar na memoria", "busque na memoria", "pesquisar na memoria",
        "procure na memoria", "memoria canonica", "historico do projeto",
        "onde paramos", "o que ficou aprovado", "lembra", "lembrar",
    )),
    ("aion.specialists.snapshot", (
        "snapshot do especialista", "leitura do especialista", "estado do especialista",
        "como esta o studio", "como esta o radar", "como esta o macro",
        "como esta o negocio", "specialist snapshot",
    )),
    ("aion.secretary.draft_brief", (
        "briefing da secretaria", "briefing executivo", "resumo executivo",
        "rascunho do briefing", "secretary brief",
    )),
)

_SENSITIVE_ACTION_PATTERNS = (
    re.compile(r"\b(faca|faz|execute|executar|rode|rodar|dispare)\s+(o\s+|a\s+)?(deploy|merge|publicacao|cobranca|pagamento|ordem|trade)\b"),
    re.compile(r"\b(publique|publicar)\b"),
    re.compile(r"\b(salve|salvar|grave|gravar)\b.{0,50}\bcheckpoint\b"),
    re.compile(r"\b(compre|comprar|venda|vender)\b.{0,60}\b(real|mercado|ativo|forex|acao|acoes|cripto)\b"),
    re.compile(r"\b(ative|ativar)\b.{0,60}\b(api paga|cobranca|assinatura|pagamento)\b"),
    re.compile(r"\b(mostre|mostrar|leia|ler|revele|revelar)\b.{0,50}\b(senha|token|secret|segredo|api key|chave de api)\b"),
    re.compile(r"\b(cobrar|cobre)\b.{0,40}\b(cliente|usuario|assinante)\b"),
    re.compile(r"\b(fazer|efetuar|realizar)\s+(o\s+|a\s+)?pagamento\b"),
    re.compile(r"\b(enviar|mande|mandar|disparar)\b.{0,40}\bordem\b.{0,20}\b(real|mercado)\b"),
    re.compile(r"\bpublicacao\b.{0,30}\b(imediata|agora|externa|instagram|youtube|tiktok)\b"),
)

_SPECIALIST_HINTS = (
    ("macro", ("macro", "cpi", "pce", "payroll", "nfp", "fed", "fomc", "bce", "ecb")),
    ("market", ("mercado", "forex", "radar", "trading", "estrutura")),
    ("ict", ("ict", "smc", "fvg", "order block", "breaker")),
    ("dev", ("codigo", "desenvolvimento", "github", "interface", "bug", "teste")),
    ("research", ("pesquisa", "evidencia", "fonte", "research")),
    ("business", ("negocio", "vendas", "produto", "margem", "growth")),
    ("studio", ("studio", "video", "imagem", "conteudo")),
    ("risk", ("risco", "guardian", "seguranca")),
    ("admin", ("admin", "administracao", "checkpoint")),
)


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _clean(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _sensitive_action_requested(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_ACTION_PATTERNS)


def _catalog_map() -> dict[str, dict[str, str]]:
    return {row["tool_id"]: dict(row) for row in local_allowlist()}


def command_catalog() -> tuple[dict[str, str], ...]:
    """Return only locally executable READ/SEARCH/DRAFT command targets."""
    catalog = _catalog_map()
    out = []
    seen = set()
    for tool_id, _phrases in _RULES:
        item = catalog.get(tool_id)
        if not item or tool_id in seen or item.get("kind") not in SAFE_KINDS:
            continue
        seen.add(tool_id)
        out.append({
            "tool_id": tool_id,
            "kind": str(item.get("kind") or ""),
            "label": str(item.get("label") or tool_id),
        })
    return tuple(out)


def _phrase_position(text: str, phrase: str) -> int:
    """Return a whole-phrase match position, never a substring inside another word."""
    parts = [re.escape(part) for part in phrase.split() if part]
    if not parts:
        return -1
    pattern = re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)")
    match = pattern.search(text)
    return match.start() if match else -1


def _candidate_tools(text: str) -> list[dict[str, Any]]:
    catalog = _catalog_map()
    candidates = []
    for priority, (tool_id, phrases) in enumerate(_RULES):
        item = catalog.get(tool_id)
        if not item or item.get("kind") not in SAFE_KINDS:
            continue
        positions_by_phrase = [(phrase, _phrase_position(text, phrase)) for phrase in phrases]
        matched = [phrase for phrase, position in positions_by_phrase if position >= 0]
        if not matched:
            continue
        positions = [position for _phrase, position in positions_by_phrase if position >= 0]
        position = min(positions) if positions else 999999
        candidates.append({
            "tool_id": tool_id,
            "kind": str(item.get("kind") or ""),
            "label": str(item.get("label") or tool_id),
            "score": max(len(phrase) for phrase in matched) * 10 + len(matched),
            "priority": priority,
            "position": position,
            "matched_phrases": matched[:6],
        })
    return candidates


def _empty_plan(state: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "tool_id": "",
        "kind": "",
        "matches": [],
        "reason": reason,
        "executes_tool": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
    }


def plan_local_command(question: Any) -> dict[str, Any]:
    """Choose zero or one local tool without executing it."""
    raw = _clean(question, 1200)
    text = _norm(raw)
    if not text:
        return _empty_plan("NO_COMMAND", "EMPTY_COMMAND")
    if _sensitive_action_requested(text):
        return _empty_plan("BLOCKED_INTENT", "SENSITIVE_OR_EXTERNAL_ACTION_REQUEST")

    candidates = _candidate_tools(text)
    if not candidates:
        return _empty_plan("NO_MATCH", "NO_SAFE_LOCAL_TOOL_MATCH")

    candidates.sort(key=lambda row: (-int(row["score"]), int(row["priority"]), str(row["tool_id"])))
    top = candidates[0]
    if len(candidates) > 1 and int(candidates[1]["score"]) == int(top["score"]):
        return {
            **_empty_plan("AMBIGUOUS", "MULTIPLE_EQUAL_LOCAL_TOOL_MATCHES"),
            "matches": candidates[:4],
        }

    return {
        "schema": SCHEMA,
        "state": "READY",
        "tool_id": top["tool_id"],
        "kind": top["kind"],
        "label": top["label"],
        "matches": candidates[:4],
        "reason": "SAFE_LOCAL_TOOL_SELECTED",
        "executes_tool": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
    }


def plan_local_bundle(question: Any, *, max_tools: int = MAX_BUNDLE_TOOLS) -> dict[str, Any]:
    """Plan a bounded multi-tool bundle using READ/SEARCH tools only."""
    raw = _clean(question, 1200)
    text = _norm(raw)
    limit = max(2, min(int(max_tools or MAX_BUNDLE_TOOLS), MAX_BUNDLE_TOOLS))
    if not text:
        return {
            "schema": BUNDLE_SCHEMA,
            "state": "NO_COMMAND",
            "selected": [],
            "selected_count": 0,
            "reason": "EMPTY_COMMAND",
            "executes_tools": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
        }
    if _sensitive_action_requested(text):
        return {
            "schema": BUNDLE_SCHEMA,
            "state": "BLOCKED_INTENT",
            "selected": [],
            "selected_count": 0,
            "reason": "SENSITIVE_OR_EXTERNAL_ACTION_REQUEST",
            "executes_tools": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
        }

    candidates = [
        row for row in _candidate_tools(text)
        if str(row.get("kind") or "") in BUNDLE_SAFE_KINDS
    ]
    candidates.sort(key=lambda row: (int(row["position"]), int(row["priority"]), -int(row["score"])))
    selected = candidates[:limit]
    state = "READY_MULTI" if len(selected) >= 2 else "SINGLE_OR_NONE"
    return {
        "schema": BUNDLE_SCHEMA,
        "state": state,
        "selected": selected,
        "selected_count": len(selected),
        "tool_ids": [str(row["tool_id"]) for row in selected],
        "kinds": [str(row["kind"]) for row in selected],
        "excluded_draft_from_bundle": any(
            str(row.get("kind") or "") == "DRAFT" for row in _candidate_tools(text)
        ),
        "max_tools": limit,
        "reason": "BOUNDED_SAFE_READ_BUNDLE" if state == "READY_MULTI" else "NOT_ENOUGH_READ_INTENTS",
        "executes_tools": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
    }


def _infer_specialist(question: Any) -> str:
    text = _norm(question)
    for specialist, hints in _SPECIALIST_HINTS:
        if any(hint in text for hint in hints):
            return specialist
    return "core"


def _arguments_for(tool_id: str, question: Any, runtime: Mapping[str, Any]) -> dict[str, Any]:
    if tool_id == "aion.memory.search":
        return {"query": _clean(question, 500)}
    if tool_id == "aion.memory.recall":
        return {
            "persona": _clean(runtime.get("persona") or "admin", 80),
            "tags": list(runtime.get("tags") or [])[:12] if isinstance(runtime.get("tags"), (list, tuple)) else [],
            "include_expired": False,
            "include_superseded": False,
        }
    if tool_id == "aion.specialists.snapshot":
        return {"specialist": _infer_specialist(question)}
    return {}


def _scalar(result: Mapping[str, Any], key: str) -> str:
    value = result.get(key)
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, (int, float, str)) and str(value).strip():
        return _clean(value, 80)
    return ""


def _result_summary(tool_id: str, execution: Mapping[str, Any]) -> str:
    state = str(execution.get("state") or "UNKNOWN").upper()
    if state != "SUCCESS":
        preflight = execution.get("preflight") if isinstance(execution.get("preflight"), Mapping) else {}
        blockers = [str(x) for x in list(preflight.get("blockers") or []) if str(x).strip()]
        suffix = " · ".join(blockers[:3]) if blockers else state
        return f"{tool_id}: handler não executado ({suffix})."

    result = execution.get("result") if isinstance(execution.get("result"), Mapping) else {}
    if tool_id == "aion.memory.search":
        return f"Memória canônica: {_scalar(result, 'canonical_count') or '0'} referência(s)."
    if tool_id == "aion.memory.recall":
        return f"Recall local: {_scalar(result, 'layered_count') or '0'} item(ns) elegíveis."
    if tool_id == "aion.checkpoint.inspect":
        integrity = result.get("integrity") if isinstance(result.get("integrity"), Mapping) else {}
        counts = result.get("counts") if isinstance(result.get("counts"), Mapping) else {}
        return (
            f"Checkpoint: versão {_scalar(result, 'checkpoint_version') or 'UNKNOWN'} · "
            f"integridade {_scalar(integrity, 'state') or 'UNKNOWN'} · "
            f"tarefas {_scalar(counts, 'tasks') or '0'} · eventos {_scalar(counts, 'events') or '0'}."
        )
    if tool_id == "aion.status.read":
        return "Quadro de status local consultado."
    if tool_id == "aion.tasks.summary":
        return (
            f"Tarefas: total {_scalar(result, 'total') or '0'} · "
            f"ativas {_scalar(result, 'active') or '0'} · "
            f"aguardando aprovação {_scalar(result, 'waiting_approval') or '0'} · "
            f"bloqueadas {_scalar(result, 'blocked') or '0'}."
        )
    if tool_id == "aion.missions.summary":
        return f"Missões: total {_scalar(result, 'total') or '0'} · ativas {_scalar(result, 'active') or '0'}."
    if tool_id == "aion.durable.summary":
        count = _scalar(result, "tasks") or _scalar(result, "total") or "0"
        return f"Tarefas duráveis: {count} registro(s)."
    if tool_id == "aion.approvals.summary":
        return f"Aprovações: {_scalar(result, 'total') or '0'} item(ns)."
    if tool_id == "aion.events.summary":
        total = _scalar(result, "total") or _scalar(result, "events") or "0"
        warnings = _scalar(result, "warnings") or "0"
        return f"Eventos: total {total} · warnings {warnings}."
    if tool_id == "aion.specialists.snapshot":
        truth = _scalar(result, "truth_state") or _scalar(result, "answer_truth") or "UNKNOWN"
        return (
            f"Especialista: input {_scalar(result, 'input_state') or 'UNKNOWN'} · "
            f"verdade {truth} · freshness {_scalar(result, 'freshness') or 'UNVERIFIED'}."
        )
    if tool_id == "aion.secretary.draft_brief":
        return "Briefing preparado somente como rascunho; nenhuma publicação foi executada."
    return "Consulta local executada sem efeito externo."


def _execute_one(
    tool_id: str,
    question: Any,
    runtime: Mapping[str, Any],
    *,
    hub: Mapping[str, Any] | None,
    portable_core: Mapping[str, Any] | None,
    access: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | None,
    source_kind: Any,
    authenticated_admin: bool,
    request_id: Any,
) -> dict[str, Any]:
    return execute_local_tool(
        tool_id,
        arguments=_arguments_for(tool_id, question, runtime),
        runtime_context=runtime,
        hub=hub if hub is not None else default_tool_hub(),
        portable_core=portable_core if portable_core is not None else default_portable_core(),
        access=access,
        feature_flags=feature_flags,
        source_kind=source_kind,
        authenticated_admin=authenticated_admin is True,
        approved=False,
        request_id=request_id,
    )


def orchestrate_local_command(
    question: Any,
    *,
    execute: bool = False,
    runtime_context: Mapping[str, Any] | None = None,
    hub: Mapping[str, Any] | None = None,
    portable_core: Mapping[str, Any] | None = None,
    access: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    source_kind: Any = "ADMIN",
    authenticated_admin: bool = False,
    request_id: Any = "",
) -> dict[str, Any]:
    """Plan and optionally execute one safe tool or a bounded safe read bundle."""
    single_plan = plan_local_command(question)
    bundle_plan = plan_local_bundle(question)
    is_multi = bundle_plan.get("state") == "READY_MULTI"
    if single_plan.get("state") == "BLOCKED_INTENT" or bundle_plan.get("state") == "BLOCKED_INTENT":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED_INTENT",
            "mode": "BLOCKED",
            "plan": single_plan,
            "bundle_plan": bundle_plan,
            "tool_id": "",
            "tool_ids": [],
            "kind": "",
            "execution_requested": execute is True,
            "executor_invoked": False,
            "handler_executed": False,
            "handlers_executed": 0,
            "automatic_execution": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
            "summary": "Pedido de ação sensível permanece bloqueado nesta camada.",
            "tool_result": None,
            "tool_results": [],
            "synthesis": synthesize_local_tool_results([]),
        }

    if not is_multi:
        plan = single_plan
        base = {
            "schema": SCHEMA,
            "question_present": bool(_clean(question, 1200)),
            "mode": "SINGLE",
            "plan": plan,
            "bundle_plan": bundle_plan,
            "tool_id": str(plan.get("tool_id") or ""),
            "tool_ids": [str(plan.get("tool_id"))] if plan.get("tool_id") else [],
            "kind": str(plan.get("kind") or ""),
            "execution_requested": execute is True,
            "executor_invoked": False,
            "handler_executed": False,
            "handlers_executed": 0,
            "automatic_execution": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
        }
        if plan.get("state") != "READY":
            base["state"] = str(plan.get("state") or "NO_MATCH")
            base["summary"] = ""
            base["tool_result"] = None
            base["tool_results"] = []
            base["synthesis"] = synthesize_local_tool_results([])
            return base
        if execute is not True:
            base["state"] = "PLANNED"
            base["summary"] = "Ferramenta local selecionada, mas o handler não foi executado nesta prévia."
            base["tool_result"] = None
            base["tool_results"] = []
            base["synthesis"] = synthesize_local_tool_results([])
            return base

        runtime = dict(runtime_context or {})
        execution = _execute_one(
            plan["tool_id"],
            question,
            runtime,
            hub=hub,
            portable_core=portable_core,
            access=access,
            feature_flags=feature_flags,
            source_kind=source_kind,
            authenticated_admin=authenticated_admin,
            request_id=request_id,
        )
        base["executor_invoked"] = True
        base["handler_executed"] = execution.get("state") == "SUCCESS"
        base["handlers_executed"] = 1 if base["handler_executed"] else 0
        base["state"] = str(execution.get("state") or "ERROR")
        synthesis = synthesize_local_tool_results([execution])
        base["summary"] = _result_summary(plan["tool_id"], execution) + " Síntese: " + str(synthesis.get("summary") or "")
        base["tool_result"] = execution
        base["tool_results"] = [execution]
        base["synthesis"] = synthesis
        traceability = build_local_traceability([execution], synthesis=synthesis)
        base["traceability"] = traceability
        if traceability.get("state") == "SECURITY_BLOCK":
            base["state"] = "SECURITY_BLOCK"
            base["summary"] = "Leitura local bloqueada por inconsistência no contrato de evidência."
        base["executive_response"] = compose_local_executive_response(
            synthesis,
            summaries=[_result_summary(plan["tool_id"], execution)],
            traceability=traceability,
        )
        return base

    selected = list(bundle_plan.get("selected") or [])
    base = {
        "schema": SCHEMA,
        "question_present": bool(_clean(question, 1200)),
        "mode": "MULTI_READ",
        "plan": single_plan,
        "bundle_plan": bundle_plan,
        "tool_id": str(selected[0].get("tool_id") or "") if selected else "",
        "tool_ids": [str(row.get("tool_id") or "") for row in selected],
        "kind": "READ_BUNDLE",
        "execution_requested": execute is True,
        "executor_invoked": False,
        "handler_executed": False,
        "handlers_executed": 0,
        "automatic_execution": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }
    if execute is not True:
        base["state"] = "PLANNED_MULTI"
        base["summary"] = f"{len(selected)} ferramentas locais READ/SEARCH selecionadas; nenhuma executada nesta prévia."
        base["tool_result"] = None
        base["tool_results"] = []
        base["synthesis"] = synthesize_local_tool_results([])
        return base

    runtime = dict(runtime_context or {})
    results = []
    summaries = []
    successful = 0
    final_state = "SUCCESS"
    for index, row in enumerate(selected):
        tool_id = str(row.get("tool_id") or "")
        execution = _execute_one(
            tool_id,
            question,
            runtime,
            hub=hub,
            portable_core=portable_core,
            access=access,
            feature_flags=feature_flags,
            source_kind=source_kind,
            authenticated_admin=authenticated_admin,
            request_id=f"{_clean(request_id, 60)}:{index + 1}" if request_id else f"local-bundle:{index + 1}",
        )
        results.append(execution)
        summaries.append(_result_summary(tool_id, execution))
        if execution.get("state") == "SUCCESS":
            successful += 1
            continue
        final_state = str(execution.get("state") or "ERROR")
        break

    base["executor_invoked"] = bool(results)
    base["handler_executed"] = successful > 0
    base["handlers_executed"] = successful
    base["state"] = final_state
    synthesis = synthesize_local_tool_results(results)
    base["summary"] = " ".join(summaries) + " Síntese: " + str(synthesis.get("summary") or "")
    base["tool_result"] = results[-1] if results else None
    base["tool_results"] = results
    base["synthesis"] = synthesis
    traceability = build_local_traceability(results, synthesis=synthesis)
    base["traceability"] = traceability
    if traceability.get("state") == "SECURITY_BLOCK":
        base["state"] = "SECURITY_BLOCK"
        base["summary"] = "Bundle local bloqueado por inconsistência no contrato de evidência."
    base["executive_response"] = compose_local_executive_response(
        synthesis,
        summaries=summaries,
        traceability=traceability,
    )
    base["stopped_early"] = len(results) < len(selected)
    return base


__all__ = [
    "SCHEMA",
    "BUNDLE_SCHEMA",
    "SAFE_KINDS",
    "BUNDLE_SAFE_KINDS",
    "MAX_BUNDLE_TOOLS",
    "command_catalog",
    "plan_local_command",
    "plan_local_bundle",
    "orchestrate_local_command",
]
