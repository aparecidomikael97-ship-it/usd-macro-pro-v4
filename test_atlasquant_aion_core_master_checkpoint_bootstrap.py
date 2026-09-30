import json
import tempfile
import unittest
from pathlib import Path

from atlasquant_aion_core_master_checkpoint_bootstrap import (
    augment_system_context_with_master_checkpoint,
    master_checkpoint_bootstrap_snapshot,
    master_checkpoint_evidence,
)
from atlasquant_aion_core_runtime_bridge import handle_runtime_intent


def _access():
    return {
        "allowed": True,
        "mode": "AUTHENTICATED",
        "role": "ADMIN",
        "session": {
            "username": "mikael",
            "role": "ADMIN",
            "credential_fingerprint": "a1b2c3d4e5f60718293a4b5c",
            "permissions": ["app:read", "admin:read", "aion:admin"],
        },
    }


class AionCoreMasterCheckpointBootstrapTests(unittest.TestCase):
    def test_repository_checkpoint_loads_as_validated_snapshot(self):
        snapshot = master_checkpoint_bootstrap_snapshot()
        self.assertEqual(snapshot["state"], "MASTER_CHECKPOINT_LOADED")
        self.assertTrue(snapshot["evidence_ready"])
        self.assertEqual(snapshot["latest_date"], "2026-09-30")
        self.assertEqual(snapshot["economics"]["initial_monthly_budget_cap_brl"], 200)
        self.assertFalse(snapshot["runtime_authorized"])
        self.assertFalse(snapshot["executes_action"])

    def test_evidence_contains_priority_and_decisions(self):
        rows, snapshot = master_checkpoint_evidence()
        self.assertTrue(snapshot["evidence_ready"])
        claims = {row["claim"] for row in rows}
        self.assertIn("checkpoint.master.decisions", claims)
        self.assertIn("checkpoint.master.ecosystem_priority", claims)
        self.assertIn("checkpoint.master.economics", claims)
        self.assertTrue(all(row["truth_state"] == "CONFIRMED" for row in rows))
        self.assertTrue(all(row["time_sensitive"] is False for row in rows))

    def test_existing_system_evidence_is_preserved(self):
        original = {
            "core_evidence": [{
                "claim": "build",
                "value": "abc",
                "truth_state": "CONFIRMED",
                "source": "runtime",
                "source_ref": "build:abc",
                "time_sensitive": False,
            }]
        }
        augmented, state = augment_system_context_with_master_checkpoint(original)
        self.assertEqual(state["state"], "MASTER_CHECKPOINT_LOADED")
        self.assertGreater(len(augmented["core_evidence"]), 1)
        self.assertEqual(augmented["core_evidence"][0]["claim"], "build")

    def test_tampered_pointer_blocks_bootstrap(self):
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
            snapshot = master_checkpoint_bootstrap_snapshot(base)
            self.assertEqual(snapshot["state"], "MASTER_CHECKPOINT_BLOCKED")
            self.assertFalse(snapshot["evidence_ready"])

    def test_runtime_bridge_reports_master_checkpoint_state(self):
        result = handle_runtime_intent(
            _access(),
            "qual é o estado do sistema e das prioridades",
            system_context={},
        )
        self.assertEqual(
            result["master_checkpoint"]["state"],
            "MASTER_CHECKPOINT_LOADED",
        )
        self.assertFalse(result["master_checkpoint"]["runtime_authorized"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
