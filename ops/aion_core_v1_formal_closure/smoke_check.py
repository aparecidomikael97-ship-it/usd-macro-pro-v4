#!/usr/bin/env python3
"""OPS-only smoke checks for AION Core V1 formal closure tooling."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "ops" / "aion-core-v1-formal-closure" / "unsigned_v220_evidence_packet.json"
VALIDATOR = ROOT / "ops" / "aion_core_v1_formal_closure" / "validate_unsigned_v220_packet.py"

TOOLS = (
    "ops/aion_core_v1_formal_closure/export_v220_signing_bundle.py",
    "ops/aion_core_v1_formal_closure/apply_v220_signatures.py",
    "ops/aion_core_v1_formal_closure/prepare_v220_v222.py",
    "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py",
    "ops/aion_core_v1_formal_closure/prepare_v224_owner_signature.py",
    "ops/aion_core_v1_formal_closure/verify_v224_prepare_v225.py",
    "ops/aion_core_v1_formal_closure/perform_v225_v226.py",
    "ops/aion_core_v1_formal_closure/core_freeze_ceremony.py",
    "ops/aion_core_v1_formal_closure/prepare_core_freeze.py",
    "ops/aion_core_v1_formal_closure/perform_core_freeze.py",
    "ops/aion_core_v1_formal_closure/validate_post_freeze_boundary.py",
)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), str(PACKET)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        return completed.returncode
    result = json.loads(completed.stdout.strip())
    assert result["state"] == "VALID_UNSIGNED_PACKET"
    assert result["required_dimension_count"] == 17
    assert result["observed_dimension_count"] == 17
    assert result["contract_test_count_sum"] == 2729
    assert result["contains_private_key"] is False
    assert result["contains_signature"] is False
    assert result["network_called"] is False
    assert result["executes_action"] is False

    for rel in TOOLS:
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "ed25519privatekey.generate" not in text
        assert "privatekey.generate" not in text
        assert "generate_private_key" not in text

    v223 = (ROOT / "ops/aion_core_v1_formal_closure/perform_v223_runtime_write.py").read_text(encoding="utf-8")
    assert "--execute-v223-write" in v223
    assert "allow_global_arming_transition=False" in v223
    assert "automatic_retry" in v223

    v226 = (ROOT / "ops/aion_core_v1_formal_closure/perform_v225_v226.py").read_text(encoding="utf-8")
    assert "--execute-v226-write" in v226
    assert "allow_global_arming_transition=False" in v226
    assert "if not args.execute_v226_write" in v226
    assert v226.index("if not args.execute_v226_write") < v226.index("verify_owner_decision(")

    freeze_exec = (ROOT / "ops/aion_core_v1_formal_closure/perform_core_freeze.py").read_text(encoding="utf-8")
    assert "--execute-core-freeze" in freeze_exec
    assert "allow_global_arming_transition=False" in freeze_exec
    assert "if not args.execute_core_freeze" in freeze_exec
    assert freeze_exec.index("if not args.execute_core_freeze") < freeze_exec.index("registry.claim(")
    assert "merge_pull_request" not in freeze_exec
    assert "activate_global_worker_feature_flag" not in freeze_exec
    assert "persist_staged_global_arming" not in freeze_exec

    # Pure, public-key-only request test: positive V2.26 APPROVE can prepare a
    # freeze-signing request, but it still cannot freeze, merge, deploy or arm.
    from atlasquant_aion_trust_root import TrustRootRegistry
    from ops.aion_core_v1_formal_closure.core_freeze_ceremony import (
        TARGET,
        build_freeze_request,
        digest,
    )

    material = {
        "schema": "ATLASQUANT_AION_CORE_FREEZE_CEREMONY_MATERIAL_V1",
        "target_commit_sha": TARGET,
        "decision": "APPROVE_CORE_FREEZE",
        "decision_request_digest": "sha256:" + "1" * 64,
        "decision_signature_digest": "sha256:" + "2" * 64,
        "decision_record_digest": "sha256:" + "3" * 64,
        "decision_runtime_sha": "1" * 40,
        "decision_runtime_digest": "0123456789abcdef",
        "decision_write_intent_id": "ci-intent",
        "owner_decision_recorded": True,
        "decision_record_persisted": True,
        "core_freeze_ceremony_eligible": True,
        "core_freeze_execution_authorized": False,
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "execution_allowed": False,
        "worker_armed": False,
        "external_action_executed": False,
    }
    v226_attestation = {
        "state": "OWNER_DECISION_RECORD_PERSISTENCE_ATTESTED_APPROVE",
        "owner_decision": "APPROVE_CORE_FREEZE",
        "owner_decision_recorded": True,
        "decision_record_persisted": True,
        "persistence_attested": True,
        "core_freeze_ceremony_eligible": True,
        "core_freeze_execution_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "core_freeze_ceremony_material": material,
        "digest_to_core_freeze_ceremony": digest(material),
    }
    roots = TrustRootRegistry.from_mapping({
        "schema": "ATLASQUANT_AION_TRUST_ROOT_V1",
        "roots": [{
            "key_id": "ci-owner-public-only",
            "key_version": 1,
            "algorithm": "Ed25519",
            "public_key_b64": b64url(b"\x01" * 32),
            "status": "ACTIVE",
            "not_before": "2026-01-01T00:00:00Z",
            "not_after": "2027-01-01T00:00:00Z",
        }],
        "revoked_key_ids": [],
    })
    freeze = build_freeze_request(
        v226_attestation,
        owner_trust_roots=roots,
        now_ts="2026-10-06T18:00:30Z",
        ceremony_id="core-freeze-ci-20261006",
        nonce="core-freeze-ci-nonce-0001",
        issued_at="2026-10-06T18:00:00Z",
        expires_at="2026-10-06T18:02:00Z",
        key_id="ci-owner-public-only",
        key_version=1,
    )
    assert freeze["state"] == "READY_FOR_EXTERNAL_CORE_FREEZE_SIGNATURE"
    assert freeze["request"]["core_freeze_execution_authorized"] is False
    assert freeze["request"]["core_frozen"] is False
    assert freeze["request"]["merge_authorized"] is False
    assert freeze["request"]["deploy_authorized"] is False
    assert freeze["request"]["worker_armed"] is False
    assert freeze["executes_action"] is False

    print(json.dumps({
        "state": "OPS_FORMAL_CLOSURE_SMOKE_PASS",
        "packet_digest": result["packet_digest"],
        "dimension_count": 17,
        "test_count_sum": 2729,
        "private_key_generation_present": False,
        "v223_write_requires_explicit_flag": True,
        "v226_write_requires_explicit_flag": True,
        "core_freeze_write_requires_explicit_flag": True,
        "decision_nonce_consumed_in_dry_run": False,
        "freeze_nonce_consumed_in_dry_run": False,
        "freeze_request_requires_v226_approve": True,
        "post_freeze_merge_deploy_worker_default_closed": True,
        "executes_action": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
