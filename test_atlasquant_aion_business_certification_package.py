import ast
import unittest
from pathlib import Path

from atlasquant_aion_business_certification_package import (
    ATTESTATION_SCHEMA,
    HUMAN_REVIEW_SCHEMA,
    BUSINESS_REQUIRED_GATES,
    EVIDENCE_ID,
    PROVENANCE,
    SUITE,
    assess_business_certification_package,
    build_business_specialist_evidence,
    business_package_readiness,
    business_primary_scope,
    business_technical_probe,
    normalize_ci_attestation,
)


SHA = "86df2db8a8140a8ee740196c9b5ac3ed73b52be8"
REFS = [
    "docs/aion/AION_BUSINESS_CERTIFICATION_PACKAGE_V1.md",
    "docs/aion/AION_SPECIALIST_CERTIFICATION_V1.md",
    "docs/aion/ARCHITECTURE.md",
]


def _product_evidence(**updates):
    data = {name: True for name in BUSINESS_REQUIRED_GATES}
    data["evidence_refs"] = list(REFS)
    data.update(updates)
    return data


def _attestation(fingerprint, **updates):
    data = {
        "schema": ATTESTATION_SCHEMA,
        "state": "VERIFIED",
        "tests_passed": True,
        "evidence_verified": True,
        "provenance_verified": True,
        "specialist": "BUSINESS",
        "version": "1",
        "suite": SUITE,
        "provenance": PROVENANCE,
        "evidence_id": EVIDENCE_ID,
        "sha": SHA,
        "refs": list(REFS),
        "fingerprint": fingerprint,
        "test_count": 1,
    }
    data.update(updates)
    return data


def _trusted_ci_verifier(accept=True):
    def verify(record):
        if not accept:
            return {
                "state": "REJECTED",
                "provenance_verified": False,
                "evidence_verified": False,
            }
        return {
            "state": "VERIFIED",
            "provenance_verified": True,
            "evidence_verified": True,
            "specialist": record.get("specialist"),
            "version": record.get("version"),
            "suite": record.get("suite"),
            "evidence_id": record.get("evidence_id"),
            "sha": record.get("sha"),
            "bound_refs": list(record.get("refs") or []),
            "fingerprint": record.get("fingerprint"),
        }
    return verify


def _review_record(fingerprint, **updates):
    data = {
        "schema": HUMAN_REVIEW_SCHEMA,
        "state": "APPROVED",
        "specialist": "BUSINESS",
        "version": "1",
        "evidence_id": EVIDENCE_ID,
        "approval_scope": "CERTIFICATION_ONLY",
        "reviewer": "human-reviewer-1",
        "reviewed_at": "2026-09-30T09:35:00Z",
        "reviewed_sha": SHA,
        "evidence_fingerprint": fingerprint,
        "runtime_activation_approved": False,
    }
    data.update(updates)
    return data


def _trusted_review_verifier(accept=True):
    def verify(review):
        if not accept:
            return {"state": "REJECTED", "review_verified": False}
        return {
            "state": "VERIFIED",
            "review_verified": True,
            "specialist": review.get("specialist"),
            "version": review.get("version"),
            "evidence_id": review.get("evidence_id"),
            "approval_scope": review.get("approval_scope"),
            "reviewer": review.get("reviewer"),
            "reviewed_sha": review.get("reviewed_sha"),
            "evidence_fingerprint": review.get("evidence_fingerprint"),
            "runtime_activation_approved": False,
        }
    return verify


