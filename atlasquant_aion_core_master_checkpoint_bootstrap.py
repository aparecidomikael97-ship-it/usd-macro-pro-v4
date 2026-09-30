"""Read-only bootstrap bridge from Checkpoint Mestre into AION Core evidence.

The Checkpoint Mestre remains the single official continuity source. This module
does not create a second memory store and performs no network or external I/O.
It validates the latest checkpoint pointer before exposing a bounded snapshot to
AION Core as stable internal evidence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

from atlasquant_aion_checkpoint_latest import (
    LATEST_POINTER_PATH,
    validate_latest_checkpoint,
)

SCHEMA = "ATLASQUANT_AION_CORE_MASTER_CHECKPOINT_BOOTSTRAP_V1"
VERSION = "1"
MAX_DECISIONS = 200
MAX_PENDING = 100


def _root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parent


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("checkpoint document must be an object")
    return value


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def master_checkpoint_bootstrap_snapshot(
    root: Path | None = None,
) -> dict[str, Any]:
    base = _root(root)
    validation = validate_latest_checkpoint(base)
    if validation.get("ok") is not True:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "MASTER_CHECKPOINT_BLOCKED",
            "reason": "LATEST_CHECKPOINT_VALIDATION_FAILED",
            "errors": list(validation.get("errors") or [])[:50],
            "evidence_ready": False,
            "runtime_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
            "executes_action": False,
        }

    try:
        pointer = _load_json(base / LATEST_POINTER_PATH)
        manifest_rel = str(pointer.get("latest_manifest") or "")
        manifest = _load_json(base / manifest_rel)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "MASTER_CHECKPOINT_BLOCKED",
            "reason": "MASTER_CHECKPOINT_LOAD_FAILED",
            "errors": [type(exc).__name__],
            "evidence_ready": False,
            "runtime_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
            "executes_action": False,
        }

    raw_decisions = manifest.get("decisions")
    raw_pending = manifest.get("pending")
    if not isinstance(raw_decisions, list) or len(raw_decisions) > MAX_DECISIONS:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "MASTER_CHECKPOINT_BLOCKED",
            "reason": "DECISION_SET_INVALID",
            "errors": [],
            "evidence_ready": False,
            "runtime_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
            "executes_action": False,
        }
    if not isinstance(raw_pending, list) or len(raw_pending) > MAX_PENDING:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "MASTER_CHECKPOINT_BLOCKED",
            "reason": "PENDING_SET_INVALID",
            "errors": [],
            "evidence_ready": False,
            "runtime_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
            "executes_action": False,
        }

    decisions: list[dict[str, Any]] = []
    for item in raw_decisions:
        if not isinstance(item, Mapping):
            continue
        decisions.append({
            "id": str(item.get("id") or ""),
            "state": str(item.get("state") or ""),
            "implemented": item.get("implemented") is True,
            "validated": item.get("validated") is True,
        })

    multiagent = manifest.get("multiagent")
    roles = []
    if isinstance(multiagent, Mapping) and isinstance(multiagent.get("roles"), list):
        roles = [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
            }
            for item in multiagent["roles"]
            if isinstance(item, Mapping)
        ]

    economics = manifest.get("economics")
    monetization = manifest.get("monetization")
    priority = manifest.get("ecosystem_priority")
    finops = manifest.get("finops")
    stack = manifest.get("business_stack")

    snapshot_payload = {
        "latest_date": str(pointer.get("latest_date") or ""),
        "manifest": manifest_rel,
        "decisions": decisions,
        "pending": [str(x) for x in raw_pending],
        "economics": deepcopy(dict(economics)) if isinstance(economics, Mapping) else {},
        "monetization": deepcopy(dict(monetization)) if isinstance(monetization, Mapping) else {},
        "ecosystem_priority": deepcopy(dict(priority)) if isinstance(priority, Mapping) else {},
        "finops": deepcopy(dict(finops)) if isinstance(finops, Mapping) else {},
        "multiagent_roles": roles,
        "business_stack": {
            key: value
            for key, value in dict(stack).items()
            if key in {
                "draft_prs",
                "current_runtime_authorized",
                "merge_authorized_by_this_checkpoint",
                "deploy_authorized_by_this_checkpoint",
                "billing_authorized_by_this_checkpoint",
                "quota_application_authorized_by_this_checkpoint",
            }
        } if isinstance(stack, Mapping) else {},
    }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "MASTER_CHECKPOINT_LOADED",
        "reason": "LATEST_CHECKPOINT_VALIDATED",
        **snapshot_payload,
        "snapshot_digest": _digest(snapshot_payload),
        "evidence_ready": True,
        "runtime_authorized": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "automatic_memory_write": False,
        "executes_action": False,
    }


def master_checkpoint_evidence(
    root: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = master_checkpoint_bootstrap_snapshot(root)
    if snapshot.get("evidence_ready") is not True:
        return [], snapshot

    source_ref = str(snapshot.get("manifest") or LATEST_POINTER_PATH)
    rows = [
        {
            "claim": "checkpoint.master.latest_date",
            "value": snapshot["latest_date"],
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
        {
            "claim": "checkpoint.master.decisions",
            "value": snapshot["decisions"],
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
        {
            "claim": "checkpoint.master.pending",
            "value": snapshot["pending"],
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
        {
            "claim": "checkpoint.master.economics",
            "value": {
                "economics": snapshot["economics"],
                "finops": snapshot["finops"],
                "monetization": snapshot["monetization"],
            },
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
        {
            "claim": "checkpoint.master.ecosystem_priority",
            "value": snapshot["ecosystem_priority"],
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
        {
            "claim": "checkpoint.master.multiagent_roles",
            "value": snapshot["multiagent_roles"],
            "truth_state": "CONFIRMED",
            "source": "AtlasQuant Checkpoint Mestre",
            "source_ref": source_ref,
            "time_sensitive": False,
        },
    ]
    return rows, snapshot


def augment_system_context_with_master_checkpoint(
    system_context: Mapping[str, Any] | None,
    *,
    root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = dict(system_context) if isinstance(system_context, Mapping) else {}
    existing = base.get("core_evidence")
    current_rows = (
        [dict(x) for x in existing if isinstance(x, Mapping)]
        if isinstance(existing, (list, tuple))
        else []
    )
    rows, snapshot = master_checkpoint_evidence(root)
    if rows:
        base["core_evidence"] = current_rows + rows
    elif current_rows:
        base["core_evidence"] = current_rows
    return base, snapshot


__all__ = [
    "SCHEMA",
    "VERSION",
    "master_checkpoint_bootstrap_snapshot",
    "master_checkpoint_evidence",
    "augment_system_context_with_master_checkpoint",
]
