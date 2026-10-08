"""AION Windows Installation Manifest + Local Agent Package Attestation V1.

Pure, non-installing supply-chain boundary for the future Windows local agent.

This layer defines and verifies:
- a closed installation file manifest;
- package/archive, SBOM and provenance digests;
- an external package-release Ed25519 signature;
- externally attested Windows code-signing/Authenticode evidence;
- anti-downgrade upgrade rules;
- uninstall/rollback manifest with evidence preservation.

It does NOT:
- build an executable;
- install/copy/delete any file;
- modify Windows startup/registry/ACL;
- create a service or Scheduled Task;
- spawn a process;
- load credentials/private keys;
- open network transport;
- call GitHub;
- perform any repository mutation.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


SCHEMA = "ATLASQUANT_AION_WINDOWS_INSTALLATION_MANIFEST_PACKAGE_ATTESTATION_V1"
INSTALL_MANIFEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_INSTALLATION_MANIFEST_V1"
PACKAGE_ATTESTATION_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_PACKAGE_ATTESTATION_V1"
UPGRADE_PREFLIGHT_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_UPGRADE_PREFLIGHT_V1"
UNINSTALL_MANIFEST_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_UNINSTALL_MANIFEST_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_LOCAL_AGENT_PACKAGE_POLICY_V1"

PACKAGE_FAMILY = "AtlasQuant.AION.RepositoryMutationRuntime"
PACKAGE_CHANNEL = "OWNER_LOCAL_OFFLINE"
TARGET_PLATFORM = "WINDOWS"
TARGET_ARCH = "X86_64"
SERVICE_MODE = "CURRENT_USER_LOGON_AGENT"
MANIFEST_SIGNATURE_CONTEXT = b"ATLASQUANT:AION:WINDOWS_LOCAL_AGENT:PACKAGE_MANIFEST:"

REQUIRED_PACKAGE_ROLES = (
    "AGENT_ENTRYPOINT",
    "REPOSITORY_MUTATION_RUNTIME",
    "RUNTIME_HARDENING",
    "PROCESS_ISOLATION",
    "HEALTH_IPC_DESCRIPTOR",
    "RUNTIME_POLICY",
    "UNINSTALL_DESCRIPTOR",
)
ROLE_DESTINATIONS = {
    "AGENT_ENTRYPOINT": "agent/aion_repository_mutation_agent.py",
    "REPOSITORY_MUTATION_RUNTIME":
        "lib/atlasquant_aion_repository_mutation_offline_runtime_v1.py",
    "RUNTIME_HARDENING":
        "lib/atlasquant_aion_repository_mutation_local_runtime_hardening_v1.py",
    "PROCESS_ISOLATION":
        "lib/atlasquant_aion_windows_local_service_crash_isolation_v1.py",
    "HEALTH_IPC_DESCRIPTOR": "config/health-ipc-v1.json",
    "RUNTIME_POLICY": "config/runtime-policy-v1.json",
    "UNINSTALL_DESCRIPTOR": "config/uninstall-v1.json",
}
ALLOWED_FILE_SUFFIXES = (".py", ".json")
FORBIDDEN_PATH_SEGMENTS = (
    ".git",
    ".github",
    "__pycache__",
    "secrets",
    "credentials",
    "tokens",
    "keys",
)
MAX_PACKAGE_FILES = 32
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_BYTES = 512 * 1024 * 1024

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


class PackageManifestError(ValueError):
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


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise PackageManifestError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise PackageManifestError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def _version_tuple(value: Any) -> tuple[int, int, int, str]:
    text = _clean(value, 80)
    match = _SEMVER_RE.fullmatch(text)
    if not match:
        raise PackageManifestError("PACKAGE_VERSION_INVALID")
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        match.group(4) or "",
    )


def _normalized_relative_path(value: Any) -> str:
    raw = str(value or "")
    if not raw or raw != raw.strip() or "\x00" in raw:
        raise PackageManifestError("PACKAGE_PATH_INVALID")
    if "\\" in raw or ":" in raw or raw.startswith("/"):
        raise PackageManifestError("PACKAGE_PATH_MUST_BE_RELATIVE_POSIX")
    path = PurePosixPath(raw)
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise PackageManifestError("PACKAGE_PATH_TRAVERSAL_FORBIDDEN")
    lowered = [part.casefold() for part in parts]
    if any(part in FORBIDDEN_PATH_SEGMENTS for part in lowered):
        raise PackageManifestError("PACKAGE_PATH_FORBIDDEN_SEGMENT")
    if path.suffix.casefold() not in ALLOWED_FILE_SUFFIXES:
        raise PackageManifestError("PACKAGE_FILE_SUFFIX_NOT_ALLOWED")
    return str(path)


def _public_key_bytes(public_key_b64: Any) -> bytes:
    text = _clean(public_key_b64, 8192)
    if not text:
        raise PackageManifestError("PACKAGE_SIGNER_PUBLIC_KEY_REQUIRED")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise PackageManifestError("PACKAGE_SIGNER_PUBLIC_KEY_INVALID") from exc
    if len(raw) != 32:
        raise PackageManifestError("PACKAGE_SIGNER_PUBLIC_KEY_LENGTH_INVALID")
    return raw


def package_signer_fingerprint(public_key_b64: Any) -> str:
    raw = _public_key_bytes(public_key_b64)
    return "sha256:" + sha256(raw).hexdigest()


def _normalize_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    role = _clean(raw.get("role"), 100).upper()
    if role not in REQUIRED_PACKAGE_ROLES:
        raise PackageManifestError("PACKAGE_ROLE_INVALID")
    path = _normalized_relative_path(raw.get("path"))
    if path != ROLE_DESTINATIONS[role]:
        raise PackageManifestError("PACKAGE_ROLE_PATH_MISMATCH:" + role)

    file_digest = _sha256(raw.get("sha256"))
    if not file_digest:
        raise PackageManifestError("PACKAGE_FILE_DIGEST_REQUIRED:" + role)
    try:
        size = int(raw.get("size_bytes"))
    except Exception as exc:
        raise PackageManifestError("PACKAGE_FILE_SIZE_INVALID:" + role) from exc
    if size <= 0 or size > MAX_FILE_BYTES:
        raise PackageManifestError("PACKAGE_FILE_SIZE_INVALID:" + role)

    contains_credentials = raw.get("contains_credentials") is True
    contains_private_key = raw.get("contains_private_key") is True
    contains_secret_locator = raw.get("contains_secret_locator") is True
    contains_network_endpoint = raw.get("contains_network_endpoint") is True
    if contains_credentials:
        raise PackageManifestError("PACKAGE_CREDENTIAL_MATERIAL_FORBIDDEN:" + role)
    if contains_private_key:
        raise PackageManifestError("PACKAGE_PRIVATE_KEY_MATERIAL_FORBIDDEN:" + role)
    if contains_secret_locator:
        raise PackageManifestError("PACKAGE_SECRET_LOCATOR_FORBIDDEN:" + role)
    if contains_network_endpoint:
        raise PackageManifestError("PACKAGE_NETWORK_ENDPOINT_FORBIDDEN:" + role)

    return {
        "role": role,
        "path": path,
        "sha256": file_digest,
        "size_bytes": size,
        "executable": raw.get("executable") is True,
        "contains_credentials": False,
        "contains_private_key": False,
        "contains_secret_locator": False,
        "contains_network_endpoint": False,
    }


def build_installation_manifest(
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    package_version: Any,
    build_id: Any,
    build_commit_sha: Any,
    minimum_windows_build: int,
    python_runtime_version: Any,
    created_at: Any,
) -> dict[str, Any]:
    """Build a closed, exact package file manifest."""
    blockers: list[str] = []
    try:
        version = _clean(package_version, 80)
        _version_tuple(version)
    except PackageManifestError as exc:
        version = ""
        blockers.append(exc.code)

    build = _identity(build_id, 180)
    commit = _clean(build_commit_sha, 60)
    if not build:
        blockers.append("BUILD_ID_REQUIRED")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        blockers.append("BUILD_COMMIT_SHA_INVALID")
    try:
        windows_build = int(minimum_windows_build)
        if windows_build < 22000:
            blockers.append("MINIMUM_WINDOWS_BUILD_TOO_OLD")
    except Exception:
        windows_build = 0
        blockers.append("MINIMUM_WINDOWS_BUILD_INVALID")

    python_version = _clean(python_runtime_version, 40)
    if not re.fullmatch(r"3\.12\.[0-9]+", python_version):
        blockers.append("PINNED_PYTHON_RUNTIME_VERSION_REQUIRED")

    try:
        created = _aware(created_at, "MANIFEST_CREATED_AT")
    except PackageManifestError as exc:
        created = None
        blockers.append(exc.code)

    raw_entries = list(entries or [])
    if len(raw_entries) != len(REQUIRED_PACKAGE_ROLES):
        blockers.append("EXACT_REQUIRED_PACKAGE_FILE_COUNT_REQUIRED")
    if len(raw_entries) > MAX_PACKAGE_FILES:
        blockers.append("PACKAGE_FILE_COUNT_LIMIT_EXCEEDED")

    normalized: list[dict[str, Any]] = []
    for raw in raw_entries:
        try:
            if not isinstance(raw, Mapping):
                raise PackageManifestError("PACKAGE_ENTRY_INVALID")
            normalized.append(_normalize_entry(raw))
        except PackageManifestError as exc:
            blockers.append(exc.code)

    roles = [row["role"] for row in normalized]
    paths = [row["path"].casefold() for row in normalized]
    if len(set(roles)) != len(roles):
        blockers.append("DUPLICATE_PACKAGE_ROLE")
    if len(set(paths)) != len(paths):
        blockers.append("DUPLICATE_PACKAGE_PATH")
    if set(roles) != set(REQUIRED_PACKAGE_ROLES):
        blockers.append("REQUIRED_PACKAGE_ROLES_MISMATCH")

    total_size = sum(row["size_bytes"] for row in normalized)
    if total_size <= 0 or total_size > MAX_PACKAGE_BYTES:
        blockers.append("PACKAGE_TOTAL_SIZE_INVALID")

    entrypoint = [
        row for row in normalized if row["role"] == "AGENT_ENTRYPOINT"
    ]
    if len(entrypoint) == 1 and entrypoint[0]["executable"] is not True:
        blockers.append("AGENT_ENTRYPOINT_EXECUTABLE_FLAG_REQUIRED")
    for row in normalized:
        if row["role"] != "AGENT_ENTRYPOINT" and row["executable"] is True:
            blockers.append("UNEXPECTED_EXECUTABLE_PACKAGE_FILE:" + row["role"])

    blockers = list(dict.fromkeys(blockers))
    files = sorted(normalized, key=lambda row: row["role"])
    material = {
        "package_family": PACKAGE_FAMILY,
        "package_channel": PACKAGE_CHANNEL,
        "package_version": version,
        "build_id": build,
        "build_commit_sha": commit,
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "service_mode": SERVICE_MODE,
        "minimum_windows_build": windows_build,
        "python_runtime_version": python_version,
        "created_at": created.isoformat() if created else "",
        "files": files,
        "total_size_bytes": total_size,
    }
    return {
        "schema": INSTALL_MANIFEST_SCHEMA,
        "state": "INSTALLATION_MANIFEST_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "manifest_digest": _digest(material) if not blockers else "",
        "closed_file_inventory": True,
        "extra_files_allowed": False,
        "credential_material_present": False,
        "private_key_material_present": False,
        "network_endpoint_material_present": False,
        "filesystem_modified": False,
        "package_built_by_this_module": False,
        "package_installed": False,
        "process_spawned": False,
    }


def build_package_attestation(
    manifest: Mapping[str, Any] | None,
    *,
    archive_digest: Any,
    sbom_digest: Any,
    build_provenance_digest: Any,
    dependency_lock_digest: Any,
    package_signer_public_key_b64: Any,
    expected_package_signer_fingerprint: Any,
    detached_signature_b64: Any,
    authenticode_binary_digest: Any,
    authenticode_evidence_digest: Any,
    authenticode_signature_verified: bool,
    authenticode_trusted_chain_verified: bool,
    authenticode_timestamp_verified: bool,
    authenticode_publisher_match_verified: bool,
    release_review_digest: Any,
    attested_at: Any,
) -> dict[str, Any]:
    """Verify release signature + externally observed Authenticode evidence."""
    row = dict(manifest or {})
    blockers: list[str] = []

    if row.get("schema") != INSTALL_MANIFEST_SCHEMA:
        blockers.append("INSTALLATION_MANIFEST_SCHEMA_MISMATCH")
    if row.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("READY_INSTALLATION_MANIFEST_REQUIRED")
    manifest_digest = _sha256(row.get("manifest_digest"))
    if not manifest_digest:
        blockers.append("INSTALLATION_MANIFEST_DIGEST_REQUIRED")

    archive = _sha256(archive_digest)
    sbom = _sha256(sbom_digest)
    provenance = _sha256(build_provenance_digest)
    lock_digest = _sha256(dependency_lock_digest)
    binary_digest = _sha256(authenticode_binary_digest)
    authenticode_evidence = _sha256(authenticode_evidence_digest)
    release_review = _sha256(release_review_digest)
    for label, value in (
        ("ARCHIVE_DIGEST_REQUIRED", archive),
        ("SBOM_DIGEST_REQUIRED", sbom),
        ("BUILD_PROVENANCE_DIGEST_REQUIRED", provenance),
        ("DEPENDENCY_LOCK_DIGEST_REQUIRED", lock_digest),
        ("AUTHENTICODE_BINARY_DIGEST_REQUIRED", binary_digest),
        ("AUTHENTICODE_EVIDENCE_DIGEST_REQUIRED", authenticode_evidence),
        ("RELEASE_REVIEW_DIGEST_REQUIRED", release_review),
    ):
        if not value:
            blockers.append(label)

    try:
        raw_key = _public_key_bytes(package_signer_public_key_b64)
        signer_fingerprint = "sha256:" + sha256(raw_key).hexdigest()
    except PackageManifestError as exc:
        raw_key = b""
        signer_fingerprint = ""
        blockers.append(exc.code)

    expected_fingerprint = _sha256(expected_package_signer_fingerprint)
    if not expected_fingerprint:
        blockers.append("EXPECTED_PACKAGE_SIGNER_FINGERPRINT_REQUIRED")
    elif signer_fingerprint and signer_fingerprint != expected_fingerprint:
        blockers.append("PACKAGE_SIGNER_FINGERPRINT_MISMATCH")

    try:
        raw_signature = base64.b64decode(
            _clean(detached_signature_b64, 8192),
            validate=True,
        )
        if len(raw_signature) != 64:
            blockers.append("PACKAGE_DETACHED_SIGNATURE_LENGTH_INVALID")
    except Exception:
        raw_signature = b""
        blockers.append("PACKAGE_DETACHED_SIGNATURE_INVALID")

    signed_material = {
        "manifest_digest": manifest_digest,
        "archive_digest": archive,
        "sbom_digest": sbom,
        "build_provenance_digest": provenance,
        "dependency_lock_digest": lock_digest,
        "package_family": row.get("package_family"),
        "package_version": row.get("package_version"),
        "build_id": row.get("build_id"),
        "build_commit_sha": row.get("build_commit_sha"),
    }
    release_payload_digest = _digest(signed_material)
    release_signature_verified = False
    if not blockers and raw_key and raw_signature:
        try:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                raw_signature,
                MANIFEST_SIGNATURE_CONTEXT
                + release_payload_digest.encode("ascii"),
            )
            release_signature_verified = True
        except InvalidSignature:
            blockers.append("PACKAGE_DETACHED_SIGNATURE_NOT_VERIFIED")
        except Exception:
            blockers.append("PACKAGE_DETACHED_SIGNATURE_VERIFICATION_FAILED")

    for label, flag in (
        ("AUTHENTICODE_SIGNATURE_REQUIRED", authenticode_signature_verified),
        ("AUTHENTICODE_TRUSTED_CHAIN_REQUIRED", authenticode_trusted_chain_verified),
        ("AUTHENTICODE_TIMESTAMP_REQUIRED", authenticode_timestamp_verified),
        ("AUTHENTICODE_PUBLISHER_MATCH_REQUIRED", authenticode_publisher_match_verified),
    ):
        if flag is not True:
            blockers.append(label)

    try:
        attested = _aware(attested_at, "PACKAGE_ATTESTED_AT")
    except PackageManifestError as exc:
        attested = None
        blockers.append(exc.code)

    blockers = list(dict.fromkeys(blockers))
    material = {
        **signed_material,
        "package_signer_fingerprint": signer_fingerprint,
        "release_payload_digest": release_payload_digest,
        "release_signature_verified": release_signature_verified,
        "authenticode_binary_digest": binary_digest,
        "authenticode_evidence_digest": authenticode_evidence,
        "authenticode_signature_verified": authenticode_signature_verified is True,
        "authenticode_trusted_chain_verified":
            authenticode_trusted_chain_verified is True,
        "authenticode_timestamp_verified": authenticode_timestamp_verified is True,
        "authenticode_publisher_match_verified":
            authenticode_publisher_match_verified is True,
        "release_review_digest": release_review,
        "attested_at": attested.isoformat() if attested else "",
    }
    return {
        "schema": PACKAGE_ATTESTATION_SCHEMA,
        "state": "PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "package_attestation_digest": _digest(material) if not blockers else "",
        "manifest_signature_verified": release_signature_verified,
        "package_installed": False,
        "files_copied": False,
        "startup_entry_created": False,
        "windows_acl_modified": False,
        "windows_registry_modified": False,
        "scheduled_task_installed": False,
        "windows_service_installed": False,
        "process_spawned": False,
        "private_signing_key_loaded": False,
        "credential_material_loaded": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_performed": False,
    }


def build_upgrade_preflight(
    current_manifest: Mapping[str, Any] | None,
    candidate_manifest: Mapping[str, Any] | None,
    candidate_attestation: Mapping[str, Any] | None,
    *,
    current_package_attestation_digest: Any,
    rollback_archive_digest: Any,
    rollback_manifest_digest: Any,
    owner_approved_downgrade: bool = False,
) -> dict[str, Any]:
    """Fail closed on downgrade and unverified package transition."""
    current = dict(current_manifest or {})
    candidate = dict(candidate_manifest or {})
    attestation = dict(candidate_attestation or {})
    blockers: list[str] = []

    if current.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("CURRENT_INSTALLATION_MANIFEST_REQUIRED")
    if candidate.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("CANDIDATE_INSTALLATION_MANIFEST_REQUIRED")
    if attestation.get("state") != "PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED":
        blockers.append("CANDIDATE_PACKAGE_ATTESTATION_REQUIRED")
    if _sha256(attestation.get("manifest_digest")) != _sha256(
        candidate.get("manifest_digest")
    ):
        blockers.append("CANDIDATE_ATTESTATION_MANIFEST_BINDING_MISMATCH")

    current_attestation = _sha256(current_package_attestation_digest)
    rollback_archive = _sha256(rollback_archive_digest)
    rollback_manifest = _sha256(rollback_manifest_digest)
    if not current_attestation:
        blockers.append("CURRENT_PACKAGE_ATTESTATION_DIGEST_REQUIRED")
    if not rollback_archive:
        blockers.append("ROLLBACK_ARCHIVE_DIGEST_REQUIRED")
    if not rollback_manifest:
        blockers.append("ROLLBACK_MANIFEST_DIGEST_REQUIRED")

    try:
        current_version = _version_tuple(current.get("package_version"))
        candidate_version = _version_tuple(candidate.get("package_version"))
        is_downgrade = candidate_version[:3] < current_version[:3]
        is_same = candidate_version[:3] == current_version[:3]
    except PackageManifestError as exc:
        blockers.append(exc.code)
        current_version = (0, 0, 0, "")
        candidate_version = (0, 0, 0, "")
        is_downgrade = False
        is_same = False

    if is_downgrade:
        blockers.append("PACKAGE_DOWNGRADE_FORBIDDEN")
    if is_same and _sha256(candidate.get("manifest_digest")) != _sha256(
        current.get("manifest_digest")
    ):
        blockers.append("SAME_VERSION_DIFFERENT_MANIFEST_FORBIDDEN")
    if owner_approved_downgrade is True:
        # V1 intentionally has no downgrade ceremony. A boolean must not bypass it.
        blockers.append("BOOLEAN_DOWNGRADE_OVERRIDE_FORBIDDEN")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "current_manifest_digest": _sha256(current.get("manifest_digest")),
        "candidate_manifest_digest": _sha256(candidate.get("manifest_digest")),
        "candidate_package_attestation_digest": _sha256(
            attestation.get("package_attestation_digest")
        ),
        "current_package_attestation_digest": current_attestation,
        "current_version": current.get("package_version"),
        "candidate_version": candidate.get("package_version"),
        "rollback_archive_digest": rollback_archive,
        "rollback_manifest_digest": rollback_manifest,
    }
    return {
        "schema": UPGRADE_PREFLIGHT_SCHEMA,
        "state": "UPGRADE_PACKAGE_READY_FOR_FUTURE_INSTALLATION_REVIEW"
        if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "upgrade_preflight_digest": _digest(material) if not blockers else "",
        "downgrade_allowed": False,
        "installation_authorized": False,
        "package_installed": False,
        "rollback_executed": False,
        "filesystem_modified": False,
        "process_spawned": False,
    }


def build_uninstall_manifest(
    installation_manifest: Mapping[str, Any] | None,
    package_attestation: Mapping[str, Any] | None,
    *,
    startup_entry_digest: Any,
    owner_data_backup_policy_digest: Any,
    uninstall_review_digest: Any,
) -> dict[str, Any]:
    """Build a removal plan that preserves owner data/evidence by default."""
    install = dict(installation_manifest or {})
    package = dict(package_attestation or {})
    blockers: list[str] = []

    if install.get("state") != "INSTALLATION_MANIFEST_READY":
        blockers.append("READY_INSTALLATION_MANIFEST_REQUIRED")
    if package.get("state") != "PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED":
        blockers.append("ATTESTED_PACKAGE_REQUIRED")
    if _sha256(package.get("manifest_digest")) != _sha256(
        install.get("manifest_digest")
    ):
        blockers.append("PACKAGE_INSTALL_MANIFEST_BINDING_MISMATCH")

    startup_digest = _sha256(startup_entry_digest)
    backup_policy = _sha256(owner_data_backup_policy_digest)
    review = _sha256(uninstall_review_digest)
    if not startup_digest:
        blockers.append("STARTUP_ENTRY_DIGEST_REQUIRED")
    if not backup_policy:
        blockers.append("OWNER_DATA_BACKUP_POLICY_DIGEST_REQUIRED")
    if not review:
        blockers.append("UNINSTALL_REVIEW_DIGEST_REQUIRED")

    removal_paths = sorted(
        row["path"] for row in install.get("files", [])
        if isinstance(row, Mapping)
    )
    material = {
        "package_family": install.get("package_family"),
        "package_version": install.get("package_version"),
        "installation_manifest_digest": _sha256(install.get("manifest_digest")),
        "package_attestation_digest": _sha256(
            package.get("package_attestation_digest")
        ),
        "startup_entry_digest": startup_digest,
        "owner_data_backup_policy_digest": backup_policy,
        "uninstall_review_digest": review,
        "package_file_removal_paths": removal_paths,
        "runtime_database_action": "PRESERVE",
        "audit_evidence_action": "PRESERVE",
        "owner_key_enrollment_action": "PRESERVE_UNTIL_SEPARATE_OWNER_PURGE",
        "kill_switch_action": "FORCE_ENABLED_BEFORE_UNINSTALL",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": UNINSTALL_MANIFEST_SCHEMA,
        "state": "UNINSTALL_MANIFEST_READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "uninstall_manifest_digest": _digest(material) if not blockers else "",
        "owner_data_deleted_by_default": False,
        "runtime_database_deleted_by_default": False,
        "audit_evidence_deleted_by_default": False,
        "owner_key_enrollment_deleted_by_default": False,
        "separate_owner_purge_ceremony_required": True,
        "uninstall_executed": False,
        "files_deleted": False,
        "startup_entry_removed": False,
        "process_stopped_by_this_module": False,
        "filesystem_modified": False,
    }


def windows_package_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "package_family": PACKAGE_FAMILY,
        "package_channel": PACKAGE_CHANNEL,
        "target_platform": TARGET_PLATFORM,
        "target_arch": TARGET_ARCH,
        "service_mode": SERVICE_MODE,
        "required_package_roles": list(REQUIRED_PACKAGE_ROLES),
        "closed_file_inventory_required": True,
        "extra_files_allowed": False,
        "exact_role_path_binding_required": True,
        "sha256_per_file_required": True,
        "sbom_required": True,
        "build_provenance_required": True,
        "dependency_lock_digest_required": True,
        "release_review_digest_required": True,
        "detached_release_signature_required": True,
        "authenticode_signature_required": True,
        "authenticode_trusted_chain_required": True,
        "authenticode_timestamp_required": True,
        "authenticode_publisher_match_required": True,
        "package_credentials_forbidden": True,
        "package_private_keys_forbidden": True,
        "package_secret_locators_forbidden": True,
        "package_network_endpoints_forbidden": True,
        "anti_downgrade_required": True,
        "boolean_downgrade_override_allowed": False,
        "same_version_different_manifest_allowed": False,
        "rollback_archive_required_before_upgrade": True,
        "owner_data_preserved_on_uninstall_by_default": True,
        "runtime_database_preserved_on_uninstall_by_default": True,
        "audit_evidence_preserved_on_uninstall_by_default": True,
        "separate_owner_purge_required": True,
        "package_built_by_this_module": False,
        "package_installed": False,
        "files_copied": False,
        "windows_service_installed": False,
        "scheduled_task_installed": False,
        "startup_entry_created": False,
        "windows_acl_modified": False,
        "windows_registry_modified": False,
        "process_spawned": False,
        "uninstall_executed": False,
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
    "INSTALL_MANIFEST_SCHEMA",
    "PACKAGE_ATTESTATION_SCHEMA",
    "UPGRADE_PREFLIGHT_SCHEMA",
    "UNINSTALL_MANIFEST_SCHEMA",
    "POLICY_SCHEMA",
    "PACKAGE_FAMILY",
    "PACKAGE_CHANNEL",
    "TARGET_PLATFORM",
    "TARGET_ARCH",
    "SERVICE_MODE",
    "MANIFEST_SIGNATURE_CONTEXT",
    "REQUIRED_PACKAGE_ROLES",
    "ROLE_DESTINATIONS",
    "PackageManifestError",
    "package_signer_fingerprint",
    "build_installation_manifest",
    "build_package_attestation",
    "build_upgrade_preflight",
    "build_uninstall_manifest",
    "windows_package_policy",
]
