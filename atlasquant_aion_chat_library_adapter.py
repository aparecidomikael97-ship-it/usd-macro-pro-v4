"""Scoped Chat -> AION Library bridge.

Attachments remain untrusted data. The adapter validates content against chat
metadata and may stage supported documents for the existing Library pipeline,
but it never performs admin review, automatic indexing, memory promotion,
provider calls or external persistence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from aion_chat.attachments import detect_mime, sanitize_name, validate_metadata
from aion_chat.models import Attachment, Scope
from atlasquant_aion_library_foundation import ingest_document
from atlasquant_aion_library_index import (
    INDEXABLE_STATES,
    SCHEMA as LIBRARY_INDEX_SCHEMA,
    empty_library_index,
    search_library_index,
)
from atlasquant_aion_truth_mapping import map_truth_knowledge_state
from atlasquant_aion_library_pdf_ingestion import stage_pdf_document

SCHEMA = "ATLASQUANT_AION_CHAT_LIBRARY_ADAPTER_V1"
MAX_TEXT_BYTES = 2_000_000


def _scope_key(scope: Scope) -> str:
    if not isinstance(scope, Scope):
        raise TypeError("Scope required")
    raw = f"{scope.owner_id}\0{scope.tenant_id}\0{scope.workspace_id}".encode("utf-8")
    return sha256(raw).hexdigest()


def _trusted_scope(scope: Scope) -> dict[str, str]:
    return {
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
        "role": "USER",
    }


class AionChatLibraryAdapter:
    """RetrievalAdapter-compatible scoped bridge over reviewed Library indexes."""

    def __init__(self):
        self._indexes: dict[str, dict[str, Any]] = {}

    def stage_attachment(
        self,
        scope: Scope,
        attachment: Attachment,
        data: bytes,
        *,
        explicit_analysis: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        if not isinstance(attachment, Attachment):
            raise TypeError("Attachment required")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("attachment bytes required")
        raw = bytes(data)
        validate_metadata(attachment)
        name = sanitize_name(attachment.name)
        actual_digest = sha256(raw).hexdigest()
        if actual_digest != attachment.digest:
            raise ValueError("attachment digest mismatch")
        if len(raw) != attachment.size:
            raise ValueError("attachment size mismatch")
        extension = Path(name).suffix.lower()
        actual_mime = detect_mime(raw, extension)
        if actual_mime != attachment.mime_type:
            raise ValueError("attachment MIME mismatch")

        base = {
            "schema": SCHEMA,
            "conversation_id": attachment.conversation_id,
            "attachment_id": attachment.id,
            "name": name,
            "mime_type": actual_mime,
            "checksum": "sha256:" + actual_digest,
            "status": "QUARANTINED",
            "requires_explicit_analysis": True,
            "requires_human_review": True,
            "external_persisted": False,
            "memory_promoted": False,
            "execution_authorized": False,
            "external_action_executed": False,
        }
        if not explicit_analysis:
            return base

        if actual_mime == "application/pdf":
            staged = stage_pdf_document(
                pdf_bytes=raw,
                filename=name,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                trusted_context=_trusted_scope(scope),
                title=name,
            )
            return {
                **base,
                "status": "ANALYSIS_STAGED" if staged.get("status") == "STAGED" else "REVIEW_REQUIRED",
                "library": staged,
                "requires_explicit_analysis": False,
            }

        if actual_mime == "text/plain":
            if len(raw) > MAX_TEXT_BYTES:
                raise ValueError("text attachment exceeds analysis byte budget")
            text = raw.decode("utf-8-sig")
            staged = ingest_document(
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                title=name,
                source_reference="chat-upload://" + attachment.id,
                checksum="sha256:" + actual_digest,
                source_type="INTERNAL_DOCUMENT",
                summary=text[:4000],
                evidence_refs=["sha256:" + actual_digest],
            )
            return {
                **base,
                "status": "ANALYSIS_STAGED" if staged.get("status") == "STAGED" else "REVIEW_REQUIRED",
                "library": staged,
                "requires_explicit_analysis": False,
            }

        return {
            **base,
            "status": "REVIEW_REQUIRED",
            "blockers": ["ANALYSIS_PIPELINE_NOT_IMPLEMENTED_FOR_MIME"],
            "requires_explicit_analysis": False,
        }

    def install_reviewed_index(self, scope: Scope, index: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        state = deepcopy(dict(index or empty_library_index()))
        if state.get("schema") != LIBRARY_INDEX_SCHEMA:
            raise ValueError("invalid library index schema")
        docs = [x for x in list(state.get("documents") or []) if isinstance(x, Mapping)]
        passages = [x for x in list(state.get("passages") or []) if isinstance(x, Mapping)]

        doc_ids: set[str] = set()
        for row in docs:
            if row.get("tenant_id") != scope.tenant_id or row.get("workspace_id") != scope.workspace_id:
                raise ValueError("library index crosses scope")
            if row.get("state") not in INDEXABLE_STATES:
                raise ValueError("library index contains unreviewed document")
            document_id = str(row.get("document_id") or "").strip()
            if not document_id or document_id in doc_ids:
                raise ValueError("library index document identity invalid")
            doc_ids.add(document_id)

        for row in passages:
            if row.get("tenant_id") != scope.tenant_id or row.get("workspace_id") != scope.workspace_id:
                raise ValueError("library index crosses scope")
            if row.get("state") != "INDEXED":
                raise ValueError("library index contains unreviewed passage")
            if str(row.get("document_id") or "").strip() not in doc_ids:
                raise ValueError("library index passage references unknown document")

        self._indexes[_scope_key(scope)] = state
        return {
            "schema": SCHEMA,
            "status": "REVIEWED_INDEX_INSTALLED",
            "documents": len(docs),
            "passages": len(passages),
            "truth_mapping_enforced": True,
            "memory_promoted": False,
            "external_persisted": False,
        }

    def retrieve(self, scope: Scope, query: str) -> list[dict]:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        state = self._indexes.get(_scope_key(scope), empty_library_index())
        result = search_library_index(
            state,
            query,
            trusted_context=_trusted_scope(scope),
            limit=20,
        )
        hits = []
        for item in list(result.get("hits") or []):
            row = dict(item)
            mapping = map_truth_knowledge_state(
                evidence_truth_state=row.get("truth_state"),
                library_state=row.get("document_state"),
                library_truth_state=row.get("truth_state"),
            )
            row["runtime_truth_state"] = mapping["operational_truth_state"]
            row["usable_as_confirmed_fact"] = mapping["usable_as_confirmed_fact"]
            row["truth_mapping"] = mapping
            hits.append(row)
        return hits


__all__ = ["SCHEMA", "AionChatLibraryAdapter"]
