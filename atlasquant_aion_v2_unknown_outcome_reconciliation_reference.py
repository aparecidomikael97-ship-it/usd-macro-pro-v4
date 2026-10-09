"""AION V2 UNKNOWN_OUTCOME evidence + manual review: CRYPTO MATH ONLY.

No real provider receipt exists here. The disposable CI "PROVIDER_FIXTURE"
signer is NOT an enrolled, independently authenticated billing authority.
Manual owner review also uses a caller-supplied pin, not Windows Hello/FIDO2.
Even both valid math signatures NEVER grant retry, refund, payment settlement,
provider invocation or real identity/owner presence.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    ReferenceOneShotUnknownOutcomeJournal, STATE_CLAIMED, STATE_UNKNOWN,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    MATCH as HEAD_MATCH, review_dual_witnessed_journal,
)

SCHEMA="ATLASQUANT_AION_V2_UNKNOWN_OUTCOME_RECONCILIATION_REFERENCE_V1"
PROVIDER_SCHEMA="ATLASQUANT_AION_V2_PROVIDER_EVIDENCE_SIMULATION_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_V2_OWNER_REVIEW_SIMULATION_V1"
PROVIDER_PURPOSE="DOCUMENT_ONE_SIMULATED_PROVIDER_OBSERVATION_NOT_BILLING"
REVIEW_PURPOSE="REVIEW_UNKNOWN_OUTCOME_MATH_ONLY_NO_EXECUTION"
PROVIDER_ROLE="PROVIDER_EVIDENCE_FIXTURE_ED25519"
REVIEW_ROLE="HUMAN_OWNER_REVIEW_FIXTURE_ED25519"
PROVIDER_DOMAIN=b"ATLASQUANT_AION_V2_PROVIDER_EVIDENCE_SIMULATION_V1\x00"
REVIEW_DOMAIN=b"ATLASQUANT_AION_V2_HUMAN_REVIEW_SIMULATION_V1\x00"
STATUS_PROCESSED="PROCESSED"
STATUS_NOT_FOUND="NOT_FOUND"
STATUS_UNCERTAIN="UNCERTAIN"
DECISION_KEEP_UNKNOWN="KEEP_UNKNOWN"
DECISION_ACK_PROCESSED="ACKNOWLEDGE_PROCESSED"
DECISION_ACK_NOT_FOUND="ACKNOWLEDGE_NOT_FOUND_AS_INCONCLUSIVE"
PROVIDER_CANDIDATE="PROVIDER_OBSERVATION_SIGNATURE_MATH_ONLY_UNTRUSTED"
REVIEW_CANDIDATE="OWNER_REVIEW_SIGNATURE_MATH_ONLY_UNTRUSTED"
ZERO="0"*64
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_HEX128=re.compile(r"[0-9a-f]{128}\Z")
_TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_PERIOD=re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
_SCOPE=("owner_id","tenant_id","workspace_id","period_id","policy_generation")
_PROVIDER_KEYS=frozenset({
    "schema","purpose","role","provider_key_id","provider_id",
    "provider_request_id","owner_id","tenant_id","workspace_id",
    "period_id","policy_generation","nonce_hex","signed_v2_intent_sha256",
    "full_provider_request_sha256","key_registry_roster_sha256",
    "journal_snapshot_sha256","journal_sequence","claim_sequence",
    "observation_status","response_sha256","reported_micro_usd",
})
_REVIEW_KEYS=frozenset({
    "schema","purpose","role","owner_review_key_id","owner_id",
    "tenant_id","workspace_id","period_id","policy_generation",
    "nonce_hex","signed_v2_intent_sha256","full_provider_request_sha256",
    "journal_snapshot_sha256","journal_sequence","claim_sequence",
    "provider_observation_sha256","decision_code","challenge_nonce_hex",
})
_PIN_KEYS=frozenset({"key_id","public_key_hex"})
_ENVELOPE_KEYS=frozenset({"payload","signature_hex"})
_FALSE={
    "reference_only":True,
    "true_provider_provenance_verified":False,
    "actual_provider_idempotency_verified":False,
    "billing_settlement_verified":False,
    "real_charge_verified":False,
    "real_refund_authorized":False,
    "real_owner_identity_verified":False,
    "owner_presence_verified":False,
    "owner_public_key_enrolled":False,
    "provider_public_key_enrolled":False,
    "witness_heads_independently_fresh":False,
    "journal_protected_from_rollback":False,
    "paid_dispatch_authorized":False,
    "paid_dispatch_performed":False,
    "automatic_retry_permitted":False,
    "same_nonce_reusable":False,
    "paid_provider_called":False,
    "network_called":False,
    "installer_authorized":False,
    "safe_to_resume":False,
}


def _hex(v:Any)->bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _int(v:Any,lo:int,hi:int)->bool:
    return type(v) is int and lo<=v<=hi


def _token(v:Any)->bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _pin(v:Any)->bool:
    return type(v) is dict and set(v)==_PIN_KEYS and _token(v["key_id"]) and _hex(v["public_key_hex"])


def _canonical(payload:Any)->bytes:
    return json.dumps(
        payload,sort_keys=True,separators=(",",":"),
        ensure_ascii=False,allow_nan=False,
    ).encode("utf-8")


def canonical_provider_observation(payload:Any)->bytes:
    if type(payload) is not dict or set(payload)!=_PROVIDER_KEYS:
        raise ValueError("exact provider observation schema required")
    return PROVIDER_DOMAIN+_canonical(payload)


def provider_observation_sha256(envelope:Any)->str:
    if (type(envelope) is not dict or set(envelope)!=_ENVELOPE_KEYS
        or type(envelope["payload"]) is not dict
        or not _HEX128.fullmatch(str(envelope["signature_hex"]))):
        raise ValueError("provider evidence envelope required")
    return sha256(PROVIDER_DOMAIN+_canonical(envelope)).hexdigest()


def canonical_owner_review(payload:Any)->bytes:
    if type(payload) is not dict or set(payload)!=_REVIEW_KEYS:
        raise ValueError("exact owner review schema required")
    return REVIEW_DOMAIN+_canonical(payload)


def _signature(payload:Any,hex_signature:Any,pin:Any,message:bytes)->bool:
    if not _pin(pin) or type(hex_signature) is not str or not _HEX128.fullmatch(hex_signature):
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin["public_key_hex"])).verify(
            bytes.fromhex(hex_signature),message,
        )
        return True
    except (InvalidSignature,ValueError,TypeError,OverflowError):
        return False


def _out(state:str,reason:str,*,observation_sha256:str="",decision:str="")->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "observation_sha256_math_only":
            observation_sha256 if state in (PROVIDER_CANDIDATE,REVIEW_CANDIDATE) else "",
        "review_decision_math_only":decision if state==REVIEW_CANDIDATE else "",
        "needs_human_reconciliation":True,
        "must_not_automatically_retry":True,
        "reconciliation_not_actual_settlement":True,
        **_FALSE,
    }


def _read_claimed_or_unknown(
    *,journal:Any,intent:Any,head_args:Any,
)->tuple[str,dict[str,Any]|None]:
    if (type(journal) is not ReferenceOneShotUnknownOutcomeJournal
        or type(intent) is not dict
        or type(head_args) is not dict
        or set(head_args)!={
            "primary_read","primary_pin","primary_query",
            "anchor_read","anchor_pin","anchor_query"
        }):
        return "JOURNAL_INTENT_OR_SIGNED_HEADS_REQUIRED",None
    result=review_dual_witnessed_journal(journal,intent=intent,**head_args)
    if result["state"]!=HEAD_MATCH:
        return "DISPATCH_JOURNAL_NOT_DOUBLE_SIGNED_MATH_MATCHED",None
    head=result["matching_reference_head"]
    if head["intent_state"] not in (STATE_CLAIMED,STATE_UNKNOWN):
        return "INTENT_NOT_POSSIBLY_DISPATCHED",None
    return "",head


def review_provider_outcome_observation(
    *,journal:Any,intent:Any,head_args:Any,
    provider_envelope:Any,provider_public_pin:Any,
)->dict[str,Any]:
    """Checks only provider-FIXTURE signature and witnessed journal binding."""
    error,head=_read_claimed_or_unknown(
        journal=journal,intent=intent,head_args=head_args,
    )
    if error:
        return _out("BLOCKED",error)
    if not _pin(provider_public_pin):
        return _out("BLOCKED","UNENROLLED_OR_INVALID_PROVIDER_PIN")
    if type(provider_envelope) is not dict or set(provider_envelope)!=_ENVELOPE_KEYS:
        return _out("BLOCKED","PROVIDER_ENVELOPE_INVALID")
    p=provider_envelope["payload"]
    if type(p) is not dict or set(p)!=_PROVIDER_KEYS:
        return _out("BLOCKED","PROVIDER_SCHEMA_INVALID")
    if (p["schema"]!=PROVIDER_SCHEMA or p["purpose"]!=PROVIDER_PURPOSE
        or p["role"]!=PROVIDER_ROLE or p["provider_key_id"]!=provider_public_pin["key_id"]
        or not _token(p["provider_id"])
        or not _token(p["provider_request_id"])
        or p["provider_request_id"]=="pending"
        or not _int(p["reported_micro_usd"],0,2_000_000_000)
        or not _hex(p["response_sha256"])):
        return _out("BLOCKED","PROVIDER_ROLE_ID_OR_FIELDS_INVALID")
    if any(p[k]!=intent.get(k) or type(p[k]) is not type(intent.get(k))
           for k in _SCOPE+(
               "nonce_hex","signed_v2_intent_sha256",
               "full_provider_request_sha256","key_registry_roster_sha256",
           )):
        return _out("BLOCKED","PROVIDER_SIGNED_REQUEST_SCOPE_MISMATCH")
    if (p["journal_snapshot_sha256"]!=head["journal_snapshot_sha256"]
        or p["journal_sequence"]!=head["journal_sequence"]
        or p["claim_sequence"]!=head["claim_sequence"]
        or type(p["journal_sequence"]) is not int
        or type(p["claim_sequence"]) is not int):
        return _out("BLOCKED","PROVIDER_OBSERVATION_JOURNAL_REBOUND")
    if p["observation_status"] not in (
        STATUS_PROCESSED,STATUS_NOT_FOUND,STATUS_UNCERTAIN
    ):
        return _out("BLOCKED","PROVIDER_OBSERVATION_STATUS_INVALID")
    if (p["observation_status"]==STATUS_PROCESSED
        and p["response_sha256"]==ZERO):
        return _out("BLOCKED","PROCESSED_OBSERVATION_MUST_BIND_RESPONSE_HASH")
    if (p["observation_status"]!=STATUS_PROCESSED
        and (p["response_sha256"]!=ZERO or p["reported_micro_usd"]!=0)):
        return _out("BLOCKED","UNCONFIRMED_OBSERVATION_CANNOT_ASSERT_CHARGE_OR_RESPONSE")
    try:
        signing=canonical_provider_observation(p)
        if not _signature(
            p,provider_envelope["signature_hex"],provider_public_pin,signing
        ):
            return _out("BLOCKED","PROVIDER_FIXTURE_SIGNATURE_INVALID")
        digest=provider_observation_sha256(provider_envelope)
    except (ValueError,TypeError,OverflowError):
        return _out("BLOCKED","PROVIDER_SIGNED_DATA_INVALID")
    return _out(PROVIDER_CANDIDATE,
                "VALID_SIMULATED_PROVIDER_SIGNATURE_NOT_AUTHENTICATED_OR_BILLED",
                observation_sha256=digest)


def review_manual_reconciliation_candidate(
    *,journal:Any,intent:Any,head_args:Any,
    provider_envelope:Any,provider_public_pin:Any,
    owner_review_envelope:Any,owner_review_public_pin:Any,
    expected_new_challenge_nonce_hex:Any,
)->dict[str,Any]:
    """Even a signed manual review never permits another dispatch or refund."""
    observation=review_provider_outcome_observation(
        journal=journal,intent=intent,head_args=head_args,
        provider_envelope=provider_envelope,
        provider_public_pin=provider_public_pin,
    )
    if observation["state"]!=PROVIDER_CANDIDATE:
        return _out("BLOCKED","PROVIDER_OBSERVATION_NOT_VERIFIED_MATH")
    if (not _pin(owner_review_public_pin)
        or not _hex(expected_new_challenge_nonce_hex)
        or expected_new_challenge_nonce_hex==ZERO
        or type(owner_review_envelope) is not dict
        or set(owner_review_envelope)!=_ENVELOPE_KEYS):
        return _out("BLOCKED","OWNER_PIN_CHALLENGE_OR_REVIEW_ENVELOPE_INVALID")
    r=owner_review_envelope["payload"]
    if type(r) is not dict or set(r)!=_REVIEW_KEYS:
        return _out("BLOCKED","OWNER_REVIEW_SCHEMA_INVALID")
    if (r["schema"]!=REVIEW_SCHEMA or r["purpose"]!=REVIEW_PURPOSE
        or r["role"]!=REVIEW_ROLE
        or r["owner_review_key_id"]!=owner_review_public_pin["key_id"]
        or r["challenge_nonce_hex"]!=expected_new_challenge_nonce_hex):
        return _out("BLOCKED","OWNER_ROLE_PURPOSE_OR_NEW_CHALLENGE_MISMATCH")
    if any(r[k]!=intent.get(k) or type(r[k]) is not type(intent.get(k))
           for k in _SCOPE+(
               "nonce_hex","signed_v2_intent_sha256",
               "full_provider_request_sha256",
           )):
        return _out("BLOCKED","OWNER_REVIEW_SIGNED_SCOPE_OR_REQUEST_MISMATCH")
    head=review_dual_witnessed_journal(
        journal,intent=intent,**head_args
    )["matching_reference_head"]
    if (head is None or r["journal_snapshot_sha256"]!=head["journal_snapshot_sha256"]
        or r["journal_sequence"]!=head["journal_sequence"]
        or r["claim_sequence"]!=head["claim_sequence"]
        or type(r["journal_sequence"]) is not int
        or type(r["claim_sequence"]) is not int
        or r["provider_observation_sha256"]!=observation["observation_sha256_math_only"]):
        return _out("BLOCKED","OWNER_REVIEW_HEAD_OR_OBSERVATION_REBOUND")
    decision=r["decision_code"]
    obs=provider_envelope["payload"]["observation_status"]
    if decision not in (
        DECISION_KEEP_UNKNOWN,DECISION_ACK_PROCESSED,DECISION_ACK_NOT_FOUND
    ):
        return _out("BLOCKED","OWNER_REVIEW_DECISION_INVALID")
    if (decision==DECISION_ACK_PROCESSED and obs!=STATUS_PROCESSED
        or decision==DECISION_ACK_NOT_FOUND and obs!=STATUS_NOT_FOUND):
        return _out("BLOCKED","OWNER_DECISION_CONTRADICTS_OBSERVATION")
    if not _signature(
        r,owner_review_envelope["signature_hex"],owner_review_public_pin,
        canonical_owner_review(r),
    ):
        return _out("BLOCKED","OWNER_REVIEW_SIGNATURE_INVALID")
    return _out(
        REVIEW_CANDIDATE,
        "MATH_ONLY_REVIEW_NO_REAL_OWNER_PRESENCE_PROVIDER_AUTHENTICITY_OR_SETTLEMENT",
        observation_sha256=observation["observation_sha256_math_only"],
        decision=decision,
    )


__all__=[
    "SCHEMA","PROVIDER_SCHEMA","REVIEW_SCHEMA",
    "PROVIDER_PURPOSE","REVIEW_PURPOSE","PROVIDER_ROLE","REVIEW_ROLE",
    "PROVIDER_DOMAIN","REVIEW_DOMAIN","STATUS_PROCESSED","STATUS_NOT_FOUND",
    "STATUS_UNCERTAIN","DECISION_KEEP_UNKNOWN","DECISION_ACK_PROCESSED",
    "DECISION_ACK_NOT_FOUND","PROVIDER_CANDIDATE","REVIEW_CANDIDATE",
    "canonical_provider_observation","provider_observation_sha256",
    "canonical_owner_review","review_provider_outcome_observation",
    "review_manual_reconciliation_candidate",
]
