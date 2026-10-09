"""AION V2 HTTP GET-only retry/redirect reference and actual adapter AST audit.

OFFLINE ONLY: no imported HTTP client, no sockets, provider tokens, requests
or urllib3 transport. Plans/traces are caller supplied and never authorise
network GET, generation POST, owner identity, spending or automatic retry.

The audit inspects the EXISTING provider adapter as untrusted source to
identify deployment blockers, not to certify real third-party SDK behavior.
"""
from __future__ import annotations

import ast
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA="ATLASQUANT_AION_V2_HTTP_NO_RETRY_GET_ONLY_AUDIT_REFERENCE_V1"
GET_PLAN="OFFLINE_STRICT_GET_TRANSPORT_SHAPE_NO_NETWORK_AUTHORITY"
TRACE="SYNTHETIC_ONE_SHOT_GET_TRACE_MATH_ONLY_UNTRUSTED"
AUDIT="CURRENT_PROVIDER_POST_ADAPTER_AUDIT_FINDINGS"
_CAPTURE_MATCH="TWO_SIGNED_CAPTURE_HEADS_MATH_MATCH_UNTRUSTED_NO_NETWORK"
_ALLOWED_ORIGINS={
    "openai":"https://api.openai.com",
    "anthropic":"https://api.anthropic.com",
}
_OPENAI=re.compile(r"/v1/responses/resp_[A-Za-z0-9_-]{1,123}\Z")
_ANTHROPIC=re.compile(
    r"/v1/messages/batches/msgbatch_[A-Za-z0-9_-]{1,120}(/results)?\Z"
)
_HEX64=re.compile(r"[a-f0-9]{64}\Z")
_FALSE={
    "reference_only":True,
    "verified_live_sdk_config":False,
    "verified_network_retry_disabled":False,
    "verified_live_redirect_block":False,
    "verified_network_tls":False,
    "verified_proxy_environment_disabled":False,
    "owner_identity_enrolled":False,
    "two_independent_fresh_witnesses_verified":False,
    "captured_response_id_authentic":False,
    "provider_endpoint_live_authenticated":False,
    "get_authorized":False,
    "get_performed":False,
    "post_authorized":False,
    "post_performed":False,
    "automatic_retry_permitted":False,
    "same_nonce_reusable":False,
    "provider_post_idempotency_verified":False,
    "actual_billing_verified":False,
    "billing_settlement_verified":False,
    "network_called":False,
    "safe_to_resume":False,
}


def _canonical(value:Any)->bytes:
    return json.dumps(
        value,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False,
    ).encode("utf-8")


def _out(state:str,reason:str,*,plans:Any=None,findings:Any=None)->dict[str,Any]:
    return {
        "schema":SCHEMA,"state":state,"reason":reason,
        "offline_plans":plans if state==GET_PLAN else [],
        "findings":findings if state==AUDIT else [],
        "must_not_automatically_retry":True,
        **_FALSE,
    }


def _valid_path(provider:Any,path:Any)->bool:
    if type(provider) is not str or type(path) is not str:
        return False
    if provider=="openai":
        return bool(_OPENAI.fullmatch(path))
    if provider=="anthropic":
        return bool(_ANTHROPIC.fullmatch(path))
    return False


