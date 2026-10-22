"""A151 offline import boundary auditor: experimental A145-A150 != H0 authority.

A passing return code means ONLY that listed static Python import patterns
from LAB modules were not found in non-test Python source. NOT proof of
executable reachability, independent custodian, owner consent or P0 readiness.
Dynamic/unparsed assembly, subprocesses, opaque plugins and external packages
are outside its scope. Never enables a Worker, deploy, provider or trade.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LAB_MODULE = re.compile(r"^aion_p0_a(?:145|146|147|148|149|150)(?:_|$)")
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".tox",
             ".pytest_cache", "build", "dist"}
STATIC_DYNAMIC_LOADERS = {"__import__", "import_module"}
CALL_DYNAMIC_SUFFIXES = {".import_module", ".__import__"}
SCHEMA = "AION_P0_A151_OFFLINE_LAB_IMPORT_FENCE_V1"


def _is_test_or_lab(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in SKIP_DIRS for part in relative.parts[:-1]):
        return True
    if "tests" in relative.parts[:-1] or path.name.startswith("test_"):
        return True
    # Only explicit A145–A150 root-level experimental modules; the
    # new A151 sentinel is NOT part of this exclusion.
    if len(relative.parts) == 1 and LAB_MODULE.match(path.stem) is not None:
        return True
    return False


def _loader_name(fn: ast.expr) -> str:
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return _loader_name(fn.value) + "." + fn.attr
    return ""


def _module_matches(module: str) -> bool:
    if not isinstance(module, str):
        return False
    # Python import targets have dotted descendants.
    return LAB_MODULE.match(module) is not None


def inspect_source(code: str, relative_path: str) -> list[dict[str, Any]]:
    """Find literal/direct uses of the isolated A145-A150 modules."""
    if not isinstance(code, str) or not isinstance(relative_path, str):
        raise TypeError("invalid_source")
    try:
        tree = ast.parse(code, filename=relative_path)
    except (SyntaxError, ValueError, UnicodeError) as exc:
        # Fail closed on parse errors: never claim this source was inspected.
        return [{"file": relative_path, "line": 0, "reason": "UNPARSEABLE_PYTHON_SOURCE"}]
    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Import):
            target = next((n.name for n in node.names if _module_matches(n.name)), None)
        elif isinstance(node, ast.ImportFrom):
            target = node.module if _module_matches(node.module or "") else None
        elif isinstance(node, ast.Call):
            name = _loader_name(node.func)
            if (name in STATIC_DYNAMIC_LOADERS
                    or any(name.endswith(suffix) for suffix in CALL_DYNAMIC_SUFFIXES)):
                if node.args and isinstance(node.args[0], ast.Constant):
                    val = node.args[0].value
                    if isinstance(val, str) and _module_matches(val):
                        target = val
        if target is not None:
            violations.append({
                "file": relative_path,
                "line": node.lineno,
                "reason": "LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",
                "module": target,
            })
    return violations


def audit_repository(root: Path) -> dict[str, Any]:
    """Static scan of checked-out Python files, no executing target modules."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("repository_root_missing")
    violations: list[dict[str, Any]] = []
    inspected = 0
    excluded = 0
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink():
            violations.append({"file": str(path.relative_to(root)), "line": 0,
                               "reason": "SYMLINKED_PYTHON_SOURCE"})
            continue
        if _is_test_or_lab(path, root):
            excluded += 1
            continue
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append({"file": relative, "line": 0,
                               "reason": "UNREADABLE_PYTHON_SOURCE"})
            continue
        inspected += 1
        violations.extend(inspect_source(source, relative))
    return {
        "schema": SCHEMA,
        "inspected_non_lab_python_files": inspected,
        "excluded_test_and_explicit_lab_files": excluded,
        "findings": violations,
        "static_import_boundary_clean": not bool(violations),
        "external_custodian_independence_verified": False,
        "real_trust_root_enrolled": False,
        "H0_effect_authorization": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "verdict": "HARD_NO_GO_EXTERNAL_WITNESS_UNPROVEN",
    }


def main() -> int:
    report = audit_repository(ROOT)
    print(json.dumps(report, indent=2, sort_keys=True))
    # Exit zero ONLY for the static scan, NOT as an operational GO signal.
    return 0 if report["static_import_boundary_clean"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
