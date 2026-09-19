"""AtlasQuant source release-candidate evidence.

This module summarizes source-release evidence only. It never merges branches,
promotes production, copies runtime data, changes model weights or enables real
orders. Post-deploy validation remains mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math


@dataclass(frozen=True)
class SourceReleaseCandidateEvidence:
    integration_gate_ok: bool
    source_checkpoint_ok: bool
    quality_tests_total: int
    quality_tests_failed: int
    pr_mergeable: bool
    candidate_based_on_current_main: bool
    secret_hygiene_ok: bool
    production_health_baseline_ok: bool
    runtime_source_parity_ok: bool
    integration_ui_smoke_ok: bool
    runtime_data_files: int = 0
    browser_smoke_baseline_ok: bool = False
    pr_draft: bool = True


def _valid_bool(value: object) -> bool:
    return isinstance(value,bool)


def _valid_count(value: object) -> bool:
    if isinstance(value,bool):
        return False
    try:
        x=float(value)
        return math.isfinite(x) and x>=0 and x.is_integer()
    except Exception:
        return False


def assess_source_release_candidate(
    ev: SourceReleaseCandidateEvidence,
    *,
    min_quality_tests: int = 900,
) -> dict[str,Any]:
    hard:list[str]=[]
    pending:list[str]=[]

    bools=(
        ("integration_gate_ok",ev.integration_gate_ok),
        ("source_checkpoint_ok",ev.source_checkpoint_ok),
        ("pr_mergeable",ev.pr_mergeable),
        ("candidate_based_on_current_main",ev.candidate_based_on_current_main),
        ("secret_hygiene_ok",ev.secret_hygiene_ok),
        ("production_health_baseline_ok",ev.production_health_baseline_ok),
        ("runtime_source_parity_ok",ev.runtime_source_parity_ok),
        ("integration_ui_smoke_ok",ev.integration_ui_smoke_ok),
        ("browser_smoke_baseline_ok",ev.browser_smoke_baseline_ok),
        ("pr_draft",ev.pr_draft),
    )
    invalid_bools=[name for name,value in bools if not _valid_bool(value)]
    if invalid_bools:
        hard.append("Invalid boolean release evidence: "+", ".join(invalid_bools))

    counts=(
        ("quality_tests_total",ev.quality_tests_total),
        ("quality_tests_failed",ev.quality_tests_failed),
        ("runtime_data_files",ev.runtime_data_files),
        ("min_quality_tests",min_quality_tests),
    )
    invalid_counts=[name for name,value in counts if not _valid_count(value)]
    if invalid_counts:
        hard.append("Invalid release counts: "+", ".join(invalid_counts))

    if _valid_count(min_quality_tests) and int(min_quality_tests)<1:
        hard.append("Minimum quality-test threshold must be >= 1")
    if _valid_count(ev.quality_tests_total) and _valid_count(min_quality_tests):
        if int(ev.quality_tests_total)<max(1,int(min_quality_tests)):
            hard.append("Quality-test coverage below release threshold")
    if _valid_count(ev.quality_tests_failed) and int(ev.quality_tests_failed)>0:
        hard.append(f"{int(ev.quality_tests_failed)} quality test(s) failed")
    if (
        _valid_count(ev.quality_tests_total)
        and _valid_count(ev.quality_tests_failed)
        and int(ev.quality_tests_failed)>int(ev.quality_tests_total)
    ):
        hard.append("Failed-test count exceeds total tests")

    for name,value,message in (
        ("integration_gate_ok",ev.integration_gate_ok,"Integration source-only gate failed"),
        ("source_checkpoint_ok",ev.source_checkpoint_ok,"Source Checkpoint failed"),
        ("pr_mergeable",ev.pr_mergeable,"Pull request is not cleanly mergeable"),
        ("candidate_based_on_current_main",ev.candidate_based_on_current_main,"Candidate is behind/diverged from current main"),
        ("secret_hygiene_ok",ev.secret_hygiene_ok,"Repository secret hygiene failed"),
        ("production_health_baseline_ok",ev.production_health_baseline_ok,"Current production health baseline is not healthy"),
        ("runtime_source_parity_ok",ev.runtime_source_parity_ok,"Runtime source does not match integration candidate"),
        ("integration_ui_smoke_ok",ev.integration_ui_smoke_ok,"Integration desktop/mobile UI smoke failed or is missing"),
    ):
        if _valid_bool(value) and not value:
            hard.append(message)

    if _valid_count(ev.runtime_data_files) and int(ev.runtime_data_files)>0:
        hard.append("Source candidate contains runtime data changes")

    if _valid_bool(ev.browser_smoke_baseline_ok) and not ev.browser_smoke_baseline_ok:
        pending.append("Production browser smoke baseline needs a green re-check")
    if _valid_bool(ev.pr_draft) and ev.pr_draft:
        pending.append("Draft PR still requires human review before merge")

    source_reviewable=not hard
    if hard:
        status="BLOCKED"
    elif pending:
        status="SOURCE_REVIEWABLE_PENDING_MANUAL"
    else:
        status="SOURCE_REVIEWABLE"

    return {
        "status":status,
        "source_reviewable":source_reviewable,
        "hard_blocks":hard,
        "pending":pending,
        "manual_review_required":True,
        "automatic_merge_allowed":False,
        "automatic_promotion_allowed":False,
        "runtime_data_copy_allowed":False,
        "post_deploy_health_required":True,
        "post_deploy_browser_smoke_required":True,
        "real_orders_changed":False,
    }
