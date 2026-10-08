"""Synthetic Ed25519 registry + build witness adversarial tests.

All three signing keys generated independently in memory. No real AION
signing key, certificate, build witness, release, owner device or installer.
"""
import copy
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_windows_signed_release_provenance_ci_fixture_v1 import (
    SCHEMA as RELEASE_SCHEMA, SCOPE as RELEASE_SCOPE, KEY_SOURCE,
    verify_ci_detached_release, _bytes_digest, _canonical_bytes, _digest,
)
from atlasquant_aion_ci_publisher_registry_build_witness_v1 import (
    SCHEMA, REGISTRY_SCHEMA, WITNESS_SCHEMA, SCOPE, REGISTRY_READY,
    WITNESS_READY, REVIEW_READY, BLOCKED,
    ENTRY_FIELDS, REGISTRY_FIELDS, WITNESS_FIELDS,
    verify_ci_publisher_registry, verify_ci_separate_build_witness,
    build_ci_publisher_and_build_review, publisher_build_policy,
    _canonical_bytes as canon,
)

def D(c):
    return "sha256:" + c * 64

def pub(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

class AIONPublisherRegistryBuildWitnessV1Tests(unittest.TestCase):
    def setUp(self):
        self.publisher = Ed25519PrivateKey.generate()
        self.governance = Ed25519PrivateKey.generate()
        self.witness = Ed25519PrivateKey.generate()
        self.pub = pub(self.publisher)
        self.gov_pub = pub(self.governance)
        self.witness_pub = pub(self.witness)
        self.release = self.release_candidate()
        self.registry = self.registry_snapshot()
        self.registry_proof = self.prove_registry()
        self.statement = self.witness_statement()
        self.witness_proof = self.prove_witness()

    def release_candidate(self):
        artifacts = {"bin/aion-ci-inert.exe": b"MZ" + b"CI_FIXTURE_ONLY" * 8}
        rows = [{"path": p, "size_bytes": len(x), "sha256": _bytes_digest(x)}
                for p, x in sorted(artifacts.items())]
        m = {
            "schema": RELEASE_SCHEMA, "scope": RELEASE_SCOPE,
            "release_id": "ci-aion-registry-0001", "version": "0.2.0-ci.5",
            "source_commit": "a" * 40,
            "build_workflow_digest": D("1"), "build_run_id": "778899",
            "build_environment_digest": D("2"),
            "ci_signer_public_key_sha256": _bytes_digest(self.pub),
            "publisher_policy_digest": D("3"), "release_challenge_digest": D("4"),
            "files": rows, "key_source": KEY_SOURCE,
            "publisher_identity_authorized": False,
            "build_provenance_independently_attested": False,
            "owner_install_authorization_present": False,
        }
        expected = {
            "release_id": m["release_id"], "version": m["version"],
            "source_commit": m["source_commit"],
            "build_workflow_digest": m["build_workflow_digest"],
            "build_run_id": m["build_run_id"],
            "build_environment_digest": m["build_environment_digest"],
            "publisher_policy_digest": m["publisher_policy_digest"],
            "release_challenge_digest": m["release_challenge_digest"],
            "ci_signer_public_key_sha256": m["ci_signer_public_key_sha256"],
            "file_table_digest": _digest(rows),
        }
        r = verify_ci_detached_release(
            m, artifacts, self.pub, self.publisher.sign(_canonical_bytes(m)),
            expected=expected,
        )
        self.assertEqual(r["state"], "CI_DETACHED_SIGNATURE_AND_MANIFEST_MATCH_UNTRUSTED", r)
        return r

    def registry_snapshot(self):
        m = {
            "schema": REGISTRY_SCHEMA, "scope": SCOPE,
            "registry_id": "ci-reg-atlasquant-0001", "sequence": 5,
            "previous_snapshot_digest": D("5"),
            "publisher_policy_digest": D("6"),
            "governance_key_sha256": _bytes_digest(self.gov_pub),
            "registry_challenge_digest": D("7"),
            "entries": [
                {
                    "key_id": "ci-key-alpha", "public_key_sha256": D("8"),
                    "status": "REVOKED", "activated_sequence": 1,
                    "revoked_sequence": 3, "rotation_parent_id": "",
                },
                {
                    "key_id": "ci-key-zeta", "public_key_sha256": _bytes_digest(self.pub),
                    "status": "ACTIVE", "activated_sequence": 4,
                    "revoked_sequence": 0, "rotation_parent_id": "ci-key-alpha",
                },
            ],
            "governance_authority_trusted": False,
            "production_key_imported": False,
            "owner_install_authorization_present": False,
        }
        self.assertEqual(set(m), set(REGISTRY_FIELDS))
        return m

    def prove_registry(self, snapshot=None, governance_private=None, governance_pub=None, **kw):
        m = self.registry if snapshot is None else snapshot
        priv = self.governance if governance_private is None else governance_private
        gp = self.gov_pub if governance_pub is None else governance_pub
        args = {
            "expected_registry_id": self.registry["registry_id"],
            "expected_sequence": self.registry["sequence"],
            "expected_previous_snapshot_digest": self.registry["previous_snapshot_digest"],
            "expected_policy_digest": self.registry["publisher_policy_digest"],
            "expected_challenge_digest": self.registry["registry_challenge_digest"],
            "expected_governance_key_sha256": _bytes_digest(self.gov_pub),
        }
        args.update(kw)
        return verify_ci_publisher_registry(
            m, gp, priv.sign(canon(m)), **args,
        )

    def witness_statement(self):
        r, g = self.release, self.registry_proof
        s = {
            "schema": WITNESS_SCHEMA, "scope": SCOPE,
            "witness_key_sha256": _bytes_digest(self.witness_pub),
            "registry_digest": g["registry_digest"],
            "registry_sequence": g["sequence"],
            "active_publisher_key_sha256": g["active_key_sha256"],
            "release_candidate_digest": r["candidate_evidence_digest"],
            "release_manifest_sha256": r["manifest_sha256"],
            "release_file_table_digest": r["file_table_digest"],
            "release_id": r["release_id"], "source_commit": r["source_commit"],
            "build_run_id": r["build_run_id"],
            "build_workflow_digest": D("1"),
            "build_environment_digest": D("2"),
            "release_challenge_digest": r["release_challenge_digest"],
            "witness_challenge_digest": D("9"),
            "build_independence_trusted": False,
            "slsa_attestation_trusted": False,
            "production_release_authorized": False,
        }
        self.assertEqual(set(s), set(WITNESS_FIELDS))
        return s

    def prove_witness(self, statement=None, release=None, registry_proof=None,
                      witness_priv=None, witness_pub=None, **kw):
        s = self.statement if statement is None else statement
        args = {
            "expected_witness_key_sha256": _bytes_digest(self.witness_pub),
            "expected_build_workflow_digest": D("1"),
            "expected_build_environment_digest": D("2"),
            "expected_witness_challenge_digest": D("9"),
        }
        args.update(kw)
        k = self.witness if witness_priv is None else witness_priv
        return verify_ci_separate_build_witness(
            s, self.witness_pub if witness_pub is None else witness_pub,
            k.sign(canon(s)), self.release if release is None else release,
            self.registry_proof if registry_proof is None else registry_proof,
            **args,
        )

    def review(self, registry=None, witness=None, release=None, **kw):
        args = {
            "external_approval_policy_digest": D("a"),
            "external_provenance_policy_digest": D("b"),
            "expected_registry_sequence": 5,
        }
        args.update(kw)
        return build_ci_publisher_and_build_review(
            self.registry_proof if registry is None else registry,
            self.witness_proof if witness is None else witness,
            self.release if release is None else release, **args,
        )

    def assert_blocked(self, item, reason=None):
        self.assertEqual(item["state"], BLOCKED, item)
        if reason:
            self.assertIn(reason, item["blockers"])
        self.assertFalse(item.get("real_release_authorized", False))
        self.assertFalse(item.get("real_publisher_key_approved", False))

    def test_signatures_match_three_different_ephemeral_keys(self):
        self.assertNotEqual(self.gov_pub, self.pub)
        self.assertNotEqual(self.gov_pub, self.witness_pub)
        self.assertNotEqual(self.witness_pub, self.pub)
        self.assertEqual(self.registry_proof["state"], REGISTRY_READY)
        self.assertEqual(self.witness_proof["state"], WITNESS_READY)
        out = self.review()
        self.assertEqual(out["state"], REVIEW_READY, out)

    def test_positive_shapes_never_issue_real_trust(self):
        for flag in ("publisher_registry_root_trusted",
                     "registry_antirollback_authoritatively_persisted",
                     "real_publisher_key_approved",
                     "revocation_checked_against_real_authority"):
            self.assertFalse(self.registry_proof[flag])
        for flag in ("external_build_witness_identity_trusted",
                     "witness_identity_verified_independent",
                     "real_slsa_attestation_verified", "real_release_authorized"):
            self.assertFalse(self.witness_proof[flag])
        for key, val in self.review().items():
            if key.startswith(("real_", "production_", "owner_", "slsa_", "replay_", "hsm_", "package_")):
                if isinstance(val, bool):
                    self.assertFalse(val, key)

    def test_registry_wrong_governance_signature(self):
        bad = Ed25519PrivateKey.generate()
        self.assert_blocked(self.prove_registry(governance_private=bad),
                            "REGISTRY_GOVERNANCE_SIGNATURE_INVALID")

    def test_registry_wrong_governance_pub_key(self):
        bad = Ed25519PrivateKey.generate()
        self.assert_blocked(self.prove_registry(governance_pub=pub(bad)),
                            "GOVERNANCE_PUBLIC_KEY_MISMATCH")

    def test_registry_signature_old_after_mutation(self):
        old_sig = self.governance.sign(canon(self.registry))
        changed = copy.deepcopy(self.registry)
        changed["sequence"] = 6
        p = verify_ci_publisher_registry(
            changed, self.gov_pub, old_sig,
            expected_registry_id=changed["registry_id"],
            expected_sequence=6,
            expected_previous_snapshot_digest=changed["previous_snapshot_digest"],
            expected_policy_digest=changed["publisher_policy_digest"],
            expected_challenge_digest=changed["registry_challenge_digest"],
            expected_governance_key_sha256=_bytes_digest(self.gov_pub),
        )
        self.assert_blocked(p, "REGISTRY_GOVERNANCE_SIGNATURE_INVALID")

    def test_registry_sequence_rollback_blocked(self):
        self.assert_blocked(self.prove_registry(expected_sequence=6),
                            "EXTERNAL_REGISTRY_EXPECTATION_MISMATCH:sequence")

    def test_registry_parent_snapshot_rollback_blocked(self):
        self.assert_blocked(self.prove_registry(expected_previous_snapshot_digest=D("f")))

    def test_registry_governance_anchor_mismatch_blocked(self):
        self.assert_blocked(self.prove_registry(expected_governance_key_sha256=D("f")))

    def test_registry_challenge_replay_blocked(self):
        self.assert_blocked(self.prove_registry(expected_challenge_digest=D("f")))

    def test_registry_zero_sequence_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["sequence"] = 0
        self.assert_blocked(self.prove_registry(snapshot=snap), "MONOTONIC_SEQUENCE_REQUIRED")

    def test_registry_revoked_active_key_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["revoked_sequence"] = 5
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REVOKED_KEY_CANNOT_BE_ACTIVE")

    def test_registry_fully_revoked_no_active_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["status"] = "REVOKED"
        snap["entries"][1]["revoked_sequence"] = 5
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "EXACTLY_ONE_ACTIVE_SIGNER_REQUIRED")

    def test_registry_two_active_signers_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][0]["status"] = "ACTIVE"
        snap["entries"][0]["revoked_sequence"] = 0
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "EXACTLY_ONE_ACTIVE_SIGNER_REQUIRED")

    def test_registry_duplicate_key_material_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][0]["public_key_sha256"] = snap["entries"][1]["public_key_sha256"]
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_DUPLICATE_KEY_MATERIAL")

    def test_registry_duplicate_key_id_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["key_id"] = "ci-key-alpha"
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_KEY_IDS_ORDER_OR_DUPLICATION")

    def test_registry_unsorted_entries_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"].reverse()
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_KEY_IDS_ORDER_OR_DUPLICATION")

    def test_registry_missing_rotation_parent_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["rotation_parent_id"] = ""
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "ACTIVE_ROTATION_PARENT_REQUIRED")

    def test_registry_unknown_rotation_parent_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["rotation_parent_id"] = "ci-key-unknown"
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "ROTATION_PARENT_MUST_BE_PRESENT_NONACTIVE")

    def test_registry_revoked_before_activation_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][0]["revoked_sequence"] = 0
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REVOKED_KEY_REQUIRES_VALID_CUTOFF")

    def test_registry_future_activation_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["activated_sequence"] = 20
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_KEY_ACTIVATION_INVALID:1")

    def test_registry_injected_authorization_flag_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["owner_install_authorization_present"] = True
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "FALSE_TRUST_ASSERTION_FORBIDDEN:owner_install_authorization_present")

    def test_registry_extra_private_key_blocked(self):
        snap = copy.deepcopy(self.registry)
        snap["governance_private_key"] = "LEAK"
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_EXACT_FIELDS_REQUIRED")

    def test_registry_missing_denial_flag_blocked(self):
        snap = copy.deepcopy(self.registry)
        del snap["production_key_imported"]
        self.assert_blocked(self.prove_registry(snapshot=snap),
                            "REGISTRY_EXACT_FIELDS_REQUIRED")

    def test_registry_key_material_not_same_as_governance_root(self):
        snap = copy.deepcopy(self.registry)
        snap["entries"][1]["public_key_sha256"] = _bytes_digest(self.gov_pub)
        # Registry alone may carry such data; the witness step rejects role reuse.
        reg = self.prove_registry(snapshot=snap)
        self.assertEqual(reg["state"], REGISTRY_READY)
        self.assert_blocked(self.prove_witness(registry_proof=reg),
                            "PUBLISHER_ROOT_AND_WITNESS_KEY_ROLES_MUST_DIFFER")

    def test_witness_invalid_signature(self):
        bad = Ed25519PrivateKey.generate()
        self.assert_blocked(self.prove_witness(witness_priv=bad),
                            "DETACHED_WITNESS_SIGNATURE_INVALID")

    def test_witness_old_signature_after_manifest_modification(self):
        old_sig = self.witness.sign(canon(self.statement))
        statement = copy.deepcopy(self.statement)
        statement["source_commit"] = "b" * 40
        r = verify_ci_separate_build_witness(
            statement, self.witness_pub, old_sig, self.release, self.registry_proof,
            expected_witness_key_sha256=_bytes_digest(self.witness_pub),
            expected_build_workflow_digest=D("1"),
            expected_build_environment_digest=D("2"),
            expected_witness_challenge_digest=D("9"),
        )
        self.assert_blocked(r, "DETACHED_WITNESS_SIGNATURE_INVALID")

    def test_witness_wrong_github_commit_blocked(self):
        s = copy.deepcopy(self.statement)
        s["source_commit"] = "b" * 40
        self.assert_blocked(self.prove_witness(statement=s),
                            "WITNESS_RELEASE_OR_REGISTRY_BINDING_MISMATCH:source_commit")

    def test_witness_wrong_build_run_blocked(self):
        s = copy.deepcopy(self.statement)
        s["build_run_id"] = "99999"
        self.assert_blocked(self.prove_witness(statement=s),
                            "WITNESS_RELEASE_OR_REGISTRY_BINDING_MISMATCH:build_run_id")

    def test_witness_wrong_artifact_table_digest_blocked(self):
        s = copy.deepcopy(self.statement)
        s["release_file_table_digest"] = D("f")
        self.assert_blocked(self.prove_witness(statement=s),
                            "WITNESS_RELEASE_OR_REGISTRY_BINDING_MISMATCH:release_file_table_digest")

    def test_witness_wrong_manifest_digest_blocked(self):
        s = copy.deepcopy(self.statement)
        s["release_manifest_sha256"] = D("f")
        self.assert_blocked(self.prove_witness(statement=s))

    def test_witness_wrong_registry_digest_blocked(self):
        s = copy.deepcopy(self.statement)
        s["registry_digest"] = D("f")
        self.assert_blocked(self.prove_witness(statement=s))

    def test_witness_wrong_registry_sequence_blocked(self):
        s = copy.deepcopy(self.statement)
        s["registry_sequence"] = 4
        self.assert_blocked(self.prove_witness(statement=s))

    def test_witness_replay_challenge_blocked(self):
        self.assert_blocked(self.prove_witness(expected_witness_challenge_digest=D("e")))

    def test_witness_policy_builder_mismatch_blocked(self):
        self.assert_blocked(self.prove_witness(expected_build_workflow_digest=D("f")))

    def test_witness_environment_mismatch_blocked(self):
        self.assert_blocked(self.prove_witness(expected_build_environment_digest=D("f")))

    def test_witness_forged_independence_flag_blocked(self):
        s = copy.deepcopy(self.statement)
        s["build_independence_trusted"] = True
        self.assert_blocked(self.prove_witness(statement=s),
                            "WITNESS_TRUST_ESCALATION_FORBIDDEN:build_independence_trusted")

    def test_witness_forged_slsa_flag_blocked(self):
        s = copy.deepcopy(self.statement)
        s["slsa_attestation_trusted"] = True
        self.assert_blocked(self.prove_witness(statement=s),
                            "WITNESS_TRUST_ESCALATION_FORBIDDEN:slsa_attestation_trusted")

    def test_witness_unlisted_attestor_field_blocked(self):
        s = copy.deepcopy(self.statement)
        s["production_signer_approved"] = True
        self.assert_blocked(self.prove_witness(statement=s), "EXACT_WITNESS_FIELDS_REQUIRED")

    def test_witness_missing_false_denial_blocked(self):
        s = copy.deepcopy(self.statement)
        del s["production_release_authorized"]
        self.assert_blocked(self.prove_witness(statement=s), "EXACT_WITNESS_FIELDS_REQUIRED")

    def test_witness_public_key_mismatch_blocked(self):
        bad = Ed25519PrivateKey.generate()
        self.assert_blocked(self.prove_witness(witness_pub=pub(bad)),
                            "WITNESS_KEY_FINGERPRINT_MISMATCH")

    def test_witness_same_key_as_publisher_blocked(self):
        s = copy.deepcopy(self.statement)
        s["witness_key_sha256"] = _bytes_digest(self.pub)
        self.assert_blocked(self.prove_witness(statement=s, witness_pub=self.pub,
                            witness_priv=self.publisher,
                            expected_witness_key_sha256=_bytes_digest(self.pub)),
                            "PUBLISHER_ROOT_AND_WITNESS_KEY_ROLES_MUST_DIFFER")

    def test_witness_same_key_as_root_blocked(self):
        s = copy.deepcopy(self.statement)
        s["witness_key_sha256"] = _bytes_digest(self.gov_pub)
        self.assert_blocked(self.prove_witness(statement=s, witness_pub=self.gov_pub,
                            witness_priv=self.governance,
                            expected_witness_key_sha256=_bytes_digest(self.gov_pub)),
                            "PUBLISHER_ROOT_AND_WITNESS_KEY_ROLES_MUST_DIFFER")

    def test_witness_active_publisher_differs_release_blocked(self):
        s = copy.deepcopy(self.statement)
        s["active_publisher_key_sha256"] = D("c")
        self.assert_blocked(self.prove_witness(statement=s),
                            "ACTIVE_PUBLISHER_KEY_MUST_MATCH_RELEASE_SIGNER")

    def test_witness_tampered_release_candidate_blocked(self):
        release = dict(self.release)
        release["source_commit"] = "b" * 40
        self.assert_blocked(self.prove_witness(release=release),
                            "CI_RELEASE_CANDIDATE_DIGEST_INVALID")

    def test_witness_release_fake_authorization_blocked(self):
        release = dict(self.release)
        release["signed_by_authorized_aion_publisher"] = True
        self.assert_blocked(self.prove_witness(release=release))

    def test_witness_tampered_registry_proof_blocked(self):
        g = dict(self.registry_proof)
        g["active_key_sha256"] = D("f")
        self.assert_blocked(self.prove_witness(registry_proof=g),
                            "REGISTRY_PROOF_DIGEST_INVALID")

    def test_review_rejects_registry_rehash_divergence(self):
        g = dict(self.registry_proof)
        g["sequence"] = 4
        self.assert_blocked(self.review(registry=g), "REGISTRY_PROOF_REHASH_FAILED")

    def test_review_rejects_witness_rehash_divergence(self):
        w = dict(self.witness_proof)
        w["source_commit"] = "b" * 40
        self.assert_blocked(self.review(witness=w), "WITNESS_PROOF_REHASH_FAILED")

    def test_review_rejects_expected_registry_sequence_rollback(self):
        self.assert_blocked(self.review(expected_registry_sequence=4),
                            "EXTERNAL_REGISTRY_SEQUENCE_MISMATCH")

    def test_review_rejects_missing_owner_approval_policy(self):
        self.assert_blocked(self.review(external_approval_policy_digest=""),
                            "EXTERNAL_POLICY_REQUIRED:external_approval_policy_digest")

    def test_review_rejects_unapproved_attestation_claim(self):
        w = dict(self.witness_proof)
        w["real_slsa_attestation_verified"] = True
        self.assert_blocked(self.review(witness=w),
                            "PROOF_SELF_TRUST_PROMOTION_FORBIDDEN:real_slsa_attestation_verified")

    def test_review_rejects_failure_shaped_witness(self):
        w = dict(self.witness_proof)
        w["state"] = BLOCKED
        self.assert_blocked(self.review(witness=w), "WITNESS_PROOF_SHAPE_REQUIRED")

    def test_policy_never_promotes_ci_keys_into_production(self):
        p = publisher_build_policy()
        self.assertTrue(p["ci_only"])
        self.assertTrue(p["two_distinct_ci_signers"])
        for k in p:
            if k not in ("schema", "ci_only", "two_distinct_ci_signers"):
                self.assertFalse(p[k], k)

if __name__ == "__main__":
    unittest.main()
