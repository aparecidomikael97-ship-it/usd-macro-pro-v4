"""Bounded SQLite transaction/evidence substrate for the offline WebAuthn ledger.

No network or retry. Every call owns its native thread-affine connection.
Hash chains detect accidental/tampered inconsistency, NOT privileged rollback.
"""
import json
from pathlib import Path
import sqlite3

from atlasquant_aion_first_install_preparation.contracts import (
    ContractError, digest, digest_value, exact, integer, result, token)

ZERO = "0" * 64
LIMIT = 512
TABLES = {
    "config": "singleton INTEGER PRIMARY KEY CHECK(singleton=1),scope_json TEXT NOT NULL",
    "meta": "singleton INTEGER PRIMARY KEY CHECK(singleton=1),sequence INTEGER NOT NULL,head_digest TEXT NOT NULL",
    "credentials": "credential_id TEXT NOT NULL,generation INTEGER NOT NULL,device_id TEXT NOT NULL,key_hex TEXT NOT NULL,key_sha256 TEXT NOT NULL,backup_eligible INTEGER NOT NULL,sign_count INTEGER NOT NULL,backup_state INTEGER,expires_at INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(credential_id,generation)",
    "challenges": "challenge TEXT PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,nonce_hex TEXT UNIQUE NOT NULL,intent_json TEXT NOT NULL,intent_digest TEXT NOT NULL,credential_id TEXT NOT NULL,generation INTEGER NOT NULL,rp_id TEXT NOT NULL,origin TEXT NOT NULL,issued_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,state TEXT NOT NULL,attempt_id TEXT",
    "attempts": "attempt_id TEXT PRIMARY KEY,challenge TEXT UNIQUE NOT NULL,intent_digest TEXT NOT NULL,assertion_digest TEXT NOT NULL,request_digest TEXT NOT NULL,state TEXT NOT NULL,consumed_counter INTEGER",
    "receipts": "namespace TEXT NOT NULL,operation_id TEXT NOT NULL,request_digest TEXT NOT NULL,sequence INTEGER UNIQUE NOT NULL,PRIMARY KEY(namespace,operation_id)",
    "events": "sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload_json TEXT NOT NULL,previous_digest TEXT NOT NULL,state_digest TEXT NOT NULL,event_digest TEXT NOT NULL",
}
ORDERS = {"config":"singleton","credentials":"credential_id,generation",
    "challenges":"challenge","attempts":"attempt_id","receipts":"sequence"}
NAMESPACES = {"REGISTER","ROTATE","REVOKE","ISSUE","ADMISSION","CONSUMPTION","QUARANTINE"}
COLUMNS = {
    "config":("singleton","scope_json"),"meta":("singleton","sequence","head_digest"),
    "credentials":("credential_id","generation","device_id","key_hex","key_sha256","backup_eligible","sign_count","backup_state","expires_at","state"),
    "challenges":("challenge","request_id","nonce_hex","intent_json","intent_digest","credential_id","generation","rp_id","origin","issued_at","expires_at","state","attempt_id"),
    "attempts":("attempt_id","challenge","intent_digest","assertion_digest","request_digest","state","consumed_counter"),
    "receipts":("namespace","operation_id","request_digest","sequence"),
    "events":("sequence","kind","payload_json","previous_digest","state_digest","event_digest"),
}

class Refusal(ContractError):
    """Fixed local reason codes only."""

def scope_contract(value):
    exact(value,{"owner_id","tenant_id","workspace_id"})
    if not all(token(value[k]) and value[k].startswith("fixture-") for k in value):
        raise Refusal("DISPOSABLE_SCOPE_ALIASES_REQUIRED")
    return dict(value)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)

def _rows(db,table,order):
    # SQLite checks lengths BEFORE materializing a caller-restored text/BLOB.
    columns=[r[1] for r in db.execute("PRAGMA table_info("+table+")")]
    lengths="+".join("coalesce(length("+c+"),0)" for c in columns)
    if db.execute("SELECT 1 FROM "+table+" WHERE "+lengths+">32768 LIMIT 1").fetchone():
        raise Refusal("ROW_BOUND_EXCEEDED")
    rows=db.execute("SELECT * FROM "+table+" ORDER BY "+order+" LIMIT ?",(LIMIT+1,)).fetchall()
    if len(rows)>LIMIT:
        raise Refusal("HISTORY_BOUND_EXCEEDED")
    return [dict(r) for r in rows]

