"""A298 LAB: exact six-P0 gap register stays NO-GO and evidence-separated."""
from dataclasses import replace
import json
import unittest
from unittest import mock

from labs import a298_six_p0_gap_register_lab as registry


class A298CanonicalSixP0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = registry.audit_six_p0_registry()

    def test_exact_six_canonical_ids_in_order(self):
        self.assertEqual(
            [item.id for item in registry.P0_REGISTRY],
            [f"P0-{i}" for i in range(1, 7)],
        )
        self.assertEqual(self.audit["blocked_count_computed"], 6)
        self.assertEqual(self.audit["homologated_count_computed"], 0)

    def test_all_six_include_acceptance_gap_free_next_action_and_real_dependency(self):
        self.assertTrue(self.audit["valid_lab_inventory"], self.audit["issues"])
        for item in registry.P0_REGISTRY:
            with self.subTest(p0=item.id):
                self.assertTrue(item.title.strip())
                self.assertTrue(item.acceptance.strip())
                self.assertTrue(item.observed_gap.strip())
                self.assertTrue(item.free_lab_next_action.strip())
                self.assertTrue(item.needs_real_independence.strip())
                self.assertFalse(item.homologated)
                self.assertGreaterEqual(len(item.evidence_prs), 2)

    def test_owner_and_receipt_p0_require_real_independence(self):
        self.assertIn("proprietário", registry.P0_REGISTRY[0].title)
        self.assertIn("externos", registry.P0_REGISTRY[1].title)
        self.assertIn("independente", registry.P0_REGISTRY[0].acceptance)
        self.assertIn("custodiantes", registry.P0_REGISTRY[1].acceptance)

    def test_semantic_duplication_and_crash_recovery_are_distinct(self):
        p3,p4 = registry.P0_REGISTRY[2:4]
        self.assertIn("IDs técnicos", p3.acceptance)
        self.assertIn("primeira", p3.acceptance.lower())
        self.assertIn("rollback", p4.title)
        self.assertIn("high-water", p4.acceptance)

    def test_native_sqlite_read_and_write_p0_are_distinct(self):
        p5,p6 = registry.P0_REGISTRY[4:6]
        self.assertIn("VFS/FD", p5.acceptance)
        self.assertIn("COMMIT", p6.acceptance)
        self.assertIn(1504, p5.evidence_prs)
        self.assertIn(1743, p6.evidence_prs)

    def test_no_lab_pr_is_interpreted_as_p0_closure(self):
        self.assertEqual(self.audit["decision"], registry.HARD_NO_GO)
        self.assertFalse(self.audit["ready_for_real_worker"])
        self.assertFalse(self.audit["external_trust_verified"])
        self.assertTrue(self.audit["all_evidence_is_pr_description_or_prior_lab"])
        self.assertEqual(self.audit["homologated_count_computed"], 0)

    def test_zero_spending_no_deploy_and_zero_resend(self):
        report = registry.registry_as_dict()
        self.assertFalse(report["new_spending_authorized"])
        self.assertFalse(report["can_homologate_from_lab"])
        self.assertTrue(report["worker_disabled"])
        self.assertTrue(report["deploy_disabled"])
        self.assertTrue(report["zero_auto_resend"])
        self.assertTrue(report["hard_no_go"])
        self.assertTrue(report["no_claim_of_external_identity_or_custody"])

    def test_machine_readable_export_preserves_all_gates(self):
        parsed = json.loads(registry.render_lab_status_json())
        self.assertEqual(parsed["schema"], registry.SCHEMA)
        self.assertEqual(len(parsed["p0"]), 6)
        self.assertEqual(parsed["blocked_count_computed"], 6)
        self.assertEqual(parsed["decision"], "HARD_NO_GO")
        self.assertFalse(parsed["ready_for_real_worker"])


class A298FailClosedMutationTests(unittest.TestCase):
    def test_removing_one_p0_fails_inventory(self):
        with mock.patch.object(
            registry, "P0_REGISTRY", registry.P0_REGISTRY[:-1]
        ):
            audit = registry.audit_six_p0_registry()
        self.assertFalse(audit["valid_lab_inventory"])
        self.assertIn(
            "CANONICAL_SIX_P0_ORDER_OR_COUNT_CHANGED", audit["issues"]
        )

    def test_accidentally_marking_p0_homologated_is_rejected(self):
        bogus = (
            replace(registry.P0_REGISTRY[0], homologated=True),
            *registry.P0_REGISTRY[1:],
        )
        with mock.patch.object(registry, "P0_REGISTRY", bogus):
            audit = registry.audit_six_p0_registry()
        self.assertFalse(audit["valid_lab_inventory"])
        self.assertIn("UNAUTHORIZED_P0_HOMOLOGATION", audit["issues"])
        self.assertEqual(audit["decision"], "HARD_NO_GO")
        self.assertFalse(audit["ready_for_real_worker"])

    def test_missing_acceptance_or_bad_pr_reference_is_rejected(self):
        broken = replace(
            registry.P0_REGISTRY[2], acceptance="", evidence_prs=(1464, 1464)
        )
        candidates = (
            *registry.P0_REGISTRY[:2], broken,
            *registry.P0_REGISTRY[3:],
        )
        with mock.patch.object(registry, "P0_REGISTRY", candidates):
            audit = registry.audit_six_p0_registry()
        self.assertFalse(audit["valid_lab_inventory"])
        self.assertIn(
            "P0_MISSING_ACCEPTANCE_OR_BLOCKER:P0-3", audit["issues"]
        )
        self.assertIn(
            "P0_DUPLICATE_EVIDENCE_REFERENCE:P0-3", audit["issues"]
        )

    def test_evidence_descriptions_never_grant_provider_send(self):
        for item in registry.P0_REGISTRY:
            self.assertFalse(item.homologated)
            self.assertTrue(all(n > 0 for n in item.evidence_prs))
        audit = registry.audit_six_p0_registry()
        self.assertEqual(audit["homologated_count_computed"], 0)
        self.assertFalse(audit["ready_for_real_worker"])


if __name__ == "__main__":
    unittest.main()
