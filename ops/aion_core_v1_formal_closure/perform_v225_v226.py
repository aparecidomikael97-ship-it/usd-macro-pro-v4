#!/usr/bin/env python3
"""Verify V2.25 and persist/attest V2.26 only under an exact execution flag.

Dry-run mode validates current runtime and the decision signature WITHOUT
consuming the V2.25 decision nonce and WITHOUT writing runtime state.
"""
from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_memory import (
    load_runtime_checkpoint,
    runtime_configuration_status,
    save_runtime_checkpoint,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_decision_persistence_attestation import (
    stage_owner_decision_record_persistence_candidate,
    verify_owner_decision_record_persistence,
)
from atlasquant_aion_owner_decision_record import (
    build_owner_decision_request,
    canonical_owner_decision_bytes,
    verify_owner_decision,
)
from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
EXPECTED_SOURCE = "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_signature(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit("signature file is empty")
    return value


def decode_signature(value: str) -> bytes:
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    if len(raw) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return raw


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def ensure_registry_outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo_root = Path.cwd().resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return resolved
    raise SystemExit("nonce registry must be outside the repository working tree")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def blocked(reason: str, *, output_dir: Path, evidence: Any = None) -> int:
    result = {"state": "BLOCKED", "reason": reason, "automatic_retry": False}
    if evidence is not None:
        result["evidence"] = evidence
    write_json(output_dir / "v226_blocked.json", result)
    print(json.dumps({"state": "BLOCKED", "reason": reason, "automatic_retry": False}, sort_keys=True))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v225-request", type=Path, required=True)
    parser.add_argument("--v225-signature-file", type=Path, required=True)
    parser.add_argument("--v224-request", type=Path, required=True)
    parser.add_argument("--v224-signature-file", type=Path, required=True)
    parser.add_argument("--owner-trust-root", type=Path, required=True)
    parser.add_argument("--nonce-registry", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--certification-trust-root", type=Path, required=True)
    parser.add_argument("--checkpoint-master", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--v223-runtime-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute-v226-write", action="store_true")
    args = parser.parse_args()

    out = args.output_dir
    request = read_json(args.v225_request)
    decision_signature = read_signature(args.v225_signature_file)
    v224_request = read_json(args.v224_request)
    v224_signature = read_signature(args.v224_signature_file)
    owner_roots = TrustRootRegistry.from_mapping(read_json(args.owner_trust_root))
    cert_roots = TrustRootRegistry.from_mapping(read_json(args.certification_trust_root))
    manifest = read_json(args.manifest)
    master = read_json(args.checkpoint_master)
    preflight = read_json(args.preflight)
    v223_runtime = read_json(args.v223_runtime_result)
    v223_receipt = v223_runtime.get("write_receipt")
    if not isinstance(v223_receipt, dict):
        return blocked("V2.23 write receipt missing", output_dir=out)

    prior_sha = str(v223_runtime.get("sha") or "").strip()
    current = load_runtime_checkpoint()
    write_json(out / "v226_runtime_before.json", current)
    if current.get("status") != "CONFIRMED" or current.get("source") != EXPECTED_SOURCE:
        return blocked("current runtime is not the confirmed official target", output_dir=out, evidence=current)
    if str(current.get("sha") or "").strip() != prior_sha:
        return blocked("runtime changed after V2.23; rebuild owner ceremony before consuming decision nonce", output_dir=out, evidence=current)

    now = now_iso()
    # Rebuild the exact V2.25 request before nonce consumption.
    rebuilt = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        runtime_result=v223_runtime,
        write_receipt=v223_receipt,
        now_ts=now,
        decision=request.get("decision"),
        ceremony_id=request.get("ceremony_id"),
        nonce=request.get("nonce"),
        issued_at=request.get("issued_at"),
        expires_at=request.get("expires_at"),
        key_id=request.get("decision_key_id"),
        key_version=request.get("decision_key_version"),
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE":
        return blocked("V2.25 request rebuild blocked", output_dir=out, evidence=rebuilt)
    if rebuilt.get("request") != request:
        return blocked("V2.25 request rebuild mismatch", output_dir=out, evidence=rebuilt)

    # Cryptographically precheck the decision signature without claiming the nonce.
    try:
        entry, key_problem = owner_roots.verify_key_available(
            request["decision_key_id"],
            request["decision_key_version"],
            now,
        )
        if key_problem or entry is None:
            raise ValueError(key_problem or "owner key missing")
        entry.public_key().verify(
            decode_signature(decision_signature),
            canonical_owner_decision_bytes(request),
        )
    except (ValueError, InvalidSignature, KeyError) as exc:
        return blocked("V2.25 decision signature precheck failed: " + type(exc).__name__, output_dir=out)

    config = runtime_configuration_status()
    write_json(out / "v226_runtime_config_status.json", config)
    dry = {
        "schema": "AION_CORE_V1_V226_WRITE_PREFLIGHT_V1",
        "state": "READY_FOR_EXPLICIT_V226_WRITE",
        "decision": request.get("decision"),
        "runtime_sha": prior_sha,
        "decision_signature_preverified": True,
        "decision_nonce_consumed": False,
        "write_ready": config.get("write_ready") is True,
        "execute_requested": args.execute_v226_write is True,
        "core_freeze_ceremony_eligible": False,
        "core_frozen": False,
        "automatic_retry": False,
    }
    write_json(out / "v226_write_preflight.json", dry)
    if not args.execute_v226_write:
        print(json.dumps(dry, sort_keys=True))
        return 0
    if config.get("write_ready") is not True:
        return blocked("runtime write credential is not configured", output_dir=out, evidence=config)

    registry = PersistentNonceRegistry(ensure_registry_outside_repo(args.nonce_registry))
    verified = verify_owner_decision(
        request,
        decision_signature_b64=decision_signature,
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        decision_nonce_registry=registry,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        runtime_result=v223_runtime,
        write_receipt=v223_receipt,
        now_ts=now_iso(),
    )
    write_json(out / "v225_verification.json", verified)
    if verified.get("state") not in {
        "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE",
        "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE",
    }:
        return blocked("V2.25 verification blocked after nonce claim; do not retry with same nonce", output_dir=out, evidence=verified)

    staged = stage_owner_decision_record_persistence_candidate(
        decision_request=request,
        decision_signature_b64=decision_signature,
        decision_nonce_registry=registry,
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        v223_runtime_result=v223_runtime,
        v223_write_receipt=v223_receipt,
    )
    write_json(out / "v226_staged_candidate.json", staged)
    if staged.get("state") != "STAGED_FOR_EXPLICIT_DECISION_RECORD_PERSISTENCE":
        return blocked("V2.26 staging blocked after decision nonce claim; do not retry automatically", output_dir=out, evidence=staged)
    if staged.get("expected_previous_runtime_sha") != prior_sha:
        return blocked("V2.26 staged CAS base mismatch", output_dir=out, evidence=staged)

    saved = save_runtime_checkpoint(
        staged["runtime_checkpoint_candidate"],
        approved=True,
        expected_sha=prior_sha,
        allow_global_arming_transition=False,
    )
    write_json(out / "v226_save_result.json", saved)
    if saved.get("status") != "CONFIRMED" or saved.get("saved") is not True or saved.get("verified") is not True:
        return blocked("V2.26 write not positively confirmed; reconcile manually and never retry automatically", output_dir=out, evidence=saved)

    decision_receipt = saved.get("write_receipt")
    if not isinstance(decision_receipt, dict):
        return blocked("V2.26 confirmed write missing receipt", output_dir=out, evidence=saved)

    attested = verify_owner_decision_record_persistence(
        decision_request=request,
        decision_signature_b64=decision_signature,
        decision_nonce_registry=registry,
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        v223_runtime_result=v223_runtime,
        v223_write_receipt=v223_receipt,
        decision_runtime_result=saved,
        decision_write_receipt=decision_receipt,
        now_ts=now_iso(),
    )
    write_json(out / "v226_attestation.json", attested)
    if attested.get("state") not in {
        "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE",
        "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_DENY",
    }:
        return blocked("V2.26 attestation blocked; do not proceed to Core Freeze", output_dir=out, evidence=attested)

    summary = {
        "schema": "AION_CORE_V1_REAL_V226_RESULT_V1",
        "state": attested["state"],
        "owner_decision": attested["owner_decision"],
        "owner_decision_recorded": attested["owner_decision_recorded"],
        "decision_record_persisted": attested["decision_record_persisted"],
        "persistence_attested": attested["persistence_attested"],
        "core_freeze_ceremony_eligible": attested["core_freeze_ceremony_eligible"],
        "digest_to_core_freeze_ceremony": attested.get("digest_to_core_freeze_ceremony", ""),
        "core_freeze_execution_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "automatic_retry": False,
    }
    write_json(out / "v226_success_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
