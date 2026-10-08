"""AION Secure Desktop Runtime Blueprint V1.

Pure planning/readiness contract for the future Windows companion agent.
It encodes the architecture required before any PC-only implementation begins.

The preferred runtime model is a per-user desktop agent, not a SYSTEM service.
That choice keeps UI application launch, future microphone access and owner
session identity inside the interactive Windows user session.

No installer, service, listener, process launch, registry mutation, startup
entry, IPC endpoint, application resolution or external action is created here.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


SCHEMA = "ATLASQUANT_AION_SECURE_DESKTOP_RUNTIME_BLUEPRINT_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_SECURE_DESKTOP_RUNTIME_PLAN_V1"
PLAN_VERIFY_SCHEMA = "ATLASQUANT_AION_SECURE_DESKTOP_RUNTIME_PLAN_VERIFY_V1"
INSTALLED_ATTESTATION_SCHEMA = "ATLASQUANT_AION_SECURE_DESKTOP_RUNTIME_INSTALLED_ATTESTATION_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_SECURE_DESKTOP_RUNTIME_POLICY_V1"

PLATFORM = "WINDOWS"
AGENT_MODEL = "PER_USER_DESKTOP_AGENT"
RUNTIME_IDENTITY = "CURRENT_USER"
STARTUP_MODE = "USER_LOGIN"
INTERNAL_IPC = "WINDOWS_NAMED_PIPE"
UPDATE_MODE = "SIGNED_MANUAL_UPDATE"

BRIDGE_STRATEGIES = (
    "LOOPBACK_BRIDGE",
    "CUSTOM_URI_SIGNED_ENVELOPE",
    "NATIVE_SHELL_IPC",
)
OWNER_VERIFICATION_MECHANISMS = (
    "WINDOWS_HELLO",
    "FIDO2",
    "OWNER_SESSION_SIGNATURE",
)
LOCAL_SECRET_STORAGE_MODES = (
    "WINDOWS_DPAPI_CURRENT_USER",
    "NONE_REQUIRED",
)

REQUIRED_COMPONENTS = (
    "TRUSTED_OWNER_HOST_BRIDGE",
    "OWNER_IDENTITY_VERIFIER",
    "REPLAY_REGISTRY",
    "APP_ALLOWLIST_RESOLVER",
    "PROCESS_LAUNCH_ADAPTER",
    "MEDIA_SESSION_ADAPTER",
    "POSTCONDITION_OBSERVER",
    "AUDIT_JOURNAL",
    "RECEIPT_PIPELINE",
    "KILL_SWITCH",
    "UNINSTALL_ROLLBACK",
)

THREAT_MODEL = (
    {
        "threat": "REMOTE_COMMAND_INJECTION",
        "required_control": "NO_REMOTE_OR_LAN_LISTENER",
    },
    {
        "threat": "ARBITRARY_EXECUTABLE_LAUNCH",
        "required_control": "LOGICAL_APP_ALLOWLIST_ONLY",
    },
    {
        "threat": "SHELL_COMMAND_INJECTION",
        "required_control": "NO_SHELL_OR_COMMAND_LINE_EXECUTION",
    },
    {
        "threat": "OWNER_IDENTITY_SPOOFING",
        "required_control": "FRESH_CRYPTOGRAPHIC_OWNER_VERIFICATION",
    },
    {
        "threat": "REQUEST_REPLAY",
        "required_control": "DURABLE_SINGLE_USE_NONCE_REGISTRY",
    },
    {
        "threat": "UNSIGNED_AGENT_REPLACEMENT",
        "required_control": "CODE_SIGNING_AND_BINARY_DIGEST_VERIFICATION",
    },
    {
        "threat": "IPC_HIJACK",
        "required_control": "LOCAL_CHANNEL_ACCESS_CONTROL_AND_EXACT_PROTOCOL",
    },
    {
        "threat": "RECEIPT_FALSIFICATION",
        "required_control": "APPEND_ONLY_AUDIT_JOURNAL_AND_RECEIPT_DIGESTS",
    },
    {
        "threat": "PRIVILEGE_ESCALATION",
        "required_control": "CURRENT_USER_NO_SYSTEM_RUNTIME",
    },
    {
        "threat": "SILENT_PERSISTENCE",
        "required_control": "EXPLICIT_USER_LOGIN_STARTUP_AND_KILL_SWITCH",
    },
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 300) -> str:
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


def _identity(value: Any, limit: int = 160) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _bool(raw: Mapping[str, Any], key: str) -> bool:
    return raw.get(key) is True


def _false(raw: Mapping[str, Any], key: str) -> bool:
    return raw.get(key) is False


def _plan_material(plan: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(plan)
    raw.pop("plan_digest", None)
    return raw


def desktop_runtime_blueprint() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "platform": PLATFORM,
        "agent_model": AGENT_MODEL,
        "runtime_identity": RUNTIME_IDENTITY,
        "startup_mode": STARTUP_MODE,
        "internal_ipc": INTERNAL_IPC,
        "update_mode": UPDATE_MODE,
        "bridge_strategies": list(BRIDGE_STRATEGIES),
        "owner_verification_mechanisms": list(OWNER_VERIFICATION_MECHANISMS),
        "required_components": list(REQUIRED_COMPONENTS),
        "threat_model": [dict(item) for item in THREAT_MODEL],
        "runs_as_system": False,
        "requires_runtime_elevation": False,
        "remote_listener_allowed": False,
        "lan_listener_allowed": False,
        "arbitrary_executable_allowed": False,
        "shell_allowed": False,
        "physical_install_started": False,
        "runtime_process_started": False,
        "startup_entry_created": False,
        "ipc_endpoint_created": False,
        "application_launched": False,
        "network_called": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


def build_desktop_runtime_plan(raw_plan: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a design plan only. Positive state means ready for PC implementation."""
    raw = dict(raw_plan or {})
    blockers: list[str] = []

    platform = _clean(raw.get("platform"), 40).upper()
    agent_model = _clean(raw.get("agent_model"), 80).upper()
    runtime_identity = _clean(raw.get("runtime_identity"), 80).upper()
    startup_mode = _clean(raw.get("startup_mode"), 80).upper()
    bridge = _clean(raw.get("bridge_strategy"), 80).upper()
    internal_ipc = _clean(raw.get("internal_ipc"), 80).upper()
    update_mode = _clean(raw.get("update_mode"), 80).upper()
    secret_storage = _clean(raw.get("local_secret_storage"), 80).upper()

    if platform != PLATFORM:
        blockers.append("WINDOWS_PLATFORM_REQUIRED")
    if agent_model != AGENT_MODEL:
        blockers.append("PER_USER_DESKTOP_AGENT_REQUIRED")
    if runtime_identity != RUNTIME_IDENTITY:
        blockers.append("CURRENT_USER_RUNTIME_REQUIRED")
    if startup_mode != STARTUP_MODE:
        blockers.append("USER_LOGIN_STARTUP_REQUIRED")
    if bridge not in BRIDGE_STRATEGIES:
        blockers.append("APPROVED_BRIDGE_STRATEGY_REQUIRED")
    if internal_ipc != INTERNAL_IPC:
        blockers.append("WINDOWS_NAMED_PIPE_INTERNAL_IPC_REQUIRED")
    if update_mode != UPDATE_MODE:
        blockers.append("SIGNED_MANUAL_UPDATE_V1_REQUIRED")
    if secret_storage not in LOCAL_SECRET_STORAGE_MODES:
        blockers.append("LOCAL_SECRET_STORAGE_MODE_INVALID")

    required_true = (
        "bridge_local_only",
        "bridge_origin_or_signed_envelope_validation",
        "exact_protocol_version_required",
        "internal_ipc_acl_current_user_only",
        "signed_binary_required",
        "code_signing_chain_verification_required",
        "binary_digest_verification_required",
        "fresh_owner_verification_required",
        "durable_single_use_replay_registry_required",
        "logical_app_allowlist_only",
        "postcondition_observer_required",
        "append_only_audit_journal_required",
        "audit_receipt_contract_required",
        "update_signature_verification_required",
        "kill_switch_required",
        "uninstall_path_required",
        "rollback_plan_required",
        "crash_recovery_plan_required",
        "least_privilege_required",
    )
    for key in required_true:
        if not _bool(raw, key):
            blockers.append("REQUIRED_CONTROL_MISSING:" + key)

    required_false = (
        "remote_listener_enabled",
        "lan_listener_enabled",
        "runs_as_system",
        "runtime_elevation_required",
        "arbitrary_executable_paths_allowed",
        "shell_execution_allowed",
        "command_line_execution_allowed",
        "credential_export_allowed",
        "raw_process_output_export_allowed",
        "automatic_unknown_retry_allowed",
        "automatic_unknown_reconciliation_allowed",
    )
    for key in required_false:
        if not _false(raw, key):
            blockers.append("FORBIDDEN_CONTROL_ENABLED_OR_UNSET:" + key)

    protocol_version = _identity(raw.get("protocol_version"), 40)
    if protocol_version != "1":
        blockers.append("PROTOCOL_VERSION_1_REQUIRED")

    mechanisms = []
    for item in list(raw.get("owner_verification_mechanisms") or []):
        token = _clean(item, 80).upper()
        if token in OWNER_VERIFICATION_MECHANISMS and token not in mechanisms:
            mechanisms.append(token)
    if not mechanisms:
        blockers.append("OWNER_VERIFICATION_MECHANISM_REQUIRED")

    components = []
    for item in list(raw.get("components") or []):
        token = _clean(item, 120).upper()
        if token and token not in components:
            components.append(token)
    missing_components = [
        item for item in REQUIRED_COMPONENTS if item not in components
    ]
    blockers.extend(
        "REQUIRED_COMPONENT_MISSING:" + item for item in missing_components
    )

    if bridge == "LOOPBACK_BRIDGE":
        if not _bool(raw, "loopback_bind_only"):
            blockers.append("LOOPBACK_BIND_ONLY_REQUIRED")
        if not _bool(raw, "strict_origin_allowlist_required"):
            blockers.append("STRICT_ORIGIN_ALLOWLIST_REQUIRED")
    else:
        if raw.get("loopback_bind_only") is True and bridge != "LOOPBACK_BRIDGE":
            blockers.append("LOOPBACK_CONTROL_MISMATCH")

    if bridge == "CUSTOM_URI_SIGNED_ENVELOPE":
        if not _bool(raw, "signed_envelope_required"):
            blockers.append("SIGNED_URI_ENVELOPE_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "state": "READY_FOR_PC_IMPLEMENTATION" if not blockers else "BLOCKED",
        "blockers": blockers,
        "platform": platform,
        "agent_model": agent_model,
        "runtime_identity": runtime_identity,
        "startup_mode": startup_mode,
        "bridge_strategy": bridge,
        "internal_ipc": internal_ipc,
        "protocol_version": protocol_version,
        "update_mode": update_mode,
        "local_secret_storage": secret_storage,
        "owner_verification_mechanisms": mechanisms,
        "components": components,
        "missing_components": missing_components,
        "security_controls": {
            key: raw.get(key)
            for key in (*required_true, *required_false)
        },
        "loopback_bind_only": raw.get("loopback_bind_only") is True,
        "strict_origin_allowlist_required": (
            raw.get("strict_origin_allowlist_required") is True
        ),
        "signed_envelope_required": raw.get("signed_envelope_required") is True,
        "physical_install_started": False,
        "runtime_process_started": False,
        "startup_entry_created": False,
        "ipc_endpoint_created": False,
        "application_launched": False,
        "network_called": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
        "plan_digest": "",
    }
    plan["plan_digest"] = _digest(_plan_material(plan))
    return plan


