#!/usr/bin/env python3
"""Apply externally produced Ed25519 signatures to the V2.20 signing bundle."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def decode_sig(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature missing")
    padded = value + "=" * ((4 - len(value) % 4) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    if len(raw) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--signatures", type=Path, required=True,
                        help="JSON object mapping dimension -> base64url Ed25519 signature")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bundle = read_json(args.bundle)
    signatures = read_json(args.signatures)
    if bundle.get("schema") != "AION_CORE_V1_V220_EXTERNAL_SIGNING_BUNDLE_V1":
        raise SystemExit("signing bundle schema invalid")
    if bundle.get("state") != "READY_FOR_EXTERNAL_SIGNATURE":
        raise SystemExit("signing bundle is not ready")
    if not isinstance(signatures, dict):
        raise SystemExit("signature map must be a JSON object")

    evidence = {}
    missing = []
    unexpected = sorted(set(signatures) - {entry["dimension"] for entry in bundle.get("entries", [])})
    if unexpected:
        raise SystemExit("unexpected signature dimensions: " + ",".join(unexpected))

    for entry in bundle.get("entries", []):
        dimension = entry["dimension"]
        signature = signatures.get(dimension)
        if not signature:
            missing.append(dimension)
            continue
        decode_sig(signature)
        row = dict(entry["row_to_sign"])
        row["signature_b64"] = signature
        evidence[dimension] = row

    if missing:
        raise SystemExit("missing signatures: " + ",".join(missing))

    result = {
        "schema": "AION_CORE_V1_V220_SIGNED_EVIDENCE_PACKET_V1",
        "state": "SIGNED_EVIDENCE_PENDING_CRYPTOGRAPHIC_VERIFICATION",
        "formal_target_commit_sha": bundle["formal_target_commit_sha"],
        "unsigned_packet_digest": bundle["unsigned_packet_digest"],
        "key_id": bundle["key_id"],
        "key_version": bundle["key_version"],
        "issued_at": bundle["issued_at"],
        "expires_at": bundle["expires_at"],
        "evidence": evidence,
        "private_key_loaded": False,
        "signature_performed_by_this_tool": False,
        "network_called": False,
        "executes_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": result["state"],
        "evidence_count": len(evidence),
        "output": str(args.output),
        "private_key_loaded": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
