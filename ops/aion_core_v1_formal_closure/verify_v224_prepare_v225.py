#!/usr/bin/env python3
"""Verify V2.24, durably claim its nonce, and prepare (not sign) V2.25."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_decision_record import (
    DECISIONS,
    build_owner_decision_request,
    canonical_owner_decision_bytes,
)
from atlasquant_aion_owner_signature_ceremony import verify_owner_signature
from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_signature(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit("signature file is empty")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def ensure_registry_outside_repo(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo_root = Path.cwd().resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return resolved
    raise SystemExit("nonce registry must be outside the repository working tree")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v224-request", type=Path, required=True)
    parser.add_argument("--v224-signature-file", type=Path, required=True)
    parser.add_argument("--owner-trust-root", type=Path, required=True)
    parser.add_argument("--nonce-registry", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--certification-trust-root", type=Path, required=True)
    parser.add_argument("--checkpoint-master", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--v223-runtime-result", type=Path, required=True)
    parser.add_argument("--now-ts", required=True)
    parser.add_argument("--decision", choices=DECISIONS, required=True)
    parser.add_argument("--decision-ceremony-id", required=True)
    parser.add_argument("--decision-nonce", required=True)
    parser.add_argument("--decision-issued-at", required=True)
    parser.add_argument("--decision-expires-at", required=True)
    parser.add_argument("--decision-key-id", required=True)
    parser.add_argument("--decision-key-version", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    v224_request = read_json(args.v224_request)
    v224_signature = read_signature(args.v224_signature_file)
    owner_roots = TrustRootRegistry.from_mapping(read_json(args.owner_trust_root))
    cert_roots = TrustRootRegistry.from_mapping(read_json(args.certification_trust_root))
    manifest = read_json(args.manifest)
    master = read_json(args.checkpoint_master)
    preflight = read_json(args.preflight)
    runtime = read_json(args.v223_runtime_result)
    receipt = runtime.get("write_receipt")
    if not isinstance(receipt, dict):
        raise SystemExit("V2.23 write receipt missing")

    # Build V2.25 fully before consuming the V2.24 nonce. This re-verifies the
    # V2.24 signature and all state bindings without mutating the nonce registry.
    decision_prebuild = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        runtime_result=runtime,
        write_receipt=receipt,
        now_ts=args.now_ts,
        decision=args.decision,
        ceremony_id=args.decision_ceremony_id,
        nonce=args.decision_nonce,
        issued_at=args.decision_issued_at,
        expires_at=args.decision_expires_at,
        key_id=args.decision_key_id,
        key_version=args.decision_key_version,
    )
    if decision_prebuild.get("state") != "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE":
        raise SystemExit("V2.25 prebuild blocked: " + ",".join(decision_prebuild.get("blockers") or []))

    registry_path = ensure_registry_outside_repo(args.nonce_registry)
    registry = PersistentNonceRegistry(registry_path)
    v224_verified = verify_owner_signature(
        v224_request,
        signature_b64=v224_signature,
        owner_trust_roots=owner_roots,
        nonce_registry=registry,
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=cert_roots,
        expected_target_commit_sha=TARGET,
        runtime_result=runtime,
        write_receipt=receipt,
        now_ts=args.now_ts,
    )
    if v224_verified.get("state") != "READY_FOR_EXPLICIT_OWNER_DECISION":
        raise SystemExit("V2.24 verification blocked: " + ",".join(v224_verified.get("blockers") or []))

    request = decision_prebuild["request"]
    message = canonical_owner_decision_bytes(request)
    bundle = {
        "schema": "AION_CORE_V1_V225_EXTERNAL_DECISION_SIGNING_BUNDLE_V1",
        "state": "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE",
        "decision": args.decision,
        "request": request,
        "request_digest": decision_prebuild["request_digest"],
        "canonical_message_b64url": b64url(message),
        "canonical_message_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
        "v224_nonce_registered": True,
        "decision_nonce_consumed": False,
        "private_key_loaded": False,
        "decision_signature_performed": False,
        "core_freeze_ceremony_eligible": False,
        "core_frozen": False,
        "network_called": False,
        "executes_action": False,
    }
    out = args.output_dir
    write_json(out / "v224_verification.json", v224_verified)
    write_json(out / "v225_decision_request.json", request)
    write_json(out / "v225_decision_signing_bundle.json", bundle)
    print(json.dumps({
        "state": bundle["state"],
        "decision": args.decision,
        "request_digest": bundle["request_digest"],
        "v224_nonce_registered": True,
        "decision_nonce_consumed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
