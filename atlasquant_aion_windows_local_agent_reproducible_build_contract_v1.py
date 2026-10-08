"""AION Windows Local Agent Build Recipe + Reproducible Package Contract V1.

Pure, non-installing reproducible-build contract for the future Windows local
agent package.

This layer defines:
- exact toolchain/dependency pins;
- deterministic environment variables;
- SOURCE_DATE_EPOCH normalization;
- exact source-role composition inherited from the package manifest;
- normalized file mode/timestamp/order rules;
- reproducible SBOM/provenance material;
- two-build comparison;
- fail-closed non-reproducibility reporting.

It does not build or install a production package, invoke a compiler/packager,
spawn subprocesses, load credentials/private keys, call GitHub, or mutate a
repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    INSTALL_MANIFEST_SCHEMA,
    PACKAGE_FAMILY,
    PACKAGE_CHANNEL,
    REQUIRED_PACKAGE_ROLES,
    ROLE_DESTINATIONS,
    TARGET_ARCH,
    TARGET_PLATFORM,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_REPRODUCIBLE_BUILD_CONTRACT_V1"
RECIPE_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_BUILD_RECIPE_V1"
LOCK_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_BUILD_DEPENDENCY_LOCK_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_BUILD_SOURCE_SET_V1"
BUILD_OBSERVATION_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_BUILD_OBSERVATION_V1"
REPRODUCIBILITY_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_REPRODUCIBILITY_CERTIFICATE_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_REPRODUCIBLE_BUILD_POLICY_V1"

PYTHON_VERSION = "3.12.12"
PIP_VERSION = "26.2.1"
CRYPTOGRAPHY_VERSION = "50.0.2"
BUILD_FORMAT = "DETERMINISTIC_ZIP_STAGING"
ZIP_COMPRESSION = "ZIP_DEFLATED_LEVEL_9"
NORMALIZED_FILE_MODE = 0o644
NORMALIZED_ENTRYPOINT_MODE = 0o755
NORMALIZED_UID = 0
NORMALIZED_GID = 0
NORMALIZED_UNAME = ""
NORMALIZED_GNAME = ""
NORMALIZED_TIMEZONE = "UTC"
NORMALIZED_LOCALE = "C.UTF-8"
PYTHONHASHSEED = "0"
BUILD_NETWORK_POLICY = "NO_NETWORK_DURING_BUILD"
MAX_SOURCE_DATE_EPOCH = 4102444800  # 2100-01-01 UTC
MIN_SOURCE_DATE_EPOCH = 946684800   # 2000-01-01 UTC

PINNED_BUILD_DEPENDENCIES = (
    {"name": "pip", "version": PIP_VERSION, "source": "PYPI_PINNED"},
    {
        "name": "cryptography",
        "version": CRYPTOGRAPHY_VERSION,
        "source": "PYPI_PINNED",
    },
)

FORBIDDEN_ENV_KEYS = (
    "USERNAME",
    "USERPROFILE",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "COMPUTERNAME",
    "HOSTNAME",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "CI_JOB_ID",
    "RUNNER_NAME",
    "TEMP",
    "TMP",
)
REQUIRED_REPRO_ENV = {
    "TZ": NORMALIZED_TIMEZONE,
    "LC_ALL": NORMALIZED_LOCALE,
    "LANG": NORMALIZED_LOCALE,
    "PYTHONHASHSEED": PYTHONHASHSEED,
}
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ReproducibleBuildError(ValueError):
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
        raise ReproducibleBuildError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise ReproducibleBuildError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _source_date_epoch(value: Any) -> int:
    try:
        epoch = int(value)
    except Exception as exc:
        raise ReproducibleBuildError("SOURCE_DATE_EPOCH_INVALID") from exc
    if epoch < MIN_SOURCE_DATE_EPOCH or epoch > MAX_SOURCE_DATE_EPOCH:
        raise ReproducibleBuildError("SOURCE_DATE_EPOCH_OUT_OF_RANGE")
    return epoch


def _normalize_dependency(raw: Mapping[str, Any]) -> dict[str, Any]:
    name = _clean(raw.get("name"), 128)
    version = _clean(raw.get("version"), 80)
    source = _clean(raw.get("source"), 80)
    if not _NAME_RE.fullmatch(name):
        raise ReproducibleBuildError("BUILD_DEPENDENCY_NAME_INVALID")
    if not _SEMVER_RE.fullmatch(version):
        raise ReproducibleBuildError("BUILD_DEPENDENCY_VERSION_UNPINNED")
    if source != "PYPI_PINNED":
        raise ReproducibleBuildError("BUILD_DEPENDENCY_SOURCE_INVALID")
    return {"name": name, "version": version, "source": source}


def build_dependency_lock(
    dependencies: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = list(dependencies or PINNED_BUILD_DEPENDENCIES)
    blockers: list[str] = []
    normalized: list[dict[str, Any]] = []

    for raw in rows:
        try:
            if not isinstance(raw, Mapping):
                raise ReproducibleBuildError("BUILD_DEPENDENCY_INVALID")
            normalized.append(_normalize_dependency(raw))
        except ReproducibleBuildError as exc:
            blockers.append(exc.code)

    names = [row["name"].casefold() for row in normalized]
    if len(set(names)) != len(names):
        blockers.append("DUPLICATE_BUILD_DEPENDENCY")

    expected = {
        row["name"]: row["version"] for row in PINNED_BUILD_DEPENDENCIES
    }
    observed = {row["name"]: row["version"] for row in normalized}
    if observed != expected:
        blockers.append("BUILD_DEPENDENCY_LOCK_DRIFT")

    normalized = sorted(normalized, key=lambda row: row["name"].casefold())
    material = {
        "python_version": PYTHON_VERSION,
        "dependencies": normalized,
        "dependency_count": len(normalized),
        "network_install_allowed_during_build": False,
        "resolver_mutation_allowed": False,
        "dependency_upgrade_allowed": False,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": LOCK_SCHEMA,
        "state": "BUILD_DEPENDENCY_LOCK_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "dependency_lock_digest": _digest(material) if not blockers else "",
        "all_versions_exactly_pinned": not blockers,
        "lock_generated_by_this_module": False,
        "dependencies_installed_by_this_module": False,
        "network_called": False,
    }


def build_source_set(
    installation_manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    manifest = dict(installation_manifest or {})
    blockers: list[str] = []

    if manifest.get("schema") != INSTALL_MANIFEST_SCHEMA:
        blockers.append("INSTALLATION_MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("READY_INSTALLATION_MANIFEST_REQUIRED")

    manifest_digest = _sha256(manifest.get("manifest_digest"))
    if not manifest_digest:
        blockers.append("INSTALLATION_MANIFEST_DIGEST_REQUIRED")

    files = [
        dict(row)
        for row in manifest.get("files", [])
        if isinstance(row, Mapping)
    ]
    if len(files) != len(REQUIRED_PACKAGE_ROLES):
        blockers.append("EXACT_SOURCE_FILE_COUNT_REQUIRED")

    source_rows: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    seen_paths: set[str] = set()
    for row in files:
        role = _clean(row.get("role"), 100).upper()
        path = str(row.get("path") or "")
        digest = _sha256(row.get("sha256"))
        try:
            size = int(row.get("size_bytes"))
        except Exception:
            size = 0

        if role not in REQUIRED_PACKAGE_ROLES:
            blockers.append("SOURCE_ROLE_INVALID")
            continue
        if path != ROLE_DESTINATIONS[role]:
            blockers.append("SOURCE_ROLE_PATH_MISMATCH:" + role)
        if not digest:
            blockers.append("SOURCE_FILE_DIGEST_REQUIRED:" + role)
        if size <= 0:
            blockers.append("SOURCE_FILE_SIZE_REQUIRED:" + role)
        if role in seen_roles:
            blockers.append("DUPLICATE_SOURCE_ROLE")
        if path.casefold() in seen_paths:
            blockers.append("DUPLICATE_SOURCE_PATH")
        seen_roles.add(role)
        seen_paths.add(path.casefold())
        source_rows.append(
            {
                "role": role,
                "path": path,
                "sha256": digest,
                "size_bytes": size,
                "normalized_mode": (
                    NORMALIZED_ENTRYPOINT_MODE
                    if role == "AGENT_ENTRYPOINT"
                    else NORMALIZED_FILE_MODE
                ),
            }
        )

    if seen_roles != set(REQUIRED_PACKAGE_ROLES):
        blockers.append("SOURCE_ROLE_SET_MISMATCH")

    source_rows.sort(key=lambda row: row["path"].encode("utf-8"))
    material = {
        "installation_manifest_digest": manifest_digest,
        "package_family": manifest.get("package_family"),
        "package_version": manifest.get("package_version"),
        "build_commit_sha": manifest.get("build_commit_sha"),
        "sources": source_rows,
        "source_order": "UTF8_BYTEWISE_ASCENDING_PATH",
        "normalized_uid": NORMALIZED_UID,
        "normalized_gid": NORMALIZED_GID,
        "normalized_uname": NORMALIZED_UNAME,
        "normalized_gname": NORMALIZED_GNAME,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": SOURCE_SCHEMA,
        "state": "BUILD_SOURCE_SET_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "source_set_digest": _digest(material) if not blockers else "",
        "source_contents_modified": False,
        "extra_sources_allowed": False,
        "host_paths_embedded": False,
        "credentials_embedded": False,
        "private_keys_embedded": False,
    }


def build_reproducible_recipe(
    installation_manifest: Mapping[str, Any] | None,
    dependency_lock: Mapping[str, Any] | None,
    source_set: Mapping[str, Any] | None,
    *,
    source_date_epoch: Any,
    recipe_revision: int,
    builder_image_digest: Any,
    build_script_digest: Any,
    sbom_recipe_digest: Any,
    provenance_recipe_digest: Any,
) -> dict[str, Any]:
    manifest = dict(installation_manifest or {})
    lock = dict(dependency_lock or {})
    sources = dict(source_set or {})
    blockers: list[str] = []

    if manifest.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("READY_INSTALLATION_MANIFEST_REQUIRED")
    if lock.get("state") != "BUILD_DEPENDENCY_LOCK_READY":
        blockers.append("READY_DEPENDENCY_LOCK_REQUIRED")
    if sources.get("state") != "BUILD_SOURCE_SET_READY":
        blockers.append("READY_SOURCE_SET_REQUIRED")

    if _sha256(sources.get("installation_manifest_digest")) != _sha256(
        manifest.get("manifest_digest")
    ):
        blockers.append("SOURCE_SET_MANIFEST_BINDING_MISMATCH")

    try:
        epoch = _source_date_epoch(source_date_epoch)
    except ReproducibleBuildError as exc:
        epoch = 0
        blockers.append(exc.code)

    try:
        revision = int(recipe_revision)
        if revision < 1:
            blockers.append("BUILD_RECIPE_REVISION_INVALID")
    except Exception:
        revision = 0
        blockers.append("BUILD_RECIPE_REVISION_INVALID")

    builder = _sha256(builder_image_digest)
    script = _sha256(build_script_digest)
    sbom_recipe = _sha256(sbom_recipe_digest)
    provenance_recipe = _sha256(provenance_recipe_digest)
    for label, value in (
        ("BUILDER_IMAGE_DIGEST_REQUIRED", builder),
        ("BUILD_SCRIPT_DIGEST_REQUIRED", script),
        ("SBOM_RECIPE_DIGEST_REQUIRED", sbom_recipe),
        ("PROVENANCE_RECIPE_DIGEST_REQUIRED", provenance_recipe),
    ):
        if not value:
            blockers.append(label)

    environment = {
        **REQUIRED_REPRO_ENV,
        "SOURCE_DATE_EPOCH": str(epoch),
    }
    material = {
        "package_family": PACKAGE_FAMILY,
        "package_channel": PACKAGE_CHANNEL,
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "package_version": manifest.get("package_version"),
        "build_commit_sha": manifest.get("build_commit_sha"),
        "installation_manifest_digest": _sha256(manifest.get("manifest_digest")),
        "dependency_lock_digest": _sha256(lock.get("dependency_lock_digest")),
        "source_set_digest": _sha256(sources.get("source_set_digest")),
        "recipe_revision": revision,
        "python_version": PYTHON_VERSION,
        "pip_version": PIP_VERSION,
        "cryptography_version": CRYPTOGRAPHY_VERSION,
        "build_format": BUILD_FORMAT,
        "zip_compression": ZIP_COMPRESSION,
        "normalized_file_mode": NORMALIZED_FILE_MODE,
        "normalized_entrypoint_mode": NORMALIZED_ENTRYPOINT_MODE,
        "normalized_uid": NORMALIZED_UID,
        "normalized_gid": NORMALIZED_GID,
        "normalized_uname": NORMALIZED_UNAME,
        "normalized_gname": NORMALIZED_GNAME,
        "environment": environment,
        "forbidden_environment_keys": list(FORBIDDEN_ENV_KEYS),
        "source_order": "UTF8_BYTEWISE_ASCENDING_PATH",
        "archive_member_timestamp": "SOURCE_DATE_EPOCH_UTC",
        "json_serialization": "UTF8_SORT_KEYS_COMPACT_NO_NAN",
        "line_endings": "LF",
        "build_network_policy": BUILD_NETWORK_POLICY,
        "builder_image_digest": builder,
        "build_script_digest": script,
        "sbom_recipe_digest": sbom_recipe,
        "provenance_recipe_digest": provenance_recipe,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": RECIPE_SCHEMA,
        "state": "REPRODUCIBLE_BUILD_RECIPE_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "build_recipe_digest": _digest(material) if not blockers else "",
        "source_date_epoch_normalized": epoch if not blockers else 0,
        "wall_clock_time_embedded": False,
        "host_username_embedded": False,
        "host_path_embedded": False,
        "runner_identity_embedded": False,
        "random_seed_uncontrolled": False,
        "network_during_build_allowed": False,
        "dependency_resolution_during_build_allowed": False,
        "production_package_built_by_this_module": False,
        "subprocess_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
    }


def build_observation(
    recipe: Mapping[str, Any] | None,
    *,
    build_observation_id: Any,
    output_archive_digest: Any,
    output_manifest_digest: Any,
    output_sbom_digest: Any,
    output_provenance_digest: Any,
    output_tree_digest: Any,
    builder_image_digest: Any,
    build_script_digest: Any,
    dependency_lock_digest: Any,
    source_set_digest: Any,
    source_date_epoch: Any,
    normalized_member_metadata_verified: bool,
    no_extra_files_verified: bool,
    no_host_specific_metadata_verified: bool,
    no_credentials_verified: bool,
    no_private_keys_verified: bool,
    network_not_used_verified: bool,
    observed_at: Any,
) -> dict[str, Any]:
    recipe_row = dict(recipe or {})
    blockers: list[str] = []

    if recipe_row.get("schema") != RECIPE_SCHEMA:
        blockers.append("BUILD_RECIPE_SCHEMA_MISMATCH")
    if recipe_row.get("state") != "REPRODUCIBLE_BUILD_RECIPE_READY":
        blockers.append("READY_BUILD_RECIPE_REQUIRED")

    observation_id = _clean(build_observation_id, 180)
    if not _NAME_RE.fullmatch(observation_id):
        blockers.append("BUILD_OBSERVATION_ID_INVALID")

    archive = _sha256(output_archive_digest)
    manifest = _sha256(output_manifest_digest)
    sbom = _sha256(output_sbom_digest)
    provenance = _sha256(output_provenance_digest)
    tree = _sha256(output_tree_digest)
    for label, value in (
        ("OUTPUT_ARCHIVE_DIGEST_REQUIRED", archive),
        ("OUTPUT_MANIFEST_DIGEST_REQUIRED", manifest),
        ("OUTPUT_SBOM_DIGEST_REQUIRED", sbom),
        ("OUTPUT_PROVENANCE_DIGEST_REQUIRED", provenance),
        ("OUTPUT_TREE_DIGEST_REQUIRED", tree),
    ):
        if not value:
            blockers.append(label)

    if _sha256(builder_image_digest) != _sha256(
        recipe_row.get("builder_image_digest")
    ):
        blockers.append("BUILDER_IMAGE_DIGEST_MISMATCH")
    if _sha256(build_script_digest) != _sha256(
        recipe_row.get("build_script_digest")
    ):
        blockers.append("BUILD_SCRIPT_DIGEST_MISMATCH")
    if _sha256(dependency_lock_digest) != _sha256(
        recipe_row.get("dependency_lock_digest")
    ):
        blockers.append("DEPENDENCY_LOCK_DIGEST_MISMATCH")
    if _sha256(source_set_digest) != _sha256(
        recipe_row.get("source_set_digest")
    ):
        blockers.append("SOURCE_SET_DIGEST_MISMATCH")

    try:
        epoch = _source_date_epoch(source_date_epoch)
        if epoch != int(recipe_row.get("source_date_epoch_normalized") or 0):
            blockers.append("SOURCE_DATE_EPOCH_MISMATCH")
    except ReproducibleBuildError as exc:
        epoch = 0
        blockers.append(exc.code)

    for label, flag in (
        ("NORMALIZED_MEMBER_METADATA_REQUIRED", normalized_member_metadata_verified),
        ("NO_EXTRA_FILES_VERIFICATION_REQUIRED", no_extra_files_verified),
        ("NO_HOST_METADATA_VERIFICATION_REQUIRED", no_host_specific_metadata_verified),
        ("NO_CREDENTIALS_VERIFICATION_REQUIRED", no_credentials_verified),
        ("NO_PRIVATE_KEYS_VERIFICATION_REQUIRED", no_private_keys_verified),
        ("BUILD_NETWORK_ABSENCE_VERIFICATION_REQUIRED", network_not_used_verified),
    ):
        if flag is not True:
            blockers.append(label)

    try:
        observed = _aware(observed_at, "BUILD_OBSERVED_AT")
    except ReproducibleBuildError as exc:
        observed = None
        blockers.append(exc.code)

    material = {
        "build_observation_id": observation_id,
        "build_recipe_digest": _sha256(recipe_row.get("build_recipe_digest")),
        "output_archive_digest": archive,
        "output_manifest_digest": manifest,
        "output_sbom_digest": sbom,
        "output_provenance_digest": provenance,
        "output_tree_digest": tree,
        "builder_image_digest": _sha256(builder_image_digest),
        "build_script_digest": _sha256(build_script_digest),
        "dependency_lock_digest": _sha256(dependency_lock_digest),
        "source_set_digest": _sha256(source_set_digest),
        "source_date_epoch": epoch,
        "normalized_member_metadata_verified":
            normalized_member_metadata_verified is True,
        "no_extra_files_verified": no_extra_files_verified is True,
        "no_host_specific_metadata_verified":
            no_host_specific_metadata_verified is True,
        "no_credentials_verified": no_credentials_verified is True,
        "no_private_keys_verified": no_private_keys_verified is True,
        "network_not_used_verified": network_not_used_verified is True,
        # Observation time is evidence metadata only and is deliberately excluded
        # from the reproducibility fingerprint below.
        "observed_at": observed.isoformat() if observed else "",
    }
    reproducibility_fingerprint_material = {
        key: value for key, value in material.items()
        if key not in ("build_observation_id", "observed_at")
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": BUILD_OBSERVATION_SCHEMA,
        "state": "BUILD_OBSERVATION_VALID" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "build_observation_digest": _digest(material) if not blockers else "",
        "reproducibility_fingerprint": (
            _digest(reproducibility_fingerprint_material)
            if not blockers else ""
        ),
        "production_package_built_by_this_module": False,
        "package_installed": False,
        "network_called_by_this_module": False,
    }


def compare_independent_builds(
    recipe: Mapping[str, Any] | None,
    build_a: Mapping[str, Any] | None,
    build_b: Mapping[str, Any] | None,
    *,
    independent_builders_verified: bool,
    independent_workdirs_verified: bool,
    clean_build_roots_verified: bool,
) -> dict[str, Any]:
    recipe_row = dict(recipe or {})
    first = dict(build_a or {})
    second = dict(build_b or {})
    blockers: list[str] = []

    if recipe_row.get("state") != "REPRODUCIBLE_BUILD_RECIPE_READY":
        blockers.append("READY_BUILD_RECIPE_REQUIRED")
    for label, row in (("BUILD_A", first), ("BUILD_B", second)):
        if row.get("schema") != BUILD_OBSERVATION_SCHEMA:
            blockers.append(label + "_SCHEMA_MISMATCH")
        if row.get("state") != "BUILD_OBSERVATION_VALID":
            blockers.append(label + "_VALID_OBSERVATION_REQUIRED")
        if _sha256(row.get("build_recipe_digest")) != _sha256(
            recipe_row.get("build_recipe_digest")
        ):
            blockers.append(label + "_RECIPE_BINDING_MISMATCH")

    if first.get("build_observation_id") == second.get("build_observation_id"):
        blockers.append("INDEPENDENT_BUILD_OBSERVATION_IDS_REQUIRED")
    for label, flag in (
        ("INDEPENDENT_BUILDERS_REQUIRED", independent_builders_verified),
        ("INDEPENDENT_WORKDIRS_REQUIRED", independent_workdirs_verified),
        ("CLEAN_BUILD_ROOTS_REQUIRED", clean_build_roots_verified),
    ):
        if flag is not True:
            blockers.append(label)

    compared_fields = (
        "output_archive_digest",
        "output_manifest_digest",
        "output_sbom_digest",
        "output_provenance_digest",
        "output_tree_digest",
        "reproducibility_fingerprint",
    )
    mismatches = [
        field for field in compared_fields
        if first.get(field) != second.get(field)
    ]
    if mismatches:
        blockers.extend("REPRODUCIBILITY_MISMATCH:" + field for field in mismatches)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "build_recipe_digest": _sha256(recipe_row.get("build_recipe_digest")),
        "build_a_observation_digest": _sha256(
            first.get("build_observation_digest")
        ),
        "build_b_observation_digest": _sha256(
            second.get("build_observation_digest")
        ),
        "build_a_id": first.get("build_observation_id"),
        "build_b_id": second.get("build_observation_id"),
        "compared_fields": list(compared_fields),
        "mismatches": mismatches,
        "independent_builders_verified": independent_builders_verified is True,
        "independent_workdirs_verified": independent_workdirs_verified is True,
        "clean_build_roots_verified": clean_build_roots_verified is True,
    }
    return {
        "schema": REPRODUCIBILITY_SCHEMA,
        "state": (
            "TWO_BUILD_REPRODUCIBILITY_CONFIRMED"
            if not blockers else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "reproducibility_certificate_digest": (
            _digest(material) if not blockers else ""
        ),
        "bit_for_bit_reproducibility_confirmed": not blockers,
        "installation_authorized": False,
        "release_authorized": False,
        "production_package_built_by_this_module": False,
        "package_installed": False,
        "network_called": False,
        "github_api_called": False,
    }


def reproducible_build_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "package_family": PACKAGE_FAMILY,
        "package_channel": PACKAGE_CHANNEL,
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "python_version": PYTHON_VERSION,
        "pip_version": PIP_VERSION,
        "cryptography_version": CRYPTOGRAPHY_VERSION,
        "pinned_build_dependencies": [dict(row) for row in PINNED_BUILD_DEPENDENCIES],
        "source_date_epoch_required": True,
        "timezone_normalized_utc": True,
        "locale_normalized": True,
        "python_hash_seed_fixed": True,
        "lexical_source_order_required": True,
        "normalized_file_modes_required": True,
        "normalized_uid_gid_required": True,
        "host_username_forbidden": True,
        "host_path_forbidden": True,
        "runner_identity_forbidden": True,
        "wall_clock_time_forbidden_in_artifact": True,
        "network_during_build_allowed": False,
        "dependency_resolution_during_build_allowed": False,
        "dependency_upgrade_during_build_allowed": False,
        "sbom_recipe_pinned": True,
        "provenance_recipe_pinned": True,
        "builder_image_digest_required": True,
        "build_script_digest_required": True,
        "two_independent_builds_required": True,
        "clean_build_roots_required": True,
        "independent_workdirs_required": True,
        "archive_digest_must_match": True,
        "manifest_digest_must_match": True,
        "sbom_digest_must_match": True,
        "provenance_digest_must_match": True,
        "tree_digest_must_match": True,
        "production_package_built_by_this_module": False,
        "package_installed": False,
        "release_authorized": False,
        "installation_authorized": False,
        "subprocess_spawned": False,
        "filesystem_modified": False,
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
    "RECIPE_SCHEMA",
    "LOCK_SCHEMA",
    "SOURCE_SCHEMA",
    "BUILD_OBSERVATION_SCHEMA",
    "REPRODUCIBILITY_SCHEMA",
    "POLICY_SCHEMA",
    "PYTHON_VERSION",
    "PIP_VERSION",
    "CRYPTOGRAPHY_VERSION",
    "BUILD_FORMAT",
    "PINNED_BUILD_DEPENDENCIES",
    "FORBIDDEN_ENV_KEYS",
    "REQUIRED_REPRO_ENV",
    "ReproducibleBuildError",
    "build_dependency_lock",
    "build_source_set",
    "build_reproducible_recipe",
    "build_observation",
    "compare_independent_builds",
    "reproducible_build_policy",
]
