"""A190 G37: authority-signed semantic reservation, synthetic custody LAB.

Witness accepts AUTHORITY SIGNED permits, never caller supplied snapshot digest.
Issuer public key and custody signer are separate, but both are test-controlled
on the same host. This is NOT an external root, honest issuer, tamperproof
monotonic store, production reservation, or provider integration.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
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

DOMAIN = "AION-G37-AUTHORITY-SEMANTIC-PERMIT-LAB-V1"
TIP_DOMAIN = "AION-G37-LATEST-CUSTODY-TIP-LAB-V1"
ROOT = "AION-G37-SYNTHETIC-CUSTODIAN"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FIELDS = frozenset({"domain", "event_id", "scope", "action", "aggregate_key",
                    "amount_minor", "currency", "expires_unix"})


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def valid_permit(permit: Any, *, now: int) -> bool:
    if not isinstance(permit, dict) or set(permit) != FIELDS:
        return False
    if permit["domain"] != DOMAIN:
        return False
    if any(not isinstance(permit[k], str) or not _TOKEN.fullmatch(permit[k])
           for k in ("event_id", "action", "aggregate_key")):
        return False
    if not isinstance(permit["scope"], list) or len(permit["scope"]) != 3:
        return False
    if any(not isinstance(v, str) or not _TOKEN.fullmatch(v) for v in permit["scope"]):
        return False
    if type(permit["amount_minor"]) is not int or permit["amount_minor"] < 1:
        return False
    if permit["currency"] != "BRL":
        return False
    if type(permit["expires_unix"]) is not int:
        return False
    if not now < permit["expires_unix"] <= now + 3600:
        return False
    return True


def event_key(permit: dict) -> str:
    return sha256(canonical([permit["scope"], permit["event_id"]])).hexdigest()


def permit_digest(permit: dict) -> str:
    return sha256(canonical(permit)).hexdigest()


def signing_bytes(permit: dict) -> bytes:
    return DOMAIN.encode("utf-8") + b"\x00" + canonical(permit)


def issue_for_lab(signer: Ed25519PrivateKey, permit: dict) -> dict:
    return {"permit": permit, "issuer_signature": signer.sign(signing_bytes(permit)).hex()}


def tip_bytes(proof: dict) -> bytes:
    keys = ("domain", "root_id", "event_key", "permit_digest",
            "event_sequence", "global_sequence", "global_head", "nonce")
    return canonical({key: proof[key] for key in keys})


def _load(location: Path):
    key_bytes = (location / "custody-key.raw").read_bytes()
    pin = (location / "authority-pin.raw").read_bytes()
    if len(key_bytes) != 32 or len(pin) != 32:
        raise RuntimeError("G37_INVALID_PROVISIONING")
    db = sqlite3.connect(location / "witness.sqlite3", isolation_level=None, timeout=5)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA busy_timeout=5000")
    return db, Ed25519PrivateKey.from_private_bytes(key_bytes), pin


def witness_command(location: Path, command: str, payload: dict) -> dict:
    location = Path(location)
    if command == "init":
        pin_hex = payload.get("authority_pin")
        if not isinstance(pin_hex, str):
            raise RuntimeError("G37_AUTHORITY_PIN_REQUIRED")
        pin = bytes.fromhex(pin_hex)
        if len(pin) != 32:
            raise RuntimeError("G37_AUTHORITY_PIN_INVALID")
        location.mkdir(parents=True, exist_ok=True)
        keypath = location / "custody-key.raw"
        pinpath = location / "authority-pin.raw"
        dbpath = location / "witness.sqlite3"
        exists = [p.exists() for p in (keypath, pinpath, dbpath)]
        if any(exists) and not all(exists):
            raise RuntimeError("G37_PARTIAL_CUSTODY_DENIED")
        if not any(exists):
            signer = Ed25519PrivateKey.generate()
            keypath.write_bytes(signer.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                serialization.NoEncryption()))
            pinpath.write_bytes(pin)
            for p in (keypath, pinpath):
                try:
                    p.chmod(0o600)
                except OSError:
                    pass
            db = sqlite3.connect(dbpath)
            try:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("CREATE TABLE reservations("
                           "sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
                           "event_key TEXT NOT NULL UNIQUE,"
                           "permit_digest TEXT NOT NULL,"
                           "prev_head TEXT NOT NULL,"
                           "head TEXT NOT NULL)")
                db.commit()
            finally:
                db.close()
        db, signer, fixed_pin = _load(location)
        try:
            if fixed_pin != pin:
                raise RuntimeError("G37_AUTHORITY_PIN_ROTATION_DENIED")
            return {"root_id": ROOT, "custody_public_key": signer.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()}
        finally:
            db.close()

    db, signer, pin = _load(location)
    try:
        if command == "reserve":
            certified = payload.get("certified")
            if not isinstance(certified, dict) or set(certified) != {"permit", "issuer_signature"}:
                raise RuntimeError("G37_CERTIFIED_PERMIT_REQUIRED_NO_RAW_DIGEST")
            permit = certified["permit"]
            now = int(datetime.now(timezone.utc).timestamp())
            if not valid_permit(permit, now=now):
                raise RuntimeError("G37_PERMIT_INVALID_OR_EXPIRED")
            try:
                Ed25519PublicKey.from_public_bytes(pin).verify(
                    bytes.fromhex(certified["issuer_signature"]), signing_bytes(permit))
            except (InvalidSignature, ValueError, TypeError) as exc:
                raise RuntimeError("G37_ISSUER_SIGNATURE_INVALID") from exc
            ekey, digest = event_key(permit), permit_digest(permit)
            db.execute("BEGIN IMMEDIATE")
            try:
                old = db.execute(
                    "SELECT sequence,permit_digest,head FROM reservations WHERE event_key=?",
                    (ekey,)).fetchone()
                if old:
                    if old[1] != digest:
                        raise RuntimeError("G37_SEMANTIC_EVENT_CONFLICT")
                    db.execute("COMMIT")
                    return {"event_key": ekey, "event_sequence": old[0],
                            "permit_digest": digest, "idempotent": True}
                last = db.execute(
                    "SELECT sequence,head FROM reservations ORDER BY sequence DESC LIMIT 1"
                ).fetchone()
                seq = last[0] + 1 if last else 1
                prev = last[1] if last else "0" * 64
                head = sha256(canonical([TIP_DOMAIN, seq, ekey, digest, prev])).hexdigest()
                db.execute(
                    "INSERT INTO reservations(event_key,permit_digest,prev_head,head)"
                    "VALUES(?,?,?,?)", (ekey, digest, prev, head))
                db.execute("COMMIT")
                return {"event_key": ekey, "event_sequence": seq,
                        "permit_digest": digest, "idempotent": False}
            except Exception:
                db.execute("ROLLBACK")
                raise
        if command == "attest":
            nonce = payload.get("nonce")
            ekey = payload.get("event_key")
            if (not isinstance(nonce, str) or not re.fullmatch("[0-9a-f]{64}", nonce)
                    or not isinstance(ekey, str) or not re.fullmatch("[0-9a-f]{64}", ekey)):
                raise RuntimeError("G37_CHALLENGE_OR_EVENT_INVALID")
            event = db.execute(
                "SELECT sequence,permit_digest FROM reservations WHERE event_key=?",
                (ekey,)).fetchone()
            latest = db.execute(
                "SELECT sequence,head FROM reservations ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            if not event or not latest:
                raise RuntimeError("G37_RESERVATION_ABSENT")
            # Latest-row hash consistency is not append-only antirollback.
            current = db.execute(
                "SELECT event_key,permit_digest,prev_head FROM reservations "
                "WHERE sequence=?", (latest[0],)).fetchone()
            if sha256(canonical([TIP_DOMAIN,latest[0],current[0],current[1],
                                 current[2]])).hexdigest() != latest[1]:
                raise RuntimeError("G37_CURRENT_HEAD_TAMPER")
            proof = {"domain": TIP_DOMAIN, "root_id": ROOT, "event_key": ekey,
                     "permit_digest": event[1], "event_sequence": event[0],
                     "global_sequence": latest[0], "global_head": latest[1],
                     "nonce": nonce}
            proof["custody_signature"] = signer.sign(tip_bytes(proof)).hex()
            return proof
        raise RuntimeError("G37_UNKNOWN_COMMAND")
    finally:
        db.close()


def subprocess_witness(location: Path, command: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()),
         str(location), command, json.dumps(payload, separators=(",", ":"))],
        capture_output=True, text=True, timeout=20, check=False)
    if proc.returncode:
        raise RecoveryDenied("G37_CUSTODY_DENIED:" + proc.stderr.strip()[-300:])
    try:
        return json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise RecoveryDenied("G37_RESPONSE_MALFORMED") from exc


if __name__ == "__main__":
    try:
        print(json.dumps(witness_command(
            Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])),
            separators=(",", ":")))
    except Exception as err:
        print(type(err).__name__ + ":" + str(err), file=sys.stderr)
        sys.exit(2)
