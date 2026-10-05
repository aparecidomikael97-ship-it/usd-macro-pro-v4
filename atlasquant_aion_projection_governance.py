"""Governance contract for disposable AION retrieval/vector projections.

A projection is never a source of truth. It may accelerate retrieval, including
future vector/embedding retrieval, but every hit must be re-bound to the current
canonical source before it may be treated as evidence.

No embedding provider or vector database is called here.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_RETRIEVAL_PROJECTION_V1"
CANONICAL_STATES = frozenset({
    "PROMOTED",
    "VALIDATED",
    "CONFLICTING",
    "STALE",
})
MAX_SOURCES = 5000
MAX_CHUNKS = 50000


def _clean(value: Any, limit: int = 2000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _refs(values: Sequence[Any] | None, limit: int = 80) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[: limit * 2]:
        value = _clean(raw, 300)
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


def _scope(context: Mapping[str, Any] | None) -> tuple[str, str]:
    raw = dict(context or {})
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not tenant or not workspace:
        raise ValueError("trusted tenant/workspace required")
    return tenant, workspace


def empty_projection() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "sources": rows,
        "chunks": [],
        "digest": _digest({"sources": [], "chunks": []}),
        "projection_only": True,
        "canonical_source": False,
        "rebuildable": True,
        "retrieval_does_not_validate": True,
        "vector_provider_connected": False,
        "external_persisted": False,
        "memory_promoted": False,
        "executes_action": False,
    }


def _canonical_source(
    raw: Mapping[str, Any],
    *,
    tenant: str,
    workspace: str,
) -> dict[str, Any]:
    item = dict(raw or {})
    source_id = _clean(item.get("source_id"), 160)
    source_version = _clean(item.get("source_version"), 120)
    content_digest = _clean(item.get("content_digest"), 180)
    state = _clean(item.get("canonical_state"), 40).upper()
    truth = _clean(item.get("truth_state") or "UNKNOWN", 40).upper()
    source_tenant = _clean(item.get("tenant_id"), 120)
    source_workspace = _clean(item.get("workspace_id"), 120)
    if not source_id or not source_version or not content_digest:
        raise ValueError("canonical source identity/version/digest required")
    if source_tenant != tenant or source_workspace != workspace:
        raise PermissionError("canonical source crosses trusted scope")
    if state not in CANONICAL_STATES:
        raise ValueError("source is not in an indexable canonical state")
    provenance = _refs(
        item.get("provenance_refs")
        if isinstance(item.get("provenance_refs"), (list, tuple))
        else []
    )
    if not provenance:
        raise ValueError("canonical source provenance required")
    taint = _refs(
        item.get("taint_labels")
        if isinstance(item.get("taint_labels"), (list, tuple))
        else []
    )
    # A governed promoted memory may not remain tainted. Reviewed library
    # records can remain CONFLICTING/STALE; retrieval must preserve that state.
    if state == "PROMOTED" and taint:
        raise ValueError("promoted canonical source cannot carry unresolved taint")
    return {
        "source_id": source_id,
        "tenant_id": tenant,
        "workspace_id": workspace,
        "source_version": source_version,
        "content_digest": content_digest,
        "canonical_state": state,
        "truth_state": truth,
        "provenance_refs": provenance,
        "taint_labels": taint,
    }


def rebuild_projection(
    canonical_records: Sequence[Mapping[str, Any]] | None,
    *,
    trusted_context: Mapping[str, Any] | None,
    projection_version: Any,
) -> dict[str, Any]:
    """Build a fresh projection from canonical records only.

    Existing projection state is intentionally not accepted: deletion and rebuild
    are the recovery model, preventing residual chunks from becoming durable truth.
    """
    tenant, workspace = _scope(trusted_context)
    version = _clean(projection_version, 120)
    if not version:
        raise ValueError("projection_version required")
    sources: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for raw in list(canonical_records or [])[:MAX_SOURCES]:
        source = _canonical_source(raw, tenant=tenant, workspace=workspace)
        if source["source_id"] in seen_sources:
            raise ValueError("duplicate canonical source_id")
        seen_sources.add(source["source_id"])
        sources.append(source)
        raw_chunks = raw.get("chunks") if isinstance(raw, Mapping) else []
        if not isinstance(raw_chunks, (list, tuple)):
            raw_chunks = []
        for ordinal, raw_chunk in enumerate(raw_chunks, start=1):
            if len(chunks) >= MAX_CHUNKS:
                break
            if isinstance(raw_chunk, Mapping):
                text = _clean(raw_chunk.get("text"), 4000)
                chunk_source_digest = _clean(raw_chunk.get("source_content_digest"), 180)
                if chunk_source_digest and chunk_source_digest != source["content_digest"]:
                    raise ValueError("chunk source digest mismatch")
            else:
                text = _clean(raw_chunk, 4000)
            if not text:
                continue
            chunk_digest = "sha256:" + sha256(text.encode("utf-8")).hexdigest()
            chunk_id = "RAG-" + sha256(
                (source["source_id"] + "\0" + str(ordinal) + "\0" + chunk_digest).encode("utf-8")
            ).hexdigest()[:24].upper()
            chunks.append({
                "chunk_id": chunk_id,
                "source_id": source["source_id"],
                "tenant_id": tenant,
                "workspace_id": workspace,
                "ordinal": ordinal,
                "text": text,
                "chunk_digest": chunk_digest,
                "source_version": source["source_version"],
                "source_content_digest": source["content_digest"],
                "canonical_state": source["canonical_state"],
                "truth_state": source["truth_state"],
                "provenance_refs": list(source["provenance_refs"]),
                "taint_labels": list(source["taint_labels"]),
                "retrieval_does_not_validate": True,
                "authority": "NONE",
            })
    payload = {
        "sources": sources,
        "chunks": chunks,
        "projection_version": version,
        "tenant_id": tenant,
        "workspace_id": workspace,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "digest": _digest(payload),
        "projection_only": True,
        "canonical_source": False,
        "rebuildable": True,
        "retrieval_does_not_validate": True,
        "vector_provider_connected": False,
        "external_persisted": False,
        "memory_promoted": False,
        "executes_action": False,
    }


def delete_source_projection(
    projection: Mapping[str, Any] | None,
    source_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Forget one source from the projection without touching canonical storage."""
    state = dict(projection or empty_projection())
    tenant, workspace = _scope(trusted_context)
    target = _clean(source_id, 160)
    if not target:
        raise ValueError("source_id required")
    if state.get("tenant_id") and (
        state.get("tenant_id") != tenant or state.get("workspace_id") != workspace
    ):
        raise PermissionError("projection crosses trusted scope")
    sources = [
        deepcopy(row)
        for row in list(state.get("sources") or [])
        if isinstance(row, Mapping) and row.get("source_id") != target
    ]
    chunks = [
        deepcopy(row)
        for row in list(state.get("chunks") or [])
        if isinstance(row, Mapping) and row.get("source_id") != target
    ]
    payload = {
        "sources": sources,
        "chunks": chunks,
        "projection_version": _clean(state.get("projection_version"), 120),
        "tenant_id": tenant,
        "workspace_id": workspace,
    }
    removed_sources = len(list(state.get("sources") or [])) - len(sources)
    removed_chunks = len(list(state.get("chunks") or [])) - len(chunks)
    return {
        "schema": SCHEMA,
        **payload,
        "digest": _digest(payload),
        "projection_only": True,
        "canonical_source": False,
        "rebuildable": True,
        "retrieval_does_not_validate": True,
        "vector_provider_connected": False,
        "external_persisted": False,
        "memory_promoted": False,
        "executes_action": False,
        "deletion": {
            "source_id": target,
            "removed_sources": removed_sources,
            "removed_chunks": removed_chunks,
        },
    }


