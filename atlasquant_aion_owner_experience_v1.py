"""AION Owner Experience V1 — pure contracts for trusted owner interaction.

This module binds the already-authenticated ADMIN session to an externally
verified HUMAN_OWNER assertion and prepares owner-facing interaction plans.

It is deliberately side-effect free:
- no environment or secret lookup;
- no network/provider call;
- no microphone access;
- no hotword listener;
- no subprocess/application launch;
- no browser navigation;
- no Worker;
- no Core mutation;
- no production deploy.

The host/local-agent layers must execute any approved physical action later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping

from atlasquant_aion_clock import greeting_period


SCHEMA = "ATLASQUANT_AION_OWNER_EXPERIENCE_V1"
PRINCIPAL = "HUMAN_OWNER"

DEVICES = frozenset({"DESKTOP", "MOBILE"})
MODES = frozenset({"NORMAL", "TEACHING", "MEETING"})
MEETING_STATES = frozenset({"IDLE", "PRESENTING", "PAUSED_FOR_QA", "RESUME_PENDING"})
INTERNAL_DESTINATIONS = {
    "central": "central",
    "atlasquant": "central",
    "trader": "trader",
    "negocios": "negocios",
    "negócios": "negocios",
    "investimentos": "investimentos",
    "aion": "aion",
}
EXTERNAL_APPS = {
    "chatgpt": "chatgpt",
    "whatsapp": "whatsapp",
    "spotify": "spotify",
}
_FORBIDDEN_HANDOFF_KEYS = frozenset({
    "password", "passwd", "secret", "token", "jwt", "cookie", "authorization",
    "api_key", "apikey", "private_key", "database_url", "dsn",
})
_REQUIRED_PERMISSIONS = frozenset({"app:read", "aion:admin"})


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _permissions(session: Mapping[str, Any]) -> set[str]:
    raw = session.get("permissions")
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return set()
    return {_clean(item, 120) for item in raw if _clean(item, 120)}


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def owner_binding(
    access: Mapping[str, Any] | None,
    owner_assertion: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Bind authenticated ADMIN identity to a trusted HUMAN_OWNER assertion."""
    raw = _mapping(access)
    session = _mapping(raw.get("session"))
    assertion = _mapping(owner_assertion)
    blockers: list[str] = []

    if raw.get("allowed") is not True:
        blockers.append("ACCESS_NOT_ALLOWED")
    if _clean(raw.get("mode"), 40).upper() != "AUTHENTICATED":
        blockers.append("AUTHENTICATED_MODE_REQUIRED")
    if _clean(raw.get("role") or session.get("role"), 24).upper() != "ADMIN":
        blockers.append("ADMIN_ROLE_REQUIRED")
    if _clean(session.get("role"), 24).upper() != "ADMIN":
        blockers.append("ADMIN_SESSION_REQUIRED")

    username = _clean(session.get("username"), 120)
    fingerprint = _clean(session.get("credential_fingerprint"), 160)
    if not username:
        blockers.append("AUTHENTICATED_USERNAME_REQUIRED")
    if not fingerprint:
        blockers.append("CREDENTIAL_FINGERPRINT_REQUIRED")

    missing = sorted(_REQUIRED_PERMISSIONS - _permissions(session))
    blockers.extend("MISSING_PERMISSION:" + item for item in missing)

    if assertion.get("verified") is not True:
        blockers.append("OWNER_ASSERTION_NOT_VERIFIED")
    if _clean(assertion.get("principal"), 40).upper() != PRINCIPAL:
        blockers.append("HUMAN_OWNER_PRINCIPAL_REQUIRED")
    subject = _clean(assertion.get("subject"), 120)
    if not subject:
        blockers.append("OWNER_SUBJECT_REQUIRED")
    elif username and subject != username:
        blockers.append("OWNER_SUBJECT_MISMATCH")
    issuer = _clean(assertion.get("issuer"), 120)
    if not issuer:
        blockers.append("OWNER_ASSERTION_ISSUER_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    evidence = {
        "principal": PRINCIPAL,
        "subject": subject,
        "issuer": issuer,
        "credential_fingerprint_present": bool(fingerprint),
        "permissions_verified": not missing,
    }
    return {
        "schema": SCHEMA,
        "state": "BOUND" if not blockers else "BLOCKED",
        "bound": not blockers,
        "blockers": blockers,
        "principal": PRINCIPAL if not blockers else "",
        "subject": username if not blockers else "",
        "binding_digest": _canonical_digest(evidence) if not blockers else "",
        "authenticated": not blockers,
        "self_escalation": False,
        "grants_authority": False,
        "executes_action": False,
    }