def state_digest(db):
    return digest({t:_rows(db,t,order) for t,order in ORDERS.items()})

def verify_locked(db,scope):
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables!=set(TABLES) or db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
        raise Refusal("STORE_INTEGRITY_INVALID")
    for table,columns in COLUMNS.items():
        if tuple(r[1] for r in db.execute("PRAGMA table_info("+table+")"))!=columns:
            raise Refusal("SCHEMA_COLUMNS_INVALID")
    config=db.execute("SELECT * FROM config WHERE singleton=1").fetchone()
    if config is None or config["scope_json"]!=canonical(scope):
        raise Refusal("STORE_SCOPE_MISMATCH")
    meta=db.execute("SELECT * FROM meta WHERE singleton=1").fetchone()
    if meta is None or not integer(meta["sequence"],0,LIMIT) or not digest_value(meta["head_digest"]):
        raise Refusal("HEAD_INVALID")
    previous=ZERO;events=_rows(db,"events","sequence")
    for number,event in enumerate(events,1):
        try:payload=json.loads(event["payload_json"])
        except (TypeError,ValueError):raise Refusal("EVENT_INVALID") from None
        body={k:event[k] for k in ("sequence","kind","payload_json","previous_digest","state_digest")}
        if (event["sequence"]!=number or event["kind"] not in NAMESPACES
                or event["previous_digest"]!=previous or len(event["payload_json"])>1024
                or event["payload_json"]!=canonical(payload)
                or not digest_value(event["state_digest"]) or digest(body)!=event["event_digest"]):
            raise Refusal("EVENT_CHAIN_INVALID")
        previous=event["event_digest"]
    if meta["sequence"]!=len(events) or meta["head_digest"]!=previous:
        raise Refusal("HEAD_CHAIN_MISMATCH")
    current=state_digest(db)
    if not events and any(db.execute("SELECT 1 FROM "+t+" LIMIT 1").fetchone() for t in ("credentials","challenges","attempts","receipts")):
        raise Refusal("UNTRACKED_BOOTSTRAP_STATE")
    if events and events[-1]["state_digest"]!=current:
        raise Refusal("CURRENT_STATE_EVIDENCE_MISMATCH")
    receipts=_rows(db,"receipts","sequence")
    if len(receipts)!=len(events):raise Refusal("RECEIPT_EVENT_COUNT_MISMATCH")
    for receipt,event in zip(receipts,events):
        if (receipt["sequence"]!=event["sequence"] or receipt["namespace"]!=event["kind"]
                or not token(receipt["operation_id"]) or not digest_value(receipt["request_digest"])
                or json.loads(event["payload_json"])!={"operation_id":receipt["operation_id"],"request_digest":receipt["request_digest"]}):
            raise Refusal("CAUSAL_RECEIPT_MISMATCH")
    # Semantic registry monotonicity, in addition to digest consistency.
    prior={};active={}
    for row in _rows(db,"credentials","credential_id,generation"):
        cid=row["credential_id"]
        if (not token(cid) or row["generation"]!=prior.get(cid,0)+1
                or row["state"] not in ("ACTIVE","REVOKED","RETIRED")
                or not integer(row["sign_count"],0,2**32-1)
                or row["backup_eligible"] not in (0,1) or row["backup_state"] not in (None,0,1)
                or row["backup_state"]==1 and row["backup_eligible"]!=1):
            raise Refusal("CREDENTIAL_HISTORY_INVALID")
        if row["state"]=="ACTIVE":
            if cid in active:raise Refusal("MULTIPLE_ACTIVE_GENERATIONS")
            active[cid]=row["generation"]
        prior[cid]=row["generation"]
    if any(active[cid]!=prior[cid] for cid in active):raise Refusal("ACTIVE_GENERATION_DOWNGRADE")
    for row in _rows(db,"challenges","challenge"):
        if row["state"] not in ("ISSUED","ATTEMPT_PENDING","CONSUMED","QUARANTINED"):
            raise Refusal("CHALLENGE_STATE_INVALID")
        attempt=db.execute("SELECT * FROM attempts WHERE challenge=?",(row["challenge"],)).fetchone()
        if row["state"]=="ISSUED":
            if row["attempt_id"] is not None or attempt is not None:raise Refusal("ISSUED_HAS_ATTEMPT")
        elif (attempt is None or row["attempt_id"]!=attempt["attempt_id"]
                or row["intent_digest"]!=attempt["intent_digest"]
                or attempt["state"]!={"ATTEMPT_PENDING":"PENDING","CONSUMED":"CONSUMED","QUARANTINED":"QUARANTINED"}[row["state"]]):
            raise Refusal("ATTEMPT_CHALLENGE_MISMATCH")
        if attempt is not None:
            namespace="CONSUMPTION" if attempt["state"]=="CONSUMED" else "QUARANTINE" if attempt["state"]=="QUARANTINED" else "ADMISSION"
            receipt=db.execute("SELECT request_digest FROM receipts WHERE namespace=? AND operation_id=?",(namespace,attempt["attempt_id"])).fetchone()
            if receipt is None or receipt[0]!=attempt["request_digest"]:
                raise Refusal("ATTEMPT_RECEIPT_ABSENT_OR_UNBOUND")
            if attempt["state"]=="CONSUMED":
                credential=db.execute("SELECT sign_count FROM credentials WHERE credential_id=? AND generation=?",(row["credential_id"],row["generation"])).fetchone()
                if not integer(attempt["consumed_counter"],0,2**32-1) or credential is None or credential[0]<attempt["consumed_counter"]:
                    raise Refusal("CONSUMED_COUNTER_INCONSISTENT")
            elif attempt["consumed_counter"] is not None:raise Refusal("UNCONSUMED_COUNTER_PRESENT")
    if db.execute("SELECT 1 FROM attempts a LEFT JOIN challenges c ON a.challenge=c.challenge WHERE c.challenge IS NULL LIMIT 1").fetchone():
        raise Refusal("ORPHAN_ATTEMPT")
    return dict(meta)

