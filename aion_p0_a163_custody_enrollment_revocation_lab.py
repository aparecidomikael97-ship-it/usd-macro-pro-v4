"""A163: read-only key enrollment, rotation, terminal revocation (SYNTHETIC LAB).

The trust-root key, latest generation/digest anchor, issuer administration,
new-key possession, and prior-key retirement signatures are caller-supplied
offline-test materials. Cryptography proves signatures under bytes given by
the test, NOT the independent identities, custody or external irreversibility
of D1, D2, the owner or the issuer. Joint rollback of policy + trusted anchor
+ all signer keys is impossible to detect here. No network, disk writing,
secrets enrollment, provider calls, Worker, grants or production trust.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aion_p0_a162_three_source_recovery_lab import (
    SCHEMA as A162_SCHEMA, assess_three_source_restart,
)
from aion_p0_a161_dual_custodian_floor_lab import SignedFloor

SCHEMA="AION_P0_A163_SYNTHETIC_CUSTODY_POLICY_NO_GO_V1"
POLICY_DOMAIN=b"AION-P0-A163-CUSTODY-POLICY-v1\x00"
POP_DOMAIN=b"AION-P0-A163-KEY-ENROLL-POP-v1\x00"
RETIRE_DOMAIN=b"AION-P0-A163-KEY-RETIRE-ACK-v1\x00"
CHAIN_DOMAIN=b"AION-P0-A163-SIGNED-POLICY-CHAIN-v1\x00"
_ID=re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_HEX32=re.compile(r"[0-9a-f]{32}\Z")
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_MAX_EVENTS=32
_ZERO_DIGEST="0"*64
_MAX_INT=2**63-1


class CustodyRejected(ValueError):
    """Explicit closed outcome; never silently enroll/rotate or rebootstrap."""


@dataclass(frozen=True)
class PolicyEvent:
    ledger_id: str
    epoch: str
    generation: int
    action: str
    previous_digest: str
    d1_public_hex: str
    d2_public_hex: str
    request_nonce: str
    issued_ns: int


@dataclass(frozen=True)
class SignedPolicyEvent:
    event: PolicyEvent
    issuer_signature_b64: str
    d1_pop_b64: str = ""
    d2_pop_b64: str = ""
    old_d1_retire_b64: str = ""
    old_d2_retire_b64: str = ""


@dataclass(frozen=True)
class PolicyAnchor:
    ledger_id: str
    epoch: str
    generation: int
    chain_digest: str


@dataclass(frozen=True)
class VerifiedPolicyLAB:
    ledger_id: str
    epoch: str
    generation: int
    chain_digest: str
    terminal_revoked: bool
    d1_key: bytes
    d2_key: bytes


@dataclass(frozen=True)
class CustodyReview:
    schema: str
    verdict: str
    reason: str
    synthetic_policy_signatures_valid: bool = False
    generation_checked_against_caller_anchor: bool = False
    mathematical_three_source_match: bool = False
    actual_independent_issuer_custody_verified: bool = False
    actual_independent_d1_d2_administrators_verified: bool = False
    out_of_band_irreversible_anchor_verified: bool = False
    owner_consent_verified: bool = False
    provider_effect_or_no_effect_verified: bool = False
    live_enrollment_performed: bool = False
    checkpoint_restore_allowed: bool = False
    worker_allowed: bool = False
    external_execution_allowed: bool = False
    automatic_retry_allowed: bool = False
    automatic_resend_allowed: bool = False
    homologated_p0_count: int = 0


def _validate_id(x: Any, label: str) -> None:
    if type(x) is not str or _ID.fullmatch(x) is None:
        raise CustodyRejected("invalid_"+label)


def _validate_hex(x: Any, pattern: re.Pattern[str], label: str) -> None:
    if type(x) is not str or pattern.fullmatch(x) is None:
        raise CustodyRejected("invalid_"+label)


def _uint(x: Any, label: str, *, minimum: int = 1) -> None:
    if type(x) is not int or not minimum <= x <= _MAX_INT:
        raise CustodyRejected("invalid_"+label)


def _public(x: Any, label: str) -> bytes:
    if type(x) is not bytes or len(x) != 32:
        raise CustodyRejected("invalid_"+label)
    try:
        Ed25519PublicKey.from_public_bytes(x)
    except ValueError as exc:
        raise CustodyRejected("invalid_"+label) from exc
    return x


def _signature(value: Any, *, allow_empty: bool = False) -> bytes | None:
    if allow_empty and value == "" and type(value) is str:
        return None
    if type(value) is not str:
        raise CustodyRejected("signature_encoding_invalid")
    try:
        decoded=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise CustodyRejected("signature_encoding_invalid") from exc
    if len(decoded)!=64 or base64.b64encode(decoded).decode("ascii")!=value:
        raise CustodyRejected("signature_length_or_canonical_encoding_invalid")
    return decoded


def _verify(pub: bytes, payload: bytes, signature: Any, label: str) -> None:
    # Missing critical consent/proof MUST be distinguishable from corrupt
    # base64 while remaining an unconditional fail-closed denial.
    if type(signature) is not str or not signature:
        raise CustodyRejected(label+"_signature_missing")
    sig=_signature(signature)
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig,payload)
    except (ValueError,InvalidSignature) as exc:
        raise CustodyRejected(label+"_signature_invalid") from exc


def canonical_policy_bytes(event: PolicyEvent) -> bytes:
    if type(event) is not PolicyEvent:
        raise CustodyRejected("invalid_policy_event")
    _validate_id(event.ledger_id,"ledger")
    _validate_hex(event.epoch,_HEX32,"epoch")
    _uint(event.generation,"generation")
    if event.action not in ("ENROLL","ROTATE","REVOKE_ALL") or type(event.action) is not str:
        raise CustodyRejected("unknown_policy_action")
    _validate_hex(event.previous_digest,_HEX64,"previous_digest")
    _validate_hex(event.request_nonce,_HEX32,"request_nonce")
    _uint(event.issued_ns,"issued_ns")
    if event.action == "REVOKE_ALL":
        if type(event.d1_public_hex) is not str or event.d1_public_hex:
            raise CustodyRejected("revoke_must_remove_d1")
        if type(event.d2_public_hex) is not str or event.d2_public_hex:
            raise CustodyRejected("revoke_must_remove_d2")
    else:
        _validate_hex(event.d1_public_hex,_HEX64,"d1_key")
        _validate_hex(event.d2_public_hex,_HEX64,"d2_key")
    fields={f:getattr(event,f) for f in PolicyEvent.__dataclass_fields__}
    return POLICY_DOMAIN+json.dumps(
        fields,sort_keys=True,separators=(",",":"),ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def policy_event_digest(record: SignedPolicyEvent) -> str:
    """Hash cryptographic transition and every signed proof, not untrusted description."""
    if type(record) is not SignedPolicyEvent:
        raise CustodyRejected("invalid_signed_event")
    payload=canonical_policy_bytes(record.event)
    sigs=(
        record.issuer_signature_b64,record.d1_pop_b64,
        record.d2_pop_b64,record.old_d1_retire_b64,record.old_d2_retire_b64,
    )
    for item in sigs:
        _signature(item,allow_empty=True)
    b=json.dumps(sigs,separators=(",",":"),ensure_ascii=False).encode("ascii")
    return sha256(CHAIN_DOMAIN+payload+b).hexdigest()


def validate_policy_chain(
    *, signed_events: Any, trusted_issuer_public_key: Any,
    required_anchor: PolicyAnchor, ledger_id: str,
    epoch: str,
) -> VerifiedPolicyLAB:
    """Strict static replay, not registration, persistence or real trust.

    Anchor MUST be independently current. Merely passing a matching anchor
    from the SAME compromised snapshot cannot establish freshness.
    """
    _validate_id(ledger_id,"expected_ledger")
    _validate_hex(epoch,_HEX32,"expected_epoch")
    issuer=_public(trusted_issuer_public_key,"pre_pinned_issuer_key")
    if type(required_anchor) is not PolicyAnchor:
        raise CustodyRejected("trusted_anchor_required")
    if required_anchor.ledger_id!=ledger_id or required_anchor.epoch!=epoch:
        raise CustodyRejected("trusted_anchor_identity_mismatch")
    _uint(required_anchor.generation,"anchor_generation")
    _validate_hex(required_anchor.chain_digest,_HEX64,"anchor_chain_digest")
    if (type(signed_events) not in (tuple,list) or
            not 1 <= len(signed_events) <= _MAX_EVENTS):
        raise CustodyRejected("policy_chain_missing_or_unbounded")
    seen_keys={issuer}
    seen_nonces=set()
    previous_digest=_ZERO_DIGEST
    previous_ns=0
    previous_d1=None
    previous_d2=None
    revoked=False
    for n,record in enumerate(signed_events,start=1):
        if type(record) is not SignedPolicyEvent:
            raise CustodyRejected("unexpected_policy_envelope")
        event=record.event
        payload=canonical_policy_bytes(event)
        if event.ledger_id!=ledger_id or event.epoch!=epoch:
            raise CustodyRejected("policy_ledger_epoch_mismatch")
        if event.generation!=n:
            raise CustodyRejected("policy_generation_gap_or_fork")
        if event.previous_digest!=previous_digest:
            raise CustodyRejected("policy_history_digest_mismatch")
        if event.request_nonce in seen_nonces:
            raise CustodyRejected("reused_enrollment_request_nonce")
        if event.issued_ns<=previous_ns:
            raise CustodyRejected("policy_timestamp_not_strictly_increasing")
        if revoked:
            raise CustodyRejected("terminal_revocation_forbids_reenrollment")
        _verify(issuer,payload,record.issuer_signature_b64,"issuer")
        if n==1 and event.action!="ENROLL":
            raise CustodyRejected("only_explicit_genesis_enrollment")
        if n>1 and event.action=="ENROLL":
            raise CustodyRejected("implicit_or_duplicate_reenrollment_forbidden")
        if event.action in ("ENROLL","ROTATE"):
            d1=_public(bytes.fromhex(event.d1_public_hex),"d1_enrollment_key")
            d2=_public(bytes.fromhex(event.d2_public_hex),"d2_enrollment_key")
            if d1==d2 or d1 in seen_keys or d2 in seen_keys:
                raise CustodyRejected("reused_or_shared_custodian_key")
            _verify(d1,POP_DOMAIN+payload,record.d1_pop_b64,"d1_proof_of_possession")
            _verify(d2,POP_DOMAIN+payload,record.d2_pop_b64,"d2_proof_of_possession")
            if n>1:
                _verify(previous_d1,RETIRE_DOMAIN+payload,
                        record.old_d1_retire_b64,"previous_d1_retirement_ack")
                _verify(previous_d2,RETIRE_DOMAIN+payload,
                        record.old_d2_retire_b64,"previous_d2_retirement_ack")
            elif record.old_d1_retire_b64!="" or record.old_d2_retire_b64!="":
                raise CustodyRejected("genesis_cannot_have_previous_ack")
            previous_d1,previous_d2=d1,d2
            seen_keys.update((d1,d2))
        else:
            # Emergency terminal revoke: the issuer alone can STOP the LAB.
            # A compromised old custodian cannot obstruct a safety stop.
            # There is no auto-reactivation or trust-root re-bootstrap API.
            if n==1:
                raise CustodyRejected("genesis_revoke_forbidden")
            if any(getattr(record,name)!="" for name in (
                "d1_pop_b64","d2_pop_b64",
                "old_d1_retire_b64","old_d2_retire_b64",
            )):
                raise CustodyRejected("revoke_must_not_claim_new_key_proofs")
            previous_d1=previous_d2=b""
            revoked=True
        previous_digest=policy_event_digest(record)
        previous_ns=event.issued_ns
        seen_nonces.add(event.request_nonce)
    if (required_anchor.generation!=len(signed_events)
            or not hmac.compare_digest(required_anchor.chain_digest,previous_digest)):
        raise CustodyRejected("out_of_band_anchor_does_not_match_latest_generation")
    return VerifiedPolicyLAB(
        ledger_id,epoch,len(signed_events),previous_digest,revoked,
        previous_d1,previous_d2,
    )


def assess_enrollment_and_recovery(
    *,
    signed_events: Any,
    trusted_issuer_public_key: Any,
    required_anchor: PolicyAnchor,
    ledger_id: str,
    epoch: str,
    # A162 existing synthetic read-only sources:
    journal: Any, local_witness: Any, checkpoint: Any,
    checkpoint_pins: Any, floor_d1: SignedFloor, floor_d2: SignedFloor,
    request_nonce: str, now_ns: int,
) -> CustodyReview:
    """A163 gate: revoked/old keys hard-block; current match only quarantines."""
    try:
        state=validate_policy_chain(
            signed_events=signed_events, trusted_issuer_public_key=trusted_issuer_public_key,
            required_anchor=required_anchor, ledger_id=ledger_id, epoch=epoch,
        )
        if state.terminal_revoked:
            return CustodyReview(
                SCHEMA,"LAB_HARD_BLOCKED",
                "terminal_revocation_blocks_all_floor_signers",
                synthetic_policy_signatures_valid=True,
                generation_checked_against_caller_anchor=True,
            )
        verification=assess_three_source_restart(
            journal=journal,local_witness=local_witness,
            checkpoint=checkpoint,checkpoint_pins=checkpoint_pins,
            floor_d1=floor_d1,floor_d2=floor_d2,
            floor_pins={"d1":state.d1_key,"d2":state.d2_key},
            expected_ledger=ledger_id,expected_epoch=epoch,
            request_nonce=request_nonce,now_ns=now_ns,
        )
        if verification.schema != A162_SCHEMA or verification.verdict != "LAB_QUARANTINE_MANUAL_REVIEW":
            return CustodyReview(
                SCHEMA,"LAB_HARD_BLOCKED",
                "a162_three_source_rejected:"+verification.reason,
                synthetic_policy_signatures_valid=True,
                generation_checked_against_caller_anchor=True,
            )
        return CustodyReview(
            SCHEMA,"LAB_QUARANTINE_MANUAL_REVIEW",
            "synthetic_current_generation_matches_no_external_custody_attested",
            synthetic_policy_signatures_valid=True,
            generation_checked_against_caller_anchor=True,
            mathematical_three_source_match=True,
        )
    except CustodyRejected as exc:
        return CustodyReview(SCHEMA,"LAB_HARD_BLOCKED",str(exc))
    except Exception:
        return CustodyReview(SCHEMA,"LAB_HARD_BLOCKED","unexpected_or_unavailable_policy_source")
