"""A123: offline crash-cut/receipt PROTOCOL FIXTURE, NOT independent custody.

Two mutable local SQLite databases and a toy HMAC signatory simulate roles.
They share one filesystem/admin; their joint restore or signer compromise defeats
antirollback. No network, cloud, real provider, SDK, credentials, or effect proof.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, asdict
import hashlib
import hmac
import json
import sqlite3


class Denied(RuntimeError):
    pass


class Uncertain(RuntimeError):
    pass


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Intent:
    intent_id: str
    owner: str
    tenant: str
    workspace: str
    account: str
    action: str
    destination_digest: str
    payload_digest: str
    epoch: int

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == "epoch":
                if type(value) is not int or value < 1:
                    raise ValueError("INVALID_EPOCH")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError("EMPTY_" + key)

    @property
    def binding(self):
        return digest(asdict(self))


@contextmanager
def transaction(path):
    db = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    db.execute("PRAGMA busy_timeout=30000")
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise Denied("UNIQUE_CONSTRAINT_OR_NONCE_REPLAY") from exc
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


class LocalToySigner:
    """NOT independently controlled. HMAC is intentionally a fixture, NOT KMS."""
    def __init__(self, key=b"A123-TEST-KEY-NOT-SECURE", key_id="TEST-KEY-1", available=True):
        self.key = key
        self.key_id = key_id
        self.available = available

    def sign(self, payload):
        if not self.available:
            raise Uncertain("TOY_SIGNER_UNAVAILABLE")
        return hmac.new(self.key, canonical(payload).encode(), hashlib.sha256).hexdigest()

    def verify(self, payload, signature, key_id):
        if not self.available or key_id != self.key_id or type(signature) is not str:
            raise Denied("TOY_SIGNER_UNAVAILABLE_OR_WRONG_KEY")
        if not hmac.compare_digest(self.sign(payload), signature):
            raise Denied("TOY_SIGNATURE_MISMATCH")


class ToyVault:
    """SQLite fixture that models append constraints, NOT physical WORM/immutable storage."""
    def __init__(self, path, signer, *, online=True):
        self.path = str(path)
        self.signer = signer
        self.online = online
        with transaction(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY, intent_id TEXT NOT NULL, binding TEXT NOT NULL,
                kind TEXT NOT NULL, nonce TEXT NOT NULL, prev TEXT NOT NULL,
                commitment TEXT NOT NULL, signature TEXT NOT NULL, key_id TEXT NOT NULL,
                UNIQUE(intent_id,kind), UNIQUE(nonce))""")
            db.execute("CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK (id=1), seq INTEGER NOT NULL, head TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO metadata VALUES(1,0,'GENESIS')")

    def _gate(self):
        if not self.online:
            raise Denied("VAULT_UNAVAILABLE_FAIL_CLOSED")

    @staticmethod
    def _body(seq, intent, kind, nonce, prev):
        return {"seq":seq, "intent_id":intent.intent_id, "binding":intent.binding,
                "kind":kind, "nonce":nonce, "prev":prev}

    def _verify_history(self, db):
        prev = "GENESIS"
        counter = 0
        seen = set()
        for seq, intent_id, binding, kind, nonce, old, commitment, signature, key_id in db.execute(
            "SELECT seq,intent_id,binding,kind,nonce,prev,commitment,signature,key_id FROM events ORDER BY seq"):
            counter += 1
            if seq != counter or old != prev or (intent_id,kind) in seen:
                raise Denied("VAULT_CHAIN_FORK_OR_MISSING_EVENT")
            seen.add((intent_id,kind))
            body={"seq":seq,"intent_id":intent_id,"binding":binding,"kind":kind,"nonce":nonce,"prev":old}
            if digest(body) != commitment:
                raise Denied("VAULT_COMMITMENT_MISMATCH")
            self.signer.verify(body,signature,key_id)
            prev=commitment
        s,h=db.execute("SELECT seq,head FROM metadata WHERE id=1").fetchone()
        if (s,h)!=(counter,prev):
            raise Denied("VAULT_HEAD_OR_TRUNCATION_MISMATCH")

    def record(self, intent, kind, nonce, *, permit_existing=False):
        self._gate()
        if kind not in {"ANCHOR", "ISSUE_ONCE", "PRE_FENCE"}:
            raise Denied("EVENT_KIND_NOT_ALLOWED")
        if type(nonce) is not str or len(nonce)<10:
            raise Denied("NONCE_INVALID")
        with transaction(self.path) as db:
            self._verify_history(db)
            existing=db.execute("SELECT seq,nonce,commitment,signature,key_id,binding FROM events WHERE intent_id=? AND kind=?",(intent.intent_id,kind)).fetchone()
            if existing:
                if kind != "ANCHOR" or not permit_existing or existing[5]!=intent.binding:
                    raise Denied("VAULT_EVENT_ALREADY_RECORDED")
                return {"kind":kind,"seq":existing[0],"nonce":existing[1],"commitment":existing[2],"signature":existing[3],"key_id":existing[4],"intent_id":intent.intent_id,"binding":intent.binding}
            other=db.execute("SELECT binding,kind FROM events WHERE intent_id=? LIMIT 1",(intent.intent_id,)).fetchone()
            if other and other[0] != intent.binding:
                raise Denied("INTENT_BINDING_CONFLICT")
            if kind in {"ISSUE_ONCE","PRE_FENCE"}:
                if not db.execute("SELECT 1 FROM events WHERE intent_id=? AND kind='ANCHOR'",(intent.intent_id,)).fetchone():
                    raise Denied("ANCHOR_REQUIRED")
                if db.execute("SELECT 1 FROM events WHERE intent_id=? AND kind IN ('ISSUE_ONCE','PRE_FENCE')",(intent.intent_id,)).fetchone():
                    raise Denied("FINAL_DECISION_ALREADY_PRESENT")
            seq,head=db.execute("SELECT seq,head FROM metadata WHERE id=1").fetchone()
            body=self._body(seq+1,intent,kind,nonce,head)
            commitment=digest(body)
            signature=self.signer.sign(body) # failure rolls back transaction, NO external emission
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",(seq+1,intent.intent_id,intent.binding,kind,nonce,head,commitment,signature,self.signer.key_id))
            db.execute("UPDATE metadata SET seq=?,head=? WHERE id=1",(seq+1,commitment))
            return {"kind":kind,"seq":seq+1,"nonce":nonce,"commitment":commitment,"signature":signature,"key_id":self.signer.key_id,"intent_id":intent.intent_id,"binding":intent.binding}

    def attest(self,intent,kind):
        self._gate()
        with transaction(self.path) as db:
            self._verify_history(db)
            row=db.execute("SELECT seq,nonce,commitment,signature,key_id,binding FROM events WHERE intent_id=? AND kind=?",(intent.intent_id,kind)).fetchone()
            if not row or row[5]!=intent.binding:
                raise Denied("VAULT_ATTESTATION_UNAVAILABLE")
            return {"kind":kind,"seq":row[0],"nonce":row[1],"commitment":row[2],"signature":row[3],"key_id":row[4],"intent_id":intent.intent_id,"binding":intent.binding}

    def verify_receipt(self,intent,receipt,*,kind):
        if not isinstance(receipt,dict) or set(receipt)!={"kind","seq","nonce","commitment","signature","key_id","intent_id","binding"}:
            raise Denied("RECEIPT_STRUCTURE_INVALID")
        if receipt["kind"] != kind or receipt["intent_id"]!=intent.intent_id or receipt["binding"]!=intent.binding:
            raise Denied("RECEIPT_SCOPE_OR_KIND_MISMATCH")
        real=self.attest(intent,kind)  # fresh vault read, not proof solely from caller-provided blob
        if receipt != real:
            raise Denied("STALE_FORGED_OR_REPLAYED_ATTESTATION")
        # Admission evidence NEVER proves a provider-side effect.
        return {"status":"ADMISSION_ATTESTED_IN_TOY_VAULT","provider_effect_proven":False,"no_effect_fenced_post_handoff":False}


