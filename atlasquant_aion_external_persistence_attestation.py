"""AION V2.23 external Checkpoint persistence attestation bridge.

This module bridges the logical V2.3 Checkpoint Master contract to the existing
runtime Checkpoint persistence contract without performing I/O.

It can:
1. stage an in-memory runtime candidate carrying a digest-bound logical master
   binding; and
2. verify, from externally supplied runtime observation + write receipt, that the
   exact binding is currently persisted and write-attributed.

It never performs a runtime save, never performs network I/O, never records an
owner decision, never freezes the Core, and never arms the worker.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from atlasquant_aion_checkpoint_master import (
    checkpoint_master_digest,
    reconstruct_checkpoint,
)
from atlasquant_aion_core_freeze_preflight import (
    CHALLENGE_SCHEMA,
    verify_preflight_still_current,
)
from atlasquant_aion_memory import (
    DEFAULT_RUNTIME_REPO,
    RUNTIME_PATH,
    SCHEMA as MEMORY_SCHEMA,
    WRITE_RECEIPT_SCHEMA,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
    reconcile_runtime_write,
)
from atlasquant_aion_trust_root import TrustRootRegistry
from atlasquant_runtime_store import require_runtime_branch

SCHEMA = "ATLASQUANT_AION_EXTERNAL_PERSISTENCE_ATTESTATION_V1"
BINDING_SCHEMA = "ATLASQUANT_AION_CHECKPOINT_RUNTIME_BINDING_V1"
SIGNING_SCHEMA = "ATLASQUANT_AION_OWNER_SIGNATURE_CHALLENGE_V1"
NAMESPACE = "aion_core_checkpoint_master_v1"
MAX_RUNTIME_OBSERVATION_AGE_SECONDS = 300
EXPECTED_RUNTIME_REPO = DEFAULT_RUNTIME_REPO
EXPECTED_RUNTIME_BRANCH = "atlasquant-runtime"
EXPECTED_RUNTIME_PATH = RUNTIME_PATH
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX16_RE = re.compile(r"^[0-9a-f]{16}$")


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


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp required")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _clean_sha(value: Any) -> str:
    sha = str(value or "").strip().lower()
    if not _SHA_RE.fullmatch(sha):
        raise ValueError("expected_target_commit_sha must be a 40-char git SHA")
    return sha


def _review_from_master(checkpoint_master: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rebuilt = reconstruct_checkpoint(checkpoint_master)
    snapshot = rebuilt.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise ValueError("checkpoint snapshot missing")
    review = snapshot.get("aion_core_completion_review")
    if not isinstance(review, Mapping):
        raise ValueError("checkpoint V2.21 review missing")
    return rebuilt, dict(review)


def build_runtime_binding(
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    *,
    expected_target_commit_sha: str,
) -> dict[str, Any]:
    """Build the deterministic logical-master binding stored in runtime."""
    if not isinstance(checkpoint_master, Mapping):
        raise ValueError("checkpoint_master required")
    if not isinstance(preflight, Mapping):
        raise ValueError("preflight required")
    target = _clean_sha(expected_target_commit_sha)
    if preflight.get("schema") != CHALLENGE_SCHEMA:
        raise ValueError("preflight schema mismatch")
    if preflight.get("state") != "READY_FOR_OWNER_DECISION_PREFLIGHT":
        raise ValueError("preflight state mismatch")
    if preflight.get("owner_decision_preflight_ready") is not True:
        raise ValueError("preflight is not logically ready")
    if preflight.get("owner_decision_ready") is not False:
        raise ValueError("owner decision must remain not ready")
    if preflight.get("digest_to_sign") != "":
        raise ValueError("V2.22 digest_to_sign must remain empty")
    if preflight.get("target_commit_sha") != target:
        raise ValueError("preflight target mismatch")

    rebuilt, review = _review_from_master(checkpoint_master)
    master_digest = checkpoint_master_digest(checkpoint_master)
    if review.get("review_digest") != preflight.get("v221_review_digest"):
        raise ValueError("V2.21 review digest mismatch")
    if master_digest != preflight.get("checkpoint_master_digest"):
        raise ValueError("checkpoint master digest mismatch")
    if rebuilt.get("state_digest") != preflight.get("checkpoint_state_digest"):
        raise ValueError("checkpoint state digest mismatch")
    if rebuilt.get("revision") != preflight.get("checkpoint_revision"):
        raise ValueError("checkpoint revision mismatch")

    body = {
        "schema": BINDING_SCHEMA,
        "target_commit_sha": target,
        "checkpoint_master_digest": master_digest,
        "checkpoint_state_digest": rebuilt["state_digest"],
        "checkpoint_revision": rebuilt["revision"],
        "v221_review_digest": review["review_digest"],
        "v222_preflight_challenge_digest": preflight["challenge_digest"],
        "owner_decision": "UNDECIDED",
        "owner_decision_ready": False,
        "signature_material_ready": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "worker_armed": False,
        "external_action_executed": False,
        "persistence_claimed_by_binding": False,
    }
    return {**body, "binding_digest": _digest(body)}


def stage_runtime_persistence_candidate(
    runtime_checkpoint: Mapping[str, Any] | None,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    *,
    expected_target_commit_sha: str,
) -> dict[str, Any]:
    """Stage a runtime candidate in memory only. No save or network call occurs."""
    binding = build_runtime_binding(
        checkpoint_master,
        preflight,
        expected_target_commit_sha=expected_target_commit_sha,
    )
    candidate = ensure_operating_checkpoint(runtime_checkpoint)
    candidate = deepcopy(candidate)
    candidate[NAMESPACE] = binding
    operating = candidate.get("operating")
    if isinstance(operating, dict):
        operating["dirty"] = True

    expected_runtime_digest = checkpoint_source_digest(candidate)
    if not _HEX16_RE.fullmatch(expected_runtime_digest):
        raise ValueError("runtime candidate digest invalid")

    return {
        "schema": SCHEMA,
        "state": "STAGED",
        "namespace": NAMESPACE,
        "binding": binding,
        "runtime_checkpoint_candidate": candidate,
        "expected_runtime_digest": expected_runtime_digest,
        "requires_explicit_checkpoint_save": True,
        "checkpoint_external_persistence_verified": False,
        "signature_material_ready": False,
        "digest_to_sign": "",
        "owner_decision_ready": False,
        "owner_decision": "UNDECIDED",
        "core_freeze_authorized": False,
        "core_frozen": False,
        "worker_armed": False,
        "external_persisted": False,
        "external_action_executed": False,
        "network_called": False,
        "save_called": False,
    }


def _binding_blockers(
    actual: Any,
    *,
    expected: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if not isinstance(actual, Mapping):
        return ["RUNTIME_BINDING_MISSING"]
    if set(actual) != set(expected):
        blockers.append("RUNTIME_BINDING_SHAPE_MISMATCH")
    for key, value in expected.items():
        if actual.get(key) != value:
            blockers.append(f"RUNTIME_BINDING_MISMATCH:{key}")
    supplied = str(actual.get("binding_digest") or "")
    body = {key: value for key, value in actual.items() if key != "binding_digest"}
    if not _SHA256_RE.fullmatch(supplied) or supplied != _digest(body):
        blockers.append("RUNTIME_BINDING_DIGEST_INVALID")
    return blockers


def verify_external_checkpoint_persistence(
    *,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    runtime_result: Mapping[str, Any] | None,
    write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Verify external persistence evidence and prepare signable material only."""
    blockers: list[str] = []
    target = _clean_sha(expected_target_commit_sha)

    if not isinstance(checkpoint_master, Mapping):
        blockers.append("CHECKPOINT_MASTER_REQUIRED")
    if not isinstance(preflight, Mapping):
        blockers.append("V222_PREFLIGHT_REQUIRED")

    if not blockers:
        preflight_check = verify_preflight_still_current(
            preflight,
            certification_manifest=certification_manifest,
            certification_trust_roots=certification_trust_roots,
            expected_target_commit_sha=target,
            checkpoint_master=checkpoint_master,
            now_ts=now_ts,
        )
        if preflight_check.get("state") != "CURRENT":
            blockers.append("V222_PREFLIGHT_NOT_CURRENT")
            blockers.extend(
                f"V222:{item}" for item in preflight_check.get("blockers", [])
            )
    else:
        preflight_check = {
            "state": "BLOCKED",
            "blockers": list(blockers),
            "preflight_current": False,
        }

    expected_binding = None
    if not blockers:
        try:
            expected_binding = build_runtime_binding(
                checkpoint_master,
                preflight,
                expected_target_commit_sha=target,
            )
        except Exception:
            blockers.append("RUNTIME_BINDING_BUILD_FAILED")

    runtime = dict(runtime_result or {}) if isinstance(runtime_result, Mapping) else {}
    receipt = dict(write_receipt or {}) if isinstance(write_receipt, Mapping) else {}

    if runtime.get("schema") != MEMORY_SCHEMA:
        blockers.append("RUNTIME_SCHEMA_INVALID")
    if str(runtime.get("status") or "").upper() != "CONFIRMED":
        blockers.append("RUNTIME_NOT_CONFIRMED")
    runtime_sha = str(runtime.get("sha") or "").strip().lower()
    if not _SHA_RE.fullmatch(runtime_sha):
        blockers.append("RUNTIME_SHA_INVALID")
    runtime_checkpoint = runtime.get("checkpoint")
    if not isinstance(runtime_checkpoint, Mapping):
        blockers.append("RUNTIME_CHECKPOINT_MISSING")

    try:
        observed = _parse_ts(runtime.get("checked_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("RUNTIME_OBSERVATION_TIME_INVALID")
    else:
        age = (now - observed).total_seconds()
        if age < -5:
            blockers.append("RUNTIME_OBSERVATION_FROM_FUTURE")
        elif age > MAX_RUNTIME_OBSERVATION_AGE_SECONDS:
            blockers.append("RUNTIME_OBSERVATION_STALE")

    target_info = receipt.get("target") if isinstance(receipt.get("target"), Mapping) else {}
    target_branch = str(target_info.get("branch") or "").strip()
    target_path = str(target_info.get("path") or "").strip()
    target_repo = str(target_info.get("repo") or "").strip()
    if receipt.get("schema") != WRITE_RECEIPT_SCHEMA:
        blockers.append("WRITE_RECEIPT_SCHEMA_INVALID")
    if not all((target_repo, target_branch, target_path)):
        blockers.append("WRITE_RECEIPT_TARGET_INCOMPLETE")
    else:
        try:
            require_runtime_branch(target_branch)
        except Exception:
            blockers.append("WRITE_RECEIPT_RUNTIME_BRANCH_UNSAFE")
        if target_repo != EXPECTED_RUNTIME_REPO:
            blockers.append("WRITE_RECEIPT_TARGET_MISMATCH:repo")
        if target_branch != EXPECTED_RUNTIME_BRANCH:
            blockers.append("WRITE_RECEIPT_TARGET_MISMATCH:branch")
        if target_path != EXPECTED_RUNTIME_PATH:
            blockers.append("WRITE_RECEIPT_TARGET_MISMATCH:path")
        expected_source = f"GitHub:{EXPECTED_RUNTIME_BRANCH}:{EXPECTED_RUNTIME_PATH}"
        if str(runtime.get("source") or "").strip() != expected_source:
            blockers.append("RUNTIME_SOURCE_MISMATCH")

    if expected_binding is not None and isinstance(runtime_checkpoint, Mapping):
        normalized_runtime = ensure_operating_checkpoint(runtime_checkpoint)
        blockers.extend(
            _binding_blockers(
                normalized_runtime.get(NAMESPACE),
                expected=expected_binding,
            )
        )
    else:
        normalized_runtime = None

    reconciliation = reconcile_runtime_write(receipt, runtime)
    if reconciliation.get("status") != "CONFIRMED":
        blockers.append("WRITE_NOT_ATTRIBUTED_CONFIRMED")
    if reconciliation.get("verified") is not True:
        blockers.append("WRITE_RECEIPT_NOT_VERIFIED")
    if reconciliation.get("write_attributed") is not True:
        blockers.append("WRITE_NOT_ATTRIBUTED")
    if reconciliation.get("executes_action") is not False:
        blockers.append("RECONCILIATION_EXECUTION_FLAG_INVALID")

    runtime_digest = ""
    if normalized_runtime is not None:
        runtime_digest = checkpoint_source_digest(normalized_runtime)
        if receipt.get("expected_digest") != runtime_digest:
            blockers.append("RUNTIME_DIGEST_RECEIPT_MISMATCH")
        if reconciliation.get("actual_digest") != runtime_digest:
            blockers.append("RUNTIME_DIGEST_RECONCILIATION_MISMATCH")

    write_sha = str(receipt.get("write_sha") or "").strip().lower()
    if not _SHA_RE.fullmatch(write_sha) or write_sha != runtime_sha:
        blockers.append("RUNTIME_WRITE_SHA_MISMATCH")

    unique = sorted(set(blockers))
    attested = not unique

    signature_body = {
        "schema": SIGNING_SCHEMA,
        "target_commit_sha": target,
        "v222_preflight_challenge_digest": (
            str(preflight.get("challenge_digest") or "")
            if isinstance(preflight, Mapping)
            else ""
        ),
        "runtime_binding_digest": (
            str(expected_binding.get("binding_digest") or "")
            if isinstance(expected_binding, Mapping)
            else ""
        ),
        "runtime_checkpoint_digest": runtime_digest,
        "runtime_sha": runtime_sha,
        "runtime_source": str(runtime.get("source") or "").strip(),
        "write_receipt_intent_id": str(receipt.get("intent_id") or "").strip(),
        "write_receipt_schema": str(receipt.get("schema") or "").strip(),
        "persistence_attested": attested,
        "owner_decision": "UNDECIDED",
        "owner_decision_ready": False,
        "signature_performed": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    signing_digest = _digest(signature_body) if attested else ""

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_OWNER_SIGNATURE_CEREMONY" if attested else "BLOCKED",
        "blockers": unique,
        "checkpoint_external_persistence_verified": attested,
        "runtime_write_attributed": bool(
            attested and reconciliation.get("write_attributed") is True
        ),
        "runtime_observation_fresh": bool(
            attested and "RUNTIME_OBSERVATION_STALE" not in unique
        ),
        "signature_material_ready": attested,
        "signature_challenge": signature_body if attested else {},
        "digest_to_sign": signing_digest,
        "owner_decision_ready": False,
        "owner_decision": "UNDECIDED",
        "signature_active": False,
        "biometric_capture_performed": False,
        "signature_performed": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "worker_armed": False,
        "checkpoint_saved_by_this_check": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "external_action_executed": False,
        "network_called": False,
        "save_called": False,
        "reconciliation": reconciliation,
        "v222_preflight_check": preflight_check,
    }


__all__ = [
    "SCHEMA",
    "BINDING_SCHEMA",
    "SIGNING_SCHEMA",
    "NAMESPACE",
    "MAX_RUNTIME_OBSERVATION_AGE_SECONDS",
    "EXPECTED_RUNTIME_REPO",
    "EXPECTED_RUNTIME_BRANCH",
    "EXPECTED_RUNTIME_PATH",
    "build_runtime_binding",
    "stage_runtime_persistence_candidate",
    "verify_external_checkpoint_persistence",
]
