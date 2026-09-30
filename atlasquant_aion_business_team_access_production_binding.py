"""AION BUSINESS Team Access Production Binding V1.

Read-only evidence binding between the existing Business RBAC contract and
future production identity/session infrastructure.

This module never creates accounts, sends invitations, stores passwords,
enables MFA, writes the registry, revokes sessions, disables accounts, changes
roles, calls providers, deploys or activates runtime. It only validates
caller-supplied evidence and prepares administrative review packets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re

from atlasquant_access_control import normalize_username
from atlasquant_aion_business_team_access_rbac import (
    SCHEMA as TEAM_RBAC_SCHEMA,
)

SCHEMA = "ATLASQUANT_AION_BUSINESS_TEAM_ACCESS_PRODUCTION_BINDING_V1"
VERSION = "1"

STRONG_AUTH_FACTORS = (
    "PASSKEY",
    "SECURITY_KEY",
    "TOTP",
)

GENESIS_DIGEST = "0" * 64
_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _positive_int(value: Any, *, maximum: int = 1_000_000) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 1 or value > maximum:
        return None
    return value


def production_binding_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TEAM_ACCESS_PRODUCTION_EVIDENCE_REQUIRED",
        "strong_auth_factors": list(STRONG_AUTH_FACTORS),
        "individual_account_required": True,
        "shared_account_allowed": False,
        "registry_readback_required": True,
        "session_revocation_verification_required": True,
        "account_provisioning_executed_here": False,
        "mfa_enrollment_executed_here": False,
        "registry_write_executed_here": False,
        "session_revocation_executed_here": False,
        "account_disable_executed_here": False,
        "automatic_permission_escalation": False,
        "executes_action": False,
    }


def account_provisioning_attestation(
    invitation_plan: Mapping[str, Any] | None,
    *,
    provider_ref: Any,
    account_ref: Any,
    account_username: Any,
    individual_account_verified: Any,
    shared_account_detected: Any,
    account_active_verified: Any,
    observed_at: Any,
) -> dict[str, Any]:
    invitation = _mapping(invitation_plan)
    membership = _mapping(invitation.get("membership"))
    expected_username = normalize_username(membership.get("username"))
    username = normalize_username(account_username)
    provider = _clean(provider_ref, 180)
    account = _clean(account_ref, 240)
    observed = _parse_time(observed_at)

    gates = {
        "invitation_plan_ready": bool(
            invitation.get("schema") == TEAM_RBAC_SCHEMA
            and invitation.get("state") == "TEAM_INVITATION_REVIEW_READY"
            and invitation.get("invitation_sent") is False
            and invitation.get("account_created") is False
            and invitation.get("membership_applied") is False
            and invitation.get("executes_action") is False
        ),
        "expected_username_present": bool(expected_username),
        "provider_ref_present": bool(provider),
        "account_ref_present": bool(account),
        "username_matches_invitation": bool(
            username and expected_username and username == expected_username
        ),
        "individual_account_verified": individual_account_verified is True,
        "shared_account_absent": shared_account_detected is False,
        "account_active_verified": account_active_verified is True,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())

    payload = {
        "invitation_plan_digest": invitation.get("invitation_plan_digest"),
        "membership_digest": membership.get("membership_digest"),
        "provider_ref": provider,
        "account_ref": account,
        "username": username,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "ACCOUNT_PROVISIONING_ATTESTATION_READY"
            if ready
            else "ACCOUNT_PROVISIONING_ATTESTATION_BLOCKED"
        ),
        "gates": gates,
        "provider_ref": provider if ready else "",
        "account_ref": account if ready else "",
        "username": username if ready else "",
        "membership_digest": membership.get("membership_digest") if ready else "",
        "attestation_digest": _digest(payload) if ready else "",
        "shared_account_detected": False if ready else None,
        "account_created_by_module": False,
        "invitation_sent_by_module": False,
        "credential_value_present": False,
        "executes_action": False,
    }


def strong_auth_attestation(
    account_attestation: Mapping[str, Any] | None,
    *,
    factor_type: Any,
    factor_ref: Any,
    enrollment_verified: Any,
    challenge_verified: Any,
    observed_at: Any,
) -> dict[str, Any]:
    account = _mapping(account_attestation)
    factor = _clean(factor_type, 60).upper()
    factor_reference = _clean(factor_ref, 240)
    observed = _parse_time(observed_at)

    gates = {
        "account_attestation_ready": (
            account.get("schema") == SCHEMA
            and account.get("state") == "ACCOUNT_PROVISIONING_ATTESTATION_READY"
        ),
        "strong_factor_allowed": factor in STRONG_AUTH_FACTORS,
        "factor_ref_present": bool(factor_reference),
        "enrollment_verified": enrollment_verified is True,
        "challenge_verified": challenge_verified is True,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())

    payload = {
        "account_attestation_digest": account.get("attestation_digest"),
        "username": account.get("username"),
        "factor_type": factor,
        "factor_ref": factor_reference,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "STRONG_AUTH_ATTESTATION_READY" if ready else "STRONG_AUTH_ATTESTATION_BLOCKED",
        "gates": gates,
        "username": account.get("username") if ready else "",
        "account_attestation_digest": account.get("attestation_digest") if ready else "",
        "factor_type": factor if ready else "",
        "factor_ref": factor_reference if ready else "",
        "attestation_digest": _digest(payload) if ready else "",
        "mfa_enabled_by_module": False,
        "credential_value_present": False,
        "executes_action": False,
    }


def _registry_payload(
    registry_audit: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str], str]:
    audit = _mapping(registry_audit)
    memberships = list(audit.get("memberships") or [])
    digests: list[str] = []
    canonical: list[dict[str, Any]] = []

    for raw in memberships:
        row = _mapping(raw)
        digest = _clean(row.get("membership_digest"), 80).lower()
        if not _DIGEST64.fullmatch(digest):
            return {}, [], ""
        username = normalize_username(row.get("username"))
        if not username:
            return {}, [], ""
        digests.append(digest)
        canonical.append({
            "username": username,
            "profile": _clean(row.get("profile"), 80),
            "tenant_ids": sorted(str(x) for x in list(row.get("tenant_ids") or [])),
            "active": row.get("active") is True,
            "strong_auth_required": row.get("strong_auth_required") is True,
            "membership_digest": digest,
        })

    canonical.sort(key=lambda x: x["username"])
    payload = {
        "team_rbac_schema": audit.get("schema"),
        "member_count": audit.get("member_count"),
        "memberships": canonical,
    }
    return payload, sorted(digests), _digest(payload) if canonical else ""


def registry_persistence_attestation(
    registry_audit: Mapping[str, Any] | None,
    *,
    storage_ref: Any,
    revision: Any,
    previous_revision_digest: Any,
    readback_registry_digest: Any,
    persistence_verified: Any,
    readback_verified: Any,
    observed_at: Any,
) -> dict[str, Any]:
    audit = _mapping(registry_audit)
    payload, membership_digests, expected_registry_digest = _registry_payload(audit)
    storage = _clean(storage_ref, 300)
    revision_no = _positive_int(revision)
    previous = _clean(previous_revision_digest, 80).lower()
    readback = _clean(readback_registry_digest, 80).lower()
    observed = _parse_time(observed_at)

    gates = {
        "registry_audit_verified": bool(
            audit.get("schema") == TEAM_RBAC_SCHEMA
            and audit.get("state") == "TEAM_REGISTRY_INTEGRITY_VERIFIED"
            and audit.get("integrity_verified") is True
            and audit.get("executes_action") is False
        ),
        "registry_payload_valid": bool(expected_registry_digest),
        "storage_ref_present": bool(storage),
        "revision_valid": revision_no is not None,
        "previous_revision_digest_valid": bool(_DIGEST64.fullmatch(previous)),
        "genesis_only_for_first_revision": bool(
            revision_no is not None
            and (
                (revision_no == 1 and previous == GENESIS_DIGEST)
                or (revision_no > 1 and previous != GENESIS_DIGEST)
            )
        ),
        "persistence_verified": persistence_verified is True,
        "readback_verified": readback_verified is True,
        "readback_digest_matches": bool(
            expected_registry_digest
            and readback == expected_registry_digest
        ),
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())

    attestation_payload = {
        "storage_ref": storage,
        "revision": revision_no,
        "previous_revision_digest": previous,
        "registry_digest": expected_registry_digest,
        "membership_digests": membership_digests,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "REGISTRY_PERSISTENCE_ATTESTATION_READY"
            if ready
            else "REGISTRY_PERSISTENCE_ATTESTATION_BLOCKED"
        ),
        "gates": gates,
        "storage_ref": storage if ready else "",
        "revision": revision_no if ready else None,
        "previous_revision_digest": previous if ready else "",
        "registry_digest": expected_registry_digest if ready else "",
        "membership_digests": membership_digests if ready else [],
        "attestation_digest": _digest(attestation_payload) if ready else "",
        "registry_written_by_module": False,
        "registry_mutation_authorized": False,
        "executes_action": False,
    }


def team_access_activation_review(
    invitation_plan: Mapping[str, Any] | None,
    account_attestation: Mapping[str, Any] | None,
    strong_auth: Mapping[str, Any] | None,
    registry_attestation: Mapping[str, Any] | None,
    *,
    requested_by: Any,
) -> dict[str, Any]:
    invitation = _mapping(invitation_plan)
    membership = _mapping(invitation.get("membership"))
    account = _mapping(account_attestation)
    auth = _mapping(strong_auth)
    registry = _mapping(registry_attestation)
    requester = normalize_username(requested_by)
    membership_digest = _clean(membership.get("membership_digest"), 80).lower()

    gates = {
        "invitation_plan_ready": invitation.get("state") == "TEAM_INVITATION_REVIEW_READY",
        "account_attested": account.get("state") == "ACCOUNT_PROVISIONING_ATTESTATION_READY",
        "strong_auth_attested": auth.get("state") == "STRONG_AUTH_ATTESTATION_READY",
        "registry_persistence_attested": registry.get("state") == "REGISTRY_PERSISTENCE_ATTESTATION_READY",
        "membership_digest_present": bool(_DIGEST64.fullmatch(membership_digest)),
        "account_matches_membership": account.get("membership_digest") == membership_digest,
        "auth_matches_account": auth.get("account_attestation_digest") == account.get("attestation_digest"),
        "registry_contains_membership": membership_digest in list(registry.get("membership_digests") or []),
        "username_consistent": bool(
            account.get("username")
            and account.get("username") == auth.get("username")
            and account.get("username") == membership.get("username")
        ),
        "requester_present": bool(requester),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "invitation_plan_digest": invitation.get("invitation_plan_digest"),
        "account_attestation_digest": account.get("attestation_digest"),
        "strong_auth_attestation_digest": auth.get("attestation_digest"),
        "registry_attestation_digest": registry.get("attestation_digest"),
        "membership_digest": membership_digest,
        "requested_by": requester,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_TEAM_ACCESS_ACTIVATION_REVIEW"
            if ready
            else "TEAM_ACCESS_ACTIVATION_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "username": account.get("username") if ready else "",
        "membership_digest": membership_digest if ready else "",
        "review_digest": _digest(payload) if ready else "",
        "access_activation_authorized": False,
        "session_activation_authorized": False,
        "permission_escalation_authorized": False,
        "billing_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


def revocation_execution_attestation(
    revocation_plan: Mapping[str, Any] | None,
    *,
    provider_ref: Any,
    evidence_ref: Any,
    account_disabled_verified: Any,
    sessions_revoked_verified: Any,
    registry_membership_inactive_verified: Any,
    registry_readback_verified: Any,
    observed_at: Any,
) -> dict[str, Any]:
    plan = _mapping(revocation_plan)
    provider = _clean(provider_ref, 180)
    evidence = _clean(evidence_ref, 300)
    observed = _parse_time(observed_at)

    gates = {
        "revocation_plan_ready": bool(
            plan.get("schema") == TEAM_RBAC_SCHEMA
            and plan.get("state") == "TEAM_REVOCATION_REVIEW_READY"
            and plan.get("membership_revoked") is False
            and plan.get("session_revoked") is False
            and plan.get("account_disabled") is False
            and plan.get("executes_action") is False
        ),
        "provider_ref_present": bool(provider),
        "evidence_ref_present": bool(evidence),
        "account_disabled_verified": account_disabled_verified is True,
        "sessions_revoked_verified": sessions_revoked_verified is True,
        "registry_membership_inactive_verified": registry_membership_inactive_verified is True,
        "registry_readback_verified": registry_readback_verified is True,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())

    payload = {
        "revocation_plan_digest": plan.get("revocation_plan_digest"),
        "target_username": plan.get("target_username"),
        "provider_ref": provider,
        "evidence_ref": evidence,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "TEAM_REVOCATION_EXTERNALLY_VERIFIED"
            if ready
            else "TEAM_REVOCATION_VERIFICATION_BLOCKED"
        ),
        "gates": gates,
        "target_username": plan.get("target_username") if ready else "",
        "verification_digest": _digest(payload) if ready else "",
        "account_disable_executed_by_module": False,
        "session_revocation_executed_by_module": False,
        "registry_write_executed_by_module": False,
        "access_reactivation_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "STRONG_AUTH_FACTORS",
    "GENESIS_DIGEST",
    "production_binding_policy",
    "account_provisioning_attestation",
    "strong_auth_attestation",
    "registry_persistence_attestation",
    "team_access_activation_review",
    "revocation_execution_attestation",
]
