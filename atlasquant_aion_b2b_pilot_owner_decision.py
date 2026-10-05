"""AION B2B Pilot Owner Decision V1.

Cryptographic, pilot-specific owner decision ceremony.

This module is intentionally separate from the existing Core-Freeze owner
decision path. It accepts only APPROVE_PILOT or DENY_PILOT, binds the decision
to the exact Pilot Owner Review Packet digest, verifies an external Ed25519
signature using the local trust-root registry, and claims a durable nonce.

Even a valid APPROVE_PILOT result remains pending persistence and does not
activate the pilot, contact a customer, sign a contract, bill, deploy, write
CRM data, call a provider or mutate production.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_V1"
REQUEST_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_REQUEST_V1"
RESULT_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_DECISION_VERIFICATION_V1"
PACKET_SCHEMA = "ATLASQUANT_AION_B2B_PILOT_OWNER_REVIEW_PACKET_V1"

DECISION_PURPOSE = "B2B_PILOT_EXPLICIT_OWNER_DECISION"
SIGNATURE_MECHANISM = "ED25519_EXTERNAL_OWNER_KEY"
DECISIONS = ("APPROVE_PILOT", "DENY_PILOT")
MAX_DECISION_WINDOW_SECONDS = 180

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,159}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{15,255}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def canonical_pilot_owner_decision_bytes(
    request_body: Mapping[str, Any],
) -> bytes:
    return _canonical(dict(request_body)).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_pilot_owner_decision_bytes(value)
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
        return ["PILOT_OWNER_DECISION_TIME_INVALID"]

    blockers: list[str] = []
    window = (expires - issued).total_seconds()
    if window <= 0:
        blockers.append("PILOT_OWNER_DECISION_WINDOW_INVALID")
    elif window > MAX_DECISION_WINDOW_SECONDS:
        blockers.append("PILOT_OWNER_DECISION_WINDOW_TOO_LONG")
    if issued > now:
        blockers.append("PILOT_OWNER_DECISION_NOT_YET_VALID")
    if expires <= now:
        blockers.append("PILOT_OWNER_DECISION_EXPIRED")
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


def _packet_blockers(packet: Mapping[str, Any] | None) -> list[str]:
    data = dict(packet) if isinstance(packet, Mapping) else {}
    blockers: list[str] = []

    if data.get("schema") != PACKET_SCHEMA:
        blockers.append("PILOT_REVIEW_PACKET_SCHEMA_INVALID")
    if data.get("state") != "READY_FOR_OWNER_REVIEW":
        blockers.append("PILOT_REVIEW_PACKET_NOT_READY")
    if data.get("owner_decision") != "UNDECIDED":
        blockers.append("PILOT_REVIEW_PACKET_ALREADY_DECIDED")
    if data.get("owner_decision_recorded") is not False:
        blockers.append("PILOT_REVIEW_PACKET_DECISION_RECORD_UNSAFE")
    if data.get("owner_approval_recorded") is not False:
        blockers.append("PILOT_REVIEW_PACKET_APPROVAL_RECORD_UNSAFE")
    if data.get("human_owner_decision_required") is not True:
        blockers.append("PILOT_REVIEW_PACKET_OWNER_BOUNDARY_MISSING")
    if data.get("pilot_activation_authorized") is not False:
        blockers.append("PILOT_REVIEW_PACKET_ACTIVATION_UNSAFE")
    if data.get("decision_mechanism_reused_from_core_freeze") is not False:
        blockers.append("CORE_FREEZE_DECISION_MECHANISM_REUSE_FORBIDDEN")

    for key in (
        "automatic_activation",
        "automatic_customer_contact",
        "automatic_contract_signature",
        "automatic_billing",
        "automatic_spend",
        "automatic_deploy",
        "crm_write",
        "provider_called",
        "production_mutation",
        "grants_authority",
        "executes_action",
    ):
        if data.get(key) is not False:
            blockers.append(
                f"PILOT_REVIEW_PACKET_{key.upper()}_UNSAFE"
            )

    scope = _scope(
        data.get("scope")
        if isinstance(data.get("scope"), Mapping)
        else {}
    )
    if not all(scope.values()):
        blockers.append("PILOT_REVIEW_PACKET_SCOPE_INVALID")

    packet_digest = _text(data.get("packet_digest"), 180)
    if not _SHA256_RE.fullmatch(packet_digest):
        blockers.append("PILOT_REVIEW_PACKET_DIGEST_INVALID")

    candidate_id = _text(data.get("candidate_id"), 120)
    if not candidate_id:
        blockers.append("PILOT_REVIEW_PACKET_CANDIDATE_REQUIRED")

    summary = (
        dict(data.get("summary"))
        if isinstance(data.get("summary"), Mapping)
        else {}
    )
    proposal = (
        dict(summary.get("proposal"))
        if isinstance(summary.get("proposal"), Mapping)
        else {}
    )
    pilot = (
        dict(summary.get("pilot"))
        if isinstance(summary.get("pilot"), Mapping)
        else {}
    )
    evidence = (
        dict(summary.get("evidence"))
        if isinstance(summary.get("evidence"), Mapping)
        else {}
    )
    if not _text(proposal.get("proposal_id"), 120):
        blockers.append("PILOT_REVIEW_PACKET_PROPOSAL_REQUIRED")
    if not _text(pilot.get("pilot_id"), 120):
        blockers.append("PILOT_REVIEW_PACKET_PILOT_REQUIRED")
    if pilot.get("activation_state") != "BLOCKED_UNTIL_OWNER_APPROVAL":
        blockers.append("PILOT_REVIEW_PACKET_ACTIVATION_BOUNDARY_INVALID")
    for key in (
        "proposal_digest",
        "readiness_evidence_digest",
        "pilot_handoff_digest",
        "operating_contract_digest",
    ):
        if not _text(evidence.get(key), 180):
            blockers.append(
                "PILOT_REVIEW_PACKET_EVIDENCE_DIGEST_MISSING:" + key
            )

    return list(dict.fromkeys(blockers))


def _request_identity_blockers(
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
        blockers.append("PILOT_OWNER_DECISION_CEREMONY_ID_INVALID")
    if (
        not isinstance(nonce, str)
        or _NONCE_RE.fullmatch(nonce) is None
    ):
        blockers.append("PILOT_OWNER_DECISION_NONCE_INVALID")
    if (
        not isinstance(key_id, str)
        or not key_id
        or len(key_id) > 128
    ):
        blockers.append("PILOT_OWNER_DECISION_KEY_ID_INVALID")
    if (
        not isinstance(key_version, int)
        or isinstance(key_version, bool)
        or key_version < 1
    ):
        blockers.append("PILOT_OWNER_DECISION_KEY_VERSION_INVALID")
    if decision not in DECISIONS:
        blockers.append("PILOT_OWNER_DECISION_CHOICE_INVALID")
    return blockers


def _blocked(*items: str) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "state": "BLOCKED",
        "blockers": sorted(set(items)),
        "owner_identity_signature_verified": False,
        "owner_decision_signature_verified": False,
        "owner_decision_verified": False,
        "owner_decision": "UNDECIDED",
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_approved": False,
        "pilot_denied": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "signature_capture_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def build_pilot_owner_decision_request(
    *,
    review_packet: Mapping[str, Any] | None,
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
    """Prepare a decision-specific external-signature request."""
    packet = dict(review_packet) if isinstance(review_packet, Mapping) else {}
    blockers = _packet_blockers(packet)
    blockers.extend(
        _request_identity_blockers(
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
                blockers.append(f"OWNER_{key_problem}")

    unique = sorted(set(blockers))
    if unique or entry is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "blockers": unique or ["PILOT_OWNER_DECISION_PRECONDITION_FAILED"],
            "request": {},
            "request_digest": "",
            "digest_to_sign": "",
            **{
                k: v
                for k, v in _blocked().items()
                if k not in {"schema", "state", "blockers"}
            },
        }

    scope = _scope(packet.get("scope"))
    summary = dict(packet.get("summary") or {})
    proposal = dict(summary.get("proposal") or {})
    pilot = dict(summary.get("pilot") or {})
    evidence = dict(summary.get("evidence") or {})

    body = {
        "schema": REQUEST_SCHEMA,
        "ceremony_id": ceremony_id,
        "decision_purpose": DECISION_PURPOSE,
        "signature_mechanism": SIGNATURE_MECHANISM,
        "decision": decision,
        "owner_id": scope["owner_id"],
        "tenant_id": scope["tenant_id"],
        "workspace_id": scope["workspace_id"],
        "candidate_id": _text(packet.get("candidate_id"), 120),
        "proposal_id": _text(proposal.get("proposal_id"), 120),
        "pilot_id": _text(pilot.get("pilot_id"), 120),
        "packet_digest": _text(packet.get("packet_digest"), 180),
        "proposal_digest": _text(evidence.get("proposal_digest"), 180),
        "readiness_evidence_digest": _text(
            evidence.get("readiness_evidence_digest"),
            180,
        ),
        "pilot_handoff_digest": _text(
            evidence.get("pilot_handoff_digest"),
            180,
        ),
        "operating_contract_digest": _text(
            evidence.get("operating_contract_digest"),
            180,
        ),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "key_id": key_id,
        "key_version": key_version,
        "owner_public_key_fingerprint": _public_key_fingerprint(entry),
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
    }
    request_digest = _digest(body)
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE",
        "blockers": [],
        "request": body,
        "request_digest": request_digest,
        "digest_to_sign": request_digest,
        "owner_identity_signature_verified": False,
        "owner_decision_signature_verified": False,
        "owner_decision_verified": False,
        "owner_decision": "UNDECIDED",
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_approved": False,
        "pilot_denied": False,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "signature_capture_performed": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
    }


def _nonce_scope(request: Mapping[str, Any], request_digest: str) -> str:
    scope = "|".join(
        (
            "B2B_PILOT_OWNER_DECISION",
            _text(request.get("owner_id"), 120),
            _text(request.get("tenant_id"), 120),
            _text(request.get("workspace_id"), 120),
            _text(request.get("pilot_id"), 120),
            _text(request.get("packet_digest"), 180),
            request_digest,
            _text(request.get("key_id"), 128),
            str(request.get("key_version")),
        )
    )
    if len(scope) > 256:
        return "B2B_PILOT|" + hashlib.sha256(
            scope.encode("utf-8")
        ).hexdigest()
    return scope


def verify_pilot_owner_decision(
    request: Mapping[str, Any] | None,
    *,
    decision_signature_b64: str,
    review_packet: Mapping[str, Any] | None,
    owner_trust_roots: TrustRootRegistry,
    decision_nonce_registry: PersistentNonceRegistry,
    now_ts: str,
) -> dict[str, Any]:
    """Verify exact pilot decision while keeping persistence/activation separate."""
    if not isinstance(request, Mapping):
        return _blocked("PILOT_OWNER_DECISION_REQUEST_REQUIRED")
    if not isinstance(owner_trust_roots, TrustRootRegistry):
        return _blocked("OWNER_TRUST_ROOT_REGISTRY_INVALID")
    if not isinstance(decision_nonce_registry, PersistentNonceRegistry):
        return _blocked("PILOT_OWNER_DECISION_NONCE_REGISTRY_INVALID")

    presented = dict(request)
    required_keys = {
        "schema",
        "ceremony_id",
        "decision_purpose",
        "signature_mechanism",
        "decision",
        "owner_id",
        "tenant_id",
        "workspace_id",
        "candidate_id",
        "proposal_id",
        "pilot_id",
        "packet_digest",
        "proposal_digest",
        "readiness_evidence_digest",
        "pilot_handoff_digest",
        "operating_contract_digest",
        "issued_at",
        "expires_at",
        "nonce",
        "key_id",
        "key_version",
        "owner_public_key_fingerprint",
        "owner_decision_recorded",
        "decision_record_persisted",
        "pilot_activation_authorized",
        "pilot_activated",
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "production_mutation_authorized",
        "external_action_executed",
    }
    if set(presented) != required_keys:
        return _blocked("PILOT_OWNER_DECISION_REQUEST_SHAPE_MISMATCH")

    blockers: list[str] = []
    if presented.get("schema") != REQUEST_SCHEMA:
        blockers.append("PILOT_OWNER_DECISION_REQUEST_SCHEMA_INVALID")
    if presented.get("decision_purpose") != DECISION_PURPOSE:
        blockers.append("PILOT_OWNER_DECISION_PURPOSE_INVALID")
    if presented.get("signature_mechanism") != SIGNATURE_MECHANISM:
        blockers.append("PILOT_OWNER_DECISION_SIGNATURE_MECHANISM_INVALID")

    blockers.extend(
        _request_identity_blockers(
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
        "owner_decision_recorded",
        "decision_record_persisted",
        "pilot_activation_authorized",
        "pilot_activated",
        "customer_contact_authorized",
        "contract_signature_authorized",
        "billing_authorized",
        "spend_authorized",
        "deploy_authorized",
        "crm_write_authorized",
        "production_mutation_authorized",
        "external_action_executed",
    ):
        if presented.get(key) is not False:
            blockers.append(
                "PILOT_OWNER_DECISION_UNSAFE_FIELD:" + key
            )

    if blockers:
        return _blocked(*blockers)

    rebuilt = build_pilot_owner_decision_request(
        review_packet=review_packet,
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
    if rebuilt.get("state") != "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE":
        result = _blocked(
            "PILOT_OWNER_DECISION_REQUEST_REBUILD_BLOCKED"
        )
        result["blockers"] = sorted(
            set(
                result["blockers"]
                + [
                    "REBUILD:" + item
                    for item in rebuilt.get("blockers", [])
                ]
            )
        )
        return result
    if rebuilt.get("request") != presented:
        return _blocked("PILOT_OWNER_DECISION_REQUEST_REBUILD_MISMATCH")

    try:
        entry, key_problem = owner_trust_roots.verify_key_available(
            presented["key_id"],
            presented["key_version"],
            now_ts,
        )
    except Exception:
        return _blocked("OWNER_TRUST_ROOT_VERIFICATION_FAILURE")
    if key_problem:
        return _blocked(f"OWNER_{key_problem}")
    if entry is None:
        return _blocked("OWNER_TRUST_KEY_UNKNOWN")
    if (
        presented.get("owner_public_key_fingerprint")
        != _public_key_fingerprint(entry)
    ):
        return _blocked(
            "PILOT_OWNER_DECISION_PUBLIC_KEY_FINGERPRINT_MISMATCH"
        )

    try:
        signature = _decode_signature(decision_signature_b64)
        entry.public_key().verify(
            signature,
            canonical_pilot_owner_decision_bytes(presented),
        )
    except (ValueError, InvalidSignature):
        return _blocked("PILOT_OWNER_DECISION_SIGNATURE_INVALID")

    request_digest = rebuilt["request_digest"]
    try:
        claimed = decision_nonce_registry.claim(
            scope=_nonce_scope(presented, request_digest),
            nonce=presented["nonce"],
            expires_at=presented["expires_at"],
            now_ts=now_ts,
        )
    except Exception:
        result = _blocked(
            "PILOT_OWNER_DECISION_NONCE_REGISTRY_FAILURE"
        )
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result
    if not claimed:
        result = _blocked("PILOT_OWNER_DECISION_NONCE_REPLAYED")
        result["owner_identity_signature_verified"] = True
        result["owner_decision_signature_verified"] = True
        return result

    decision = presented["decision"]
    approved = decision == "APPROVE_PILOT"
    denied = decision == "DENY_PILOT"

    record = {
        "schema": RESULT_SCHEMA,
        "decision": decision,
        "owner_id": presented["owner_id"],
        "tenant_id": presented["tenant_id"],
        "workspace_id": presented["workspace_id"],
        "candidate_id": presented["candidate_id"],
        "proposal_id": presented["proposal_id"],
        "pilot_id": presented["pilot_id"],
        "packet_digest": presented["packet_digest"],
        "decision_request_digest": request_digest,
        "owner_decision_verified": True,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "pilot_approved": approved,
        "pilot_denied": denied,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
    }

    return {
        "schema": RESULT_SCHEMA,
        "state": (
            "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE"
            if approved
            else "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
        ),
        "blockers": [],
        "owner_identity_signature_verified": True,
        "owner_decision_signature_verified": True,
        "owner_decision_verified": True,
        "owner_decision": decision,
        "owner_decision_recorded": False,
        "decision_record_persisted": False,
        "decision_record": record,
        "decision_record_digest": _digest(record),
        "pilot_approved": approved,
        "pilot_denied": denied,
        "pilot_activation_authorized": False,
        "pilot_activated": False,
        "requires_decision_record_persistence": True,
        "eligible_for_activation_ceremony_after_persistence": bool(approved),
        "signature_capture_performed": False,
        "customer_contact_authorized": False,
        "contract_signature_authorized": False,
        "billing_authorized": False,
        "spend_authorized": False,
        "deploy_authorized": False,
        "crm_write_authorized": False,
        "production_mutation_authorized": False,
        "external_action_executed": False,
        "network_called": False,
        "executes_action": False,
        "generic_chat_instruction_accepted_as_decision": False,
    }


__all__ = [
    "SCHEMA",
    "REQUEST_SCHEMA",
    "RESULT_SCHEMA",
    "PACKET_SCHEMA",
    "DECISION_PURPOSE",
    "SIGNATURE_MECHANISM",
    "DECISIONS",
    "MAX_DECISION_WINDOW_SECONDS",
    "canonical_pilot_owner_decision_bytes",
    "build_pilot_owner_decision_request",
    "verify_pilot_owner_decision",
]
