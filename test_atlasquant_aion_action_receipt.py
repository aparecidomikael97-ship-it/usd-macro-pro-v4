from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from atlasquant_aion_action_receipt import (
    canonical_fingerprint,
    seal_action_receipt,
    validate_action_receipt,
)


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def _verify(refs):
    return {"state": "VERIFIED", "bound_refs": list(refs)}


class AtlasQuantAionActionReceiptTests(unittest.TestCase):
    def context(self, **extra):
        payload = {
            "requester_id": "user-1",
            "tenant_id": "tenant-a",
            "workspace_id": "central",
            "prime_id": "prime-1",
            "shadow_id": "shadow-1",
            "sentinel_id": "sentinel-1",
        }
        payload.update(extra)
        return payload

    def payload(self, **extra):
        payload = {
            "task_id": "task-1",
            "blast_radius": "LOW",
            "policy_ref": "policy-1",
            "guardian": {"state": "ALLOW", "allowed": True},
            "evidence_refs": ["evidence-1"],
            "approval_refs": ["approval-1"],
            "child_receipts": [{
                "receipt_id": "RCPT-CHILD",
                "schema": "AION_CORE_EXECUTION_RECEIPT_V1",
                "fingerprint": "a" * 64,
                "raw_secret": "token=example-token-value",
            }],
            "capability": "DRAFT",
            "tool_id": "draft",
            "state": "RECORDED",
            "result": "draft stored",
            "issued_at": NOW.isoformat(),
            "rollback_ref": "rollback-1",
            "correlation_id": "corr-1",
        }
        payload.update(extra)
        return payload

    def sealed(self, **extra):
        return seal_action_receipt(self.payload(**extra), trusted_context=self.context())

    def validate(self, receipt, **extra):
        payload = {
            "trusted_context": self.context(),
            "now": NOW,
            "evidence_verifier": _verify,
            "approval_verifier": _verify,
            "policy_verifier": _verify,
        }
        payload.update(extra)
        return validate_action_receipt(receipt, **payload)

    def test_fingerprint_is_stable_and_not_a_signature(self):
        first = self.sealed()
        second = self.sealed()
        self.assertEqual(first["receipt"]["fingerprint"], second["receipt"]["fingerprint"])
        self.assertFalse(first["digest_is_signature"])
        self.assertEqual(first["digest_kind"], "CANONICAL_FINGERPRINT")
        self.assertFalse(first["executes_action"])
        self.assertNotIn("raw_secret", first["receipt"]["child_receipts"][0])
        checked = self.validate(first["receipt"])
        self.assertEqual(checked["state"], "INFORMATION_ONLY")
        self.assertEqual(checked["authorization"], "NONE")
        self.assertEqual(checked["truth_state"], "UNKNOWN")

    def test_mutation_breaks_fingerprint_and_secrets_stay_redacted(self):
        sealed = self.sealed(result="token=example-token-value")
        self.assertNotIn("example-token-value", sealed["receipt"]["result"])
        self.assertTrue(sealed["secret_redacted"])
        mutated = dict(sealed["receipt"])
        mutated["result"] = "changed"
        checked = self.validate(mutated)
        self.assertFalse(checked["fingerprint_ok"])
        self.assertIn("FINGERPRINT_MISMATCH", checked["blockers"])
        self.assertEqual(checked["state"], "INVALID")

    def test_missing_bindings_guardian_and_scope_fail_closed(self):
        sealed = self.sealed(guardian={"state": "UNKNOWN", "allowed": "yes"}, evidence_refs=[], approval_refs=[], policy_ref="")
        checked = self.validate(sealed["receipt"])
        self.assertIn("GUARDIAN_UNKNOWN", checked["blockers"])
        self.assertIn("EVIDENCE_MISSING", checked["blockers"])
        self.assertIn("APPROVAL_MISSING", checked["blockers"])
        self.assertIn("POLICY_MISSING", checked["blockers"])
        self.assertEqual(checked["truth_state"], "UNKNOWN")
        other = self.validate(self.sealed()["receipt"], trusted_context=self.context(tenant_id="tenant-b"))
        self.assertIn("TENANT_MISMATCH", other["blockers"])
        workspace = self.validate(self.sealed()["receipt"], trusted_context=self.context(workspace_id="trading"))
        self.assertIn("WORKSPACE_MISMATCH", workspace["blockers"])

    def test_replay_forged_reviewer_policy_and_parent_fail_closed(self):
        receipt = self.sealed()["receipt"]
        replay = self.validate(receipt, seen_correlation_ids=["corr-1"])
        self.assertIn("REPLAY", replay["blockers"])
        forged = dict(receipt)
        forged["sentinel_id"] = "prime-1"
        forged["fingerprint"] = canonical_fingerprint({key: forged[key] for key in forged if key != "fingerprint"})
        checked = self.validate(forged)
        self.assertIn("FORGED_REVIEWER:SENTINEL", checked["blockers"])
        invented = self.validate(receipt, policy_verifier=lambda refs: {"state": "REJECTED", "bound_refs": list(refs)})
        self.assertIn("POLICY_UNVERIFIED", invented["blockers"])
        parent = dict(receipt)
        parent["parent_receipt_id"] = "RCPT-PARENT"
        parent["parent_fingerprint"] = ""
        parent["fingerprint"] = canonical_fingerprint({key: parent[key] for key in parent if key != "fingerprint"})
        invalid_parent = self.validate(parent)
        self.assertIn("PARENT_INVALID", invalid_parent["blockers"])
        future = dict(receipt)
        future["issued_at"] = (NOW + timedelta(minutes=5)).isoformat()
        future["fingerprint"] = canonical_fingerprint({key: future[key] for key in future if key != "fingerprint"})
        stale = self.validate(future)
        self.assertIn("STALE_OR_FUTURE", stale["blockers"])
        self.assertFalse(stale["executes_action"])


if __name__ == "__main__":
    unittest.main()
