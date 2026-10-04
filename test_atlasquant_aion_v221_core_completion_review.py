"""AION V2.21 Core Completion Review Gate red-team tests."""
from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
    reconstruct_checkpoint,
)
from atlasquant_aion_core_certification import (
    REQUIRED_DIMENSIONS,
    canonical_evidence_attestation_bytes,
    certify_core,
    synthetic_evidence_row,
)
from atlasquant_aion_core_completion_review import (
    build_checkpoint_patch_candidate,
    build_core_completion_review,
    reverify_certification_manifest,
)
from atlasquant_aion_trust_root import TrustRootRegistry


TARGET = "c" * 40
NOW = "2026-10-04T20:00:00Z"
ISSUED = "2026-10-04T19:00:00Z"
EXPIRES = "2026-10-04T21:00:00Z"
KEY_ID = "test-v221-certification-key"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def keypair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private, b64url(public)


PRIVATE_KEY, PUBLIC_KEY_B64 = keypair()


def roots(*, revoked=False, public_key_b64=PUBLIC_KEY_B64):
    return TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": KEY_ID,
            "key_version": 1,
            "algorithm": "Ed25519",
            "public_key_b64": public_key_b64,
            "status": "ACTIVE",
            "not_before": "2026-10-01T00:00:00Z",
            "not_after": "2027-10-01T00:00:00Z",
        }],
        "revoked_key_ids": [KEY_ID] if revoked else [],
    })


TRUST_ROOTS = roots()


def signed_row(dimension, *, commit=TARGET, private_key=PRIVATE_KEY):
    source = (
        "CI"
        if dimension in {"CANONICAL_GATES", "GLOBAL_WORKER_READINESS"}
        else "TEST_SUITE"
    )
    row = synthetic_evidence_row(
        dimension,
        commit_sha=commit,
        run_id=f"run-{dimension.lower()}",
        test_count=100,
        source=source,
        key_id=KEY_ID,
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )
    row["signature_b64"] = b64url(
        private_key.sign(canonical_evidence_attestation_bytes(dimension, row))
    )
    return row


def certification_manifest(*, commit=TARGET, trust_roots=TRUST_ROOTS):
    evidence = {
        dimension: signed_row(dimension, commit=commit)
        for dimension in REQUIRED_DIMENSIONS
    }
    return certify_core(
        evidence,
        target_commit_sha=commit,
        certification_trust_roots=trust_roots,
        now_ts=NOW,
        core_freeze_authorized=False,
    )


def review(manifest=None, **kwargs):
    return build_core_completion_review(
        manifest or certification_manifest(),
        certification_trust_roots=kwargs.pop(
            "certification_trust_roots", TRUST_ROOTS
        ),
        now_ts=kwargs.pop("now_ts", NOW),
        expected_target_commit_sha=kwargs.pop(
            "expected_target_commit_sha", TARGET
        ),
        **kwargs,
    )


def test_valid_v220_manifest_becomes_owner_review_ready_only():
    result = review()
    assert result["state"] == "READY_FOR_OWNER_REVIEW"
    assert result["owner_review_ready"] is True
    assert result["certification_verified"] is True
    assert result["canonical_gates_green"] is True
    assert result["global_worker_readiness_green"] is True
    assert result["owner_decision_recorded"] is False
    assert result["core_complete"] is False
    assert result["core_complete_claim_allowed"] is False
    assert result["core_freeze_authorized"] is False
    assert result["core_frozen"] is False
    assert result["checkpoint_saved"] is False
    assert result["execution_allowed"] is False
    assert result["worker_armed"] is False
    assert result["merge_authorized"] is False
    assert result["deploy_authorized"] is False
    assert result["external_action_executed"] is False


def test_tampered_manifest_digest_blocks_review():
    manifest = certification_manifest()
    manifest["manifest_digest"] = "sha256:" + "0" * 64
    result = review(manifest)
    assert result["state"] == "BLOCKED"
    assert "CERTIFICATION_MANIFEST_DIGEST_MISMATCH" in result["blockers"]


