#!/usr/bin/env python3
"""Execute the separate AION Core V1 Freeze ceremony under an exact flag.

Dry-run verifies V2.26, external owner signature and runtime continuity without
consuming the freeze nonce. The real path claims the nonce and performs exactly
one CAS write to the official runtime. It never authorizes merge, deploy or the
Global Worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlasquant_aion_memory import (
    checkpoint_source_digest,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    reconcile_runtime_write,
    runtime_configuration_status,
    save_runtime_checkpoint,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry
from ops.aion_core_v1_formal_closure.core_freeze_ceremony import (
    FREEZE_RECORD_SCHEMA,
    FREEZE_RESULT_SCHEMA,
    NAMESPACE,
    TARGET,
    canonical,
    digest,
    verify_freeze_signature,
)

EXPECTED_SOURCE = "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_signature(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit("freeze signature file is empty")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_registry_outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    root = Path.cwd().resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise SystemExit("nonce registry must be outside the repository working tree")


def blocked(reason: str, *, out: Path, evidence: Any = None) -> int:
    payload = {
        "schema": FREEZE_RESULT_SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "automatic_retry": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
    }
    if evidence is not None:
        payload["evidence"] = evidence
    write_json(out / "core_freeze_blocked.json", payload)
    print(json.dumps({
        "state": "BLOCKED",
        "reason": reason,
        "automatic_retry": False,
    }, sort_keys=True))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v226-attestation", type=Path, required=True)
    parser.add_argument("--freeze-request", type=Path, required=True)
    parser.add_argument("--freeze-signature-file", type=Path, required=True)
    parser.add_argument("--owner-trust-root", type=Path, required=True)
    parser.add_argument("--nonce-registry", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute-core-freeze", action="store_true")
    args = parser.parse_args()

    out = args.output_dir
    v226 = read_json(args.v226_attestation)
    request = read_json(args.freeze_request)
    signature = read_signature(args.freeze_signature_file)
    roots = TrustRootRegistry.from_mapping(read_json(args.owner_trust_root))
    now = now_iso()

    verified = verify_freeze_signature(
        request,
        signature_b64=signature,
        owner_trust_roots=roots,
        v226=v226,
        now_ts=now,
    )
    write_json(out / "core_freeze_signature_verification.json", verified)
    if verified.get("state") != "CORE_FREEZE_SIGNATURE_VERIFIED":
        return blocked("Core Freeze signature verification failed", out=out, evidence=verified)

    current = load_runtime_checkpoint()
    write_json(out / "core_freeze_runtime_before.json", current)
    if current.get("status") != "CONFIRMED":
        return blocked("official runtime is not CONFIRMED", out=out, evidence=current)
    if current.get("source") != EXPECTED_SOURCE:
        return blocked("runtime source mismatch", out=out, evidence=current)
    current_sha = str(current.get("sha") or "").strip()
    if current_sha != str(verified.get("source_runtime_sha") or ""):
        return blocked("runtime changed after V2.26; rebuild freeze ceremony", out=out, evidence=current)
    checkpoint = current.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return blocked("runtime checkpoint missing", out=out, evidence=current)
    current_digest = checkpoint_source_digest(checkpoint)
    request_runtime_digest = str(request.get("decision_runtime_digest") or "")
    if current_digest != request_runtime_digest:
        return blocked("runtime digest changed after V2.26", out=out, evidence={
            "observed": current_digest,
            "expected": request_runtime_digest,
        })

    config = runtime_configuration_status()
    write_json(out / "core_freeze_runtime_config_status.json", config)
    dry = {
        "schema": "AION_CORE_V1_CORE_FREEZE_WRITE_PREFLIGHT_V1",
        "state": "READY_FOR_EXPLICIT_CORE_FREEZE_WRITE",
        "target_commit_sha": TARGET,
        "runtime_sha": current_sha,
        "runtime_digest": current_digest,
        "freeze_signature_verified": True,
        "freeze_nonce_consumed": False,
        "write_ready": config.get("write_ready") is True,
        "execute_requested": args.execute_core_freeze is True,
        "core_freeze_execution_authorized": True,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "automatic_retry": False,
    }
    write_json(out / "core_freeze_write_preflight.json", dry)
    if not args.execute_core_freeze:
        print(json.dumps(dry, sort_keys=True))
        return 0
    if config.get("write_ready") is not True:
        return blocked("runtime write credential is not configured", out=out, evidence=config)

    registry = PersistentNonceRegistry(ensure_registry_outside_repo(args.nonce_registry))
    scope = "|".join((
        "CORE_FREEZE_EXECUTION",
        str(request.get("owner_id") or ""),
        str(request.get("tenant_id") or ""),
        str(request.get("key_id") or ""),
        str(request.get("key_version") or ""),
        str(request.get("request_digest") or digest(request)),
    ))
    try:
        claimed = registry.claim(
            scope=scope,
            nonce=str(request["nonce"]),
            expires_at=str(request["expires_at"]),
            now_ts=now_iso(),
        )
    except Exception as exc:
        return blocked("freeze nonce registry failure: " + type(exc).__name__, out=out)
    if not claimed:
        return blocked("freeze nonce replayed or expired", out=out)

    record_body = {
        "schema": FREEZE_RECORD_SCHEMA,
        "state": "CORE_FROZEN",
        "target_commit_sha": TARGET,
        "owner_id": str(request["owner_id"]),
        "tenant_id": str(request["tenant_id"]),
        "owner_decision": "APPROVE_CORE_FREEZE",
        "owner_decision_recorded": True,
        "decision_record_persisted": True,
        "v226_freeze_material_digest": str(request["v226_freeze_material_digest"]),
        "decision_record_digest": str(request["decision_record_digest"]),
        "freeze_request_digest": digest(request),
        "freeze_signature_digest": str(verified["signature_digest"]),
        "owner_key_id": str(verified["owner_key_id"]),
        "owner_key_version": int(verified["owner_key_version"]),
        "source_runtime_sha": current_sha,
        "source_runtime_digest": current_digest,
        "frozen_at": now_iso(),
        "core_complete": True,
        "core_freeze_ceremony_eligible": True,
        "core_freeze_execution_authorized": True,
        "core_frozen": True,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    record = {**record_body, "freeze_record_digest": digest(record_body)}

    candidate = ensure_operating_checkpoint(checkpoint)
    candidate = deepcopy(candidate)
    candidate[NAMESPACE] = record
    if isinstance(candidate.get("operating"), dict):
        candidate["operating"]["dirty"] = True
    expected_digest = checkpoint_source_digest(candidate)

    staged = {
        "schema": "AION_CORE_V1_CORE_FREEZE_STAGED_RUNTIME_V1",
        "state": "STAGED_FOR_EXPLICIT_CORE_FREEZE_PERSISTENCE",
        "namespace": NAMESPACE,
        "record": record,
        "expected_previous_runtime_sha": current_sha,
        "expected_runtime_digest": expected_digest,
        "freeze_nonce_consumed": True,
        "core_frozen_in_memory_only": True,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "runtime_checkpoint_candidate": candidate,
    }
    write_json(out / "core_freeze_staged_candidate.json", staged)

    saved = save_runtime_checkpoint(
        candidate,
        approved=True,
        expected_sha=current_sha,
        allow_global_arming_transition=False,
    )
    write_json(out / "core_freeze_save_result.json", saved)
    if saved.get("status") != "CONFIRMED" or saved.get("saved") is not True or saved.get("verified") is not True:
        return blocked(
            "Core Freeze write not positively confirmed; reconcile manually and never retry automatically",
            out=out,
            evidence=saved,
        )

    receipt = saved.get("write_receipt")
    if not isinstance(receipt, dict):
        return blocked("confirmed Core Freeze write missing receipt", out=out, evidence=saved)

    reconciliation = reconcile_runtime_write(receipt, saved)
    persisted = saved.get("checkpoint")
    blockers = []
    if not isinstance(persisted, dict):
        blockers.append("PERSISTED_CHECKPOINT_MISSING")
        persisted = {}
    normalized = ensure_operating_checkpoint(persisted)
    actual = normalized.get(NAMESPACE)
    if actual != record:
        blockers.append("FREEZE_RECORD_READ_AFTER_WRITE_MISMATCH")
    actual_digest = checkpoint_source_digest(normalized)
    if actual_digest != expected_digest:
        blockers.append("FREEZE_RUNTIME_DIGEST_MISMATCH")
    if receipt.get("expected_sha") != current_sha:
        blockers.append("FREEZE_WRITE_CAS_BASE_MISMATCH")
    runtime_sha_after = str(saved.get("sha") or "")
    if not runtime_sha_after or runtime_sha_after == current_sha:
        blockers.append("FREEZE_RUNTIME_SHA_DID_NOT_ADVANCE")
    if receipt.get("write_sha") != runtime_sha_after:
        blockers.append("FREEZE_WRITE_SHA_MISMATCH")
    if receipt.get("expected_digest") != actual_digest:
        blockers.append("FREEZE_RECEIPT_DIGEST_MISMATCH")
    if reconciliation.get("status") != "CONFIRMED":
        blockers.append("FREEZE_WRITE_RECONCILIATION_NOT_CONFIRMED")
    if reconciliation.get("verified") is not True:
        blockers.append("FREEZE_WRITE_RECEIPT_NOT_VERIFIED")
    if reconciliation.get("write_attributed") is not True:
        blockers.append("FREEZE_WRITE_NOT_ATTRIBUTED")

    if blockers:
        return blocked(
            "Core Freeze persistence attestation blocked; do not proceed to merge/deploy/worker",
            out=out,
            evidence={"blockers": sorted(set(blockers)), "reconciliation": reconciliation},
        )

    attestation_body = {
        "schema": FREEZE_RESULT_SCHEMA,
        "state": "CORE_FREEZE_PERSISTENCE_ATTESTED",
        "target_commit_sha": TARGET,
        "freeze_record_digest": record["freeze_record_digest"],
        "freeze_request_digest": record["freeze_request_digest"],
        "freeze_signature_digest": record["freeze_signature_digest"],
        "source_runtime_sha": current_sha,
        "frozen_runtime_sha": runtime_sha_after,
        "frozen_runtime_digest": actual_digest,
        "write_intent_id": str(receipt.get("intent_id") or ""),
        "core_complete": True,
        "core_frozen": True,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "global_worker_activation_authorized": False,
        "requires_separate_merge_decision": True,
        "requires_separate_deploy_decision": True,
        "requires_separate_global_worker_arming": True,
        "requires_separate_global_worker_activation": True,
        "automatic_retry": False,
    }
    attestation = {
        **attestation_body,
        "attestation_digest": digest(attestation_body),
        "reconciliation": reconciliation,
    }
    write_json(out / "core_freeze_attestation.json", attestation)

    handoff = {
        "schema": "AION_CORE_V1_POST_FREEZE_HANDOFF_V1",
        "state": "CORE_V1_FROZEN_NEXT_ACTIONS_CLOSED",
        "target_commit_sha": TARGET,
        "freeze_attestation_digest": attestation["attestation_digest"],
        "core_complete": True,
        "core_frozen": True,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "worker_activation_authorized": False,
        "next_steps": {
            "merge": "SEPARATE_OWNER_DECISION_REQUIRED",
            "deploy": "SEPARATE_OWNER_DECISION_REQUIRED_AFTER_MERGE_EVIDENCE",
            "global_worker_arming": "SEPARATE_ARMING_CEREMONY_REQUIRED",
            "global_worker_activation": "SEPARATE_ACTIVATION_CEREMONY_REQUIRED_AFTER_PERSISTED_ARMED_STATE",
        },
    }
    write_json(out / "post_freeze_handoff.json", handoff)
    print(json.dumps(attestation, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
