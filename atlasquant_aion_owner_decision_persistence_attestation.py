"""AION V2.26 owner-decision record persistence attestation.

This layer proves that an exact V2.25 owner decision record was durably written
to the official runtime target and read back with write attribution.

It never performs the write itself. It reconstructs and re-verifies the V2.25
decision from cryptographic evidence plus the durable nonce claim, stages an
in-memory runtime candidate, and later verifies an externally supplied write
receipt + confirmed runtime observation.

Only after persistence attestation may owner_decision_recorded become true.
Even an attested APPROVE never executes Core Freeze.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_memory import (
    DEFAULT_RUNTIME_REPO,
    RUNTIME_PATH,
    SCHEMA as MEMORY_SCHEMA,
    WRITE_RECEIPT_SCHEMA,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
    reconcile_runtime_write,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_decision_record import (
    DECISION_PURPOSE,
    DECISION_SIGNATURE_MECHANISM,
    DECISIONS,
    REQUEST_SCHEMA as V225_REQUEST_SCHEMA,
    build_owner_decision_request,
    canonical_owner_decision_bytes,
    owner_decision_nonce_scope,
)
from atlasquant_aion_trust_root import TrustRootRegistry
from atlasquant_runtime_store import require_runtime_branch

SCHEMA = "ATLASQUANT_AION_OWNER_DECISION_PERSISTENCE_ATTESTATION_V1"
RECORD_SCHEMA = "ATLASQUANT_AION_OWNER_DECISION_RUNTIME_RECORD_V1"
FREEZE_MATERIAL_SCHEMA = "ATLASQUANT_AION_CORE_FREEZE_CEREMONY_MATERIAL_V1"
NAMESPACE = "aion_core_owner_decision_v1"
EXPECTED_RUNTIME_REPO = DEFAULT_RUNTIME_REPO
EXPECTED_RUNTIME_BRANCH = "atlasquant-runtime"
EXPECTED_RUNTIME_PATH = RUNTIME_PATH
MAX_RUNTIME_OBSERVATION_AGE_SECONDS = 300
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


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        decoded = base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return decoded


def _signature_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_decode_signature(value)).hexdigest()


def _public_key_fingerprint(entry: Any) -> str:
    encoded = str(entry.public_key_b64 or "").encode("ascii")
    raw = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _decision_evidence(
    *,
    decision_request: Mapping[str, Any] | None,
    decision_signature_b64: str,
    decision_nonce_registry: PersistentNonceRegistry,
    v224_request: Mapping[str, Any] | None,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    v223_runtime_result: Mapping[str, Any] | None,
    v223_write_receipt: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    if not isinstance(decision_request, Mapping):
        return None, ["V225_DECISION_REQUEST_REQUIRED"]
    if not isinstance(decision_nonce_registry, PersistentNonceRegistry):
        return None, ["V225_DECISION_NONCE_REGISTRY_INVALID"]
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return None, ["OWNER_TRUST_ROOT_REGISTRY_INVALID"]

    presented = dict(decision_request)
    if presented.get("schema") != V225_REQUEST_SCHEMA:
        blockers.append("V225_DECISION_REQUEST_SCHEMA_INVALID")
    if presented.get("decision") not in DECISIONS:
        blockers.append("V225_DECISION_CHOICE_INVALID")
    if presented.get("decision_purpose") != DECISION_PURPOSE:
        blockers.append("V225_DECISION_PURPOSE_INVALID")
    if presented.get("decision_signature_mechanism") != DECISION_SIGNATURE_MECHANISM:
        blockers.append("V225_DECISION_SIGNATURE_MECHANISM_INVALID")
    if blockers:
        return None, blockers

    request_digest = _digest(presented)
    if not _SHA256_RE.fullmatch(request_digest):
        return None, ["V225_DECISION_REQUEST_DIGEST_INVALID"]

    try:
        scope = owner_decision_nonce_scope(
            presented,
            request_digest=request_digest,
        )
        claim = decision_nonce_registry.read_claim(
            scope=scope,
            nonce=str(presented.get("nonce") or ""),
        )
    except Exception:
        return None, ["V225_DECISION_NONCE_CLAIM_READ_FAILURE"]
    if not isinstance(claim, Mapping):
        return None, ["V225_DECISION_NONCE_CLAIM_MISSING"]
    if claim.get("expires_at") != presented.get("expires_at"):
        blockers.append("V225_DECISION_NONCE_EXPIRY_MISMATCH")

    claim_created_at = str(claim.get("created_at") or "")
    try:
        claim_time = _parse_ts(claim_created_at)
        issued = _parse_ts(presented.get("issued_at"))
        expires = _parse_ts(presented.get("expires_at"))
    except ValueError:
        blockers.append("V225_DECISION_NONCE_TIME_INVALID")
    else:
        if claim_time < issued or claim_time >= expires:
            blockers.append("V225_DECISION_NONCE_CLAIM_OUTSIDE_WINDOW")

    if blockers:
        return None, blockers

    rebuilt = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature_b64,
        owner_trust_roots=owner_trust_roots,
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        runtime_result=v223_runtime_result,
        write_receipt=v223_write_receipt,
        now_ts=claim_created_at,
        decision=presented["decision"],
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["decision_key_id"],
        key_version=presented["decision_key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE":
        blockers.append("V225_DECISION_REQUEST_REBUILD_BLOCKED")
        blockers.extend(
            f"V225:{item}" for item in rebuilt.get("blockers", [])
        )
        return None, sorted(set(blockers))
    if rebuilt.get("request") != presented:
        return None, ["V225_DECISION_REQUEST_REBUILD_MISMATCH"]
    if rebuilt.get("request_digest") != request_digest:
        return None, ["V225_DECISION_REQUEST_DIGEST_MISMATCH"]

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["decision_key_id"],
            presented["decision_key_version"],
            claim_created_at,
        )
    except Exception:
        return None, ["OWNER_TRUST_ROOT_VERIFICATION_FAILURE"]
    if key_problem:
        return None, [f"OWNER_{key_problem}"]
    if entry is None:
        return None, ["OWNER_TRUST_KEY_UNKNOWN"]
    if (
        presented.get("decision_public_key_fingerprint")
        != _public_key_fingerprint(entry)
    ):
        return None, ["V225_DECISION_PUBLIC_KEY_FINGERPRINT_MISMATCH"]

    try:
        signature = _decode_signature(decision_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_decision_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return None, ["V225_DECISION_SIGNATURE_INVALID"]

    decision = presented["decision"]
    approved = decision == "APPROVE_CORE_FREEZE"
    record_body = {
        "schema": RECORD_SCHEMA,
        "target_commit_sha": str(expected_target_commit_sha or "").strip().lower(),
        "owner_id": presented["owner_id"],
        "tenant_id": presented["tenant_id"],
        "decision": decision,
        "decision_request_digest": request_digest,
        "decision_signature_digest": _signature_digest(decision_signature_b64),
        "decision_nonce": presented["nonce"],
        "decision_nonce_scope_digest": _digest({"scope": scope}),
        "decision_nonce_claimed_at": claim_created_at,
        "decision_nonce_expires_at": presented["expires_at"],
        "v224_request_digest": presented["v224_request_digest"],
        "v224_signature_digest": presented["v224_signature_digest"],
        "v223_digest_to_sign": presented["v223_digest_to_sign"],
        "decision_key_id": presented["decision_key_id"],
        "decision_key_version": presented["decision_key_version"],
        "decision_public_key_fingerprint": presented[
            "decision_public_key_fingerprint"
        ],
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "persistence_attested": False,
        "core_freeze_approved": approved,
        "core_freeze_denied": not approved,
        "core_freeze_ceremony_eligible": False,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    return {
        **record_body,
        "record_digest": _digest(record_body),
    }, []


def stage_owner_decision_record_persistence_candidate(
    *,
    decision_request: Mapping[str, Any] | None,
    decision_signature_b64: str,
    decision_nonce_registry: PersistentNonceRegistry,
    v224_request: Mapping[str, Any] | None,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    v223_runtime_result: Mapping[str, Any] | None,
    v223_write_receipt: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Stage exact V2.25 decision record into runtime memory; never save it."""
    record, blockers = _decision_evidence(
        decision_request=decision_request,
        decision_signature_b64=decision_signature_b64,
        decision_nonce_registry=decision_nonce_registry,
        v224_request=v224_request,
        v224_signature_b64=v224_signature_b64,
        owner_trust_roots=owner_trust_roots,
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        v223_runtime_result=v223_runtime_result,
        v223_write_receipt=v223_write_receipt,
    )
    if blockers or record is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": sorted(set(blockers or ["V225_DECISION_EVIDENCE_INVALID"])),
            "runtime_checkpoint_candidate": {},
            "expected_runtime_digest": "",
            "owner_decision_verified": False,
            "owner_decision_recorded": False,
            "decision_record_persisted": False,
            "persistence_attested": False,
            "core_freeze_ceremony_eligible": False,
            "core_freeze_execution_authorized": False,
            "core_frozen": False,
            "save_called": False,
            "network_called": False,
            "external_action_executed": False,
        }

    prior_runtime = (
        dict(v223_runtime_result or {}).get("checkpoint")
        if isinstance(v223_runtime_result, Mapping)
        else None
    )
    if not isinstance(prior_runtime, Mapping):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": ["V223_RUNTIME_CHECKPOINT_MISSING"],
            "runtime_checkpoint_candidate": {},
            "expected_runtime_digest": "",
            "owner_decision_verified": False,
            "owner_decision_recorded": False,
            "decision_record_persisted": False,
            "persistence_attested": False,
            "core_freeze_ceremony_eligible": False,
            "core_freeze_execution_authorized": False,
            "core_frozen": False,
            "save_called": False,
            "network_called": False,
            "external_action_executed": False,
        }

    candidate = ensure_operating_checkpoint(prior_runtime)
    candidate = deepcopy(candidate)
    candidate[NAMESPACE] = record
    operating = candidate.get("operating")
    if isinstance(operating, dict):
        operating["dirty"] = True
    expected_digest = checkpoint_source_digest(candidate)
    if not _HEX16_RE.fullmatch(expected_digest):
        raise ValueError("runtime candidate digest invalid")

    return {
        "schema": SCHEMA,
        "state": "STAGED_FOR_EXPLICIT_DECISION_RECORD_PERSISTENCE",
        "blockers": [],
        "namespace": NAMESPACE,
        "decision_record": record,
        "runtime_checkpoint_candidate": candidate,
        "expected_runtime_digest": expected_digest,
        "expected_previous_runtime_sha": str(
            dict(v223_runtime_result or {}).get("sha") or ""
        ).strip().lower(),
        "requires_explicit_checkpoint_save": True,
        "requires_persistence_attestation": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "persistence_attested": False,
        "core_freeze_ceremony_eligible": False,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "save_called": False,
        "network_called": False,
        "external_action_executed": False,
    }


