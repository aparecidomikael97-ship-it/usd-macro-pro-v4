"""A296 LAB: external-authority evidence contract is never self-homologating."""
import copy
import unittest

from labs.a296_external_authority_evidence_contract_lab import (
    CLAIM_FIELDS, OBLIGATIONS, PACK_FIELDS, SCHEMA,
    evaluate_evidence_contract, local_a295_self_claims_pack,
    probe_canonical_lab_counterexamples, synthetic_forged_complete_pack,
)


class A296ForgedPlausibleEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = synthetic_forged_complete_pack()
        cls.report = evaluate_evidence_contract(cls.pack)

    def test_complete_fake_pack_has_all_eight_syntactic_obligations(self):
        self.assertEqual(frozenset(self.pack), PACK_FIELDS)
        self.assertEqual(self.pack["schema"], SCHEMA)
        self.assertEqual(len(self.pack["claims"]), len(OBLIGATIONS))
        for claim in self.pack["claims"]:
            self.assertEqual(frozenset(claim), CLAIM_FIELDS)
        self.assertTrue(self.report["structurally_plausible"])
        self.assertEqual(self.report["syntactically_complete_count"], 8)
        self.assertEqual(self.report["present_obligations"], sorted(OBLIGATIONS))
        self.assertEqual(self.report["missing_obligations"], [])

    def test_fake_proof_bytes_never_count_as_crypto_verification(self):
        self.assertEqual(self.report["cryptographic_signatures_verified"], 0)
        self.assertEqual(self.report["authenticated_obligations"], 0)
        self.assertTrue(self.report["no_trusted_root_configured"])
        self.assertTrue(self.report["no_authenticated_external_custody"])

    def test_even_complete_fake_evidence_never_authorizes_effect(self):
        self.assertEqual(self.report["decision"], "HARD_NO_GO")
        self.assertFalse(self.report["can_authorize_real_effect"])
        self.assertFalse(self.report["can_activate_worker"])
        self.assertFalse(self.report["can_deploy"])
        self.assertEqual(self.report["p0_homologated"], 0)
        self.assertTrue(self.report["zero_auto_resend"])
        self.assertTrue(self.report["no_new_paid_services"])

    def test_policy_has_exact_eight_research_obligations(self):
        self.assertEqual(len(OBLIGATIONS), 8)
        self.assertEqual(len(set(OBLIGATIONS)), 8)
        for obligation in (
            "independent_owner_identity",
            "independent_custodian_identity",
            "cryptographic_intent_binding",
            "durable_off_host_epoch_and_nonce",
            "atomic_effect_and_ack_receipt",
            "authenticated_native_sqlite_vfs_fd",
            "host_resistant_antirollback_witness",
            "independent_uncertain_outcome_recovery",
        ):
            self.assertIn(obligation, OBLIGATIONS)


