"""A190 G36 — subprocess SQLite custody *simulation*, LAB ONLY.

The witness has its own process, SQLite file and Ed25519 key. However those
files remain on the SAME HOST and are controlled by the LAB caller. The host
can replace keys and database or submit a dishonest snapshot. This is NOT an
independent operator, trust root, antirollback store or first-send witness.

No network, provider, Worker, customer data or production integration.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from g20_independent_witness_recovery_contract_lab import Admission, RecoveryDenied

ROOT = "AION-G36-SYNTHETIC-SUBPROCESS-NOT-TRUSTED"
DOMAIN = "AION-A190-G36-SYNTHETIC-LEDGER-TIP-V1"


def outbox_snapshot_digest(outbox: Any) -> str:
    """Local *diagnostic* snapshot; not atomic vs concurrent writers."""
    rows = sorted(outbox.list(), key=lambda row: row["idempotency_key"])
    text = json.dumps(rows, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _statement(sequence: int, snapshot_digest: str, chain_head: str,
               nonce_hex: str) -> bytes:
    return json.dumps({
        "domain": DOMAIN, "root_id": ROOT, "sequence": sequence,
        "snapshot_digest": snapshot_digest, "chain_head": chain_head,
        "nonce": nonce_hex,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _chain(sequence: int, digest: str, previous: str) -> str:
    data = json.dumps([DOMAIN, sequence, digest, previous],
                      separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _digest_ok(raw: Any) -> bool:
    return (isinstance(raw, str) and len(raw) == 64 and
            all(c in "0123456789abcdef" for c in raw))


def _open_witness(location: Path):
    keypath, dbpath = location / "signing-key.raw", location / "custody.sqlite3"
    if not keypath.exists() or not dbpath.exists():
        raise RuntimeError("G36_WITNESS_NOT_INITIALIZED")
    keyraw = keypath.read_bytes()
    if len(keyraw) != 32:
        raise RuntimeError("G36_INVALID_PRIVATE_KEY")
    signer = Ed25519PrivateKey.from_private_bytes(keyraw)
    db = sqlite3.connect(dbpath, isolation_level=None, timeout=5)
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA synchronous=FULL")
    return db, signer


def witness_command(location: Path, command: str,
                    payload: dict[str, Any]) -> dict[str, Any]:
    """Called exclusively from a subprocess for the G36 harness."""
    location = Path(location)
    keypath, dbpath = location / "signing-key.raw", location / "custody.sqlite3"
    if command == "init":
        location.mkdir(parents=True, exist_ok=True)
        if keypath.exists() != dbpath.exists():
            raise RuntimeError("G36_PARTIALLY_INITIALIZED_DENIED")
        if not keypath.exists():
            signer = Ed25519PrivateKey.generate()
            keypath.write_bytes(signer.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            ))
            try:
                keypath.chmod(0o600)
            except OSError:
                pass
            db = sqlite3.connect(dbpath)
            try:
                db.execute("PRAGMA journal_mode=DELETE")
                db.execute("PRAGMA synchronous=FULL")
                db.execute(
                    "CREATE TABLE witness_log("
                    "seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "snapshot_digest TEXT NOT NULL,"
                    "previous_head TEXT NOT NULL,"
                    "chain_head TEXT NOT NULL)"
                )
                db.commit()
            finally:
                db.close()
        db, signer = _open_witness(location)
        try:
            pub = signer.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            ).hex()
            return {"root_id": ROOT, "public_key": pub}
        finally:
            db.close()

    db, signer = _open_witness(location)
    try:
        if command == "observe":
            digest = payload.get("snapshot_digest")
            if not _digest_ok(digest):
                raise RuntimeError("G36_INVALID_SNAPSHOT_DIGEST")
            db.execute("BEGIN IMMEDIATE")
            try:
                old = db.execute(
                    "SELECT seq,snapshot_digest,chain_head FROM witness_log "
                    "ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                if old and old[1] == digest:
                    db.execute("COMMIT")
                    return {"sequence": old[0], "snapshot_digest": digest,
                            "chain_head": old[2], "idempotent": True}
                sequence = old[0] + 1 if old else 1
                previous = old[2] if old else "0" * 64
                head = _chain(sequence, digest, previous)
                db.execute(
                    "INSERT INTO witness_log"
                    "(seq,snapshot_digest,previous_head,chain_head)"
                    "VALUES (?,?,?,?)", (sequence, digest, previous, head),
                )
                db.execute("COMMIT")
                return {"sequence": sequence, "snapshot_digest": digest,
                        "chain_head": head, "idempotent": False}
            except Exception:
                db.execute("ROLLBACK")
                raise
        if command == "attest":
            nonce = payload.get("nonce")
            if (not isinstance(nonce, str) or len(nonce) != 64 or
                    any(c not in "0123456789abcdef" for c in nonce)):
                raise RuntimeError("G36_INVALID_CHALLENGE")
            row = db.execute(
                "SELECT seq,snapshot_digest,previous_head,chain_head "
                "FROM witness_log ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            if row is None:
                raise RuntimeError("G36_WITNESS_NO_OBSERVATION")
            seq, digest, previous, head = row
            if head != _chain(seq, digest, previous):
                raise RuntimeError("G36_WITNESS_LATEST_ROW_TAMPER_DETECTED")
            proof = {
                "domain": DOMAIN, "root_id": ROOT, "sequence": seq,
                "snapshot_digest": digest, "chain_head": head,
                "nonce": nonce,
                "signature": signer.sign(
                    _statement(seq, digest, head, nonce)
                ).hex(),
            }
            return proof
        raise RuntimeError("G36_UNKNOWN_COMMAND")
    finally:
        db.close()


def call_witness(location: Path, command: str,
                 payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Spawn a new witness process; nothing here establishes host independence."""
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()),
         str(location), command, json.dumps(payload or {})],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if proc.returncode != 0:
        raise RecoveryDenied("G36_WITNESS_PROCESS_DENIED:" +
                             proc.stderr.strip()[-350:])
    try:
        return json.loads(proc.stdout)
    except (TypeError, ValueError) as exc:
        raise RecoveryDenied("G36_WITNESS_RESPONSE_MALFORMED") from exc


