"""A294 LAB: volatile independent-process witness prototype, stdlib only.

Witness state and its HMAC key live in a separate *local child process*,
not in the SQLite file. This models an external checkpoint protocol, but
the host controls BOTH processes and can reset the witness, replay a bootstrap
or bypass verification; it is emphatically not independent/off-host custody.
"""
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

from aion_chat.models import Message, Scope
from aion_chat.store import HEALTHY, SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_VOLATILE_WITNESS_SIM_LAB_V1"
SCOPE = Scope("owner-a294", "tenant-a294", "workspace-a294")
GENESIS = "GENESIS"
TABLES = ("conversations", "messages", "records")
WITNESS_CHILD = r'''
import hashlib, hmac, json, secrets, sys

secret = secrets.token_bytes(32)
record = None

def valid_sha256(value):
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))

def respond(**value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)

for line in sys.stdin:
    try:
        q = json.loads(line)
        op = q.get("op")
        if op == "stop":
            respond(ok=True, reason="STOPPED")
            break
        if op == "anchor":
            seq, digest, previous = q.get("seq"), q.get("digest"), q.get("previous")
            if type(seq) is not int or not valid_sha256(digest) or type(previous) is not str:
                respond(ok=False, reason="INVALID_ANCHOR")
                continue
            expected_seq = (record["seq"] + 1) if record else 1
            expected_previous = record["head"] if record else "GENESIS"
            if seq != expected_seq:
                respond(ok=False, reason="NON_MONOTONIC_SEQUENCE")
                continue
            if previous != expected_previous:
                respond(ok=False, reason="WRONG_PREVIOUS_HEAD")
                continue
            mac = hmac.new(
                secret, f"A294|{seq}|{digest}|{previous}".encode(),
                hashlib.sha256,
            ).hexdigest()
            head = hashlib.sha256(
                f"A294|{previous}|{mac}".encode()
            ).hexdigest()
            record = {"seq": seq, "digest": digest, "previous": previous,
                      "mac": mac, "head": head}
            respond(ok=True, reason="ANCHORED", receipt=record)
        elif op == "verify":
            receipt, digest = q.get("receipt"), q.get("digest")
            if not record:
                respond(ok=False, reason="WITNESS_UNINITIALIZED")
                continue
            if not valid_sha256(digest) or not isinstance(receipt, dict):
                respond(ok=False, reason="INVALID_VERIFY_INPUT")
                continue
            signed = receipt.get("mac")
            if type(signed) is not str:
                respond(ok=False, reason="RECEIPT_INVALID")
                continue
            derived = hmac.new(
                secret,
                f"A294|{receipt.get('seq')}|{receipt.get('digest')}|{receipt.get('previous')}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(derived, signed) or receipt != record:
                respond(ok=False, reason="RECEIPT_MISMATCH")
            elif not hmac.compare_digest(record["digest"], digest):
                respond(ok=False, reason="SNAPSHOT_MISMATCH")
            else:
                respond(ok=True, reason="MATCH")
        else:
            respond(ok=False, reason="UNSUPPORTED_OPERATION")
    except (ValueError, TypeError, KeyError):
        respond(ok=False, reason="INVALID_REQUEST")
'''


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "disposable_sqlite_only": True,
        "child_process_has_ephemeral_secret": True,
        "same_host_not_independent": True,
        "volatile_no_durable_custody": True,
        "can_authorize_send": False,
        "provider_worker_deploy_orders_disabled": True,
        "zero_auto_resend": True,
        "p0_homologated": 0,
        "native_fd_authenticated": False,
        "trusted_external_signer": False,
        "host_resistant_rollback_witness": False,
    }


