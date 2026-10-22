"""A156 offline AST contract for the REAL historical Checkpoint Mestre restore.

This is narrow defense-in-depth for atlasquant_aion_recovery.py. It does
NOT authorize RESTORE and cannot prove trusted independent witness custody,
real owner approval, absence of dynamic aliases or any real provider effect.
Scanned code is NEVER executed, imported or connected to GitHub.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "atlasquant_aion_recovery.py"
HELPER = "_require_independent_recovery_head_witness"
RESTORE = "restore_checkpoint_revision"
SCHEMA = "AION_P0_A156_REAL_RESTORE_DENY_AST_LAB_V1"
HELPER_DENIES = {
    "allowed": False,
    "status": "BLOCKED",
    "independent_witness_enrolled": False,
    "monotonic_head_proven": False,
    "human_owner_verified": False,
    "restoration_authorized": False,
    "executes_action": False,
}
RESTORE_DENIES = {
    "status": "BLOCKED", "saved": False, "verified": False,
    "restored_revision": "", "restore_confirmed": False,
    "reconciliation_required": False, "automatic_retry_allowed": False,
    "automatic_restore": False, "independent_witness_enrolled": False,
    "monotonic_head_proven": False, "human_owner_verified": False,
}


def _callee(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        s = _callee(node.value)
        return s + "." + node.attr if s else node.attr
    return ""


def _const(node: ast.AST | None, value: Any) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is type(value) and node.value == value


def _literal_dict(node: ast.AST | None) -> dict[str, ast.AST] | None:
    if not isinstance(node, ast.Dict):
        return None
    found: dict[str, ast.AST] = {}
    for k, v in zip(node.keys, node.values):
        if not isinstance(k, ast.Constant) or type(k.value) is not str or k.value in found:
            return None
        found[k.value] = v
    return found


def _denies(node: ast.AST | None, expected: dict[str, Any]) -> bool:
    obj = _literal_dict(node)
    return obj is not None and all(k in obj and _const(obj[k], value) for k, value in expected.items())


def _body(fn: ast.FunctionDef) -> list[ast.stmt]:
    statements = fn.body
    if (statements and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and type(statements[0].value.value) is str):
        return statements[1:]
    return statements


def _is_identity_not_true(expr: ast.AST, *, variable: str | None = None, field: str | None = None) -> bool:
    if (not isinstance(expr, ast.Compare) or len(expr.ops) != 1
            or not isinstance(expr.ops[0], ast.IsNot)
            or len(expr.comparators) != 1 or not _const(expr.comparators[0], True)):
        return False
    lhs = expr.left
    if field is None:
        return isinstance(lhs, ast.Name) and lhs.id == variable
    if (not isinstance(lhs, ast.Call) or len(lhs.args) != 1 or lhs.keywords
            or not _const(lhs.args[0], field)
            or not isinstance(lhs.func, ast.Attribute) or lhs.func.attr != "get"):
        return False
    return isinstance(lhs.func.value, ast.Name) and lhs.func.value.id == variable


def _witness_assignment(node: ast.stmt) -> bool:
    if (not isinstance(node, ast.Assign) or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
            or node.targets[0].id != "witness_admission"):
        return False
    call = node.value
    if (not isinstance(call, ast.Call) or _callee(call.func) != HELPER
            or len(call.args) != 1 or not isinstance(call.args[0], ast.Name)
            or call.args[0].id != "config"):
        return False
    kw = {item.arg: item.value for item in call.keywords if item.arg is not None}
    if len(kw) != len(call.keywords) or set(kw) != {
        "ancestry", "current_blob_sha", "candidate_revision"
    }:
        return False
    return (isinstance(kw["ancestry"], ast.Name)
            and kw["ancestry"].id == "ancestry"
            and isinstance(kw["candidate_revision"], ast.Name)
            and kw["candidate_revision"].id == "revision"
            and isinstance(kw["current_blob_sha"], ast.Call)
            and isinstance(kw["current_blob_sha"].func, ast.Attribute)
            and kw["current_blob_sha"].func.attr == "get"
            and isinstance(kw["current_blob_sha"].func.value, ast.Name)
            and kw["current_blob_sha"].func.value.id == "preflight"
            and len(kw["current_blob_sha"].args) == 1
            and _const(kw["current_blob_sha"].args[0], "expected_sha"))


def _approved_guard(node: ast.stmt) -> bool:
    if (not isinstance(node, ast.If) or node.orelse
            or not _is_identity_not_true(node.test, variable="approved")
            or len(node.body) != 1 or not isinstance(node.body[0], ast.Return)):
        return False
    return _denies(node.body[0].value, {
        "status": "BLOCKED", "saved": False, "verified": False,
    })


def _save_assignment(node: ast.stmt) -> bool:
    if (not isinstance(node, ast.Assign) or len(node.targets) != 1
            or not isinstance(node.targets[0], ast.Name)
            or node.targets[0].id != "result"):
        return False
    call = node.value
    if not isinstance(call, ast.Call) or _callee(call.func) != "save_runtime_checkpoint":
        return False
    if len(call.args) != 2 or [_callee(x) for x in call.args] != ["checkpoint", "config"]:
        return False
    kw = {item.arg: item.value for item in call.keywords if item.arg is not None}
    if len(kw) != len(call.keywords) or set(kw) != {"approved", "expected_sha", "timeout"}:
        return False
    return (_const(kw["approved"], True)
            and isinstance(kw["timeout"], ast.Name) and kw["timeout"].id == "timeout"
            and isinstance(kw["expected_sha"], ast.Call)
            and _callee(kw["expected_sha"].func) == "str")


def inspect_recovery_source(source: str) -> dict[str, Any]:
    issues: list[str] = []
    if type(source) is not str or len(source.encode("utf-8")) > 2_000_000:
        issues.append("SOURCE_UNSUPPORTED")
        source = ""
    try:
        tree = ast.parse(source, filename="atlasquant_aion_recovery.py")
    except (SyntaxError, TypeError, UnicodeError, ValueError, RecursionError):
        issues.append("RECOVERY_SOURCE_UNPARSEABLE")
        tree = ast.Module(body=[], type_ignores=[])

    def unique_fn(name: str) -> ast.FunctionDef | None:
        matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name == name]
        if len(matches) != 1 or not isinstance(matches[0], ast.FunctionDef):
            issues.append("FUNCTION_MISSING_DUPLICATED_OR_ASYNC:" + name)
            return None
        if matches[0].decorator_list:
            issues.append("UNREVIEWED_FUNCTION_DECORATOR:" + name)
        return matches[0]

    witness = unique_fn(HELPER)
    restore = unique_fn(RESTORE)
    if witness is not None:
        body = _body(witness)
        if (len(body) != 1 or not isinstance(body[0], ast.Return)
                or not _denies(body[0].value, HELPER_DENIES)):
            issues.append("INDEPENDENT_RECOVERY_WITNESS_NOT_UNCONDITIONALLY_DENY_ONLY")
        for node in tree.body:
            if node is witness:
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                if any(isinstance(x, ast.Name) and x.id == HELPER and isinstance(x.ctx, ast.Store)
                       for x in ast.walk(node)):
                    issues.append("RECOVERY_WITNESS_REBOUND_AT_MODULE_SCOPE")
                    break

    if restore is not None:
        body = _body(restore)
        if not body or not _approved_guard(body[0]):
            issues.append("EXPLICIT_APPROVAL_MUST_DENY_BEFORE_NETWORK")
        calls = [n for n in ast.walk(restore) if isinstance(n, ast.Call)]
        witness_calls = [n for n in calls if _callee(n.func) == HELPER]
        writes = [n for n in calls if _callee(n.func) == "save_runtime_checkpoint"]
        if len(witness_calls) != 1:
            issues.append("INDEPENDENT_WITNESS_CALL_NOT_UNIQUE")
        if len(writes) != 1:
            issues.append("SHARED_CHECKPOINT_SAVE_CALL_NOT_UNIQUE")
        admission_indices = [i for i, st in enumerate(body) if _witness_assignment(st)]
        if len(admission_indices) != 1:
            issues.append("RECOVERY_WITNESS_ASSIGNMENT_NOT_TOP_LEVEL_OR_BINDING_DRIFT")
        else:
            index = admission_indices[0]
            guard_stmt = body[index]
            if index + 1 >= len(body):
                issues.append("RECOVERY_NEGATIVE_ADMISSION_BRANCH_MISSING")
            else:
                denial = body[index + 1]
                if (not isinstance(denial, ast.If)
                        or not _is_identity_not_true(
                            denial.test, variable="witness_admission", field="allowed"
                        )):
                    issues.append("RECOVERY_NEGATIVE_ADMISSION_CONDITION_ALTERED")
                elif (denial.orelse or len(denial.body) != 1
                      or not isinstance(denial.body[0], ast.Return)
                      or not _denies(denial.body[0].value, RESTORE_DENIES)):
                    issues.append("RECOVERY_NEGATIVE_ADMISSION_NOT_COMPLETE_RETURN")
            if writes and min(n.lineno for n in writes) <= guard_stmt.lineno:
                issues.append("CHECKPOINT_WRITE_BEFORE_RECOVERY_WITNESS")
            if any(
                isinstance(n, ast.Call)
                and _callee(n.func) == "save_runtime_checkpoint"
                for st in body[:index+2] for n in ast.walk(st)
            ):
                issues.append("CHECKPOINT_SAVE_WITHIN_OR_BEFORE_DENIAL")
        save_indices = [i for i, st in enumerate(body) if _save_assignment(st)]
        if len(save_indices) != 1:
            issues.append("SHARED_CHECKPOINT_SAVE_BINDING_DRIFT")
        elif admission_indices and save_indices[0] <= admission_indices[0]+1:
            issues.append("SHARED_CHECKPOINT_SAVE_NOT_AFTER_GUARD")

        unexpected_mutations = [
            _callee(n.func) for n in calls
            if (_callee(n.func).split(".")[-1] in {
                "put", "post", "patch", "delete", "request", "create_file", "update_file",
                "restore_file", "restore_checkpoint", "exec", "eval",
            })
        ]
        if unexpected_mutations:
            issues.append("UNREVIEWED_ALTERNATE_RECOVERY_MUTATOR")
        if any(isinstance(n, ast.Name) and n.id == HELPER
               and isinstance(n.ctx, (ast.Store, ast.Del))
               for n in ast.walk(restore)):
            issues.append("RECOVERY_WITNESS_SHADOWED_LOCALLY")

    return {
        "schema": SCHEMA,
        "source_kind": "STATIC_AST_ONLY_REAL_CHECKPOINT_RECOVERY",
        "findings": sorted(set(issues)),
        "recovery_static_deny_contract_intact_lab": not issues,
        "real_independent_witness_verified": False,
        "human_owner_critical_consent_verified": False,
        "checkpoint_restoration_authorized": False,
        "real_provider_effect_proven": False,
        "worker_allowed": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "verdict": "HARD_NO_GO_RECOVERY_WITNESS_NOT_ENROLLED",
    }


def main() -> int:
    try:
        if RECOVERY.is_symlink() or not RECOVERY.is_file():
            raise ValueError("RECOVERY_SOURCE_MISSING_OR_SYMLINK")
        result = inspect_recovery_source(RECOVERY.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"schema": SCHEMA, "verdict": "HARD_NO_GO",
                          "findings": [type(exc).__name__]}))
        return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    # Zero is documentary syntactic conformance ONLY, never a RESTORE GO.
    return 0 if result["recovery_static_deny_contract_intact_lab"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
