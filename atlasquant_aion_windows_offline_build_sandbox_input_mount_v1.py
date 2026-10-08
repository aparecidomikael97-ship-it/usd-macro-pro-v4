"""AION Windows Offline Build Sandbox + Input Mount Contract V1.

Pure, non-executing Windows build-sandbox contract.

This module binds the already-attested offline inputs from the previous layer
into a future sandbox design with:
- read-only cache/source/runtime roots;
- isolated writable output/temp roots;
- exact environment scrub;
- one pinned python.exe process only;
- no shell or child processes;
- no network, DNS, loopback, proxy or remote IPC;
- explicit filesystem anti-escape requirements;
- bounded resources.

It does not mount directories, spawn a process, create a Windows Job Object,
create firewall rules, open sockets, modify ACLs, build a package, install
anything, call GitHub or mutate a repository.
"""
from __future__ import annotations

from pathlib import PureWindowsPath
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_build_input_offline_cache_attestation_v1 import (
    PROMOTION_SCHEMA,
)
from atlasquant_aion_windows_local_agent_reproducible_build_contract_v1 import (
    RECIPE_SCHEMA,
    PYTHON_VERSION,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_SANDBOX_INPUT_MOUNT_V1"
MOUNT_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_INPUT_MOUNT_V1"
ENV_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_ENVIRONMENT_SCRUB_V1"
PROCESS_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_PROCESS_ALLOWLIST_V1"
NETWORK_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_NETWORK_DENY_V1"
PREFLIGHT_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_SANDBOX_PREFLIGHT_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_OFFLINE_BUILD_SANDBOX_POLICY_V1"

SANDBOX_MODE = "WINDOWS_CURRENT_USER_OFFLINE_BUILD"
PROCESS_POLICY = "SINGLE_PINNED_PYTHON_NO_CHILDREN"
NETWORK_POLICY = "DENY_ALL"
FILESYSTEM_POLICY = "RO_INPUTS_RW_OUTPUT_TEMP_ONLY"
PATH_LOOKUP_POLICY = "DISABLED"
MAX_RUNTIME_SECONDS = 300
MAX_MEMORY_MB = 1024
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
MAX_PROCESS_COUNT = 1
MAX_CHILD_PROCESS_COUNT = 0

REQUIRED_ENVIRONMENT = {
    "TZ": "UTC",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "PYTHONSAFEPATH": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_NO_INDEX": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_CONFIG_FILE": "NUL",
}
FORBIDDEN_ENVIRONMENT_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "USERNAME",
    "COMPUTERNAME",
    "HOSTNAME",
    "APPDATA",
    "LOCALAPPDATA",
    "TEMP",
    "TMP",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.exe$", re.IGNORECASE)


class OfflineBuildSandboxError(ValueError):
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


def _windows_abs_local_path(value: Any, label: str) -> str:
    raw = str(value or "")
    if not raw or raw != raw.strip() or "\x00" in raw:
        raise OfflineBuildSandboxError(label + "_INVALID")
    if raw.startswith("\\"):
        raise OfflineBuildSandboxError(label + "_UNC_FORBIDDEN")
    path = PureWindowsPath(raw)
    if not path.is_absolute() or not path.drive:
        raise OfflineBuildSandboxError(label + "_ABSOLUTE_LOCAL_PATH_REQUIRED")
    if any(part in ("", ".", "..") for part in path.parts[1:]):
        raise OfflineBuildSandboxError(label + "_TRAVERSAL_FORBIDDEN")
    return str(path)


def _path_key(value: str) -> tuple[str, ...]:
    path = PureWindowsPath(value)
    return tuple(part.casefold() for part in path.parts)


def _is_ancestor(parent: str, child: str) -> bool:
    p = _path_key(parent)
    c = _path_key(child)
    return len(p) <= len(c) and c[: len(p)] == p


def _paths_overlap(left: str, right: str) -> bool:
    return _is_ancestor(left, right) or _is_ancestor(right, left)


def build_input_mount_contract(
    promotion: Mapping[str, Any] | None,
    *,
    cache_root: Any,
    source_root: Any,
    runtime_root: Any,
    output_root: Any,
    temp_root: Any,
    cache_root_evidence_digest: Any,
    source_tree_digest: Any,
    runtime_tree_digest: Any,
    output_root_identity_digest: Any,
    temp_root_identity_digest: Any,
) -> dict[str, Any]:
    """Bind non-overlapping Windows roots without mounting anything."""
    promo = dict(promotion or {})
    blockers: list[str] = []

    if promo.get("schema") != PROMOTION_SCHEMA:
        blockers.append("OFFLINE_INPUT_PROMOTION_SCHEMA_MISMATCH")
    if promo.get("state") != "OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD":
        blockers.append("READY_OFFLINE_INPUT_PROMOTION_REQUIRED")

    roots: dict[str, str] = {}
    for name, value in (
        ("cache_root", cache_root),
        ("source_root", source_root),
        ("runtime_root", runtime_root),
        ("output_root", output_root),
        ("temp_root", temp_root),
    ):
        try:
            roots[name] = _windows_abs_local_path(
                value,
                name.upper(),
            )
        except OfflineBuildSandboxError as exc:
            roots[name] = ""
            blockers.append(exc.code)

    valid_roots = {key: value for key, value in roots.items() if value}
    names = list(valid_roots)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            if _paths_overlap(valid_roots[left_name], valid_roots[right_name]):
                blockers.append(
                    "SANDBOX_ROOT_OVERLAP:"
                    + left_name.upper()
                    + ":"
                    + right_name.upper()
                )

    digests = {}
    for key, value, label in (
        (
            "cache_root_evidence_digest",
            cache_root_evidence_digest,
            "CACHE_ROOT_EVIDENCE_DIGEST_REQUIRED",
        ),
        (
            "source_tree_digest",
            source_tree_digest,
            "SOURCE_TREE_DIGEST_REQUIRED",
        ),
        (
            "runtime_tree_digest",
            runtime_tree_digest,
            "RUNTIME_TREE_DIGEST_REQUIRED",
        ),
        (
            "output_root_identity_digest",
            output_root_identity_digest,
            "OUTPUT_ROOT_IDENTITY_DIGEST_REQUIRED",
        ),
        (
            "temp_root_identity_digest",
            temp_root_identity_digest,
            "TEMP_ROOT_IDENTITY_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "offline_input_promotion_digest": _sha256(
            promo.get("offline_input_promotion_digest")
        ),
        "offline_cache_attestation_digest": _sha256(
            promo.get("offline_cache_attestation_digest")
        ),
        "cache_tree_digest": _sha256(promo.get("cache_tree_digest")),
        **roots,
        **digests,
        "cache_mode": "READ_ONLY",
        "source_mode": "READ_ONLY",
        "runtime_mode": "READ_ONLY",
        "output_mode": "WRITE_ONLY_BUILD_OUTPUT",
        "temp_mode": "READ_WRITE_EPHEMERAL",
        "path_comparison": "WINDOWS_CASE_INSENSITIVE_COMPONENT_BOUNDARY",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": MOUNT_SCHEMA,
        "state": "OFFLINE_BUILD_INPUT_MOUNT_CONTRACT_READY"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "mount_contract_digest": _digest(material) if not blockers else "",
        "cache_write_allowed": False,
        "source_write_allowed": False,
        "runtime_write_allowed": False,
        "output_read_as_input_allowed": False,
        "repository_write_allowed": False,
        "path_traversal_allowed": False,
        "symlink_escape_allowed": False,
        "reparse_point_escape_allowed": False,
        "hardlink_escape_allowed": False,
        "alternate_data_streams_allowed": False,
        "device_path_access_allowed": False,
        "network_share_allowed": False,
        "mount_performed": False,
        "filesystem_modified": False,
    }


def build_environment_scrub_contract(
    recipe: Mapping[str, Any] | None,
    mount: Mapping[str, Any] | None,
    *,
    source_date_epoch: Any,
    caller_environment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce the only environment map a future build process may receive."""
    recipe_row = dict(recipe or {})
    mount_row = dict(mount or {})
    blockers: list[str] = []

    if recipe_row.get("schema") != RECIPE_SCHEMA:
        blockers.append("REPRODUCIBLE_BUILD_RECIPE_SCHEMA_MISMATCH")
    if recipe_row.get("state") != "REPRODUCIBLE_BUILD_RECIPE_READY":
        blockers.append("READY_REPRODUCIBLE_BUILD_RECIPE_REQUIRED")
    if mount_row.get("schema") != MOUNT_SCHEMA:
        blockers.append("INPUT_MOUNT_SCHEMA_MISMATCH")
    if mount_row.get("state") != "OFFLINE_BUILD_INPUT_MOUNT_CONTRACT_READY":
        blockers.append("READY_INPUT_MOUNT_CONTRACT_REQUIRED")

    try:
        epoch = int(source_date_epoch)
    except Exception:
        epoch = 0
        blockers.append("SOURCE_DATE_EPOCH_INVALID")
    if str(epoch) != str(
        recipe_row.get("environment", {}).get("SOURCE_DATE_EPOCH", "")
    ):
        blockers.append("SOURCE_DATE_EPOCH_RECIPE_MISMATCH")

    supplied = dict(caller_environment or {})
    rejected = sorted(
        key
        for key in supplied
        if key.upper() in FORBIDDEN_ENVIRONMENT_KEYS
        or key.upper().startswith("GIT_CONFIG_")
        or key not in REQUIRED_ENVIRONMENT
    )
    if rejected:
        blockers.append("CALLER_ENVIRONMENT_KEY_NOT_ALLOWED")

    for key, expected in REQUIRED_ENVIRONMENT.items():
        if key in supplied and str(supplied[key]) != expected:
            blockers.append("CALLER_ENVIRONMENT_OVERRIDE_FORBIDDEN:" + key)

    environment = {
        **REQUIRED_ENVIRONMENT,
        "SOURCE_DATE_EPOCH": str(epoch),
        "AION_CACHE_ROOT": mount_row.get("cache_root", ""),
        "AION_SOURCE_ROOT": mount_row.get("source_root", ""),
        "AION_RUNTIME_ROOT": mount_row.get("runtime_root", ""),
        "AION_OUTPUT_ROOT": mount_row.get("output_root", ""),
        "AION_TEMP_ROOT": mount_row.get("temp_root", ""),
    }
    material = {
        "build_recipe_digest": _sha256(recipe_row.get("build_recipe_digest")),
        "mount_contract_digest": _sha256(mount_row.get("mount_contract_digest")),
        "environment": environment,
        "rejected_caller_environment_keys": rejected,
        "parent_environment_inherited": False,
        "path_lookup_allowed": False,
        "proxy_environment_allowed": False,
        "user_site_allowed": False,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": ENV_SCHEMA,
        "state": "OFFLINE_BUILD_ENVIRONMENT_SCRUB_READY"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "environment_contract_digest": _digest(material) if not blockers else "",
        "parent_environment_inherited": False,
        "caller_environment_overrides_allowed": False,
        "path_lookup_allowed": False,
        "credentials_in_environment_allowed": False,
        "proxy_environment_allowed": False,
        "environment_applied_to_process": False,
    }


def build_process_allowlist_contract(
    recipe: Mapping[str, Any] | None,
    mount: Mapping[str, Any] | None,
    environment: Mapping[str, Any] | None,
    *,
    python_executable_path: Any,
    python_executable_sha256: Any,
    build_script_path: Any,
    build_script_sha256: Any,
) -> dict[str, Any]:
    """Define one absolute pinned python process; no execution occurs."""
    recipe_row = dict(recipe or {})
    mount_row = dict(mount or {})
    env_row = dict(environment or {})
    blockers: list[str] = []

    if recipe_row.get("state") != "REPRODUCIBLE_BUILD_RECIPE_READY":
        blockers.append("READY_REPRODUCIBLE_BUILD_RECIPE_REQUIRED")
    if mount_row.get("state") != "OFFLINE_BUILD_INPUT_MOUNT_CONTRACT_READY":
        blockers.append("READY_INPUT_MOUNT_CONTRACT_REQUIRED")
    if env_row.get("state") != "OFFLINE_BUILD_ENVIRONMENT_SCRUB_READY":
        blockers.append("READY_ENVIRONMENT_SCRUB_REQUIRED")

    try:
        python_path = _windows_abs_local_path(
            python_executable_path,
            "PYTHON_EXECUTABLE_PATH",
        )
    except OfflineBuildSandboxError as exc:
        python_path = ""
        blockers.append(exc.code)
    try:
        script_path = _windows_abs_local_path(
            build_script_path,
            "BUILD_SCRIPT_PATH",
        )
    except OfflineBuildSandboxError as exc:
        script_path = ""
        blockers.append(exc.code)

    runtime_root = mount_row.get("runtime_root", "")
    source_root = mount_row.get("source_root", "")
    if python_path and runtime_root and not _is_ancestor(runtime_root, python_path):
        blockers.append("PYTHON_EXECUTABLE_OUTSIDE_RUNTIME_ROOT")
    if script_path and source_root and not _is_ancestor(source_root, script_path):
        blockers.append("BUILD_SCRIPT_OUTSIDE_SOURCE_ROOT")
    if python_path and not _EXE_NAME_RE.fullmatch(PureWindowsPath(python_path).name):
        blockers.append("PYTHON_EXECUTABLE_NAME_INVALID")
    if python_path and PureWindowsPath(python_path).name.casefold() != "python.exe":
        blockers.append("ONLY_PYTHON_EXE_ALLOWED")

    python_digest = _sha256(python_executable_sha256)
    script_digest = _sha256(build_script_sha256)
    if not python_digest:
        blockers.append("PYTHON_EXECUTABLE_SHA256_REQUIRED")
    if not script_digest:
        blockers.append("BUILD_SCRIPT_SHA256_REQUIRED")
    if script_digest != _sha256(recipe_row.get("build_script_digest")):
        blockers.append("BUILD_SCRIPT_RECIPE_DIGEST_MISMATCH")

    argv_template = [
        python_path,
        "-I",
        "-S",
        script_path,
        "--offline",
        "--no-network",
        "--cache-root",
        mount_row.get("cache_root", ""),
        "--source-root",
        mount_row.get("source_root", ""),
        "--output-root",
        mount_row.get("output_root", ""),
        "--temp-root",
        mount_row.get("temp_root", ""),
    ]
    material = {
        "build_recipe_digest": _sha256(recipe_row.get("build_recipe_digest")),
        "mount_contract_digest": _sha256(mount_row.get("mount_contract_digest")),
        "environment_contract_digest": _sha256(
            env_row.get("environment_contract_digest")
        ),
        "python_version": PYTHON_VERSION,
        "python_executable_path": python_path,
        "python_executable_sha256": python_digest,
        "build_script_path": script_path,
        "build_script_sha256": script_digest,
        "argv_template": argv_template,
        "process_policy": PROCESS_POLICY,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PROCESS_SCHEMA,
        "state": "OFFLINE_BUILD_PROCESS_ALLOWLIST_READY"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "process_contract_digest": _digest(material) if not blockers else "",
        "shell_allowed": False,
        "cmd_exe_allowed": False,
        "powershell_allowed": False,
        "path_lookup_allowed": False,
        "python_c_flag_allowed": False,
        "python_m_pip_allowed": False,
        "arbitrary_arguments_allowed": False,
        "child_process_allowed": False,
        "detached_process_allowed": False,
        "background_process_allowed": False,
        "process_spawned": False,
    }


def build_network_deny_contract() -> dict[str, Any]:
    material = {
        "network_policy": NETWORK_POLICY,
        "dns_policy": "DENY",
        "tcp_policy": "DENY",
        "udp_policy": "DENY",
        "loopback_policy": "DENY",
        "proxy_policy": "DENY",
        "named_pipe_remote_policy": "DENY",
        "unc_policy": "DENY",
    }
    return {
        "schema": NETWORK_SCHEMA,
        "state": "OFFLINE_BUILD_NETWORK_DENY_CONTRACT_READY",
        **material,
        "network_contract_digest": _digest(material),
        "network_allowed": False,
        "dns_allowed": False,
        "tcp_allowed": False,
        "udp_allowed": False,
        "loopback_allowed": False,
        "proxy_allowed": False,
        "remote_named_pipe_allowed": False,
        "unc_allowed": False,
        "socket_opened": False,
        "network_called": False,
        "firewall_rule_created": False,
        "windows_network_isolation_physically_verified": False,
    }


def build_sandbox_preflight(
    promotion: Mapping[str, Any] | None,
    recipe: Mapping[str, Any] | None,
    mount: Mapping[str, Any] | None,
    environment: Mapping[str, Any] | None,
    process: Mapping[str, Any] | None,
    network: Mapping[str, Any] | None,
    *,
    resource_policy_digest: Any,
) -> dict[str, Any]:
    """Aggregate the logical sandbox design. This is not execution authority."""
    promo = dict(promotion or {})
    recipe_row = dict(recipe or {})
    mount_row = dict(mount or {})
    env_row = dict(environment or {})
    process_row = dict(process or {})
    network_row = dict(network or {})
    blockers: list[str] = []

    expected_states = (
        (
            promo,
            "OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD",
            "READY_OFFLINE_INPUT_PROMOTION_REQUIRED",
        ),
        (
            recipe_row,
            "REPRODUCIBLE_BUILD_RECIPE_READY",
            "READY_REPRODUCIBLE_BUILD_RECIPE_REQUIRED",
        ),
        (
            mount_row,
            "OFFLINE_BUILD_INPUT_MOUNT_CONTRACT_READY",
            "READY_INPUT_MOUNT_CONTRACT_REQUIRED",
        ),
        (
            env_row,
            "OFFLINE_BUILD_ENVIRONMENT_SCRUB_READY",
            "READY_ENVIRONMENT_SCRUB_REQUIRED",
        ),
        (
            process_row,
            "OFFLINE_BUILD_PROCESS_ALLOWLIST_READY",
            "READY_PROCESS_ALLOWLIST_REQUIRED",
        ),
        (
            network_row,
            "OFFLINE_BUILD_NETWORK_DENY_CONTRACT_READY",
            "READY_NETWORK_DENY_CONTRACT_REQUIRED",
        ),
    )
    for row, state, label in expected_states:
        if row.get("state") != state:
            blockers.append(label)

    if _sha256(promo.get("reproducible_build_recipe_digest")) != _sha256(
        recipe_row.get("build_recipe_digest")
    ):
        blockers.append("PROMOTION_RECIPE_BINDING_MISMATCH")
    if _sha256(mount_row.get("offline_input_promotion_digest")) != _sha256(
        promo.get("offline_input_promotion_digest")
    ):
        blockers.append("MOUNT_PROMOTION_BINDING_MISMATCH")
    if _sha256(env_row.get("build_recipe_digest")) != _sha256(
        recipe_row.get("build_recipe_digest")
    ):
        blockers.append("ENVIRONMENT_RECIPE_BINDING_MISMATCH")
    if _sha256(process_row.get("environment_contract_digest")) != _sha256(
        env_row.get("environment_contract_digest")
    ):
        blockers.append("PROCESS_ENVIRONMENT_BINDING_MISMATCH")

    resource_digest = _sha256(resource_policy_digest)
    if not resource_digest:
        blockers.append("RESOURCE_POLICY_DIGEST_REQUIRED")

    resources = {
        "max_runtime_seconds": MAX_RUNTIME_SECONDS,
        "max_memory_mb": MAX_MEMORY_MB,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "max_process_count": MAX_PROCESS_COUNT,
        "max_child_process_count": MAX_CHILD_PROCESS_COUNT,
    }
    physical_proofs = [
        "WINDOWS_RESTRICTED_TOKEN_PROOF_REQUIRED",
        "WINDOWS_JOB_OBJECT_LIMITS_PROOF_REQUIRED",
        "CACHE_READ_ONLY_MOUNT_PROOF_REQUIRED",
        "SOURCE_READ_ONLY_MOUNT_PROOF_REQUIRED",
        "RUNTIME_READ_ONLY_MOUNT_PROOF_REQUIRED",
        "OUTPUT_TEMP_ONLY_WRITE_PROOF_REQUIRED",
        "SYMLINK_REPARSE_HARDLINK_ESCAPE_PROOF_REQUIRED",
        "ENVIRONMENT_SCRUB_PHYSICAL_PROOF_REQUIRED",
        "PINNED_PYTHON_BINARY_PROOF_REQUIRED",
        "NO_CHILD_PROCESS_PHYSICAL_PROOF_REQUIRED",
        "WINDOWS_NETWORK_DENY_PHYSICAL_PROOF_REQUIRED",
        "RESOURCE_LIMITS_PHYSICAL_PROOF_REQUIRED",
    ]
    material = {
        "sandbox_mode": SANDBOX_MODE,
        "offline_input_promotion_digest": _sha256(
            promo.get("offline_input_promotion_digest")
        ),
        "build_recipe_digest": _sha256(recipe_row.get("build_recipe_digest")),
        "mount_contract_digest": _sha256(mount_row.get("mount_contract_digest")),
        "environment_contract_digest": _sha256(
            env_row.get("environment_contract_digest")
        ),
        "process_contract_digest": _sha256(
            process_row.get("process_contract_digest")
        ),
        "network_contract_digest": _sha256(
            network_row.get("network_contract_digest")
        ),
        "resource_policy_digest": resource_digest,
        "filesystem_policy": FILESYSTEM_POLICY,
        "process_policy": PROCESS_POLICY,
        "network_policy": NETWORK_POLICY,
        "path_lookup_policy": PATH_LOOKUP_POLICY,
        "resources": resources,
        "required_physical_proofs": physical_proofs,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PREFLIGHT_SCHEMA,
        "state": "WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "sandbox_preflight_digest": _digest(material) if not blockers else "",
        "physical_windows_sandbox_verified": False,
        "restricted_token_created": False,
        "job_object_created": False,
        "read_only_mounts_created": False,
        "network_isolation_physically_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_performed": False,
    }


def offline_build_sandbox_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "sandbox_mode": SANDBOX_MODE,
        "filesystem_policy": FILESYSTEM_POLICY,
        "process_policy": PROCESS_POLICY,
        "network_policy": NETWORK_POLICY,
        "path_lookup_policy": PATH_LOOKUP_POLICY,
        "cache_read_only_required": True,
        "source_read_only_required": True,
        "runtime_read_only_required": True,
        "output_temp_only_writable": True,
        "sandbox_roots_must_not_overlap": True,
        "unc_paths_allowed": False,
        "network_share_allowed": False,
        "path_traversal_allowed": False,
        "symlink_escape_allowed": False,
        "reparse_point_escape_allowed": False,
        "hardlink_escape_allowed": False,
        "alternate_data_streams_allowed": False,
        "device_path_access_allowed": False,
        "parent_environment_inheritance_allowed": False,
        "caller_environment_overrides_allowed": False,
        "path_lookup_allowed": False,
        "shell_allowed": False,
        "powershell_allowed": False,
        "cmd_exe_allowed": False,
        "arbitrary_process_spawn_allowed": False,
        "child_process_allowed": False,
        "detached_process_allowed": False,
        "background_process_allowed": False,
        "network_allowed": False,
        "dns_allowed": False,
        "tcp_allowed": False,
        "udp_allowed": False,
        "loopback_allowed": False,
        "proxy_allowed": False,
        "remote_named_pipe_allowed": False,
        "max_runtime_seconds": MAX_RUNTIME_SECONDS,
        "max_memory_mb": MAX_MEMORY_MB,
        "max_output_bytes": MAX_OUTPUT_BYTES,
        "max_process_count": MAX_PROCESS_COUNT,
        "max_child_process_count": MAX_CHILD_PROCESS_COUNT,
        "physical_windows_sandbox_verified": False,
        "restricted_token_created": False,
        "job_object_created": False,
        "read_only_mounts_created": False,
        "network_isolation_physically_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "process_spawned": False,
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
    "MOUNT_SCHEMA",
    "ENV_SCHEMA",
    "PROCESS_SCHEMA",
    "NETWORK_SCHEMA",
    "PREFLIGHT_SCHEMA",
    "POLICY_SCHEMA",
    "SANDBOX_MODE",
    "PROCESS_POLICY",
    "NETWORK_POLICY",
    "FILESYSTEM_POLICY",
    "PATH_LOOKUP_POLICY",
    "REQUIRED_ENVIRONMENT",
    "FORBIDDEN_ENVIRONMENT_KEYS",
    "MAX_RUNTIME_SECONDS",
    "MAX_MEMORY_MB",
    "MAX_OUTPUT_BYTES",
    "MAX_PROCESS_COUNT",
    "MAX_CHILD_PROCESS_COUNT",
    "OfflineBuildSandboxError",
    "build_input_mount_contract",
    "build_environment_scrub_contract",
    "build_process_allowlist_contract",
    "build_network_deny_contract",
    "build_sandbox_preflight",
    "offline_build_sandbox_policy",
]
