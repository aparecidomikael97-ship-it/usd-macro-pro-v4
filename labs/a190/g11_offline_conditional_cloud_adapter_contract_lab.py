"""A190 G11: OFFLINE wire-shape drafts for DynamoDB and Firestore.

Never connects, authenticates, retries, sends, effects, provisions, or bills.
These JSON envelopes are implementation sketches based on official API docs,
not real IAM tests, trustworthy receipts, monotonic storage or P0 approval.
"""
from __future__ import annotations

from hashlib import sha256
import re
import time

from g8_independent_authority_protocol_lab import (
    EVENT_DOMAIN, EVENT_FIELDS, canonical, check_seal,
)

SEMANTIC_HEX = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{5,29}$")
SYNTHETIC_TABLE = "AION_A190_G11_LAB_ONLY"
SYNTHETIC_PROJECT = "aion-g11-synthetic-project"
DDB_OPERATIONS = frozenset({"PutItem", "GetItem"})
FIRESTORE_OPERATIONS = frozenset({"PATCH", "GET"})
ALWAYS_DENY = "HARD_NO_GO_NOT_AUTHORIZED_TO_EXECUTE"


class ContractDenied(ValueError):
    pass


def original_subject(event, trusted_issuer_public_key, *, now=None):
    stamp = int(time.time()) if now is None else now
    payload = check_seal(
        event, trusted_issuer_public_key, EVENT_DOMAIN, EVENT_FIELDS
    )
    if payload is None:
        raise ContractDenied("G11_BAD_ORIGINAL_ISSUER_SIGNATURE")
    if (payload["schema"] != "A190_G8_EVENT_V1"
            or payload["issuer"] != "LAB_EVENT_ISSUER_NOT_REAL"
            or not isinstance(payload["tenant"], str)
            or not TOKEN.fullmatch(payload["tenant"])
            or not isinstance(payload["semantic_digest"], str)
            or not SEMANTIC_HEX.fullmatch(payload["semantic_digest"])
            or not isinstance(payload["event_ref"], str)
            or not payload["event_ref"] or len(payload["event_ref"]) > 120
            or type(payload["not_before"]) is not int
            or type(payload["expires"]) is not int
            or payload["not_before"] > stamp
            or payload["expires"] <= stamp
            or payload["expires"] - payload["not_before"] > 3600
            or not isinstance(payload["nonce"], str)
            or not payload["nonce"]):
        raise ContractDenied("G11_BAD_ORIGINAL_SCOPE_OR_TIME")
    subject = {
        "schema": "A190_G11_CANONICAL_SUBJECT_V1",
        "tenant": payload["tenant"],
        "semantic_digest": payload["semantic_digest"],
    }
    # Exclude attacker-supplied request_id or claimed_original_id and even
    # issuer event_ref: same semantic content must be one native object key.
    key_hash = sha256(b"A190:G11:SEMANTIC_NATIVE_KEY\0" + canonical(subject))
    return {
        "subject": subject,
        "original_event_ref": payload["event_ref"],
        "native_id": "aion-g11-" + key_hash.hexdigest(),
    }


def _reference(event, pin, request_id):
    if not isinstance(request_id, str) or not TOKEN.fullmatch(request_id):
        raise ContractDenied("G11_BAD_REQUEST_IDENTIFIER")
    return original_subject(event, pin)


def _doc_fields(reference, request_id):
    subject = reference["subject"]
    return {
        "schema": {"stringValue": subject["schema"]},
        "tenant": {"stringValue": subject["tenant"]},
        "semantic_digest": {"stringValue": subject["semantic_digest"]},
        "original_ref": {"stringValue": reference["original_event_ref"]},
        "request_id": {"stringValue": request_id},
        "state": {"stringValue": "RESERVED_STORAGE_ONLY"},
        "real_effect": {"booleanValue": False},
    }


