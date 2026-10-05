"""AION B2B recurring-service business action authorization ceremony.

Cryptographic owner ceremony after a clean recurring business-action preflight.

Accepted authorization decisions are exactly:
- AUTHORIZE_BUSINESS_ACTION
- DENY_BUSINESS_ACTION

The signature binds the exact already-persisted commercial choice and all
preflight/evidence digests. Verification proves owner intent only. It does not
persist the authorization and does not execute the underlying business action.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_b2b_owner_renewal_action_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_CEREMONY_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_REQUEST_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_VERIFICATION_V1"
PURPOSE = "B2B_OWNER_EXPLICIT_RECURRING_BUSINESS_ACTION_DECISION"
MECHANISM = "ED25519_EXTERNAL_OWNER_ACTION_KEY"
DECISIONS = (
    "AUTHORIZE_BUSINESS_ACTION",
    "DENY_BUSINESS_ACTION",
)
MAX_WINDOW_SECONDS = 180

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")

_AUTHORITY_FIELDS = (
    "business_action_authorized",
    "renewal_authorized",
    "expansion_authorized",
    "non_renewal_authorized",
    "remediation_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "package_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
    "network_called",
    "executes_action",
)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def canonical_business_action_decision_bytes(
    request_body: Mapping[str, Any],
) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_business_action_decision_bytes(value)
    ).hexdigest()


def _text(value: Any, limit: int = 420) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    row = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(row.get("owner_id"), 120),
        "tenant_id": _text(row.get("tenant_id"), 120),
        "workspace_id": _text(row.get("workspace_id"), 120),
    }


def _parse_ts(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("timestamp must be RFC3339 UTC")
    try:
        return datetime.fromisoformat(
            value[:-1] + "+00:00"
        ).astimezone(timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp") from exc


def _window_blockers(
    *,
    issued_at: Any,
    expires_at: Any,
    now_ts: Any,
) -> list[str]:
    try:
        issued = _parse_ts(issued_at)
        expires = _parse_ts(expires_at)
        now = _parse_ts(now_ts)
    except ValueError:
        return ["BUSINESS_ACTION_TIME_INVALID"]

    blockers: list[str] = []
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("BUSINESS_ACTION_WINDOW_INVALID")
    elif window > MAX_WINDOW_SECONDS:
        blockers.append("BUSINESS_ACTION_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("BUSINESS_ACTION_NOT_YET_VALID")
    if expires <= now:
        blockers.append("BUSINESS_ACTION_REQUEST_EXPIRED")
    return blockers


def _decode_signature(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("signature required")
    try:
        raw = value.encode("ascii")
        decoded = base64.urlsafe_b64decode(
            raw + b"=" * (-len(raw) % 4)
        )
    except Exception as exc:
        raise ValueError("invalid signature encoding") from exc
    if len(decoded) != 64:
        raise ValueError("Ed25519 signature must be 64 bytes")
    return decoded


def _public_key_fingerprint(entry: Any) -> str:
    encoded = str(entry.public_key_b64 or "").encode("ascii")
    raw = base64.urlsafe_b64decode(
        encoded + b"=" * (-len(encoded) % 4)
    )
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "authorization_decision": "UNDECIDED",
        "owner_action_identity_verified": False,
        "owner_action_signature_verified": False,
        "action_decision_verified": False,
        "action_authorization_intent": False,
        "action_denial_intent": False,
        "action_record": {},
        "action_record_digest": "",
        "action_record_persisted": False,
        "generic_chat_instruction_accepted_as_action_authorization": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def _preflight_blockers(
    action_preflight: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    row = (
        dict(action_preflight)
        if isinstance(action_preflight, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("BUSINESS_ACTION_PREFLIGHT_SCHEMA_INVALID")
    if (
        row.get("state")
        != "READY_FOR_BUSINESS_ACTION_AUTHORIZATION_CEREMONY"
    ):
        blockers.append("BUSINESS_ACTION_PREFLIGHT_NOT_READY")
    if row.get("blockers"):
        blockers.append("BUSINESS_ACTION_PREFLIGHT_HAS_BLOCKERS")
    if row.get("action_ceremony_eligible") is not True:
        blockers.append("BUSINESS_ACTION_CEREMONY_NOT_ELIGIBLE")
    if row.get("requires_fresh_recheck_before_ceremony") is not True:
        blockers.append("BUSINESS_ACTION_FRESH_RECHECK_BOUNDARY_MISSING")
    if row.get("action_request_issued") is not False:
        blockers.append("BUSINESS_ACTION_REQUEST_ALREADY_ISSUED")
    if row.get("owner_action_signature_required") is not True:
        blockers.append("OWNER_ACTION_SIGNATURE_BOUNDARY_MISSING")
    if row.get("owner_action_signature_verified") is not False:
        blockers.append("OWNER_ACTION_SIGNATURE_PREVERIFIED_UNSAFE")
    if row.get("customer_visible") is not False:
        blockers.append("BUSINESS_ACTION_PREFLIGHT_VISIBILITY_UNSAFE")

    for key in _AUTHORITY_FIELDS:
        if row.get(key) is not False:
            blockers.append("BUSINESS_ACTION_PREFLIGHT_UNSAFE_FIELD:" + key)

    scope = _scope(row.get("scope"))
    if not all(scope.values()):
        blockers.append("BUSINESS_ACTION_PREFLIGHT_SCOPE_INVALID")

    for key in (
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
    ):
        if not _text(row.get(key), 120):
            blockers.append("BUSINESS_ACTION_PREFLIGHT_FIELD_REQUIRED:" + key)

    for key in (
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_record_digest",
        "persistence_receipt_digest",
        "checkpoint_digest",
        "writer_request_digest",
        "environment_digest",
        "preflight_digest",
    ):
        if not _text(row.get(key), 180):
            blockers.append(
                "BUSINESS_ACTION_PREFLIGHT_DIGEST_REQUIRED:" + key
            )

    return row, list(dict.fromkeys(blockers))


def _identity_blockers(
    *,
    ceremony_id: Any,
    nonce: Any,
    key_id: Any,
    key_version: Any,
    decision: Any,
) -> list[str]:
    blockers: list[str] = []
    if (
        not isinstance(ceremony_id, str)
        or _ID_RE.fullmatch(ceremony_id) is None
    ):
        blockers.append("BUSINESS_ACTION_CEREMONY_ID_INVALID")
    if (
        not isinstance(nonce, str)
        or _NONCE_RE.fullmatch(nonce) is None
    ):
        blockers.append("BUSINESS_ACTION_NONCE_INVALID")
    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("BUSINESS_ACTION_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("BUSINESS_ACTION_KEY_VERSION_INVALID")
    if decision not in DECISIONS:
        blockers.append("BUSINESS_ACTION_AUTHORIZATION_DECISION_INVALID")
    return blockers


def build_owner_business_action_request(
    *,
    action_preflight: Mapping[str, Any] | None,
    owner_trust_roots: TrustRootRegistry,
    now_ts: str,
    decision: str,
    ceremony_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    preflight, blockers = _preflight_blockers(action_preflight)
    blockers.extend(
        _identity_blockers(
            ceremony_id=ceremony_id,
            nonce=nonce,
            key_id=key_id,
            key_version=key_version,
            decision=decision,
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=issued_at,
            expires_at=expires_at,
            now_ts=now_ts,
        )
    )

    entry = None
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        blockers.append("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    elif not blockers:
        try:
            entry, key_problem = owner_trust_roots.verify_key_available(
                key_id,
                key_version,
                now_ts,
            )
        except Exception:
            blockers.append("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
        else:
            if key_problem:
                blockers.append("OWNER_" + key_problem)

    blockers = list(dict.fromkeys(blockers))
    if blockers or entry is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": blockers
            or ["BUSINESS_ACTION_PRECONDITION_FAILED"],
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            **{
                key: value
                for key, value in _blocked().items()
                if key not in {"schema", "state", "blockers"}
            },
        }

    scope = _scope(preflight.get("scope"))
    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "purpose": PURPOSE,
        "signature_mechanism": MECHANISM,
        "authorization_decision": decision,
        "owner_id": scope["owner_id"],
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "customer_id": _text(preflight.get("customer_id"), 120),
        "pilot_id": _text(preflight.get("pilot_id"), 120),
        "package": _text(preflight.get("package"), 40),
        "review_type": _text(preflight.get("review_type"), 120),
        "requested_choice": _text(preflight.get("requested_choice"), 120),
        "action_family": _text(preflight.get("action_family"), 120),
        "owner_review_packet_digest": _text(
            preflight.get("owner_review_packet_digest"),
            180,
        ),
        "cycle_evidence_digest": _text(
            preflight.get("cycle_evidence_digest"),
            180,
        ),
        "contract_digest": _text(preflight.get("contract_digest"), 180),
        "value_bound_conversion_digest": _text(
            preflight.get("value_bound_conversion_digest"),
            180,
        ),
        "decision_record_digest": _text(
            preflight.get("decision_record_digest"),
            180,
        ),
        "persistence_receipt_digest": _text(
            preflight.get("persistence_receipt_digest"),
            180,
        ),
        "checkpoint_digest": _text(
            preflight.get("checkpoint_digest"),
            180,
        ),
        "writer_request_digest": _text(
            preflight.get("writer_request_digest"),
            180,
        ),
        "environment_digest": _text(
            preflight.get("environment_digest"),
            180,
        ),
        "preflight_digest": _text(
            preflight.get("preflight_digest"),
            180,
        ),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": _public_key_fingerprint(entry),
        "action_record_persisted": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }
    request_digest = _digest(body)

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_ACTION_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "authorization_decision": "UNDECIDED",
        "owner_action_identity_verified": False,
        "owner_action_signature_verified": False,
        "action_decision_verified": False,
        "action_authorization_intent": False,
        "action_denial_intent": False,
        "action_record_persisted": False,
        "generic_chat_instruction_accepted_as_action_authorization": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def _nonce_scope(
    request: Mapping[str, Any],
    request_digest: str,
) -> str:
    material = "|".join(
        (
            "B2B_RECURRING_BUSINESS_ACTION",
            _text(request.get("owner_id"), 120),
            _text(request.get("tenant_id"), 120),
            _text(request.get("workspace_id"), 120),
            _text(request.get("customer_id"), 120),
            _text(request.get("pilot_id"), 120),
            _text(request.get("requested_choice"), 120),
            _text(request.get("preflight_digest"), 180),
            request_digest,
            _text(request.get("key_id"), 128),
            str(request.get("key_version")),
        )
    )
    if len(material) > 256:
        return "B2B_ACTION|" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return material


def verify_owner_business_action_decision(
    request: Mapping[str, Any] | None,
    *,
    action_signature_b64: str,
    action_preflight: Mapping[str, Any] | None,
    owner_trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        return _blocked("BUSINESS_ACTION_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(nonce_registry, PersistentNonceRegistry):
        return _blocked("BUSINESS_ACTION_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    required = {
        "schema",
        "ceremony_id",
        "purpose",
        "signature_mechanism",
        "authorization_decision",
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_record_digest",
        "persistence_receipt_digest",
        "checkpoint_digest",
        "writer_request_digest",
        "environment_digest",
        "preflight_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "owner_public_key_fingerprint",
        "action_record_persisted",
        *_AUTHORITY_FIELDS,
    }
    if set(presented) != required:
        return _blocked("BUSINESS_ACTION_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("BUSINESS_ACTION_REQUEST_SCHEMA_INVALID")
    if presented.get("purpose") != PURPOSE:
        blockers.append("BUSINESS_ACTION_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != MECHANISM:
        blockers.append("BUSINESS_ACTION_MECHANISM_INVALID")

    blockers.extend(
        _identity_blockers(
            ceremony_id=presented.get("ceremony_id"),
            nonce=presented.get("nonce"),
            key_id=presented.get("key_id"),
            key_version=presented.get("key_version"),
            decision=presented.get("authorization_decision"),
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )

    if presented.get("action_record_persisted") is not False:
        blockers.append("BUSINESS_ACTION_RECORD_PREPERSISTED_UNSAFE")
    for key in _AUTHORITY_FIELDS:
        if presented.get(key) is not False:
            blockers.append("BUSINESS_ACTION_REQUEST_UNSAFE_FIELD:" + key)

    if blockers:
        return _blocked(*blockers)

    rebuilt = build_owner_business_action_request(
        action_preflight=action_preflight,
        owner_trust_roots=owner_trust_roots,
        now_ts=now_ts,
        decision=presented["authorization_decision"],
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["key_id"],
        key_version=presented["key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_ACTION_SIGNATURE":
        result = _blocked("BUSINESS_ACTION_REQUEST_REBUILD_BLOCKED")
        result["blockers"] = sorted(
            set(
                result["blockers"]
                + [
                    "REBUILD:" + str(item)
                    for item in list(rebuilt.get("blockers") or [])[:40]
                ]
            )
        )
        return result
    if rebuilt.get("request") != presented:
        return _blocked("BUSINESS_ACTION_REQUEST_REBUILD_MISMATCH")

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["key_id"],
            presented["key_version"],
            now_ts,
        )
    except Exception:
        return _blocked("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
    if key_problem:
        return _blocked("OWNER_" + key_problem)
    if entry is None:
        return _blocked("OWNER_TRUST_KEY_UNKNOWN")
    if (
        presented.get("owner_public_key_fingerprint")
        != _public_key_fingerprint(entry)
    ):
        return _blocked("OWNER_ACTION_PUBLIC_KEY_FINGERPRINT_MISMATCH")

    try:
        signature = _decode_signature(action_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_business_action_decision_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("OWNER_ACTION_SIGNATURE_INVALID")

    request_digest = rebuilt["request_digest"]
    try:
        claimed = nonce_registry.claim(
            scope=_nonce_scope(presented, request_digest),
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("BUSINESS_ACTION_NONCE_REGISTRY_FAILURE")
        result["owner_action_identity_verified"] = True
        result["owner_action_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("BUSINESS_ACTION_NONCE_REPLAYED")
        result["owner_action_identity_verified"] = True
        result["owner_action_signature_verified"] = True
        return result

    decision = presented["authorization_decision"]
    authorize = decision == "AUTHORIZE_BUSINESS_ACTION"
    state = (
        "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize
        else "OWNER_BUSINESS_ACTION_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "authorization_decision": decision,
        "owner_id": presented["owner_id"],
        "tenant_id": presented["tenant_id"],
        "workspace_id": presented["workspace_id"],
        "customer_id": presented["customer_id"],
        "pilot_id": presented["pilot_id"],
        "package": presented["package"],
        "review_type": presented["review_type"],
        "requested_choice": presented["requested_choice"],
        "action_family": presented["action_family"],
        "owner_review_packet_digest": presented[
            "owner_review_packet_digest"
        ],
        "cycle_evidence_digest": presented["cycle_evidence_digest"],
        "contract_digest": presented["contract_digest"],
        "value_bound_conversion_digest": presented[
            "value_bound_conversion_digest"
        ],
        "decision_record_digest": presented["decision_record_digest"],
        "persistence_receipt_digest": presented[
            "persistence_receipt_digest"
        ],
        "checkpoint_digest": presented["checkpoint_digest"],
        "writer_request_digest": presented["writer_request_digest"],
        "environment_digest": presented["environment_digest"],
        "preflight_digest": presented["preflight_digest"],
        "authorization_request_digest": request_digest,
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": not authorize,
        "action_record_persisted": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": RESULT_SCHEMA,
        "state": state,
        "blockers": [],
        "authorization_decision": decision,
        "requested_choice": presented["requested_choice"],
        "action_family": presented["action_family"],
        "owner_action_identity_verified": True,
        "owner_action_signature_verified": True,
        "action_decision_verified": True,
        "action_authorization_intent": authorize,
        "action_denial_intent": not authorize,
        "action_record": record,
        "action_record_digest": _digest(record),
        "action_record_persisted": False,
        "requires_action_record_persistence": True,
        "generic_chat_instruction_accepted_as_action_authorization": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "PURPOSE",
    "MECHANISM",
    "DECISIONS",
    "MAX_WINDOW_SECONDS",
    "canonical_business_action_decision_bytes",
    "build_owner_business_action_request",
    "verify_owner_business_action_decision",
]
