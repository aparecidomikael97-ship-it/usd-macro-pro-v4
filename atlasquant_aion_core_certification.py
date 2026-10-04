"""AION V2.20 Core Certification contract.

Aggregates independent CI/test evidence into a deterministic certification
candidate. This module never executes production work and never authorizes Core
Freeze. A successful result means only that the documented certification
criteria have evidence attached.

Core Freeze remains a separate explicit owner decision after certification.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_CORE_CERTIFICATION_V1"
CERTIFICATION_VERSION = 1

REQUIRED_DIMENSIONS = (
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
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _exact_true(value: Any) -> bool:
    return value is True


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def normalize_evidence(dimension: str, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize one certification evidence row without upgrading its truth."""
    key = _clean(dimension, 80).upper()
    item = dict(raw or {})
    state = _clean(item.get("state"), 40).upper()
    source = _clean(item.get("source"), 80).upper()
    run_id = _clean(item.get("run_id"), 120)
    commit_sha = _clean(item.get("commit_sha"), 64).lower()
    evidence_digest = _clean(item.get("evidence_digest"), 80).lower()
    test_count = _positive_int(item.get("test_count"))
    verified = _exact_true(item.get("verified"))

    blockers: list[str] = []
    if key not in REQUIRED_DIMENSIONS:
        blockers.append("DIMENSION_UNKNOWN")
    if state != "VERIFIED":
        blockers.append("EVIDENCE_STATE_NOT_VERIFIED")
    if source not in {"CI", "TEST_SUITE", "DRILL", "AUDIT"}:
        blockers.append("EVIDENCE_SOURCE_INVALID")
    if not run_id:
        blockers.append("EVIDENCE_RUN_ID_REQUIRED")
    if not _SHA_RE.fullmatch(commit_sha):
        blockers.append("EVIDENCE_COMMIT_SHA_INVALID")
    if not _DIGEST_RE.fullmatch(evidence_digest):
        blockers.append("EVIDENCE_DIGEST_INVALID")
    if test_count is None:
        blockers.append("EVIDENCE_TEST_COUNT_INVALID")
    if not verified:
        blockers.append("EVIDENCE_NOT_VERIFIED")

    if (
        key in REQUIRED_DIMENSIONS
        and source in {"CI", "TEST_SUITE", "DRILL", "AUDIT"}
        and run_id
        and _SHA_RE.fullmatch(commit_sha)
        and test_count is not None
        and _DIGEST_RE.fullmatch(evidence_digest)
    ):
        expected_digest = _digest({
            "dimension": key,
            "commit_sha": commit_sha,
            "run_id": run_id,
            "test_count": test_count,
            "source": source,
        })
        if evidence_digest != expected_digest:
            blockers.append("EVIDENCE_DIGEST_MISMATCH")

    return {
        "dimension": key,
        "state": state or "UNKNOWN",
        "source": source,
        "run_id": run_id,
        "commit_sha": commit_sha,
        "evidence_digest": evidence_digest,
        "test_count": test_count or 0,
        "verified": verified,
        "blockers": blockers,
        "eligible": not blockers,
    }


def certification_evidence_digest(evidence: Mapping[str, Any]) -> str:
    canonical = {
        key: normalize_evidence(key, value if isinstance(value, Mapping) else {})
        for key, value in sorted(dict(evidence or {}).items())
    }
    return _digest(canonical)


