"""AION Repository Mutation Authorization Receipt V1.

Pure, non-executing cryptographic authorization contracts for one future
repository mutation challenge produced by the live merge-step preflight layer.

This module preserves the accepted AION security rule:
SIGNATURE != DECISION != EXECUTION.

Sequence:
1. exact live challenge is verified;
2. external Ed25519 HUMAN_OWNER signature attestation is verified;
3. a separate explicit owner mutation decision is verified;
4. live repository state is rebuilt and must still match the challenge;
5. a single-use repository mutation authorization receipt is produced;
6. an external durable-persistence attestation may prove the receipt was stored.

No GitHub mutation is performed here. No PR is marked ready, retargeted, rebased,
merged, closed or deleted. No deploy/Worker/provider/persistence activation is
performed.

A positive receipt may state repository_mutation_authorized=True because it
represents a future externally verified authorization artifact. It still always
states repository_mutation_performed=False and authorization_consumed=False.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_owner_stack_live_merge_step_preflight_challenge_v1 import (
    CHALLENGE_SCHEMA,
    PREFLIGHT_SCHEMA,
    MUTATIONS,
    verify_owner_authorization_challenge,
)


SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTHORIZATION_RECEIPT_V1"
SIGNATURE_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_OWNER_SIGNATURE_ATTESTATION_V1"
)
DECISION_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_OWNER_DECISION_V1"
RECEIPT_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTHORIZATION_RECEIPT_RECORD_V1"
PERSISTENCE_SCHEMA = (
    "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTHORIZATION_PERSISTENCE_ATTESTATION_V1"
)
VERIFY_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTHORIZATION_VERIFY_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_REPOSITORY_MUTATION_AUTHORIZATION_POLICY_V1"

PURPOSE = "HUMAN_OWNER_EXPLICIT_REPOSITORY_MUTATION_AUTHORIZATION"
MECHANISM = "ED25519_EXTERNAL_OWNER_REPOSITORY_MUTATION_KEY"
DECISIONS = (
    "AUTHORIZE_REPOSITORY_MUTATION",
    "DENY_REPOSITORY_MUTATION",
)
MAX_DECISION_WINDOW_SECONDS = 120

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


def _clean(value: Any, limit: int = 1000) -> str:
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


def _sha(value: Any) -> str:
    token = _clean(value, 60)
    return token if _SHA_RE.fullmatch(token) else ""


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _DIGEST_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"{label} invalid") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{label} timezone required")
    return dt.astimezone(timezone.utc)


def _challenge_binding_material(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "challenge_id",
            "purpose",
            "owner_subject",
            "owner_binding_digest",
            "nonce_digest",
            "pr_number",
            "requested_mutation",
            "preflight_digest",
            "main_sha",
            "main_tree_sha",
            "head_branch",
            "head_sha",
            "base_branch",
            "file_delta_digest",
            "workflow_snapshot_digest",
            "readiness_digest",
            "rollback_plan_digest",
            "confirmation_text",
            "issued_at",
            "expires_at",
            "challenge_digest",
        )
    }


def build_owner_signature_attestation(
    challenge: Mapping[str, Any] | None,
    *,
    owner_key_fingerprint: Any,
    signed_challenge_digest: Any,
    signature_attestation_id: Any,
    verified_owner_signature: bool,
    verified_active_trust_root: bool,
    signer_owner_subject_match: bool,
    signer_owner_binding_match: bool,
    persistent_nonce_replay_guard_verified: bool,
    challenge_nonce_single_use_claimed: bool,
    signature_verified_at: Any,
) -> dict[str, Any]:
    """Represent external verification of challenge signature only.

    A valid signature proves owner/key/challenge identity. It never means the
    owner has made the separate authorize/deny repository-mutation decision.
    """
    raw = dict(challenge or {})
    blockers: list[str] = []

    try:
        now = _aware(signature_verified_at, "signature_verified_at")
        challenge_check = verify_owner_authorization_challenge(
            raw,
            now=now.isoformat(),
        )
    except ValueError:
        now = None
        challenge_check = {"valid": False}
        blockers.append("SIGNATURE_VERIFICATION_TIME_INVALID")

    if challenge_check.get("valid") is not True:
        blockers.append("VALID_FRESH_CHALLENGE_REQUIRED")
    if raw.get("schema") != CHALLENGE_SCHEMA:
        blockers.append("CHALLENGE_SCHEMA_MISMATCH")

    attestation_id = _identity(signature_attestation_id, 180)
    key_fingerprint = _sha256(owner_key_fingerprint)
    signed_digest = _sha256(signed_challenge_digest)
    challenge_digest = _sha256(raw.get("challenge_digest"))

    if not attestation_id:
        blockers.append("SIGNATURE_ATTESTATION_ID_REQUIRED")
    if not key_fingerprint:
        blockers.append("OWNER_KEY_FINGERPRINT_REQUIRED")
    if not signed_digest:
        blockers.append("SIGNED_CHALLENGE_DIGEST_REQUIRED")
    if not challenge_digest:
        blockers.append("CHALLENGE_DIGEST_REQUIRED")
    if signed_digest and challenge_digest and signed_digest != challenge_digest:
        blockers.append("SIGNED_CHALLENGE_DIGEST_MISMATCH")
    if verified_owner_signature is not True:
        blockers.append("OWNER_SIGNATURE_NOT_VERIFIED")
    if verified_active_trust_root is not True:
        blockers.append("ACTIVE_TRUST_ROOT_NOT_VERIFIED")
    if signer_owner_subject_match is not True:
        blockers.append("SIGNER_OWNER_SUBJECT_MISMATCH")
    if signer_owner_binding_match is not True:
        blockers.append("SIGNER_OWNER_BINDING_MISMATCH")
    if persistent_nonce_replay_guard_verified is not True:
        blockers.append("PERSISTENT_NONCE_REPLAY_GUARD_REQUIRED")
    if challenge_nonce_single_use_claimed is not True:
        blockers.append("CHALLENGE_NONCE_SINGLE_USE_CLAIM_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "signature_attestation_id": attestation_id,
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "challenge_digest": challenge_digest,
        "owner_subject": _clean(raw.get("owner_subject"), 240),
        "owner_binding_digest": _sha256(raw.get("owner_binding_digest")),
        "owner_key_fingerprint": key_fingerprint,
        "signed_challenge_digest": signed_digest,
        "challenge_nonce_digest": _sha256(raw.get("nonce_digest")),
        "verified_owner_signature": verified_owner_signature is True,
        "verified_active_trust_root": verified_active_trust_root is True,
        "signer_owner_subject_match": signer_owner_subject_match is True,
        "signer_owner_binding_match": signer_owner_binding_match is True,
        "persistent_nonce_replay_guard_verified": (
            persistent_nonce_replay_guard_verified is True
        ),
        "challenge_nonce_single_use_claimed": (
            challenge_nonce_single_use_claimed is True
        ),
        "signature_verified_at": now.isoformat() if now else "",
    }

    return {
        "schema": SIGNATURE_SCHEMA,
        "state": "OWNER_SIGNATURE_ATTESTED" if not blockers else "BLOCKED",
        "blockers": blockers,
        **material,
        "signature_attestation_digest": _digest(material) if not blockers else "",
        "signature_is_decision": False,
        "approval_implied_by_signature": False,
        "mutation_decision": "UNDECIDED",
        "repository_mutation_authorized": False,
        "authorization_receipt_created": False,
        "authorization_consumed": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "executes_action": False,
    }


def build_explicit_owner_mutation_decision(
    challenge: Mapping[str, Any] | None,
    signature_attestation: Mapping[str, Any] | None,
    *,
    decision_id: Any,
    decision: Any,
    signed_decision_digest: Any,
    decision_nonce_digest: Any,
    owner_key_fingerprint: Any,
    verified_owner_decision_signature: bool,
    verified_active_trust_root: bool,
    persistent_decision_nonce_replay_guard_verified: bool,
    decision_nonce_single_use_claimed: bool,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Represent a separate explicit authorize/deny owner decision."""
    challenge_row = dict(challenge or {})
    signature = dict(signature_attestation or {})
    blockers: list[str] = []

    try:
        current = _aware(now, "now")
        challenge_check = verify_owner_authorization_challenge(
            challenge_row,
            now=current.isoformat(),
        )
    except ValueError:
        current = None
        challenge_check = {"valid": False}
        blockers.append("DECISION_NOW_INVALID")

    if challenge_check.get("valid") is not True:
        blockers.append("VALID_FRESH_CHALLENGE_REQUIRED")
    if signature.get("schema") != SIGNATURE_SCHEMA:
        blockers.append("SIGNATURE_ATTESTATION_SCHEMA_MISMATCH")
    if signature.get("state") != "OWNER_SIGNATURE_ATTESTED":
        blockers.append("OWNER_SIGNATURE_ATTESTATION_REQUIRED")
    if signature.get("signature_is_decision") is not False:
        blockers.append("SIGNATURE_DECISION_SEPARATION_REQUIRED")
    if _sha256(signature.get("challenge_digest")) != _sha256(
        challenge_row.get("challenge_digest")
    ):
        blockers.append("SIGNATURE_CHALLENGE_BINDING_MISMATCH")

    did = _identity(decision_id, 180)
    decision_name = _clean(decision, 100).upper()
    signed_digest = _sha256(signed_decision_digest)
    nonce = _sha256(decision_nonce_digest)
    key_fingerprint = _sha256(owner_key_fingerprint)

    if not did:
        blockers.append("DECISION_ID_REQUIRED")
    if decision_name not in DECISIONS:
        blockers.append("MUTATION_DECISION_INVALID")
    if not signed_digest:
        blockers.append("SIGNED_DECISION_DIGEST_REQUIRED")
    if not nonce:
        blockers.append("DECISION_NONCE_DIGEST_REQUIRED")
    if not key_fingerprint:
        blockers.append("OWNER_KEY_FINGERPRINT_REQUIRED")
    if key_fingerprint and key_fingerprint != _sha256(
        signature.get("owner_key_fingerprint")
    ):
        blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")
    if verified_owner_decision_signature is not True:
        blockers.append("OWNER_DECISION_SIGNATURE_NOT_VERIFIED")
    if verified_active_trust_root is not True:
        blockers.append("ACTIVE_TRUST_ROOT_NOT_VERIFIED")
    if persistent_decision_nonce_replay_guard_verified is not True:
        blockers.append("PERSISTENT_DECISION_NONCE_REPLAY_GUARD_REQUIRED")
    if decision_nonce_single_use_claimed is not True:
        blockers.append("DECISION_NONCE_SINGLE_USE_CLAIM_REQUIRED")

    try:
        issued = _aware(issued_at, "issued_at")
        expires = _aware(expires_at, "expires_at")
        if expires <= issued:
            blockers.append("DECISION_EXPIRY_INVALID")
        if (expires - issued).total_seconds() > MAX_DECISION_WINDOW_SECONDS:
            blockers.append("DECISION_WINDOW_TOO_LONG")
        if current is not None and current < issued:
            blockers.append("DECISION_FROM_FUTURE")
        if current is not None and current > expires:
            blockers.append("DECISION_EXPIRED")
        challenge_expires = _aware(
            challenge_row.get("expires_at"),
            "challenge_expires_at",
        )
        if expires > challenge_expires:
            blockers.append("DECISION_CANNOT_OUTLIVE_CHALLENGE")
    except ValueError:
        issued = None
        expires = None
        blockers.append("DECISION_TIME_INVALID")

    expected_decision_material = {
        "decision_id": did,
        "purpose": PURPOSE,
        "decision": decision_name,
        "challenge_digest": _sha256(challenge_row.get("challenge_digest")),
        "signature_attestation_digest": _sha256(
            signature.get("signature_attestation_digest")
        ),
        "pr_number": challenge_row.get("pr_number"),
        "requested_mutation": challenge_row.get("requested_mutation"),
        "owner_subject": challenge_row.get("owner_subject"),
        "owner_binding_digest": _sha256(
            challenge_row.get("owner_binding_digest")
        ),
        "owner_key_fingerprint": key_fingerprint,
        "decision_nonce_digest": nonce,
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
    }
    expected_signed_digest = _digest(expected_decision_material)
    if signed_digest and signed_digest != expected_signed_digest:
        blockers.append("SIGNED_DECISION_DIGEST_MISMATCH")

    blockers = list(dict.fromkeys(blockers))
    authorized = (
        not blockers and decision_name == "AUTHORIZE_REPOSITORY_MUTATION"
    )
    denied = (
        not blockers and decision_name == "DENY_REPOSITORY_MUTATION"
    )

    material = {
        **expected_decision_material,
        "verified_owner_decision_signature": (
            verified_owner_decision_signature is True
        ),
        "verified_active_trust_root": verified_active_trust_root is True,
        "persistent_decision_nonce_replay_guard_verified": (
            persistent_decision_nonce_replay_guard_verified is True
        ),
        "decision_nonce_single_use_claimed": (
            decision_nonce_single_use_claimed is True
        ),
        "verified_at": current.isoformat() if current else "",
    }

    return {
        "schema": DECISION_SCHEMA,
        "state": (
            "OWNER_MUTATION_DECISION_AUTHORIZED"
            if authorized
            else "OWNER_MUTATION_DECISION_DENIED"
            if denied
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "decision_digest": _digest(material) if not blockers else "",
        "explicit_owner_decision_verified": not blockers,
        "repository_mutation_authorization_intent": authorized,
        "repository_mutation_denied": denied,
        "decision_is_execution": False,
        "authorization_receipt_created": False,
        "authorization_consumed": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "executes_action": False,
    }


def build_repository_mutation_authorization_receipt(
    challenge: Mapping[str, Any] | None,
    signature_attestation: Mapping[str, Any] | None,
    decision_record: Mapping[str, Any] | None,
    live_rebuilt_preflight: Mapping[str, Any] | None,
    *,
    receipt_id: Any,
    authorization_nonce_digest: Any,
    persistent_authorization_nonce_replay_guard_verified: bool,
    authorization_nonce_single_use_claimed: bool,
    issued_at: Any,
    expires_at: Any,
    now: Any,
) -> dict[str, Any]:
    """Build a single-use authorization artifact for exactly one mutation.

    This receipt authorizes a future mutation only if a future executor later
    re-verifies and atomically consumes it. This function performs no mutation.
    """
    challenge_row = dict(challenge or {})
    signature = dict(signature_attestation or {})
    decision = dict(decision_record or {})
    rebuilt = dict(live_rebuilt_preflight or {})
    blockers: list[str] = []

    try:
        current = _aware(now, "now")
        challenge_check = verify_owner_authorization_challenge(
            challenge_row,
            now=current.isoformat(),
        )
    except ValueError:
        current = None
        challenge_check = {"valid": False}
        blockers.append("RECEIPT_NOW_INVALID")

    if challenge_check.get("valid") is not True:
        blockers.append("VALID_FRESH_CHALLENGE_REQUIRED")
    if signature.get("schema") != SIGNATURE_SCHEMA:
        blockers.append("SIGNATURE_ATTESTATION_SCHEMA_MISMATCH")
    if signature.get("state") != "OWNER_SIGNATURE_ATTESTED":
        blockers.append("OWNER_SIGNATURE_ATTESTATION_REQUIRED")
    if decision.get("schema") != DECISION_SCHEMA:
        blockers.append("OWNER_DECISION_SCHEMA_MISMATCH")
    if decision.get("state") != "OWNER_MUTATION_DECISION_AUTHORIZED":
        blockers.append("EXPLICIT_OWNER_AUTHORIZE_DECISION_REQUIRED")
    if decision.get("repository_mutation_authorization_intent") is not True:
        blockers.append("OWNER_AUTHORIZATION_INTENT_FLAG_REQUIRED")

    if rebuilt.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("LIVE_REBUILD_PREFLIGHT_SCHEMA_MISMATCH")
    if rebuilt.get("state") != "LIVE_STEP_PREFLIGHT_READY":
        blockers.append("LIVE_REBUILD_PREFLIGHT_REQUIRED")

    challenge_digest = _sha256(challenge_row.get("challenge_digest"))
    signature_challenge_digest = _sha256(signature.get("challenge_digest"))
    decision_challenge_digest = _sha256(decision.get("challenge_digest"))
    if not challenge_digest:
        blockers.append("CHALLENGE_DIGEST_REQUIRED")
    if signature_challenge_digest != challenge_digest:
        blockers.append("SIGNATURE_CHALLENGE_BINDING_MISMATCH")
    if decision_challenge_digest != challenge_digest:
        blockers.append("DECISION_CHALLENGE_BINDING_MISMATCH")

    if _sha256(rebuilt.get("preflight_digest")) != _sha256(
        challenge_row.get("preflight_digest")
    ):
        blockers.append("LIVE_REBUILD_PREFLIGHT_DIGEST_MISMATCH")

    binding_pairs = (
        ("pr_number", "pr_number"),
        ("requested_mutation", "requested_mutation"),
        ("main_sha", "observed_main_sha"),
        ("main_tree_sha", "observed_main_tree_sha"),
        ("head_branch", "observed_head"),
        ("head_sha", "observed_head_sha"),
        ("base_branch", "observed_base"),
        ("file_delta_digest", "observed_files_digest"),
        ("workflow_snapshot_digest", "observed_workflows_digest"),
        ("readiness_digest", "current_readiness_digest"),
        ("rollback_plan_digest", "rollback_plan_digest"),
    )
    for challenge_key, rebuild_key in binding_pairs:
        if challenge_row.get(challenge_key) != rebuilt.get(rebuild_key):
            blockers.append("LIVE_REBUILD_BINDING_MISMATCH:" + challenge_key)

    if challenge_row.get("requested_mutation") not in MUTATIONS:
        blockers.append("CHALLENGE_MUTATION_INVALID")

    rid = _identity(receipt_id, 180)
    auth_nonce = _sha256(authorization_nonce_digest)
    if not rid:
        blockers.append("RECEIPT_ID_REQUIRED")
    if not auth_nonce:
        blockers.append("AUTHORIZATION_NONCE_DIGEST_REQUIRED")
    if persistent_authorization_nonce_replay_guard_verified is not True:
        blockers.append("PERSISTENT_AUTHORIZATION_NONCE_REPLAY_GUARD_REQUIRED")
    if authorization_nonce_single_use_claimed is not True:
        blockers.append("AUTHORIZATION_NONCE_SINGLE_USE_CLAIM_REQUIRED")

    try:
        issued = _aware(issued_at, "issued_at")
        expires = _aware(expires_at, "expires_at")
        if expires <= issued:
            blockers.append("AUTHORIZATION_RECEIPT_EXPIRY_INVALID")
        if (expires - issued).total_seconds() > MAX_DECISION_WINDOW_SECONDS:
            blockers.append("AUTHORIZATION_RECEIPT_WINDOW_TOO_LONG")
        if current is not None and current < issued:
            blockers.append("AUTHORIZATION_RECEIPT_FROM_FUTURE")
        if current is not None and current > expires:
            blockers.append("AUTHORIZATION_RECEIPT_EXPIRED")

        challenge_expires = _aware(
            challenge_row.get("expires_at"),
            "challenge_expires_at",
        )
        decision_expires = _aware(
            decision.get("expires_at"),
            "decision_expires_at",
        )
        if expires > challenge_expires:
            blockers.append("RECEIPT_CANNOT_OUTLIVE_CHALLENGE")
        if expires > decision_expires:
            blockers.append("RECEIPT_CANNOT_OUTLIVE_DECISION")
    except ValueError:
        issued = None
        expires = None
        blockers.append("AUTHORIZATION_RECEIPT_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "receipt_id": rid,
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "pr_number": challenge_row.get("pr_number"),
        "requested_mutation": challenge_row.get("requested_mutation"),
        "owner_subject": challenge_row.get("owner_subject"),
        "owner_binding_digest": _sha256(
            challenge_row.get("owner_binding_digest")
        ),
        "owner_key_fingerprint": _sha256(
            signature.get("owner_key_fingerprint")
        ),
        "challenge_digest": challenge_digest,
        "signature_attestation_digest": _sha256(
            signature.get("signature_attestation_digest")
        ),
        "decision_digest": _sha256(decision.get("decision_digest")),
        "live_rebuilt_preflight_digest": _sha256(
            rebuilt.get("preflight_digest")
        ),
        "main_sha": _sha(challenge_row.get("main_sha")),
        "main_tree_sha": _sha(challenge_row.get("main_tree_sha")),
        "head_branch": challenge_row.get("head_branch"),
        "head_sha": _sha(challenge_row.get("head_sha")),
        "base_branch": challenge_row.get("base_branch"),
        "file_delta_digest": _sha256(
            challenge_row.get("file_delta_digest")
        ),
        "workflow_snapshot_digest": _sha256(
            challenge_row.get("workflow_snapshot_digest")
        ),
        "readiness_digest": _sha256(
            challenge_row.get("readiness_digest")
        ),
        "rollback_plan_digest": _sha256(
            challenge_row.get("rollback_plan_digest")
        ),
        "authorization_nonce_digest": auth_nonce,
        "persistent_authorization_nonce_replay_guard_verified": (
            persistent_authorization_nonce_replay_guard_verified is True
        ),
        "authorization_nonce_single_use_claimed": (
            authorization_nonce_single_use_claimed is True
        ),
        "issued_at": issued.isoformat() if issued else "",
        "expires_at": expires.isoformat() if expires else "",
        "verified_at": current.isoformat() if current else "",
    }

    authorized = not blockers
    return {
        "schema": RECEIPT_SCHEMA,
        "state": (
            "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED"
            if authorized
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "authorization_receipt_digest": _digest(material) if authorized else "",
        "repository_mutation_authorized": authorized,
        "authorized_for_exactly_one_mutation": authorized,
        "authorization_single_use": authorized,
        "authorization_persisted": False,
        "persistence_attested": False,
        "authorization_consumed": False,
        "authorization_reuse_allowed": False,
        "authorization_scope_expansion_allowed": False,
        "authorization_pr_change_allowed": False,
        "authorization_mutation_change_allowed": False,
        "authorization_head_change_allowed": False,
        "authorization_main_change_allowed": False,
        "authorization_base_change_allowed": False,
        "execution_time_state_rebuild_required": True,
        "execution_time_exact_receipt_match_required": True,
        "atomic_authorization_consumption_required": True,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "branch_deleted": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
        "executes_action": False,
    }


def build_authorization_receipt_persistence_attestation(
    receipt: Mapping[str, Any] | None,
    *,
    persisted_record_digest: Any,
    writer_attestation_digest: Any,
    persisted_at: Any,
    read_after_write_verified: bool,
    atomic_write_or_cas_verified: bool,
    writer_identity_verified: bool,
    now: Any,
) -> dict[str, Any]:
    """Represent external durable storage proof for a verified receipt."""
    raw = dict(receipt or {})
    blockers: list[str] = []

    if raw.get("schema") != RECEIPT_SCHEMA:
        blockers.append("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
    if raw.get("state") != "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED":
        blockers.append("VERIFIED_AUTHORIZATION_RECEIPT_REQUIRED")
    if raw.get("repository_mutation_authorized") is not True:
        blockers.append("REPOSITORY_MUTATION_AUTHORIZATION_FLAG_REQUIRED")
    if raw.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")

    receipt_digest = _sha256(raw.get("authorization_receipt_digest"))
    record_digest = _sha256(persisted_record_digest)
    writer_digest = _sha256(writer_attestation_digest)

    if not receipt_digest:
        blockers.append("AUTHORIZATION_RECEIPT_DIGEST_REQUIRED")
    if not record_digest:
        blockers.append("PERSISTED_RECORD_DIGEST_REQUIRED")
    if not writer_digest:
        blockers.append("WRITER_ATTESTATION_DIGEST_REQUIRED")
    if read_after_write_verified is not True:
        blockers.append("READ_AFTER_WRITE_VERIFICATION_REQUIRED")
    if atomic_write_or_cas_verified is not True:
        blockers.append("ATOMIC_WRITE_OR_CAS_REQUIRED")
    if writer_identity_verified is not True:
        blockers.append("WRITER_IDENTITY_VERIFICATION_REQUIRED")

    try:
        persisted = _aware(persisted_at, "persisted_at")
        current = _aware(now, "now")
        issued = _aware(raw.get("issued_at"), "receipt_issued_at")
        expires = _aware(raw.get("expires_at"), "receipt_expires_at")
        if persisted < issued:
            blockers.append("RECEIPT_PERSISTED_BEFORE_ISSUE")
        if persisted > expires:
            blockers.append("RECEIPT_PERSISTED_AFTER_EXPIRY")
        if current < persisted:
            blockers.append("PERSISTENCE_ATTESTATION_FROM_FUTURE")
        if current > expires:
            blockers.append("AUTHORIZATION_EXPIRED_AFTER_PERSISTENCE")
    except ValueError:
        persisted = None
        current = None
        blockers.append("AUTHORIZATION_PERSISTENCE_TIME_INVALID")

    blockers = list(dict.fromkeys(blockers))
    material = {
        "authorization_receipt_digest": receipt_digest,
        "persisted_record_digest": record_digest,
        "writer_attestation_digest": writer_digest,
        "persisted_at": persisted.isoformat() if persisted else "",
        "read_after_write_verified": read_after_write_verified is True,
        "atomic_write_or_cas_verified": atomic_write_or_cas_verified is True,
        "writer_identity_verified": writer_identity_verified is True,
    }

    return {
        "schema": PERSISTENCE_SCHEMA,
        "state": (
            "AUTHORIZATION_RECEIPT_PERSISTENCE_ATTESTED"
            if not blockers
            else "BLOCKED"
        ),
        "blockers": blockers,
        **material,
        "persistence_attestation_digest": _digest(material) if not blockers else "",
        "authorization_persisted_by_this_module": False,
        "authorization_consumed": False,
        "repository_mutation_authorized_by_this_attestation": False,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "executes_action": False,
    }


def verify_repository_mutation_authorization_receipt(
    receipt: Mapping[str, Any] | None,
    *,
    now: Any,
) -> dict[str, Any]:
    """Verify deterministic receipt integrity/freshness. Does not consume it."""
    raw = dict(receipt or {})
    blockers: list[str] = []

    if raw.get("schema") != RECEIPT_SCHEMA:
        blockers.append("AUTHORIZATION_RECEIPT_SCHEMA_MISMATCH")
    if raw.get("state") != "REPOSITORY_MUTATION_AUTHORIZATION_VERIFIED":
        blockers.append("VERIFIED_AUTHORIZATION_RECEIPT_REQUIRED")
    if raw.get("repository_mutation_authorized") is not True:
        blockers.append("REPOSITORY_MUTATION_AUTHORIZATION_FLAG_REQUIRED")
    if raw.get("authorized_for_exactly_one_mutation") is not True:
        blockers.append("SINGLE_MUTATION_SCOPE_REQUIRED")
    if raw.get("authorization_single_use") is not True:
        blockers.append("SINGLE_USE_AUTHORIZATION_REQUIRED")
    if raw.get("authorization_consumed") is not False:
        blockers.append("AUTHORIZATION_ALREADY_CONSUMED")

    material = {
        key: raw.get(key)
        for key in (
            "receipt_id",
            "purpose",
            "mechanism",
            "pr_number",
            "requested_mutation",
            "owner_subject",
            "owner_binding_digest",
            "owner_key_fingerprint",
            "challenge_digest",
            "signature_attestation_digest",
            "decision_digest",
            "live_rebuilt_preflight_digest",
            "main_sha",
            "main_tree_sha",
            "head_branch",
            "head_sha",
            "base_branch",
            "file_delta_digest",
            "workflow_snapshot_digest",
            "readiness_digest",
            "rollback_plan_digest",
            "authorization_nonce_digest",
            "persistent_authorization_nonce_replay_guard_verified",
            "authorization_nonce_single_use_claimed",
            "issued_at",
            "expires_at",
            "verified_at",
        )
    }
    supplied = _sha256(raw.get("authorization_receipt_digest"))
    expected = _digest(material)
    if not supplied or supplied != expected:
        blockers.append("AUTHORIZATION_RECEIPT_DIGEST_MISMATCH")

    try:
        current = _aware(now, "now")
        issued = _aware(raw.get("issued_at"), "issued_at")
        expires = _aware(raw.get("expires_at"), "expires_at")
        if current < issued:
            blockers.append("AUTHORIZATION_RECEIPT_FROM_FUTURE")
        if current > expires:
            blockers.append("AUTHORIZATION_RECEIPT_EXPIRED")
    except ValueError:
        blockers.append("AUTHORIZATION_RECEIPT_TIME_INVALID")

    if raw.get("repository_mutation_performed") is not False:
        blockers.append("REPOSITORY_MUTATION_MUST_REMAIN_UNPERFORMED")
    if raw.get("merge_executed") is not False:
        blockers.append("MERGE_MUST_REMAIN_UNEXECUTED")
    if raw.get("retarget_executed") is not False:
        blockers.append("RETARGET_MUST_REMAIN_UNEXECUTED")
    if raw.get("draft_transition_executed") is not False:
        blockers.append("DRAFT_TRANSITION_MUST_REMAIN_UNEXECUTED")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": VERIFY_SCHEMA,
        "state": "VALID_AUTHORIZATION_RECEIPT" if not blockers else "INVALID",
        "valid": not blockers,
        "blockers": blockers,
        "authorization_receipt_digest": supplied,
        "repository_mutation_authorized": not blockers,
        "authorization_consumed": False,
        "repository_mutation_performed": False,
        "executes_action": False,
    }


def repository_mutation_authorization_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "purpose": PURPOSE,
        "mechanism": MECHANISM,
        "supported_mutations": list(MUTATIONS),
        "signature_and_decision_are_separate": True,
        "signature_implies_authorization": False,
        "generic_chat_is_signature": False,
        "generic_chat_is_decision": False,
        "generic_chat_is_authorization": False,
        "external_owner_signature_required": True,
        "active_trust_root_required": True,
        "challenge_nonce_replay_guard_required": True,
        "separate_decision_signature_required": True,
        "separate_decision_nonce_required": True,
        "decision_nonce_replay_guard_required": True,
        "live_state_rebuild_required_before_receipt": True,
        "exact_preflight_digest_match_required": True,
        "exact_main_sha_match_required": True,
        "exact_main_tree_sha_match_required": True,
        "exact_head_sha_match_required": True,
        "exact_base_match_required": True,
        "exact_file_delta_digest_match_required": True,
        "exact_workflow_snapshot_digest_match_required": True,
        "exact_readiness_digest_match_required": True,
        "exact_rollback_plan_digest_match_required": True,
        "authorization_receipt_single_use": True,
        "authorization_reuse_allowed": False,
        "authorization_scope_expansion_allowed": False,
        "authorization_pr_change_allowed": False,
        "authorization_mutation_change_allowed": False,
        "authorization_head_change_allowed": False,
        "authorization_main_change_allowed": False,
        "authorization_base_change_allowed": False,
        "durable_receipt_persistence_required_before_executor": True,
        "read_after_write_required": True,
        "atomic_write_or_cas_required": True,
        "execution_time_state_rebuild_required": True,
        "atomic_authorization_consumption_required": True,
        "receipt_authorization_is_not_execution": True,
        "repository_mutation_performed": False,
        "merge_executed": False,
        "retarget_executed": False,
        "draft_transition_executed": False,
        "branch_deleted": False,
        "deploy_executed": False,
        "worker_activation_allowed": False,
        "provider_activation_allowed": False,
        "production_persistence_activation_allowed": False,
        "external_action_executed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "SIGNATURE_SCHEMA",
    "DECISION_SCHEMA",
    "RECEIPT_SCHEMA",
    "PERSISTENCE_SCHEMA",
    "VERIFY_SCHEMA",
    "POLICY_SCHEMA",
    "PURPOSE",
    "MECHANISM",
    "DECISIONS",
    "MAX_DECISION_WINDOW_SECONDS",
    "build_owner_signature_attestation",
    "build_explicit_owner_mutation_decision",
    "build_repository_mutation_authorization_receipt",
    "build_authorization_receipt_persistence_attestation",
    "verify_repository_mutation_authorization_receipt",
    "repository_mutation_authorization_policy",
]
