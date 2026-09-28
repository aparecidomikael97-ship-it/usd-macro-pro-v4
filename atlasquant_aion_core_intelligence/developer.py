"""Static application-level analysis, review and recorded regression comparison.

The Developer Engine is reused for logical planning only. Security-chain
contracts belong to a separate adapter boundary; no Builder/Runner is imported.
"""
import ast
from datetime import datetime
from hashlib import sha256
from atlasquant_aion_developer_engine import new_development_workflow
from .administration import observed_status
from .context import Context, Domain
from .evidence import Evidence, safe_text


MAX_CODE_BYTES = 200_000


def _tree(code: str):
    if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError("bounded Python source required")
    return ast.parse(code)


def analyze(code: str) -> dict:
    try:
        tree = _tree(code)
    except SyntaxError as error:
        return {"status": "SYNTAX_ERROR", "line": error.lineno,
                "source_executed": False, "tests_executed": False}
    names = sorted({node.name for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))})
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append({"rule": "BARE_EXCEPT", "line": node.lineno, "kind": "REVIEW_REQUIRED"})
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            findings.append({"rule": "DYNAMIC_EXECUTION_CALL", "line": node.lineno, "kind": "REVIEW_REQUIRED"})
    return {"status": "STATIC_ANALYSIS_ONLY", "source_sha256": sha256(code.encode()).hexdigest(),
            "symbols": names, "findings": findings, "tests_executed": False,
            "source_executed": False, "security_audit_complete": False,
            "test_status": "UNKNOWN", "reason": "AST inspection does not prove correctness or test success."}


def compare(before: str, after: str, observations: tuple[Evidence, ...], now: datetime) -> dict:
    old, new = analyze(before), analyze(after)
    if old["status"] == "SYNTAX_ERROR" or new["status"] == "SYNTAX_ERROR":
        return {"status": "NEEDS_REVIEW", "before": old, "after": new,
                "regression": "SYNTAX_REGRESSION" if new["status"] == "SYNTAX_ERROR" and old["status"] != "SYNTAX_ERROR" else "UNKNOWN",
                "tests_executed": False}
    old_test = observed_status("tests@" + old["source_sha256"], observations, now)
    new_test = observed_status("tests@" + new["source_sha256"], observations, now)
    known = old_test["state"] == new_test["state"] == "SYSTEM_OBSERVED"
    regression = "OBSERVED_TEST_REGRESSION" if known and old_test["value"] == "PASS" and new_test["value"] == "FAIL" else "UNKNOWN"
    return {"status": "COMPARISON_ONLY", "before": old, "after": new,
            "removed_symbols": sorted(set(old["symbols"]) - set(new["symbols"])),
            "added_symbols": sorted(set(new["symbols"]) - set(old["symbols"])),
            "before_test_evidence": old_test, "after_test_evidence": new_test,
            "regression": regression, "tests_executed": False,
            "reason": "No absence-of-regression claim; test evidence must match each source digest."}


def plan(context: Context, request: str, *, branch: str, baseline_ref: str, now: datetime) -> dict:
    context.require_domain(Domain.DEVELOPER)
    if context.role != "ADMIN":
        raise ValueError("ROLE_DENIED")
    workflow = new_development_workflow(safe_text(request), branch=branch,
              baseline_ref=baseline_ref, requested_by=context.actor_id, created_at=now.isoformat())
    return {"workflow": workflow, "test_plan": ["targeted_tests", "risk_regressions", "independent_review"],
            "execution_authorized": False, "security_chain_adapter": "UNAVAILABLE",
            "reason": "Future handoff must use the existing security chain; no execution attached."}
