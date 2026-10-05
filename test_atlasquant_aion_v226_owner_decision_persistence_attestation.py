"""AION V2.26 owner decision record persistence attestation red-team."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from atlasquant_aion_memory import checkpoint_source_digest
from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_owner_decision_persistence_attestation import (
    FREEZE_MATERIAL_SCHEMA,
    NAMESPACE,
    RECORD_SCHEMA,
    SCHEMA,
    stage_owner_decision_record_persistence_candidate,
    verify_owner_decision_record_persistence,
)
from atlasquant_aion_owner_decision_record import (
    build_owner_decision_request,
)
from test_atlasquant_aion_v222_core_freeze_preflight import NOW
from test_atlasquant_aion_v223_external_persistence_attestation import (
    RUNTIME_SHA,
    receipt_for,
    runtime_result,
)
from test_atlasquant_aion_v224_owner_signature_ceremony import (
    OWNER_KEY_ID,
    OWNER_KEY_VERSION,
)
from test_atlasquant_aion_v225_explicit_owner_decision_record import (
    DECISION_CEREMONY_ID,
    DECISION_EXPIRES,
    DECISION_ISSUED,
    DECISION_NONCE,
    decision_fixture,
    sign_decision,
    verify_fixture,
)


DECISION_RUNTIME_SHA = "d" * 40
FINAL_NOW = "2026-10-04T20:00:45Z"
FINAL_CHECKED_AT = "2026-10-04T20:00:30+00:00"


def verified_decision(tmp_path, *, decision="APPROVE_CORE_FREEZE"):
    secret, roots, evidence, v224_request, v224_signature, built = decision_fixture(
        decision=decision
    )
    registry = PersistentNonceRegistry(tmp_path / "decision_nonce.sqlite3")
    decision_signature = sign_decision(secret, built["request"])
    verified = verify_fixture(
        secret=secret,
        owner_roots=roots,
        evidence=evidence,
        v224_request=v224_request,
        v224_signature=v224_signature,
        built=built,
        registry=registry,
        decision_signature=decision_signature,
    )
    expected_state = (
        "OWNER_DECISION_VERIFIED_APPROVE_PENDING_PERSISTENCE"
        if decision == "APPROVE_CORE_FREEZE"
        else "OWNER_DECISION_VERIFIED_DENY_PENDING_PERSISTENCE"
    )
    assert verified["state"] == expected_state
    assert verified["owner_decision_recorded"] is False
    return {
        "secret": secret,
        "roots": roots,
        "evidence": evidence,
        "v224_request": v224_request,
        "v224_signature": v224_signature,
        "built": built,
        "registry": registry,
        "decision_signature": decision_signature,
        "verified": verified,
    }


def stage(ctx):
    e = ctx["evidence"]
    return stage_owner_decision_record_persistence_candidate(
        decision_request=ctx["built"]["request"],
        decision_signature_b64=ctx["decision_signature"],
        decision_nonce_registry=ctx["registry"],
        v224_request=ctx["v224_request"],
        v224_signature_b64=ctx["v224_signature"],
        owner_trust_roots=ctx["roots"],
        checkpoint_master=e["checkpoint_master"],
        preflight=e["preflight"],
        certification_manifest=e["certification_manifest"],
        certification_trust_roots=e["certification_trust_roots"],
        expected_target_commit_sha=e["expected_target_commit_sha"],
        v223_runtime_result=e["runtime_result"],
        v223_write_receipt=e["write_receipt"],
    )


def attest(ctx, *, candidate=None, receipt=None, runtime=None, now_ts=FINAL_NOW, **overrides):
    e = ctx["evidence"]
    staged = candidate or stage(ctx)
    runtime_checkpoint = staged["runtime_checkpoint_candidate"]
    final_receipt = receipt or receipt_for(
        runtime_checkpoint,
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
    )
    final_runtime = runtime or runtime_result(
        runtime_checkpoint,
        sha=DECISION_RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    kwargs = {
        "decision_request": ctx["built"]["request"],
        "decision_signature_b64": ctx["decision_signature"],
        "decision_nonce_registry": ctx["registry"],
        "v224_request": ctx["v224_request"],
        "v224_signature_b64": ctx["v224_signature"],
        "owner_trust_roots": ctx["roots"],
        "checkpoint_master": e["checkpoint_master"],
        "preflight": e["preflight"],
        "certification_manifest": e["certification_manifest"],
        "certification_trust_roots": e["certification_trust_roots"],
        "expected_target_commit_sha": e["expected_target_commit_sha"],
        "v223_runtime_result": e["runtime_result"],
        "v223_write_receipt": e["write_receipt"],
        "decision_runtime_result": final_runtime,
        "decision_write_receipt": final_receipt,
        "now_ts": now_ts,
    }
    kwargs.update(overrides)
    return verify_owner_decision_record_persistence(**kwargs)


def test_nonce_claim_metadata_is_read_only_and_exact(tmp_path):
    ctx = verified_decision(tmp_path)
    before = ctx["registry"].count()
    request = ctx["built"]["request"]
    from atlasquant_aion_owner_decision_record import owner_decision_nonce_scope

    scope = owner_decision_nonce_scope(
        request,
        request_digest=ctx["built"]["request_digest"],
    )
    claim = ctx["registry"].read_claim(scope=scope, nonce=request["nonce"])
    assert claim is not None
    assert claim["scope"] == scope
    assert claim["nonce"] == request["nonce"]
    assert claim["expires_at"] == request["expires_at"]
    assert claim["created_at"] == NOW
    assert ctx["registry"].count() == before


def test_stage_candidate_is_memory_only_and_exactly_bound(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    assert staged["schema"] == SCHEMA
    assert staged["state"] == "STAGED_FOR_EXPLICIT_DECISION_RECORD_PERSISTENCE"
    assert staged["blockers"] == []
    assert staged["namespace"] == NAMESPACE
    assert staged["owner_decision_verified"] is True
    assert staged["owner_decision_recorded"] is False
    assert staged["decision_record_persisted"] is False
    assert staged["persistence_attested"] is False
    assert staged["core_freeze_ceremony_eligible"] is False
    assert staged["core_freeze_execution_authorized"] is False
    assert staged["core_frozen"] is False
    assert staged["requires_explicit_checkpoint_save"] is True
    assert staged["requires_persistence_attestation"] is True
    assert staged["save_called"] is False
    assert staged["network_called"] is False
    assert staged["external_action_executed"] is False
    record = staged["decision_record"]
    assert record["schema"] == RECORD_SCHEMA
    assert record["decision"] == "APPROVE_CORE_FREEZE"
    assert record["owner_decision_verified"] is True
    assert record["owner_decision_recorded"] is False
    assert record["decision_record_persisted"] is False
    assert record["persistence_attested"] is False
    assert record["core_freeze_ceremony_eligible"] is False
    assert record["record_digest"].startswith("sha256:")
    assert staged["runtime_checkpoint_candidate"][NAMESPACE] == record
    assert staged["expected_previous_runtime_sha"] == RUNTIME_SHA
    assert staged["expected_runtime_digest"] == checkpoint_source_digest(
        staged["runtime_checkpoint_candidate"]
    )


def test_valid_approve_persistence_attestation_makes_record_durable_only(tmp_path):
    ctx = verified_decision(tmp_path)
    result = attest(ctx)
    assert result["state"] == "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE"
    assert result["blockers"] == []
    assert result["owner_decision_verified"] is True
    assert result["owner_decision_recorded"] is True
    assert result["decision_record_persisted"] is True
    assert result["persistence_attested"] is True
    assert result["owner_decision"] == "APPROVE_CORE_FREEZE"
    assert result["runtime_write_attributed"] is True
    assert result["runtime_observation_fresh"] is True
    assert result["core_freeze_approved"] is True
    assert result["core_freeze_denied"] is False
    assert result["core_freeze_ceremony_eligible"] is True
    assert result["core_freeze_ceremony_material_ready"] is True
    assert result["core_freeze_ceremony_material"]["schema"] == FREEZE_MATERIAL_SCHEMA
    assert result["digest_to_core_freeze_ceremony"].startswith("sha256:")
    assert result["core_freeze_execution_authorized"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["checkpoint_saved_by_this_check"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["save_called"] is False
    assert result["network_called"] is False
    assert result["external_action_executed"] is False
    assert result["executes_action"] is False


def test_valid_deny_persistence_attestation_records_deny_without_freeze_eligibility(tmp_path):
    ctx = verified_decision(tmp_path, decision="DENY_CORE_FREEZE")
    result = attest(ctx)
    assert result["state"] == "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_DENY"
    assert result["owner_decision_recorded"] is True
    assert result["decision_record_persisted"] is True
    assert result["owner_decision"] == "DENY_CORE_FREEZE"
    assert result["core_freeze_approved"] is False
    assert result["core_freeze_denied"] is True
    assert result["core_freeze_ceremony_eligible"] is False
    assert result["core_freeze_ceremony_material_ready"] is False
    assert result["core_freeze_ceremony_material"] == {}
    assert result["digest_to_core_freeze_ceremony"] == ""
    assert result["core_freeze_execution_authorized"] is False
    assert result["core_frozen"] is False


def test_missing_nonce_claim_blocks_stage(tmp_path):
    ctx = verified_decision(tmp_path)
    empty = PersistentNonceRegistry(tmp_path / "empty.sqlite3")
    ctx["registry"] = empty
    staged = stage(ctx)
    assert staged["state"] == "BLOCKED"
    assert "V225_DECISION_NONCE_CLAIM_MISSING" in staged["blockers"]
    assert staged["runtime_checkpoint_candidate"] == {}
    assert staged["owner_decision_recorded"] is False


def test_nonce_claim_for_approve_does_not_attest_unclaimed_deny_with_same_nonce(tmp_path):
    ctx = verified_decision(tmp_path)
    e = ctx["evidence"]
    deny = build_owner_decision_request(
        v224_request=ctx["v224_request"],
        v224_signature_b64=ctx["v224_signature"],
        owner_trust_roots=ctx["roots"],
        checkpoint_master=e["checkpoint_master"],
        preflight=e["preflight"],
        certification_manifest=e["certification_manifest"],
        certification_trust_roots=e["certification_trust_roots"],
        expected_target_commit_sha=e["expected_target_commit_sha"],
        runtime_result=e["runtime_result"],
        write_receipt=e["write_receipt"],
        now_ts=NOW,
        decision="DENY_CORE_FREEZE",
        ceremony_id="owner-decision-ceremony-026-deny",
        nonce=DECISION_NONCE,
        issued_at=DECISION_ISSUED,
        expires_at=DECISION_EXPIRES,
        key_id=OWNER_KEY_ID,
        key_version=OWNER_KEY_VERSION,
    )
    assert deny["state"] == "READY_FOR_EXTERNAL_OWNER_DECISION_SIGNATURE"
    ctx["built"] = deny
    ctx["decision_signature"] = sign_decision(ctx["secret"], deny["request"])
    staged = stage(ctx)
    assert staged["state"] == "BLOCKED"
    assert "V225_DECISION_NONCE_CLAIM_MISSING" in staged["blockers"]


def test_wrong_decision_signature_blocks_stage(tmp_path):
    ctx = verified_decision(tmp_path)
    attacker, _, _, _, _, _ = decision_fixture()
    ctx["decision_signature"] = sign_decision(attacker, ctx["built"]["request"])
    staged = stage(ctx)
    assert staged["state"] == "BLOCKED"
    assert "V225_DECISION_SIGNATURE_INVALID" in staged["blockers"]


def test_tampered_decision_request_blocks_rebuild(tmp_path):
    ctx = verified_decision(tmp_path)
    forged = deepcopy(ctx["built"])
    forged["request"] = deepcopy(ctx["built"]["request"])
    forged["request"]["decision"] = "DENY_CORE_FREEZE"
    ctx["built"] = forged
    staged = stage(ctx)
    assert staged["state"] == "BLOCKED"
    assert (
        "V225_DECISION_NONCE_CLAIM_MISSING" in staged["blockers"]
        or "V225_DECISION_REQUEST_REBUILD_MISMATCH" in staged["blockers"]
    )


def test_missing_runtime_decision_namespace_blocks_attestation(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    plain = deepcopy(ctx["evidence"]["runtime_result"]["checkpoint"])
    receipt = receipt_for(
        plain,
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
    )
    runtime = runtime_result(
        plain,
        sha=DECISION_RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, receipt=receipt, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_RECORD_MISSING" in result["blockers"]


def test_tampered_runtime_decision_record_blocks_even_with_matching_outer_receipt(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    candidate = deepcopy(staged["runtime_checkpoint_candidate"])
    candidate[NAMESPACE]["decision"] = "DENY_CORE_FREEZE"
    candidate[NAMESPACE]["core_freeze_approved"] = False
    candidate[NAMESPACE]["core_freeze_denied"] = True
    # Recompute attacker-controlled record digest and outer write receipt.
    body = {
        k: v for k, v in candidate[NAMESPACE].items()
        if k != "record_digest"
    }
    import hashlib, json
    candidate[NAMESPACE]["record_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    receipt = receipt_for(
        candidate,
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
    )
    runtime = runtime_result(
        candidate,
        sha=DECISION_RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, receipt=receipt, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_RECORD_MISMATCH:decision" in result["blockers"]


@pytest.mark.parametrize("field,value,blocker", [
    ("repo", "evil/example", "DECISION_WRITE_RECEIPT_TARGET_MISMATCH:repo"),
    ("branch", "main", "DECISION_WRITE_RECEIPT_RUNTIME_BRANCH_UNSAFE"),
    ("path", "dados/aion/other.json", "DECISION_WRITE_RECEIPT_TARGET_MISMATCH:path"),
])
def test_wrong_runtime_target_blocks(tmp_path, field, value, blocker):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    kwargs = {field: value}
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
        **kwargs,
    )
    result = attest(ctx, candidate=staged, receipt=receipt)
    assert result["state"] == "BLOCKED"
    assert blocker in result["blockers"]


def test_wrong_cas_base_sha_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha="e" * 40,
        write_sha=DECISION_RUNTIME_SHA,
    )
    result = attest(ctx, candidate=staged, receipt=receipt)
    assert result["state"] == "BLOCKED"
    assert "DECISION_WRITE_CAS_BASE_SHA_MISMATCH" in result["blockers"]


def test_runtime_sha_must_advance_from_v223_base(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha=RUNTIME_SHA,
        write_sha=RUNTIME_SHA,
    )
    runtime = runtime_result(
        staged["runtime_checkpoint_candidate"],
        sha=RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, receipt=receipt, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_SHA_DID_NOT_ADVANCE" in result["blockers"]


def test_runtime_write_sha_mismatch_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha=RUNTIME_SHA,
        write_sha="e" * 40,
    )
    runtime = runtime_result(
        staged["runtime_checkpoint_candidate"],
        sha=DECISION_RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, receipt=receipt, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_WRITE_SHA_MISMATCH" in result["blockers"]


def test_content_match_without_unique_write_attribution_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha=RUNTIME_SHA,
        write_sha="",
    )
    result = attest(ctx, candidate=staged, receipt=receipt)
    assert result["state"] == "BLOCKED"
    assert "DECISION_WRITE_NOT_ATTRIBUTED_CONFIRMED" in result["blockers"]
    assert "DECISION_WRITE_NOT_ATTRIBUTED" in result["blockers"]


def test_rejected_write_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    receipt = receipt_for(
        staged["runtime_checkpoint_candidate"],
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
        write_accepted=False,
    )
    result = attest(ctx, candidate=staged, receipt=receipt)
    assert result["state"] == "BLOCKED"
    assert "DECISION_WRITE_NOT_ATTRIBUTED_CONFIRMED" in result["blockers"]


def test_stale_runtime_observation_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    runtime = runtime_result(
        staged["runtime_checkpoint_candidate"],
        sha=DECISION_RUNTIME_SHA,
        checked_at="2026-10-04T19:54:00+00:00",
    )
    result = attest(ctx, candidate=staged, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_OBSERVATION_STALE" in result["blockers"]


def test_future_runtime_observation_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    runtime = runtime_result(
        staged["runtime_checkpoint_candidate"],
        sha=DECISION_RUNTIME_SHA,
        checked_at="2026-10-04T20:01:00+00:00",
    )
    result = attest(ctx, candidate=staged, runtime=runtime, now_ts=FINAL_NOW)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_OBSERVATION_FROM_FUTURE" in result["blockers"]


def test_runtime_source_mismatch_blocks(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    runtime = runtime_result(
        staged["runtime_checkpoint_candidate"],
        sha=DECISION_RUNTIME_SHA,
        source="GitHub:atlasquant-runtime:dados/aion/other.json",
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_SOURCE_MISMATCH" in result["blockers"]


def test_staged_digest_mismatch_blocks_unrelated_runtime_change(tmp_path):
    ctx = verified_decision(tmp_path)
    staged = stage(ctx)
    candidate = deepcopy(staged["runtime_checkpoint_candidate"])
    candidate["unrelated_concurrent_change"] = {"value": 1}
    receipt = receipt_for(
        candidate,
        expected_sha=RUNTIME_SHA,
        write_sha=DECISION_RUNTIME_SHA,
    )
    runtime = runtime_result(
        candidate,
        sha=DECISION_RUNTIME_SHA,
        checked_at=FINAL_CHECKED_AT,
    )
    result = attest(ctx, candidate=staged, receipt=receipt, runtime=runtime)
    assert result["state"] == "BLOCKED"
    assert "DECISION_RUNTIME_STAGED_DIGEST_MISMATCH" in result["blockers"]


def test_approve_freeze_material_is_deterministic(tmp_path):
    ctx = verified_decision(tmp_path)
    a = attest(ctx)
    # Use a fresh registry/file because V2.26 does not consume the nonce.
    b = attest(ctx)
    assert a["digest_to_core_freeze_ceremony"] == b["digest_to_core_freeze_ceremony"]
    assert a["core_freeze_ceremony_material"] == b["core_freeze_ceremony_material"]


def test_v226_source_has_no_save_network_freeze_merge_deploy_or_arming_action():
    source = Path(
        "atlasquant_aion_owner_decision_persistence_attestation.py"
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