def sqlite_semantic_digest(path):
    """Stable SHA-256 over all three chat business tables, not WAL file bytes."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("SQLite snapshot missing")
    values = {}
    with closing(sqlite3.connect(str(path), timeout=5)) as db:
        for table in TABLES:
            values[table] = [
                list(row) for row in db.execute(
                    "SELECT * FROM " + table + " ORDER BY 1"
                ).fetchall()
            ]
    serialized = json.dumps(
        values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class VolatileWitnessClient:
    """Synchronous JSON-line client to separate disposable local Python PID."""

    def __init__(self):
        self._child = subprocess.Popen(
            [sys.executable, "-u", "-c", WITNESS_CHILD],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )

    @property
    def active(self):
        return self._child.poll() is None

    def call(self, op, **args):
        if not self.active or self._child.stdin is None:
            return {"ok": False, "reason": "WITNESS_UNAVAILABLE"}
        try:
            self._child.stdin.write(json.dumps({"op": op, **args}) + "\n")
            self._child.stdin.flush()
            answer = self._child.stdout.readline()
            if not answer:
                return {"ok": False, "reason": "WITNESS_UNAVAILABLE"}
            response = json.loads(answer)
            if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                return {"ok": False, "reason": "WITNESS_INVALID_RESPONSE"}
            return response
        except (OSError, ValueError, BrokenPipeError):
            return {"ok": False, "reason": "WITNESS_UNAVAILABLE"}

    def close(self):
        if self.active:
            self.call("stop")
        try:
            self._child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self._child.kill()
            self._child.communicate(timeout=5)


@contextmanager
def volatile_witness():
    client = VolatileWitnessClient()
    try:
        yield client
    finally:
        client.close()


def _seed(path):
    store = SQLiteChatStore(path, strict_local_data_version=True)
    try:
        conv = store.create_conversation(SCOPE, "witness-ledger")
        return conv.id
    finally:
        store.close()


def _append(path, cid):
    store = SQLiteChatStore(path, strict_local_data_version=True)
    try:
        message = store.append_message(
            SCOPE, Message(cid, "user", "synthetic committed history",
                           id="a294-msg-first"),
        )
        return message.sequence
    finally:
        store.close()


def probe_witness_catches_closed_store_rollback():
    """Verified snapshot fails after host puts previously valid SQLite back."""
    result = _base()
    with TemporaryDirectory(prefix="a294-witness-rollback-") as raw:
        path = Path(raw) / "staging.db"
        old = Path(raw) / "old-valid.db"
        cid = _seed(path)
        shutil.copy2(path, old)
        _append(path, cid)
        latest = sqlite_semantic_digest(path)
        with volatile_witness() as witness:
            anchored = witness.call(
                "anchor", seq=1, digest=latest, previous=GENESIS
            )
            receipt = anchored.get("receipt")
            verified_before = witness.call(
                "verify", digest=latest, receipt=receipt
            )
            os.replace(old, path)
            previous = sqlite_semantic_digest(path)
            verified_after = witness.call(
                "verify", digest=previous, receipt=receipt
            )
            reopened = SQLiteChatStore(path, strict_local_data_version=True)
            try:
                local_ok = reopened.storage_health(deep=True)["state"] == HEALTHY
                local_count = reopened.get_conversation(
                    SCOPE, cid
                ).message_count
            finally:
                reopened.close()
            result.update({
                "anchored": anchored["ok"],
                "prior_snapshot_verified": verified_before["ok"],
                "different_digest_after_host_rollback": previous != latest,
                "post_rollback_witness_denied": (
                    not verified_after["ok"]
                    and verified_after["reason"] == "SNAPSHOT_MISMATCH"
                ),
                "local_strict_reopen_still_healthy": local_ok,
                "local_messages_lost": local_count == 0,
            })
    return result


def probe_sequence_and_receipt_tampering():
    """Monotonic chain, wrong parent, replay and forged receipt are refused."""
    result = _base()
    with TemporaryDirectory(prefix="a294-witness-chain-") as raw:
        path = Path(raw) / "staging.db"
        cid = _seed(path)
        first = sqlite_semantic_digest(path)
        with volatile_witness() as witness:
            initial = witness.call(
                "anchor", seq=1, digest=first, previous=GENESIS
            )
            receipt1 = initial["receipt"]
            replay = witness.call(
                "anchor", seq=1, digest=first, previous=GENESIS
            )
            wrong_parent = witness.call(
                "anchor", seq=2, digest=first, previous=GENESIS
            )
            _append(path, cid)
            second = sqlite_semantic_digest(path)
            stale = witness.call(
                "verify", digest=second, receipt=receipt1
            )
            next_ack = witness.call(
                "anchor", seq=2, digest=second,
                previous=receipt1["head"],
            )
            receipt2 = next_ack["receipt"]
            verified = witness.call(
                "verify", digest=second, receipt=receipt2
            )
            forged = dict(receipt2, mac="0" * 64)
            forged_verification = witness.call(
                "verify", digest=second, receipt=forged
            )
            old_receipt_again = witness.call(
                "verify", digest=first, receipt=receipt1
            )
            result.update({
                "first_anchor_accepted": initial["ok"],
                "replay_denied": replay["reason"] == "NON_MONOTONIC_SEQUENCE",
                "wrong_parent_denied": (
                    wrong_parent["reason"] == "WRONG_PREVIOUS_HEAD"
                ),
                "new_history_requires_new_anchor": (
                    stale["reason"] == "SNAPSHOT_MISMATCH"
                ),
                "second_chain_anchor_accepted": next_ack["ok"],
                "latest_receipt_verified": verified["ok"],
                "forged_receipt_denied": (
                    forged_verification["reason"] == "RECEIPT_MISMATCH"
                ),
                "old_receipt_no_longer_current": (
                    old_receipt_again["reason"] == "RECEIPT_MISMATCH"
                ),
            })
    return result


def probe_witness_reset_and_bootstrap_bypass():
    """A same-host attacker can reset witness and improperly re-bootstrap."""
    result = _base()
    with TemporaryDirectory(prefix="a294-reset-") as raw:
        path = Path(raw) / "staging.db"
        cid = _seed(path)
        old = Path(raw) / "old.db"
        shutil.copy2(path, old)
        _append(path, cid)
        valid_latest = sqlite_semantic_digest(path)
        with volatile_witness() as witness:
            ack = witness.call(
                "anchor", seq=1, digest=valid_latest, previous=GENESIS
            )
            receipt = ack["receipt"]
            witness._child.kill()
            witness._child.wait(timeout=5)
            unavailable = witness.call(
                "verify", digest=valid_latest, receipt=receipt
            )
        os.replace(old, path)
        old_digest = sqlite_semantic_digest(path)
        with volatile_witness() as reset_witness:
            old_receipt = reset_witness.call(
                "verify", digest=valid_latest, receipt=receipt
            )
            forged_bootstrap = reset_witness.call(
                "anchor", seq=1, digest=old_digest, previous=GENESIS
            )
            bogus_independent_claim = reset_witness.call(
                "verify", digest=old_digest,
                receipt=forged_bootstrap.get("receipt"),
            )
            result.update({
                "initial_anchor": ack["ok"],
                "killed_witness_denied": (
                    unavailable["reason"] == "WITNESS_UNAVAILABLE"
                ),
                "new_empty_witness_denied_old_receipt": (
                    old_receipt["reason"] == "WITNESS_UNINITIALIZED"
                ),
                "unsafe_reset_can_reanchor_old_history": (
                    forged_bootstrap["ok"] and bogus_independent_claim["ok"]
                ),
                "same_host_witness_is_not_trusted_custody": True,
            })
    return result


__all__ = [
    "SCHEMA", "GENESIS", "TABLES", "sqlite_semantic_digest",
    "VolatileWitnessClient", "volatile_witness",
    "probe_witness_catches_closed_store_rollback",
    "probe_sequence_and_receipt_tampering",
    "probe_witness_reset_and_bootstrap_bypass",
]