def owner_greeting_plan(
    access: Mapping[str, Any] | None,
    owner_assertion: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    timezone_name: str | None = None,
    display_name: Any = "Mikael",
) -> dict[str, Any]:
    binding = owner_binding(access, owner_assertion)
    if binding["bound"] is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "text": "",
            "spoken": False,
            "binding": binding,
            "executes_action": False,
        }
    name = _clean(display_name, 64) or "Mikael"
    period = greeting_period(now, timezone_name=timezone_name).casefold()
    text = (
        f"{name}, {period}. AION ativo. Bem-vindo ao AtlasQuant. "
        "O que você gostaria de saber ou fazer?"
    )
    return {
        "schema": SCHEMA,
        "state": "READY",
        "text": text,
        "period": period,
        "name": name,
        "spoken": False,
        "voice_execution_required": True,
        "binding": binding,
        "executes_action": False,
    }


def voice_capability_plan(
    *,
    device: Any,
    microphone_permission: bool,
    continuous_recognition_available: bool,
    hotword_runtime_available: bool,
    tts_ready: bool,
    app_active: bool,
) -> dict[str, Any]:
    device_name = _clean(device, 20).upper()
    if device_name not in DEVICES:
        raise ValueError("unsupported device")
    hotword_ready = bool(
        microphone_permission
        and continuous_recognition_available
        and hotword_runtime_available
        and app_active
    )
    return {
        "schema": SCHEMA,
        "state": "READY" if microphone_permission and tts_ready else "PARTIAL",
        "device": device_name,
        "microphone_permission": bool(microphone_permission),
        "continuous_recognition_available": bool(continuous_recognition_available),
        "hotword_runtime_available": bool(hotword_runtime_available),
        "hotword_ready": hotword_ready,
        "hotword": "AION",
        "app_active_required": True,
        "tts_ready": bool(tts_ready),
        "microphone_opened": False,
        "listener_started": False,
        "provider_called": False,
        "executes_action": False,
    }


def _normalize_command(text: Any) -> str:
    value = _clean(text, 600).casefold()
    value = re.sub(r"[^a-z0-9áàâãéêíóôõúç\s-]", " ", value)
    return " ".join(value.split())


def command_plan(
    text: Any,
    *,
    device: Any,
    owner_bound: bool,
) -> dict[str, Any]:
    """Classify owner commands; never executes navigation/app launch itself."""
    command = _normalize_command(text)
    device_name = _clean(device, 20).upper()
    if device_name not in DEVICES:
        raise ValueError("unsupported device")
    if owner_bound is not True:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "HUMAN_OWNER_BINDING_REQUIRED",
            "command": command,
            "executes_action": False,
        }

    for alias, target in INTERNAL_DESTINATIONS.items():
        if alias in command and any(word in command for word in ("abre", "abrir", "entra", "ir", "vai")):
            return {
                "schema": SCHEMA,
                "state": "PLANNED",
                "kind": "ATLASQUANT_NAVIGATION",
                "target": target,
                "adapter_required": "TRUSTED_HOST_NAVIGATION",
                "requires_explicit_approval": False,
                "physical_execution": False,
                "executes_action": False,
            }

    for alias, app in EXTERNAL_APPS.items():
        if alias in command and any(word in command for word in ("abre", "abrir", "toca", "tocar")):
            return {
                "schema": SCHEMA,
                "state": "PLANNED",
                "kind": "LOCAL_APPLICATION",
                "target": app,
                "adapter_required": "SECURE_LOCAL_AGENT",
                "requires_explicit_approval": True,
                "device_supported": device_name == "DESKTOP",
                "physical_execution": False,
                "executes_action": False,
            }

    return {
        "schema": SCHEMA,
        "state": "NO_MATCH",
        "kind": "",
        "target": "",
        "adapter_required": "",
        "requires_explicit_approval": False,
        "physical_execution": False,
        "executes_action": False,
    }