def dynamodb_envelopes(event, trusted_issuer_public_key, request_id):
    reference = _reference(event, trusted_issuer_public_key, request_id)
    subject = reference["subject"]
    pk = reference["native_id"]
    item = {
        "PK": {"S": pk},
        "schema": {"S": subject["schema"]},
        "tenant": {"S": subject["tenant"]},
        "semantic_digest": {"S": subject["semantic_digest"]},
        "original_ref": {"S": reference["original_event_ref"]},
        "request_id": {"S": request_id},
        "state": {"S": "RESERVED_STORAGE_ONLY"},
        "real_effect": {"BOOL": False},
    }
    return {
        "provider": "AWS_DYNAMODB_OFFLINE_ONLY",
        "operation_intent": "RESERVE_NATIVE_DB_NOT_REAL_EFFECT",
        "native_id": pk,
        "table_assumption": "PARTITION_KEY_PK_ONLY_NO_SORT_KEY",
        "put": {
            "action": "PutItem",
            "args": {
                "TableName": SYNTHETIC_TABLE,
                "Item": item,
                # Without this PutItem silently replaces the old row.
                "ConditionExpression": "attribute_not_exists(#pk)",
                "ExpressionAttributeNames": {"#pk": "PK"},
                "ReturnValues": "NONE",
            },
        },
        "lookup": {
            "action": "GetItem",
            "args": {
                "TableName": SYNTHETIC_TABLE,
                "Key": {"PK": {"S": pk}},
                # GetItem defaults to eventually consistent otherwise.
                "ConsistentRead": True,
            },
        },
        "allowed_operations_documentary_only": sorted(DDB_OPERATIONS),
        "execution_allowed": False,
        "external_root_verified": False,
        "vendor_effect_verified": False,
        "security_decision": ALWAYS_DENY,
    }


def firestore_envelopes(event, trusted_issuer_public_key, request_id,
                        *, project=SYNTHETIC_PROJECT):
    reference = _reference(event, trusted_issuer_public_key, request_id)
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise ContractDenied("G11_BAD_DOCUMENTARY_PROJECT_ID")
    native_id = reference["native_id"]
    resource = (
        "projects/" + project +
        "/databases/(default)/documents/aion_g11_reservations/" +
        native_id
    )
    return {
        "provider": "GOOGLE_FIRESTORE_OFFLINE_ONLY",
        "operation_intent": "RESERVE_NATIVE_DB_NOT_REAL_EFFECT",
        "native_id": native_id,
        "put": {
            "method": "PATCH",
            "url_shape": "https://firestore.googleapis.com/v1/" + resource,
            # Official REST patch currentDocument.exists=false precondition;
            # omission would overwrite an existing reservation.
            "query": {"currentDocument.exists": "false"},
            "body": {
                "name": resource,
                "fields": _doc_fields(reference, request_id),
            },
        },
        "lookup": {
            "method": "GET",
            "url_shape": "https://firestore.googleapis.com/v1/" + resource,
            # Server-side Get defaults to strongly consistent read.
            "query": {},
        },
        "allowed_operations_documentary_only": sorted(FIRESTORE_OPERATIONS),
        "execution_allowed": False,
        "external_root_verified": False,
        "vendor_effect_verified": False,
        "security_decision": ALWAYS_DENY,
    }


def classify_wire_response(provider, *, stage, status_code=None,
                           error_code=None, response_body=None):
    """Contract-level decision ONLY. Never authorize effect or a second send."""
    if provider not in {"dynamodb", "firestore"}:
        raise ContractDenied("G11_UNKNOWN_PROVIDER")
    if stage not in {"RESERVE", "READ_ONLY_RECONCILE"}:
        raise ContractDenied("G11_UNSAFE_OPERATION")
    duplicate = (
        (provider == "dynamodb"
         and error_code == "ConditionalCheckFailedException")
        or (provider == "firestore"
            and error_code in {"ALREADY_EXISTS", "FAILED_PRECONDITION"})
    )
    if status_code is None:
        state = "UNCERTAIN_ZERO_AUTO_RESEND"
    elif duplicate:
        state = "DUPLICATE_STORAGE_RESERVATION_READ_ONLY_ONLY"
    elif type(status_code) is int and 200 <= status_code < 300:
        # A database ACK is NOT an effect provider ACK, regardless of body.
        state = ("STORAGE_RESERVATION_ACK_NOT_EFFECT_PROOF"
                 if stage == "RESERVE"
                 else "STORAGE_READ_ONLY_NOT_EFFECT_PROOF")
    else:
        state = "UNCERTAIN_ZERO_AUTO_RESEND"
    return {
        "classification": state,
        "real_effect_allowed": False,
        "auto_resend": False,
        "receipt_authenticity_independent": False,
        "response_body_trusted_as_effect_proof": False,
        "operational_verdict": ALWAYS_DENY,
    }


def check_dangerous_request(provider, operation):
    if provider == "dynamodb":
        allowed = DDB_OPERATIONS
    elif provider == "firestore":
        allowed = FIRESTORE_OPERATIONS
    else:
        raise ContractDenied("G11_UNKNOWN_PROVIDER")
    if operation not in allowed:
        raise ContractDenied("G11_NOT_IN_READ_OR_CONDITIONAL_PUT_ALLOWLIST")
    # Still only an offline *shape*; valid operation != auth to send.
    return "DOCUMENTARY_ALLOWLIST_MATCH_NO_TRANSPORT"


if __name__ == "__main__":
    print("A190 G11. Offline envelope module; no CLI executes a provider call.")
