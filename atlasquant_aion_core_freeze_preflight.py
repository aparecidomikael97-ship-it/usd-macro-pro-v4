"""AION V2.22 Core Freeze Ceremony Preflight.

This layer prepares a bounded, deterministic HUMAN_OWNER decision challenge.
It binds the future Core Freeze decision to:
- the exact V2.20 certification manifest;
- the exact V2.21 review digest;
- the exact Checkpoint Mestre digest, state digest and revision;
- a short-lived ceremony id + nonce window.

It never records an owner decision, never performs biometric/FIDO2 capture,
never freezes the Core, never saves the Checkpoint Mestre, never merges/deploys,
and never performs external execution.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_checkpoint_master import (
    checkpoint_master_digest,
    reconstruct_checkpoint,
)
from atlasquant_aion_core_completion_review import build_core_completion_review
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_CORE_FREEZE_PREFLIGHT_V1"
CHALLENGE_SCHEMA = "ATLASQUANT_AION_CORE_FREEZE_CHALLENGE_V1"
VERSION = 1
MAX_CEREMONY_SECONDS = 900
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_SAFE_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,256}$")
_DECISION_OPTIONS = ("APPROVE_CORE_FREEZE", "REJECT_CORE_FREEZE")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _validate_window(*, now_ts: str, issued_at: str, expires_at: str) -> list[str]:
    blockers: list[str] = []
    try:
        now = _parse_ts(now_ts)
        issued = _parse_ts(issued_at)
        expires = _parse_ts(expires_at)
    except ValueError:
        return ["CEREMONY_TIME_INVALID"]

    if issued > now:
        blockers.append("CEREMONY_NOT_YET_VALID")
    if expires <= now or expires <= issued:
        blockers.append("CEREMONY_EXPIRED_OR_INVALID_WINDOW")
    if expires > issued:
        lifetime = int((expires - issued).total_seconds())
        if lifetime > MAX_CEREMONY_SECONDS:
            blockers.append("CEREMONY_WINDOW_TOO_LONG")
    return blockers


def _checkpoint_review_blockers(
    snapshot: Mapping[str, Any],
    *,
    expected_review: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    record = snapshot.get("aion_core_completion_review")
    if not isinstance(record, Mapping):
        return ["CHECKPOINT_REVIEW_RECORD_MISSING"]

    expected_pairs = {
        "schema": expected_review.get("schema"),
        "state": "READY_FOR_OWNER_REVIEW",
        "target_commit_sha": expected_review.get("target_commit_sha"),
        "certification_manifest_digest": expected_review.get(
            "certification_manifest_digest"
        ),
        "certification_trust_root_binding_digest": expected_review.get(
            "certification_trust_root_binding_digest"
        ),
        "review_digest": expected_review.get("review_digest"),
        "owner_review_ready": True,
        "owner_decision_recorded": False,
        "core_complete": False,
        "core_frozen": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }
    for field, expected in expected_pairs.items():
        if record.get(field) != expected:
            blockers.append(f"CHECKPOINT_REVIEW_MISMATCH:{field}")
    return blockers


def build_core_freeze_preflight(
    certification_manifest: Mapping[str, Any] | None,
    *,
    certification_trust_roots: TrustRootRegistry,
    now_ts: str,
    expected_target_commit_sha: str,
    checkpoint_master: Mapping[str, Any] | None,
    ceremony_id: str,
    challenge_nonce: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Build a short-lived HUMAN_OWNER decision challenge without deciding."""
    blockers: list[str] = []

    target = _clean(expected_target_commit_sha, 64).lower()
    if not _SHA_RE.fullmatch(target):
        raise ValueError("expected_target_commit_sha must be a 40-char git SHA")
    if not isinstance(ceremony_id, str) or not _SAFE_ID_RE.fullmatch(ceremony_id):
        raise ValueError("ceremony_id must be canonical and 8-160 chars")
    if not isinstance(challenge_nonce, str) or not _SAFE_NONCE_RE.fullmatch(
        challenge_nonce
    ):
        raise ValueError("challenge_nonce must be canonical and 16-256 chars")

    blockers.extend(
        _validate_window(
            now_ts=now_ts,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )

    review = build_core_completion_review(
        certification_manifest,
        certification_trust_roots=certification_trust_roots,
        now_ts=now_ts,
        expected_target_commit_sha=target,
    )
    if review.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("CORE_COMPLETION_REVIEW_NOT_READY")
    if review.get("owner_review_ready") is not True:
        blockers.append("OWNER_REVIEW_NOT_READY")

    checkpoint_digest = ""
    checkpoint_state_digest = ""
    checkpoint_revision = -1
    checkpoint_snapshot: Mapping[str, Any] = {}
    if not isinstance(checkpoint_master, Mapping):
        blockers.append("CHECKPOINT_MASTER_REQUIRED")
    else:
        try:
            reconstructed = reconstruct_checkpoint(checkpoint_master)
            checkpoint_digest = checkpoint_master_digest(checkpoint_master)
            checkpoint_state_digest = reconstructed["state_digest"]
            checkpoint_revision = reconstructed["revision"]
            checkpoint_snapshot = reconstructed["snapshot"]
        except Exception:
            blockers.append("CHECKPOINT_MASTER_INTEGRITY_INVALID")

    if checkpoint_snapshot:
        blockers.extend(
            _checkpoint_review_blockers(
                checkpoint_snapshot,
                expected_review=review,
            )
        )

    unique = sorted(set(blockers))
    ready = not unique

    challenge_body = {
        "schema": CHALLENGE_SCHEMA,
        "version": VERSION,
        "ceremony_id": ceremony_id,
        "decision_scope": "AION_CORE_FREEZE_ONLY",
        "decision_options": list(_DECISION_OPTIONS),
        "target_commit_sha": target,
        "v220_certification_manifest_digest": review.get(
            "certification_manifest_digest", ""
        ),
        "v220_certification_trust_root_binding_digest": review.get(
            "certification_trust_root_binding_digest", ""
        ),
        "v221_review_digest": review.get("review_digest", ""),
        "checkpoint_master_digest": checkpoint_digest,
        "checkpoint_state_digest": checkpoint_state_digest,
        "checkpoint_revision": checkpoint_revision,
        "challenge_nonce": challenge_nonce,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "human_owner_required": True,
        "owner_decision_recorded": False,
        "signature_mechanism": "FIDO2_OR_PLATFORM_SIGNATURE_FUTURE",
        "signature_active": False,
        "biometric_capture_performed": False,
        "signature_performed": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "executes_action": False,
        "blockers": unique,
        "state": "READY_FOR_OWNER_DECISION" if ready else "BLOCKED",
    }
    challenge_digest = _digest(challenge_body)

    return {
        **challenge_body,
        "challenge_digest": challenge_digest,
        "digest_to_sign": challenge_digest if ready else "",
        "owner_decision_ready": ready,
        "owner_decision": "UNDECIDED",
        "requires_explicit_human_owner_action": True,
        "requires_checkpoint_state_match_at_decision_time": True,
        "requires_fresh_challenge_at_decision_time": True,
        "approval_is_not_execution_authority": True,
        "automatic_freeze": False,
        "automatic_checkpoint_write": False,
    }


def verify_preflight_still_current(
    preflight: Mapping[str, Any] | None,
    *,
    checkpoint_master: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Read-only TOCTOU guard for a previously prepared challenge."""
    blockers: list[str] = []
    row = dict(preflight or {}) if isinstance(preflight, Mapping) else {}
    if row.get("schema") != CHALLENGE_SCHEMA:
        blockers.append("PREFLIGHT_SCHEMA_INVALID")
    if row.get("state") != "READY_FOR_OWNER_DECISION":
        blockers.append("PREFLIGHT_NOT_READY")
    if row.get("owner_decision_ready") is not True:
        blockers.append("PREFLIGHT_OWNER_DECISION_NOT_READY")
    if row.get("challenge_digest") != _digest({
        key: value
        for key, value in row.items()
        if key not in {
            "challenge_digest",
            "digest_to_sign",
            "owner_decision_ready",
            "owner_decision",
            "requires_explicit_human_owner_action",
            "requires_checkpoint_state_match_at_decision_time",
            "requires_fresh_challenge_at_decision_time",
            "approval_is_not_execution_authority",
            "automatic_freeze",
            "automatic_checkpoint_write",
        }
    }):
        blockers.append("PREFLIGHT_CHALLENGE_DIGEST_MISMATCH")

    blockers.extend(
        _validate_window(
            now_ts=now_ts,
            issued_at=row.get("issued_at"),
            expires_at=row.get("expires_at"),
        )
    )

    if not isinstance(checkpoint_master, Mapping):
        blockers.append("CHECKPOINT_MASTER_REQUIRED")
    else:
        try:
            reconstructed = reconstruct_checkpoint(checkpoint_master)
            current_master_digest = checkpoint_master_digest(checkpoint_master)
        except Exception:
            blockers.append("CHECKPOINT_MASTER_INTEGRITY_INVALID")
        else:
            if current_master_digest != row.get("checkpoint_master_digest"):
                blockers.append("CHECKPOINT_MASTER_CHANGED")
            if reconstructed["state_digest"] != row.get("checkpoint_state_digest"):
                blockers.append("CHECKPOINT_STATE_CHANGED")
            if reconstructed["revision"] != row.get("checkpoint_revision"):
                blockers.append("CHECKPOINT_REVISION_CHANGED")

    for field in (
        "owner_decision_recorded",
        "signature_active",
        "biometric_capture_performed",
        "signature_performed",
        "core_freeze_authorized",
        "core_frozen",
        "checkpoint_saved",
        "merge_authorized",
        "deploy_authorized",
        "execution_allowed",
        "worker_armed",
        "external_action_executed",
        "executes_action",
    ):
        if row.get(field) is not False:
            blockers.append(f"UNSAFE_PREFLIGHT_FIELD:{field}")

    unique = sorted(set(blockers))
    current = not unique
    return {
        "schema": "ATLASQUANT_AION_CORE_FREEZE_PREFLIGHT_RECHECK_V1",
        "state": "CURRENT" if current else "BLOCKED",
        "blockers": unique,
        "preflight_current": current,
        "owner_decision_recorded": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "execution_allowed": False,
        "external_action_executed": False,
    }


__all__ = [
    "SCHEMA",
    "CHALLENGE_SCHEMA",
    "VERSION",
    "MAX_CEREMONY_SECONDS",
    "build_core_freeze_preflight",
    "verify_preflight_still_current",
]
