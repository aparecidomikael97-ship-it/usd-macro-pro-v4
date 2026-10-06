#!/usr/bin/env python3
"""Prepare Core Freeze signing material from a positive V2.26 attestation.

No nonce is consumed and no runtime write occurs.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_trust_root import TrustRootRegistry
from ops.aion_core_v1_formal_closure.core_freeze_ceremony import (
    build_freeze_request,
    canonical,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v226-attestation", type=Path, required=True)
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

    v226 = read_json(args.v226_attestation)
    roots = TrustRootRegistry.from_mapping(read_json(args.owner_trust_root))
    result = build_freeze_request(
        v226,
        owner_trust_roots=roots,
        now_ts=args.now_ts,
        ceremony_id=args.ceremony_id,
        nonce=args.nonce,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
        key_id=args.key_id,
        key_version=args.key_version,
    )
    if result.get("state") != "READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE":
        raise SystemExit("Core Freeze request blocked: " + ",".join(result.get("blockers") or []))

    request = result["request"]
    message = canonical(request)
    bundle = {
        "schema": "AION_CORE_V1_CORE_FREEZE_EXTERNAL_SIGNING_BUNDLE_V1",
        "state": "READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE",
        "request": request,
        "request_digest": result["request_digest"],
        "canonical_message_b64url": b64url(message),
        "canonical_message_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
        "private_key_loaded": False,
        "signature_performed": False,
        "nonce_consumed": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "network_called": False,
        "executes_action": False,
    }
    out = args.output_dir
    write_json(out / "core_freeze_request.json", request)
    write_json(out / "core_freeze_signing_bundle.json", bundle)
    print(json.dumps({
        "state": bundle["state"],
        "request_digest": bundle["request_digest"],
        "nonce_consumed": False,
        "signature_performed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