class A296FailClosedManifestMutationTests(unittest.TestCase):
    def setUp(self):
        self.pack = synthetic_forged_complete_pack()

    def _issues(self, pack):
        return evaluate_evidence_contract(pack)["issues"]

    def test_missing_obligation_detected(self):
        self.pack["claims"].pop()
        self.assertIn("MISSING_OBLIGATIONS", self._issues(self.pack))

    def test_duplicate_obligation_detected(self):
        self.pack["claims"][1]["obligation"] = (
            self.pack["claims"][0]["obligation"]
        )
        issues = self._issues(self.pack)
        self.assertIn("DUPLICATE_OBLIGATION", issues)
        self.assertIn("MISSING_OBLIGATIONS", issues)

    def test_same_host_self_attested_is_detected(self):
        report = evaluate_evidence_contract(local_a295_self_claims_pack())
        self.assertFalse(report["structurally_plausible"])
        self.assertTrue(any(
            "SAME_HOST_ISSUER_UNTRUSTED" in issue for issue in report["issues"]
        ))
        self.assertTrue(any(
            "SELF_VERIFICATION_UNTRUSTED" in issue for issue in report["issues"]
        ))
        self.assertFalse(report["can_authorize_real_effect"])

    def test_changed_subject_or_epoch_is_detected(self):
        for field, issue in (
            ("subject_digest", "SUBJECT_BINDING_MISMATCH"),
            ("epoch_digest", "EPOCH_BINDING_MISMATCH"),
        ):
            with self.subTest(field=field):
                p = copy.deepcopy(self.pack)
                p["claims"][0][field] = "e" * 64
                self.assertTrue(any(
                    issue in found for found in self._issues(p)
                ))

    def test_replayed_nonce_is_detected(self):
        self.pack["claims"][1]["nonce"] = self.pack["claims"][0]["nonce"]
        self.assertTrue(any(
            "NONCE_REPLAY" in issue for issue in self._issues(self.pack)
        ))

    def test_signature_bad_length_or_invalid_base64_detected(self):
        for value in ("@@", "", "YQ=="):
            with self.subTest(signature=value):
                p = copy.deepcopy(self.pack)
                p["claims"][0]["signature_base64"] = value
                self.assertTrue(any(
                    "SIGNATURE_SHAPE_INVALID" in issue for issue in self._issues(p)
                ))

    def test_expired_or_future_claim_detected(self):
        p = copy.deepcopy(self.pack)
        p["claims"][0]["expires_at"] = 1
        self.assertTrue(any(
            "EVIDENCE_TIME_INVALID" in issue for issue in self._issues(p)
        ))

    def test_unknown_claim_or_extra_field_denied(self):
        p = copy.deepcopy(self.pack)
        p["claims"][0]["obligation"] = "activate_worker"
        self.assertTrue(any(
            "UNKNOWN_OBLIGATION" in issue for issue in self._issues(p)
        ))
        p2 = copy.deepcopy(self.pack)
        p2["claims"][0]["self_homologated"] = True
        self.assertTrue(any(
            "CLAIM_FIELDS_INVALID" in issue for issue in self._issues(p2)
        ))

    def test_unknown_pack_fields_or_wrong_schema_denied(self):
        for mutation in (
            dict(self.pack, requested_worker_activation=True),
            dict(self.pack, schema="WRONG_SCHEMA"),
            {"claims": []},
            {"schema": SCHEMA, "subject_digest": "x",
             "epoch_digest": "y", "claims": 1},
        ):
            with self.subTest(mutation=str(list(mutation))):
                result = evaluate_evidence_contract(mutation)
                self.assertFalse(result["structurally_plausible"])
                self.assertFalse(result["can_authorize_real_effect"])
                self.assertEqual(result["decision"], "HARD_NO_GO")

    def test_nonhashable_or_wrong_type_domains_do_not_crash(self):
        p = copy.deepcopy(self.pack)
        p["claims"][0]["issuer_domain"] = {"untrusted": True}
        p["claims"][0]["verifier_domain"] = []
        report = evaluate_evidence_contract(p)
        self.assertFalse(report["structurally_plausible"])
        self.assertTrue(any(
            "ISSUER_DOMAIN_INVALID" in issue for issue in report["issues"]
        ))
        self.assertTrue(any(
            "VERIFIER_DOMAIN_INVALID" in issue for issue in report["issues"]
        ))

    def test_bounded_claim_list_and_invalid_now_denied(self):
        p = copy.deepcopy(self.pack)
        p["claims"] = p["claims"] * 9
        self.assertIn("PACK_CLAIMS_INVALID", self._issues(p))
        with self.assertRaises(ValueError):
            evaluate_evidence_contract(self.pack, now="now")

    def test_no_claims_cannot_be_construed_as_approval(self):
        p = copy.deepcopy(self.pack)
        p["claims"] = []
        result = evaluate_evidence_contract(p)
        self.assertIn("MISSING_OBLIGATIONS", result["issues"])
        self.assertEqual(result["authenticated_obligations"], 0)


class A296ObservedNegativeSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = probe_canonical_lab_counterexamples()

    def test_seven_real_lab_negative_scenarios_were_exercised(self):
        negatives = self.report["negative_findings"]
        self.assertEqual(len(negatives), 7)
        self.assertEqual(self.report["negative_findings_observed"], 7)
        self.assertTrue(all(negatives.values()), negatives)

    def test_real_negative_results_do_not_homologate_any_p0(self):
        self.assertTrue(self.report["synthetic_evidence_is_not_canonical_p0_proof"])
        self.assertEqual(self.report["authenticated_obligations"], 0)
        self.assertEqual(self.report["p0_homologated"], 0)
        self.assertFalse(self.report["can_authorize_real_effect"])
        self.assertTrue(self.report["hard_no_go"])


if __name__ == "__main__":
    unittest.main()
