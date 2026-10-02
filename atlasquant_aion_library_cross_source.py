"""Deterministic cross-source comparison for AION Library documents.

This module never decides truth or changes document state. It only compares
reviewable metadata/provenance fields within the same tenant/workspace and
returns bounded review hints for a human reviewer.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
import re
import unicodedata

SCHEMA = "ATLASQUANT_AION_LIBRARY_CROSS_SOURCE_V1"
MAX_PEERS = 100
MAX_HINTS = 100


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _fold(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", _clean(value, 500))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _fold(value)).strip()


def _fingerprint(record: Mapping[str, Any]) -> str:
    intel = record.get("document_intelligence")
    if isinstance(intel, Mapping):
        return _clean(intel.get("content_fingerprint"), 160)
    return ""


def compare_library_records(
    candidate: Mapping[str, Any] | None,
    peers: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    row = dict(candidate or {})
    tenant = _clean(row.get("tenant_id"), 120)
    workspace = _clean(row.get("workspace_id"), 120)
    document_id = _clean(row.get("document_id"), 120)
    title_key = _token(row.get("title"))
    source_ref = _clean(row.get("source_reference"), 400)
    version = _clean(row.get("document_version"), 120)
    checksum = _clean(row.get("checksum"), 180)
    fingerprint = _fingerprint(row)

    blockers: list[str] = []
    if not tenant or not workspace or not document_id:
        blockers.append("CANDIDATE_SCOPE_OR_ID_MISSING")
    if blockers:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "blockers": blockers,
            "hints": [],
            "compared_peers": 0,
            "skipped_scope_mismatch": 0,
            "conflict_candidate_count": 0,
            "automatic_state_change": False,
            "truth_decision_made": False,
            "external_action_executed": False,
        }

    hints: list[dict[str, Any]] = []
    compared = 0
    skipped_scope = 0
    seen: set[tuple[str, str]] = set()

    for peer_raw in list(peers or [])[:MAX_PEERS]:
        if not isinstance(peer_raw, Mapping):
            continue
        peer = dict(peer_raw)
        if (
            _clean(peer.get("tenant_id"), 120) != tenant
            or _clean(peer.get("workspace_id"), 120) != workspace
        ):
            skipped_scope += 1
            continue
        peer_id = _clean(peer.get("document_id"), 120)
        if not peer_id or peer_id == document_id:
            continue
        compared += 1

        peer_title = _token(peer.get("title"))
        peer_source = _clean(peer.get("source_reference"), 400)
        peer_version = _clean(peer.get("document_version"), 120)
        peer_checksum = _clean(peer.get("checksum"), 180)
        peer_fingerprint = _fingerprint(peer)

        relations: list[tuple[str, str, str]] = []
        if checksum and peer_checksum and checksum == peer_checksum:
            relations.append((
                "DUPLICATE_CONTENT",
                "INFO",
                "Mesmo checksum em documentos distintos.",
            ))
        elif fingerprint and peer_fingerprint and fingerprint == peer_fingerprint:
            relations.append((
                "DUPLICATE_EXTRACTED_CONTENT",
                "INFO",
                "Mesmo fingerprint de conteúdo extraído.",
            ))

        if source_ref and peer_source and source_ref == peer_source and checksum and peer_checksum and checksum != peer_checksum:
            relations.append((
                "SOURCE_CONTENT_CHANGED",
                "REVIEW",
                "A mesma referência de origem aparece com conteúdo diferente.",
            ))

        if title_key and peer_title and title_key == peer_title:
            if version and peer_version and version == peer_version and checksum and peer_checksum and checksum != peer_checksum:
                relations.append((
                    "POTENTIAL_CONFLICT_SAME_VERSION",
                    "REVIEW",
                    "Mesmo título e versão, mas checksum diferente.",
                ))
            elif version and peer_version and version != peer_version:
                relations.append((
                    "VERSION_DIVERGENCE",
                    "REVIEW",
                    "Mesmo título com versões documentais diferentes.",
                ))

        for relation, severity, reason in relations:
            dedupe = (peer_id, relation)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            hints.append({
                "peer_document_id": peer_id,
                "peer_title": _clean(peer.get("title"), 400),
                "relation": relation,
                "severity": severity,
                "reason": reason,
                "evidence_refs": [
                    ref for ref in (
                        peer_id,
                        peer_checksum,
                        _clean((peer.get("provenance") or {}).get("provenance_id") if isinstance(peer.get("provenance"), Mapping) else "", 180),
                    ) if ref
                ],
                "automatic_conflict_classification": False,
                "requires_human_review": True,
            })
            if len(hints) >= MAX_HINTS:
                break
        if len(hints) >= MAX_HINTS:
            break

    conflict_candidates = sum(
        hint["relation"] in {"SOURCE_CONTENT_CHANGED", "POTENTIAL_CONFLICT_SAME_VERSION"}
        for hint in hints
    )
    return {
        "schema": SCHEMA,
        "status": "REVIEW_HINTS_READY",
        "blockers": [],
        "candidate_document_id": document_id,
        "compared_peers": compared,
        "skipped_scope_mismatch": skipped_scope,
        "hints": hints,
        "conflict_candidate_count": int(conflict_candidates),
        "automatic_state_change": False,
        "truth_decision_made": False,
        "external_action_executed": False,
    }


__all__ = ["SCHEMA", "MAX_PEERS", "MAX_HINTS", "compare_library_records"]