class FakeSender:
    def __init__(self,sink=None,behavior="ack"):
        self.sink = sink if sink is not None else []
        self.behavior=behavior

    def call(self,intent):
        self.sink.append(intent.binding)
        if self.behavior in {"timeout","429","5xx","connection_lost"}:
            raise Uncertain("FAKE_PROVIDER_"+self.behavior)
        return {"fixture_ack":True,"provider_effect_proven":False}


class AdmissionFixture:
    """Contract caller; every operation is synthetic and fails closed on ambiguity."""
    def __init__(self,ledger_path,vault,*,sender=None,enrolled=True):
        self.ledger_path=str(ledger_path)
        self.vault=vault
        self._sender=sender if sender is not None else FakeSender()
        if type(self._sender) is not FakeSender:
            raise Denied("ONLY_FAKE_SENDER_ALLOWED")
        self.enrolled=enrolled # test assumption, NOT external human attestation
        with transaction(self.ledger_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS intents (intent_id TEXT PRIMARY KEY,binding TEXT NOT NULL,state TEXT NOT NULL)")

    def _gate(self):
        if self.enrolled is not True:
            raise Denied("ENROLLMENT_NOT_PROVEN")
        self.vault._gate()

    def status(self,intent):
        self._gate()
        with transaction(self.ledger_path) as db:
            row=db.execute("SELECT binding,state FROM intents WHERE intent_id=?",(intent.intent_id,)).fetchone()
        if not row:return "ABSENT"
        if row[0] != intent.binding:raise Denied("IMMUTABLE_SCOPE_CONFLICT")
        return row[1]

    def prepare(self,intent,*,cut=None,nonce="PREPARE-NONCE-00001"):
        self._gate()
        with transaction(self.ledger_path) as db:
            row=db.execute("SELECT binding,state FROM intents WHERE intent_id=?",(intent.intent_id,)).fetchone()
            if row and row[0]!=intent.binding:raise Denied("IMMUTABLE_SCOPE_CONFLICT")
            if row and row[1] not in {"PENDING_ANCHOR","PREPARED"}:raise Denied("INTENT_CONSUMED")
            if not row:
                db.execute("INSERT INTO intents VALUES(?,?,?)",(intent.intent_id,intent.binding,"PENDING_ANCHOR"))
        if cut=="after_local_prepare":raise Uncertain("CUT_AFTER_LOCAL_PREPARE")
        receipt=self.vault.record(intent,"ANCHOR",nonce,permit_existing=True)
        if cut=="after_vault_anchor":raise Uncertain("CUT_AFTER_VAULT_ANCHOR")
        self.vault.verify_receipt(intent,receipt,kind="ANCHOR")
        with transaction(self.ledger_path) as db:
            res=db.execute("UPDATE intents SET state='PREPARED' WHERE intent_id=? AND binding=? AND state IN ('PENDING_ANCHOR','PREPARED')",(intent.intent_id,intent.binding))
            if res.rowcount!=1:raise Denied("PREPARE_STATE_CHANGED")
        if cut=="after_prepare_commit":raise Uncertain("CUT_AFTER_PREPARE_COMMIT")
        return receipt

    def issue_once(self,intent,*,cut=None,nonce="ISSUE-NONCE-0000001"):
        self._gate()
        # Check vault anchor before committing local irreversible marker.
        self.vault.attest(intent,"ANCHOR")
        with transaction(self.ledger_path) as db:
            row=db.execute("SELECT binding,state FROM intents WHERE intent_id=?",(intent.intent_id,)).fetchone()
            if not row or row[0]!=intent.binding or row[1]!="PREPARED":
                raise Denied("NO_NEW_ATTEMPT_AFTER_CONSUMPTION")
            res=db.execute("UPDATE intents SET state='UNKNOWN_CONSUMED' WHERE intent_id=? AND binding=? AND state='PREPARED'",(intent.intent_id,intent.binding))
            if res.rowcount!=1:raise Denied("ISSUE_ONCE_CAS_LOST")
        # NO RETRY even if crash here: no WORM receipt is proof of *absence*.
        if cut=="after_local_issue":raise Uncertain("CUT_AFTER_LOCAL_ISSUE")
        issue_receipt=self.vault.record(intent,"ISSUE_ONCE",nonce)
        if cut=="after_vault_issue":raise Uncertain("CUT_AFTER_VAULT_ISSUE")
        self.vault.verify_receipt(intent,issue_receipt,kind="ISSUE_ONCE")
        if cut=="before_sender":raise Uncertain("CUT_BEFORE_FAKE_SENDER")
        self._sender.call(intent)
        if cut=="after_sender":raise Uncertain("CUT_AFTER_FAKE_SENDER")
        return {"status":"UNKNOWN","admission_receipt":issue_receipt,"provider_effect_proven":False,"no_effect_fenced_post_handoff":False}

    def pre_fence(self,intent,*,nonce="FENCE-NONCE-0000001"):
        self._gate()
        self.vault.attest(intent,"ANCHOR")
        with transaction(self.ledger_path) as db:
            row=db.execute("SELECT binding,state FROM intents WHERE intent_id=?",(intent.intent_id,)).fetchone()
            if not row or row[0]!=intent.binding or row[1]!="PREPARED":
                raise Denied("NO_FENCE_AFTER_ISSUE_OR_UNKNOWN")
            db.execute("UPDATE intents SET state='UNKNOWN_CONSUMED' WHERE intent_id=?",(intent.intent_id,))
        # Fail closed on gap, even if PRE_FENCE receipt never materializes.
        proof=self.vault.record(intent,"PRE_FENCE",nonce)
        self.vault.verify_receipt(intent,proof,kind="PRE_FENCE")
        return {"status":"PRE_FENCE_TOY_ONLY","no_effect_fenced_post_handoff":False}


def production_eligible():
    return False
