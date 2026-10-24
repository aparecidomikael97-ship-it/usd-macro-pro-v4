"""A190 G9 LAB: synthetic third-party provider, NEVER a real effect or provider.

Adds a distinct TCP PROCESS, vendor Ed25519 pin and SQLite idempotency ledger
to G8's signed original + reservation. Models uncertain first send and signed
read-only reconciliation; does NOT prove vendor control, independent root,
HUMAN_OWNER authorization or external effect. Same-host admin rollback is RED.
"""
from __future__ import annotations

import base64
from contextlib import closing
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
import socketserver
import sqlite3
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from g8_independent_authority_protocol_lab import (
    MAX_WIRE, canonical, check_seal, private_raw, pub_bytes, rpc, seal,
    verify_receipt,
)

VENDOR_DOMAIN = b"A190:G9:SYNTHETIC_VENDOR_NEVER_REAL\0"
VENDOR_FIELDS = frozenset({
    "schema", "issuer", "tenant", "semantic_digest", "reservation_sha256",
    "seq", "vendor_epoch", "vendor_request_id", "simulated_transaction_id",
    "status", "issued_at", "expires",
})
SYNTHETIC_STATUS = "SIMULATED_RECORD_NOT_EXTERNAL_EFFECT"


def reservation_hash(envelope):
    return sha256(canonical(envelope)).hexdigest()


def verify_vendor_receipt(envelope, pinned_vendor_pub, expected_reservation,
                          *, now=None, epoch=1):
    if not verify_receipt(expected_reservation, pinned_vendor_pub):
        # Note: authority vs vendor keys differ; validated separately below.
        pass
    payload = check_seal(
        envelope, pinned_vendor_pub, VENDOR_DOMAIN, VENDOR_FIELDS,
    )
    stamp = int(time.time()) if now is None else now
    if payload is None or not isinstance(expected_reservation, dict):
        return False
    reserved = expected_reservation.get("payload")
    if not isinstance(reserved, dict):
        return False
    if (payload["schema"] != "A190_G9_VENDOR_LAB_V1"
            or payload["issuer"] != "SYNTHETIC_VENDOR_NOT_REAL"
            or payload["status"] != SYNTHETIC_STATUS
            or payload["tenant"] != reserved.get("tenant")
            or payload["semantic_digest"] != reserved.get("semantic_digest")
            or payload["reservation_sha256"] != reservation_hash(
                expected_reservation
            )
            or type(payload["seq"]) is not int or payload["seq"] <= 0
            or type(payload["vendor_epoch"]) is not int
            or payload["vendor_epoch"] != epoch
            or type(payload["issued_at"]) is not int
            or type(payload["expires"]) is not int
            or not payload["issued_at"] <= stamp < payload["expires"]
            or payload["expires"] - payload["issued_at"] > 300
            or not isinstance(payload["vendor_request_id"], str)
            or not isinstance(payload["simulated_transaction_id"], str)):
        return False
    return True


