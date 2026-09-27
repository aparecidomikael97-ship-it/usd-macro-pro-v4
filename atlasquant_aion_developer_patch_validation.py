"""Read-only patch validation for the AION Developer chain.

Treats a unified Git diff as untrusted data and enumerates its effects against
an already-authorized Builder Sandbox Request and a passing declarative
Sandbox Preflight. It never applies a patch, edits files, runs tests/commands,
spawns processes, accesses the network, commits, merges, deploys or enables
production/trading authority.

Passing validation means only READY_FOR_PATCH_REVIEW. It is not permission to
write files or execute the patch.

``validation_id`` binds the upstream ids, ``patch_digest`` and the semantic
manifest of this document. That is structural consistency. It is not
independent source proof. ``patch_digest`` is not re-derived from the
original unified diff here, and the raw patch is not stored. An attacker who
rewrites the whole document, recomputes every id and fabricates another
coherent structural attestation still has only structural consistency.
Coherent reseal without the original patch bytes is an EXPECTED STRUCTURAL
LIMITATION. ``source_bound_proof_required_before_physical_execution`` stays
true: a future source-bound assertion must receive the raw patch, check
``patch_digest`` and compare ``parse_patch_semantics`` before any physical
execution.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import PurePosixPath
import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import (
    READY_STATE as BUILDER_READY_STATE,
    assert_builder_sandbox_request_integrity,
)
from atlasquant_aion_developer_manifest import normalize_ref, release_sensitive_path, stable_digest
from atlasquant_aion_developer_sandbox_preflight import (
    READY_STATE as PREFLIGHT_READY_STATE,
    assert_sandbox_preflight_integrity,
)
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PATCH_VALIDATION_V1"
READY_STATE = "READY_FOR_PATCH_REVIEW"
BLOCKED_STATE = "BLOCKED"
_TOTAL_BLOCKER = "TOTAL_CHANGE_BUDGET_EXCEEDED"
SOURCE_BOUND_PROOF_BLOCKER = "SOURCE_BOUND_PATCH_PROOF_REQUIRED_BEFORE_PHYSICAL_EXECUTION"
EXPECTED_STRUCTURAL_LIMITATION = (
    "COHERENT_RESEAL_WITHOUT_SOURCE_IS_STRUCTURAL_CONSISTENCY_NOT_INDEPENDENT_SOURCE_PROOF"
)
_FILE_BOOLS = (
    "mode_changed",
    "binary_patch",
    "header_duplicate",
    "header_missing",
    "header_path_mismatch",
    "header_out_of_order",
    "hunk_invalid",
    "path_changed",
    "additive_test_neutralization",
    "canonical_path_collision",
    "creates_file",
    "deletes_file",
    "renames_or_copies",
    "test_disable_marker",
)
_FILE_KEYS = frozenset({
    "path",
    "operation",
    "added_lines",
    "deleted_lines",
    "hunk_count",
    "secret_additions",
    "blockers",
}) | frozenset(_FILE_BOOLS)
_REVISION_KEYS = frozenset({
    "baseline_ref",
    "candidate_ref",
    "refs_match_approved_request",
    "revision_content_verified",
})
_FALSE_FLAGS = (
    "patch_applied",
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "tool_output_is_authority",
)
_CONTRACT_KEYS = frozenset({
    "schema",
    "validation_id",
    "state",
    "builder_request_id",
    "preflight_id",
    "patch_digest",
    "revision_binding",
    "files",
    "file_count",
    "patch_bytes",
    "patch_lines",
    "changed_lines",
    "secret_like_additions",
    "blockers",
    "patch_text_included",
    "content_binding_requires_external_verification",
    "human_patch_review_required",
    "source_bound_proof_required_before_physical_execution",
}) | frozenset(_FALSE_FLAGS)
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
    """Record header facts. Blockers are derived later from those facts."""
    section["header_duplicate"] = (
        int(section.get("minus_seen") or 0) > 1 or int(section.get("plus_seen") or 0) > 1
    )
    minus = section.get("minus_header")
    plus = section.get("plus_header")
    section["header_missing"] = not minus or not plus
    section["header_path_mismatch"] = False
    if minus and plus and section.get("operation") == "MODIFY":
        expected_minus = "a/" + str(section.get("old_path") or "")
        expected_plus = "b/" + str(section.get("path") or "")
        section["header_path_mismatch"] = minus != expected_minus or plus != expected_plus
    section["header_out_of_order"] = bool(section.get("header_order_error"))


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _exact_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be an exact bool")
    return value


def _exact_int(value: Any, label: str) -> int:
    """Reject bools and every negative counter. Cancellation cannot reach zero."""
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact int")
    if value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return value


def _false_file_facts() -> dict[str, bool]:
    return {name: False for name in _FILE_BOOLS}


def _paths_with_canonical_collision(paths: list[str]) -> set[str]:
    first: dict[str, str] = {}
    collided: set[str] = set()
    for path in paths:
        key = _canonical_path_key(path)
        prior = first.get(key)
        if prior is None:
            first[key] = path
        elif prior != path:
            collided.add(prior)
            collided.add(path)
    return collided


def _required_file_blockers(
    summary: Mapping[str, Any],
    requested: set[str],
    authorized: set[str],
    collided: set[str] | None = None,
) -> list[str]:
    """Re-derive every file blocker from summary facts, not from blocker names."""
    path = str(summary.get("path") or "")
    operation = summary.get("operation")
    facts = {name: _exact_bool(summary.get(name), name) for name in _FILE_BOOLS}
    creates = facts["creates_file"]
    deletes = facts["deletes_file"]
    renames = facts["renames_or_copies"]
    if operation == "CREATE":
        if not creates:
            raise ValueError("CREATE operation contradicts creates_file")
    elif operation == "DELETE":
        if not deletes:
            raise ValueError("DELETE operation contradicts deletes_file")
    elif operation == "RENAME_OR_COPY":
        if not renames:
            raise ValueError("RENAME_OR_COPY operation contradicts renames_or_copies")
    elif operation == "MODIFY":
        if creates or deletes or renames:
            raise ValueError("MODIFY operation contradicts file mutation facts")
    else:
        raise ValueError("patch operation is not allowlisted")
    collision = path in (collided or set())
    if facts["canonical_path_collision"] is not collision:
        raise ValueError("canonical path collision fact was not derived")
    added = _exact_int(summary.get("added_lines"), "added_lines")
    deleted = _exact_int(summary.get("deleted_lines"), "deleted_lines")
    secret = _exact_int(summary.get("secret_additions"), "secret_additions")
    hunk_count = _exact_int(summary.get("hunk_count"), "hunk_count")
    if secret > added:
        raise ValueError("secret_additions exceed added_lines")
    blockers: list[str] = []
    if creates:
        blockers.append("NEW_FILE_NOT_ALLOWED")
    if deletes:
        blockers.append("DELETE_FILE_NOT_ALLOWED")
    if renames:
        blockers.append("RENAME_OR_COPY_NOT_ALLOWED")
    if facts["path_changed"]:
        blockers.append("PATH_CHANGE_OR_RENAME_NOT_ALLOWED")
    if facts["mode_changed"]:
        blockers.append("FILE_MODE_CHANGE_NOT_ALLOWED")
    if facts["binary_patch"]:
        blockers.append("BINARY_PATCH_NOT_ALLOWED")
    if facts["header_duplicate"]:
        blockers.append("DIFF_HEADER_DUPLICATE")
    if facts["header_missing"]:
        blockers.append("DIFF_HEADER_MISSING")
    if facts["header_path_mismatch"]:
        blockers.append("DIFF_HEADER_PATH_MISMATCH")
    if facts["header_out_of_order"]:
        blockers.append("DIFF_HEADER_OUT_OF_ORDER")
    if facts["hunk_invalid"]:
        blockers.append("DIFF_HUNK_INVALID")
    if operation == "MODIFY" and hunk_count < 1:
        blockers.append("DIFF_HUNK_REQUIRED")
    if path not in requested or path not in authorized:
        blockers.append("PATCH_PATH_OUTSIDE_AUTHORIZED_SCOPE")
    if _is_secret_path(path):
        blockers.append("SECRET_OR_CREDENTIAL_PATH_NOT_ALLOWED")
    if release_sensitive_path(path):
        blockers.append("RELEASE_SURFACE_REQUIRES_SEPARATE_REVIEW")
    if _is_dependency_path(path):
        blockers.append("DEPENDENCY_CHANGE_REQUIRES_SEPARATE_REVIEW")
    if (_is_test_path(path) and deleted > 0) or facts["test_disable_marker"]:
        blockers.append("TEST_DELETION_OR_WEAKENING_NOT_ALLOWED")
    if facts["additive_test_neutralization"]:
        blockers.append("TEST_ADDITIVE_NEUTRALIZATION_REQUIRES_SEPARATE_REVIEW")
    if collision:
        blockers.append("CANONICAL_PATH_COLLISION")
    if secret > 0:
        blockers.append("SECRET_LIKE_ADDITION_NOT_ALLOWED")
    if added + deleted > MAX_CHANGED_LINES_PER_FILE:
        blockers.append("PER_FILE_CHANGE_BUDGET_EXCEEDED")
    return blockers


def _derived_patch_blockers(
    files: list[Mapping[str, Any]],
    requested: set[str],
    authorized: set[str],
    changed_lines: int,
) -> list[str]:
    collided = _paths_with_canonical_collision([str(summary.get("path") or "") for summary in files])
    ordered: list[str] = []
    for summary in files:
        for blocker in _required_file_blockers(summary, requested, authorized, collided):
            if blocker not in ordered:
                ordered.append(blocker)
    if changed_lines > MAX_CHANGED_LINES and _TOTAL_BLOCKER not in ordered:
        ordered.append(_TOTAL_BLOCKER)
    return ordered


def parse_patch_semantics(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
) -> dict[str, Any]:
    """Parse a unified diff into the canonical patch document.

    The raw patch is not stored. ``validation_id`` is the structural binding
    of upstream ids, ``patch_digest`` and the semantic manifest. It does not
    prove those semantics against the original diff bytes.
    """
    assert_builder_sandbox_request_integrity(builder_request)
    if builder_request.get("state") != BUILDER_READY_STATE:
        raise ValueError("builder request is not ready for patch validation")
    assert_sandbox_preflight_integrity(preflight, builder_request)
    if preflight.get("state") != PREFLIGHT_READY_STATE or preflight.get("preflight_passed") is not True:
        raise ValueError("sandbox preflight is not ready")

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
                "mode_changed": False,
                "binary_patch": False,
                "hunk_invalid": False,
                "path_changed": old_path != new_path,
                "additive_test_neutralization": False,
                "creates_file": False,
                "deletes_file": False,
                "renames_or_copies": False,
                "test_disable_marker": False,
            }
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
            current["creates_file"] = True
        elif line.startswith("deleted file mode "):
            current["operation"] = "DELETE"
            current["deletes_file"] = True
        elif line.startswith(("rename from ", "rename to ", "similarity index ", "copy from ", "copy to ")):
            current["operation"] = "RENAME_OR_COPY"
            current["renames_or_copies"] = True
        elif line.startswith(("old mode ", "new mode ")):
            current["mode_changed"] = True
        elif line.startswith("GIT binary patch") or lowered.startswith("binary files "):
            current["binary_patch"] = True
        elif line.startswith("--- "):
            header = _header_path(line)
            if current.get("hunk_count") or current.get("plus_header") is not None:
                current["header_order_error"] = True
            current["minus_seen"] = int(current.get("minus_seen") or 0) + 1
            current["minus_header"] = header
            if header == "/dev/null":
                current["operation"] = "CREATE"
                current["creates_file"] = True
        elif line.startswith("+++ "):
            header = _header_path(line)
            if current.get("hunk_count") or current.get("minus_header") is None:
                current["header_order_error"] = True
            current["plus_seen"] = int(current.get("plus_seen") or 0) + 1
            current["plus_header"] = header
            if header == "/dev/null":
                current["operation"] = "DELETE"
                current["deletes_file"] = True
        elif _HUNK_RE.match(line):
            if current.get("minus_header") is None or current.get("plus_header") is None:
                current["header_order_error"] = True
            current["hunk_count"] = int(current.get("hunk_count") or 0) + 1
        elif line.startswith("@@"):
            current["hunk_invalid"] = True
        elif line.startswith("+") and not line.startswith("+++"):
            current["added_lines"] += 1
            added = line[1:]
            if _line_has_secret(added):
                current["secret_additions"] += 1
            if _is_test_path(str(current["path"])):
                if _TEST_DISABLE_RE.search(added):
                    current["test_disable_marker"] = True
                definition = _TEST_DEF_RE.match(added)
                if definition:
                    # Without the baseline file this contract cannot prove an added
                    # test function is new rather than a shadow of an existing one.
                    current["additive_test_neutralization"] = True
                    name = definition.group(1)
                    current["added_test_names"].append(name)
                elif _TEST_NEUTRAL_RE.match(added):
                    current["additive_test_neutralization"] = True
        elif line.startswith("-") and not line.startswith("---"):
            current["deleted_lines"] += 1

    if current is not None:
        _finalize_patch_section(current)
    if not sections:
        raise ValueError("no unified diff file sections found")
    if len(sections) > MAX_PATCH_FILES:
        raise ValueError("patch exceeds file budget")

    summaries: list[dict[str, Any]] = []
    for section in sections:
        summaries.append({
            "path": str(section["path"]),
            "operation": str(section["operation"]),
            "added_lines": int(section["added_lines"]),
            "deleted_lines": int(section["deleted_lines"]),
            "hunk_count": int(section.get("hunk_count") or 0),
            "secret_additions": int(section["secret_additions"]),
            "mode_changed": bool(section["mode_changed"]),
            "binary_patch": bool(section["binary_patch"]),
            "header_duplicate": bool(section["header_duplicate"]),
            "header_missing": bool(section["header_missing"]),
            "header_path_mismatch": bool(section["header_path_mismatch"]),
            "header_out_of_order": bool(section["header_out_of_order"]),
            "hunk_invalid": bool(section["hunk_invalid"]),
            "path_changed": bool(section["path_changed"]),
            "additive_test_neutralization": bool(section["additive_test_neutralization"]),
            "canonical_path_collision": False,
            "creates_file": bool(section["creates_file"]),
            "deletes_file": bool(section["deletes_file"]),
            "renames_or_copies": bool(section["renames_or_copies"]),
            "test_disable_marker": bool(section["test_disable_marker"]),
            "blockers": [],
        })
    collided = _paths_with_canonical_collision([summary["path"] for summary in summaries])
    changed = 0
    secret_total = 0
    for summary in summaries:
        summary["canonical_path_collision"] = summary["path"] in collided
        summary["blockers"] = _required_file_blockers(summary, requested, authorized, collided)
        changed += summary["added_lines"] + summary["deleted_lines"]
        secret_total += summary["secret_additions"]
    global_blockers: list[str] = []
    for summary in summaries:
        for blocker in summary["blockers"]:
            if blocker not in global_blockers:
                global_blockers.append(blocker)
    if changed > MAX_CHANGED_LINES and _TOTAL_BLOCKER not in global_blockers:
        global_blockers.append(_TOTAL_BLOCKER)
    state = READY_STATE if not global_blockers else BLOCKED_STATE

    document = {
        "schema": SCHEMA,
        "validation_id": "",
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
        "changed_lines": changed,
        "secret_like_additions": secret_total,
        "blockers": global_blockers,
        "patch_text_included": False,
        "patch_applied": False,
        "content_binding_requires_external_verification": True,
        "human_patch_review_required": True,
        "source_bound_proof_required_before_physical_execution": True,
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
    document["validation_id"] = expected_patch_validation_id(document)
    return document


def validate_patch(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
) -> dict[str, Any]:
    """Validate a unified diff without applying or executing it."""
    document = parse_patch_semantics(
        builder_request,
        preflight,
        patch_text,
        baseline_ref=baseline_ref,
        candidate_ref=candidate_ref,
    )
    assert_patch_validation_integrity(document, builder_request, preflight)
    return document


def _revision_manifest(revision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "baseline_ref": revision.get("baseline_ref"),
        "candidate_ref": revision.get("candidate_ref"),
        "refs_match_approved_request": revision.get("refs_match_approved_request"),
        "revision_content_verified": revision.get("revision_content_verified"),
    }


def _file_manifest_entry(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {key: summary.get(key) for key in sorted(_FILE_KEYS)}


def patch_validation_manifest(patch_validation: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields of a patch document. ``validation_id`` is not an input."""
    if not isinstance(patch_validation, Mapping):
        raise ValueError("patch validation must be an object")
    revision = patch_validation.get("revision_binding")
    if not isinstance(revision, Mapping):
        raise ValueError("patch revision binding must be an object")
    files = patch_validation.get("files")
    if isinstance(files, (str, bytes, bytearray)) or not isinstance(files, list):
        raise ValueError("patch files must be a non-empty list")
    manifested_files = []
    for summary in files:
        if not isinstance(summary, Mapping):
            raise ValueError("patch file summary must be an object")
        manifested_files.append(_file_manifest_entry(summary))
    return {
        "state": patch_validation.get("state"),
        "blockers": list(patch_validation.get("blockers") or []),
        "builder_request_id": patch_validation.get("builder_request_id"),
        "preflight_id": patch_validation.get("preflight_id"),
        "patch_digest": patch_validation.get("patch_digest"),
        "revision_binding": _revision_manifest(revision),
        "files": manifested_files,
        "file_count": patch_validation.get("file_count"),
        "patch_bytes": patch_validation.get("patch_bytes"),
        "patch_lines": patch_validation.get("patch_lines"),
        "changed_lines": patch_validation.get("changed_lines"),
        "secret_like_additions": patch_validation.get("secret_like_additions"),
        "patch_text_included": patch_validation.get("patch_text_included"),
        "patch_applied": patch_validation.get("patch_applied"),
        "content_binding_requires_external_verification": patch_validation.get(
            "content_binding_requires_external_verification"
        ),
        "human_patch_review_required": patch_validation.get("human_patch_review_required"),
        "source_bound_proof_required_before_physical_execution": patch_validation.get(
            "source_bound_proof_required_before_physical_execution"
        ),
        "false_flags": {field: patch_validation.get(field) for field in _FALSE_FLAGS},
    }


