"""AION Admin guidance adapters.

Pure/offline adapters that bind the existing Intelligent Onboarding and Admin
Copilot contracts to the administrator session without widening permissions.

This module never writes Streamlit session state, the Checkpoint Mestre or any
runtime. The UI owns session-local progress explicitly.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Mapping

from atlasquant_access_control import normalize_role
from atlasquant_aion_admin_copilot import build_admin_copilot
from atlasquant_aion_onboarding import assess_onboarding


SCHEMA = "ATLASQUANT_AION_ADMIN_GUIDANCE_V1"
EXPERIENCE_MODES = ("BEGINNER", "ADVANCED")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def admin_subject_ref(access: Mapping[str, Any] | None) -> str:
    """Return an opaque subject bound to the authenticated credential/session."""
    root = _mapping(access)
    session = _mapping(root.get("session"))
    seed = str(
        session.get("credential_fingerprint")
        or root.get("credential_fingerprint")
        or session.get("username")
        or root.get("username")
        or ""
    ).strip()
    if not seed:
        return ""
    digest = sha256(("aion-admin-onboarding|" + seed).encode("utf-8")).hexdigest()
    return "admin-" + digest[:24]


def build_admin_onboarding_payload(
    access: Mapping[str, Any] | None,
    *,
    experience_mode: Any,
    started_at: Any,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build only evidence already present in the current administrator session."""
    root = _mapping(access)
    session = _mapping(root.get("session"))
    role = normalize_role(root.get("role") or session.get("role"))
    mode = str(experience_mode or "").strip().upper()
    started = str(started_at or "").strip()
    flags = {
        str(key): value
        for key, value in dict(feature_flags or {}).items()
        if isinstance(key, str) and type(value) is bool
    }
    system = dict(system_context or {})

    payload: dict[str, Any] = {
        "subject_ref": admin_subject_ref(root),
        "role": role,
        "experience_mode": mode,
        "updated_at": started,
        "feature_flags": flags,
    }
    operational = system.get("operational_integration_confirmed")
    if type(operational) is bool:
        payload["operational_integration_confirmed"] = operational
    return payload


def build_admin_onboarding_snapshot(
    access: Mapping[str, Any] | None,
    *,
    experience_mode: Any,
    started_at: Any,
    feature_flags: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    progress: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = build_admin_onboarding_payload(
        access,
        experience_mode=experience_mode,
        started_at=started_at,
        feature_flags=feature_flags,
        system_context=system_context,
    )
    return assess_onboarding(payload, progress, now=now)


def build_admin_copilot_snapshot(
    *,
    status_board: Mapping[str, Any] | None = None,
    incident_snapshot: Mapping[str, Any] | None = None,
    executive_snapshot: Mapping[str, Any] | None = None,
    reliability_snapshot: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    max_items: int = 6,
) -> dict[str, Any]:
    board = dict(status_board or {})
    system = dict(system_context or {})
    return build_admin_copilot(
        status_board=board,
        system_health_center=(
            board.get("system_health_center")
            if isinstance(board.get("system_health_center"), Mapping)
            else {}
        ),
        cost_center=(
            board.get("cost_center")
            if isinstance(board.get("cost_center"), Mapping)
            else {}
        ),
        release_matrix=(
            system.get("release_matrix")
            if isinstance(system.get("release_matrix"), Mapping)
            else {}
        ),
        incident_snapshot=incident_snapshot,
        executive_snapshot=executive_snapshot,
        reliability_snapshot=reliability_snapshot,
        max_items=max_items,
    )


__all__ = [
    "SCHEMA",
    "EXPERIENCE_MODES",
    "admin_subject_ref",
    "build_admin_onboarding_payload",
    "build_admin_onboarding_snapshot",
    "build_admin_copilot_snapshot",
]
