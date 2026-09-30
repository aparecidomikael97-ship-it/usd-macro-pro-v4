import json
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_checkpoint_latest import validate_latest_checkpoint


class AionCheckpointLatestTests(unittest.TestCase):
    def test_repository_latest_checkpoint_is_valid(self):
        result = validate_latest_checkpoint()
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["latest_date"], "2026-09-30")
        self.assertEqual(result["role_count"], 8)
        self.assertEqual(result["budget_cap_brl"], 200)

    def test_tampered_budget_is_blocked(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = [
                "docs/continuidade/checkpoint_mestre_latest.json",
                "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-30.json",
                "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-30.md",
                "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-29.json",
                "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md",
            ]
            for rel in files:
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((root / rel).read_text(encoding="utf-8"), encoding="utf-8")
            manifest_path = base / "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-30.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["economics"]["initial_monthly_budget_cap_brl"] = 1000
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validate_latest_checkpoint(base)
            self.assertFalse(result["ok"])
            self.assertIn("initial budget cap must be 200 BRL", result["errors"])

    def test_runtime_authorization_cannot_be_smuggled_in_pointer(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = [
                "docs/continuidade/checkpoint_mestre_latest.json",
                "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-30.json",
                "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-30.md",
                "docs/continuidade/checkpoint_mestre_reconciliation_2026-09-29.json",
                "docs/continuidade/CHECKPOINT_MESTRE_RECONCILIACAO_2026-09-29.md",
            ]
            for rel in files:
                target = base / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((root / rel).read_text(encoding="utf-8"), encoding="utf-8")
            pointer_path = base / "docs/continuidade/checkpoint_mestre_latest.json"
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            pointer["runtime_authorized"] = True
            pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
            result = validate_latest_checkpoint(base)
            self.assertFalse(result["ok"])
            self.assertIn("runtime_authorized invalid", result["errors"])


if __name__ == "__main__":
    unittest.main()
