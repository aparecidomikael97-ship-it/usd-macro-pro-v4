"""Read real persisted scoped AION pending USER turn before inert owner claim.

REFERENCE ONLY: does not certify an independently authenticated host session,
a real enrolled HUMAN_OWNER key, monotonic remote witnesses or paid execution.
In particular SQLite chat and claim journals have NO cross-store atomicity.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from aion_chat.models import Message, Scope
from atlasquant_aion_chat_signed_full_request_review_v2 import (
    CANDIDATE as STORED_CANDIDATE,
    review_signed_full_provider_request_v2,
)
from atlasquant_aion_chat_pending_model_turn_v1 import SCHEMA as PENDING_SCHEMA
from atlasquant_aion_v2_owner_signed_one_shot_admission_reference import (
    MATH_CANDIDATE, LOCAL_BURN,
    review_owner_signed_preclaim_reference,
    consume_one_local_reference_claim_only,
    NO_GO,
)

SCHEMA="ATLASQUANT_AION_V2_PERSISTED_CHAT_OWNER_ONE_SHOT_REFERENCE_V1"
MATCH="PERSISTED_PENDING_CHAT_AND_SIGNED_PRECLAIM_MATH_ONLY_NO_AUTHORITY"
BURN="PERSISTED_CHAT_CHECKED_LOCAL_NONCE_BURN_ONLY_NO_POST"
NO_AUTH={
    **NO_GO,
    "host_access_is_independently_authenticated":False,
    "chat_store_is_remote_antirollback_protected":False,
    "cross_chat_journal_atomicity_verified":False,
    "chat_row_locked_through_claim":False,
    "session_freshness_and_revocation_verified":False,
    "real_owner_signature_enrollment_verified":False,
    "production_admission":False,
}

def _out(state:str,reason:str)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "math_only_candidate":state in (MATCH,BURN),
        "must_not_automatically_retry":True,
        **NO_AUTH,
    }


def _stored_pending_source(store:Any,scope:Scope,
                           conversation_id:Any,message_id:Any,
                           envelope:Any)->tuple[str,dict[str,str]|None]:
    """Re-read exact pending message. No caller supplied source hash accepted."""
    try:
        conversation=store.get_conversation(scope,conversation_id)
        row=store.get_message(scope,conversation_id,message_id)
    except Exception:
        return "CHAT_STORE_RECHECK_UNAVAILABLE",None
    if (conversation.id!=conversation_id
        or conversation.archived
        or type(row) is not Message
        or row.id!=message_id
        or row.conversation_id!=conversation_id
        or row.role!="user"
        or type(row.attachments) is not list
        or row.attachments
        or type(row.content) is not str
        or type(row.metadata) is not dict
        or set(row.metadata)!={
            "contract","request_digest","message_sha256",
            "approval_state","model_invocation_authorized"
        }
        or row.metadata["contract"]!=PENDING_SCHEMA
        or row.metadata["approval_state"]!="PENDING"
        or row.metadata["model_invocation_authorized"] is not False):
        return "STORED_PENDING_ROW_CHANGED_OR_ARCHIVED",None
    source_sha=sha256(row.content.encode("utf-8")).hexdigest()
    metadata=row.metadata
    if (metadata["message_sha256"]!=source_sha
        or type(metadata["request_digest"]) is not str
        or type(envelope) is not dict
        or type(envelope.get("payload")) is not dict
        or envelope["payload"].get("request_digest")!=metadata["request_digest"]
        or envelope["payload"].get("source_message_sha256")!=source_sha):
        return "STORED_SOURCE_OR_REQUEST_DIGEST_REBOUND",None
    return "",{
        "source_message_sha256":source_sha,
        "request_digest":metadata["request_digest"],
        "content":row.content,
    }


def _verify_all(
    *,store:Any,scope:Any,access:Any,journal:Any,intent:Any,
    conversation_id:Any,message_id:Any,final_prompt:Any,
    owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
    lane:Any,provider_values:Any,expected_policy_generation:Any,
    host_quote_micro_usd:Any,
)->tuple[dict[str,Any],dict[str,Any]|None]:
    if (not isinstance(scope,Scope)
        or not isinstance(access,Mapping)
        or type(intent) is not dict
        or type(owner_envelope) is not dict
        or type(owner_envelope.get("payload")) is not dict
        or intent.get("conversation_id")!=conversation_id
        or intent.get("message_id")!=message_id
        or intent.get("owner_id")!=scope.owner_id
        or intent.get("tenant_id")!=scope.tenant_id
        or intent.get("workspace_id")!=scope.workspace_id
        or intent.get("policy_generation")!=expected_policy_generation):
        return _out("BLOCKED","SCOPE_SESSION_JOURNAL_OR_OWNER_SCHEMA_MISMATCH"),None
    try:
        stored=review_signed_full_provider_request_v2(
            store,scope,access,
            conversation_id=conversation_id,message_id=message_id,
            final_prompt=final_prompt,envelope=owner_envelope,
            host_public_pin=owner_public_pin,
            expected_policy_generation=expected_policy_generation,
            provider_values=provider_values,
            host_quote_micro_usd=host_quote_micro_usd,
        )
    except Exception:
        return _out("BLOCKED","CHAT_SESSION_OR_STORED_SIGNATURE_REVIEW_UNAVAILABLE"),None
    if (stored.get("state")!=STORED_CANDIDATE
        or stored.get("reference_only") is not True
        or stored.get("signed_payload_sha256")!=intent.get(
            "signed_v2_intent_sha256"
        )):
        return _out("BLOCKED","REAL_STORED_CHAT_V2_REVIEW_NOT_MATCHED"),None
    reason,pending=_stored_pending_source(
        store,scope,conversation_id,message_id,owner_envelope,
    )
    if reason:return _out("BLOCKED",reason),None
    kwargs={
        "journal":journal,"intent":intent,
        "owner_envelope":owner_envelope,
        "owner_public_pin":owner_public_pin,
        "witness_heads":witness_heads,
        "final_prompt":final_prompt,"lane":lane,
        "provider_values":provider_values,
        "original_message_sha256_assertion":pending["source_message_sha256"],
        "original_request_digest_assertion":pending["request_digest"],
        "quoted_micro_usd":host_quote_micro_usd,
    }
    try:
        combined=review_owner_signed_preclaim_reference(**kwargs)
    except Exception:
        return _out("BLOCKED","COMPOSED_PRECLAIM_REFERENCE_UNAVAILABLE"),None
    if (combined.get("state")!=MATH_CANDIDATE
        or combined.get("real_post_authorized") is not False
        or combined.get("paid_dispatch_authorized") is not False
        or combined.get("network_called") is not False):
        return _out("BLOCKED","COMPOSED_OWNER_PRECLAIM_NOT_MATH_MATCHED"),None
    return _out(MATCH,"SIGNED_PENDING_STORED_USER_TURN_MATH_ONLY_NO_LIVE_TRUST"),kwargs


def review_persisted_owner_preclaim_reference(
    *,store:Any,scope:Any,access:Any,journal:Any,intent:Any,
    conversation_id:Any,message_id:Any,final_prompt:Any,
    owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
    lane:Any,provider_values:Any,expected_policy_generation:Any,
    host_quote_micro_usd:Any,
)->dict[str,Any]:
    outcome,_=_verify_all(
        store=store,scope=scope,access=access,journal=journal,intent=intent,
        conversation_id=conversation_id,message_id=message_id,
        final_prompt=final_prompt,owner_envelope=owner_envelope,
        owner_public_pin=owner_public_pin,witness_heads=witness_heads,
        lane=lane,provider_values=provider_values,
        expected_policy_generation=expected_policy_generation,
        host_quote_micro_usd=host_quote_micro_usd,
    )
    return outcome


def consume_persisted_owner_local_reference_only(
    *,store:Any,scope:Any,access:Any,journal:Any,intent:Any,
    conversation_id:Any,message_id:Any,final_prompt:Any,
    owner_envelope:Any,owner_public_pin:Any,witness_heads:Any,
    lane:Any,provider_values:Any,expected_policy_generation:Any,
    host_quote_micro_usd:Any,
)->dict[str,Any]:
    """Double check persisted message, then burn local nonce, NEVER HTTP.

    NOT atomic across chat SQLite and dispatch SQLite. This is explicit
    NO-GO: hostile concurrent chat DB modification can race final read/claim.
    """
    inputs=dict(
        store=store,scope=scope,access=access,journal=journal,intent=intent,
        conversation_id=conversation_id,message_id=message_id,
        final_prompt=final_prompt,owner_envelope=owner_envelope,
        owner_public_pin=owner_public_pin,witness_heads=witness_heads,
        lane=lane,provider_values=provider_values,
        expected_policy_generation=expected_policy_generation,
        host_quote_micro_usd=host_quote_micro_usd,
    )
    pre,kwargs=_verify_all(**inputs)
    if pre["state"]!=MATCH:return pre
    # Re-read the same persisted row again as close to local claim as
    # possible. Still not a cross-store transaction; no paid authority.
    second,verified_kwargs=_verify_all(**inputs)
    if (second["state"]!=MATCH or verified_kwargs!=kwargs):
        return _out("BLOCKED","CHAT_CHANGED_BETWEEN_PRECLAIM_AND_LOCAL_BURN")
    try:
        claimed=consume_one_local_reference_claim_only(**verified_kwargs)
    except Exception:
        return _out("BLOCKED","LOCAL_CLAIM_UNAVAILABLE_NO_NETWORK")
    if (claimed.get("state")!=LOCAL_BURN
        or claimed.get("real_post_authorized") is not False
        or claimed.get("network_called") is not False):
        return _out("BLOCKED","LOCAL_CLAIM_REPLAY_OR_FAILED_NO_NETWORK")
    return _out(BURN,"CHAT_RECHECKED_LOCAL_NONCE_ONLY_NOT_PAID_ADMISSION")


__all__=[
    "SCHEMA","MATCH","BURN","NO_AUTH",
    "review_persisted_owner_preclaim_reference",
    "consume_persisted_owner_local_reference_only",
]
