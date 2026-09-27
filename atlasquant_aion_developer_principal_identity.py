"""Stable principal identity for the AION Developer chain.

display_actor is a label. principal_id is the only value used to separate
roles. The principal id is never derived from the display name, and display
similarity is not identity. This module does not fold Unicode confusables and
does not apply NFKC.

No process, network, filesystem write, commit, merge, deploy or execution
authority is created here.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PRINCIPAL_IDENTITY_V1"
PRINCIPAL_BINDING_VERSION = "ATLASQUANT_AION_DEVELOPER_PRINCIPAL_BINDING_V1"

ROLE_FIELDS = (
    "builder_principal_id",
    "reviewer_principal_id",
    "breaker_principal_id",
    "approver_principal_id",
    "attestor_principal_id",
)
READINESS_PRINCIPAL_FIELDS = (
    "builder_principal_id",
    "reviewer_principal_id",
    "breaker_principal_id",
)
AUTHORIZATION_PRINCIPAL_FIELDS = READINESS_PRINCIPAL_FIELDS + (
    "approver_principal_id",
)

_PRINCIPAL_RE = re.compile(r"^prn_[a-z0-9]{8,64}$")


def require_principal_id(value: Any, field: str = "principal_id") -> str:
    """Accept an explicit principal id without rewriting it.

    Empty, external whitespace, controls, format characters and any other
    whitespace are rejected. A string that does not already match the
    restricted pattern is rejected rather than normalized.
    """
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an explicit string")
    if not value or value != value.strip():
        raise ValueError(f"{field} is empty or has external whitespace")
    if any(
        unicodedata.category(char) in {"Cc", "Cf"}
        or char.isspace()
        or unicodedata.category(char).startswith("Z")
        for char in value
    ):
        raise ValueError(f"{field} contains control, invisible, or whitespace characters")
    if not _PRINCIPAL_RE.fullmatch(value):
        raise ValueError(f"{field} does not match the restricted principal format")
    return value


def require_distinct_principal_ids(
    values: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, str]:
    """Require one explicit principal id per field, all pairwise distinct.

    Equality is exact principal_id equality. Display labels are not read.
    """
    if not isinstance(values, Mapping):
        raise ValueError("principal roles must be an object")
    resolved: dict[str, str] = {}
    owner: dict[str, str] = {}
    for field in fields:
        principal_id = require_principal_id(values.get(field), field)
        previous = owner.get(principal_id)
        if previous is not None:
            raise ValueError(f"principal ids collide: {previous} and {field}")
        owner[principal_id] = field
        resolved[field] = principal_id
    return resolved


def assert_independent_principals(roles: Mapping[str, Any]) -> dict[str, str]:
    """Require five distinct principal ids, one per role.

    Equality is exact principal_id equality. Display labels are ignored, so
    two different spellings of a name that share one principal id still
    collide, and two identical labels with different ids stay distinct.
    """
    return require_distinct_principal_ids(roles, ROLE_FIELDS)


def assert_attestor_independent(
    attestor_principal_id: Any,
    prior_roles: Mapping[str, Any],
) -> str:
    """Compare the attestor with earlier role principals.

    Display labels are not consulted. The same principal id collides even
    when the labels differ.
    """
    attestor = require_principal_id(attestor_principal_id, "attestor_principal_id")
    prior = require_distinct_principal_ids(prior_roles, AUTHORIZATION_PRINCIPAL_FIELDS)
    for field, principal_id in prior.items():
        if principal_id == attestor:
            raise ValueError(f"attestor principal collides with {field}")
    return attestor


def classify_actor_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    """Classify two actors by principal id only.

    SAME_PRINCIPAL means the ids are exactly equal, including when the display
    labels differ by homoglyphs. DISTINCT_PRINCIPALS does not mean the displays
    were proved to be different people.
    """
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        raise ValueError("actors must be objects")
    left_id = require_principal_id(left.get("principal_id"), "principal_id")
    right_id = require_principal_id(right.get("principal_id"), "principal_id")
    if left_id == right_id:
        return "SAME_PRINCIPAL"
    return "DISTINCT_PRINCIPALS"


__all__ = [
    "SCHEMA",
    "PRINCIPAL_BINDING_VERSION",
    "ROLE_FIELDS",
    "READINESS_PRINCIPAL_FIELDS",
    "AUTHORIZATION_PRINCIPAL_FIELDS",
    "require_principal_id",
    "require_distinct_principal_ids",
    "assert_independent_principals",
    "assert_attestor_independent",
    "classify_actor_pair",
]
