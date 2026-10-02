import unittest
from io import BytesIO

from pypdf import PdfWriter

from atlasquant_aion_library_document_intelligence import (
    enrich_staged_pdf,
    inspect_pdf_document,
    prepare_ocr_handoff,
)
from atlasquant_aion_library_pdf_ingestion import stage_pdf_document


def _pdf_with_text(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT /F1 12 Tf 72 720 Td (" + safe + ") Tj ET").encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
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
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def _blank_pdf(*, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({
        "/Title": "Scanned Macro Notes",
        "/Author": "AION Test",
        "/Subject": "OCR candidate",
    })
    if encrypted:
        writer.encrypt("secret")
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _admin(tenant: str = "tenant:a", workspace: str = "workspace:a") -> dict:
    return {
        "tenant_id": tenant,
        "workspace_id": workspace,
        "role": "ADMIN",
        "review_approved": True,
    }


class AionLibraryDocumentIntelligenceTests(unittest.TestCase):
    def test_text_pdf_is_inspected_with_quality_and_fingerprint(self):
        text = " ".join(
            ["Payroll NFP inflation Federal Reserve USD macroeconomics analysis"] * 20
        )
        result = inspect_pdf_document(_pdf_with_text(text))
        self.assertEqual(result["status"], "INSPECTED")
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["extracted_pages"], 1)
        self.assertGreater(result["extracted_chars"], 150)
        self.assertTrue(result["content_fingerprint"].startswith("sha256:"))
        self.assertEqual(result["scanned_likelihood"], "LOW")
        self.assertFalse(result["ocr_recommended"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["model_called"])

    def test_blank_pdf_is_flagged_as_probable_scan_without_running_ocr(self):
        result = inspect_pdf_document(_blank_pdf())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertIn("NO_EXTRACTABLE_TEXT", result["blockers"])
        self.assertEqual(result["scanned_likelihood"], "HIGH")
        self.assertTrue(result["ocr_recommended"])
        self.assertFalse(result["ocr_executed"])
        self.assertEqual(result["metadata"]["title"], "Scanned Macro Notes")
        self.assertEqual(result["quality"]["band"], "NO_TEXT")

    def test_encrypted_pdf_fails_closed_for_ocr_planning(self):
        intelligence = inspect_pdf_document(_blank_pdf(encrypted=True))
        self.assertEqual(intelligence["status"], "REVIEW_REQUIRED")
        self.assertIn("PDF_ENCRYPTED", intelligence["blockers"])
        result = prepare_ocr_handoff(
            intelligence,
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_ENCRYPTED_REQUIRES_UNLOCK", result["blockers"])

    def test_invalid_signature_is_blocked(self):
        result = inspect_pdf_document(b"not-pdf")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PDF_SIGNATURE_INVALID", result["blockers"])

    def test_inspection_is_deterministic_for_same_document(self):
        raw = _pdf_with_text(" ".join(["macro forex payroll"] * 80))
        first = inspect_pdf_document(raw)
        second = inspect_pdf_document(raw)
        self.assertEqual(first["checksum"], second["checksum"])
        self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
        self.assertEqual(first["quality"], second["quality"])
        self.assertEqual(first["scanned_likelihood"], second["scanned_likelihood"])

    def test_intelligence_enriches_quarantined_record_without_promoting_it(self):
        raw = _pdf_with_text(" ".join(["Payroll NFP USD Federal Reserve"] * 60))
        staged = stage_pdf_document(
            pdf_bytes=raw,
            filename="macro.pdf",
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
            title="Macro Guide",
            rights_status="OWNED",
        )
        intelligence = inspect_pdf_document(raw)
        result = enrich_staged_pdf(staged, intelligence)
        self.assertEqual(result["status"], "STAGED")
        self.assertEqual(result["record"]["state"], "QUARANTINED")
        self.assertIn("document_intelligence", result["record"])
        self.assertEqual(
            result["record"]["document_intelligence"]["checksum"],
            intelligence["checksum"],
        )
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_ocr_plan_requires_matching_scope_and_admin(self):
        intelligence = inspect_pdf_document(_blank_pdf())
        bad_scope = prepare_ocr_handoff(
            intelligence,
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin("tenant:b", "workspace:b"),
        )
        self.assertEqual(bad_scope["status"], "BLOCKED")
        self.assertIn("SCOPE_MISMATCH", bad_scope["blockers"])

        non_admin = prepare_ocr_handoff(
            intelligence,
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context={
                "tenant_id": "tenant:a",
                "workspace_id": "workspace:a",
                "role": "USER",
            },
        )
        self.assertEqual(non_admin["status"], "BLOCKED")
        self.assertIn("ADMIN_CONTEXT_REQUIRED", non_admin["blockers"])

    def test_ocr_plan_is_prepare_only_and_digest_bound(self):
        intelligence = inspect_pdf_document(_blank_pdf())
        result = prepare_ocr_handoff(
            intelligence,
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"], "PLAN_READY")
        self.assertTrue(result["plan"]["requires_explicit_admin_approval"])
        self.assertTrue(result["plan"]["preserve_original_checksum"])
        self.assertTrue(result["plan_digest"].startswith("sha256:"))
        self.assertFalse(result["ocr_executed"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["provider_called"])

    def test_ocr_plan_not_required_when_text_is_sufficient(self):
        raw = _pdf_with_text(" ".join(["CPI PCE payroll forex USD"] * 80))
        intelligence = inspect_pdf_document(raw)
        result = prepare_ocr_handoff(
            intelligence,
            tenant_id="tenant:a",
            workspace_id="workspace:a",
            trusted_context=_admin(),
        )
        self.assertEqual(result["status"], "NOT_REQUIRED")
        self.assertEqual(result["reason"], "TEXT_EXTRACTION_SUFFICIENT")
        self.assertFalse(result["ocr_executed"])


if __name__ == "__main__":
    unittest.main()
