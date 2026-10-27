"""G138 strictly synthetic separate-process signature issuer.

THIS IS AN ATTACKER-CONTROLLED FIXTURE, NEVER A TRUSTED CUSTODIAN.
The calling tests own and can replace the private seed, payload JSON, root
and local replay floor. No durable reservation, independent principal,
provider endpoint, network, Worker, operational authority or SEND.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from aion_chat.signed_receipt_lab import canonical_bytes
from labs.a190.g138_signed_custody_wire_lab import DOMAIN


def sign_fixture_lab(raw_private_seed: bytes, payload: dict) -> dict:
    if type(raw_private_seed) is not bytes or len(raw_private_seed) != 32:
        raise ValueError("G138_EXACT_SYNTHETIC_ED25519_SEED_REQUIRED")
    if type(payload) is not dict:
        raise ValueError("G138_SYNTHETIC_PAYLOAD_MUST_BE_DICT")
    signature = Ed25519PrivateKey.from_private_bytes(raw_private_seed).sign(
        DOMAIN + canonical_bytes(payload)
    )
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("G138_SYNTHETIC_SIGNER_NEEDS_SEED_AND_PAYLOAD_FILE")
    # Test-only file read; seed is discarded when temporary test directory
    # closes. A real independent custodian must NEVER accept caller-owned seed.
    seed = Path(argv[1]).read_bytes()
    payload = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(sign_fixture_lab(seed, payload),
                     ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