def verify_desktop_runtime_plan(
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(plan or {})
    blockers: list[str] = []
    if raw.get("schema") != PLAN_SCHEMA:
        blockers.append("PLAN_SCHEMA_MISMATCH")

    supplied = _sha256(raw.get("plan_digest"))
    expected = _digest(_plan_material(raw))
    if supplied != expected:
        blockers.append("PLAN_DIGEST_MISMATCH")

    if raw.get("state") == "READY_FOR_PC_IMPLEMENTATION":
        if raw.get("blockers"):
            blockers.append("READY_PLAN_CANNOT_HAVE_BLOCKERS")
        if raw.get("missing_components"):
            blockers.append("READY_PLAN_CANNOT_HAVE_MISSING_COMPONENTS")

    for key in (
        "physical_install_started",
        "runtime_process_started",
        "startup_entry_created",
        "ipc_endpoint_created",
        "application_launched",
        "network_called",
        "deploy_executed",
        "core_checkpoint_write",
        "executes_action",
    ):
        if raw.get(key) is not False:
            blockers.append("PLANNING_BOUNDARY_INVALID:" + key)

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PLAN_VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "plan_digest": supplied,
        "executes_action": False,
    }


def pc_implementation_sequence(
    plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    verified = verify_desktop_runtime_plan(plan)
    raw = dict(plan or {})
    if verified["valid"] is not True or raw.get("state") != "READY_FOR_PC_IMPLEMENTATION":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": ["VALID_READY_PLAN_REQUIRED"],
            "steps": [],
            "requires_pc": True,
            "commands_generated": False,
            "executes_action": False,
        }

    steps = [
        {
            "order": 1,
            "id": "PACKAGE_AND_SIGNING_SCAFFOLD",
            "goal": "Create per-user agent package and signing boundary.",
            "requires_pc": True,
        },
        {
            "order": 2,
            "id": "LOCAL_BRIDGE_SPIKE",
            "goal": "Validate selected PWA/native bridge locally without remote exposure.",
            "requires_pc": True,
        },
        {
            "order": 3,
            "id": "OWNER_IDENTITY_BRIDGE",
            "goal": "Bind Windows Hello/FIDO2/owner-session verification to requests.",
            "requires_pc": True,
        },
        {
            "order": 4,
            "id": "DURABLE_REPLAY_REGISTRY",
            "goal": "Implement single-use nonce persistence and replay rejection.",
            "requires_pc": True,
        },
        {
            "order": 5,
            "id": "ALLOWLIST_RESOLVER",
            "goal": "Resolve only approved logical applications locally.",
            "requires_pc": True,
        },
        {
            "order": 6,
            "id": "PHYSICAL_ADAPTER",
            "goal": "Implement low-risk app launch/media adapter without shell authority.",
            "requires_pc": True,
        },
        {
            "order": 7,
            "id": "POSTCONDITION_OBSERVER",
            "goal": "Observe app/media outcomes without inferring success.",
            "requires_pc": True,
        },
        {
            "order": 8,
            "id": "AUDIT_JOURNAL",
            "goal": "Persist append-only outcome receipts and evidence digests.",
            "requires_pc": True,
        },
        {
            "order": 9,
            "id": "KILL_SWITCH_UNINSTALL_ROLLBACK",
            "goal": "Prove disable, uninstall and rollback paths.",
            "requires_pc": True,
        },
        {
            "order": 10,
            "id": "RED_TEAM_AND_INTEGRATION",
            "goal": "Run injection, replay, identity, crash and duplicate-effect tests.",
            "requires_pc": True,
        },
    ]
    return {
        "schema": SCHEMA,
        "state": "PC_IMPLEMENTATION_SEQUENCE_READY",
        "plan_digest": raw.get("plan_digest"),
        "steps": steps,
        "requires_pc": True,
        "commands_generated": False,
        "installer_generated": False,
        "physical_install_started": False,
        "executes_action": False,
    }


