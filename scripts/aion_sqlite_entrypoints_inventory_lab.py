"""G129 read-only SQLite native-entrypoint inventory for AION, LAB ONLY.

Enumerates tracked production Python modules using Git, parses their ASTs,
and flags direct sqlite3.connect calls that have no recorded human review.
This tool is a *regression inventory*, not an OS/native VFS security boundary.

NO P0 clearance, NO self-attested receipt, NO Worker/prod changes.
Known legacy calls remain security debt (not approved as safe by this list).
A green scan only means the review list has not silently grown.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

# Explicit REVIEW DEBT, not a security exception or certification.
# The chat-store native call below creates an offline :memory: validator DB.
# Its *physical* connection uses an untrusted caller/default factory, which
# is separately detected by the factory_reference classification.
REVIEWED_NATIVE_OPEN_MAX = {
    "aion_chat/store.py": 1,
    "atlasquant_aion_core_intelligence/store.py": 1,
    "atlasquant_aion_durable_execution_kernel.py": 1,
    "atlasquant_aion_nonce_registry.py": 1,
    "atlasquant_aion_vault_physical_backend.py": 1,
}

STORE_CONSTRUCTORS = {
    "SQLiteChatStore",
    "OperationScopedSQLiteChatStore",
    "CoreStore",
    "DurableExecutionStore",
    "PersistentNonceRegistry",
    "VaultPhysicalBackend",
}

# REVIEW DEBT: known, explicitly gated non-test Python constructor sites.
# The absence of direct CoreStore/DurableExecutionStore/NonceRegistry/Vault
# construction in the inspected operational modules is a static observation,
# NOT proof that injection/dynamic import or external host activation is safe.
REVIEWED_STORE_CONSTRUCTOR_MAX = {
    "aion_chat/staged_store.py::SQLiteChatStore": 2,
    "atlasquant_aion_chat_host_staging.py::OperationScopedSQLiteChatStore": 1,
    "atlasquant_aion_chat_storage_resilience.py::SQLiteChatStore": 1,
    "atlasquant_aion_chat_ui.py::SQLiteChatStore": 1,
    "tools/aion_durable_task_cas_process_worker.py::SQLiteChatStore": 1,
}


def new_unreviewed_constructors(
    observed: dict[str, int],
    baseline: dict[str, int] | None = None,
) -> dict[str, int]:
    limits = REVIEWED_STORE_CONSTRUCTOR_MAX if baseline is None else baseline
    return {
        site: count for site, count in sorted(observed.items())
        if count > limits.get(site, 0)
    }


def is_production_path(path: str) -> bool:
    parts = Path(path).parts
    if not parts or Path(path).suffix != ".py":
        return False
    if any(p in {"tests", "test", "labs", "scripts"} for p in parts[:-1]):
        return False
    filename = parts[-1]
    return not (
        filename.startswith(("test_", "lab_"))
        or filename.endswith(("_test.py", "_lab.py"))
    )


def scan_source(source: str, filename: str = "<fixture>") -> list[dict]:
    """Conservatively inventory explicit calls, including lexical aliases.

    This is an AST review trigger, NOT scope-aware data flow, executable
    provenance, or a reliable defense against dynamic lookup/rebinding.
    False positives due to shadowing require human review; they are not
    silently excluded from a security-relevant inventory.
    """
    tree = ast.parse(source, filename=filename)
    module_names = set()
    connect_names = set()
    constructor_aliases = {name: name for name in STORE_CONSTRUCTORS}
    assignments = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == "sqlite3":
                    module_names.add(item.asname or "sqlite3")
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                if node.module == "sqlite3" and item.name == "connect":
                    connect_names.add(item.asname or "connect")
                if item.name in STORE_CONSTRUCTORS:
                    constructor_aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets
                     if isinstance(target, ast.Name)]
            if names:
                assignments.append((names, node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                assignments.append(([node.target.id], node.value))

    # A bounded fixed point is sufficient for chains of simple assignments:
    # RegistryAlias = PersistentNonceRegistry; Another = RegistryAlias.
    # Unknown computed expressions, getattr and imports at runtime remain
    # explicitly untracked, NOT "proved safe".
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            connect_alias = False
            module_alias = False
            constructor = None
            if isinstance(value, ast.Name):
                connect_alias = value.id in connect_names
                module_alias = value.id in module_names
                constructor = constructor_aliases.get(value.id)
            elif isinstance(value, ast.Attribute):
                connect_alias = (
                    value.attr == "connect"
                    and isinstance(value.value, ast.Name)
                    and value.value.id in module_names
                )
                if value.attr in STORE_CONSTRUCTORS:
                    constructor = value.attr
            for name in targets:
                if connect_alias and name not in connect_names:
                    connect_names.add(name)
                    changed = True
                if module_alias and name not in module_names:
                    module_names.add(name)
                    changed = True
                if constructor and name not in constructor_aliases:
                    # Preserve the first lexical candidate if a name is rebound.
                    # Rebinding is outside this static checker and needs review.
                    constructor_aliases[name] = constructor
                    changed = True

    observations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "connect"
                and isinstance(func.value, ast.Name)
                and func.value.id in module_names
            ):
                observations.append({"line": node.lineno, "kind": "native_connect"})
                continue
            if isinstance(func, ast.Name) and func.id in connect_names:
                observations.append({"line": node.lineno, "kind": "native_connect"})
                continue
            constructor = (
                constructor_aliases.get(func.id) if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute)
                and func.attr in STORE_CONSTRUCTORS else None
            )
            if constructor in STORE_CONSTRUCTORS:
                observations.append({
                    "line": node.lineno,
                    "kind": "store_constructor",
                    "symbol": constructor,
                })
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "connect"
            and isinstance(node.value, ast.Name)
            and node.value.id in module_names
        ):
            observations.append({
                "line": node.lineno, "kind": "native_connect_reference"
            })
    return sorted(
        observations, key=lambda item: (item["line"], item["kind"])
    )


def tracked_python_files(root: Path) -> list[str]:
    raw = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    paths = sorted(
        item.decode("utf-8") for item in raw.split(b"\0") if item
    )
    return [path for path in paths if is_production_path(path)]


def audit(root: Path = REPO_ROOT) -> dict:
    paths = tracked_python_files(root)
    findings = []
    for path in paths:
        source = (root / path).read_text(encoding="utf-8-sig")
        for item in scan_source(source, path):
            findings.append({"path": path, **item})

    native_counts = Counter(
        item["path"] for item in findings
        if item["kind"] == "native_connect"
    )
    new_or_expanded = {
        path: count for path, count in sorted(native_counts.items())
        if count > REVIEWED_NATIVE_OPEN_MAX.get(path, 0)
    }
    # Existing debt remains printed even if --check returns success. This
    # checker is NOT a pass/fail measure of production authorization safety.
    unresolved = {
        path: count for path, count in sorted(native_counts.items())
        if path in REVIEWED_NATIVE_OPEN_MAX
    }
    constructor_counts = Counter(
        item["path"] + "::" + item["symbol"] for item in findings
        if item["kind"] == "store_constructor"
    )
    unreviewed_constructors = new_unreviewed_constructors(constructor_counts)
    # Constructor review debt is not an activation proof. It covers explicit
    # AST construction only and deliberately cannot see dynamic injection.
    old_constructors = {
        site: count for site, count in sorted(constructor_counts.items())
        if site in REVIEWED_STORE_CONSTRUCTOR_MAX
    }
    return {
        "status": "INVENTORY_ONLY_NOT_P0",
        "production_python_files_scanned": len(paths),
        "legacy_direct_sqlite_calls": unresolved,
        "new_or_expanded_unreviewed_direct_sqlite_calls": new_or_expanded,
        "legacy_store_constructor_calls": old_constructors,
        "new_or_expanded_unreviewed_store_constructors": unreviewed_constructors,
        "findings": findings,
        "limitations": [
            "No dynamic imports, getattr, generated code, non-Python native callers",
            "No SQLite VFS fd/handle identity or WAL/SHM attestation",
            "Alias detection is lexical, not scope-aware or a call graph; no OS ACL enforcement",
            "Legacy reviewed means tracked debt, NOT safe or P0-approved",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-known", action="store_true",
        help="Fail for new unreviewed native sqlite opens OR store constructors",
    )
    args = parser.parse_args()
    result = audit()
    print(json.dumps(result, sort_keys=True, indent=2))
    if args.check_known and result["new_or_expanded_unreviewed_direct_sqlite_calls"]:
        print("G129_NEW_UNREVIEWED_NATIVE_OPEN=FAIL", file=sys.stderr)
        return 1
    if args.check_known and result["new_or_expanded_unreviewed_store_constructors"]:
        print("G130_NEW_UNREVIEWED_STORE_CONSTRUCTOR=FAIL", file=sys.stderr)
        return 1
    print("G129_INVENTORY_CHECK=PASS_NOT_P0")
    print("G130_CONSTRUCTOR_GROWTH_GATE=PASS_NOT_P0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
