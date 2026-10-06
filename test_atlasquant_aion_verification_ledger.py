from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from atlasquant_aion_memory import checkpoint_integrity_report, default_checkpoint
from atlasquant_aion_verification_ledger import (
    GENESIS_HASH,
    default_verification_ledger,
    find_verified_entry,
    normalize_verification_ledger,
    record_independent_verification,
    verification_ledger_summary,
    verify_ledger_integrity,
)


NOW = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)


def scope(tenant="tenant-a", workspace="workspace-a", owner="mikael"):
    return {
        "owner_id": owner,
        "tenant_id": tenant,
        "workspace_id": workspace,
    }


def verifier(
    claim_digest,
    refs,
    *,
    verifier_id="critic-2",
    state="VERIFIED",
    independent=True,
):
    def check(_envelope):
        return {
            "state": state,
            "independent": independent,
            "verifier_id": verifier_id,
            "bound_claim_digest": claim_digest,
            "bound_refs": list(refs),
            "reason": "independent evidence check",
        }
    return check


class AionIndependentVerificationLedgerTests(unittest.TestCase):
    def _record(
        self,
        ledger=None,
        *,
        claim_id="claim-1",
        digest="sha256:claim-1",
        generator_id="generator-1",
        verifier_id="critic-2",
        refs=None,
        trusted=None,
        state="VERIFIED",
        independent=True,
    ):
        refs = refs or ["evidence:1"]
        return record_independent_verification(
            ledger or default_verification_ledger(),
            claim_id=claim_id,
            claim_kind="MEMORY_PROPOSAL",
            claim_digest=digest,
            generator_id=generator_id,
            verifier_kind="SOURCE_REQUERY",
            verifier_id=verifier_id,
            evidence_refs=refs,
            trusted_context=trusted or scope(),
            verifier=verifier(
                digest,
                refs,
                verifier_id=verifier_id,
                state=state,
                independent=independent,
            ),
            created_at=NOW,
        )

    def test_default_ledger_is_empty_matching_and_non_authoritative(self):
        ledger = default_verification_ledger()
        report = verify_ledger_integrity(ledger)
        self.assertEqual(report["state"], "MATCH")
        self.assertEqual(ledger["tip_hash"], GENESIS_HASH)
        self.assertEqual(ledger["entries"], [])
        self.assertFalse(ledger["automatic_authority"])
        self.assertFalse(ledger["executes_action"])

    def test_append_builds_hash_chain_and_preserves_previous_entry(self):
        first = self._record()
        second = self._record(
            first["ledger"],
            claim_id="claim-2",
            digest="sha256:claim-2",
            refs=["evidence:2"],
            verifier_id="critic-3",
        )
        rows = second["ledger"]["entries"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], first["entry"])
        self.assertEqual(rows[0]["previous_hash"], GENESIS_HASH)
        self.assertEqual(rows[1]["previous_hash"], rows[0]["entry_hash"])
        self.assertEqual(second["ledger"]["tip_hash"], rows[1]["entry_hash"])
        self.assertEqual(verify_ledger_integrity(second["ledger"])["state"], "MATCH")

    def test_generator_cannot_be_same_verifier_principal(self):
        with self.assertRaisesRegex(ValueError, "independent principals"):
            self._record(generator_id="same-agent", verifier_id="same-agent")

    def test_non_independent_result_is_recorded_inconclusive_not_verified(self):
        result = self._record(independent=False)
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertIn(
            "VERIFIER_INDEPENDENCE_NOT_PROVED",
            result["entry"]["blockers"],
        )
        self.assertEqual(
            find_verified_entry(
                result["ledger"],
                result["entry"]["entry_id"],
                claim_id="claim-1",
                claim_digest="sha256:claim-1",
                trusted_context=scope(),
            )["state"],
            "BLOCK",
        )

    def test_mismatched_claim_digest_and_refs_fail_closed(self):
        refs = ["evidence:1"]
        def bad(_envelope):
            return {
                "state": "VERIFIED",
                "independent": True,
                "verifier_id": "critic-2",
                "bound_claim_digest": "sha256:different",
                "bound_refs": ["evidence:different"],
                "reason": "bad binding",
            }
        result = record_independent_verification(
            default_verification_ledger(),
            claim_id="claim-1",
            claim_kind="MEMORY_PROPOSAL",
            claim_digest="sha256:claim-1",
            generator_id="generator-1",
            verifier_kind="SOURCE_REQUERY",
            verifier_id="critic-2",
            evidence_refs=refs,
            trusted_context=scope(),
            verifier=bad,
            created_at=NOW,
        )
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertIn("CLAIM_DIGEST_BINDING_MISMATCH", result["entry"]["blockers"])
        self.assertIn("EVIDENCE_REF_BINDING_MISMATCH", result["entry"]["blockers"])

    def test_verifier_exception_becomes_inconclusive_audit_event(self):
        def exploding(_envelope):
            raise RuntimeError("synthetic verifier outage")

        result = record_independent_verification(
            default_verification_ledger(),
            claim_id="claim-1",
            claim_kind="FACT",
            claim_digest="sha256:claim-1",
            generator_id="generator-1",
            verifier_kind="CODE",
            verifier_id="deterministic-checker",
            evidence_refs=["fixture:1"],
            trusted_context=scope(),
            verifier=exploding,
            created_at=NOW,
        )
        self.assertEqual(result["state"], "INCONCLUSIVE")
        self.assertEqual(len(result["ledger"]["entries"]), 1)
        self.assertEqual(verify_ledger_integrity(result["ledger"])["state"], "MATCH")

    def test_tampering_content_breaks_entry_hash(self):
        result = self._record()
        tampered = deepcopy(result["ledger"])
        tampered["entries"][0]["result_reason"] = "rewritten"
        report = verify_ledger_integrity(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertEqual(report["reason"], "ENTRY_HASH_MISMATCH")

    def test_deleting_first_entry_breaks_sequence_or_previous_hash(self):
        first = self._record()
        second = self._record(
            first["ledger"],
            claim_id="claim-2",
            digest="sha256:claim-2",
            refs=["evidence:2"],
            verifier_id="critic-3",
        )
        tampered = deepcopy(second["ledger"])
        tampered["entries"] = tampered["entries"][1:]
        report = verify_ledger_integrity(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn(
            report["reason"],
            {"ENTRY_SEQUENCE_MISMATCH", "HASH_CHAIN_PREVIOUS_MISMATCH"},
        )

    def test_reordering_entries_is_detected(self):
        first = self._record()
        second = self._record(
            first["ledger"],
            claim_id="claim-2",
            digest="sha256:claim-2",
            refs=["evidence:2"],
            verifier_id="critic-3",
        )
        tampered = deepcopy(second["ledger"])
        tampered["entries"] = list(reversed(tampered["entries"]))
        self.assertEqual(verify_ledger_integrity(tampered)["state"], "MISMATCH")

    def test_tip_or_digest_rewrite_is_detected(self):
        result = self._record()
        bad_tip = deepcopy(result["ledger"])
        bad_tip["tip_hash"] = GENESIS_HASH
        self.assertEqual(verify_ledger_integrity(bad_tip)["reason"], "LEDGER_TIP_MISMATCH")

        bad_digest = deepcopy(result["ledger"])
        bad_digest["digest"] = "0" * 64
        report = verify_ledger_integrity(bad_digest)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertEqual(report["reason"], "LEDGER_DIGEST_MISMATCH")

    def test_append_refuses_tampered_ledger(self):
        result = self._record()
        tampered = deepcopy(result["ledger"])
        tampered["entries"][0]["claim_id"] = "rewritten"
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            self._record(
                tampered,
                claim_id="claim-2",
                digest="sha256:claim-2",
                refs=["evidence:2"],
                verifier_id="critic-3",
            )

    def test_verified_entry_is_bound_to_exact_scope_and_claim(self):
        result = self._record()
        entry_id = result["entry"]["entry_id"]
        ok = find_verified_entry(
            result["ledger"],
            entry_id,
            claim_id="claim-1",
            claim_digest="sha256:claim-1",
            trusted_context=scope(),
        )
        self.assertTrue(ok["verified"])

        foreign = find_verified_entry(
            result["ledger"],
            entry_id,
            claim_id="claim-1",
            claim_digest="sha256:claim-1",
            trusted_context=scope(tenant="tenant-b"),
        )
        self.assertEqual(foreign["state"], "BLOCK")
        self.assertEqual(foreign["reason"], "SCOPE_MISMATCH")

        wrong_claim = find_verified_entry(
            result["ledger"],
            entry_id,
            claim_id="claim-other",
            claim_digest="sha256:claim-1",
            trusted_context=scope(),
        )
        self.assertEqual(wrong_claim["reason"], "CLAIM_BINDING_MISMATCH")

    def test_rejected_result_is_audited_but_never_verified(self):
        result = self._record(state="REJECTED")
        self.assertEqual(result["state"], "REJECTED")
        found = find_verified_entry(
            result["ledger"],
            result["entry"]["entry_id"],
            claim_id="claim-1",
            claim_digest="sha256:claim-1",
            trusted_context=scope(),
        )
        self.assertEqual(found["state"], "BLOCK")
        self.assertEqual(found["reason"], "VERIFICATION_NOT_CONFIRMED")

    def test_summary_reports_chain_state_without_authority(self):
        first = self._record()
        second = self._record(
            first["ledger"],
            claim_id="claim-2",
            digest="sha256:claim-2",
            refs=["evidence:2"],
            verifier_id="critic-3",
            state="REJECTED",
        )
        summary = verification_ledger_summary(second["ledger"])
        self.assertEqual(summary["integrity_state"], "MATCH")
        self.assertEqual(summary["entries"], 2)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["rejected"], 1)
        self.assertFalse(summary["automatic_authority"])
        self.assertFalse(summary["executes_action"])

    def test_checkpoint_master_covers_ledger_chain_integrity(self):
        cp = default_checkpoint()
        self.assertIn("verification_ledger", cp)
        self.assertEqual(checkpoint_integrity_report(cp)["state"], "CONFIRMED")

        recorded = self._record(cp["verification_ledger"])
        cp["verification_ledger"] = recorded["ledger"]
        self.assertEqual(checkpoint_integrity_report(cp)["state"], "CONFIRMED")

        tampered = deepcopy(cp)
        tampered["verification_ledger"]["entries"][0]["verifier_id"] = "rewritten"
        report = checkpoint_integrity_report(tampered)
        self.assertEqual(report["state"], "MISMATCH")
        self.assertIn("verification_ledger", report["mismatches"])

    def test_normalizer_does_not_silently_heal_tampered_chain(self):
        result = self._record()
        tampered = deepcopy(result["ledger"])
        tampered["entries"][0]["claim_kind"] = "REWRITTEN"
        normalized = normalize_verification_ledger(tampered)
        self.assertEqual(normalized["integrity_state"], "MISMATCH")
        self.assertEqual(normalized["entries"][0]["claim_kind"], "REWRITTEN")


if __name__ == "__main__":
    unittest.main()
