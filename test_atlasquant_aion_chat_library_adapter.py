from hashlib import sha256
import pytest

from aion_chat.models import Attachment, Scope
from atlasquant_aion_chat_library_adapter import AionChatLibraryAdapter


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def attachment(data: bytes, *, name="notes.txt", mime="text/plain", conversation_id="conv-1"):
    digest = sha256(data).hexdigest()
    return Attachment(
        conversation_id=conversation_id,
        name=name,
        mime_type=mime,
        size=len(data),
        digest=digest,
        storage_reference=digest + ".blob",
    )


def test_attachment_stays_quarantined_without_explicit_analysis():
    raw = b"conteudo seguro"
    out = AionChatLibraryAdapter().stage_attachment(scope(), attachment(raw), raw)
    assert out["status"] == "QUARANTINED"
    assert out["requires_explicit_analysis"] is True
    assert out["memory_promoted"] is False
    assert out["external_persisted"] is False


def test_text_analysis_only_stages_library_review():
    raw = "Inflação e política monetária.".encode()
    out = AionChatLibraryAdapter().stage_attachment(
        scope(), attachment(raw), raw, explicit_analysis=True
    )
    assert out["status"] == "ANALYSIS_STAGED"
    assert out["library"]["status"] == "STAGED"
    assert out["library"]["record"]["state"] == "QUARANTINED"
    assert out["library"]["memory_promoted"] is False
    assert out["external_action_executed"] is False


def test_digest_mismatch_is_rejected():
    raw = b"abc"
    a = attachment(raw)
    with pytest.raises(ValueError, match="digest mismatch"):
        AionChatLibraryAdapter().stage_attachment(scope(), a, b"abcd")


def test_declared_metadata_cannot_hide_real_mime():
    raw = b"%PDF-not-a-real-pdf"
    a = attachment(raw, name="fake.pdf", mime="text/plain")
    with pytest.raises(ValueError, match="MIME mismatch"):
        AionChatLibraryAdapter().stage_attachment(scope(), a, raw)


def test_invalid_pdf_signature_does_not_enter_pdf_pipeline():
    raw = b"plain text pretending to be pdf"
    digest = sha256(raw).hexdigest()
    a = Attachment(
        conversation_id="conv-1",
        name="fake.pdf",
        mime_type="application/pdf",
        size=len(raw),
        digest=digest,
        storage_reference=digest + ".blob",
    )
    with pytest.raises(ValueError):
        AionChatLibraryAdapter().stage_attachment(scope(), a, raw, explicit_analysis=True)


def test_path_traversal_name_is_rejected_by_chat_metadata_contract():
    raw = b"abc"
    digest = sha256(raw).hexdigest()
    a = Attachment(
        conversation_id="conv-1",
        name="../../secret.txt",
        mime_type="text/plain",
        size=len(raw),
        digest=digest,
        storage_reference=digest + ".blob",
    )
    with pytest.raises(ValueError):
        AionChatLibraryAdapter().stage_attachment(scope(), a, raw)


def reviewed_index(s: Scope):
    return {
        "schema": "ATLASQUANT_AION_LIBRARY_INDEX_V1",
        "documents": [{
            "document_id": "LIB-1",
            "tenant_id": s.tenant_id,
            "workspace_id": s.workspace_id,
            "title": "Guia Macro",
            "state": "VALIDATED",
            "truth_state": "CONFIRMED",
            "source_reference": "internal://macro",
            "checksum": "sha256:x",
            "provenance_id": "PROV-1",
            "evidence_refs": ["E-1"],
            "terms": ["inflacao", "juros"],
        }],
        "passages": [{
            "passage_id": "PASS-1",
            "document_id": "LIB-1",
            "tenant_id": s.tenant_id,
            "workspace_id": s.workspace_id,
            "ordinal": 1,
            "text": "Inflação e juros exigem análise conjunta.",
            "terms": ["inflacao", "juros", "analise"],
            "state": "INDEXED",
            "provenance_id": "PROV-1",
            "evidence_refs": ["E-1"],
            "truth_state": "CONFIRMED",
        }],
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


def test_retrieval_reads_only_installed_reviewed_scope():
    s = scope("a")
    adapter = AionChatLibraryAdapter()
    adapter.install_reviewed_index(s, reviewed_index(s))
    hits = adapter.retrieve(s, "inflação")
    assert len(hits) == 1
    assert hits[0]["document_id"] == "LIB-1"
    assert hits[0]["truth_state"] == "CONFIRMED"


def test_cross_tenant_index_install_is_rejected():
    adapter = AionChatLibraryAdapter()
    with pytest.raises(ValueError, match="crosses scope"):
        adapter.install_reviewed_index(scope("b"), reviewed_index(scope("a")))


def test_same_query_in_other_tenant_returns_no_hits():
    a = scope("a")
    b = scope("b")
    adapter = AionChatLibraryAdapter()
    adapter.install_reviewed_index(a, reviewed_index(a))
    assert adapter.retrieve(b, "inflação") == []