def certify_core(
    evidence: Mapping[str, Any],
    *,
    target_commit_sha: str,
    canonical_gates_green: Any,
    global_worker_readiness_green: Any,
    core_freeze_authorized: Any = False,
) -> dict[str, Any]:
    """Build a certification candidate from explicit independent evidence.

    The core_freeze_authorized argument is observed only to prove that
    certification cannot perform or infer a freeze. Even True does not change
    core_frozen.
    """
    target = _clean(target_commit_sha, 64).lower()
    if not _SHA_RE.fullmatch(target):
        raise ValueError("target_commit_sha must be a 40-char git SHA")
    if canonical_gates_green is not True and canonical_gates_green is not False:
        raise ValueError("canonical_gates_green must be exact boolean")
    if global_worker_readiness_green is not True and global_worker_readiness_green is not False:
        raise ValueError("global_worker_readiness_green must be exact boolean")
    if core_freeze_authorized is not True and core_freeze_authorized is not False:
        raise ValueError("core_freeze_authorized must be exact boolean")

    raw = dict(evidence or {})
    rows: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []

    unexpected = sorted(set(str(k).upper() for k in raw) - set(REQUIRED_DIMENSIONS))
    if unexpected:
        blockers.append("UNEXPECTED_EVIDENCE_DIMENSION")

    for dimension in REQUIRED_DIMENSIONS:
        value = raw.get(dimension)
        row = normalize_evidence(
            dimension,
            value if isinstance(value, Mapping) else {},
        )
        rows[dimension] = row
        if not row["eligible"]:
            blockers.append(f"DIMENSION_NOT_CERTIFIED:{dimension}")
        elif row["commit_sha"] != target:
            blockers.append(f"DIMENSION_COMMIT_MISMATCH:{dimension}")

    if canonical_gates_green is not True:
        blockers.append("CANONICAL_GATES_NOT_GREEN")
    if global_worker_readiness_green is not True:
        blockers.append("GLOBAL_WORKER_READINESS_NOT_GREEN")

    total_tests = sum(row["test_count"] for row in rows.values())
    if total_tests < 1000:
        blockers.append("CERTIFICATION_TEST_VOLUME_BELOW_MINIMUM")

    unique = sorted(set(blockers))
    candidate = not unique

    manifest_body = {
        "schema": SCHEMA,
        "version": CERTIFICATION_VERSION,
        "target_commit_sha": target,
        "required_dimensions": list(REQUIRED_DIMENSIONS),
        "evidence": rows,
        "canonical_gates_green": canonical_gates_green is True,
        "global_worker_readiness_green": global_worker_readiness_green is True,
        "total_evidence_test_count": total_tests,
        "blockers": unique,
        "state": "CERTIFICATION_CANDIDATE" if candidate else "BLOCKED",
    }
    manifest_digest = _digest(manifest_body)

    return {
        **manifest_body,
        "manifest_digest": manifest_digest,
        "certification_candidate": candidate,
        "core_complete_candidate": candidate,
        "core_complete_claim_allowed": False,
        "owner_core_complete_review_required": candidate,
        "core_freeze_requested": core_freeze_authorized is True,
        "core_freeze_authorized_by_this_module": False,
        "core_frozen": False,
        "freeze_requires_explicit_owner_action_outside_certification": True,
        "execution_allowed": False,
        "worker_armed": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "external_action_executed": False,
        "executes_action": False,
    }


def synthetic_evidence_row(
    dimension: str,
    *,
    commit_sha: str,
    run_id: str,
    test_count: int,
    source: str = "TEST_SUITE",
) -> dict[str, Any]:
    """Test/helper constructor. It creates evidence-shaped data, not authority."""
    key = _clean(dimension, 80).upper()
    target = _clean(commit_sha, 64).lower()
    tests = _positive_int(test_count)
    if key not in REQUIRED_DIMENSIONS:
        raise ValueError("unknown certification dimension")
    if not _SHA_RE.fullmatch(target):
        raise ValueError("invalid commit sha")
    if not _clean(run_id, 120):
        raise ValueError("run_id required")
    if tests is None:
        raise ValueError("positive test_count required")
    source_key = _clean(source, 80).upper()
    if source_key not in {"CI", "TEST_SUITE", "DRILL", "AUDIT"}:
        raise ValueError("invalid evidence source")
    body = {
        "dimension": key,
        "commit_sha": target,
        "run_id": _clean(run_id, 120),
        "test_count": tests,
        "source": source_key,
    }
    return {
        "state": "VERIFIED",
        "source": source_key,
        "run_id": body["run_id"],
        "commit_sha": target,
        "evidence_digest": _digest(body),
        "test_count": tests,
        "verified": True,
    }


__all__ = [
    "SCHEMA",
    "CERTIFICATION_VERSION",
    "REQUIRED_DIMENSIONS",
    "normalize_evidence",
    "certification_evidence_digest",
    "certify_core",
    "synthetic_evidence_row",
]
