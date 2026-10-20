"""LAB ONLY: offline AWS KMS Ed25519 RAW interop proposal reviewer.

This verifies CONFIGURATION/FORM of a proposed KMS Sign contract against
official ECC_NIST_EDWARDS25519 / ED25519_SHA_512 / RAW semantics. No boto3,
no AWS request, no real KMS key, no enrollment, no monetary charge.
A KMS key ID, claimed thumbprint, IAM label and caller-supplied public key
do not authenticate signer ownership or issuer freshness. ALWAYS BLOCKED.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from atlasquant_aion_p0_incident_external_witness_proposal_lab import NO_GO_FLAGS
from atlasquant_aion_p0_signed_incident_envelope_lab import (
    DOMAIN, inspect_signed_incident_envelope_lab,
)

SCHEMA = "AION_P0_KMS_ED25519_RAW_INTEROP_LAB_V1"
FIELDS = frozenset((
    "key_spec","key_usage","signing_algorithm","message_type","kms_key_id",
    "signing_region","public_key_sha256","signed_message_sha256",
))
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:@-]{2,199}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
REQ = {
    "key_spec":"ECC_NIST_EDWARDS25519",
    "key_usage":"SIGN_VERIFY",
    "signing_algorithm":"ED25519_SHA_512",
    "message_type":"RAW",
}


def _value(v: Any) -> bool:
    return type(v) is str and bool(ID.fullmatch(v))


def _digest(v: Any) -> bool:
    return type(v) is str and bool(HEX64.fullmatch(v))


def review_kms_ed25519_raw_proposal_lab(
    proposal: Any, envelope: Any, signature: Any, public_key: Any, *,
    expected_issuer: Any, expected_scope: Any, expected_nonce: Any,
    now_utc: Any, observed_head: Any = None,
) -> dict[str, Any]:
    defects: list[str] = []
    if type(proposal) is not dict:
        defects.append("PROPOSAL_NOT_PLAIN_DICT")
        proposal = {}
    if frozenset(proposal) != FIELDS:
        defects.append("PROPOSAL_FIELDS_NOT_EXACT")
    for field, requirement in REQ.items():
        current = proposal.get(field)
        if type(current) is not str or current != requirement:
            defects.append("AWS_KMS_MODE_NOT_COMPATIBLE:" + field)
    for field in ("kms_key_id","signing_region"):
        if not _value(proposal.get(field)):
            defects.append("PROPOSAL_ID_INVALID:" + field)
    for field in ("public_key_sha256","signed_message_sha256"):
        if not _digest(proposal.get(field)):
            defects.append("PROPOSAL_DIGEST_INVALID:" + field)

    if type(envelope) is not bytes or not (1<=len(envelope)<=4096):
        defects.append("ENVELOPE_BYTES_INVALID")
    elif len(DOMAIN)+len(envelope)>4096:
        defects.append("KMS_RAW_MESSAGE_GT_4096")
    if type(signature) is not bytes or len(signature)!=64:
        defects.append("SIGNATURE_BYTES_INVALID")
    if type(public_key) is not bytes or len(public_key)!=32:
        defects.append("ED25519_PUBLIC_KEY_BYTES_INVALID")
    if type(public_key) is bytes and len(public_key)==32 and (
        _digest(proposal.get("public_key_sha256"))
    ) and sha256(public_key).hexdigest()!=proposal["public_key_sha256"]:
        defects.append("LOCAL_KEY_FINGERPRINT_MISMATCH")
    if type(envelope) is bytes and 1<=len(envelope)<=4096 and (
        _digest(proposal.get("signed_message_sha256"))
    ) and sha256(DOMAIN+envelope).hexdigest()!=proposal["signed_message_sha256"]:
        defects.append("SIGNED_MESSAGE_DIGEST_MISMATCH")

    crypto_valid = False
    if (type(envelope) is bytes and 1<=len(envelope)<=4096
        and type(signature) is bytes and len(signature)==64
        and type(public_key) is bytes and len(public_key)==32):
        observation = inspect_signed_incident_envelope_lab(
            envelope, signature, public_key,
            expected_issuer=expected_issuer, expected_scope=expected_scope,
            expected_nonce=expected_nonce, now_utc=now_utc,
            observed_head=observed_head,
        )
        crypto_valid=observation[
            "signature_mathematically_valid_with_caller_key_in_lab"]
        defects.extend("ENVELOPE:"+x for x in observation["blockers"]
                       if x not in (
                           "OUT_OF_BAND_SIGNER_NOT_ENROLLED",
                           "EXTERNAL_NONCE_REPLAY_GUARD_NOT_ENROLLED",
                           "INDEPENDENT_LATEST_HEAD_NOT_AUTHENTICATED",
                       ))

    # The Signature mathematically verifies under a CALLER key; it does not
    # bind to AWS KMS's *actual*, independently controlled signing key ID.
    reasons=tuple(sorted(set(defects+[
        "INDEPENDENT_KMS_KEY_OWNERSHIP_NOT_VERIFIED",
        "OUT_OF_BAND_PUBLIC_KEY_ENROLLMENT_NOT_ATTESTED",
        "LATEST_EXTERNAL_HEAD_NOT_AUTHENTICATED",
        "EXTERNAL_NONCE_REPLAY_FENCE_NOT_ENROLLED",
        "OWNER_APPROVAL_AND_PRODUCER_EFFECT_NOT_VERIFIED",
    ])))
    return {
        "schema":SCHEMA,
        "status":"BLOCKED",
        "allowed":False,
        "reason":reasons[0],
        "blockers":reasons,
        "crypto_valid_with_supplied_key_only_lab":crypto_valid,
        "aws_api_called":False,
        "aws_key_created":False,
        "external_signer_verified":False,
        "latest_head_authenticated":False,
        "external_revocation_authenticated":False,
        "external_nonce_replay_fenced":False,
        "simulation_only":True,
        **{field:False for field in NO_GO_FLAGS},
    }


__all__ = ["SCHEMA","FIELDS","REQ","review_kms_ed25519_raw_proposal_lab"]
