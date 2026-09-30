"""AION BUSINESS Team Access Sandbox Evidence V1.

Validates read-only evidence captured from the isolated physical sandbox.

The collector output is intentionally separate from lifecycle mutation evidence.
This module never calls Docker, Keycloak, PostgreSQL or the network and never
stores credentials. It only validates supplied observations and prepares an
administrative review packet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_SANDBOX_EVIDENCE_V1"
VERSION = "1"

EXPECTED_KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.7.5"
EXPECTED_POSTGRES_IMAGE = "postgres:18.6"
EXPECTED_SERVICES = ("keycloak", "keycloak-db", "registry-db")
EXPECTED_REGISTRY_TABLES = ("registry_revisions", "team_memberships")

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
_LOCAL_ISSUER = re.compile(
    r"^http://(?:127\.0\.0\.1|localhost):\d+/realms/atlasquant-sandbox$"
)
_SENSITIVE_KEY = re.compile(
    r"(password|passwd|secret|token|authorization|credential|private[_-]?key)",
    re.I,
)


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set, frozenset)) else []


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                return True
            if _contains_sensitive_key(item):
                return True
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def sandbox_evidence_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_SANDBOX_EVIDENCE_POLICY_DEFINED",
        "expected_keycloak_image": EXPECTED_KEYCLOAK_IMAGE,
        "expected_postgres_image": EXPECTED_POSTGRES_IMAGE,
        "expected_services": list(EXPECTED_SERVICES),
        "expected_registry_tables": list(EXPECTED_REGISTRY_TABLES),
        "local_only": True,
        "secrets_allowed": False,
        "mutation_evidence_collected_here": False,
        "production_evidence_allowed": False,
        "executes_action": False,
    }


def validate_baseline_evidence(
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(evidence)
    oidc = _mapping(row.get("oidc"))
    artifacts = _mapping(row.get("artifacts"))
    services = sorted({_clean(item, 80) for item in _list(row.get("running_services")) if _clean(item, 80)})
    tables = sorted({_clean(item, 80) for item in _list(row.get("registry_tables")) if _clean(item, 80)})
    captured_at = _parse_time(row.get("captured_at"))

    artifact_digests = [
        _clean(value, 80).lower()
        for value in artifacts.values()
        if _clean(value, 80)
    ]
    issuer = _clean(oidc.get("issuer"), 400)
    keycloak_image = _clean(row.get("keycloak_image"), 240)
    postgres_image = _clean(row.get("postgres_image"), 240)

    gates = {
        "schema_valid": row.get("schema") == SCHEMA,
        "environment_sandbox": _clean(row.get("environment"), 40).upper() == "SANDBOX",
        "production_environment_false": row.get("production_environment") is False,
        "collector_read_only": row.get("collector_executes_mutation") is False,
        "side_effects_absent": row.get("external_side_effects_executed") is False,
        "secrets_declared_absent": row.get("secrets_included") is False,
        "sensitive_keys_absent": not _contains_sensitive_key(row),
        "captured_at_valid": captured_at is not None,
        "keycloak_image_matches": keycloak_image == EXPECTED_KEYCLOAK_IMAGE,
        "postgres_image_matches": postgres_image == EXPECTED_POSTGRES_IMAGE,
        "services_complete": set(EXPECTED_SERVICES).issubset(services),
        "registry_tables_complete": set(EXPECTED_REGISTRY_TABLES).issubset(tables),
        "oidc_issuer_local": bool(_LOCAL_ISSUER.fullmatch(issuer)),
        "artifact_digest_set_present": len(artifact_digests) >= 3,
        "artifact_digests_valid": bool(artifact_digests)
        and all(_DIGEST64.fullmatch(item) for item in artifact_digests),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    canonical = {
        "captured_at": captured_at.isoformat() if captured_at else "",
        "keycloak_image": keycloak_image,
        "postgres_image": postgres_image,
        "running_services": services,
        "registry_tables": tables,
        "oidc_issuer": issuer,
        "artifacts": dict(sorted(artifacts.items())),
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW"
            if ready
            else "TEAM_ACCESS_SANDBOX_BASELINE_EVIDENCE_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "evidence_digest": _digest(canonical) if ready else "",
        "captured_at": captured_at.isoformat() if ready and captured_at else "",
        "issuer": issuer if ready else "",
        "running_services": services if ready else [],
        "registry_tables": tables if ready else [],
        "secrets_returned": False,
        "lifecycle_mutation_authorized": False,
        "production_authorized": False,
        "deploy_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def lifecycle_evidence_template(
    baseline_review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    baseline = _mapping(baseline_review)
    baseline_ready = (
        baseline.get("schema") == SCHEMA
        and baseline.get("state")
        == "READY_FOR_ADMIN_TEAM_ACCESS_SANDBOX_LIFECYCLE_TEST_REVIEW"
        and bool(_DIGEST64.fullmatch(_clean(baseline.get("evidence_digest"), 80)))
        and baseline.get("executes_action") is False
    )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "TEAM_ACCESS_SANDBOX_LIFECYCLE_EVIDENCE_TEMPLATE_READY"
            if baseline_ready
            else "TEAM_ACCESS_SANDBOX_LIFECYCLE_EVIDENCE_TEMPLATE_BLOCKED"
        ),
        "baseline_evidence_digest": (
            baseline.get("evidence_digest") if baseline_ready else ""
        ),
        "required_manual_evidence": [
            "individual_account_created_in_sandbox",
            "account_username_matches_invitation",
            "strong_auth_enrollment_verified",
            "strong_auth_challenge_verified",
            "registry_revision_persisted",
            "registry_exact_readback_digest_verified",
            "account_disabled_verified",
            "sessions_revoked_verified",
            "registry_membership_inactive_verified",
            "registry_inactive_readback_verified",
        ] if baseline_ready else [],
        "automatic_account_creation": False,
        "automatic_mfa_enrollment": False,
        "automatic_registry_write": False,
        "automatic_session_revocation": False,
        "production_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "EXPECTED_KEYCLOAK_IMAGE",
    "EXPECTED_POSTGRES_IMAGE",
    "EXPECTED_SERVICES",
    "EXPECTED_REGISTRY_TABLES",
    "sandbox_evidence_policy",
    "validate_baseline_evidence",
    "lifecycle_evidence_template",
]
