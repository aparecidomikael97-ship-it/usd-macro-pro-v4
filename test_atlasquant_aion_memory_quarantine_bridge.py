from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from atlasquant_aion_memory import (
    AION_MEMORY_QUARANTINE_NAMESPACE,
    checkpoint_integrity_report,
    checkpoint_source_digest,
    ensure_operating_checkpoint,
)
from atlasquant_aion_memory_quarantine_bridge import (
    load_quarantine_checkpoint,
    stage_memory_candidate,
    stage_memory_promotion,
)


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
CTX = {
    "tenant_id": "tenant-a",
    "workspace_id": "central",
    "role": "ADMIN",
    "review_approved": True,
}


def verified(refs):
    return {"state": "VERIFIED", "bound_refs": list(refs)}


class AionMemoryQuarantineCheckpointBridgeTests(unittest.TestCase):
    def stage(self):
        return stage_memory_candidate(
            {},
            content="Preferência observada para respostas compactas.",
            source_type="PASTED_TEXT",
            tenant_id="tenant-a",
            workspace_id="central",
            trusted_context=CTX,
            observed_at=NOW,
            provenance="conversation:1",
            evidence_refs=["evidence:1"],
            category="fact",
            now=NOW,
        )

    def test_candidate_is_staged_in_versioned_namespace_only(self):
        result = self.stage()
        self.assertEqual(result["status"], "STAGED")
        self.assertTrue(result["requires_checkpoint_save"])
        self.assertFalse(result["external_persisted"])
        cp = result["checkpoint"]
        self.assertIn(AION_MEMORY_QUARANTINE_NAMESPACE, cp)
        self.assertTrue(cp[AION_MEMORY_QUARANTINE_NAMESPACE]["digest"])
        self.assertEqual(len(cp[AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"]), 1)

        baseline = ensure_operating_checkpoint({})
        self.assertEqual(cp["memory_layers"]["digest"], baseline["memory_layers"]["digest"])

    def test_namespace_integrity_is_checked_by_master_report(self):
        result = self.stage()
        report = checkpoint_integrity_report(result["checkpoint"])
        self.assertNotIn("aion_memory_quarantine", report["mismatches"])
        row = next(x for x in report["checks"] if x["component"] == "aion_memory_quarantine")
        self.assertEqual(row["state"], "MATCH")

        tampered = deepcopy(result["checkpoint"])
        tampered[AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"][0]["content"] = "tampered"
        report = checkpoint_integrity_report(tampered)
        self.assertIn("aion_memory_quarantine", report["mismatches"])

    def test_quarantine_changes_checkpoint_conflict_digest(self):
        baseline = ensure_operating_checkpoint({})
        staged = self.stage()["checkpoint"]
        self.assertNotEqual(
            checkpoint_source_digest(baseline),
            checkpoint_source_digest(staged),
        )

    def test_load_rejects_tampered_namespace(self):
        staged = self.stage()["checkpoint"]
        tampered = deepcopy(staged)
        tampered[AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"][0]["state"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "MEMORY_QUARANTINE_DIGEST_MISMATCH"):
            load_quarantine_checkpoint(tampered)

    def test_promotion_requires_admin_review_and_verified_evidence(self):
        staged = self.stage()["checkpoint"]
        candidate = staged[AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"][0]["candidate_id"]

        blocked_ctx = dict(CTX)
        blocked_ctx["review_approved"] = "true"
        blocked = stage_memory_promotion(
            staged,
            candidate,
            trusted_context=blocked_ctx,
            evidence_verifier=verified,
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("REVIEW_MISSING", blocked["blockers"])

        blocked = stage_memory_promotion(
            staged,
            candidate,
            trusted_context=CTX,
            evidence_verifier=None,
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("EVIDENCE_UNVERIFIED", blocked["blockers"])

    def test_verified_promotion_updates_layers_only_as_unknown_truth(self):
        staged = self.stage()["checkpoint"]
        candidate = staged[AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"][0]["candidate_id"]
        before = staged["memory_layers"]["digest"]

        promoted = stage_memory_promotion(
            staged,
            candidate,
            trusted_context=CTX,
            evidence_verifier=verified,
        )
        self.assertEqual(promoted["status"], "STAGED")
        self.assertTrue(promoted["memory_promoted"])
        self.assertEqual(promoted["truth_state"], "UNKNOWN")
        self.assertEqual(promoted["authority"], "NONE")
        self.assertNotEqual(promoted["checkpoint"]["memory_layers"]["digest"], before)
        stored = promoted["checkpoint"][AION_MEMORY_QUARANTINE_NAMESPACE]["candidates"][0]
        self.assertEqual(stored["state"], "APPROVED")
        self.assertEqual(stored["truth_state"], "UNKNOWN")

    def test_cross_scope_candidate_is_not_persisted(self):
        result = stage_memory_candidate(
            {},
            content="conteúdo",
            source_type="PASTED_TEXT",
            tenant_id="tenant-b",
            workspace_id="central",
            trusted_context=CTX,
            observed_at=NOW,
            evidence_refs=["evidence:1"],
            now=NOW,
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["requires_checkpoint_save"])
        self.assertNotIn(AION_MEMORY_QUARANTINE_NAMESPACE, result["checkpoint"])

    def test_bridge_has_no_network_or_runtime_save(self):
        source = Path("atlasquant_aion_memory_quarantine_bridge.py").read_text(encoding="utf-8")
        for banned in (
            "import requests",
            "requests.",
            "save_runtime_checkpoint(",
            "restore_checkpoint_revision(",
            "subprocess",
            "urlopen(",
        ):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
