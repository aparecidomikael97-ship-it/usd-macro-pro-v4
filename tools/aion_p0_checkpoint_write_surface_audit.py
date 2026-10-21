"""Read-only, stdlib-only AION Checkpoint Mestre Python write-surface inventory.

This script never imports scanned files or executes product code; it parses AST.
The evidence is a bounded inventory, NOT proof that dynamic write paths cannot
exist. In particular, aliases, reflection, generated code, non-Python tools
and API-side permissions require an additional runtime/credential audit.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

SKIP_DIRS = frozenset(
    {".git", ".venv", "venv", ".tox", "__pycache__", "node_modules", "tests"}
)
TARGET = "atlasquant_aion_memory.py"
CHECKPOINT_LITERAL = "checkpoint_master.json"
WRITE_NAMES = frozenset({
    "requests.put", "requests.patch",
    "httpx.put", "httpx.patch",
    "urllib3.request", "requests.request",
    "github.update_file", "github.create_file",
})


def dotted(expr: ast.AST) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        prev = dotted(expr.value)
        return prev + "." + expr.attr if prev else expr.attr
    return ""


def write_kind(call: ast.Call) -> str:
    name = dotted(call.func)
    if name in WRITE_NAMES:
        if name in {"requests.request", "urllib3.request"}:
            method = (
                call.args[0].value
                if call.args and isinstance(call.args[0], ast.Constant)
                else None
            )
            method = method if method is not None else next(
                (kw.value.value for kw in call.keywords
                 if kw.arg == "method" and isinstance(kw.value, ast.Constant)),
                None,
            )
            return name if method in {"PUT", "PATCH", "POST", "DELETE"} else ""
        return name
    if name.endswith(".update_file") or name.endswith(".create_file"):
        return name
    # Other arbitrary client.put methods are only heuristic candidates when
    # checkpoint literals/references occur in the same module.
    if name.endswith(".put") or name.endswith(".patch"):
        return name
    return ""


def inspect_source(content: str, relative_path: str) -> dict:
    tree = ast.parse(content, filename=relative_path)
    references = []
    writes = []
    calls = []
    definitions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if CHECKPOINT_LITERAL in node.value:
                references.append(node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "save_runtime_checkpoint":
                definitions.append(node.lineno)
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if name.endswith("save_runtime_checkpoint"):
                calls.append({"line": node.lineno, "callee": name})
            kind = write_kind(node)
            if kind:
                writes.append({"line": node.lineno, "kind": kind})
    # String detection is narrow and intentionally does not resolve imports.
    contextual = bool(
        references
        or "save_runtime_checkpoint" in content
        or "_contents_url(" in content
        or "RUNTIME_PATH" in content
        or "runtime_checkpoint" in content
        or "checkpoint_master" in content
    )
    return {
        "path": relative_path,
        "checkpoint_literal_lines": sorted(set(references)),
        "runtime_save_calls": sorted(calls, key=lambda x: x["line"]),
        "runtime_save_definitions": sorted(definitions),
        "network_or_mutator_candidates": sorted(writes, key=lambda x: x["line"]),
        "contextual": contextual,
    }


def _production_python_files(root: Path):
    for file in sorted(root.rglob("*.py")):
        parts = file.relative_to(root).parts
        if any(p in SKIP_DIRS for p in parts[:-1]):
            continue
        if file.name.startswith("test_") or file.name.endswith("_test.py"):
            continue
        yield file


def reviewed_alternate_transport(root: Path, path: str) -> str:
    """Conservative review for three existing non-checkpoint candidates.

    Explicit safe purpose is required. In particular, the old Global Worker
    checkpoint writer has an unconditional deny-only return before PUT. If that
    return is ever deleted, fail CI rather than silently approving the writer.
    """
    text = (root / path).read_text(encoding="utf-8")
    tree = ast.parse(text, filename=path)
    if path == "atlasquant_aion_global_worker.py":
        fn = [
            n for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name == "_persist_runtime_checkpoint_cas"
        ]
        if len(fn) != 1:
            return ""
        body = fn[0].body
        if body and isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ) and isinstance(body[0].value.value, str):
            body = body[1:]
        if (
            body and isinstance(body[0], ast.Return)
            and "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED" in text
        ):
            return "DORMANT_GLOBAL_WORKER_WRITER_UNCONDITIONAL_EARLY_RETURN"
        return ""
    if path == "autopilot_v107.py":
        # This is still a same-GitHub runtime-data transport; its narrow
        # path fence was added by A136b. It is NOT independently authenticated.
        if (
            "def gh_put_bytes(" in text
            and 'path == "dados/aion/checkpoint_master.json"' in text
            and 'any(segment in ("", ".", "..") for segment in path.split("/"))' in text
            and "requests.put(" in text
        ):
            return "AUTOPILOT_DADOS_PATH_RESTRICTED_NO_CHECKPOINT_WITNESS"
        return ""
    if path == "atlasquant_flight_recorder_store.py":
        if (
            'FLIGHT_RECORDER_PATH="dados/atlasquant_flight_recorder.jsonl"' in text
            and "/contents/{FLIGHT_RECORDER_PATH}" in text
            and "def persist_records(" in text
            and "checkpoint_master.json" not in text
        ):
            return "SEPARATE_FLIGHT_RECORDER_JSONL_PATH_STATIC_ONLY"
        return ""
    if path == "atlasquant_aion_global_worker_activation.py":
        if (
            "def force_disable_repository_feature_flag(" in text
            and "/actions/variables" in text
            and '"value": DISABLED_VALUE' in text
            and "def write_repository_feature_flag_enabled(" in text
            and "return _independent_activation_authority_denial()" in text
        ):
            return "SAFETY_DISABLE_REPOSITORY_VARIABLE_NOT_CHECKPOINT"
        return ""
    return ""


def audit_tree(root: Path) -> dict:
    files = []
    parse_errors = []
    for path in _production_python_files(root):
        name = str(path.relative_to(root)).replace("\\", "/")
        try:
            content = path.read_text(encoding="utf-8")
            entry = inspect_source(content, name)
        except (OSError, UnicodeError, SyntaxError) as exc:
            parse_errors.append({"path": name, "error": type(exc).__name__})
            continue
        if (
            entry["checkpoint_literal_lines"]
            or entry["runtime_save_calls"]
            or entry["runtime_save_definitions"]
            or entry["network_or_mutator_candidates"]
        ):
            files.append(entry)
    reviewed = []
    suspicious = []
    for entry in files:
        if entry["path"] == TARGET or not entry["network_or_mutator_candidates"]:
            continue
        if entry["contextual"]:
            review = reviewed_alternate_transport(root, entry["path"])
            item = {
                "path": entry["path"],
                "writes": entry["network_or_mutator_candidates"],
            }
            if review:
                reviewed.append({**item, "limited_review": review})
            else:
                suspicious.append(item)
    # Inventory ALL other Python mutators too. Some may use dynamic paths
    # without mentioning "checkpoint"; this list remains manual review, not
    # evidence of a clean call graph or absence of other transports.
    other_mutators = [
        {"path": f["path"], "writes": f["network_or_mutator_candidates"]}
        for f in files
        if f["path"] != TARGET
        and not f["contextual"]
        and f["network_or_mutator_candidates"]
    ]
    runtime_writes = [
        {"path": f["path"], "writes": f["network_or_mutator_candidates"]}
        for f in files
        if f["path"] == TARGET
    ]
    return {
        "schema": "AION_P0_CHECKPOINT_WRITE_SURFACE_AST_V1",
        "status": "STATIC_SOURCE_INVENTORY_ONLY_NO_GO",
        "root": ".",
        "scanned_python_files": sum(1 for _ in _production_python_files(root)),
        "entries": files,
        "contextual_mutator_candidates_outside_primary_writer": suspicious,
        "reviewed_alternate_transport_candidates": reviewed,
        "other_mutators_pending_manual_code_review": other_mutators,
        "primary_writer_mutators": runtime_writes,
        "parse_errors": parse_errors,
        "external_witness_enrolled": False,
        "runtime_write_authorized": False,
    }


def guard_shape(root: Path) -> dict:
    """Verify syntactic presence/order of the A135 call before requests.put.

    This is deliberately NOT a complete control-flow/taint analysis. A review
    is still needed to exclude other direct write paths.
    """
    text = (root / TARGET).read_text(encoding="utf-8")
    tree = ast.parse(text, filename=TARGET)
    funcs = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "save_runtime_checkpoint"
    ]
    if len(funcs) != 1:
        return {"ok": False, "reason": "save_runtime_checkpoint is not unique"}
    func = funcs[0]
    calls = [
        n for n in ast.walk(func)
        if isinstance(n, ast.Call)
    ]
    guards = [
        n.lineno for n in calls
        if dotted(n.func) == "_require_independent_runtime_write_witness"
    ]
    puts = [
        n.lineno for n in calls
        if dotted(n.func) == "requests.put"
    ]
    branch_guards = [
        n.lineno for n in ast.walk(func)
        if isinstance(n, ast.If)
        and any(
            isinstance(x, ast.Constant) and x.value is True
            for x in ast.walk(n.test)
        )
        and any(
            isinstance(x, ast.Name) and x.id == "admission"
            for x in ast.walk(n.test)
        )
    ]
    good = (
        len(guards) == 1 and len(puts) == 1
        and len(branch_guards) >= 1
        and guards[0] < min(branch_guards) < puts[0]
    )
    return {
        "ok": good,
        "guard_calls": guards,
        "deny_branches": branch_guards,
        "github_put_calls": puts,
        "reason": "AST call order only; no proof of effective independent trust",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = audit_tree(root)
    report["writer_guard_shape"] = guard_shape(root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if args.enforce and (
        report["parse_errors"]
        or report["contextual_mutator_candidates_outside_primary_writer"]
        or not report["writer_guard_shape"]["ok"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
