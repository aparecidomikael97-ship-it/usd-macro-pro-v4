"""Offline AST-only inventory of Autopilot writes outside Shadow/Flight deny."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

EXPECTED = frozenset({
    ("gh_put_json", "SCANNER_PATH"),
    ("gh_put_json", "DAILY_CACHE_PATH"),
    ("gh_put_json", "RESEARCH_TF_CACHE_PATH"),
    ("gh_put_json", "SERIES_PATH"),
    ("gh_put_json", "MASTER_PATH"),
    ("gh_put_json", "NEWS_CURRENT_PATH"),
    ("gh_put_json", "AION_LIVE_EVENT_JOURNAL_PATH"),
    ("gh_put_csv", "NEWS_VALIDATION_PATH"),
    ("gh_put_json", "SIGNAL_LIFECYCLE_PATH"),
    ("gh_put_json", "HOME_SNAPSHOT_PATH"),
    ("gh_put_json", "QUOTA_SHADOW_PATH"),
    ("gh_put_json", "STATUS_PATH"),
})


def _function(parent: ast.AST, name: str) -> ast.FunctionDef:
    matches = [n for n in getattr(parent, "body", ())
               if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError("EXPECTED_ONE_FUNCTION_" + name)
    return matches[0]


def _method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    matches = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls]
    if len(matches) != 1:
        raise ValueError("EXPECTED_ONE_CLASS_" + cls)
    return _function(matches[0], name)


def _dotted(expr: ast.AST) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return _dotted(expr.value) + "." + expr.attr
    return ""


def find_sinks(source: str) -> list[tuple[str, str]]:
    """Enumerate main() mutations; unknown expressions do not disappear."""
    main = _function(ast.parse(source), "main")
    sinks = []
    for call in ast.walk(main):
        if not isinstance(call, ast.Call):
            continue
        writer = _dotted(call.func)
        if writer not in ("gh_put_json", "gh_put_csv"):
            continue
        target = (call.args[0].id if call.args and isinstance(call.args[0], ast.Name)
                  else "DYNAMIC_OR_MISSING_TARGET")
        sinks.append((writer, target))
    return sorted(sinks)


def _old_budget_retry_shape(tree: ast.Module) -> bool:
    save = _method(tree, "GitHubStore", "save")
    change = _method(tree, "Budget", "_change")
    reported_conflict_returns_false = False
    for clause in ast.walk(save):
        if not (isinstance(clause, ast.If) and isinstance(clause.test, ast.Compare)):
            continue
        compare = clause.test
        if not (len(compare.ops) == 1 and isinstance(compare.ops[0], ast.In)
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], (ast.Tuple, ast.Set))):
            continue
        codes = {n.value for n in compare.comparators[0].elts
                 if isinstance(n, ast.Constant) and type(n.value) is int}
        if {409, 422}.issubset(codes) and any(
            isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
            and n.value.value is False for n in clause.body
        ):
            reported_conflict_returns_false = True
    retry_loop = any(
        isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
        and _dotted(n.iter.func) == "range" and len(n.iter.args) == 1
        and isinstance(n.iter.args[0], ast.Constant)
        and type(n.iter.args[0].value) is int and n.iter.args[0].value > 1
        for n in ast.walk(change)
    )
    return reported_conflict_returns_false and retry_loop


def audit(root: Path) -> dict[str, Any]:
    root = Path(root)
    auto = ast.parse((root / "autopilot_v107.py").read_text(encoding="utf-8"))
    budget = ast.parse((root / "twelve_budget_v1108.py").read_text(encoding="utf-8"))
    sinks = find_sinks((root / "autopilot_v107.py").read_text(encoding="utf-8"))
    seen = set(sinks)
    missing, new = sorted(EXPECTED - seen), sorted(seen - EXPECTED)
    duplicates = sorted(x for x in seen if sinks.count(x) != 1)
    put_fn = _function(auto, "gh_put_bytes")
    calls = [(_dotted(n.func), n.lineno) for n in ast.walk(put_fn)
             if isinstance(n, ast.Call)]
    put_lines = [n for name, n in calls if name == "requests.put"]
    post_get = bool(put_lines) and any(
        name == "requests.get" and n > min(put_lines) for name, n in calls
    )
    success_no_readback = bool(put_lines) and not post_get and any(
        isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)
        and len(n.value.elts) == 2
        and all(isinstance(x, ast.Constant) for x in n.value.elts)
        and [x.value for x in n.value.elts] == [True, ""]
        for n in ast.walk(put_fn)
    )
    protected = sum(
        1 for n in ast.walk(_function(auto, "persist_decision_evidence"))
        if isinstance(n, ast.Call)
        and _dotted(n.func) == "guarded_autopilot_evidence_write"
    )
    zero_exit = any(
        isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
        and n.value.value == 0 for n in ast.walk(_function(auto, "main"))
    )
    complete = not missing and not new and not duplicates and len(sinks) == 12
    return {
        "schema": "ATLASQUANT_AION_V2_AUTOPILOT_WRITE_INVENTORY_V1",
        "state": "KNOWN_RISK_REVIEW_REQUIRED" if complete else "INVENTORY_DRIFT_BLOCK",
        "inventory_consistent": complete,
        "generic_sinks": [list(x) for x in sinks],
        "generic_sink_count": len(sinks),
        "missing_expected": missing,
        "new_unreviewed": new,
        "duplicate_calls": duplicates,
        "shadow_flight_guard_calls": protected,
        "generic_http_success_without_readback_shape": success_no_readback,
        "budget_reported_conflict_retry_shape": _old_budget_retry_shape(budget),
        "main_has_zero_exit": zero_exit,
        "source_only": True,
        "remote_write_executed": False,
        "remote_durability_certified": False,
        "cross_process_cas_certified": False,
        "safe_to_deploy": False,
    }


def main() -> int:
    result = audit(Path(__file__).resolve().parent)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Zero means ONLY pinned inventory, not operational safety.
    return 0 if result["inventory_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