def validate_projection_hit(
    hit: Mapping[str, Any],
    *,
    trusted_context: Mapping[str, Any] | None,
    canonical_resolver: Callable[[str], Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Rebind one retrieved chunk to the current canonical source.

    Similarity/retrieval ranking can never upgrade truth. If the source was
    deleted, changed version/digest, moved scope, or is no longer canonical,
    the projection hit is stale and blocked.
    """
    tenant, workspace = _scope(trusted_context)
    row = dict(hit or {})
    source_id = _clean(row.get("source_id"), 160)
    blockers: list[str] = []
    if row.get("tenant_id") != tenant or row.get("workspace_id") != workspace:
        blockers.append("SCOPE_MISMATCH")
    if not source_id:
        blockers.append("SOURCE_ID_MISSING")
    if not callable(canonical_resolver):
        raise TypeError("canonical_resolver required")
    current = canonical_resolver(source_id) if source_id else None
    if not isinstance(current, Mapping):
        blockers.append("CANONICAL_SOURCE_MISSING")
        current = {}
    else:
        try:
            canonical = _canonical_source(current, tenant=tenant, workspace=workspace)
        except Exception:
            blockers.append("CANONICAL_SOURCE_INVALID")
            canonical = {}
        if canonical:
            if row.get("source_version") != canonical["source_version"]:
                blockers.append("SOURCE_VERSION_CHANGED")
            if row.get("source_content_digest") != canonical["content_digest"]:
                blockers.append("SOURCE_DIGEST_CHANGED")
            if row.get("canonical_state") != canonical["canonical_state"]:
                blockers.append("SOURCE_STATE_CHANGED")
            if sorted(_refs(row.get("provenance_refs") or [])) != sorted(canonical["provenance_refs"]):
                blockers.append("PROVENANCE_CHANGED")
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCK_STALE_PROJECTION",
            "blockers": sorted(set(blockers)),
            "usable_as_evidence": False,
            "usable_as_confirmed_fact": False,
            "retrieval_does_not_validate": True,
            "authority": "NONE",
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "BOUND_CURRENT",
        "source_id": source_id,
        "chunk_id": _clean(row.get("chunk_id"), 160),
        "text": _clean(row.get("text"), 4000),
        "truth_state": _clean(row.get("truth_state") or "UNKNOWN", 40).upper(),
        "canonical_state": _clean(row.get("canonical_state"), 40).upper(),
        "provenance_refs": _refs(row.get("provenance_refs") or []),
        "taint_labels": _refs(row.get("taint_labels") or []),
        "usable_as_evidence": True,
        "usable_as_confirmed_fact": bool(
            row.get("truth_state") == "CONFIRMED"
            and row.get("canonical_state") in {"PROMOTED", "VALIDATED"}
            and not row.get("taint_labels")
        ),
        "retrieval_does_not_validate": True,
        "ranking_elevates_confidence": False,
        "authority": "NONE",
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "CANONICAL_STATES",
    "empty_projection",
    "rebuild_projection",
    "delete_source_projection",
    "validate_projection_hit",
]
