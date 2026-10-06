#!/usr/bin/env python3
"""Build real V2.20 -> V2.22 ceremony artifacts from externally signed evidence.

No network, runtime persistence, owner signature, owner decision, freeze, merge,
deploy, or worker activation is performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from atlasquant_aion_checkpoint_master import (
    append_checkpoint_patch,
    new_checkpoint_master,
    reconstruct_checkpoint,
)
from atlasquant_aion_core_certification import certify_core
from atlasquant_aion_core_completion_review import (
    build_checkpoint_patch_candidate,
    build_core_completion_review,
)
from atlasquant_aion_core_freeze_preflight import (
    build_core_freeze_preflight,
    verify_preflight_still_current,
)
from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-evidence", type=Path, required=True)
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--now-ts", required=True)
    parser.add_argument("--ceremony-id", required=True)
    parser.add_argument("--challenge-nonce", required=True)
    parser.add_argument("--issued-at", required=True)
    parser.add_argument("--expires-at", required=True)
    parser.add_argument("--checkpoint-base-snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    signed = read_json(args.signed_evidence)
    if signed.get("schema") != "AION_CORE_V1_V220_SIGNED_EVIDENCE_PACKET_V1":
        raise SystemExit("signed evidence packet schema invalid")
    if signed.get("formal_target_commit_sha") != TARGET:
        raise SystemExit("signed evidence target mismatch")
    evidence = signed.get("evidence")
    if not isinstance(evidence, dict):
        raise SystemExit("signed evidence map missing")

    trust_payload = read_json(args.trust_root)
    trust_roots = TrustRootRegistry.from_mapping(trust_payload)

    manifest = certify_core(
        evidence,
        target_commit_sha=TARGET,
        certification_trust_roots=trust_roots,
        now_ts=args.now_ts,
        core_freeze_authorized=False,
    )
    if manifest.get("state") != "CERTIFICATION_CANDIDATE":
        raise SystemExit("V2.20 blocked: " + ",".join(manifest.get("blockers") or []))

    review = build_core_completion_review(
        manifest,
        certification_trust_roots=trust_roots,
        now_ts=args.now_ts,
        expected_target_commit_sha=TARGET,
    )
    if review.get("state") != "READY_FOR_OWNER_REVIEW":
        raise SystemExit("V2.21 blocked: " + ",".join(review.get("blockers") or []))

    patch_candidate = build_checkpoint_patch_candidate(
        manifest,
        certification_trust_roots=trust_roots,
        now_ts=args.now_ts,
        expected_target_commit_sha=TARGET,
    )

    if args.checkpoint_base_snapshot:
        base_snapshot = read_json(args.checkpoint_base_snapshot)
        if not isinstance(base_snapshot, dict):
            raise SystemExit("checkpoint base snapshot must be a JSON object")
    else:
        base_snapshot = {
            "system": {
                "state": "AION_CORE_V1_FORMAL_CLOSURE",
                "technical_target_commit_sha": TARGET,
                "technical_closure_candidate_pr": 951,
            }
        }

    master = new_checkpoint_master(
        base_snapshot,
        base_revision=0,
        created_at=args.now_ts,
        source_refs=[
            "PR#951",
            manifest["manifest_digest"],
            review["review_digest"],
        ],
    )
    master = append_checkpoint_patch(
        master,
        event_id=patch_candidate["recommended_event_id"],
        patch=patch_candidate["patch"],
        expected_revision=0,
        created_at=args.now_ts,
        evidence_refs=[
            manifest["manifest_digest"],
            review["review_digest"],
            patch_candidate["patch_digest"],
        ],
    )
    reconstructed = reconstruct_checkpoint(master)
    if reconstructed.get("revision") != 1:
        raise SystemExit("logical checkpoint revision mismatch")

    preflight = build_core_freeze_preflight(
        manifest,
        certification_trust_roots=trust_roots,
        now_ts=args.now_ts,
        expected_target_commit_sha=TARGET,
        checkpoint_master=master,
        ceremony_id=args.ceremony_id,
        challenge_nonce=args.challenge_nonce,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
    )
    if preflight.get("state") != "READY_FOR_OWNER_DECISION_PREFLIGHT":
        raise SystemExit("V2.22 blocked: " + ",".join(preflight.get("blockers") or []))

    recheck = verify_preflight_still_current(
        preflight,
        certification_manifest=manifest,
        certification_trust_roots=trust_roots,
        expected_target_commit_sha=TARGET,
        checkpoint_master=master,
        now_ts=args.now_ts,
    )
    if recheck.get("state") != "CURRENT":
        raise SystemExit("V2.22 recheck blocked: " + ",".join(recheck.get("blockers") or []))

    out = args.output_dir
    write_json(out / "v220_certification_manifest.json", manifest)
    write_json(out / "v221_owner_review.json", review)
    write_json(out / "v221_checkpoint_patch_candidate.json", patch_candidate)
    write_json(out / "logical_checkpoint_master.json", master)
    write_json(out / "v222_preflight.json", preflight)
    write_json(out / "v222_recheck.json", recheck)

    summary = {
        "schema": "AION_CORE_V1_FORMAL_CLOSURE_PREP_RESULT_V1",
        "state": "READY_FOR_REAL_V223_PERSISTENCE",
        "formal_target_commit_sha": TARGET,
        "v220_state": manifest["state"],
        "v220_manifest_digest": manifest["manifest_digest"],
        "v221_state": review["state"],
        "v221_review_digest": review["review_digest"],
        "logical_checkpoint_revision": reconstructed["revision"],
        "logical_checkpoint_state_digest": reconstructed["state_digest"],
        "v222_state": preflight["state"],
        "v222_challenge_digest": preflight["challenge_digest"],
        "v222_current": True,
        "owner_decision": "UNDECIDED",
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "network_called": False,
        "runtime_modified": False,
        "executes_action": False,
    }
    write_json(out / "formal_closure_prep_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
