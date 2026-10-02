"""Bounded Checkpoint Mestre representation for AION Library review state.

Only reviewed metadata/audit state is stored. Raw PDF bytes, extracted passages,
provider/model output, OCR output and semantic-memory promotion are forbidden.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_LIBRARY_CHECKPOINT_V1"
MAX_RECORDS = 100
MAX_REVIEW_HISTORY = 500
DOCUMENT_STATES = frozenset({
    "VALIDATED", "CONFLICTING", "STALE", "QUARANTINED", "REJECTED",
})


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _strings(values: Any, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    out: list[str] = []
    for raw in list(values)[:limit]:
        value = _clean(raw, item_limit)
        if value and value not in out:
            out.append(value)
    return out


def _metadata(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, str] = {}
    for key, value in list(raw.items())[:30]:
        k = _clean(key, 80)
        v = _clean(value, 500)
        if k and v:
            out[k] = v
    return out


def _quality(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key in ("score", "band", "coverage_ratio", "chars_per_page", "failure_ratio"):
        value = raw.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            out[key] = value
        else:
            text = _clean(value, 80)
            if text:
                out[key] = text
    return out


def normalize_library_record(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(raw or {})
    document_id = _clean(row.get("document_id"), 120)
    tenant_id = _clean(row.get("tenant_id"), 120)
    workspace_id = _clean(row.get("workspace_id"), 120)
    if not document_id or not tenant_id or not workspace_id:
        return {}

    state = _clean(row.get("state"), 40).upper()
    if state not in DOCUMENT_STATES:
        state = "QUARANTINED"

    prov_raw = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    provenance = {
        key: value
        for key, value in {
            "provenance_id": _clean(prov_raw.get("provenance_id"), 120),
            "tenant_id": _clean(prov_raw.get("tenant_id"), 120),
            "domain_id": _clean(prov_raw.get("domain_id"), 120),
            "source_type": _clean(prov_raw.get("source_type"), 80),
            "source_reference": _clean(prov_raw.get("source_reference"), 500),
            "checksum": _clean(prov_raw.get("checksum"), 180),
            "author": _clean(prov_raw.get("author"), 240),
            "publisher": _clean(prov_raw.get("publisher"), 240),
            "published_at": _clean(prov_raw.get("published_at"), 100),
            "retrieved_at": _clean(prov_raw.get("retrieved_at"), 100),
            "document_version": _clean(prov_raw.get("document_version"), 120),
            "rights_status": _clean(prov_raw.get("rights_status"), 80),
            "review_status": _clean(prov_raw.get("review_status"), 80),
            "stale_reason": _clean(prov_raw.get("stale_reason"), 500),
        }.items()
        if value
    }
    conflict_refs = _strings(prov_raw.get("conflict_refs"), limit=50, item_limit=180)
    if conflict_refs:
        provenance["conflict_refs"] = conflict_refs

    intel_raw = (
        row.get("document_intelligence")
        if isinstance(row.get("document_intelligence"), Mapping)
        else {}
    )
    intelligence = {
        key: value
        for key, value in {
            "checksum": _clean(intel_raw.get("checksum"), 180),
            "content_fingerprint": _clean(intel_raw.get("content_fingerprint"), 180),
            "pdf_version": _clean(intel_raw.get("pdf_version"), 80),
            "scanned_likelihood": _clean(intel_raw.get("scanned_likelihood"), 40),
        }.items()
        if value
    }
    for key in ("page_count", "extracted_pages", "extracted_chars"):
        value = intel_raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            intelligence[key] = value
    intelligence["ocr_recommended"] = intel_raw.get("ocr_recommended") is True
    quality = _quality(intel_raw.get("quality"))
    if quality:
        intelligence["quality"] = quality
    metadata = _metadata(intel_raw.get("metadata"))
    if metadata:
        intelligence["metadata"] = metadata

    topic_raw = row.get("topic_classification")
    topic_classification: dict[str, Any] = {}
    if isinstance(topic_raw, Mapping):
        for key, value in list(topic_raw.items())[:30]:
            k = _clean(key, 80)
            if not k:
                continue
            if isinstance(value, bool):
                topic_classification[k] = value
            elif isinstance(value, (int, float)):
                topic_classification[k] = value
            elif isinstance(value, (list, tuple, set)):
                topic_classification[k] = _strings(value, limit=30, item_limit=120)
            else:
                text = _clean(value, 240)
                if text:
                    topic_classification[k] = text

    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "workspace_id": workspace_id,
        "title": _clean(row.get("title"), 400),
        "author": _clean(row.get("author"), 240),
        "publisher": _clean(row.get("publisher"), 240),
        "published_at": _clean(row.get("published_at"), 100),
        "retrieved_at": _clean(row.get("retrieved_at"), 100),
        "document_version": _clean(row.get("document_version"), 120),
        "rights_status": _clean(row.get("rights_status"), 80),
        "source_reference": _clean(row.get("source_reference"), 500),
        "checksum": _clean(row.get("checksum"), 180),
        "summary": _clean(row.get("summary"), 1200),
        "state": state,
        "reason_codes": _strings(row.get("reason_codes"), limit=20, item_limit=240),
        "evidence_refs": _strings(row.get("evidence_refs"), limit=50, item_limit=180),
        "truth_state": _clean(row.get("truth_state"), 40) or "UNKNOWN",
        "authority": "NONE",
        "provenance": provenance,
        "document_intelligence": intelligence,
        "topic_classification": topic_classification,
        "raw_pdf_persisted": False,
        "passages_persisted": False,
        "memory_promoted": False,
        "executes_action": False,
    }


def normalize_library_records(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in list(values)[-MAX_RECORDS:]:
        if not isinstance(raw, Mapping):
            continue
        row = normalize_library_record(raw)
        doc_id = row.get("document_id")
        if not doc_id:
            continue
        if doc_id not in by_id:
            order.append(doc_id)
        by_id[doc_id] = row
    return [by_id[doc_id] for doc_id in order if doc_id in by_id][-MAX_RECORDS:]


def normalize_review_history(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    rows: list[dict[str, Any]] = []
    for raw in list(values)[-MAX_REVIEW_HISTORY:]:
        if not isinstance(raw, Mapping):
            continue
        document_id = _clean(raw.get("document_id"), 120)
        state = _clean(raw.get("state"), 40).upper()
        if not document_id or state not in DOCUMENT_STATES:
            continue
        rows.append({
            "review_id": _clean(raw.get("review_id"), 160),
            "document_id": document_id,
            "state": state,
            "reason": _clean(raw.get("reason"), 500),
            "evidence_refs": _strings(raw.get("evidence_refs"), limit=50, item_limit=180),
            "related_document_ids": _strings(raw.get("related_document_ids"), limit=50, item_limit=180),
            "reviewer_id": _clean(raw.get("reviewer_id"), 120),
            "reviewed_at": _clean(raw.get("reviewed_at"), 100),
            "automatic_decision": False,
            "external_action_executed": False,
        })
    return rows[-MAX_REVIEW_HISTORY:]


def library_checkpoint_digest(records: Any, review_history: Any) -> str:
    payload = {
        "records": normalize_library_records(records),
        "review_history": normalize_review_history(review_history),
        "raw_pdf_persisted": False,
        "passages_persisted": False,
        "memory_auto_promotion": False,
        "automatic_state_transition": False,
    }
    return "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def default_library_checkpoint() -> dict[str, Any]:
    return {
        "records": [],
        "review_history": [],
        "digest": library_checkpoint_digest([], []),
        "raw_pdf_persisted": False,
        "passages_persisted": False,
        "memory_auto_promotion": False,
        "automatic_state_transition": False,
        "external_action_authority": False,
    }


def normalize_library_checkpoint(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    state = dict(raw or {})
    records = normalize_library_records(state.get("records"))
    history = normalize_review_history(state.get("review_history"))
    return {
        "records": records,
        "review_history": history,
        "digest": library_checkpoint_digest(records, history),
        "raw_pdf_persisted": False,
        "passages_persisted": False,
        "memory_auto_promotion": False,
        "automatic_state_transition": False,
        "external_action_authority": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_RECORDS",
    "MAX_REVIEW_HISTORY",
    "DOCUMENT_STATES",
    "normalize_library_record",
    "normalize_library_records",
    "normalize_review_history",
    "library_checkpoint_digest",
    "default_library_checkpoint",
    "normalize_library_checkpoint",
]