def _record_blockers(actual: Any, *, expected: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not isinstance(actual, Mapping):
        return ["DECISION_RUNTIME_RECORD_MISSING"]
    if set(actual) != set(expected):
        blockers.append("DECISION_RUNTIME_RECORD_SHAPE_MISMATCH")
    for key, value in expected.items():
        if actual.get(key) != value:
            blockers.append(f"DECISION_RUNTIME_RECORD_MISMATCH:{key}")
    supplied = str(actual.get("record_digest") or "")
    body = {key: value for key, value in actual.items() if key != "record_digest"}
    if not _SHA256_RE.fullmatch(supplied) or supplied != _digest(body):
        blockers.append("DECISION_RUNTIME_RECORD_DIGEST_INVALID")
    return blockers


def verify_owner_decision_record_persistence(
    *,
    decision_request: Mapping[str, Any] | None,
    decision_signature_b64: str,
    decision_nonce_registry: PersistentNonceRegistry,
    v224_request: Mapping[str, Any] | None,
    v224_signature_b64: str,
    owner_trust_roots: TrustRootRegistry,
    checkpoint_master: Mapping[str, Any] | None,
    preflight: Mapping[str, Any] | None,
    certification_manifest: Mapping[str, Any] | None,
    certification_trust_roots: TrustRootRegistry,
    expected_target_commit_sha: str,
    v223_runtime_result: Mapping[str, Any] | None,
    v223_write_receipt: Mapping[str, Any] | None,
    decision_runtime_result: Mapping[str, Any] | None,
    decision_write_receipt: Mapping[str, Any] | None,
    now_ts: str,
) -> dict[str, Any]:
    """Verify attributed persistence of the exact decision record."""
    staged = stage_owner_decision_record_persistence_candidate(
        decision_request=decision_request,
        decision_signature_b64=decision_signature_b64,
        decision_nonce_registry=decision_nonce_registry,
        v224_request=v224_request,
        v224_signature_b64=v224_signature_b64,
        owner_trust_roots=owner_trust_roots,
        checkpoint_master=checkpoint_master,
        preflight=preflight,
        certification_manifest=certification_manifest,
        certification_trust_roots=certification_trust_roots,
        expected_target_commit_sha=expected_target_commit_sha,
        v223_runtime_result=v223_runtime_result,
        v223_write_receipt=v223_write_receipt,
    )
    blockers = list(staged.get("blockers", []))
    if staged.get("state") != "STAGED_FOR_EXPLICIT_DECISION_RECORD_PERSISTENCE":
        blockers.append("DECISION_RECORD_STAGING_NOT_READY")

    runtime = (
        dict(decision_runtime_result or {})
        if isinstance(decision_runtime_result, Mapping)
        else {}
    )
    receipt = (
        dict(decision_write_receipt or {})
        if isinstance(decision_write_receipt, Mapping)
        else {}
    )

    if runtime.get("schema") != MEMORY_SCHEMA:
        blockers.append("DECISION_RUNTIME_SCHEMA_INVALID")
    if str(runtime.get("status") or "").upper() != "CONFIRMED":
        blockers.append("DECISION_RUNTIME_NOT_CONFIRMED")
    runtime_sha = str(runtime.get("sha") or "").strip().lower()
    if not _SHA_RE.fullmatch(runtime_sha):
        blockers.append("DECISION_RUNTIME_SHA_INVALID")
    runtime_checkpoint = runtime.get("checkpoint")
    if not isinstance(runtime_checkpoint, Mapping):
        blockers.append("DECISION_RUNTIME_CHECKPOINT_MISSING")

    try:
        observed = _parse_ts(runtime.get("checked_at"))
        now = _parse_ts(now_ts)
    except ValueError:
        blockers.append("DECISION_RUNTIME_OBSERVATION_TIME_INVALID")
    else:
        age = (now - observed).total_seconds()
        if age < -5:
            blockers.append("DECISION_RUNTIME_OBSERVATION_FROM_FUTURE")
        elif age > MAX_RUNTIME_OBSERVATION_AGE_SECONDS:
            blockers.append("DECISION_RUNTIME_OBSERVATION_STALE")

    target = receipt.get("target") if isinstance(receipt.get("target"), Mapping) else {}
    repo = str(target.get("repo") or "").strip()
    branch = str(target.get("branch") or "").strip()
    path = str(target.get("path") or "").strip()
    if receipt.get("schema") != WRITE_RECEIPT_SCHEMA:
        blockers.append("DECISION_WRITE_RECEIPT_SCHEMA_INVALID")
    if not all((repo, branch, path)):
        blockers.append("DECISION_WRITE_RECEIPT_TARGET_INCOMPLETE")
    else:
        try:
            require_runtime_branch(branch)
        except Exception:
            blockers.append("DECISION_WRITE_RECEIPT_RUNTIME_BRANCH_UNSAFE")
        if repo != EXPECTED_RUNTIME_REPO:
            blockers.append("DECISION_WRITE_RECEIPT_TARGET_MISMATCH:repo")
        if branch != EXPECTED_RUNTIME_BRANCH:
            blockers.append("DECISION_WRITE_RECEIPT_TARGET_MISMATCH:branch")
        if path != EXPECTED_RUNTIME_PATH:
            blockers.append("DECISION_WRITE_RECEIPT_TARGET_MISMATCH:path")
        expected_source = f"GitHub:{EXPECTED_RUNTIME_BRANCH}:{EXPECTED_RUNTIME_PATH}"
        if str(runtime.get("source") or "").strip() != expected_source:
            blockers.append("DECISION_RUNTIME_SOURCE_MISMATCH")

    previous_sha = str(staged.get("expected_previous_runtime_sha") or "").strip().lower()
    receipt_expected_sha = str(receipt.get("expected_sha") or "").strip().lower()
    if not _SHA_RE.fullmatch(previous_sha):
        blockers.append("V223_PRIOR_RUNTIME_SHA_INVALID")
    if receipt_expected_sha != previous_sha:
        blockers.append("DECISION_WRITE_CAS_BASE_SHA_MISMATCH")
    if _SHA_RE.fullmatch(runtime_sha) and runtime_sha == previous_sha:
        blockers.append("DECISION_RUNTIME_SHA_DID_NOT_ADVANCE")

    expected_record = staged.get("decision_record")
    normalized_runtime = None
    if isinstance(runtime_checkpoint, Mapping):
        normalized_runtime = ensure_operating_checkpoint(runtime_checkpoint)
        if isinstance(expected_record, Mapping):
            blockers.extend(
                _record_blockers(
                    normalized_runtime.get(NAMESPACE),
                    expected=expected_record,
                )
            )

    reconciliation = reconcile_runtime_write(receipt, runtime)
    if reconciliation.get("status") != "CONFIRMED":
        blockers.append("DECISION_WRITE_NOT_ATTRIBUTED_CONFIRMED")
    if reconciliation.get("verified") is not True:
        blockers.append("DECISION_WRITE_RECEIPT_NOT_VERIFIED")
    if reconciliation.get("write_attributed") is not True:
        blockers.append("DECISION_WRITE_NOT_ATTRIBUTED")
    if reconciliation.get("executes_action") is not False:
        blockers.append("DECISION_RECONCILIATION_EXECUTION_FLAG_INVALID")

    runtime_digest = ""
    if normalized_runtime is not None:
        runtime_digest = checkpoint_source_digest(normalized_runtime)
        if runtime_digest != staged.get("expected_runtime_digest"):
            blockers.append("DECISION_RUNTIME_STAGED_DIGEST_MISMATCH")
        if receipt.get("expected_digest") != runtime_digest:
            blockers.append("DECISION_RUNTIME_DIGEST_RECEIPT_MISMATCH")
        if reconciliation.get("actual_digest") != runtime_digest:
            blockers.append("DECISION_RUNTIME_DIGEST_RECONCILIATION_MISMATCH")

    write_sha = str(receipt.get("write_sha") or "").strip().lower()
    if not _SHA_RE.fullmatch(write_sha) or write_sha != runtime_sha:
        blockers.append("DECISION_RUNTIME_WRITE_SHA_MISMATCH")

    unique = sorted(set(blockers))
    attested = not unique
    record = dict(expected_record or {}) if isinstance(expected_record, Mapping) else {}
    approved = record.get("decision") == "APPROVE_CORE_FREEZE"
    denied = record.get("decision") == "DENY_CORE_FREEZE"

    freeze_body = {
        "schema": FREEZE_MATERIAL_SCHEMA,
        "target_commit_sha": str(expected_target_commit_sha or "").strip().lower(),
        "decision": record.get("decision"),
        "decision_request_digest": record.get("decision_request_digest"),
        "decision_signature_digest": record.get("decision_signature_digest"),
        "decision_record_digest": record.get("record_digest"),
        "decision_runtime_sha": runtime_sha,
        "decision_runtime_digest": runtime_digest,
        "decision_write_intent_id": str(receipt.get("intent_id") or ""),
        "owner_decision_recorded": bool(attested),
        "decision_record_persisted": bool(attested),
        "core_freeze_ceremony_eligible": bool(attested and approved),
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    freeze_digest = _digest(freeze_body) if attested and approved else ""

    return {
        "schema": SCHEMA,
        "state": (
            "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE"
            if attested and approved
            else (
                "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_DENY"
                if attested and denied
                else "BLOCKED"
            )
        ),
        "blockers": unique,
        "owner_decision_verified": bool(attested),
        "owner_decision_recorded": bool(attested),
        "decision_record_persisted": bool(attested),
        "persistence_attested": bool(attested),
        "owner_decision": record.get("decision") if attested else "UNDECIDED",
        "decision_record_digest": record.get("record_digest") if attested else "",
        "runtime_write_attributed": bool(
            attested and reconciliation.get("write_attributed") is True
        ),
        "runtime_observation_fresh": bool(
            attested and "DECISION_RUNTIME_OBSERVATION_STALE" not in unique
        ),
        "core_freeze_approved": bool(attested and approved),
        "core_freeze_denied": bool(attested and denied),
        "core_freeze_ceremony_eligible": bool(attested and approved),
        "core_freeze_ceremony_material_ready": bool(attested and approved),
        "core_freeze_ceremony_material": freeze_body if attested and approved else {},
        "digest_to_core_freeze_ceremony": freeze_digest,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "checkpoint_saved_by_this_check": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "save_called": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
        "reconciliation": reconciliation,
    }


__all__ = [
    "SCHEMA",
    "RECORD_SCHEMA",
    "FREEZE_MATERIAL_SCHEMA",
    "NAMESPACE",
    "EXPECTED_RUNTIME_REPO",
    "EXPECTED_RUNTIME_BRANCH",
    "EXPECTED_RUNTIME_PATH",
    "MAX_RUNTIME_OBSERVATION_AGE_SECONDS",
    "stage_owner_decision_record_persistence_candidate",
    "verify_owner_decision_record_persistence",
]
