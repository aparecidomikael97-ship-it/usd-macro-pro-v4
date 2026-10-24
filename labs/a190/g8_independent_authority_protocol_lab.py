"""A190 G8 LAB: simulated outside-the-client authority protocol over real loopback TCP.

A separate process owns a SQLite ledger and an Ed25519 signing key; the client
receives only the public pin. This is NOT an independent host, operator,
hardware root, authentic HUMAN_OWNER, provider receipt or P0 homologation:
same-host admin can restore BOTH secrets and ledger. All data is synthetic.
"""
from __future__ import annotations

import base64
from contextlib import closing
from hashlib import sha256
import json
import multiprocessing
import os
from pathlib import Path
import socket
import socketserver
import sqlite3
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

EVENT_DOMAIN = b"A190:G8:SYNTHETIC_EVENT_ISSUER\0"
RECEIPT_DOMAIN = b"A190:G8:SYNTHETIC_CUSTODIAN\0"
EVENT_FIELDS = frozenset({
    "schema", "issuer", "tenant", "event_ref", "semantic_digest",
    "not_before", "expires", "nonce",
})
RECEIPT_FIELDS = frozenset({
    "schema", "issuer", "tenant", "event_ref", "semantic_digest",
    "seq", "epoch", "request_id", "status", "issued_at", "expires",
})
MAX_WIRE = 16384


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":")).encode("ascii")


def pub_bytes(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def private_raw(private):
    return private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def seal(private, domain, payload):
    return {
        "payload": payload,
        "signature_b64": base64.b64encode(
            private.sign(domain + canonical(payload))
        ).decode("ascii"),
    }


def check_seal(envelope, pin, domain, fields):
    if not isinstance(envelope, dict) or set(envelope) != {
        "payload", "signature_b64",
    }:
        return None
    payload = envelope["payload"]
    if not isinstance(payload, dict) or set(payload) != fields:
        return None
    if not isinstance(envelope["signature_b64"], str):
        return None
    try:
        Ed25519PublicKey.from_public_bytes(pin).verify(
            base64.b64decode(envelope["signature_b64"], validate=True),
            domain + canonical(payload),
        )
    except (ValueError, InvalidSignature, TypeError, OverflowError):
        return None
    return payload


def synthetic_event(private, *, ref="issuer-event-01", digest=None, now=None):
    now = int(time.time()) if now is None else now
    if digest is None:
        digest = sha256(b"ONE-SYNTHETIC-NONFINANCIAL-EFFECT").hexdigest()
    return seal(private, EVENT_DOMAIN, {
        "schema": "A190_G8_EVENT_V1",
        "issuer": "LAB_EVENT_ISSUER_NOT_REAL",
        "tenant": "synthetic_tenant",
        "event_ref": ref,
        "semantic_digest": digest,
        "not_before": now - 10,
        "expires": now + 900,
        "nonce": "synthetic-original-authenticated-by-lab-key",
    })


class Custodian:
    """State outside CLIENT rollback only; same-host root controls everything."""
    def __init__(self, state_dir, pinned_event_key):
        self.state_dir = Path(state_dir)
        self.db_path = self.state_dir / "custodian.sqlite"
        self.key_path = self.state_dir / "custodian-private.raw"
        self.pinned_event_key = bytes.fromhex(pinned_event_key)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            with self.key_path.open("xb") as handle:
                handle.write(private_raw(Ed25519PrivateKey.generate()))
                handle.flush()
                os.fsync(handle.fileno())
        self.signer = Ed25519PrivateKey.from_private_bytes(
            self.key_path.read_bytes()
        )
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations("
                "seq INTEGER PRIMARY KEY,"
                "tenant TEXT NOT NULL,"
                "semantic_digest TEXT NOT NULL,"
                "event_ref TEXT NOT NULL,"
                "request_id TEXT NOT NULL UNIQUE,"
                "receipt_json TEXT NOT NULL,"
                "UNIQUE(tenant,semantic_digest))"
            )
            db.commit()

    def pub_hex(self):
        return pub_bytes(self.signer).hex()

    def reserve(self, event, claimed_event_id, request_id):
        stamp = int(time.time())
        payload = check_seal(
            event, self.pinned_event_key, EVENT_DOMAIN, EVENT_FIELDS
        )
        if payload is None:
            return {"status": "DENY_UNAUTHENTICATED_EVENT"}
        if (payload["schema"] != "A190_G8_EVENT_V1"
                or payload["issuer"] != "LAB_EVENT_ISSUER_NOT_REAL"
                or payload["tenant"] != "synthetic_tenant"
                or not isinstance(payload["event_ref"], str)
                or not 1 <= len(payload["event_ref"]) <= 120
                or not isinstance(payload["semantic_digest"], str)
                or len(payload["semantic_digest"]) != 64
                or any(c not in "0123456789abcdef"
                       for c in payload["semantic_digest"])
                or type(payload["not_before"]) is not int
                or type(payload["expires"]) is not int
                or payload["not_before"] > stamp
                or payload["expires"] <= stamp
                or payload["expires"] - payload["not_before"] > 3600
                or not isinstance(payload["nonce"], str)
                or not payload["nonce"]):
            return {"status": "DENY_EVENT_SCOPE_OR_TIME"}
        if (not isinstance(request_id, str)
                or not 1 <= len(request_id) <= 48
                or not all(c.isascii() and (c.isalnum() or c in "-_")
                           for c in request_id)
                or not isinstance(claimed_event_id, str)):
            return {"status": "DENY_REQUEST_INPUT"}
        # CRITICAL: claimed_event_id is ignored for uniqueness. Server uses
        # semantic_digest inside a trusted-signature original event envelope.
        with closing(sqlite3.connect(self.db_path, timeout=5)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            already = db.execute(
                "SELECT seq FROM reservations "
                "WHERE (tenant=? AND semantic_digest=?) OR request_id=?",
                (payload["tenant"], payload["semantic_digest"], request_id),
            ).fetchone()
            if already:
                db.rollback()
                return {"status": "DENY_DUPLICATE_SEMANTIC_OR_REQUEST"}
            seq = db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 FROM reservations"
            ).fetchone()[0]
            receipt = seal(self.signer, RECEIPT_DOMAIN, {
                "schema": "A190_G8_RECEIPT_V1",
                "issuer": "LAB_CUSTODIAN_NOT_EXTERNAL",
                "tenant": payload["tenant"],
                "event_ref": payload["event_ref"],
                "semantic_digest": payload["semantic_digest"],
                "seq": seq,
                "epoch": 1,
                "request_id": request_id,
                "status": "RESERVED_ONLY_NO_EFFECT",
                "issued_at": stamp,
                "expires": stamp + 300,
            })
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?,?,?,?)",
                (seq, payload["tenant"], payload["semantic_digest"],
                 payload["event_ref"], request_id,
                 canonical(receipt).decode("ascii")),
            )
            db.commit()
            return {"status": "RESERVED_ONLY", "receipt": receipt}

    def lookup(self, tenant, digest):
        # Read-only synthetic discovery is not a provider receipt or effect ACK.
        with closing(sqlite3.connect(self.db_path)) as db:
            row = db.execute(
                "SELECT receipt_json FROM reservations "
                "WHERE tenant=? AND semantic_digest=?", (tenant, digest),
            ).fetchone()
            return {"status": "RESERVED_ONLY" if row else "NOT_FOUND",
                    "receipt": json.loads(row[0]) if row else None}


