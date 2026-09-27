"""Offline anti-drift auditor for the local AION tool path.

The auditor inspects registries, handler tables, command rules, envelopes,
synthesis, executive response, admin source and workflow filters. It does not
execute connectors, open a network socket, publish, deploy, move money or
trade. A PASS result means the inspected contracts still agree. It is not a
security score and it does not authorize any action.
"""
from __future__ import annotations

import ast
import fnmatch
import re
import sys
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import atlasquant_aion_command_orchestrator as command
import atlasquant_aion_local_executor as executor
from atlasquant_aion_command_orchestrator import (
    BUNDLE_SAFE_KINDS,
    MAX_BUNDLE_TOOLS,
    orchestrate_local_command,
    plan_local_bundle,
    plan_local_command,
)
from atlasquant_aion_ecosystem import OFFICIAL_AREA_IDS
from atlasquant_aion_local_executor import execute_local_tool, local_allowlist
from atlasquant_aion_local_response import compose_local_executive_response
from atlasquant_aion_local_synthesis import synthesize_local_tool_results
from atlasquant_aion_local_traceability import SOURCE_CATALOG, build_local_traceability, local_contract_fingerprint
from atlasquant_aion_memory import default_checkpoint
from atlasquant_aion_memory_layers import remember
from atlasquant_aion_observability import is_secret_key, redact_text
from atlasquant_aion_portable import default_portable_core
from atlasquant_aion_tool_hub import (
    DEFAULT_TOOLS,
    TOOL_KINDS,
    TOOL_STATES,
    default_tool_hub,
)

SCHEMA = "ATLASQUANT_AION_CONTRACT_AUDIT_V1"
ROOT = Path(__file__).resolve().parent
RESULT_SCHEMA = "ATLASQUANT_AION_LOCAL_TOOL_RESULT_V1"
SAFE_KINDS = frozenset({"READ", "SEARCH", "DRAFT"})
FORBIDDEN_KINDS = frozenset({"WRITE", "PUBLISH", "PRODUCTION", "SECRETS", "FINANCIAL"})
ENVELOPE_FIELDS = (
    "schema", "request_id", "tool_id", "workspace_id", "kind", "contract_fingerprint", "state", "result",
    "truncated", "preflight", "provenance", "truth", "security", "executes_action",
    "external_action_executed", "real_orders_enabled", "tool_output_is_authority",
)
RESULT_STATES = frozenset({"SUCCESS", "BLOCKED", "DEGRADED", "ERROR"})
CRITICAL_MODULES = (
    "atlasquant_aion_tool_hub.py",
    "atlasquant_aion_local_executor.py",
    "atlasquant_aion_command_orchestrator.py",
    "atlasquant_aion_local_synthesis.py",
    "atlasquant_aion_local_response.py",
    "atlasquant_aion_local_traceability.py",
    "atlasquant_aion_admin.py",
)
CRITICAL_TESTS = (
    "test_atlasquant_aion_tool_hub.py",
    "test_atlasquant_aion_local_executor.py",
    "test_atlasquant_aion_command_orchestrator.py",
    "test_atlasquant_aion_local_synthesis.py",
    "test_atlasquant_aion_local_response.py",
    "test_atlasquant_aion_local_traceability.py",
    "test_atlasquant_aion_local_security_matrix.py",
    "test_atlasquant_aion_contract_auditor.py",
    "test_atlasquant_aion_admin.py",
)
STATIC_MODULES = (
    "atlasquant_aion_local_executor.py",
    "atlasquant_aion_command_orchestrator.py",
    "atlasquant_aion_local_synthesis.py",
    "atlasquant_aion_local_response.py",
    "atlasquant_aion_local_traceability.py",
)
BANNED_CALLS = frozenset({"eval", "exec", "__import__", "getattr"})
BANNED_IMPORTS = frozenset({
    "importlib", "subprocess", "socket", "requests", "urllib",
    "http", "ftplib", "smtplib", "telnetlib",
})
SECRET_NAMES = (
    "password", "passwd", "senha", "senha_admin", "token", "api_key", "api-key",
    "chave_de_api", "chave de api", "authorization", "autorizacao", "autorização", "secret",
    "segredo", "cookie", "credential", "credencial", "bearer", "client_secret",
    "access_token",
)
SENSITIVE_PHRASES = (
    "faça deploy",
    "faz o deploy",
    "execute deploy",
    "faça merge",
    "publique",
    "publicar no Instagram",
    "publicação imediata",
    "salvar checkpoint",
    "grave o checkpoint",
    "revelar senha",
    "mostrar token",
    "mostrar secret",
    "mostrar chave de API",
    "ativar API paga",
    "cobrar cliente",
    "fazer pagamento",
    "enviar ordem real",
    "executar trade real",
    "comprar ativo real",
    "vender no mercado real",
)
BOUNDARY_CASES = (
    ("lembra", "aion.memory.search", ("deslembrado", "lembranca", "relembranca", "deslembra")),
    ("lembrar", "aion.memory.search", ("deslembrar", "relembranca", "lembrarextra")),
)
LOCAL_CONTRACT = (
    ("aion.memory.search", "SEARCH", "central", "search", ("memory:read",)),
    ("aion.memory.recall", "SEARCH", "central", "search", ("memory:read",)),
    ("aion.checkpoint.inspect", "READ", "administration", "read", ("checkpoint:read",)),
    ("aion.status.read", "READ", "central", "read", ("status:read",)),
    ("aion.tasks.summary", "READ", "administration", "read", ("tasks:read",)),
    ("aion.missions.summary", "READ", "administration", "read", ("missions:read",)),
    ("aion.durable.summary", "READ", "development", "read", ("durable:read",)),
    ("aion.approvals.summary", "READ", "administration", "read", ("approvals:read",)),
    ("aion.events.summary", "READ", "administration", "read", ("events:read",)),
    ("aion.specialists.snapshot", "READ", "central", "read", ("specialist:read",)),
    ("aion.secretary.draft_brief", "DRAFT", "administration", "draft", ("secretary:draft",)),
)
WRITE_CONTRACT = (
    "aion.checkpoint.prepare_save", "WRITE", "administration", "save_checkpoint",
    ("checkpoint:write",), True,
)
ADMIN = {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}}
USER = {"role": "USER", "session": {"username": "cliente", "role": "USER"}}
_SENTINEL = "contract-auditor-sentinel"
_TOKEN = "ghp_CONTRACTAUDITOR1234567890"
_MISSING = object()


def _finding(invariant_id: str, module: str, description: str, *, severity: str = "FAIL") -> dict[str, str]:
    return {
        "invariant_id": invariant_id,
        "module": module,
        "description": description,
        "severity": severity,
    }


def _index(tools: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("tool_id") or ""): dict(item) for item in tools}


def local_security_violations(envelope: Mapping[str, Any] | None) -> list[str]:
    """Return objective security-invariant failures for one local envelope."""
    item = dict(envelope or {})
    security = item.get("security") if isinstance(item.get("security"), Mapping) else {}
    provenance = item.get("provenance") if isinstance(item.get("provenance"), Mapping) else {}
    violations = []
    expected_false = {
        "network_called": security.get("network_called"),
        "connector_called": security.get("connector_called"),
        "external_side_effects": security.get("external_side_effects"),
        "permissions_expanded": security.get("permissions_expanded"),
        "secrets_included": security.get("secrets_included"),
        "executes_action": item.get("executes_action"),
        "external_action_executed": item.get("external_action_executed"),
        "real_orders_enabled": item.get("real_orders_enabled"),
        "tool_output_is_authority": item.get("tool_output_is_authority"),
    }
    for key, value in expected_false.items():
        if value is not False:
            violations.append(f"{key}={value!r}")
    if provenance.get("local_only") is not True:
        violations.append(f"provenance.local_only={provenance.get('local_only')!r}")
    if security.get("sanitized") is not True:
        violations.append(f"sanitized={security.get('sanitized')!r}")
    return violations


