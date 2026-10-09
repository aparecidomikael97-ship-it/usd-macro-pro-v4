"""AION V2 captured response ID antirollback double witness, math-only.

The two trust heads, public pins and challenges are synthetic caller inputs.
No real signer key, API client, external monotonic write, cloud service, paid
dispatch, owner presence or provider-receipt provenance is available.
A math-valid GET plan is *data for offline review*, NEVER network permission.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import sqlite3
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    MATCH as JOURNAL_MATCH, review_dual_witnessed_journal,
    local_journal_intent_commitment,
)
from atlasquant_aion_v2_readonly_recovery_id_capture_reference import (
    ReferenceDurableRecoveryIdCapture, GET_PLAN,
)
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    ReferenceOneShotUnknownOutcomeJournal,
)

SCHEMA="ATLASQUANT_AION_V2_CAPTURE_ID_DUAL_SIGNED_HIGHWATER_REFERENCE_V1"
READ_SCHEMA="ATLASQUANT_AION_V2_CAPTURE_ID_SIGNED_READ_V1"
PURPOSE="SIGNED_LOCAL_ID_CAPTURE_HIGHWATER_MATH_ONLY_NO_GET"
DOMAIN=b"ATLASQUANT_AION_V2_CAPTURE_ID_SIGNED_READ_V1\x00"
ZERO="0"*64
ROLES=("PRIMARY_WITNESS","SECONDARY_ANCHOR")
STATE_ABSENT="NO_CAPTURE_YET"
STATE_CAPTURED="CAPTURE_RECORDED_LOCAL_ONLY"
MATCH="TWO_SIGNED_CAPTURE_HEADS_MATH_MATCH_UNTRUSTED_NO_NETWORK"
FENCE="CAPTURE_SINGLE_EVENT_FENCE_MATH_ONLY_UNCOMMITTED"
_HEX=re.compile(r"[a-f0-9]{64}\Z")
_SIG=re.compile(r"[a-f0-9]{128}\Z")
_TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_QUERY_KEYS=frozenset({
    "owner_id","tenant_id","workspace_id","period_id",
    "policy_generation","key_registry_roster_sha256","nonce_hex",
    "challenge_nonce_hex","minimum_witness_epoch",
})
_PAYLOAD_KEYS=frozenset({
    "schema","purpose","role","signer_key_id",
    *_QUERY_KEYS,
    "witness_epoch","capture_sequence","capture_snapshot_sha256",
    "capture_state","capture_event_sha256","journal_sequence",
    "journal_snapshot_sha256","claim_sequence",
    "signed_v2_intent_sha256","full_provider_request_sha256",
})
_HEAD_KEYS=frozenset({
    "witness_epoch","capture_sequence","capture_snapshot_sha256",
    "capture_state","capture_event_sha256","journal_sequence",
    "journal_snapshot_sha256","claim_sequence",
    "signed_v2_intent_sha256","full_provider_request_sha256",
})
_ACTUAL_KEYS=_HEAD_KEYS-{"witness_epoch"}
_FALSE={
    "reference_only":True,
    "owner_presence_verified":False,
    "owner_identity_enrolled":False,
    "provider_id_provenance_verified":False,
    "witness_primary_live_enrolled":False,
    "second_anchor_live_enrolled":False,
    "independent_fresh_read_verified":False,
    "capture_antirollback_production_verified":False,
    "dispatch_journal_antirollback_production_verified":False,
    "capture_external_cas_performed":False,
    "secondary_external_cas_performed":False,
    "cross_database_atomicity_verified":False,
    "actual_provider_response_retrieved":False,
    "provider_exactly_once_verified":False,
    "network_called":False,
    "real_get_authorized":False,
    "real_get_performed":False,
    "paid_post_authorized":False,
    "paid_post_performed":False,
    "automatic_retry_permitted":False,
    "billing_settlement_verified":False,
    "safe_to_resume":False,
}


def _token(v:Any)->bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _hash(v:Any)->bool:
    return type(v) is str and bool(_HEX.fullmatch(v))


def _integer(v:Any,lo:int,hi:int)->bool:
    return type(v) is int and lo<=v<=hi


def _canon(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


def _out(state:str,reason:str,head:Any=None,paths:Any=None)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "mathematical_candidate_only":state in (MATCH,FENCE),
        "matching_untrusted_head":head if state==MATCH else None,
        "offline_relative_get_paths":paths if state==MATCH else [],
        "must_not_automatically_retry":True,
        **_FALSE,
    }


def _scope(query:Any)->bool:
    return (
        type(query) is dict and set(query)==_QUERY_KEYS
        and all(_token(query[k]) for k in (
            "owner_id","tenant_id","workspace_id"
        ))
        and type(query["period_id"]) is str
        and bool(re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",query["period_id"]))
        and _integer(query["policy_generation"],1,2**31-1)
        and all(_hash(query[k]) for k in (
            "key_registry_roster_sha256","nonce_hex","challenge_nonce_hex"
        ))
        and query["nonce_hex"]!=ZERO
        and query["challenge_nonce_hex"]!=ZERO
        and _integer(query["minimum_witness_epoch"],1,2**31-1)
    )


def _pin(v:Any)->bool:
    return (
        type(v) is dict and set(v)=={"key_id","public_key_hex"}
        and _token(v["key_id"]) and _hash(v["public_key_hex"])
    )


def _valid_head(h:Any)->bool:
    if type(h) is not dict or set(h)!=_HEAD_KEYS:
        return False
    if (not _integer(h["witness_epoch"],1,2**31-1)
        or not _integer(h["capture_sequence"],0,2**63-1)
        or not _hash(h["capture_snapshot_sha256"])
        or h["capture_state"] not in (STATE_ABSENT,STATE_CAPTURED)
        or not _hash(h["capture_event_sha256"])
        or not _integer(h["journal_sequence"],1,2**63-1)
        or not _hash(h["journal_snapshot_sha256"])
        or not _integer(h["claim_sequence"],2,2**63-1)
        or h["journal_sequence"]<h["claim_sequence"]
        or not _hash(h["signed_v2_intent_sha256"])
        or not _hash(h["full_provider_request_sha256"])):
        return False
    if h["capture_state"]==STATE_ABSENT:
        return h["capture_sequence"]==0 and h["capture_event_sha256"]==ZERO
    return h["capture_sequence"]>=1 and h["capture_event_sha256"]!=ZERO


def canonical_capture_witness_read(payload:Any)->bytes:
    if type(payload) is not dict or set(payload)!=_PAYLOAD_KEYS:
        raise ValueError("strict separate capture high-watermark signed READ")
    return DOMAIN+_canon(payload)


def local_capture_commitment(
    capture_db:Any,*,journal:Any,intent:Any,
)->dict[str,Any]:
    """Reference dual-file consistency check; NOT atomic across databases."""
    if (type(capture_db) is not ReferenceDurableRecoveryIdCapture
        or type(journal) is not ReferenceOneShotUnknownOutcomeJournal
        or type(intent) is not dict
        or capture_db.config!=journal.config):
        raise ValueError("reference capture, journal and intent required")
    jhead=local_journal_intent_commitment(journal,intent=intent)
    if jhead["intent_state"] not in ("DISPATCH_CLAIMED","UNKNOWN_OUTCOME"):
        raise ValueError("not a possibly dispatched intent")
    if capture_db.db.in_transaction:
        raise ValueError("unfinished capture database transaction")
    try:
        capture_db.db.execute("BEGIN IMMEDIATE")
        seq=capture_db._verify_locked()
        rows=capture_db.db.execute(
            "SELECT * FROM aion_recovery_ids_ref ORDER BY sequence"
        ).fetchall()
        item=capture_db.db.execute(
            "SELECT * FROM aion_recovery_ids_ref WHERE nonce_hex=?",
            (intent["nonce_hex"],),
        ).fetchone()
        policy={"schema":"ATLASQUANT_AION_V2_LOCAL_READ_ONLY_RECOVERY_CAPTURE_REFERENCE_V1",
                "policy":capture_db.config,"sequence":seq,
                "captures":[dict(r) for r in rows]}
        snapshot=sha256(_canon(policy)).hexdigest()
        if item is None:
            state=STATE_ABSENT
            digest=ZERO
        else:
            cap=json.loads(item["capture_json"])
            if any(cap[k]!=intent[k] for k in (
                "owner_id","tenant_id","workspace_id",
                "nonce_hex","signed_v2_intent_sha256",
                "full_provider_request_sha256","key_registry_roster_sha256"
            )):
                raise ValueError("capture under nonce rebound to different request")
            if cap["claim_sequence"]!=jhead["claim_sequence"]:
                raise ValueError("capture claim sequence mismatch")
            state=STATE_CAPTURED
            digest=item["capture_sha256"]
        return {
            "capture_sequence":seq,
            "capture_snapshot_sha256":snapshot,
            "capture_state":state,
            "capture_event_sha256":digest,
            "journal_sequence":jhead["journal_sequence"],
            "journal_snapshot_sha256":jhead["journal_snapshot_sha256"],
            "claim_sequence":jhead["claim_sequence"],
            "signed_v2_intent_sha256":intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":intent["full_provider_request_sha256"],
        }
    finally:
        if capture_db.db.in_transaction:
            capture_db.db.rollback()


def unsigned_capture_witness_candidate(
    capture_db:Any,*,journal:Any,intent:Any,
    query:Any,role:Any,signer_key_id:Any,witness_epoch:Any,
)->dict[str,Any]:
    if (role not in ROLES or not _scope(query)
        or not _token(signer_key_id)
        or not _integer(witness_epoch,query["minimum_witness_epoch"],2**31-1)):
        raise ValueError("strict witness candidate required")
    if any(query[k]!=journal.config[k] for k in (
        "owner_id","tenant_id","workspace_id","period_id","policy_generation"
    )) or query["key_registry_roster_sha256"]!=intent.get(
        "key_registry_roster_sha256"
    ) or query["nonce_hex"]!=intent.get("nonce_hex"):
        raise ValueError("query doesn't bind journal and exact intent")
    return {
        "schema":READ_SCHEMA,"purpose":PURPOSE,"role":role,
        "signer_key_id":signer_key_id,**query,
        "witness_epoch":witness_epoch,
        **local_capture_commitment(capture_db,journal=journal,intent=intent),
    }


def _read(envelope:Any,query:Any,pin:Any,role:str):
    if not _scope(query) or not _pin(pin):
        return "UNENROLLED_REFERENCE_PIN_OR_CHALLENGE_INVALID",None
    if type(envelope) is not dict or set(envelope)!={"payload","signature_hex"}:
        return "READ_ENVELOPE_INVALID",None
    p=envelope["payload"]
    if (type(p) is not dict or set(p)!=_PAYLOAD_KEYS
        or type(envelope["signature_hex"]) is not str
        or not _SIG.fullmatch(envelope["signature_hex"])):
        return "READ_SCHEMA_INVALID",None
    if (p["schema"]!=READ_SCHEMA or p["purpose"]!=PURPOSE
        or p["role"]!=role or p["signer_key_id"]!=pin["key_id"]):
        return "READ_ROLE_OR_KEY_REUSE_INVALID",None
    if any(type(p[k]) is not type(query[k]) or p[k]!=query[k] for k in _QUERY_KEYS):
        return "READ_SIGNED_NONCE_SCOPE_OR_EPOCH_FLOOR_MISMATCH",None
    head={k:p[k] for k in _HEAD_KEYS}
    if not _valid_head(head) or head["witness_epoch"]<query["minimum_witness_epoch"]:
        return "HEAD_STATE_SEQUENCE_OR_HASH_INVALID",None
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(pin["public_key_hex"])
        ).verify(
            bytes.fromhex(envelope["signature_hex"]),
            canonical_capture_witness_read(p),
        )
    except (InvalidSignature,ValueError,TypeError,OverflowError):
        return "SIGNATURE_MATH_INVALID",None
    return "",head


def _dual(primary_read:Any,primary_query:Any,primary_pin:Any,
          anchor_read:Any,anchor_query:Any,anchor_pin:Any):
    if (not _scope(primary_query) or not _scope(anchor_query)
        or not _pin(primary_pin) or not _pin(anchor_pin)
        or primary_pin["public_key_hex"]==anchor_pin["public_key_hex"]
        or primary_pin["key_id"]==anchor_pin["key_id"]
        or any(primary_query[k]!=anchor_query[k] for k in _QUERY_KEYS
               if k!="challenge_nonce_hex")):
        return "TWO_DOMAIN_KEY_OR_SCOPE_MISMATCH",None
    p,hp=_read(primary_read,primary_query,primary_pin,ROLES[0])
    if p:return "PRIMARY_"+p,None
    a,ha=_read(anchor_read,anchor_query,anchor_pin,ROLES[1])
    if a:return "SECONDARY_"+a,None
    if hp["witness_epoch"]!=ha["witness_epoch"]:
        return "TWO_CAPTURE_EPOCHS_SPLIT_BRAIN",None
    if hp["capture_sequence"]<ha["capture_sequence"]:
        return "PRIMARY_CAPTURE_ROLLBACK_BEHIND_ANCHOR",None
    if hp["capture_sequence"]>ha["capture_sequence"]:
        return "PRIMARY_CAPTURE_AHEAD_OF_SECOND_ANCHOR",None
    if hp!=ha:
        return "SAME_SEQUENCE_CAPTURE_FORK",None
    return "",hp


def review_double_witnessed_capture_for_offline_get(
    capture_db:Any,*,journal:Any,intent:Any,journal_head_args:Any,
    primary_read:Any,primary_query:Any,primary_pin:Any,
    anchor_read:Any,anchor_query:Any,anchor_pin:Any,
)->dict[str,Any]:
    reason,head=_dual(
        primary_read,primary_query,primary_pin,
        anchor_read,anchor_query,anchor_pin,
    )
    if reason:return _out("BLOCKED",reason)
    if (type(journal_head_args) is not dict
        or set(journal_head_args)!={
            "primary_read","primary_pin","primary_query",
            "anchor_read","anchor_pin","anchor_query"
        }
        or type(intent) is not dict or type(journal) is not
        ReferenceOneShotUnknownOutcomeJournal):
        return _out("BLOCKED","SIGNED_JOURNAL_REFERENCE_REQUIRED")
    journal_review=review_dual_witnessed_journal(
        journal,intent=intent,**journal_head_args,
    )
    if journal_review["state"]!=JOURNAL_MATCH:
        return _out("BLOCKED","DISPATCH_JOURNAL_NOT_DUAL_WITNESSED")
    if (any(primary_query[k]!=journal.config[k] for k in (
        "owner_id","tenant_id","workspace_id","period_id","policy_generation"
    )) or primary_query["key_registry_roster_sha256"]!=intent.get(
        "key_registry_roster_sha256"
    ) or primary_query["nonce_hex"]!=intent.get("nonce_hex")):
        return _out("BLOCKED","SIGNED_CAPTURE_QUERY_INTENT_SCOPE_MISMATCH")
    try:
        local=local_capture_commitment(
            capture_db,journal=journal,intent=intent,
        )
    except (sqlite3.Error,ValueError,TypeError,OverflowError,AttributeError):
        return _out("BLOCKED","CAPTURE_LOCAL_REFERENCE_UNAVAILABLE_OR_CORRUPT")
    if local["capture_sequence"]<head["capture_sequence"]:
        return _out("BLOCKED","LOCAL_CAPTURE_RESTORED_BEHIND_WITNESSES")
    if local["capture_sequence"]>head["capture_sequence"]:
        return _out("BLOCKED","UNANCHORED_LOCAL_CAPTURE_ADVANCE")
    if any(local[k]!=head[k] for k in _ACTUAL_KEYS):
        return _out("BLOCKED","LOCAL_CAPTURE_FORK_OR_JOURNAL_REBOUND")
    j=journal_review["matching_reference_head"]
    for field in (
        "journal_sequence","journal_snapshot_sha256","claim_sequence",
        "signed_v2_intent_sha256","full_provider_request_sha256"
    ):
        if head[field]!=j[field]:
            return _out("BLOCKED","CAPTURE_JOURNAL_HEADS_DISAGREE")
    if head["capture_state"]!=STATE_CAPTURED:
        return _out("BLOCKED","KNOWN_RESPONSE_ID_NOT_CAPTURED")
    if (type(capture_db) is not ReferenceDurableRecoveryIdCapture
        or capture_db.config!=journal.config):
        return _out("BLOCKED","CAPTURE_POLICY_MISMATCH")
    plan=capture_db.plan_recovery_get_reference_only(
        journal=journal,intent=intent,
    )
    if plan["state"]!=GET_PLAN:
        return _out("BLOCKED","NO_CLOSED_GET_ONLY_PLAN")
    paths=plan["relative_get_paths_for_offline_review"]
    if (not paths or type(paths) is not list
        or any(type(x) is not dict or set(x)!={"method","relative_path"}
               or x["method"]!="GET" or type(x["relative_path"]) is not str
               or not x["relative_path"].startswith("/v1/")
               for x in paths)):
        return _out("BLOCKED","NON_GET_OR_UNEXPECTED_ROUTE_DATA")
    return _out(
        MATCH,
        "TWO_SIGNATURES_MATH_ONLY_OFFLINE_GET_PATHS_NOT_NETWORK_PERMISSION",
        head=head,paths=paths,
    )


def review_one_step_capture_anchor_preflight(
    *,old_primary_read:Any,old_primary_query:Any,
    old_anchor_read:Any,old_anchor_query:Any,
    new_primary_read:Any,new_primary_query:Any,
    new_anchor_read:Any,new_anchor_query:Any,
    primary_pin:Any,anchor_pin:Any,
)->dict[str,Any]:
    """Only checks PREVIOUS signed absent -> NEW signed captured; no CAS."""
    reason,old=_dual(
        old_primary_read,old_primary_query,primary_pin,
        old_anchor_read,old_anchor_query,anchor_pin,
    )
    if reason:return _out("BLOCKED","OLD_"+reason)
    reason,new=_dual(
        new_primary_read,new_primary_query,primary_pin,
        new_anchor_read,new_anchor_query,anchor_pin,
    )
    if reason:return _out("BLOCKED","NEW_"+reason)
    if (any(old_primary_query[k]!=new_primary_query[k] for k in
            _QUERY_KEYS if k!="challenge_nonce_hex")
        or old["witness_epoch"]!=new["witness_epoch"]
        or old["capture_state"]!=STATE_ABSENT
        or old["capture_sequence"]!=0
        or old["capture_event_sha256"]!=ZERO
        or new["capture_state"]!=STATE_CAPTURED
        or new["capture_sequence"]!=1
        or new["capture_event_sha256"]==ZERO
        or old["capture_snapshot_sha256"]==new["capture_snapshot_sha256"]
        or any(old[k]!=new[k] for k in (
            "journal_sequence","journal_snapshot_sha256","claim_sequence",
            "signed_v2_intent_sha256","full_provider_request_sha256"
        ))):
        return _out("BLOCKED","INVALID_ONE_CAPTURE_EVENT_FENCE_TRANSITION")
    return _out(FENCE,"MATH_ONLY_NO_PROTECTED_COMPARE_AND_SWAP")


__all__=[
    "SCHEMA","READ_SCHEMA","PURPOSE","DOMAIN","ZERO",
    "STATE_ABSENT","STATE_CAPTURED","MATCH","FENCE",
    "canonical_capture_witness_read","local_capture_commitment",
    "unsigned_capture_witness_candidate",
    "review_double_witnessed_capture_for_offline_get",
    "review_one_step_capture_anchor_preflight",
]
