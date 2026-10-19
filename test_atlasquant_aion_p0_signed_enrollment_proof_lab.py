"""P0 LAB signed-owner-enrollment attestation adversarial matrix.

Only ephemeral fixture signer keys are generated. No real HUMAN_OWNER is
enrolled. Even a valid signature MUST return BLOCKED, as trusted issuer
custody / real owner binding / durable CAS are not established in this LAB.
"""
import base64
from copy import deepcopy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_p0_signed_enrollment_proof_lab import (
    SCHEMA, PURPOSE, canonical_receipt_bytes, inspect_signed_enrollment_lab,
)

NOW = "2026-10-19T18:00:00Z"
NONCE = "fixed_challenge_nonce_123456789012345"
FINGERPRINT = "sha256:" + "1" * 64
SCOPE = {
    "owner_id": "HUMAN_OWNER",
    "tenant_id": "atlasquant-owner",
    "workspace_id": "owner-workspace-01",
    "credential_id": "credential-owner-01",
}


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def proof():
    secret = Ed25519PrivateKey.generate()
    pub = secret.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    anchor = {
        "issuer_id": "external-witness-lab",
        "key_id": "issuer-key-v1",
        "public_key_b64": b64(pub),
        "status": "ACTIVE",
    }
    receipt = {
        "schema": SCHEMA,
        "purpose": PURPOSE,
        "owner_id": SCOPE["owner_id"],
        "tenant_id": SCOPE["tenant_id"],
        "workspace_id": SCOPE["workspace_id"],
        "credential_id": SCOPE["credential_id"],
        "owner_public_key_sha256": FINGERPRINT,
        "challenge_nonce": NONCE,
        "issuer_id": anchor["issuer_id"],
        "key_id": anchor["key_id"],
        "evidence_id": "owner-enrollment-evidence-001",
        "source_revision": 1,
        "issued_at": "2026-10-19T17:59:30Z",
        "expires_at": "2026-10-19T18:01:30Z",
        "intent": "ENROLL",
    }
    return secret, anchor, receipt


def signed(secret, receipt):
    return {"receipt": deepcopy(receipt),
            "signature_b64": b64(secret.sign(canonical_receipt_bytes(receipt)))}


def evaluate(evidence, anchor, **overrides):
    cfg = {
        "pinned_issuer": anchor,
        "expected_scope": SCOPE,
        "expected_nonce": NONCE,
        "expected_fingerprint": FINGERPRINT,
        "prior_source_revision": 0,
        "seen_evidence_ids": frozenset(),
        "now": NOW,
    }
    cfg.update(overrides)
    evidence_before, anchor_before = deepcopy(evidence), deepcopy(anchor)
    out = inspect_signed_enrollment_lab(evidence, **cfg)
    assert evidence == evidence_before and anchor == anchor_before
    assert out["state"] == "BLOCKED"
    for k in ("independent_issuer_custody_verified", "human_owner_identity_established",
              "owner_enrollment_authorized", "trust_registry_modified",
              "owner_decision_authorized", "worker_armed",
              "external_action_executed", "executes_action"):
        assert out[k] is False, (k, out)
    return out


def test_p0_01_valid_ed25519_issuer_receipt_is_diagnostic_not_enrollment(proof):
    secret, anchor, row = proof
    out = evaluate(signed(secret, row), anchor)
    assert out["signature_checked"] is True
    assert out["reason"] == "P0_SIGNATURE_CONSISTENT_BUT_ISSUER_CUSTODY_UNVERIFIED"


def test_p0_02_forged_issuer_signature_does_not_pass(proof):
    _, anchor, row = proof
    outsider = Ed25519PrivateKey.generate()
    out = evaluate(signed(outsider, row), anchor)
    assert out["reason"] == "P0_ATTESTATION_SIGNATURE_INVALID"


def test_p0_03_changing_issuer_public_key_breaks_signature(proof):
    secret, anchor, row = proof
    outsider = Ed25519PrivateKey.generate()
    changed = deepcopy(anchor)
    changed["public_key_b64"] = b64(outsider.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ))
    out = evaluate(signed(secret, row), changed)
    assert out["reason"] == "P0_ATTESTATION_SIGNATURE_INVALID"


def test_p0_04_signed_receipt_with_self_supplied_issuer_still_no_authority(proof):
    secret, anchor, row = proof
    # The entire trust anchor is supplied by this test, not a custodian.
    out = evaluate(signed(secret, row), deepcopy(anchor))
    assert out["reason"] == "P0_SIGNATURE_CONSISTENT_BUT_ISSUER_CUSTODY_UNVERIFIED"
    assert not out["independent_issuer_custody_verified"]


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("owner_id", "OTHER_OWNER", "P0_SCOPE_MISMATCH"),
    ("tenant_id", "other-tenant", "P0_SCOPE_MISMATCH"),
    ("workspace_id", "cross-workspace", "P0_SCOPE_MISMATCH"),
    ("credential_id", "cross-credential", "P0_SCOPE_MISMATCH"),
    ("owner_public_key_sha256", "sha256:" + "2" * 64, "P0_CREDENTIAL_KEY_MISMATCH"),
    ("challenge_nonce", "different_nonce_123456789012345", "P0_NONCE_MISMATCH"),
    ("source_revision", 0, "P0_REVISION_NOT_MONOTONIC"),
    ("source_revision", 3, "P0_REVISION_NOT_MONOTONIC"),
    ("source_revision", True, "P0_REVISION_NOT_MONOTONIC"),
])
def test_p0_05_to_13_scope_and_revision_contract(proof, field, value, reason):
    secret, anchor, row = proof
    forged = deepcopy(row)
    forged[field] = value
    assert evaluate(signed(secret, forged), anchor)["reason"] == reason


