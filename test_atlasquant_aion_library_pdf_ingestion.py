import unittest
from hashlib import sha256

from atlasquant_aion_library_pdf_ingestion import (
    MAX_PDF_BYTES,
    classify_topics,
    chunk_text,
    extract_pdf,
    stage_pdf_document,
    review_and_index_pdf,
)
from atlasquant_aion_library_index import search_library_index


def _pdf_with_text(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(('BT /F1 12 Tf 72 720 Td (' + safe + ') Tj ET').encode('latin-1'))} >>\nstream\nBT /F1 12 Tf 72 720 Td ({safe}) Tj ET\nendstream".encode("latin-1"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def _admin(tenant="tenant:a", workspace="workspace:a", approved=True):
    return {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "role": "ADMIN",
        "review_approved": approved,
    }


class AionLibraryPdfIngestionTests(unittest.TestCase):
    def test_extracts_text_from_real_pdf_bytes(self):
        raw = _pdf_with_text("Payroll NFP employment wages Federal Reserve")
        result = extract_pdf(raw)
        self.assertEqual(result["status"], "EXTRACTED")
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["extracted_pages"], 1)
        self.assertIn("Payroll", result["pages"][0]["text"])
        self.assertEqual(result["checksum"], "sha256:" + sha256(raw).hexdigest())
        self.assertFalse(result["ocr_executed"])

    def test_invalid_signature_fails_closed(self):
        result = extract_pdf(b"not-a-pdf")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_SIGNATURE_INVALID", result["blockers"])

    def test_empty_pdf_fails_closed(self):
        result = extract_pdf(b"")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_EMPTY", result["blockers"])

    def test_size_limit_fails_before_parser(self):
        raw = b"%PDF-" + (b"x" * MAX_PDF_BYTES)
        result = extract_pdf(raw)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_TOO_LARGE", result["blockers"])

    def test_topic_classification_is_deterministic_and_transparent(self):
        text = "CPI PCE inflation FED FOMC USD EUR forex"
        a = classify_topics(text)
        b = classify_topics(text)
        self.assertEqual(a, b)
        self.assertEqual(a["primary_topic"], "MACROECONOMIA")
        self.assertFalse(a["model_called"])
        self.assertFalse(a["provider_called"])

    def test_chunking_is_bounded_and_deterministic(self):
        text = " ".join(["payroll"] * 2000)
        a = chunk_text(text, chunk_chars=500, overlap=50)
        b = chunk_text(text, chunk_chars=500, overlap=50)
        self.assertEqual(a, b)
        self.assertGreater(len(a), 1)
        self.assertTrue(all(len(x) <= 500 for x in a))

    def test_stage_pdf_creates_quarantined_foundation_record(self):
        raw = _pdf_with_text("Payroll NFP jobs wages USD")
        result = stage_pdf_document(
            pdf_bytes=raw,
            filename="macro.pdf",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
            title="Macro Payroll",
            rights_status="OWNED",
        )
        self.assertEqual(result["status"], "STAGED")
        self.assertEqual(result["record"]["state"], "QUARANTINED")
        self.assertTrue(result["passages"])
        self.assertEqual(result["topic_classification"]["primary_topic"], "MACROECONOMIA")
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])

    def test_scope_mismatch_blocks_before_library_admission(self):
        raw = _pdf_with_text("Payroll")
        result = stage_pdf_document(
            pdf_bytes=raw,
            filename="macro.pdf",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin("tenant:b", "workspace:b"),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SCOPE_MISMATCH", result["blockers"])

    def test_non_pdf_extension_is_blocked(self):
        raw = _pdf_with_text("Payroll")
        result = stage_pdf_document(
            pdf_bytes=raw,
            filename="macro.txt",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_EXTENSION_REQUIRED", result["blockers"])

    def test_review_and_index_requires_explicit_admin_approval(self):
        staged = stage_pdf_document(
            pdf_bytes=_pdf_with_text("Payroll NFP jobs wages USD"),
            filename="macro.pdf",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
        )
        result = review_and_index_pdf(
            staged=staged,
            trusted_context=_admin(approved=False),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("ADMIN_REVIEW_REQUIRED", result["blockers"])

    def test_review_and_index_end_to_end_keeps_provenance(self):
        staged = stage_pdf_document(
            pdf_bytes=_pdf_with_text("Payroll NFP jobs wages USD Federal Reserve"),
            filename="macro.pdf",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
            title="Payroll Guide",
            rights_status="OWNED",
        )
        result = review_and_index_pdf(
            staged=staged,
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"], "INDEXED")
        self.assertGreater(result["indexed_passages"], 0)
        hits = search_library_index(
            result["index"],
            "payroll jobs",
            trusted_context=_admin(),
        )
        self.assertEqual(hits["status"], "RESULTS")
        self.assertTrue(hits["hits"][0]["provenance_id"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["execution_authorized"])

if __name__ == "__main__":
    unittest.main()
