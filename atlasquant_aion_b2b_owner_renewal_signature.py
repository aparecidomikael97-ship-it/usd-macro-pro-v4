"""AION B2B owner renewal decision signature and verification ceremony.

This layer verifies an externally produced Ed25519 owner signature over the exact
renewal/continuation review choice prepared by the preceding decision-request
layer. Verification proves the owner signed the exact bounded request. It does
not persist the decision and does not authorize or execute any business action.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_b2b_owner_renewal_decision_request import (
    SCHEMA as DECISION_REQUEST_SCHEMA,
    build_owner_renewal_decision_request,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_SIGNATURE_V1"
SIGNATURE_REQUEST_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_SIGNATURE_REQUEST_V1"
)
RESULT_SCHEMA = (
    "ATLASQUANT_AION_B2B_OWNER_RENEWAL_DECISION_VERIFICATION_V1"
)
DECISION_PURPOSE = "B2B_OWNER_RENEWAL_EXPLICIT_DECISION"
SIGNATURE_MECHANISM = "ED25519_EXTERNAL_OWNER_KEY"
MAX_DECISION_WINDOW_SECONDS = 180

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")

_BASE_REQUEST_KEYS = {
    "purpose",
    "owner_id",
    "tenant_id",
    "workspace_id",
    "customer_id",
    "pilot_id",
    "package",
    "review_type",
    "requested_choice",
    "owner_review_packet_digest",
    "cycle_evidence_digest",
    "contract_digest",
    "value_bound_conversion_digest",
    "ceremony_id",
    "nonce",
    "issued_at",
    "expires_at",
}

_UNSAFE_PREPARED_FIELDS = (
    "owner_signature_verified",
    "owner_decision_verified",
    "owner_decision_recorded",
    "decision_persisted",
    "renewal_authorized",
    "expansion_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
    "executes_action",
)

_AUTHORIZATION_FIELDS = (
    "renewal_authorized",
    "expansion_authorized",
    "pause_authorized",
    "termination_authorized",
    "billing_authorized",
    "pricing_change_authorized",
    "quota_change_authorized",
    "role_change_authorized",
    "integration_change_authorized",
    "customer_contact_authorized",
    "provisioning_authorized",
    "deploy_authorized",
    "provider_called",
    "crm_write_authorized",
    "production_mutation_authorized",
    "external_action_executed",
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


def canonical_owner_renewal_signature_bytes(
    request_body: Mapping[str, Any],
) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_owner_renewal_signature_bytes(value)
    ).hexdigest()


def _text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
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
        return ["OWNER_RENEWAL_DECISION_TIME_INVALID"]

    blockers: list[str] = []
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("OWNER_RENEWAL_DECISION_WINDOW_INVALID")
    elif window > MAX_DECISION_WINDOW_SECONDS:
        blockers.append("OWNER_RENEWAL_DECISION_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("OWNER_RENEWAL_DECISION_NOT_YET_VALID")
    if expires <= now:
        blockers.append("OWNER_RENEWAL_DECISION_EXPIRED")
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
        "owner_identity_signature_verified": False,
        "owner_decision_signature_verified": False,
        "owner_decision_verified": False,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "decision_record": {},
        "decision_record_digest": "",
        "requested_choice": "",
        "requires_decision_persistence": False,
        "signature_capture_performed": False,
        "generic_chat_instruction_accepted_as_decision": False,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


def _validate_prepared_decision_request(
    decision_request_result: Mapping[str, Any] | None,
    *,
    owner_review_packet: Mapping[str, Any] | None,
    now_ts: str,
) -> tuple[dict[str, Any], list[str]]:
    prepared = (
        dict(decision_request_result)
        if isinstance(decision_request_result, Mapping)
        else {}
    )
    blockers: list[str] = []

    if prepared.get("schema") != DECISION_REQUEST_SCHEMA:
        blockers.append("OWNER_RENEWAL_REQUEST_SCHEMA_INVALID")
    if prepared.get("state") != "READY_FOR_EXPLICIT_OWNER_SIGNATURE":
        blockers.append("OWNER_RENEWAL_REQUEST_NOT_READY")
    if prepared.get("blockers"):
        blockers.append("OWNER_RENEWAL_REQUEST_HAS_BLOCKERS")
    if prepared.get("owner_signature_required") is not True:
        blockers.append("OWNER_SIGNATURE_BOUNDARY_MISSING")
    if (
        prepared.get("generic_chat_instruction_accepted_as_decision")
        is not False
    ):
        blockers.append("GENERIC_CHAT_DECISION_BOUNDARY_UNSAFE")

    for key in _UNSAFE_PREPARED_FIELDS:
        if prepared.get(key) is not False:
            blockers.append("OWNER_RENEWAL_REQUEST_UNSAFE_FIELD:" + key)

    request = (
        dict(prepared.get("request"))
        if isinstance(prepared.get("request"), Mapping)
        else {}
    )
    if set(request) != _BASE_REQUEST_KEYS:
        blockers.append("OWNER_RENEWAL_REQUEST_SHAPE_MISMATCH")

    request_digest = _text(prepared.get("request_digest"), 180)
    if not request_digest:
        blockers.append("OWNER_RENEWAL_REQUEST_DIGEST_REQUIRED")
    elif request and _digest(request) != request_digest:
        blockers.append("OWNER_RENEWAL_REQUEST_DIGEST_MISMATCH")

    if request.get("purpose") != DECISION_PURPOSE:
        blockers.append("OWNER_RENEWAL_DECISION_PURPOSE_INVALID")

    ceremony_id = _text(request.get("ceremony_id"), 160)
    nonce = _text(request.get("nonce"), 256)
    if not ceremony_id or _ID_RE.fullmatch(ceremony_id) is None:
        blockers.append("OWNER_RENEWAL_CEREMONY_ID_INVALID")
    if not nonce or _NONCE_RE.fullmatch(nonce) is None:
        blockers.append("OWNER_RENEWAL_NONCE_INVALID")

    blockers.extend(
        _window_blockers(
            issued_at=request.get("issued_at"),
            expires_at=request.get("expires_at"),
            now_ts=now_ts,
        )
    )

    if request:
        rebuilt = build_owner_renewal_decision_request(
            trusted_scope=_scope(request),
            owner_review_packet=owner_review_packet or {},
            requested_choice=request.get("requested_choice"),
            ceremony_id=request.get("ceremony_id"),
            nonce=request.get("nonce"),
            issued_at=request.get("issued_at"),
            expires_at=request.get("expires_at"),
        )
        if rebuilt.get("state") != "READY_FOR_EXPLICIT_OWNER_SIGNATURE":
            blockers.append("OWNER_RENEWAL_REQUEST_REBUILD_BLOCKED")
            blockers.extend(
                "REBUILD:" + str(item)
                for item in list(rebuilt.get("blockers") or [])[:40]
            )
        elif (
            rebuilt.get("request") != request
            or rebuilt.get("request_digest") != request_digest
        ):
            blockers.append("OWNER_RENEWAL_REQUEST_REBUILD_MISMATCH")

    return request, list(dict.fromkeys(blockers))


def prepare_owner_renewal_signature_request(
    *,
    decision_request_result: Mapping[str, Any],
    owner_review_packet: Mapping[str, Any],
    owner_trust_roots: TrustRootRegistry,
    now_ts: str,
    key_id: str,
    key_version: int,
) -> dict[str, Any]:
    base, blockers = _validate_prepared_decision_request(
        decision_request_result,
        owner_review_packet=owner_review_packet,
        now_ts=now_ts,
    )

    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("OWNER_RENEWAL_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("OWNER_RENEWAL_KEY_VERSION_INVALID")

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

    if blockers or entry is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": sorted(set(blockers)),
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            **{
                key: value
                for key, value in _blocked().items()
                if key not in {"schema", "state", "blockers"}
            },
        }

    body = {
        "schema": SIGNATURE_REQUEST_SCHEMA,
        "ceremony_id": base["ceremony_id"],
        "decision_purpose": DECISION_PURPOSE,
        "signature_mechanism": SIGNATURE_MECHANISM,
        "requested_choice": base["requested_choice"],
        "owner_id": base["owner_id"],
        "tenant_id": base["tenant_id"],
        "workspace_id": base["workspace_id"],
        "customer_id": base["customer_id"],
        "pilot_id": base["pilot_id"],
        "package": base["package"],
        "review_type": base["review_type"],
        "owner_review_packet_digest": base[
            "owner_review_packet_digest"
        ],
        "cycle_evidence_digest": base["cycle_evidence_digest"],
        "contract_digest": base["contract_digest"],
        "value_bound_conversion_digest": base[
            "value_bound_conversion_digest"
        ],
        "decision_request_digest": _text(
            decision_request_result.get("request_digest"),
            180,
        ),
        "issued_at": base["issued_at"],
        "expires_at": base["expires_at"],
        "nonce": base["nonce"],
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": _public_key_fingerprint(entry),
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "renewal_authorized": False,
        "expansion_authorized": False,
        "pause_authorized": False,
        "termination_authorized": False,
        "billing_authorized": False,
        "pricing_change_authorized": False,
        "quota_change_authorized": False,
        "role_change_authorized": False,
        "integration_change_authorized": False,
        "customer_contact_authorized": False,
        "provisioning_authorized": False,
        "deploy_authorized": False,
        "provider_called": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
    }
    request_digest = _digest(body)

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "owner_identity_signature_verified": False,
        "owner_decision_signature_verified": False,
        "owner_decision_verified": False,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "requested_choice": base["requested_choice"],
        "requires_signature_verification": True,
        "requires_decision_persistence": False,
        "signature_capture_performed": False,
        "generic_chat_instruction_accepted_as_decision": False,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


def _nonce_scope(request: Mapping[str, Any], request_digest: str) -> str:
    scope = "|".join(
        (
            "B2B_OWNER_RENEWAL_DECISION",
            _text(request.get("owner_id"), 120),
            _text(request.get("tenant_id"), 120),
            _text(request.get("workspace_id"), 120),
            _text(request.get("customer_id"), 120),
            _text(request.get("pilot_id"), 120),
            _text(request.get("decision_request_digest"), 180),
            request_digest,
            _text(request.get("key_id"), 128),
            str(request.get("key_version")),
        )
    )
    if len(scope) > 256:
        return "B2B_RENEWAL|" + hashlib.sha256(
            scope.encode("utf-8")
        ).hexdigest()
    return scope


def verify_owner_renewal_decision_signature(
    request: Mapping[str, Any] | None,
    *,
    decision_signature_b64: str,
    decision_request_result: Mapping[str, Any],
    owner_review_packet: Mapping[str, Any],
    owner_trust_roots: TrustRootRegistry,
    decision_nonce_registry: PersistentNonceRegistry,
    now_ts: str,
) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        return _blocked("OWNER_RENEWAL_SIGNATURE_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(decision_nonce_registry, PersistentNonceRegistry):
        return _blocked("OWNER_RENEWAL_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    required_keys = {
        "schema",
        "ceremony_id",
        "decision_purpose",
        "signature_mechanism",
        "requested_choice",
        "owner_id",
        "tenant_id",
        "workspace_id",
        "customer_id",
        "pilot_id",
        "package",
        "review_type",
        "owner_review_packet_digest",
        "cycle_evidence_digest",
        "contract_digest",
        "value_bound_conversion_digest",
        "decision_request_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "owner_public_key_fingerprint",
        "owner_decision_recorded",
        "decision_persisted",
        *_AUTHORIZATION_FIELDS[:-1],
    }
    # executes_action is a verification-result property, not a signed request field.
    if set(presented) != required_keys:
        return _blocked("OWNER_RENEWAL_SIGNATURE_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != SIGNATURE_REQUEST_SCHEMA:
        blockers.append("OWNER_RENEWAL_SIGNATURE_REQUEST_SCHEMA_INVALID")
    if presented.get("decision_purpose") != DECISION_PURPOSE:
        blockers.append("OWNER_RENEWAL_DECISION_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != SIGNATURE_MECHANISM:
        blockers.append("OWNER_RENEWAL_SIGNATURE_MECHANISM_INVALID")

    blockers.extend(
        _window_blockers(
            issued_at=presented.get("issued_at"),
            expires_at=presented.get("expires_at"),
            now_ts=now_ts,
        )
    )
    if (
        not isinstance(presented.get("key_id"), str)
        or not presented.get("key_id")
    ):
        blockers.append("OWNER_RENEWAL_KEY_ID_INVALID")
    if (
        not isinstance(presented.get("key_version"), int)
        or isinstance(presented.get("key_version"), bool)
        or presented.get("key_version") < 1
    ):
        blockers.append("OWNER_RENEWAL_KEY_VERSION_INVALID")

    for key in (
        "owner_decision_recorded",
        "decision_persisted",
        *_AUTHORIZATION_FIELDS[:-1],
    ):
        if presented.get(key) is not False:
            blockers.append("OWNER_RENEWAL_SIGNATURE_UNSAFE_FIELD:" + key)

    if blockers:
        return _blocked(*blockers)

    rebuilt = prepare_owner_renewal_signature_request(
        decision_request_result=decision_request_result,
        owner_review_packet=owner_review_packet,
        owner_trust_roots=owner_trust_roots,
        now_ts=now_ts,
        key_id=presented["key_id"],
        key_version=presented["key_version"],
    )
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_SIGNATURE":
        result = _blocked("OWNER_RENEWAL_SIGNATURE_REQUEST_REBUILD_BLOCKED")
        result["blockers"] = sorted(
            set(
                result["blockers"]
                + [
                    "REBUILD:" + item
                    for item in list(rebuilt.get("blockers") or [])[:40]
                ]
            )
        )
        return result
    if rebuilt.get("request") != presented:
        return _blocked("OWNER_RENEWAL_SIGNATURE_REQUEST_REBUILD_MISMATCH")

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
        return _blocked("OWNER_RENEWAL_PUBLIC_KEY_FINGERPRINT_MISMATCH")

    try:
        signature = _decode_signature(decision_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_owner_renewal_signature_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("OWNER_RENEWAL_SIGNATURE_INVALID")

    request_digest = rebuilt["request_digest"]
    try:
        claimed = decision_nonce_registry.claim(
            scope=_nonce_scope(presented, request_digest),
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked("OWNER_RENEWAL_NONCE_REGISTRY_FAILURE")
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("OWNER_RENEWAL_NONCE_REPLAYED")
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result

    record = {
        "schema": RESULT_SCHEMA,
        "requested_choice": presented["requested_choice"],
        "owner_id": presented["owner_id"],
        "tenant_id": presented["tenant_id"],
        "workspace_id": presented["workspace_id"],
        "customer_id": presented["customer_id"],
        "pilot_id": presented["pilot_id"],
        "package": presented["package"],
        "review_type": presented["review_type"],
        "owner_review_packet_digest": presented[
            "owner_review_packet_digest"
        ],
        "cycle_evidence_digest": presented["cycle_evidence_digest"],
        "contract_digest": presented["contract_digest"],
        "value_bound_conversion_digest": presented[
            "value_bound_conversion_digest"
        ],
        "decision_request_digest": presented["decision_request_digest"],
        "signature_request_digest": request_digest,
        "owner_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
    }

    return {
        "schema": RESULT_SCHEMA,
        "state": "OWNER_RENEWAL_DECISION_VERIFIED_PENDING_PERSISTENCE",
        "blockers": [],
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_persisted": False,
        "requested_choice": presented["requested_choice"],
        "decision_record": record,
        "decision_record_digest": _digest(record),
        "requires_decision_persistence": True,
        "signature_capture_performed": False,
        "generic_chat_instruction_accepted_as_decision": False,
        **{key: False for key in _AUTHORIZATION_FIELDS},
    }


__all__ = [
    "SCHEMA",
    "SIGNATURE_REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "DECISION_PURPOSE",
    "SIGNATURE_MECHANISM",
    "MAX_DECISION_WINDOW_SECONDS",
    "canonical_owner_renewal_signature_bytes",
    "prepare_owner_renewal_signature_request",
    "verify_owner_renewal_decision_signature",
]