def review_offline_get_transport_shape(
    *,capture_witness_review:Any,provider:Any,
    timeout_seconds:Any,transport_policy:Any,
)->dict[str,Any]:
    """Inert transport plan from already untrusted #1138 match.

    Caller-supplied signed head math is not proof of enrolled key identity;
    this merely fails closed on a proposed future HTTP configuration.
    """
    if (type(capture_witness_review) is not dict
        or capture_witness_review.get("state")!=_CAPTURE_MATCH
        or capture_witness_review.get("reference_only") is not True
        or capture_witness_review.get("get_authorized") is True
        or capture_witness_review.get("real_get_authorized") is not False
        or capture_witness_review.get("real_get_performed") is not False
        or capture_witness_review.get("network_called") is not False):
        return _out("BLOCKED","UNTRUSTED_CAPTURE_WITNESS_PRECHECK_REQUIRED")
    if type(provider) is not str or provider not in _ALLOWED_ORIGINS:
        return _out("BLOCKED","UNSUPPORTED_PROVIDER_FOR_FIXED_GET")
    if (type(timeout_seconds) not in (int,float)
        or not 1<=timeout_seconds<=30):
        return _out("BLOCKED","FINITE_BOUNDED_TIMEOUT_REQUIRED")
    policy_keys={
        "method","allow_redirects","trust_env","verify_tls",
        "max_attempts","http_adapter_retry_total",
        "sdk_auto_retry_enabled","proxy_configured",
        "follow_location_header","allow_method_fallback",
    }
    if (type(transport_policy) is not dict
        or set(transport_policy)!=policy_keys
        or transport_policy!={
            "method":"GET","allow_redirects":False,"trust_env":False,
            "verify_tls":True,"max_attempts":1,
            "http_adapter_retry_total":0,"sdk_auto_retry_enabled":False,
            "proxy_configured":False,"follow_location_header":False,
            "allow_method_fallback":False,
        }):
        return _out("BLOCKED","REDIRECT_RETRY_PROXY_METHOD_OR_TLS_POLICY_INVALID")
    routes=capture_witness_review.get("offline_relative_get_paths")
    if (type(routes) is not list or not 1<=len(routes)<=2
        or any(type(route) is not dict
            or set(route)!={"method","relative_path"}
            or route["method"]!="GET"
            or not _valid_path(provider,route["relative_path"])
            for route in routes)
        or len({r["relative_path"] for r in routes})!=len(routes)):
        return _out("BLOCKED","ONLY_EXACT_PROVIDER_GET_PATHS_ACCEPTED")
    if provider=="openai" and len(routes)!=1:
        return _out("BLOCKED","OPENAI_SINGLE_GET_REQUIRED")
    if provider=="anthropic":
        if (len(routes)!=2
            or routes[0]["relative_path"].endswith("/results")
            or routes[1]["relative_path"]!=routes[0]["relative_path"]+"/results"):
            return _out("BLOCKED","ANTHROPIC_BATCH_STATUS_THEN_RESULTS_REQUIRED")
    plans=[
        {
            "method":"GET","origin":_ALLOWED_ORIGINS[provider],
            "relative_path":r["relative_path"],
            "timeout_seconds":timeout_seconds,
            "allow_redirects":False,"trust_env":False,
            "verify_tls":True,"max_attempts":1,
            "http_adapter_retry_total":0,
            "sdk_auto_retry_enabled":False,
            "proxy_configured":False,"follow_location_header":False,
            "allow_method_fallback":False,
        }
        for r in routes
    ]
    return _out(GET_PLAN,"UNTRUSTED_FIXED_GET_CONFIGURATION_ONLY_NO_CLIENT",
                plans=plans)


