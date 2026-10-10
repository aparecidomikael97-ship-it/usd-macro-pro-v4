"""Durable browser-request correlation, not an execution queue or authority.

Uses the staged chat database and SQLite's existing transaction/identity model.
The external ExecutionOutbox remains separate: no leases, dispatcher, provider,
retry worker, approval or effect ledger is introduced here.
"""
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import secrets
import re
import sqlite3

from aion_chat.models import Conversation, Scope
from aion_chat.store import BUSY_TIMEOUT_MS, StorageUnavailableError, dump

TABLE = "chat_browser_requests"
MAX_PAIR_BYTES = 200_000


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def request_digests(scope, access, text):
    return (_hash({"message": text, "attachments": []}),
            _hash({"scope": asdict(scope),
                   "fingerprint": access["session"]["credential_fingerprint"]}))


@contextmanager
def _open(path, *, readonly=False):
    path = Path(path).resolve()
    identity = path.stat()
    db = sqlite3.connect(path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                         uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        if readonly:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
        yield db
        after = path.stat()
        if (identity.st_dev, identity.st_ino) != (after.st_dev, after.st_ino):
            raise StorageUnavailableError("request database identity changed")
    finally:
        db.close()


def _args(scope, rid):
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id, rid


def _row(db, scope, rid):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return None
    row = db.execute(f"SELECT * FROM {TABLE} WHERE owner=? AND tenant=? AND workspace=? AND request_id=?",
                     _args(scope, rid)).fetchone()
    return dict(row) if row else None


def _owned(db, scope, cid):
    row = db.execute("SELECT data FROM conversations WHERE id=? AND owner=? AND tenant=? AND workspace=?",
                     (cid, scope.owner_id, scope.tenant_id, scope.workspace_id)).fetchone()
    if not row:
        raise LookupError("scoped conversation unavailable")
    data = json.loads(row["data"])
    if any(data.get(k) != v for k, v in asdict(scope).items()) or data.get("id") != cid:
        raise ValueError("conversation identity mismatch")
    return data


def _validate(row, requested_cid, current_cid, input_digest, context_digest):
    if row["input_digest"] != input_digest or row["context_digest"] != context_digest:
        raise ValueError("browser request binding conflict")
    if requested_cid not in {row["requested_cid"], row["conversation_id"]}:
        raise ValueError("browser request conversation conflict")
    if current_cid and current_cid != row["conversation_id"]:
        raise ValueError("active conversation conflicts with browser request")


def reserve_request(store, scope, rid, requested_cid, current_cid, input_digest, context_digest):
    """Return an existing binding, or atomically reserve exactly one first attempt."""
    if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}", rid):
        raise ValueError("invalid browser request identity")
    path = store.path
    with _open(path, readonly=True) as db:
        old = _row(db, scope, rid)
        if old:
            _validate(old, requested_cid, current_cid, input_digest, context_digest)
            return {**old, "fresh": False}
    store.require_healthy()  # A failed facade can reconcile, never admit new writes.
    if requested_cid != current_cid:
        raise ValueError("durable session conversation mismatch")
    permit = secrets.token_hex(32)
    with _open(path) as db:
        db.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE}(
            owner TEXT NOT NULL, tenant TEXT NOT NULL, workspace TEXT NOT NULL,
            request_id TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations(id),
            requested_cid TEXT NOT NULL, input_digest TEXT NOT NULL, context_digest TEXT NOT NULL,
            turn_index INTEGER NOT NULL, turn_id TEXT NOT NULL DEFAULT '',
            permit_digest TEXT NOT NULL, expected_pair TEXT NOT NULL DEFAULT '',
            expected_digest TEXT NOT NULL DEFAULT '', state TEXT NOT NULL,
            PRIMARY KEY(owner,tenant,workspace,request_id),
            CHECK(length(expected_pair)<=200000))""")
        db.execute(f"CREATE INDEX IF NOT EXISTS browser_request_pending ON {TABLE}(owner,tenant,workspace,conversation_id,state)")
        db.execute("BEGIN IMMEDIATE")
        old = _row(db, scope, rid)
        if old:
            _validate(old, requested_cid, current_cid, input_digest, context_digest)
            db.commit()
            return {**old, "fresh": False}
        cid = current_cid
        if cid:
            conversation = _owned(db, scope, cid)
            registered = db.execute(f"SELECT 1 FROM {TABLE} WHERE owner=? AND tenant=? AND workspace=? AND conversation_id=? AND state IN ('COMPLETE','LOCAL_RECONCILED') LIMIT 1",
                                    (scope.owner_id, scope.tenant_id, scope.workspace_id, cid)).fetchone()
            if int(conversation["message_count"]) and not registered:
                raise StorageUnavailableError("legacy request history has no durable browser binding")
            pending = db.execute(f"SELECT request_id FROM {TABLE} WHERE owner=? AND tenant=? AND workspace=? AND conversation_id=? AND state NOT IN ('COMPLETE','LOCAL_RECONCILED','NO_WRITE') LIMIT 1",
                                 (scope.owner_id, scope.tenant_id, scope.workspace_id, cid)).fetchone()
            if pending:
                raise StorageUnavailableError("prior browser request requires reconciliation")
        else:
            conversation = Conversation(**asdict(scope), title="AION principal")
            cid = conversation.id
            db.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
                       (cid, scope.owner_id, scope.tenant_id, scope.workspace_id,
                        conversation.updated_at, False, conversation.title, dump(conversation)))
            conversation = asdict(conversation)
        db.execute(f"INSERT INTO {TABLE}(owner,tenant,workspace,request_id,conversation_id,requested_cid,input_digest,context_digest,turn_index,permit_digest,state) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (*_args(scope, rid), cid, requested_cid, input_digest, context_digest,
                    int(conversation["message_count"]), _hash(permit), "ADMITTED"))
        db.commit()
        row = _row(db, scope, rid)
    return {**row, "fresh": True, "_permit": permit}


def bind_expected_pair(path, scope, ticket, user, assistant):
    """Persist exact expected rows BEFORE crossing either message-write boundary."""
    if user.role != "user" or assistant.role != "assistant":
        raise ValueError("expected user/assistant pair required")
    for message in (user, assistant):
        if message.conversation_id != ticket["conversation_id"]:
            raise ValueError("expected pair conversation mismatch")
        message.metadata.update(browser_request_id=ticket["request_id"],
                                request_input_digest=ticket["input_digest"],
                                request_context_digest=ticket["context_digest"])
    pair = [json.loads(dump(m)) for m in (user, assistant)]
    turn_id = user.metadata.get("turn_id")
    if not turn_id or assistant.metadata.get("turn_id") != turn_id:
        raise ValueError("expected pair turn mismatch")
    encoded = _json(pair)
    if len(encoded.encode("utf-8")) > MAX_PAIR_BYTES:
        raise ValueError("expected pair exceeds bound")
    with _open(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = _row(db, scope, ticket["request_id"])
        if not row or row["state"] != "ADMITTED" or row["permit_digest"] != _hash(ticket.get("_permit")):
            raise StorageUnavailableError("first-attempt request permit unavailable")
        _validate(row, ticket["requested_cid"], ticket["conversation_id"], ticket["input_digest"], ticket["context_digest"])
        db.execute(f"UPDATE {TABLE} SET expected_pair=?,expected_digest=?,turn_id=?,state='PREPARED' WHERE owner=? AND tenant=? AND workspace=? AND request_id=? AND state='ADMITTED'",
                   (encoded, _hash(pair), turn_id, *_args(scope, ticket["request_id"])))
        db.commit()


def _proof(db, scope, row):
    if str(db.execute("PRAGMA quick_check").fetchone()[0]).lower() != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
        raise StorageUnavailableError("request readback integrity failed")
    _owned(db, scope, row["conversation_id"])
    if row["state"] not in {"PREPARED", "COMPLETE", "LOCAL_RECONCILED"} or not row["expected_pair"]:
        return False
    pair = json.loads(row["expected_pair"])
    if not isinstance(pair, list) or len(pair) != 2 or _hash(pair) != row["expected_digest"]:
        return False
    sequences = []
    for expected, role in zip(pair, ("user", "assistant")):
        if expected.get("role") != role or expected.get("conversation_id") != row["conversation_id"]:
            return False
        metadata = expected.get("metadata") or {}
        if metadata.get("turn_id") != row["turn_id"] or metadata.get("browser_request_id") != row["request_id"]:
            return False
        if metadata.get("request_input_digest") != row["input_digest"] or metadata.get("request_context_digest") != row["context_digest"]:
            return False
        found = db.execute("SELECT seq,data FROM messages WHERE cid=? AND id=?", (row["conversation_id"], expected["id"])).fetchone()
        if not found:
            return False
        observed = json.loads(found["data"])
        if observed.get("sequence") != found["seq"]:
            return False
        expected = dict(expected)
        observed.pop("sequence", None)
        expected.pop("sequence", None)
        if observed != expected:
            return False
        sequences.append(found["seq"])
    return sequences[0] < sequences[1]


def reconcile_request(path, scope, ticket, *, completed=False):
    """Independent, query-only readback; absence never authorizes another append."""
    with _open(path, readonly=True) as db:
        row = _row(db, scope, ticket["request_id"])
        if not row:
            raise StorageUnavailableError("durable request binding missing")
        _validate(row, ticket["requested_cid"], ticket["conversation_id"], ticket["input_digest"], ticket["context_digest"])
        matched = _proof(db, scope, row)
    if matched:
        # Recheck under the write lock to avoid confirming a stale read snapshot.
        # This changes only the correlation row, never messages or authority.
        with _open(path) as db:
            db.execute("BEGIN IMMEDIATE")
            latest = _row(db, scope, ticket["request_id"])
            if not latest or latest["expected_digest"] != row["expected_digest"] or not _proof(db, scope, latest):
                raise StorageUnavailableError("request changed during reconciliation")
            db.execute(f"UPDATE {TABLE} SET state=? WHERE owner=? AND tenant=? AND workspace=? AND request_id=?",
                       ("COMPLETE" if completed else "LOCAL_RECONCILED", *_args(scope, ticket["request_id"])))
            db.commit()
    no_write = row["state"] == "NO_WRITE"
    return {"state": ("LOCAL_PAIR_RECONCILED" if matched else
                      "REQUEST_ALREADY_SEEN_NO_WRITE" if no_write else
                      "BLOCKED_RECONCILIATION_REQUIRED"),
            "reason": ("SCOPED_PAIR_READBACK_MATCH" if matched else
                       "LIVE_PREFLIGHT_FINALIZED_WITHOUT_WRITE" if no_write else
                       "PAIR_ABSENT_PARTIAL_OR_CONFLICTING"),
            "request_id": ticket["request_id"], "conversation_id": ticket["conversation_id"],
            "turn_id": row["turn_id"], "local_history_persisted": matched,
            "execution_authorized": False, "grants_authority": False,
            "external_action_executed": False, "persisted_externally": False,
            "memory_promoted": False, "automatic_checkpoint_write": False,
            "message_write_attempted": False, "retry_authorized": False,
            "provider_called": False, "network_called": False,
            "global_worker_started": False, "real_orders_enabled": False}


def finish_without_write(path, scope, ticket):
    """Only a live first-attempt caller may record a verified no-write preflight."""
    with _open(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = _row(db, scope, ticket["request_id"])
        if row and row["state"] == "ADMITTED" and row["permit_digest"] == _hash(ticket.get("_permit")):
            _validate(row, ticket["requested_cid"], ticket["conversation_id"], ticket["input_digest"], ticket["context_digest"])
            db.execute(f"UPDATE {TABLE} SET state='NO_WRITE' WHERE owner=? AND tenant=? AND workspace=? AND request_id=?",
                       _args(scope, ticket["request_id"]))
        db.commit()