def append_event(db,namespace,operation_id,request_digest):
    if namespace not in NAMESPACES or not token(operation_id) or not digest_value(request_digest):
        raise Refusal("CAUSAL_ID_INVALID")
    old=db.execute("SELECT * FROM receipts WHERE namespace=? AND operation_id=?",(namespace,operation_id)).fetchone()
    if old is not None:raise Refusal("OPERATION_ID_ALREADY_USED_NO_RETRY")
    meta=db.execute("SELECT * FROM meta WHERE singleton=1").fetchone()
    seq=meta["sequence"]+1
    if seq>LIMIT:raise Refusal("HISTORY_BOUND_EXCEEDED")
    db.execute("INSERT INTO receipts VALUES (?,?,?,?)",(namespace,operation_id,request_digest,seq))
    payload=canonical({"operation_id":operation_id,"request_digest":request_digest})
    body=dict(sequence=seq,kind=namespace,payload_json=payload,previous_digest=meta["head_digest"],state_digest=state_digest(db))
    head=digest(body)
    db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",(seq,namespace,payload,meta["head_digest"],body["state_digest"],head))
    db.execute("UPDATE meta SET sequence=?,head_digest=? WHERE singleton=1",(seq,head))
    return seq

class LedgerStorage:
    def __init__(self,path,*,scope,timeout=1):
        self.path=Path(path).resolve();self.scope=scope_contract(scope)
        if type(timeout) not in (int,float) or type(timeout) is bool or not 0<=timeout<=2:
            raise Refusal("BOUNDED_TIMEOUT_REQUIRED")
        self.timeout=timeout
        db=None
        try:
            db=self.connect(create=True)
            db.execute("PRAGMA journal_mode=WAL");db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            found={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if found and found!=set(TABLES):raise Refusal("UNKNOWN_SCHEMA_NO_REBOOTSTRAP")
            if not found:
                for name,ddl in TABLES.items():db.execute("CREATE TABLE "+name+" ("+ddl+")")
                db.execute("INSERT INTO config VALUES (1,?)",(canonical(self.scope),))
                db.execute("INSERT INTO meta VALUES (1,0,?)",(ZERO,))
            verify_locked(db,self.scope);db.commit()
        except (sqlite3.Error,ValueError,TypeError,OSError):
            if db is not None:
                try:
                    if db.in_transaction:db.rollback()
                except sqlite3.Error:pass
            raise Refusal("OFFLINE_STORE_UNAVAILABLE_NO_REBOOTSTRAP") from None
        finally:
            if db is not None:db.close()

    def connect(self,*,read_only=False,create=False):
        mode="ro" if read_only else "rwc" if create else "rw"
        db=sqlite3.connect(self.path.as_uri()+"?mode="+mode,uri=True,
                          timeout=self.timeout,isolation_level=None)
        try:
            db.row_factory=sqlite3.Row
            if read_only:db.execute("PRAGMA query_only=ON")
            else:db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error:
            db.close();raise

    def transaction(self,callback):
        db=None;commit_attempted=False;out=None
        try:
            db=self.connect();db.execute("BEGIN IMMEDIATE");verify_locked(db,self.scope)
            out=callback(db)
            verify_locked(db,self.scope)
            commit_attempted=True;db.commit()
        except Refusal:
            out=result("BLOCKED","LEDGER_CONTRACT_OR_INTEGRITY_REJECTED")
            if db is not None:
                try:
                    if db.in_transaction:db.rollback()
                except sqlite3.Error:out=result("UNKNOWN_OUTCOME","ROLLBACK_UNCERTAIN_NO_RETRY")
        except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError):
            out=result("UNKNOWN_OUTCOME" if commit_attempted else "RECONCILIATION_REQUIRED",
                       "SQLITE_OUTCOME_UNPROVEN_NO_RETRY")
            if db is not None:
                try:
                    if db.in_transaction:db.rollback()
                except sqlite3.Error:out=result("UNKNOWN_OUTCOME","ROLLBACK_UNCERTAIN_NO_RETRY")
        finally:
            if db is not None:
                try:db.close()
                except sqlite3.Error:out=result("UNKNOWN_OUTCOME","CLOSE_ACK_UNCERTAIN_NO_RETRY")
        return out