def patch_validation_manifest_id(patch_validation: Mapping[str, Any]) -> str:
    """Digest the semantic manifest. This id is not a seed of ``validation_id`` alone."""
    return stable_digest(patch_validation_manifest(patch_validation), prefix="DEVPATCHMAN-", length=24)


def expected_patch_validation_id(patch_validation: Mapping[str, Any]) -> str:
    """Bind upstream ids, the patch digest and the semantic manifest.

    The stored ``validation_id`` is not an input. Recomputing this value after
    a semantic edit is structural consistency, not independent source proof.
    """
    seed = {
        "builder_request_id": patch_validation.get("builder_request_id"),
        "preflight_id": patch_validation.get("preflight_id"),
        "patch_digest": patch_validation.get("patch_digest"),
        "manifest_id": patch_validation_manifest_id(patch_validation),
    }
    return stable_digest(seed, prefix="DEVPATCHVAL-", length=24)


def assert_patch_validation_integrity(
    patch_validation: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> str:
    """Re-derive patch blockers from sealed facts and bind ``validation_id``.

    ``revision_content_verified`` stays false. A matching ``validation_id``
    proves the semantic manifest was not edited under the old id. It does not
    prove the original unified diff. Coherent reseal without those bytes is
    an EXPECTED STRUCTURAL LIMITATION (``EXPECTED_STRUCTURAL_LIMITATION``).
    ``SOURCE_BOUND_PROOF_BLOCKER`` stays required before any physical execution.
    """
    assert_builder_sandbox_request_integrity(builder_request)
    if builder_request.get("state") != BUILDER_READY_STATE:
        raise ValueError("builder request is not ready for patch validation")
    assert_sandbox_preflight_integrity(preflight, builder_request)
    if preflight.get("state") != PREFLIGHT_READY_STATE or preflight.get("preflight_passed") is not True:
        raise ValueError("sandbox preflight is not ready")
    if not isinstance(patch_validation, Mapping):
        raise ValueError("patch validation must be an object")
    if patch_validation.get("schema") != SCHEMA:
        raise ValueError("invalid Patch Validation")
    _reject_closed(patch_validation, _CONTRACT_KEYS, "patch validation")
    for field in _FALSE_FLAGS:
        if patch_validation.get(field) is not False:
            raise ValueError(f"patch validation cannot claim {field}")
    if patch_validation.get("patch_text_included") is not False:
        raise ValueError("patch text must stay outside the validation document")
    if patch_validation.get("content_binding_requires_external_verification") is not True:
        raise ValueError("patch content binding still requires external verification")
    if patch_validation.get("human_patch_review_required") is not True:
        raise ValueError("human patch review remains required")
    if patch_validation.get("source_bound_proof_required_before_physical_execution") is not True:
        raise ValueError(SOURCE_BOUND_PROOF_BLOCKER)
    if patch_validation.get("builder_request_id") != builder_request.get("request_id"):
        raise ValueError("patch validation request lineage mismatch")
    if patch_validation.get("preflight_id") != preflight.get("preflight_id"):
        raise ValueError("patch validation preflight lineage mismatch")
    revision = patch_validation.get("revision_binding")
    if not isinstance(revision, Mapping):
        raise ValueError("patch revision binding must be an object")
    _reject_closed(revision, _REVISION_KEYS, "patch revision binding")
    if revision.get("revision_content_verified") is not False:
        raise ValueError("patch revision content is not independently verified")
    if revision.get("refs_match_approved_request") is not True:
        raise ValueError("patch refs are not bound to approved request")
    branch = builder_request.get("branch_contract") if isinstance(builder_request.get("branch_contract"), Mapping) else {}
    if revision.get("baseline_ref") != branch.get("baseline_ref"):
        raise ValueError("patch baseline differs from builder request")
    if revision.get("candidate_ref") != branch.get("candidate_ref"):
        raise ValueError("patch candidate differs from builder request")
    files = patch_validation.get("files")
    if not isinstance(files, list) or isinstance(files, (str, bytes, bytearray)) or not files:
        raise ValueError("patch files must be a non-empty list")
    scope = builder_request.get("scope") if isinstance(builder_request.get("scope"), Mapping) else {}
    requested = set(require_patch_paths(scope.get("requested_files")))
    authorized = set(require_patch_paths(scope.get("authorized_files")))
    changed = 0
    secret_total = 0
    collided = _paths_with_canonical_collision([
        str(summary.get("path") or "") for summary in files if isinstance(summary, Mapping)
    ])
    for summary in files:
        if not isinstance(summary, Mapping):
            raise ValueError("patch file summary must be an object")
        _reject_closed(summary, _FILE_KEYS, "patch file summary")
        required = _required_file_blockers(summary, requested, authorized, collided)
        stored = summary.get("blockers")
        if not isinstance(stored, list) or stored != required:
            raise ValueError("patch file blockers were not derived from the file facts")
        changed += _exact_int(summary.get("added_lines"), "added_lines")
        changed += _exact_int(summary.get("deleted_lines"), "deleted_lines")
        secret_total += _exact_int(summary.get("secret_additions"), "secret_additions")
    if _exact_int(patch_validation.get("file_count"), "file_count") != len(files):
        raise ValueError("patch file_count was not derived")
    if _exact_int(patch_validation.get("changed_lines"), "changed_lines") != changed:
        raise ValueError("patch changed_lines were not derived")
    if _exact_int(patch_validation.get("secret_like_additions"), "secret_like_additions") != secret_total:
        raise ValueError("patch secret additions were not derived")
    if secret_total > changed:
        raise ValueError("secret_like_additions exceed changed_lines")
    patch_bytes = _exact_int(patch_validation.get("patch_bytes"), "patch_bytes")
    patch_lines = _exact_int(patch_validation.get("patch_lines"), "patch_lines")
    if patch_bytes < 1 or patch_bytes > MAX_PATCH_BYTES:
        raise ValueError("patch byte budget is not coherent")
    if patch_lines < 1 or patch_lines > MAX_PATCH_LINES:
        raise ValueError("patch line budget is not coherent")
    if len(files) > MAX_PATCH_FILES:
        raise ValueError("patch file budget is not coherent")
    derived = _derived_patch_blockers(files, requested, authorized, changed)
    blockers = patch_validation.get("blockers")
    if not isinstance(blockers, list) or blockers != derived:
        raise ValueError("patch blockers were not derived from the file summaries")
    state = patch_validation.get("state")
    if not derived:
        if state != READY_STATE:
            raise ValueError("ready patch state was not derived")
    elif state != BLOCKED_STATE:
        raise ValueError("blocked patch state was not derived")
    validation_id = patch_validation.get("validation_id")
    patch_digest = patch_validation.get("patch_digest")
    if not isinstance(validation_id, str) or not validation_id:
        raise ValueError("patch validation id is required")
    if not isinstance(patch_digest, str) or not patch_digest:
        raise ValueError("patch digest is required")
    if validation_id != expected_patch_validation_id(patch_validation):
        raise ValueError("patch validation id mismatch")
    return validation_id


def require_patch_paths(values: Any) -> list[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, (list, tuple)):
        raise ValueError("patch scope paths must be a list")
    return [str(item) for item in values]


def canonical_patch_document(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    *,
    patch_digest: str = "DEVPATCH-ABC",
) -> dict[str, Any]:
    """Seal one in-scope modification. Content verification stays false.

    This does not parse a diff and does not prove the patch bytes. ``patch_digest``
    is a caller label for the fixture, not a digest of an original diff.
    ``validation_id`` binds that label to the semantic manifest. The result is
    structural consistency, not independent source proof.
    """
    assert_sandbox_preflight_integrity(preflight, builder_request)
    if builder_request.get("state") != BUILDER_READY_STATE:
        raise ValueError("builder request is not ready for patch validation")
    if preflight.get("state") != PREFLIGHT_READY_STATE:
        raise ValueError("sandbox preflight is not ready")
    scope = builder_request.get("scope") if isinstance(builder_request.get("scope"), Mapping) else {}
    requested = require_patch_paths(scope.get("requested_files"))
    authorized = set(require_patch_paths(scope.get("authorized_files")))
    path = requested[0]
    deleted = 0 if _is_test_path(path) else 1
    branch = builder_request.get("branch_contract") if isinstance(builder_request.get("branch_contract"), Mapping) else {}
    summary = {
        "path": path,
        "operation": "MODIFY",
        "added_lines": 1,
        "deleted_lines": deleted,
        "hunk_count": 1,
        "secret_additions": 0,
        **_false_file_facts(),
        "blockers": [],
    }
    summary["blockers"] = _required_file_blockers(summary, set(requested), authorized, set())
    changed = 1 + deleted
    blockers = _derived_patch_blockers([summary], set(requested), authorized, changed)
    document = {
        "schema": SCHEMA,
        "validation_id": "",
        "state": READY_STATE if not blockers else BLOCKED_STATE,
        "builder_request_id": builder_request.get("request_id"),
        "preflight_id": preflight.get("preflight_id"),
        "patch_digest": patch_digest,
        "revision_binding": {
            "baseline_ref": branch.get("baseline_ref"),
            "candidate_ref": branch.get("candidate_ref"),
            "refs_match_approved_request": True,
            "revision_content_verified": False,
        },
        "files": [summary],
        "file_count": 1,
        "patch_bytes": 128,
        "patch_lines": 8,
        "changed_lines": changed,
        "secret_like_additions": 0,
        "blockers": blockers,
        "patch_text_included": False,
        "content_binding_requires_external_verification": True,
        "human_patch_review_required": True,
        "source_bound_proof_required_before_physical_execution": True,
        **{field: False for field in _FALSE_FLAGS},
    }
    document["validation_id"] = expected_patch_validation_id(document)
    assert_patch_validation_integrity(document, builder_request, preflight)
    return document


__all__ = [
    "SCHEMA",
    "MAX_PATCH_BYTES",
    "MAX_PATCH_FILES",
    "MAX_PATCH_LINES",
    "MAX_CHANGED_LINES",
    "READY_STATE",
    "MAX_CHANGED_LINES_PER_FILE",
    "SOURCE_BOUND_PROOF_BLOCKER",
    "EXPECTED_STRUCTURAL_LIMITATION",
    "parse_patch_semantics",
    "patch_validation_manifest",
    "patch_validation_manifest_id",
    "expected_patch_validation_id",
    "validate_patch",
    "assert_patch_validation_integrity",
    "canonical_patch_document",
]
