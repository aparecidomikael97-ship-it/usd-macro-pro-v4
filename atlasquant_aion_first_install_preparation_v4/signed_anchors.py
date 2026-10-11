"""Closed lab anchor/fresh-read contracts; reuse existing Ed25519 primitive.

Every pin/root/floor/clock/history is a FIXTURE input, never real custody.
No signer, HTTP, enrolled identity, witness service or registry write exists.
"""
from hashlib import sha256
from cryptography.exceptions import InvalidSignature
from atlasquant_aion_runtime_source_boundary_ref_v1 import _verify_sig,canonical_bytes
from atlasquant_aion_first_install_preparation.contracts import (
    exact,token,tokens,integer,digest_value)
from .outcomes import result
from atlasquant_aion_first_install_preparation_v3.ledger_storage import Refusal,ZERO
from .commitments import (CONFIG,config_contract,commitment_contract,commitment_digest,domain_digest)

ANCHOR_DOMAIN=b"AION_WEBAUTHN_SIGNED_ANCHOR_V4\0"
READ_DOMAIN=b"AION_WEBAUTHN_AUTHENTICATED_HEAD_READ_V4\0"
PIN_DOMAIN=b"AION_WEBAUTHN_FIXTURE_PIN_V4\0"
RECEIPT_DOMAIN=b"AION_WEBAUTHN_WITNESS_RECEIPT_V4\0"
PIN_FIELDS=frozenset({"schema","mode","owner_id","tenant_id","workspace_id","ledger_id","witness_id",
    "operator_alias","administrative_domain_alias","key_id","key_generation","public_key_hex","algorithm",
    "policy_id","policy_version","root_provenance_digest","revocation","expires_at"})
ANCHOR_FIELDS=frozenset({"schema","algorithm","key_id","key_generation","commitment","signature"})
QUERY_FIELDS=frozenset({"schema","owner_id","tenant_id","workspace_id","ledger_id","witness_id",
    "policy_id","policy_version","minimum_epoch","key_id","key_generation","root_provenance_digest",
    "nonce","issued_at","expires_at","clock_provenance"})
READ_FIELDS=frozenset({"schema","algorithm","key_id","key_generation","witness_id","commitment",
    "nonce","issued_at","expires_at","root_provenance_digest","clock_provenance","signature"})

def pin_contract(value):
    exact(value,PIN_FIELDS)
    if (value["schema"]!="AION_WEBAUTHN_FIXTURE_PIN_V4" or value["mode"]!="FIXTURE_UNENROLLED"
            or value["algorithm"]!="Ed25519" or value["revocation"]!="SIMULATED_NOT_REVOKED"
            or not all(token(value[k]) and value[k].startswith("fixture-") for k in (
                "owner_id","tenant_id","workspace_id","ledger_id","witness_id","operator_alias",
                "administrative_domain_alias","key_id","policy_id"))
            or not digest_value(value["public_key_hex"]) or not digest_value(value["root_provenance_digest"])
            or not integer(value["key_generation"],1,2**31-1) or not integer(value["policy_version"],1,2**31-1)
            or not integer(value["expires_at"],1)):
        raise Refusal("FIXTURE_PIN_INVALID")
    return dict(value)

def pin_digest(value):return domain_digest(pin_contract(value),PIN_DOMAIN)

def _pin_check(pin,expected_pin_digest,config,revoked_keys,revoked_operators):
    pin=pin_contract(pin);config=config_contract(config)
    if not digest_value(expected_pin_digest) or pin_digest(pin)!=expected_pin_digest:
        raise Refusal("EXPECTED_PIN_SUBSTITUTION")
    if not tokens(revoked_keys,128) or not tokens(revoked_operators,128):
        raise Refusal("REVOCATION_STATE_UNKNOWN")
    if pin["key_id"] in revoked_keys or pin["operator_alias"] in revoked_operators:
        raise Refusal("WITNESS_KEY_OR_OPERATOR_REVOKED")
    for k in CONFIG-{"epoch"}:
        if type(pin[k]) is not type(config[k]) or pin[k]!=config[k]:raise Refusal("PIN_SCOPE_POLICY_MISMATCH")
    return pin,config

def _floor_check(commitment,floor,config):
    commitment=commitment_contract(commitment);floor=commitment_contract(floor)
    for record in (commitment,floor):
        for key in CONFIG:
            if type(record[key]) is not type(config[key]) or record[key]!=config[key]:
                raise Refusal("ANCHOR_SCOPE_OR_EPOCH_MISMATCH")
    if commitment["sequence"]<floor["sequence"]:raise Refusal("SIGNED_ANCHOR_ROLLBACK")
    if commitment["sequence"]==floor["sequence"]:
        if commitment_digest(commitment)!=commitment_digest(floor):raise Refusal("SAME_SEQUENCE_FORK")
    elif commitment["previous_commitment_digest"]!=commitment_digest(floor):
        raise Refusal("UNBOUND_PREVIOUS_COMMITMENT")
    return commitment