class BusinessCertificationPackageTests(unittest.TestCase):
    def test_primary_scope_has_five_engines_and_excludes_legacy_marketplace_focus(self):
        scope = business_primary_scope()
        self.assertEqual(len(scope["engines"]), 5)
        self.assertEqual(scope["starter_bundle"]["delivery_model"], "MANAGED_HYBRID")
        self.assertEqual(scope["commercial_model"], "PACOTE_FECHADO_COM_IMPLANTACAO_E_RECORRENCIA")
        self.assertFalse(scope["legacy_marketplace_is_primary_scope"])
        self.assertIn("marketplace_shopee", scope["excluded_primary_legacy"])
        self.assertIn("marketplace_mercado_livre", scope["excluded_primary_legacy"])
        self.assertFalse(scope["promises_revenue"])
        self.assertFalse(scope["executes_action"])

    def test_technical_probe_passes_required_fail_closed_dimensions(self):
        probe = business_technical_probe()
        self.assertTrue(probe["routing"]["correct_specialist_selected"])
        self.assertTrue(probe["routing"]["ambiguous_not_silently_selected"])
        self.assertTrue(probe["isolation"]["memory_separated"])
        self.assertTrue(probe["isolation"]["evidence_separated"])
        self.assertFalse(probe["isolation"]["automatic_cross_domain_access"])
        self.assertFalse(probe["permissions"]["scope_escalated"])
        self.assertFalse(probe["permissions"]["role_escalated"])
        self.assertFalse(probe["permissions"]["undeclared_tool"])
        self.assertFalse(probe["truth"]["unknown_promoted"])
        self.assertFalse(probe["truth"]["stale_promoted"])
        self.assertFalse(probe["truth"]["conflict_resolved_silently"])
        self.assertFalse(probe["truth"]["incomplete_promoted"])
        self.assertFalse(probe["safety"]["real_trading_enabled"])
        self.assertFalse(probe["safety"]["payment_executed"])
        self.assertFalse(probe["safety"]["publication_executed"])
        self.assertFalse(probe["safety"]["deploy_executed"])
        self.assertFalse(probe["safety"]["external_side_effects"])
        self.assertFalse(probe["provider_called"])
        self.assertFalse(probe["external_write"])
        self.assertFalse(probe["runtime_activated"])

    def test_product_readiness_fails_closed_on_any_missing_or_lookalike_boolean(self):
        ready = business_package_readiness(_product_evidence())
        self.assertTrue(ready["ready_for_certification_review"])
        self.assertEqual(ready["certification_state"], "NOT_CERTIFIED")
        missing = business_package_readiness(_product_evidence(demo_sandbox_passed=False))
        self.assertFalse(missing["ready_for_certification_review"])
        lookalike = business_package_readiness(_product_evidence(admin_training_ready="true"))
        self.assertFalse(lookalike["ready_for_certification_review"])

    def test_attestation_must_be_structurally_verified(self):
        evidence = build_business_specialist_evidence(None)
        fp = evidence["tests"]["fingerprint"]
        good = normalize_ci_attestation(_attestation(fp))
        self.assertTrue(good["valid"])
        self.assertEqual(good["state"], "VERIFIED")
        for key, value in (
            ("tests_passed", "true"),
            ("evidence_verified", 1),
            ("provenance_verified", "yes"),
            ("sha", "not-a-sha"),
            ("suite", "other.py"),
            ("provenance", "self-declared"),
        ):
            with self.subTest(key=key):
                bad = normalize_ci_attestation(_attestation(fp, **{key: value}))
                self.assertFalse(bad["valid"])
                self.assertEqual(bad["state"], "REJECTED")

    def test_green_attestation_without_exact_fingerprint_does_not_become_tested(self):
        candidate = build_business_specialist_evidence(None)
        wrong = _attestation("0" * 64)
        result = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=wrong,
            human_review_approved=False,
        )
        self.assertEqual(result["state"], "READY_FOR_CERTIFICATION_REVIEW")
        self.assertEqual(result["technical_state"], "CANDIDATE")
        self.assertEqual(result["certification_state"], "NOT_CERTIFIED")
        self.assertFalse(result["runtime_activated"])

    def test_bound_ci_attestation_reaches_tested_without_certifying(self):
        seed = build_business_specialist_evidence({
            "schema": ATTESTATION_SCHEMA,
            "state": "VERIFIED",
            "tests_passed": True,
            "evidence_verified": True,
            "provenance_verified": True,
            "specialist": "BUSINESS",
            "version": "1",
            "suite": SUITE,
            "provenance": PROVENANCE,
            "evidence_id": EVIDENCE_ID,
            "sha": SHA,
            "refs": list(REFS),
            "fingerprint": "",
            "test_count": 1,
        })
        fp = seed["tests"]["fingerprint"]
        attestation = _attestation(fp)
        evidence = build_business_specialist_evidence(attestation)
        # fingerprint excludes the claimed fingerprint and provenance, so the
        # exact bound attestation remains stable.
        self.assertEqual(evidence["tests"]["fingerprint"], fp)
        self_declared = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=attestation,
            human_review_approved=False,
        )
        self.assertEqual(self_declared["state"], "READY_FOR_CERTIFICATION_REVIEW")
        self.assertEqual(self_declared["technical_state"], "CANDIDATE")
        self.assertFalse(self_declared["technical"]["evidence_verified"])

        result = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=attestation,
            human_review_approved=False,
            trusted_ci_verifier=_trusted_ci_verifier(),
        )
        self.assertEqual(result["state"], "TESTED")
        self.assertEqual(result["technical_state"], "TESTED")
        self.assertTrue(result["technical"]["tests_pass"])
        self.assertTrue(result["technical"]["evidence_verified"])
        self.assertFalse(result["human_review_approved"])
        self.assertEqual(result["certification_state"], "NOT_CERTIFIED")
        self.assertFalse(result["runtime_activated"])

    def test_exact_human_review_can_certify_but_never_activate_runtime(self):
        seed = build_business_specialist_evidence({
            "schema": ATTESTATION_SCHEMA,
            "state": "VERIFIED",
            "tests_passed": True,
            "evidence_verified": True,
            "provenance_verified": True,
            "specialist": "BUSINESS",
            "version": "1",
            "suite": SUITE,
            "provenance": PROVENANCE,
            "evidence_id": EVIDENCE_ID,
            "sha": SHA,
            "refs": list(REFS),
            "fingerprint": "",
            "test_count": 1,
        })
        attestation = _attestation(seed["tests"]["fingerprint"])
        unverified_review = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=attestation,
            human_review_approved=True,
            trusted_ci_verifier=_trusted_ci_verifier(),
        )
        self.assertEqual(unverified_review["state"], "TESTED")
        self.assertFalse(unverified_review["human_review_verified"])

        review = _review_record(attestation["fingerprint"])
        certified = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=attestation,
            human_review_approved=True,
            human_review_record=review,
            trusted_ci_verifier=_trusted_ci_verifier(),
            trusted_human_review_verifier=_trusted_review_verifier(),
        )
        self.assertEqual(certified["state"], "CERTIFIED")
        self.assertEqual(certified["certification_state"], "CERTIFIED")
        self.assertTrue(certified["human_review_verified"])
        self.assertFalse(certified["runtime_capability_available"])
        self.assertFalse(certified["runtime_activated"])
        self.assertFalse(certified["external_action_executed"])
        self.assertFalse(certified["payment_executed"])
        self.assertFalse(certified["publication_executed"])
        self.assertFalse(certified["deploy_executed"])
        self.assertFalse(certified["real_trading_enabled"])
        self.assertFalse(certified["authorizes_contract_signature"])
        self.assertFalse(certified["authorizes_external_contact"])
        self.assertFalse(certified["authorizes_spend"])
        self.assertFalse(certified["authorizes_merge"])
        self.assertFalse(certified["authorizes_deploy"])
        for lookalike in ("true", "approved", 1, None):
            with self.subTest(review=lookalike):
                result = assess_business_certification_package(
                    product_evidence=_product_evidence(),
                    ci_attestation=attestation,
                    human_review_approved=lookalike,
                    human_review_record=review,
                    trusted_ci_verifier=_trusted_ci_verifier(),
                    trusted_human_review_verifier=_trusted_review_verifier(),
                )
                self.assertNotEqual(result["state"], "CERTIFIED")
                self.assertFalse(result["human_review_approved"])

    def test_product_gap_blocks_published_certification_state(self):
        seed = build_business_specialist_evidence({
            "schema": ATTESTATION_SCHEMA,
            "state": "VERIFIED",
            "tests_passed": True,
            "evidence_verified": True,
            "provenance_verified": True,
            "specialist": "BUSINESS",
            "version": "1",
            "suite": SUITE,
            "provenance": PROVENANCE,
            "evidence_id": EVIDENCE_ID,
            "sha": SHA,
            "refs": list(REFS),
            "fingerprint": "",
            "test_count": 1,
        })
        attestation = _attestation(seed["tests"]["fingerprint"])
        result = assess_business_certification_package(
            product_evidence=_product_evidence(lgpd_privacy_defined=False),
            ci_attestation=attestation,
            human_review_approved=True,
            human_review_record=_review_record(attestation["fingerprint"]),
            trusted_ci_verifier=_trusted_ci_verifier(),
            trusted_human_review_verifier=_trusted_review_verifier(),
        )
        self.assertEqual(result["state"], "NOT_READY")
        self.assertFalse(result["product_ready"])
        self.assertEqual(result["certification_state"], "NOT_CERTIFIED")
        self.assertFalse(result["runtime_activated"])

    def test_human_review_is_bound_to_sha_fingerprint_and_certification_only_scope(self):
        seed = build_business_specialist_evidence(_attestation(""))
        attestation = _attestation(seed["tests"]["fingerprint"])
        cases = (
            _review_record(attestation["fingerprint"], reviewed_sha="fedcba9876543210"),
            _review_record("0" * 64),
            _review_record(attestation["fingerprint"], approval_scope="RUNTIME_AND_CERTIFICATION"),
            _review_record(attestation["fingerprint"], runtime_activation_approved=True),
            _review_record(attestation["fingerprint"], reviewer=""),
        )
        for review in cases:
            with self.subTest(review=review):
                result = assess_business_certification_package(
                    product_evidence=_product_evidence(),
                    ci_attestation=attestation,
                    human_review_approved=True,
                    human_review_record=review,
                    trusted_ci_verifier=_trusted_ci_verifier(),
                    trusted_human_review_verifier=_trusted_review_verifier(),
                )
                self.assertEqual(result["state"], "TESTED")
                self.assertFalse(result["human_review_verified"])
                self.assertEqual(result["certification_state"], "NOT_CERTIFIED")

        rejected = assess_business_certification_package(
            product_evidence=_product_evidence(),
            ci_attestation=attestation,
            human_review_approved=True,
            human_review_record=_review_record(attestation["fingerprint"]),
            trusted_ci_verifier=_trusted_ci_verifier(),
            trusted_human_review_verifier=_trusted_review_verifier(accept=False),
        )
        self.assertEqual(rejected["state"], "TESTED")
        self.assertFalse(rejected["human_review_verified"])

    def test_module_has_no_network_process_or_external_sdk_imports(self):
        source = Path("atlasquant_aion_business_certification_package.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
        for banned in ("requests", "urllib", "httpx", "socket", "subprocess", "openai"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