def inspect_outbox_against_subprocess_witness(
    *, outbox: Any, response: Any,
    challenge: bytes, pinned_root_id: str,
    pinned_public_key: bytes,
) -> Admission:
    """Never authorize first SEND, RETRY or externally claimed zero effect."""
    if not isinstance(response, dict):
        raise RecoveryDenied("G36_WITNESS_MISSING")
    if response.get("domain") != DOMAIN or response.get("root_id") != pinned_root_id:
        raise RecoveryDenied("G36_ROOT_UNTRUSTED")
    if pinned_root_id != ROOT or len(pinned_public_key) != 32:
        raise RecoveryDenied("G36_PIN_MISSING_OR_WRONG")
    if (not isinstance(challenge, bytes) or len(challenge) != 32 or
            response.get("nonce") != challenge.hex()):
        raise RecoveryDenied("G36_CHALLENGE_MISMATCH")
    sequence = response.get("sequence")
    digest = response.get("snapshot_digest")
    head = response.get("chain_head")
    if (type(sequence) is not int or sequence < 1 or
            not _digest_ok(digest) or not _digest_ok(head)):
        raise RecoveryDenied("G36_INVALID_WITNESS_HEAD")
    try:
        signature = bytes.fromhex(response["signature"])
        Ed25519PublicKey.from_public_bytes(pinned_public_key).verify(
            signature, _statement(sequence, digest, head, challenge.hex()),
        )
    except (InvalidSignature, ValueError, TypeError, KeyError) as exc:
        raise RecoveryDenied("G36_INVALID_PINNED_SIGNATURE") from exc
    try:
        actual = outbox_snapshot_digest(outbox)
    except Exception as exc:
        raise RecoveryDenied("G36_LOCAL_OUTBOX_READ_UNAVAILABLE") from exc
    if actual != digest:
        raise RecoveryDenied("G36_LOCAL_SNAPSHOT_BEHIND_OR_DIVERGENT")
    return Admission.UNCERTAIN


if __name__ == "__main__":
    try:
        location = Path(sys.argv[1])
        command = sys.argv[2]
        payload = json.loads(sys.argv[3])
        print(json.dumps(witness_command(location, command, payload),
                         separators=(",", ":")))
    except Exception as exc:
        print(type(exc).__name__ + ":" + str(exc), file=sys.stderr)
        sys.exit(2)
