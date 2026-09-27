"""Read-only repository intelligence for the AION Developer workspace.

The scanner produces structural metadata only. It never executes repository
code, imports scanned modules, invokes a shell, calls the network, writes files,
reads known secret files, follows symlinks outside the requested root, commits,
merges or deploys.

The output is designed to feed the existing AION Developer Engine / Dev Fusion
workflow with bounded evidence about modules, tests, imports and likely test
coverage.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_engine import PHASES
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_INTELLIGENCE_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_DEVELOPMENT_PLAN_V1"
MAX_FILES = 800
MAX_FILE_BYTES = 1_000_000
SAFE_SUFFIXES = frozenset({".py", ".yml", ".yaml", ".md", ".json", ".toml", ".txt", ".cfg", ".ini"})
DENY_DIRS = frozenset({
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".streamlit",
})
SENSITIVE_NAMES = frozenset({
    ".env", "secrets.toml", "credentials.json", "token.json", "tokens.json",
    "service-account.json", "service_account.json", "private_key.pem",
    "id_rsa", "id_ed25519",
})
RISK_PATTERNS = {
    "AUTHORITY": ("guardian", "access_control", "entitlement", "approval", "permission"),
    "SECRETS": ("secret", "vault", "credential", "token", "observability"),
    "TRADING": ("trading", "broker", "order", "execution", "paper_trading", "risk_guardian"),
    "FINANCIAL": ("billing", "payment", "treasury", "investment", "sales"),
    "RELEASE": ("deploy", "release", "production", "render", "workflow"),
    "ADMIN": ("admin", "tenant", "account"),
}


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _digest(value: Any, length: int = 20) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _is_sensitive_name(name: str) -> bool:
    lower = str(name or "").lower()
    if lower in SENSITIVE_NAMES or lower.startswith(".env."):
        return True
    collapsed = lower.replace("-", "_").replace(" ", "_")
    return any(token in collapsed for token in (
        "private_key", "client_secret", "api_secret", "access_token",
        "refresh_token", "service_account_key",
    ))


def _category(relative: str) -> str:
    lower = relative.lower()
    name = Path(relative).name.lower()
    if name.startswith("test_") and name.endswith(".py"):
        return "TEST"
    if lower.startswith(".github/workflows/"):
        return "WORKFLOW"
    if lower.startswith("docs/") or name.endswith(".md"):
        return "DOC"
    if name.endswith(".py"):
        return "MODULE"
    if name.endswith((".yml", ".yaml", ".json", ".toml", ".cfg", ".ini")):
        return "CONFIG"
    return "OTHER"


def _risk_tags(relative: str) -> list[str]:
    lower = relative.lower()
    tags = [
        tag for tag, patterns in RISK_PATTERNS.items()
        if any(pattern in lower for pattern in patterns)
    ]
    return sorted(tags)


def _python_facts(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {
            "syntax_state": "ERROR",
            "imports": [],
            "functions": 0,
            "classes": 0,
            "test_functions": 0,
        }

    imports = set()
    functions = 0
    classes = 0
    test_functions = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.add(str(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(str(node.module))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions += 1
            if str(node.name).startswith("test_"):
                test_functions += 1
        elif isinstance(node, ast.ClassDef):
            classes += 1
    return {
        "syntax_state": "OK",
        "imports": sorted(imports)[:120],
        "functions": functions,
        "classes": classes,
        "test_functions": test_functions,
    }


def scan_repository(
    root: str | os.PathLike[str],
    *,
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Scan structural repository metadata without executing or writing code."""
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError("repository root must be an existing directory")
    max_files = max(1, min(int(max_files), MAX_FILES))
    max_file_bytes = max(1, min(int(max_file_bytes), MAX_FILE_BYTES))

    rows: list[dict[str, Any]] = []
    skipped_sensitive = 0
    skipped_symlink = 0
    skipped_oversized = 0
    syntax_errors = 0
    truncated = False

    for current_root, dirs, files in os.walk(root_path, topdown=True, followlinks=False):
        current = Path(current_root)
        kept_dirs = []
        for raw_dir in sorted(dirs):
            candidate = current / raw_dir
            if candidate.is_symlink():
                skipped_symlink += 1
                continue
            if raw_dir in DENY_DIRS:
                continue
            if raw_dir.startswith(".") and raw_dir != ".github":
                continue
            kept_dirs.append(raw_dir)
        dirs[:] = kept_dirs

        for raw_name in sorted(files):
            if len(rows) >= max_files:
                truncated = True
                break
            candidate = current / raw_name
            if candidate.is_symlink():
                skipped_symlink += 1
                continue
            if _is_sensitive_name(raw_name):
                skipped_sensitive += 1
                continue

            try:
                resolved = candidate.resolve(strict=True)
                relative = resolved.relative_to(root_path).as_posix()
            except (OSError, ValueError):
                skipped_symlink += 1
                continue
            if any(part in DENY_DIRS for part in Path(relative).parts[:-1]):
                continue
            suffix = resolved.suffix.lower()
            if suffix not in SAFE_SUFFIXES:
                continue

            try:
                size = resolved.stat().st_size
            except OSError:
                continue
            if size > max_file_bytes:
                skipped_oversized += 1
                continue

            facts = {
                "syntax_state": "NOT_APPLICABLE",
                "imports": [],
                "functions": 0,
                "classes": 0,
                "test_functions": 0,
            }
            if suffix == ".py":
                try:
                    text = resolved.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
                facts = _python_facts(text)
                if facts["syntax_state"] == "ERROR":
                    syntax_errors += 1

            rows.append({
                "path": relative,
                "category": _category(relative),
                "suffix": suffix,
                "size_bytes": int(size),
                "risk_tags": _risk_tags(relative),
                **facts,
            })
        if truncated:
            break

    rows.sort(key=lambda item: str(item["path"]))
    category_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    for row in rows:
        category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1
        for tag in row["risk_tags"]:
            risk_counts[tag] = risk_counts.get(tag, 0) + 1

    digest_payload = [{
        "path": row["path"],
        "category": row["category"],
        "size_bytes": row["size_bytes"],
        "imports": row["imports"],
        "syntax_state": row["syntax_state"],
    } for row in rows]
    return {
        "schema": SCHEMA,
        "root_name": root_path.name,
        "snapshot_digest": "REPO-" + _digest(digest_payload, 24),
        "files": rows,
        "file_count": len(rows),
        "category_counts": dict(sorted(category_counts.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "syntax_errors": syntax_errors,
        "skipped_sensitive": skipped_sensitive,
        "skipped_symlink": skipped_symlink,
        "skipped_oversized": skipped_oversized,
        "truncated": truncated,
        "content_included": False,
        "executes_repository_code": False,
        "writes_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "real_trading_enabled": False,
    }


def build_test_coverage_map(
    snapshot: Mapping[str, Any],
    changed_paths: Sequence[Any] | None,
) -> dict[str, Any]:
    """Map changed files to likely tests using names and static imports only."""
    rows = [dict(row) for row in list(snapshot.get("files") or []) if isinstance(row, Mapping)]
    by_path = {str(row.get("path") or ""): row for row in rows}
    tests = [row for row in rows if row.get("category") == "TEST"]
    changes = []
    unmatched_code = []

    for raw in list(changed_paths or [])[:200]:
        path = _clean(raw, 400).replace("\\", "/")
        if not path or path in {row["path"] for row in changes}:
            continue
        source = by_path.get(path, {})
        category = str(source.get("category") or _category(path))
        suffix = Path(path).suffix.lower()
        matched = []

        if category == "TEST":
            matched = [path] if path in by_path else []
            state = "SELF_TEST"
        elif suffix == ".py":
            stem = Path(path).stem
            module_name = path[:-3].replace("/", ".")
            direct_names = {f"test_{stem}.py", f"{stem}_test.py"}
            for test in tests:
                test_path = str(test.get("path") or "")
                imports = {str(item) for item in list(test.get("imports") or [])}
                if (
                    Path(test_path).name in direct_names
                    or module_name in imports
                    or stem in imports
                ):
                    matched.append(test_path)
            matched = sorted(set(matched))
            state = "COVERED" if matched else "NO_MATCH"
            if not matched:
                unmatched_code.append(path)
        else:
            state = "NON_PYTHON"

        changes.append({
            "path": path,
            "category": category,
            "state": state,
            "matched_tests": matched[:50],
            "risk_tags": list(source.get("risk_tags") or _risk_tags(path)),
        })

    recommended_tests = sorted({
        test
        for item in changes
        for test in list(item.get("matched_tests") or [])
    })
    return {
        "schema": SCHEMA,
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "changes": changes,
        "changed_count": len(changes),
        "recommended_tests": recommended_tests,
        "unmatched_code": sorted(set(unmatched_code)),
        "coverage_is_proof": False,
        "writes_files": False,
        "executes_tests": False,
        "network_called": False,
    }


def build_development_plan(
    request: Any,
    snapshot: Mapping[str, Any],
    *,
    branch: Any,
    baseline_ref: Any,
    changed_paths: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Produce a bounded, non-executing plan compatible with Developer Engine phases."""
    request_text = _clean(request, 1200)
    branch_text = _clean(branch, 240)
    baseline = _clean(baseline_ref, 240)
    if not request_text or not branch_text or not baseline:
        raise ValueError("request, branch and baseline_ref are required")

    coverage = build_test_coverage_map(snapshot, changed_paths)
    impacted = [str(item.get("path") or "") for item in coverage["changes"]]
    risks = sorted({
        tag
        for item in coverage["changes"]
        for tag in list(item.get("risk_tags") or [])
    })
    warnings = []
    if coverage["unmatched_code"]:
        warnings.append("CHANGED_PYTHON_WITHOUT_LIKELY_TEST")
    if bool(snapshot.get("truncated")):
        warnings.append("REPOSITORY_SNAPSHOT_TRUNCATED")
    if int(snapshot.get("syntax_errors") or 0):
        warnings.append("SNAPSHOT_CONTAINS_PYTHON_SYNTAX_ERRORS")

    plan_seed = {
        "request": request_text,
        "branch": branch_text,
        "baseline_ref": baseline,
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "impacted": impacted,
    }
    return {
        "schema": PLAN_SCHEMA,
        "plan_id": "DEVPLAN-" + _digest(plan_seed, 16),
        "request": request_text,
        "branch": branch_text,
        "baseline_ref": baseline,
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "impacted_files": impacted,
        "risk_tags": risks,
        "recommended_tests": coverage["recommended_tests"],
        "unmatched_code": coverage["unmatched_code"],
        "warnings": warnings,
        "phases": list(PHASES),
        "developer_engine_seed": {
            "request": request_text,
            "branch": branch_text,
            "baseline_ref": baseline,
            "requested_by": "AION_ANALYSIS",
            "components": impacted,
            "dependencies": risks,
            "impact": "HIGH" if risks else "MEDIUM",
        },
        "analysis_only": True,
        "human_release_review_required": True,
        "automatic_edit": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "MAX_FILES",
    "MAX_FILE_BYTES",
    "SAFE_SUFFIXES",
    "scan_repository",
    "build_test_coverage_map",
    "build_development_plan",
]
