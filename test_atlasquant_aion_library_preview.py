import unittest
from io import BytesIO

from pypdf import PdfWriter

from atlasquant_aion_library_preview import build_library_pdf_preview


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


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata({"/Title": "Scanned Notes"})
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _admin():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a" * 32,
            "permissions": ["app:read", "admin:read", "aion:admin"],
            "authenticated_at": 10,
            "last_seen": 10,
        },
    }


class AionLibraryPreviewTests(unittest.TestCase):
    def test_text_pdf_builds_offline_preview_without_persistence(self):
        raw = _pdf_with_text(" ".join(["CPI payroll Federal Reserve USD macro"] * 80))
        result = build_library_pdf_preview(
            _admin(),
            pdf_bytes=raw,
            filename="macro.pdf",
            title="Macro Guide",
            rights_status="OWNED",
        )
        self.assertEqual(result["status"], "PREVIEW_READY")
        self.assertEqual(result["intelligence"]["status"], "INSPECTED")
        self.assertEqual(result["staged"]["status"], "STAGED")
        self.assertIn("document_intelligence", result["staged"]["record"])
        self.assertIn("biblioteca", result["scope"]["workspace_id"])
        self.assertEqual(result["scope"]["role"], "ADMIN")
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["ocr_executed"])
        self.assertFalse(result["provider_called"])
        self.assertFalse(result["model_called"])
        self.assertFalse(result["execution_authorized"])

    def test_explicit_review_builds_temporary_index_only(self):
        raw = _pdf_with_text(" ".join(["NFP PCE forex USD macroeconomics"] * 80))
        result = build_library_pdf_preview(
            _admin(),
            pdf_bytes=raw,
            filename="research.pdf",
            title="Research",
            rights_status="OWNED",
            approve_review=True,
        )
        self.assertEqual(result["status"], "REVIEW_INDEX_READY")
        self.assertEqual(result["review"]["status"], "INDEXED")
        self.assertGreater(result["review"]["indexed_passages"], 0)
        self.assertFalse(result["review"]["external_persisted"])
        self.assertFalse(result["review"]["memory_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_probable_scan_prepares_ocr_handoff_without_executing_ocr(self):
        result = build_library_pdf_preview(
            _admin(),
            pdf_bytes=_blank_pdf(),
            filename="scan.pdf",
        )
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(result["intelligence"]["ocr_recommended"])
        self.assertEqual(result["ocr_handoff"]["status"], "PLAN_READY")
        self.assertTrue(
            result["ocr_handoff"]["plan"]["requires_explicit_admin_approval"]
        )
        self.assertFalse(result["ocr_handoff"]["ocr_executed"])
        self.assertFalse(result["execution_authorized"])

    def test_untrusted_or_incomplete_admin_context_is_blocked(self):
        result = build_library_pdf_preview(
            {"role": "ADMIN", "session": {"username": "mikael", "role": "ADMIN"}},
            pdf_bytes=_pdf_with_text("macro " * 200),
            filename="macro.pdf",
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
