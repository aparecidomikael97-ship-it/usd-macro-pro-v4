"""Human-gated evidence promotion for AION Developer correction plans.

This module evaluates whether reproduction evidence is sufficient to present a
root-cause hypothesis to a human reviewer. It never confirms a cause
automatically. Confirmation requires an explicit human approval call and stays
in-memory unless another separately governed persistence path is used.

No function executes tests, edits files, applies patches, calls processes or
network, commits, merges, deploys, publishes or enables real trading.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_developer_correction import SCHEMA as CORRECTION_SCHEMA
from atlasquant_aion_observability import redact_text
from atlasquant_aion_developer_manifest import correction_manifest_id

SCHEMA = "ATLASQUANT_AION_DEVELOPER_EVIDENCE_GATE_V1"
CONFIRMATION_SCHEMA = "ATLASQUANT_AION_DEVELOPER_CAUSE_CONFIRMATION_V1"


def _clean(value: Any, limit: int = 1200) -> str:
    return " ".join(redact_text(value).replace("\x00", "").split())[:limit]


def _list(values: Sequence[Any] | None, limit: int = 80) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        text = _clean(raw, 500)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _digest(value: Any, length: int = 18) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length].upper()


def _hypothesis_labels(correction: Mapping[str, Any]) -> set[str]:
    return {
        str(item.get("label") or "")
        for item in list(correction.get("hypotheses") or [])
        if isinstance(item, Mapping) and str(item.get("label") or "")
    }


def evaluate_evidence_promotion(
    correction: Mapping[str, Any],
    *,
    hypothesis_label: Any,
    test_id: Any,
    before_state: Any,
    after_state: Any,
    changed_files: Sequence[Any] | None,
    evidence_refs: Sequence[Any] | None,
    intervention_summary: Any,
    scope_preserved: bool,
    snapshot_digest: Any,
    diagnostic_id: Any,
) -> dict[str, Any]:
    """Evaluate evidence readiness without applying truth promotion."""
    if correction.get("schema") != CORRECTION_SCHEMA:
        raise ValueError("invalid developer correction plan")
    if str(correction.get("state") or "") != "WAITING_HUMAN":
        raise ValueError("correction plan must remain WAITING_HUMAN")
    if bool(correction.get("root_cause_confirmed")):
        raise ValueError("root cause is already confirmed")

    lineage = correction.get("lineage") if isinstance(correction.get("lineage"), Mapping) else {}
    expected_snapshot = str(lineage.get("snapshot_digest") or "")
    expected_diagnostic = str(lineage.get("diagnostic_id") or "")
    supplied_snapshot = _clean(snapshot_digest, 200)
    supplied_diagnostic = _clean(diagnostic_id, 200)
    if not expected_snapshot or supplied_snapshot != expected_snapshot:
        raise ValueError("snapshot lineage mismatch")
    if not expected_diagnostic or supplied_diagnostic != expected_diagnostic:
        raise ValueError("diagnostic lineage mismatch")

    correction_manifest = correction_manifest_id(correction)
    hypothesis = _clean(hypothesis_label, 160)
    if hypothesis not in _hypothesis_labels(correction):
        raise ValueError("hypothesis is not part of correction plan")

    test = _clean(test_id, 500)
    allowed_tests = set(_list(correction.get("test_candidates"), 120))
    before = _clean(before_state, 30).upper()
    after = _clean(after_state, 30).upper()
    changed = _list(changed_files, 40)
    allowed_scope = set(_list(correction.get("target_files"), 60))
    refs = _list(evidence_refs, 60)
    intervention = _clean(intervention_summary, 1600)

    blockers: list[str] = []
    if not test:
        blockers.append("TEST_ID_REQUIRED")
    elif allowed_tests and test not in allowed_tests:
        blockers.append("TEST_NOT_IN_CORRECTION_CANDIDATES")
    if before != "FAIL":
        blockers.append("BEFORE_STATE_MUST_BE_FAIL")
    if after != "PASS":
        blockers.append("AFTER_STATE_MUST_BE_PASS")
    if not changed:
        blockers.append("CHANGED_FILES_REQUIRED")
    if any(path not in allowed_scope for path in changed):
        blockers.append("CHANGED_FILE_OUTSIDE_ALLOWED_SCOPE")
    if not scope_preserved:
        blockers.append("SCOPE_NOT_PRESERVED")
    if not intervention:
        blockers.append("INTERVENTION_SUMMARY_REQUIRED")
    if len(refs) < 2:
        blockers.append("BEFORE_AND_AFTER_EVIDENCE_REQUIRED")
    if len(set(refs)) < 2:
        blockers.append("EVIDENCE_REFS_MUST_BE_DISTINCT")

    blockers = list(dict.fromkeys(blockers))
    state = "READY_FOR_HUMAN_CAUSE_REVIEW" if not blockers else "INSUFFICIENT_EVIDENCE"
    gate_seed = {
        "correction_id": correction.get("correction_id"),
        "correction_manifest_id": correction_manifest,
        "hypothesis": hypothesis,
        "test": test,
        "before": before,
        "after": after,
        "changed": changed,
        "refs": refs,
    }
    return {
        "schema": SCHEMA,
        "gate_id": "DEVGATE-" + _digest(gate_seed),
        "state": state,
        "correction_id": str(correction.get("correction_id") or ""),
        "correction_manifest_id": correction_manifest,
        "lineage": {
            "snapshot_digest": expected_snapshot,
            "diagnostic_id": expected_diagnostic,
            "package_id": str(lineage.get("package_id") or ""),
        },
        "hypothesis": {
            "label": hypothesis,
            "current_truth_status": "UNKNOWN",
            "proposed_truth_status": "CONFIRMED",
            "promotion_applied": False,
        },
        "reproduction": {
            "test_id": test,
            "before_state": before,
            "after_state": after,
            "changed_files": changed,
            "scope_preserved": bool(scope_preserved),
            "intervention_summary": intervention,
            "evidence_refs": refs,
        },
        "blockers": blockers,
        "human_review_required": True,
        "automatic_truth_promotion": False,
        "root_cause_confirmed": False,
        "analysis_only": True,
        "persists_checkpoint": False,
        "executes_repository_code": False,
        "runs_tests": False,
        "writes_files": False,
        "network_called": False,
        "subprocess_called": False,
        "automatic_fix": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "tool_output_is_authority": False,
    }


def confirm_root_cause_human_review(
    correction: Mapping[str, Any],
    gate: Mapping[str, Any],
    *,
    approved: bool,
    reviewer_actor: Any,
    review_evidence_refs: Sequence[Any] | None,
) -> dict[str, Any]:
    """Apply a session-local truth promotion only after explicit human review."""
    if correction.get("schema") != CORRECTION_SCHEMA:
        raise ValueError("invalid correction plan")
    if gate.get("schema") != SCHEMA:
        raise ValueError("invalid evidence promotion gate")
    if str(gate.get("state") or "") != "READY_FOR_HUMAN_CAUSE_REVIEW":
        raise ValueError("evidence gate is not ready for human review")
    if str(gate.get("correction_id") or "") != str(correction.get("correction_id") or ""):
        raise ValueError("gate correction lineage mismatch")
    current_manifest = correction_manifest_id(correction)
    if str(gate.get("correction_manifest_id") or "") != current_manifest:
        raise ValueError("gate correction manifest mismatch")
    if approved is not True:
        raise ValueError("explicit human approval required")

    actor = _clean(reviewer_actor, 160)
    refs = _list(review_evidence_refs, 40)
    if not actor:
        raise ValueError("human reviewer actor required")
    if not refs:
        raise ValueError("human review evidence required")

    out = deepcopy(dict(correction))
    hypothesis = gate.get("hypothesis") if isinstance(gate.get("hypothesis"), Mapping) else {}
    label = _clean(hypothesis.get("label"), 160)
    if label not in _hypothesis_labels(correction):
        raise ValueError("gate hypothesis no longer matches correction plan")

    confirmation_seed = {
        "correction_id": correction.get("correction_id"),
        "gate_id": gate.get("gate_id"),
        "actor": actor,
        "refs": refs,
    }
    out["root_cause_confirmed"] = True
    out["root_cause_truth_status"] = "CONFIRMED"
    out["confirmed_root_cause"] = {
        "schema": CONFIRMATION_SCHEMA,
        "confirmation_id": "DEVCAUSE-" + _digest(confirmation_seed),
        "hypothesis_label": label,
        "reviewer_actor": actor,
        "gate_id": str(gate.get("gate_id") or ""),
        "correction_manifest_id": current_manifest,
        "evidence_refs": refs,
        "human_approved": True,
        "source": "HUMAN_REVIEW",
    }
    out["state"] = "CAUSE_CONFIRMED_WAITING_IMPLEMENTATION"
    out["patch_generated"] = False
    out["analysis_only"] = True
    out["persists_checkpoint"] = False
    out["executes_repository_code"] = False
    out["runs_tests"] = False
    out["writes_files"] = False
    out["network_called"] = False
    out["subprocess_called"] = False
    out["automatic_fix"] = False
    out["automatic_commit"] = False
    out["automatic_merge"] = False
    out["automatic_deploy"] = False
    out["production_change_allowed"] = False
    out["real_trading_enabled"] = False
    out["tool_output_is_authority"] = False
    return out


__all__ = [
    "SCHEMA",
    "CONFIRMATION_SCHEMA",
    "evaluate_evidence_promotion",
    "confirm_root_cause_human_review",
]