def interaction_mode_plan(
    mode: Any,
    *,
    topic: Any = "",
    sector: Any = "",
) -> dict[str, Any]:
    value = _clean(mode, 24).upper()
    if value not in MODES:
        raise ValueError("unsupported interaction mode")
    topic_text = _clean(topic, 240)
    sector_text = _clean(sector, 120)

    if value == "TEACHING":
        return {
            "schema": SCHEMA,
            "state": "READY",
            "mode": value,
            "topic": topic_text,
            "voice_style": "CALM_PATIENT",
            "slides": True,
            "drawings": True,
            "exercises": True,
            "adaptive_depth": True,
            "external_action_executed": False,
            "executes_action": False,
        }
    if value == "MEETING":
        return {
            "schema": SCHEMA,
            "state": "READY",
            "mode": value,
            "sector": sector_text,
            "presentation_state": "IDLE",
            "slides": True,
            "live_demo_supported": True,
            "pause_for_questions": True,
            "resume_to_prior_slide": True,
            "external_action_executed": False,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "READY",
        "mode": value,
        "external_action_executed": False,
        "executes_action": False,
    }


def meeting_transition(current: Any, event: Any, *, slide: int = 0) -> dict[str, Any]:
    state = _clean(current, 40).upper()
    action = _clean(event, 40).upper()
    if state not in MEETING_STATES:
        raise ValueError("invalid meeting state")
    if isinstance(slide, bool) or not isinstance(slide, int) or slide < 0:
        raise ValueError("invalid slide")

    transitions = {
        ("IDLE", "START"): "PRESENTING",
        ("PRESENTING", "QUESTION"): "PAUSED_FOR_QA",
        ("PAUSED_FOR_QA", "ANSWERED"): "RESUME_PENDING",
        ("RESUME_PENDING", "RESUME"): "PRESENTING",
        ("PRESENTING", "STOP"): "IDLE",
        ("PAUSED_FOR_QA", "STOP"): "IDLE",
        ("RESUME_PENDING", "STOP"): "IDLE",
    }
    next_state = transitions.get((state, action))
    if next_state is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "INVALID_MEETING_TRANSITION",
            "meeting_state": state,
            "slide": slide,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "TRANSITION_PLANNED",
        "meeting_state": next_state,
        "return_slide": slide if next_state in {"PAUSED_FOR_QA", "RESUME_PENDING", "PRESENTING"} else 0,
        "executes_action": False,
    }


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _clean(key, 120).casefold()
            if normalized in _FORBIDDEN_HANDOFF_KEYS:
                return True
            if _contains_forbidden_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def continuity_handoff(
    *,
    source_device: Any,
    target_device: Any,
    owner_subject: Any,
    conversation_id: Any,
    last_turn_id: Any = "",
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = _clean(source_device, 20).upper()
    target = _clean(target_device, 20).upper()
    if source not in DEVICES or target not in DEVICES:
        raise ValueError("unsupported device")
    subject = _clean(owner_subject, 120)
    conversation = _clean(conversation_id, 160)
    turn = _clean(last_turn_id, 160)
    safe_context = _mapping(context)
    if not subject or not conversation:
        raise ValueError("owner subject and conversation required")
    if _contains_forbidden_key(safe_context):
        raise ValueError("secret-bearing continuity context forbidden")

    public_context = {
        str(key)[:80]: value
        for key, value in safe_context.items()
        if _clean(key, 120).casefold() not in _FORBIDDEN_HANDOFF_KEYS
    }
    payload = {
        "owner_subject": subject,
        "conversation_id": conversation,
        "last_turn_id": turn,
        "source_device": source,
        "target_device": target,
        "context": public_context,
    }
    return {
        "schema": SCHEMA,
        "state": "HANDOFF_READY",
        **payload,
        "handoff_digest": _canonical_digest(payload),
        "authentication_transferred": False,
        "session_token_transferred": False,
        "secrets_transferred": False,
        "requires_target_reauthentication": True,
        "executes_action": False,
    }


def owner_experience_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "principal": PRINCIPAL,
        "devices": sorted(DEVICES),
        "modes": sorted(MODES),
        "hotword": "AION",
        "owner_assertion_injected": True,
        "owner_identity_inferred": False,
        "automatic_app_launch": False,
        "automatic_navigation": False,
        "microphone_started": False,
        "continuous_listener_started": False,
        "cross_device_authentication_transfer": False,
        "secure_local_agent_required_for_external_apps": True,
        "worker_armed": False,
        "deploy_executed": False,
        "core_checkpoint_write": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "PRINCIPAL",
    "DEVICES",
    "MODES",
    "MEETING_STATES",
    "owner_binding",
    "owner_greeting_plan",
    "voice_capability_plan",
    "command_plan",
    "interaction_mode_plan",
    "meeting_transition",
    "continuity_handoff",
    "owner_experience_policy",
]
