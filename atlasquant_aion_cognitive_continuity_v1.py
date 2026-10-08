"""AION Cognitive Memory + Continuity V1 integration facade.

This module reuses the existing governed memory, mission continuity and chat
resume contracts. It does not create a second memory database, transfer
authentication between devices, promote memory automatically, persist a Core
checkpoint, call providers, or execute external actions.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from aion_core.memory_architecture import list_history
from atlasquant_aion_chat_resume_bridge import SCHEMA as CHAT_RESUME_SCHEMA
from atlasquant_aion_continuity import continuity_briefing, continuity_digest
from atlasquant_aion_memory_layers import recall
from atlasquant_aion_owner_experience_v1 import continuity_handoff


SCHEMA = "ATLASQUANT_AION_COGNITIVE_CONTINUITY_V1"
VERIFY_SCHEMA = "ATLASQUANT_AION_COGNITIVE_CONTINUITY_VERIFY_V1"

CHANNELS = ("SEMANTIC", "EPISODIC", "PROCEDURAL", "DECISION")
_LAYERED_CHANNELS = {
    "SEMANTIC": "knowledge",
    "EPISODIC": "episodic",
    "DECISION": "decision",
}
_FORBIDDEN_TRUE_FLAGS = frozenset({
    "authentication_transferred",
    "session_token_transferred",
    "credentials_transferred",
    "memory_promoted",
    "automatic_memory_promotion",
    "automatic_checkpoint_write",
    "core_checkpoint_write",
    "provider_called",
    "network_called",
    "tool_executed",
    "external_action_executed",
    "grants_authority",
    "executes_action",
})
_TOP_LEVEL_AUTH_KEYS = frozenset({
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
_MAX_PER_CHANNEL = 100


def _clean(value: Any, limit: int = 400) -> str:
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


def _bounded_limit(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("limit_per_channel must be an integer")
    try:
        number = int(value)
    except Exception as exc:
        raise ValueError("limit_per_channel must be an integer") from exc
    if number < 1 or number > _MAX_PER_CHANNEL:
        raise ValueError("limit_per_channel out of range")
    return number


def _scope(
    *,
    persona: Any,
    domain: Any,
    accessor_profile: Any,
    explicit_domains: Sequence[Any] | None,
    tenant_id: Any,
) -> dict[str, Any]:
    domains: list[str] = []
    for item in list(explicit_domains or []):
        token = _clean(item, 40).upper()
        if token and token not in domains:
            domains.append(token)
    return {
        "persona": _clean(persona, 80).lower(),
        "domain": _clean(domain, 40).upper(),
        "accessor_profile": _clean(accessor_profile, 40).upper().replace(" ", "_"),
        "explicit_domains": domains,
        "tenant_id": _clean(tenant_id, 120),
    }


def _project_layered(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "memory_id": _clean(row.get("memory_id"), 120),
        "layer": _clean(row.get("layer"), 40).lower(),
        "category": _clean(row.get("category"), 120),
        "content": _clean(row.get("content"), 4000),
        "origin": _clean(row.get("origin"), 240),
        "truth_state": _clean(row.get("truth_state"), 40).upper(),
        "confidence": row.get("confidence"),
        "status": _clean(row.get("status"), 40).upper(),
        "promotion_state": _clean(row.get("promotion_state"), 40).upper(),
        "domain": _clean(row.get("domain"), 40).upper(),
        "persona": _clean(row.get("persona"), 80).lower(),
        "source_refs": [
            _clean(item, 240) for item in list(row.get("source_refs") or [])[:24]
            if _clean(item, 240)
        ],
        "valid_until": _clean(row.get("valid_until"), 100),
        "used_as_current_fact": bool(row.get("used_as_current_fact") is True),
    }


def _project_procedural(row: Mapping[str, Any]) -> dict[str, Any]:
    state = _clean(row.get("state"), 40).upper()
    return {
        "memory_id": _clean(row.get("memory_id"), 120),
        "layer": "procedural",
        "content": _clean(row.get("content"), 4000),
        "state": state,
        "confidence": row.get("confidence"),
        "tenant_id": _clean(row.get("tenant_id"), 120),
        "domain_id": _clean(row.get("domain_id"), 40).upper(),
        "source_ref": _clean(row.get("source_ref"), 240),
        "version": _clean(row.get("version"), 40),
        "used_as_current_fact": state == "VALIDATED",
    }


def _snapshot_material(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scope": dict(snapshot.get("scope") or {}),
        "channels": dict(snapshot.get("channels") or {}),
        "counts": dict(snapshot.get("counts") or {}),
    }


def cognitive_memory_snapshot(
    layered_memory: Mapping[str, Any] | None,
    architecture_store: Mapping[str, Any] | None,
    *,
    persona: Any = "",
    domain: Any = "",
    accessor_profile: Any = "AION_CORE",
    explicit_domains: Sequence[Any] | None = None,
    tenant_id: Any = "",
    limit_per_channel: int = 20,
) -> dict[str, Any]:
    """Build one read-only cognitive view from existing memory systems."""
    limit = _bounded_limit(limit_per_channel)
    scope = _scope(
        persona=persona,
        domain=domain,
        accessor_profile=accessor_profile,
        explicit_domains=explicit_domains,
        tenant_id=tenant_id,
    )

    channels: dict[str, list[dict[str, Any]]] = {}
    for channel, layer in _LAYERED_CHANNELS.items():
        rows = recall(
            layered_memory,
            layers=(layer,),
            persona=scope["persona"],
            domain=scope["domain"],
            accessor_profile=scope["accessor_profile"],
            explicit_domains=scope["explicit_domains"],
            limit=limit,
        )
        channels[channel] = [_project_layered(row) for row in rows[:limit]]

    procedural: list[dict[str, Any]] = []
    for row in reversed(list_history(architecture_store, include_non_operational=False)):
        if _clean(row.get("layer"), 40).upper() != "PROCEDURAL":
            continue
        row_tenant = _clean(row.get("tenant_id"), 120)
        row_domain = _clean(row.get("domain_id"), 40).upper()
        if scope["tenant_id"] and row_tenant and row_tenant != scope["tenant_id"]:
            continue
        if scope["domain"] and row_domain and row_domain != scope["domain"]:
            continue
        procedural.append(_project_procedural(row))
        if len(procedural) >= limit:
            break
    channels["PROCEDURAL"] = procedural

    ordered = {channel: channels.get(channel, []) for channel in CHANNELS}
    counts = {channel: len(ordered[channel]) for channel in CHANNELS}
    snapshot = {
        "schema": SCHEMA,
        "state": "READY",
        "scope": scope,
        "channels": ordered,
        "counts": counts,
        "memory_digest": "",
        "authentication_embedded": False,
        "credentials_embedded": False,
        "automatic_memory_promotion": False,
        "memory_promoted": False,
        "memory_persisted": False,
        "automatic_checkpoint_write": False,
        "core_checkpoint_write": False,
        "provider_called": False,
        "network_called": False,
        "tool_executed": False,
        "external_action_executed": False,
        "grants_authority": False,
        "executes_action": False,
    }
    snapshot["memory_digest"] = _digest(_snapshot_material(snapshot))
    return snapshot


def verify_cognitive_memory_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers: list[str] = []
    raw = dict(snapshot or {})
    if raw.get("schema") != SCHEMA:
        blockers.append("SCHEMA_MISMATCH")

    channels = raw.get("channels")
    if not isinstance(channels, Mapping):
        blockers.append("CHANNELS_MISSING")
    else:
        if tuple(channels.keys()) != CHANNELS:
            blockers.append("CHANNEL_SET_MISMATCH")
        for channel in CHANNELS:
            if not isinstance(channels.get(channel), list):
                blockers.append("CHANNEL_INVALID:" + channel)

    supplied = _clean(raw.get("memory_digest"), 80)
    expected = _digest(_snapshot_material(raw))
    if supplied != expected:
        blockers.append("MEMORY_DIGEST_MISMATCH")

    for flag in _FORBIDDEN_TRUE_FLAGS:
        if raw.get(flag) is True:
            blockers.append("FORBIDDEN_TRUE_FLAG:" + flag)

    if raw.get("authentication_embedded") is True:
        blockers.append("AUTHENTICATION_MUST_NOT_BE_EMBEDDED")
    if raw.get("credentials_embedded") is True:
        blockers.append("CREDENTIALS_MUST_NOT_BE_EMBEDDED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "memory_digest": supplied,
        "executes_action": False,
    }


def _validate_resume_envelope(
    resume_context: Mapping[str, Any] | None,
    *,
    conversation_id: str,
) -> dict[str, Any]:
    raw = dict(resume_context or {})
    blockers: list[str] = []
    if raw.get("schema") != CHAT_RESUME_SCHEMA:
        blockers.append("RESUME_SCHEMA_MISMATCH")
    if _clean(raw.get("conversation_id"), 120) != conversation_id:
        blockers.append("RESUME_CONVERSATION_MISMATCH")
    if raw.get("identity_binding_complete") is not True:
        blockers.append("RESUME_IDENTITY_BINDING_INCOMPLETE")
    if not _clean(raw.get("identity_binding_digest"), 100):
        blockers.append("RESUME_IDENTITY_BINDING_DIGEST_REQUIRED")
    if not _clean(raw.get("context_digest"), 100):
        blockers.append("RESUME_CONTEXT_DIGEST_REQUIRED")

    for key in _TOP_LEVEL_AUTH_KEYS:
        if key in raw:
            blockers.append("AUTH_MATERIAL_FORBIDDEN:" + key)
    for flag in _FORBIDDEN_TRUE_FLAGS:
        if raw.get(flag) is True:
            blockers.append("RESUME_FORBIDDEN_TRUE_FLAG:" + flag)

    blockers = list(dict.fromkeys(blockers))
    return {
        "valid": not blockers,
        "blockers": blockers,
        "state": _clean(raw.get("state"), 40).upper(),
        "context_digest": _clean(raw.get("context_digest"), 100),
        "identity_binding_digest": _clean(raw.get("identity_binding_digest"), 100),
        "checkpoint_id": _clean(raw.get("checkpoint_id"), 160),
        "summary_id": _clean(raw.get("summary_id"), 160),
    }


def prepare_cognitive_continuity(
    cognitive_snapshot: Mapping[str, Any],
    resume_context: Mapping[str, Any],
    *,
    source_device: Any,
    target_device: Any,
    owner_subject: Any,
    conversation_id: Any,
    last_turn_id: Any = "",
    missions: Sequence[Mapping[str, Any]] | None = None,
    handoffs: Sequence[Mapping[str, Any]] | None = None,
    tasks: Sequence[Mapping[str, Any]] | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
    checkpoint_digest: Any = "",
    mode: Any = "",
    topic: Any = "",
    slide: Any = None,
) -> dict[str, Any]:
    """Bind memory digests + chat resume + mission continuity for device handoff."""
    verified = verify_cognitive_memory_snapshot(cognitive_snapshot)
    if verified["valid"] is not True:
        raise ValueError("invalid cognitive memory snapshot")

    cid = _clean(conversation_id, 120)
    if not cid:
        raise ValueError("conversation_id required")

    resume = _validate_resume_envelope(resume_context, conversation_id=cid)
    if resume["valid"] is not True:
        raise ValueError("invalid resume context: " + ",".join(resume["blockers"]))

    briefing = continuity_briefing(
        missions,
        handoffs,
        tasks=tasks,
        events=events,
        checkpoint_digest=checkpoint_digest,
    )
    mission_digest = continuity_digest(missions, handoffs)

    safe_context: dict[str, Any] = {
        "cognitive_memory_digest": cognitive_snapshot["memory_digest"],
        "mission_continuity_digest": mission_digest,
        "resume_context_digest": resume["context_digest"],
        "resume_identity_binding_digest": resume["identity_binding_digest"],
        "checkpoint_digest": _clean(checkpoint_digest, 100),
        "mode": _clean(mode, 40).upper(),
        "topic": _clean(topic, 240),
    }
    if isinstance(slide, int) and not isinstance(slide, bool) and slide >= 0:
        safe_context["slide"] = slide

    handoff = continuity_handoff(
        source_device=source_device,
        target_device=target_device,
        owner_subject=owner_subject,
        conversation_id=cid,
        last_turn_id=last_turn_id,
        context=safe_context,
    )

    state = (
        "REHYDRATION_REQUIRED"
        if resume["state"] == "REHYDRATION_REQUIRED"
        else "READY"
    )
    return {
        "schema": SCHEMA,
        "state": state,
        "conversation_id": cid,
        "source_device": handoff["source_device"],
        "target_device": handoff["target_device"],
        "cognitive_memory": {
            "digest": cognitive_snapshot["memory_digest"],
            "counts": dict(cognitive_snapshot.get("counts") or {}),
            "raw_memory_transferred": False,
        },
        "resume": {
            "state": resume["state"],
            "context_digest": resume["context_digest"],
            "identity_binding_digest": resume["identity_binding_digest"],
            "checkpoint_id": resume["checkpoint_id"],
            "summary_id": resume["summary_id"],
            "raw_context_transferred": False,
        },
        "mission_continuity": {
            "digest": mission_digest,
            "current_focus": _clean(briefing.get("current_focus"), 600),
            "next_steps": [
                _clean(item, 600) for item in list(briefing.get("next_steps") or [])[:8]
            ],
            "blockers": [
                _clean(item, 600) for item in list(briefing.get("blockers") or [])[:8]
            ],
        },
        "handoff": handoff,
        "requires_target_reauthentication": True,
        "authentication_transferred": False,
        "session_token_transferred": False,
        "credentials_transferred": False,
        "memory_promoted": False,
        "memory_persisted": False,
        "automatic_checkpoint_write": False,
        "core_checkpoint_write": False,
        "provider_called": False,
        "network_called": False,
        "tool_executed": False,
        "external_action_executed": False,
        "grants_authority": False,
        "executes_action": False,
    }


def cognitive_continuity_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "channels": list(CHANNELS),
        "reuses_existing_memory_systems": True,
        "creates_second_memory_database": False,
        "cross_device_raw_memory_transfer": False,
        "cross_device_raw_chat_context_transfer": False,
        "cross_device_authentication_transfer": False,
        "target_reauthentication_required": True,
        "automatic_memory_promotion": False,
        "automatic_checkpoint_write": False,
        "core_checkpoint_write": False,
        "worker_armed": False,
        "deploy_executed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERIFY_SCHEMA",
    "CHANNELS",
    "cognitive_memory_snapshot",
    "verify_cognitive_memory_snapshot",
    "prepare_cognitive_continuity",
    "cognitive_continuity_policy",
]
