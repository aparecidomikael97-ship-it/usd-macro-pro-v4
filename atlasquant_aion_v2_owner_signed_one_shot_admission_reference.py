"""Join owner V2 signature, exact POST preview and prepared witness heads.

STRICTLY REFERENCE ONLY. This module NEVER calls the provider, cannot grant
a paid POST, does NOT enroll owner keys, prove real owner presence, read live
external witnesses, atomically commit remote dispatch CAS or verify budget.
Synthetic signatures and a local SQLite claim are NOT production admission.

Purpose: make isolated reference math fail closed when joined, and burn a
local simulated nonce only after all caller-supplied math checks pass.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_chat_signed_full_request_review_v2 import (
    APPROVAL_SCHEMA, PURPOSE, ROLE, canonical_full_request_approval_v2,
)
from atlasquant_aion_provider import (
    REQUEST_BOUNDARY_SCHEMA, preview_openai_request_binding,
)
from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import (
    INTENT_SCHEMA, LOCAL_CLAIM, STATE_PREPARED,
    ReferenceOneShotUnknownOutcomeJournal,
    _valid_intent,
)
from atlasquant_aion_v2_dispatch_journal_dual_witness_reference import (
    MATCH as JOURNAL_MATCH, review_dual_witnessed_journal,
    local_journal_intent_commitment,
)

SCHEMA="ATLASQUANT_AION_V2_COMPOSED_OWNER_ONE_SHOT_REFERENCE_V1"
MATH_CANDIDATE="SIGNED_OWNER_PREPARED_TWO_HEADS_MATH_ONLY_NOT_ADMISSION"
LOCAL_BURN="LOCAL_NONCE_BURNED_REFERENCE_ONLY_NO_POST"
HEX64=re.compile(r"[0-9a-f]{64}\Z")
HEX128=re.compile(r"[0-9a-f]{128}\Z")
TOKEN=re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}\Z")
PIN_FIELDS={"key_id","public_key_hex"}
JOURNAL_FIELDS={
    "primary_read","primary_pin","primary_query",
    "anchor_read","anchor_pin","anchor_query",
}
NO_GO={
    "reference_only":True,
    "owner_private_key_custody_verified":False,
    "owner_enrollment_verified":False,
    "owner_presence_verified":False,
    "original_user_message_persisted_verified":False,
    "noncolluding_signed_witnesses_enrolled":False,
    "remote_journal_head_freshness_verified":False,
    "external_dispatch_cas_performed":False,
    "external_antirollback_verified":False,
    "trusted_budget_hold_verified":False,
    "global_one_shot_guaranteed":False,
    "paid_dispatch_authorized":False,
    "paid_dispatch_performed":False,
    "real_get_authorized":False,
    "real_post_authorized":False,
    "network_called":False,
    "real_provider_called":False,
    "provider_exactly_once_verified":False,
    "actual_cost_verified":False,
    "billing_settlement_verified":False,
    "automatic_retry_permitted":False,
    "same_nonce_reusable":False,
    "safe_to_resume":False,
}


def _out(state:str,reason:str,*,nonce:str="",full_hash:str="")->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "signature_math_and_local_state_only":state in (MATH_CANDIDATE,LOCAL_BURN),
        "reference_nonce_hex":nonce if state in (MATH_CANDIDATE,LOCAL_BURN) else "",
        "reference_full_request_sha256":full_hash if state in
            (MATH_CANDIDATE,LOCAL_BURN) else "",
        "must_not_automatically_retry":True,
        **NO_GO,
    }


def _hex(v:Any,pattern:re.Pattern[str])->bool:
    return type(v) is str and bool(pattern.fullmatch(v))


def _token(v:Any)->bool:
    return type(v) is str and bool(TOKEN.fullmatch(v))


def _pin(v:Any)->bool:
    return (type(v) is dict and set(v)==PIN_FIELDS
            and _token(v["key_id"]) and _hex(v["public_key_hex"],HEX64))


def review_owner_signed_preclaim_reference(
    *,journal:Any,intent:Any,owner_envelope:Any,owner_public_pin:Any,
    witness_heads:Any,final_prompt:Any,lane:Any,provider_values:Any,
    original_message_sha256_assertion:Any,
    original_request_digest_assertion:Any,quoted_micro_usd:Any,
)->dict[str,Any]:
    """Combined math over owner signature, provider bytes and PREPARED heads.

    Source-message hashes and device/root trust are supplied as assertions:
    no storage backend or owner ceremony can be authenticated here.
    """
    if type(journal) is not ReferenceOneShotUnknownOutcomeJournal:
        return _out("BLOCKED","EXACT_REFERENCE_JOURNAL_REQUIRED")
    if not _valid_intent(intent,journal.config):
        return _out("BLOCKED","CLOSED_SIGNED_V2_INTENT_REQUIRED")
    if (type(owner_envelope) is not dict
        or set(owner_envelope)!={"payload","signature_hex"}
        or not _pin(owner_public_pin)
        or not _hex(owner_envelope["signature_hex"],HEX128)
        or type(owner_envelope["payload"]) is not dict
        or type(witness_heads) is not dict
        or set(witness_heads)!=JOURNAL_FIELDS):
        return _out("BLOCKED","SIGNED_OWNER_OR_WITNESS_SCHEMA_INVALID")
    p=owner_envelope["payload"]
    try:
        signed=canonical_full_request_approval_v2(p)
    except (ValueError,TypeError,OverflowError):
        return _out("BLOCKED","EXACT_V2_OWNER_TRANSCRIPT_REQUIRED")
    digest=sha256(signed).hexdigest()
    if (p["schema"]!=APPROVAL_SCHEMA or p["purpose"]!=PURPOSE
        or p["role"]!=ROLE or p["owner_key_id"]!=owner_public_pin["key_id"]
        or p["owner_id"]!=intent["owner_id"]
        or p["tenant_id"]!=intent["tenant_id"]
        or p["workspace_id"]!=intent["workspace_id"]
        or p["conversation_id"]!=intent["conversation_id"]
        or p["message_id"]!=intent["message_id"]
        or p["nonce_hex"]!=intent["nonce_hex"]
        or p["policy_generation"]!=intent["policy_generation"]
        or type(p["max_cost_micro_usd"]) is not int
        or p["max_cost_micro_usd"]!=intent["max_cost_micro_usd"]
        or digest!=intent["signed_v2_intent_sha256"]):
        return _out("BLOCKED","OWNER_SIGNED_SCOPE_INTENT_OR_NONCE_REBOUND")
    if (not _hex(original_message_sha256_assertion,HEX64)
        or not _hex(original_request_digest_assertion,HEX64)
        or p["source_message_sha256"]!=original_message_sha256_assertion
        or p["request_digest"]!=original_request_digest_assertion
        or type(final_prompt) is not str or not final_prompt
        or type(lane) is not str
        or type(quoted_micro_usd) is not int
        or not 1<=quoted_micro_usd<=p["max_cost_micro_usd"]
        or type(provider_values) is not dict):
        return _out("BLOCKED","MESSAGE_ASSERTION_OR_COST_QUOTE_INVALID")
    try:
        preview=preview_openai_request_binding(
            final_prompt,lane=lane,values=provider_values,
        )
    except (ValueError,TypeError,OverflowError,AttributeError):
        return _out("BLOCKED","RECOMPUTE_REAL_PROVIDER_BOUNDARY_FAILED")
    if (type(preview) is not dict
        or preview.get("schema")!=REQUEST_BOUNDARY_SCHEMA
        or preview.get("state")!="BOUND_REQUEST_PREVIEW_UNTRUSTED"):
        return _out("BLOCKED","REAL_PROVIDER_BOUNDARY_PREVIEW_BLOCKED")
    if (p["provider_id"]!="openai"
        or p["full_provider_request_sha256"]!=intent["full_provider_request_sha256"]
        or p["full_provider_request_sha256"]!=preview["request_sha256"]
        or p["final_prompt_sha256"]!=preview["final_prompt_sha256"]
        or p["provider_id"]!=preview["provider"]
        or p["model_id"]!=preview["resolved_model"]
        or p["lane"]!=lane or p["lane"]!=preview["lane"]
        or p["endpoint"]!="https://api.openai.com/v1/responses"
        or p["endpoint"]!=preview["endpoint"]
        or p["max_output_tokens"]!=preview["max_output_tokens"]
        or p["timeout_seconds_repr"]!=repr(preview["timeout_seconds"])
        or preview.get("transport_policy")!={
            "allow_redirects":False,"trust_env":False,"verify_tls":True,
            "http_retry_total":0,"http_retry_connect":0,"http_retry_read":0,
            "http_retry_status":0,"http_retry_other":0,
            "max_redirects":0,"max_app_attempts":1,
        }):
        return _out("BLOCKED","SIGNED_FULL_PROVIDER_POST_OR_TRANSPORT_CHANGED")
    try:
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(owner_public_pin["public_key_hex"])
        ).verify(bytes.fromhex(owner_envelope["signature_hex"]),signed)
    except (ValueError,InvalidSignature,TypeError,OverflowError):
        return _out("BLOCKED","OWNER_V2_SIGNATURE_INVALID")
    # The source journal must remain PREPARED when both signed READs match.
    # No network, witness signer, nonce-consumption, remote CAS is performed.
    try:
        review=review_dual_witnessed_journal(
            journal,intent=intent,**witness_heads,
        )
        local=local_journal_intent_commitment(
            journal,intent=intent,
        )
    except (ValueError,TypeError,OverflowError,AttributeError,KeyError):
        return _out("BLOCKED","DISPATCH_JOURNAL_WITNESSES_UNAVAILABLE")
    if (review.get("state")!=JOURNAL_MATCH
        or local["intent_state"]!=STATE_PREPARED
        or local["claim_sequence"]!=0
        or review.get("matching_reference_head",{}).get("intent_state")!=STATE_PREPARED
        or local["signed_v2_intent_sha256"]!=digest
        or local["full_provider_request_sha256"]!=preview["request_sha256"]):
        return _out("BLOCKED","NO_FRESH_PREPARED_TWO_WITNESS_REFERENCE")
    return _out(
        MATH_CANDIDATE,
        "OWNER_AND_TWO_HEADS_MATH_VALID_WITHOUT_REAL_TRUST_NO_PAID_SEND",
        nonce=intent["nonce_hex"],full_hash=preview["request_sha256"],
    )


def consume_one_local_reference_claim_only(
    *,journal:Any,intent:Any,owner_envelope:Any,owner_public_pin:Any,
    witness_heads:Any,final_prompt:Any,lane:Any,provider_values:Any,
    original_message_sha256_assertion:Any,
    original_request_digest_assertion:Any,quoted_micro_usd:Any,
)->dict[str,Any]:
    """Burn once in an untrusted *local* reference ledger; NEVER send.

    The previous signed PREPARED heads are invalid after the claim, and
    this operation intentionally returns NO network-authorizing token.
    """
    outcome=review_owner_signed_preclaim_reference(
        journal=journal,intent=intent,
        owner_envelope=owner_envelope,owner_public_pin=owner_public_pin,
        witness_heads=witness_heads,final_prompt=final_prompt,lane=lane,
        provider_values=provider_values,
        original_message_sha256_assertion=original_message_sha256_assertion,
        original_request_digest_assertion=original_request_digest_assertion,
        quoted_micro_usd=quoted_micro_usd,
    )
    if outcome["state"]!=MATH_CANDIDATE:
        return outcome
    # reference-only journal has local SQLite BEGIN IMMEDIATE CAS for this
    # nonce. No remote fence exists, so claim is NEVER a POST authorization.
    result=journal.claim_reference_only(intent=intent)
    if result.get("state")!=LOCAL_CLAIM:
        return _out("BLOCKED","NONCE_ALREADY_CLAIMED_UNKNOWN_OR_RACING")
    return _out(
        LOCAL_BURN,"LOCAL_CLAIM_NOT_REMOTE_FENCED_NO_NETWORK_PERMISSION",
        nonce=intent["nonce_hex"],
        full_hash=intent["full_provider_request_sha256"],
    )


__all__=[
    "SCHEMA","MATH_CANDIDATE","LOCAL_BURN","NO_GO",
    "review_owner_signed_preclaim_reference",
    "consume_one_local_reference_claim_only",
]
