"""AION V2.24 owner signature ceremony red-team."""
from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_signature_ceremony import (
    EXPECTED_OWNER_ID,
    EXPECTED_TENANT_ID,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    SIGNATURE_MECHANISM,
    SIGNATURE_PURPOSE,
    build_owner_signature_request,
    canonical_owner_signature_bytes,
    verify_owner_signature,
)
from atlasquant_aion_trust_root import TrustRootRegistry
from test_atlasquant_aion_v222_core_freeze_preflight import (
    NOW,
    TARGET,
    TRUST_ROOTS,
    certification_manifest,
)
from test_atlasquant_aion_v223_external_persistence_attestation import (
    receipt_for,
    runtime_result,
    staged_runtime,
)


ISSUED = "2026-10-04T19:59:30Z"
EXPIRES = "2026-10-04T20:02:00Z"
CEREMONY_ID = "owner-signature-ceremony-001"
NONCE = "owner_signature_nonce_0001"
OWNER_KEY_ID = "owner-root-1"
OWNER_KEY_VERSION = 1


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def owner_keypair(*, key_id=OWNER_KEY_ID, version=OWNER_KEY_VERSION, status="ACTIVE"):
    secret = Ed25519PrivateKey.generate()
    public = secret.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    registry = TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": key_id,
            "key_version": version,
            "algorithm": "Ed25519",
            "public_key_b64": b64url(public),
            "status": status,
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    })
    return secret, registry


def evidence():
    master, preflight, staged = staged_runtime()
    runtime_checkpoint = staged["runtime_checkpoint_candidate"]
    return {
        "checkpoint_master": master,
        "preflight": preflight,
        "certification_manifest": certification_manifest(),
        "certification_trust_roots": TRUST_ROOTS,
        "expected_target_commit_sha": TARGET,
        "runtime_result": runtime_result(runtime_checkpoint),
        "write_receipt": receipt_for(runtime_checkpoint),
        "runtime_checkpoint": runtime_checkpoint,
    }


def request_for(owner_roots, **overrides):
    e = evidence()
    kwargs = {
        **{k: v for k, v in e.items() if k != "runtime_checkpoint"},
        "owner_trust_roots": owner_roots,
        "now_ts": NOW,
        "ceremony_id": CEREMONY_ID,
        "nonce": NONCE,
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
        "key_id": OWNER_KEY_ID,
        "key_version": OWNER_KEY_VERSION,
    }
    kwargs.update(overrides)
    built = build_owner_signature_request(**kwargs)
    return e, built


def verify(request, signature, owner_roots, nonce_registry, e=None, **overrides):
    e = e or evidence()
    kwargs = {
        "request": request,
        "signature_b64": signature,
        "owner_trust_roots": owner_roots,
        "nonce_registry": nonce_registry,
        "checkpoint_master": e["checkpoint_master"],
        "preflight": e["preflight"],
        "certification_manifest": e["certification_manifest"],
        "certification_trust_roots": e["certification_trust_roots"],
        "expected_target_commit_sha": e["expected_target_commit_sha"],
        "runtime_result": e["runtime_result"],
        "write_receipt": e["write_receipt"],
        "now_ts": NOW,
    }
    kwargs.update(overrides)
    return verify_owner_signature(**kwargs)


def sign(secret, request):
    return b64url(secret.sign(canonical_owner_signature_bytes(request)))


def test_request_is_exact_state_bound_and_not_a_decision():
    _, owner_roots = owner_keypair()
    _, built = request_for(owner_roots)
    assert built["state"] == "READY_FOR_EXTERNAL_OWNER_SIGNATURE"
    assert built["request"]["schema"] == REQUEST_SCHEMA
    assert built["request"]["owner_id"] == EXPECTED_OWNER_ID
    assert built["request"]["tenant_id"] == EXPECTED_TENANT_ID
    assert built["request"]["signature_purpose"] == SIGNATURE_PURPOSE
    assert built["request"]["signature_mechanism"] == SIGNATURE_MECHANISM
    assert built["request"]["owner_public_key_fingerprint"].startswith("sha256:")
    assert built["request"]["owner_decision"] == "UNDECIDED"
    assert built["request"]["core_freeze_authorized"] is False
    assert built["request"]["execution_allowed"] is False
    assert built["digest_to_sign"] == built["request_digest"]
    assert built["owner_signature_verified"] is False
    assert built["owner_decision_ready"] is False
    assert built["signature_capture_performed"] is False
    assert built["core_frozen"] is False
    assert built["external_action_executed"] is False
    assert built["network_called"] is False


