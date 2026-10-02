"""Offline admin preview bridge for the AION Library.

This bridge scopes an uploaded PDF to the authenticated AION admin context,
runs deterministic local inspection/staging/intelligence, and optionally performs
explicit human review into an in-memory index. It never persists externally,
runs OCR, promotes memory, calls providers/models, or authorizes execution.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_library_document_intelligence import (
    enrich_staged_pdf,
    inspect_pdf_document,
    prepare_ocr_handoff,
)
from atlasquant_aion_library_pdf_ingestion import (
    review_and_index_pdf,
    stage_pdf_document,
)

SCHEMA = "ATLASQUANT_AION_LIBRARY_PREVIEW_V1"


def _admin_scope(access: Mapping[str, Any] | None) -> dict[str, Any]:
    try:
        context = authenticated_context(access, Domain.ADMIN)
    except Exception as exc:
        return {
            "ready": False,
            "reason": type(exc).__name__,
            "tenant_id": "",
            "workspace_id": "",
            "trusted_context": {},
        }
    if context.role != "ADMIN":
        return {
            "ready": False,
            "reason": "ADMIN_CONTEXT_REQUIRED",
            "tenant_id": "",
            "workspace_id": "",
            "trusted_context": {},
        }
    workspace_id = f"{context.workspace_id}:biblioteca"
    return {
        "ready": True,
        "reason": "OK",
        "tenant_id": context.tenant_id,
        "workspace_id": workspace_id,
        "trusted_context": {
            "tenant_id": context.tenant_id,
            "workspace_id": workspace_id,
            "role": "ADMIN",
            "review_approved": True,
        },
    }


def build_library_pdf_preview(
    access: Mapping[str, Any] | None,
    *,
    pdf_bytes: bytes,
    filename: Any,
    title: Any = "",
    author: Any = "",
    publisher: Any = "",
    published_at: Any = "",
    document_version: Any = "1",
    rights_status: Any = "UNKNOWN",
    approve_review: bool = False,
    index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope = _admin_scope(access)
    if not scope["ready"]:
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "blockers": [scope["reason"]],
            "external_persisted": False,
            "memory_promoted": False,
            "ocr_executed": False,
            "execution_authorized": False,
            "external_action_executed": False,
        }

    intelligence = inspect_pdf_document(pdf_bytes)
    ocr_handoff = prepare_ocr_handoff(
        intelligence,
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
        trusted_context=scope["trusted_context"],
    )

    if intelligence.get("status") != "INSPECTED":
        return {
            "schema": SCHEMA,
            "status": str(intelligence.get("status") or "BLOCKED"),
            "blockers": list(intelligence.get("blockers") or []),
            "scope": {
                "tenant_id": scope["tenant_id"],
                "workspace_id": scope["workspace_id"],
                "role": "ADMIN",
            },
            "intelligence": intelligence,
            "ocr_handoff": ocr_handoff,
            "staged": None,
            "review": None,
            "external_persisted": False,
            "memory_promoted": False,
            "ocr_executed": False,
            "execution_authorized": False,
            "external_action_executed": False,
        }

    staged = stage_pdf_document(
        pdf_bytes=pdf_bytes,
        filename=filename,
        tenant_id=scope["tenant_id"],
        workspace_id=scope["workspace_id"],
        trusted_context=scope["trusted_context"],
        title=title,
        author=author,
        publisher=publisher,
        published_at=published_at,
        document_version=document_version,
        rights_status=rights_status,
    )
    enriched = enrich_staged_pdf(staged, intelligence)
    if enriched.get("status") != "STAGED":
        return {
            "schema": SCHEMA,
            "status": "BLOCKED",
            "blockers": list(enriched.get("blockers") or staged.get("blockers") or []),
            "scope": {
                "tenant_id": scope["tenant_id"],
                "workspace_id": scope["workspace_id"],
                "role": "ADMIN",
            },
            "intelligence": intelligence,
            "ocr_handoff": ocr_handoff,
            "staged": enriched,
            "review": None,
            "external_persisted": False,
            "memory_promoted": False,
            "ocr_executed": False,
            "execution_authorized": False,
            "external_action_executed": False,
        }

    review = None
    status = "PREVIEW_READY"
    if approve_review is True:
        review = review_and_index_pdf(
            staged=enriched,
            trusted_context=scope["trusted_context"],
            evidence_refs=[intelligence.get("checksum")],
            index=index,
        )
        status = (
            "REVIEW_INDEX_READY"
            if review.get("status") == "INDEXED"
            else "BLOCKED"
        )

    return {
        "schema": SCHEMA,
        "status": status,
        "blockers": list((review or {}).get("blockers") or []),
        "scope": {
            "tenant_id": scope["tenant_id"],
            "workspace_id": scope["workspace_id"],
            "role": "ADMIN",
        },
        "intelligence": intelligence,
        "ocr_handoff": ocr_handoff,
        "staged": enriched,
        "review": review,
        "external_persisted": False,
        "memory_promoted": False,
        "ocr_executed": False,
        "provider_called": False,
        "model_called": False,
        "web_research_executed": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


__all__ = ["SCHEMA", "build_library_pdf_preview"]