@pytest.mark.parametrize("field", [
    "core_complete_claim_allowed",
    "core_frozen",
    "core_freeze_authorized_by_this_module",
    "execution_allowed",
    "worker_armed",
    "merge_authorized",
    "deploy_authorized",
    "external_action_executed",
    "executes_action",
])
def test_unsafe_certification_claims_block_even_outside_manifest_digest(field):
    manifest = certification_manifest()
    manifest[field] = True
    result = review(manifest)
    assert result["state"] == "BLOCKED"
    assert f"UNSAFE_CERTIFICATION_FIELD:{field}" in result["blockers"]


def test_target_commit_mismatch_blocks_review():
    result = review(expected_target_commit_sha="d" * 40)
    assert result["state"] == "BLOCKED"
    assert "EXPECTED_TARGET_COMMIT_MISMATCH" in result["blockers"]


def test_expired_signed_evidence_blocks_review():
    result = review(now_ts="2026-10-04T22:00:00Z")
    assert result["state"] == "BLOCKED"
    assert "CERTIFICATION_NOT_CANDIDATE" in result["blockers"]


def test_revoked_certification_key_blocks_review():
    result = review(certification_trust_roots=roots(revoked=True))
    assert result["state"] == "BLOCKED"
    assert "CERTIFICATION_NOT_CANDIDATE" in result["blockers"]


def test_missing_global_worker_signed_dimension_blocks_review():
    manifest = certification_manifest()
    del manifest["evidence"]["GLOBAL_WORKER_READINESS"]
    result = review(manifest)
    assert result["state"] == "BLOCKED"
    assert "CERTIFICATION_EVIDENCE_DIMENSION_SET_MISMATCH" in result["blockers"]


def test_reverification_rejects_non_mapping_manifest_fail_closed():
    result = reverify_certification_manifest(
        None,
        certification_trust_roots=TRUST_ROOTS,
        now_ts=NOW,
    )
    assert result["certification_verified"] is False
    assert "CERTIFICATION_MANIFEST_INVALID" in result["blockers"]
    assert result["execution_allowed"] is False


def test_review_digest_is_deterministic():
    manifest = certification_manifest()
    a = review(manifest)
    b = review(deepcopy(manifest))
    assert a["review_digest"] == b["review_digest"]


def test_checkpoint_patch_candidate_is_staged_only():
    result = review()
    candidate = build_checkpoint_patch_candidate(result)
    assert candidate["requires_explicit_checkpoint_save"] is True
    assert candidate["automatic_checkpoint_write"] is False
    assert candidate["checkpoint_saved"] is False
    assert candidate["execution_allowed"] is False
    assert candidate["external_action_executed"] is False
    record = candidate["patch"]["aion_core_completion_review"]
    assert record["state"] == "READY_FOR_OWNER_REVIEW"
    assert record["owner_decision_recorded"] is False
    assert record["core_complete"] is False
    assert record["core_frozen"] is False


def test_checkpoint_patch_can_use_existing_checkpoint_master_explicitly():
    result = review()
    candidate = build_checkpoint_patch_candidate(result)
    master = new_checkpoint_master(
        {"system": {"state": "SAFE"}},
        base_revision=0,
        created_at=NOW,
        source_refs=["v2.21-test"],
    )
    staged = append_checkpoint_patch(
        master,
        event_id=candidate["recommended_event_id"],
        patch=candidate["patch"],
        expected_revision=0,
        created_at=NOW,
        evidence_refs=[result["review_digest"]],
    )
    restored = reconstruct_checkpoint(staged)
    record = restored["snapshot"]["aion_core_completion_review"]
    assert record["review_digest"] == result["review_digest"]
    assert record["core_complete"] is False
    assert record["core_frozen"] is False
    assert restored["execution_allowed"] is False


def test_tampered_review_digest_cannot_build_checkpoint_candidate():
    result = review()
    result["review_digest"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        build_checkpoint_patch_candidate(result)


def test_checkpoint_candidate_rejects_unsafe_review_field():
    result = review()
    result["core_frozen"] = True
    with pytest.raises(ValueError, match="unsafe review field"):
        build_checkpoint_patch_candidate(result)


def test_review_gate_has_no_network_or_automatic_persistence_paths():
    source = Path("atlasquant_aion_core_completion_review.py").read_text(
        encoding="utf-8"
    )
    for banned in (
        "import requests",
        "requests.",
        "urlopen",
        "subprocess",
        "save_runtime_checkpoint(",
        "merge_pull_request",
        "deploy",
    ):
        assert banned not in source.lower()
