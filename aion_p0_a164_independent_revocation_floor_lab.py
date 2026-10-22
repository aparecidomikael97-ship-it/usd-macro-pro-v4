"""A164: read-only SYNTHETIC policy-revocation floor, ALWAYS HARD NO-GO.

Models TWO independently pre-pinned external *audit role identifiers* signing
the latest A163 policy generation/digest/revoked status for a fresh challenge.
If an out-of-band-preserved signed floor is newer than locally restored
policy+anchor, the rollback is detected. BOTH auditor keys, challenge and time
remain caller-controlled synthetic bytes: no real independence, freshness,
revocation propagation, trusted clock, owner identity, or custody is attested.

All results are BLOCK or QUARANTINE, never GO. No disk writes, network, Worker,
real issuer enrollment, provider effect, restored checkpoint or approval.
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

from aion_p0_a163_custody_enrollment_revocation_lab import (
    PolicyAnchor, CustodyRejected, validate_policy_chain,
    assess_enrollment_and_recovery,
)

SCHEMA="AION_P0_A164_REVOKE_FLOOR_CUSTODY_SIMULATION_NO_GO_V1"
DOMAIN=b"AION-P0-A164-REVOCATION-POLICY-HEAD-v1\x00"
AUDIENCE="AION-H0-REVOCATION-FLOOR-READONLY-LAB"
HEX32=re.compile(r"[0-9a-f]{32}\Z")
HEX64=re.compile(r"[0-9a-f]{64}\Z")
IDENT=re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
MAX_NS=2**63-1
MAX_WINDOW_NS=20_000_000_000


class RevocationFloorRejected(ValueError):
    pass


@dataclass(frozen=True)
class RevocationFloor:
    ledger_id: str
    epoch: str
    generation: int
    chain_digest: str
    terminal_revoked: bool
    request_nonce: str
    audience: str
    observed_ns: int
    valid_until_ns: int


@dataclass(frozen=True)
class SignedRevocationFloor:
    floor: RevocationFloor
    role: str
    signature_b64: str


@dataclass(frozen=True)
class RevocationFloorReview:
    schema: str
    verdict: str
    reason: str
    two_synthetic_auditor_signatures_verified: bool = False
    local_policy_chain_verified: bool = False
    latest_external_generation_verified: bool = False
    actual_independent_auditor_administration_verified: bool = False
    actual_nonrollbackable_revocation_floor_verified: bool = False
    actual_owner_identity_and_consent_verified: bool = False
    actual_provider_effect_or_no_effect_verified: bool = False
    checkpoint_restore_allowed: bool = False
    external_execution_allowed: bool = False
    worker_allowed: bool = False
    automatic_retry_allowed: bool = False
    automatic_resend_allowed: bool = False
    homologated_p0_count: int = 0


def _id(text: Any, label: str):
    if type(text) is not str or IDENT.fullmatch(text) is None:
        raise RevocationFloorRejected("invalid_"+label)


def _hex(value: Any, pattern: re.Pattern[str], label: str):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise RevocationFloorRejected("invalid_"+label)


def _uint(value: Any, label: str, lower: int = 1):
    if type(value) is not int or not lower <= value <= MAX_NS:
        raise RevocationFloorRejected("invalid_"+label)


def _key(value: Any, label: str) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise RevocationFloorRejected("invalid_"+label)
    try:
        Ed25519PublicKey.from_public_bytes(value)
    except ValueError as exc:
        raise RevocationFloorRejected("invalid_"+label) from exc
    return value


def canonical_revocation_floor_bytes(floor: RevocationFloor) -> bytes:
    if type(floor) is not RevocationFloor:
        raise RevocationFloorRejected("invalid_revocation_floor_type")
    _id(floor.ledger_id,"ledger")
    _hex(floor.epoch,HEX32,"epoch")
    _uint(floor.generation,"generation")
    _hex(floor.chain_digest,HEX64,"chain_digest")
    if type(floor.terminal_revoked) is not bool:
        raise RevocationFloorRejected("revocation_state_must_be_boolean")
    _hex(floor.request_nonce,HEX32,"challenge_nonce")
    if type(floor.audience) is not str or floor.audience != AUDIENCE:
        raise RevocationFloorRejected("readonly_audience_required")
    _uint(floor.observed_ns,"observation_time")
    _uint(floor.valid_until_ns,"expiry_time")
    if (floor.valid_until_ns <= floor.observed_ns
            or floor.valid_until_ns - floor.observed_ns > MAX_WINDOW_NS):
        raise RevocationFloorRejected("invalid_bounded_freshness_window")
    fields={name:getattr(floor,name) for name in RevocationFloor.__dataclass_fields__}
    return DOMAIN + json.dumps(
        fields,sort_keys=True,separators=(",",":"),ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _verify(role: str, signed: Any, key: bytes) -> RevocationFloor:
    if type(signed) is not SignedRevocationFloor or type(signed.role) is not str or signed.role != role:
        raise RevocationFloorRejected("auditor_role_mismatch")
    if type(signed.signature_b64) is not str or not signed.signature_b64:
        raise RevocationFloorRejected("required_auditor_signature_missing")
    try:
        raw=base64.b64decode(signed.signature_b64,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise RevocationFloorRejected("auditor_signature_bad_base64") from exc
    if len(raw)!=64 or base64.b64encode(raw).decode("ascii")!=signed.signature_b64:
        raise RevocationFloorRejected("auditor_signature_noncanonical")
    msg=canonical_revocation_floor_bytes(signed.floor)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(raw,msg)
    except (InvalidSignature,ValueError) as exc:
        raise RevocationFloorRejected("auditor_signature_invalid") from exc
    return signed.floor


def verify_signed_revocation_floor(
    *, signed_r1: SignedRevocationFloor,
    signed_r2: SignedRevocationFloor,
    pinned_auditor_keys: dict[str,bytes],
    challenge_nonce: str, expected_ledger: str,
    expected_epoch: str, now_ns: int,
) -> RevocationFloor:
    """Cryptographic checking only; NO proof of remote or current custody."""
    _id(expected_ledger,"expected_ledger")
    _hex(expected_epoch,HEX32,"expected_epoch")
    _hex(challenge_nonce,HEX32,"expected_challenge_nonce")
    _uint(now_ns,"observed_request_time")
    if type(pinned_auditor_keys) is not dict or set(pinned_auditor_keys)!={"r1","r2"}:
        raise RevocationFloorRejected("exact_two_out_of_band_auditor_pins_required")
    k1=_key(pinned_auditor_keys["r1"],"r1_key")
    k2=_key(pinned_auditor_keys["r2"],"r2_key")
    if hmac.compare_digest(k1,k2):
        raise RevocationFloorRejected("auditor_key_reuse")
    f1=_verify("r1",signed_r1,k1)
    f2=_verify("r2",signed_r2,k2)
    if f1!=f2:
        raise RevocationFloorRejected("two_auditors_disagree_on_policy_floor")
    if f1.ledger_id!=expected_ledger or f1.epoch!=expected_epoch:
        raise RevocationFloorRejected("signed_floor_ledger_epoch_mismatch")
    if not hmac.compare_digest(f1.request_nonce,challenge_nonce):
        raise RevocationFloorRejected("replayed_or_wrong_challenge_nonce")
    if now_ns < f1.observed_ns:
        raise RevocationFloorRejected("signed_floor_observation_in_future")
    if now_ns >= f1.valid_until_ns:
        raise RevocationFloorRejected("signed_floor_expired")
    return f1


def _review(reason: str, *, valid=False, chain=False, quarantine=False) -> RevocationFloorReview:
    return RevocationFloorReview(
        schema=SCHEMA,
        verdict="LAB_QUARANTINE_MANUAL_REVIEW" if quarantine else "LAB_HARD_BLOCKED",
        reason=reason,
        two_synthetic_auditor_signatures_verified=valid,
        local_policy_chain_verified=chain,
    )


def assess_external_revocation_floor(
    *, signed_events: Any,
    trusted_issuer_public_key: bytes,
    local_anchor: PolicyAnchor,
    signed_r1: SignedRevocationFloor,
    signed_r2: SignedRevocationFloor,
    pinned_auditor_keys: dict[str,bytes],
    challenge_nonce: str, ledger_id: str,
    epoch: str, now_ns: int,
    # Optional full H0 read-only integration - presence REQUIRED on current match
    journal: Any, local_witness: Any, checkpoint: Any,
    checkpoint_pins: Any, floor_d1: Any, floor_d2: Any,
    request_nonce: str,
) -> RevocationFloorReview:
    """Latest policy floor before A163/A162 H0, always blocked/quarantined.

    A newer TWO-signed revocation floor blocks the rollback of BOTH
    locally-held policy chain and locally-held PolicyAnchor. This requires
    that the auditors' latest floor actually survived independently; the
    local synthetic process cannot establish this crucial premise.
    """
    try:
        state=validate_policy_chain(
            signed_events=signed_events,
            trusted_issuer_public_key=trusted_issuer_public_key,
            required_anchor=local_anchor,
            ledger_id=ledger_id,
            epoch=epoch,
        )
        if type(pinned_auditor_keys) is not dict:
            raise RevocationFloorRejected("auditor_pins_missing")
        # Five key domains in play: policy issuer, local D1/D2, R1/R2;
        # distinct bytes are NOT distinct administrators.
        issuer=_key(trusted_issuer_public_key,"issuer_key")
        active_keys=[issuer]
        if not state.terminal_revoked:
            active_keys.extend((_key(state.d1_key,"d1_key"),_key(state.d2_key,"d2_key")))
        if set(pinned_auditor_keys)=={"r1","r2"}:
            audit1=_key(pinned_auditor_keys["r1"],"r1_key")
            audit2=_key(pinned_auditor_keys["r2"],"r2_key")
            if any(k in active_keys for k in (audit1,audit2)):
                raise RevocationFloorRejected("auditor_key_reuses_policy_signer")
            # Also refuse key reuse from *retired* roles in the supplied
            # authentic chain. This is an independence hygiene check only.
            for record in signed_events:
                for public_hex in (
                    record.event.d1_public_hex,record.event.d2_public_hex,
                ):
                    if public_hex and bytes.fromhex(public_hex) in (audit1,audit2):
                        raise RevocationFloorRejected("auditor_key_was_retired_policy_key")
        signed=verify_signed_revocation_floor(
            signed_r1=signed_r1,signed_r2=signed_r2,
            pinned_auditor_keys=pinned_auditor_keys,
            challenge_nonce=challenge_nonce,
            expected_ledger=ledger_id,expected_epoch=epoch,
            now_ns=now_ns,
        )
        if state.generation < signed.generation:
            return _review("local_policy_and_anchor_rolled_back_below_signed_floor",
                           valid=True,chain=True)
        if state.generation > signed.generation:
            return _review("unwitnessed_policy_generation_ahead_of_signed_floor",
                           valid=True,chain=True)
        if not hmac.compare_digest(state.chain_digest,signed.chain_digest):
            return _review("equal_generation_chain_digest_fork",
                           valid=True,chain=True)
        if state.terminal_revoked!=signed.terminal_revoked:
            return _review("signed_revocation_state_disagreement",
                           valid=True,chain=True)
        if state.terminal_revoked:
            return _review("terminal_revocation_signed_by_two_auditors",
                           valid=True,chain=True)

        result=assess_enrollment_and_recovery(
            signed_events=signed_events,
            trusted_issuer_public_key=trusted_issuer_public_key,
            required_anchor=local_anchor,
            ledger_id=ledger_id,epoch=epoch,
            journal=journal,local_witness=local_witness,
            checkpoint=checkpoint,checkpoint_pins=checkpoint_pins,
            floor_d1=floor_d1,floor_d2=floor_d2,
            request_nonce=request_nonce,now_ns=now_ns,
        )
        if result.verdict!="LAB_QUARANTINE_MANUAL_REVIEW":
            return _review("a163_issuer_or_h0_rejected:"+result.reason,
                           valid=True,chain=True)
        return _review(
            "current_synthetic_policy_mathematically_consistent_only",
            valid=True,chain=True,quarantine=True,
        )
    except (RevocationFloorRejected,CustodyRejected,ValueError) as exc:
        return _review(str(exc))
    except Exception:
        return _review("unexpected_external_policy_floor_validation_failure")
