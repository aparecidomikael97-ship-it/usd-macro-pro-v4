"""A255 two-signer event/reservation BINDING: synthetic LAB only.

Two different Ed25519 signing keys can be controlled by the same host. This
module validates a format and cross-signature binding; it NEVER authenticates
independence or returns authority to send. No network, Worker or provider.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import re
from threading import Lock
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a254_synthetic_origin_event_identity import (
    SyntheticOriginEventRegistryLab,
    canonical_bytes,
)

SCHEMA = "ATLASQUANT_AION_A255_SYNTHETIC_TWO_PARTY_RESERVATION_V1"
DOMAIN = b"ATLASQUANT:A255:LAB:TWO_PARTY_RESERVATION_V1\x00"
HEX64 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
FIELDS = frozenset({
    "schema", "status", "issuer", "key_id", "challenge", "event_id",
    "origin_envelope_sha256", "event_effect_digest", "owner_id",
    "tenant_id", "workspace_id", "sequence", "issued_at", "expires_at",
})


def _failed(reason):
    return {
        "schema": SCHEMA, "status": reason, "linked_format_valid": False,
        "authorizes_send": False, "independent_origin_proven": False,
        "independent_witness_proven": False, "p0_homologated": 0,
    }


def _utc_stamp(raw):
    if type(raw) is not str:
        raise ValueError("timestamp must be text")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return parsed.astimezone(timezone.utc)


class SyntheticTwoPartyReservationLab:
    """Consumes valid A254 event proof and checks separate witness signature.

    The origin event is consumed before the witness reply is evaluated. Lost or
    invalid reservation evidence therefore burns the local synthetic event
    and requires independent reconciliation; no retry is authorized.
    """

    def __init__(
        self, *, origin_issuer, origin_key_id, origin_public_key,
        witness_issuer, witness_key_id, witness_public_key, now,
        high_water=0,
    ):
        if type(origin_public_key) is not bytes or len(origin_public_key) != 32:
            raise ValueError("32-byte origin key required")
        if type(witness_public_key) is not bytes or len(witness_public_key) != 32:
            raise ValueError("32-byte witness key required")
        if origin_public_key == witness_public_key:
            raise ValueError("distinct signer keys required, not independent custody")
        if (
            type(witness_issuer) is not str or not witness_issuer
            or len(witness_issuer) > 128 or type(witness_key_id) is not str
            or not witness_key_id or len(witness_key_id) > 128
        ):
            raise ValueError("witness identity fields required")
        if origin_issuer == witness_issuer:
            raise ValueError("origin and witness labels must differ")
        if type(high_water) is not int or high_water < 0:
            raise ValueError("nonnegative integer high water required")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("aware local LAB clock required")
        self._origin = SyntheticOriginEventRegistryLab(
            issuer=origin_issuer, key_id=origin_key_id,
            public_key=origin_public_key, now=now,
        )
        self._witness_key = Ed25519PublicKey.from_public_bytes(witness_public_key)
        self._witness_issuer = witness_issuer
        self._witness_key_id = witness_key_id
        self._now = now.astimezone(timezone.utc)
        self._high_water = high_water
        self._lock = Lock()

    def review(self, decision, origin_envelope, witness_envelope, *, expected_challenge):
        try:
            return self._review(
                decision, origin_envelope, witness_envelope,
                expected_challenge=expected_challenge,
            )
        except Exception:
            return _failed("DENY_MALFORMED_OR_UNVERIFIED")

    def _review(self, decision, origin_envelope, witness_envelope, *, expected_challenge):
        if type(expected_challenge) is not str or HEX64.fullmatch(expected_challenge) is None:
            return _failed("DENY_CHALLENGE")
        if not isinstance(decision, Mapping):
            return _failed("DENY_DECISION")
        if type(origin_envelope) is not dict or set(origin_envelope) != {"payload", "signature"}:
            return _failed("DENY_ORIGIN_ENVELOPE")
        if type(witness_envelope) is not dict or set(witness_envelope) != {"payload", "signature"}:
            return _failed("DENY_WITNESS_ENVELOPE")
        witnessed = witness_envelope["payload"]
        if type(witnessed) is not dict or set(witnessed) != FIELDS:
            return _failed("DENY_WITNESS_FIELDS")
        if (
            witnessed["schema"] != SCHEMA or witnessed["status"] != "RESERVED"
            or witnessed["issuer"] != self._witness_issuer
            or witnessed["key_id"] != self._witness_key_id
            or witnessed["challenge"] != expected_challenge
        ):
            return _failed("DENY_WITNESS_IDENTITY_OR_CHALLENGE")

        # Validate the witness's *format and signature first*. Do not record
        # an origin event upon a bare unsigned/malformed claim.
        sig_text = witness_envelope["signature"]
        if type(sig_text) is not str or len(sig_text) > 128:
            return _failed("DENY_WITNESS_SIGNATURE")
        raw_sig = base64.b64decode(sig_text, validate=True)
        if len(raw_sig) != 64:
            return _failed("DENY_WITNESS_SIGNATURE")
        self._witness_key.verify(raw_sig, DOMAIN + canonical_bytes(witnessed))

        origin_digest = sha256(canonical_bytes(origin_envelope)).hexdigest()
        if witnessed["origin_envelope_sha256"] != origin_digest:
            return _failed("DENY_ORIGIN_ENVELOPE_MISMATCH")

        origin_payload = origin_envelope["payload"]
        if type(origin_payload) is not dict:
            return _failed("DENY_ORIGIN_PAYLOAD")
        if any(
            type(witnessed[field]) is not str
            or witnessed[field] != origin_payload.get(field)
            for field in ("event_id", "owner_id", "tenant_id", "workspace_id")
        ):
            return _failed("DENY_EVENT_OR_SCOPE_MISMATCH")
        seq = witnessed["sequence"]
        if type(seq) is not int or seq <= 0:
            return _failed("DENY_SEQUENCE")
        issued = _utc_stamp(witnessed["issued_at"])
        expires = _utc_stamp(witnessed["expires_at"])
        if (
            issued > self._now or expires < self._now or expires <= issued
            or (expires - issued).total_seconds() > 90
        ):
            return _failed("DENY_WITNESS_TIME")

        event_result = self._origin.review(decision, origin_envelope)
        if not event_result["new_event"]:
            return _failed("DENY_ORIGIN_EVENT_OR_REPLAY")
        if witnessed["event_effect_digest"] != event_result["event_effect_digest"]:
            return _failed("DENY_EFFECT_DIGEST_MISMATCH")

        with self._lock:
            if seq <= self._high_water:
                return _failed("DENY_STALE_WITNESS_SEQUENCE")
            self._high_water = seq

        return {
            "schema": SCHEMA, "status": "LAB_TWO_SIGNATURES_MATCHED_ONLY",
            "linked_format_valid": True,
            "authorizes_send": False,
            "independent_origin_proven": False,
            "independent_witness_proven": False,
            "p0_homologated": 0,
        }


__all__ = ["SCHEMA", "DOMAIN", "FIELDS", "SyntheticTwoPartyReservationLab"]