def verify_anchor_reference(envelope,*,pin,expected_pin_digest,config,floor,
                            revoked_keys=None,revoked_operators=None):
    try:
        pin,config=_pin_check(pin,expected_pin_digest,config,revoked_keys,revoked_operators)
        exact(envelope,ANCHOR_FIELDS)
        if (envelope["schema"]!="AION_WEBAUTHN_SIGNED_ANCHOR_V4" or envelope["algorithm"]!="Ed25519"
                or type(envelope["key_generation"]) is not int or envelope["key_generation"]!=pin["key_generation"]
                or envelope["key_id"]!=pin["key_id"]):raise Refusal("ANCHOR_IDENTITY_INVALID")
        commitment=commitment_contract(envelope["commitment"])
        _verify_sig(envelope,bytes.fromhex(pin["public_key_hex"]),ANCHOR_DOMAIN)
        _floor_check(commitment,floor,config)
        return result("REFERENCE_SIGNED_ANCHOR_MATH_UNTRUSTED","SIGNATURE_NOT_INDEPENDENT_CUSTODY",
            commitment=commitment,commitment_digest=commitment_digest(commitment),
            signed_receipt_digest=sha256(RECEIPT_DOMAIN+canonical_bytes(envelope,domain=ANCHOR_DOMAIN)+bytes.fromhex(envelope["signature"])).hexdigest(),signature_mathematical_valid=True,
            root_trust_verified=False,independent_custody_verified=False,latest_head_independently_verified=False)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,InvalidSignature):
        return result("BLOCKED","SIGNED_ANCHOR_REJECTED",signature_mathematical_valid=False)

def query_contract(query):
    exact(query,QUERY_FIELDS)
    if (query["schema"]!="AION_WEBAUTHN_FRESH_READ_QUERY_V4" or query["clock_provenance"]!="FIXTURE_CLOCK"
            or not all(token(query[k]) and query[k].startswith("fixture-") for k in (
                "owner_id","tenant_id","workspace_id","ledger_id","witness_id","policy_id","key_id"))
            or not integer(query["policy_version"],1) or not integer(query["key_generation"],1)
            or not integer(query["minimum_epoch"],1) or not digest_value(query["root_provenance_digest"])
            or not digest_value(query["nonce"]) or query["nonce"]==ZERO
            or not integer(query["issued_at"]) or not integer(query["expires_at"])
            or not 1<=query["expires_at"]-query["issued_at"]<=60):raise Refusal("QUERY_INVALID")
    return dict(query)

def verify_fresh_read_reference(response,*,query,pin,expected_pin_digest,config,floor,now,
        consumed_nonces=None,revoked_keys=None,revoked_operators=None):
    if response is None:return result("UNKNOWN_OUTCOME","WITNESS_UNAVAILABLE_NO_LOCAL_FALLBACK")
    try:
        pin,config=_pin_check(pin,expected_pin_digest,config,revoked_keys,revoked_operators)
        query=query_contract(query);exact(response,READ_FIELDS)
        if (not integer(now) or not query["issued_at"]<=now<query["expires_at"]
                or now>=pin["expires_at"]):raise Refusal("READ_OR_PIN_EXPIRED")
        if (type(consumed_nonces) is not list or len(consumed_nonces)>128
                or not all(digest_value(n) for n in consumed_nonces)
                or len(set(consumed_nonces))!=len(consumed_nonces) or query["nonce"] in consumed_nonces):
            raise Refusal("NONCE_UNKNOWN_OR_REPLAYED")
        for k in CONFIG-{"epoch"}:
            if query[k]!=config[k] or type(query[k]) is not type(config[k]):raise Refusal("QUERY_SCOPE_MISMATCH")
        if query["minimum_epoch"]!=config["epoch"]:raise Refusal("QUERY_EPOCH_MISMATCH")
        for k in ("key_id","key_generation","root_provenance_digest"):
            if query[k]!=pin[k] or type(query[k]) is not type(pin[k]):raise Refusal("QUERY_PIN_MISMATCH")
        for k in ("nonce","issued_at","expires_at","clock_provenance","witness_id","key_id","key_generation","root_provenance_digest"):
            if response[k]!=query[k] or type(response[k]) is not type(query[k]):raise Refusal("RESPONSE_QUERY_MISMATCH")
        if response["schema"]!="AION_WEBAUTHN_FRESH_READ_RESPONSE_V4" or response["algorithm"]!="Ed25519":
            raise Refusal("READ_PROFILE_INVALID")
        commitment=commitment_contract(response["commitment"])
        _verify_sig(response,bytes.fromhex(pin["public_key_hex"]),READ_DOMAIN)
        _floor_check(commitment,floor,config)
        return result("REFERENCE_FRESH_READ_MATH_UNTRUSTED","FIXTURE_TIME_AND_ROOT_NOT_INDEPENDENT_TRUST",
            commitment=commitment,commitment_digest=commitment_digest(commitment),
            signature_mathematical_valid=True,root_trust_verified=False,trusted_clock_verified=False,
            latest_head_independently_verified=False,durable_nonce_consumption_verified=False)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError,InvalidSignature):
        return result("BLOCKED","SIGNED_FRESH_READ_REJECTED",signature_mathematical_valid=False)
