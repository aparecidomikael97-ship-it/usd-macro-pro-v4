"""A121 synthetic custody-boundary contract. No network/provider credentials/production integration.

Custodian SQLite and client SQLite files are separate test fixtures under one Linux admin.
This is NOT independent custody or signed authentic attestation in the real world.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, asdict
import hashlib
import json
import sqlite3

class Denied(RuntimeError):
    pass

class Uncertain(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Intent:
    intent_id: str
    idem_key: str
    owner: str
    tenant: str
    workspace: str
    action: str
    account: str
    destination_digest: str
    payload_digest: str
    epoch: int

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == "epoch":
                if type(value) is not int or value < 1:
                    raise ValueError("INVALID_EPOCH")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError("EMPTY_INTENT_FIELD_" + key)

    @property
    def identity_hash(self):
        return digest(asdict(self))


class FakeSender:
    """Intentionally inert, with no production SDK and no networking."""
    def __init__(self, sink=None, effect="ack"):
        self.sink = sink if sink is not None else []
        self.effect = effect

    def call(self, intent):
        self.sink.append(intent.identity_hash)
        if self.effect in ("timeout", "429", "5xx"):
            raise Uncertain("FAKE_PROVIDER_UNCERTAIN_" + self.effect)
        return {"accepted_by_fixture": True, "provider_effect_proven": False}


class CustodianFixture:
    """Emulated outside-admin trust boundary; caller CANNOT certify admin separation."""
    def __init__(self, ledger_path, *, available=True, enrolled=True, sender=None):
        self.ledger_path = str(ledger_path)
        self.available = available
        self.enrolled = enrolled
        # Fixture-only injected sender; caller of dispatch_once cannot swap SDK.
        self._sender = sender if sender is not None else FakeSender()
        if type(self._sender) is not FakeSender:
            raise Denied("CUSTODIAN_FAKE_SENDER_ONLY")
        with self._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS intents (
                intent_id TEXT PRIMARY KEY, identity TEXT NOT NULL,
                state TEXT NOT NULL, version INTEGER NOT NULL,
                binding TEXT NOT NULL, audit_head TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, intent_id TEXT NOT NULL,
                event TEXT NOT NULL, binding TEXT NOT NULL, nonce TEXT NOT NULL DEFAULT '',
                previous TEXT NOT NULL, hash TEXT NOT NULL)""")
            db.execute("CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), audit_head TEXT NOT NULL, seq INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO meta VALUES(1,?,0)", ("GENESIS",))
            db.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, intent_id TEXT NOT NULL)")

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.ledger_path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _policy(self):
        if not self.available:
            raise Denied("CUSTODIAN_UNAVAILABLE_FAIL_CLOSED")
        if not self.enrolled:
            raise Denied("INDEPENDENT_ENROLLMENT_UNPROVEN")

    @staticmethod
    def _row(db, intent):
        return db.execute("SELECT identity,state,version,binding,audit_head FROM intents WHERE intent_id=?", (intent.intent_id,)).fetchone()

    @staticmethod
    def _binding(intent, state, version):
        return digest({"identity": intent.identity_hash, "state": state, "version": version})

    @staticmethod
    def _append(db, intent_id, event, binding, nonce=""):
        previous,seq=db.execute("SELECT audit_head,seq FROM meta WHERE id=1").fetchone()
        seq+=1
        row={"seq":seq,"intent_id":intent_id,"event":event,"binding":binding,"nonce":nonce,"previous":previous}
        h=digest(row)
        db.execute("INSERT INTO audit (seq,intent_id,event,binding,nonce,previous,hash) VALUES (?,?,?,?,?,?,?)",
                   (seq,intent_id,event,binding,nonce,previous,h))
        db.execute("UPDATE meta SET audit_head=?,seq=? WHERE id=1", (h,seq))
        return h

    @staticmethod
    def _verify_all(db):
        last="GENESIS"; last_seq=0; seen=set()
        for seq,intent_id,event,binding,nonce,previous,h in db.execute(
            "SELECT seq,intent_id,event,binding,nonce,previous,hash FROM audit ORDER BY seq"):
            if seq!=last_seq+1 or previous!=last:
                raise Denied("CUSTODIAN_AUDIT_CHAIN_MISMATCH")
            row={"seq":seq,"intent_id":intent_id,"event":event,"binding":binding,"nonce":nonce,"previous":previous}
            if digest(row)!=h:
                raise Denied("CUSTODIAN_AUDIT_TAMPER")
            if event=="NONCE_USED":
                if nonce in seen or not nonce:
                    raise Denied("CUSTODIAN_NONCE_REPLAY")
                seen.add(nonce)
            last=h;last_seq=seq
        stored_head,stored_seq=db.execute("SELECT audit_head,seq FROM meta WHERE id=1").fetchone()
        if (stored_head,stored_seq)!=(last,last_seq):
            raise Denied("CUSTODIAN_AUDIT_HEAD_MISMATCH")
        stored_nonces={r[0] for r in db.execute("SELECT nonce FROM nonces")}
        if stored_nonces != seen:
            raise Denied("CUSTODIAN_NONCE_LEDGER_MISMATCH")
        # Every active state must be backed by its own latest witnessed event.
        for intent_id,binding,head in db.execute("SELECT intent_id,binding,audit_head FROM intents"):
            last_event=db.execute("SELECT binding,hash FROM audit WHERE intent_id=? AND event!='NONCE_USED' ORDER BY seq DESC LIMIT 1",(intent_id,)).fetchone()
            if not last_event or last_event != (binding,head):
                raise Denied("CUSTODIAN_ROW_AND_AUDIT_DIVERGED")

    def enroll_intent(self, intent):
        self._policy()
        with self._tx() as db:
            self._verify_all(db)
            row=self._row(db,intent)
            if row:
                if row[0]!=intent.identity_hash:
                    raise Denied("IMMUTABLE_INTENT_SCOPE_CONFLICT")
                return {"state":row[1],"version":row[2],"binding":row[3]}
            bind=self._binding(intent,"PREPARED",1)
            head=self._append(db,intent.intent_id,"PREPARED",bind)
            db.execute("INSERT INTO intents VALUES(?,?,?,?,?,?)",(intent.intent_id,intent.identity_hash,"PREPARED",1,bind,head))
            return {"state":"PREPARED","version":1,"binding":bind}

    def read(self, intent):
        self._policy()
        with self._tx() as db:
            self._verify_all(db)
            row=self._row(db,intent)
            if row is None:
                raise Denied("CUSTODIAN_INTENT_NOT_ENROLLED")
            if row[0]!=intent.identity_hash:
                raise Denied("IMMUTABLE_INTENT_SCOPE_CONFLICT")
            if row[3]!=self._binding(intent,row[1],row[2]):
                raise Denied("CUSTODIAN_ROW_COMMITMENT_MISMATCH")
            return {"state":row[1],"version":row[2],"binding":row[3]}

    def _transition(self, intent, target):
        self._policy()
        with self._tx() as db:
            self._verify_all(db)
            row=self._row(db,intent)
            if row is None or row[0]!=intent.identity_hash:
                raise Denied("CUSTODIAN_SCOPE_OR_ENROLLMENT_DENIED")
            if row[1]!="PREPARED" or row[2]!=1:
                raise Denied("ISSUE_ALREADY_CONSUMED_OR_FENCED")
            newbind=self._binding(intent,target,2)
            head=self._append(db,intent.intent_id,"ISSUE_ONCE" if target=="UNKNOWN" else "FENCED_PRE_HANDOFF",newbind)
            db.execute("UPDATE intents SET state=?,version=2,binding=?,audit_head=? WHERE intent_id=? AND version=1",
                       (target,newbind,head,intent.intent_id))
        return {"state":target,"version":2,"binding":newbind}

    def fence_pre_handoff(self, intent):
        return self._transition(intent,"FENCED_PRE_HANDOFF")

    def dispatch_once(self, intent, *, crash_after_mark=False):
        # Only the custodian fixture owns the fake sender; client cannot supply SDK.
        decision=self._transition(intent,"UNKNOWN")  # committed before fake sender call
        if crash_after_mark:
            raise Uncertain("CRASH_AFTER_ISSUE_BEFORE_FAKE_CALL")
        self._sender.call(intent)
        return decision  # Remains UNKNOWN: fixture ACK never proves provider effect.

    def register_receipt_nonce(self, intent, nonce):
        self._policy()
        if type(nonce) is not str or len(nonce)<6:
            raise Denied("NONCE_INVALID")
        with self._tx() as db:
            self._verify_all(db)
            row=self._row(db,intent)
            if not row or row[0]!=intent.identity_hash:
                raise Denied("NONCE_INTENT_NOT_ENROLLED")
            if db.execute("SELECT 1 FROM nonces WHERE nonce=?",(nonce,)).fetchone():
                raise Denied("NONCE_REPLAY_DENIED")
            self._append(db,intent.intent_id,"NONCE_USED",row[3],nonce=nonce)
            db.execute("INSERT INTO nonces VALUES(?,?)",(nonce,intent.intent_id))
        return "NONCE_RECORDED_IN_FIXTURE_ONLY"

    def verify_mirror(self, intent, mirror):
        remote=self.read(intent)  # Mandatory external-first policy assumed.
        if not isinstance(mirror,dict) or set(mirror)!={"state","version","binding"}:
            raise Denied("MIRROR_MISSING_OR_INVALID")
        if mirror!=remote:
            raise Denied("CLIENT_ROLLBACK_OR_DIVERGENCE_QUARANTINE")
        return "MIRROR_MATCHES_FAKE_CUSTODIAN"


def production_enabled():
    return False
