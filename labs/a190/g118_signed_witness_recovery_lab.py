"""G118 signed witness observation after uncertain first attempt (LAB ONLY).

A signed witness reservation proves at most that the same-host test witness
recorded a RESERVED intent. It does NOT prove that the external provider
executed, rejected or even received it. This class has NO reserve(), send(),
reconcile_provider(), bootstrap() or approval methods. Every result forbids
SEND, RETRY and effect confirmation, including statuses labelled NOT_FOUND.
Privileged same-host rollback, repinning and Python replacement remain open.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from aion_chat.first_attempt_witness_lab import _effect_digest
from aion_chat.intent_binding_a182_lab import semantic_bytes
from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab
from labs.a190.g114_public_key_witness_client_lab import G114PublicKeyWitnessClientLab

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class RecoveryObservationLab:
    """Read-only result; never a provider receipt or send authorization."""
    disposition: str
    observed_sequence: int | None = None
    signed_witness_observed: bool = False
    provider_outcome: str = "UNKNOWN"
    allow_send: bool = False
    allow_retry: bool = False
    may_mark_provider_confirmed: bool = False


class G118SignedWitnessRecoveryLab:
    """Read signed same-host witness state without creating a new intention."""

    def __init__(
        self, *, witness_client, event_id, original_decision,
        original_sha256, retained_high_water=0,
    ):
        if type(witness_client) is not G114PublicKeyWitnessClientLab:
            raise TypeError("G118_SIGNED_PUBLIC_CLIENT_REQUIRED")
        if (type(event_id) is not str or _HEX64.fullmatch(event_id) is None):
            raise ValueError("G118_PINNED_EVENT_ID_REQUIRED")
        if type(original_decision) is not dict:
            raise ValueError("G118_ORIGINAL_DECISION_REQUIRED")
        source = semantic_bytes(original_decision)
        expected = sha256(source).hexdigest()
        if original_sha256 != expected or type(original_sha256) is not str:
            raise ValueError("G118_ORIGINAL_SHA256_PIN_REQUIRED")
        if type(retained_high_water) is not int or retained_high_water < 0:
            raise ValueError("G118_RETAINED_ORDINAL_REQUIRED")
        request = original_decision.get("idempotency_key")
        if type(request) is not str or _HEX64.fullmatch(request) is None:
            raise ValueError("G118_ORIGINAL_REQUEST_ID_REQUIRED")
        scope = tuple(original_decision.get(k) for k in (
            "owner_id", "tenant_id", "workspace_id",
        ))
        if any(type(k) is not str or not k for k in scope):
            raise ValueError("G118_ORIGINAL_SCOPE_REQUIRED")
        self._client = witness_client
        self._event = event_id
        self._original_sha256 = expected
        self._effect = _effect_digest(original_decision)
        self._request_id = request
        self._scope = scope
        self._retained = retained_high_water

    def inspect(self):
        """Fresh signed status only. Does NOT enroll, reserve or send."""
        try:
            signed = self._client.status(self._event)
        except (WitnessProcessUnavailableLab, OSError, RuntimeError, ValueError):
            return RecoveryObservationLab("WITNESS_UNAVAILABLE_HOLD_NO_SEND")
        if type(signed) is not dict:
            return RecoveryObservationLab("MALFORMED_SIGNED_STATUS_NO_SEND")
        if (signed.get("event_id") != self._event
                or type(signed.get("high_water")) is not int
                or type(signed.get("count")) is not int
                or type(signed.get("sequence")) is not int
                or signed["high_water"] < 0
                or signed["high_water"] != signed["count"]
                or signed["sequence"] < 0
                or signed["sequence"] > signed["high_water"]):
            return RecoveryObservationLab("MALFORMED_SIGNED_STATUS_NO_SEND")
        if signed["high_water"] < self._retained:
            return RecoveryObservationLab(
                "ROLLBACK_SUSPECTED_NO_SEND", signed["sequence"], True,
            )
        if signed.get("status") == "NOT_FOUND":
            # No record in a locally restorable witness cannot establish
            # authoritative ABSENCE of a past attempt.
            return RecoveryObservationLab(
                "ABSENCE_UNPROVEN_NO_SEND", None, True,
            )
        if (signed.get("original_sha256") != self._original_sha256
                or tuple(signed.get(k) for k in (
                    "owner_id", "tenant_id", "workspace_id",
                )) != self._scope):
            return RecoveryObservationLab(
                "ORIGINAL_IDENTITY_CONFLICT_NO_SEND", signed["sequence"], True,
            )
        if signed.get("status") == "ENROLLED":
            # Even valid fresh enrollment after rollback says nothing about
            # what happened before the current ledger image was created.
            if (signed["sequence"] != 0
                    or signed.get("effect_digest") != ""
                    or signed.get("idempotency_key") != ""):
                return RecoveryObservationLab(
                    "INCONSISTENT_ENROLLMENT_NO_SEND",
                    signed["sequence"], True,
                )
            return RecoveryObservationLab(
                "UNSPENT_NOT_PROVEN_NO_SEND", None, True,
            )
        if signed.get("status") == "RESERVED":
            if (signed["sequence"] < 1
                    or signed.get("effect_digest") != self._effect
                    or signed.get("idempotency_key") != self._request_id):
                return RecoveryObservationLab(
                    "RESERVATION_IDENTITY_CONFLICT_NO_SEND",
                    signed["sequence"], True,
                )
            # Reservation means INTENT SPENT, not a provider delivery receipt.
            return RecoveryObservationLab(
                "RESERVATION_PRESENT_PROVIDER_UNKNOWN",
                signed["sequence"], True,
            )
        return RecoveryObservationLab(
            "UNEXPECTED_SIGNED_STATUS_NO_SEND", signed["sequence"], True,
        )
