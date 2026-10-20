"""Compare historical and migrated Journal test methods WITHOUT executing them.

LAB-only evidence aid, not a test migration approval or a P0 acceptance gate.
Requires the original 12-Oct folder to be recovered; all conclusions are
conservative and require independent review. No import of historical modules.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import stat

CASES = (
    ("JOURNAL_A", "test_lab_journal.py", "test_lab_journal_migrated_v2.py", "test_readback_rejects_forged_content"),
    ("JOURNAL_B", "test_conservative_journal.py", "test_conservative_journal_migrated_v2.py", "test_direct_SQL_still_bypasses_limit_characterization"),
)
MAX_BYTES = 2 * 1024 * 1024


def locate(root: Path, name: str) -> tuple[Path | None, str]:
    if not root.is_dir() or root.is_symlink():
        return None, "ARCHIVE_UNAVAILABLE"
    root = root.resolve()
    try:
        found = sorted(root.rglob(name))
    except OSError:
        return None, "SCAN_ERROR"
    if len(found) != 1:
        return None, "MISSING" if not found else "AMBIGUOUS_DUPLICATES"
    path = found[0]
    if path.is_symlink() or not path.is_file():
        return None, "UNSAFE_PATH"
    # Avoid reading symlinked directories even on platforms where glob follows them.
    if not path.resolve().is_relative_to(root) or any(
        part.is_symlink() for part in path.parents if part == root or root in part.parents
    ):
        return None, "UNSAFE_PATH"
    try:
        s = path.stat()
        if not stat.S_ISREG(s.st_mode) or s.st_size > MAX_BYTES:
            return None, "UNSAFE_SIZE_OR_TYPE"
    except OSError:
        return None, "UNREADABLE"
    return path, "FOUND_UNAUTHENTICATED"


def read_ast(path: Path) -> tuple[ast.Module, str]:
    # Read as untrusted inert text. Parsing with ast.parse NEVER executes it.
    before = path.stat()
    if before.st_size > MAX_BYTES:
        raise ValueError("SOURCE_TOO_LARGE")
    content = path.read_bytes()
    after = path.stat()
    if len(content) > MAX_BYTES or (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ):
        raise ValueError("SOURCE_CHANGED_WHILE_READING")
    digest = hashlib.sha256(content).hexdigest()
    try:
        tree = ast.parse(content.decode("utf-8-sig"), filename=path.name)
    except (UnicodeError, SyntaxError, ValueError) as err:
        raise ValueError("UNPARSABLE_SOURCE") from err
    return tree, digest


def get_test(tree: ast.Module, method: str) -> tuple[ast.FunctionDef | None, str]:
    methods = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method]
    if len(methods) != 1:
        return None, "METHOD_MISSING" if not methods else "DUPLICATE_METHODS"
    if isinstance(methods[0], ast.AsyncFunctionDef):
        return None, "ASYNCHRONOUS_METHOD_REVIEW"
    return methods[0], "FOUND"


def assertion_shapes(fn: ast.FunctionDef) -> tuple[str, ...]:
    found: list[str] = []
    for n in ast.walk(fn):
        is_assert_call = (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr.startswith("assert")
        )
        if isinstance(n, ast.Assert) or is_assert_call:
            found.append(ast.dump(n, include_attributes=False))
    return tuple(sorted(found))


def review_pair(root: Path, case_id: str, orig_name: str, migr_name: str, method: str) -> dict:
    r = {
        "case": case_id,
        "legacy_method": method,
        "status": "REVIEW_REQUIRED",
        "p0_homologated": False,
        "historical_code_executed": False,
        "authentic_original_source_proven": False,
        "migrated_behavior_proven": False,
        "manual_security_review_required": True,
        "original_sha256": None,
        "migrated_sha256": None,
        "findings": [],
    }
    orig, orig_status = locate(root, orig_name)
    migrated, mig_status = locate(root, migr_name)
    if orig is None or migrated is None:
        r["findings"].extend([f"ORIGINAL:{orig_status}", f"MIGRATED:{mig_status}"])
        return r
    try:
        orig_ast, orig_hash = read_ast(orig)
        migrated_ast, migrated_hash = read_ast(migrated)
    except (OSError, ValueError) as err:
        r["findings"].append(f"STATIC_READ_OR_PARSE_BLOCKED:{type(err).__name__}")
        return r
    r["original_sha256"] = orig_hash
    r["migrated_sha256"] = migrated_hash
    original_fn, a = get_test(orig_ast, method)
    migrated_fn, b = get_test(migrated_ast, method)
    if original_fn is None or migrated_fn is None:
        r["findings"].extend([f"ORIGINAL_METHOD:{a}", f"MIGRATED_METHOD:{b}"])
        return r
    a_asserts = assertion_shapes(original_fn)
    b_asserts = assertion_shapes(migrated_fn)
    r["assertion_nodes_original"] = len(a_asserts)
    r["assertion_nodes_migrated"] = len(b_asserts)
    if not a_asserts or not b_asserts:
        r["findings"].append("NO_EXPLICIT_ASSERTION_NODES")
    elif a_asserts != b_asserts:
        r["findings"].append("ASSERTION_AST_CHANGED_REQUIRES_HUMAN_DIFF")
    else:
        r["findings"].append("ASSERTION_AST_MATCHES_BUT_RUNTIME_EQUIVALENCE_UNPROVEN")
    if ast.dump(original_fn, include_attributes=False) != ast.dump(migrated_fn, include_attributes=False):
        r["findings"].append("TEST_BODY_CHANGED_MANUAL_REVIEW_REQUIRED")
    else:
        r["findings"].append("TEST_BODY_AST_UNCHANGED_NO_MIGRATION_PROVEN")
    r["findings"].append("PUBLIC_JOURNAL_DB_READONLY_AND_RAW_SQL_FIXTURE_BOUNDARY_NOT_REEXECUTED")
    return r


def inspect(root: Path) -> dict:
    rows = [review_pair(root, *args) for args in CASES]
    return {
        "schema": "AION_P0_JOURNAL_MIGRATION_STATIC_REVIEW_LAB_V1",
        "status": "HARD_NO_GO_REVIEW_REQUIRED",
        "historical_76_tests_executed": False,
        "journal_p0_homologated": 0,
        "worker_allowed": False,
        "automatic_retry_allowed": False,
        "production_allowed": False,
        "rows": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only AST comparison, never executes recovered test source")
    p.add_argument("--root", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(inspect(args.root), ensure_ascii=False, indent=2, sort_keys=True))
    return 3  # Never use a static comparison to approve an original P0.


if __name__ == "__main__":
    raise SystemExit(main())
