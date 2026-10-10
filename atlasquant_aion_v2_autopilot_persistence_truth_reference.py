"""Inert review of Autopilot persistence truth and source-level health claims.

This reference makes NO writes, imports no runtime application or provider
modules, and grants NO retry, physical, deployment or reconciliation authority.
An observation is a supplied report, not an independently trusted receipt.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import Any

TARGETS = (
    "SCANNER_PATH",
    "DAILY_CACHE_PATH",
    "RESEARCH_TF_CACHE_PATH",
    "SERIES_PATH",
    "MASTER_PATH",
    "NEWS_CURRENT_PATH",
    "AION_LIVE_EVENT_JOURNAL_PATH",
    "NEWS_VALIDATION_PATH",
    "SIGNAL_LIFECYCLE_PATH",
    "HOME_SNAPSHOT_PATH",
    "QUOTA_SHADOW_PATH",
    "STATUS_PATH",
)
STATES = frozenset({
    "NOT_ATTEMPTED", "SKIPPED_CONDITION", "PRE_WRITE_ABORT",
    "REPORTED_HTTP_SUCCESS", "REPORTED_MATCHING_READBACK",
    "UNKNOWN_OUTCOME", "CONFLICT", "VALIDATION_REJECTED",
    "FAILED", "DENIED",
})
UNCERTAIN = frozenset({"UNKNOWN_OUTCOME", "CONFLICT", "VALIDATION_REJECTED"})
UNKNOWN_STATE = "MISSING_EVIDENCE"


def evaluate_persistence_reports(
    observations: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Conservative aggregation: a complete status report is not a receipt.

    Does NOT treat a reported HTTP 2xx or matching GET as independent
    origin, custody, rollback protection or remote durability. All
    operational admission decisions remain denied regardless of input.
    """
    if observations is None:
        observations = {}
    if not isinstance(observations, Mapping):
        raise ValueError("OBSERVATIONS_MAPPING_REQUIRED")
    unexpected = sorted(set(observations) - set(TARGETS))
    rows = []
    counts: dict[str, int] = {}
    for target in TARGETS:
        evidence = observations.get(target)
        if evidence is None:
            state = UNKNOWN_STATE
        elif not isinstance(evidence, Mapping):
            state = "INVALID_EVIDENCE"
        else:
            reported_state = evidence.get("state")
            state = (reported_state if type(reported_state) is str and
                     reported_state in STATES else "INVALID_EVIDENCE")
        counts[state] = counts.get(state, 0) + 1
        rows.append({"target": target, "reported_state": state,
                     "trusted_provenance_verified": False,
                     "remote_durability_certified": False})
    has_uncertainty = bool(any(x in counts for x in UNCERTAIN))
    complete = not unexpected and not (
        UNKNOWN_STATE in counts or "INVALID_EVIDENCE" in counts
    )
    all_reported_readback = (
        complete and counts.get("REPORTED_MATCHING_READBACK", 0) == len(TARGETS)
    )
    if unexpected:
        posture = "UNREVIEWED_TARGET_BLOCK"
    elif has_uncertainty:
        posture = "RECONCILIATION_REQUIRED"
    elif not complete:
        posture = "EVIDENCE_INCOMPLETE"
    elif all_reported_readback:
        posture = "ONLY_SELF_REPORTED_READBACK_NO_INDEPENDENT_CERTIFICATE"
    else:
        posture = "UNVERIFIED_OR_NOT_PERSISTED"
    return {
        "schema": "ATLASQUANT_AION_V2_PERSISTENCE_TRUTH_REFERENCE_V1",
        "posture": posture,
        "expected_targets": len(TARGETS),
        "reported_targets": len(observations),
        "missing_targets": [r["target"] for r in rows
                            if r["reported_state"] == UNKNOWN_STATE],
        "unexpected_targets": unexpected,
        "state_counts": counts,
        "rows": rows,
        "reconciliation_required": has_uncertainty,
        "source_reports_only": True,
        "remote_write_executed": False,
        "real_authorization_granted": False,
        "safe_to_retry": False,
        "safe_to_resume": False,
        "independent_attestation_verified": False,
        "remote_durability_certified": False,
        "safe_to_deploy": False,
    }


def _fn(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise ValueError("EXPECTED_ONE_FUNCTION_" + name)
    return matches[0]


def source_health_claim_review(source: str) -> dict[str, Any]:
    """Inspect status claims without importing or running Autopilot."""
    tree = ast.parse(source)
    summary = _fn(tree, "status_summary")
    main = _fn(tree, "main")
    healthy_values = [
        v for n in ast.walk(summary) if isinstance(n, ast.Dict)
        for k, v in zip(n.keys, n.values)
        if isinstance(k, ast.Constant) and k.value == "healthy"
    ]
    threshold = len(healthy_values) == 1 and any(
        isinstance(n, ast.Compare) and len(n.ops) == 1
        and isinstance(n.ops[0], ast.Lt) and len(n.comparators) == 1
        and isinstance(n.comparators[0], ast.Constant)
        and n.comparators[0].value == 8
        and isinstance(n.left, ast.Call) and isinstance(n.left.func, ast.Name)
        and n.left.func.id == "len" and len(n.left.args) == 1
        and isinstance(n.left.args[0], ast.Name) and n.left.args[0].id == "errors"
        for n in ast.walk(healthy_values[0])
    ) if len(healthy_values) == 1 else False
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)]
    status_builds = [
        n.lineno for n in calls
        if isinstance(n.func, ast.Name) and n.func.id == "status_summary"
    ]
    status_writes = [
        n.lineno for n in calls
        if isinstance(n.func, ast.Name) and n.func.id == "gh_put_json"
        and n.args and isinstance(n.args[0], ast.Name)
        and n.args[0].id == "STATUS_PATH"
    ]
    writes_after_build = (
        len(status_builds) == 1 and len(status_writes) == 1
        and status_writes[0] > status_builds[0]
    )
    zero_exit = any(
        isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
        and type(n.value.value) is int and n.value.value == 0
        for n in ast.walk(main)
    )
    return {
        "schema": "ATLASQUANT_AION_V2_AUTOPILOT_HEALTH_SOURCE_REVIEW_V1",
        "healthy_can_be_true_with_fewer_than_8_errors": threshold,
        "status_is_written_after_healthy_is_calculated": writes_after_build,
        "main_contains_zero_exit": zero_exit,
        "source_only": True,
        "runtime_executed": False,
        "writes_executed": False,
        "operational_health_certified": False,
        "remote_durability_certified": False,
        "safe_to_deploy": False,
    }


def review_repository(root: Path) -> dict[str, Any]:
    source = (Path(root) / "autopilot_v107.py").read_text(encoding="utf-8")
    return source_health_claim_review(source)


__all__ = [
    "TARGETS", "evaluate_persistence_reports",
    "source_health_claim_review", "review_repository",
]
