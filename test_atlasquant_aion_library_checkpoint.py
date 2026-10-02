import unittest
from copy import deepcopy

from atlasquant_aion_library_checkpoint import (
    default_library_checkpoint,
    library_checkpoint_digest,
    normalize_library_checkpoint,
    normalize_library_record,
)
from atlasquant_aion_memory import (
    checkpoint_integrity_report,
    default_checkpoint,
    ensure_operating_checkpoint,
    stage_library_review_checkpoint,
)


def _record(doc_id="DOC-1", *, state="VALIDATED", checksum="sha256:a"):
    return {
        "document_id": doc_id,
        "tenant_id": "tenant:a",
        "workspace_id": "workspace:a:biblioteca",
        "title": "Macro Guide",
        "author": "Autor",
        "publisher": "Editora",
        "published_at": "2026-09-01T00:00:00Z",
        "retrieved_at": "2026-10-02T12:00:00Z",
        "document_version": "1",
        "rights_status": "OWNED",
        "source_reference": "upload://macro.pdf",
        "checksum": checksum,
        "summary": "Resumo revisado.",
        "state": state,
        "reason_codes": ["REVIEW_" + state],
        "evidence_refs": [checksum],
        "truth_state": "SUPPORTED" if state == "VALIDATED" else "UNKNOWN",
        "authority": "NONE",
        "provenance": {
            "provenance_id": "PROV-" + doc_id,
            "tenant_id": "tenant:a",
            "domain_id": "BIBLIOTECA",
            "source_type": "INTERNAL_DOCUMENT",
            "source_reference": "upload://macro.pdf",
            "checksum": checksum,
            "review_status": state,
        },
        "document_intelligence": {
            "checksum": checksum,
            "content_fingerprint": "sha256:f-" + doc_id,
            "page_count": 2,
            "extracted_pages": 2,
            "extracted_chars": 500,
            "quality": {"score": 90, "band": "HIGH"},
            "scanned_likelihood": "LOW",
            "ocr_recommended": False,
            "metadata": {"title": "Macro Guide"},
        },
        "topic_classification": {"macro": True, "topics": ["cpi", "payroll"]},
        "raw_pdf_bytes": b"forbidden",
        "passages": ["raw passage should not persist"],
    }


class AionLibraryCheckpointTests(unittest.TestCase):
    def test_default_section_is_empty_bounded_and_non_authoritative(self):
        state = default_library_checkpoint()
        self.assertEqual(state["records"], [])
        self.assertEqual(state["review_history"], [])
        self.assertTrue(state["digest"].startswith("sha256:"))
        self.assertFalse(state["raw_pdf_persisted"])
        self.assertFalse(state["passages_persisted"])
        self.assertFalse(state["memory_auto_promotion"])
        self.assertFalse(state["automatic_state_transition"])
        self.assertFalse(state["external_action_authority"])

    def test_record_normalizer_excludes_raw_pdf_and_passages(self):
        row = normalize_library_record(_record())
        self.assertEqual(row["document_id"], "DOC-1")
        self.assertNotIn("raw_pdf_bytes", row)
        self.assertNotIn("passages", row)
        self.assertFalse(row["raw_pdf_persisted"])
        self.assertFalse(row["passages_persisted"])
        self.assertFalse(row["memory_promoted"])
        self.assertEqual(row["authority"], "NONE")

    def test_digest_is_deterministic(self):
        rows = [_record()]
        first = library_checkpoint_digest(rows, [])
        second = library_checkpoint_digest(rows, [])
        self.assertEqual(first, second)

    def test_legacy_checkpoint_without_library_remains_compatible(self):
        cp = default_checkpoint()
        cp.pop("library", None)
        report = checkpoint_integrity_report(cp)
        self.assertEqual(report["state"], "CONFIRMED", report)
        upgraded = ensure_operating_checkpoint(cp)
        self.assertIn("library", upgraded)
        self.assertEqual(upgraded["library"]["records"], [])
        self.assertTrue(upgraded["library"]["digest"])

    def test_stage_review_marks_working_checkpoint_dirty_without_persisting(self):
        result = stage_library_review_checkpoint(
            default_checkpoint(),
            _record(),
            reviewer_id="mikael",
            related_document_ids=[],
            reason="Revisão humana concluída.",
        )
        self.assertEqual(result["status"], "STAGED")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        self.assertFalse(result["memory_promoted"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["external_action_executed"])
        cp = result["checkpoint"]
        self.assertTrue(cp["operating"]["dirty"])
        self.assertEqual(len(cp["library"]["records"]), 1)
        self.assertEqual(len(cp["library"]["review_history"]), 1)
        self.assertEqual(cp["library"]["review_history"][0]["reviewer_id"], "mikael")
        self.assertEqual(checkpoint_integrity_report(cp)["state"], "CONFIRMED")

    def test_same_document_replaces_record_but_preserves_review_history(self):
        first = stage_library_review_checkpoint(
            default_checkpoint(),
            _record(state="VALIDATED", checksum="sha256:a"),
            reviewer_id="mikael",
            reason="Primeira revisão.",
        )
        second = stage_library_review_checkpoint(
            first["checkpoint"],
            _record(state="STALE", checksum="sha256:a"),
            reviewer_id="mikael",
            reason="Nova versão disponível.",
        )
        self.assertEqual(second["status"], "STAGED")
        self.assertEqual(len(second["library"]["records"]), 1)
        self.assertEqual(second["library"]["records"][0]["state"], "STALE")
        self.assertEqual(len(second["library"]["review_history"]), 2)

    def test_tampered_library_digest_is_detected_when_section_exists(self):
        cp = stage_library_review_checkpoint(
            default_checkpoint(),
            _record(),
            reviewer_id="mikael",
            reason="Revisão.",
        )["checkpoint"]
        broken = deepcopy(cp)
        broken["library"]["digest"] = "sha256:" + ("0" * 64)
        report = checkpoint_integrity_report(broken)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("library", report["mismatches"])


if __name__ == "__main__":
    unittest.main()
