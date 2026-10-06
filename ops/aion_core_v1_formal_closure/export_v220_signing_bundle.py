#!/usr/bin/env python3
"""Export canonical V2.20 signing messages. Does not load or use a private key."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from atlasquant_aion_core_certification import canonical_evidence_attestation_bytes
from ops.aion_core_v1_formal_closure.validate_unsigned_v220_packet import validate_packet

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--key-version", type=int, required=True)
    parser.add_argument("--issued-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    packet = read_json(args.packet)
    validation = validate_packet(packet)
    if validation["state"] != "VALID_UNSIGNED_PACKET":
        raise SystemExit("unsigned packet validation failed: " + ",".join(validation["blockers"]))
    if args.key_version < 1:
        raise SystemExit("key-version must be >= 1")

    entries = []
    for item in packet["rows"]:
        dimension = item["dimension"]
        row = deepcopy(item["claim"])
        row.update({
            "key_id": args.key_id,
            "key_version": args.key_version,
            "issued_at": args.issued_at,
            "expires_at": args.expires_at,
            "signature_b64": "",
        })
        message = canonical_evidence_attestation_bytes(dimension, row)
        entries.append({
            "dimension": dimension,
            "row_to_sign": row,
            "canonical_message_b64url": b64url(message),
            "canonical_message_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
        })

    bundle = {
        "schema": "AION_CORE_V1_V220_EXTERNAL_SIGNING_BUNDLE_V1",
        "state": "READY_FOR_EXTERNAL_SIGNATURE",
        "formal_target_commit_sha": TARGET,
        "unsigned_packet_digest": packet["unsigned_packet_digest"],
        "key_id": args.key_id,
        "key_version": args.key_version,
        "issued_at": args.issued_at,
        "expires_at": args.expires_at,
        "entries": entries,
        "private_key_loaded": False,
        "signature_performed": False,
        "network_called": False,
        "executes_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": bundle["state"],
        "entry_count": len(entries),
        "output": str(args.output),
        "private_key_loaded": False,
        "signature_performed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
