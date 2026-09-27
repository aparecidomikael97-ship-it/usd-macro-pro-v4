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
    sample = line[:4000]
    return any(pattern.search(sample) for pattern in _SECRET_PATTERNS)


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
            current = {
                "old_path": old_path,
                "path": new_path,
                "operation": "MODIFY",
                "added_lines": 0,
                "deleted_lines": 0,
                "secret_additions": 0,
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
        elif line.startswith("--- ") and line.endswith("/dev/null"):
            current["operation"] = "CREATE"
            current["blockers"].append("NEW_FILE_NOT_ALLOWED")
        elif line.startswith("+++ ") and line.endswith("/dev/null"):
            current["operation"] = "DELETE"
            current["blockers"].append("DELETE_FILE_NOT_ALLOWED")
        elif line.startswith("+") and not line.startswith("+++"):
            current["added_lines"] += 1
            if _line_has_secret(line[1:]):
                current["secret_additions"] += 1
                added_secret_count += 1
            if _is_test_path(str(current["path"])) and _TEST_DISABLE_RE.search(line[1:]):
                current["blockers"].append("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED")
        elif line.startswith("-") and not line.startswith("---"):
            current["deleted_lines"] += 1

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
