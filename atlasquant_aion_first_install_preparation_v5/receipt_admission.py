"""AION V5 disposable receipt/nonce admission reference.

Local durability and crypto mathematics ONLY. Caller-owned pinned fixture is
not enrolled external custody. No network, no productive authenticator,
no installer, no Worker, no retry after uncertain outcomes.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any

from atlasquant_aion_first_install_preparation.contracts import digest_value, result as _base_result, integer, token
from atlasquant_aion_first_install_preparation_v3.ledger_storage import canonical, Refusal
from atlasquant_aion_first_install_preparation_v4.signed_anchors import (
    config_contract, pin_contract, pin_digest, query_contract,
    verify_fresh_read_reference,
)
from atlasquant_aion_first_install_preparation_v4.commitments import (
    commitment_contract, commitment_digest,
)

SCHEMA = "AION_V5_OFFLINE_SIGNED_READ_ADMISSION_ONLY"
DOMAIN = b"AION_V5_RECEIPT_EVENT\0"
LIMIT = 512
TABLES = {
    "context": "singleton INTEGER PRIMARY KEY CHECK(singleton=1),config_json TEXT NOT NULL,pin_json TEXT NOT NULL,expected_pin_digest TEXT NOT NULL",
    "meta": "singleton INTEGER PRIMARY KEY CHECK(singleton=1),floor_json TEXT NOT NULL,sequence INTEGER NOT NULL,head_digest TEXT NOT NULL",
    "nonces": "nonce TEXT PRIMARY KEY,operation_id TEXT NOT NULL UNIQUE,query_json TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('ISSUED','CONSUMED')),receipt_digest TEXT",
    "receipts": "nonce TEXT PRIMARY KEY,operation_id TEXT NOT NULL UNIQUE,sequence INTEGER NOT NULL UNIQUE,request_digest TEXT NOT NULL,commitment_digest TEXT NOT NULL,receipt_digest TEXT NOT NULL",
    "events": "sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,operation_id TEXT NOT NULL,nonce TEXT NOT NULL,body_digest TEXT NOT NULL,previous_digest TEXT NOT NULL,event_digest TEXT NOT NULL",
    "revocations": "kind TEXT NOT NULL CHECK(kind IN ('KEY','OPERATOR')),identifier TEXT NOT NULL,PRIMARY KEY(kind,identifier)",
}
ZERO = "0" * 64

def _out(state: str, reason: str, **details: Any) -> dict:
    # Base result puts untrusted/prohibited authority flags before/after details.
    out = _base_result(state, reason, **details)
    for key in ("installer_authorized","worker_authorized","owner_identity_verified",
                "external_anchor_verified","root_trust_verified",
                "latest_head_independently_verified","independent_custody_verified",
                "safe_to_resume","automatic_retry_allowed","billing_authorized"):
        out[key] = False
    out["independent_rollback_protection_verified"] = False
    out["local_reference_only"] = True
    return out

def _sha(data: Any) -> str:
    return sha256(data if isinstance(data, bytes) else canonical(data).encode("utf-8")).hexdigest()

def _event(prev: str, sequence: int, kind: str, operation_id: str, nonce: str, body: str) -> str:
    return sha256(DOMAIN + canonical([prev,sequence,kind,operation_id,nonce,body]).encode()).hexdigest()

def _verify(db: sqlite3.Connection) -> dict:
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables != set(TABLES) or db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise Refusal("INTEGRITY_OR_SCHEMA_INVALID")
        for name,ddl in TABLES.items():
            row=db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone()
            if not row or row[0] != "CREATE TABLE "+name+" ("+ddl+")":
                raise Refusal("SCHEMA_CONSTRAINT_CHANGED")
        ctx=db.execute("SELECT * FROM context WHERE singleton=1").fetchone()
        meta=db.execute("SELECT * FROM meta WHERE singleton=1").fetchone()
        if not ctx or not meta or not integer(meta["sequence"],0,LIMIT) or not digest_value(meta["head_digest"]):
            raise Refusal("CONTEXT_OR_HEAD_MISSING")
        if not digest_value(ctx["expected_pin_digest"]):
            raise Refusal("PIN_DIGEST_INVALID")
        config=json.loads(ctx["config_json"]);pin=json.loads(ctx["pin_json"]);floor=json.loads(meta["floor_json"])
        config_contract(config);pin_contract(pin);commitment_contract(floor)
        if canonical(config)!=ctx["config_json"] or canonical(pin)!=ctx["pin_json"] or canonical(floor)!=meta["floor_json"]:
            raise Refusal("NONCANONICAL_CONTEXT")
        if pin_digest(pin)!=ctx["expected_pin_digest"]:
            raise Refusal("PIN_MISMATCH")
        for k in ("owner_id","tenant_id","workspace_id","ledger_id","policy_id","policy_version","witness_id"):
            if pin[k] != config[k] or floor[k] != config[k]:
                raise Refusal("CONTEXT_SCOPE_MISMATCH")
        if floor["epoch"]!=config["epoch"]:
            raise Refusal("EPOCH_CHANGED_WITHOUT_CEREMONY")
        events=db.execute("SELECT * FROM events ORDER BY sequence LIMIT ?",(LIMIT+1,)).fetchall()
        if len(events)!=meta["sequence"] or len(events)>LIMIT:raise Refusal("EVENT_COUNT_MISMATCH")
        previous=ZERO
        for seq,ev in enumerate(events,1):
            if (ev["sequence"]!=seq or ev["previous_digest"]!=previous or
                ev["event_digest"]!=_event(previous,seq,ev["kind"],ev["operation_id"],ev["nonce"],ev["body_digest"])):
                raise Refusal("EVENT_CHAIN_INVALID")
            previous=ev["event_digest"]
        if previous!=meta["head_digest"]:raise Refusal("EVENT_HEAD_MISMATCH")
        row=db.execute("SELECT COUNT(*) FROM nonces").fetchone()[0]
        rc=db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
        rev=db.execute("SELECT COUNT(*) FROM revocations").fetchone()[0]
        if any(n>LIMIT for n in (row,rc,rev)):raise Refusal("ROW_BOUND")
        if db.execute("SELECT 1 FROM nonces WHERE length(query_json)>4096 LIMIT 1").fetchone():
            raise Refusal("QUERY_BOUND")
        if db.execute("SELECT 1 FROM nonces n JOIN receipts r ON n.nonce=r.nonce WHERE n.state!='CONSUMED' OR n.operation_id!=r.operation_id OR n.receipt_digest!=r.receipt_digest LIMIT 1").fetchone():
            raise Refusal("RECEIPT_NONCE_MISMATCH")
        if db.execute("SELECT 1 FROM receipts r LEFT JOIN nonces n ON n.nonce=r.nonce WHERE n.nonce IS NULL LIMIT 1").fetchone():
            raise Refusal("ORPHAN_RECEIPT")
        if db.execute("SELECT 1 FROM nonces WHERE state='CONSUMED' AND receipt_digest IS NULL LIMIT 1").fetchone():
            raise Refusal("CONSUMED_RECEIPT_ABSENT")
        for row in db.execute("SELECT query_json,nonce FROM nonces"):
            q=json.loads(row["query_json"])
            if canonical(query_contract(q))!=row["query_json"] or q["nonce"]!=row["nonce"]:
                raise Refusal("QUERY_BINDING_TAMPERED")
        return {"config":config,"pin":pin,"floor":floor,"sequence":meta["sequence"],"head_digest":previous,
                "expected_pin_digest":ctx["expected_pin_digest"]}
    except (KeyError,TypeError,ValueError,UnicodeError,RecursionError) as exc:
        raise Refusal("STORE_SCHEMA_OR_EVIDENCE_REJECTED") from None

class OfflineWitnessReceiptAdmission:
    """A distinct throwaway SQLite file, never a live independent witness.

    Bootstrap only with explicit fixture inputs; a missing existing file is
    never silently reinitialized in 'read' or admission calls. Creating a
    fresh lab fixture is an explicit constructor-only operation.
    """
    def __init__(self,path,*,config,pin,floor,timeout=1.0,bootstrap=False):
        self.path=Path(path).resolve()
        self.config=config_contract(config)
        self.pin=pin_contract(pin)
        self.floor=commitment_contract(floor)
        if type(timeout) not in (int,float) or type(timeout) is bool or not 0<=timeout<=2:
            raise ValueError("UNBOUNDED_TIMEOUT")
        self.timeout=float(timeout)
        if type(bootstrap) is not bool:raise ValueError("BOOTSTRAP_INVALID")
        if not bootstrap:return
        if self.path.exists():raise Refusal("NO_OVERWRITE_OR_REBOOTSTRAP")
        db=None
        try:
            db=self._connect(create=True)
            db.execute("PRAGMA journal_mode=WAL");db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            for name,ddl in TABLES.items():db.execute("CREATE TABLE "+name+" ("+ddl+")")
            db.execute("INSERT INTO context VALUES (1,?,?,?)",
                       (canonical(self.config),canonical(self.pin),pin_digest(self.pin)))
            db.execute("INSERT INTO meta VALUES (1,?,0,?)",(canonical(self.floor),ZERO))
            _verify(db)
            db.commit()
        except (sqlite3.Error,ValueError,TypeError,Refusal):
            if db is not None and db.in_transaction:db.rollback()
            raise Refusal("BOOTSTRAP_NOT_PROVEN") from None
        finally:
            if db is not None:db.close()

    def _connect(self,*,ro=False,create=False):
        mode="ro" if ro else "rwc" if create else "rw"
        db=sqlite3.connect(self.path.as_uri()+"?mode="+mode,uri=True,
                           timeout=self.timeout,isolation_level=None)
        db.row_factory=sqlite3.Row
        if ro:db.execute("PRAGMA query_only=ON")
        else:db.execute("PRAGMA synchronous=FULL")
        return db

    def _mutate(self,work):
        db=None;commit_attempted=False;out=None
        try:
            db=self._connect();db.execute("BEGIN IMMEDIATE")
            before=_verify(db)
            if before["config"]!=self.config or before["pin"]!=self.pin:
                raise Refusal("CALLER_BOUND_CONTEXT_MISMATCH")
            out=work(db,before)
            _verify(db)
            commit_attempted=True;db.commit()
        except Refusal:
            out=_out("UNKNOWN_OUTCOME" if commit_attempted else "BLOCKED",
                     "LOCAL_PRECONDITION_OR_COMMIT_UNCERTAIN_NO_RESEND")
        except sqlite3.IntegrityError:
            # A duplicate key or violated CHECK raised by the write statement
            # before commit is deterministic refusal, not ambiguous storage.
            out=_out("UNKNOWN_OUTCOME" if commit_attempted else "BLOCKED",
                     "SQLITE_CONSTRAINT_DENIED_NO_RETRY")
        except (sqlite3.Error,OSError,ValueError,KeyError,TypeError,OverflowError,RecursionError):
            out=_out("UNKNOWN_OUTCOME" if commit_attempted else "RECONCILIATION_REQUIRED",
                     "LOCAL_PERSISTENCE_UNCERTAIN_NO_RESEND")
        finally:
            if db is not None:
                try:
                    if db.in_transaction:db.rollback()
                except sqlite3.Error:
                    out=_out("UNKNOWN_OUTCOME","ROLLBACK_UNCERTAIN_NO_RESEND")
                try:db.close()
                except sqlite3.Error:
                    out=_out("UNKNOWN_OUTCOME","CLOSE_UNCERTAIN_NO_RESEND")
        return out

    def _append(self,db,old,kind,operation_id,nonce,body):
        seq=old["sequence"]+1
        if seq>LIMIT:raise Refusal("HISTORY_LIMIT")
        head=_event(old["head_digest"],seq,kind,operation_id,nonce,body)
        db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)",
                   (seq,kind,operation_id,nonce,body,old["head_digest"],head))
        db.execute("UPDATE meta SET sequence=?,head_digest=? WHERE singleton=1",(seq,head))
        return seq

    def issue_reference(self,query,*,operation_id):
        try:
            q=query_contract(query)
            if not token(operation_id) or len(canonical(q))>4096:
                raise Refusal("ISSUANCE_INPUT_INVALID")
        except (Refusal,ValueError,TypeError,KeyError):
            return _out("BLOCKED","ISSUANCE_INPUT_INVALID")
        def work(db,old):
            for key in ("owner_id","tenant_id","workspace_id","ledger_id","witness_id","policy_id","policy_version"):
                if q[key]!=old["config"][key]:raise Refusal("ISSUANCE_SCOPE_MISMATCH")
            if q["minimum_epoch"]!=old["config"]["epoch"] or q["key_id"]!=old["pin"]["key_id"] or q["key_generation"]!=old["pin"]["key_generation"] or q["root_provenance_digest"]!=old["pin"]["root_provenance_digest"]:
                raise Refusal("ISSUANCE_ROOT_MISMATCH")
            if db.execute("SELECT 1 FROM revocations WHERE (kind='KEY' AND identifier=?) OR (kind='OPERATOR' AND identifier=?)",
                          (old["pin"]["key_id"],old["pin"]["operator_alias"])).fetchone():
                raise Refusal("REVOKED_ROOT")
            db.execute("INSERT INTO nonces VALUES (?,?,?,'ISSUED',NULL)",(q["nonce"],operation_id,canonical(q)))
            seq=self._append(db,old,"ISSUE",operation_id,q["nonce"],_sha(q))
            return _out("REFERENCE_ISSUED_UNTRUSTED","LOCAL_FIXTURE_ONLY",local_sequence=seq)
        return self._mutate(work)

    def admit_reference(self,query,response,*,now):
        # Cryptographic verification and consumption occur under one local
        # BEGIN IMMEDIATE lock. The caller cannot override pinned floor/pin.
        try:q=query_contract(query)
        except (Refusal,ValueError,TypeError,KeyError):return _out("BLOCKED","QUERY_INVALID")
        def work(db,old):
            row=db.execute("SELECT * FROM nonces WHERE nonce=?",(q["nonce"],)).fetchone()
            if row is None or row["state"]!="ISSUED" or row["query_json"]!=canonical(q):
                raise Refusal("NOT_ISSUED_OR_REPLAY")
            revoked_keys=[r[0] for r in db.execute("SELECT identifier FROM revocations WHERE kind='KEY'")]
            revoked_operators=[r[0] for r in db.execute("SELECT identifier FROM revocations WHERE kind='OPERATOR'")]
            review=verify_fresh_read_reference(
                response,query=q,pin=old["pin"],expected_pin_digest=old["expected_pin_digest"],
                config=old["config"],floor=old["floor"],now=now,
                consumed_nonces=[],revoked_keys=revoked_keys,revoked_operators=revoked_operators)
            if review["state"]!="REFERENCE_FRESH_READ_MATH_UNTRUSTED":
                raise Refusal("SIGNED_READ_INVALID")
            commitment=review["commitment"]
            receipt_digest=_sha(response)
            request_digest=_sha(q)
            db.execute("UPDATE nonces SET state='CONSUMED',receipt_digest=? WHERE nonce=?",
                       (receipt_digest,q["nonce"]))
            seq=self._append(db,old,"ADMIT",row["operation_id"],q["nonce"],
                             _sha([request_digest,receipt_digest,commitment_digest(commitment)]))
            db.execute("INSERT INTO receipts VALUES (?,?,?,?,?,?)",
                       (q["nonce"],row["operation_id"],seq,request_digest,
                        commitment_digest(commitment),receipt_digest))
            db.execute("UPDATE meta SET floor_json=? WHERE singleton=1",(canonical(commitment),))
            return _out("REFERENCE_WRITE_ACK_UNTRUSTED","LOCAL_COMMIT_NEEDS_FRESH_READBACK",
                        operation_id=row["operation_id"],receipt_digest=receipt_digest)
        out=self._mutate(work)
        if out["state"]!="REFERENCE_WRITE_ACK_UNTRUSTED":return out
        return self.readback_reference(query["nonce"],expected_receipt_digest=out["receipt_digest"])

    def revoke_reference(self,kind,identifier,*,operation_id):
        if kind not in ("KEY","OPERATOR") or not token(identifier) or not token(operation_id):
            return _out("BLOCKED","REVOCATION_INPUT_INVALID")
        def work(db,old):
            if kind=="KEY" and identifier!=old["pin"]["key_id"]:raise Refusal("KEY_SCOPE_MISMATCH")
            if kind=="OPERATOR" and identifier!=old["pin"]["operator_alias"]:raise Refusal("OPERATOR_SCOPE_MISMATCH")
            db.execute("INSERT INTO revocations VALUES (?,?)",(kind,identifier))
            seq=self._append(db,old,"REVOKE",operation_id,identifier,_sha([kind,identifier]))
            return _out("REFERENCE_REVOCATION_UNTRUSTED","LOCAL_SIMULATED_REVOCATION_ONLY",local_sequence=seq)
        return self._mutate(work)

    def readback_reference(self,nonce,*,expected_receipt_digest):
        db=None;out=None
        try:
            if not digest_value(expected_receipt_digest) or not digest_value(nonce):
                raise Refusal("READ_REQUEST_INVALID")
            db=self._connect(ro=True);db.execute("BEGIN")
            state=_verify(db)
            if state["config"]!=self.config or state["pin"]!=self.pin:
                raise Refusal("CALLER_BOUND_CONTEXT_MISMATCH")
            row=db.execute("SELECT * FROM nonces WHERE nonce=?",(nonce,)).fetchone()
            receipt=db.execute("SELECT * FROM receipts WHERE nonce=?",(nonce,)).fetchone()
            if row is None or receipt is None:
                out=_out("RECONCILIATION_REQUIRED","RECEIPT_ABSENT_NO_RETRY")
            else:
                event=db.execute("SELECT * FROM events WHERE sequence=?",(receipt["sequence"],)).fetchone()
                expected_body=_sha([receipt["request_digest"],receipt["receipt_digest"],receipt["commitment_digest"]])
                valid=(row["state"]=="CONSUMED"
                    and receipt["receipt_digest"]==expected_receipt_digest
                    and row["receipt_digest"]==expected_receipt_digest
                    and receipt["operation_id"]==row["operation_id"]
                    and receipt["request_digest"]==_sha(json.loads(row["query_json"]))
                    and integer(receipt["sequence"],1,state["sequence"])
                    and event is not None and event["kind"]=="ADMIT"
                    and event["operation_id"]==row["operation_id"]
                    and event["nonce"]==nonce and event["body_digest"]==expected_body)
                if not valid:
                    out=_out("BLOCKED","CAUSAL_RECEIPT_CONFLICT")
                else:
                    out=_out("REFERENCE_DURABLE_RECEIPT_UNTRUSTED","LOCAL_RECEIPT_NOT_EXTERNAL_FRESHNESS",
                         local_receipt_verified=True,local_sequence=receipt["sequence"],
                         local_head_sequence=state["sequence"],nonce_consumed_locally=True)
        except Refusal:
            out=_out("BLOCKED","READ_INTEGRITY_OR_SCOPE_REJECTED")
        except (sqlite3.Error,ValueError,TypeError,KeyError,OSError,RecursionError):
            out=_out("UNKNOWN_OUTCOME","READBACK_UNAVAILABLE_NO_RETRY")
        finally:
            if db is not None:
                try:db.close()
                except sqlite3.Error:
                    out=_out("UNKNOWN_OUTCOME","READBACK_CLOSE_UNCERTAIN_NO_RETRY")
        return out
