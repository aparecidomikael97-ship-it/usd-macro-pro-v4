"""AION Library Document Intelligence V1.

Deterministic, offline PDF inspection for metadata, extraction quality and
scanned-document likelihood. This module never runs OCR, network calls,
providers, models, persistence, memory promotion, or external actions.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from typing import Any, Mapping
import json

from pypdf import PdfReader

from atlasquant_aion_library_pdf_ingestion import (
    MAX_EXTRACTED_CHARS,
    MAX_PAGES,
    MAX_PDF_BYTES,
    stage_pdf_document,
)

SCHEMA = "ATLASQUANT_AION_LIBRARY_DOCUMENT_INTELLIGENCE_V1"
MAX_METADATA_VALUE = 1000
LOW_TEXT_CHARS_PER_PAGE = 40
HEALTHY_TEXT_CHARS_PER_PAGE = 150

def _clean(value: Any, limit: int = MAX_METADATA_VALUE) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]

def _sha256(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()

def _metadata_dict(reader: PdfReader) -> dict[str, str]:
    try:
        raw = dict(reader.metadata or {})
    except Exception:
        raw = {}
    aliases = {
        "/Title": "title", "/Author": "author", "/Subject": "subject",
        "/Creator": "creator", "/Producer": "producer", "/Keywords": "keywords",
        "/CreationDate": "created_at_raw", "/ModDate": "modified_at_raw",
    }
    return {aliases[k]: _clean(v) for k, v in raw.items() if k in aliases and _clean(v)}
def _quality_metrics(
    *, page_count: int, extracted_pages: int, total_chars: int,
    failures: int, metadata_fields: int,
) -> dict[str, Any]:
    if page_count <= 0:
        return {
            "score": 0, "band": "NO_PAGES", "coverage": 0.0,
            "chars_per_page": 0.0, "failure_ratio": 0.0,
        }
    coverage = extracted_pages / page_count
    chars_per_page = total_chars / page_count
    failure_ratio = failures / page_count
    if total_chars <= 0:
        score = 0
        band = "NO_TEXT"
    else:
        score = round(
            min(1.0, coverage) * 55
            + min(1.0, chars_per_page / 800.0) * 35
            + (10 if metadata_fields else 0)
            - min(1.0, failure_ratio) * 20
        )
        score = max(0, min(100, int(score)))
        band = "HIGH" if score >= 80 else "MEDIUM" if score >= 55 else "LOW"
    return {
        "score": score,
        "band": band,
        "coverage": round(coverage, 4),
        "chars_per_page": round(chars_per_page, 2),
        "failure_ratio": round(failure_ratio, 4),
    }

def _scanned_likelihood(*, page_count: int, extracted_pages: int, total_chars: int) -> str:
    if page_count <= 0:
        return "UNKNOWN"
    coverage = extracted_pages / page_count
    chars_per_page = total_chars / page_count
    if total_chars <= 0:
        return "HIGH"
    if coverage < 0.25 or chars_per_page < LOW_TEXT_CHARS_PER_PAGE:
        return "HIGH"
    if coverage < 0.70 or chars_per_page < HEALTHY_TEXT_CHARS_PER_PAGE:
        return "MEDIUM"
    return "LOW"
def inspect_pdf_document(pdf_bytes: bytes) -> dict[str, Any]:
    if not isinstance(pdf_bytes, (bytes, bytearray)):
        return {"schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_BYTES_REQUIRED"]}
    raw = bytes(pdf_bytes)
    if not raw:
        return {"schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_EMPTY"]}
    if len(raw) > MAX_PDF_BYTES:
        return {"schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_TOO_LARGE"]}
    if not raw.startswith(b"%PDF-"):
        return {"schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_SIGNATURE_INVALID"]}
    checksum = _sha256(raw)
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
    except Exception as exc:
        return {
            "schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_PARSE_ERROR"],
            "error_type": type(exc).__name__, "checksum": checksum,
        }

    metadata = _metadata_dict(reader)
    encrypted = bool(getattr(reader, "is_encrypted", False))
    if encrypted:
        return {
            "schema": SCHEMA, "status": "REVIEW_REQUIRED", "blockers": ["PDF_ENCRYPTED"],
            "checksum": checksum, "bytes": len(raw), "metadata": metadata,
            "encrypted": True, "ocr_recommended": False, "ocr_executed": False,
            "provider_called": False, "model_called": False,
            "web_research_executed": False, "external_persisted": False,
            "memory_promoted": False, "execution_authorized": False,
        }
    try:
        page_count = len(reader.pages)
    except Exception as exc:
        return {
            "schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_PAGE_READ_ERROR"],
            "error_type": type(exc).__name__, "checksum": checksum, "metadata": metadata,
        }
    if page_count > MAX_PAGES:
        return {
            "schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_PAGE_LIMIT"],
            "checksum": checksum, "page_count": page_count, "metadata": metadata,
        }
    page_stats: list[dict[str, Any]] = []
    text_parts: list[str] = []
    total_chars = 0
    extracted_pages = 0
    failures = 0
    truncated = False
    for idx, page in enumerate(reader.pages, start=1):
        if total_chars >= MAX_EXTRACTED_CHARS:
            truncated = True
            break
        try:
            text = _clean(page.extract_text() or "", MAX_EXTRACTED_CHARS - total_chars)
        except Exception:
            text = ""
            failures += 1
        if text:
            extracted_pages += 1
            total_chars += len(text)
            text_parts.append(text)
        try:
            width = round(float(page.mediabox.width), 2)
            height = round(float(page.mediabox.height), 2)
        except Exception:
            width = height = None
        page_stats.append({
            "page": idx, "text_chars": len(text), "text_present": bool(text),
            "width_pt": width, "height_pt": height,
        })

    quality = _quality_metrics(
        page_count=page_count, extracted_pages=extracted_pages,
        total_chars=total_chars, failures=failures, metadata_fields=len(metadata),
    )
    scanned = _scanned_likelihood(
        page_count=page_count, extracted_pages=extracted_pages, total_chars=total_chars,
    )
    normalized_text = "\n".join(text_parts)
    content_fingerprint = (
        "sha256:" + sha256(normalized_text.encode("utf-8")).hexdigest()
        if normalized_text else ""
    )
    blockers = [] if total_chars else ["NO_EXTRACTABLE_TEXT"]
    status = "INSPECTED" if total_chars else "REVIEW_REQUIRED"
    return {
        "schema": SCHEMA,
        "status": status,
        "blockers": blockers,
        "checksum": checksum,
        "content_fingerprint": content_fingerprint,
        "bytes": len(raw),
        "pdf_version": _clean(getattr(reader, "pdf_header", ""), 80),
        "page_count": page_count,
        "extracted_pages": extracted_pages,
        "blank_or_unreadable_pages": max(0, page_count - extracted_pages),
        "extraction_failures": failures,
        "extracted_chars": total_chars,
        "text_truncated": truncated,
        "metadata": metadata,
        "page_stats": page_stats,
        "quality": quality,
        "scanned_likelihood": scanned,
        "ocr_recommended": scanned in {"HIGH", "MEDIUM"},
        "encrypted": False,
        "ocr_executed": False,
        "provider_called": False,
        "model_called": False,
        "web_research_executed": False,
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }
def enrich_staged_pdf(
    staged: Mapping[str, Any], intelligence: Mapping[str, Any]
) -> dict[str, Any]:
    item = dict(staged or {})
    intel = dict(intelligence or {})
    record = dict(item.get("record") or {})
    if item.get("status") != "STAGED" or not record:
        return {
            "schema": SCHEMA, "status": "BLOCKED", "blockers": ["PDF_NOT_STAGED"],
            "external_persisted": False, "memory_promoted": False,
            "execution_authorized": False,
        }
    if intel.get("status") != "INSPECTED":
        return {
            "schema": SCHEMA, "status": "BLOCKED",
            "blockers": ["DOCUMENT_INTELLIGENCE_NOT_READY"],
            "external_persisted": False, "memory_promoted": False,
            "execution_authorized": False,
        }
    record["document_intelligence"] = {
        "checksum": intel.get("checksum"),
        "content_fingerprint": intel.get("content_fingerprint"),
        "pdf_version": intel.get("pdf_version"),
        "page_count": intel.get("page_count"),
        "extracted_pages": intel.get("extracted_pages"),
        "extracted_chars": intel.get("extracted_chars"),
        "quality": dict(intel.get("quality") or {}),
        "scanned_likelihood": intel.get("scanned_likelihood"),
        "ocr_recommended": bool(intel.get("ocr_recommended")),
        "metadata": dict(intel.get("metadata") or {}),
    }
    out = dict(item)
    out["record"] = record
    out["document_intelligence"] = record["document_intelligence"]
    return out
def prepare_ocr_handoff(
    intelligence: Mapping[str, Any], *, tenant_id: Any, workspace_id: Any,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    intel = dict(intelligence or {})
    ctx = dict(trusted_context or {})
    tenant = _clean(tenant_id, 120)
    workspace = _clean(workspace_id, 120)
    blockers: list[str] = []
    if tenant != _clean(ctx.get("tenant_id"), 120):
        blockers.append("SCOPE_MISMATCH")
    if workspace != _clean(ctx.get("workspace_id"), 120):
        blockers.append("SCOPE_MISMATCH")
    if _clean(ctx.get("role"), 40).upper() != "ADMIN":
        blockers.append("ADMIN_CONTEXT_REQUIRED")
    if intel.get("encrypted") is True:
        blockers.append("PDF_ENCRYPTED_REQUIRES_UNLOCK")
    if blockers:
        return {
            "schema": SCHEMA, "status": "BLOCKED",
            "blockers": list(dict.fromkeys(blockers)),
            "ocr_executed": False,
            "execution_authorized": False,
        }
    if intel.get("ocr_recommended") is not True:
        return {
            "schema": SCHEMA,
            "status": "NOT_REQUIRED",
            "reason": "TEXT_EXTRACTION_SUFFICIENT",
            "ocr_executed": False,
            "execution_authorized": False,
        }
    plan = {
        "input_checksum": intel.get("checksum"),
        "page_count": intel.get("page_count"),
        "scanned_likelihood": intel.get("scanned_likelihood"),
        "quality_band": (intel.get("quality") or {}).get("band"),
        "tenant_id": tenant,
        "workspace_id": workspace,
        "requires_explicit_admin_approval": True,
        "requires_isolated_ocr_adapter": True,
        "preserve_original_checksum": True,
        "reingest_after_ocr": True,
    }
    digest = sha256(
        json.dumps(plan, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema": SCHEMA,
        "status": "PLAN_READY",
        "plan": plan,
        "plan_digest": "sha256:" + digest,
        "ocr_executed": False,
        "provider_called": False,
        "model_called": False,
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
    }

__all__ = [
    "SCHEMA",
    "inspect_pdf_document",
    "enrich_staged_pdf",
    "prepare_ocr_handoff",
]
