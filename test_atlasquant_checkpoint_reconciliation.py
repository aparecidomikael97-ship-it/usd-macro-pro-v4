import ast
import copy
import unittest
from pathlib import Path

import atlasquant_checkpoint_reconciliation as gate


ROOT = Path(__file__).resolve().parent


class CheckpointReconciliationGateTests(unittest.TestCase):
    def test_repository_gate_passes(self):
        report = gate.validate_repository(ROOT)
        self.assertEqual(report["errors"], [], "\n".join(report["errors"]))
        self.assertTrue(report["ok"])
        self.assertEqual(report["gate_id"], gate.GATE_ID)
        self.assertGreaterEqual(report["adr_count"], 10)
        self.assertGreaterEqual(report["decision_count"], len(gate.REQUIRED_DECISION_IDS))
        self.assertGreaterEqual(report["source_count"], len(gate.REQUIRED_SOURCES))
        self.assertEqual(report["ok"], not report["errors"])

    def test_period_registry_and_preserved_checkpoint_are_present(self):
        narrative = (ROOT / gate.NARRATIVE_PATH).read_text(encoding="utf-8")
        readme = (ROOT / gate.ADR_README).read_text(encoding="utf-8")
        self.assertIn("2026-09-15", narrative)
        self.assertIn("2026-09-29", narrative)
        self.assertIn(gate.PRESERVED_CHECKPOINT, narrative)
        self.assertIn("Average Daily Range", narrative)
        self.assertIn("American Depositary Receipts", narrative)
        self.assertIn("Average True Range", narrative)
        self.assertIn("Architecture Decision Records", readme)
        self.assertNotIn("requests", (ROOT / "atlasquant_checkpoint_reconciliation.py").read_text(encoding="utf-8"))
        tree = ast.parse((ROOT / "atlasquant_checkpoint_reconciliation.py").read_text(encoding="utf-8"))
        imported = [node.names[0].name if isinstance(node, ast.Import) else node.module for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual(imported, ["__future__", "json", "pathlib", "typing"])
        source = (ROOT / "atlasquant_checkpoint_reconciliation.py").read_text(encoding="utf-8")
        for banned in ("urllib", "httpx", "socket", "openai", "subprocess"):
            self.assertNotIn(banned, source)

    def test_pending_cannot_be_marked_validated_or_implemented(self):
        manifest = gate.load_manifest(ROOT)
        item = copy.deepcopy(manifest["decisions"][0])
        item["state"] = "APROVADO / PENDENTE"
        item["validated"] = True
        item["implemented"] = True
        errors = gate.validate_decision(item)
        self.assertTrue(any("validado" in error for error in errors))
        self.assertTrue(any("implementado" in error for error in errors))

    def test_implemented_cannot_be_presented_as_validated(self):
        errors = gate.validate_decision({
            "id": "D-EXAMPLE",
            "state": "IMPLEMENTADO / EM VALIDAÇÃO",
            "implemented": True,
            "validated": True,
            "evidence": ["docs/aion/ARCHITECTURE.md"],
        })
        self.assertTrue(any("VALIDADO" in error for error in errors))
        missing = gate.validate_decision({
            "id": "D-EXAMPLE",
            "state": "VALIDADO",
            "validated": True,
            "implemented": True,
            "evidence": [],
        })
        self.assertTrue(any("evidência" in error for error in missing))

    def test_invalid_state_and_superseded_without_successor_fail(self):
        self.assertTrue(gate.validate_decision({"id": "D-BAD", "state": "QUASE_PRONTO"}))
        errors = gate.validate_decision({
            "id": "D-OLD",
            "state": "SUBSTITUÍDO",
            "implemented": False,
            "validated": False,
            "superseded_by": "",
        })
        self.assertTrue(any("substituto" in error for error in errors))
        adr_errors = gate.validate_adr_text("ADR-0099", "Status: SUPERSEDED\nSuperseded by\nNenhum\n", "SUPERSEDED")
        self.assertTrue(any("SUPERSEDED" in error for error in adr_errors))

    def test_missing_required_decision_or_adr_fails_closed(self):
        manifest = gate.load_manifest(ROOT)
        narrative = (ROOT / gate.NARRATIVE_PATH).read_text(encoding="utf-8")
        readme = (ROOT / gate.ADR_README).read_text(encoding="utf-8")
        shrunk = copy.deepcopy(manifest)
        shrunk["decisions"] = [item for item in shrunk["decisions"] if item["id"] != "D-REAL-TRADING-FAIL-CLOSED"]
        errors = gate.validate_manifest(
            shrunk,
            narrative=narrative + "\n" + readme,
            adr_texts={},
            existing_paths=set(),
        )
        self.assertTrue(any("D-REAL-TRADING-FAIL-CLOSED" in error for error in errors))
        without_adr = copy.deepcopy(manifest)
        without_adr["adrs"] = without_adr["adrs"][:-1]
        errors = gate.validate_manifest(
            without_adr,
            narrative=narrative + "\n" + readme,
            adr_texts={},
            existing_paths=set(),
        )
        self.assertTrue(any("registry de ADR" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
