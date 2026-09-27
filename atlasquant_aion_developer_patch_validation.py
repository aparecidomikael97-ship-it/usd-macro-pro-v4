"""Read-only patch validation for the AION Developer chain.

Treats a unified Git diff as untrusted data and enumerates its effects against
an already-authorized Builder Sandbox Request and a passing declarative
Sandbox Preflight. It never applies a patch, edits files, runs tests/commands,
spawns processes, accesses the network, commits, merges, deploys or enables
production/trading authority.

Passing validation means only READY_FOR_PATCH_REVIEW. It is not permission to
write files or execute the patch.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import SCHEMA as BUILDER_REQUEST_SCHEMA
from atlasquant_aion_developer_manifest import normalize_ref, release_sensitive_path
from atlasquant_aion_developer_sandbox_preflight import SCHEMA as PREFLIGHT_SCHEMA
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1"
MAX_PATCH_BYTES = 500_000
MAX_PATCH_FILES = 20
MAX_PATCH_LINES = 5_000
MAX_CHANGED_LINES = 2_000
MAX_CHANGED_LINES_PER_FILE = 1_000

_DIFF_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:password|passwd|token|api[_ -]?key|secret|authorization|senha|chave[_ -]?de[_ -]?api)\s*[:=]"),
    re.compile(r"(?i)https?://[^\s/:@]+:[^\s/@]+@"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*(?:PRIVATE KEY|SECRET)[A-Z0-9 ]*-----"),
)
_DEPENDENCY_FILES = frozenset({
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock",
    "pdm.lock", "uv.lock", "pipfile", "pipfile.lock", "package.json",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
})
_SECRET_PATH_PARTS = frozenset({
    ".env", "secrets.toml", "credentials", "credential", "private_key",
    "private-key", "id_rsa", "id_ed25519",
})
_TEST_DISABLE_RE = re.compile(
    r"(?i)("
    r"unittest\.skip|"
    r"unittest\.expectedfailure|"
    r"pytest\.mark\.skip|"
    r"pytest\.mark\.xfail|"
    r"pytest\.skip\s*\(|"
    r"\.skiptest\s*\(|"
    r"\bexpectedfailure\b|"
    r"\bxfail\b"
    r")"
)
_TEST_DEF_RE = re.compile(r"(?i)^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]*)\b")
_TEST_NEUTRAL_RE = re.compile(r"(?i)^\s*(?:pass|return)\b")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _patch_digest(raw: str) -> str:
    return "DEVPATCH-" + sha256(raw.encode("utf-8")).hexdigest()[:24].upper()


def _canonical_path_key(path: str) -> str:
    return unicodedata.normalize("NFKC", path).casefold()


def _safe_relative_path(value: Any) -> str:
    raw = unicodedata.normalize("NFKC", str(value or "").replace("\\", "/"))
    if not raw or raw.startswith("/") or raw.startswith("~") or "\x00" in raw:
        raise ValueError("unsafe patch path")
    if raw.startswith("./"):
        raw = raw[2:]
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("unsafe patch path")
    if ":" in path.parts[0] or raw.startswith("../"):
        raise ValueError("unsafe patch path")
    return raw


def _is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return name.startswith("test_") or "/tests/" in f"/{path.lower()}/"


def _is_dependency_path(path: str) -> bool:
    return path.rsplit("/", 1)[-1].lower() in _DEPENDENCY_FILES


def _is_secret_path(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    parts = {part for part in lowered.split("/") if part}
    return bool(parts & _SECRET_PATH_PARTS) or lowered.endswith(".pem") or lowered.endswith(".key")


def _line_has_secret(line: str) -> bool:
    """Scan the entire accepted line. A prefix window must not hide a secret."""
    return any(pattern.search(line) for pattern in _SECRET_PATTERNS)


def _header_path(line: str) -> str:
    return line[4:].split("\t", 1)[0]


def _finalize_patch_section(section: dict[str, Any]) -> None:
    if int(section.get("minus_seen") or 0) > 1 or int(section.get("plus_seen") or 0) > 1:
        section["blockers"].append("DIFF_HEADER_DUPLICATE")
    minus = section.get("minus_header")
    plus = section.get("plus_header")
    if not minus or not plus:
        section["blockers"].append("DIFF_HEADER_MISSING")
    elif section.get("operation") == "MODIFY":
        expected_minus = "a/" + str(section.get("old_path") or "")
        expected_plus = "b/" + str(section.get("path") or "")
        if minus != expected_minus or plus != expected_plus:
            section["blockers"].append("DIFF_HEADER_PATH_MISMATCH")
        if int(section.get("hunk_count") or 0) < 1:
            section["blockers"].append("DIFF_HUNK_REQUIRED")
    if section.get("header_order_error"):
        section["blockers"].append("DIFF_HEADER_OUT_OF_ORDER")


def validate_patch(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
) -> dict[str, Any]:
    """Validate a unified diff without applying or executing it."""
    if builder_request.get("schema") != BUILDER_REQUEST_SCHEMA:
        raise ValueError("invalid Builder Sandbox Request")
    if str(builder_request.get("state") or "") != "READY_FOR_BUILDER_SANDBOX":
        raise ValueError("builder request is not ready for patch validation")
    if list(builder_request.get("blockers") or []):
        raise ValueError("builder request has blockers")
    if builder_request.get("execution_authorized") is not False:
        raise ValueError("builder request unexpectedly authorizes execution")
    if builder_request.get("executor_attached") is not False:
        raise ValueError("builder request unexpectedly has executor attached")

    if preflight.get("schema") != PREFLIGHT_SCHEMA:
        raise ValueError("invalid Sandbox Preflight")
    if str(preflight.get("state") or "") != "READY_FOR_EXECUTOR_DESIGN_REVIEW":
        raise ValueError("sandbox preflight is not ready")
    if preflight.get("preflight_passed") is not True:
        raise ValueError("sandbox preflight did not pass")
    if preflight.get("execution_authorized") is not False:
        raise ValueError("sandbox preflight unexpectedly authorizes execution")
    if preflight.get("executor_attached") is not False:
        raise ValueError("sandbox preflight unexpectedly has executor")
    if str(preflight.get("builder_request_id") or "") != str(builder_request.get("request_id") or ""):
        raise ValueError("preflight and builder request lineage mismatch")

    branch_contract = (
        builder_request.get("branch_contract")
        if isinstance(builder_request.get("branch_contract"), Mapping)
        else {}
    )
    expected_baseline = normalize_ref(branch_contract.get("baseline_ref"), 240)
    expected_candidate = normalize_ref(branch_contract.get("candidate_ref"), 240)
    baseline = normalize_ref(baseline_ref, 240)
    candidate = normalize_ref(candidate_ref, 240)
    if baseline != expected_baseline or candidate != expected_candidate:
        raise ValueError("patch revision refs differ from approved builder request")

    scope = (
        builder_request.get("scope")
        if isinstance(builder_request.get("scope"), Mapping)
        else {}
    )
    requested = {str(x) for x in list(scope.get("requested_files") or []) if str(x)}
    authorized = {str(x) for x in list(scope.get("authorized_files") or []) if str(x)}
    if not requested or not requested.issubset(authorized):
        raise ValueError("invalid builder request scope")

    raw = str(patch_text or "")
    patch_bytes = len(raw.encode("utf-8"))
    if not raw.strip():
        raise ValueError("patch text required")
    if "\x00" in raw:
        raise ValueError("binary or NUL patch input is not supported")
    if patch_bytes > MAX_PATCH_BYTES:
        raise ValueError("patch exceeds byte budget")

    lines = raw.splitlines()
    if len(lines) > MAX_PATCH_LINES:
        raise ValueError("patch exceeds line budget")

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    global_blockers: list[str] = []
    added_secret_count = 0

    for line in lines:
        match = _DIFF_RE.match(line)
        if match:
            old_raw, new_raw = match.group(1), match.group(2)
            if any(value.startswith('"') or value.endswith('"') for value in (old_raw, new_raw)):
                raise ValueError("quoted git paths are not supported by patch validator v1")
            old_path = _safe_relative_path(old_raw)
            new_path = _safe_relative_path(new_raw)
            if current is not None:
                _finalize_patch_section(current)
            current = {
                "old_path": old_path,
                "path": new_path,
                "operation": "MODIFY",
                "added_lines": 0,
                "deleted_lines": 0,
                "secret_additions": 0,
                "hunk_count": 0,
                "minus_seen": 0,
                "plus_seen": 0,
                "minus_header": None,
                "plus_header": None,
                "header_order_error": False,
                "added_test_names": [],
                "blockers": [],
            }
            if old_path != new_path:
                current["blockers"].append("PATH_CHANGE_OR_RENAME_NOT_ALLOWED")
            sections.append(current)
            continue

        if current is None:
            if line.strip() and not line.startswith(("index ", "--- ", "+++ ", "@@")):
                # Metadata/preamble is ignored only until the first file section.
                continue
            continue

        lowered = line.lower()
        if line.startswith("new file mode "):
            current["operation"] = "CREATE"
            current["blockers"].append("NEW_FILE_NOT_ALLOWED")
        elif line.startswith("deleted file mode "):
            current["operation"] = "DELETE"
            current["blockers"].append("DELETE_FILE_NOT_ALLOWED")
        elif line.startswith(("rename from ", "rename to ", "similarity index ", "copy from ", "copy to ")):
            current["operation"] = "RENAME_OR_COPY"
            current["blockers"].append("RENAME_OR_COPY_NOT_ALLOWED")
        elif line.startswith(("old mode ", "new mode ")):
            current["blockers"].append("FILE_MODE_CHANGE_NOT_ALLOWED")
        elif line.startswith("GIT binary patch") or lowered.startswith("binary files "):
            current["blockers"].append("BINARY_PATCH_NOT_ALLOWED")
        elif line.startswith("--- "):
            header = _header_path(line)
            if current.get("hunk_count") or current.get("plus_header") is not None:
                current["header_order_error"] = True
            current["minus_seen"] = int(current.get("minus_seen") or 0) + 1
            current["minus_header"] = header
            if header == "/dev/null":
                current["operation"] = "CREATE"
                current["blockers"].append("NEW_FILE_NOT_ALLOWED")
        elif line.startswith("+++ "):
            header = _header_path(line)
            if current.get("hunk_count") or current.get("minus_header") is None:
                current["header_order_error"] = True
            current["plus_seen"] = int(current.get("plus_seen") or 0) + 1
            current["plus_header"] = header
            if header == "/dev/null":
                current["operation"] = "DELETE"
                current["blockers"].append("DELETE_FILE_NOT_ALLOWED")
        elif _HUNK_RE.match(line):
            if current.get("minus_header") is None or current.get("plus_header") is None:
                current["header_order_error"] = True
            current["hunk_count"] = int(current.get("hunk_count") or 0) + 1
        elif line.startswith("@@"):
            current["blockers"].append("DIFF_HUNK_INVALID")
        elif line.startswith("+") and not line.startswith("+++"):
            current["added_lines"] += 1
            added = line[1:]
            if _line_has_secret(added):
                current["secret_additions"] += 1
                added_secret_count += 1
            if _is_test_path(str(current["path"])):
                if _TEST_DISABLE_RE.search(added):
                    current["blockers"].append("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED")
                definition = _TEST_DEF_RE.match(added)
                if definition:
                    # Without the baseline file this contract cannot prove an added
                    # test function is new rather than a shadow of an existing one.
                    current["blockers"].append(
                        "TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW"
                    )
                    name = definition.group(1)
                    if name in current["added_test_names"]:
                        current["blockers"].append(
                            "TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW"
                        )
                    current["added_test_names"].append(name)
                elif _TEST_NEUTRAL_RE.match(added):
                    current["blockers"].append(
                        "TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW"
                    )
        elif line.startswith("-") and not line.startswith("---"):
            current["deleted_lines"] += 1

    if current is not None:
        _finalize_patch_section(current)
    if not sections:
        raise ValueError("no unified diff file sections found")
    if len(sections) > MAX_PATCH_FILES:
        raise ValueError("patch exceeds file budget")

    path_keys: dict[str, str] = {}
    total_changed = 0
    summaries: list[dict[str, Any]] = []
    for section in sections:
        path = str(section["path"])
        key = _canonical_path_key(path)
        if key in path_keys and path_keys[key] != path:
            section["blockers"].append("CANONICAL_PATH_COLLISION")
        path_keys.setdefault(key, path)

        if path not in requested or path not in authorized:
            section["blockers"].append("PATCH_PATH_OUTSIDE_AUTHORIZED_SCOPE")
        if _is_secret_path(path):
            section["blockers"].append("SECRET_OR_CREDENTIAL_PATH_NOT_ALLOWED")
        if release_sensitive_path(path):
            section["blockers"].append("RELEASE_SURFACE_REQUIRES_SEPARATE_REVIEW")
        if _is_dependency_path(path):
            section["blockers"].append("DEPENDENCY_CHANGE_REQUIRES_SEPARATE_REVIEW")
        if _is_test_path(path) and int(section["deleted_lines"]) > 0:
            section["blockers"].append("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED")
        if int(section["secret_additions"]) > 0:
            section["blockers"].append("SECRET_LIKE_ADDITION_NOT_ALLOWED")

        changed = int(section["added_lines"]) + int(section["deleted_lines"])
        total_changed += changed
        if changed > MAX_CHANGED_LINES_PER_FILE:
            section["blockers"].append("PER_FILE_CHANGE_BUDGET_EXCEEDED")

        blockers = list(dict.fromkeys(str(x) for x in section["blockers"]))
        global_blockers.extend(blockers)
        summaries.append({
            "path": path,
            "operation": str(section["operation"]),
            "added_lines": int(section["added_lines"]),
            "deleted_lines": int(section["deleted_lines"]),
            "hunk_count": int(section.get("hunk_count") or 0),
            "secret_additions": int(section["secret_additions"]),
            "blockers": blockers,
        })

    if total_changed > MAX_CHANGED_LINES:
        global_blockers.append("TOTAL_CHANGE_BUDGET_EXCEEDED")
    global_blockers = list(dict.fromkeys(global_blockers))
    state = "READY_FOR_PATCH_REVIEW" if not global_blockers else "BLOCKED"

    return {
        "schema": SCHEMA,
        "validation_id": _patch_digest(
            f"{builder_request.get('request_id')}|{preflight.get('preflight_id')}|{raw}"
        ),
        "state": state,
        "builder_request_id": str(builder_request.get("request_id") or ""),
        "preflight_id": str(preflight.get("preflight_id") or ""),
        "patch_digest": _patch_digest(raw),
        "revision_binding": {
            "baseline_ref": baseline,
            "candidate_ref": candidate,
            "refs_match_approved_request": True,
            "revision_content_verified": False,
        },
        "files": summaries,
        "file_count": len(summaries),
        "patch_bytes": patch_bytes,
        "patch_lines": len(lines),
        "changed_lines": total_changed,
        "secret_like_additions": added_secret_count,
        "blockers": global_blockers,
        "patch_text_included": False,
        "patch_applied": False,
        "content_binding_requires_external_verification": True,
        "human_patch_review_required": True,
        "execution_authorized": False,
        "executor_attached": False,
        "commands_executed": False,
        "writes_files": False,
        "runs_tests": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "symlink_physical_boundary_verified": False,
        "hardlink_physical_boundary_verified": False,
        "tool_output_is_authority": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_PATCH_BYTES",
    "MAX_PATCH_FILES",
    "MAX_PATCH_LINES",
    "MAX_CHANGED_LINES",
    "MAX_CHANGED_LINES_PER_FILE",
    "validate_patch",
]