def audit_tool_rows(tools: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Audit a raw tool registry. Duplicates are not normalized away."""
    findings = []
    seen: set[str] = set()
    expected = {row[0]: row for row in LOCAL_CONTRACT}
    write_id = WRITE_CONTRACT[0]
    for item in tools:
        tool_id = str(item.get("tool_id") or "")
        if not tool_id.strip():
            findings.append(_finding("registry.empty_id", "atlasquant_aion_tool_hub", "Tool com ID vazio."))
            continue
        if tool_id in seen:
            findings.append(_finding(
                "registry.duplicate_id", "atlasquant_aion_tool_hub",
                f"tool_id duplicado: {tool_id}.",
            ))
        seen.add(tool_id)
        kind = str(item.get("kind") or "")
        state = str(item.get("state") or "")
        workspace = str(item.get("workspace_id") or "")
        if kind not in TOOL_KINDS:
            findings.append(_finding("registry.kind", "atlasquant_aion_tool_hub", f"{tool_id} kind inválido: {kind}."))
        if state not in TOOL_STATES:
            findings.append(_finding("registry.state", "atlasquant_aion_tool_hub", f"{tool_id} state inválido: {state}."))
        if workspace not in OFFICIAL_AREA_IDS:
            findings.append(_finding(
                "registry.workspace", "atlasquant_aion_tool_hub",
                f"{tool_id} workspace fora do registro canônico: {workspace}.",
            ))
        action = str(item.get("guardian_action") or "")
        scopes = tuple(item.get("required_scopes") or ())
        if tool_id in expected:
            exp_id, exp_kind, exp_ws, exp_action, exp_scopes = expected[tool_id]
            del exp_id
            if kind != exp_kind or workspace != exp_ws or state != "LOCAL_READY":
                findings.append(_finding(
                    "registry.local_shape", "atlasquant_aion_tool_hub",
                    f"{tool_id} divergiu do contrato local ({kind}, {workspace}, {state}).",
                ))
            if item.get("connector_id"):
                findings.append(_finding(
                    "registry.local_connector", "atlasquant_aion_tool_hub",
                    f"{tool_id} local não pode ter connector_id.",
                ))
            if bool(item.get("external_side_effects")):
                findings.append(_finding(
                    "registry.local_side_effect", "atlasquant_aion_tool_hub",
                    f"{tool_id} local não pode ter external_side_effects.",
                ))
            if kind not in SAFE_KINDS:
                findings.append(_finding(
                    "registry.local_kind", "atlasquant_aion_tool_hub",
                    f"{tool_id} local saiu de READ/SEARCH/DRAFT.",
                ))
            if action != exp_action or scopes != exp_scopes:
                findings.append(_finding(
                    "registry.guardian_scope", "atlasquant_aion_tool_hub",
                    f"{tool_id} guardian_action/scopes divergiram ({action}, {scopes}).",
                ))
        elif tool_id == write_id:
            _, exp_kind, exp_ws, exp_action, exp_scopes, exp_side = WRITE_CONTRACT
            if kind != exp_kind or state != "LOCAL_READY" or workspace != exp_ws:
                findings.append(_finding(
                    "registry.write_shape", "atlasquant_aion_tool_hub",
                    f"{tool_id} deixou de ser WRITE local no workspace esperado.",
                ))
            if action != exp_action or scopes != exp_scopes or bool(item.get("external_side_effects")) is not exp_side:
                findings.append(_finding(
                    "registry.write_policy", "atlasquant_aion_tool_hub",
                    f"{tool_id} mudou ação, escopo ou efeito externo.",
                ))
        else:
            findings.append(_finding(
                "registry.unexpected_tool", "atlasquant_aion_tool_hub",
                f"Tool fora do contrato fechado: {tool_id}.",
            ))
    for tool_id in list(expected) + [write_id]:
        if tool_id not in seen:
            findings.append(_finding(
                "registry.missing_tool", "atlasquant_aion_tool_hub",
                f"Tool ausente do registry: {tool_id}.",
            ))
    if len(list(tools)) != len(LOCAL_CONTRACT) + 1:
        findings.append(_finding(
            "registry.count", "atlasquant_aion_tool_hub",
            f"Total de tools {len(list(tools))} diferente de {len(LOCAL_CONTRACT) + 1}.",
        ))
    return findings


def audit_allowlist_rows(
    allowlist: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings = []
    hub = _index(tools)
    expected = [row[0] for row in LOCAL_CONTRACT]
    ids = [str(row.get("tool_id") or "") for row in allowlist]
    if ids != expected:
        findings.append(_finding(
            "allowlist.identity", "atlasquant_aion_local_executor",
            f"Allowlist {ids} divergiu das 11 ferramentas locais.",
        ))
    if len(ids) != len(set(ids)):
        findings.append(_finding(
            "allowlist.duplicate", "atlasquant_aion_local_executor",
            "Allowlist contém tool_id repetido.",
        ))
    for row in allowlist:
        tool_id = str(row.get("tool_id") or "")
        tool = hub.get(tool_id)
        if tool is None:
            findings.append(_finding(
                "allowlist.missing_hub", "atlasquant_aion_local_executor",
                f"{tool_id} está na allowlist e não está no Hub.",
            ))
            continue
        if str(row.get("kind") or "") != str(tool.get("kind") or ""):
            findings.append(_finding(
                "allowlist.kind", "atlasquant_aion_local_executor",
                f"{tool_id} kind da allowlist divergiu do Hub.",
            ))
        if str(tool.get("kind") or "") not in SAFE_KINDS:
            findings.append(_finding(
                "allowlist.forbidden_kind", "atlasquant_aion_local_executor",
                f"{tool_id} entrou na allowlist com kind {tool.get('kind')}.",
            ))
        if tool.get("connector_id") or tool.get("state") != "LOCAL_READY" or tool.get("external_side_effects"):
            findings.append(_finding(
                "allowlist.local_flags", "atlasquant_aion_local_executor",
                f"{tool_id} não está local, pronto e sem efeito externo.",
            ))
        if "workspace_id" in row and str(row.get("workspace_id") or "") != str(tool.get("workspace_id") or ""):
            findings.append(_finding(
                "allowlist.workspace", "atlasquant_aion_local_executor",
                f"{tool_id} workspace da allowlist divergiu do Hub.",
            ))
    if WRITE_CONTRACT[0] in ids:
        findings.append(_finding(
            "allowlist.write", "atlasquant_aion_local_executor",
            "aion.checkpoint.prepare_save entrou na allowlist local.",
        ))
    return findings


def audit_handler_map(
    handlers: Mapping[str, Any],
    allowlist: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    findings = []
    hub = _index(tools)
    allow_ids = [str(row.get("tool_id") or "") for row in allowlist]
    handler_ids = list(handlers)
    if handler_ids != allow_ids:
        findings.append(_finding(
            "handlers.identity", "atlasquant_aion_local_executor",
            f"Tabela de handlers {handler_ids} divergiu da allowlist {allow_ids}.",
        ))
    seen_functions = {}
    for tool_id, fn in handlers.items():
        tool = hub.get(str(tool_id))
        kind = str((tool or {}).get("kind") or "")
        if tool is None:
            findings.append(_finding(
                "handlers.unregistered", "atlasquant_aion_local_executor",
                f"Handler sem registry: {tool_id}.",
            ))
        elif kind in FORBIDDEN_KINDS:
            findings.append(_finding(
                "handlers.forbidden_kind", "atlasquant_aion_local_executor",
                f"Handler para kind proibido {kind}: {tool_id}.",
            ))
        if not callable(fn):
            findings.append(_finding(
                "handlers.not_callable", "atlasquant_aion_local_executor",
                f"Handler de {tool_id} não é callable.",
            ))
            continue
        previous = seen_functions.get(id(fn))
        if previous:
            findings.append(_finding(
                "handlers.alias", "atlasquant_aion_local_executor",
                f"{tool_id} reutiliza o callable de {previous}.",
            ))
        seen_functions[id(fn)] = str(tool_id)
    if WRITE_CONTRACT[0] in handlers:
        findings.append(_finding(
            "handlers.write", "atlasquant_aion_local_executor",
            "prepare_save possui handler local executável.",
        ))
    for tool_id, *_rest in LOCAL_CONTRACT:
        if tool_id not in handlers:
            findings.append(_finding(
                "handlers.missing", "atlasquant_aion_local_executor",
                f"Tool local sem handler: {tool_id}.",
            ))
    return findings


def audit_command_rules(
    rules: Sequence[tuple[Any, Sequence[Any]]],
    tools: Sequence[Mapping[str, Any]],
    allowlist: Sequence[Mapping[str, Any]],
    handlers: Mapping[str, Any],
) -> list[dict[str, str]]:
    findings = []
    hub = _index(tools)
    allow_ids = {str(row.get("tool_id") or "") for row in allowlist}
    seen = set()
    for tool_id, phrases in rules:
        key = str(tool_id or "")
        if key in seen:
            findings.append(_finding(
                "rules.duplicate", "atlasquant_aion_command_orchestrator",
                f"Regra duplicada para {key}.",
            ))
        seen.add(key)
        tool = hub.get(key)
        if tool is None or key not in allow_ids or key not in handlers:
            findings.append(_finding(
                "rules.unbound", "atlasquant_aion_command_orchestrator",
                f"Regra aponta para tool fora do conjunto local: {key}.",
            ))
            continue
        if str(tool.get("kind") or "") not in SAFE_KINDS:
            findings.append(_finding(
                "rules.sensitive", "atlasquant_aion_command_orchestrator",
                f"Regra textual aponta para kind sensível: {key}.",
            ))
        if not tuple(phrases):
            findings.append(_finding(
                "rules.empty", "atlasquant_aion_command_orchestrator",
                f"Regra sem frases: {key}.",
            ))
    if WRITE_CONTRACT[0] in seen:
        findings.append(_finding(
            "rules.write", "atlasquant_aion_command_orchestrator",
            "prepare_save entrou nas regras de comando local.",
        ))
    return findings


def audit_static_source(path: Path) -> list[dict[str, str]]:
    findings = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module = path.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BANNED_IMPORTS:
                    findings.append(_finding(
                        "static.import", module, f"Import proibido: {alias.name}.",
                    ))
        elif isinstance(node, ast.ImportFrom):
            root = str(node.module or "").split(".", 1)[0]
            if root in BANNED_IMPORTS:
                findings.append(_finding(
                    "static.import", module, f"Import proibido: {node.module}.",
                ))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in BANNED_CALLS:
                findings.append(_finding(
                    "static.call", module, f"Chamada proibida: {name}.",
                ))
            if name in {"system", "Popen"}:
                findings.append(_finding(
                    "static.process", module, f"Execução de processo: {name}.",
                ))
    function = _function(tree, "execute_local_tool") if module == "atlasquant_aion_local_executor.py" else None
    if module == "atlasquant_aion_local_executor.py":
        if function is None:
            findings.append(_finding(
                "static.executor_missing", module, "execute_local_tool não foi encontrada.",
            ))
        else:
            plan_line = _first_lineno(function, lambda node: isinstance(node, ast.Call) and _call_name(node) == "plan_tool_call")
            handler_line = _first_lineno(function, lambda node: _mentions_handlers(node))
            if plan_line is None or handler_line is None or plan_line > handler_line:
                findings.append(_finding(
                    "static.preflight_order", module,
                    "execute_local_tool resolve handler antes de plan_tool_call.",
                ))
            if _kw_default(function, "approved") is not False or _kw_default(function, "authenticated_admin") is not False:
                findings.append(_finding(
                    "static.approval_default", module,
                    "approved ou authenticated_admin deixou de ter default False.",
                ))
    if module == "atlasquant_aion_command_orchestrator.py":
        for fn_name in ("plan_local_command", "plan_local_bundle"):
            fn = _function(tree, fn_name)
            if fn and _first_lineno(fn, lambda node: isinstance(node, ast.Call) and _call_name(node) == "execute_local_tool") is not None:
                findings.append(_finding(
                    "static.plan_executes", module, f"{fn_name} chama o executor.",
                ))
        execute_one = _function(tree, "_execute_one")
        if execute_one is None or not _call_passes_constant(execute_one, "execute_local_tool", "approved", False):
            findings.append(_finding(
                "static.approved_false", module,
                "_execute_one não passa approved=False de forma estática.",
            ))
    if module in {"atlasquant_aion_local_synthesis.py", "atlasquant_aion_local_response.py"}:
        if _first_lineno(tree, lambda node: isinstance(node, ast.Call) and _call_name(node) == "execute_local_tool") is not None:
            findings.append(_finding(
                "static.layer_executes", module, "A camada chama execute_local_tool.",
            ))
        imported = _imported_modules(tree)
        if "atlasquant_aion_local_executor" in imported:
            findings.append(_finding(
                "static.layer_imports_executor", module,
                "A camada importa o executor.",
            ))
    return findings


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _first_lineno(tree: ast.AST, predicate) -> int | None:
    best = None
    for node in ast.walk(tree):
        lineno = node.lineno if hasattr(node, "lineno") else None
        if lineno and predicate(node):
            if best is None or lineno < best:
                best = lineno
    return best


def _mentions_handlers(node: ast.AST) -> bool:
    if isinstance(node, ast.Name) and node.id == "_HANDLERS":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "_HANDLERS":
        return True
    return False


def _kw_default(fn: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> Any:
    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if arg.arg == name:
            if isinstance(default, ast.Constant):
                return default.value
            return _MISSING
    return _MISSING


def _call_passes_constant(fn: ast.AST, call_name: str, keyword: str, expected: Any) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or _call_name(node) != call_name:
            continue
        for item in node.keywords:
            if item.arg == keyword and isinstance(item.value, ast.Constant) and item.value.value is expected:
                return True
    return False


def _imported_modules(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _norm_phrase(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _phrase_variants(text: str) -> tuple[str, ...]:
    spaced = re.sub(r"\s+", "   ", text)
    return tuple(dict.fromkeys((
        text,
        text.upper(),
        text.casefold(),
        f"  {text}  ",
        text + "\x00",
        text + ".",
        text + "?",
        spaced,
    )))


def _glued(phrase: str) -> tuple[str, ...]:
    compact = phrase.replace(" ", "")
    return (f"pre{compact}zado", f"{compact}extra", f"xx{compact}xx")


@contextmanager
def _temporary_handler(tool_id: str, fn):
    previous = executor._HANDLERS.get(tool_id, _MISSING)
    executor._HANDLERS[tool_id] = fn
    try:
        yield
    finally:
        if previous is _MISSING:
            executor._HANDLERS.pop(tool_id, None)
        else:
            executor._HANDLERS[tool_id] = previous


def _hub_replacing(tool_id: str, **changes) -> dict[str, Any]:
    hub = default_tool_hub()
    tools = []
    for tool in hub["tools"]:
        item = dict(tool)
        if item["tool_id"] == tool_id:
            item.update(changes)
        tools.append(item)
    hub["tools"] = tools
    return hub


def _handler_not_called(tool_id: str, **kwargs) -> tuple[dict[str, Any], bool]:
    called = {"value": False}

    def spy(*_args, **_kwargs):
        called["value"] = True
        return {"leaked": _SENTINEL}

    with _temporary_handler(tool_id, spy):
        out = execute_local_tool(
            tool_id,
            runtime_context={"checkpoint": default_checkpoint()},
            approved=kwargs.pop("approved", False),
            **kwargs,
        )
    return out, called["value"]


def _audit_runtime_gates() -> list[dict[str, str]]:
    findings = []
    order = []
    real_plan = executor.plan_tool_call

    def tracking_plan(*args, **kwargs):
        order.append("plan")
        return real_plan(*args, **kwargs)

    def tracking_handler(*_args, **_kwargs):
        order.append("handler")
        return {"total": 0, "active": 0, "waiting_approval": 0, "blocked": 0}

    executor.plan_tool_call = tracking_plan
    try:
        with _temporary_handler("aion.tasks.summary", tracking_handler):
            success = execute_local_tool(
                "aion.tasks.summary",
                runtime_context={"checkpoint": default_checkpoint()},
                access=ADMIN,
                source_kind="ADMIN",
                authenticated_admin=True,
                approved=False,
            )
    finally:
        executor.plan_tool_call = real_plan
    if order != ["plan", "handler"]:
        findings.append(_finding(
            "gate.order", "atlasquant_aion_local_executor",
            f"Ordem observada {order}; o preflight precisa preceder o handler.",
        ))
    if success.get("state") != "SUCCESS" or local_security_violations(success):
        findings.append(_finding(
            "gate.success_invariants", "atlasquant_aion_local_executor",
            "A leitura admin autenticada não preservou o envelope seguro.",
        ))

    probes = (
        ("missing", "aion.does.not.exist", {}),
        ("disabled", "aion.status.read", {"hub": _hub_replacing("aion.status.read", state="DISABLED")}),
        ("connector", "aion.status.read", {"hub": _hub_replacing("aion.status.read", connector_id="ghost-feed")}),
        ("source", "aion.status.read", {"source_kind": "EXTERNAL_AI", "authenticated_admin": True, "access": ADMIN}),
        ("guardian", "aion.status.read", {"source_kind": "ADMIN", "authenticated_admin": True, "access": USER}),
        ("write", WRITE_CONTRACT[0], {"approved": True, "source_kind": "ADMIN", "authenticated_admin": True, "access": ADMIN}),
    )
    for name, tool_id, kwargs in probes:
        kwargs.setdefault("access", ADMIN)
        kwargs.setdefault("source_kind", "ADMIN")
        kwargs.setdefault("authenticated_admin", True)
        out, called = _handler_not_called(tool_id, **kwargs)
        if called or out.get("state") not in {"BLOCKED", "DEGRADED"}:
            findings.append(_finding(
                "gate.blocked_handler", "atlasquant_aion_local_executor",
                f"Sonda {name} chamou handler ou não bloqueou ({out.get('state')}).",
            ))
        if local_security_violations(out):
            findings.append(_finding(
                "gate.blocked_invariants", "atlasquant_aion_local_executor",
                f"Sonda {name} violou invariantes: {local_security_violations(out)}.",
            ))
    return findings


def _audit_forbidden_kinds() -> list[dict[str, str]]:
    findings = []
    for kind in FORBIDDEN_KINDS:
        out, called = _handler_not_called(
            "aion.status.read",
            hub=_hub_replacing("aion.status.read", kind=kind, guardian_action="read", connector_id="", state="LOCAL_READY"),
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
            approved=True,
        )
        if called or out.get("state") != "BLOCKED":
            findings.append(_finding(
                "kinds.forbidden", "atlasquant_aion_local_executor",
                f"Kind {kind} com guardian_action read foi executado ({out.get('state')}).",
            ))
    return findings


def _audit_phrases() -> list[dict[str, str]]:
    findings = []
    explicit = {phrase: tool_id for phrase, tool_id, _negatives in BOUNDARY_CASES}
    negatives = {phrase: words for phrase, _tool_id, words in BOUNDARY_CASES}
    for tool_id, phrases in command._RULES:
        for phrase in phrases:
            out = plan_local_command(phrase)
            if out.get("state") != "READY" or out.get("tool_id") != tool_id:
                findings.append(_finding(
                    "phrases.exact", "atlasquant_aion_command_orchestrator",
                    f"Frase {phrase!r} não selecionou {tool_id} ({out.get('state')}, {out.get('tool_id')}).",
                ))
            for glued in _glued(_norm_phrase(phrase)):
                glued_out = plan_local_command(glued)
                if glued_out.get("tool_id") == tool_id or glued_out.get("state") == "READY":
                    findings.append(_finding(
                        "phrases.glued", "atlasquant_aion_command_orchestrator",
                        f"{glued!r} selecionou ferramenta a partir de {phrase!r}.",
                    ))
    for phrase, tool_id in explicit.items():
        out = plan_local_command(phrase)
        if out.get("tool_id") != tool_id:
            findings.append(_finding(
                "phrases.short", "atlasquant_aion_command_orchestrator",
                f"{phrase!r} deixou de selecionar {tool_id}.",
            ))
        for word in negatives[phrase]:
            blocked = plan_local_command(word)
            if blocked.get("tool_id") or blocked.get("state") not in {"NO_MATCH", "NO_COMMAND"}:
                findings.append(_finding(
                    "phrases.boundary", "atlasquant_aion_command_orchestrator",
                    f"{word!r} disparou {blocked.get('tool_id') or blocked.get('state')}.",
                ))
    return findings


def _audit_sensitive_intents() -> list[dict[str, str]]:
    findings = []
    original = command.execute_local_tool
    called = {"value": False}

    def spy(*_args, **_kwargs):
        called["value"] = True
        return {"state": "SUCCESS"}

    command.execute_local_tool = spy
    try:
        for phrase in SENSITIVE_PHRASES:
            for variant in _phrase_variants(phrase):
                out = plan_local_command(variant)
                executed = orchestrate_local_command(variant, execute=True, access=ADMIN, authenticated_admin=True)
                if out.get("state") != "BLOCKED_INTENT" or out.get("tool_id") or out.get("kind") in SAFE_KINDS:
                    findings.append(_finding(
                        "intents.blocked", "atlasquant_aion_command_orchestrator",
                        f"{variant!r} não ficou BLOCKED_INTENT ({out.get('state')}, {out.get('tool_id')}).",
                    ))
                    return findings
                if executed.get("executor_invoked") or executed.get("tool_ids"):
                    findings.append(_finding(
                        "intents.executor", "atlasquant_aion_command_orchestrator",
                        f"{variant!r} acionou o executor.",
                    ))
                    return findings
    finally:
        command.execute_local_tool = original
    if called["value"]:
        findings.append(_finding(
            "intents.spy", "atlasquant_aion_command_orchestrator",
            "Uma intenção sensível chamou execute_local_tool.",
        ))
    return findings


def _audit_bundles() -> list[dict[str, str]]:
    findings = []
    if MAX_BUNDLE_TOOLS != 3 or BUNDLE_SAFE_KINDS != frozenset({"READ", "SEARCH"}):
        findings.append(_finding(
            "bundle.constants", "atlasquant_aion_command_orchestrator",
            "O bundle deixou de ser no máximo 3 READ/SEARCH.",
        ))
    expected = {
        "onde paramos e o que falta?": ["aion.memory.search", "aion.tasks.summary"],
        "status geral e tarefas pendentes": ["aion.status.read", "aion.tasks.summary"],
        "missões ativas e aprovações pendentes": ["aion.missions.summary", "aion.approvals.summary"],
        "checkpoint mestre e eventos locais": ["aion.checkpoint.inspect", "aion.events.summary"],
    }
    for question, tool_ids in expected.items():
        first = plan_local_bundle(question)
        second = plan_local_bundle(question)
        if first != second or first.get("tool_ids") != tool_ids:
            findings.append(_finding(
                "bundle.order", "atlasquant_aion_command_orchestrator",
                f"Bundle instável para {question!r}: {first.get('tool_ids')}.",
            ))
        if any(kind not in BUNDLE_SAFE_KINDS for kind in first.get("kinds") or []):
            findings.append(_finding(
                "bundle.kind", "atlasquant_aion_command_orchestrator",
                f"Bundle de {question!r} saiu de READ/SEARCH.",
            ))
    capped = plan_local_bundle("onde paramos, o que falta, aprovações pendentes e eventos locais")
    if capped.get("selected_count") != 3 or "aion.events.summary" in (capped.get("tool_ids") or []):
        findings.append(_finding(
            "bundle.limit", "atlasquant_aion_command_orchestrator",
            f"O quarto intent não foi descartado: {capped.get('tool_ids')}.",
        ))
    mixed = plan_local_bundle("briefing executivo, onde paramos e resumo de tarefas")
    if "aion.secretary.draft_brief" in (mixed.get("tool_ids") or []) or "DRAFT" in (mixed.get("kinds") or []):
        findings.append(_finding(
            "bundle.draft", "atlasquant_aion_command_orchestrator",
            "DRAFT entrou no bundle.",
        ))
    loose = plan_local_bundle("memória canônica, tarefas e aprovações")
    if loose.get("tool_ids") != ["aion.memory.search"]:
        findings.append(_finding(
            "bundle.loose_words", "atlasquant_aion_command_orchestrator",
            f"Palavras soltas inventaram tools: {loose.get('tool_ids')}.",
        ))
    repeated = plan_local_bundle("resumo de tarefas resumo de tarefas")
    if repeated.get("tool_ids") != ["aion.tasks.summary"]:
        findings.append(_finding(
            "bundle.duplicate_intent", "atlasquant_aion_command_orchestrator",
            "A mesma intenção foi duplicada no bundle.",
        ))
    for question in expected:
        if WRITE_CONTRACT[0] in (plan_local_bundle(question).get("tool_ids") or []):
            findings.append(_finding(
                "bundle.write", "atlasquant_aion_command_orchestrator",
                "WRITE entrou num bundle de leitura.",
            ))
    original = command.execute_local_tool
    calls = []

    def spy(tool_id, *args, **kwargs):
        calls.append((tool_id, kwargs.get("approved")))
        return original(tool_id, *args, **kwargs)

    command.execute_local_tool = spy
    try:
        preview = orchestrate_local_command("status geral e tarefas pendentes", execute=False)
        if preview.get("executor_invoked") or calls:
            findings.append(_finding(
                "bundle.preview", "atlasquant_aion_command_orchestrator",
                "execute=False chamou o executor.",
            ))
        calls.clear()
        executed = orchestrate_local_command(
            "status geral e tarefas pendentes",
            execute=True,
            runtime_context={"checkpoint": default_checkpoint()},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
        if [tool_id for tool_id, _approved in calls] != ["aion.status.read", "aion.tasks.summary"]:
            findings.append(_finding(
                "bundle.execute", "atlasquant_aion_command_orchestrator",
                f"Execução do bundle divergiu: {calls}.",
            ))
        if any(approved is not False for _tool, approved in calls):
            findings.append(_finding(
                "bundle.approved", "atlasquant_aion_command_orchestrator",
                "Uma chamada do bundle não usou approved=False.",
            ))
        for row in executed.get("tool_results") or []:
            if local_security_violations(row):
                findings.append(_finding(
                    "bundle.invariants", "atlasquant_aion_command_orchestrator",
                    f"Invariante violada em {row.get('tool_id')}.",
                ))
    finally:
        command.execute_local_tool = original

    stopped = orchestrate_local_command(
        "onde paramos, o que falta e eventos locais",
        execute=True,
        runtime_context={"checkpoint": default_checkpoint()},
        hub=_hub_replacing("aion.tasks.summary", state="DISABLED"),
        access=ADMIN,
        source_kind="ADMIN",
        authenticated_admin=True,
    )
    if stopped.get("state") != "BLOCKED" or not stopped.get("stopped_early") or len(stopped.get("tool_results") or []) != 2:
        findings.append(_finding(
            "bundle.stop_block", "atlasquant_aion_command_orchestrator",
            "O bundle não parou no primeiro BLOCK.",
        ))
    return findings


def _contains_secret(payload: Any) -> bool:
    text = repr(payload)
    return _SENTINEL in text or _TOKEN in text or "segredo-pt" in text


def _audit_sanitization() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    findings = []
    warnings = []
    moment = datetime(2026, 9, 27, tzinfo=timezone.utc)
    payload = {
        "when": moment,
        "flag": False,
        "count": 4,
        "ratio": 1.25,
        "empty": None,
        "note": f"senha={_SENTINEL} token={_TOKEN}",
        "items": [{"label": "visivel", "secret": _SENTINEL}],
        "box": {"level": {"name": "local", "authorization": _TOKEN}},
    }
    for name in SECRET_NAMES:
        payload[name] = _SENTINEL
        if not is_secret_key(name):
            findings.append(_finding(
                "sanitize.key", "atlasquant_aion_observability",
                f"is_secret_key não classifica {name!r}.",
            ))
    if redact_text(f"senha={_SENTINEL}") == f"senha={_SENTINEL}":
        findings.append(_finding(
            "sanitize.text", "atlasquant_aion_observability",
            "redact_text preservou senha=valor.",
        ))
    clean = executor.sanitize_local_arguments(payload)
    if _contains_secret(clean) or any(name in clean for name in SECRET_NAMES):
        findings.append(_finding(
            "sanitize.arguments", "atlasquant_aion_local_executor",
            "sanitize_local_arguments devolveu campo ou valor secreto.",
        ))
    if clean.get("when") != moment or type(clean.get("flag")) is not bool or clean.get("count") != 4 or clean.get("ratio") != 1.25 or clean.get("empty") is not None:
        findings.append(_finding(
            "sanitize.scalars", "atlasquant_aion_local_executor",
            "datetime, bool, int, float ou None não foram preservados.",
        ))
    seen = {}

    def capture(arguments, _runtime):
        seen["arguments"] = arguments
        raise RuntimeError(f"password={_SENTINEL} token={_TOKEN}")

    with _temporary_handler("aion.tasks.summary", capture):
        failed = execute_local_tool(
            "aion.tasks.summary",
            arguments=payload,
            runtime_context={"checkpoint": default_checkpoint(), "password": _SENTINEL},
            access=ADMIN,
            source_kind="ADMIN",
            authenticated_admin=True,
        )
    if _contains_secret(seen.get("arguments")) or _contains_secret(failed) or "Traceback" in repr(failed):
        findings.append(_finding(
            "sanitize.handler_and_error", "atlasquant_aion_local_executor",
            "Segredo chegou ao handler ou escapou na exceção.",
        ))
    if failed.get("state") != "ERROR":
        findings.append(_finding(
            "sanitize.error_state", "atlasquant_aion_local_executor",
            "Exceção do handler não virou ERROR.",
        ))
    return findings, warnings


def _audit_envelope(envelope: Mapping[str, Any]) -> list[dict[str, str]]:
    findings = []
    for field in ENVELOPE_FIELDS:
        if field not in envelope:
            findings.append(_finding(
                "envelope.field", "atlasquant_aion_local_executor",
                f"Campo obrigatório ausente: {field}.",
            ))
    if envelope.get("schema") != RESULT_SCHEMA:
        findings.append(_finding(
            "envelope.schema", "atlasquant_aion_local_executor",
            f"Schema divergente: {envelope.get('schema')}.",
        ))
    fingerprint = str(envelope.get("contract_fingerprint") or "")
    if not re.fullmatch(r"AION-LCL-[0-9A-F]{16}", fingerprint):
        findings.append(_finding(
            "envelope.contract_fingerprint", "atlasquant_aion_local_executor",
            "Envelope sem selo válido do contrato local.",
        ))
    if envelope.get("state") not in RESULT_STATES:
        findings.append(_finding(
            "envelope.state", "atlasquant_aion_local_executor",
            f"Estado fora do contrato: {envelope.get('state')}.",
        ))
    preflight = envelope.get("preflight")
    truth = envelope.get("truth")
    if not isinstance(preflight, Mapping) or "state" not in preflight or "blockers" not in preflight:
        findings.append(_finding(
            "envelope.preflight", "atlasquant_aion_local_executor",
            "preflight não tem state e blockers.",
        ))
    if not isinstance(truth, Mapping) or "status" not in truth or "freshness" not in truth:
        findings.append(_finding(
            "envelope.truth", "atlasquant_aion_local_executor",
            "truth não tem status e freshness.",
        ))
    if not isinstance(envelope.get("truncated"), bool):
        findings.append(_finding(
            "envelope.truncated", "atlasquant_aion_local_executor",
            "truncated não é bool.",
        ))
    findings.extend(
        _finding("envelope.security", "atlasquant_aion_local_executor", f"Invariante {item}.")
        for item in local_security_violations(envelope)
    )
    return findings


def _audit_truth() -> list[dict[str, str]]:
    findings = []
    plain = execute_local_tool(
        "aion.tasks.summary",
        runtime_context={"checkpoint": default_checkpoint()},
        access=ADMIN,
        source_kind="ADMIN",
        authenticated_admin=True,
    )
    if plain.get("state") != "SUCCESS" or plain.get("truth", {}).get("status") != "UNKNOWN" or plain.get("truth", {}).get("freshness") != "UNVERIFIED":
        findings.append(_finding(
            "truth.success_unknown", "atlasquant_aion_local_executor",
            "SUCCESS sem truth explícita não permaneceu UNKNOWN/UNVERIFIED.",
        ))
    if plain.get("tool_output_is_authority") is not False:
        findings.append(_finding(
            "truth.authority", "atlasquant_aion_local_executor",
            "Saída de tool foi promovida a autoridade.",
        ))
    moment = datetime(2026, 9, 27, tzinfo=timezone.utc)
    expired = remember(
        None, layer="working", content="expirado", origin="admin", category="note",
        memory_key="auditor:expired", truth_state="CONFIRMED", valid_until="2020-01-01T00:00:00+00:00",
    )
    shown = execute_local_tool(
        "aion.memory.recall",
        arguments={"memory_layers": expired, "now": moment, "include_expired": True},
        access=ADMIN, source_kind="ADMIN", authenticated_admin=True,
    )
    rows = list((shown.get("result") or {}).get("layered") or [])
    if not rows or rows[0].get("truth_state") == "CONFIRMED" or rows[0].get("status") != "EXPIRED":
        findings.append(_finding(
            "truth.expired", "atlasquant_aion_local_executor",
            "Memória expirada foi promovida ou não foi marcada EXPIRED.",
        ))
    superseded = remember(
        remember(
            None, layer="decision", content="antigo", origin="admin", category="decision",
            memory_key="auditor:decision", truth_state="CONFIRMED",
        ),
        layer="decision", content="vigente", origin="admin", category="decision",
        memory_key="auditor:decision", truth_state="INFERENCE",
    )
    current = execute_local_tool(
        "aion.memory.recall",
        arguments={"memory_layers": superseded, "include_superseded": False},
        access=ADMIN, source_kind="ADMIN", authenticated_admin=True,
    )
    contents = [row.get("content") for row in (current.get("result") or {}).get("layered") or []]
    if contents != ["vigente"] or current.get("truth", {}).get("status") == "CONFIRMED":
        findings.append(_finding(
            "truth.superseded", "atlasquant_aion_local_executor",
            "Memória superseded foi promovida ou substituída em silêncio.",
        ))

    def envelope(status, freshness, **extra):
        result = {"conflicts": extra.get("conflicts") or []}
        return {
            "schema": RESULT_SCHEMA,
            "tool_id": extra.get("tool_id", "aion.status.read"),
            "state": extra.get("state", "SUCCESS"),
            "kind": "READ",
            "result": result,
            "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
            "provenance": {"local_only": True},
            "truth": {"status": status, "freshness": freshness},
            "security": {
                "sanitized": True, "network_called": extra.get("network_called", False),
                "connector_called": False, "external_side_effects": False,
                "permissions_expanded": False, "secrets_included": False,
            },
            "executes_action": False, "external_action_executed": False,
            "real_orders_enabled": False, "tool_output_is_authority": False,
        }

    cases = {
        "fresh": (envelope("CONFIRMED", "FRESH"), "SYNTHESIZED", "CONFIRMED", True),
        "unverified": (envelope("CONFIRMED", "UNVERIFIED"), "SYNTHESIZED", "UNKNOWN", False),
        "unknown": (envelope("UNKNOWN", "UNVERIFIED"), "SYNTHESIZED", "UNKNOWN", False),
        "inference": (envelope("INFERENCE", "UNVERIFIED"), "SYNTHESIZED", "INFERENCE", False),
        "hypothesis": (envelope("HYPOTHESIS", "UNVERIFIED"), "SYNTHESIZED", "HYPOTHESIS", False),
        "conflict": (envelope("CONFIRMED", "FRESH", conflicts=["a contra b"]), "CONFLICT", "UNKNOWN", False),
        "security": (envelope("CONFIRMED", "FRESH", network_called=True), "SECURITY_BLOCK", "UNKNOWN", False),
    }
    for name, (row, state, truth, confirmed) in cases.items():
        syn = synthesize_local_tool_results([row])
        content = bool((syn.get("items") or [{}])[0].get("content_confirmed"))
        if syn.get("state") != state or syn.get("truth", {}).get("status") != truth or content is not confirmed:
            findings.append(_finding(
                "truth.synthesis", "atlasquant_aion_local_synthesis",
                f"Caso {name} produziu {syn.get('state')}/{syn.get('truth', {}).get('status')}/confirmed={content}.",
            ))
        if syn.get("tool_output_is_authority") is not False or syn.get("executes_action") is not False:
            findings.append(_finding(
                "truth.synthesis_authority", "atlasquant_aion_local_synthesis",
                f"Caso {name} ampliou autoridade.",
            ))
    empty = synthesize_local_tool_results([])
    if empty.get("state") != "NO_RESULTS":
        findings.append(_finding(
            "truth.no_results", "atlasquant_aion_local_synthesis",
            "Lista vazia não ficou NO_RESULTS.",
        ))
    return findings


def _audit_traceability() -> list[dict[str, str]]:
    findings = []
    expected_sources = {row[0] for row in LOCAL_CONTRACT}
    if set(SOURCE_CATALOG) != expected_sources:
        findings.append(_finding(
            "trace.catalog", "atlasquant_aion_local_traceability",
            "SOURCE_CATALOG divergiu das 11 ferramentas locais.",
        ))

    def envelope(*, result=None, truth="UNKNOWN", freshness="UNVERIFIED", network_called=False):
        return {
            "schema": RESULT_SCHEMA,
            "request_id": "contract-trace",
            "tool_id": "aion.tasks.summary",
            "workspace_id": "administration",
            "kind": "READ",
            "contract_fingerprint": local_contract_fingerprint(),
            "state": "SUCCESS",
            "result": result or {},
            "truncated": False,
            "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
            "provenance": {
                "source_module": "atlasquant_aion_local_executor",
                "source_function": "_audit_traceability",
                "input_scope": "local",
                "local_only": True,
            },
            "truth": {"status": truth, "freshness": freshness},
            "security": {
                "sanitized": True,
                "network_called": network_called,
                "connector_called": False,
                "external_side_effects": False,
                "permissions_expanded": False,
                "secrets_included": False,
            },
            "executes_action": False,
            "external_action_executed": False,
            "real_orders_enabled": False,
            "tool_output_is_authority": False,
        }

    first = envelope(result={"senha": _SENTINEL})
    second = envelope(result={"senha": "outro-segredo-local"})
    syn = synthesize_local_tool_results([first])
    traced = build_local_traceability([first], synthesis=syn)
    traced_again = build_local_traceability([second], synthesis=synthesize_local_tool_results([second]))

    records = list(traced.get("records") or [])
    if traced.get("schema") != "ATLASQUANT_AION_LOCAL_TRACEABILITY_V1" or len(records) != 1:
        findings.append(_finding(
            "trace.schema", "atlasquant_aion_local_traceability",
            "Rastreabilidade não produziu schema/registro esperado.",
        ))
        return findings

    row = records[0]
    other_rows = list(traced_again.get("records") or [])
    if not re.fullmatch(r"AION-LCL-[0-9A-F]{16}", str(row.get("contract_fingerprint") or "")):
        findings.append(_finding(
            "trace.contract_fingerprint", "atlasquant_aion_local_traceability",
            "Rastreabilidade não preservou o selo do contrato local.",
        ))
    if not str(row.get("trace_id") or "").startswith("LCL-EV-"):
        findings.append(_finding(
            "trace.id", "atlasquant_aion_local_traceability",
            "trace_id não usa o prefixo LCL-EV-.",
        ))
    if not other_rows or row.get("trace_id") != other_rows[0].get("trace_id"):
        findings.append(_finding(
            "trace.payload_independence", "atlasquant_aion_local_traceability",
            "trace_id mudou quando apenas o payload bruto mudou.",
        ))
    if traced.get("raw_result_included") is not False or _contains_secret(traced):
        findings.append(_finding(
            "trace.raw_payload", "atlasquant_aion_local_traceability",
            "Rastreabilidade incluiu payload bruto ou segredo.",
        ))
    if row.get("truth_status") != "UNKNOWN" or row.get("content_confirmed") is not False:
        findings.append(_finding(
            "trace.truth", "atlasquant_aion_local_traceability",
            "Rastreabilidade promoveu conteúdo UNKNOWN.",
        ))
    if row.get("authority") is not False or traced.get("tool_output_is_authority") is not False:
        findings.append(_finding(
            "trace.authority", "atlasquant_aion_local_traceability",
            "Rastreabilidade ampliou autoridade.",
        ))

    unsafe = envelope(network_called=True)
    unsafe_syn = synthesize_local_tool_results([unsafe])
    unsafe_trace = build_local_traceability([unsafe], synthesis=unsafe_syn)
    if unsafe_trace.get("state") != "SECURITY_BLOCK" or unsafe_trace.get("security", {}).get("state") != "BLOCK":
        findings.append(_finding(
            "trace.security", "atlasquant_aion_local_traceability",
            "Rastreabilidade não falhou fechada para network_called=True.",
        ))
    return findings


def _audit_response() -> list[dict[str, str]]:
    findings = []
    unknown = synthesize_local_tool_results([{
        "schema": RESULT_SCHEMA, "tool_id": "aion.tasks.summary", "state": "SUCCESS", "kind": "READ",
        "result": {}, "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
        "provenance": {"local_only": True}, "truth": {"status": "UNKNOWN", "freshness": "UNVERIFIED"},
        "security": {"sanitized": True, "network_called": False, "connector_called": False,
                     "external_side_effects": False, "permissions_expanded": False, "secrets_included": False},
        "executes_action": False, "external_action_executed": False, "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }])
    response = compose_local_executive_response(unknown, summaries=["resumo inseguro que não pode ir para sabemos"])
    text = response.get("plain_text") or ""
    known = " ".join(response.get("sections", {}).get("known") or [])
    if "resumo inseguro" in known or "O que sabemos:" not in text or "O que não sabemos:" not in text:
        findings.append(_finding(
            "response.unknown", "atlasquant_aion_local_response",
            "Conteúdo UNKNOWN entrou em 'O que sabemos'.",
        ))
    conflict = synthesize_local_tool_results([{
        "schema": RESULT_SCHEMA, "tool_id": "aion.checkpoint.inspect", "state": "SUCCESS", "kind": "READ",
        "result": {"conflicts": ["lado A contra lado B"]},
        "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
        "provenance": {"local_only": True}, "truth": {"status": "CONFIRMED", "freshness": "FRESH"},
        "security": {"sanitized": True, "network_called": False, "connector_called": False,
                     "external_side_effects": False, "permissions_expanded": False, "secrets_included": False},
        "executes_action": False, "external_action_executed": False, "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }])
    conflict_response = compose_local_executive_response(conflict, summaries=["fato em conflito"])
    conflict_text = " ".join(conflict_response.get("sections", {}).get("conflicts") or [])
    known_text = " ".join(conflict_response.get("sections", {}).get("known") or [])
    plain = conflict_response.get("plain_text") or ""
    if "EXPLICIT_CONFLICTS" not in conflict_text or "fato em conflito" in known_text or "Conflitos:" not in plain:
        findings.append(_finding(
            "response.conflict", "atlasquant_aion_local_response",
            "Conflito não ficou restrito à seção de conflitos.",
        ))
    blocked = synthesize_local_tool_results([{
        "schema": RESULT_SCHEMA, "tool_id": "aion.status.read", "state": "SUCCESS", "kind": "READ",
        "result": {}, "preflight": {"state": "READY_FOR_EXECUTOR", "blockers": []},
        "provenance": {"local_only": True}, "truth": {"status": "CONFIRMED", "freshness": "FRESH"},
        "security": {"sanitized": True, "network_called": True, "connector_called": False,
                     "external_side_effects": False, "permissions_expanded": False, "secrets_included": False},
        "executes_action": False, "external_action_executed": False, "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }])
    blocked_response = compose_local_executive_response(blocked, summaries=["não exibir"])
    if blocked_response.get("safe_to_display") is not False or blocked_response.get("posture") != "SECURITY_BLOCK":
        findings.append(_finding(
            "response.security_block", "atlasquant_aion_local_response",
            "SECURITY_BLOCK continuou exibível como resposta normal.",
        ))
    if blocked_response.get("executes_action") is not False or blocked_response.get("tool_output_is_authority") is not False:
        findings.append(_finding(
            "response.authority", "atlasquant_aion_local_response",
            "A resposta executiva ampliou autoridade.",
        ))
    return findings


def _audit_admin() -> list[dict[str, str]]:
    findings = []
    path = ROOT / "atlasquant_aion_admin.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    if "Esta seção não executa ferramenta." not in source:
        findings.append(_finding(
            "admin.passive_caption", "atlasquant_aion_admin",
            "A seção Tool Hub local perdeu a declaração de que não executa ferramenta.",
        ))
    marker = source.split("##### Tool Hub local", 1)
    if len(marker) != 2 or "execute_local_tool" in marker[1][:800] or "orchestrate_local_command" in marker[1][:800]:
        findings.append(_finding(
            "admin.section_executes", "atlasquant_aion_admin",
            "A seção Tool Hub local passou a referenciar execução.",
        ))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node) == "execute_local_tool":
            findings.append(_finding(
                "admin.direct_execute", "atlasquant_aion_admin",
                "O admin chama execute_local_tool diretamente.",
            ))
        if _call_name(node) != "orchestrate_local_command":
            continue
        execute_value = None
        for keyword in node.keywords:
            if keyword.arg == "execute":
                if isinstance(keyword.value, ast.Constant):
                    execute_value = keyword.value.value
                else:
                    execute_value = _MISSING
        if execute_value is True and not _inside_button(node, parents):
            findings.append(_finding(
                "admin.render_executes", "atlasquant_aion_admin",
                "orchestrate_local_command(execute=True) roda fora do botão explícito.",
            ))
        if execute_value is _MISSING:
            findings.append(_finding(
                "admin.dynamic_execute", "atlasquant_aion_admin",
                "execute do orquestrador local não é uma constante.",
            ))
    return findings


def _inside_button(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.If) and _is_button(current.test):
            return True
    return False


def _is_button(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and _call_name(node) == "button":
        return True
    if isinstance(node, ast.BoolOp):
        return any(_is_button(value) for value in node.values)
    return False


def _workflow_path_lists(text: str) -> list[tuple[str, list[str] | None]]:
    lines = text.splitlines()
    event = ""
    found = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"  [A-Za-z0-9_]+:", line):
            event = line.strip()[:-1]
        if line.strip() == "paths:" and event:
            items = []
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith("- "):
                items.append(lines[index].split("- ", 1)[1].strip().strip("'\""))
                index += 1
            found.append((event, items))
            continue
        index += 1
    if not any(name == "pull_request" for name, _items in found):
        found.append(("pull_request", None))
    return found


def _covered(paths: Sequence[str] | None, filename: str) -> bool:
    if paths is None:
        return True
    return any(path == filename or fnmatch.fnmatch(filename, path) for path in paths)


def _audit_workflows() -> list[dict[str, str]]:
    findings = []
    specs = {
        "quality-tests.yml": ("pull_request", "push"),
        "atlasquant-ui-smoke.yml": ("pull_request", "push"),
        "mobile-dom-stability.yml": ("pull_request", "push"),
    }
    for filename, events in specs.items():
        text = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
        lists = {name: items for name, items in _workflow_path_lists(text)}
        for event in events:
            paths = lists.get(event)
            if paths is not None:
                duplicates = sorted({item for item in paths if paths.count(item) > 1})
                if duplicates:
                    findings.append(_finding(
                        "workflow.duplicate", filename,
                        f"{event} repete paths: {duplicates}.",
                    ))
            for module in CRITICAL_MODULES:
                if not _covered(paths, module):
                    findings.append(_finding(
                        "workflow.missing_module", filename,
                        f"{event} não dispara {module}.",
                    ))
    quality = (ROOT / ".github" / "workflows" / "quality-tests.yml").read_text(encoding="utf-8")
    listed = set(re.findall(r"(?m)^\s+(test_[A-Za-z0-9_]+\.py)\s*\\?$", quality))
    for test_name in CRITICAL_TESTS:
        if test_name not in listed:
            findings.append(_finding(
                "workflow.missing_test", "quality-tests.yml",
                f"Quality não executa {test_name}.",
            ))
        if not (ROOT / test_name).exists():
            findings.append(_finding(
                "workflow.missing_test_file", "quality-tests.yml",
                f"Teste crítico ausente no repositório: {test_name}.",
            ))
    return findings


def audit_aion_local_contracts() -> dict[str, Any]:
    """Audit the live local AION contracts. Offline and deterministic."""
    groups: list[tuple[str, list[dict[str, str]]]] = []
    warnings: list[dict[str, str]] = []

    def add(check_id: str, findings: Iterable[dict[str, str]]) -> None:
        rows = list(findings)
        groups.append((check_id, [row for row in rows if row.get("severity") != "WARNING"]))
        warnings.extend(row for row in rows if row.get("severity") == "WARNING")

    add("registry", audit_tool_rows(tuple(dict(item) for item in DEFAULT_TOOLS)))
    allow = local_allowlist()
    hub_tools = default_tool_hub()["tools"]
    allow_findings = audit_allowlist_rows(allow, hub_tools)
    if not any("workspace_id" in row for row in allow):
        warnings.append(_finding(
            "allowlist.workspace_source", "atlasquant_aion_local_executor",
            "A allowlist não carrega workspace_id; o workspace é conferido no Tool Hub.",
            severity="WARNING",
        ))
    add("allowlist", allow_findings)
    add("handlers", audit_handler_map(dict(executor._HANDLERS), allow, hub_tools))
    add("rules", audit_command_rules(tuple(command._RULES), hub_tools, allow, executor._HANDLERS))
    static = []
    for name in STATIC_MODULES:
        static.extend(audit_static_source(ROOT / name))
    add("static", static)
    add("preflight", _audit_runtime_gates())
    add("forbidden_kinds", _audit_forbidden_kinds())
    add("phrases", _audit_phrases())
    add("sensitive_intents", _audit_sensitive_intents())
    add("bundles", _audit_bundles())
    sanitize_findings, sanitize_warnings = _audit_sanitization()
    warnings.extend(sanitize_warnings)
    add("sanitization", sanitize_findings)
    envelope = execute_local_tool(
        "aion.tasks.summary",
        runtime_context={"checkpoint": default_checkpoint()},
        access=ADMIN, source_kind="ADMIN", authenticated_admin=True, request_id="contract-audit",
    )
    add("envelope", _audit_envelope(envelope))
    add("truth", _audit_truth())
    add("traceability", _audit_traceability())
    add("response", _audit_response())
    add("admin", _audit_admin())
    add("workflows", _audit_workflows())

    failed_groups = [check_id for check_id, rows in groups if rows]
    findings = [row for _check_id, rows in groups for row in rows]
    passed = len(groups) - len(failed_groups)
    local_ids = [row[0] for row in LOCAL_CONTRACT]
    return {
        "schema": SCHEMA,
        "state": "FAIL" if findings else "PASS",
        "checks_total": len(groups),
        "passed": passed,
        "failed": len(failed_groups),
        "warnings": warnings,
        "findings": findings,
        "invariant_summary": {
            "security": "FAIL" if any(row["invariant_id"].startswith(("gate.", "kinds.", "envelope.security", "bundle.invariants")) for row in findings) else "PASS",
            "truth": "FAIL" if any(row["invariant_id"].startswith("truth.") for row in findings) else "PASS",
            "sanitization": "FAIL" if any(row["invariant_id"].startswith("sanitize.") for row in findings) else "PASS",
            "authority": "FAIL" if any(row["invariant_id"].startswith(("intents.", "kinds.", "allowlist.write", "handlers.write", "rules.write")) for row in findings) else "PASS",
        },
        "registry_summary": {
            "tools": len(DEFAULT_TOOLS),
            "local_tools": len(local_ids),
            "write_tool": WRITE_CONTRACT[0],
            "write_kind": WRITE_CONTRACT[1],
            "local_ids": local_ids,
        },
        "handler_summary": {
            "handlers": len(executor._HANDLERS),
            "static_table": True,
            "write_handler": WRITE_CONTRACT[0] in executor._HANDLERS,
        },
        "orchestration_summary": {
            "max_bundle_tools": MAX_BUNDLE_TOOLS,
            "bundle_kinds": sorted(BUNDLE_SAFE_KINDS),
            "draft_in_bundle": False,
            "approved_default": False,
        },
        "workflow_summary": {
            "quality_tests": "quality-tests.yml",
            "ui_smoke": "atlasquant-ui-smoke.yml",
            "mobile_dom": "mobile-dom-stability.yml",
            "critical_modules": list(CRITICAL_MODULES),
            "critical_tests": list(CRITICAL_TESTS),
        },
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "tool_output_is_authority": False,
    }


def format_audit_report(report: Mapping[str, Any]) -> str:
    lines = [
        "AION Local Contract Audit",
        str(report.get("state") or "FAIL"),
        f"{int(report.get('checks_total') or 0)} checks",
        f"{int(report.get('failed') or 0)} failures",
    ]
    for finding in list(report.get("findings") or []):
        lines.append(
            f"{finding.get('invariant_id')} | {finding.get('module')} | {finding.get('description')}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    report = audit_aion_local_contracts()
    print(format_audit_report(report))
    return 0 if report.get("state") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "SCHEMA",
    "LOCAL_CONTRACT",
    "WRITE_CONTRACT",
    "CRITICAL_MODULES",
    "CRITICAL_TESTS",
    "audit_aion_local_contracts",
    "audit_allowlist_rows",
    "audit_command_rules",
    "audit_handler_map",
    "audit_static_source",
    "audit_tool_rows",
    "format_audit_report",
    "local_security_violations",
    "main",
]
