"""Read-only failure diagnostics for AION Developer.

Consumes supplied test/log evidence and returns a bounded, sanitized structural
analysis. It never executes tests, edits files, applies patches, invokes a
process, calls the network, persists checkpoints, commits, merges or deploys.
Confirmed log facts remain separate from causal hypotheses.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_developer_engine import record_test_attempt
from atlasquant_aion_developer_intelligence import (
    SCHEMA as INTELLIGENCE_SCHEMA,
    build_test_coverage_map,
)
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_DIAGNOSTIC_V1"
MAX_LOG_CHARS = 120_000
MAX_FACTS = 30
MAX_RECOMMENDED_TESTS = 50

_TRACE_RE = re.compile(r"""File\s+["']([^"']+)["'],\s+line\s+(\d+)""")
_FAILED_RE = re.compile(r"""(?m)^\s*(?:FAILED|ERROR)\s+([^\s]+)""")
_EXCEPTION_RE = re.compile(
    r"""(?m)^\s*([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception))(?::\s*(.*))?$"""
)

_HYPOTHESIS_RULES = (
    (("SyntaxError", "IndentationError", "TabError"), "SYNTAX_OR_PARSE_FAILURE",
     "A sintaxe ou estrutura do arquivo citado pode estar inválida."),
    (("ModuleNotFoundError", "ImportError"), "IMPORT_OR_DEPENDENCY_MISMATCH",
     "Import, caminho de módulo ou dependência pode divergir do ambiente esperado."),
    (("AssertionError",), "BEHAVIOR_OR_EXPECTATION_MISMATCH",
     "Comportamento observado e expectativa do teste podem ter divergido."),
    (("TypeError", "AttributeError"), "INTERFACE_OR_TYPE_MISMATCH",
     "Assinatura, tipo ou atributo consumido pode ter mudado."),
    (("KeyError", "IndexError"), "DATA_SHAPE_OR_BOUNDARY_MISMATCH",
     "Formato de dados, chave ou limite pode não corresponder ao esperado."),
    (("TimeoutError", "ConnectionError"), "IO_OR_TIMING_CONDITION",
     "Tempo, disponibilidade ou fronteira de I/O pode ter afetado a execução."),
)


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _known_paths(snapshot: Mapping[str, Any]) -> list[str]:
    return sorted({
        str(row.get("path") or "").replace("\\", "/")
        for row in list(snapshot.get("files") or [])
        if isinstance(row, Mapping) and str(row.get("path") or "")
    }, key=len, reverse=True)


def _match_repo_path(raw: Any, known: list[str]) -> str:
    value = str(raw or "").replace("\\", "/")
    for relative in known:
        if value == relative or value.endswith("/" + relative):
            return relative
    return ""


def _hypotheses(exception_type: str) -> list[dict[str, str]]:
    for types, label, rationale in _HYPOTHESIS_RULES:
        if exception_type in types:
            return [{
                "label": label,
                "truth_status": "UNKNOWN",
                "rationale": rationale,
            }]
    return [{
        "label": "CAUSE_NOT_YET_CONFIRMED",
        "truth_status": "UNKNOWN",
        "rationale": "O log identifica falha, mas não confirma sozinho a causa raiz.",
    }]


def diagnose_failure(
    snapshot: Mapping[str, Any],
    log_text: Any,
) -> dict[str, Any]:
    """Extract sanitized facts from failure evidence without executing anything."""
    if snapshot.get("schema") != INTELLIGENCE_SCHEMA:
        raise ValueError("valid Developer Intelligence snapshot required")
    unsafe_snapshot = (
        bool(snapshot.get("content_included"))
        or bool(snapshot.get("executes_repository_code"))
        or bool(snapshot.get("writes_files"))
        or bool(snapshot.get("network_called"))
        or bool(snapshot.get("subprocess_called"))
    )
    if unsafe_snapshot:
        raise ValueError("unsafe repository snapshot")

    raw = str(log_text or "")[:MAX_LOG_CHARS]
    sanitized = redact_text(raw)
    known = _known_paths(snapshot)

    exception_type = ""
    exception_hint = ""
    exception_matches = list(_EXCEPTION_RE.finditer(sanitized))
    if exception_matches:
        match = exception_matches[-1]
        exception_type = _clean(match.group(1), 120)
        exception_hint = _clean(match.group(2), 240)

    file_refs = []
    for match in _TRACE_RE.finditer(sanitized):
        relative = _match_repo_path(match.group(1), known)
        if not relative:
            continue
        row = {
            "path": relative,
            "line": int(match.group(2)),
            "truth_status": "CONFIRMED_BY_LOG",
        }
        if row not in file_refs:
            file_refs.append(row)
        if len(file_refs) >= MAX_FACTS:
            break

    explicit_tests = []
    for match in _FAILED_RE.finditer(sanitized):
        node = str(match.group(1) or "")
        raw_path = node.split("::", 1)[0]
        relative = _match_repo_path(raw_path, known)
        if not relative:
            continue
        suffix = node[len(raw_path):] if node.startswith(raw_path) else ""
        safe_node = relative + _clean(suffix, 300)
        if safe_node not in explicit_tests:
            explicit_tests.append(safe_node)
        if len(explicit_tests) >= MAX_FACTS:
            break

    affected = sorted({
        row["path"] for row in file_refs
    } | {
        node.split("::", 1)[0] for node in explicit_tests
    })
    source_paths = [
        path for path in affected
        if not path.rsplit("/", 1)[-1].startswith("test_")
    ]
    coverage = build_test_coverage_map(snapshot, source_paths)
    recommended = sorted(set(
        explicit_tests + list(coverage.get("recommended_tests") or [])
    ))[:MAX_RECOMMENDED_TESTS]

    facts = []
    if exception_type:
        facts.append({
            "kind": "EXCEPTION_TYPE",
            "value": exception_type,
            "truth_status": "CONFIRMED_BY_LOG",
        })
    if exception_hint:
        facts.append({
            "kind": "EXCEPTION_HINT",
            "value": exception_hint,
            "truth_status": "CONFIRMED_BY_LOG",
        })
    for row in file_refs:
        facts.append({
            "kind": "TRACE_FILE",
            "value": f"{row['path']}:{row['line']}",
            "truth_status": "CONFIRMED_BY_LOG",
        })
    for node in explicit_tests:
        facts.append({
            "kind": "TEST_NODE",
            "value": node,
            "truth_status": "CONFIRMED_BY_LOG",
        })
    facts = facts[:MAX_FACTS]

    state = "FAILURE_EVIDENCE" if facts else "INSUFFICIENT_EVIDENCE"
    hypotheses = _hypotheses(exception_type) if state == "FAILURE_EVIDENCE" else []
    evidence_seed = {
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "exception_type": exception_type,
        "affected": affected,
        "tests": explicit_tests,
        "log_digest": _digest(sanitized, 24),
    }
    return {
        "schema": SCHEMA,
        "diagnostic_id": "DEVFAIL-" + _digest(evidence_seed),
        "state": state,
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "log_digest": "LOG-" + _digest(sanitized, 24),
        "exception_type": exception_type or "UNKNOWN_FAILURE",
        "confirmed_facts": facts,
        "affected_files": affected,
        "explicit_tests": explicit_tests,
        "recommended_tests": recommended,
        "unmatched_code": list(coverage.get("unmatched_code") or []),
        "hypotheses": hypotheses,
        "cause_confirmed": False,
        "cause_truth_status": "UNKNOWN",
        "next_steps": [
            "Revisar somente os arquivos confirmados ou diretamente relacionados.",
            "Executar os testes candidatos em ambiente de teste antes de concluir a causa.",
            "Confirmar a causa com reprodução/evidência antes de registrar causa raiz.",
        ] if state == "FAILURE_EVIDENCE" else [
            "Fornecer um trecho de falha com exceção, traceback ou nó de teste identificável.",
        ],
        "raw_log_included": False,
        "analysis_only": True,
        "executes_repository_code": False,
        "runs_tests": False,
        "writes_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_fix": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


def record_failure_attempt(
    workflow: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    *,
    command_label: Any = "reported test failure",
) -> dict[str, Any]:
    """Record a failed attempt in-memory; never apply a correction."""
    if diagnostic.get("schema") != SCHEMA:
        raise ValueError("valid developer diagnostic required")
    if diagnostic.get("state") != "FAILURE_EVIDENCE":
        raise ValueError("diagnostic has insufficient failure evidence")
    hypotheses = [
        str(item.get("label") or "")
        for item in list(diagnostic.get("hypotheses") or [])
        if isinstance(item, Mapping) and str(item.get("label") or "")
    ]
    refs = [str(diagnostic.get("diagnostic_id") or "")]
    refs.extend(str(x) for x in list(diagnostic.get("recommended_tests") or [])[:10])
    return record_test_attempt(
        workflow,
        command_label=_clean(command_label, 240),
        state="FAIL",
        error_type=_clean(diagnostic.get("exception_type"), 120) or "UNKNOWN_FAILURE",
        hypothesis=" | ".join(hypotheses) or "CAUSE_NOT_YET_CONFIRMED",
        cause="",
        evidence_refs=[x for x in refs if x],
    )


__all__ = [
    "SCHEMA",
    "MAX_LOG_CHARS",
    "diagnose_failure",
    "record_failure_attempt",
]