def review_mock_transport_trace(
    *,offline_plan_result:Any,observed_attempts:Any,
)->dict[str,Any]:
    """Offline abstract trace: one GET attempt/path, no hidden resend.

    Each attempt record states exactly path/method plus outcome type. It is
    not an actual HTTP log; a malicious library can hide its extra attempt.
    """
    if (type(offline_plan_result) is not dict
        or offline_plan_result.get("state")!=GET_PLAN
        or offline_plan_result.get("reference_only") is not True
        or offline_plan_result.get("get_authorized") is not False
        or offline_plan_result.get("network_called") is not False):
        return _out("BLOCKED","NO_VALID_OFFLINE_TRANSPORT_PLAN")
    plans=offline_plan_result.get("offline_plans")
    if (type(plans) is not list or not 1<=len(plans)<=2
        or type(observed_attempts) is not list
        or not 1<=len(observed_attempts)<=len(plans)):
        return _out("BLOCKED","TRACE_ATTEMPT_COUNT_OR_PLAN_INVALID")
    events={"RESPONSE","TIMEOUT","CONNECTION_ERROR","TLS_ERROR","REDIRECT"}
    for i,event in enumerate(observed_attempts):
        if (type(event) is not dict
            or set(event)!={"method","origin","relative_path",
                            "event","http_status","attempt_no"}
            or type(event["event"]) is not str
            or event["event"] not in events
            or event["method"]!="GET"
            or event["origin"]!=plans[i]["origin"]
            or event["relative_path"]!=plans[i]["relative_path"]
            or type(event["attempt_no"]) is not int or event["attempt_no"]!=1
            or type(event["http_status"]) is not int
            or not 0<=event["http_status"]<=599):
            return _out("BLOCKED","TRACE_EXTRA_HOP_POST_FALLBACK_OR_RETRY")
        if event["event"]=="RESPONSE":
            if not 200<=event["http_status"]<=599:
                return _out("BLOCKED","RESPONSE_STATUS_INVALID")
            if 300<=event["http_status"]<400:
                return _out("BLOCKED","REDIRECT_STATUS_MUST_NOT_BE_FOLLOWED")
        else:
            if event["http_status"]!=0:
                return _out("BLOCKED","ERROR_EVENT_MUST_NOT_INVENT_HTTP_STATUS")
            if event["event"]=="REDIRECT":
                return _out("BLOCKED","LOCATION_REDIRECT_MUST_NOT_BE_FOLLOWED")
            if i!=len(observed_attempts)-1:
                return _out("BLOCKED","NO_SECOND_STEP_AFTER_FAILED_GET")
        if i==1:
            previous=observed_attempts[0]
            if (previous["event"]!="RESPONSE"
                or previous["http_status"]!=200):
                return _out("BLOCKED","BATCH_RESULTS_REQUIRES_SUCCESSFUL_STATUS_GET")
    return _out(TRACE,
                "MOCK_GET_TRACE_NO_RETRIES_BILLING_STILL_UNKNOWN")


def audit_existing_provider_source(source:Any)->dict[str,Any]:
    """Analyze actual repo adapter AST without executing source or secrets."""
    if type(source) is not str or len(source)>300_000:
        return _out("BLOCKED","SOURCE_TEXT_REQUIRED")
    try:
        tree=ast.parse(source)
    except (SyntaxError,ValueError,TypeError,RecursionError):
        return _out("BLOCKED","PROVIDER_SOURCE_UNPARSABLE")
    method=next((
        node for node in tree.body
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
        and node.name=="execute_openai_answer"
    ),None)
    if method is None:
        return _out("BLOCKED","KNOWN_PROVIDER_EXECUTION_FUNCTION_MISSING")
    calls=[
        n for n in ast.walk(method)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and n.func.attr=="post"
    ]
    if len(calls)!=1:
        return _out("BLOCKED","EXPECTED_ONE_VISIBLE_POST_CALL")
    call=calls[0]
    kw={k.arg for k in call.keywords}
    findings=[]
    if "allow_redirects" not in kw:
        findings.append("POST_REDIRECT_POLICY_NOT_EXPLICITLY_DISABLED")
    else:
        val=next(k.value for k in call.keywords if k.arg=="allow_redirects")
        if not isinstance(val,ast.Constant) or val.value is not False:
            findings.append("POST_REDIRECTS_NOT_STATIC_FALSE")
    if any(
        isinstance(n,ast.BoolOp) and isinstance(n.op,ast.Or)
        and any(isinstance(v,ast.Name) and v.id=="session"
                for v in n.values)
        for n in ast.walk(method)
    ):
        findings.append("CALLER_SESSION_RETRY_ADAPTER_NOT_ATTESTED")
    if not any(isinstance(n,ast.Call)
               and isinstance(n.func,ast.Name) and n.func.id=="_full_request_sha256"
               for n in ast.walk(method)):
        findings.append("FULL_PROVIDER_REQUEST_DIGEST_NOT_FOUND")
    if not findings:
        findings.append("STATIC_POST_SITE_LOOKS_BOUND_BUT_NOT_LIVE_ATTESTED")
    # Source AST analysis does NOT establish actual HTTP adapter behavior.
    return _out(AUDIT,"STATIC_FINDINGS_NOT_A_LIVE_SDK_AUDIT",
                findings=sorted(findings))


__all__=[
    "SCHEMA","GET_PLAN","TRACE","AUDIT",
    "review_offline_get_transport_shape",
    "review_mock_transport_trace","audit_existing_provider_source",
]
