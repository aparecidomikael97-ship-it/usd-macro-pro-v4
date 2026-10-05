from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from aion_chat.models import Scope
from atlasquant_aion_governance_audit_bridge import (
    append_authority_revalidation_audit,
    append_memory_promotion_audit,
    append_outbox_reconciliation_audit,
    append_verification_audit,
)
from atlasquant_aion_independent_verifier import (
    as_memory_verifier_result,
    new_verification_request,
    validate_verification_receipt,
    verify_with_code,
    verify_with_human_review,
    verify_with_independent_model,
    verify_with_source_requery,
)
from atlasquant_aion_memory_governance import (
    default_memory_governance,
    promote_verified_memory,
    propose_memory,
    verify_memory_proposal,
)
from atlasquant_aion_memory_layers import default_memory_layers
from atlasquant_aion_unified_journal import (
    new_request_journal,
    verify_request_journal,
)
from atlasquant_aion_unified_journal_store import UnifiedJournalStore


NOW = datetime(2026, 10, 5, 6, 30, tzinfo=timezone.utc)
SCOPE = Scope("mikael", "tenant-a", "workspace-a")


def request(*, producer_id="producer", producer_fp="producer-fp"):
    return new_verification_request(
        claim_ref="claim-1",
        content="Fonte primária confirma o valor observado.",
        source_type="DOCUMENT",
        producer_id=producer_id,
        producer_fingerprint=producer_fp,
        evidence_refs=["evidence:1", "evidence:2"],
        provenance_refs=["source:primary"],
        scope=SCOPE,
        policy_version="policy-v1",
        created_at=NOW,
    )


def source_receipt(req, *, verifier_id="source-verifier", verifier_fp="verifier-fp", now=NOW):
    def resolver(refs):
        return {
            "state": "VERIFIED",
            "bound_refs": list(refs),
            "content_digest": req["content_digest"],
            "source_snapshots": [
                {"ref": ref, "digest": "sha256:snapshot-" + str(i)}
                for i, ref in enumerate(refs)
            ],
        }
    return verify_with_source_requery(
        req,
        verifier_id=verifier_id,
        verifier_fingerprint=verifier_fp,
        resolver=resolver,
        now=now,
    )


