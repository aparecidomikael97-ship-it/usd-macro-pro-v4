"""AION V2.22 Core Freeze Ceremony Preflight red-team tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import json

import pytest

from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
)
from atlasquant_aion_core_completion_review import build_checkpoint_patch_candidate
from atlasquant_aion_core_freeze_preflight import (
    build_core_freeze_preflight,
    verify_preflight_still_current,
)
from test_atlasquant_aion_v221_core_completion_review import (
    TARGET,
    TRUST_ROOTS,
    certification_manifest,
)


NOW = "2026-10-04T20:00:00Z"
ISSUED = "2026-10-04T19:59:00Z"
EXPIRES = "2026-10-04T20:10:00Z"
CEREMONY_ID = "core-freeze-ceremony-001"
NONCE = "v222_nonce_0123456789abcdef"


def staged_checkpoint():
    manifest = certification_manifest()
    candidate = build_checkpoint_patch_candidate(
        manifest,
        certification_trust_roots=TRUST_ROOTS,
        now_ts=NOW,
        expected_target_commit_sha=TARGET,
    )
    master = new_checkpoint_master(
        {"system": {"state": "SAFE"}},
        base_revision=0,
        created_at=NOW,
        source_refs=["v2.22-test"],
    )
    return append_checkpoint_patch(
        master,
        event_id=candidate["recommended_event_id"],
        patch=candidate["patch"],
        expected_revision=0,
        created_at=NOW,
        evidence_refs=[
            candidate["patch"]["aion_core_completion_review"]["review_digest"]
        ],
    )


def preflight(*, checkpoint=None, manifest=None, **overrides):
    kwargs = {
        "certification_manifest": (
            certification_manifest() if manifest is None else manifest
        ),
        "certification_trust_roots": TRUST_ROOTS,
        "now_ts": NOW,
        "expected_target_commit_sha": TARGET,
        "checkpoint_master": staged_checkpoint() if checkpoint is None else checkpoint,
        "ceremony_id": CEREMONY_ID,
        "challenge_nonce": NONCE,
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
    }
    kwargs.update(overrides)
    return build_core_freeze_preflight(**kwargs)


def recheck(result, *, checkpoint, now_ts=NOW, manifest=None):
    return verify_preflight_still_current(
        result,
        certification_manifest=(
            certification_manifest() if manifest is None else manifest
        ),
        certification_trust_roots=TRUST_ROOTS,
        expected_target_commit_sha=TARGET,
        checkpoint_master=checkpoint,
        now_ts=now_ts,
    )


def test_valid_preflight_is_ready_for_owner_decision_only():
    result = preflight()
    assert result["state"] == "READY_FOR_OWNER_DECISION_PREFLIGHT"
    assert result["owner_decision_preflight_ready"] is True
    assert result["owner_decision_ready"] is False
    assert result["owner_decision"] == "UNDECIDED"
    assert result["digest_to_sign"] == ""
    assert result["human_owner_required"] is True
    assert result["signature_mechanism"] == "FIDO2_OR_PLATFORM_SIGNATURE_FUTURE"
    assert result["signature_active"] is False
    assert result["biometric_capture_performed"] is False
    assert result["signature_performed"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["checkpoint_saved"] is False
    assert result["checkpoint_external_persistence_verified"] is False
    assert result["requires_external_persistence_attestation"] is True
    assert result["signature_material_ready"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["external_action_executed"] is False
    assert result["automatic_freeze"] is False
    assert result["automatic_checkpoint_write"] is False


def test_missing_persisted_review_blocks_ceremony():
    empty = new_checkpoint_master(
        {"system": {"state": "SAFE"}},
        created_at=NOW,
    )
    result = preflight(checkpoint=empty)
    assert result["state"] == "BLOCKED"
    assert "CHECKPOINT_REVIEW_RECORD_MISSING" in result["blockers"]
    assert result["digest_to_sign"] == ""


def test_valid_but_empty_checkpoint_still_blocks_missing_review():
    empty = new_checkpoint_master({}, created_at=NOW)
    result = preflight(checkpoint=empty)
    assert result["state"] == "BLOCKED"
    assert "CHECKPOINT_REVIEW_RECORD_MISSING" in result["blockers"]


def test_forged_checkpoint_review_cannot_replace_reverified_v221_review():
    master = new_checkpoint_master(
        {
            "aion_core_completion_review": {
                "schema": "ATLASQUANT_AION_CORE_COMPLETION_REVIEW_V1",
                "state": "READY_FOR_OWNER_REVIEW",
                "target_commit_sha": TARGET,
                "certification_manifest_digest": "sha256:" + "1" * 64,
                "certification_trust_root_binding_digest": "sha256:" + "2" * 64,
                "review_digest": "sha256:" + "3" * 64,
                "owner_review_ready": True,
                "owner_decision_recorded": False,
                "core_complete": False,
                "core_frozen": False,
                "execution_allowed": False,
                "external_action_executed": False,
            }
        },
        created_at=NOW,
    )
    result = preflight(checkpoint=master)
    assert result["state"] == "BLOCKED"
    assert any(
        blocker.startswith("CHECKPOINT_REVIEW_MISMATCH:")
        for blocker in result["blockers"]
    )


def test_tampered_checkpoint_integrity_blocks():
    master = staged_checkpoint()
    master = deepcopy(master)
    master["state_digest"] = "sha256:" + "0" * 64
    result = preflight(checkpoint=master)
    assert result["state"] == "BLOCKED"
    assert "CHECKPOINT_MASTER_INTEGRITY_INVALID" in result["blockers"]


def test_checkpoint_change_after_preflight_blocks_toctou_recheck():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    changed = append_checkpoint_patch(
        master,
        event_id="post-review-change",
        patch={"system": {"note": "changed"}},
        expected_revision=1,
        created_at=NOW,
        evidence_refs=["post-review"],
    )
    check = recheck(result, checkpoint=changed)
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_CHALLENGE_REBUILD_MISMATCH" in check["blockers"]
    assert check["core_freeze_authorized"] is False


def test_same_checkpoint_keeps_preflight_current():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    check = recheck(result, checkpoint=master)
    assert check["state"] == "CURRENT"
    assert check["preflight_current"] is True
    assert check["core_freeze_authorized"] is False


def test_expired_challenge_blocks_recheck():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    check = recheck(
        result,
        checkpoint=master,
        now_ts="2026-10-04T20:11:00Z",
    )
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_REBUILD_NOT_READY" in check["blockers"]
    assert "REBUILD:CEREMONY_EXPIRED_OR_INVALID_WINDOW" in check["blockers"]


def test_long_ceremony_window_blocks_preflight():
    result = preflight(
        expires_at="2026-10-04T20:30:00Z",
    )
    assert result["state"] == "BLOCKED"
    assert "CEREMONY_WINDOW_TOO_LONG" in result["blockers"]


def test_future_issued_ceremony_blocks_preflight():
    result = preflight(
        issued_at="2026-10-04T20:01:00Z",
        expires_at="2026-10-04T20:10:00Z",
    )
    assert result["state"] == "BLOCKED"
    assert "CEREMONY_NOT_YET_VALID" in result["blockers"]


@pytest.mark.parametrize("bad_id", ["short", "has spaces here", "x" * 161])
def test_ceremony_id_must_be_canonical(bad_id):
    with pytest.raises(ValueError, match="ceremony_id"):
        preflight(ceremony_id=bad_id)


@pytest.mark.parametrize("bad_nonce", ["short", "bad nonce with spaces", "x" * 257])
def test_nonce_must_be_canonical(bad_nonce):
    with pytest.raises(ValueError, match="challenge_nonce"):
        preflight(challenge_nonce=bad_nonce)


def test_target_mismatch_blocks_even_with_valid_checkpoint():
    result = preflight(expected_target_commit_sha="d" * 40)
    assert result["state"] == "BLOCKED"
    assert "CORE_COMPLETION_REVIEW_NOT_READY" in result["blockers"]


def test_challenge_digest_is_deterministic_for_same_state():
    master = staged_checkpoint()
    a = preflight(checkpoint=master)
    b = preflight(checkpoint=deepcopy(master))
    assert a["challenge_digest"] == b["challenge_digest"]


def test_nonce_and_ceremony_id_change_challenge_digest():
    master = staged_checkpoint()
    a = preflight(checkpoint=master)
    b = preflight(
        checkpoint=master,
        ceremony_id="core-freeze-ceremony-002",
        challenge_nonce="v222_nonce_fedcba9876543210",
    )
    assert a["challenge_digest"] != b["challenge_digest"]


def test_tampered_preflight_challenge_digest_is_detected():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    result["target_commit_sha"] = "d" * 40
    check = recheck(result, checkpoint=master)
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_CHALLENGE_DIGEST_MISMATCH" in check["blockers"]


def test_digest_to_sign_must_remain_empty_until_persistence_attestation():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    result["digest_to_sign"] = result["challenge_digest"]
    check = recheck(result, checkpoint=master)
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_DIGEST_TO_SIGN_MUST_REMAIN_EMPTY" in check["blockers"]


def test_owner_decision_cannot_be_injected_into_preflight():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    result["owner_decision"] = "APPROVE_CORE_FREEZE"
    check = recheck(result, checkpoint=master)
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_CHALLENGE_DIGEST_MISMATCH" in check["blockers"]
    assert "OWNER_DECISION_MUST_REMAIN_UNDECIDED_IN_PREFLIGHT" in check["blockers"]


@pytest.mark.parametrize("field", [
    "owner_decision_recorded",
    "signature_active",
    "biometric_capture_performed",
    "signature_performed",
    "core_freeze_authorized",
    "core_frozen",
    "checkpoint_saved",
    "checkpoint_external_persistence_verified",
    "signature_material_ready",
    "owner_decision_ready",
    "merge_authorized",
    "deploy_authorized",
    "execution_allowed",
    "worker_armed",
    "external_action_executed",
    "executes_action",
    "automatic_freeze",
    "automatic_checkpoint_write",
])
def test_unsafe_preflight_field_cannot_be_promoted(field):
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    result[field] = True
    check = recheck(result, checkpoint=master)
    assert check["state"] == "BLOCKED"
    assert f"UNSAFE_PREFLIGHT_FIELD:{field}" in check["blockers"]


def test_forged_preflight_cannot_bypass_signed_chain_rebuild():
    master = staged_checkpoint()
    result = preflight(checkpoint=master)
    forged = deepcopy(result)
    forged["checkpoint_master_digest"] = "sha256:" + "9" * 64

    presented_body = {
        key: value
        for key, value in forged.items()
        if key not in {
            "challenge_digest",
            "digest_to_sign",
        }
    }
    forged["challenge_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            presented_body,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    forged["digest_to_sign"] = ""

    check = recheck(forged, checkpoint=master)
    assert check["state"] == "BLOCKED"
    assert "PREFLIGHT_CHALLENGE_DIGEST_MISMATCH" not in check["blockers"]
    assert "PREFLIGHT_CHALLENGE_REBUILD_MISMATCH" in check["blockers"]
    assert check["signed_chain_rebuilt"] is True


def test_preflight_source_has_no_signing_network_persistence_or_deploy_action():
    source = Path("atlasquant_aion_core_freeze_preflight.py").read_text(
        encoding="utf-8"
    ).lower()
    for banned in (
        "import requests",
        "requests.",
        "urlopen",
        "subprocess",
        "private_key",
        "save_runtime_checkpoint(",
        "merge_pull_request(",
        "deploy_to_production(",
        "windows hello",
    ):
        assert banned not in source
