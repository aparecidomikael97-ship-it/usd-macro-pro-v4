"""AION Windows Build Input Snapshot + Offline Dependency Cache Attestation V1.

Non-downloading, non-building contract that freezes the exact inputs required by
the Windows local-agent reproducible-build environment.

The cache itself is future physical host state. This module validates supplied
snapshot/cache evidence and never downloads packages, resolves dependencies,
installs wheels, invokes a compiler, calls GitHub, or mutates a repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_windows_local_agent_reproducible_build_contract_v1 import (
    LOCK_SCHEMA,
    PYTHON_VERSION,
    PIP_VERSION,
    CRYPTOGRAPHY_VERSION,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_INPUT_OFFLINE_CACHE_ATTESTATION_V1"
SNAPSHOT_SCHEMA = "ATLASQUANT_AION_WINDOWS_BUILD_INPUT_SNAPSHOT_V1"
CACHE_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_DEPENDENCY_CACHE_V1"
PROMOTION_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_INPUT_PROMOTION_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_DEPENDENCY_CACHE_POLICY_V1"

TARGET_PLATFORM = "WINDOWS"
TARGET_ARCH = "X86_64"
CFFI_VERSION = "2.1.1"
PYCPARSER_VERSION = "3.1"
CACHE_MODE = "READ_ONLY_AFTER_ATTESTATION"
CACHE_NETWORK_POLICY = "NO_NETWORK"
CACHE_INSTALL_POLICY = "NO_INSTALL_DURING_ATTESTATION"

EXPECTED_INPUTS = {
    "PYTHON_RUNTIME": {
        "project_name": "python",
        "version": PYTHON_VERSION,
        "artifact_kind": "RUNTIME_ZIP",
        "filename_pattern": r"^python-3\.12\.12-embed-amd64\.zip$",
        "compatibility": "CPYTHON_312_WINDOWS_AMD64_EMBED",
        "dependencies": (),
    },
    "PIP_WHEEL": {
        "project_name": "pip",
        "version": PIP_VERSION,
        "artifact_kind": "WHEEL",
        "filename_pattern": r"^pip-26\.2\.1-py3-none-any\.whl$",
        "compatibility": "PY3_NONE_ANY",
        "dependencies": (),
    },
    "CRYPTOGRAPHY_WHEEL": {
        "project_name": "cryptography",
        "version": CRYPTOGRAPHY_VERSION,
        "artifact_kind": "WHEEL",
        "filename_pattern":
            r"^cryptography-50\.0\.2-cp3[0-9]+-abi3-win_amd64\.whl$",
        "compatibility": "ABI3_WIN_AMD64_COMPATIBLE_WITH_CPYTHON_312",
        "dependencies": ("CFFI_WHEEL",),
    },
    "CFFI_WHEEL": {
        "project_name": "cffi",
        "version": CFFI_VERSION,
        "artifact_kind": "WHEEL",
        "filename_pattern": r"^cffi-2\.1\.1-cp312-cp312-win_amd64\.whl$",
        "compatibility": "CP312_CP312_WIN_AMD64",
        "dependencies": ("PYCPARSER_WHEEL",),
    },
    "PYCPARSER_WHEEL": {
        "project_name": "pycparser",
        "version": PYCPARSER_VERSION,
        "artifact_kind": "WHEEL",
        "filename_pattern": r"^pycparser-3\.1-py3-none-any\.whl$",
        "compatibility": "PY3_NONE_ANY",
        "dependencies": (),
    },
}
EXPECTED_ROLES = tuple(EXPECTED_INPUTS)
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_CACHE_BYTES = 768 * 1024 * 1024

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{2,239}$")


class OfflineCacheError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise OfflineCacheError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise OfflineCacheError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _normalize_filename(value: Any) -> str:
    filename = str(value or "")
    if (
        not filename
        or filename != filename.strip()
        or "/" in filename
        or "\\" in filename
        or ":" in filename
        or ".." in filename
        or not _SAFE_FILENAME_RE.fullmatch(filename)
    ):
        raise OfflineCacheError("CACHE_ARTIFACT_FILENAME_INVALID")
    return filename


def _normalize_artifact(raw: Mapping[str, Any]) -> dict[str, Any]:
    role = _clean(raw.get("role"), 100).upper()
    expected = EXPECTED_INPUTS.get(role)
    if expected is None:
        raise OfflineCacheError("CACHE_ARTIFACT_ROLE_INVALID")

    project = _clean(raw.get("project_name"), 100).casefold()
    version = _clean(raw.get("version"), 80)
    kind = _clean(raw.get("artifact_kind"), 40).upper()
    filename = _normalize_filename(raw.get("filename"))
    expected_digest = _sha256(raw.get("expected_sha256"))
    observed_digest = _sha256(raw.get("observed_sha256"))
    source_metadata_digest = _sha256(raw.get("source_metadata_digest"))
    acquisition_receipt_digest = _sha256(raw.get("acquisition_receipt_digest"))
    package_metadata_digest = _sha256(raw.get("package_metadata_digest"))

    if project != expected["project_name"]:
        raise OfflineCacheError("CACHE_PROJECT_NAME_MISMATCH:" + role)
    if version != expected["version"]:
        raise OfflineCacheError("CACHE_ARTIFACT_VERSION_MISMATCH:" + role)
    if kind != expected["artifact_kind"]:
        raise OfflineCacheError("CACHE_ARTIFACT_KIND_MISMATCH:" + role)
    if not re.fullmatch(expected["filename_pattern"], filename):
        raise OfflineCacheError("CACHE_ARTIFACT_FILENAME_MISMATCH:" + role)
    if not expected_digest:
        raise OfflineCacheError("CACHE_EXPECTED_SHA256_REQUIRED:" + role)
    if not observed_digest:
        raise OfflineCacheError("CACHE_OBSERVED_SHA256_REQUIRED:" + role)
    if observed_digest != expected_digest:
        raise OfflineCacheError("CACHE_ARTIFACT_HASH_MISMATCH:" + role)
    if not source_metadata_digest:
        raise OfflineCacheError("SOURCE_METADATA_DIGEST_REQUIRED:" + role)
    if not acquisition_receipt_digest:
        raise OfflineCacheError("ACQUISITION_RECEIPT_DIGEST_REQUIRED:" + role)
    if not package_metadata_digest:
        raise OfflineCacheError("PACKAGE_METADATA_DIGEST_REQUIRED:" + role)

    try:
        size = int(raw.get("size_bytes"))
    except Exception as exc:
        raise OfflineCacheError("CACHE_ARTIFACT_SIZE_INVALID:" + role) from exc
    if size <= 0 or size > MAX_ARTIFACT_BYTES:
        raise OfflineCacheError("CACHE_ARTIFACT_SIZE_INVALID:" + role)

    if raw.get("download_transport_verified") is not True:
        raise OfflineCacheError("ACQUISITION_TRANSPORT_VERIFICATION_REQUIRED:" + role)
    if raw.get("trusted_source_snapshot_verified") is not True:
        raise OfflineCacheError("TRUSTED_SOURCE_SNAPSHOT_REQUIRED:" + role)
    if raw.get("compiled_from_source") is True:
        raise OfflineCacheError("BUILD_FROM_SOURCE_FORBIDDEN:" + role)
    if raw.get("sdist") is True:
        raise OfflineCacheError("SDIST_FORBIDDEN:" + role)
    if raw.get("contains_credentials") is True:
        raise OfflineCacheError("CACHE_CREDENTIAL_MATERIAL_FORBIDDEN:" + role)
    if raw.get("contains_private_keys") is True:
        raise OfflineCacheError("CACHE_PRIVATE_KEY_MATERIAL_FORBIDDEN:" + role)

    return {
        "role": role,
        "project_name": project,
        "version": version,
        "artifact_kind": kind,
        "filename": filename,
        "expected_sha256": expected_digest,
        "observed_sha256": observed_digest,
        "size_bytes": size,
        "compatibility": expected["compatibility"],
        "dependencies": list(expected["dependencies"]),
        "source_metadata_digest": source_metadata_digest,
        "package_metadata_digest": package_metadata_digest,
        "acquisition_receipt_digest": acquisition_receipt_digest,
        "download_transport_verified": True,
        "trusted_source_snapshot_verified": True,
        "compiled_from_source": False,
        "sdist": False,
        "contains_credentials": False,
        "contains_private_keys": False,
    }


def build_input_snapshot(
    dependency_lock: Mapping[str, Any] | None,
    artifacts: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_python_release_snapshot_digest: Any,
    trusted_python_package_index_snapshot_digest: Any,
    resolver_evidence_digest: Any,
    acquisition_environment_digest: Any,
    snapshot_created_at: Any,
) -> dict[str, Any]:
    """Freeze a closed dependency graph from already-acquired artifact evidence."""
    lock = dict(dependency_lock or {})
    blockers: list[str] = []

    if lock.get("schema") != LOCK_SCHEMA:
        blockers.append("DEPENDENCY_LOCK_SCHEMA_MISMATCH")
    if lock.get("state") != "BUILD_DEPENDENCY_LOCK_READY":
        blockers.append("READY_DEPENDENCY_LOCK_REQUIRED")

    lock_digest = _sha256(lock.get("dependency_lock_digest"))
    if not lock_digest:
        blockers.append("DEPENDENCY_LOCK_DIGEST_REQUIRED")

    lock_versions = {
        str(row.get("name")): str(row.get("version"))
        for row in lock.get("dependencies", [])
        if isinstance(row, Mapping)
    }
    if lock_versions.get("pip") != PIP_VERSION:
        blockers.append("PIP_LOCK_VERSION_MISMATCH")
    if lock_versions.get("cryptography") != CRYPTOGRAPHY_VERSION:
        blockers.append("CRYPTOGRAPHY_LOCK_VERSION_MISMATCH")

    global_digests = {}
    for key, value, label in (
        (
            "trusted_python_release_snapshot_digest",
            trusted_python_release_snapshot_digest,
            "PYTHON_RELEASE_SNAPSHOT_DIGEST_REQUIRED",
        ),
        (
            "trusted_python_package_index_snapshot_digest",
            trusted_python_package_index_snapshot_digest,
            "PACKAGE_INDEX_SNAPSHOT_DIGEST_REQUIRED",
        ),
        (
            "resolver_evidence_digest",
            resolver_evidence_digest,
            "RESOLVER_EVIDENCE_DIGEST_REQUIRED",
        ),
        (
            "acquisition_environment_digest",
            acquisition_environment_digest,
            "ACQUISITION_ENVIRONMENT_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        global_digests[key] = digest
        if not digest:
            blockers.append(label)

    try:
        created = _aware(snapshot_created_at, "INPUT_SNAPSHOT_CREATED_AT")
    except OfflineCacheError as exc:
        created = None
        blockers.append(exc.code)

    raw_rows = list(artifacts or [])
    if len(raw_rows) != len(EXPECTED_ROLES):
        blockers.append("EXACT_CACHE_ARTIFACT_COUNT_REQUIRED")

    normalized: list[dict[str, Any]] = []
    for raw in raw_rows:
        try:
            if not isinstance(raw, Mapping):
                raise OfflineCacheError("CACHE_ARTIFACT_INVALID")
            normalized.append(_normalize_artifact(raw))
        except OfflineCacheError as exc:
            blockers.append(exc.code)

    roles = [row["role"] for row in normalized]
    filenames = [row["filename"].casefold() for row in normalized]
    if len(set(roles)) != len(roles):
        blockers.append("DUPLICATE_CACHE_ARTIFACT_ROLE")
    if len(set(filenames)) != len(filenames):
        blockers.append("DUPLICATE_CACHE_ARTIFACT_FILENAME")
    if set(roles) != set(EXPECTED_ROLES):
        blockers.append("CACHE_ARTIFACT_ROLE_SET_MISMATCH")

    total = sum(row["size_bytes"] for row in normalized)
    if total <= 0 or total > MAX_CACHE_BYTES:
        blockers.append("CACHE_TOTAL_SIZE_INVALID")

    # Closed graph: every dependency edge must target a present exact role.
    role_set = set(roles)
    for row in normalized:
        for dependency in row["dependencies"]:
            if dependency not in role_set:
                blockers.append(
                    "TRANSITIVE_DEPENDENCY_MISSING:"
                    + row["role"]
                    + "->"
                    + dependency
                )

    normalized.sort(key=lambda row: row["role"])
    graph = {
        role: list(EXPECTED_INPUTS[role]["dependencies"])
        for role in sorted(EXPECTED_ROLES)
    }
    material = {
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "python_version": PYTHON_VERSION,
        "pip_version": PIP_VERSION,
        "cryptography_version": CRYPTOGRAPHY_VERSION,
        "cffi_version": CFFI_VERSION,
        "pycparser_version": PYCPARSER_VERSION,
        "dependency_lock_digest": lock_digest,
        **global_digests,
        "snapshot_created_at": created.isoformat() if created else "",
        "artifacts": normalized,
        "dependency_graph": graph,
        "artifact_count": len(normalized),
        "total_size_bytes": total,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SNAPSHOT_SCHEMA,
        "state": "BUILD_INPUT_SNAPSHOT_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "input_snapshot_digest": _digest(material) if not blockers else "",
        "dependency_graph_closed": not blockers,
        "all_artifact_hashes_verified": not blockers,
        "sdist_allowed": False,
        "build_from_source_allowed": False,
        "network_called": False,
        "artifact_downloaded_by_this_module": False,
        "dependency_resolved_by_this_module": False,
        "package_installed": False,
    }


def attest_offline_cache(
    snapshot: Mapping[str, Any] | None,
    observed_cache_files: Sequence[Mapping[str, Any]] | None,
    *,
    cache_root_evidence_digest: Any,
    cache_acl_attestation_digest: Any,
    cache_manifest_digest: Any,
    cache_read_only_verified: bool,
    owner_only_acl_verified: bool,
    no_extra_files_verified: bool,
    no_symlinks_verified: bool,
    no_reparse_points_verified: bool,
    no_alternate_data_streams_verified: bool,
    cache_network_isolation_verified: bool,
    attested_at: Any,
) -> dict[str, Any]:
    """Attest a future physical cache from independently observed file evidence."""
    snap = dict(snapshot or {})
    blockers: list[str] = []

    if snap.get("schema") != SNAPSHOT_SCHEMA:
        blockers.append("INPUT_SNAPSHOT_SCHEMA_MISMATCH")
    if snap.get("state") != "BUILD_INPUT_SNAPSHOT_READY":
        blockers.append("READY_INPUT_SNAPSHOT_REQUIRED")

    snapshot_digest = _sha256(snap.get("input_snapshot_digest"))
    if not snapshot_digest:
        blockers.append("INPUT_SNAPSHOT_DIGEST_REQUIRED")

    cache_root = _sha256(cache_root_evidence_digest)
    acl = _sha256(cache_acl_attestation_digest)
    manifest_digest = _sha256(cache_manifest_digest)
    if not cache_root:
        blockers.append("CACHE_ROOT_EVIDENCE_DIGEST_REQUIRED")
    if not acl:
        blockers.append("CACHE_ACL_ATTESTATION_DIGEST_REQUIRED")
    if not manifest_digest:
        blockers.append("CACHE_MANIFEST_DIGEST_REQUIRED")

    for label, flag in (
        ("CACHE_READ_ONLY_VERIFICATION_REQUIRED", cache_read_only_verified),
        ("CACHE_OWNER_ONLY_ACL_REQUIRED", owner_only_acl_verified),
        ("CACHE_NO_EXTRA_FILES_REQUIRED", no_extra_files_verified),
        ("CACHE_NO_SYMLINKS_REQUIRED", no_symlinks_verified),
        ("CACHE_NO_REPARSE_POINTS_REQUIRED", no_reparse_points_verified),
        (
            "CACHE_NO_ALTERNATE_DATA_STREAMS_REQUIRED",
            no_alternate_data_streams_verified,
        ),
        (
            "CACHE_NETWORK_ISOLATION_REQUIRED",
            cache_network_isolation_verified,
        ),
    ):
        if flag is not True:
            blockers.append(label)

    expected = {
        row["role"]: row
        for row in snap.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    observed_rows = list(observed_cache_files or [])
    if len(observed_rows) != len(expected):
        blockers.append("OBSERVED_CACHE_FILE_COUNT_MISMATCH")

    normalized_observed: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    seen_names: set[str] = set()
    for raw in observed_rows:
        if not isinstance(raw, Mapping):
            blockers.append("OBSERVED_CACHE_FILE_INVALID")
            continue
        role = _clean(raw.get("role"), 100).upper()
        try:
            filename = _normalize_filename(raw.get("filename"))
        except OfflineCacheError as exc:
            blockers.append(exc.code)
            continue
        digest = _sha256(raw.get("sha256"))
        try:
            size = int(raw.get("size_bytes"))
        except Exception:
            size = 0

        target = expected.get(role)
        if target is None:
            blockers.append("UNEXPECTED_CACHE_FILE_ROLE:" + role)
            continue
        if role in seen_roles:
            blockers.append("DUPLICATE_OBSERVED_CACHE_ROLE")
        if filename.casefold() in seen_names:
            blockers.append("DUPLICATE_OBSERVED_CACHE_FILENAME")
        seen_roles.add(role)
        seen_names.add(filename.casefold())

        if filename != target.get("filename"):
            blockers.append("CACHE_FILENAME_DRIFT:" + role)
        if digest != target.get("expected_sha256"):
            blockers.append("CACHE_HASH_DRIFT:" + role)
        if size != target.get("size_bytes"):
            blockers.append("CACHE_SIZE_DRIFT:" + role)
        normalized_observed.append(
            {
                "role": role,
                "filename": filename,
                "sha256": digest,
                "size_bytes": size,
            }
        )

    if seen_roles != set(expected):
        blockers.append("OBSERVED_CACHE_ROLE_SET_MISMATCH")

    normalized_observed.sort(key=lambda row: row["filename"].encode("utf-8"))
    tree_material = {
        "files": normalized_observed,
        "order": "UTF8_BYTEWISE_ASCENDING_FILENAME",
    }
    cache_tree_digest = _digest(tree_material)

    try:
        at = _aware(attested_at, "CACHE_ATTESTED_AT")
    except OfflineCacheError as exc:
        at = None
        blockers.append(exc.code)

    material = {
        "input_snapshot_digest": snapshot_digest,
        "dependency_lock_digest": _sha256(snap.get("dependency_lock_digest")),
        "cache_root_evidence_digest": cache_root,
        "cache_acl_attestation_digest": acl,
        "cache_manifest_digest": manifest_digest,
        "cache_tree_digest": cache_tree_digest,
        "observed_files": normalized_observed,
        "cache_read_only_verified": cache_read_only_verified is True,
        "owner_only_acl_verified": owner_only_acl_verified is True,
        "no_extra_files_verified": no_extra_files_verified is True,
        "no_symlinks_verified": no_symlinks_verified is True,
        "no_reparse_points_verified": no_reparse_points_verified is True,
        "no_alternate_data_streams_verified":
            no_alternate_data_streams_verified is True,
        "cache_network_isolation_verified":
            cache_network_isolation_verified is True,
        "attested_at": at.isoformat() if at else "",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": CACHE_SCHEMA,
        "state": "OFFLINE_DEPENDENCY_CACHE_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "offline_cache_attestation_digest": (
            _digest(material) if not blockers else ""
        ),
        "cache_mode": CACHE_MODE,
        "cache_network_policy": CACHE_NETWORK_POLICY,
        "cache_install_policy": CACHE_INSTALL_POLICY,
        "cache_mutation_allowed_after_attestation": False,
        "network_called": False,
        "files_copied_by_this_module": False,
        "packages_installed": False,
        "build_started": False,
    }


def build_offline_input_promotion(
    dependency_lock: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any] | None,
    cache_attestation: Mapping[str, Any] | None,
    *,
    reproducible_build_recipe_digest: Any,
    promotion_review_digest: Any,
) -> dict[str, Any]:
    """Bind an attested cache to a reproducible-build recipe without starting it."""
    lock = dict(dependency_lock or {})
    snap = dict(snapshot or {})
    cache = dict(cache_attestation or {})
    blockers: list[str] = []

    if lock.get("state") != "BUILD_DEPENDENCY_LOCK_READY":
        blockers.append("READY_DEPENDENCY_LOCK_REQUIRED")
    if snap.get("state") != "BUILD_INPUT_SNAPSHOT_READY":
        blockers.append("READY_INPUT_SNAPSHOT_REQUIRED")
    if cache.get("state") != "OFFLINE_DEPENDENCY_CACHE_ATTESTED":
        blockers.append("ATTESTED_OFFLINE_CACHE_REQUIRED")

    lock_digest = _sha256(lock.get("dependency_lock_digest"))
    if _sha256(snap.get("dependency_lock_digest")) != lock_digest:
        blockers.append("SNAPSHOT_DEPENDENCY_LOCK_BINDING_MISMATCH")
    if _sha256(cache.get("dependency_lock_digest")) != lock_digest:
        blockers.append("CACHE_DEPENDENCY_LOCK_BINDING_MISMATCH")
    if _sha256(cache.get("input_snapshot_digest")) != _sha256(
        snap.get("input_snapshot_digest")
    ):
        blockers.append("CACHE_INPUT_SNAPSHOT_BINDING_MISMATCH")

    recipe_digest = _sha256(reproducible_build_recipe_digest)
    review_digest = _sha256(promotion_review_digest)
    if not recipe_digest:
        blockers.append("REPRODUCIBLE_BUILD_RECIPE_DIGEST_REQUIRED")
    if not review_digest:
        blockers.append("PROMOTION_REVIEW_DIGEST_REQUIRED")
    if cache.get("cache_read_only_verified") is not True:
        blockers.append("READ_ONLY_CACHE_REQUIRED")
    if cache.get("cache_network_isolation_verified") is not True:
        blockers.append("NETWORK_ISOLATED_CACHE_REQUIRED")

    material = {
        "dependency_lock_digest": lock_digest,
        "input_snapshot_digest": _sha256(snap.get("input_snapshot_digest")),
        "offline_cache_attestation_digest": _sha256(
            cache.get("offline_cache_attestation_digest")
        ),
        "cache_tree_digest": _sha256(cache.get("cache_tree_digest")),
        "reproducible_build_recipe_digest": recipe_digest,
        "promotion_review_digest": review_digest,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PROMOTION_SCHEMA,
        "state": "OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "offline_input_promotion_digest": _digest(material) if not blockers else "",
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "cache_mutation_allowed": False,
        "dependency_resolution_allowed": False,
        "network_allowed": False,
        "network_called": False,
        "github_api_called": False,
    }


def offline_cache_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "python_version": PYTHON_VERSION,
        "pip_version": PIP_VERSION,
        "cryptography_version": CRYPTOGRAPHY_VERSION,
        "cffi_version": CFFI_VERSION,
        "pycparser_version": PYCPARSER_VERSION,
        "expected_roles": list(EXPECTED_ROLES),
        "closed_dependency_graph_required": True,
        "exact_artifact_count_required": True,
        "sha256_expected_and_observed_required": True,
        "trusted_source_snapshot_required": True,
        "acquisition_receipt_required": True,
        "package_metadata_digest_required": True,
        "download_transport_verification_required": True,
        "sdist_allowed": False,
        "build_from_source_allowed": False,
        "extra_cache_files_allowed": False,
        "cache_read_only_after_attestation": True,
        "owner_only_cache_acl_required": True,
        "symlinks_allowed": False,
        "reparse_points_allowed": False,
        "alternate_data_streams_allowed": False,
        "network_during_cache_attestation_allowed": False,
        "network_during_reproducible_build_allowed": False,
        "cache_mutation_after_attestation_allowed": False,
        "dependency_resolution_from_cache_allowed": False,
        "artifact_downloaded_by_this_module": False,
        "dependency_resolved_by_this_module": False,
        "files_copied_by_this_module": False,
        "packages_installed": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "private_signing_key_loaded": False,
        "credential_material_loaded": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "SNAPSHOT_SCHEMA",
    "CACHE_SCHEMA",
    "PROMOTION_SCHEMA",
    "POLICY_SCHEMA",
    "TARGET_PLATFORM",
    "TARGET_ARCH",
    "CFFI_VERSION",
    "PYCPARSER_VERSION",
    "EXPECTED_INPUTS",
    "EXPECTED_ROLES",
    "OfflineCacheError",
    "build_input_snapshot",
    "attest_offline_cache",
    "build_offline_input_promotion",
    "offline_cache_policy",
]
