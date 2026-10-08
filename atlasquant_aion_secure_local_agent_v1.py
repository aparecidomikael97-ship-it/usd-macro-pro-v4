"""AION Secure Local Agent V1 — non-executing desktop action boundary.

This contract turns an already-planned Owner Experience LOCAL_APPLICATION
request into a bounded logical local-action request and evaluates whether the
trusted desktop adapter has enough evidence to consider dispatch.

It deliberately does NOT:
- resolve executable paths;
- generate shell commands or command-line arguments;
- spawn processes;
- open applications;
- send messages;
- access credentials;
- call the network;
- capture the microphone;
- verify Windows Hello/FIDO2 cryptography itself;
- persist or claim replay nonces;
- change the frozen AION Core;
- deploy anything.

The future signed desktop service must implement the physical adapter and the
trusted OS/replay attestations. This module remains pure and fail-closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_owner_experience_v1 import SCHEMA as OWNER_EXPERIENCE_SCHEMA


SCHEMA = "ATLASQUANT_AION_SECURE_LOCAL_AGENT_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_LOCAL_ACTION_REQUEST_V1"
READINESS_SCHEMA = "ATLASQUANT_AION_LOCAL_DISPATCH_READINESS_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_LOCAL_AGENT_POLICY_V1"

MAX_COMMAND_CHARS = 600
MAX_MEDIA_QUERY_CHARS = 160
MAX_ACTION_WINDOW_SECONDS = 60

SUPPORTED_PLATFORM = "WINDOWS"
SUPPORTED_DEVICE = "DESKTOP"
SUPPORTED_ACTIONS = ("OPEN_APP", "MEDIA_PLAYBACK")

APP_REGISTRY = {
    "chatgpt": {
        "display_name": "ChatGPT",
        "logical_app_id": "CHATGPT",
        "actions": ("OPEN_APP",),
    },
    "whatsapp": {
        "display_name": "WhatsApp",
        "logical_app_id": "WHATSAPP",
        "actions": ("OPEN_APP",),
    },
    "spotify": {
        "display_name": "Spotify",
        "logical_app_id": "SPOTIFY",
        "actions": ("OPEN_APP", "MEDIA_PLAYBACK"),
    },
}

_FORBIDDEN_COMMAND_MARKERS = (
    "&&",
    "||",
    ";",
    "`",
    "$(",
    "powershell",
    "cmd.exe",
    "cmd /",
    "wscript",
    "cscript",
    "rundll32",
    "reg.exe",
    "reg add",
    "schtasks",
    "curl ",
    "wget ",
    "http://",
    "https://",
    "file://",
)

_FORBIDDEN_MATERIAL_KEYS = frozenset({
    "path",
    "executable",
    "binary",
    "command",
    "command_line",
    "argv",
    "args",
    "shell",
    "powershell",
    "url",
    "uri",
    "cwd",
    "environment",
    "env",
    "password",
    "passwd",
    "secret",
    "token",
    "jwt",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "database_url",
    "dsn",
})

_HIGH_RISK_CAPABILITIES = frozenset({
    "SEND_MESSAGE",
    "SEND_EMAIL",
    "FILE_WRITE",
    "FILE_DELETE",
    "SHELL",
    "INSTALL_SOFTWARE",
    "UNINSTALL_SOFTWARE",
    "SYSTEM_SETTINGS",
    "CREDENTIAL_ACCESS",
    "PURCHASE",
    "PAYMENT",
    "TRADING_ORDER",
    "BROWSER_AUTOFILL",
})


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


def _identity(value: Any, limit: int = 160) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _aware_datetime(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError(f"{label} invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return parsed.astimezone(timezone.utc)


def _request_material(request: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(request)
    raw.pop("request_digest", None)
    return raw


def _contains_forbidden_material(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _clean(key, 120).casefold()
            if normalized in _FORBIDDEN_MATERIAL_KEYS:
                return True
            if _contains_forbidden_material(item):
                return True
    elif isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_forbidden_material(item) for item in value)
    return False


def _forbidden_command_marker(text: str) -> str:
    folded = text.casefold()
    for marker in _FORBIDDEN_COMMAND_MARKERS:
        if marker.casefold() in folded:
            return marker
    return ""


def _command_targets(command_text: str) -> list[str]:
    folded = command_text.casefold()
    return [app_id for app_id in APP_REGISTRY if app_id in folded]


def _media_query(command_text: str, target: str) -> str:
    if target != "spotify":
        return ""
    folded = command_text.casefold()
    match = re.search(r"\b(?:toca|tocar)\b\s+(.+)$", folded)
    if not match:
        return ""
    candidate = _clean(match.group(1), MAX_MEDIA_QUERY_CHARS)
    if not candidate:
        return ""
    if _forbidden_command_marker(candidate):
        raise ValueError("forbidden media query material")
    return candidate


def local_app_registry() -> dict[str, Any]:
    """Expose logical capabilities only; never executable/path bindings."""
    return {
        "schema": SCHEMA,
        "platform": SUPPORTED_PLATFORM,
        "device": SUPPORTED_DEVICE,
        "apps": {
            app_id: {
                "display_name": row["display_name"],
                "logical_app_id": row["logical_app_id"],
                "actions": list(row["actions"]),
                "physical_binding_included": False,
                "executable_path_included": False,
                "launch_command_included": False,
                "url_handler_included": False,
            }
            for app_id, row in APP_REGISTRY.items()
        },
        "physical_binding_included": False,
        "executes_action": False,
    }


def _validate_owner_plan(owner_plan: Mapping[str, Any] | None) -> tuple[str, list[str]]:
    plan = dict(owner_plan or {})
    blockers: list[str] = []

    if plan.get("schema") != OWNER_EXPERIENCE_SCHEMA:
        blockers.append("OWNER_PLAN_SCHEMA_MISMATCH")
    if plan.get("state") != "PLANNED":
        blockers.append("OWNER_PLAN_NOT_PLANNED")
    if plan.get("kind") != "LOCAL_APPLICATION":
        blockers.append("LOCAL_APPLICATION_PLAN_REQUIRED")
    if plan.get("adapter_required") != "SECURE_LOCAL_AGENT":
        blockers.append("SECURE_LOCAL_AGENT_ADAPTER_REQUIRED")
    if plan.get("device_supported") is not True:
        blockers.append("DESKTOP_DEVICE_REQUIRED")
    if plan.get("requires_explicit_approval") is not True:
        blockers.append("EXPLICIT_OWNER_APPROVAL_REQUIREMENT_MISSING")
    if plan.get("physical_execution") is not False:
        blockers.append("OWNER_PLAN_PHYSICAL_EXECUTION_MUST_BE_FALSE")
    if plan.get("executes_action") is not False:
        blockers.append("OWNER_PLAN_EXECUTION_MUST_BE_FALSE")

    target = _clean(plan.get("target"), 80).casefold()
    if target not in APP_REGISTRY:
        blockers.append("APP_NOT_ALLOWLISTED")

    if _contains_forbidden_material(plan):
        blockers.append("OWNER_PLAN_CONTAINS_EXECUTABLE_MATERIAL")

    return target, list(dict.fromkeys(blockers))


def build_local_action_request(
    owner_plan: Mapping[str, Any] | None,
    *,
    command_text: Any,
    owner_subject: Any,
    owner_binding_digest: Any,
    command_id: Any,
    command_nonce: Any,
    device_id: Any,
    platform: Any = SUPPORTED_PLATFORM,
    issued_at: Any,
    expires_at: Any,
) -> dict[str, Any]:
    """Create a bounded logical request; a fresh command is not yet dispatch."""
    target, blockers = _validate_owner_plan(owner_plan)
    command = _clean(command_text, MAX_COMMAND_CHARS)
    marker = _forbidden_command_marker(command)
    if marker:
        blockers.append("COMMAND_CONTAINS_FORBIDDEN_MATERIAL")

    subject = _identity(owner_subject, 120)
    binding_digest = _identity(owner_binding_digest, 90)
    command_identity = _identity(command_id, 160)
    nonce = _identity(command_nonce, 160)
    desktop_id = _identity(device_id, 160)
    platform_name = _clean(platform, 40).upper()

    if not command:
        blockers.append("COMMAND_TEXT_REQUIRED")
    else:
        mentioned_targets = _command_targets(command)
        if target and target not in mentioned_targets:
            blockers.append("PLANNED_TARGET_NOT_PRESENT_IN_COMMAND")
        if len(mentioned_targets) != 1:
            blockers.append("COMMAND_TARGET_AMBIGUOUS")
    if not subject:
        blockers.append("OWNER_SUBJECT_REQUIRED")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", binding_digest):
        blockers.append("OWNER_BINDING_DIGEST_INVALID")
    if not command_identity:
        blockers.append("COMMAND_ID_REQUIRED")
    if not nonce:
        blockers.append("COMMAND_NONCE_REQUIRED")
    if not desktop_id:
        blockers.append("DEVICE_ID_REQUIRED")
    if platform_name != SUPPORTED_PLATFORM:
        blockers.append("WINDOWS_PLATFORM_REQUIRED")

    try:
        issued = _aware_datetime(issued_at, "issued_at")
        expires = _aware_datetime(expires_at, "expires_at")
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0 or lifetime > MAX_ACTION_WINDOW_SECONDS:
            blockers.append("ACTION_WINDOW_INVALID")
    except ValueError:
        issued = None
        expires = None
        blockers.append("ACTION_WINDOW_INVALID")

    actions: list[dict[str, Any]] = []
    media = ""
    if target in APP_REGISTRY and not marker:
        actions.append({
            "action": "OPEN_APP",
            "logical_app_id": APP_REGISTRY[target]["logical_app_id"],
            "parameters": {},
        })
        try:
            media = _media_query(command, target)
        except ValueError:
            blockers.append("MEDIA_QUERY_REJECTED")
            media = ""
        if media:
            if "MEDIA_PLAYBACK" not in APP_REGISTRY[target]["actions"]:
                blockers.append("MEDIA_PLAYBACK_NOT_ALLOWED_FOR_APP")
            else:
                actions.append({
                    "action": "MEDIA_PLAYBACK",
                    "logical_app_id": APP_REGISTRY[target]["logical_app_id"],
                    "parameters": {"query": media},
                })

    if any(
        action.get("action") in _HIGH_RISK_CAPABILITIES
        for action in actions
    ):
        blockers.append("HIGH_RISK_CAPABILITY_FORBIDDEN")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": REQUEST_SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "request_digest": "",
            "target": target,
            "actions": [],
            "dispatch_ready": False,
            "physical_execution_allowed": False,
            "physical_execution_performed": False,
            "executes_action": False,
        }

    issued_text = issued.isoformat() if issued else ""
    expires_text = expires.isoformat() if expires else ""
    payload = {
        "schema": REQUEST_SCHEMA,
        "state": "REQUEST_READY",
        "blockers": [],
        "target": target,
        "actions": actions,
        "owner_subject": subject,
        "owner_binding_digest": binding_digest,
        "command_id": command_identity,
        "command_text_digest": _digest(command),
        "command_nonce_digest": _digest(nonce),
        "device_id": desktop_id,
        "platform": platform_name,
        "issued_at": issued_text,
        "expires_at": expires_text,
        "approval_mode": "FRESH_OWNER_COMMAND_WITH_TRUSTED_HOST_ATTESTATION",
        "requires_trusted_host_authorization": True,
        "requires_replay_guard": True,
        "requires_single_use_nonce": True,
        "requires_signed_local_adapter": True,
        "raw_command_stored": False,
        "raw_nonce_stored": False,
        "physical_binding_included": False,
        "executable_path_included": False,
        "launch_command_included": False,
        "shell_command_generated": False,
        "execution_command_generated": False,
        "dispatch_ready": False,
        "physical_execution_allowed": False,
        "physical_execution_performed": False,
        "provider_called": False,
        "network_called": False,
        "microphone_opened": False,
        "worker_armed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
        "executes_action": False,
        "request_digest": "",
    }
    payload["request_digest"] = _digest(_request_material(payload))
    return payload


def verify_local_action_request(
    request: Mapping[str, Any] | None,
    *,
    now: Any,
) -> dict[str, Any]:
    raw = dict(request or {})
    blockers: list[str] = []

    if raw.get("schema") != REQUEST_SCHEMA:
        blockers.append("REQUEST_SCHEMA_MISMATCH")
    if raw.get("state") != "REQUEST_READY":
        blockers.append("REQUEST_NOT_READY")

    supplied = _clean(raw.get("request_digest"), 90)
    expected = _digest(_request_material(raw))
    if supplied != expected:
        blockers.append("REQUEST_DIGEST_MISMATCH")

    target = _clean(raw.get("target"), 80).casefold()
    if target not in APP_REGISTRY:
        blockers.append("APP_NOT_ALLOWLISTED")
    if _clean(raw.get("platform"), 40).upper() != SUPPORTED_PLATFORM:
        blockers.append("WINDOWS_PLATFORM_REQUIRED")

    actions = raw.get("actions")
    if not isinstance(actions, list) or not actions:
        blockers.append("ACTIONS_REQUIRED")
    else:
        allowed = set(APP_REGISTRY.get(target, {}).get("actions", ()))
        for action in actions:
            if not isinstance(action, Mapping):
                blockers.append("ACTION_INVALID")
                continue
            action_name = _clean(action.get("action"), 80).upper()
            if action_name not in SUPPORTED_ACTIONS:
                blockers.append("ACTION_NOT_SUPPORTED:" + action_name)
            if action_name not in allowed:
                blockers.append("ACTION_NOT_ALLOWLISTED_FOR_APP:" + action_name)
            if action_name in _HIGH_RISK_CAPABILITIES:
                blockers.append("HIGH_RISK_CAPABILITY_FORBIDDEN")
            if _contains_forbidden_material(action):
                blockers.append("EXECUTABLE_MATERIAL_FORBIDDEN")

    for key in (
        "owner_subject",
        "owner_binding_digest",
        "command_id",
        "command_text_digest",
        "command_nonce_digest",
        "device_id",
    ):
        if not _identity(raw.get(key), 180):
            blockers.append("REQUEST_FIELD_INVALID:" + key)

    if raw.get("physical_binding_included") is not False:
        blockers.append("PHYSICAL_BINDING_MUST_BE_ABSENT")
    if raw.get("executable_path_included") is not False:
        blockers.append("EXECUTABLE_PATH_MUST_BE_ABSENT")
    if raw.get("launch_command_included") is not False:
        blockers.append("LAUNCH_COMMAND_MUST_BE_ABSENT")
    if raw.get("shell_command_generated") is not False:
        blockers.append("SHELL_COMMAND_MUST_NOT_EXIST")
    if raw.get("execution_command_generated") is not False:
        blockers.append("EXECUTION_COMMAND_MUST_NOT_EXIST")

    try:
        current = _aware_datetime(now, "now")
        issued = _aware_datetime(raw.get("issued_at"), "issued_at")
        expires = _aware_datetime(raw.get("expires_at"), "expires_at")
        lifetime = (expires - issued).total_seconds()
        if lifetime <= 0 or lifetime > MAX_ACTION_WINDOW_SECONDS:
            blockers.append("ACTION_WINDOW_INVALID")
        if current < issued:
            blockers.append("ACTION_NOT_YET_VALID")
        if current > expires:
            blockers.append("ACTION_REQUEST_EXPIRED")
    except ValueError:
        blockers.append("ACTION_WINDOW_INVALID")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": REQUEST_SCHEMA,
        "state": "CURRENT" if not blockers else "INVALID_OR_STALE",
        "current": not blockers,
        "blockers": blockers,
        "request_digest": supplied,
        "dispatch_ready": False,
        "physical_execution_allowed": False,
        "physical_execution_performed": False,
        "executes_action": False,
    }


def evaluate_dispatch_readiness(
    request: Mapping[str, Any] | None,
    *,
    trusted_host_authorization: Mapping[str, Any] | None,
    replay_guard_attestation: Mapping[str, Any] | None,
    now: Any,
) -> dict[str, Any]:
    """Evaluate evidence only. Even READY does not perform the physical action."""
    verified_request = verify_local_action_request(request, now=now)
    blockers = list(verified_request["blockers"])
    raw = dict(request or {})
    host = dict(trusted_host_authorization or {})
    replay = dict(replay_guard_attestation or {})

    request_digest = _clean(raw.get("request_digest"), 90)
    owner_subject = _clean(raw.get("owner_subject"), 120)
    binding_digest = _clean(raw.get("owner_binding_digest"), 90)
    nonce_digest = _clean(raw.get("command_nonce_digest"), 90)

    if host.get("verified") is not True:
        blockers.append("TRUSTED_HOST_AUTHORIZATION_NOT_VERIFIED")
    if host.get("source") != "TRUSTED_OWNER_DESKTOP_HOST":
        blockers.append("TRUSTED_HOST_SOURCE_INVALID")
    if host.get("mechanism") not in {"WINDOWS_HELLO", "FIDO2", "OWNER_SESSION_SIGNATURE"}:
        blockers.append("OWNER_AUTHORIZATION_MECHANISM_INVALID")
    if host.get("fresh_owner_command") is not True:
        blockers.append("FRESH_OWNER_COMMAND_REQUIRED")
    if host.get("generic_chat_acknowledgement") is not False:
        blockers.append("GENERIC_CHAT_ACKNOWLEDGEMENT_FORBIDDEN")
    if _clean(host.get("owner_subject"), 120) != owner_subject:
        blockers.append("OWNER_SUBJECT_MISMATCH")
    if _clean(host.get("owner_binding_digest"), 90) != binding_digest:
        blockers.append("OWNER_BINDING_MISMATCH")
    if _clean(host.get("request_digest"), 90) != request_digest:
        blockers.append("HOST_REQUEST_DIGEST_MISMATCH")
    if _clean(host.get("command_nonce_digest"), 90) != nonce_digest:
        blockers.append("HOST_NONCE_DIGEST_MISMATCH")
    if host.get("cryptographic_verification_performed") is not True:
        blockers.append("OS_OR_SIGNATURE_VERIFICATION_REQUIRED")

    if replay.get("verified") is not True:
        blockers.append("REPLAY_GUARD_NOT_VERIFIED")
    if _clean(replay.get("request_digest"), 90) != request_digest:
        blockers.append("REPLAY_REQUEST_DIGEST_MISMATCH")
    if _clean(replay.get("command_nonce_digest"), 90) != nonce_digest:
        blockers.append("REPLAY_NONCE_DIGEST_MISMATCH")
    if replay.get("fresh") is not True:
        blockers.append("NONCE_NOT_FRESH")
    if replay.get("single_use_claimed") is not True:
        blockers.append("NONCE_SINGLE_USE_CLAIM_REQUIRED")
    if replay.get("durable_replay_rejection") is not True:
        blockers.append("DURABLE_REPLAY_REJECTION_REQUIRED")

    if _contains_forbidden_material(host) or _contains_forbidden_material(replay):
        blockers.append("ATTESTATION_EXECUTABLE_OR_SECRET_MATERIAL_FORBIDDEN")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return {
        "schema": READINESS_SCHEMA,
        "state": "DISPATCH_READY" if ready else "BLOCKED",
        "dispatch_ready": ready,
        "blockers": blockers,
        "request_digest": request_digest,
        "target": _clean(raw.get("target"), 80).casefold(),
        "actions": list(raw.get("actions") or []) if ready else [],
        "trusted_host_authorization_verified": ready,
        "replay_guard_verified": ready,
        "adapter_must_reverify_before_execution": True,
        "physical_binding_included": False,
        "executable_path_included": False,
        "launch_command_included": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "subprocess_called": False,
        "network_called": False,
        "microphone_opened": False,
        "physical_execution_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def secure_local_agent_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "platform": SUPPORTED_PLATFORM,
        "device": SUPPORTED_DEVICE,
        "allowlisted_apps": sorted(APP_REGISTRY),
        "supported_actions": list(SUPPORTED_ACTIONS),
        "fresh_owner_command_can_supply_explicit_intent": True,
        "trusted_host_attestation_required": True,
        "cryptographic_owner_verification_required": True,
        "durable_single_use_replay_guard_required": True,
        "signed_local_adapter_required": True,
        "arbitrary_app_launch": False,
        "arbitrary_executable_path": False,
        "shell_execution": False,
        "command_line_execution": False,
        "file_mutation": False,
        "system_settings_mutation": False,
        "credential_access": False,
        "send_message": False,
        "send_email": False,
        "purchase_or_payment": False,
        "trading_order": False,
        "browser_autofill": False,
        "microphone_started": False,
        "hotword_listener_started": False,
        "network_called": False,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "physical_execution_performed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "READINESS_SCHEMA",
    "POLICY_SCHEMA",
    "MAX_ACTION_WINDOW_SECONDS",
    "SUPPORTED_PLATFORM",
    "SUPPORTED_DEVICE",
    "SUPPORTED_ACTIONS",
    "APP_REGISTRY",
    "local_app_registry",
    "build_local_action_request",
    "verify_local_action_request",
    "evaluate_dispatch_readiness",
    "secure_local_agent_policy",
]
