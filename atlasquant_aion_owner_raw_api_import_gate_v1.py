"""Fail-closed static import-boundary audit for AION HUMAN_OWNER raw APIs.

This gate detects Python dependency edges that would let a new runtime module
import internal verification / navigation building blocks. It does NOT
authenticate a host, sandbox Python execution, or stop runtime reflection.
A real restricted server facade and external pen-test remain prerequisites.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCHEMA = "AION_OWNER_RAW_API_IMPORT_BOUNDARY_V1"

# Module names are exact and cannot be configured via an untrusted manifest.
# A UI entrypoint must never import any of these modules. Only the documented
# internal dependency chain may do so. The top-level rooted preflight currently
# has NO production consumers: its trusted host has not been implemented.
INTERNAL_MODULES = frozenset({
    "atlasquant_aion_owner_host_entry_navigation_bridge_v1",
    "atlasquant_aion_trusted_owner_host_crypto_proof_v1",
    "atlasquant_aion_owner_proof_navigation_composition_v1",
    "atlasquant_aion_owner_signed_intent_guard_v1",
    "atlasquant_aion_owner_signed_key_registry_preflight_v1",
    "atlasquant_aion_rooted_owner_signed_ui_preflight_v1",
})

PERMITTED_IMPORTERS = {
    "atlasquant_aion_owner_host_entry_navigation_bridge_v1": frozenset({
        "atlasquant_aion_owner_proof_navigation_composition_v1.py",
    }),
    "atlasquant_aion_trusted_owner_host_crypto_proof_v1": frozenset({
        "atlasquant_aion_owner_proof_navigation_composition_v1.py",
        "atlasquant_aion_owner_signed_intent_guard_v1.py",
        "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
    }),
    "atlasquant_aion_owner_proof_navigation_composition_v1": frozenset({
        "atlasquant_aion_owner_signed_intent_guard_v1.py",
        "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
    }),
    "atlasquant_aion_owner_signed_intent_guard_v1": frozenset({
        "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
    }),
    "atlasquant_aion_owner_signed_key_registry_preflight_v1": frozenset({
        "atlasquant_aion_rooted_owner_signed_ui_preflight_v1.py",
    }),
    "atlasquant_aion_rooted_owner_signed_ui_preflight_v1": frozenset(),
}
SELF = "atlasquant_aion_owner_raw_api_import_gate_v1.py"
SKIP_DIRS = frozenset({
    ".git", ".github", ".venv", "venv", "node_modules", "__pycache__",
    "tests", "docs", ".pytest_cache", ".mypy_cache",
})
DYNAMIC_IMPORT_NAMES = frozenset({
    "__import__", "import_module", "run_module", "find_spec",
})


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    module: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path, "line": self.line,
            "code": self.code, "module": self.module,
        }


def _match_internal(name: str) -> str | None:
    if type(name) is not str or not name:
        return None
    # Exact root module or its dot-qualified children.
    for module in sorted(INTERNAL_MODULES):
        if name == module or name.startswith(module + "."):
            return module
    return None


def _import_refs(node: ast.AST) -> Iterable[tuple[str, int]]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name, node.lineno
    elif isinstance(node, ast.ImportFrom):
        # Covers "from raw_module import X", "from . import raw_module",
        # and "from .raw_module import X". No protected module lives in a
        # nested production package at present.
        if node.module:
            yield node.module, node.lineno
        for alias in node.names:
            if _match_internal(alias.name):
                yield alias.name, node.lineno


def _dynamic_import_ref(node: ast.Call) -> str | None:
    """Common importlib/runpy/__import__ calls with literal module names."""
    function = node.func
    if isinstance(function, ast.Name):
        function_name = function.id
    elif isinstance(function, ast.Attribute):
        function_name = function.attr
    else:
        return None
    if function_name not in DYNAMIC_IMPORT_NAMES:
        return None
    first = node.args[0] if node.args else None
    if isinstance(first, ast.Constant) and type(first.value) is str:
        return first.value
    # Literal keyword in importlib.import_module(name="module").
    for kw in node.keywords:
        if kw.arg in ("name", "mod_name") and isinstance(kw.value, ast.Constant):
            if type(kw.value.value) is str:
                return kw.value.value
    return None


def inspect_python_source(content: str, relative_path: str) -> list[Finding]:
    """Analyze one Python source; reject unaudited protected import edges."""
    if type(content) is not str or type(relative_path) is not str or not relative_path:
        raise ValueError("source and repository-relative path required")
    relative_path = relative_path.replace("\\", "/")
    if relative_path.startswith("/") or ".." in Path(relative_path).parts:
        raise ValueError("unsafe repository path")
    if relative_path == SELF:
        return []  # POLICY IMPLEMENTATION; separately tested and reviewed.
    try:
        tree = ast.parse(content, filename=relative_path)
    except (SyntaxError, UnicodeError, ValueError):
        return [Finding(relative_path, 0, "PYTHON_PARSE_FAILURE", "")]
    violations: list[Finding] = []
    seen: set[tuple[int, str, str]] = set()
    for node in ast.walk(tree):
        refs: list[tuple[str, int, str]] = []
        for name, line in _import_refs(node):
            refs.append((name, line, "PROTECTED_IMPORT_OUTSIDE_ALLOWLIST"))
        if isinstance(node, ast.Call):
            dynamic = _dynamic_import_ref(node)
            if dynamic is not None:
                refs.append((dynamic, node.lineno, "PROTECTED_DYNAMIC_IMPORT"))
        for name, line, code in refs:
            matched = _match_internal(name)
            if matched is None:
                continue
            if relative_path in PERMITTED_IMPORTERS[matched]:
                continue
            key = (line, code, matched)
            if key not in seen:
                violations.append(Finding(relative_path, line, code, matched))
                seen.add(key)
    return sorted(violations, key=lambda v: (v.path, v.line, v.code, v.module))


def _production_py_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if (
            any(part in SKIP_DIRS for part in relative.parts[:-1])
            or relative.name.startswith("test_")
            or relative.name == SELF
        ):
            continue
        yield path


def scan_production_checkout(repository_root: str | Path) -> tuple[int, list[Finding]]:
    """Audit Python production sources, no network, subprocess or writes.

    Tests, docs and vendored dependency dirs are excluded intentionally.
    CI must run from a trusted pristine checkout. Symlinks fail closed.
    """
    root = Path(repository_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("checkout must be a normal directory")
    findings: list[Finding] = []
    inspected = 0
    for path in _production_py_files(root):
        relative = path.relative_to(root).as_posix()
        inspected += 1
        if path.is_symlink():
            findings.append(Finding(relative, 0, "SYMLINKED_PRODUCTION_SOURCE", ""))
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append(Finding(relative, 0, "PRODUCTION_SOURCE_UNREADABLE", ""))
            continue
        findings.extend(inspect_python_source(source, relative))
    return inspected, sorted(findings, key=lambda f: (f.path, f.line, f.code, f.module))


__all__ = [
    "SCHEMA", "INTERNAL_MODULES", "PERMITTED_IMPORTERS", "Finding",
    "inspect_python_source", "scan_production_checkout",
]