class SyntheticVendor:
    """Ephemeral same-host vendor simulator, not a trustworthy third party."""
    def __init__(self, state_dir, pinned_authority_pub):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = self.dir / "fake-vendor-ledger.sqlite"
        self.key = self.dir / "fake-vendor-private.raw"
        self.authority_pin = bytes.fromhex(pinned_authority_pub)
        if not self.key.exists():
            with self.key.open("xb") as output:
                output.write(private_raw(Ed25519PrivateKey.generate()))
                output.flush()
                os.fsync(output.fileno())
        self.signer = Ed25519PrivateKey.from_private_bytes(
            self.key.read_bytes()
        )
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS synthetic_effects("
                "seq INTEGER PRIMARY KEY,"
                "tenant TEXT NOT NULL,"
                "semantic_digest TEXT NOT NULL,"
                "vendor_request_id TEXT NOT NULL UNIQUE,"
                "receipt_json TEXT NOT NULL,"
                "UNIQUE(tenant,semantic_digest))"
            )
            db.commit()

    def pub_hex(self):
        return pub_bytes(self.signer).hex()

    def submit(self, reservation, request_id):
        if not verify_receipt(reservation, self.authority_pin):
            return {"status": "DENY_UNVERIFIED_RESERVATION"}
        claimed = reservation["payload"]
        if (not isinstance(request_id, str)
                or not 1 <= len(request_id) <= 48
                or not all(c.isascii() and (c.isalnum() or c in "-_")
                           for c in request_id)):
            return {"status": "DENY_VENDOR_REQUEST"}
        with closing(sqlite3.connect(self.db, timeout=5)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            found = db.execute(
                "SELECT 1 FROM synthetic_effects WHERE "
                "(tenant=? AND semantic_digest=?) OR vendor_request_id=?",
                (claimed["tenant"], claimed["semantic_digest"], request_id),
            ).fetchone()
            if found:
                db.rollback()
                return {"status": "DENY_VENDOR_DUPLICATE_SEMANTIC"}
            seq = db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM synthetic_effects"
            ).fetchone()[0]
            stamp = int(time.time())
            receipt = seal(self.signer, VENDOR_DOMAIN, {
                "schema": "A190_G9_VENDOR_LAB_V1",
                "issuer": "SYNTHETIC_VENDOR_NOT_REAL",
                "tenant": claimed["tenant"],
                "semantic_digest": claimed["semantic_digest"],
                "reservation_sha256": reservation_hash(reservation),
                "seq": seq,
                "vendor_epoch": 1,
                "vendor_request_id": request_id,
                "simulated_transaction_id": "SYNTHETIC_ONLY_" + str(seq),
                "status": SYNTHETIC_STATUS,
                "issued_at": stamp,
                "expires": stamp + 300,
            })
            db.execute(
                "INSERT INTO synthetic_effects VALUES (?,?,?,?,?)",
                (seq, claimed["tenant"], claimed["semantic_digest"],
                 request_id, canonical(receipt).decode("ascii")),
            )
            db.commit()
            return {"status": "SYNTHETIC_RECORDED", "receipt": receipt}

    def lookup(self, tenant, digest):
        with closing(sqlite3.connect(self.db)) as db:
            row = db.execute(
                "SELECT receipt_json FROM synthetic_effects "
                "WHERE tenant=? AND semantic_digest=?", (tenant, digest),
            ).fetchone()
            return {
                "status": "SYNTHETIC_RECORDED" if row else "NOT_FOUND",
                "receipt": json.loads(row[0]) if row else None,
            }


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(MAX_WIRE + 1)
        if len(line) > MAX_WIRE:
            return
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                return
            method = request.get("op")
            if method == "submit":
                result = self.server.vendor.submit(
                    request.get("reservation"), request.get("request_id")
                )
            elif method == "lookup":
                result = self.server.vendor.lookup(
                    request.get("tenant"), request.get("digest")
                )
            else:
                result = {"status": "DENY_UNKNOWN_METHOD"}
            if (method == "submit"
                    and request.get("lab_drop_response") is True
                    and result.get("status") == "SYNTHETIC_RECORDED"):
                # Close TCP only AFTER SQLite COMMIT, not a simulated Boolean.
                return
            self.wfile.write(canonical(result) + b"\n")
        except (TypeError, ValueError, KeyError, sqlite3.Error):
            self.wfile.write(canonical({"status": "DENY_MALFORMED"}) + b"\n")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(state_dir, authority_pub, ready):
    try:
        vendor = SyntheticVendor(state_dir, authority_pub)
        with Server(("127.0.0.1", 0), Handler) as server:
            server.vendor = vendor
            ready.send((server.server_address[1], vendor.pub_hex()))
            ready.close()
            server.serve_forever(poll_interval=0.1)
    except BaseException as error:
        try:
            ready.send(("ERROR", type(error).__name__ + ": " + str(error)))
        finally:
            ready.close()
        raise


