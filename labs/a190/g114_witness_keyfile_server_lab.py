"""G114 LAB signer-side keyfile subprocess, NOT external protected custody.

The test signer seed is stored on the SAME host. The client-side protocol
must receive a pinned public key only, never the signing seed. The subprocess
reads a synthetic test key from a witness-side fixture file; the host owner
can still read/replace both file and database. Do not use real credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from labs.a190.g113_subprocess_witness_lab import (
    SyntheticWitnessUnavailable, execute,
)


def _load_test_signer(key_path):
    path = Path(key_path)
    # Refuse missing/symlinked keys; never generate a signer on recovery.
    if path.is_symlink() or not path.is_file():
        raise SyntheticWitnessUnavailable("G114_SIGNER_FILE_UNAVAILABLE")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise SyntheticWitnessUnavailable("G114_SIGNER_NOT_REGULAR")
    if os.name != "nt" and info.st_mode & 0o077:
        raise SyntheticWitnessUnavailable("G114_SIGNER_WORLD_OR_GROUP_READABLE")
    # This is a keyfile controlled by the test runner, not a KMS or HSM.
    with path.open("rb") as file:
        seed = file.read(33)
    if len(seed) != 32:
        raise SyntheticWitnessUnavailable("G114_SIGNER_KEY_MALFORMED")
    return Ed25519PrivateKey.from_private_bytes(seed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("bootstrap", "enroll", "reserve", "status"))
    parser.add_argument("--db", required=True)
    parser.add_argument("--synthetic-key-file", required=True)
    args = parser.parse_args()
    try:
        signer = _load_test_signer(args.synthetic_key_file)
        raw = sys.stdin.buffer.readline(8193)
        if not raw or len(raw) > 8192:
            raise SyntheticWitnessUnavailable("G114_BODY_SIZE_DENIED")
        message = json.loads(raw)
        response = execute(Path(args.db), signer, args.action, message)
        sys.stdout.write(json.dumps(
            response, separators=(",", ":"), sort_keys=True, allow_nan=False,
        ) + "\n")
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError,
            SyntheticWitnessUnavailable):
        # Never print private signing material, exception args or keyfile
        # contents to stdout/stderr. Nonzero exit means no authorization.
        print("G114_SYNTHETIC_WITNESS_DENIED", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
