"""AION V2.23 external Checkpoint persistence attestation red-team."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from atlasquant_aion_checkpoint_master import append_checkpoint_patch
from atlasquant_aion_external_persistence_attestation import (
    BINDING_SCHEMA,
    NAMESPACE,
    SCHEMA,
    SIGNING_SCHEMA,
    build_runtime_binding,
    stage_runtime_persistence_candidate,
    verify_external_checkpoint_persistence,
)
from atlasquant_aion_memory import (
    WRITE_RECEIPT_SCHEMA,
    checkpoint_source_digest,
    default_checkpoint,
)
from test_atlasquant_aion_v222_core_freeze_preflight import (
    NOW,
    TARGET,
    TRUST_ROOTS,
    certification_manifest,
    preflight,
    staged_checkpoint,
)


RUNTIME_SHA = "a" * 40
PREVIOUS_SHA = "b" * 40
SOURCE = "GitHub:atlasquant-runtime:dados/aion/checkpoint_master.json"


def logical_pair():
    master = staged_checkpoint()
    challenge = preflight(checkpoint=master)
    assert challenge["state"] == "READY_FOR_OWNER_DECISION_PREFLIGHT"
    return master, challenge


def staged_runtime():
    master, challenge = logical_pair()
    staged = stage_runtime_persistence_candidate(
        default_checkpoint(),
        master,
        challenge,
        expected_target_commit_sha=TARGET,
    )
    return master, challenge, staged


def receipt_for(runtime_checkpoint, *, branch="atlasquant-runtime", path="dados/aion/checkpoint_master.json",
                repo="aparecidomikael97-ship-it/usd-macro-pro-v4", write_sha=RUNTIME_SHA,
                expected_sha=PREVIOUS_SHA, write_accepted=True):
    expected_digest = checkpoint_source_digest(runtime_checkpoint)
    target = {"repo": repo, "branch": branch, "path": path}
    intent = {
        "target": target,
        "expected_sha": expected_sha,
        "expected_digest": expected_digest,
    }
    intent_id = hashlib.sha256(
        json.dumps(
            intent,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema": WRITE_RECEIPT_SCHEMA,
        "intent_id": intent_id,
        "target": target,
        "expected_sha": expected_sha,
        "expected_digest": expected_digest,
        "write_sha": write_sha,
        "write_accepted": write_accepted,
        "automatic_retry": False,
        "executes_action": False,
        "created_at": "2026-10-04T19:59:30+00:00",
    }


def runtime_result(runtime_checkpoint, *, sha=RUNTIME_SHA, source=SOURCE,
                   checked_at="2026-10-04T20:00:00+00:00", status="CONFIRMED"):
    return {
        "schema": "ATLASQUANT_AION_MEMORY_V1",
        "status": status,
        "source": source,
        "checkpoint": deepcopy(runtime_checkpoint),
        "sha": sha,
        "checked_at": checked_at,
    }


def attest(master, challenge, runtime_checkpoint, receipt=None, runtime=None, **kwargs):
    return verify_external_checkpoint_persistence(
        checkpoint_master=master,
        preflight=challenge,
        certification_manifest=certification_manifest(),
        certification_trust_roots=TRUST_ROOTS,
        expected_target_commit_sha=TARGET,
        runtime_result=runtime or runtime_result(runtime_checkpoint),
        write_receipt=receipt or receipt_for(runtime_checkpoint),
        now_ts=kwargs.pop("now_ts", NOW),
        **kwargs,
    )


def test_stage_candidate_is_memory_only_and_digest_bound():
    master, challenge, staged = staged_runtime()
    assert staged["schema"] == SCHEMA
    assert staged["state"] == "STAGED"
    assert staged["requires_explicit_checkpoint_save"] is True
    assert staged["checkpoint_external_persistence_verified"] is False
    assert staged["signature_material_ready"] is False
    assert staged["digest_to_sign"] == ""
    assert staged["external_persisted"] is False
    assert staged["external_action_executed"] is False
    assert staged["network_called"] is False
    assert staged["save_called"] is False
    candidate = staged["runtime_checkpoint_candidate"]
    assert candidate[NAMESPACE] == staged["binding"]
    assert staged["expected_runtime_digest"] == checkpoint_source_digest(candidate)
    assert staged["binding"]["checkpoint_master_digest"] == challenge["checkpoint_master_digest"]


def test_runtime_binding_is_strict_and_non_self_attesting():
    master, challenge = logical_pair()
    binding = build_runtime_binding(
        master,
        challenge,
        expected_target_commit_sha=TARGET,
    )
    assert binding["schema"] == BINDING_SCHEMA
    assert binding["persistence_claimed_by_binding"] is False
    assert binding["owner_decision_ready"] is False
    assert binding["signature_material_ready"] is False
    assert binding["core_freeze_authorized"] is False
    assert binding["external_action_executed"] is False


def test_valid_attribution_prepares_signature_material_only():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(master, challenge, candidate)
    assert result["state"] == "READY_FOR_OWNER_SIGNATURE_CEREMONY"
    assert result["blockers"] == []
    assert result["checkpoint_external_persistence_verified"] is True
    assert result["runtime_write_attributed"] is True
    assert result["runtime_observation_fresh"] is True
    assert result["signature_material_ready"] is True
    assert result["signature_challenge"]["schema"] == SIGNING_SCHEMA
    assert result["digest_to_sign"].startswith("sha256:")
    assert result["owner_decision_ready"] is False
    assert result["owner_decision"] == "UNDECIDED"
    assert result["signature_active"] is False
    assert result["biometric_capture_performed"] is False
    assert result["signature_performed"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["worker_armed"] is False
    assert result["checkpoint_saved_by_this_check"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["execution_allowed"] is False
    assert result["external_action_executed"] is False
    assert result["network_called"] is False
    assert result["save_called"] is False


def test_signature_digest_is_deterministic_for_same_evidence():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    a = attest(master, challenge, candidate)
    b = attest(master, deepcopy(challenge), deepcopy(candidate))
    assert a["digest_to_sign"] == b["digest_to_sign"]
    assert a["signature_challenge"] == b["signature_challenge"]


def test_runtime_sha_changes_signing_digest():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    a = attest(master, challenge, candidate)
    other_sha = "c" * 40
    b = attest(
        master,
        challenge,
        candidate,
        receipt=receipt_for(candidate, write_sha=other_sha),
        runtime=runtime_result(candidate, sha=other_sha),
    )
    assert b["state"] == "READY_FOR_OWNER_SIGNATURE_CEREMONY"
    assert a["digest_to_sign"] != b["digest_to_sign"]


def test_missing_runtime_binding_blocks():
    master, challenge, _ = staged_runtime()
    plain = default_checkpoint()
    result = attest(master, challenge, plain)
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_BINDING_MISSING" in result["blockers"]
    assert result["digest_to_sign"] == ""


def test_tampered_runtime_binding_blocks_even_when_runtime_digest_and_receipt_match():
    master, challenge, staged = staged_runtime()
    candidate = deepcopy(staged["runtime_checkpoint_candidate"])
    candidate[NAMESPACE]["checkpoint_revision"] += 1
    # Recompute only the enclosing runtime receipt, not the protected binding digest.
    result = attest(
        master,
        challenge,
        candidate,
        receipt=receipt_for(candidate),
        runtime=runtime_result(candidate),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_BINDING_MISMATCH:checkpoint_revision" in result["blockers"]
    assert "RUNTIME_BINDING_DIGEST_INVALID" in result["blockers"]


def test_attacker_recomputing_binding_digest_still_cannot_change_expected_logical_state():
    master, challenge, staged = staged_runtime()
    candidate = deepcopy(staged["runtime_checkpoint_candidate"])
    candidate[NAMESPACE]["checkpoint_revision"] += 1
    body = {
        k: v for k, v in candidate[NAMESPACE].items()
        if k != "binding_digest"
    }
    candidate[NAMESPACE]["binding_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    result = attest(
        master,
        challenge,
        candidate,
        receipt=receipt_for(candidate),
        runtime=runtime_result(candidate),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_BINDING_DIGEST_INVALID" not in result["blockers"]
    assert "RUNTIME_BINDING_MISMATCH:checkpoint_revision" in result["blockers"]


def test_unattributed_content_match_is_not_enough():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    receipt = receipt_for(candidate, write_sha="", write_accepted=None)
    result = attest(
        master,
        challenge,
        candidate,
        receipt=receipt,
        runtime=runtime_result(candidate),
    )
    assert result["state"] == "BLOCKED"
    assert "WRITE_NOT_ATTRIBUTED_CONFIRMED" in result["blockers"]
    assert "WRITE_NOT_ATTRIBUTED" in result["blockers"]


def test_runtime_sha_mismatch_blocks():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        receipt=receipt_for(candidate, write_sha="c" * 40),
        runtime=runtime_result(candidate, sha=RUNTIME_SHA),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_WRITE_SHA_MISMATCH" in result["blockers"]


def test_wrong_runtime_source_blocks():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        runtime=runtime_result(candidate, source="GitHub:wrong:path.json"),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_SOURCE_MISMATCH" in result["blockers"]


def test_main_branch_receipt_is_rejected():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        receipt=receipt_for(candidate, branch="main"),
        runtime=runtime_result(
            candidate,
            source="GitHub:main:dados/aion/checkpoint_master.json",
        ),
    )
    assert result["state"] == "BLOCKED"
    assert "WRITE_RECEIPT_RUNTIME_BRANCH_UNSAFE" in result["blockers"]


def test_stale_runtime_observation_blocks():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        runtime=runtime_result(
            candidate,
            checked_at="2026-10-04T19:54:00+00:00",
        ),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_OBSERVATION_STALE" in result["blockers"]


def test_future_runtime_observation_blocks():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        runtime=runtime_result(
            candidate,
            checked_at="2026-10-04T20:00:06+00:00",
        ),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_OBSERVATION_FROM_FUTURE" in result["blockers"]


@pytest.mark.parametrize("status", ["ERROR", "UNAVAILABLE", "NOT_FOUND", ""])
def test_unconfirmed_runtime_blocks(status):
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    result = attest(
        master,
        challenge,
        candidate,
        runtime=runtime_result(candidate, status=status),
    )
    assert result["state"] == "BLOCKED"
    assert "RUNTIME_NOT_CONFIRMED" in result["blockers"]


def test_runtime_content_changed_after_receipt_blocks():
    master, challenge, staged = staged_runtime()
    original = staged["runtime_checkpoint_candidate"]
    receipt = receipt_for(original)
    changed = deepcopy(original)
    changed["evidence"] = {"post_write": "changed"}
    result = attest(
        master,
        challenge,
        changed,
        receipt=receipt,
        runtime=runtime_result(changed),
    )
    assert result["state"] == "BLOCKED"
    assert "WRITE_NOT_ATTRIBUTED_CONFIRMED" in result["blockers"]
    assert "RUNTIME_DIGEST_RECEIPT_MISMATCH" in result["blockers"]


def test_changed_logical_checkpoint_invalidates_preflight_and_attestation():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    changed_master = append_checkpoint_patch(
        master,
        event_id="v223-logical-change",
        patch={"system": {"after_preflight": True}},
        expected_revision=1,
        created_at=NOW,
        evidence_refs=["v223-red-team"],
    )
    result = attest(changed_master, challenge, candidate)
    assert result["state"] == "BLOCKED"
    assert "V222_PREFLIGHT_NOT_CURRENT" in result["blockers"]


def test_direct_owner_decision_in_preflight_blocks_attestation():
    master, challenge, staged = staged_runtime()
    candidate = staged["runtime_checkpoint_candidate"]
    forged = deepcopy(challenge)
    forged["owner_decision"] = "APPROVE_CORE_FREEZE"
    result = attest(master, forged, candidate)
    assert result["state"] == "BLOCKED"
    assert "V222_PREFLIGHT_NOT_CURRENT" in result["blockers"]


def test_binding_builder_rejects_non_preflight_state():
    master, challenge = logical_pair()
    bad = deepcopy(challenge)
    bad["state"] = "READY_FOR_OWNER_DECISION"
    with pytest.raises(ValueError, match="preflight state mismatch"):
        build_runtime_binding(
            master,
            bad,
            expected_target_commit_sha=TARGET,
        )


def test_binding_builder_rejects_nonempty_v222_digest_to_sign():
    master, challenge = logical_pair()
    bad = deepcopy(challenge)
    bad["digest_to_sign"] = bad["challenge_digest"]
    with pytest.raises(ValueError, match="digest_to_sign"):
        build_runtime_binding(
            master,
            bad,
            expected_target_commit_sha=TARGET,
        )


@pytest.mark.parametrize("bad_sha", ["", "abc", "g" * 40, "a" * 39])
def test_target_sha_is_strict(bad_sha):
    master, challenge = logical_pair()
    with pytest.raises(ValueError, match="40-char git SHA"):
        build_runtime_binding(
            master,
            challenge,
            expected_target_commit_sha=bad_sha,
        )


def test_attestation_source_has_no_network_save_freeze_merge_or_arming_action():
    source = Path(
        "atlasquant_aion_external_persistence_attestation.py"
    ).read_text(encoding="utf-8").lower()
    for banned in (
        "import requests",
        "requests.",
        "urlopen",
        "subprocess",
        "save_runtime_checkpoint(",
        "merge_pull_request(",
        "deploy_to_production(",
        "windows hello",
        "fido2.",
    ):
        assert banned not in source
