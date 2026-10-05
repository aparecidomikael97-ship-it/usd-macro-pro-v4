"""AION B2B recurring business-action execution ceremony.

Cryptographic HUMAN_OWNER confirmation after a clean recurring action execution
preflight.

A valid signature records execution intent only. It never generates a command,
never executes the commercial action and requires a separate persistence proof
before any command-planning layer may exist.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_b2b_owner_renewal_action_execution_preflight import (
    SCHEMA as PREFLIGHT_SCHEMA,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_CEREMONY_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_REQUEST_V1"
RESULT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_EXECUTION_VERIFICATION_V1"
)
PURPOSE = "B2B_OWNER_EXPLICIT_RECURRING_BUSINESS_ACTION_EXECUTION_DECISION"
MECHANISM = "ED25519_EXTERNAL_OWNER_EXECUTION_KEY"
DECISIONS = (
    "AUTHORIZE_BUSINESS_ACTION_EXECUTION",
    "DENY_BUSINESS_ACTION_EXECUTION",
)
MAX_WINDOW_SECONDS = 120

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

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

_PREFLIGHT_FALSE_FIELDS = (
    "execution_request_issued",
    "owner_execution_signature_verified",
    "execution_command_generated",
    "execution_command_executed",
    *_AUTHORITY_FIELDS,
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


def canonical_owner_business_action_execution_bytes(
    request_body: Mapping[str, Any],
) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_owner_business_action_execution_bytes(value)
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
        return ["BUSINESS_ACTION_EXECUTION_TIME_INVALID"]

    blockers: list[str] = []
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("BUSINESS_ACTION_EXECUTION_WINDOW_INVALID")
    elif window > MAX_WINDOW_SECONDS:
        blockers.append("BUSINESS_ACTION_EXECUTION_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("BUSINESS_ACTION_EXECUTION_NOT_YET_VALID")
    if expires <= now:
        blockers.append("BUSINESS_ACTION_EXECUTION_REQUEST_EXPIRED")
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
        "execution_decision": "UNDECIDED",
        "owner_execution_identity_verified": False,
        "owner_execution_signature_verified": False,
        "execution_decision_verified": False,
        "execution_authorization_intent": False,
        "execution_denial_intent": False,
        "execution_record": {},
        "execution_record_digest": "",
        "execution_record_persisted": False,
        "requires_execution_record_persistence": False,
        "eligible_for_command_planning_after_persistence": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "generic_chat_instruction_accepted_as_execution": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def _preflight_blockers(
    execution_preflight: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    row = (
        dict(execution_preflight)
        if isinstance(execution_preflight, Mapping)
        else {}
    )
    blockers: list[str] = []

    if row.get("schema") != PREFLIGHT_SCHEMA:
        blockers.append("EXECUTION_PREFLIGHT_SCHEMA_INVALID")
    if row.get("state") != "READY_FOR_BUSINESS_ACTION_EXECUTION_CEREMONY":
        blockers.append("EXECUTION_PREFLIGHT_NOT_READY")
    if row.get("blockers"):
        blockers.append("EXECUTION_PREFLIGHT_HAS_BLOCKERS")
    if row.get("business_action_execution_ceremony_eligible") is not True:
        blockers.append("EXECUTION_CEREMONY_NOT_ELIGIBLE")
    if row.get("human_execution_confirmation_required") is not True:
        blockers.append("HUMAN_EXECUTION_CONFIRMATION_BOUNDARY_MISSING")
    if row.get("customer_visible") is not False:
        blockers.append("EXECUTION_PREFLIGHT_VISIBILITY_UNSAFE")

    scope = _scope(row.get("scope"))
    if not all(scope.values()):
        blockers.append("EXECUTION_PREFLIGHT_SCOPE_INVALID")
    if _scope(row) != scope:
        blockers.append("EXECUTION_PREFLIGHT_SCOPE_DUPLICATE_MISMATCH")

    for key in (
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
    ):
        if not _text(row.get(key), 120):
            blockers.append("EXECUTION_PREFLIGHT_FIELD_REQUIRED:" + key)

    for key in (
        "action_record_digest",
        "action_persistence_receipt_digest",
        "action_checkpoint_digest",
        "action_writer_request_digest",
        "authorization_preflight_digest",
        "action_parameters_digest",
        "execution_environment_digest",
        "execution_preflight_digest",
    ):
        if not _SHA256_RE.fullmatch(_text(row.get(key), 180)):
            blockers.append("EXECUTION_PREFLIGHT_DIGEST_INVALID:" + key)

    for key in _PREFLIGHT_FALSE_FIELDS:
        if row.get(key) is not False:
            blockers.append("EXECUTION_PREFLIGHT_UNSAFE_FIELD:" + key)

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
        blockers.append("BUSINESS_ACTION_EXECUTION_CEREMONY_ID_INVALID")
    if (
        not isinstance(nonce, str)
        or _NONCE_RE.fullmatch(nonce) is None
    ):
        blockers.append("BUSINESS_ACTION_EXECUTION_NONCE_INVALID")
    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("BUSINESS_ACTION_EXECUTION_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("BUSINESS_ACTION_EXECUTION_KEY_VERSION_INVALID")
    if decision not in DECISIONS:
        blockers.append("BUSINESS_ACTION_EXECUTION_DECISION_INVALID")
    return blockers


def build_owner_business_action_execution_request(
    *,
    execution_preflight: Mapping[str, Any] | None,
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
    preflight, blockers = _preflight_blockers(execution_preflight)
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
            or ["BUSINESS_ACTION_EXECUTION_PRECONDITION_FAILED"],
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
        "decision": decision,
        "owner_id": scope["owner_id"],
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "customer_id": _text(preflight.get("customer_id"), 120),
        "pilot_id": _text(preflight.get("pilot_id"), 120),
        "package": _text(preflight.get("package"), 40),
        "review_type": _text(preflight.get("review_type"), 120),
        "requested_choice": _text(preflight.get("requested_choice"), 120),
        "action_family": _text(preflight.get("action_family"), 120),
        "action_record_digest": _text(
            preflight.get("action_record_digest"), 180
        ),
        "action_persistence_receipt_digest": _text(
            preflight.get("action_persistence_receipt_digest"), 180
        ),
        "action_checkpoint_digest": _text(
            preflight.get("action_checkpoint_digest"), 180
        ),
        "action_writer_request_digest": _text(
            preflight.get("action_writer_request_digest"), 180
        ),
        "authorization_preflight_digest": _text(
            preflight.get("authorization_preflight_digest"), 180
        ),
        "action_parameters_digest": _text(
            preflight.get("action_parameters_digest"), 180
        ),
        "execution_environment_digest": _text(
            preflight.get("execution_environment_digest"), 180
        ),
        "execution_preflight_digest": _text(
            preflight.get("execution_preflight_digest"), 180
        ),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": _public_key_fingerprint(entry),
        "execution_record_persisted": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }
    request_digest = _digest(body)

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_BUSINESS_ACTION_EXECUTION_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "execution_decision": "UNDECIDED",
        "owner_execution_identity_verified": False,
        "owner_execution_signature_verified": False,
        "execution_decision_verified": False,
        "execution_authorization_intent": False,
        "execution_denial_intent": False,
        "execution_record_persisted": False,
        "requires_execution_record_persistence": False,
        "eligible_for_command_planning_after_persistence": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "generic_chat_instruction_accepted_as_execution": False,
        **{key: False for key in _AUTHORITY_FIELDS},
    }


def _nonce_scope(
    request: Mapping[str, Any],
    request_digest: str,
) -> str:
    material = "|".join(
        (
            "B2B_RECURRING_BUSINESS_ACTION_EXECUTION",
            _text(request.get("owner_id"), 120),
            _text(request.get("tenant_id"), 120),
            _text(request.get("workspace_id"), 120),
            _text(request.get("customer_id"), 120),
            _text(request.get("pilot_id"), 120),
            _text(request.get("requested_choice"), 120),
            _text(request.get("action_parameters_digest"), 180),
            _text(request.get("execution_preflight_digest"), 180),
            request_digest,
            _text(request.get("key_id"), 128),
            str(request.get("key_version")),
        )
    )
    if len(material) > 256:
        return "B2B_ACTION_EXEC|" + hashlib.sha256(
            material.encode("utf-8")
        ).hexdigest()
    return material


def verify_owner_business_action_execution_decision(
    request: Mapping[str, Any] | None,
    *,
    execution_signature_b64: str,
    execution_preflight: Mapping[str, Any] | None,
    owner_trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        return _blocked("BUSINESS_ACTION_EXECUTION_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(nonce_registry, PersistentNonceRegistry):
        return _blocked("BUSINESS_ACTION_EXECUTION_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    required = {
        "schema",
        "ceremony_id",
        "purpose",
        "signature_mechanism",
        "decision",
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "requested_choice",
        "action_family",
        "action_record_digest",
        "action_persistence_receipt_digest",
        "action_checkpoint_digest",
        "action_writer_request_digest",
        "authorization_preflight_digest",
        "action_parameters_digest",
        "execution_environment_digest",
        "execution_preflight_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "owner_public_key_fingerprint",
        "execution_record_persisted",
        "execution_command_generated",
        "execution_command_executed",
        *_AUTHORITY_FIELDS,
    }
    if set(presented) != required:
        return _blocked("BUSINESS_ACTION_EXECUTION_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("BUSINESS_ACTION_EXECUTION_REQUEST_SCHEMA_INVALID")
    if presented.get("purpose") != PURPOSE:
        blockers.append("BUSINESS_ACTION_EXECUTION_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != MECHANISM:
        blockers.append("BUSINESS_ACTION_EXECUTION_MECHANISM_INVALID")
    blockers.extend(
        _identity_blockers(
            ceremony_id=presented.get("ceremony_id"),
            nonce=presented.get("nonce"),
            key_id=presented.get("key_id"),
            key_version=presented.get("key_version"),
            decision=presented.get("decision"),
        )
    )
    blockers.extend(
        _window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )
    for key in (
        "execution_record_persisted",
        "execution_command_generated",
        "execution_command_executed",
        *_AUTHORITY_FIELDS,
    ):
        if presented.get(key) is not False:
            blockers.append("BUSINESS_ACTION_EXECUTION_UNSAFE_FIELD:" + key)

    if blockers:
        return _blocked(*blockers)

    rebuilt = build_owner_business_action_execution_request(
        execution_preflight=execution_preflight,
        owner_trust_roots=owner_trust_roots,
        now_ts=now_ts,
        decision=presented["decision"],
        ceremony_id=presented["ceremony_id"],
        nonce=presented["nonce"],
        issued_at=presented["issued_at"],
        expires_at=presented["expires_at"],
        key_id=presented["key_id"],
        key_version=presented["key_version"],
    )
    if (
        rebuilt.get("state")
        != "READY_FOR_EXTERNAL_OWNER_BUSINESS_ACTION_EXECUTION_SIGNATURE"
    ):
        result = _blocked("BUSINESS_ACTION_EXECUTION_REQUEST_REBUILD_BLOCKED")
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
        return _blocked("BUSINESS_ACTION_EXECUTION_REQUEST_REBUILD_MISMATCH")

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
        return _blocked(
            "BUSINESS_ACTION_EXECUTION_PUBLIC_KEY_FINGERPRINT_MISMATCH"
        )

    try:
        signature = _decode_signature(execution_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_business_action_execution_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("BUSINESS_ACTION_EXECUTION_SIGNATURE_INVALID")

    request_digest = rebuilt["request_digest"]
    try:
        claimed = nonce_registry.claim(
            scope=_nonce_scope(presented, request_digest),
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("BUSINESS_ACTION_EXECUTION_NONCE_REGISTRY_FAILURE")
        result["owner_execution_identity_verified"] = True
        result["owner_execution_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("BUSINESS_ACTION_EXECUTION_NONCE_REPLAYED")
        result["owner_execution_identity_verified"] = True
        result["owner_execution_signature_verified"] = True
        return result

    authorize = (
        presented["decision"] == "AUTHORIZE_BUSINESS_ACTION_EXECUTION"
    )
    state = (
        "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_AUTHORIZE_PENDING_PERSISTENCE"
        if authorize
        else "OWNER_BUSINESS_ACTION_EXECUTION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    record = {
        "schema": RESULT_SCHEMA,
        "state": state,
        "execution_decision": presented["decision"],
        "owner_id": presented["owner_id"],
        "tenant_id": presented["tenant_id"],
        "workspace_id": presented["workspace_id"],
        "customer_id": presented["customer_id"],
        "pilot_id": presented["pilot_id"],
        "package": presented["package"],
        "review_type": presented["review_type"],
        "requested_choice": presented["requested_choice"],
        "action_family": presented["action_family"],
        "action_record_digest": presented["action_record_digest"],
        "action_persistence_receipt_digest": presented[
            "action_persistence_receipt_digest"
        ],
        "action_checkpoint_digest": presented["action_checkpoint_digest"],
        "action_writer_request_digest": presented[
            "action_writer_request_digest"
        ],
        "authorization_preflight_digest": presented[
            "authorization_preflight_digest"
        ],
        "action_parameters_digest": presented["action_parameters_digest"],
        "execution_environment_digest": presented[
            "execution_environment_digest"
        ],
        "execution_preflight_digest": presented[
            "execution_preflight_digest"
        ],
        "execution_request_digest": request_digest,
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": not authorize,
        "execution_record_persisted": False,
        "execution_command_generated": False,
        "execution_command_executed": False,
        "business_action_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }

    return {
        "schema": RESULT_SCHEMA,
        "state": state,
        "blockers": [],
        "execution_decision": presented["decision"],
        "requested_choice": presented["requested_choice"],
        "action_family": presented["action_family"],
        "owner_execution_identity_verified": True,
        "owner_execution_signature_verified": True,
        "execution_decision_verified": True,
        "execution_authorization_intent": authorize,
        "execution_denial_intent": not authorize,
        "execution_record": record,
        "execution_record_digest": _digest(record),
        "execution_record_persisted": False,
        "requires_execution_record_persistence": True,
        "eligible_for_command_planning_after_persistence": bool(authorize),
        "execution_command_generated": False,
        "execution_command_executed": False,
        "generic_chat_instruction_accepted_as_execution": False,
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
    "canonical_owner_business_action_execution_bytes",
    "build_owner_business_action_execution_request",
    "verify_owner_business_action_execution_decision",
]
