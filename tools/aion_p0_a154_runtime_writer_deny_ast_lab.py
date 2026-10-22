"""A154 read-only AST verifier for the ACTUAL Checkpoint Mestre GitHub writer.

The earlier A136 inventory checks lexical line order of a witness call and
requests.put. This more stringent A154 contract also verifies the immediate,
unconditional deny-only helper and the exact negative admission branch.

All checks are STATIC SYNTAX properties, NOT a formal control-flow proof,
not a real independently enrolled witness, not live enforcement, not IAM and
not an authorization to write. Dynamic aliases/monkeypatch/other languages,
reflection, runtime configuration, indirect transports and external
credentials require independent audit. No executed scanned code or network.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = ROOT / "atlasquant_aion_memory.py"
GUARD_NAME = "_require_independent_runtime_write_witness"
WRITER_NAME = "save_runtime_checkpoint"
REQUIRED_HELPER_VALUES = {
    "allowed": False,
    "status": "BLOCKED",
    "independent_witness_enrolled": False,
    "monotonic_head_proven": False,
    "owner_identity_verified": False,
    "executes_action": False,
}
REQUIRED_DENIAL_VALUES = {
    "status": "BLOCKED",
    "saved": False,
    "verified": False,
    "write_outcome": "NOT_ATTEMPTED",
    "reconciliation_required": False,
    "automatic_retry_allowed": False,
    "independent_witness_enrolled": False,
    "monotonic_head_proven": False,
}
SCHEMA = "AION_P0_A154_RUNTIME_WRITER_DENY_AST_LAB_V1"


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        root = _name(node.value)
        return root + "." + node.attr if root else node.attr
    return ""


def _is_literal(node: ast.AST | None, expected: Any) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is type(expected) and node.value == expected


def _dict_expression(node: ast.AST | None) -> dict[str, ast.AST] | None:
    if not isinstance(node, ast.Dict):
        return None
    out: dict[str, ast.AST] = {}
    for k, v in zip(node.keys, node.values):
        if not isinstance(k, ast.Constant) or type(k.value) is not str:
            return None
        if k.value in out:
            return None
        out[k.value] = v
    return out


def _matches_values(node: ast.AST | None, required: dict[str, Any]) -> bool:
    fields = _dict_expression(node)
    return fields is not None and all(
        key in fields and _is_literal(fields[key], wanted)
        for key, wanted in required.items()
    )


def _strip_docstring(statements: list[ast.stmt]) -> list[ast.stmt]:
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ) and isinstance(statements[0].value.value, str):
        return statements[1:]
    return statements


def _guard_assignment(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return False
    target = statement.targets[0]
    if not isinstance(target, ast.Name) or target.id != "admission":
        return False
    call = statement.value
    if not isinstance(call, ast.Call) or _name(call.func) != GUARD_NAME:
        return False
    if len(call.args) != 1 or not isinstance(call.args[0], ast.Name) or call.args[0].id != "cfg":
        return False
    if any(kw.arg is None for kw in call.keywords):
        return False
    if {kw.arg for kw in call.keywords} != {"expected_sha", "expected_digest"}:
        return False
    digest = next(kw.value for kw in call.keywords if kw.arg == "expected_digest")
    if not isinstance(digest, ast.Name) or digest.id != "expected_digest":
        return False
    return True


def _is_exact_negative_admission(condition: ast.AST) -> bool:
    if not isinstance(condition, ast.Compare):
        return False
    if len(condition.ops) != 1 or not isinstance(condition.ops[0], ast.IsNot):
        return False
    if len(condition.comparators) != 1 or not _is_literal(condition.comparators[0], True):
        return False
    left = condition.left
    if not isinstance(left, ast.Call) or left.keywords or len(left.args) != 1:
        return False
    if not _is_literal(left.args[0], "allowed"):
        return False
    if not isinstance(left.func, ast.Attribute) or left.func.attr != "get":
        return False
    return isinstance(left.func.value, ast.Name) and left.func.value.id == "admission"


def inspect_runtime_writer_source(source: str) -> dict[str, Any]:
    """Fail closed unless a very specific deny-only writer AST is maintained."""
    findings: list[str] = []
    if type(source) is not str or len(source.encode("utf-8")) > 3_000_000:
        findings.append("SOURCE_INVALID_OR_TOO_LARGE")
        source = ""
    try:
        tree = ast.parse(source, filename="atlasquant_aion_memory.py")
    except (SyntaxError, TypeError, ValueError, UnicodeError, RecursionError):
        findings.append("RUNTIME_SOURCE_UNPARSEABLE")
        tree = ast.Module(body=[], type_ignores=[])

    def unique_function(name: str) -> ast.FunctionDef | None:
        matches = [x for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and x.name == name]
        if len(matches) != 1 or not isinstance(matches[0], ast.FunctionDef):
            findings.append("FUNCTION_MISSING_DUPLICATED_OR_ASYNC:" + name)
            return None
        if matches[0].decorator_list:
            findings.append("FUNCTION_DECORATOR_UNREVIEWED:" + name)
        return matches[0]

    guard_fn = unique_function(GUARD_NAME)
    writer_fn = unique_function(WRITER_NAME)
    if guard_fn is not None:
        helper_body = _strip_docstring(guard_fn.body)
        if (len(helper_body) != 1 or not isinstance(helper_body[0], ast.Return)
                or not _matches_values(helper_body[0].value, REQUIRED_HELPER_VALUES)):
            findings.append("INDEPENDENT_WITNESS_HELPER_NOT_UNCONDITIONALLY_DENY_ONLY")
        # Assignment or import that replaces the helper in the same module
        # invalidates any static claim of an unmodified call target.
        for stmt in tree.body:
            if stmt is guard_fn:
                continue
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == GUARD_NAME:
                        findings.append("GUARD_HELPER_REBOUND_AT_MODULE_SCOPE")
                        break

    if writer_fn is not None:
        body = _strip_docstring(writer_fn.body)
        guards = [n for n in ast.walk(writer_fn)
                  if isinstance(n, ast.Call) and _name(n.func) == GUARD_NAME]
        puts = [n for n in ast.walk(writer_fn)
                if isinstance(n, ast.Call) and _name(n.func) == "requests.put"]
        if len(guards) != 1:
            findings.append("GUARD_CALL_NOT_UNIQUE")
        if len(puts) != 1:
            findings.append("RUNTIME_GITHUB_PUT_NOT_UNIQUE")
        indices = [i for i, stmt in enumerate(body) if _guard_assignment(stmt)]
        if len(indices) != 1:
            findings.append("GUARD_ASSIGNMENT_NOT_DIRECT_TOP_LEVEL")
        else:
            index = indices[0]
            guard_stmt = body[index]
            if index + 1 >= len(body):
                findings.append("NEGATIVE_ADMISSION_BRANCH_MISSING")
            else:
                negative = body[index+1]
                if (not isinstance(negative, ast.If)
                        or not _is_exact_negative_admission(negative.test)):
                    findings.append("NEGATIVE_ADMISSION_CONDITION_ALTERED")
                elif (negative.orelse or len(negative.body) != 1
                      or not isinstance(negative.body[0], ast.Return)
                      or not _matches_values(negative.body[0].value, REQUIRED_DENIAL_VALUES)):
                    findings.append("NEGATIVE_ADMISSION_MUST_RETURN_COMPLETE_DENIAL")
            if puts and min(x.lineno for x in puts) <= guard_stmt.lineno:
                findings.append("GITHUB_PUT_PRECEDES_GUARD")
            # No GitHub transport may be introduced before completion of
            # the guard+denial pair, even if hidden inside a conditional.
            for stmt in body[:index+2]:
                if any(isinstance(n, ast.Call) and _name(n.func) == "requests.put"
                       for n in ast.walk(stmt)):
                    findings.append("GITHUB_MUTATION_WITHIN_OR_BEFORE_GUARD")

        # Shadowing guard binding through nested assignments/del statements is
        # never needed in the actual writer and would invalidate assumptions.
        guard_local_store = [
            n for n in ast.walk(writer_fn)
            if isinstance(n, ast.Name) and n.id == GUARD_NAME
            and isinstance(n.ctx, (ast.Store, ast.Del))
        ]
        if guard_local_store:
            findings.append("GUARD_HELPER_SHADOWED_LOCALLY")

    return {
        "schema": SCHEMA,
        "source_type": "STATIC_AST_REVIEW_OF_REAL_RUNTIME_WRITER",
        "source_size": len(source),
        "findings": sorted(set(findings)),
        "writer_deny_shape_intact_lab": not findings,
        "independent_runtime_witness_enrolled": False,
        "actual_runtime_effects_proven_safe": False,
        "github_checkpoint_write_authorized": False,
        "worker_allowed": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "verdict": "HARD_NO_GO_RUNTIME_WITNESS_UNENROLLED",
    }


def main() -> int:
    try:
        if RUNTIME_SOURCE.is_symlink() or not RUNTIME_SOURCE.is_file():
            raise ValueError("RUNTIME_WRITER_NOT_AN_ORDINARY_FILE")
        result = inspect_runtime_writer_source(RUNTIME_SOURCE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"schema": SCHEMA, "verdict": "HARD_NO_GO",
                          "findings": ["RUNTIME_WRITER_UNREADABLE:"+type(exc).__name__]}))
        return 3
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["writer_deny_shape_intact_lab"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