def evaluate_installed_runtime_attestation(
    plan: Mapping[str, Any] | None,
    attestation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate future PC evidence; this module never gathers that evidence."""
    verified_plan = verify_desktop_runtime_plan(plan)
    raw_plan = dict(plan or {})
    evidence = dict(attestation or {})
    blockers: list[str] = []

    if verified_plan["valid"] is not True:
        blockers.append("VALID_PLAN_REQUIRED")
    if raw_plan.get("state") != "READY_FOR_PC_IMPLEMENTATION":
        blockers.append("READY_PLAN_REQUIRED")
    if evidence.get("schema") != INSTALLED_ATTESTATION_SCHEMA:
        blockers.append("INSTALLED_ATTESTATION_SCHEMA_MISMATCH")
    if evidence.get("verified") is not True:
        blockers.append("INSTALLED_ATTESTATION_NOT_VERIFIED")
    if _clean(evidence.get("plan_digest"), 90) != _clean(
        raw_plan.get("plan_digest"), 90
    ):
        blockers.append("INSTALLED_PLAN_DIGEST_MISMATCH")

    if _clean(evidence.get("platform"), 40).upper() != PLATFORM:
        blockers.append("INSTALLED_PLATFORM_MISMATCH")
    if _clean(evidence.get("agent_model"), 80).upper() != AGENT_MODEL:
        blockers.append("INSTALLED_AGENT_MODEL_MISMATCH")
    if _clean(evidence.get("runtime_identity"), 80).upper() != RUNTIME_IDENTITY:
        blockers.append("INSTALLED_RUNTIME_IDENTITY_MISMATCH")
    if _clean(evidence.get("bridge_strategy"), 80).upper() != raw_plan.get(
        "bridge_strategy"
    ):
        blockers.append("INSTALLED_BRIDGE_STRATEGY_MISMATCH")
    if _clean(evidence.get("protocol_version"), 40) != "1":
        blockers.append("INSTALLED_PROTOCOL_VERSION_MISMATCH")

    binary_digest = _sha256(evidence.get("binary_digest"))
    evidence_bundle_digest = _sha256(evidence.get("evidence_bundle_digest"))
    if not binary_digest:
        blockers.append("INSTALLED_BINARY_DIGEST_REQUIRED")
    if not evidence_bundle_digest:
        blockers.append("INSTALLED_EVIDENCE_BUNDLE_DIGEST_REQUIRED")
    if not _identity(evidence.get("attestor_identity"), 200):
        blockers.append("INSTALLED_ATTESTOR_IDENTITY_REQUIRED")
    if evidence.get("attestor_signature_verified") is not True:
        blockers.append("INSTALLED_ATTESTOR_SIGNATURE_NOT_VERIFIED")
    if evidence.get("code_signature_verified") is not True:
        blockers.append("INSTALLED_CODE_SIGNATURE_NOT_VERIFIED")
    if not _identity(evidence.get("publisher_identity"), 200):
        blockers.append("INSTALLED_PUBLISHER_IDENTITY_REQUIRED")
    if evidence.get("runs_as_system") is not False:
        blockers.append("INSTALLED_SYSTEM_RUNTIME_FORBIDDEN")
    if evidence.get("runtime_elevated") is not False:
        blockers.append("INSTALLED_ELEVATED_RUNTIME_FORBIDDEN")
    if evidence.get("remote_listener_present") is not False:
        blockers.append("INSTALLED_REMOTE_LISTENER_FORBIDDEN")
    if evidence.get("lan_listener_present") is not False:
        blockers.append("INSTALLED_LAN_LISTENER_FORBIDDEN")
    if evidence.get("local_channel_access_control_verified") is not True:
        blockers.append("INSTALLED_LOCAL_CHANNEL_ACL_NOT_VERIFIED")

    bridge = raw_plan.get("bridge_strategy")
    if bridge == "LOOPBACK_BRIDGE":
        if evidence.get("loopback_only_verified") is not True:
            blockers.append("INSTALLED_LOOPBACK_ONLY_NOT_VERIFIED")
        if evidence.get("strict_origin_allowlist_verified") is not True:
            blockers.append("INSTALLED_ORIGIN_ALLOWLIST_NOT_VERIFIED")
    elif bridge == "CUSTOM_URI_SIGNED_ENVELOPE":
        if evidence.get("signed_uri_envelope_verified") is not True:
            blockers.append("INSTALLED_SIGNED_URI_ENVELOPE_NOT_VERIFIED")
    elif bridge == "NATIVE_SHELL_IPC":
        if evidence.get("native_shell_channel_verified") is not True:
            blockers.append("INSTALLED_NATIVE_SHELL_CHANNEL_NOT_VERIFIED")
    if evidence.get("owner_verification_bridge_verified") is not True:
        blockers.append("INSTALLED_OWNER_VERIFICATION_BRIDGE_NOT_VERIFIED")
    if evidence.get("durable_replay_registry_verified") is not True:
        blockers.append("INSTALLED_REPLAY_REGISTRY_NOT_VERIFIED")
    if evidence.get("single_use_nonce_rejection_verified") is not True:
        blockers.append("INSTALLED_SINGLE_USE_REPLAY_REJECTION_NOT_VERIFIED")
    if evidence.get("allowlist_resolver_verified") is not True:
        blockers.append("INSTALLED_ALLOWLIST_RESOLVER_NOT_VERIFIED")
    if evidence.get("arbitrary_path_launch_possible") is not False:
        blockers.append("INSTALLED_ARBITRARY_PATH_LAUNCH_FORBIDDEN")
    if evidence.get("shell_execution_possible") is not False:
        blockers.append("INSTALLED_SHELL_EXECUTION_FORBIDDEN")
    if evidence.get("append_only_audit_journal_verified") is not True:
        blockers.append("INSTALLED_AUDIT_JOURNAL_NOT_VERIFIED")
    if evidence.get("receipt_pipeline_verified") is not True:
        blockers.append("INSTALLED_RECEIPT_PIPELINE_NOT_VERIFIED")
    if evidence.get("kill_switch_verified") is not True:
        blockers.append("INSTALLED_KILL_SWITCH_NOT_VERIFIED")
    if evidence.get("uninstall_path_verified") is not True:
        blockers.append("INSTALLED_UNINSTALL_NOT_VERIFIED")
    if evidence.get("rollback_path_verified") is not True:
        blockers.append("INSTALLED_ROLLBACK_NOT_VERIFIED")
    if evidence.get("signed_update_verification_verified") is not True:
        blockers.append("INSTALLED_UPDATE_SIGNATURE_VERIFICATION_NOT_VERIFIED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": INSTALLED_ATTESTATION_SCHEMA,
        "state": "INSTALLED_RUNTIME_ATTESTATION_VALID" if not blockers else "BLOCKED",
        "valid": not blockers,
        "blockers": blockers,
        "plan_digest": _clean(raw_plan.get("plan_digest"), 90),
        "binary_digest": binary_digest,
        "evidence_bundle_digest": evidence_bundle_digest,
        "attestor_identity": _clean(evidence.get("attestor_identity"), 200),
        "evidence_gathered_by_this_module": False,
        "installation_performed_by_this_module": False,
        "runtime_started_by_this_module": False,
        "external_action_executed_by_this_module": False,
        "executes_action": False,
    }


def secure_desktop_runtime_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "platform": PLATFORM,
        "agent_model": AGENT_MODEL,
        "runtime_identity": RUNTIME_IDENTITY,
        "per_user_agent_required": True,
        "system_service_v1": False,
        "runtime_elevation": False,
        "remote_listener": False,
        "lan_listener": False,
        "local_bridge_security_required": True,
        "exact_protocol_version_required": True,
        "current_user_ipc_acl_required": True,
        "code_signing_required": True,
        "binary_digest_verification_required": True,
        "fresh_owner_verification_required": True,
        "durable_single_use_replay_registry_required": True,
        "logical_app_allowlist_only": True,
        "arbitrary_executable_paths": False,
        "shell_execution": False,
        "command_line_execution": False,
        "append_only_audit_journal_required": True,
        "outcome_receipt_required": True,
        "automatic_unknown_retry": False,
        "kill_switch_required": True,
        "uninstall_required": True,
        "rollback_required": True,
        "signed_update_verification_required": True,
        "physical_install_started": False,
        "runtime_started": False,
        "application_launched": False,
        "network_called": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "PLAN_VERIFY_SCHEMA",
    "INSTALLED_ATTESTATION_SCHEMA",
    "POLICY_SCHEMA",
    "PLATFORM",
    "AGENT_MODEL",
    "RUNTIME_IDENTITY",
    "STARTUP_MODE",
    "INTERNAL_IPC",
    "UPDATE_MODE",
    "BRIDGE_STRATEGIES",
    "OWNER_VERIFICATION_MECHANISMS",
    "LOCAL_SECRET_STORAGE_MODES",
    "REQUIRED_COMPONENTS",
    "THREAT_MODEL",
    "desktop_runtime_blueprint",
    "build_desktop_runtime_plan",
    "verify_desktop_runtime_plan",
    "pc_implementation_sequence",
    "evaluate_installed_runtime_attestation",
    "secure_desktop_runtime_policy",
]
