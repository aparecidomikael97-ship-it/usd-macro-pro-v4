"""G115 opt-in Outbox guard backed by a G114 public-only TEST witness.

This is a laboratory integration of a process-separated synthetic signed
event reservation with ExecutionOutbox.first_attempt_guard. The G114 public
client contains no signer key; the witness signing key and SQLite database
still exist under SAME-HOST test-harness control and may be restored.

Do not wire into production Worker or treat this as first-provider-SEND
certification, independently authenticated enrollment or external P0 custody.
"""
from copy import deepcopy
from hashlib import sha256
import sqlite3
from threading import Lock

from aion_chat.first_attempt_witness_lab import _effect_digest
from aion_chat.intent_binding_a182_lab import semantic_bytes
from labs.a190.g113_subprocess_witness_client_lab import WitnessProcessUnavailableLab
from labs.a190.g114_public_key_witness_client_lab import G114PublicKeyWitnessClientLab
from labs.a190.g120_synthetic_owner_enrollment_lab import verify_synthetic_owner_enrollment


class PublicOnlyWitnessOutboxGuardLab:
    """Fail-closed LAB callback: exact enrolled event -> reserve -> fresh status."""

    def __init__(self, *, witness_client, enrolled_event_id,
                 enrolled_original_sha256, original_decision,
                 minimum_sequence=0, owner_enrollment_receipt=None,
                 pinned_owner_enrollment_public_key=None, owner_approval_clock=None):
        # G115 previously trusted any object returning unsigned dictionaries,
        # allowing a fake duck-typed status/reserve object to release Outbox.
        # Require the exact opt-in G114 client implementation, which checks
        # Ed25519 signatures and challenge nonces before yielding payloads.
        # This is API hardening, NOT protection against privileged monkeypatch,
        # forged constructor pins, or same-host ledger rollback.
        if type(witness_client) is not G114PublicKeyWitnessClientLab:
            raise TypeError("G116_AUTHENTICATED_CLIENT_REQUIRED")
        if (not callable(getattr(witness_client, "reserve", None))
                or not callable(getattr(witness_client, "status", None))):
            raise TypeError("G116_SIGNED_CLIENT_METHODS_REQUIRED")
        if type(enrolled_event_id) is not str or len(enrolled_event_id) != 64:
            raise ValueError("G115_IMMUTABLE_EVENT_ID_REQUIRED")
        if type(minimum_sequence) is not int or minimum_sequence < 0:
            raise ValueError("G115_RETAINED_SEQUENCE_FLOOR_REQUIRED")
        self._original = semantic_bytes(original_decision)
        expected_hash = sha256(self._original).hexdigest()
        if (type(enrolled_original_sha256) is not str
                or enrolled_original_sha256 != expected_hash):
            raise ValueError("G115_ORIGINAL_DECISION_PIN_REQUIRED")
        # Require a second, separately signed owner enrollment for exactly
        # THIS original business event. A locally re-enrolled new event_id is
        # not approved merely because the witness signed it.
        # The signing key, pin and clock are SYNTHETIC HOST-OWNED fixtures,
        # not proof of actual HUMAN_OWNER authority.
        if not callable(owner_approval_clock):
            raise ValueError("G120_OWNER_ENROLLMENT_CLOCK_REQUIRED")
        verify_synthetic_owner_enrollment(
            owner_enrollment_receipt,
            pinned_public_key=pinned_owner_enrollment_public_key,
            expected_event_id=enrolled_event_id,
            original_decision=original_decision,
            now=owner_approval_clock(),
        )
        self._owner_approval_receipt = deepcopy(owner_enrollment_receipt)
        self._owner_approval_pin = pinned_owner_enrollment_public_key
        self._owner_clock = owner_approval_clock
        # These pins are supplied from a LAB fixture. A real trusted event
        # authority must enroll them outside both host and request context.
        self._event_id = enrolled_event_id
        self._original_hash = expected_hash
        self._original_effect = _effect_digest(original_decision)
        self._scope = tuple(
            original_decision[field] for field in
            ("owner_id", "tenant_id", "workspace_id")
        )
        if any(type(field) is not str or not field for field in self._scope):
            raise ValueError("G115_SCOPE_REQUIRED")
        self._client = witness_client
        self._minimum = minimum_sequence
        self._lock = Lock()

    def _same_source(self, signed, *, status):
        return (
            type(signed) is dict
            and signed.get("status") == status
            and signed.get("event_id") == self._event_id
            and signed.get("original_sha256") == self._original_hash
            and tuple(signed.get(k) for k in (
                "owner_id", "tenant_id", "workspace_id",
            )) == self._scope
            and type(signed.get("high_water")) is int
            and type(signed.get("count")) is int
            and signed["high_water"] == signed["count"]
            and signed["high_water"] >= self._minimum
        )

    def __call__(self, intent):
        # Lock is per Python object, NOT a multi-host/remote atomicity fence.
        with self._lock:
            try:
                if type(intent) is not dict or type(intent.get("decision")) is not dict:
                    return False
                decision = intent["decision"]
                if semantic_bytes(decision) != self._original:
                    return False
                # A previously valid synthetic approval MUST be checked
                # again at the moment of use; an expired one never lets the
                # Outbox attempt a first reservation.
                verify_synthetic_owner_enrollment(
                    self._owner_approval_receipt,
                    pinned_public_key=self._owner_approval_pin,
                    expected_event_id=self._event_id,
                    original_decision=decision,
                    now=self._owner_clock(),
                )
                request_id = intent.get("idempotency_key")
                if (type(request_id) is not str or len(request_id) != 64
                        or request_id != decision.get("idempotency_key")):
                    return False
                before = self._client.status(self._event_id)
                # A previously signed RESERVATION is a spent event, NEVER
                # permission to send; only previously enrolled original may
                # attempt its first reservation.
                if not self._same_source(before, status="ENROLLED"):
                    return False
                if (before.get("sequence") != 0
                        or before.get("effect_digest") != ""
                        or before.get("idempotency_key") != ""):
                    return False
                kwargs = dict(
                    event_id=self._event_id,
                    original_sha256=self._original_hash,
                    effect_digest=self._original_effect,
                    idempotency_key=request_id,
                    owner_id=self._scope[0],
                    tenant_id=self._scope[1],
                    workspace_id=self._scope[2],
                )
                first = self._client.reserve(**kwargs)
                if not self._same_source(first, status="RESERVED"):
                    return False
                if (type(first.get("sequence")) is not int
                        or first["sequence"] != before["high_water"] + 1
                        or first["high_water"] != first["sequence"]
                        or first.get("effect_digest") != self._original_effect
                        or first.get("idempotency_key") != request_id):
                    return False
                # This second status uses a different challenge and signed
                # response from a separate process, not a local echo.
                after = self._client.status(self._event_id)
                return (
                    self._same_source(after, status="RESERVED")
                    and after["sequence"] == first["sequence"]
                    and after["high_water"] == first["high_water"]
                    and after["effect_digest"] == self._original_effect
                    and after["idempotency_key"] == request_id
                )
            except (WitnessProcessUnavailableLab, KeyError, TypeError,
                    ValueError, RuntimeError, OSError, sqlite3.Error):
                # A failed preflight, lost reservation ACK or missing
                # postproof is DENY. The remote reservation may already have
                # COMMITTED: caller must not automatically resend.
                return False
