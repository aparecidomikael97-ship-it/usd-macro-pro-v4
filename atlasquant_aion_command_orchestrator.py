"""Safe local command bridge for AION.

This layer turns a user-initiated AION command into at most one local Tool Hub
call. Selection is deterministic. Execution is opt-in, defaults off, and every
selected tool still has to pass execute_local_tool(), which owns the Tool Hub
preflight and Guardian enforcement.

This module does not call providers, connectors, subprocesses, the network,
deployments, publishers, payment rails, brokers, or real trading.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_local_executor import execute_local_tool, local_allowlist
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_hub import default_tool_hub

SCHEMA = "ATLASQUANT_AION_LOCAL_COMMAND_V1"
SAFE_KINDS = frozenset({"READ", "SEARCH", "DRAFT"})

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


def plan_local_command(question: Any) -> dict[str, Any]:
    """Choose zero or one local tool without executing it."""
    raw = _clean(question, 1200)
    text = _norm(raw)
    if not text:
        return {
            "schema": SCHEMA,
            "state": "NO_COMMAND",
            "tool_id": "",
            "kind": "",
            "matches": [],
            "reason": "EMPTY_COMMAND",
            "executes_tool": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
        }
    if _sensitive_action_requested(text):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED_INTENT",
            "tool_id": "",
            "kind": "",
            "matches": [],
            "reason": "SENSITIVE_OR_EXTERNAL_ACTION_REQUEST",
            "executes_tool": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
        }

    catalog = _catalog_map()
    candidates = []
    for priority, (tool_id, phrases) in enumerate(_RULES):
        item = catalog.get(tool_id)
        if not item or item.get("kind") not in SAFE_KINDS:
            continue
        matched = [phrase for phrase in phrases if phrase in text]
        if not matched:
            continue
        score = max(len(phrase) for phrase in matched) * 10 + len(matched)
        candidates.append({
            "tool_id": tool_id,
            "kind": str(item.get("kind") or ""),
            "label": str(item.get("label") or tool_id),
            "score": score,
            "priority": priority,
            "matched_phrases": matched[:6],
        })

    if not candidates:
        return {
            "schema": SCHEMA,
            "state": "NO_MATCH",
            "tool_id": "",
            "kind": "",
            "matches": [],
            "reason": "NO_SAFE_LOCAL_TOOL_MATCH",
            "executes_tool": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
        }

    candidates.sort(key=lambda row: (-int(row["score"]), int(row["priority"]), str(row["tool_id"])))
    top = candidates[0]
    if len(candidates) > 1 and int(candidates[1]["score"]) == int(top["score"]):
        return {
            "schema": SCHEMA,
            "state": "AMBIGUOUS",
            "tool_id": "",
            "kind": "",
            "matches": candidates[:4],
            "reason": "MULTIPLE_EQUAL_LOCAL_TOOL_MATCHES",
            "executes_tool": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
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
        return f"Tool Hub local não executou o handler: {suffix}."

    result = execution.get("result") if isinstance(execution.get("result"), Mapping) else {}
    if tool_id == "aion.memory.search":
        return f"Memória canônica consultada: {_scalar(result, 'canonical_count') or '0'} referência(s)."
    if tool_id == "aion.memory.recall":
        return f"Recall local consultado: {_scalar(result, 'layered_count') or '0'} item(ns) elegíveis."
    if tool_id == "aion.checkpoint.inspect":
        integrity = result.get("integrity") if isinstance(result.get("integrity"), Mapping) else {}
        counts = result.get("counts") if isinstance(result.get("counts"), Mapping) else {}
        return (
            "Checkpoint inspecionado localmente: "
            f"versão {_scalar(result, 'checkpoint_version') or 'UNKNOWN'} · "
            f"integridade {_scalar(integrity, 'state') or 'UNKNOWN'} · "
            f"tarefas {_scalar(counts, 'tasks') or '0'} · "
            f"eventos {_scalar(counts, 'events') or '0'}."
        )
    if tool_id == "aion.status.read":
        return "Quadro de status local consultado pelo Tool Hub."
    if tool_id == "aion.tasks.summary":
        return (
            f"Tarefas locais: total {_scalar(result, 'total') or '0'} · "
            f"ativas {_scalar(result, 'active') or '0'} · "
            f"aguardando aprovação {_scalar(result, 'waiting_approval') or '0'} · "
            f"bloqueadas {_scalar(result, 'blocked') or '0'}."
        )
    if tool_id == "aion.missions.summary":
        return (
            f"Missões locais: total {_scalar(result, 'total') or '0'} · "
            f"ativas {_scalar(result, 'active') or '0'}."
        )
    if tool_id == "aion.durable.summary":
        count = _scalar(result, "tasks") or _scalar(result, "total") or "0"
        return f"Tarefas duráveis consultadas localmente: {count} registro(s)."
    if tool_id == "aion.approvals.summary":
        return f"Caixa de aprovações consultada: {_scalar(result, 'total') or '0'} item(ns)."
    if tool_id == "aion.events.summary":
        total = _scalar(result, "total") or _scalar(result, "events") or "0"
        warnings = _scalar(result, "warnings") or "0"
        return f"Eventos locais consultados: total {total} · warnings {warnings}."
    if tool_id == "aion.specialists.snapshot":
        truth = _scalar(result, "truth_state") or _scalar(result, "answer_truth") or "UNKNOWN"
        return (
            "Snapshot de especialista lido localmente: "
            f"input {_scalar(result, 'input_state') or 'UNKNOWN'} · "
            f"verdade {truth} · "
            f"freshness {_scalar(result, 'freshness') or 'UNVERIFIED'}."
        )
    if tool_id == "aion.secretary.draft_brief":
        return "Briefing local preparado somente como rascunho; nenhuma publicação foi executada."
    return "Consulta local executada pelo Tool Hub sem efeito externo."


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
    """Plan and optionally execute one safe local tool.

    execute defaults to False so previews and UI rendering cannot run handlers.
    Even with execute=True, execute_local_tool() performs the authoritative
    Tool Hub preflight before looking up a handler.
    """
    plan = plan_local_command(question)
    base = {
        "schema": SCHEMA,
        "question_present": bool(_clean(question, 1200)),
        "plan": plan,
        "tool_id": str(plan.get("tool_id") or ""),
        "kind": str(plan.get("kind") or ""),
        "execution_requested": bool(execute),
        "executor_invoked": False,
        "handler_executed": False,
        "automatic_execution": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }
    if plan.get("state") != "READY":
        base["state"] = str(plan.get("state") or "NO_MATCH")
        base["summary"] = (
            "Pedido de ação sensível permanece bloqueado nesta camada."
            if plan.get("state") == "BLOCKED_INTENT"
            else ""
        )
        base["tool_result"] = None
        return base

    if not execute:
        base["state"] = "PLANNED"
        base["summary"] = "Ferramenta local selecionada, mas o handler não foi executado nesta prévia."
        base["tool_result"] = None
        return base

    runtime = dict(runtime_context or {})
    execution = execute_local_tool(
        plan["tool_id"],
        arguments=_arguments_for(plan["tool_id"], question, runtime),
        runtime_context=runtime,
        hub=hub if hub is not None else default_tool_hub(),
        portable_core=portable_core if portable_core is not None else default_portable_core(),
        access=access,
        feature_flags=feature_flags,
        source_kind=source_kind,
        authenticated_admin=bool(authenticated_admin),
        approved=False,
        request_id=request_id,
    )
    base["executor_invoked"] = True
    base["handler_executed"] = execution.get("state") == "SUCCESS"
    base["state"] = str(execution.get("state") or "ERROR")
    base["summary"] = _result_summary(plan["tool_id"], execution)
    base["tool_result"] = execution
    return base


__all__ = [
    "SCHEMA",
    "SAFE_KINDS",
    "command_catalog",
    "plan_local_command",
    "orchestrate_local_command",
]
