"""AION V2 two signed registry-generation high-watermarks, math-only.

This is NOT external anchoring in production. Both signer pins, challenge
nonces, prior registry and signed READ envelopes are supplied by the caller.
It never signs/creates keys, persists a registry, contacts witnesses, spends,
approves a model request or installs anything. Privileged simultaneous
replacement of pins and signed reads can still pass mathematical checks.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_v2_four_role_key_enrollment_reference import (
    CANDIDATE as ROSTER_CANDIDATE, ROLES, ROSTER_SCHEMA,
    review_four_role_roster, roster_sha256,
)

SCHEMA="ATLASQUANT_AION_V2_REGISTRY_DUAL_SIGNED_HIGH_WATERMARK_REFERENCE_V1"
HEAD_SCHEMA="ATLASQUANT_AION_V2_REGISTRY_SIGNED_GENERATION_READ_V1"
PURPOSE="ATTEST_ONE_ROLE_REGISTRY_GENERATION_MATH_ONLY"
DOMAIN=b"ATLASQUANT_AION_V2_REGISTRY_GENERATION_READ_V1\x00"
MATCH="REGISTRY_TWO_SIGNED_GENERATIONS_MATCH_MATH_ONLY_UNTRUSTED"
TRANSITION="REGISTRY_ROTATION_PRECONDITIONS_MATH_ONLY_UNTRUSTED"
ROLES_FOR_READ=("PRIMARY_WITNESS","SECONDARY_ANCHOR")
ZERO="0"*64
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_HEX128=re.compile(r"[0-9a-f]{128}\Z")
_TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
_PIN_KEYS=frozenset({"key_id","public_key_hex"})
_SCOPE_KEYS=frozenset({"owner_id","tenant_id","workspace_id"})
_QUERY_KEYS=frozenset({
    "owner_id","tenant_id","workspace_id","challenge_nonce_hex",
    "minimum_registry_epoch",
})
_READ_KEYS=frozenset({
    "schema","purpose","role","signer_key_id",
    "owner_id","tenant_id","workspace_id","challenge_nonce_hex",
    "minimum_registry_epoch","registry_epoch","generation",
    "roster_sha256","revoked_set_sha256","previous_roster_sha256",
})
_ENVELOPE_KEYS=frozenset({"payload","signature_hex"})
_FALSE={
    "reference_only":True,
    "trusted_owner_enrollment_verified":False,
    "owner_presence_verified":False,
    "trusted_human_owner_consent":False,
    "primary_witness_key_enrolled":False,
    "secondary_anchor_key_enrolled":False,
    "independent_freshness_verified":False,
    "registry_generation_antirollback_production_verified":False,
    "registry_write_persisted":False,
    "registry_dual_domain_cas_committed":False,
    "revocation_effective_in_production":False,
    "provider_request_approved":False,
    "model_invocation_authorized":False,
    "paid_dispatch_performed":False,
    "network_called":False,
    "billing_authorized":False,
    "installer_authorized":False,
    "safe_to_resume":False,
}


def _int(v: Any,lo:int,hi:int)->bool:
    return type(v) is int and lo<=v<=hi


def _hash(v:Any)->bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _token(v:Any)->bool:
    return type(v) is str and bool(_TOKEN.fullmatch(v))


def _pin(v:Any)->bool:
    return type(v) is dict and set(v)==_PIN_KEYS and _token(v["key_id"]) and _hash(v["public_key_hex"])


def _canon(v:Any)->bytes:
    return json.dumps(
        v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False,
    ).encode("utf-8")


def revoked_set_sha256(revoked: Any)->str:
    if (type(revoked) is not list or any(not _hash(x) for x in revoked)
        or revoked != sorted(set(revoked))):
        raise ValueError("exact cumulative sorted revoked-key fingerprints required")
    return sha256(b"ATLASQUANT_AION_V2_REVOKED_KEY_SET_V1\x00"+_canon(revoked)).hexdigest()


def canonical_registry_read(payload: Mapping[str,Any])->bytes:
    if type(payload) is not dict or set(payload)!=_READ_KEYS:
        raise ValueError("closed registry-head signed READ required")
    return DOMAIN+_canon(payload)


def _out(state:str,reason:str,*,digest:str="")->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "matched_roster_sha256":digest if state in (MATCH,TRANSITION) else "",
        "mathematical_candidate_only":state in (MATCH,TRANSITION),
        **_FALSE,
    }


def _valid_roster(roster:Any)->bool:
    if (type(roster) is not dict or roster.get("schema")!=ROSTER_SCHEMA
        or not _int(roster.get("generation"),1,2**31-1)
        or not all(_token(roster.get(k)) for k in _SCOPE_KEYS)
        or not _hash(roster.get("previous_roster_sha256"))):
        return False
    pins=roster.get("pins")
    return (type(pins) is dict and set(pins)==set(ROLES)
            and all(_pin(pins[k]) for k in ROLES))


def _read(
    envelope:Any,*,pin:Any,role:str,query:Any,
)->tuple[str,dict[str,Any]|None]:
    if not _pin(pin):
        return "TRUSTED_REFERENCE_PIN_INVALID",None
    if (type(query) is not dict or set(query)!=_QUERY_KEYS
        or not all(_token(query.get(k)) for k in _SCOPE_KEYS)
        or not _hash(query.get("challenge_nonce_hex"))
        or query["challenge_nonce_hex"]==ZERO
        or not _int(query.get("minimum_registry_epoch"),1,2**31-1)):
        return "REFERENCE_CHALLENGE_SCOPE_EPOCH_INVALID",None
    if type(envelope) is not dict or set(envelope)!=_ENVELOPE_KEYS:
        return "READ_ENVELOPE_SCHEMA_INVALID",None
    p=envelope["payload"]
    if (type(p) is not dict or set(p)!=_READ_KEYS
        or not isinstance(envelope["signature_hex"],str)
        or not _HEX128.fullmatch(envelope["signature_hex"])):
        return "READ_PAYLOAD_OR_SIGNATURE_INVALID",None
    if (p["schema"]!=HEAD_SCHEMA or p["purpose"]!=PURPOSE
        or p["role"]!=role or p["signer_key_id"]!=pin["key_id"]):
        return "READ_ROLE_PURPOSE_OR_PIN_MISMATCH",None
    if any(type(p[k]) is not type(query[k]) or p[k]!=query[k] for k in _QUERY_KEYS):
        return "READ_SIGNED_CHALLENGE_OR_SCOPE_MISMATCH",None
    if (not _int(p["registry_epoch"],query["minimum_registry_epoch"],2**31-1)
        or not _int(p["generation"],1,2**31-1)
        or not all(_hash(p[k]) for k in (
            "roster_sha256","revoked_set_sha256","previous_roster_sha256"
        ))
        or (p["generation"]==1 and p["previous_roster_sha256"]!=ZERO)):
        return "READ_REGISTRY_EPOCH_GENERATION_OR_DIGEST_INVALID",None
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pin["public_key_hex"])).verify(
            bytes.fromhex(envelope["signature_hex"]),canonical_registry_read(p),
        )
    except (InvalidSignature,ValueError,TypeError,OverflowError):
        return "READ_SIGNATURE_MATH_INVALID",None
    return "",{
        "registry_epoch":p["registry_epoch"],
        "generation":p["generation"],
        "roster_sha256":p["roster_sha256"],
        "revoked_set_sha256":p["revoked_set_sha256"],
        "previous_roster_sha256":p["previous_roster_sha256"],
    }


def review_dual_registry_generation(
    *,local_roster:Any,authority_roster:Any,
    primary_read:Any,primary_query:Any,
    secondary_read:Any,secondary_query:Any,
)->dict[str,Any]:
    """Mathematics only. authority_roster must be pinned OUTSIDE rollback.

    For a rotation its keys are the PREVIOUS independently accepted keys,
    not the new untrusted local roster keys. Neither anchor is contacted.
    """
    if not _valid_roster(local_roster) or not _valid_roster(authority_roster):
        return _out("BLOCKED","LOCAL_OR_PREVIOUS_ROSTER_INVALID")
    if any(local_roster[k]!=authority_roster[k] for k in _SCOPE_KEYS):
        return _out("BLOCKED","REGISTRY_SCOPE_MISMATCH")
    if (type(primary_query) is not dict or type(secondary_query) is not dict
        or any(primary_query.get(k)!=secondary_query.get(k)
               for k in _SCOPE_KEYS)):
        return _out("BLOCKED","TWO_DOMAIN_SCOPE_MISMATCH")
    if any(primary_query.get(k)!=local_roster[k] for k in _SCOPE_KEYS):
        return _out("BLOCKED","QUERY_ROSTER_SCOPE_MISMATCH")
    r1,h1=_read(
        primary_read,pin=authority_roster["pins"]["PRIMARY_WITNESS"],
        role="PRIMARY_WITNESS",query=primary_query,
    )
    if r1: return _out("BLOCKED","PRIMARY_"+r1)
    r2,h2=_read(
        secondary_read,pin=authority_roster["pins"]["SECONDARY_ANCHOR"],
        role="SECONDARY_ANCHOR",query=secondary_query,
    )
    if r2: return _out("BLOCKED","SECONDARY_"+r2)
    if h1["registry_epoch"]!=h2["registry_epoch"]:
        return _out("BLOCKED","REGISTRY_EPOCH_SPLIT_BRAIN")
    if h1["generation"]<h2["generation"]:
        return _out("BLOCKED","PRIMARY_REGISTRY_ROLLBACK")
    if h1["generation"]>h2["generation"]:
        return _out("BLOCKED","PRIMARY_REGISTRY_AHEAD_OF_SECOND_ANCHOR")
    if h1!=h2:
        return _out("BLOCKED","SAME_GENERATION_REGISTRY_FORK")
    if local_roster["generation"]<h1["generation"]:
        return _out("BLOCKED","LOCAL_REGISTRY_ROLLBACK_BEHIND_SIGNED_HEADS")
    if local_roster["generation"]>h1["generation"]:
        return _out("BLOCKED","LOCAL_REGISTRY_AHEAD_OF_SIGNED_HEADS")
    try:
        digest=roster_sha256(local_roster)
        revoked=revoked_set_sha256(local_roster["revoked_public_key_sha256"])
    except (ValueError,TypeError,OverflowError):
        return _out("BLOCKED","LOCAL_ROSTER_NOT_CANONICAL")
    if (h1["roster_sha256"]!=digest
        or h1["revoked_set_sha256"]!=revoked
        or h1["previous_roster_sha256"]!=local_roster["previous_roster_sha256"]):
        return _out("BLOCKED","LOCAL_REGISTRY_HASH_OR_REVOCATION_FORK")
    return _out(MATCH,"TWO_SIGNED_READS_MATCH_MATH_ONLY_NOT_TRUST",digest=digest)


def review_anchored_rotation_preflight(
    *,previous_roster:Any,proposed_envelope:Any,
    primary_read:Any,primary_query:Any,
    secondary_read:Any,secondary_query:Any,
    expected_admin_domains:Any,
)->dict[str,Any]:
    """Validate previous registry head AND owner-approved new roster.

    Cannot implement atomic writes to two trust domains or revoke live keys.
    A production caller MUST never infer success from this candidate.
    """
    old=review_dual_registry_generation(
        local_roster=previous_roster,authority_roster=previous_roster,
        primary_read=primary_read,primary_query=primary_query,
        secondary_read=secondary_read,secondary_query=secondary_query,
    )
    if old["state"]!=MATCH:
        return _out("BLOCKED","PREVIOUS_REGISTRY_NOT_DOUBLE_ANCHORED")
    if type(proposed_envelope) is not dict:
        return _out("BLOCKED","PROPOSED_ROSTER_ENVELOPE_INVALID")
    roster=proposed_envelope.get("roster")
    if type(roster) is not dict or not _valid_roster(roster):
        return _out("BLOCKED","PROPOSED_ROSTER_INVALID")
    verified=review_four_role_roster(
        proposed_envelope,
        expected_owner_pin=previous_roster["pins"]["HUMAN_OWNER"],
        expected_admin_domains=expected_admin_domains,
        expected_generation=previous_roster["generation"]+1,
        expected_previous_roster=previous_roster,
        expected_owner_id=previous_roster["owner_id"],
        expected_tenant_id=previous_roster["tenant_id"],
        expected_workspace_id=previous_roster["workspace_id"],
        expected_challenge_nonce_hex=roster["challenge_nonce_hex"],
    )
    if verified["state"]!=ROSTER_CANDIDATE:
        return _out("BLOCKED","OWNER_APPROVAL_POP_REVOCATION_OR_TRANSITION_INVALID")
    return _out(
        TRANSITION,
        "ROTATION_MATH_PRECHECK_ONLY_NOT_WRITTEN_TO_EITHER_DOMAIN",
        digest=verified["roster_sha256"],
    )


__all__=[
    "SCHEMA","HEAD_SCHEMA","PURPOSE","DOMAIN","MATCH","TRANSITION","ZERO",
    "canonical_registry_read","revoked_set_sha256",
    "review_dual_registry_generation","review_anchored_rotation_preflight",
]
