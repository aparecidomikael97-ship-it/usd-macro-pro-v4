"""A256 LAB: issue, bind and consume one-time challenges before A255 review.

This is HOST-MEMORY state with a HOST-SUPPLIED clock and signer public keys.
It cannot prove independent issuance, monotonicity, ownership or real effects.
Every result explicitly denies permission to send.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math
import secrets
import time
from threading import Lock
from typing import Mapping

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from labs.a254_synthetic_origin_event_identity import (
    DOMAIN as ORIGIN_DOMAIN, EVENT_ID, FIELDS as ORIGIN_FIELDS,
    MATCH_FIELDS, SCHEMA as ORIGIN_SCHEMA, canonical_bytes,
)
from labs.a255_two_party_reservation_binding import SyntheticTwoPartyReservationLab

SCHEMA = "ATLASQUANT_AION_A256_LOCAL_ONE_TIME_CHALLENGE_LAB_V1"


def _deny(reason):
    return {
        "schema": SCHEMA, "status": reason, "challenge": None,
        "linked_format_valid": False, "authorizes_send": False,
        "independent_origin_proven": False,
        "independent_witness_proven": False,
        "independent_challenge_proven": False, "p0_homologated": 0,
    }


def _clock(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


class SyntheticOneTimeChallengeLab:
    """Generate and consume an event-bound nonce exactly once per local run.

    A failed/late/ambiguous response consumes its pending nonce; independent
    reconciliation is required before any real retry, which this class cannot
    perform. It does not expose an authorization or adapter capability.
    """

    def __init__(
        self, *, origin_issuer, origin_key_id, origin_public_key,
        witness_issuer, witness_key_id, witness_public_key,
        now, high_water=0, ttl_seconds=60, monotonic_clock=None,
    ):
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 90:
            raise ValueError("challenge TTL must be 1..90 seconds")
        self._start = _clock(now)
        self._ttl = ttl_seconds
        # A257: elapsed time must never default to the startup wall time.
        # The monotonic clock is a HOST clock; tests inject a deterministic one.
        self._ticks = time.monotonic if monotonic_clock is None else monotonic_clock
        if not callable(self._ticks):
            raise ValueError("monotonic clock callable required")
        self._first_tick = None
        self._last_tick = None
        self._clock_failed = False
        self._issuer = origin_issuer
        self._key_id = origin_key_id
        self._origin_key = Ed25519PublicKey.from_public_bytes(origin_public_key)
        self._link = SyntheticTwoPartyReservationLab(
            origin_issuer=origin_issuer, origin_key_id=origin_key_id,
            origin_public_key=origin_public_key,
            witness_issuer=witness_issuer, witness_key_id=witness_key_id,
            witness_public_key=witness_public_key,
            now=now, high_water=high_water,
        )
        self._lock = Lock()
        self._issued = {}
        self._events_seen = set()

    @staticmethod
    def _binding(decision, origin_envelope):
        if not isinstance(decision, Mapping):
            raise ValueError("decision must be a mapping")
        if type(origin_envelope) is not dict or set(origin_envelope) != {"payload", "signature"}:
            raise ValueError("signed origin envelope structure required")
        payload = origin_envelope["payload"]
        if type(payload) is not dict or set(payload) != ORIGIN_FIELDS:
            raise ValueError("strict origin fields required")
        if payload.get("schema") != ORIGIN_SCHEMA:
            raise ValueError("wrong origin schema")
        event_id = payload.get("event_id")
        if type(event_id) is not str or EVENT_ID.fullmatch(event_id) is None:
            raise ValueError("invalid event ID")
        if type(payload.get("issuer")) is not str or not payload["issuer"]:
            raise ValueError("origin issuer missing")
        if any(
            type(decision.get(field)) is not str
            or not decision[field]
            or decision[field] != payload.get(field)
            for field in MATCH_FIELDS
        ):
            raise ValueError("scope/action/payload mismatch")
        if type(origin_envelope["signature"]) is not str:
            raise ValueError("origin signature representation required")
        identity = (
            payload["issuer"], payload["owner_id"], payload["tenant_id"],
            payload["workspace_id"], event_id,
        )
        origin_hash = sha256(canonical_bytes(origin_envelope)).hexdigest()
        decision_hash = sha256(canonical_bytes({
            field: decision[field] for field in MATCH_FIELDS
        })).hexdigest()
        return identity, origin_hash, decision_hash

    def _tick_locked(self):
        """Strictly increasing/nondecreasing clock observation under mutex."""
        if self._clock_failed:
            raise ValueError("local LAB clock already unsafe")
        try:
            value = self._ticks()
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid monotonic tick")
            tick = float(value)
            if self._last_tick is not None and tick < self._last_tick:
                raise ValueError("monotonic clock went backward")
        except Exception:
            self._clock_failed = True
            raise
        if self._first_tick is None:
            self._first_tick = tick
        self._last_tick = tick
        return tick

    def _lab_time_at(self, tick):
        # Host-injected anchor + monotonic elapsed: not external trusted time.
        return self._start + timedelta(seconds=tick - self._first_tick)

    def _verify_origin_before_issue(self, origin_envelope, observed):
        """Verify cryptographic format BEFORE reserving/issuing a nonce."""
        payload = origin_envelope["payload"]
        if (payload["issuer"] != self._issuer or payload["key_id"] != self._key_id):
            raise ValueError("host-pinned issuer/key ID mismatch")
        signature = origin_envelope["signature"]
        if type(signature) is not str or len(signature) > 128:
            raise ValueError("bad origin signature encoding")
        raw = base64.b64decode(signature, validate=True)
        if len(raw) != 64:
            raise ValueError("bad origin signature size")
        self._origin_key.verify(raw, ORIGIN_DOMAIN + canonical_bytes(payload))
        start = _clock(datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00")))
        end = _clock(datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00")))
        if not (start <= observed <= end) or end <= start or (end - start).total_seconds() > 300:
            raise ValueError("origin event outside signed time window")

    def begin(self, decision, origin_envelope):
        """Issue random nonce for one candidate event; not a proof of identity."""
        try:
            identity, origin_hash, decision_hash = self._binding(decision, origin_envelope)
        except Exception:
            return _deny("DENY_INVALID_EVENT_CANDIDATE")
        with self._lock:
            try:
                issued_tick = self._tick_locked()
            except Exception:
                return _deny("DENY_LOCAL_CLOCK_UNSAFE")
            if identity in self._events_seen:
                return _deny("DENY_EVENT_ALREADY_SEEN_OR_PENDING")
            try:
                self._verify_origin_before_issue(
                    origin_envelope, self._lab_time_at(issued_tick)
                )
            except Exception:
                return _deny("DENY_UNVERIFIED_OR_EXPIRED_ORIGIN")
            challenge = secrets.token_hex(32)
            if challenge in self._issued:
                return _deny("DENY_CHALLENGE_COLLISION")
            self._issued[challenge] = {
                "identity": identity, "origin_hash": origin_hash,
                "decision_hash": decision_hash,
                "issued_at": self._lab_time_at(issued_tick),
                "issued_tick": issued_tick, "consumed": False,
            }
            # This remains reserved even after a malformed response, a
            # timeout, or an abandoned request: no blind reissuance.
            self._events_seen.add(identity)
        return {
            **_deny("LAB_CHALLENGE_ISSUED_NO_AUTHORITY"),
            "challenge": challenge,
        }

    def review(
        self, decision, origin_envelope, witness_envelope, *,
        challenge, observed_at=None,
    ):
        """Spend nonce atomically before verifying a possibly late receipt."""
        if type(challenge) is not str:
            return _deny("DENY_UNKNOWN_CHALLENGE")
        with self._lock:
            record = self._issued.get(challenge)
            if record is None:
                return _deny("DENY_UNKNOWN_CHALLENGE")
            if record["consumed"]:
                return _deny("DENY_CHALLENGE_ALREADY_CONSUMED")
            record["consumed"] = True
            try:
                observed_tick = self._tick_locked()
            except Exception:
                return _deny("DENY_LOCAL_CLOCK_UNSAFE")
            effective_now = self._lab_time_at(observed_tick)
        try:
            # A caller-provided observed_at is *only* an extra denial check.
            # It cannot replace or rewind the measured monotonic elapsed time.
            if (observed_tick - record["issued_tick"] > self._ttl):
                return _deny("DENY_EXPIRED_CHALLENGE")
            if observed_at is not None:
                reported = _clock(observed_at)
                if reported < record["issued_at"] or (
                    reported - record["issued_at"]
                ).total_seconds() > self._ttl:
                    return _deny("DENY_EXPIRED_CHALLENGE")
            # A255 has a fixed host LAB clock. Reject witness envelopes that
            # are expired/future relative to A257's progressing local time.
            if type(witness_envelope) is dict and type(witness_envelope.get("payload")) is dict:
                proof = witness_envelope["payload"]
                signed_from = _clock(datetime.fromisoformat(proof["issued_at"].replace("Z", "+00:00")))
                signed_until = _clock(datetime.fromisoformat(proof["expires_at"].replace("Z", "+00:00")))
                if signed_from > effective_now or signed_until < effective_now:
                    return _deny("DENY_WITNESS_TIME_ELAPSED")
            try:
                identity, origin_hash, decision_hash = self._binding(
                    decision, origin_envelope
                )
            except Exception:
                # A submitted nonce is already spent. A semantic or malformed
                # event mismatch must remain an explicit fail-closed result.
                return _deny("DENY_CHALLENGE_EVENT_MISMATCH")
            if (
                identity != record["identity"]
                or origin_hash != record["origin_hash"]
                or decision_hash != record["decision_hash"]
            ):
                return _deny("DENY_CHALLENGE_EVENT_MISMATCH")
            result = self._link.review(
                decision, origin_envelope, witness_envelope,
                expected_challenge=challenge,
            )
            return {
                **result, "challenge": None,
                "independent_challenge_proven": False,
                "authorizes_send": False, "p0_homologated": 0,
            }
        except Exception:
            return _deny("DENY_CHALLENGE_REVIEW_ERROR")


__all__ = ["SCHEMA", "SyntheticOneTimeChallengeLab"]
