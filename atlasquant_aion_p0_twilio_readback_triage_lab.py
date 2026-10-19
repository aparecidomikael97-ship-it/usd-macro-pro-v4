"""P0 Twilio-style readback triage: PURE LAB, READ-ONLY, NEVER SEND OR RETRY.

A query result, callback, or even apparently matching message SID is NOT
authenticated producer evidence here. A complete *listing* with zero matches
cannot prove an earlier POST did not create a resource. Multiple matching
resources cannot be collapsed into one. All output stays HUMAN_REVIEW_ONLY,
and the original uncertain outcome remains unchanged.

No Twilio SDK, endpoint, credentials, network, database, API actions or side
effects. Inputs are synthetic/untrusted and are never elevated to proof.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "AION_P0_TWILIO_READBACK_TRIAGE_LAB_V1"
_ACCOUNT = re.compile(r"^AC[0-9a-fA-F]{32}$")
_SID = re.compile(r"^(?:SM|MM)[0-9a-fA-F]{32}$")
_PHONE = re.compile(r"^\+[1-9][0-9]{7,14}$")
_OP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")
_ALLOWED_STATUS = frozenset({
    "accepted", "scheduled", "queued", "sending", "sent",
    "delivered", "read", "undelivered", "failed", "canceled"
})
_EXPECTED = frozenset({"operation_ref", "account_sid", "to", "from", "known_message_sid"})
_EVIDENCE = frozenset({"source", "pagination_complete", "source_error", "messages"})
_MESSAGE = frozenset({"sid", "account_sid", "to", "from", "status"})


def _decision(reason: str, *, review=None, observed=(), statuses=()) -> dict[str, Any]:
    # Include status hints for human triage WITHOUT promoting their trust.
    return {
        "schema": SCHEMA,
        "state": "BLOCKED",
        "reason": reason,
        "review": review or "MANUAL_PROVIDER_REVIEW_REQUIRED",
        "observed_candidate_count": len(observed),
        "observed_sids": tuple(observed),
        "observed_statuses": tuple(statuses),
        "provider_identity_authenticated": False,
        "provider_readback_authenticated": False,
        "provider_completeness_proven": False,
        "current_external_effect_verified": False,
        "definitive_no_effect_fence_verified": False,
        "unknown_outcome_cleared": False,
        "attempt_state_mutated": False,
        "automatic_retry_allowed": False,
        "resend_authorized": False,
        "outbox_release_authorized": False,
        "effect_ledger_authorized": False,
        "worker_armed": False,
        "network_called": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def inspect_twilio_message_readback_lab(expected: Any, observation: Any) -> dict[str, Any]:
    """Treat all GET/list/callback-shaped data as untrusted lab evidence.

    *Known SID* is the strongest local selector if previously persisted from
    an authenticated response, but this LAB cannot verify such provenance.
    If the first POST response was lost, an empty query never proves absence.
    """
    if type(expected) is not dict or any(type(k) is not str for k in expected) or set(expected) != _EXPECTED:
        return _decision("EXPECTED_ATTEMPT_SCOPE_INVALID")
    if (type(expected["operation_ref"]) is not str
            or _OP.fullmatch(expected["operation_ref"]) is None
            or type(expected["account_sid"]) is not str
            or _ACCOUNT.fullmatch(expected["account_sid"]) is None
            or type(expected["to"]) is not str or _PHONE.fullmatch(expected["to"]) is None
            or type(expected["from"]) is not str or _PHONE.fullmatch(expected["from"]) is None
            or type(expected["known_message_sid"]) is not str
            or (expected["known_message_sid"] != "" and _SID.fullmatch(expected["known_message_sid"]) is None)):
        return _decision("EXPECTED_ATTEMPT_BINDING_INVALID")

    if type(observation) is not dict or any(type(k) is not str for k in observation) or set(observation) != _EVIDENCE:
        return _decision("READBACK_SHAPE_INVALID")
    source = observation["source"]
    if type(source) is not str or source not in {"MESSAGE_LIST", "MESSAGE_FETCH", "STATUS_CALLBACK"}:
        return _decision("READBACK_SOURCE_INVALID")
    if type(observation["pagination_complete"]) is not bool:
        return _decision("PAGINATION_TYPE_INVALID")
    if observation["source_error"] is not None:
        if type(observation["source_error"]) is not str or observation["source_error"] not in {
            "TIMEOUT", "AUTH_ERROR", "RATE_LIMIT", "SERVER_ERROR", "NOT_FOUND", "UNKNOWN"
        }:
            return _decision("READBACK_ERROR_INVALID")
        return _decision("READBACK_FAILED_OR_UNAVAILABLE")
    records = observation["messages"]
    if type(records) is not list or len(records) > 100:
        return _decision("READBACK_MESSAGES_INVALID")
    if source == "STATUS_CALLBACK":
        return _decision("CALLBACK_ALONE_UNTRUSTED")
    if source == "MESSAGE_FETCH" and len(records) > 1:
        return _decision("FETCH_MUST_RETURN_AT_MOST_ONE")
    if source == "MESSAGE_FETCH" and not expected["known_message_sid"]:
        return _decision("FETCH_WITHOUT_DURABLY_KNOWN_SID_UNSUPPORTED")

    matches: list[dict] = []
    observed_sids: set[str] = set()
    for item in records:
        if type(item) is not dict or any(type(k) is not str for k in item) or set(item) != _MESSAGE:
            return _decision("READBACK_ROW_MALFORMED")
        if any(type(item[k]) is not str for k in _MESSAGE):
            return _decision("READBACK_ROW_TYPES_INVALID")
        if (_SID.fullmatch(item["sid"]) is None
                or _ACCOUNT.fullmatch(item["account_sid"]) is None
                or _PHONE.fullmatch(item["to"]) is None
                or _PHONE.fullmatch(item["from"]) is None
                or item["status"] not in _ALLOWED_STATUS):
            return _decision("READBACK_ROW_VALUES_INVALID")
        if item["sid"] in observed_sids:
            return _decision("READBACK_DUPLICATE_SID_AMBIGUOUS")
        observed_sids.add(item["sid"])
        # A row claiming some other account/sender/recipient is not evidence
        # of this local attempt, even if its SID resembles the expected SID.
        if item["account_sid"] != expected["account_sid"]:
            if expected["known_message_sid"] == item["sid"]:
                return _decision("KNOWN_SID_ACCOUNT_SCOPE_CONFLICT")
            continue
        if item["to"] != expected["to"] or item["from"] != expected["from"]:
            if expected["known_message_sid"] == item["sid"]:
                return _decision("KNOWN_SID_DESTINATION_SCOPE_CONFLICT")
            continue
        if expected["known_message_sid"] and item["sid"] != expected["known_message_sid"]:
            continue
        matches.append(item)

    if not matches:
        if source == "MESSAGE_LIST" and not observation["pagination_complete"]:
            return _decision("LIST_INCOMPLETE_NO_MATCH_PROOF")
        # Even allegedly complete pagination is merely caller supplied here;
        # operational absence is NEVER inferred.
        return _decision("NO_MATCH_IS_NOT_NO_EFFECT")
    matches.sort(key=lambda m: m["sid"])
    if len(matches) > 1:
        return _decision(
            "MULTIPLE_CANDIDATES_AMBIGUOUS",
            observed=[m["sid"] for m in matches],
            statuses=[m["status"] for m in matches],
        )
    m = matches[0]
    if source == "MESSAGE_LIST" and not observation["pagination_complete"]:
        return _decision(
            "POSSIBLE_MATCH_FROM_INCOMPLETE_LIST",
            observed=[m["sid"]], statuses=[m["status"]],
        )
    return _decision(
        "POSSIBLE_EXISTING_MESSAGE_UNAUTHENTICATED",
        review="RECONCILE_EXACT_SID_WITH_AUTHENTICATED_PROVIDER",
        observed=[m["sid"]],
        statuses=[m["status"]],
    )
