"""P0 HUMAN_OWNER root-custody boundary audit (LAB ONLY, A118 original).

All keys in this test are generated ephemeral; NO real owner signature is
captured. A valid signature plus caller-controlled public-key registry shows
conditional cryptographic verification, NOT independently established owner
identity. No module here enrolls a real owner or authorizes operations.

Review expectation: the positive synthetic case is deliberately documented
as a TRUST GAP, never as P0 PASS. Do not wire it into activation.
"""
from copy import deepcopy

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_signature_ceremony import (
    verify_owner_signature,
)
from test_atlasquant_aion_v224_owner_signature_ceremony import (
    NOW, owner_keypair, request_for, verify, sign,
)
from test_atlasquant_aion_v225_explicit_owner_decision_record import (
    decision_fixture, verify_fixture,
)


def _must_be_inert(result):
    for field in (
        "core_freeze_authorized", "core_frozen", "merge_authorized",
        "deploy_authorized", "execution_allowed", "worker_armed",
        "external_action_executed",
    ):
        assert result.get(field) is False, (field, result.get(field))


def test_p0_01_generated_root_and_own_signature_show_unenrolled_custody_gap(tmp_path):
    # An entirely synthetic registry and corresponding key still satisfy the
    # low-level cryptographic checker if a caller supplies them as trusted.
    # This MUST NOT be confused with proving who the real HUMAN_OWNER is.
    generated_secret, generated_roots = owner_keypair()
    evidence, built = request_for(generated_roots)
    assert built["state"] == "READY_FOR_EXTERNAL_OWNER_SIGNATURE"
    result = verify(
        built["request"], sign(generated_secret, built["request"]),
        generated_roots,
        PersistentNonceRegistry(tmp_path / "synthetic_owner_nonce.sqlite3"),
        e=evidence,
    )
    assert result["state"] == "READY_FOR_EXPLICIT_OWNER_DECISION"
    assert result["owner_identity_verified"] is True
    assert result["owner_decision"] == "UNDECIDED"
    assert result["approval_implied"] is False
    _must_be_inert(result)
    # The above is proof of a missing *caller-independent trust-root enrollment*
    # at this function's input boundary, not an activated exploit.


def test_p0_02_signature_cannot_substitute_key_into_distinct_pinned_roots(tmp_path):
    attacker_secret, attacker_roots = owner_keypair()
    _genuine_secret, pinned_roots = owner_keypair()
    e, built = request_for(pinned_roots)
    result = verify(
        built["request"], sign(attacker_secret, built["request"]),
        pinned_roots, PersistentNonceRegistry(tmp_path / "wrong_key.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_INVALID" in result["blockers"]
    assert result["owner_decision_ready"] is False
    _must_be_inert(result)


def test_p0_03_switching_registry_after_challenge_is_blocked(tmp_path):
    secret, pinned_roots = owner_keypair()
    _, swapped_roots = owner_keypair()
    e, built = request_for(pinned_roots)
    result = verify(
        built["request"], sign(secret, built["request"]),
        swapped_roots, PersistentNonceRegistry(tmp_path / "changed_roots.sqlite3"),
        e=e,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_REQUEST_REBUILD_MISMATCH" in result["blockers"]
    _must_be_inert(result)


def test_p0_04_chat_text_does_not_establish_owner_authority(tmp_path):
    _, pinned_roots = owner_keypair()
    e, built = request_for(pinned_roots)
    registry = PersistentNonceRegistry(tmp_path / "chat.sqlite3")
    result = verify(built["request"], "vamos la", pinned_roots, registry, e=e)
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_INVALID" in result["blockers"]
    assert registry.count() == 0
    _must_be_inert(result)


def test_p0_05_owner_nonce_replay_after_registry_reopen_is_denied(tmp_path):
    secret, roots = owner_keypair()
    e, built = request_for(roots)
    nonce_file = tmp_path / "owner-replay.sqlite3"
    signature = sign(secret, built["request"])
    first = verify(
        built["request"], signature, roots, PersistentNonceRegistry(nonce_file), e=e
    )
    assert first["state"] == "READY_FOR_EXPLICIT_OWNER_DECISION"
    _must_be_inert(first)
    replay = verify(
        built["request"], signature, roots, PersistentNonceRegistry(nonce_file), e=e
    )
    assert replay["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_NONCE_REPLAYED" in replay["blockers"]
    _must_be_inert(replay)


def test_p0_06_revoked_owner_key_cannot_start_ceremony():
    _, roots = owner_keypair(status="REVOKED")
    _, built = request_for(roots)
    assert built["state"] == "BLOCKED"
    assert "OWNER_TRUST_KEY_REVOKED" in built["blockers"]
    assert built.get("owner_signature_verified") is not True


def test_p0_07_verified_owner_decision_does_not_grant_runtime_actions(tmp_path):
    secret, roots, evidence, request, signature, built = decision_fixture()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=request,
        v224_signature=signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
    )
    assert result["state"] == "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE"
    assert result["owner_decision_recorded"] is False
    assert result["core_freeze_execution_authorized"] is False
    assert result["worker_armed"] is False
    assert result["execution_allowed"] is False
    _must_be_inert(result)


def test_p0_08_local_owner_identity_labels_cannot_replace_signature(tmp_path):
    _, roots = owner_keypair()
    e, built = request_for(roots)
    forged = deepcopy(built["request"])
    forged["owner_id"] = "ADMIN"
    result = verify(
        forged, "owner-approved-in-chat", roots,
        PersistentNonceRegistry(tmp_path / "role_label.sqlite3"), e=e
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_SIGNATURE_OWNER_ID_MISMATCH" in result["blockers"]
    _must_be_inert(result)
