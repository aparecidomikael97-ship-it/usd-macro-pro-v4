"""Presentation-only policy for the restricted Sales navigation item."""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_SALES_VISIBILITY_V1"
POLICIES = ("VISIBLE_LOCKED", "HIDE_FROM_USER")


def sales_menu_policy(
    access: Mapping[str, Any] | None,
    policy: object = "VISIBLE_LOCKED",
) -> dict[str, Any]:
    role = str((access or {}).get("role") or "").strip().upper()
    selected = str(policy or "VISIBLE_LOCKED").strip().upper()
    if selected not in POLICIES:
        selected = "VISIBLE_LOCKED"
    authorized = role in {"SALES", "ADMIN"}
    visible = authorized or selected == "VISIBLE_LOCKED"
    return {
        "schema": SCHEMA,
        "role": role,
        "policy": selected,
        "visible": visible,
        "authorized": authorized,
        "authorization_changed": False,
    }


__all__ = ["POLICIES", "SCHEMA", "sales_menu_policy"]
