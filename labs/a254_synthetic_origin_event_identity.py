"""A254 LAB — signed *event identity* schema, never execution authority.

P0-3 prerequisite only: distinguish two authentic distinct business events with
identical payloads from a replay of the same event under different request IDs.
The pinned origin key, ledger and clock are caller-controlled, hence NOT
independent. This module does not contact an external origin and may NEVER
authorize an adapter.send, activate a Worker, or close any P0.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from threading import Lock
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "ATLASQUANT_AION_A254_SYNTHETIC_ORIGIN_EVENT_V1"
DOMAIN = b"ATLASQUANT:A254:LAB:EVENT_ORIGIN_V1\x00"
EFFECT_DOMAIN = b"ATLASQUANT:A254:LAB:EVENT_EFFECT_V1\x00"
FIELDS = frozenset({
    "schema", "issuer", "key_id", "event_id", "owner_id", "tenant_id",
    "workspace_id", "action", "aggregate_key", "payload_digest",
    "issued_at", "expires_at",
})
EVENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
HEX_SHA256 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
MATCH_FIELDS = (
    "owner_id", "tenant_id", "workspace_id", "action",
    "aggregate_key", "payload_digest",
)


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _utc_stamp(value):
    if type(value) is not str:
        raise ValueError("timestamp must be string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone-aware stamp required")
    return dt.astimezone(timezone.utc)


def _fail(reason):
    return {
        "schema": SCHEMA, "status": reason,
        "format_valid": False, "new_event": False,
        "event_effect_digest": None, "authorizes_send": False,
        "independent_origin_proven": False,
    }


class SyntheticOriginEventRegistryLab:
    """Host-memory anti-replay for test-only identities; NO external custody."""

    def __init__(self, *, issuer, key_id, public_key, now):
        if type(issuer) is not str or not issuer or len(issuer) > 128:
            raise ValueError("issuer required")
        if type(key_id) is not str or not key_id or len(key_id) > 128:
            raise ValueError("key ID required")
        if type(public_key) is not bytes or len(public_key) != 32:
            raise ValueError("Ed25519 raw public key required")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("timezone-aware local LAB clock required")
        self._issuer = issuer
        self._key_id = key_id
        self._origin_key = Ed25519PublicKey.from_public_bytes(public_key)
        self._now = now.astimezone(timezone.utc)
        self._seen = {}
        self._lock = Lock()

    def review(self, decision, envelope):
        """Review format and LAB in-memory replay, never authorize any send."""
        try:
            return self._review(decision, envelope)
        except Exception:
            return _fail("DENY_MALFORMED_OR_UNVERIFIED")

    def _review(self, decision, envelope):
        if not isinstance(decision, Mapping):
            return _fail("DENY_DECISION")
        if type(envelope) is not dict or set(envelope) != {"payload", "signature"}:
            return _fail("DENY_ENVELOPE")
        payload = envelope["payload"]
        if type(payload) is not dict or set(payload) != FIELDS:
            return _fail("DENY_FIELDS")
        if (
            payload["schema"] != SCHEMA or
            payload["issuer"] != self._issuer or
            payload["key_id"] != self._key_id
        ):
            return _fail("DENY_ORIGIN_PIN")
        if any(
            type(payload[name]) is not str or type(decision.get(name)) is not str
            or payload[name] != decision[name] or not payload[name]
            for name in MATCH_FIELDS
        ):
            return _fail("DENY_SCOPE_ACTION_OR_PAYLOAD_MISMATCH")
        if HEX_SHA256.fullmatch(payload["payload_digest"]) is None:
            return _fail("DENY_PAYLOAD_DIGEST")
        eid = payload["event_id"]
        if type(eid) is not str or EVENT_ID.fullmatch(eid) is None:
            return _fail("DENY_EVENT_ID")
        for k in ("issuer", "key_id"):
            if type(payload[k]) is not str or not payload[k] or len(payload[k]) > 128:
                return _fail("DENY_IDENTITY_FIELD")
        start = _utc_stamp(payload["issued_at"])
        end = _utc_stamp(payload["expires_at"])
        if start > self._now or self._now > end or end <= start:
            return _fail("DENY_EVENT_TIME")
        if (end - start).total_seconds() > 300:
            return _fail("DENY_EVENT_TIME")
        signature = envelope["signature"]
        if type(signature) is not str or len(signature) > 128:
            return _fail("DENY_SIGNATURE")
        decoded = base64.b64decode(signature, validate=True)
        if len(decoded) != 64:
            return _fail("DENY_SIGNATURE")
        self._origin_key.verify(decoded, DOMAIN + canonical_bytes(payload))

        # Stable identity is NOT request ID: same authentic event under a new
        # technical request ID yields same effect digest and replay denial.
        # Different authentic events, even with the same payload, are distinct.
        identity = (
            self._issuer, payload["owner_id"], payload["tenant_id"],
            payload["workspace_id"], eid,
        )
        effect = sha256(EFFECT_DOMAIN + canonical_bytes({
            "issuer": self._issuer, "event_id": eid,
            **{name: payload[name] for name in MATCH_FIELDS},
        })).hexdigest()
        with self._lock:
            if identity in self._seen:
                return {
                    **_fail(
                        "DENY_EVENT_ID_PAYLOAD_CONFLICT"
                        if self._seen[identity] != effect
                        else "DENY_REPEATED_EVENT"
                    ),
                    "format_valid": True,
                }
            self._seen[identity] = effect

        return {
            "schema": SCHEMA, "status": "LAB_SIGNED_DISTINCT_EVENT",
            "format_valid": True, "new_event": True,
            "event_effect_digest": effect, "authorizes_send": False,
            "independent_origin_proven": False,
        }


__all__ = ["SCHEMA", "DOMAIN", "EFFECT_DOMAIN", "FIELDS",
           "canonical_bytes", "SyntheticOriginEventRegistryLab"]
