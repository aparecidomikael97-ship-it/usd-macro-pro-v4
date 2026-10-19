"""AION P0 LAB structural regression sentinel for CURRENT hard-stop locations.

Not a formal proof, source-code authorization, trust root, or runtime control.
This purposely rejects accidental removal/reordering of A118 NO-PRODUCER,
Global Worker NO-WITNESS, generic SQLite RESTORE denial and H0 NO-WITNESS
diagnostic. Real producer/custody/HUMAN_OWNER P0 are UNRESOLVED.

Only Python AST in local read-only files; never executes analyzed modules,
imports hosts, calls GitHub, touches SQLite, signs data or authorizes work.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

WATCHED = (
    "atlasquant_aion_execution_outbox.py",
    "atlasquant_aion_global_worker.py",
    "atlasquant_aion_global_worker_readiness.py",
    "aion_chat/store.py",
    "atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py",
)
BLOCK_PRODUCER = "INDEPENDENT_PRODUCER_NOT_ENROLLED"
BLOCK_SOURCE = "INDEPENDENT_SOURCE_WITNESS_NOT_ENROLLED"
BLOCK_RESTORE = "P0_EXECUTION_RESTORE_REQUIRES_INDEPENDENT_WITNESS"
BLOCK_H0 = "INDEPENDENT_H0_WITNESS_NOT_ENROLLED"
H0_FALSE_FIELDS = (
    "local_rollback_ruled_out", "independent_witness_source_enrolled",
    "independent_witness_authenticated", "external_highwater_compared",
    "monotonic_epoch_verified", "producer_receipt_authenticated",
    "first_attempt_cleared", "unknown_outcome_cleared",
    "automatic_retry_allowed", "claim_release_authorized",
    "worker_arming_allowed", "external_action_executed",
    "database_written_by_this_check",
)


def _function(tree: ast.AST, name: str, cls: str | None = None) -> ast.FunctionDef | None:
    nodes = tree.body if isinstance(tree, ast.Module) else []
    if cls is not None:
        nodes = next((n.body for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls), [])
    return next((n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _dict_literal(node: ast.AST | None) -> dict[str, ast.AST]:
    if not isinstance(node, ast.Dict):
        return {}
    return {k.value: v for k, v in zip(node.keys, node.values)
            if isinstance(k, ast.Constant) and type(k.value) is str}


def _constant(node: ast.AST | None, value: object) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is type(value) and node.value == value


def _direct_return_reason(fn: ast.FunctionDef | None, reason: str) -> list[ast.Return]:
    if fn is None:
        return []
    return [
        n for n in fn.body
        if isinstance(n, ast.Return)
        and _constant(_dict_literal(n.value).get("reason"), reason)
    ]


def _calls(fn: ast.AST, name: str) -> list[ast.Call]:
    return [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and (
            isinstance(n.func, ast.Name) and n.func.id == name
            or isinstance(n.func, ast.Attribute) and n.func.attr == name
        )
    ]


def _direct_raise(fn: ast.FunctionDef | None, reason: str) -> list[ast.Raise]:
    if fn is None:
        return []
    return [
        n for n in fn.body if isinstance(n, ast.Raise)
        and isinstance(n.exc, ast.Call)
        and isinstance(n.exc.func, ast.Name)
        and n.exc.func.id == "PermissionError"
        and len(n.exc.args) == 1 and _constant(n.exc.args[0], reason)
    ]


def _check_worker(tree: ast.Module, errors: list[str]) -> None:
    writer = _function(tree, "_persist_runtime_checkpoint_cas")
    blocks = _direct_return_reason(writer, BLOCK_SOURCE)
    if writer is None or not writer.body or writer.body[0] not in blocks:
        errors.append("WORKER_WRITER_NOT_UNCONDITIONALLY_BLOCKED")
    worker = _function(tree, "run_global_worker_once")
    if worker is None:
        errors.append("WORKER_ENTRYPOINT_MISSING")
        return
    source_stops = _direct_return_reason(worker, BLOCK_SOURCE)
    # Exact direct-body return must be BEFORE the first lease writer/executor
    # call; a string in an unreachable function or comment is NOT enough.
    effects = _calls(worker, "_persist_runtime_checkpoint_cas") + _calls(worker, "_execute_due_local_work_authorized")
    if not source_stops or not effects or min(n.lineno for n in source_stops) >= min(n.lineno for n in effects):
        errors.append("WORKER_NO_WITNESS_GATE_MISSING_OR_AFTER_EFFECT_BOUNDARY")


def _check_outbox(tree: ast.Module, errors: list[str]) -> None:
    dispatch = _function(tree, "dispatch_claimed", "ExecutionOutbox")
    reconcile = _function(tree, "reconcile", "ExecutionOutbox")
    if not _direct_raise(dispatch, BLOCK_PRODUCER):
        errors.append("OUTBOX_DISPATCH_NO_PRODUCER_HARDSTOP_MISSING")
    if not _direct_raise(reconcile, BLOCK_PRODUCER):
        errors.append("OUTBOX_RECONCILE_NO_PRODUCER_HARDSTOP_MISSING")


def _check_restore(tree: ast.Module, errors: list[str]) -> None:
    restore = _function(tree, "restore_from_backup", "SQLiteChatStore")
    if restore is None:
        errors.append("SQLITE_OFFICIAL_RESTORE_MISSING")
        return
    source_guards = _calls(restore, "_require_chat_only_restore_file")
    target_guards = _calls(restore, "_require_restore_target_safe")
    file_replacements = _calls(restore, "replace")
    if (len(source_guards) < 2 or len(target_guards) < 2 or not file_replacements
            or max(n.lineno for n in source_guards) >= max(n.lineno for n in file_replacements)
            or max(n.lineno for n in target_guards) >= max(n.lineno for n in file_replacements)):
        errors.append("SQLITE_RESTORE_MISSING_SOURCE_TARGET_RECHECK_BEFORE_REPLACE")
    helper = _function(tree, "_require_chat_only_restore_file")
    if helper is None or not any(
        _constant(n, BLOCK_RESTORE) for n in ast.walk(helper)
    ):
        errors.append("SQLITE_RESTORE_EXECUTION_LEDGER_REFUSAL_MISSING")


def _check_readiness(tree: ast.Module, errors: list[str]) -> None:
    fn = _function(tree, "activation_readiness_snapshot")
    if fn is None:
        errors.append("READINESS_ENTRYPOINT_MISSING")
        return
    checks = [
        n for n in fn.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        and n.target.id == "blockers" and isinstance(n.value, ast.List)
        and any(_constant(v, BLOCK_SOURCE) for v in n.value.elts)
    ]
    if not checks:
        errors.append("READINESS_INDEPENDENT_SOURCE_BLOCKER_MISSING")


def _check_h0(tree: ast.Module, errors: list[str]) -> None:
    observe = _function(tree, "observe_h0_sqlite_first_effect_lab")
    if observe is None:
        errors.append("H0_READONLY_OBSERVER_MISSING")
        return
    reports = [
        _dict_literal(n.value)
        for n in observe.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        and n.target.id == "report"
    ]
    report = reports[0] if reports else {}
    if not _constant(report.get("state"), "BLOCKED") or not _constant(report.get("blocker"), BLOCK_H0):
        errors.append("H0_OBSERVER_NOT_BLOCKED_BY_DEFAULT")
    for field in H0_FALSE_FIELDS:
        if not _constant(report.get(field), False):
            errors.append("H0_FALSE_AUTHORITY_CONTRACT_CHANGED:" + field)
    main = _function(tree, "main")
    if main is None or not any(isinstance(n, ast.Return) and _constant(n.value, 2) for n in main.body):
        errors.append("H0_CLI_NO_GO_EXIT_CODE_MISSING")


def verify_p0_staging_boundaries(files: Mapping[str, str]) -> tuple[str, ...]:
    """Diagnostic only; a PASS never authorizes first effect or Worker."""
    errors: list[str] = []
    parsers = {
        "atlasquant_aion_global_worker.py": _check_worker,
        "atlasquant_aion_execution_outbox.py": _check_outbox,
        "aion_chat/store.py": _check_restore,
        "atlasquant_aion_global_worker_readiness.py": _check_readiness,
        "atlasquant_aion_p0_h0_sqlite_startup_observer_lab.py": _check_h0,
    }
    for filename in WATCHED:
        source = files.get(filename)
        if type(source) is not str:
            errors.append("SOURCE_MISSING:" + filename)
            continue
        try:
            tree = ast.parse(source, filename=filename)
        except (SyntaxError, ValueError, TypeError):
            errors.append("SOURCE_NOT_PARSEABLE:" + filename)
            continue
        parsers[filename](tree, errors)
    return tuple(errors)


def verify_checkout(root: str | Path = ".") -> tuple[str, ...]:
    base = Path(root)
    sources = {}
    for name in WATCHED:
        try:
            sources[name] = (base / name).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            pass
    return verify_p0_staging_boundaries(sources)


if __name__ == "__main__":
    import json
    result = verify_checkout()
    print(json.dumps({
        "status": "SOURCE_INVARIANTS_OBSERVED_NOT_AUTHORITY" if not result else "BLOCKED_SOURCE_REGRESSION",
        "violations": list(result),
        "external_witness_enrolled": False,
        "highwater_authenticated": False,
        "first_effect_authorized": False,
        "worker_armed": False,
    }, sort_keys=True))
    raise SystemExit(0 if not result else 2)
