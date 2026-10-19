"""WebAuthn ES256 signed assertion adversarial contracts (P0 / LAB).

EPHEMERAL generated fixture credential is not a real passkey and does NOT
establish HUMAN_OWNER. Even an intact signed assertion returns BLOCKED.
No browser, RP server, real user, biometric, Windows Hello, Android or provider.
"""
import base64
from copy import deepcopy
import hashlib
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from atlasquant_aion_p0_webauthn_assertion_lab import (
    inspect_owner_webauthn_assertion_lab,
)

RP_ID = "atlasquant.invalid"
ORIGIN = "https://atlasquant.invalid"
NOW = "2026-10-19T18:00:00Z"


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def sample():
    secret = ec.generate_private_key(ec.SECP256R1())
    pub = secret.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    ctx = {
        "credential_id": "owner-credential-lab-001",
        "owner_id": "HUMAN_OWNER",
        "tenant_id": "atlasquant-owner",
        "workspace_id": "owner-workspace-lab",
        "rp_id": RP_ID,
        "origin": ORIGIN,
        "challenge_b64": b64(b"x" * 32),
        "issued_at": "2026-10-19T17:59:30Z",
        "expires_at": "2026-10-19T18:01:30Z",
    }
    pin = {
        "credential_id": ctx["credential_id"],
        "owner_id": ctx["owner_id"],
        "tenant_id": ctx["tenant_id"],
        "workspace_id": ctx["workspace_id"],
        "public_key_sec1_b64": b64(pub),
        "status": "ACTIVE",
        "stored_sign_count": 7,
    }
    return {"private": secret, "ctx": ctx, "pin": pin}


