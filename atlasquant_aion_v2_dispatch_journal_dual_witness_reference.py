"""Two signed dispatch-journal high-watermarks + fencing: MATH REFERENCE ONLY.

No external witness clients, private keys, paid HTTP, clock, enrollment, or
trusted storage. All signatures and expected keys are caller-supplied.
A mathematical match must NEVER authorize (re)dispatch or bill a provider.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    ReferenceOneShotUnknownOutcomeJournal, SCHEMA as JOURNAL_SCHEMA,
    STATE_PREPARED, STATE_CLAIMED, STATE_UNKNOWN, STATE_CANCELLED,
    _valid_intent,
)

SCHEMA="ATLASQUANT_AION_V2_DISPATCH_JOURNAL_DUAL_HEAD_REFERENCE_V1"
READ_SCHEMA="ATLASQUANT_AION_V2_DISPATCH_JOURNAL_SIGNED_READ_V1"
PURPOSE="ATTEST_ONE_DISPATCH_JOURNAL_SNAPSHOT_MATH_ONLY"
DOMAIN=b"ATLASQUANT_AION_V2_DISPATCH_JOURNAL_SIGNED_READ_V1\x00"
ROLES=("PRIMARY_WITNESS","SECONDARY_ANCHOR")
MATCH="DUAL_WITNESSED_DISPATCH_STATE_MATH_ONLY_UNTRUSTED"
FENCE_CANDIDATE="ONE_SHOT_FENCED_CLAIM_PRECHECK_MATH_ONLY_UNTRUSTED"
ZERO="0"*64
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_HEX128=re.compile(r"[0-9a-f]{128}\Z")
_TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_PIN_KEYS=frozenset({"key_id","public_key_hex"})
_QUERY_KEYS=frozenset({
    "owner_id","tenant_id","workspace_id","period_id",
    "policy_generation","key_registry_roster_sha256","nonce_hex",
    "challenge_nonce_hex","minimum_witness_epoch",
})
_PAYLOAD_KEYS=frozenset({
    "schema","purpose","role","signer_key_id",
    "owner_id","tenant_id","workspace_id","period_id",
    "policy_generation","key_registry_roster_sha256","nonce_hex",
    "challenge_nonce_hex","minimum_witness_epoch","witness_epoch",
    "journal_sequence","journal_snapshot_sha256","intent_state",
    "claim_sequence","signed_v2_intent_sha256",
    "full_provider_request_sha256",
})
_HEAD_KEYS=frozenset({
    "witness_epoch","journal_sequence","journal_snapshot_sha256",
    "intent_state","claim_sequence","signed_v2_intent_sha256",
    "full_provider_request_sha256",
})
_OUT_FALSE={
    "reference_only":True,
    "trusted_owner_identity_verified":False,
    "owner_presence_verified":False,
    "public_keys_enrolled":False,
    "two_independent_head_freshness_verified":False,
    "journal_antirollback_production_verified":False,
    "witness_cas_performed":False,
    "secondary_anchor_cas_performed":False,
    "cross_domain_atomicity_verified":False,
    "provider_idempotency_verified":False,
    "provider_response_verified":False,
    "paid_request_authorized":False,
    "paid_request_sent":False,
    "network_called":False,
    "billing_authorized":False,
    "safe_to_resume":False,
}


def _hex(v:Any)->bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _integer(v:Any,lo:int,hi:int)->bool:
    return type(v) is int and lo<=v<=hi


def _token(v:Any)->bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _canonical(value:Any)->bytes:
    return json.dumps(
        value,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False,
    ).encode("utf-8")


def _valid_query(q:Any)->bool:
    return (
        type(q) is dict and set(q)==_QUERY_KEYS
        and all(_token(q[k]) for k in ("owner_id","tenant_id","workspace_id"))
        and type(q["period_id"]) is str
        and bool(re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",q["period_id"]))
        and _integer(q["policy_generation"],1,2**31-1)
        and all(_hex(q[k]) for k in (
            "key_registry_roster_sha256","nonce_hex","challenge_nonce_hex"
        ))
        and q["nonce_hex"]!=ZERO and q["challenge_nonce_hex"]!=ZERO
        and _integer(q["minimum_witness_epoch"],1,2**31-1)
    )


def _valid_pin(p:Any)->bool:
    return type(p) is dict and set(p)==_PIN_KEYS and _token(p["key_id"]) and _hex(p["public_key_hex"])


def _valid_head(h:Any)->bool:
    return (
        type(h) is dict and set(h)==_HEAD_KEYS
        and _integer(h["witness_epoch"],1,2**31-1)
        and _integer(h["journal_sequence"],1,2**63-1)
        and _hex(h["journal_snapshot_sha256"])
        and h["intent_state"] in (
            STATE_PREPARED,STATE_CLAIMED,STATE_UNKNOWN,STATE_CANCELLED
        )
        and _integer(h["claim_sequence"],0,2**63-1)
        and _hex(h["signed_v2_intent_sha256"])
        and _hex(h["full_provider_request_sha256"])
        and (h["claim_sequence"]==0)==(h["intent_state"] in (
            STATE_PREPARED,STATE_CANCELLED
        ))
        and h["claim_sequence"]<=h["journal_sequence"]
    )


def canonical_dispatch_journal_read(payload:Mapping[str,Any])->bytes:
    if type(payload) is not dict or set(payload)!=_PAYLOAD_KEYS:
        raise ValueError("exact signed dispatch journal head required")
    return DOMAIN+_canonical(payload)


def _out(state:str,reason:str,*,head:Any=None)->dict[str,Any]:
    return {
        "schema":SCHEMA,
        "state":state,
        "reason":reason,
        "mathematical_candidate_only":state in (MATCH,FENCE_CANDIDATE),
        "matching_reference_head":head if state==MATCH else None,
        "fence_sequence_math_only":head["journal_sequence"]
           if state==FENCE_CANDIDATE else 0,
        "must_not_automatically_retry":True,
        **_OUT_FALSE,
    }


def local_journal_intent_commitment(
    journal:Any,*,intent:Any,
)->dict[str,Any]:
    """Atomic local snapshot; #1133 journal mutation remains a separate txn."""
    if type(journal) is not ReferenceOneShotUnknownOutcomeJournal:
        raise ValueError("exact reference journal required")
    if not _valid_intent(intent,journal.config):
        raise ValueError("exact synthetic V2 intent required")
    if journal.db.in_transaction:
        raise ValueError("unfinished SQLite transaction")
    db=journal.db
    try:
        db.execute("BEGIN IMMEDIATE")
        sequence=journal._verify_locked()
        rows=db.execute(
            "SELECT * FROM aion_dispatch_intents ORDER BY nonce_hex"
        ).fetchall()
        evidence=db.execute(
            "SELECT * FROM aion_dispatch_evidence ORDER BY nonce_hex,evidence_sha256"
        ).fetchall()
        selected=db.execute(
            "SELECT * FROM aion_dispatch_intents WHERE nonce_hex=?",
            (intent["nonce_hex"],),
        ).fetchone()
        if selected is None or selected["intent_json"]!=_canonical(intent).decode("utf-8"):
            raise ValueError("specific intent missing or rebound")
        snapshot={
            "schema":JOURNAL_SCHEMA,"policy":journal.config,
            "journal_sequence":sequence,
            "intents":[dict(x) for x in rows],
            "evidence":[dict(x) for x in evidence],
        }
        return {
            "journal_sequence":sequence,
            "journal_snapshot_sha256":sha256(_canonical(snapshot)).hexdigest(),
            "intent_state":selected["state"],
            "claim_sequence":selected["claim_sequence"] or 0,
            "signed_v2_intent_sha256":intent["signed_v2_intent_sha256"],
            "full_provider_request_sha256":intent["full_provider_request_sha256"],
        }
    finally:
        if db.in_transaction:
            db.rollback()