class IndependentVerifierTests(unittest.TestCase):
    def test_same_producer_identity_cannot_verify_itself(self):
        req = request(producer_id="same", producer_fp="same-fp")
        receipt = verify_with_code(
            req,
            verifier_id="same",
            verifier_fingerprint="same-fp",
            checks={"digest": True, "range": True},
            now=NOW,
        )
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn("PRODUCER_VERIFIER_ID_COLLISION", receipt["blockers"])
        self.assertIn("PRODUCER_VERIFIER_FINGERPRINT_COLLISION", receipt["blockers"])
        self.assertFalse(receipt["independent"])

    def test_code_lane_requires_all_deterministic_checks_true(self):
        req = request()
        blocked = verify_with_code(
            req,
            verifier_id="code-verifier",
            verifier_fingerprint="code-verifier-fp",
            checks={"digest": True, "constraint": False},
            now=NOW,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("CODE_CHECK_FAILED", blocked["blockers"])

        verified = verify_with_code(
            req,
            verifier_id="code-verifier",
            verifier_fingerprint="code-verifier-fp",
            checks={"digest": True, "constraint": True},
            now=NOW,
        )
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertTrue(verified["independent"])
        self.assertFalse(verified["action_authorized"])
        self.assertFalse(verified["executes_action"])

    def test_source_requery_requires_exact_refs_snapshots_and_digest(self):
        req = request()

        bad = verify_with_source_requery(
            req,
            verifier_id="source-verifier",
            verifier_fingerprint="source-verifier-fp",
            resolver=lambda refs: {
                "state": "VERIFIED",
                "bound_refs": [refs[0]],
                "content_digest": "sha256:wrong",
                "source_snapshots": [],
            },
            now=NOW,
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertIn("SOURCE_CONTENT_DIGEST_MISMATCH", bad["blockers"])
        self.assertIn("SOURCE_BOUND_REFS_MISMATCH", bad["blockers"])
        self.assertIn("SOURCE_SNAPSHOTS_MISSING", bad["blockers"])

        good = source_receipt(req)
        self.assertEqual(good["state"], "VERIFIED")
        self.assertEqual(sorted(good["bound_refs"]), sorted(req["evidence_refs"]))
        self.assertTrue(good["receipt_digest"].startswith("sha256:"))

    def test_independent_model_lane_requires_distinct_fingerprint_and_attestation(self):
        req = request()
        blocked = verify_with_independent_model(
            req,
            verifier_id="model-reviewer",
            verifier_fingerprint="model-reviewer-fp",
            evaluator=lambda raw: {
                "state": "VERIFIED",
                "independent": False,
                "bound_refs": raw["evidence_refs"],
                "content_digest": raw["content_digest"],
                "verifier_fingerprint": "model-reviewer-fp",
                "evaluation_ref": "eval-1",
            },
            now=NOW,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("MODEL_INDEPENDENCE_NOT_ATTESTED", blocked["blockers"])

        verified = verify_with_independent_model(
            req,
            verifier_id="model-reviewer",
            verifier_fingerprint="model-reviewer-fp",
            evaluator=lambda raw: {
                "state": "VERIFIED",
                "independent": True,
                "bound_refs": raw["evidence_refs"],
                "content_digest": raw["content_digest"],
                "verifier_fingerprint": "model-reviewer-fp",
                "evaluation_ref": "eval-2",
            },
            now=NOW,
        )
        self.assertEqual(verified["state"], "VERIFIED")

    def test_human_lane_is_evidence_bound_not_blanket_approval(self):
        req = request()
        blocked = verify_with_human_review(
            req,
            verifier_id="human-reviewer",
            verifier_fingerprint="human-reviewer-fp",
            reviewed_refs=["evidence:1"],
            review_approved=True,
            review_ref="review-1",
            now=NOW,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("HUMAN_REVIEW_REFS_MISMATCH", blocked["blockers"])

        verified = verify_with_human_review(
            req,
            verifier_id="human-reviewer",
            verifier_fingerprint="human-reviewer-fp",
            reviewed_refs=req["evidence_refs"],
            review_approved=True,
            review_ref="review-2",
            now=NOW,
        )
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertFalse(verified["approval_implied"])

    def test_receipt_tamper_scope_and_staleness_fail_closed(self):
        req = request()
        receipt = source_receipt(req)

        tampered = deepcopy(receipt)
        tampered["content_digest"] = "sha256:tampered"
        check = validate_verification_receipt(
            tampered,
            request=req,
            scope=SCOPE,
            now=NOW,
        )
        self.assertFalse(check["valid"])
        self.assertIn("RECEIPT_DIGEST_MISMATCH", check["blockers"])

        other_scope = Scope("mikael", "tenant-b", "workspace-a")
        check = validate_verification_receipt(
            receipt,
            request=req,
            scope=other_scope,
            now=NOW,
        )
        self.assertIn("RECEIPT_SCOPE_MISMATCH", check["blockers"])

        stale = validate_verification_receipt(
            receipt,
            request=req,
            scope=SCOPE,
            now=NOW + timedelta(minutes=16),
        )
        self.assertIn("RECEIPT_STALE_OR_FUTURE", stale["blockers"])

    def test_memory_promotion_requires_structurally_validated_receipt(self):
        proposed = propose_memory(
            default_memory_governance(),
            content="Fonte primária confirma o valor observado.",
            source_type="DOCUMENT",
            provenance_ref="source:primary",
            evidence_refs=["evidence:1", "evidence:2"],
            category="macro",
            layer="knowledge",
            domain="TRADER",
            memory_key="macro:value",
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            created_at=NOW,
        )
        p = proposed["proposal"]
        req = new_verification_request(
            claim_ref=p["proposal_id"],
            content=p["content"],
            source_type=p["source_type"],
            producer_id="memory-producer",
            producer_fingerprint="memory-producer-fp",
            evidence_refs=p["evidence_refs"],
            provenance_refs=[p["provenance_ref"]],
            scope=SCOPE,
            policy_version="memory-policy-v1",
            created_at=NOW,
        )
        receipt = source_receipt(req)

        def callback(_candidate):
            return as_memory_verifier_result(
                receipt,
                request=req,
                scope=SCOPE,
                now=NOW,
            )

        verified = verify_memory_proposal(
            proposed["governance"],
            p["proposal_id"],
            verifier_kind="SOURCE_REQUERY",
            verifier_id="source-verifier",
            verification_refs=p["evidence_refs"],
            verifier=callback,
            verification_receipt=receipt,
            verification_request=req,
            verification_scope={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            now=NOW,
        )
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertTrue(verified["proposal"]["verification_receipt_validated"])

        promoted = promote_verified_memory(
            verified["governance"],
            default_memory_layers(),
            p["proposal_id"],
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            review_approved=True,
            reviewed_by="mikael",
            now=NOW,
        )
        self.assertEqual(promoted["state"], "PROMOTED")
        self.assertEqual(
            promoted["proposal"]["verification_receipt_digest"],
            receipt["receipt_digest"],
        )

    def test_unreceipted_verified_memory_cannot_promote(self):
        proposed = propose_memory(
            default_memory_governance(),
            content="Contexto sem receipt.",
            source_type="DOCUMENT",
            provenance_ref="doc:1",
            evidence_refs=["evidence:1"],
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            created_at=NOW,
        )
        p = proposed["proposal"]
        verified = verify_memory_proposal(
            proposed["governance"],
            p["proposal_id"],
            verifier_kind="SOURCE_REQUERY",
            verifier_id="legacy-callback",
            verification_refs=["evidence:1"],
            verifier=lambda candidate: {
                "state": "VERIFIED",
                "independent": True,
                "verifier_id": "legacy-callback",
                "bound_refs": ["evidence:1"],
                "content_digest": candidate["content_digest"],
            },
            now=NOW,
        )
        self.assertEqual(verified["state"], "VERIFIED")
        self.assertFalse(verified["proposal"]["verification_receipt_validated"])
        blocked = promote_verified_memory(
            verified["governance"],
            default_memory_layers(),
            p["proposal_id"],
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            review_approved=True,
            reviewed_by="mikael",
            now=NOW,
        )
        self.assertEqual(blocked["state"], "BLOCK")
        self.assertIn("VERIFICATION_RECEIPT_REQUIRED", blocked["blockers"])


class GovernanceAuditBridgeTests(unittest.TestCase):
    def test_verification_and_promotion_events_extend_existing_hash_chain(self):
        req = request()
        receipt = source_receipt(req)
        journal = new_request_journal(SCOPE, "REQ-AUDIT", "conv-audit")
        journal = append_verification_audit(
            journal,
            receipt=receipt,
            request=req,
            scope=SCOPE,
            observed_at=NOW.isoformat(),
        )
        self.assertTrue(
            verify_request_journal(journal, scope=SCOPE, request_id="REQ-AUDIT")["valid"]
        )
        self.assertEqual(journal["events"][0]["event_type"], "VERIFICATION_RECORDED")

        # Build a real promoted memory result for the audit bridge.
        proposed = propose_memory(
            default_memory_governance(),
            content=req["content"],
            source_type="DOCUMENT",
            provenance_ref="source:primary",
            evidence_refs=req["evidence_refs"],
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            created_at=NOW,
        )
        p = proposed["proposal"]
        memory_req = new_verification_request(
            claim_ref=p["proposal_id"],
            content=p["content"],
            source_type=p["source_type"],
            producer_id="memory-producer",
            producer_fingerprint="memory-producer-fp",
            evidence_refs=p["evidence_refs"],
            provenance_refs=[p["provenance_ref"]],
            scope=SCOPE,
            policy_version="memory-policy-v1",
            created_at=NOW,
        )
        memory_receipt = source_receipt(memory_req)

        def callback(_candidate):
            return as_memory_verifier_result(
                memory_receipt,
                request=memory_req,
                scope=SCOPE,
                now=NOW,
            )

        verified = verify_memory_proposal(
            proposed["governance"],
            p["proposal_id"],
            verifier_kind="SOURCE_REQUERY",
            verifier_id="source-verifier",
            verification_refs=p["evidence_refs"],
            verifier=callback,
            verification_receipt=memory_receipt,
            verification_request=memory_req,
            verification_scope={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            now=NOW,
        )
        promoted = promote_verified_memory(
            verified["governance"],
            default_memory_layers(),
            p["proposal_id"],
            trusted_context={
                "owner_id": SCOPE.owner_id,
                "tenant_id": SCOPE.tenant_id,
                "workspace_id": SCOPE.workspace_id,
            },
            review_approved=True,
            reviewed_by="mikael",
            now=NOW,
        )
        journal = append_memory_promotion_audit(
            journal,
            promotion=promoted,
            observed_at=NOW.isoformat(),
        )
        check = verify_request_journal(journal, scope=SCOPE, request_id="REQ-AUDIT")
        self.assertTrue(check["valid"])
        self.assertEqual(journal["revision"], 2)
        self.assertEqual(
            journal["events"][1]["event_type"],
            "MEMORY_PROMOTION_RECORDED",
        )

        tampered = deepcopy(journal)
        tampered["events"][0]["metadata"]["verifier_id"] = "forged"
        self.assertFalse(
            verify_request_journal(tampered, scope=SCOPE, request_id="REQ-AUDIT")["valid"]
        )

    def test_governance_audit_events_survive_physical_store_restart(self):
        req = request()
        receipt = source_receipt(req)
        journal = new_request_journal(SCOPE, "REQ-DURABLE-AUDIT", "conv-durable-audit")
        journal = append_verification_audit(
            journal,
            receipt=receipt,
            request=req,
            scope=SCOPE,
            observed_at=NOW.isoformat(),
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "journal"
            first = UnifiedJournalStore(root)
            persisted = first.persist_journal(
                journal,
                scope=SCOPE,
                request_id="REQ-DURABLE-AUDIT",
                idempotency_key="governance-audit-1",
            )
            self.assertEqual(persisted["persistence_state"], "DURABLE")

            restarted = UnifiedJournalStore(root)
            recovered = restarted.recover(
                scope=SCOPE,
                request_id="REQ-DURABLE-AUDIT",
            )
            self.assertEqual(recovered["status"], "RECOVERED")
            self.assertEqual(recovered["event_count"], 1)
            self.assertTrue(recovered["journal_integrity"]["valid"])
            self.assertFalse(recovered["external_action_executed"])
            self.assertFalse(recovered["memory_promoted"])

    def test_revocation_and_reconciliation_are_auditable_without_granting_authority(self):
        journal = new_request_journal(SCOPE, "REQ-OUTBOX", "conv-outbox")
        journal = append_authority_revalidation_audit(
            journal,
            outbox_result={
                "state": "REVOKED",
                "idempotency_key": "idem-1",
                "decision_id": "dec-1",
                "last_error": "AUTHORITY_REVOKED",
            },
            observed_at=NOW.isoformat(),
        )
        journal = append_outbox_reconciliation_audit(
            journal,
            outbox_result={
                "state": "CONFIRMED",
                "reconcile_state": "CONFIRMED",
                "idempotency_key": "idem-2",
                "decision_id": "dec-2",
                "effect_ref": "effect-1",
            },
            observed_at=NOW.isoformat(),
        )
        check = verify_request_journal(journal, scope=SCOPE, request_id="REQ-OUTBOX")
        self.assertTrue(check["valid"])
        self.assertEqual(
            [row["event_type"] for row in journal["events"]],
            ["AUTHORITY_REVALIDATED", "OUTBOX_RECONCILED"],
        )
        self.assertTrue(
            all(row["external_action_executed"] is False for row in journal["events"])
        )


if __name__ == "__main__":
    unittest.main()
