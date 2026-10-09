"""AION V2 host-signed session transcript bound to persisted owner preclaim.

Purely inert crypto verification against caller-provided host authority pin.
NOT real IdP, key enrollment, session freshness, FIDO2 or trusted clock.
No HTTP/client/credential issuance, real paid dispatch or live trust.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_chat.models import Scope
from atlasquant_aion_v2_persisted_chat_owner_one_shot_reference import (
    MATCH as CHAT_MATCH, BURN as CHAT_BURN,
    NO_AUTH, review_persisted_owner_preclaim_reference,
    consume_persisted_owner_local_reference_only,
)

SCHEMA="ATLASQUANT_AION_V2_HOST_SESSION_SIGNED_PRECLAIM_REFERENCE_V1"
ATTESTATION_SCHEMA="ATLASQUANT_AION_V2_HOST_SESSION_SCOPE_ATTESTATION_V1"
PURPOSE="ATTEST_ONE_SCOPED_PENDING_OWNER_V2_REQUEST_MATH_ONLY"
DOMAIN=b"ATLASQUANT_AION_V2_HOST_SESSION_SCOPE_ATTESTATION_V1\x00"
ROLE="HOST_SESSION_AUTHORITY"
AUDIENCE="atlasquant-aion-v2-owner-preclaim-reference"
MATCH="HOST_SESSION_AND_PERSISTED_OWNER_MATH_ONLY_NO_AUTHORITY"
BURN="HOST_SESSION_ATTESTED_LOCAL_NONCE_BURN_ONLY_NO_POST"
HEX64=re.compile(r"[a-f0-9]{64}\Z")
HEX128=re.compile(r"[a-f0-9]{128}\Z")
TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
FPRINT_MAX=240
PIN_KEYS=frozenset({"key_id","public_key_hex"})
ENVELOPE_KEYS=frozenset({"payload","signature_hex"})
ATTRS=frozenset({
    "schema","purpose","role","signer_key_id","issuer_id","audience",
    "owner_id","tenant_id","workspace_id","username","host_role",
    "credential_fingerprint_sha256","permissions",
    "conversation_id","message_id","nonce_hex",
    "signed_v2_intent_sha256","full_provider_request_sha256",
    "session_epoch","revocation_generation","issued_at_unix",
    "auth_time_unix","expires_at_unix","challenge_nonce_hex",
})
NO_GO={
    **NO_AUTH,
    "real_idp_signature_verified":False,
    "session_signing_root_enrolled":False,
    "session_signature_is_independently_trusted":False,
    "independent_clock_attested":False,
    "session_challenge_consumed":False,
    "session_revocation_list_checked":False,
    "session_crypto_key_isolation_verified":False,
    "signed_host_session_freshness_proven":False,
    "session_token_issued":False,
    "host_session_is_production_authority":False,
    "provider_called":False,
}


def _out(state:str,reason:str)->dict[str,Any]:
    return {"schema":SCHEMA,"state":state,"reason":reason,
            "math_only":state in (MATCH,BURN),
            "must_not_automatically_retry":True,**NO_GO}


def _h64(v:Any)->bool:
    return type(v) is str and bool(HEX64.fullmatch(v))


def _tok(v:Any)->bool:
    return type(v) is str and bool(TOKEN.fullmatch(v))


def _int(v:Any,low:int,high:int)->bool:
    return type(v) is int and low<=v<=high


def _pin(v:Any)->bool:
    return (type(v) is dict and set(v)==PIN_KEYS
            and _tok(v["key_id"]) and _h64(v["public_key_hex"]))


def canonical_host_session_attestation(payload:Any)->bytes:
    if type(payload) is not dict or set(payload)!=ATTRS:
        raise ValueError("exact host session transcript required")
    return DOMAIN+json.dumps(payload,sort_keys=True,separators=(",",":"),
                             ensure_ascii=False,allow_nan=False).encode()


def _access_consistency(access:Any,scope:Any)->tuple[str,str]|None:
    # This merely checks the supplied host assertion. It does NOT query an IdP.
    if (type(access) is not dict
        or set(access)!={"allowed","mode","role","session"}
        or access["allowed"] is not True
        or access["mode"]!="AUTHENTICATED"
        or access["role"]!="ADMIN"):
        return None
    session=access["session"]
    if (type(session) is not dict
        or set(session)!={"role","username","credential_fingerprint","permissions"}
        or session["role"]!="ADMIN"
        or session["username"]!=scope.owner_id
        or type(session["credential_fingerprint"]) is not str
        or not 1<=len(session["credential_fingerprint"])<=FPRINT_MAX
        or type(session["permissions"]) is not list
        or any(type(p) is not str for p in session["permissions"])
        or sorted(session["permissions"])!=["aion:admin","app:read"]):
        return None
    return (
        sha256(session["credential_fingerprint"].encode()).hexdigest(),
        session["username"],
    )


def _math_verify(
    *,scope:Any,access:Any,conversation_id:Any,message_id:Any,
    intent:Any,owner_public_pin:Any,witness_heads:Any,
    host_envelope:Any,host_authority_pin:Any,
    challenge_nonce_hex:Any,expected_issuer_id:Any,
    expected_session_epoch:Any,revocation_generation_floor:Any,
    now_unix:Any,
)->str:
    if (type(scope) is not Scope or type(intent) is not dict
        or not _pin(host_authority_pin) or not _pin(owner_public_pin)
        or type(witness_heads) is not dict
        or any(not _pin(witness_heads.get(x)) for x in
               ("primary_pin","anchor_pin"))
        or type(host_envelope) is not dict
        or set(host_envelope)!=ENVELOPE_KEYS
        or type(host_envelope["payload"]) is not dict
        or type(host_envelope["signature_hex"]) is not str
        or not HEX128.fullmatch(host_envelope["signature_hex"])):
        return "SESSION_PROOF_OR_PIN_SHAPE_INVALID"
    all_pins=[
        host_authority_pin,owner_public_pin,
        witness_heads["primary_pin"],witness_heads["anchor_pin"],
    ]
    if (len({x["key_id"] for x in all_pins})!=4
        or len({x["public_key_hex"] for x in all_pins})!=4):
        return "SESSION_SIGNER_MUST_DIFFER_FROM_OWNER_AND_WITNESSES"
    if (not _h64(challenge_nonce_hex)
        or challenge_nonce_hex=="0"*64
        or not _tok(expected_issuer_id)
        or not _int(expected_session_epoch,1,2**31-1)
        or not _int(revocation_generation_floor,1,2**31-1)
        or not _int(now_unix,1,2**62)):
        return "CHALLENGE_ISSUER_CLOCK_OR_REVOCATION_FLOOR_INVALID"
    actual=_access_consistency(access,scope)
    if actual is None:return "HOST_ACCESS_SCOPE_PERMISSIONS_INCONSISTENT"
    p=host_envelope["payload"]
    if set(p)!=ATTRS:return "SESSION_SIGNED_CLOSED_SCHEMA_MISMATCH"
    if (p["schema"]!=ATTESTATION_SCHEMA
        or p["purpose"]!=PURPOSE or p["role"]!=ROLE
        or p["audience"]!=AUDIENCE
        or p["signer_key_id"]!=host_authority_pin["key_id"]
        or p["issuer_id"]!=expected_issuer_id
        or p["owner_id"]!=scope.owner_id
        or p["tenant_id"]!=scope.tenant_id
        or p["workspace_id"]!=scope.workspace_id
        or p["username"]!=actual[1]
        or p["host_role"]!="ADMIN"
        or p["credential_fingerprint_sha256"]!=actual[0]
        or p["permissions"]!=["aion:admin","app:read"]
        or p["conversation_id"]!=conversation_id
        or p["message_id"]!=message_id
        or p["nonce_hex"]!=intent.get("nonce_hex")
        or p["signed_v2_intent_sha256"]!=intent.get("signed_v2_intent_sha256")
        or p["full_provider_request_sha256"]!=intent.get("full_provider_request_sha256")
        or p["challenge_nonce_hex"]!=challenge_nonce_hex):
        return "HOST_ATTESTATION_REBOUND_TO_OTHER_ACCESS_OR_REQUEST"
    if (not _int(p["session_epoch"],1,2**31-1)
        or p["session_epoch"]!=expected_session_epoch
        or not _int(p["revocation_generation"],1,2**31-1)
        or p["revocation_generation"]<revocation_generation_floor):
        return "SIGNED_SESSION_EPOCH_REVOKED_OR_ROLLBACK"
    if (not _int(p["issued_at_unix"],1,2**62)
        or not _int(p["auth_time_unix"],1,2**62)
        or not _int(p["expires_at_unix"],1,2**62)
        or p["issued_at_unix"]>now_unix+30
        or now_unix>=p["expires_at_unix"]
        or p["expires_at_unix"]-p["issued_at_unix"]>300
        or p["expires_at_unix"]<=p["issued_at_unix"]
        or p["auth_time_unix"]>p["issued_at_unix"]
        or p["issued_at_unix"]-p["auth_time_unix"]>600
        or now_unix-p["issued_at_unix"]>300):
        return "SESSION_ASSERTED_TIME_WINDOW_OR_AUTH_AGE_INVALID"
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(host_authority_pin["public_key_hex"])
        ).verify(
            bytes.fromhex(host_envelope["signature_hex"]),
            canonical_host_session_attestation(p),
        )
    except (InvalidSignature,ValueError,OverflowError,TypeError):
        return "HOST_SESSION_SIGNATURE_MATH_INVALID"
    return ""


def _route(*,consume:bool,store:Any,scope:Any,access:Any,journal:Any,
           intent:Any,conversation_id:Any,message_id:Any,final_prompt:Any,
           owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
           lane:Any,provider_values:Any,expected_policy_generation:Any,
           host_quote_micro_usd:Any,host_envelope:Any,host_authority_pin:Any,
           challenge_nonce_hex:Any,expected_issuer_id:Any,
           expected_session_epoch:Any,revocation_generation_floor:Any,
           now_unix:Any)->dict[str,Any]:
    reason=_math_verify(
        scope=scope,access=access,conversation_id=conversation_id,
        message_id=message_id,intent=intent,
        owner_public_pin=owner_public_pin,witness_heads=witness_heads,
        host_envelope=host_envelope,host_authority_pin=host_authority_pin,
        challenge_nonce_hex=challenge_nonce_hex,expected_issuer_id=expected_issuer_id,
        expected_session_epoch=expected_session_epoch,
        revocation_generation_floor=revocation_generation_floor,
        now_unix=now_unix,
    )
    if reason:return _out("BLOCKED",reason)
    kwargs={
        "store":store,"scope":scope,"access":access,
        "journal":journal,"intent":intent,
        "conversation_id":conversation_id,"message_id":message_id,
        "final_prompt":final_prompt,
        "owner_envelope":owner_envelope,"owner_public_pin":owner_public_pin,
        "witness_heads":witness_heads,"lane":lane,
        "provider_values":provider_values,
        "expected_policy_generation":expected_policy_generation,
        "host_quote_micro_usd":host_quote_micro_usd,
    }
    if consume:
        # Last time/race check is mathematical and still uses caller clock.
        if _math_verify(
            scope=scope,access=access,conversation_id=conversation_id,
            message_id=message_id,intent=intent,owner_public_pin=owner_public_pin,
            witness_heads=witness_heads,host_envelope=host_envelope,
            host_authority_pin=host_authority_pin,
            challenge_nonce_hex=challenge_nonce_hex,
            expected_issuer_id=expected_issuer_id,
            expected_session_epoch=expected_session_epoch,
            revocation_generation_floor=revocation_generation_floor,
            now_unix=now_unix,
        ):
            return _out("BLOCKED","SECOND_HOST_SESSION_RECHECK_INVALID")
    try:
        result=(consume_persisted_owner_local_reference_only(**kwargs)
                if consume else review_persisted_owner_preclaim_reference(**kwargs))
    except Exception:
        return _out("BLOCKED","PERSISTED_CHAT_PRECLAIM_UNAVAILABLE")
    wanted=CHAT_BURN if consume else CHAT_MATCH
    if (result.get("state")!=wanted
        or result.get("production_admission") is not False
        or result.get("paid_dispatch_authorized") is not False
        or result.get("network_called") is not False):
        return _out("BLOCKED","STORED_USER_CHAT_OR_OWNER_WITNESSES_NOT_MATCHED")
    return _out(
        BURN if consume else MATCH,
        "HOST_SESSION_SIGNATURE_AND_OWNER_CHAT_MATH_ONLY_NO_TRUST",
    )


def review_host_attested_persisted_preclaim_reference(
    *,store:Any,scope:Any,access:Any,journal:Any,intent:Any,
    conversation_id:Any,message_id:Any,final_prompt:Any,
    owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
    lane:Any,provider_values:Any,expected_policy_generation:Any,
    host_quote_micro_usd:Any,host_envelope:Any,host_authority_pin:Any,
    challenge_nonce_hex:Any,expected_issuer_id:Any,
    expected_session_epoch:Any,revocation_generation_floor:Any,
    now_unix:Any,
)->dict[str,Any]:
    return _route(consume=False,**locals())


def consume_host_attested_persisted_local_reference_only(
    *,store:Any,scope:Any,access:Any,journal:Any,intent:Any,
    conversation_id:Any,message_id:Any,final_prompt:Any,
    owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
    lane:Any,provider_values:Any,expected_policy_generation:Any,
    host_quote_micro_usd:Any,host_envelope:Any,host_authority_pin:Any,
    challenge_nonce_hex:Any,expected_issuer_id:Any,
    expected_session_epoch:Any,revocation_generation_floor:Any,
    now_unix:Any,
)->dict[str,Any]:
    return _route(consume=True,**locals())


__all__=[
    "SCHEMA","ATTESTATION_SCHEMA","PURPOSE","DOMAIN","ROLE","AUDIENCE",
    "ATTRS","MATCH","BURN","NO_GO",
    "canonical_host_session_attestation",
    "review_host_attested_persisted_preclaim_reference",
    "consume_host_attested_persisted_local_reference_only",
]
