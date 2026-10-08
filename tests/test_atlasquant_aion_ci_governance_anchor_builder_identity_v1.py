"""Adversarial CI-only governance-root and builder identity preflight V1.

Reuses #1066's already tested synthetic upstream fixture (module import only).
All signatures use independently generated ephemeral in-memory Ed25519 keys.
Never creates or promotes real owner/governance/build keys.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import test_atlasquant_aion_ci_publisher_registry_build_witness_v1 as upstream
from atlasquant_aion_ci_governance_anchor_builder_identity_v1 import (
    SCHEMA, ANCHOR_SCHEMA, BUILD_SCHEMA, SCOPE,
    ANCHOR_READY, BUILD_READY, REVIEW_READY, BLOCKED,
    ANCHOR_FIELDS, BUILD_FIELDS, _canonical, _digest, _bdigest,
    verify_ci_governance_anchor, verify_ci_builder_identity,
    review_ci_governance_builder_preflight, governance_builder_policy,
)

D = lambda c: "sha256:" + c * 64

def public(k):
    return k.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

class AIONCIGovernanceRootBuilderIdentityV1Tests(unittest.TestCase):
    def setUp(self):
        self.parent = upstream.AIONPublisherRegistryBuildWitnessV1Tests("runTest")
        self.parent.setUp()
        self.custodian_private = Ed25519PrivateKey.generate()
        self.builder_private = Ed25519PrivateKey.generate()
        self.custodian_public = public(self.custodian_private)
        self.builder_public = public(self.builder_private)
        self.g = self.parent.registry_proof
        self.w = self.parent.witness_proof
        self.r = self.parent.release
        self.anchor = self.make_anchor()
        self.anchor_proof = self.anchor_verify()
        self.builder = self.make_builder()
        self.builder_proof = self.builder_verify()

    def make_anchor(self):
        return {
            "schema": ANCHOR_SCHEMA, "scope": SCOPE,
            "anchor_id": "ci-anchor-atlasquant-001",
            "checkpoint_sequence": 7,
            "previous_anchor_digest": D("1"),
            "registry_digest": self.g["registry_digest"],
            "registry_sequence": self.g["sequence"],
            "governance_key_sha256": self.g["governance_key_sha256"],
            "publisher_key_sha256": self.g["active_key_sha256"],
            "custodian_review_key_sha256": _bdigest(self.custodian_public),
            "custodian_policy_digest": D("2"),
            "owner_review_challenge_digest": D("3"),
            "checkpoint_policy_digest": D("4"),
            "owner_identity_attested": False,
            "custodian_review_authoritative": False,
            "rollback_counter_durably_verified": False,
            "production_root_activated": False,
        }

    def anchor_verify(self, m=None, priv=None, pk=None, g=None, signature=None, **overrides):
        obj = self.anchor if m is None else m
        args = {
            "expected_anchor_id": self.anchor["anchor_id"],
            "expected_sequence": 7,
            "expected_previous_anchor_digest": D("1"),
            "expected_custodian_key_sha256": _bdigest(self.custodian_public),
            "expected_owner_review_challenge_digest": D("3"),
            "expected_custodian_policy_digest": D("2"),
            "expected_checkpoint_policy_digest": D("4"),
        }
        args.update(overrides)
        secret = self.custodian_private if priv is None else priv
        return verify_ci_governance_anchor(
            obj, self.custodian_public if pk is None else pk,
            secret.sign(_canonical(obj)) if signature is None else signature,
            self.g if g is None else g,
            **args,
        )

    def make_builder(self):
        a, g, w, r = self.anchor_proof, self.g, self.w, self.r
        return {
            "schema": BUILD_SCHEMA, "scope": SCOPE,
            "builder_id": "ci-builder-atlasquant-001",
            "builder_public_key_sha256": _bdigest(self.builder_public),
            "builder_identity_policy_digest": D("5"),
            "builder_workload_identity_digest": D("6"),
            "builder_workflow_digest": w["build_workflow_digest"],
            "builder_environment_digest": w["build_environment_digest"],
            "source_commit": r["source_commit"],
            "build_run_id": r["build_run_id"],
            "release_id": r["release_id"],
            "release_manifest_sha256": r["manifest_sha256"],
            "release_file_table_digest": r["file_table_digest"],
            "release_candidate_digest": r["candidate_evidence_digest"],
            "registry_digest": g["registry_digest"],
            "registry_sequence": g["sequence"],
            "witness_statement_digest": w["witness_statement_digest"],
            "witness_key_sha256": w["witness_key_sha256"],
            "governance_anchor_digest": a["anchor_digest"],
            "subject_digest": _digest({
                "release_manifest_sha256": r["manifest_sha256"],
                "release_file_table_digest": r["file_table_digest"],
                "release_candidate_digest": r["candidate_evidence_digest"],
            }),
            "builder_challenge_digest": D("7"),
            "slsa_predicate_type": "CI_SHAPE_ONLY_NOT_A_REAL_SLSA_ATTESTATION",
            "production_builder_identity_verified": False,
            "external_issuer_validated": False,
            "real_slsa_statement_verified": False,
            "build_reproducibility_attested": False,
        }

    def builder_verify(self, statement=None, pk=None, priv=None, sig=None,
                       a=None, g=None, w=None, r=None, **overrides):
        s = self.builder if statement is None else statement
        args = {
            "expected_builder_id": self.builder["builder_id"],
            "expected_builder_key_sha256": _bdigest(self.builder_public),
            "expected_builder_identity_policy_digest": D("5"),
            "expected_workload_identity_digest": D("6"),
            "expected_challenge_digest": D("7"),
        }
        args.update(overrides)
        key = self.builder_private if priv is None else priv
        return verify_ci_builder_identity(
            s, self.builder_public if pk is None else pk,
            key.sign(_canonical(s)) if sig is None else sig,
            self.anchor_proof if a is None else a,
            self.g if g is None else g,
            self.w if w is None else w,
            self.r if r is None else r,
            **args,
        )

    def review(self, a=None, b=None, g=None, w=None, r=None, **overrides):
        args = {
            "minimum_expected_checkpoint_sequence": 7,
            "external_anchor_digest": self.anchor_proof["anchor_digest"],
            "independent_identity_policy_digest": D("8"),
        }
        args.update(overrides)
        return review_ci_governance_builder_preflight(
            self.anchor_proof if a is None else a,
            self.builder_proof if b is None else b,
            self.g if g is None else g,
            self.w if w is None else w,
            self.r if r is None else r,
            **args,
        )

    def assert_blocked(self, result, blocker=None):
        self.assertEqual(result["state"], BLOCKED, result)
        if blocker:
            self.assertIn(blocker, result["blockers"])

    def test_ephemeral_roles_are_distinct_and_review_is_only_shape(self):
        self.assertEqual(len({
            self.custodian_public, self.builder_public,
            self.parent.gov_pub, self.parent.pub, self.parent.witness_pub,
        }), 5)
        self.assertEqual(self.anchor_proof["state"], ANCHOR_READY, self.anchor_proof)
        self.assertEqual(self.builder_proof["state"], BUILD_READY, self.builder_proof)
        self.assertEqual(self.review()["state"], REVIEW_READY)
        self.assertEqual(set(self.anchor), set(ANCHOR_FIELDS))
        self.assertEqual(set(self.builder), set(BUILD_FIELDS))

    def test_no_real_trust_even_when_all_ci_signatures_verify(self):
        for obj in (self.anchor_proof, self.builder_proof, self.review()):
            for key, value in obj.items():
                if isinstance(value, bool) and (key.endswith(("_trusted", "_attested", "_authorized", "_approved"))
                                                or key.startswith(("production_", "real_", "owner_", "slsa_"))):
                    self.assertFalse(value, key)
        self.assertFalse(self.review()["aion_installed"])

    def test_anchor_governance_root_matches_current_registry(self):
        self.assertEqual(self.anchor["governance_key_sha256"], self.g["governance_key_sha256"])
        self.assertEqual(self.anchor["publisher_key_sha256"], self.g["active_key_sha256"])

    def test_anchor_wrong_custodian_signature_rejected(self):
        self.assert_blocked(self.anchor_verify(priv=Ed25519PrivateKey.generate()),
                            "CUSTODIAN_DETACHED_SIGNATURE_INVALID")

    def test_anchor_old_signature_after_mutation_rejected(self):
        sig = self.custodian_private.sign(_canonical(self.anchor))
        changed = dict(self.anchor, checkpoint_sequence=8)
        self.assert_blocked(self.anchor_verify(m=changed, signature=sig, expected_sequence=8),
                            "CUSTODIAN_DETACHED_SIGNATURE_INVALID")

    def test_anchor_wrong_custodian_key_rejected(self):
        self.assert_blocked(self.anchor_verify(pk=public(Ed25519PrivateKey.generate())),
                            "CUSTODIAN_PUBLIC_KEY_MISMATCH")

    def test_anchor_governance_key_role_collision_rejected(self):
        a = dict(self.anchor, custodian_review_key_sha256=self.g["governance_key_sha256"])
        self.assert_blocked(self.anchor_verify(m=a),
                            "CUSTODIAN_GOVERNANCE_PUBLISHER_ROLES_COLLIDE")

    def test_anchor_publisher_key_role_collision_rejected(self):
        a = dict(self.anchor, custodian_review_key_sha256=self.g["active_key_sha256"])
        self.assert_blocked(self.anchor_verify(m=a),
                            "CUSTODIAN_GOVERNANCE_PUBLISHER_ROLES_COLLIDE")

    def test_anchor_external_sequence_rollback_rejected(self):
        self.assert_blocked(self.anchor_verify(expected_sequence=8),
                            "ANCHOR_BINDING_MISMATCH:checkpoint_sequence")

    def test_anchor_previous_digest_mismatch_rejected(self):
        self.assert_blocked(self.anchor_verify(expected_previous_anchor_digest=D("e")),
                            "ANCHOR_BINDING_MISMATCH:previous_anchor_digest")

    def test_anchor_owner_challenge_replay_rejected(self):
        self.assert_blocked(self.anchor_verify(expected_owner_review_challenge_digest=D("f")),
                            "ANCHOR_BINDING_MISMATCH:owner_review_challenge_digest")

    def test_anchor_wrong_custodian_policy_rejected(self):
        self.assert_blocked(self.anchor_verify(expected_custodian_policy_digest=D("f")),
                            "ANCHOR_BINDING_MISMATCH:custodian_policy_digest")

    def test_anchor_wrong_checkpoint_policy_rejected(self):
        self.assert_blocked(self.anchor_verify(expected_checkpoint_policy_digest=D("f")),
                            "ANCHOR_BINDING_MISMATCH:checkpoint_policy_digest")

    def test_anchor_invalid_checkpoint_type_rejected(self):
        self.assert_blocked(self.anchor_verify(m=dict(self.anchor, checkpoint_sequence=True)),
                            "CHECKPOINT_SEQUENCE_INVALID")

    def test_anchor_registry_digest_tamper_rejected(self):
        a = dict(self.anchor, registry_digest=D("f"))
        self.assert_blocked(self.anchor_verify(m=a),
                            "ANCHOR_BINDING_MISMATCH:registry_digest")

    def test_anchor_publisher_rotation_mismatch_rejected(self):
        a = dict(self.anchor, publisher_key_sha256=D("f"))
        self.assert_blocked(self.anchor_verify(m=a),
                            "ANCHOR_BINDING_MISMATCH:publisher_key_sha256")

    def test_anchor_invented_owner_approval_rejected(self):
        a = dict(self.anchor, owner_identity_attested=True)
        self.assert_blocked(self.anchor_verify(m=a),
                            "ANCHOR_SELF_TRUST_CLAIM_FORBIDDEN:owner_identity_attested")

    def test_anchor_forged_rollback_counter_rejected(self):
        a = dict(self.anchor, rollback_counter_durably_verified=True)
        self.assert_blocked(self.anchor_verify(m=a),
                            "ANCHOR_SELF_TRUST_CLAIM_FORBIDDEN:rollback_counter_durably_verified")

    def test_anchor_fake_root_activation_rejected(self):
        a = dict(self.anchor, production_root_activated=True)
        self.assert_blocked(self.anchor_verify(m=a),
                            "ANCHOR_SELF_TRUST_CLAIM_FORBIDDEN:production_root_activated")

    def test_anchor_extra_private_key_is_rejected(self):
        a = dict(self.anchor, custodian_private_key="LEAK")
        self.assert_blocked(self.anchor_verify(m=a), "ANCHOR_EXACT_FIELDS_REQUIRED")

    def test_anchor_missing_false_flag_rejected(self):
        a = dict(self.anchor)
        del a["owner_identity_attested"]
        self.assert_blocked(self.anchor_verify(m=a), "ANCHOR_EXACT_FIELDS_REQUIRED")

    def test_anchor_tampered_upstream_registry_proof_rejected(self):
        g = dict(self.g, active_key_sha256=D("f"))
        self.assert_blocked(self.anchor_verify(g=g), "UPSTREAM_REGISTRY_DIGEST_INVALID")

    def test_builder_cannot_be_governance_signer(self):
        b = dict(self.builder, builder_public_key_sha256=self.g["governance_key_sha256"])
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_CUSTODIAN_PUBLISHER_WITNESS_ROLE_COLLISION")

    def test_builder_cannot_be_release_signer(self):
        b = dict(self.builder, builder_public_key_sha256=self.g["active_key_sha256"])
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_CUSTODIAN_PUBLISHER_WITNESS_ROLE_COLLISION")

    def test_builder_cannot_be_witness_signer(self):
        b = dict(self.builder, builder_public_key_sha256=self.w["witness_key_sha256"])
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_CUSTODIAN_PUBLISHER_WITNESS_ROLE_COLLISION")

    def test_builder_wrong_signature_rejected(self):
        self.assert_blocked(self.builder_verify(priv=Ed25519PrivateKey.generate()),
                            "BUILDER_DETACHED_SIGNATURE_INVALID")

    def test_builder_wrong_key_rejected(self):
        self.assert_blocked(self.builder_verify(pk=public(Ed25519PrivateKey.generate())),
                            "BUILDER_PUBLIC_KEY_MISMATCH")

    def test_builder_old_signature_after_update_rejected(self):
        old = self.builder_private.sign(_canonical(self.builder))
        b = dict(self.builder, build_run_id="99999")
        self.assert_blocked(self.builder_verify(statement=b, sig=old),
                            "BUILDER_DETACHED_SIGNATURE_INVALID")

    def test_builder_wrong_claimed_github_run_rejected(self):
        b = dict(self.builder, build_run_id="99999")
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:build_run_id")

    def test_builder_wrong_source_commit_rejected(self):
        b = dict(self.builder, source_commit="b"*40)
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:source_commit")

    def test_builder_wrong_subject_bytes_rejected(self):
        b = dict(self.builder, subject_digest=D("f"))
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:subject_digest")

    def test_builder_wrong_manifest_hash_rejected(self):
        b = dict(self.builder, release_manifest_sha256=D("f"))
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:release_manifest_sha256")

    def test_builder_wrong_registry_sequence_rejected(self):
        b = dict(self.builder, registry_sequence=4)
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:registry_sequence")

    def test_builder_wrong_witness_statement_rejected(self):
        b = dict(self.builder, witness_statement_digest=D("f"))
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:witness_statement_digest")

    def test_builder_wrong_anchor_digest_rejected(self):
        b = dict(self.builder, governance_anchor_digest=D("f"))
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:governance_anchor_digest")

    def test_builder_witness_challenge_cannot_replay(self):
        self.assert_blocked(self.builder_verify(expected_challenge_digest=D("f")),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:builder_challenge_digest")

    def test_builder_workload_identity_policy_must_match(self):
        self.assert_blocked(self.builder_verify(expected_workload_identity_digest=D("f")),
                            "BUILDER_IDENTITY_SUBJECT_BINDING_MISMATCH:builder_workload_identity_digest")

    def test_builder_oidc_identity_claim_cannot_promote_trust(self):
        b = dict(self.builder, external_issuer_validated=True)
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_SELF_TRUST_CLAIM_FORBIDDEN:external_issuer_validated")

    def test_builder_real_slsa_claim_is_invalid(self):
        b = dict(self.builder, slsa_predicate_type="https://slsa.dev/provenance/v1")
        self.assert_blocked(self.builder_verify(statement=b),
                            "REAL_SLSA_PREDICATE_CLAIM_FORBIDDEN")

    def test_builder_fake_real_slsa_verified_flag_blocked(self):
        b = dict(self.builder, real_slsa_statement_verified=True)
        self.assert_blocked(self.builder_verify(statement=b),
                            "BUILDER_SELF_TRUST_CLAIM_FORBIDDEN:real_slsa_statement_verified")

    def test_builder_injected_real_install_authorization_rejected(self):
        b = dict(self.builder, authorized_aion_install=True)
        self.assert_blocked(self.builder_verify(statement=b), "BUILDER_EXACT_FIELDS_REQUIRED")

    def test_builder_deleted_false_flag_rejected(self):
        b = dict(self.builder)
        del b["production_builder_identity_verified"]
        self.assert_blocked(self.builder_verify(statement=b), "BUILDER_EXACT_FIELDS_REQUIRED")

    def test_builder_registry_tamper_rejected(self):
        g = dict(self.g, governance_key_sha256=D("f"))
        self.assert_blocked(self.builder_verify(g=g), "UPSTREAM_REGISTRY_DIGEST_INVALID")

    def test_builder_witness_tamper_rejected(self):
        w = dict(self.w, source_commit="b"*40)
        self.assert_blocked(self.builder_verify(w=w), "UPSTREAM_WITNESS_DIGEST_INVALID")

    def test_builder_release_tamper_rejected(self):
        r = dict(self.r, manifest_sha256=D("f"))
        self.assert_blocked(self.builder_verify(r=r), "UPSTREAM_RELEASE_DIGEST_INVALID")

    def test_builder_anchor_false_trust_rejected(self):
        a = dict(self.anchor_proof, real_owner_approval_verified=True)
        self.assert_blocked(self.builder_verify(a=a),
                            "ANCHOR_PROOF_FALSE_TRUST_REQUIRED:real_owner_approval_verified")

    def test_review_rejects_old_external_anchor(self):
        self.assert_blocked(self.review(external_anchor_digest=D("f")),
                            "EXTERNAL_ANCHOR_DIGEST_MISMATCH")

    def test_review_rejects_lower_checkpoint_than_external_minimum(self):
        self.assert_blocked(self.review(minimum_expected_checkpoint_sequence=8),
                            "ANCHOR_SEQUENCE_BELOW_EXTERNAL_MINIMUM")

    def test_review_rejects_missing_independent_policy(self):
        self.assert_blocked(self.review(independent_identity_policy_digest=""),
                            "INDEPENDENT_IDENTITY_POLICY_DIGEST_REQUIRED")

    def test_review_rejects_mutated_anchor_digest(self):
        a = dict(self.anchor_proof, registry_sequence=999)
        self.assert_blocked(self.review(a=a), "ANCHOR_PROOF_REHASH_FAILED")

    def test_review_rejects_mutated_builder_digest(self):
        b = dict(self.builder_proof, release_manifest_sha256=D("f"))
        self.assert_blocked(self.review(b=b), "BUILDER_PROOF_REHASH_FAILED")

    def test_review_rejects_forged_builder_trust_flag(self):
        b = dict(self.builder_proof, external_oidc_issuer_verified=True)
        self.assert_blocked(self.review(b=b),
                            "BUILDER_TRUST_ESCALATION_FORBIDDEN:external_oidc_issuer_verified")

    def test_review_rejects_extra_governance_field(self):
        a = dict(self.anchor_proof, owner_approved_in_chat=True)
        self.assert_blocked(self.review(a=a), "ANCHOR_PROOF_EXACT_FIELDS_REQUIRED")

    def test_review_rejects_missing_governance_denial(self):
        a = dict(self.anchor_proof)
        del a["owner_authorization_consumed"]
        self.assert_blocked(self.review(a=a), "ANCHOR_PROOF_EXACT_FIELDS_REQUIRED")

    def test_review_rejects_release_trust_escalation(self):
        r = dict(self.r, signed_by_authorized_aion_publisher=True)
        self.assert_blocked(self.review(r=r),
                            "UPSTREAM_RELEASE_TRUST_ESCALATION:signed_by_authorized_aion_publisher")

    def test_review_rejects_witness_registry_cross_conflict(self):
        w = dict(self.w, registry_digest=D("f"))
        self.assert_blocked(self.review(w=w), "UPSTREAM_WITNESS_DIGEST_INVALID")

    def test_policy_never_promotes_publisher_or_builder_to_production(self):
        p = governance_builder_policy()
        self.assertTrue(p["test_only"])
        self.assertTrue(p["ephemeral_ci_keys_only"])
        for k, v in p.items():
            if k not in ("schema", "test_only", "ephemeral_ci_keys_only"):
                self.assertIs(v, False, k)

if __name__ == "__main__":
    unittest.main()
