"""AION Voice + Hotword Runtime V1.

Pure planning/state/routing contract for owner voice interaction.

This module deliberately does NOT:
- open a microphone;
- capture, record or persist raw audio;
- start a hotword engine;
- perform speech-to-text;
- call TTS/ASR providers;
- play audio;
- launch applications;
- navigate the browser;
- authenticate the owner from a wake word;
- persist transcripts;
- run a background worker;
- deploy or mutate Core.

It defines the privacy, activation, state-transition and command-routing contract
that the future desktop/mobile host must satisfy.

Security principle:
"AION" is an activation phrase, never an authentication factor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import unicodedata
from typing import Any, Mapping

from atlasquant_aion_owner_experience_v1 import (
    DEVICES,
    command_plan,
    voice_capability_plan,
)
from atlasquant_voice_profile import VOICE_PROFILE_ID, voice_profile_ready


SCHEMA = "ATLASQUANT_AION_VOICE_HOTWORD_RUNTIME_V1"
PLAN_SCHEMA = "ATLASQUANT_AION_VOICE_HOTWORD_PLAN_V1"
TRANSITION_SCHEMA = "ATLASQUANT_AION_VOICE_STATE_TRANSITION_V1"
ACTIVATION_SCHEMA = "ATLASQUANT_AION_VOICE_ACTIVATION_V1"
ROUTE_SCHEMA = "ATLASQUANT_AION_VOICE_COMMAND_ROUTE_V1"
HANDOFF_SCHEMA = "ATLASQUANT_AION_VOICE_HANDOFF_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_VOICE_PRIVACY_POLICY_V1"

HOTWORD = "AION"
LANGUAGE = "pt-BR"

ACTIVATION_MODES = ("HOTWORD", "PUSH_TO_TALK")
RUNTIME_STATES = (
    "DISARMED",
    "ARMED",
    "LISTENING_FOR_WAKE_WORD",
    "CAPTURING_COMMAND",
    "COMMAND_READY",
    "RESPONDING",
    "PAUSED_PRIVACY",
    "SUSPENDED_APP_INACTIVE",
    "BLOCKED_PERMISSION",
    "ERROR",
)

EVENTS = (
    "ENABLE",
    "START_LISTENING",
    "WAKE_DETECTED",
    "PUSH_TO_TALK",
    "TRANSCRIPT_READY",
    "COMMAND_CONSUMED",
    "RESPONSE_READY",
    "RESPONSE_DONE",
    "PRIVACY_PAUSE",
    "PRIVACY_RESUME",
    "MIC_PERMISSION_REVOKED",
    "MIC_PERMISSION_GRANTED",
    "APP_INACTIVE",
    "APP_ACTIVE",
    "DISABLE",
    "FAIL",
    "RECOVER",
)

SENSITIVE_COMMAND_MARKERS = (
    "senha",
    "password",
    "token",
    "api key",
    "chave privada",
    "private key",
    "cookie",
    "jwt",
    "cartão",
    "cartao",
    "cvv",
)

HIGH_RISK_ACTION_MARKERS = (
    "faz pix",
    "fazer pix",
    "transfere dinheiro",
    "transferir dinheiro",
    "compra ",
    "comprar ",
    "vende ",
    "vender ",
    "envia ordem",
    "enviar ordem",
    "opera ",
    "operar ",
    "apaga arquivo",
    "deleta arquivo",
    "formata",
    "instala",
    "desinstala",
)

_ALLOWED_TRANSITIONS = {
    ("DISARMED", "ENABLE"): "ARMED",
    ("ARMED", "START_LISTENING"): "LISTENING_FOR_WAKE_WORD",
    ("ARMED", "PUSH_TO_TALK"): "CAPTURING_COMMAND",
    ("LISTENING_FOR_WAKE_WORD", "WAKE_DETECTED"): "CAPTURING_COMMAND",
    ("LISTENING_FOR_WAKE_WORD", "PUSH_TO_TALK"): "CAPTURING_COMMAND",
    ("CAPTURING_COMMAND", "TRANSCRIPT_READY"): "COMMAND_READY",
    ("COMMAND_READY", "COMMAND_CONSUMED"): "ARMED",
    ("COMMAND_READY", "RESPONSE_READY"): "RESPONDING",
    ("RESPONDING", "RESPONSE_DONE"): "ARMED",
    ("ARMED", "PRIVACY_PAUSE"): "PAUSED_PRIVACY",
    ("LISTENING_FOR_WAKE_WORD", "PRIVACY_PAUSE"): "PAUSED_PRIVACY",
    ("CAPTURING_COMMAND", "PRIVACY_PAUSE"): "PAUSED_PRIVACY",
    ("COMMAND_READY", "PRIVACY_PAUSE"): "PAUSED_PRIVACY",
    ("RESPONDING", "PRIVACY_PAUSE"): "PAUSED_PRIVACY",
    ("PAUSED_PRIVACY", "PRIVACY_RESUME"): "ARMED",
    ("ARMED", "APP_INACTIVE"): "SUSPENDED_APP_INACTIVE",
    ("LISTENING_FOR_WAKE_WORD", "APP_INACTIVE"): "SUSPENDED_APP_INACTIVE",
    ("CAPTURING_COMMAND", "APP_INACTIVE"): "SUSPENDED_APP_INACTIVE",
    ("COMMAND_READY", "APP_INACTIVE"): "SUSPENDED_APP_INACTIVE",
    ("RESPONDING", "APP_INACTIVE"): "SUSPENDED_APP_INACTIVE",
    ("SUSPENDED_APP_INACTIVE", "APP_ACTIVE"): "ARMED",
    ("ARMED", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("LISTENING_FOR_WAKE_WORD", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("CAPTURING_COMMAND", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("COMMAND_READY", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("RESPONDING", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("PAUSED_PRIVACY", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("SUSPENDED_APP_INACTIVE", "MIC_PERMISSION_REVOKED"): "BLOCKED_PERMISSION",
    ("BLOCKED_PERMISSION", "MIC_PERMISSION_GRANTED"): "ARMED",
    ("DISARMED", "FAIL"): "ERROR",
    ("ARMED", "FAIL"): "ERROR",
    ("LISTENING_FOR_WAKE_WORD", "FAIL"): "ERROR",
    ("CAPTURING_COMMAND", "FAIL"): "ERROR",
    ("COMMAND_READY", "FAIL"): "ERROR",
    ("RESPONDING", "FAIL"): "ERROR",
    ("PAUSED_PRIVACY", "FAIL"): "ERROR",
    ("SUSPENDED_APP_INACTIVE", "FAIL"): "ERROR",
    ("BLOCKED_PERMISSION", "FAIL"): "ERROR",
    ("ERROR", "RECOVER"): "DISARMED",
}

for _state in RUNTIME_STATES:
    if _state != "DISARMED":
        _ALLOWED_TRANSITIONS[(_state, "DISABLE")] = "DISARMED"


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _norm(value: Any, limit: int = 600) -> str:
    raw = unicodedata.normalize("NFKD", _clean(value, limit))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.casefold()
    raw = re.sub(r"[^a-z0-9\s-]", " ", raw)
    return " ".join(raw.split())


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


def _text_digest(value: Any) -> str:
    return "sha256:" + sha256(_clean(value, 4000).encode("utf-8")).hexdigest()


def _identity(value: Any, limit: int = 160) -> str:
    if type(value) is not str:
        return ""
    if not value or len(value) > limit or "\x00" in value:
        return ""
    if " ".join(value.split()) != value:
        return ""
    return value


def _aware_iso(value: Any) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError("aware timestamp required") from exc
    if parsed.tzinfo is None:
        raise ValueError("aware timestamp required")
    return parsed.astimezone(timezone.utc).isoformat()


def _sensitive_marker(text: str) -> str:
    normalized = _norm(text)
    for marker in SENSITIVE_COMMAND_MARKERS:
        if _norm(marker) in normalized:
            return marker
    return ""


def _high_risk_marker(text: str) -> str:
    normalized = _norm(text)
    padded = f" {normalized} "
    for marker in HIGH_RISK_ACTION_MARKERS:
        if f" {_norm(marker)} " in padded or _norm(marker) in normalized:
            return marker
    return ""


def voice_hotword_runtime_plan(
    *,
    device: Any,
    owner_binding_digest: Any,
    microphone_permission: bool,
    continuous_recognition_available: bool,
    hotword_runtime_available: bool,
    tts_ready: bool,
    app_active: bool,
    privacy_indicator_available: bool,
    push_to_talk_available: bool,
    background_listening_authorized: bool = False,
) -> dict[str, Any]:
    """Build a non-executing owner voice runtime plan."""
    device_name = _clean(device, 20).upper()
    if device_name not in DEVICES:
        raise ValueError("unsupported device")

    binding = _identity(owner_binding_digest, 100)
    blockers: list[str] = []
    if not binding.startswith("sha256:") or len(binding) != 71:
        blockers.append("VALID_OWNER_BINDING_DIGEST_REQUIRED")
    if microphone_permission is not True:
        blockers.append("MICROPHONE_PERMISSION_REQUIRED")
    if privacy_indicator_available is not True:
        blockers.append("VISIBLE_PRIVACY_INDICATOR_REQUIRED")
    if push_to_talk_available is not True and hotword_runtime_available is not True:
        blockers.append("VOICE_ACTIVATION_CHANNEL_REQUIRED")

    base = voice_capability_plan(
        device=device_name,
        microphone_permission=bool(microphone_permission),
        continuous_recognition_available=bool(continuous_recognition_available),
        hotword_runtime_available=bool(hotword_runtime_available),
        tts_ready=bool(tts_ready),
        app_active=bool(app_active),
    )

    # V1 intentionally does not promise OS-level 24/7 background listening.
    background_supported = False
    effective_app_active = bool(app_active)
    hotword_ready = bool(
        not blockers
        and base.get("hotword_ready") is True
        and effective_app_active
    )
    push_to_talk_ready = bool(
        not blockers
        and microphone_permission
        and push_to_talk_available
        and effective_app_active
    )

    state = "READY" if (hotword_ready or push_to_talk_ready) else "PARTIAL"
    if blockers:
        state = "BLOCKED"

    plan = {
        "schema": PLAN_SCHEMA,
        "state": state,
        "blockers": list(dict.fromkeys(blockers)),
        "device": device_name,
        "language": LANGUAGE,
        "hotword": HOTWORD,
        "owner_binding_digest": binding,
        "voice_profile_id": VOICE_PROFILE_ID,
        "voice_profile_ready": voice_profile_ready(),
        "microphone_permission": bool(microphone_permission),
        "continuous_recognition_available": bool(continuous_recognition_available),
        "hotword_runtime_available": bool(hotword_runtime_available),
        "hotword_ready": hotword_ready,
        "push_to_talk_available": bool(push_to_talk_available),
        "push_to_talk_ready": push_to_talk_ready,
        "app_active": effective_app_active,
        "app_active_required_for_hotword_v1": True,
        "background_listening_requested": bool(background_listening_authorized),
        "background_listening_supported_v1": background_supported,
        "privacy_indicator_available": bool(privacy_indicator_available),
        "visible_privacy_indicator_required": True,
        "tts_ready": bool(tts_ready and voice_profile_ready()),
        "generic_device_tts_fallback_allowed": False,
        "text_fallback": True,
        "raw_audio_persistence_allowed": False,
        "raw_transcript_persistence_allowed": False,
        "ephemeral_audio_only": True,
        "hotword_is_authentication": False,
        "wake_word_grants_authority": False,
        "continuous_session_started": False,
        "microphone_opened": False,
        "listener_started": False,
        "provider_called": False,
        "audio_playback_started": False,
        "background_worker_started": False,
        "external_action_executed": False,
        "executes_action": False,
        "plan_digest": "",
    }
    material = dict(plan)
    material.pop("plan_digest", None)
    plan["plan_digest"] = _digest(material)
    return plan


def voice_state_transition(
    current: Any,
    event: Any,
    *,
    microphone_permission: bool,
    app_active: bool,
    privacy_pause: bool = False,
) -> dict[str, Any]:
    """Evaluate one state transition without touching microphone/audio."""
    state = _clean(current, 80).upper()
    action = _clean(event, 80).upper()
    if state not in RUNTIME_STATES:
        raise ValueError("invalid voice runtime state")
    if action not in EVENTS:
        raise ValueError("invalid voice runtime event")

    blockers: list[str] = []
    if action in {"ENABLE", "START_LISTENING", "WAKE_DETECTED", "PUSH_TO_TALK"}:
        if microphone_permission is not True:
            blockers.append("MICROPHONE_PERMISSION_REQUIRED")
        if action != "PUSH_TO_TALK" and app_active is not True:
            blockers.append("APP_ACTIVE_REQUIRED")
        if privacy_pause is True:
            blockers.append("PRIVACY_PAUSE_ACTIVE")

    target = _ALLOWED_TRANSITIONS.get((state, action))
    if target is None:
        blockers.append("INVALID_STATE_TRANSITION")

    if action == "APP_INACTIVE":
        target = (
            "SUSPENDED_APP_INACTIVE"
            if state != "DISARMED"
            else "DISARMED"
        )
    elif action == "MIC_PERMISSION_REVOKED":
        target = (
            "BLOCKED_PERMISSION"
            if state != "DISARMED"
            else "DISARMED"
        )

    if blockers:
        target = state

    microphone_should_be_active = target in {
        "LISTENING_FOR_WAKE_WORD",
        "CAPTURING_COMMAND",
    }
    return {
        "schema": TRANSITION_SCHEMA,
        "state": "TRANSITIONED" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "from_state": state,
        "event": action,
        "to_state": target,
        "microphone_should_be_active": microphone_should_be_active,
        "microphone_opened_by_this_module": False,
        "listener_started_by_this_module": False,
        "raw_audio_recorded": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def detect_voice_activation(
    transcript_fragment: Any,
    *,
    mode: Any,
    explicit_gesture: bool = False,
) -> dict[str, Any]:
    """Detect an exact leading wake word or explicit push-to-talk activation."""
    activation_mode = _clean(mode, 40).upper()
    if activation_mode not in ACTIVATION_MODES:
        raise ValueError("unsupported activation mode")

    normalized = _norm(transcript_fragment, 600)
    parts = normalized.split()
    wake_detected = bool(parts and parts[0] == "aion")
    false_prefix = bool(parts and parts[0].startswith("aion") and parts[0] != "aion")

    if activation_mode == "HOTWORD":
        activated = wake_detected
        reason = (
            "EXACT_LEADING_HOTWORD"
            if activated
            else "NO_EXACT_LEADING_HOTWORD"
        )
    else:
        activated = explicit_gesture is True
        reason = (
            "EXPLICIT_PUSH_TO_TALK"
            if activated
            else "PUSH_TO_TALK_GESTURE_REQUIRED"
        )

    return {
        "schema": ACTIVATION_SCHEMA,
        "state": "ACTIVATED" if activated else "IGNORED",
        "activation_mode": activation_mode,
        "activation_detected": activated,
        "wake_word_detected": wake_detected,
        "false_hotword_prefix_detected": false_prefix,
        "hotword": HOTWORD,
        "activation_phrase_is_authentication": False,
        "grants_owner_authority": False,
        "reason": reason,
        "transcript_fragment_digest": _text_digest(normalized),
        "raw_transcript_returned": False,
        "raw_audio_used": False,
        "microphone_opened": False,
        "provider_called": False,
        "executes_action": False,
    }


def route_voice_command(
    transcript: Any,
    *,
    activation: Mapping[str, Any] | None,
    device: Any,
    owner_bound: bool,
    owner_binding_digest: Any,
    session_id: Any,
    activation_id: Any,
    captured_at: Any,
) -> dict[str, Any]:
    """Route recognized text to a safe plan; never execute or persist it."""
    text = _clean(transcript, 600)
    normalized = _norm(text, 600)
    act = dict(activation or {})
    device_name = _clean(device, 20).upper()
    blockers: list[str] = []

    if device_name not in DEVICES:
        blockers.append("UNSUPPORTED_DEVICE")
    if act.get("schema") != ACTIVATION_SCHEMA:
        blockers.append("ACTIVATION_SCHEMA_MISMATCH")
    if act.get("activation_detected") is not True:
        blockers.append("VOICE_ACTIVATION_REQUIRED")
    if act.get("grants_owner_authority") is not False:
        blockers.append("ACTIVATION_AUTHORITY_BOUNDARY_INVALID")
    if owner_bound is not True:
        blockers.append("HUMAN_OWNER_BINDING_REQUIRED")

    binding = _identity(owner_binding_digest, 100)
    if not binding.startswith("sha256:") or len(binding) != 71:
        blockers.append("VALID_OWNER_BINDING_DIGEST_REQUIRED")

    session = _identity(session_id, 160)
    activation_identifier = _identity(activation_id, 160)
    if not session:
        blockers.append("VOICE_SESSION_ID_REQUIRED")
    if not activation_identifier:
        blockers.append("ACTIVATION_ID_REQUIRED")
    if not normalized:
        blockers.append("NON_EMPTY_TRANSCRIPT_REQUIRED")

    try:
        captured = _aware_iso(captured_at)
    except ValueError:
        captured = ""
        blockers.append("CAPTURED_AT_INVALID")

    sensitive = _sensitive_marker(normalized)
    high_risk = _high_risk_marker(normalized)
    if sensitive:
        blockers.append("SENSITIVE_CREDENTIAL_LIKE_SPEECH_BLOCKED")
    if high_risk:
        blockers.append("HIGH_RISK_VOICE_ACTION_REQUIRES_SEPARATE_CEREMONY")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": ROUTE_SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers,
            "route_kind": "",
            "target": "",
            "adapter_required": "",
            "transcript_digest": _text_digest(normalized),
            "raw_transcript_returned": False,
            "raw_transcript_persisted": False,
            "raw_audio_persisted": False,
            "physical_execution": False,
            "external_action_executed": False,
            "executes_action": False,
        }

    owner_plan = command_plan(
        text,
        device=device_name,
        owner_bound=True,
    )

    if owner_plan.get("state") == "PLANNED":
        route_kind = _clean(owner_plan.get("kind"), 80).upper()
        target = _clean(owner_plan.get("target"), 120)
        adapter = _clean(owner_plan.get("adapter_required"), 120).upper()
        route_state = "ROUTE_READY"
    else:
        route_kind = "AION_CONVERSATION"
        target = "aion"
        adapter = "AION_CHAT_RUNTIME"
        route_state = "ROUTE_READY"

    envelope_material = {
        "session_id": session,
        "activation_id": activation_identifier,
        "captured_at": captured,
        "device": device_name,
        "owner_binding_digest": binding,
        "activation_mode": act.get("activation_mode"),
        "transcript_digest": _text_digest(normalized),
        "route_kind": route_kind,
        "target": target,
        "adapter_required": adapter,
    }

    return {
        "schema": ROUTE_SCHEMA,
        "state": route_state,
        "blockers": [],
        "session_id": session,
        "activation_id": activation_identifier,
        "captured_at": captured,
        "device": device_name,
        "owner_binding_digest": binding,
        "activation_mode": act.get("activation_mode"),
        "transcript_digest": envelope_material["transcript_digest"],
        "route_kind": route_kind,
        "target": target,
        "adapter_required": adapter,
        "owner_plan_state": owner_plan.get("state"),
        "owner_plan_requires_explicit_approval": bool(
            owner_plan.get("requires_explicit_approval")
        ),
        "physical_execution": False,
        "wake_word_grants_authority": False,
        "external_action_executed": False,
        "raw_transcript_returned": False,
        "raw_transcript_persisted": False,
        "raw_audio_persisted": False,
        "provider_called": False,
        "command_envelope_digest": _digest(envelope_material),
        "executes_action": False,
    }


def voice_response_plan(
    response_text: Any,
    *,
    voice_session_active: bool,
    tts_ready: bool,
    user_requested_audio: bool,
) -> dict[str, Any]:
    """Plan response presentation; never calls TTS or starts playback."""
    text = _clean(response_text, 4000)
    blockers: list[str] = []
    if not text:
        blockers.append("RESPONSE_TEXT_REQUIRED")

    neural_eligible = bool(
        not blockers
        and voice_session_active
        and tts_ready
        and voice_profile_ready()
        and user_requested_audio
    )
    return {
        "schema": SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "response_text_digest": _text_digest(text),
        "text_response_available": bool(text),
        "text_fallback": True,
        "voice_profile_id": VOICE_PROFILE_ID,
        "neural_audio_eligible": neural_eligible,
        "generic_device_tts_fallback_allowed": False,
        "tts_provider_call_required_for_audio": neural_eligible,
        "provider_called": False,
        "audio_generated": False,
        "audio_playback_started": False,
        "automatic_generic_speech_started": False,
        "executes_action": False,
    }


def voice_continuity_handoff(
    *,
    session_id: Any,
    source_device: Any,
    target_device: Any,
    last_route_digest: Any,
    runtime_state: Any,
) -> dict[str, Any]:
    """Create safe cross-device voice continuity metadata only."""
    source = _clean(source_device, 20).upper()
    target = _clean(target_device, 20).upper()
    state = _clean(runtime_state, 80).upper()
    blockers: list[str] = []
    if source not in DEVICES or target not in DEVICES:
        blockers.append("SUPPORTED_DEVICES_REQUIRED")
    if state not in RUNTIME_STATES:
        blockers.append("VALID_RUNTIME_STATE_REQUIRED")
    session = _identity(session_id, 160)
    if not session:
        blockers.append("VOICE_SESSION_ID_REQUIRED")
    route_digest = _identity(last_route_digest, 100)
    if route_digest and not (
        route_digest.startswith("sha256:") and len(route_digest) == 71
    ):
        blockers.append("LAST_ROUTE_DIGEST_INVALID")

    material = {
        "session_id": session,
        "source_device": source,
        "target_device": target,
        "last_route_digest": route_digest,
        "runtime_state": state,
    }
    return {
        "schema": HANDOFF_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        **material,
        "handoff_digest": _digest(material) if not blockers else "",
        "raw_audio_transferred": False,
        "raw_transcript_transferred": False,
        "microphone_state_transferred": False,
        "authentication_transferred": False,
        "owner_authority_transferred": False,
        "target_device_must_reauthenticate": True,
        "target_device_must_request_microphone_permission": True,
        "listener_started": False,
        "executes_action": False,
    }


def voice_privacy_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "language": LANGUAGE,
        "hotword": HOTWORD,
        "hotword_is_authentication": False,
        "wake_word_grants_authority": False,
        "microphone_permission_required": True,
        "visible_privacy_indicator_required": True,
        "one_tap_privacy_pause_required": True,
        "app_active_required_for_hotword_v1": True,
        "background_listening_supported_v1": False,
        "push_to_talk_supported": True,
        "exact_leading_hotword_required": True,
        "fuzzy_hotword_activation_allowed": False,
        "raw_audio_persistence_allowed": False,
        "raw_transcript_persistence_allowed": False,
        "ephemeral_audio_only": True,
        "generic_device_tts_fallback_allowed": False,
        "text_fallback_required": True,
        "credential_like_voice_commands_blocked": True,
        "high_risk_voice_actions_require_separate_ceremony": True,
        "trading_order_authority": False,
        "payment_authority": False,
        "file_delete_authority": False,
        "software_install_authority": False,
        "local_app_physical_execution": False,
        "microphone_opened": False,
        "hotword_listener_started": False,
        "asr_provider_called": False,
        "tts_provider_called": False,
        "audio_playback_started": False,
        "background_worker_started": False,
        "network_called": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "PLAN_SCHEMA",
    "TRANSITION_SCHEMA",
    "ACTIVATION_SCHEMA",
    "ROUTE_SCHEMA",
    "HANDOFF_SCHEMA",
    "POLICY_SCHEMA",
    "HOTWORD",
    "LANGUAGE",
    "ACTIVATION_MODES",
    "RUNTIME_STATES",
    "EVENTS",
    "voice_hotword_runtime_plan",
    "voice_state_transition",
    "detect_voice_activation",
    "route_voice_command",
    "voice_response_plan",
    "voice_continuity_handoff",
    "voice_privacy_policy",
]