def unsigned_journal_head_candidate(
    journal:Any,*,intent:Any,query:Any,role:str,signer_key_id:Any,
    witness_epoch:Any,
)->dict[str,Any]:
    """Fixture signature INPUT only, never signs or contacts a domain."""
    if (role not in ROLES or not _valid_query(query)
        or not _token(signer_key_id)
        or not _integer(witness_epoch,1,2**31-1)):
        raise ValueError("exact witness candidate inputs required")
    if any(query[k]!=journal.config[k] for k in (
        "owner_id","tenant_id","workspace_id","period_id","policy_generation"
    )):
        raise ValueError("witness scope mismatch")
    if (query["key_registry_roster_sha256"]!=intent["key_registry_roster_sha256"]
        or query["nonce_hex"]!=intent["nonce_hex"]
        or witness_epoch<query["minimum_witness_epoch"]):
        raise ValueError("witness intent or epoch mismatch")
    head=local_journal_intent_commitment(journal,intent=intent)
    return {
        "schema":READ_SCHEMA,"purpose":PURPOSE,"role":role,
        "signer_key_id":signer_key_id,**query,
        "witness_epoch":witness_epoch,**head,
    }


def _signed_read(
    response:Any,*,query:Any,public_pin:Any,role:str,
)->tuple[str,dict[str,Any]|None]:
    if not _valid_query(query) or not _valid_pin(public_pin):
        return "PIN_OR_CHALLENGE_NOT_ENROLLED_OR_INVALID",None
    if type(response) is not dict or set(response)!={"payload","signature_hex"}:
        return "SIGNED_HEAD_ENVELOPE_INVALID",None
    p=response["payload"]
    if (type(p) is not dict or set(p)!=_PAYLOAD_KEYS
        or type(response["signature_hex"]) is not str
        or not _HEX128.fullmatch(response["signature_hex"])):
        return "SIGNED_HEAD_SCHEMA_INVALID",None
    if (p["schema"]!=READ_SCHEMA or p["purpose"]!=PURPOSE
        or p["role"]!=role or p["signer_key_id"]!=public_pin["key_id"]):
        return "SIGNED_HEAD_ROLE_OR_PURPOSE_INVALID",None
    if any(p[k]!=query[k] or type(p[k]) is not type(query[k]) for k in _QUERY_KEYS):
        return "SIGNED_HEAD_CHALLENGE_OR_SCOPE_MISMATCH",None
    head={k:p[k] for k in _HEAD_KEYS}
    if not _valid_head(head) or head["witness_epoch"]<query["minimum_witness_epoch"]:
        return "SIGNED_HEAD_STATE_EPOCH_OR_FENCE_INVALID",None
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_pin["public_key_hex"])
        ).verify(
            bytes.fromhex(response["signature_hex"]),
            canonical_dispatch_journal_read(p),
        )
    except (InvalidSignature,ValueError,TypeError,OverflowError):
        return "SIGNED_HEAD_SIGNATURE_MATH_INVALID",None
    return "",head


