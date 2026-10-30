"""A214: local read-only evidence intake port; NEVER independent authority.

This is a staging protocol boundary. It binds an untrusted provider claim to a
local Outbox snapshot but cannot authenticate the issuer, host, owner, witness
or effect. It NEVER grants CONFIRMED or uses any network, key or provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping


OUTBOX_SCHEMA = "ATLASQUANT_AION_EXECUTION_OUTBOX_V1"
CHALLENGE_SCHEMA = "ATLASQUANT_AION_EFFECT_CHALLENGE_LOCAL_V0"
CANDIDATE_SCHEMA = "ATLASQUANT_AION_EFFECT_EVIDENCE_CANDIDATE_UNTRUSTED_V0"
_DOMAIN = b"ATLASQUANT-AION/A214/LOCAL-CHALLENGE/V0\n"
_TOK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_BOUND = frozenset({
    "owner_id", "tenant_id", "workspace_id", "idempotency_key",
    "decision_id", "intent_ref", "action", "payload_digest",
    "policy_version", "authorization_ref", "aggregate_seq",
    "attempts", "state", "dispatch_started_at", "sent_at",
    "created_at", "valid_until", "aggregate_key", "requires_reauth",
    "reauth_ref", "transaction_id", "authority_budget_ref",
    "risk_points", "capability_class", "grants_authority",
})
_CANDIDATE_KEYS = _BOUND | frozenset({
    "schema", "challenge_digest", "provider_id", "provider_event_id",
    "effect_ref", "effect_state", "provider_receipt_digest",
    "witness_root_fingerprint", "witness_checkpoint_hash",
    "witness_sequence", "occurred_at",
})
_TOK_FIELDS = frozenset({
    "owner_id", "tenant_id", "workspace_id", "decision_id", "intent_ref",
    "action", "policy_version", "authorization_ref", "aggregate_key",
})
_HEX_FIELDS = frozenset({"idempotency_key", "payload_digest"})


@dataclass(frozen=True)
class LocalEvidenceChallenge:
    challenge_json: str
    challenge_digest: str
    state: str
    may_confirm: bool = False


@dataclass(frozen=True)
class CandidatePreflight:
    matches_local_binding: bool
    may_confirm: bool
    code: str
    challenge_digest: str


def _deny(code: str) -> CandidatePreflight:
    return CandidatePreflight(False, False, code, "")


def _utc(value: Any) -> datetime:
    if type(value) is not str:
        raise ValueError("plain ISO-8601 timestamp text required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def _observed_utc(value: Any) -> datetime:
    """Caller observation may be aware datetime or ISO text; neither is trusted."""
    if type(value) is datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone required for observed_at")
        return value.astimezone(timezone.utc)
    return _utc(value)


def _token(value: Any) -> bool:
    return type(value) is str and _TOK.fullmatch(value) is not None


def _hex(value: Any) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def decode_candidate_json(raw: Any) -> dict[str, Any]:
    """Reject duplicate keys before the host can collapse them silently."""
    if type(raw) is not str or len(raw.encode("utf-8")) > 8192:
        raise ValueError("candidate JSON must be text and <=8192 bytes")

    def unique_pairs(pairs):
        out = {}
        for key, val in pairs:
            if key in out:
                raise ValueError("duplicate candidate key")
            out[key] = val
        return out

    def reject_nonfinite(value):
        raise ValueError("non-finite constant not allowed")

    try:
        parsed = json.loads(
            raw, object_pairs_hook=unique_pairs,
            parse_constant=reject_nonfinite,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid or ambiguous candidate JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("candidate must be JSON object")
    return parsed


def make_local_evidence_challenge(outbox_record: Any) -> LocalEvidenceChallenge:
    """Derive a deterministic *local* question from one ambiguous intent."""
    # Dict/field subclasses may execute arbitrary Python in get/eq/iteration.
    # This is untrusted local input, never an external authority proof.
    if type(outbox_record) is not dict:
        raise ValueError("outbox record must be a plain dict")
    if (type(outbox_record.get("schema")) is not str
            or outbox_record["schema"] != OUTBOX_SCHEMA):
        raise ValueError("outbox record unavailable")
    if (type(outbox_record.get("state")) is not str
            or outbox_record["state"] not in {"SENT", "UNCERTAIN"}):
        raise ValueError("only ambiguous SENT or UNCERTAIN may be examined")
    for field in ("idempotency_key", "decision_id", "aggregate_key",
                  "aggregate_seq", "sent_at"):
        if type(outbox_record.get(field)) not in (str, int, type(None)):
            raise ValueError("local record has nonprimitive binding")
    decision = outbox_record.get("decision")
    if (type(decision) is not dict
            or type(decision.get("schema")) is not str
            or decision["schema"] != OUTBOX_SCHEMA):
        raise ValueError("decision missing or malformed")

    body = {
        "schema": CHALLENGE_SCHEMA,
        "owner_id": decision.get("owner_id"),
        "tenant_id": decision.get("tenant_id"),
        "workspace_id": decision.get("workspace_id"),
        "idempotency_key": outbox_record.get("idempotency_key"),
        "decision_id": outbox_record.get("decision_id"),
        "intent_ref": decision.get("intent_ref"),
        "action": decision.get("action"),
        "payload_digest": decision.get("payload_digest"),
        "policy_version": decision.get("policy_version"),
        "authorization_ref": decision.get("authorization_ref"),
        "aggregate_seq": outbox_record.get("aggregate_seq"),
        "attempts": outbox_record.get("attempts"),
        "state": outbox_record.get("state"),
        "dispatch_started_at": outbox_record.get("dispatch_started_at"),
        "sent_at": outbox_record.get("sent_at"),
        "created_at": decision.get("created_at"),
        "valid_until": decision.get("valid_until"),
        "aggregate_key": decision.get("aggregate_key"),
        "requires_reauth": decision.get("requires_reauth"),
        "reauth_ref": decision.get("reauth_ref"),
        "transaction_id": decision.get("transaction_id"),
        "authority_budget_ref": decision.get("authority_budget_ref"),
        "risk_points": decision.get("risk_points"),
        "capability_class": decision.get("capability_class"),
        "grants_authority": decision.get("grants_authority"),
    }

    # A273: no Python object equality/stringification during preflight.
    if any(type(value) not in (str, int, float, bool, type(None))
           for value in body.values()):
        raise ValueError("local binding has nonprimitive value")
    for name in _TOK_FIELDS:
        if not _token(body[name]):
            raise ValueError("local token binding malformed")
    for name in _HEX_FIELDS:
        if not _hex(body[name]):
            raise ValueError("local digest binding malformed")
    for name in ("aggregate_seq", "attempts"):
        if type(body[name]) is not int or body[name] < 1:
            raise ValueError("local positive sequence required")
    for name, maximum in (("reauth_ref", 160), ("transaction_id", 128),
                          ("authority_budget_ref", 128), ("capability_class", 80)):
        value = body[name]
        if not isinstance(value, str) or len(value) > maximum or chr(0) in value:
            raise ValueError("local optional authority field malformed")
    if type(body["requires_reauth"]) is not bool or body["grants_authority"] is not False:
        raise ValueError("local authority flag malformed")
    if body["requires_reauth"] and not body["reauth_ref"]:
        raise ValueError("local reauth binding incomplete")
    if type(body["risk_points"]) is not int or not 0 <= body["risk_points"] <= 100:
        raise ValueError("local authority risk points malformed")
    if body["aggregate_key"] != outbox_record.get("aggregate_key"):
        raise ValueError("local aggregate key mismatch")
    if outbox_record["idempotency_key"] != decision.get("idempotency_key"):
        raise ValueError("local idempotency mismatch")
    if outbox_record["decision_id"] != decision.get("decision_id"):
        raise ValueError("local decision mismatch")
    if outbox_record["aggregate_seq"] != decision.get("aggregate_seq"):
        raise ValueError("local aggregate mismatch")
    if outbox_record["state"] == "SENT" and not body["sent_at"]:
        raise ValueError("SENT must have a sent timestamp")
    try:
        started = _utc(body["dispatch_started_at"])
        created = _utc(body["created_at"])
        valid_until = _utc(body["valid_until"])
        if body["sent_at"]:
            sent = _utc(body["sent_at"])
            if sent < started:
                raise ValueError("sent precedes dispatch")
    except (ValueError, OverflowError, TypeError) as exc:
        raise ValueError("invalid local time binding") from exc
    if not created <= started <= valid_until:
        raise ValueError("dispatch is outside original authority window")

    encoded = json.dumps(
        body, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    )
    digest = sha256(_DOMAIN + encoded.encode("utf-8")).hexdigest()
    return LocalEvidenceChallenge(encoded, digest, body["state"])


def preflight_untrusted_effect_candidate(
    outbox_record: Any,
    candidate: Any,
    *,
    observed_at: Any,
) -> CandidatePreflight:
    """Check claim binding only; no authority or state mutation is possible."""
    try:
        challenge = make_local_evidence_challenge(outbox_record)
    except (ValueError, OverflowError, TypeError):
        return _deny("LOCAL_INTENT_UNAVAILABLE")

    if type(candidate) is str:
        try:
            candidate = decode_candidate_json(candidate)
        except ValueError:
            return _deny("MALFORMED_OR_AMBIGUOUS_CANDIDATE")
    if (type(candidate) is not dict
            or any(type(key) is not str for key in candidate)
            or set(candidate) != _CANDIDATE_KEYS):
        return _deny("CANDIDATE_ENVELOPE_NOT_EXACT")
    if any(type(value) not in (str, int, float, bool, type(None))
           for value in candidate.values()):
        return _deny("CANDIDATE_NONPRIMITIVE_UNTRUSTED")
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        return _deny("UNSUPPORTED_CANDIDATE_SCHEMA")
    if not _hex(candidate.get("challenge_digest")):
        return _deny("INVALID_CHALLENGE_DIGEST")
    if candidate["challenge_digest"] != challenge.challenge_digest:
        return _deny("LOCAL_CHALLENGE_MISMATCH")

    body = json.loads(challenge.challenge_json)
    for name in _BOUND:
        # Also catches booleans that compare equal to integer 1.
        if type(candidate[name]) is not type(body[name]) or candidate[name] != body[name]:
            return _deny("ORIGINAL_INTENT_OR_ATTEMPT_MISMATCH")

    for name in ("provider_id", "provider_event_id", "effect_ref"):
        if not _token(candidate[name]):
            return _deny("INVALID_PROVIDER_IDENTIFIERS")
    for name in (
        "provider_receipt_digest", "witness_root_fingerprint",
        "witness_checkpoint_hash",
    ):
        if not _hex(candidate[name]):
            return _deny("INVALID_UNATTESTED_EVIDENCE_FINGERPRINT")
    if type(candidate["witness_sequence"]) is not int or candidate["witness_sequence"] < 1:
        return _deny("INVALID_WITNESS_SEQUENCE")
    if candidate["effect_state"] != "EFFECT_CONFIRMED":
        return _deny("CLAIMED_EFFECT_NOT_FINAL")

    try:
        observed = _observed_utc(observed_at)
        event_time = _utc(candidate["occurred_at"])
        started = _utc(body["dispatch_started_at"])
    except (ValueError, OverflowError, TypeError):
        return _deny("INVALID_CLAIMED_EVENT_TIME")
    if not started <= event_time <= observed:
        return _deny("CLAIMED_EFFECT_OUTSIDE_OBSERVED_WINDOW")

    # Everything above is host-observable data. A compromised host could
    # fabricate ALL fields, digests and two matching witnesses. No external
    # verification key, receipt inclusion proof or provider query occurred.
    return CandidatePreflight(
        matches_local_binding=True,
        may_confirm=False,
        code="LOCAL_BINDING_OK_EXTERNAL_AUTHORITY_AND_EFFECT_UNPROVEN",
        challenge_digest=challenge.challenge_digest,
    )


__all__ = [
    "CHALLENGE_SCHEMA", "CANDIDATE_SCHEMA",
    "LocalEvidenceChallenge", "CandidatePreflight",
    "decode_candidate_json", "make_local_evidence_challenge",
    "preflight_untrusted_effect_candidate",
]
