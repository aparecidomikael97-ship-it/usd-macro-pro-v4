#!/usr/bin/env python3
"""Validate the unsigned Core V1 V2.20 OPS packet without network or secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

TARGET = "662eab4dc4f5bb009fa1ca89f87530df74d30ddf"
PACKET_SCHEMA = "AION_CORE_V1_V220_UNSIGNED_EVIDENCE_PACKET_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_CERTIFICATION_EVIDENCE_V1"
DIMENSIONS = (
    "TRUST_ROOT_AUTHORITY",
    "DURABLE_EXECUTION",
    "CAPABILITY_ISOLATION",
    "OPERATIONAL_RESILIENCE",
    "MULTIAGENT_MEMORY_GOVERNANCE",
    "CONSTITUTION_POLICY_KERNEL",
    "PROVIDER_NEUTRAL_MODEL_GATEWAY",
    "END_TO_END",
    "LOAD",
    "CHAOS",
    "RECOVERY",
    "BACKUP_RESTORE",
    "CONCURRENCY",
    "COST_GOVERNANCE",
    "AUDIT_REPLAY",
    "CANONICAL_GATES",
    "GLOBAL_WORKER_READINESS",
)
PENDING_SIGNATURE_FIELDS = (
    "key_id",
    "key_version",
    "issued_at",
    "expires_at",
    "signature_b64",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_packet(packet: Any) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(packet, dict):
        return {"state": "BLOCKED", "blockers": ["PACKET_NOT_OBJECT"], "executes_action": False}

    if packet.get("schema") != PACKET_SCHEMA:
        blockers.append("PACKET_SCHEMA_INVALID")
    if packet.get("packet_state") != "UNSIGNED_PREPARATION_ONLY":
        blockers.append("PACKET_STATE_INVALID")
    if packet.get("formal_target_commit_sha") != TARGET:
        blockers.append("TARGET_COMMIT_MISMATCH")
    if packet.get("do_not_treat_as_certificate") is not True:
        blockers.append("CERTIFICATE_SAFETY_FLAG_MISSING")
    if packet.get("external_signer_required") is not True:
        blockers.append("EXTERNAL_SIGNER_FLAG_MISSING")
    if packet.get("private_key_must_remain_outside_repository") is not True:
        blockers.append("PRIVATE_KEY_BOUNDARY_MISSING")
    if packet.get("production_trust_root_required") is not True:
        blockers.append("TRUST_ROOT_BOUNDARY_MISSING")

    rows = packet.get("rows")
    if not isinstance(rows, list):
        blockers.append("ROWS_NOT_LIST")
        rows = []
    if packet.get("row_count") != len(DIMENSIONS) or len(rows) != len(DIMENSIONS):
        blockers.append("ROW_COUNT_MISMATCH")

    seen: set[str] = set()
    total = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            blockers.append(f"ROW_NOT_OBJECT:{index}")
            continue
        dimension = row.get("dimension")
        if dimension not in DIMENSIONS:
            blockers.append(f"DIMENSION_INVALID:{index}")
            continue
        if dimension in seen:
            blockers.append(f"DIMENSION_DUPLICATE:{dimension}")
        seen.add(dimension)

        claim = row.get("claim")
        if not isinstance(claim, dict):
            blockers.append(f"CLAIM_NOT_OBJECT:{dimension}")
            continue
        if claim.get("schema") != EVIDENCE_SCHEMA:
            blockers.append(f"EVIDENCE_SCHEMA_INVALID:{dimension}")
        if claim.get("state") != "VERIFIED":
            blockers.append(f"EVIDENCE_STATE_INVALID:{dimension}")
        if claim.get("source") != "CI":
            blockers.append(f"EVIDENCE_SOURCE_INVALID:{dimension}")
        if claim.get("commit_sha") != TARGET:
            blockers.append(f"EVIDENCE_TARGET_MISMATCH:{dimension}")
        if claim.get("verified") is not True:
            blockers.append(f"EVIDENCE_VERIFIED_CLAIM_INVALID:{dimension}")

        test_count = claim.get("test_count")
        if isinstance(test_count, bool) or not isinstance(test_count, int) or test_count <= 0:
            blockers.append(f"EVIDENCE_TEST_COUNT_INVALID:{dimension}")
            continue
        total += test_count

        body = {
            "dimension": dimension,
            "commit_sha": claim.get("commit_sha"),
            "run_id": claim.get("run_id"),
            "test_count": test_count,
            "source": claim.get("source"),
        }
        if claim.get("evidence_digest") != sha256(body):
            blockers.append(f"EVIDENCE_DIGEST_MISMATCH:{dimension}")

        leaked = [field for field in PENDING_SIGNATURE_FIELDS if field in claim]
        if leaked:
            blockers.append(f"UNSIGNED_PACKET_CONTAINS_SIGNATURE_FIELD:{dimension}")
        if row.get("signature_fields_pending") != list(PENDING_SIGNATURE_FIELDS):
            blockers.append(f"SIGNATURE_PENDING_FIELDS_MISMATCH:{dimension}")

    if set(DIMENSIONS) != seen:
        blockers.append("REQUIRED_DIMENSIONS_MISMATCH")
    if packet.get("contract_test_count_sum") != total:
        blockers.append("CONTRACT_TEST_COUNT_SUM_MISMATCH")
    minimum = packet.get("minimum_required_test_count_sum")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or total < minimum:
        blockers.append("CERTIFICATION_TEST_VOLUME_BELOW_MINIMUM")

    digest_material = deepcopy(packet)
    supplied_digest = str(digest_material.pop("unsigned_packet_digest", ""))
    expected_digest = sha256(digest_material)
    if packet.get("packet_digest_method") != "sha256(canonical-json(packet-without-unsigned_packet_digest))":
        blockers.append("PACKET_DIGEST_METHOD_INVALID")
    if supplied_digest != expected_digest:
        blockers.append("UNSIGNED_PACKET_DIGEST_MISMATCH")

    unique = sorted(set(blockers))
    return {
        "schema": "AION_CORE_V1_V220_UNSIGNED_PACKET_VALIDATION_V1",
        "state": "VALID_UNSIGNED_PACKET" if not unique else "BLOCKED",
        "blockers": unique,
        "formal_target_commit_sha": TARGET,
        "required_dimension_count": len(DIMENSIONS),
        "observed_dimension_count": len(seen),
        "contract_test_count_sum": total,
        "packet_digest": expected_digest,
        "contains_private_key": False,
        "contains_signature": False,
        "network_called": False,
        "executes_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    result = validate_packet(read_json(args.packet))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "VALID_UNSIGNED_PACKET" else 2


if __name__ == "__main__":
    raise SystemExit(main())
