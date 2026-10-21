"""AION P0 H0 LAB: synthetic provider outcome + snapshot over five witness envelopes.

SEVEN locally generated signed documents are only a mathematical consistency
experiment. Provider keys and minima are CALLER-SUPPLIED, not enrolled or
independent. A signed claim of COMMITTED_EFFECT or NO_EFFECT_FENCED can never
become an authenticated outcome, terminal outbox state or permission to retry.
No network, provider, storage, dispatch, Worker or external authorization.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

import atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab as reg
import atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab as wit
import atlasquant_aion_p0_h0_linked_five_envelopes_lab as five

SCHEMA = "AION_P0_H0_SEVEN_SIGNED_PROVIDER_RECEIPT_LAB_V1"
PROVIDER_RECEIPT_SCHEMA = "AION_P0_H0_PROVIDER_CAUSAL_RECEIPT_LAB_V1"
PROVIDER_HEAD_SCHEMA = "AION_P0_H0_PROVIDER_HEAD_READBACK_LAB_V1"
RECEIPT_FIELDS = frozenset((
    "schema", "kind", "provider_id", "key_id", "scope_digest",
    "request_id", "intent_id", "attempt_nonce", "operation_id",
    "idempotency_ref", "reservation_sha256", "readback_sha256",
    "challenge_sha256", "provider_epoch", "provider_sequence",
    "provider_head_digest", "issued_at_utc", "effect_applied",
    "fence_applied", "fence_cutoff_sequence", "future_dispatch_forbidden",
))
HEAD_FIELDS = frozenset((
    "schema", "provider_id", "key_id", "scope_digest", "request_id",
    "intent_id", "attempt_nonce", "operation_id", "provider_epoch",
    "provider_sequence", "provider_head_digest", "receipt_sha256",
    "observed_at_utc",
))
PINS_FIELDS = frozenset((
    "provider_public_key_b64url", "provider_head_public_key_b64url",
    "provider_key_id", "provider_head_key_id", "provider_id",
    "operation_id", "idempotency_ref", "minimum_provider_epoch",
    "minimum_provider_sequence", "expected_provider_head_digest",
))
STATUSES = frozenset(("COMMITTED_EFFECT", "NO_EFFECT_FENCED", "UNKNOWN"))
AUTHORITY_FALSE = {
    "provider_identity_enrolled_independently": False,
    "provider_keys_managed_independently": False,
    "provider_latest_head_authenticated": False,
    "provider_receipt_origin_authenticated": False,
    "provider_no_effect_fence_authenticated": False,
    "provider_committed_effect_authenticated": False,
    "provider_idempotency_enforced": False,
    "provider_complete_history_authenticated": False,
    "provider_rollback_ruled_out": False,
    "external_nonce_atomically_consumed": False,
    "issuer_enrollment_independent": False,
    "human_owner_authenticated": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "outbox_terminal_transition_allowed": False,
    "external_action_executed": False,
}
BLOCKERS = (
    "SYNTHETIC_CALLER_PINNED_PROVIDER_KEYS",
    "PROVIDER_ADMIN_AND_KEY_ENROLLMENT_NOT_INDEPENDENT",
    "PROVIDER_CURRENT_LATEST_STATE_NOT_AUTHENTICATED",
    "PROVIDER_RECEIPT_ORIGIN_NOT_TRUSTED",
    "REAL_PROVIDER_FENCE_AND_IDEMPOTENCY_UNPROVEN",
    "CUSTODY_NONCE_NOT_CONSUMED_OUTSIDE_EXECUTOR",
    "UNKNOWN_EFFECT_MUST_NOT_AUTO_RESEND",
    "HUMAN_OWNER_NOT_AUTHENTICATED",
    "PHYSICAL_ROLLBACK_NOT_RULED_OUT",
    "CANONICAL_QUALITY_REMAINS_RED",
)


def _receipt_valid(obj: Any) -> bool:
    if not reg._plain(obj, RECEIPT_FIELDS):
        return False
    if (type(obj["schema"]) is not str or obj["schema"] != PROVIDER_RECEIPT_SCHEMA
            or type(obj["kind"]) is not str or obj["kind"] not in STATUSES):
        return False
    if not all(reg._ident(obj[k]) for k in (
        "provider_id", "key_id", "request_id", "intent_id",
        "attempt_nonce", "operation_id", "idempotency_ref",
    )):
        return False
    if not all(reg._hex(obj[k]) for k in (
        "scope_digest", "reservation_sha256", "readback_sha256",
        "challenge_sha256", "provider_head_digest",
    )):
        return False
    if (not reg._pos(obj["provider_epoch"])
            or not reg._pos(obj["provider_sequence"])
            or reg._date(obj["issued_at_utc"]) is None):
        return False
    for k in ("effect_applied", "fence_applied", "future_dispatch_forbidden"):
        if type(obj[k]) is not bool:
            return False
    cutoff = obj["fence_cutoff_sequence"]
    if type(cutoff) is not int or not 0 <= cutoff < 2**63-1:
        return False
    kind = obj["kind"]
    if kind == "COMMITTED_EFFECT":
        expected = (True, False, 0, True)
    elif kind == "NO_EFFECT_FENCED":
        if cutoff < obj["provider_sequence"]:
            return False
        expected = (False, True, cutoff, True)
    else:
        expected = (False, False, 0, False)
    actual = (
        obj["effect_applied"], obj["fence_applied"],
        cutoff, obj["future_dispatch_forbidden"],
    )
    return actual == expected and len(reg.canonical_bytes(obj)) <= 4096


def _head_valid(obj: Any) -> bool:
    return (
        reg._plain(obj, HEAD_FIELDS)
        and type(obj["schema"]) is str
        and obj["schema"] == PROVIDER_HEAD_SCHEMA
        and all(reg._ident(obj[k]) for k in (
            "provider_id", "key_id", "request_id", "intent_id",
            "attempt_nonce", "operation_id",
        ))
        and all(reg._hex(obj[k]) for k in (
            "scope_digest", "provider_head_digest", "receipt_sha256",
        ))
        and reg._pos(obj["provider_epoch"])
        and reg._pos(obj["provider_sequence"])
        and reg._date(obj["observed_at_utc"]) is not None
        and len(reg.canonical_bytes(obj)) <= 4096
    )


def _result(findings: set[str], *, five_ok: bool = False,
            receipt_ok: bool = False, head_ok: bool = False,
            claimed_outcome: str = "UNVERIFIED") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "HARD_NO_GO",
        "allowed": False,
        "simulation_only": True,
        "reconciliation_state": "UNKNOWN_BLOCKED",
        "synthetic_five_envelopes_consistent_lab": five_ok,
        "synthetic_provider_receipt_signature_valid_lab": receipt_ok,
        "synthetic_provider_head_signature_valid_lab": head_ok,
        "synthetic_seven_envelopes_linked_lab": (
            five_ok and receipt_ok and head_ok and not findings
        ),
        "claimed_provider_outcome_lab_only": claimed_outcome,
        "findings": tuple(sorted(findings)),
        "blockers": BLOCKERS,
        **AUTHORITY_FALSE,
    }


def inspect_seven_signed_provider_lab(
    enrollment: Any, revocation: Any, challenge: Any,
    reservation: Any, readback: Any,
    provider_receipt: Any, provider_head: Any,
    caller_registry_pins: Any, caller_expectations: Any,
    caller_provider_pins: Any, *, now_utc: Any,
) -> dict[str, Any]:
    """Signed packet coherence only; no terminal state or outbound operation."""
    if not reg._plain(caller_provider_pins, PINS_FIELDS):
        return _result({"PROVIDER_PINS_SHAPE_INVALID"})
    p = caller_provider_pins
    if not all(reg._ident(p[k]) for k in (
        "provider_key_id", "provider_head_key_id", "provider_id",
        "operation_id", "idempotency_ref",
    )):
        return _result({"PROVIDER_PINS_IDENTIFIER_INVALID"})
    if not all(reg._pos(p[k]) for k in (
        "minimum_provider_epoch", "minimum_provider_sequence",
    )) or not reg._hex(p["expected_provider_head_digest"]):
        return _result({"PROVIDER_PINS_COUNTER_OR_HASH_INVALID"})
    provider_key = reg._raw_b64(p["provider_public_key_b64url"], 32)
    head_key = reg._raw_b64(p["provider_head_public_key_b64url"], 32)
    if provider_key is None or head_key is None:
        return _result({"PROVIDER_PINS_KEY_ENCODING_INVALID"})
    if provider_key == head_key or p["provider_key_id"] == p["provider_head_key_id"]:
        return _result({"PROVIDER_KEYS_NOT_SEPARATED"})
    now = reg._date(now_utc)
    if now is None:
        return _result({"CALLER_CLOCK_INVALID"})

    upstream = five.inspect_linked_five_envelopes_lab(
        enrollment, revocation, challenge, reservation, readback,
        caller_registry_pins, caller_expectations, now_utc=now_utc,
    )
    if not upstream["synthetic_five_envelopes_linked_lab"]:
        return _result(
            {"FIVE:" + f for f in upstream["findings"]}
            or {"FIVE_INVALID_OR_INCOMPLETE"}
        )

    # Distinct public-key BYTES are required, but still cannot establish
    # distinct independent owners/administrators of these keys.
    enroll = enrollment["payload"]
    role_keys = [role["public_key_b64url"] for role in enroll["roles"]]
    test_keys = (
        role_keys + [
            caller_registry_pins["registry_root_public_key_b64url"],
            caller_registry_pins["custodian_public_key_b64url"],
            p["provider_public_key_b64url"],
            p["provider_head_public_key_b64url"],
        ]
    )
    if len(set(test_keys)) != len(test_keys):
        return _result({"TEST_PROVIDER_OR_WITNESS_KEY_REUSED"}, five_ok=True)

    receipt, receipt_bytes, receipt_error = reg._envelope(
        provider_receipt, p["provider_public_key_b64url"], _receipt_valid,
    )
    head, _, head_error = reg._envelope(
        provider_head, p["provider_head_public_key_b64url"], _head_valid,
    )
    findings: set[str] = set()
    if receipt_error:
        findings.add("PROVIDER_RECEIPT_" + receipt_error)
    if head_error:
        findings.add("PROVIDER_HEAD_" + head_error)
    if findings or receipt is None or head is None or receipt_bytes is None:
        return _result(findings, five_ok=True)

    challenge_doc = challenge["payload"]
    reserve_doc = reservation["payload"]
    read_doc = readback["payload"]
    checks = (
        ("provider_id", p["provider_id"]),
        ("scope_digest", challenge_doc["scope_digest"]),
        ("request_id", challenge_doc["request_id"]),
        ("intent_id", challenge_doc["intent_id"]),
        ("attempt_nonce", reserve_doc["attempt_nonce"]),
        ("operation_id", p["operation_id"]),
    )
    for field, expected in checks:
        if receipt[field] != expected or head[field] != expected:
            findings.add("PROVIDER_WITNESS_BINDING_MISMATCH:" + field)
    if receipt["key_id"] != p["provider_key_id"] or head["key_id"] != p["provider_head_key_id"]:
        findings.add("PROVIDER_ROLE_KEY_ID_MISMATCH")
    if receipt["idempotency_ref"] != p["idempotency_ref"]:
        findings.add("PROVIDER_IDEMPOTENCY_BINDING_MISMATCH")
    for field, doc, encoder in (
        ("reservation_sha256", reserve_doc, wit.canonical_bytes),
        ("readback_sha256", read_doc, wit.canonical_bytes),
        ("challenge_sha256", challenge_doc, reg.canonical_bytes),
    ):
        if receipt[field] != hashlib.sha256(encoder(doc)).hexdigest():
            findings.add("PROVIDER_CAUSAL_HASH_MISMATCH:" + field)
    if head["receipt_sha256"] != hashlib.sha256(receipt_bytes).hexdigest():
        findings.add("PROVIDER_HEAD_NOT_BOUND_TO_RECEIPT")
    if receipt["provider_epoch"] != head["provider_epoch"]:
        findings.add("PROVIDER_EPOCH_DIVERGED")
    if receipt["provider_epoch"] < p["minimum_provider_epoch"]:
        findings.add("PROVIDER_EPOCH_BELOW_CALLER_MINIMUM")
    if receipt["provider_sequence"] != head["provider_sequence"]:
        findings.add("PROVIDER_HEAD_SEQUENCE_NOT_EXACT_RECEIPT")
    if receipt["provider_sequence"] < p["minimum_provider_sequence"]:
        findings.add("PROVIDER_SEQUENCE_BELOW_CALLER_MINIMUM")
    if (receipt["provider_head_digest"] != head["provider_head_digest"]
            or head["provider_head_digest"] != p["expected_provider_head_digest"]):
        findings.add("PROVIDER_HEAD_DIGEST_DIVERGED")

    # Caller time is NOT trusted and offers no real freshness. Issued receipt
    # must appear after signed witness readback and before signed provider
    # snapshot, with a bounded delay relative to the caller's clock.
    t_read = wit._date(read_doc["observed_at_utc"])
    t_receipt = reg._date(receipt["issued_at_utc"])
    t_head = reg._date(head["observed_at_utc"])
    if (t_read is None or t_receipt is None or t_head is None
            or not t_read <= t_receipt <= t_head <= now
            or t_head - t_receipt > timedelta(seconds=120)
            or now - t_head > timedelta(seconds=120)):
        findings.add("CALLER_PROVIDER_OBSERVATION_WINDOW_INVALID")

    return _result(
        findings, five_ok=True, receipt_ok=True, head_ok=True,
        claimed_outcome=receipt["kind"],
    )