def read_receipt_reference(path,*,scope,namespace,operation_id,expected_request_digest,
                           minimum_sequence,timeout=1):
    """Independent connection, mode=ro, no constructor/claim/write/retry."""
    db=None;out=None
    try:
        scope=scope_contract(scope)
        if (namespace not in NAMESPACES or not token(operation_id)
                or not digest_value(expected_request_digest) or not integer(minimum_sequence,0,LIMIT)):
            raise Refusal("READ_EXPECTATION_INVALID")
        reader=object.__new__(LedgerStorage);reader.path=Path(path).resolve();reader.scope=scope
        if type(timeout) not in (int,float) or not 0<=timeout<=2:raise Refusal("TIMEOUT_INVALID")
        reader.timeout=timeout;db=reader.connect(read_only=True);db.execute("BEGIN")
        head=verify_locked(db,scope)
        if head["sequence"]<minimum_sequence:raise Refusal("HEAD_REGRESSED")
        row=db.execute("SELECT * FROM receipts WHERE namespace=? AND operation_id=?",(namespace,operation_id)).fetchone()
        if row is None:out=result("RECONCILIATION_REQUIRED","NO_CAUSAL_RECEIPT_NO_RETRY")
        elif row["request_digest"]!=expected_request_digest:out=result("BLOCKED","CAUSAL_PAYLOAD_CONFLICT")
        else:
            details={}
            if namespace=="CONSUMPTION":
                attempt=db.execute("SELECT * FROM attempts WHERE attempt_id=?",(operation_id,)).fetchone()
                if attempt is None or attempt["state"]!="CONSUMED" or attempt["request_digest"]!=expected_request_digest:
                    raise Refusal("CONSUMPTION_CAUSAL_EFFECT_NOT_FOUND")
                details=dict(reference_sign_count=attempt["consumed_counter"],historical_consumption_only=True,
                    counter_assurance="NONE_FOR_ZERO" if attempt["consumed_counter"]==0 else "FIXTURE_INCREMENT_ONLY")
            out=result("REFERENCE_DURABLE_RECEIPT_UNTRUSTED","LOCAL_FILE_NOT_EXTERNAL_AUTHORITY",
                operation_kind=namespace,operation_sequence=row["sequence"],local_head_sequence=head["sequence"],
                local_head_digest=head["head_digest"],local_persistence_verified=True,
                cloning_absence_verified=False,independent_rollback_protection_verified=False,**details)
    except Refusal:
        out=result("BLOCKED","READ_CONTRACT_OR_INTEGRITY_REJECTED")
    except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,RecursionError):
        out=result("UNKNOWN_OUTCOME","READBACK_UNAVAILABLE_NO_RETRY")
    finally:
        if db is not None:
            try:db.close()
            except sqlite3.Error:out=result("UNKNOWN_OUTCOME","READ_CLOSE_UNCERTAIN_NO_RETRY")
    return out