def verify_receipt(envelope, pin, *, now=None, epoch=1):
    data = check_seal(envelope, pin, RECEIPT_DOMAIN, RECEIPT_FIELDS)
    stamp = int(time.time()) if now is None else now
    if (data is None
            or data["schema"] != "A190_G8_RECEIPT_V1"
            or data["issuer"] != "LAB_CUSTODIAN_NOT_EXTERNAL"
            or data["tenant"] != "synthetic_tenant"
            or data["status"] != "RESERVED_ONLY_NO_EFFECT"
            or type(data["seq"]) is not int or data["seq"] <= 0
            or type(data["epoch"]) is not int or data["epoch"] != epoch
            or type(data["issued_at"]) is not int
            or type(data["expires"]) is not int
            or not data["issued_at"] <= stamp < data["expires"]
            or data["expires"] - data["issued_at"] > 300
            or not isinstance(data["request_id"], str)
            or not isinstance(data["semantic_digest"], str)):
        return False
    return True


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(MAX_WIRE + 1)
        if len(line) > MAX_WIRE:
            return
        try:
            req = json.loads(line)
            if not isinstance(req, dict):
                return
            op = req.get("op")
            if op == "reserve":
                result = self.server.custodian.reserve(
                    req.get("event"), req.get("claimed_id"), req.get("request_id")
                )
            elif op == "lookup":
                result = self.server.custodian.lookup(
                    req.get("tenant"), req.get("digest")
                )
            else:
                result = {"status": "DENY_UNKNOWN_METHOD"}
            if (op == "reserve" and req.get("lab_drop_response") is True
                    and result.get("status") == "RESERVED_ONLY"):
                # Actual socket closes after durable COMMIT. Client sees EOF.
                return
            self.wfile.write(canonical(result) + b"\n")
        except (ValueError, TypeError, KeyError, sqlite3.Error):
            self.wfile.write(canonical({"status": "DENY_MALFORMED"}) + b"\n")


class TcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(state_dir, event_pin_hex, ready):
    try:
        custodian = Custodian(state_dir, event_pin_hex)
        with TcpServer(("127.0.0.1", 0), Handler) as server:
            server.custodian = custodian
            ready.send((server.server_address[1], custodian.pub_hex()))
            ready.close()
            server.serve_forever(poll_interval=0.1)
    except BaseException as error:
        try:
            ready.send(("ERROR", type(error).__name__ + ": " + str(error)))
        finally:
            ready.close()
        raise


def launch(state_dir, event_pin_hex):
    ctx = multiprocessing.get_context("spawn")
    local, remote = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=serve, args=(str(state_dir), event_pin_hex, remote))
    proc.start()
    remote.close()
    if not local.poll(15):
        proc.terminate()
        proc.join(timeout=5)
        raise RuntimeError("G8_CUSTODIAN_START_TIMEOUT")
    port, public_hex = local.recv()
    local.close()
    if port == "ERROR":
        proc.join(timeout=5)
        raise RuntimeError("G8_CUSTODIAN_START_FAILURE: " + public_hex)
    return proc, ("127.0.0.1", port), bytes.fromhex(public_hex)


def rpc(address, request):
    try:
        conn = socket.create_connection(address, timeout=2)
    except OSError as error:
        raise ConnectionError("AUTHORITY_UNAVAILABLE_BEFORE_SEND") from error
    with conn:
        conn.settimeout(2)
        conn.sendall(canonical(request) + b"\n")
        try:
            with conn.makefile("rb") as stream:
                line = stream.readline(MAX_WIRE + 1)
        except OSError as error:
            raise ConnectionError("AUTHORITY_REPLY_UNCERTAIN") from error
        if not line or len(line) > MAX_WIRE:
            raise ConnectionError("AUTHORITY_REPLY_UNCERTAIN")
        return json.loads(line)


class Client:
    def __init__(self, address, authority_pin):
        self.address = address
        self.pin = authority_pin
        self.uncertain_digests = set()
        self.send_count = 0

    def reserve_once(self, event, claimed_id, request_id, drop_ack=False):
        if not isinstance(event, dict) or not isinstance(
            event.get("payload"), dict
        ):
            return {"status": "DENY_BAD_EVENT"}
        digest = event["payload"].get("semantic_digest")
        if digest in self.uncertain_digests:
            return {"status": "UNCERTAIN_ZERO_AUTO_RESEND"}
        self.send_count += 1
        try:
            response = rpc(self.address, {
                "op": "reserve", "event": event, "claimed_id": claimed_id,
                "request_id": request_id, "lab_drop_response": drop_ack,
            })
        except ConnectionError as error:
            # An attempted send may have committed before failure. Even for
            # timeout/refusal, do not infer a safe resend.
            self.uncertain_digests.add(digest)
            return {"status": "UNCERTAIN_ZERO_AUTO_RESEND",
                    "reason": str(error)}
        if response.get("status") == "RESERVED_ONLY":
            if not verify_receipt(response.get("receipt"), self.pin):
                self.uncertain_digests.add(digest)
                return {"status": "DENY_BAD_CUSTODIAN_RECEIPT"}
            return {"status": "RESERVED_ONLY_VERIFIED_NO_EFFECT",
                    "receipt": response["receipt"]}
        return response

    def reconcile_read_only(self, tenant, digest):
        try:
            result = rpc(self.address, {
                "op": "lookup", "tenant": tenant, "digest": digest,
            })
        except ConnectionError:
            return {"status": "UNCERTAIN_AUTHORITY_UNAVAILABLE"}
        if (result.get("status") == "RESERVED_ONLY"
                and verify_receipt(result.get("receipt"), self.pin)):
            return {"status": "READ_ONLY_RESERVATION_NOT_EFFECT_CONFIRMED"}
        return {"status": "UNCERTAIN_NO_ATTESTED_RESERVATION"}


if __name__ == "__main__":
    print("G8 LAB module only. Use test_g8_remote_authority_protocol_lab.py; no service launch.")
