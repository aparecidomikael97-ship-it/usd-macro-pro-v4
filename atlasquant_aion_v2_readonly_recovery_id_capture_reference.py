"""AION V2 durable recovery-ID capture + GET-path *planner*, REFERENCE ONLY.

This is NOT an HTTP client. It does not perform GET, POST, signing, owner
authentication, billing or even a real provider response capture. The test
caller supplies the alleged identifier and 'received' event: this is not
provider provenance. Storage is local SQLite and fully restorable; all
production authority flags remain false. No output may be used as a network
capability, paid dispatch receipt, or safe re-POST decision.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    ReferenceOneShotUnknownOutcomeJournal, STATE_CLAIMED, STATE_UNKNOWN,
    _valid_intent,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    local_journal_intent_commitment,
)
from atlasquant_aion_v2_provider_recovery_capability_reference import (
    MODE_OPENAI_BACKGROUND, MODE_OPENAI_STORED, MODE_ANTHROPIC_BATCH,
    READ_CANDIDATE, review_provider_read_only_recovery_reference,
)

SCHEMA="ATLASQUANT_AION_V2_LOCAL_READ_ONLY_RECOVERY_CAPTURE_REFERENCE_V1"
CAPTURE_SCHEMA="ATLASQUANT_AION_V2_SIMULATED_PROVIDER_ID_OBSERVATION_V1"
CAPTURED="LOCAL_PROVIDER_IDENTIFIER_CAPTURE_MATH_ONLY_UNTRUSTED"
EXISTING="EXACT_LOCAL_CAPTURE_ALREADY_STORED_UNTRUSTED"
GET_PLAN="FIXED_PATH_GET_PLAN_ONLY_NO_NETWORK_OR_AUTHORITY"
_ALLOWED_MODES={MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED,MODE_ANTHROPIC_BATCH}
_LOCATOR_KEYS={"response_id","batch_id","batch_custom_id","diagnostic_request_id"}
_CAPTURE_KEYS={
    "schema","source_kind","provider","mode","owner_id","tenant_id",
    "workspace_id","nonce_hex","signed_v2_intent_sha256",
    "full_provider_request_sha256","key_registry_roster_sha256",
    "claim_sequence","documented_retention_opt_in","locator",
}
_CAPTURE_SOURCE="CI_SYNTHETIC_PROVIDER_ID_ALREADY_RECEIVED"
_SAFE_ID=re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_HASH=re.compile(r"[a-f0-9]{64}\Z")
_NO_AUTHORITY={
    "reference_only":True,
    "real_response_id_captured":False,
    "real_response_id_provenance_verified":False,
    "real_owner_identity_verified":False,
    "owner_presence_verified":False,
    "trusted_witness_heads_live_verified":False,
    "journal_externally_anchored":False,
    "cross_store_atomicity_verified":False,
    "provider_object_retrieved":False,
    "provider_idempotent_post_verified":False,
    "paid_model_post_authorized":False,
    "paid_model_post_sent":False,
    "billing_settlement_verified":False,
    "actual_charge_verified":False,
    "automatic_retry_permitted":False,
    "same_nonce_reusable":False,
    "network_called":False,
    "get_performed":False,
    "installer_authorized":False,
    "safe_to_resume":False,
}


def _canon(v: Any) -> str:
    return json.dumps(
        v, sort_keys=True, separators=(",",":"),
        ensure_ascii=False, allow_nan=False,
    )


def _digest(v: Any) -> str:
    return sha256(_canon(v).encode("utf-8")).hexdigest()


def _hex(v: Any) -> bool:
    return type(v) is str and bool(_HASH.fullmatch(v))


def _valid_capture(v: Any) -> bool:
    if type(v) is not dict or set(v)!=_CAPTURE_KEYS:
        return False
    if (v["schema"]!=CAPTURE_SCHEMA or v["source_kind"]!=_CAPTURE_SOURCE
        or type(v["mode"]) is not str
        or v["mode"] not in _ALLOWED_MODES
        or type(v["claim_sequence"]) is not int or v["claim_sequence"]<2
        or type(v["documented_retention_opt_in"]) is not bool
        or any(type(v[k]) is not str or not _SAFE_ID.fullmatch(v[k])
               for k in ("provider","owner_id","tenant_id","workspace_id"))
        or any(not _hex(v[k]) for k in (
            "nonce_hex","signed_v2_intent_sha256",
            "full_provider_request_sha256","key_registry_roster_sha256",
        ))
        or type(v["locator"]) is not dict
        or set(v["locator"])!=_LOCATOR_KEYS
        or any(type(x) is not str for x in v["locator"].values())):
        return False
    # The enclosing capability policy validates which ID fields are
    # appropriate; path construction separately permits strict tokens only.
    return True


def _out(state:str,reason:str,*,seq:int=0,paths:Any=None)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "local_sequence":seq,
        "relative_get_paths_for_offline_review":paths if state==GET_PLAN else [],
        "must_not_automatically_retry":True,
        **_NO_AUTHORITY,
    }


def _journal_claim(journal:Any,intent:Any):
    if (type(journal) is not ReferenceOneShotUnknownOutcomeJournal
        or type(intent) is not dict
        or not _valid_intent(intent,journal.config)):
        raise ValueError("exact signed V2 synthetic intent/journal required")
    head=local_journal_intent_commitment(journal,intent=intent)
    if head["intent_state"] not in (STATE_CLAIMED, STATE_UNKNOWN):
        raise ValueError("provider identifier requires possible dispatch claim")
    if head["claim_sequence"]<2:
        raise ValueError("invalid local dispatch claim sequence")
    return head


def _policy_intent(capture:Any,journal:Any):
    return {
        "provider":capture["provider"],"mode":capture["mode"],
        "owner_id":capture["owner_id"],"tenant_id":capture["tenant_id"],
        "workspace_id":capture["workspace_id"],"nonce_hex":capture["nonce_hex"],
        "signed_intent_sha256":capture["signed_v2_intent_sha256"],
        "full_provider_request_sha256":capture["full_provider_request_sha256"],
        "journal_state":STATE_UNKNOWN,
        "documented_retention_opt_in":capture["documented_retention_opt_in"],
        "transport_auto_retry_enabled":False,
    }


def _review_capture(journal:Any,intent:Any,capture:Any)->tuple[str,Any]:
    if not _valid_capture(capture):
        return "INVALID_CAPTURABLE_ID_OBSERVATION",None
    try:
        head=_journal_claim(journal,intent)
    except (ValueError,TypeError,sqlite3.Error,OverflowError):
        return "JOURNAL_CLAIM_ABSENT_RESTORED_OR_CORRUPT",None
    if (any(capture[k]!=intent.get(k) for k in (
            "owner_id","tenant_id","workspace_id","nonce_hex",
            "signed_v2_intent_sha256","full_provider_request_sha256",
            "key_registry_roster_sha256"
        ))
        or capture["claim_sequence"]!=head["claim_sequence"]):
        return "CLAIM_INTENT_SCOPE_OR_DIGEST_REBOUND",None
    preflight=review_provider_read_only_recovery_reference(
        intent=_policy_intent(capture,journal),locator=capture["locator"],
    )
    if preflight["state"]!=READ_CANDIDATE:
        return "PROVIDER_MODE_ID_OR_RETENTION_NOT_RECOVERABLE",None
    if capture["mode"] in (MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED):
        if not _SAFE_ID.fullmatch(capture["locator"]["response_id"]):
            return "UNSAFE_PROVIDER_ID_PATH_SEGMENT",None
    if capture["mode"]==MODE_ANTHROPIC_BATCH:
        if (not _SAFE_ID.fullmatch(capture["locator"]["batch_id"])
            or not _SAFE_ID.fullmatch(capture["locator"]["batch_custom_id"])):
            return "UNSAFE_BATCH_ID_OR_CUSTOM_ID",None
    return "",head


class ReferenceDurableRecoveryIdCapture:
    """A *local* receipt of an alleged ID; never proof of provider response.

    One durable local capture per nonce. This file, journal and both signing
    heads may all be restored, so this is NOT production antirollback.
    """

    def __init__(self,path:str|Path,*,journal:Any):
        if type(journal) is not ReferenceOneShotUnknownOutcomeJournal:
            raise ValueError("exact synthetic dispatch journal required")
        self.config=dict(journal.config)
        self.db=sqlite3.connect(str(path),timeout=10,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        try:
            old={r[0] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            expected={"aion_recovery_policy_ref","aion_recovery_ids_ref"}
            if old and old!=expected:
                raise ValueError("unknown/partial capture journal schema")
            self.db.execute("PRAGMA busy_timeout=10000")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS aion_recovery_policy_ref(
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  policy_json TEXT NOT NULL,sequence INTEGER NOT NULL
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS aion_recovery_ids_ref(
                  nonce_hex TEXT PRIMARY KEY,
                  signed_v2_intent_sha256 TEXT UNIQUE NOT NULL,
                  capture_json TEXT NOT NULL,
                  capture_sha256 TEXT NOT NULL,
                  sequence INTEGER NOT NULL UNIQUE
                )
            """)
            self.db.execute("BEGIN IMMEDIATE")
            row=self.db.execute(
                "SELECT policy_json FROM aion_recovery_policy_ref"
                " WHERE singleton=1",
            ).fetchone()
            if row is None:
                if old:
                    raise ValueError("existing reference registry requires policy")
                self.db.execute(
                    "INSERT INTO aion_recovery_policy_ref VALUES (1,?,0)",
                    (_canon(self.config),),
                )
            self._verify_locked()
            self.db.commit()
        except Exception:
            if self.db.in_transaction:self.db.rollback()
            self.db.close()
            raise

    def _verify_locked(self):
        if self.db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("local capture DB integrity failure")
        row=self.db.execute(
            "SELECT * FROM aion_recovery_policy_ref WHERE singleton=1"
        ).fetchone()
        if row is None or row["policy_json"]!=_canon(self.config):
            raise ValueError("local capture immutable policy mismatch")
        seq=row["sequence"]
        if type(seq) is not int or seq<0:
            raise ValueError("capture sequence malformed")
        rows=self.db.execute(
            "SELECT * FROM aion_recovery_ids_ref ORDER BY sequence"
        ).fetchall()
        if seq!=len(rows):
            raise ValueError("capture sequence rollback or gap")
        for index,item in enumerate(rows,1):
            try:cap=json.loads(item["capture_json"])
            except (ValueError,TypeError):raise ValueError("invalid capture JSON")
            if (not _valid_capture(cap)
                or cap["owner_id"]!=self.config["owner_id"]
                or cap["tenant_id"]!=self.config["tenant_id"]
                or cap["workspace_id"]!=self.config["workspace_id"]
                or item["sequence"]!=index
                or item["nonce_hex"]!=cap["nonce_hex"]
                or item["signed_v2_intent_sha256"]!=cap["signed_v2_intent_sha256"]
                or item["capture_json"]!=_canon(cap)
                or item["capture_sha256"]!=_digest(cap)):
                raise ValueError("local recovery-ID capture tampered")
        return seq

    def _txn(self,callback):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            seq=self._verify_locked()
            out=callback(seq)
            self.db.commit()
            return out
        except (sqlite3.Error,ValueError,TypeError,OverflowError):
            if self.db.in_transaction:self.db.rollback()
            return _out("BLOCKED","CAPTURE_STORAGE_UNAVAILABLE_OR_TAMPERED")

    def capture_reference_only(
        self,*,journal:Any,intent:Any,observed_capture:Any,
    )->dict[str,Any]:
        if type(journal) is not ReferenceOneShotUnknownOutcomeJournal or journal.config!=self.config:
            return _out("BLOCKED","DISPATCH_JOURNAL_POLICY_MISMATCH")
        reason,_=_review_capture(journal,intent,observed_capture)
        if reason:return _out("BLOCKED",reason)
        digest=_digest(observed_capture)
        def write(seq):
            prior=self.db.execute(
                "SELECT * FROM aion_recovery_ids_ref"
                " WHERE nonce_hex=? OR signed_v2_intent_sha256=?",
                (observed_capture["nonce_hex"],
                 observed_capture["signed_v2_intent_sha256"]),
            ).fetchall()
            if prior:
                if len(prior)==1 and prior[0]["capture_sha256"]==digest:
                    return _out(EXISTING,"EXACT_CAPTURE_IS_READ_ONLY_NO_NETWORK",seq=seq)
                return _out("BLOCKED","CAPTURE_NONCE_SIGNED_INTENT_OR_ID_REBOUND",seq=seq)
            nxt=seq+1
            self.db.execute(
                "INSERT INTO aion_recovery_ids_ref VALUES (?,?,?,?,?)",
                (observed_capture["nonce_hex"],
                 observed_capture["signed_v2_intent_sha256"],
                 _canon(observed_capture),digest,nxt),
            )
            self.db.execute(
                "UPDATE aion_recovery_policy_ref SET sequence=? WHERE singleton=1",
                (nxt,),
            )
            self._verify_locked()
            return _out(CAPTURED,
                "ALLEGED_ID_CAPTURED_LOCALLY_NO_AUTHENTIC_PROVIDER_RECEIPT",
                seq=nxt)
        return self._txn(write)

    def plan_recovery_get_reference_only(
        self,*,journal:Any,intent:Any,
    )->dict[str,Any]:
        if type(journal) is not ReferenceOneShotUnknownOutcomeJournal or journal.config!=self.config:
            return _out("BLOCKED","DISPATCH_JOURNAL_POLICY_MISMATCH")
        def read(seq):
            rows=self.db.execute(
                "SELECT * FROM aion_recovery_ids_ref WHERE nonce_hex=?",
                (intent.get("nonce_hex") if type(intent) is dict else None,),
            ).fetchall()
            if len(rows)!=1:
                return _out("BLOCKED","NO_PREVIOUSLY_STORED_RESPONSE_ID",seq=seq)
            capture=json.loads(rows[0]["capture_json"])
            reason,_=_review_capture(journal,intent,capture)
            if reason:return _out("BLOCKED",reason,seq=seq)
            if capture["mode"] in (MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED):
                paths=["/v1/responses/"+capture["locator"]["response_id"]]
            elif capture["mode"]==MODE_ANTHROPIC_BATCH:
                bid=capture["locator"]["batch_id"]
                paths=["/v1/messages/batches/"+bid,
                       "/v1/messages/batches/"+bid+"/results"]
            else:
                return _out("BLOCKED","NO_FIXED_SAFE_GET_ROUTE",seq=seq)
            # Only path strings, NEVER origin/host/headers/network capability.
            return _out(GET_PLAN,"OFFLINE_METHOD_GET_ONLY_NO_TRANSPORT",
                        seq=seq,paths=[{"method":"GET","relative_path":p}
                                       for p in paths])
        return self._txn(read)

    def local_snapshot_reference_only(self):
        def read(seq):
            rows=self.db.execute(
                "SELECT * FROM aion_recovery_ids_ref ORDER BY sequence"
            ).fetchall()
            data={"schema":SCHEMA,"policy":self.config,
                  "sequence":seq,"captures":[dict(x) for x in rows]}
            out=_out("LOCAL_CAPTURE_SNAPSHOT_UNTRUSTED",
                     "NOT_INDEPENDENTLY_PROTECTED_FROM_ROLLBACK",seq=seq)
            out["snapshot_sha256"]=_digest(data)
            return out
        return self._txn(read)

    def close(self):
        self.db.close()


__all__=["SCHEMA","CAPTURE_SCHEMA","CAPTURED","EXISTING","GET_PLAN",
         "ReferenceDurableRecoveryIdCapture"]
