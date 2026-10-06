#!/usr/bin/env python3
"""Prepare the V2.24 HUMAN_OWNER signature request without signing or consuming nonce."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_owner_signature_ceremony import (
    build_owner_signature_request,
    canonical_owner_signature_bytes,
)
from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--certification-trust-root", type=Path, required=True)
    parser.add_argument("--checkpoint-master", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--v223-runtime-result", type=Path, required=True)
    parser.add_argument("--owner-trust-root", type=Path, required=True)
    parser.add_argument("--now-ts", required=True)
    parser.add_argument("--ceremony-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--issued-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--key-version", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    runtime_result = read_json(args.v223_runtime_result)
    receipt = runtime_result.get("write_receipt")
    if not isinstance(receipt, dict):
        raise SystemExit("V2.23 runtime result has no write receipt")

    result = build_owner_signature_request(
        checkpoint_master=read_json(args.checkpoint_master),
        preflight=read_json(args.preflight),
        certification_manifest=read_json(args.manifest),
        certification_trust_roots=TrustRootRegistry.from_mapping(read_json(args.certification_trust_root)),
        expected_target_commit_sha=TARGET,
        runtime_result=runtime_result,
        write_receipt=receipt,
        owner_trust_roots=TrustRootRegistry.from_mapping(read_json(args.owner_trust_root)),
        now_ts=args.now_ts,
        ceremony_id=args.ceremony_id,
        nonce=args.nonce,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
        key_id=args.key_id,
        key_version=args.key_version,
    )
    if result.get("state") != "READY_FOR_EXTERNAL_OWNER_SIGNATURE":
        raise SystemExit("V2.24 blocked: " + ",".join(result.get("blockers") or []))

    request = result["request"]
    message = canonical_owner_signature_bytes(request)
    bundle = {
        "schema": "AION_CORE_V1_V224_EXTERNAL_SIGNING_BUNDLE_V1",
        "state": "READY_FOR_EXTERNAL_OWNER_SIGNATURE",
        "request": request,
        "request_digest": result["request_digest"],
        "canonical_message_b64url": b64url(message),
        "canonical_message_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
        "private_key_loaded": False,
        "signature_performed": False,
        "nonce_consumed": False,
        "owner_decision": "UNDECIDED",
        "core_frozen": False,
        "network_called": False,
        "executes_action": False,
    }
    out = args.output_dir
    write_json(out / "v224_request.json", request)
    write_json(out / "v224_signing_bundle.json", bundle)
    print(json.dumps({
        "state": bundle["state"],
        "request_digest": bundle["request_digest"],
        "nonce_consumed": False,
        "signature_performed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
