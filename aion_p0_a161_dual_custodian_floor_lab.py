"""A161: read-only dual-custodian signed floor, SYNTHETIC LAB / HARD NO-GO.

Purpose: expose the difference between an old joint-rollback snapshot and an
OUT-OF-BAND independently preserved high-water. Two independent Ed25519
signatures on a nonce-bound floor detect a locally stale head *only if*
their authorities actually retained the newer floor in a trust domain the
local attacker cannot roll back. This LAB does NOT provide such custody.

Both keys, challenge, timestamps, policy and head are caller-supplied test
material. Verification establishes cryptographic signatures under pins but
NEVER proves that D1/D2 are independently operated, their floor is current,
their clocks are trusted, or a supplier effect occurred. In particular an
attacker controlling BOTH synthetic signers can sign an old floor using a
fresh nonce: co-rollback is undetectable. There is NO GO output or API.
No networking, provider, Worker, automatic resend, mutable database or money.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hmac
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SCHEMA = "AION_P0_A161_SYNTHETIC_DUAL_CUSTODIAN_FLOOR_NO_GO_V1"
DOMAIN = b"AION-P0-A161-DOUBLE-CUSTODIAN-FLOOR-LAB-v1\x00"
AUDIENCE = "AION-H0-RECOVERY-READONLY-LAB"
MAX_WINDOW_NS = 30 * 1_000_000_000
MAX_CLOCK_NS = 2**63 - 1
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class FloorRejected(ValueError):
    """Conservative boundary for malformed, forged, stale or ambiguous claims."""


@dataclass(frozen=True)
class HeadSnapshot:
    ledger_id: str
    epoch: str
    sequence: int
    history_digest: str


@dataclass(frozen=True)
class FloorClaim:
    ledger_id: str
    epoch: str
    sequence: int
    history_digest: str
    request_nonce: str
    audience: str
    observed_ns: int
    valid_until_ns: int


@dataclass(frozen=True)
class SignedFloor:
    claim: FloorClaim
    custodian_id: str
    signature_b64: str


@dataclass(frozen=True)
class FloorReview:
    schema: str
    verdict: str
    reason: str
    cryptographic_pair_valid_in_lab: bool = False
    externally_independent_custodians_verified: bool = False
    nonrollbackable_external_floor_proven: bool = False
    owner_identity_verified: bool = False
    real_provider_effect_proven: bool = False
    checkpoint_restoration_authorized: bool = False
    external_execution_allowed: bool = False
    worker_allowed: bool = False
    automatic_resend_allowed: bool = False
    homologated_p0_count: int = 0


def _validate_id(s: Any) -> None:
    if type(s) is not str or _SAFE_ID.fullmatch(s) is None:
        raise FloorRejected("invalid_ledger_identity")


def _hex(s: Any, pattern: re.Pattern, reason: str) -> None:
    if type(s) is not str or pattern.fullmatch(s) is None:
        raise FloorRejected(reason)


def _validate_sequence(value: Any) -> None:
    if type(value) is not int or value < 0 or value > MAX_CLOCK_NS:
        raise FloorRejected("invalid_monotonic_sequence")


def _validate_clock(value: Any) -> None:
    if type(value) is not int or not 1 <= value <= MAX_CLOCK_NS:
        raise FloorRejected("invalid_synthetic_clock")


def _validate_head(head: Any) -> HeadSnapshot:
    if type(head) is not HeadSnapshot:
        raise FloorRejected("head_snapshot_missing_or_wrong_type")
    _validate_id(head.ledger_id)
    _hex(head.epoch, _HEX32, "invalid_head_epoch")
    _validate_sequence(head.sequence)
    _hex(head.history_digest, _HEX64, "invalid_head_digest")
    return head


def _validate_claim(claim: Any) -> FloorClaim:
    if type(claim) is not FloorClaim:
        raise FloorRejected("floor_claim_missing_or_wrong_type")
    _validate_id(claim.ledger_id)
    _hex(claim.epoch, _HEX32, "invalid_floor_epoch")
    _validate_sequence(claim.sequence)
    _hex(claim.history_digest, _HEX64, "invalid_floor_digest")
    _hex(claim.request_nonce, _HEX32, "invalid_nonce")
    if claim.audience != AUDIENCE or type(claim.audience) is not str:
        raise FloorRejected("invalid_audience")
    _validate_clock(claim.observed_ns)
    _validate_clock(claim.valid_until_ns)
    if (claim.valid_until_ns <= claim.observed_ns
            or claim.valid_until_ns - claim.observed_ns > MAX_WINDOW_NS):
        raise FloorRejected("invalid_signed_freshness_window")
    return claim


def canonical_claim_bytes(claim: FloorClaim) -> bytes:
    """Domain-separated exact encoding, no caller-supplied trust keys."""
    _validate_claim(claim)
    obj = {k: getattr(claim, k) for k in FloorClaim.__dataclass_fields__}
    return DOMAIN + json.dumps(
        obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pins(pinned_custodian_keys: Any) -> dict[str, bytes]:
    # The keys must come from an OUT-OF-BAND trust policy in production.
    # Passing the correct bytes from a test is not proof of out-of-band origin.
    if type(pinned_custodian_keys) is not dict or set(pinned_custodian_keys) != {"d1", "d2"}:
        raise FloorRejected("exact_two_pre_pinned_custodians_required")
    keys = pinned_custodian_keys
    if any(type(keys[k]) is not bytes or len(keys[k]) != 32 for k in ("d1", "d2")):
        raise FloorRejected("invalid_pinned_key")
    if hmac.compare_digest(keys["d1"], keys["d2"]):
        raise FloorRejected("custodian_key_reuse")
    for k in ("d1", "d2"):
        try:
            Ed25519PublicKey.from_public_bytes(keys[k])
        except ValueError as exc:
            raise FloorRejected("invalid_ed25519_public_key") from exc
    return keys


def _verify_one(envelope: Any, *, role: str, key: bytes) -> FloorClaim:
    if type(envelope) is not SignedFloor:
        raise FloorRejected("missing_signed_floor")
    if envelope.custodian_id != role or type(envelope.custodian_id) is not str:
        raise FloorRejected("wrong_custodian_role")
    if type(envelope.signature_b64) is not str:
        raise FloorRejected("invalid_signature_encoding")
    try:
        signature = base64.b64decode(envelope.signature_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise FloorRejected("invalid_signature_encoding") from exc
    if len(signature) != 64:
        raise FloorRejected("invalid_ed25519_signature_length")
    blob = canonical_claim_bytes(envelope.claim)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature, blob)
    except (InvalidSignature, ValueError) as exc:
        raise FloorRejected("custodian_signature_mismatch") from exc
    return envelope.claim


def verify_dual_floor(
    *, d1: SignedFloor, d2: SignedFloor,
    pinned_custodian_keys: dict[str, bytes],
    request_nonce: str, expected_ledger_id: str,
    expected_epoch: str, now_ns: int,
) -> FloorClaim:
    """Checks local math and nonce context, NOT external operator independence."""
    _validate_id(expected_ledger_id)
    _hex(expected_epoch, _HEX32, "invalid_expected_epoch")
    _hex(request_nonce, _HEX32, "invalid_expected_nonce")
    _validate_clock(now_ns)
    pins = _pins(pinned_custodian_keys)
    first = _verify_one(d1, role="d1", key=pins["d1"])
    second = _verify_one(d2, role="d2", key=pins["d2"])
    if first != second:
        raise FloorRejected("two_custodian_claims_disagree")
    if (first.ledger_id != expected_ledger_id
            or first.epoch != expected_epoch):
        raise FloorRejected("floor_identity_or_epoch_mismatch")
    if not hmac.compare_digest(first.request_nonce, request_nonce):
        raise FloorRejected("stale_or_replayed_request_nonce")
    if now_ns < first.observed_ns:
        raise FloorRejected("untrusted_future_observation")
    if now_ns >= first.valid_until_ns:
        raise FloorRejected("floor_attestation_expired")
    return first


def assess_restart_dual_floor(
    *, local_head: HeadSnapshot, d1: SignedFloor, d2: SignedFloor,
    pinned_custodian_keys: dict[str, bytes], request_nonce: str,
    expected_ledger_id: str, expected_epoch: str, now_ns: int,
) -> FloorReview:
    """Read-only evidence comparison, ALWAYS blocked or quarantined, NEVER GO."""
    try:
        head = _validate_head(local_head)
        if head.ledger_id != expected_ledger_id or head.epoch != expected_epoch:
            raise FloorRejected("local_head_identity_or_epoch_mismatch")
        floor = verify_dual_floor(
            d1=d1, d2=d2, pinned_custodian_keys=pinned_custodian_keys,
            request_nonce=request_nonce, expected_ledger_id=expected_ledger_id,
            expected_epoch=expected_epoch, now_ns=now_ns,
        )
        if head.sequence < floor.sequence:
            reason = "local_rollback_below_signed_floor"
            status = "LAB_HARD_BLOCKED"
        elif head.sequence > floor.sequence:
            reason = "unwitnessed_local_advance_unknown"
            status = "LAB_HARD_BLOCKED"
        elif not hmac.compare_digest(head.history_digest, floor.history_digest):
            reason = "same_sequence_digest_disagreement"
            status = "LAB_HARD_BLOCKED"
        else:
            reason = "synthetic_pair_matches_but_independent_custody_unproven"
            status = "LAB_QUARANTINE_MANUAL_REVIEW"
        return FloorReview(
            SCHEMA, status, reason,
            cryptographic_pair_valid_in_lab=True,
        )
    except FloorRejected as exc:
        return FloorReview(SCHEMA, "LAB_HARD_BLOCKED", str(exc))
    except Exception:
        # Never let a callback, malformed container, or crypto library
        # exception elevate trust or produce a permissive output.
        return FloorReview(SCHEMA, "LAB_HARD_BLOCKED", "unexpected_validation_failure")


def a150_read_only_head_snapshot(engine: Any) -> HeadSnapshot:
    """Adapter for A150's read-only head. Does NOT attest engine custody."""
    try:
        meta = engine.read_head()
        if type(meta) is not dict:
            raise FloorRejected("a150_head_not_mapping")
        record = HeadSnapshot(
            ledger_id=meta["ledger_id"], epoch=meta["epoch"],
            sequence=meta["sequence"], history_digest=meta["digest"],
        )
        return _validate_head(record)
    except FloorRejected:
        raise
    except Exception as exc:
        raise FloorRejected("a150_head_read_unavailable") from exc
