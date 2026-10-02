import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class AionCoreWiringTests(unittest.TestCase):
    def _text(self, name):
        return (ROOT / name).read_text(encoding="utf-8")

    def test_recovery_traceability_gate_has_real_admin_consumer(self):
        review = self._text("atlasquant_aion_recovery_review.py")
        admin = self._text("atlasquant_aion_admin.py")
        self.assertIn(
            "from atlasquant_aion_recovery_traceability_gate import",
            review,
        )
        self.assertIn("execute_local_tool(", review)
        self.assertIn("build_local_traceability(", review)
        self.assertIn("recovery_traceability_readiness(", review)
        self.assertIn(
            "from atlasquant_aion_recovery_review import build_recovery_review",
            admin,
        )
        self.assertIn("build_recovery_review(", admin)
        self.assertIn(
            'preview_review.get("state") != "READY_FOR_ADMIN_REVIEW"',
            admin,
        )

    def test_library_document_intelligence_has_real_admin_consumer(self):
        preview = self._text("atlasquant_aion_library_preview.py")
        admin = self._text("atlasquant_aion_admin.py")
        self.assertIn(
            "from atlasquant_aion_library_document_intelligence import",
            preview,
        )
        self.assertIn("inspect_pdf_document(", preview)
        self.assertIn("enrich_staged_pdf(", preview)
        self.assertIn("prepare_ocr_handoff(", preview)
        self.assertIn("review_and_index_pdf(", preview)
        self.assertIn(
            "from atlasquant_aion_library_preview import build_library_pdf_preview",
            admin,
        )
        self.assertIn('"📚 Biblioteca"', admin)
        self.assertIn("_render_library(access_map)", admin)
        self.assertIn("build_library_pdf_preview(", admin)

    def test_tenant_evidence_bundle_remains_review_artifact_not_runtime_loader(self):
        runtime = self._text("atlasquant_aion_core_runtime_bridge.py")
        admin = self._text("atlasquant_aion_admin.py")
        self.assertNotIn("atlasquant_aion_tenant_evidence_bundle", runtime)
        self.assertNotIn(
            "docs/aion/evidence/tenant_persistence_local_evidence.json",
            runtime,
        )
        self.assertNotIn("atlasquant_aion_tenant_evidence_bundle", admin)
        self.assertIn(
            '"tenant_evidence_source": "NOT_INJECTED_REVIEW_ARTIFACT"',
            runtime,
        )
        self.assertIn('"tenant_evidence_auto_loaded": False', runtime)
        self.assertIn('"automatic_activation": False', runtime)
        self.assertIn('"production_persistence_activated": False', runtime)

    def test_tenant_evidence_bundle_has_admin_review_consumer_but_no_core_autoload(self):
        review = self._text("atlasquant_aion_tenant_persistence_review.py")
        runtime = self._text("atlasquant_aion_core_runtime_bridge.py")
        admin = self._text("atlasquant_aion_admin.py")
        self.assertIn("from atlasquant_aion_tenant_evidence_bundle import", review)
        self.assertIn("verify_local_evidence_bundle(", review)
        self.assertIn(
            "from atlasquant_aion_tenant_persistence_review import",
            admin,
        )
        self.assertIn("build_tenant_persistence_admin_review(", admin)
        self.assertNotIn("atlasquant_aion_tenant_evidence_bundle", runtime)
        self.assertNotIn(
            "docs/aion/evidence/tenant_persistence_local_evidence.json",
            runtime,
        )
        self.assertIn('"tenant_evidence_auto_loaded": False', runtime)

    def test_new_bridges_remain_non_authoritative_and_non_executing(self):
        recovery = self._text("atlasquant_aion_recovery_review.py")
        library = self._text("atlasquant_aion_library_preview.py")
        for source in (recovery, library):
            self.assertIn('"external_action_executed": False', source)
            self.assertIn('"execution_authorized": False', source)
        self.assertIn('"tool_output_is_authority": False', recovery)
        self.assertIn('"memory_promoted": False', library)
        self.assertIn('"ocr_executed": False', library)


if __name__ == "__main__":
    unittest.main()
