"""A157 RED-first diagnostic: legacy A137 workflow job check.

This temporary first commit deliberately mirrors A137's narrow analysis,
so the adversarial YAML mutations in A157 CI prove its false negatives.
It WILL be replaced by a strict fail-closed YAML parser in the same
isolated Draft PR, before any claim of passing tests.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from tools.aion_p0_workflow_credential_surface_a137 import inspect_one as legacy_inspect

ROOT = Path(__file__).resolve().parents[1]
CRITICAL = {
    "autopilot-v107.yml": "autopilot",
    "coleta_automatica.yml": "coletar",
    "aion-runtime-checkpoint-bootstrap.yml": "bootstrap",
    "aion-runtime-checkpoint-migrate.yml": "migrate",
}
BACKUPS = {
    "atlasquant-checkpoint.yml": "checkpoint",
    "atlasquant-source-backup.yml": "backup",
}


def inspect_critical_workflow(name: str, source: str) -> dict[str, Any]:
    old=legacy_inspect(name, source)
    return {
        "workflow": name,
        "source_shape_strict": old["target_p0_fence_ok"],
        "findings": [] if old["target_p0_fence_ok"] else ["LEGACY_FENCE_REJECTED"],
        "no_live_iam_verified": True,
        "real_writes_allowed": False,
        "verdict": "HARD_NO_GO_A157_WORKFLOW_CUSTODY_UNENROLLED",
    }


def inspect_readonly_backup(name: str, source: str) -> dict[str, Any]:
    # RED-first placeholder, intentionally does not enforce backup shape.
    return {
        "workflow": name,
        "source_shape_strict": True,
        "findings": [],
        "no_live_iam_verified": True,
        "real_writes_allowed": False,
        "verdict": "HARD_NO_GO_A157_WORKFLOW_CUSTODY_UNENROLLED",
    }