def test_valid_external_owner_signature_makes_decision_ready_but_not_decided(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    nonces = PersistentNonceRegistry(tmp_path / "owner_nonce.sqlite3")
    result = verify(
        built["request"],
        sign(secret, built["request"]),
        owner_roots,
        nonces,
        e=e,
    )
    assert result["schema"] == RESULT_SCHEMA
    assert result["state"] == "READY_FOR_EXPLICIT_OWNER_DECISION"
    assert result["owner_signature_verified"] is True
    assert result["owner_identity_verified"] is True
    assert result["state_binding_verified"] is True
    assert result["nonce_registered"] is True
    assert result["owner_decision_ready"] is True
    assert result["owner_decision"] == "UNDECIDED"
    assert result["approval_implied"] is False
    assert result["signature_capture_performed"] is False
    assert result["signature_performed_by_this_module"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["checkpoint_saved"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["external_action_executed"] is False
    assert result["network_called"] is False
    assert result["executes_action"] is False
    assert result["generic_chat_instruction_accepted_as_signature"] is False


def test_plain_chat_text_never_counts_as_signature(tmp_path):
    _, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    nonces = PersistentNonceRegistry(tmp_path / "owner_nonce.sqlite3")
    result = verify(
        built["request"],
        "vamos lá",
        owner_roots,
        nonces,
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_INVALID" in result["blockers"]
    assert result["owner_decision_ready"] is False
    assert result["core_freeze_authorized"] is False
    assert nonces.count() == 0


def test_signature_replay_is_blocked_durably(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    path = tmp_path / "owner_nonce.sqlite3"
    nonces = PersistentNonceRegistry(path)
    signature = sign(secret, built["request"])
    first = verify(built["request"], signature, owner_roots, nonces, e=e)
    assert first["state"] == "READY_FOR_EXPLICIT_OWNER_DECISION"

    reopened = PersistentNonceRegistry(path)
    second = verify(built["request"], signature, owner_roots, reopened, e=e)
    assert second["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_NONCE_REPLAYED" in second["blockers"]
    assert second["owner_decision_ready"] is False


def test_same_key_id_version_with_different_public_key_is_rebuild_blocked(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    _, swapped_roots = owner_keypair()
    result = verify(
        built["request"],
        sign(secret, built["request"]),
        swapped_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH" in result["blockers"]


def test_wrong_signing_key_is_blocked(tmp_path):
    _, owner_roots = owner_keypair()
    attacker = Ed25519PrivateKey.generate()
    e, built = request_for(owner_roots)
    result = verify(
        built["request"],
        sign(attacker, built["request"]),
        owner_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_INVALID" in result["blockers"]


@pytest.mark.parametrize("status,expected", [
    ("REVOKED", "OWNER_TRUST_KEY_REVOKED"),
    ("RETIRED", "OWNER_TRUST_KEY_NOT_ACTIVE"),
])
def test_revoked_or_retired_owner_key_blocks_request(status, expected):
    _, owner_roots = owner_keypair(status=status)
    _, built = request_for(owner_roots)
    assert built["state"] == "BLOCKED"
    assert expected in built["blockers"]


def test_unknown_owner_key_blocks_request():
    _, owner_roots = owner_keypair(key_id="other-owner-root")
    _, built = request_for(owner_roots)
    assert built["state"] == "BLOCKED"
    assert "OWNER_TRUST_KEY_UNKNOWN" in built["blockers"]


def test_tampered_v223_digest_is_rebuild_blocked_even_if_owner_key_signs_it(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    forged = deepcopy(built["request"])
    forged["v223_digest_to_sign"] = "sha256:" + "9" * 64
    result = verify(
        forged,
        sign(secret, forged),
        owner_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH" in result["blockers"]


def test_tampered_runtime_sha_is_rebuild_blocked_even_if_signed(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    forged = deepcopy(built["request"])
    forged["v223_runtime_sha"] = "c" * 40
    result = verify(
        forged,
        sign(secret, forged),
        owner_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH" in result["blockers"]


@pytest.mark.parametrize("field,value,blocker", [
    ("owner_id", "OTHER_OWNER", "OWNER_SIGNATURE_OWNER_ID_MISMATCH"),
    ("tenant_id", "other-tenant", "OWNER_SIGNATURE_TENANT_ID_MISMATCH"),
    ("signature_purpose", "APPROVE_CORE_FREEZE", "OWNER_SIGNATURE_PURPOSE_INVALID"),
    ("signature_mechanism", "CHAT_TEXT", "OWNER_SIGNATURE_MECHANISM_INVALID"),
    ("owner_decision", "APPROVE", "OWNER_DECISION_MUST_REMAIN_UNDECIDED"),
    ("core_freeze_authorized", True, "OWNER_SIGNATURE_UNSAFE_FIELD:core_freeze_authorized"),
    ("core_frozen", True, "OWNER_SIGNATURE_UNSAFE_FIELD:core_frozen"),
    ("execution_allowed", True, "OWNER_SIGNATURE_UNSAFE_FIELD:execution_allowed"),
    ("worker_armed", True, "OWNER_SIGNATURE_UNSAFE_FIELD:worker_armed"),
    ("external_action_executed", True, "OWNER_SIGNATURE_UNSAFE_FIELD:external_action_executed"),
])
def test_unsafe_or_semantically_wrong_request_fields_block_before_nonce(
    tmp_path, field, value, blocker
):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    forged = deepcopy(built["request"])
    forged[field] = value
    nonces = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")
    result = verify(forged, sign(secret, forged), owner_roots, nonces, e=e)
    assert result["state"] == "BLOCKED"
    assert blocker in result["blockers"]
    assert nonces.count() == 0


def test_request_shape_is_exact(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    forged = deepcopy(built["request"])
    forged["surprise"] = True
    result = verify(
        forged,
        sign(secret, forged),
        owner_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["OWNER_SIGNATURE_REQUEST_SHAPE_MISMATCH"]


def test_expired_signature_window_blocks_build():
    _, owner_roots = owner_keypair()
    _, built = request_for(
        owner_roots,
        issued_at="2026-10-04T19:55:00Z",
        expires_at="2026-10-04T19:59:59Z",
    )
    assert built["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_EXPIRED" in built["blockers"]
    assert built["request"] == {}


def test_signature_window_too_long_blocks_build():
    _, owner_roots = owner_keypair()
    _, built = request_for(
        owner_roots,
        issued_at="2026-10-04T19:59:00Z",
        expires_at="2026-10-04T20:10:00Z",
    )
    assert built["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_WINDOW_TOO_LONG" in built["blockers"]


def test_future_signature_window_blocks_build():
    _, owner_roots = owner_keypair()
    _, built = request_for(
        owner_roots,
        issued_at="2026-10-04T20:00:01Z",
        expires_at="2026-10-04T20:02:00Z",
    )
    assert built["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_NOT_YET_VALID" in built["blockers"]


def test_stale_runtime_evidence_blocks_signature_request():
    _, owner_roots = owner_keypair()
    e = evidence()
    e["runtime_result"]["checked_at"] = "2026-10-04T19:54:00+00:00"
    built = build_owner_signature_request(
        **{k: v for k, v in e.items() if k != "runtime_checkpoint"},
        owner_trust_roots=owner_roots,
        now_ts=NOW,
        ceremony_id=CEREMONY_ID,
        nonce=NONCE,
        issued_at=ISSUED,
        expires_at=EXPIRES,
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert built["state"] == "BLOCKED"
    assert "V223_PERSISTENCE_ATTESTATION_NOT_READY" in built["blockers"]
    assert any(
        item == "V223:RUNTIME_OBSERVATION_STALE"
        for item in built["blockers"]
    )


def test_changed_runtime_evidence_after_request_blocks_verification(tmp_path):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    changed = deepcopy(e)
    changed["runtime_result"] = deepcopy(e["runtime_result"])
    changed["runtime_result"]["sha"] = "c" * 40
    result = verify(
        built["request"],
        sign(secret, built["request"]),
        owner_roots,
        PersistentNonceRegistry(tmp_path / "nonce.sqlite3"),
        e=changed,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_REQUEST_REBUILD_BLOCKED" in result["blockers"]


def test_nonce_registry_failure_fails_closed(tmp_path, monkeypatch):
    secret, owner_roots = owner_keypair()
    e, built = request_for(owner_roots)
    nonces = PersistentNonceRegistry(tmp_path / "nonce.sqlite3")

    def explode(**kwargs):
        raise OSError("synthetic durable-store failure")

    monkeypatch.setattr(nonces, "claim", explode)
    result = verify(
        built["request"],
        sign(secret, built["request"]),
        owner_roots,
        nonces,
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE" in result["blockers"]
    assert result["owner_signature_verified"] is True
    assert result["owner_decision_ready"] is False


def test_request_digest_changes_when_nonce_or_ceremony_changes():
    _, owner_roots = owner_keypair()
    _, a = request_for(owner_roots)
    _, b = request_for(
        owner_roots,
        ceremony_id="owner-signature-ceremony-002",
        nonce="owner_signature_nonce_0002",
    )
    assert a["request_digest"] != b["request_digest"]


def test_owner_signature_source_has_no_capture_network_freeze_merge_or_deploy_action():
    source = Path(
        "atlasquant_aion_owner_signature_ceremony.py"
    ).read_text(encoding="utf-8").lower()
    for banned in (
        "import requests",
        "requests.",
        "urlopen",
        "subprocess",
        "windows hello",
        "fido2.",
        "save_runtime_checkpoint(",
        "merge_pull_request(",
        "deploy_to_production(",
        "core_freeze(",
    ):
        assert banned not in source
