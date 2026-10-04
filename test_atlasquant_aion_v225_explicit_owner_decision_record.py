"""AION V2.25 explicit owner decision record red-team."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from atlasquant_aion_checkpoint_master import append_checkpoint_patch
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_decision_record import (
    DECISIONS,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    build_owner_decision_request,
    canonical_owner_decision_bytes,
    verify_owner_decision,
)
from test_atlasquant_aion_v222_core_freeze_preflight import NOW
from test_atlasquant_aion_v224_owner_signature_ceremony import (
    CEREMONY_ID as V224_CEREMONY_ID,
    EXPIRES as V224_EXPIRES,
    ISSUED as V224_ISSUED,
    NONCE as V224_NONCE,
    OWNER_KEY_ID,
    OWNER_KEY_VERSION,
    owner_keypair,
    request_for,
    sign as sign_v224,
)


DECISION_ISSUED = "2026-10-04T19:59:45Z"
DECISION_EXPIRES = "2026-10-04T20:02:30Z"
DECISION_CEREMONY_ID = "owner-decision-ceremony-001"
DECISION_NONCE = "owner_decision_nonce_0001"


def sign_decision(secret, request):
    import base64
    raw = secret.sign(canonical_owner_decision_bytes(request))
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decision_fixture(*, decision="APPROVE_CORE_FREEZE", **overrides):
    secret, owner_roots = owner_keypair()
    evidence, v224_built = request_for(
        owner_roots,
        ceremony_id=V224_CEREMONY_ID,
        nonce=V224_NONCE,
        issued_at=V224_ISSUED,
        expires_at=V224_EXPIRES,
    )
    v224_request = v224_built["request"]
    v224_signature = sign_v224(secret, v224_request)
    kwargs = {
        "v224_request": v224_request,
        "v224_signature_b64": v224_signature,
        "owner_trust_roots": owner_roots,
        "checkpoint_master": evidence["checkpoint_master"],
        "preflight": evidence["preflight"],
        "certification_manifest": evidence["certification_manifest"],
        "certification_trust_roots": evidence["certification_trust_roots"],
        "expected_target_commit_sha": evidence["expected_target_commit_sha"],
        "runtime_result": evidence["runtime_result"],
        "write_receipt": evidence["write_receipt"],
        "now_ts": NOW,
        "decision": decision,
        "ceremony_id": DECISION_CEREMONY_ID,
        "nonce": DECISION_NONCE,
        "issued_at": DECISION_ISSUED,
        "expires_at": DECISION_EXPIRES,
        "key_id": OWNER_KEY_ID,
        "key_version": OWNER_KEY_VERSION,
    }
    kwargs.update(overrides)
    built = build_owner_decision_request(**kwargs)
    return secret, owner_roots, evidence, v224_request, v224_signature, built


def verify_fixture(
    *,
    secret,
    owner_roots,
    evidence,
    v224_request,
    v224_signature,
    built,
    registry,
    decision_signature=None,
    **overrides,
):
    kwargs = {
        "request": built["request"],
        "decision_signature_b64": (
            decision_signature
            if decision_signature is not None
            else sign_decision(secret, built["request"])
        ),
        "v224_request": v224_request,
        "v224_signature_b64": v224_signature,
        "owner_trust_roots": owner_roots,
        "decision_nonce_registry": registry,
        "checkpoint_master": evidence["checkpoint_master"],
        "preflight": evidence["preflight"],
        "certification_manifest": evidence["certification_manifest"],
        "certification_trust_roots": evidence["certification_trust_roots"],
        "expected_target_commit_sha": evidence["expected_target_commit_sha"],
        "runtime_result": evidence["runtime_result"],
        "write_receipt": evidence["write_receipt"],
        "now_ts": NOW,
    }
    kwargs.update(overrides)
    return verify_owner_decision(**kwargs)


def test_decision_request_requires_second_signature_and_does_not_record_decision():
    _, _, _, _, _, built = decision_fixture()
    assert built["state"] == "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE"
    assert built["request"]["schema"] == REQUEST_SCHEMA
    assert built["request"]["decision"] == "APPROVE_CORE_FREEZE"
    assert built["request"]["owner_decision_recorded"] is False
    assert built["owner_identity_signature_verified"] is True
    assert built["owner_decision_signature_verified"] is False
    assert built["owner_decision_recorded"] is False
    assert built["owner_decision"] == "UNDECIDED"
    assert built["core_freeze_execution_authorized"] is False
    assert built["core_freeze_authorized"] is False
    assert built["core_frozen"] is False
    assert built["checkpoint_saved"] is False
    assert built["execution_allowed"] is False
    assert built["worker_armed"] is False
    assert built["external_action_executed"] is False


def test_valid_approve_records_decision_but_never_authorizes_freeze_execution(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
    )
    assert result["schema"] == RESULT_SCHEMA
    assert result["state"] == "OWNER_DECISION_RECORDED_APPROVE"
    assert result["owner_identity_signature_verified"] is True
    assert result["owner_decision_signature_verified"] is True
    assert result["owner_decision_recorded"] is True
    assert result["owner_decision"] == "APPROVE_CORE_FREEZE"
    assert result["core_freeze_approved"] is True
    assert result["core_freeze_denied"] is False
    assert result["requires_separate_core_freeze_ceremony"] is True
    assert result["core_freeze_execution_authorized"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["checkpoint_saved"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["external_action_executed"] is False
    assert result["generic_chat_instruction_accepted_as_decision"] is False
    assert result["decision_signature_performed_by_this_module"] is False


def test_valid_deny_records_deny_and_never_opens_freeze_path(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture(
        decision="DENY_CORE_FREEZE"
    )
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
    )
    assert result["state"] == "OWNER_DECISION_RECORDED_DENY"
    assert result["owner_decision"] == "DENY_CORE_FREEZE"
    assert result["core_freeze_approved"] is False
    assert result["core_freeze_denied"] is True
    assert result["requires_separate_core_freeze_ceremony"] is False
    assert result["core_freeze_execution_authorized"] is False
    assert result["core_frozen"] is False


@pytest.mark.parametrize("choice", ["APPROVE", "DENY", "YES", True, None, "approve_core_freeze"])
def test_noncanonical_decision_choice_is_blocked(choice):
    _, roots = owner_keypair()
    _, built = request_for(roots)
    evidence, v224_built = request_for(roots)
    # use a fresh valid identity request/signature pair below
    secret, roots2, evidence2, v224_request, v224_signature, _ = decision_fixture()
    result = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=roots2,
        checkpoint_master=evidence2["checkpoint_master"],
        preflight=evidence2["preflight"],
        certification_manifest=evidence2["certification_manifest"],
        certification_trust_roots=evidence2["certification_trust_roots"],
        expected_target_commit_sha=evidence2["expected_target_commit_sha"],
        runtime_result=evidence2["runtime_result"],
        write_receipt=evidence2["write_receipt"],
        now_ts=NOW,
        decision=choice,
        ceremony_id=DECISION_CEREMONY_ID,
        nonce=DECISION_NONCE,
        issued_at=DECISION_ISSUED,
        expires_at=DECISION_EXPIRES,
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_CHOICE_INVALID" in result["blockers"]


def test_plain_chat_text_never_counts_as_decision_signature(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        decision_signature="vamos lá",
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_SIGNATURE_INVALID" in result["blockers"]
    assert result["owner_decision_recorded"] is False
    assert result["core_freeze_execution_authorized"] is False


def test_invalid_v224_identity_signature_blocks_decision_request():
    _, roots, evidence, v224_request, _, _ = decision_fixture()
    built = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64="vamos lá",
        owner_trust_roots=roots,
        checkpoint_master=evidence["checkpoint_master"],
        preflight=evidence["preflight"],
        certification_manifest=evidence["certification_manifest"],
        certification_trust_roots=evidence["certification_trust_roots"],
        expected_target_commit_sha=evidence["expected_target_commit_sha"],
        runtime_result=evidence["runtime_result"],
        write_receipt=evidence["write_receipt"],
        now_ts=NOW,
        decision="APPROVE_CORE_FREEZE",
        ceremony_id=DECISION_CEREMONY_ID,
        nonce=DECISION_NONCE,
        issued_at=DECISION_ISSUED,
        expires_at=DECISION_EXPIRES,
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert built["state"] == "BLOCKED"
    assert "V224_OWNER_SIGNATURE_INVALID" in built["blockers"]


def test_decision_signature_replay_is_blocked_durably(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    path = tmp_path / "decision.sqlite3"
    registry = PersistentNonceRegistry(path)
    sig = sign_decision(secret, built["request"])
    first = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=registry,
        decision_signature=sig,
    )
    assert first["state"] == "OWNER_DECISION_RECORDED_APPROVE"

    second = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(path),
        decision_signature=sig,
    )
    assert second["state"] == "BLOCKED"
    assert "OWNER_DECISION_NONCE_REPLAYED" in second["blockers"]


def test_wrong_decision_signing_key_blocks(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    attacker, _ = owner_keypair()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        decision_signature=sign_decision(attacker, built["request"]),
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_SIGNATURE_INVALID" in result["blockers"]


def test_tampered_choice_after_signature_blocks(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    original_sig = sign_decision(secret, built["request"])
    forged = deepcopy(built)
    forged["request"] = deepcopy(built["request"])
    forged["request"]["decision"] = "DENY_CORE_FREEZE"
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=forged,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        decision_signature=original_sig,
    )
    assert result["state"] == "BLOCKED"
    assert (
        "OWNER_DECISION_REQUEST_REBUILD_MISMATCH" in result["blockers"]
        or "OWNER_DECISION_SIGNATURE_INVALID" in result["blockers"]
    )


@pytest.mark.parametrize("field", [
    "owner_decision_recorded",
    "core_freeze_execution_authorized",
    "core_freeze_authorized",
    "core_frozen",
    "merge_authorized",
    "deploy_authorized",
    "execution_allowed",
    "worker_armed",
    "external_action_executed",
])
def test_signed_unsafe_flag_is_still_rejected_before_recording(tmp_path, field):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    forged = deepcopy(built)
    forged["request"] = deepcopy(built["request"])
    forged["request"][field] = True
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=forged,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        decision_signature=sign_decision(secret, forged["request"]),
    )
    assert result["state"] == "BLOCKED"
    assert f"OWNER_DECISION_UNSAFE_FIELD:{field}" in result["blockers"]


def test_changed_v224_request_after_decision_request_blocks_rebuild(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    changed_v224 = deepcopy(v224_request)
    changed_v224["v223_runtime_sha"] = "c" * 40
    changed_signature = sign_v224(secret, changed_v224)
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=changed_v224,
        v224_signature=changed_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_REQUEST_REBUILD_BLOCKED" in result["blockers"]


def test_changed_logical_checkpoint_after_decision_request_blocks(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    changed_master = append_checkpoint_patch(
        evidence["checkpoint_master"],
        event_id="v225-logical-change",
        patch={"system": {"after_v225_request": True}},
        expected_revision=1,
        created_at=NOW,
        evidence_refs=["v225-red-team"],
    )
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        checkpoint_master=changed_master,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_REQUEST_REBUILD_BLOCKED" in result["blockers"]


def test_expired_decision_window_blocks_build():
    _, roots, evidence, v224_request, v224_signature, _ = decision_fixture()
    result = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=roots,
        checkpoint_master=evidence["checkpoint_master"],
        preflight=evidence["preflight"],
        certification_manifest=evidence["certification_manifest"],
        certification_trust_roots=evidence["certification_trust_roots"],
        expected_target_commit_sha=evidence["expected_target_commit_sha"],
        runtime_result=evidence["runtime_result"],
        write_receipt=evidence["write_receipt"],
        now_ts=NOW,
        decision="APPROVE_CORE_FREEZE",
        ceremony_id=DECISION_CEREMONY_ID,
        nonce=DECISION_NONCE,
        issued_at="2026-10-04T19:55:00Z",
        expires_at="2026-10-04T19:59:59Z",
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_EXPIRED" in result["blockers"]


def test_decision_window_too_long_blocks_build():
    _, roots, evidence, v224_request, v224_signature, _ = decision_fixture()
    result = build_owner_decision_request(
        v224_request=v224_request,
        v224_signature_b64=v224_signature,
        owner_trust_roots=roots,
        checkpoint_master=evidence["checkpoint_master"],
        preflight=evidence["preflight"],
        certification_manifest=evidence["certification_manifest"],
        certification_trust_roots=evidence["certification_trust_roots"],
        expected_target_commit_sha=evidence["expected_target_commit_sha"],
        runtime_result=evidence["runtime_result"],
        write_receipt=evidence["write_receipt"],
        now_ts=NOW,
        decision="APPROVE_CORE_FREEZE",
        ceremony_id=DECISION_CEREMONY_ID,
        nonce=DECISION_NONCE,
        issued_at="2026-10-04T19:59:00Z",
        expires_at="2026-10-04T20:10:00Z",
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert result["state"] == "BLOCKED"
    assert "OWNER_DECISION_WINDOW_TOO_LONG" in result["blockers"]


def test_checkpoint_patch_candidate_is_generated_atomically_only_after_verification(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
    )
    candidate = result["checkpoint_patch_candidate"]
    assert candidate["state"] == "PATCH_CANDIDATE"
    assert candidate["requires_explicit_checkpoint_save"] is True
    assert candidate["automatic_checkpoint_write"] is False
    assert candidate["checkpoint_saved"] is False
    record = candidate["patch"]["aion_core_owner_decision"]
    assert record["owner_decision"] == "APPROVE_CORE_FREEZE"
    assert record["core_freeze_approved"] is True
    assert record["core_freeze_execution_authorized"] is False
    assert record["core_frozen"] is False
    assert record["execution_allowed"] is False


def test_blocked_decision_never_gets_checkpoint_patch_candidate(tmp_path):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture()
    result = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=PersistentNonceRegistry(tmp_path / "decision.sqlite3"),
        decision_signature="vamos lá",
    )
    assert result["state"] == "BLOCKED"
    assert "checkpoint_patch_candidate" not in result


def test_owner_decision_source_has_no_save_network_freeze_merge_deploy_or_arming_action():
    source = Path(
        "atlasquant_aion_owner_decision_record.py"
    ).read_text(encoding="utf-8").lower()
    for banned in (
        "import requests",
        "requests.",
        "urlopen",
        "subprocess",
        "save_runtime_checkpoint(",
        "merge_pull_request(",
        "deploy_to_production(",
        "core_freeze(",
        "arm_worker(",
        "windows hello",
        "fido2.",
    ):
        assert banned not in source
