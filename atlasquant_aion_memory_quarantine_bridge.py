"""Checkpoint bridge for AION Memory Quarantine.

Candidates can be staged into a versioned Checkpoint Mestre namespace. This
bridge never saves remotely. Promotion requires the quarantine contract's
explicit ADMIN review plus evidence verification and only then updates the
existing top-level memory_layers section as UNKNOWN truth.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping, Sequence

from atlasquant_aion_memory import (
    AION_MEMORY_QUARANTINE_NAMESPACE,
    ensure_operating_checkpoint,
)
from atlasquant_aion_memory_quarantine import (
    SCHEMA,
    admit_memory_candidate,
    empty_quarantine,
    promote_memory_candidate,
    quarantine_checkpoint_bundle,
    quarantine_checkpoint_integrity,
)


def _store_from_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    raw = checkpoint.get(AION_MEMORY_QUARANTINE_NAMESPACE)
    if raw is None:
        store = empty_quarantine()
        store["memory_layers"] = checkpoint["memory_layers"]
        return store
    integrity = quarantine_checkpoint_integrity(raw if isinstance(raw, Mapping) else None)
    if integrity.get("state") != "MATCH":
        raise ValueError("MEMORY_QUARANTINE_DIGEST_MISMATCH")
    store = empty_quarantine()
    store["candidates"] = [
        deepcopy(dict(row))
        for row in list(raw.get("candidates") or [])
        if isinstance(row, Mapping)
    ]
    store["memory_layers"] = checkpoint["memory_layers"]
    return store


def load_quarantine_checkpoint(
    checkpoint: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = ensure_operating_checkpoint(checkpoint)
    present = AION_MEMORY_QUARANTINE_NAMESPACE in payload
    store = _store_from_checkpoint(payload)
    return store, {
        "schema": SCHEMA,
        "state": "CONNECTED" if present else "EMPTY",
        "namespace": AION_MEMORY_QUARANTINE_NAMESPACE,
        "candidate_count": len(store["candidates"]),
        "external_persisted": False,
        "executes_action": False,
    }


def _attach_store(
    checkpoint: Mapping[str, Any],
    store: Mapping[str, Any],
    *,
    update_layers: bool,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    payload[AION_MEMORY_QUARANTINE_NAMESPACE] = quarantine_checkpoint_bundle(store)
    if update_layers:
        payload["memory_layers"] = deepcopy(store.get("memory_layers") or payload["memory_layers"])
    payload["operating"]["dirty"] = True
    return payload


def stage_memory_candidate(
    checkpoint: Mapping[str, Any] | None,
    *,
    content: Any,
    source_type: Any,
    tenant_id: Any,
    workspace_id: Any,
    trusted_context: Mapping[str, Any] | None,
    subject_scope: Any = "workspace",
    observed_at: Any = "",
    valid_from: Any = "",
    valid_until: Any = "",
    provenance: Any = "",
    sensitivity: Any = "UNKNOWN",
    evidence_refs: Sequence[Any] | None = None,
    category: Any = "fact",
    version: Any = "1",
    requested_target: Any = "",
    now: Any = None,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    store = _store_from_checkpoint(payload)
    result = admit_memory_candidate(
        store,
        content=content,
        source_type=source_type,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        trusted_context=trusted_context,
        subject_scope=subject_scope,
        observed_at=observed_at,
        valid_from=valid_from,
        valid_until=valid_until,
        provenance=provenance,
        sensitivity=sensitivity,
        evidence_refs=evidence_refs,
        category=category,
        version=version,
        requested_target=requested_target,
        now=now,
    )
    changed = result.get("persisted") is True
    staged = _attach_store(payload, result["store"], update_layers=False) if changed else payload
    state = str((result.get("record") or {}).get("state") or "UNKNOWN")
    status = "STAGED" if changed else ("NO_CHANGE" if result.get("replay") is True else "BLOCKED")
    return {
        "schema": SCHEMA,
        "status": status,
        "admission_state": state,
        "record": result.get("record"),
        "checkpoint": staged,
        "requires_checkpoint_save": changed,
        "external_persisted": False,
        "memory_promoted": False,
        "executes_action": False,
        "real_trading_enabled": False,
    }


def stage_memory_promotion(
    checkpoint: Mapping[str, Any] | None,
    candidate_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    evidence_verifier: Callable[[Sequence[str]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = ensure_operating_checkpoint(checkpoint)
    store = _store_from_checkpoint(payload)
    result = promote_memory_candidate(
        store,
        candidate_id,
        trusted_context=trusted_context,
        evidence_verifier=evidence_verifier,
    )
    allowed = result.get("state") == "ADMITTED_UNCONFIRMED"
    staged = _attach_store(payload, result["store"], update_layers=True) if allowed else payload
    return {
        "schema": SCHEMA,
        "status": "STAGED" if allowed else "BLOCKED",
        "state": result.get("state"),
        "blockers": list(result.get("blockers") or []),
        "record": result.get("record"),
        "checkpoint": staged,
        "requires_checkpoint_save": allowed,
        "external_persisted": False,
        "memory_promoted": allowed,
        "truth_state": "UNKNOWN",
        "authority": "NONE",
        "executes_action": False,
        "real_trading_enabled": False,
    }


__all__ = [
    "load_quarantine_checkpoint",
    "stage_memory_candidate",
    "stage_memory_promotion",
]