def _two_signed(
    primary_read:Any,primary_pin:Any,primary_query:Any,
    anchor_read:Any,anchor_pin:Any,anchor_query:Any,
)->tuple[str,dict[str,Any]|None]:
    if (not _valid_pin(primary_pin) or not _valid_pin(anchor_pin)
        or primary_pin["public_key_hex"]==anchor_pin["public_key_hex"]
        or not _valid_query(primary_query) or not _valid_query(anchor_query)
        or any(primary_query[k]!=anchor_query[k] for k in _QUERY_KEYS
               if k!="challenge_nonce_hex")):
        return "TWO_DOMAIN_PIN_OR_SCOPE_MISMATCH",None
    reason,p=_signed_read(
        primary_read,query=primary_query,public_pin=primary_pin,
        role="PRIMARY_WITNESS",
    )
    if reason:
        return "PRIMARY_"+reason,None
    reason,a=_signed_read(
        anchor_read,query=anchor_query,public_pin=anchor_pin,
        role="SECONDARY_ANCHOR",
    )
    if reason:
        return "SECONDARY_"+reason,None
    if p["witness_epoch"]!=a["witness_epoch"]:
        return "JOURNAL_HEAD_EPOCH_SPLIT_BRAIN",None
    if p["journal_sequence"]<a["journal_sequence"]:
        return "PRIMARY_JOURNAL_ROLLBACK_BEHIND_ANCHOR",None
    if p["journal_sequence"]>a["journal_sequence"]:
        return "PRIMARY_JOURNAL_AHEAD_OF_SECONDARY_ANCHOR",None
    if p!=a:
        return "SAME_SEQUENCE_JOURNAL_HEAD_FORK",None
    return "",p


