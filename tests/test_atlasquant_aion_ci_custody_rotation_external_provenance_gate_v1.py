"""AION CI-only custody and provenance security regression tests.

All eight Ed25519 signers are ephemeral and in memory. No real root, OIDC
issuer, real AION package, installation, deployment or external effects.
"""
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import test_atlasquant_aion_ci_governance_anchor_builder_identity_v1 as upstream
from atlasquant_aion_ci_custody_rotation_external_provenance_gate_v1 import (
    CUSTODY_SCHEMA, PROVENANCE_SCHEMA, SCOPE, CUSTODY_READY,
    PROVENANCE_READY, REVIEW_READY, BLOCKED,
    CUSTODY_FIELDS, PROVENANCE_FIELDS, CUSTODY_EVIDENCE, PROVENANCE_EVIDENCE,
    verify_ci_custody_rotation, verify_ci_external_provenance_fixture,
    review_ci_custody_provenance, custody_provenance_policy,
    _canonical, _digest, _hash_bytes,
)

def D(c):
    return "sha256:" + c * 64

def pub(k):
    return k.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )

class AIONCustodyRotationProvenanceV1Tests(unittest.TestCase):
    def setUp(self):
        parent = upstream.AIONCIGovernanceRootBuilderIdentityV1Tests("runTest")
        parent.setUp()
        self.parent = parent
        self.anchor, self.builder = parent.anchor_proof, parent.builder_proof
        self.old, self.new, self.issuer = (
            Ed25519PrivateKey.generate() for _ in range(3)
        )
        self.old_pk, self.new_pk, self.issuer_pk = (
            pub(self.old), pub(self.new), pub(self.issuer)
        )
        self.ceremony = self.new_ceremony()
        self.statement = self.new_statement()
        self.custody = self.check_custody()
        self.provenance = self.check_provenance()

    def new_ceremony(self):
        oldfp = _hash_bytes(self.old_pk)
        return {
            "schema": CUSTODY_SCHEMA, "scope": SCOPE,
            "ceremony_id": "ci-aion-rotation-001",
            "anchor_digest": self.anchor["anchor_digest"],
            "registry_digest": self.anchor["registry_digest"],
            "checkpoint_sequence": self.anchor["checkpoint_sequence"],
            "previous_rotation_digest": D("1"),
            "previous_epoch": 11, "next_epoch": 12,
            "old_root_key_sha256": oldfp,
            "new_root_key_sha256": _hash_bytes(self.new_pk),
            "revoked_before": [D("2")],
            "revoked_after": sorted([D("2"), oldfp]),
            "custody_policy_digest": D("3"),
            "owner_challenge_digest": D("4"),
            "recovery_quorum_policy_digest": D("5"),
            "rotation_reason": "SCHEDULED_CI_ROTATION",
            "human_owner_approved": False, "external_custody_attested": False,
            "hsm_control_verified": False,
            "authoritative_antirollback_committed": False,
            "production_root_activated": False,
        }

    def new_statement(self):
        a, b = self.anchor, self.builder
        return {
            "schema": PROVENANCE_SCHEMA, "scope": SCOPE,
            "statement_id": "ci-aion-provenance-001",
            "builder_proof_digest": b["builder_proof_digest"],
            "anchor_digest": a["anchor_digest"],
            "registry_digest": a["registry_digest"],
            "release_manifest_sha256": b["release_manifest_sha256"],
            "release_candidate_digest": b["release_candidate_digest"],
            "artifact_subject_digest": b["subject_digest"],
            "source_commit": b["source_commit"],
            "build_run_id": b["build_run_id"],
            "build_workflow_digest": b["builder_workflow_digest"],
            "builder_workload_identity_digest": b["builder_workload_identity_digest"],
            "issuer": "ci-fixture-issuer.example.invalid",
            "audience": "ci-fixture-aion-build-verifier",
            "repository": "ci-fixture/example-repo",
            "workflow_ref": "ci-fixture/refs/heads/feature",
            "provenance_policy_digest": D("6"),
            "statement_challenge_digest": D("7"),
            "fixture_signer_key_sha256": _hash_bytes(self.issuer_pk),
            "predicate_type": "CI_PROVENANCE_FIXTURE_NOT_SLSA_OR_INTOTO",
            "issuer_token_verified": False,
            "workflow_identity_authoritative": False,
            "slsa_or_intoto_verified": False,
            "builder_is_independent": False,
            "artifact_from_verified_builder": False,
            "production_release_approved": False,
        }

    def check_custody(self, ceremony=None, **kw):
        m = self.ceremony if ceremony is None else ceremony
        args = {
            "expected_previous_epoch": 11,
            "expected_previous_rotation_digest": D("1"),
            "expected_challenge_digest": D("4"),
            "expected_policy_digest": D("3"),
            "expected_recovery_quorum_policy_digest": D("5"),
        }
        args.update(kw.pop("expect", {}))
        old_private = kw.pop("old_private", self.old)
        new_private = kw.pop("new_private", self.new)
        old_pub = kw.pop("old_public", self.old_pk)
        new_pub = kw.pop("new_public", self.new_pk)
        old_sig = kw.pop("old_sig", old_private.sign(_canonical(m)))
        new_sig = kw.pop("new_sig", new_private.sign(_canonical(m)))
        anchor = kw.pop("anchor", self.anchor)
        self.assertFalse(kw, kw)
        return verify_ci_custody_rotation(
            m, old_pub, new_pub, old_sig, new_sig, anchor, **args,
        )

    def check_provenance(self, statement=None, **kw):
        m = self.statement if statement is None else statement
        args = {
            "expected_issuer": "ci-fixture-issuer.example.invalid",
            "expected_audience": "ci-fixture-aion-build-verifier",
            "expected_repository": "ci-fixture/example-repo",
            "expected_workflow_ref": "ci-fixture/refs/heads/feature",
            "expected_provenance_policy_digest": D("6"),
            "expected_statement_challenge_digest": D("7"),
        }
        args.update(kw.pop("expect", {}))
        priv = kw.pop("private", self.issuer)
        pk = kw.pop("public", self.issuer_pk)
        signature = kw.pop("signature", priv.sign(_canonical(m)))
        anchor = kw.pop("anchor", self.anchor)
        builder = kw.pop("builder", self.builder)
        self.assertFalse(kw, kw)
        return verify_ci_external_provenance_fixture(
            m, pk, signature, anchor, builder, **args,
        )

    def check_review(self, custody=None, provenance=None, **kw):
        args = {
            "expected_anchor_digest": self.anchor["anchor_digest"],
            "minimum_expected_custody_epoch": 12,
            "external_issuer_policy_digest": D("8"),
            "independent_publisher_approval_policy_digest": D("9"),
        }
        args.update(kw.pop("expect", {}))
        anchor = kw.pop("anchor", self.anchor)
        builder = kw.pop("builder", self.builder)
        self.assertFalse(kw, kw)
        return review_ci_custody_provenance(
            self.custody if custody is None else custody,
            self.provenance if provenance is None else provenance,
            anchor, builder, **args,
        )

    def blocked(self, result, code=None):
        self.assertEqual(result["state"], BLOCKED, result)
        if code:
            self.assertIn(code, result["blockers"])

    def test_positive_synthetic_shapes_never_activate_anything(self):
        self.assertEqual(self.custody["state"], CUSTODY_READY, self.custody)
        self.assertEqual(self.provenance["state"], PROVENANCE_READY, self.provenance)
        self.assertEqual(self.check_review()["state"], REVIEW_READY)
        self.assertEqual(set(self.ceremony), set(CUSTODY_FIELDS))
        self.assertEqual(set(self.statement), set(PROVENANCE_FIELDS))
        for out in (self.custody, self.provenance, self.check_review()):
            for k, v in out.items():
                if type(v) is bool and k not in (
                    "two_ephemeral_signatures_valid", "one_ephemeral_signature_valid",
                    "synthetic_only", "all_inputs_synthetic_untrusted",
                ):
                    self.assertFalse(v, k)

    def test_all_eight_ci_signer_roles_differ(self):
        keys = {
            self.old_pk, self.new_pk, self.issuer_pk,
            self.parent.custodian_public, self.parent.builder_public,
            self.parent.parent.pub, self.parent.parent.gov_pub,
            self.parent.parent.witness_pub,
        }
        self.assertEqual(len(keys), 8)

    def test_both_rotation_signatures_mandatory(self):
        self.blocked(self.check_custody(old_private=Ed25519PrivateKey.generate()),
                     "OLD_ROOT_DETACHED_SIGNATURE_INVALID")
        self.blocked(self.check_custody(new_private=Ed25519PrivateKey.generate()),
                     "NEW_ROOT_DETACHED_SIGNATURE_INVALID")

    def test_rotation_signed_envelope_replay_blocked(self):
        old_sig = self.old.sign(_canonical(self.ceremony))
        m = dict(self.ceremony, ceremony_id="ci-aion-rotation-002")
        self.blocked(self.check_custody(m, old_sig=old_sig),
                     "OLD_ROOT_DETACHED_SIGNATURE_INVALID")

    def test_foreign_rotation_public_keys_blocked(self):
        self.blocked(self.check_custody(old_public=pub(Ed25519PrivateKey.generate())),
                     "OLD_ROOT_KEY_MISMATCH")
        self.blocked(self.check_custody(new_public=pub(Ed25519PrivateKey.generate())),
                     "NEW_ROOT_KEY_MISMATCH")

    def test_rotation_invalid_epoch_and_external_checkpoint(self):
        cases = [
            ("next_epoch", 14, "CUSTODY_EPOCH_MONOTONICITY_REQUIRED"),
            ("previous_epoch", True, "CUSTODY_EPOCH_MONOTONICITY_REQUIRED"),
            ("anchor_digest", D("f"), "CUSTODY_EXPECTATION_MISMATCH:anchor_digest"),
            ("registry_digest", D("f"), "CUSTODY_EXPECTATION_MISMATCH:registry_digest"),
            ("checkpoint_sequence", 2, "CUSTODY_EXPECTATION_MISMATCH:checkpoint_sequence"),
        ]
        for field, value, code in cases:
            with self.subTest(field=field):
                self.blocked(self.check_custody(dict(self.ceremony, **{field: value})), code)

    def test_external_expected_rotation_challenge_and_policies(self):
        cases = [
            ("expected_previous_epoch", 10, "CUSTODY_EXPECTATION_MISMATCH:previous_epoch"),
            ("expected_previous_rotation_digest", D("f"),
             "CUSTODY_EXPECTATION_MISMATCH:previous_rotation_digest"),
            ("expected_challenge_digest", D("f"),
             "CUSTODY_EXPECTATION_MISMATCH:owner_challenge_digest"),
            ("expected_policy_digest", D("f"),
             "CUSTODY_EXPECTATION_MISMATCH:custody_policy_digest"),
            ("expected_recovery_quorum_policy_digest", D("f"),
             "CUSTODY_EXPECTATION_MISMATCH:recovery_quorum_policy_digest"),
        ]
        for name, value, code in cases:
            with self.subTest(name=name):
                self.blocked(self.check_custody(expect={name: value}), code)

    def test_custody_old_new_role_collisions(self):
        m = dict(self.ceremony, new_root_key_sha256=_hash_bytes(self.old_pk))
        self.blocked(self.check_custody(
            m, new_public=self.old_pk, new_private=self.old),
            "CUSTODY_KEY_ROLES_MUST_BE_DISTINCT")
        for key in ("governance_key_sha256", "publisher_key_sha256",
                    "custodian_review_key_sha256"):
            with self.subTest(role=key):
                self.blocked(self.check_custody(
                    dict(self.ceremony, new_root_key_sha256=self.anchor[key])),
                    "CUSTODY_KEY_ROLES_MUST_BE_DISTINCT")

    def test_revocation_is_append_only_and_revokes_old(self):
        oldfp, newfp = _hash_bytes(self.old_pk), _hash_bytes(self.new_pk)
        cases = [
            ("revoked_before", [], "REVOCATION_MUST_BE_MONOTONIC_AND_RETIRE_OLD"),
            ("revoked_after", [D("2")], "REVOCATION_MUST_BE_MONOTONIC_AND_RETIRE_OLD"),
            ("revoked_after", [oldfp], "REVOCATION_MUST_BE_MONOTONIC_AND_RETIRE_OLD"),
            ("revoked_after", sorted([D("2"), oldfp, newfp]), "ROOT_REVOCATION_CONFLICT"),
            ("revoked_before", sorted([D("2"), oldfp]), "ROOT_REVOCATION_CONFLICT"),
            ("revoked_after", self.ceremony["revoked_after"] + [D("2")], "REVOCATION_SETS_INVALID"),
            ("revoked_after", list(reversed(self.ceremony["revoked_after"])), "REVOCATION_SETS_INVALID"),
        ]
        for field, value, code in cases:
            with self.subTest(field=field, value=value):
                self.blocked(self.check_custody(dict(self.ceremony, **{field:value})), code)

    def test_custody_false_claims_and_unknown_fields_fail(self):
        for field in (
            "human_owner_approved", "external_custody_attested",
            "hsm_control_verified", "authoritative_antirollback_committed",
            "production_root_activated",
        ):
            with self.subTest(field=field):
                self.blocked(self.check_custody(dict(self.ceremony, **{field:True})),
                             "CUSTODY_FALSE_TRUST_CLAIM:" + field)
        self.blocked(self.check_custody(dict(self.ceremony, secret_key="NEVER")),
                     "CUSTODY_EXACT_FIELDS_REQUIRED")
        m = dict(self.ceremony)
        del m["human_owner_approved"]
        self.blocked(self.check_custody(m), "CUSTODY_EXACT_FIELDS_REQUIRED")

    def test_unsafe_rotation_reason_fails(self):
        self.blocked(self.check_custody(
            dict(self.ceremony, rotation_reason="AUTO_APPROVED")),
            "EXPLICIT_ROTATION_REASON_REQUIRED")

    def test_anchor_predecessor_tamper_blocks_custody(self):
        self.blocked(self.check_custody(
            anchor=dict(self.anchor, registry_digest=D("f"))),
            "UPSTREAM_ANCHOR_REHASH_FAILED")

    def test_provenance_signature_mismatch_and_replay(self):
        self.blocked(self.check_provenance(private=Ed25519PrivateKey.generate()),
                     "PROVENANCE_FIXTURE_SIGNATURE_INVALID")
        self.blocked(self.check_provenance(public=pub(Ed25519PrivateKey.generate())),
                     "PROVENANCE_FIXTURE_PUBLIC_KEY_MISMATCH")
        old_sig = self.issuer.sign(_canonical(self.statement))
        new = dict(self.statement, statement_challenge_digest=D("f"))
        self.blocked(self.check_provenance(new, signature=old_sig),
                     "PROVENANCE_FIXTURE_SIGNATURE_INVALID")

    def test_provenance_external_issuer_audience_workflow_policy_pins(self):
        cases = [
            ("expected_issuer", "https://spoof.invalid", "issuer"),
            ("expected_audience", "not-aion", "audience"),
            ("expected_repository", "different/repo", "repository"),
            ("expected_workflow_ref", "main", "workflow_ref"),
            ("expected_provenance_policy_digest", D("f"), "provenance_policy_digest"),
            ("expected_statement_challenge_digest", D("f"), "statement_challenge_digest"),
        ]
        for name, value, field in cases:
            with self.subTest(name=name):
                self.blocked(self.check_provenance(expect={name:value}),
                             "PROVENANCE_BINDING_MISMATCH:" + field)

    def test_provenance_subject_commit_run_workflow_replacement_denied(self):
        cases = [
            ("source_commit", "b"*40),
            ("build_run_id", "999"),
            ("release_manifest_sha256", D("f")),
            ("release_candidate_digest", D("f")),
            ("artifact_subject_digest", D("f")),
            ("builder_workload_identity_digest", D("f")),
            ("build_workflow_digest", D("f")),
            ("registry_digest", D("f")),
            ("anchor_digest", D("f")),
        ]
        for name, value in cases:
            with self.subTest(field=name):
                self.blocked(self.check_provenance(dict(self.statement, **{name:value})),
                             "PROVENANCE_BINDING_MISMATCH:" + name)

    def test_false_slsa_oidc_independence_or_release_claims(self):
        for field in (
            "issuer_token_verified", "workflow_identity_authoritative",
            "slsa_or_intoto_verified", "builder_is_independent",
            "artifact_from_verified_builder", "production_release_approved",
        ):
            with self.subTest(field=field):
                self.blocked(self.check_provenance(dict(self.statement, **{field:True})),
                             "FALSE_EXTERNAL_ATTESTATION_CLAIM:" + field)
        self.blocked(self.check_provenance(dict(
            self.statement, predicate_type="https://slsa.dev/provenance/v1")),
            "REAL_SLSA_OR_INTOTO_PREDICATE_REFUSED")

    def test_extra_or_missing_provenance_fields_denied(self):
        self.blocked(self.check_provenance(dict(self.statement, github_token="NEVER")),
                     "PROVENANCE_EXACT_FIELDS_REQUIRED")
        m = dict(self.statement)
        del m["builder_is_independent"]
        self.blocked(self.check_provenance(m), "PROVENANCE_EXACT_FIELDS_REQUIRED")

    def test_provenance_cannot_reuse_builder_witness_or_custodian_key(self):
        for key in (
            self.builder["builder_public_key_sha256"],
            self.builder["witness_key_sha256"],
            self.anchor["custodian_review_key_sha256"],
        ):
            with self.subTest(key=key):
                self.blocked(self.check_provenance(
                    dict(self.statement, fixture_signer_key_sha256=key)),
                    "PROVENANCE_FIXTURE_SIGNER_ROLE_COLLISION")

    def test_provenance_upstream_builder_tamper_denied(self):
        self.blocked(self.check_provenance(
            builder=dict(self.builder, source_commit="b"*40)),
            "UPSTREAM_BUILDER_REHASH_FAILED")

    def test_review_rehashed_custody_chain_cannot_change_root(self):
        c = dict(self.custody, anchor_digest=D("f"))
        c["candidate_digest"] = _digest({k: c.get(k) for k in CUSTODY_EVIDENCE})
        self.blocked(self.check_review(custody=c), "EXTERNAL_ANCHOR_PIN_MISMATCH")

    def test_review_rehashed_provenance_chain_cannot_change_bytes(self):
        p = dict(self.provenance, artifact_subject_digest=D("f"))
        p["candidate_digest"] = _digest({k: p.get(k) for k in PROVENANCE_EVIDENCE})
        self.blocked(self.check_review(provenance=p), "RELEASE_BUILD_SUBJECT_MISMATCH")

    def test_review_extra_evidence_or_missing_trust_denial(self):
        self.blocked(self.check_review(
            provenance=dict(self.provenance, production_approval_claim=True)),
            "PROVENANCE_EXACT_READY_PROOF_REQUIRED")
        c = dict(self.custody)
        del c["real_owner_approval_verified"]
        self.blocked(self.check_review(custody=c),
                     "CUSTODY_EXACT_READY_PROOF_REQUIRED")

    def test_review_explicit_false_trust_flags_mandatory(self):
        for name in ("oidc_signature_and_claims_authoritative",
                     "slsa_or_intoto_statement_verified",
                     "production_release_approved"):
            with self.subTest(name=name):
                self.blocked(self.check_review(
                    provenance=dict(self.provenance, **{name:True})),
                    "PROVENANCE_FALSE_TRUST_REQUIRED:" + name)

    def test_review_rejects_rehashed_new_root_reusing_builder_key(self):
        c = dict(self.custody, new_root_key_sha256=self.builder["builder_public_key_sha256"])
        c["candidate_digest"] = _digest({k: c.get(k) for k in CUSTODY_EVIDENCE})
        self.blocked(self.check_review(custody=c), "EIGHT_CI_KEY_ROLES_MUST_BE_DISTINCT")

    def test_review_rejects_rehashed_old_root_reusing_witness_key(self):
        c = dict(self.custody, old_root_key_sha256=self.builder["witness_key_sha256"])
        c["candidate_digest"] = _digest({k: c.get(k) for k in CUSTODY_EVIDENCE})
        self.blocked(self.check_review(custody=c), "EIGHT_CI_KEY_ROLES_MUST_BE_DISTINCT")

    def test_review_rejects_rehashed_provenance_signer_reusing_root(self):
        p = dict(self.provenance, fixture_signer_key_sha256=self.custody["new_root_key_sha256"])
        p["candidate_digest"] = _digest({k: p.get(k) for k in PROVENANCE_EVIDENCE})
        self.blocked(self.check_review(provenance=p), "EIGHT_CI_KEY_ROLES_MUST_BE_DISTINCT")

    def test_review_minimum_external_epoch_and_policy_shapes(self):
        self.blocked(self.check_review(expect={"minimum_expected_custody_epoch":13}),
                     "CUSTODY_EPOCH_BELOW_EXPECTED_MINIMUM")
        self.blocked(self.check_review(expect={"expected_anchor_digest":D("f")}),
                     "EXTERNAL_ANCHOR_PIN_MISMATCH")
        for field in (
            "external_issuer_policy_digest",
            "independent_publisher_approval_policy_digest",
        ):
            with self.subTest(field=field):
                self.blocked(self.check_review(expect={field:""}),
                             "REQUIRED_UNTRUSTED_POLICY_DIGEST:" + field)

    def test_review_upstream_builder_tamper_denied(self):
        self.blocked(self.check_review(
            builder=dict(self.builder, registry_digest=D("f"))),
            "UPSTREAM_BUILDER_REHASH_FAILED")

    def test_no_real_key_or_issuer_activated(self):
        p = custody_provenance_policy()
        self.assertTrue(p["ci_only"])
        self.assertTrue(p["ephemeral_signing_keys_only"])
        for k, v in p.items():
            if k not in ("schema", "ci_only", "ephemeral_signing_keys_only"):
                self.assertIs(v, False, k)

if __name__ == "__main__":
    unittest.main()
