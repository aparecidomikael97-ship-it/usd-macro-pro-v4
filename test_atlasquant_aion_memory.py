import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_memory import (
    APPROVED_AION_FOUNDATION,
    RuntimeConfig,
    canonical_documents,
    canonical_memory_summary,
    checkpoint_digest,
    default_checkpoint,
    ensure_operating_checkpoint,
    load_runtime_checkpoint,
    merged_checkpoint,
    save_runtime_checkpoint,
    search_canonical_memory,
    update_operating_checkpoint,
)


class AtlasQuantAionMemoryTests(unittest.TestCase):
    def test_static_foundation_contains_truth_cost_and_context_separation(self):
        joined = " ".join(APPROVED_AION_FOUNDATION).lower()
        self.assertIn("verdade", joined)
        self.assertIn("custo zero", joined)
        self.assertIn("studio", joined)
        self.assertIn("negócios", joined)
        self.assertIn("checkpoint", joined)
        self.assertIn("execução real", joined)

    def test_canonical_loader_reads_project_files_and_foundation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTEXTO_DO_PROJETO.md").write_text("AtlasQuant checkpoint mestre", encoding="utf-8")
            (root / "HISTORICO_DE_ALTERACOES.md").write_text("Histórico AtlasQuant", encoding="utf-8")
            docs = canonical_documents(root)
            paths = {d["path"] for d in docs}
            self.assertIn("CONTEXTO_DO_PROJETO.md", paths)
            self.assertIn("HISTORICO_DE_ALTERACOES.md", paths)
            self.assertIn("AION_APPROVED_FOUNDATION_2026-09-23", paths)
            summary = canonical_memory_summary(root)
            self.assertEqual(summary["status"], "CONFIRMED")
            self.assertGreaterEqual(summary["document_count"], 3)

    def test_memory_search_returns_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "CONTEXTO_DO_PROJETO.md").write_text(
                "AION deve usar Checkpoint Mestre para desenvolvimento e memória.",
                encoding="utf-8",
            )
            hits = search_canonical_memory("checkpoint desenvolvimento", base_dir=root)
            self.assertTrue(hits)
            self.assertIn("path", hits[0])
            self.assertIn("excerpt", hits[0])
            self.assertIn("sha256", hits[0])

    def test_default_checkpoint_is_safe_and_has_no_real_trading(self):
        cp = default_checkpoint()
        self.assertFalse(cp["aion"]["real_trading"])
        self.assertEqual(cp["aion"]["cost_mode"], "ZERO_COST_DEFAULT")
        self.assertIn("approved_foundation", cp)
        self.assertTrue(checkpoint_digest(cp))

    def test_checkpoint_v2_has_operating_memory(self):
        cp=default_checkpoint()
        self.assertGreaterEqual(cp["checkpoint_version"],2)
        self.assertIn("operating",cp)
        self.assertEqual(cp["operating"]["tasks"],[])
        self.assertEqual(cp["operating"]["events"],[])
        self.assertFalse(cp["operating"]["dirty"])

    def test_older_checkpoint_is_upgraded_without_claiming_persistence(self):
        old={"checkpoint_version":1,"project":"AtlasQuant"}
        upgraded=ensure_operating_checkpoint(old)
        self.assertEqual(upgraded["checkpoint_version"],2)
        self.assertIn("operating",upgraded)
        changed=update_operating_checkpoint(upgraded,tasks=[],events=[],dirty=True)
        self.assertTrue(changed["operating"]["dirty"])
        self.assertTrue(changed["operating"]["task_digest"])
        self.assertTrue(changed["operating"]["event_digest"])

    def test_runtime_load_is_truthful_when_credentials_missing(self):
        cfg = RuntimeConfig(token="", repo="", branch="atlasquant-runtime")
        result = load_runtime_checkpoint(cfg)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["checkpoint"])

    def test_save_requires_explicit_approval_before_any_network_use(self):
        cfg = RuntimeConfig(token="x", repo="owner/repo", branch="atlasquant-runtime")
        result = save_runtime_checkpoint(default_checkpoint(), cfg, approved=False)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["saved"])

    def test_runtime_writes_refuse_code_branch(self):
        cfg = RuntimeConfig(token="x", repo="owner/repo", branch="main")
        load = load_runtime_checkpoint(cfg)
        save = save_runtime_checkpoint(default_checkpoint(), cfg, approved=True)
        self.assertEqual(load["status"], "BLOCKED")
        self.assertEqual(save["status"], "BLOCKED")

    def test_merged_checkpoint_labels_static_fallback(self):
        merged = merged_checkpoint({"status": "UNAVAILABLE"})
        self.assertFalse(merged["runtime_confirmed"])
        self.assertEqual(merged["provenance"], "static-seed")
        self.assertIn("checkpoint", merged)


if __name__ == "__main__":
    unittest.main()
