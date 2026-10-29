"""A217 LAB: shape-check claimed out-of-host anchor acquisition, NEVER trust.

Even three distinct claimed organizations, two witness channels and matching
digests can be fabricated by one compromised host. No actual offline ceremony,
provider, authenticated external channel, independent key vault or durable
antirollback history is consulted. This is a requirements diagnostic only.
Every result has independent_origin_verified=False and may_activate=False.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_external_evidence_intake import decode_candidate_json
from labs.a216_synthetic_key_custody import inspect_synthetic_key_custody


ANCHOR_SCHEMA = "ATLASQUANT_AION_DECLARED_OUTOFHOST_ANCHOR_V0"
WITNESS_SCHEMA = "ATLASQUANT_AION_DECLARED_OUTOFHOST_WITNESS_V0"
_ANCHOR_FIELDS = frozenset({
    "schema", "owner_id", "tenant_id", "workspace_id", "provider_id",
    "challenge_digest", "issuer_key_sha256", "acquisition_mode",
    "ceremony_id", "collector_id", "collector_org_id", "owner_review_ref",
    "artifact_digest", "nonce_hex", "acquired_at",
})
_WITNESS_FIELDS = frozenset({
    "schema", "observer_id", "org_id", "channel_id", "ceremony_id",
    "issuer_key_sha256", "challenge_digest", "nonce_hex",
    "attestation_digest", "observed_at",
})
_HEX = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class ClaimedOutsideHostReadiness:
    custody_math_valid: bool
    claimed_separation_coherent: bool
    independent_origin_verified: bool
    may_activate: bool
    may_confirm: bool
    code: str
    claims_digest: str


def _deny(code: str, *, math: bool = False) -> ClaimedOutsideHostReadiness:
    return ClaimedOutsideHostReadiness(
        custody_math_valid=math,
        claimed_separation_coherent=False,
        independent_origin_verified=False,
        may_activate=False,
        may_confirm=False,
        code=code,
        claims_digest="",
    )


def _hex(value: Any) -> bool:
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _token(value: Any) -> bool:
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def _utc(value: Any, *, allow_datetime: bool = False) -> datetime:
    if allow_datetime and isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("ISO timestamp expected")
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone required")
    return stamp.astimezone(timezone.utc)


def _mapping(candidate: Any) -> Any:
    if isinstance(candidate, str):
        try:
            return decode_candidate_json(candidate)
        except ValueError:
            return None
    return candidate


def assess_claimed_outofhost_anchor(
    outbox_record: Any,
    candidate: Any,
    signed_receipt: Any,
    custody_certificate: Any,
    anchor_claim: Any,
    witness_a: Any,
    witness_b: Any,
    *,
    candidate_pubkey_bytes: Any,
    provisional_issuer_pubkey_bytes: Any,
    provisional_issuer_fingerprint: Any,
    receipt_nonce_hex: Any,
    observed_at: Any,
    last_witness_sequence: Any,
    seen_provider_event_ids: Any,
    seen_receipt_nonces: Any,
    previous_key_epoch: Any,
    seen_custody_serial_ids: Any,
    seen_ceremony_nonces: Any,
) -> ClaimedOutsideHostReadiness:
    """Check declared *requirements* after A216, not actual independence."""
    custody = inspect_synthetic_key_custody(
        outbox_record, candidate, signed_receipt, custody_certificate,
        candidate_pubkey_bytes=candidate_pubkey_bytes,
        provisional_issuer_pubkey_bytes=provisional_issuer_pubkey_bytes,
        provisional_issuer_fingerprint=provisional_issuer_fingerprint,
        receipt_nonce_hex=receipt_nonce_hex,
        observed_at=observed_at,
        last_witness_sequence=last_witness_sequence,
        seen_provider_event_ids=seen_provider_event_ids,
        seen_receipt_nonces=seen_receipt_nonces,
        previous_key_epoch=previous_key_epoch,
        seen_custody_serial_ids=seen_custody_serial_ids,
    )
    if (
        not custody.custody_signature_math_valid
        or custody.independent_origin_verified
        or custody.may_confirm
    ):
        return _deny("A216_" + custody.code)

    candidate = _mapping(candidate)
    anchor_claim = _mapping(anchor_claim)
    witness_a = _mapping(witness_a)
    witness_b = _mapping(witness_b)
    if not isinstance(anchor_claim, Mapping) or set(anchor_claim) != _ANCHOR_FIELDS:
        return _deny("ANCHOR_CLAIM_ENVELOPE_NOT_EXACT", math=True)
    if anchor_claim.get("schema") != ANCHOR_SCHEMA:
        return _deny("ANCHOR_CLAIM_SCHEMA_UNSUPPORTED", math=True)
    if not isinstance(witness_a, Mapping) or not isinstance(witness_b, Mapping):
        return _deny("WITNESS_CLAIM_MISSING_OR_AMBIGUOUS", math=True)
    if set(witness_a) != _WITNESS_FIELDS or set(witness_b) != _WITNESS_FIELDS:
        return _deny("WITNESS_CLAIM_ENVELOPE_NOT_EXACT", math=True)
    if witness_a.get("schema") != WITNESS_SCHEMA or witness_b.get("schema") != WITNESS_SCHEMA:
        return _deny("WITNESS_CLAIM_SCHEMA_UNSUPPORTED", math=True)

    expected = {
        "owner_id": candidate["owner_id"],
        "tenant_id": candidate["tenant_id"],
        "workspace_id": candidate["workspace_id"],
        "provider_id": candidate["provider_id"],
        "challenge_digest": candidate["challenge_digest"],
        "issuer_key_sha256": provisional_issuer_fingerprint,
    }
    if any(
        not isinstance(anchor_claim.get(name), str)
        or anchor_claim[name] != value
        for name, value in expected.items()
    ):
        return _deny("ANCHOR_SCOPE_OR_KEY_MISMATCH", math=True)
    for witness in (witness_a, witness_b):
        if (
            witness["issuer_key_sha256"] != provisional_issuer_fingerprint
            or witness["challenge_digest"] != candidate["challenge_digest"]
        ):
            return _deny("WITNESS_ROOT_OR_INTENT_MISMATCH", math=True)

    if anchor_claim["acquisition_mode"] != "DECLARED_OFF_HOST_MANUAL":
        return _deny("UNACCEPTABLE_CLAIMED_ACQUISITION_MODE", math=True)
    for name in ("ceremony_id", "collector_id", "collector_org_id", "owner_review_ref"):
        if not _token(anchor_claim[name]):
            return _deny("INVALID_CLAIMED_COLLECTOR_IDENTITY", math=True)
    for name in ("artifact_digest", "nonce_hex", "issuer_key_sha256", "challenge_digest"):
        if not _hex(anchor_claim[name]):
            return _deny("INVALID_CLAIMED_ANCHOR_DIGEST", math=True)
    for witness in (witness_a, witness_b):
        for name in ("observer_id", "org_id", "channel_id", "ceremony_id"):
            if not _token(witness[name]):
                return _deny("INVALID_CLAIMED_WITNESS_IDENTITY", math=True)
        if not _hex(witness["attestation_digest"]):
            return _deny("INVALID_CLAIMED_WITNESS_DIGEST", math=True)
        if not _hex(witness["nonce_hex"]):
            return _deny("INVALID_CLAIMED_WITNESS_NONCE", math=True)

    if (
        witness_a["observer_id"] == witness_b["observer_id"]
        or witness_a["org_id"] == witness_b["org_id"]
        or witness_a["channel_id"] == witness_b["channel_id"]
    ):
        return _deny("DUPLICATED_CLAIMED_INDEPENDENCE", math=True)
    if (
        anchor_claim["collector_org_id"] in {witness_a["org_id"], witness_b["org_id"]}
        or anchor_claim["collector_id"] in {witness_a["observer_id"], witness_b["observer_id"]}
    ):
        return _deny("CLAIMED_COLLECTOR_WITNESS_COLLISION", math=True)
    for witness in (witness_a, witness_b):
        if (
            witness["ceremony_id"] != anchor_claim["ceremony_id"]
            or witness["nonce_hex"] != anchor_claim["nonce_hex"]
        ):
            return _deny("WITNESS_CEREMONY_OR_NONCE_MISMATCH", math=True)
    if (
        not isinstance(seen_ceremony_nonces, (list, tuple, set, frozenset))
        or any(not _hex(item) for item in seen_ceremony_nonces)
    ):
        return _deny("UNTRUSTED_CEREMONY_NONCE_HISTORY", math=True)
    if anchor_claim["nonce_hex"] in seen_ceremony_nonces:
        return _deny("CEREMONY_NONCE_CLAIM_REPLAY", math=True)

    try:
        acquired = _utc(anchor_claim["acquired_at"])
        a_seen = _utc(witness_a["observed_at"])
        b_seen = _utc(witness_b["observed_at"])
        observed = _utc(observed_at, allow_datetime=True)
    except (ValueError, OverflowError, TypeError):
        return _deny("INVALID_DECLARED_OBSERVATION_TIME", math=True)
    if not (
        acquired <= a_seen <= observed and acquired <= b_seen <= observed
        and observed - acquired <= timedelta(days=1)
    ):
        return _deny("DECLARED_OBSERVATION_TIME_CONFLICT", math=True)

    encoded = json.dumps(
        {"anchor": dict(anchor_claim), "a": dict(witness_a), "b": dict(witness_b)},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    # A hash of HOST-SUPPLIED text cannot establish source independence.
    return ClaimedOutsideHostReadiness(
        custody_math_valid=True,
        claimed_separation_coherent=True,
        independent_origin_verified=False,
        may_activate=False,
        may_confirm=False,
        code="CLAIMED_CHANNELS_COHERENT_INDEPENDENT_ACQUISITION_UNPROVEN",
        claims_digest=sha256(encoded).hexdigest(),
    )


__all__ = [
    "ANCHOR_SCHEMA", "WITNESS_SCHEMA", "ClaimedOutsideHostReadiness",
    "assess_claimed_outofhost_anchor",
]
