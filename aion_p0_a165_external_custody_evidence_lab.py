"""A165 — Strict read-only synthetic independent-custodian evidence CONTRACT.

Two separately named "review issuers" (v1/v2) co-sign (with each R1/R2
auditor signing its own proof-of-possession) a nonce-bound custody statement
for the exact A164 policy floor. Every byte/identity/root is supplied by one
LAB caller. Signature verification and distinct labels/keys are *NOT* proof
of real independent administrators, providers, immutable storage, ownership
or even the truth of the claims. Colluding issuers can lie consistently.

The result is ALWAYS LAB_HARD_BLOCKED or LAB_QUARANTINE_MANUAL_REVIEW;
no independently verified flag is ever true. No network, persistence,
enrollment, credential issuance, provider execution, automatic retry/worker,
recovery or production interface. This is intentionally not a trust grant.
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

from aion_p0_a164_independent_revocation_floor_lab import (
    RevocationFloor, SignedRevocationFloor,
    assess_external_revocation_floor,
)

SCHEMA="AION_P0_A165_SYNTHETIC_EXTERNAL_CUSTODY_EVIDENCE_NO_GO_V1"
DOMAIN=b"AION-P0-A165-EXTERNAL-CUSTODY-ATTESTATION-v1\x00"
POSSESSION_DOMAIN=b"AION-P0-A165-AUDITOR-POSSESSION-v1\x00"
AUDIENCE="AION-H0-READONLY-CUSTODY-INTAKE-LAB"
_HEX32=re.compile(r"[0-9a-f]{32}\Z")
_HEX64=re.compile(r"[0-9a-f]{64}\Z")
_ID=re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_MAX_NS=2**63-1
_MAX_WINDOW_NS=20_000_000_000


class CustodyEvidenceRejected(ValueError):
    """An untrusted or inconsistent claim cannot advance the H0 gate."""


@dataclass(frozen=True)
class CustodyClaim:
    role: str
    ledger_id: str
    epoch: str
    policy_generation: int
    policy_digest: str
    terminal_revoked: bool
    challenge_nonce: str
    audience: str
    auditor_public_hex: str
    # The following are SELF-DECLARED CLAIMS, NOT independently observed facts.
    organization_id: str
    administrator_id: str
    provider_account_id: str
    storage_failure_domain_id: str
    custody_request_id: str
    asserted_separate_administration: bool
    asserted_nonrollbackable_storage: bool
    observed_ns: int
    expires_ns: int


@dataclass(frozen=True)
class SignedCustodyClaim:
    claim: CustodyClaim
    review_issuer_signature_b64: str
    auditor_possession_signature_b64: str


@dataclass(frozen=True)
class CustodyEvidenceReview:
    schema: str
    verdict: str
    reason: str
    synthetic_two_issuer_signatures_checked: bool = False
    synthetic_two_auditor_pop_signatures_checked: bool = False
    claims_syntactically_disjoint: bool = False
    a164_mathematical_floor_checked: bool = False
    actual_independent_operator_identity_verified: bool = False
    actual_independent_administrator_control_verified: bool = False
    actual_nonrollbackable_storage_verified: bool = False
    real_issuer_provenance_verified: bool = False
    real_owner_identity_and_approval_verified: bool = False
    actual_provider_effect_or_no_effect_verified: bool = False
    checkpoint_restore_allowed: bool = False
    external_execution_allowed: bool = False
    worker_allowed: bool = False
    automatic_retry_allowed: bool = False
    automatic_resend_allowed: bool = False
    homologated_p0_count: int = 0


def _id(value: Any, label: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise CustodyEvidenceRejected("invalid_"+label)


def _hex(value: Any, pattern: re.Pattern, label: str) -> None:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise CustodyEvidenceRejected("invalid_"+label)


def _int(value: Any, label: str) -> None:
    if type(value) is not int or not 1 <= value <= _MAX_NS:
        raise CustodyEvidenceRejected("invalid_"+label)


def _key(value: Any, label: str) -> bytes:
    if type(value) is not bytes or len(value)!=32:
        raise CustodyEvidenceRejected("invalid_"+label)
    try:
        Ed25519PublicKey.from_public_bytes(value)
    except ValueError as exc:
        raise CustodyEvidenceRejected("invalid_"+label) from exc
    return value


def _sig(value: Any) -> bytes:
    if type(value) is not str or not value:
        raise CustodyEvidenceRejected("signature_missing")
    try:
        raw=base64.b64decode(value,validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CustodyEvidenceRejected("signature_malformed") from exc
    if len(raw)!=64 or base64.b64encode(raw).decode("ascii")!=value:
        raise CustodyEvidenceRejected("signature_noncanonical_or_wrong_length")
    return raw


def _verify(key: bytes, payload: bytes, value: Any, label: str) -> None:
    signature=_sig(value)
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(signature,payload)
    except (InvalidSignature, ValueError) as exc:
        raise CustodyEvidenceRejected(label+"_signature_invalid") from exc


def canonical_custody_claim_bytes(claim: CustodyClaim) -> bytes:
    if type(claim) is not CustodyClaim:
        raise CustodyEvidenceRejected("custody_claim_wrong_type")
    if type(claim.role) is not str or claim.role not in ("r1","r2"):
        raise CustodyEvidenceRejected("unexpected_custody_role")
    _id(claim.ledger_id,"ledger")
    _hex(claim.epoch,_HEX32,"epoch")
    _int(claim.policy_generation,"generation")
    _hex(claim.policy_digest,_HEX64,"policy_digest")
    if type(claim.terminal_revoked) is not bool:
        raise CustodyEvidenceRejected("revoked_flag_not_boolean")
    _hex(claim.challenge_nonce,_HEX32,"nonce")
    if type(claim.audience) is not str or claim.audience!=AUDIENCE:
        raise CustodyEvidenceRejected("read_only_audience_required")
    _hex(claim.auditor_public_hex,_HEX64,"auditor_public_key")
    for name in (
        "organization_id","administrator_id","provider_account_id",
        "storage_failure_domain_id","custody_request_id",
    ):
        _id(getattr(claim,name),name)
    if (type(claim.asserted_separate_administration) is not bool
            or claim.asserted_separate_administration is not True):
        raise CustodyEvidenceRejected("separate_administration_not_claimed")
    if (type(claim.asserted_nonrollbackable_storage) is not bool
            or claim.asserted_nonrollbackable_storage is not True):
        raise CustodyEvidenceRejected("nonrollbackable_storage_not_claimed")
    _int(claim.observed_ns,"observation_time")
    _int(claim.expires_ns,"expiration_time")
    if (claim.expires_ns<=claim.observed_ns
            or claim.expires_ns-claim.observed_ns>_MAX_WINDOW_NS):
        raise CustodyEvidenceRejected("unbounded_claim_freshness")
    obj={name:getattr(claim,name) for name in CustodyClaim.__dataclass_fields__}
    return DOMAIN+json.dumps(obj,sort_keys=True,separators=(",",":"),
                             ensure_ascii=False,allow_nan=False).encode("utf-8")


def _pins(pinned_issuer_keys: Any, pinned_auditor_keys: Any,
          trusted_issuer_public_key: Any) -> tuple[dict[str,bytes],dict[str,bytes]]:
    if type(pinned_issuer_keys) is not dict or set(pinned_issuer_keys)!={"v1","v2"}:
        raise CustodyEvidenceRejected("exact_two_review_issuer_pins_required")
    if type(pinned_auditor_keys) is not dict or set(pinned_auditor_keys)!={"r1","r2"}:
        raise CustodyEvidenceRejected("exact_two_auditor_pins_required")
    issuer={name:_key(pinned_issuer_keys[name],name+"_review_key") for name in ("v1","v2")}
    audit={name:_key(pinned_auditor_keys[name],name+"_audit_key") for name in ("r1","r2")}
    root=_key(trusted_issuer_public_key,"root_policy_key")
    # Distinct bytes do NOT show distinct corporations or custody.
    values=tuple(issuer.values())+tuple(audit.values())+(root,)
    if len(values)!=len(set(values)):
        raise CustodyEvidenceRejected("cross_role_key_reuse")
    return issuer,audit


def verify_synthetic_custody_claims(
    *, signed_r1: SignedCustodyClaim, signed_r2: SignedCustodyClaim,
    pinned_review_issuer_keys: dict[str,bytes],
    pinned_auditor_keys: dict[str,bytes],
    trusted_issuer_public_key: bytes,
    expected_floor: RevocationFloor,
    expected_ledger: str, expected_epoch: str,
    expected_challenge_nonce: str, now_ns: int,
) -> tuple[CustodyClaim,CustodyClaim]:
    """Enforces binding to existing A164 claim but DOES NOT prove independence."""
    from aion_p0_a164_independent_revocation_floor_lab import (
        canonical_revocation_floor_bytes,
    )
    # Validate expected floor with A164's strict parser (not a signature).
    canonical_revocation_floor_bytes(expected_floor)
    _id(expected_ledger,"expected_ledger")
    _hex(expected_epoch,_HEX32,"expected_epoch")
    _hex(expected_challenge_nonce,_HEX32,"expected_nonce")
    _int(now_ns,"caller_time")
    issuer,auditor=_pins(pinned_review_issuer_keys,pinned_auditor_keys,
                         trusted_issuer_public_key)
    if (expected_floor.ledger_id != expected_ledger
            or expected_floor.epoch != expected_epoch
            or not hmac.compare_digest(expected_floor.request_nonce,
                                       expected_challenge_nonce)):
        raise CustodyEvidenceRejected("expected_floor_identity_nonce_mismatch")
    if now_ns < expected_floor.observed_ns or now_ns >= expected_floor.valid_until_ns:
        raise CustodyEvidenceRejected("expected_floor_not_current")
    claims=[]
    for role,reviewer,entry in (
        ("r1","v1",signed_r1),("r2","v2",signed_r2),
    ):
        if type(entry) is not SignedCustodyClaim:
            raise CustodyEvidenceRejected("signed_custody_claim_required")
        claim=entry.claim
        payload=canonical_custody_claim_bytes(claim)
        if claim.role!=role:
            raise CustodyEvidenceRejected("signed_claim_wrong_role")
        if (claim.ledger_id!=expected_ledger
                or claim.epoch!=expected_epoch
                or claim.policy_generation!=expected_floor.generation
                or not hmac.compare_digest(claim.policy_digest,
                                           expected_floor.chain_digest)
                or claim.terminal_revoked!=expected_floor.terminal_revoked
                or not hmac.compare_digest(claim.challenge_nonce,
                                           expected_challenge_nonce)):
            raise CustodyEvidenceRejected("custody_claim_not_bound_to_floor")
        if not hmac.compare_digest(claim.auditor_public_hex,
                                   auditor[role].hex()):
            raise CustodyEvidenceRejected("auditor_public_pin_mismatch")
        if (now_ns<claim.observed_ns or now_ns>=claim.expires_ns
                or claim.observed_ns<expected_floor.observed_ns
                or claim.expires_ns>expected_floor.valid_until_ns):
            raise CustodyEvidenceRejected("custody_claim_stale_or_outside_floor_window")
        _verify(issuer[reviewer],payload,entry.review_issuer_signature_b64,
                reviewer+"_review")
        _verify(auditor[role],POSSESSION_DOMAIN+payload,
                entry.auditor_possession_signature_b64,role+"_possession")
        claims.append(claim)
    a,b=claims
    # Syntactic incompatibility is safer than allowing obviously shared
    # credentials, but THESE STRINGS ARE SELF-ASSERTED (not verified IDs).
    for name in (
        "organization_id","administrator_id","provider_account_id",
        "storage_failure_domain_id","custody_request_id",
    ):
        if getattr(a,name)==getattr(b,name):
            raise CustodyEvidenceRejected("shared_claimed_failure_domain:"+name)
    return a,b


def _review(reason: str, *, valid=False, disjoint=False,
            matched=False, quarantine=False) -> CustodyEvidenceReview:
    return CustodyEvidenceReview(
        SCHEMA,
        "LAB_QUARANTINE_MANUAL_REVIEW" if quarantine else "LAB_HARD_BLOCKED",
        reason,
        synthetic_two_issuer_signatures_checked=valid,
        synthetic_two_auditor_pop_signatures_checked=valid,
        claims_syntactically_disjoint=disjoint,
        a164_mathematical_floor_checked=matched,
    )


def assess_custodian_evidence_and_h0(
    *, signed_r1: SignedCustodyClaim,signed_r2: SignedCustodyClaim,
    pinned_review_issuer_keys: dict[str,bytes],
    signed_floor_r1: SignedRevocationFloor,signed_floor_r2: SignedRevocationFloor,
    pinned_auditor_keys: dict[str,bytes],
    trusted_issuer_public_key: bytes,
    challenge_nonce: str,ledger_id: str,epoch: str,now_ns: int,
    signed_events: Any,local_anchor: Any,
    journal: Any,local_witness: Any,checkpoint: Any,
    checkpoint_pins: Any,floor_d1: Any,floor_d2: Any,
    request_nonce: str,
) -> CustodyEvidenceReview:
    """Full LAB-only evidence chain; NEVER authorizes anything real."""
    try:
        if (type(signed_floor_r1) is not SignedRevocationFloor
                or type(signed_floor_r2) is not SignedRevocationFloor):
            raise CustodyEvidenceRejected("signed_revocation_floors_required")
        if signed_floor_r1.floor != signed_floor_r2.floor:
            raise CustodyEvidenceRejected("two_floor_payloads_disagree")
        verify_synthetic_custody_claims(
            signed_r1=signed_r1,signed_r2=signed_r2,
            pinned_review_issuer_keys=pinned_review_issuer_keys,
            pinned_auditor_keys=pinned_auditor_keys,
            trusted_issuer_public_key=trusted_issuer_public_key,
            expected_floor=signed_floor_r1.floor,
            expected_ledger=ledger_id,expected_epoch=epoch,
            expected_challenge_nonce=challenge_nonce,now_ns=now_ns,
        )
        revocation=assess_external_revocation_floor(
            signed_events=signed_events,
            trusted_issuer_public_key=trusted_issuer_public_key,
            local_anchor=local_anchor,
            signed_r1=signed_floor_r1,signed_r2=signed_floor_r2,
            pinned_auditor_keys=pinned_auditor_keys,
            challenge_nonce=challenge_nonce,
            ledger_id=ledger_id,epoch=epoch,now_ns=now_ns,
            journal=journal,local_witness=local_witness,
            checkpoint=checkpoint,checkpoint_pins=checkpoint_pins,
            floor_d1=floor_d1,floor_d2=floor_d2,
            request_nonce=request_nonce,
        )
        if revocation.verdict!="LAB_QUARANTINE_MANUAL_REVIEW":
            return _review("a164_revocation_or_h0_blocked:"+revocation.reason,
                           valid=True,disjoint=True)
        return _review(
            "synthetic_administrative_claims_only_no_independent_custody_proven",
            valid=True,disjoint=True,matched=True,quarantine=True,
        )
    except (CustodyEvidenceRejected,ValueError) as exc:
        return _review(str(exc))
    except Exception:
        return _review("unexpected_or_unavailable_custody_evidence_source")
