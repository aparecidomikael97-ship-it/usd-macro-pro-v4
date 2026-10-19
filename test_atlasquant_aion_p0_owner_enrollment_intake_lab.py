"""P0 owner initial enrollment: LAB-only adversarial diagnostic contracts.

All payloads are dummy text. No real key, signature, biometric or provider.
The expected scope and apparent custodian in this test are untrusted values.
A format-consistent claim MUST NOT become an enrolled HUMAN_OWNER credential.
"""
from copy import deepcopy

import pytest

from atlasquant_aion_p0_owner_enrollment_intake_lab import (
    SCHEMA, inspect_untrusted_owner_enrollment,
)

NOW = "2026-10-19T18:00:00Z"
PARAMS = {
    "expected_owner_id": "HUMAN_OWNER",
    "expected_tenant_id": "atlasquant-owner",
    "expected_workspace_id": "atlasquant-owner-workspace",
    "now": NOW,
}


def proposal():
    return {
        "schema": SCHEMA,
        "intent": "ENROLL",
        "owner_id": "HUMAN_OWNER",
        "tenant_id": "atlasquant-owner",
        "workspace_id": "atlasquant-owner-workspace",
        "credential_id": "owner-key-a001",
        "credential_version": 1,
        "credential_kind": "ED25519_EXTERNAL",
        "public_key_fingerprint": "sha256:" + "a" * 64,
        "challenge_nonce": "synthetic_owner_nonce_1234567890",
        "issued_at": "2026-10-19T17:59:30Z",
        "expires_at": "2026-10-19T18:01:00Z",
        "proposed_custodian_id": "owner-custodian-01",
    }


def check(row):
    before = deepcopy(row)
    result = inspect_untrusted_owner_enrollment(row, **PARAMS)
    assert row == before
    assert result["state"] == "BLOCKED"
    assert result["reason"] == "INDEPENDENT_OWNER_CUSTODY_NOT_ESTABLISHED"
    for key in (
        "owner_identity_verified", "independent_custody_verified",
        "enrollment_authorized", "private_key_collected",
        "trust_root_changed", "signature_capture_performed",
        "decision_authorized", "worker_armed",
        "external_action_executed", "executes_action",
    ):
        assert result[key] is False, key
    return result


def test_p0_01_fully_coherent_payload_remains_untrusted():
    result = check(proposal())
    assert result["format_consistent"] is True
    assert result["format_blockers"] == []


@pytest.mark.parametrize("key", [
    "trusted", "owner_identity_verified", "biometric_verified",
    "witness_verified", "independent_custody_verified", "owner_approved",
])
def test_p0_02_to_07_forged_authority_claims_are_rejected(key):
    p = proposal()
    p[key] = True
    result = check(p)
    assert result["format_consistent"] is False
    assert "P0_CALLER_TRUST_FLAGS_FORBIDDEN" in result["format_blockers"]


@pytest.mark.parametrize(("key", "changed", "error"), [
    ("owner_id", "FAKE_OWNER", "P0_OWNER_ID_MISMATCH"),
    ("tenant_id", "other-tenant", "P0_TENANT_ID_MISMATCH"),
    ("workspace_id", "other-workspace", "P0_WORKSPACE_ID_MISMATCH"),
])
def test_p0_08_to_10_cross_scope_rejected(key, changed, error):
    p = proposal()
    p[key] = changed
    assert error in check(p)["format_blockers"]


def test_p0_11_missing_public_key_fingerprint():
    p = proposal()
    p.pop("public_key_fingerprint")
    result = check(p)
    assert "P0_ENROLLMENT_FIELDS_MISSING" in result["format_blockers"]
    assert "P0_PUBLIC_KEY_FINGERPRINT_INVALID" in result["format_blockers"]


def test_p0_12_submitted_private_key_is_extra_untrusted_data():
    p = proposal()
    p["private_key"] = "MUST_NOT_CAPTURE"
    result = check(p)
    assert "P0_ENROLLMENT_EXTRA_FIELDS" in result["format_blockers"]


def test_p0_13_bool_as_credential_version_rejected():
    p = proposal()
    p["credential_version"] = True
    assert "P0_CREDENTIAL_VERSION_INVALID" in check(p)["format_blockers"]


def test_p0_14_invalid_nonce_rejected():
    p = proposal()
    p["challenge_nonce"] = "short"
    assert "P0_ENROLLMENT_NONCE_INVALID" in check(p)["format_blockers"]


def test_p0_15_expired_claim_is_rejected():
    p = proposal()
    p["issued_at"] = "2026-10-19T17:55:00Z"
    p["expires_at"] = "2026-10-19T17:56:00Z"
    assert "P0_ENROLLMENT_EXPIRED" in check(p)["format_blockers"]


def test_p0_16_long_validity_window_rejected():
    p = proposal()
    p["issued_at"] = "2026-10-19T17:54:00Z"
    assert "P0_ENROLLMENT_WINDOW_INVALID" in check(p)["format_blockers"]


def test_p0_17_future_issued_at_rejected():
    p = proposal()
    p["issued_at"] = "2026-10-19T18:00:01Z"
    assert "P0_ENROLLMENT_FROM_FUTURE" in check(p)["format_blockers"]


@pytest.mark.parametrize("intent", ["RECOVER", "ROTATE", "REVOKE"])
def test_p0_18_to_20_recovery_rotation_revocation_need_separate_ceremony(intent):
    p = proposal()
    p["intent"] = intent
    assert "P0_OWNER_TRANSITION_NOT_APPROVED" in check(p)["format_blockers"]


def test_p0_21_webauthn_label_alone_never_proves_platform_attestation():
    p = proposal()
    p["credential_kind"] = "WEBAUTHN_PENDING_ADAPTER"
    result = check(p)
    assert result["format_consistent"] is True
    assert result["owner_identity_verified"] is False


def test_p0_22_attempted_replay_is_never_automatically_enrolled():
    p = proposal()
    a = check(p)
    b = check(p)
    assert a["state"] == b["state"] == "BLOCKED"
    # Stateless LAB cannot claim independently verified replay prevention.


def test_p0_23_missing_payload_blocks():
    result = inspect_untrusted_owner_enrollment(None, **PARAMS)
    assert result["state"] == "BLOCKED"
    assert "P0_ENROLLMENT_ENVELOPE_REQUIRED" in result["format_blockers"]


def test_p0_24_unknown_credential_kind_blocks():
    p = proposal()
    p["credential_kind"] = "PASSWORD_FROM_CHAT"
    assert "P0_CREDENTIAL_KIND_UNSUPPORTED" in check(p)["format_blockers"]


def test_p0_25_non_utc_timestamps_rejected():
    p = proposal()
    p["expires_at"] = "2026-10-19T18:01:00-04:00"
    assert "P0_ENROLLMENT_TIME_INVALID" in check(p)["format_blockers"]


def test_p0_26_bad_public_key_fingerprint_rejected():
    p = proposal()
    p["public_key_fingerprint"] = "sha256:" + "g" * 64
    assert "P0_PUBLIC_KEY_FINGERPRINT_INVALID" in check(p)["format_blockers"]


def test_p0_27_custodian_name_is_just_claim_even_when_well_formed():
    p = proposal()
    p["proposed_custodian_id"] = "fake-custodian-1234"
    r = check(p)
    assert r["format_consistent"] is True
    assert r["independent_custody_verified"] is False
