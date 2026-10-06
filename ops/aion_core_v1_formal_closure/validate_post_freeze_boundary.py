#!/usr/bin/env python3
"""Validate the post-freeze authority boundary without performing any action."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops.aion_core_v1_formal_closure.core_freeze_ceremony import TARGET


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-attestation", type=Path, required=True)
    args = parser.parse_args()

    row = read_json(args.freeze_attestation)
    blockers = []
    if row.get("state") != "CORE_FREEZE_PERSISTENCE_ATTESTED":
        blockers.append("CORE_FREEZE_ATTESTATION_REQUIRED")
    if row.get("target_commit_sha") != TARGET:
        blockers.append("CORE_FREEZE_TARGET_MISMATCH")
    if row.get("core_complete") is not True:
        blockers.append("CORE_COMPLETE_NOT_ATTESTED")
    if row.get("core_frozen") is not True:
        blockers.append("CORE_NOT_FROZEN")
    for field in (
        "merge_authorized",
        "deploy_authorized",
        "execution_allowed",
        "worker_armed",
        "global_worker_activation_authorized",
    ):
        if row.get(field) is not False:
            blockers.append(f"POST_FREEZE_UNSAFE_FIELD:{field}")
    for field in (
        "requires_separate_merge_decision",
        "requires_separate_deploy_decision",
        "requires_separate_global_worker_arming",
        "requires_separate_global_worker_activation",
    ):
        if row.get(field) is not True:
            blockers.append(f"POST_FREEZE_SEPARATION_MISSING:{field}")

    unique = sorted(set(blockers))
    result = {
        "schema": "AION_CORE_V1_POST_FREEZE_BOUNDARY_CHECK_V1",
        "state": "CORE_V1_FROZEN_RELEASE_BOUNDARIES_CLOSED" if not unique else "BLOCKED",
        "blockers": unique,
        "target_commit_sha": row.get("target_commit_sha"),
        "core_complete": not unique,
        "core_frozen": not unique,
        "merge_authorized": False,
        "deploy_authorized": False,
        "worker_armed": False,
        "worker_activation_authorized": False,
        "next_steps": {
            "merge": "SEPARATE_OWNER_DECISION_REQUIRED",
            "deploy": "SEPARATE_OWNER_DECISION_REQUIRED_AFTER_MERGE_EVIDENCE",
            "global_worker_arming": "SEPARATE_ARMING_CEREMONY_REQUIRED",
            "global_worker_activation": "SEPARATE_ACTIVATION_CEREMONY_REQUIRED_AFTER_PERSISTED_ARMED_STATE",
        },
        "network_called": False,
        "executes_action": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not unique else 2


if __name__ == "__main__":
    raise SystemExit(main())
