"""AION V2 documented provider read-only recovery modes: REFERENCE ONLY.

Documented as of 2026-10-09; no live HTTP, no private credentials, no
real provider receipt, no provider-side exactly-once/idempotency guarantee.
Every "candidate" permits ONLY offline planning of a possible GET endpoint;
NEVER a model POST, automatic retry, spend, invoice settlement or refund.

Provider identifiers, previously stored IDs and the journal state are all
caller-supplied. This module neither authenticates them nor executes reads.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA="ATLASQUANT_AION_V2_DOCUMENTED_PROVIDER_READ_ONLY_RECOVERY_REF_V1"
MODE_OPENAI_BACKGROUND="OPENAI_RESPONSES_BACKGROUND"
MODE_OPENAI_STORED="OPENAI_RESPONSES_STORED"
MODE_OPENAI_UNSTORED="OPENAI_RESPONSES_UNSTORED"
MODE_ANTHROPIC_BATCH="ANTHROPIC_MESSAGES_BATCH"
MODE_ANTHROPIC_SYNC="ANTHROPIC_MESSAGES_SYNC"
MODE_GEMINI_SYNC="GEMINI_GENERATE_CONTENT_SYNC"
READ_CANDIDATE="READ_ONLY_RECOVERY_BY_KNOWN_ID_MATH_ONLY_UNTRUSTED"
NO_SAFE_GET="NO_DOCUMENTED_RECOVERY_BY_KNOWN_ID_NO_RETRY"
SOURCE_OPENAI="https://developers.openai.com/api/docs/guides/background"
SOURCE_ANTHROPIC="https://platform.claude.com/docs/en/api/messages/batches/retrieve"
SOURCE_ANTHROPIC_RESULTS="https://platform.claude.com/docs/en/api/messages/batches/results"
SOURCE_GEMINI="https://ai.google.dev/api/generate-content"
DOCUMENTED_MODES={
    MODE_OPENAI_BACKGROUND:{
        "provider":"openai","identifier_kind":"response_id",
        "recovery_description":"GET response by previously captured resp ID while retained",
        "source_url":SOURCE_OPENAI,"can_plan_read_only_by_id":True,
    },
    MODE_OPENAI_STORED:{
        "provider":"openai","identifier_kind":"response_id",
        "recovery_description":"GET stored response by previously captured resp ID",
        "source_url":SOURCE_OPENAI,"can_plan_read_only_by_id":True,
    },
    MODE_OPENAI_UNSTORED:{
        "provider":"openai","identifier_kind":"none",
        "recovery_description":"No assumed GET once unavailable or not retained",
        "source_url":SOURCE_OPENAI,"can_plan_read_only_by_id":False,
    },
    MODE_ANTHROPIC_BATCH:{
        "provider":"anthropic","identifier_kind":"batch_id_plus_custom_id",
        "recovery_description":"GET known batch status; read results and match custom_id",
        "source_url":SOURCE_ANTHROPIC_RESULTS,"can_plan_read_only_by_id":True,
    },
    MODE_ANTHROPIC_SYNC:{
        "provider":"anthropic","identifier_kind":"none",
        "recovery_description":"request-id diagnostics do not establish Messages GET",
        "source_url":SOURCE_ANTHROPIC,"can_plan_read_only_by_id":False,
    },
    MODE_GEMINI_SYNC:{
        "provider":"gemini","identifier_kind":"none",
        "recovery_description":"responseId in output is not documented as a synchronous GET",
        "source_url":SOURCE_GEMINI,"can_plan_read_only_by_id":False,
    },
}
FALSE_FLAGS={
    "reference_only":True,
    "real_provider_capability_live_verified":False,
    "provider_id_authenticated":False,
    "provider_object_retrieved":False,
    "provider_response_persisted":False,
    "provider_request_id_correlated_to_billing":False,
    "provider_idempotent_post_verified":False,
    "provider_side_exactly_once_verified":False,
    "real_owner_identity_verified":False,
    "owner_presence_verified":False,
    "independent_journal_antirollback_verified":False,
    "real_budget_reserved":False,
    "actual_charge_or_refund_verified":False,
    "network_called":False,
    "model_post_authorized":False,
    "model_post_performed":False,
    "automatic_retry_permitted":False,
    "same_nonce_reusable":False,
    "billing_settlement_verified":False,
    "safe_to_resume":False,
}
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,199}\Z")
_INTENT_KEYS={
    "provider","mode","owner_id","tenant_id","workspace_id",
    "nonce_hex","signed_intent_sha256","full_provider_request_sha256",
    "journal_state","documented_retention_opt_in",
    "transport_auto_retry_enabled",
}
_LOCATOR_KEYS={"response_id","batch_id","batch_custom_id","diagnostic_request_id"}


def _hash(v:Any)->bool:
    return type(v) is str and bool(_HEX64.fullmatch(v))


def _id(v:Any)->bool:
    return type(v) is str and (v=="" or bool(_ID.fullmatch(v)))


def _out(state:str,reason:str,mode:str="")->dict[str,Any]:
    entry=DOCUMENTED_MODES.get(mode)
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "read_only_planning_candidate":state==READ_CANDIDATE,
        "documented_identifier_kind":entry["identifier_kind"] if entry else "none",
        "source_url":entry["source_url"] if entry else "",
        "recovery_does_not_prove_no_charge":True,
        "must_not_automatically_retry":True,
        **FALSE_FLAGS,
    }


def review_provider_read_only_recovery_reference(
    *,intent:Any,locator:Any,
)->dict[str,Any]:
    """Fail-closed review of hypothetical GET, independent of actual network.

    An ID captured from a provider response AFTER a crash cannot be assumed.
    Owner/tenant/nonce and ID persistence are caller claims, not verified.
    """
    if type(intent) is not dict or set(intent)!=_INTENT_KEYS:
        return _out("BLOCKED","EXACT_INTENT_SCHEMA_REQUIRED")
    mode=intent["mode"]
    if type(mode) is not str or mode not in DOCUMENTED_MODES:
        return _out("BLOCKED","UNDOCUMENTED_PROVIDER_MODE")
    row=DOCUMENTED_MODES[mode]
    if (intent["provider"]!=row["provider"]
        or not all(type(intent[k]) is str and bool(_ID.fullmatch(intent[k]))
                   for k in ("owner_id","tenant_id","workspace_id"))
        or not _hash(intent["nonce_hex"]) or intent["nonce_hex"]=="0"*64
        or not _hash(intent["signed_intent_sha256"])
        or not _hash(intent["full_provider_request_sha256"])
        or type(intent["documented_retention_opt_in"]) is not bool
        or type(intent["transport_auto_retry_enabled"]) is not bool):
        return _out("BLOCKED","PROVIDER_OR_SCOPED_INTENT_INVALID",mode)
    if intent["transport_auto_retry_enabled"]:
        return _out("BLOCKED","AUTO_RETRY_MUST_BE_DISABLED_BEFORE_INTEGRATION",mode)
    if intent["journal_state"] not in ("DISPATCH_CLAIMED","UNKNOWN_OUTCOME"):
        return _out("BLOCKED","NO_POTENTIAL_PAID_DISPATCH_TO_RECOVER",mode)
    if type(locator) is not dict or set(locator)!=_LOCATOR_KEYS:
        return _out("BLOCKED","EXACT_PERSISTED_LOCATOR_SCHEMA_REQUIRED",mode)
    if any(not _id(v) for v in locator.values()):
        return _out("BLOCKED","MALFORMED_PERSISTED_IDENTIFIER",mode)
    if not row["can_plan_read_only_by_id"]:
        return _out(NO_SAFE_GET,
            "NO_DOCUMENTED_SINGLE_REQUEST_GET_OR_RETAINED_OBJECT",mode)
    if mode in (MODE_OPENAI_BACKGROUND,MODE_OPENAI_STORED):
        if (not locator["response_id"].startswith("resp_")
            or any(locator[k] for k in (
                "batch_id","batch_custom_id","diagnostic_request_id"
            ))):
            return _out("BLOCKED","NO_KNOWN_RESPONSE_ID_OR_IDENTIFIERS_REBOUND",mode)
        if mode==MODE_OPENAI_STORED and not intent["documented_retention_opt_in"]:
            return _out("BLOCKED","STORED_RESPONSE_OPT_IN_NOT_EVIDENCED",mode)
        # Also needs actual provider object retention within window; not
        # verifiable here. An expired/404 GET must not become a retry permit.
        return _out(READ_CANDIDATE,
            "MATH_ONLY_POSSIBLE_GET_BY_PERSISTED_RESPONSE_ID_NO_POST",mode)
    if mode==MODE_ANTHROPIC_BATCH:
        if (not locator["batch_id"].startswith("msgbatch_")
            or not bool(locator["batch_custom_id"])
            or locator["response_id"] or locator["diagnostic_request_id"]):
            return _out("BLOCKED","NO_KNOWN_BATCH_AND_CUSTOM_ID",mode)
        return _out(READ_CANDIDATE,
            "MATH_ONLY_POSSIBLE_GET_KNOWN_BATCH_THEN_MATCH_CUSTOM_ID",mode)
    return _out("BLOCKED","UNREACHABLE_PROVIDER_CAPABILITY_ROW",mode)


def classify_read_only_recovery_observation_reference(
    *,preflight:Any,observation:Any,
)->dict[str,Any]:
    """Mock GET results are untrusted observations, never an API settlement."""
    if (type(preflight) is not dict
        or preflight.get("state")!=READ_CANDIDATE
        or type(observation) is not dict
        or set(observation)!={"response_status","identifier_matches","request_digest_matches"}
        or type(observation["identifier_matches"]) is not bool
        or type(observation["request_digest_matches"]) is not bool):
        return _out("BLOCKED","NO_VALID_READ_ONLY_PREFLIGHT_OR_OBSERVATION")
    status=observation["response_status"]
    if status not in ("COMPLETED","PENDING","FAILED","NOT_FOUND","EXPIRED","ERROR"):
        return _out("BLOCKED","UNRECOGNIZED_PROVIDER_OBSERVATION")
    if not observation["identifier_matches"] or not observation["request_digest_matches"]:
        return _out("BLOCKED","WRONG_PROVIDER_OBJECT_OR_REQUEST_REBOUND")
    # Even COMPLETED with exact IDs does not verify amount billed, paid
    # provider signature, or independently fresh owner/journal keys.
    return _out("READ_ONLY_OBSERVATION_INCONCLUSIVE_UNTRUSTED",
                "NEVER_RETRY_FROM_STATUS_"+status,
                preflight.get("source_url_mode",""))


__all__=[
    "SCHEMA","MODE_OPENAI_BACKGROUND","MODE_OPENAI_STORED",
    "MODE_OPENAI_UNSTORED","MODE_ANTHROPIC_BATCH",
    "MODE_ANTHROPIC_SYNC","MODE_GEMINI_SYNC","DOCUMENTED_MODES",
    "READ_CANDIDATE","NO_SAFE_GET","FALSE_FLAGS",
    "review_provider_read_only_recovery_reference",
    "classify_read_only_recovery_observation_reference",
]
