#!/usr/bin/env python3
"""Perform the explicit real V2.23 runtime write only with an exact execution flag.

This tool never retries an ambiguous write. It does not sign owner material,
record a decision, freeze the Core, merge, deploy, or arm the Global Worker.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlasquant_aion_core_freeze_preflight import verify_preflight_still_current
from atlasquant_aion_external_persistence_attestation import (
    stage_runtime_persistence_candidate,
    verify_external_checkpoint_persistence,
)
from atlasquant_aion_memory import (
    load_runtime_checkpoint,
    runtime_configuration_status,
    save_runtime_checkpoint,
)
from atlasquant_aion_trust_root import TrustRootRegistry

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
EXPECTED_BRANCH = "atlasquant-runtime"
EXPECTED_PATH = "dados/aion/checkpoint_master.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(message: str, *, result: Any = None, output_dir: Path | None = None) -> int:
    if result is not None and output_dir is not None:
        write_json(output_dir / "v223_failed_result.json", result)
    print(json.dumps({"state": "BLOCKED", "reason": message, "automatic_retry": False}, sort_keys=True))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--checkpoint-master", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute-v223-write", action="store_true")
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    trust_roots = TrustRootRegistry.from_mapping(read_json(args.trust_root))
    master = read_json(args.checkpoint_master)
    preflight = read_json(args.preflight)
    out = args.output_dir

    current = load_runtime_checkpoint()
    write_json(out / "v223_runtime_before.json", current)
    if current.get("status") != "CONFIRMED":
        return fail("runtime is not CONFIRMED", result=current, output_dir=out)
    if current.get("source") != f"GitHub:{EXPECTED_BRANCH}:{EXPECTED_PATH}":
        return fail("runtime source mismatch", result=current, output_dir=out)
    current_sha = str(current.get("sha") or "").strip()
    if current_sha != args.expected_runtime_sha:
        return fail(
            f"runtime CAS changed: expected {args.expected_runtime_sha}, observed {current_sha}",
            result=current,
            output_dir=out,
        )

    now = now_iso()
    recheck = verify_preflight_still_current(
        preflight,
        certification_manifest=manifest,
        certification_trust_roots=trust_roots,
        expected_target_commit_sha=TARGET,
        checkpoint_master=master,
        now_ts=now,
    )
    write_json(out / "v222_recheck_before_v223.json", recheck)
    if recheck.get("state") != "CURRENT":
        return fail("V2.22 is not CURRENT; rebuild ceremony", result=recheck, output_dir=out)

    staged = stage_runtime_persistence_candidate(
        current.get("checkpoint"),
        master,
        preflight,
        expected_target_commit_sha=TARGET,
    )
    write_json(out / "v223_staged_candidate.json", staged)
    if staged.get("state") != "STAGED":
        return fail("V2.23 staging failed", result=staged, output_dir=out)

    config = runtime_configuration_status()
    write_json(out / "v223_runtime_config_status.json", config)
    dry_summary = {
        "schema": "AION_CORE_V1_V223_WRITE_PREFLIGHT_V1",
        "state": "READY_FOR_EXPLICIT_V223_WRITE",
        "formal_target_commit_sha": TARGET,
        "runtime_sha": current_sha,
        "expected_runtime_digest_before_writer_normalization": staged.get("expected_runtime_digest"),
        "write_ready": config.get("write_ready") is True,
        "execute_requested": args.execute_v223_write is True,
        "owner_decision": "UNDECIDED",
        "core_frozen": False,
        "worker_armed": False,
        "automatic_retry": False,
        "external_action_executed": False,
    }
    write_json(out / "v223_write_preflight.json", dry_summary)

    if not args.execute_v223_write:
        print(json.dumps(dry_summary, sort_keys=True))
        return 0
    if config.get("write_ready") is not True:
        return fail("runtime write credential is not configured", result=config, output_dir=out)

    saved = save_runtime_checkpoint(
        staged["runtime_checkpoint_candidate"],
        approved=True,
        expected_sha=current_sha,
        allow_global_arming_transition=False,
    )
    write_json(out / "v223_save_result.json", saved)

    if saved.get("status") != "CONFIRMED" or saved.get("saved") is not True or saved.get("verified") is not True:
        # Critical invariant: never retry here, especially if the transport outcome is ambiguous.
        return fail(
            "runtime write was not positively confirmed; reconcile manually and do not retry",
            result=saved,
            output_dir=out,
        )

    receipt = saved.get("write_receipt")
    if not isinstance(receipt, dict):
        return fail("confirmed save returned no write receipt", result=saved, output_dir=out)

    attestation = verify_external_checkpoint_persistence(
        checkpoint_master=master,
        preflight=preflight,
        certification_manifest=manifest,
        certification_trust_roots=trust_roots,
        expected_target_commit_sha=TARGET,
        runtime_result=saved,
        write_receipt=receipt,
        now_ts=now_iso(),
    )
    write_json(out / "v223_attestation.json", attestation)
    if attestation.get("state") != "READY_FOR_OWNER_SIGNATURE_CEREMONY":
        return fail(
            "V2.23 persistence attestation blocked; do not proceed to owner signature",
            result=attestation,
            output_dir=out,
        )

    summary = {
        "schema": "AION_CORE_V1_REAL_V223_RESULT_V1",
        "state": "READY_FOR_OWNER_SIGNATURE_CEREMONY",
        "formal_target_commit_sha": TARGET,
        "runtime_sha_before": current_sha,
        "runtime_sha_after": saved.get("sha"),
        "write_receipt_intent_id": receipt.get("intent_id"),
        "digest_to_sign": attestation.get("digest_to_sign"),
        "owner_decision": "UNDECIDED",
        "core_freeze_authorized": False,
        "core_frozen": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "automatic_retry": False,
    }
    write_json(out / "v223_success_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
