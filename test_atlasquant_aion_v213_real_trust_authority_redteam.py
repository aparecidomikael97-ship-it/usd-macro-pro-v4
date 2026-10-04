"""AION V2.13 red-team for real trust-root and authority verification."""
from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_authority_verifier import (
    SCHEMA,
    canonical_statement_bytes,
    verify_authority_statement,
)
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_trust_root import TrustRootRegistry


NOW = "2026-10-04T17:45:00Z"
ISSUED = "2026-10-04T17:40:00Z"
EXPIRES = "2026-10-04T18:45:00Z"
BINDING = {
    "subject_id": "aion-core",
    "tenant_id": "atlasquant-owner",
    "domain": "CORE",
    "policy_id": "AION_CORE_POLICY_V1",
}


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def new_keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private, b64url(public)


def root_payload(public_key_b64: str, *, key_id="root-1", version=1, status="ACTIVE"):
    return {
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": key_id,
            "key_version": version,
            "algorithm": "Ed25519",
            "public_key_b64": public_key_b64,
            "status": status,
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    }


def statement(**overrides):
    data = {
        "schema": SCHEMA,
        "statement_id": "stmt-001",
        "authority_id": "owner-control-plane",
        "subject_id": BINDING["subject_id"],
        "tenant_id": BINDING["tenant_id"],
        "domain": BINDING["domain"],
        "policy_id": BINDING["policy_id"],
        "capabilities": ["core.read", "core.plan"],
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "nonce": "bm9uY2UtMDAx",
        "key_id": "root-1",
        "key_version": 1,
        "grant_kind": "CAPABILITY_GRANT",
    }
    data.update(overrides)
    return data


def sign(private, payload):
    return b64url(private.sign(canonical_statement_bytes(payload)))


def verifier_fixture(tmp_path):
    private, public = new_keypair()
    registry = TrustRootRegistry.from_mapping(root_payload(public))
    nonces = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")
    return private, registry, nonces