def make_assertion(s, *, flags=0x05, count=8, client=None,
                   rp_id=RP_ID, raw_client=None, auth_suffix=b""):
    client = client or {
        "type": "webauthn.get",
        "challenge": s["ctx"]["challenge_b64"],
        "origin": ORIGIN,
    }
    client_raw = (
        raw_client if raw_client is not None
        else json.dumps(client, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    auth = hashlib.sha256(rp_id.encode()).digest() + bytes([flags]) + count.to_bytes(4, "big") + auth_suffix
    signature = s["private"].sign(
        auth + hashlib.sha256(client_raw).digest(), ec.ECDSA(hashes.SHA256())
    )
    return {
        "credential_id": s["ctx"]["credential_id"],
        "client_data_json_b64": b64(client_raw),
        "authenticator_data_b64": b64(auth),
        "signature_b64": b64(signature),
    }


def evaluate(s, assertion=None, *, pin=None, ctx=None, seen=frozenset(), now=NOW):
    assertion = assertion if assertion is not None else make_assertion(s)
    pin = pin if pin is not None else s["pin"]
    ctx = ctx if ctx is not None else s["ctx"]
    before = (deepcopy(assertion), deepcopy(pin), deepcopy(ctx))
    result = inspect_owner_webauthn_assertion_lab(
        assertion, pinned_credential=pin, expected=ctx,
        used_challenges=seen, now=now
    )
    assert before == (assertion, pin, ctx)
    assert result["state"] == "BLOCKED"
    for key in (
        "owner_identity_verified", "real_device_custody_verified",
        "independent_enrollment_verified", "nonce_durably_consumed",
        "counter_atomically_persisted", "owner_authenticated",
        "owner_decision_authorized", "worker_armed",
        "external_action_executed", "executes_action",
    ):
        assert result[key] is False, key
    return result


def reason(s, wanted, assertion=None, **kwargs):
    result = evaluate(s, assertion, **kwargs)
    assert result["reason"] == wanted, result
    return result


def test_01_valid_es256_assertion_remains_not_owner_identity(sample):
    result = reason(sample, "P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED")
    assert result["signature_checked"] is True
    assert result["owner_authenticated"] is False


def test_02_wrong_signing_key(sample):
    other = ec.generate_private_key(ec.SECP256R1())
    claim = make_assertion(sample)
    client_raw = base64.urlsafe_b64decode(claim["client_data_json_b64"] + "==")
    auth_raw = base64.urlsafe_b64decode(claim["authenticator_data_b64"] + "==")
    claim["signature_b64"] = b64(
        other.sign(auth_raw + hashlib.sha256(client_raw).digest(), ec.ECDSA(hashes.SHA256()))
    )
    reason(sample, "P0_ASSERTION_SIGNATURE_INVALID", claim)


def test_03_tampered_original_client_bytes_break_signature(sample):
    claim = make_assertion(sample)
    original = base64.urlsafe_b64decode(claim["client_data_json_b64"] + "==")
    claim["client_data_json_b64"] = b64(original.replace(b":", b": ", 1))
    reason(sample, "P0_ASSERTION_SIGNATURE_INVALID", claim)


def test_04_bad_origin(sample):
    claim = make_assertion(sample, client={
        "type": "webauthn.get", "challenge": sample["ctx"]["challenge_b64"],
        "origin": "https://evil.invalid",
    })
    reason(sample, "P0_ORIGIN_MISMATCH", claim)


def test_05_bad_rp_id_hash(sample):
    reason(sample, "P0_RP_ID_HASH_MISMATCH", make_assertion(sample, rp_id="evil.invalid"))


def test_06_challenge_replaced(sample):
    claim = make_assertion(sample, client={
        "type": "webauthn.get", "challenge": b64(b"a" * 32), "origin": ORIGIN
    })
    reason(sample, "P0_CHALLENGE_MISMATCH", claim)


@pytest.mark.parametrize("flags", [0x04, 0x01, 0x00])
def test_07_to_09_up_uv_required(sample, flags):
    reason(sample, "P0_USER_PRESENCE_OR_VERIFICATION_MISSING",
           make_assertion(sample, flags=flags))


def test_10_swapped_credential_id(sample):
    claim = make_assertion(sample)
    claim["credential_id"] = "attacker-key"
    reason(sample, "P0_CREDENTIAL_ID_MISMATCH", claim)


@pytest.mark.parametrize("name", ["owner_id", "tenant_id", "workspace_id"])
def test_11_to_13_cross_scope(sample, name):
    pin = deepcopy(sample["pin"])
    pin[name] = "other-scope"
    reason(sample, "P0_CREDENTIAL_SCOPE_MISMATCH", pin=pin)


def test_14_revoked_credential_denied(sample):
    pin = deepcopy(sample["pin"])
    pin["status"] = "REVOKED"
    reason(sample, "P0_CREDENTIAL_NOT_ACTIVE", pin=pin)


def test_15_challenge_used_denied(sample):
    reason(sample, "P0_CHALLENGE_REPLAYED",
           seen=frozenset({sample["ctx"]["challenge_b64"]}))


def test_16_missing_durable_nonce_state_denied(sample):
    reason(sample, "P0_REPLAY_REGISTRY_UNAVAILABLE", seen=None)


@pytest.mark.parametrize(("start", "end", "wanted"), [
    ("2026-10-19T17:00:00Z", "2026-10-19T17:01:00Z", "P0_CHALLENGE_TIME_INVALID"),
    ("2026-10-19T18:00:01Z", "2026-10-19T18:01:01Z", "P0_CHALLENGE_TIME_INVALID"),
    ("2026-10-19T17:53:00Z", "2026-10-19T18:01:30Z", "P0_CHALLENGE_TIME_INVALID"),
    ("2026-10-19T17:59:30-04:00", "2026-10-19T18:01:30Z", "P0_TIME_INVALID"),
])
def test_17_to_20_invalid_time_window(sample, start, end, wanted):
    ctx = deepcopy(sample["ctx"])
    ctx.update(issued_at=start, expires_at=end)
    reason(sample, wanted, ctx=ctx)


def test_21_counter_rollback_denied(sample):
    reason(sample, "P0_SIGN_COUNTER_NONMONOTONIC", make_assertion(sample, count=6))


def test_22_counter_same_denied(sample):
    reason(sample, "P0_SIGN_COUNTER_NONMONOTONIC", make_assertion(sample, count=7))


def test_23_zero_counter_diagnostic_only_not_clone_proof(sample):
    assert reason(sample, "P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED",
                  make_assertion(sample, count=0))["owner_authenticated"] is False


def test_24_synced_backup_flags_diagnostic_only(sample):
    assert reason(sample, "P0_CRYPTO_VALID_BUT_REAL_OWNER_BOOTSTRAP_UNVERIFIED",
                  make_assertion(sample, flags=0x1D))["owner_authenticated"] is False


def test_25_backup_state_without_eligibility_denied(sample):
    reason(sample, "P0_AUTHENTICATOR_FLAGS_UNSUPPORTED",
           make_assertion(sample, flags=0x15))


@pytest.mark.parametrize("flags", [0x45, 0x85])
def test_26_to_27_extension_and_attested_data_flags_denied(sample, flags):
    reason(sample, "P0_AUTHENTICATOR_FLAGS_UNSUPPORTED",
           make_assertion(sample, flags=flags))


def test_28_cross_origin_claim_denied(sample):
    claim = make_assertion(sample, client={
        "type": "webauthn.get", "challenge": sample["ctx"]["challenge_b64"],
        "origin": ORIGIN, "crossOrigin": True,
    })
    reason(sample, "P0_CROSS_ORIGIN_DENIED", claim)


def test_29_mismatched_operation_type_denied(sample):
    claim = make_assertion(sample, client={
        "type": "webauthn.create", "challenge": sample["ctx"]["challenge_b64"],
        "origin": ORIGIN,
    })
    reason(sample, "P0_ASSERTION_TYPE_INVALID", claim)


def test_30_extra_claim_of_authority_denied(sample):
    claim = make_assertion(sample)
    claim["owner_identity_verified"] = True
    reason(sample, "P0_ASSERTION_SHAPE_INVALID", claim)


def test_31_json_duplicate_key_denied(sample):
    raw = (
        '{"type":"webauthn.get","type":"webauthn.get","challenge":"'
        + sample["ctx"]["challenge_b64"] + '","origin":"' + ORIGIN + '"}'
    ).encode()
    reason(sample, "P0_CLIENT_DATA_MALFORMED",
           make_assertion(sample, raw_client=raw))


def test_32_unsupported_client_data_extension_denied(sample):
    claim = make_assertion(sample, client={
        "type": "webauthn.get", "challenge": sample["ctx"]["challenge_b64"],
        "origin": ORIGIN, "topOrigin": ORIGIN,
    })
    reason(sample, "P0_CLIENT_DATA_EXTENSION_UNSUPPORTED", claim)


def test_33_wrong_expected_origin_policy_denied(sample):
    ctx = deepcopy(sample["ctx"])
    ctx["origin"] = "http://" + RP_ID
    reason(sample, "P0_ORIGIN_POLICY_INVALID", ctx=ctx)


def test_34_wrong_expected_rp_id_denied(sample):
    ctx = deepcopy(sample["ctx"])
    ctx["rp_id"] = "https://atlasquant.invalid"
    reason(sample, "P0_RP_ID_INVALID", ctx=ctx)


def test_35_missing_pinned_credential(sample):
    reason(sample, "P0_CREDENTIAL_RECORD_UNAVAILABLE", pin={})


def test_36_fake_pinned_public_key_rejected(sample):
    pin = deepcopy(sample["pin"])
    other = ec.generate_private_key(ec.SECP256R1())
    pin["public_key_sec1_b64"] = b64(other.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    ))
    reason(sample, "P0_ASSERTION_SIGNATURE_INVALID", pin=pin)


def test_37_client_data_b64_invalid(sample):
    claim = make_assertion(sample)
    claim["client_data_json_b64"] = "not+canonical"
    reason(sample, "P0_CLIENT_DATA_MALFORMED", claim)


def test_38_authenticator_data_extra_bytes_rejected(sample):
    reason(sample, "P0_AUTHENTICATOR_DATA_INVALID",
           make_assertion(sample, auth_suffix=b"unexpected"))


def test_39_bogus_stored_counter_state_rejected(sample):
    pin = deepcopy(sample["pin"])
    pin["stored_sign_count"] = True
    reason(sample, "P0_COUNTER_STATE_INVALID", pin=pin)


def test_40_test_fixture_repeated_with_empty_replay_state_stays_denied(sample):
    claim = make_assertion(sample)
    a = evaluate(sample, claim)
    b = evaluate(sample, claim)
    assert a["signature_checked"] and b["signature_checked"]
    assert not a["nonce_durably_consumed"] and not b["nonce_durably_consumed"]