def review_dual_witnessed_journal(
    journal:Any,*,intent:Any,
    primary_read:Any,primary_pin:Any,primary_query:Any,
    anchor_read:Any,anchor_pin:Any,anchor_query:Any,
)->dict[str,Any]:
    reason,head=_two_signed(
        primary_read,primary_pin,primary_query,anchor_read,anchor_pin,
        anchor_query,
    )
    if reason:
        return _out("BLOCKED",reason)
    if (type(journal) is not ReferenceOneShotUnknownOutcomeJournal
        or type(intent) is not dict):
        return _out("BLOCKED","REFERENCE_JOURNAL_AND_INTENT_REQUIRED")
    if any(primary_query[k]!=journal.config[k] for k in (
        "owner_id","tenant_id","workspace_id","period_id","policy_generation"
    )) or primary_query["key_registry_roster_sha256"]!=intent.get(
        "key_registry_roster_sha256"
    ) or primary_query["nonce_hex"]!=intent.get("nonce_hex"):
        return _out("BLOCKED","JOURNAL_QUERY_SCOPE_OR_INTENT_MISMATCH")
    try:
        actual=local_journal_intent_commitment(journal,intent=intent)
    except (ValueError,TypeError,sqlite3.Error,OverflowError,AttributeError):
        return _out("BLOCKED","JOURNAL_LOCAL_SNAPSHOT_UNAVAILABLE_OR_CORRUPT")
    if actual["journal_sequence"]<head["journal_sequence"]:
        return _out("BLOCKED","LOCAL_DISPATCH_JOURNAL_ROLLED_BACK")
    if actual["journal_sequence"]>head["journal_sequence"]:
        return _out("BLOCKED","LOCAL_CLAIM_UNANCHORED_OR_UNKNOWN_GAP")
    if any(actual[k]!=head[k] for k in actual):
        return _out("BLOCKED","LOCAL_JOURNAL_HEAD_FORK_OR_REBOUND")
    if head["intent_state"] in (STATE_PREPARED,STATE_CANCELLED):
        return _out("BLOCKED","NOT_DISPATCH_CLAIMED_OR_UNKNOWN")
    return _out(MATCH,"TWO_HEADS_MATH_MATCH_NO_DISPATCH_OR_PAYMENT_AUTHORITY",
                head=head)


def review_one_step_claim_fence_preflight(
    *,old_primary_read:Any,old_anchor_read:Any,
    new_primary_read:Any,new_anchor_read:Any,
    primary_pin:Any,anchor_pin:Any,
    old_primary_query:Any,old_anchor_query:Any,
    new_primary_query:Any,new_anchor_query:Any,
)->dict[str,Any]:
    """Math-only old PREPARED -> new CLAIMED, never allocates real fencing."""
    reason,old=_two_signed(
        old_primary_read,primary_pin,old_primary_query,
        old_anchor_read,anchor_pin,old_anchor_query,
    )
    if reason:
        return _out("BLOCKED","OLD_"+reason)
    reason,new=_two_signed(
        new_primary_read,primary_pin,new_primary_query,
        new_anchor_read,anchor_pin,new_anchor_query,
    )
    if reason:
        return _out("BLOCKED","NEW_"+reason)
    if (any(old_primary_query[k]!=new_primary_query[k]
            for k in _QUERY_KEYS if k!="challenge_nonce_hex")
        or old["witness_epoch"]!=new["witness_epoch"]
        or old["intent_state"]!=STATE_PREPARED
        or old["claim_sequence"]!=0
        or new["intent_state"]!=STATE_CLAIMED
        or new["journal_sequence"]!=old["journal_sequence"]+1
        or new["claim_sequence"]!=new["journal_sequence"]
        or old["signed_v2_intent_sha256"]!=new["signed_v2_intent_sha256"]
        or old["full_provider_request_sha256"]!=new["full_provider_request_sha256"]
        or old["journal_snapshot_sha256"]==new["journal_snapshot_sha256"]):
        return _out("BLOCKED","INVALID_SINGLE_USE_FENCE_SEQUENCE_TRANSITION")
    return _out(
        FENCE_CANDIDATE,
        "TWO_MATHEMATICALLY_SIGNED_FENCE_HEADS_NO_REMOTE_CAS_OR_AUTHORITY",
        head=new,
    )


__all__=[
    "SCHEMA","READ_SCHEMA","PURPOSE","DOMAIN","ROLES","MATCH",
    "FENCE_CANDIDATE","canonical_dispatch_journal_read",
    "local_journal_intent_commitment","unsigned_journal_head_candidate",
    "review_dual_witnessed_journal","review_one_step_claim_fence_preflight",
]
