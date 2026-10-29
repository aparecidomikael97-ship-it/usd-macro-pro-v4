"""A256 LAB: issue, bind and consume one-time challenges before A255 review.

This is HOST-MEMORY state with a HOST-SUPPLIED clock and signer public keys.
It cannot prove independent issuance, monotonicity, ownership or real effects.
Every result explicitly denies permission to send.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import secrets
from threading import Lock
from typing import Mapping

from labs.a254_synthetic_origin_event_identity import (
    EVENT_ID, FIELDS as ORIGIN_FIELDS, MATCH_FIELDS,
    SCHEMA as ORIGIN_SCHEMA, canonical_bytes,
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
        now, high_water=0, ttl_seconds=60,
    ):
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 90:
            raise ValueError("challenge TTL must be 1..90 seconds")
        self._start = _clock(now)
        self._ttl = ttl_seconds
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

    def begin(self, decision, origin_envelope):
        """Issue random nonce for one candidate event; not a proof of identity."""
        try:
            identity, origin_hash, decision_hash = self._binding(decision, origin_envelope)
        except Exception:
            return _deny("DENY_INVALID_EVENT_CANDIDATE")
        with self._lock:
            if identity in self._events_seen:
                return _deny("DENY_EVENT_ALREADY_SEEN_OR_PENDING")
            challenge = secrets.token_hex(32)
            if challenge in self._issued:
                return _deny("DENY_CHALLENGE_COLLISION")
            self._issued[challenge] = {
                "identity": identity, "origin_hash": origin_hash,
                "decision_hash": decision_hash, "issued_at": self._start,
                "consumed": False,
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
            observed = self._start if observed_at is None else _clock(observed_at)
            if observed < record["issued_at"] or (
                observed - record["issued_at"]
            ).total_seconds() > self._ttl:
                return _deny("DENY_EXPIRED_CHALLENGE")
            identity, origin_hash, decision_hash = self._binding(decision, origin_envelope)
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