def test_p0_14_signed_payload_change_is_detected(proof):
    secret, anchor, row = proof
    claim = signed(secret, row)
    claim["receipt"]["credential_id"] = SCOPE["credential_id"]
    claim["receipt"]["evidence_id"] = "owner-enrollment-evidence-CHANGED"
    assert evaluate(claim, anchor)["reason"] == "P0_ATTESTATION_SIGNATURE_INVALID"


def test_p0_15_replay_list_rejects_evidence_id(proof):
    secret, anchor, row = proof
    out = evaluate(
        signed(secret, row), anchor,
        seen_evidence_ids=frozenset({row["evidence_id"]})
    )
    assert out["reason"] == "P0_REPLAY_DETECTED"


def test_p0_16_lost_prior_revision_state_cannot_claim_antirollback(proof):
    secret, anchor, row = proof
    out = evaluate(signed(secret, row), anchor, prior_source_revision=-1)
    assert out["reason"] == "P0_REVISION_NOT_MONOTONIC"


def test_p0_17_nonpersistent_state_cannot_claim_replay_resistance(proof):
    secret, anchor, row = proof
    # Repeated verification with same caller-supplied empty replay list remains
    # cryptographically consistent. This is intentionally only a diagnostic.
    signed_row = signed(secret, row)
    a = evaluate(signed_row, anchor)
    b = evaluate(signed_row, anchor)
    assert a["signature_checked"] and b["signature_checked"]
    assert not a["owner_enrollment_authorized"] and not b["owner_enrollment_authorized"]


@pytest.mark.parametrize(("field", "value"), [
    ("issued_at", "2026-10-19T18:00:01Z"),
    ("expires_at", "2026-10-19T18:00:00Z"),
    ("expires_at", "2026-10-19T18:09:00Z"),
    ("issued_at", "2026-10-19T17:58:00-04:00"),
])
def test_p0_18_to_21_signed_invalid_time_window(proof, field, value):
    secret, anchor, row = proof
    amended = deepcopy(row)
    amended[field] = value
    expected = "P0_TIME_INVALID" if "-04:00" in value else "P0_TIME_WINDOW_INVALID"
    assert evaluate(signed(secret, amended), anchor)["reason"] == expected


@pytest.mark.parametrize(("field", "value"), [
    ("schema", "OTHER_SCHEMA"), ("purpose", "ALLOW_WORKER"),
    ("intent", "RECOVER"), ("intent", "REVOKE"),
    ("intent", "ROTATE"),
])
def test_p0_22_to_26_protocol_domain_separation(proof, field, value):
    secret, anchor, row = proof
    altered = deepcopy(row)
    altered[field] = value
    assert evaluate(signed(secret, altered), anchor)["reason"] == "P0_RECEIPT_DOMAIN_INVALID"


@pytest.mark.parametrize("claim", ["trusted", "owner_identity_verified", "biometric_verified", "private_key"])
def test_p0_27_to_30_extra_trust_claims_rejected(proof, claim):
    secret, anchor, row = proof
    altered = deepcopy(row)
    altered[claim] = True
    assert evaluate(signed(secret, altered), anchor)["reason"] == "P0_RECEIPT_SHAPE_INVALID"


def test_p0_31_wrong_issuer_name_even_with_signature(proof):
    secret, anchor, row = proof
    changed = deepcopy(row)
    changed["issuer_id"] = "other-issuer"
    assert evaluate(signed(secret, changed), anchor)["reason"] == "P0_ISSUER_IDENTITY_MISMATCH"


def test_p0_32_revoked_issuer_is_denied(proof):
    secret, anchor, row = proof
    retired = deepcopy(anchor)
    retired["status"] = "REVOKED"
    assert evaluate(signed(secret, row), retired)["reason"] == "P0_ISSUER_NOT_ACTIVE"


def test_p0_33_bad_signature_encoding_denied(proof):
    secret, anchor, row = proof
    modified = signed(secret, row)
    modified["signature_b64"] = "not?base64"
    assert evaluate(modified, anchor)["reason"] == "P0_ATTESTATION_SIGNATURE_INVALID"


def test_p0_34_malformed_issuer_public_key_denied(proof):
    secret, anchor, row = proof
    modified = deepcopy(anchor)
    modified["public_key_b64"] = "not?base64"
    assert evaluate(signed(secret, row), modified)["reason"] == "P0_ATTESTATION_SIGNATURE_INVALID"


def test_p0_35_pinned_issuer_missing_denied(proof):
    secret, _, row = proof
    assert evaluate(signed(secret, row), None)["reason"] == "P0_PINNED_ISSUER_UNAVAILABLE"


def test_p0_36_wrong_expected_scope_denied(proof):
    secret, anchor, row = proof
    assert evaluate(signed(secret, row), anchor, expected_scope={})["reason"] == "P0_EXPECTED_SCOPE_UNAVAILABLE"


def test_p0_37_replay_list_unavailable_denied(proof):
    secret, anchor, row = proof
    assert evaluate(signed(secret, row), anchor, seen_evidence_ids=None)["reason"] == "P0_REPLAY_STATE_UNAVAILABLE"


def test_p0_38_unknown_evidence_shape_denied(proof):
    secret, anchor, row = proof
    claim = signed(secret, row)
    claim["independent_custody_verified"] = True
    assert evaluate(claim, anchor)["reason"] == "P0_EVIDENCE_SHAPE_INVALID"


def test_p0_39_no_real_enrollment_even_with_a_valid_receipt(proof):
    secret, anchor, row = proof
    out = evaluate(signed(secret, row), anchor)
    assert out["human_owner_identity_established"] is False
    assert out["owner_decision_authorized"] is False
    assert out["worker_armed"] is False