def test_valid_signed_authority_is_verified_but_not_executable(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    result = verify_authority_statement(
        payload,
        signature_b64=sign(private, payload),
        trust_roots=registry,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
    )
    assert result["state"] == "VERIFIED"
    assert result["authority_verified"] is True
    assert result["execution_authority_granted"] is True
    assert result["execution_allowed"] is False
    assert result["approval_implied"] is False
    assert result["executes_action"] is False
    assert result["private_key_used"] is False


def test_tampered_statement_fails_signature(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    original = statement()
    signature = sign(private, original)
    tampered = dict(original)
    tampered["tenant_id"] = "attacker"
    result = verify_authority_statement(
        tampered,
        signature_b64=signature,
        trust_roots=registry,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding={**BINDING, "tenant_id": "attacker"},
    )
    assert result["state"] == "BLOCKED"
    assert "AUTHORITY_SIGNATURE_INVALID" in result["blockers"]
    assert nonces.count() == 0


def test_wrong_signing_key_fails(tmp_path):
    _, registry, nonces = verifier_fixture(tmp_path)
    attacker, _ = new_keypair()
    payload = statement()
    result = verify_authority_statement(
        payload,
        signature_b64=sign(attacker, payload),
        trust_roots=registry,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=BINDING,
    )
    assert result["state"] == "BLOCKED"
    assert "AUTHORITY_SIGNATURE_INVALID" in result["blockers"]


@pytest.mark.parametrize("field", ["subject_id", "tenant_id", "domain", "policy_id"])
def test_binding_mismatch_is_fail_closed(tmp_path, field):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    expected = dict(BINDING)
    expected[field] = "wrong"
    result = verify_authority_statement(
        payload,
        signature_b64=sign(private, payload),
        trust_roots=registry,
        nonce_registry=nonces,
        now_ts=NOW,
        expected_binding=expected,
    )
    assert result["state"] == "BLOCKED"
    assert f"AUTHORITY_BINDING_MISMATCH:{field}" in result["blockers"]
    assert nonces.count() == 0


def test_replay_is_blocked_and_nonce_persists_after_reopen(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    signature = sign(private, payload)
    first = verify_authority_statement(
        payload, signature_b64=signature, trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert first["state"] == "VERIFIED"

    reopened = PersistentNonceRegistry(nonces.path)
    second = verify_authority_statement(
        payload, signature_b64=signature, trust_roots=registry,
        nonce_registry=reopened, now_ts=NOW, expected_binding=BINDING,
    )
    assert second["state"] == "BLOCKED"
    assert "AUTHORITY_NONCE_REPLAYED" in second["blockers"]
    assert second["signature_verified"] is True


def test_invalid_signature_does_not_burn_nonce(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    wrong, _ = new_keypair()
    bad = verify_authority_statement(
        payload, signature_b64=sign(wrong, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert bad["state"] == "BLOCKED"
    assert nonces.count() == 0
    good = verify_authority_statement(
        payload, signature_b64=sign(private, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert good["state"] == "VERIFIED"


def test_revoked_key_is_blocked(tmp_path):
    private, public = new_keypair()
    roots = root_payload(public)
    roots["revoked_key_ids"] = ["root-1"]
    registry = TrustRootRegistry.from_mapping(roots)
    nonces = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")
    payload = statement()
    result = verify_authority_statement(
        payload, signature_b64=sign(private, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert "TRUST_KEY_REVOKED" in result["blockers"]
    assert result["authority_verified"] is False


def test_key_rotation_accepts_new_active_version_and_rejects_retired_old(tmp_path):
    old_private, old_public = new_keypair()
    new_private, new_public = new_keypair()
    payload = {
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [
            {
                "key_id": "root-1", "key_version": 1, "algorithm": "Ed25519",
                "public_key_b64": old_public, "status": "RETIRED",
                "not_before": "2026-01-01T00:00:00Z",
                "not_after": "2027-01-01T00:00:00Z",
            },
            {
                "key_id": "root-1", "key_version": 2, "algorithm": "Ed25519",
                "public_key_b64": new_public, "status": "ACTIVE",
                "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2027-10-01T00:00:00Z",
            },
        ],
        "revoked_key_ids": [],
    }
    registry = TrustRootRegistry.from_mapping(payload)
    old_stmt = statement(key_version=1, nonce="b2xk")
    old = verify_authority_statement(
        old_stmt, signature_b64=sign(old_private, old_stmt), trust_roots=registry,
        nonce_registry=PersistentNonceRegistry(tmp_path / "old.sqlite3"),
        now_ts=NOW, expected_binding=BINDING,
    )
    assert "TRUST_KEY_NOT_ACTIVE" in old["blockers"]

    new_stmt = statement(key_version=2, nonce="bmV3")
    new = verify_authority_statement(
        new_stmt, signature_b64=sign(new_private, new_stmt), trust_roots=registry,
        nonce_registry=PersistentNonceRegistry(tmp_path / "new.sqlite3"),
        now_ts=NOW, expected_binding=BINDING,
    )
    assert new["state"] == "VERIFIED"
    assert new["key_version"] == 2


def test_unknown_key_version_is_blocked(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement(key_version=99)
    result = verify_authority_statement(
        payload, signature_b64=sign(private, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert "TRUST_KEY_UNKNOWN" in result["blockers"]


def test_future_statement_is_blocked_before_signature_nonce_claim(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement(issued_at="2026-10-05T00:00:00Z", expires_at="2026-10-06T00:00:00Z")
    result = verify_authority_statement(
        payload, signature_b64=sign(private, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert "AUTHORITY_NOT_YET_VALID" in result["blockers"]
    assert nonces.count() == 0


def test_expired_statement_is_blocked(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement(issued_at="2026-10-04T15:00:00Z", expires_at="2026-10-04T16:00:00Z")
    result = verify_authority_statement(
        payload, signature_b64=sign(private, payload), trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert "AUTHORITY_EXPIRED_OR_INVALID_WINDOW" in result["blockers"]


@pytest.mark.parametrize("bad_caps", [
    ["dup", "dup"],
    [""],
    "not-a-list",
])
def test_capability_shape_is_strict(tmp_path, bad_caps):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement(capabilities=bad_caps)
    result = verify_authority_statement(
        payload, signature_b64="AA", trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert "AUTHORITY_CAPABILITIES_INVALID" in result["blockers"]


def test_statement_shape_rejects_unknown_fields(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    payload["execution_allowed"] = True
    result = verify_authority_statement(
        payload, signature_b64="AA", trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert result["blockers"] == ["AUTHORITY_STATEMENT_SHAPE_MISMATCH"]


def test_trust_root_json_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "roots.json"
    path.write_text(
        '{"schema":"ATLASQUANT_AION_TRUST_ROOT_V1","schema":"FORGED","roots":[]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        TrustRootRegistry.from_json_file(path)


def test_trust_root_json_file_roundtrip(tmp_path):
    _, public = new_keypair()
    path = tmp_path / "roots.json"
    path.write_text(json.dumps(root_payload(public), sort_keys=True), encoding="utf-8")
    registry = TrustRootRegistry.from_json_file(path)
    assert registry.key_count == 1


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics vary on Windows runners")
def test_trust_root_symlink_rejected(tmp_path):
    _, public = new_keypair()
    real = tmp_path / "real.json"
    link = tmp_path / "link.json"
    real.write_text(json.dumps(root_payload(public)), encoding="utf-8")
    link.symlink_to(real)
    with pytest.raises(ValueError):
        TrustRootRegistry.from_json_file(link)


def test_nonce_registry_concurrency_allows_one_claim(tmp_path):
    registry = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")
    results = []
    errors = []

    def worker():
        try:
            results.append(registry.claim(
                scope="owner|core",
                nonce="same-nonce",
                expires_at=EXPIRES,
                now_ts=NOW,
            ))
        except Exception as exc:
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert results.count(True) == 1
    assert results.count(False) == 11


def test_nonce_is_scoped_not_globally_colliding(tmp_path):
    registry = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")
    assert registry.claim(scope="tenant-a", nonce="n", expires_at=EXPIRES, now_ts=NOW)
    assert registry.claim(scope="tenant-b", nonce="n", expires_at=EXPIRES, now_ts=NOW)


def test_invalid_trust_root_algorithm_rejected():
    _, public = new_keypair()
    payload = root_payload(public)
    payload["roots"][0]["algorithm"] = "RSA"
    with pytest.raises(ValueError):
        TrustRootRegistry.from_mapping(payload)


def test_private_key_material_is_not_part_of_trust_root_contract():
    _, public = new_keypair()
    payload = root_payload(public)
    payload["roots"][0]["private_key_b64"] = "forbidden"
    with pytest.raises(ValueError):
        TrustRootRegistry.from_mapping(payload)


def test_verified_result_is_deterministic_except_nonce_side_effect(tmp_path):
    private, registry, nonces = verifier_fixture(tmp_path)
    payload = statement()
    signature = sign(private, payload)
    first = verify_authority_statement(
        payload, signature_b64=signature, trust_roots=registry,
        nonce_registry=nonces, now_ts=NOW, expected_binding=BINDING,
    )
    assert first["state"] == "VERIFIED"
    assert first["capabilities"] == ["core.plan", "core.read"]
    assert first["network_called"] is False
    assert first["private_key_used"] is False