def launch_vendor(state_dir, authority_pin):
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=serve, args=(
        str(state_dir), authority_pin.hex(), child,
    ))
    proc.start()
    child.close()
    if not parent.poll(15):
        proc.terminate()
        proc.join(timeout=5)
        raise RuntimeError("G9_VENDOR_START_TIMEOUT")
    port, pub_hex = parent.recv()
    parent.close()
    if port == "ERROR":
        proc.join(timeout=5)
        raise RuntimeError("G9_VENDOR_START_FAILED:" + pub_hex)
    return proc, ("127.0.0.1", port), bytes.fromhex(pub_hex)


class FirstAttemptJournal:
    """Fail-closed local outbound journal; client rollback still insecure."""
    def __init__(self, path, authority_pin, vendor_pin, vendor_address):
        self.path = str(path)
        self.authority_pin = authority_pin
        self.vendor_pin = vendor_pin
        self.address = vendor_address
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS first_attempt("
                "semantic_digest TEXT PRIMARY KEY,"
                "reservation_json TEXT NOT NULL,"
                "request_id TEXT NOT NULL UNIQUE,"
                "stage TEXT NOT NULL)"
            )
            db.commit()
        self.submit_count = 0

    def stage_first_attempt(self, reservation, request_id):
        if not verify_receipt(reservation, self.authority_pin):
            return "DENY_INVALID_AUTHORITY_RESERVATION"
        digest = reservation["payload"]["semantic_digest"]
        if not isinstance(request_id, str) or not request_id:
            return "DENY_INVALID_FIRST_ATTEMPT_REQUEST"
        try:
            with closing(sqlite3.connect(self.path)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO first_attempt VALUES (?,?,?,?)",
                    (digest, canonical(reservation).decode("ascii"),
                     request_id, "UNCERTAIN_NO_AUTOMATIC_RETRY"),
                )
                db.commit()
        except sqlite3.IntegrityError:
            return "UNCERTAIN_ZERO_AUTO_RESEND"
        return "STAGED_FIRST_ATTEMPT"

    def attempt_once(self, reservation, request_id, *, drop_ack=False):
        stage = self.stage_first_attempt(reservation, request_id)
        if stage != "STAGED_FIRST_ATTEMPT":
            return {"status": stage}
        self.submit_count += 1
        try:
            response = rpc(self.address, {
                "op": "submit", "reservation": reservation,
                "request_id": request_id, "lab_drop_response": drop_ack,
            })
        except ConnectionError:
            return {"status": "UNCERTAIN_ZERO_AUTO_RESEND"}
        if (response.get("status") == "SYNTHETIC_RECORDED"
                and verify_vendor_receipt(
                    response.get("receipt"), self.vendor_pin, reservation
                )):
            return {
                "status": "SIMULATED_PROVIDER_ACK_VERIFIED_NO_REAL_EFFECT",
                "receipt": response["receipt"],
            }
        return {"status": "UNCERTAIN_ZERO_AUTO_RESEND"}

    def reconcile_read_only(self, semantic_digest):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT reservation_json FROM first_attempt "
                "WHERE semantic_digest=?", (semantic_digest,),
            ).fetchone()
        if row is None:
            return "DENY_NO_FIRST_ATTEMPT_JOURNAL"
        reservation = json.loads(row[0])
        try:
            result = rpc(self.address, {
                "op": "lookup", "tenant": reservation["payload"]["tenant"],
                "digest": semantic_digest,
            })
        except ConnectionError:
            return "UNCERTAIN_PROVIDER_UNAVAILABLE_ZERO_AUTO_RESEND"
        if result.get("status") == "NOT_FOUND":
            return "UNCERTAIN_NOT_FOUND_STILL_NO_AUTO_RESEND"
        if (result.get("status") == "SYNTHETIC_RECORDED"
                and verify_receipt(reservation, self.authority_pin)
                and verify_vendor_receipt(
                    result.get("receipt"), self.vendor_pin, reservation
                )):
            return "SIMULATED_VENDOR_RECORD_RECONCILED_READ_ONLY"
        return "DENY_UNVERIFIED_VENDOR_PROOF"


if __name__ == "__main__":
    print("A190 G9 LAB only: no real provider, no credentials, no effects.")
