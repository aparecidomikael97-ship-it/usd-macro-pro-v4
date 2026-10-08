"""AION DSSE/in-toto/SLSA v1 CI-only provenance adversarial tests.

The Ed25519 key and all artifact bytes are ephemeral, synthetic and inert.
DSSE signatures are REAL crypto; publisher/OIDC/witness trust is NOT real.
"""
import base64
import copy
from hashlib import sha256
import json
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import test_atlasquant_aion_ci_custody_rotation_external_provenance_gate_v1 as predecessor
from atlasquant_aion_ci_dsse_slsa_provenance_preflight_v1 import (
    SCHEMA, DSSE_PAYLOAD_TYPE, STATEMENT_TYPE, SLSA_PREDICATE_TYPE,
    READY, REVIEW_READY, BLOCKED, EXPECTED_FIELDS, DENIAL_FIELDS,
    CRYPTO_EVIDENCE_FIELDS, dsse_pae, verify_ci_dsse_slsa_subset,
    review_ci_attestation_trust_handoff, dsse_preflight_policy, _digest,
)

def D(char):
    return "sha256:" + char * 64

def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")

def b64(b):
    return base64.b64encode(b).decode("ascii")

class AIONCIDSSESLSAPreflightV1Tests(unittest.TestCase):
    def setUp(self):
        parent = predecessor.AIONCustodyRotationProvenanceV1Tests("runTest")
        parent.setUp()
        self.parent = parent
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.artifact = b"MZ" + b"AION_CI_INERT_ARTIFACT_NON_EXECUTABLE" * 8
        self.expected = self.make_expected()
        self.statement = self.make_statement()
        self.envelope = self.make_envelope()

    def make_expected(self):
        p = self.parent.provenance
        c = self.parent.custody
        b = self.parent.builder
        e = {
            "subject_name": "bin/aion-ci-inert-artifact.exe",
            "subject_sha256": sha256(self.artifact).hexdigest(),
            "source_commit": p["source_commit"],
            "repository": self.parent.statement["repository"],
            "workflow_ref": self.parent.statement["workflow_ref"],
            "issuer": self.parent.statement["issuer"],
            "audience": self.parent.statement["audience"],
            "builder_id": "ci-builder-atlasquant-001",
            "build_type": "https://ci-fixture.example.invalid/build/v1",
            "run_id": p["build_run_id"],
            "challenge_digest": D("e"),
            "anchor_digest": c["anchor_digest"],
            "registry_digest": c["registry_digest"],
            "custody_candidate_digest": c["candidate_digest"],
            "builder_proof_digest": b["builder_proof_digest"],
            "artifact_subject_digest": p["artifact_subject_digest"],
            "release_manifest_sha256": p["release_manifest_sha256"],
            "expected_signer_key_sha256": "sha256:" + sha256(self.public).hexdigest(),
            "external_policy_digest": D("d"),
        }
        self.assertEqual(set(e), EXPECTED_FIELDS)
        return e

    def make_statement(self):
        e = self.expected
        return {
            "_type": STATEMENT_TYPE,
            "subject": [{"name":e["subject_name"],
                         "digest":{"sha256":e["subject_sha256"]}}],
            "predicateType": SLSA_PREDICATE_TYPE,
            "predicate": {
                "buildDefinition": {
                    "buildType": e["build_type"],
                    "externalParameters": {
                        "sourceCommit":e["source_commit"],
                        "repository":e["repository"],
                        "workflowRef":e["workflow_ref"],
                        "issuer":e["issuer"],
                        "audience":e["audience"],
                        "challengeDigest":e["challenge_digest"],
                        "anchorDigest":e["anchor_digest"],
                        "registryDigest":e["registry_digest"],
                        "custodyCandidateDigest":e["custody_candidate_digest"],
                        "builderProofDigest":e["builder_proof_digest"],
                        "artifactSubjectDigest":e["artifact_subject_digest"],
                        "releaseManifestSha256":e["release_manifest_sha256"],
                    },
                },
                "runDetails": {
                    "builder":{"id":e["builder_id"]},
                    "metadata":{"invocationId":e["run_id"]},
                },
            },
        }

    def make_envelope(self, statement=None, private=None, payload=None):
        raw = canon(self.statement if statement is None else statement) if payload is None else payload
        key = self.private if private is None else private
        sig = key.sign(dsse_pae(DSSE_PAYLOAD_TYPE, raw))
        return {
            "payloadType": DSSE_PAYLOAD_TYPE,
            "payload": b64(raw),
            "signatures": [{
                "keyid": self.expected["expected_signer_key_sha256"],
                "sig": b64(sig),
            }],
        }

    def verify(self, envelope=None, key=None, expected=None, artifact=None):
        return verify_ci_dsse_slsa_subset(
            self.envelope if envelope is None else envelope,
            self.public if key is None else key,
            self.expected if expected is None else expected,
            self.artifact if artifact is None else artifact,
        )

    def review(self, candidate=None, custody=None, provenance=None,
               anchor=None, epoch=12, policy=None):
        return review_ci_attestation_trust_handoff(
            self.verify() if candidate is None else candidate,
            self.parent.custody if custody is None else custody,
            self.parent.provenance if provenance is None else provenance,
            expected_issuer_policy_digest=D("d") if policy is None else policy,
            expected_external_anchor_digest=self.parent.custody["anchor_digest"] if anchor is None else anchor,
            expected_minimum_rotation_epoch=epoch,
        )

    def fail(self, result, reason=None):
        self.assertEqual(result["state"], BLOCKED, result)
        if reason:
            self.assertIn(reason, result["blockers"])

    def altered(self, operation):
        m = copy.deepcopy(self.statement)
        operation(m)
        return self.make_envelope(statement=m)

    def test_dsse_pae_reference_bytes_are_correct(self):
        self.assertEqual(dsse_pae("text/plain", b"hello"),
                         b"DSSEv1 10 text/plain 5 hello")
        self.assertEqual(dsse_pae("a", b"0"), b"DSSEv1 1 a 1 0")

    def test_valid_crypto_only_remains_untrusted(self):
        r=self.verify()
        self.assertEqual(r["state"], READY, r)
        self.assertTrue(r["dsse_pae_signature_verified_under_supplied_ci_key"])
        self.assertTrue(r["synthetic_fixture_only"])
        self.assertEqual(r["subject_sha256"], sha256(self.artifact).hexdigest())
        for key in DENIAL_FIELDS:
            self.assertIs(r[key], False, key)

    def test_crossproof_review_uses_prior_custody_and_builder(self):
        r=self.review()
        self.assertEqual(r["state"], REVIEW_READY, r)
        self.assertTrue(r["ci_dsse_crypto_check_passed_untrusted"])
        for key,val in r.items():
            if type(val) is bool and key != "ci_dsse_crypto_check_passed_untrusted":
                self.assertFalse(val,key)

    def test_invalid_pae_signature_foreign_key_rejected(self):
        env=self.make_envelope(private=Ed25519PrivateKey.generate())
        self.fail(self.verify(envelope=env), "DSSE_ED25519_SIGNATURE_INVALID")

    def test_signature_replayed_for_wrong_payload_type_rejected(self):
        env=copy.deepcopy(self.envelope)
        env["payloadType"]="application/json"
        self.fail(self.verify(envelope=env), "DSSE_PAYLOAD_TYPE_NOT_ALLOWED")

    def test_signature_malformed_or_short_rejected(self):
        env=copy.deepcopy(self.envelope)
        env["signatures"][0]["sig"]=b64(b"x"*63)
        self.fail(self.verify(envelope=env), "DSSE_PAYLOAD_OR_SIGNATURE_LENGTH_INVALID")

    def test_wrong_public_key_rejected(self):
        other=Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fail(self.verify(key=other), "EXTERNAL_SIGNER_KEY_PIN_MISMATCH")

    def test_signer_keyid_is_not_authority(self):
        env=copy.deepcopy(self.envelope)
        env["signatures"][0]["keyid"]=D("f")
        self.fail(self.verify(envelope=env), "DSSE_UNTRUSTED_KEYID_MISMATCH")

    def test_duplicate_dsse_signatures_or_extra_keys_rejected(self):
        env=copy.deepcopy(self.envelope)
        env["signatures"].append(env["signatures"][0])
        self.fail(self.verify(envelope=env), "EXACTLY_ONE_DSSE_SIGNATURE_REQUIRED")
        env=copy.deepcopy(self.envelope)
        env["self_authorized"]=True
        self.fail(self.verify(envelope=env), "DSSE_EXACT_ENVELOPE_FIELDS_REQUIRED")

    def test_missing_dsse_signature_fails(self):
        env=copy.deepcopy(self.envelope)
        env["signatures"]=[]
        self.fail(self.verify(envelope=env), "EXACTLY_ONE_DSSE_SIGNATURE_REQUIRED")

    def test_extra_envelope_bytes_field_fails_closed_without_crash(self):
        env=copy.deepcopy(self.envelope)
        env["raw_certificate"]=b"not-json"
        self.fail(self.verify(envelope=env),
                  "DSSE_ENVELOPE_NONJSON_FIELDS_INVALID")

    def test_binary_invalid_expected_field_fails_closed_without_crash(self):
        e=dict(self.expected, artifact_subject_digest=b"not-json")
        self.fail(self.verify(expected=e),
                  "EXTERNAL_DIGEST_INVALID:artifact_subject_digest")

    def test_oversized_dsse_base64_payload_fails(self):
        env=copy.deepcopy(self.envelope)
        env["payload"]=b64(b"z"*32769)
        self.fail(self.verify(envelope=env),
                  "DSSE_PAYLOAD_OR_SIGNATURE_LENGTH_INVALID")

    def test_noncanonical_base64_fails(self):
        env=copy.deepcopy(self.envelope)
        env["payload"]="%%"
        self.fail(self.verify(envelope=env), "DSSE_BASE64_DECODE_FAILED")

    def test_noncanonical_json_fixture_fails(self):
        payload=json.dumps(self.statement, indent=2).encode("utf-8")
        self.fail(self.verify(envelope=self.make_envelope(payload=payload)),
                  "FIXTURE_NONCANONICAL_JSON_BYTES")

    def test_duplicate_json_keys_fails_even_with_signature(self):
        payload=canon(self.statement)
        bad=b'{"_type":"bad",' + payload[1:]
        self.fail(self.verify(envelope=self.make_envelope(payload=bad)),
                  "DSSE_PAYLOAD_JSON_INVALID")

    def test_empty_or_nonobject_dsse_payload_fails(self):
        self.fail(self.verify(envelope=self.make_envelope(payload=b"[]")),
                  "STATEMENT_EXACT_FIELDS_REQUIRED")

    def test_signed_predicate_replacement_blocked(self):
        self.fail(self.verify(envelope=self.altered(lambda m: m.update(
            predicateType="https://other.example.invalid/predicate"))),
            "SLSA_PROVENANCE_V1_PREDICATE_REQUIRED")

    def test_signed_statement_type_replacement_blocked(self):
        self.fail(self.verify(envelope=self.altered(lambda m: m.update(_type="spoof"))),
                  "IN_TOTO_STATEMENT_V1_REQUIRED")

    def test_signed_subject_name_switch_blocked(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["subject"][0].update(name="bin/other.exe"))),
            "SUBJECT_NAME_OR_SHAPE_INVALID")

    def test_signed_subject_hash_switch_blocked(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["subject"][0]["digest"].update(sha256="f"*64))),
            "SUBJECT_SHA256_MISMATCH")

    def test_signed_missing_subject_or_multiple_subjects_blocked(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m.update(subject=[]))), "ONE_CI_SUBJECT_REQUIRED")
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["subject"].append(m["subject"][0]))), "ONE_CI_SUBJECT_REQUIRED")

    def test_actual_artifact_byte_flip_rejected(self):
        art=bytearray(self.artifact)
        art[10]^=1
        self.fail(self.verify(artifact=bytes(art)), "ACTUAL_CI_SUBJECT_BYTES_MISMATCH")

    def test_extra_signed_statement_field_rejected(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m.update(owner_approved=True))), "STATEMENT_EXACT_FIELDS_REQUIRED")

    def test_extra_unsigned_build_metadata_rejected(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["predicate"]["runDetails"]["metadata"].update(
                issuer_trusted=True))), "BUILD_INVOCATION_ID_MISMATCH")

    def test_build_claim_wrong_git_commit_rejected(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["predicate"]["buildDefinition"]["externalParameters"].update(
                sourceCommit="b"*40))), "BUILD_INPUT_IDENTITY_MISMATCH:sourceCommit")

    def test_build_claim_wrong_repo_ref_or_issuer_rejected(self):
        for field in ("repository","workflowRef","issuer","audience"):
            with self.subTest(field=field):
                self.fail(self.verify(envelope=self.altered(
                    lambda m, f=field: m["predicate"]["buildDefinition"][
                        "externalParameters"].update({f:"ci-evil"}))),
                    "BUILD_INPUT_IDENTITY_MISMATCH:" + field)

    def test_signed_wrong_invocation_id_rejected(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["predicate"]["runDetails"]["metadata"].update(
                invocationId="9999"))), "BUILD_INVOCATION_ID_MISMATCH")

    def test_builder_id_and_build_type_replacement_rejected(self):
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["predicate"]["runDetails"]["builder"].update(id="bad"))),
            "BUILDER_ID_MISMATCH")
        self.fail(self.verify(envelope=self.altered(
            lambda m: m["predicate"]["buildDefinition"].update(buildType="bad"))),
            "BUILD_TYPE_MISMATCH")

    def test_signed_old_anchor_custody_builder_links_rejected(self):
        for field in ("anchorDigest","registryDigest","custodyCandidateDigest",
                      "builderProofDigest","artifactSubjectDigest","releaseManifestSha256",
                      "challengeDigest"):
            with self.subTest(field=field):
                self.fail(self.verify(envelope=self.altered(
                    lambda m,f=field: m["predicate"]["buildDefinition"][
                        "externalParameters"].update({f:D("f")}))),
                    "BUILD_INPUT_IDENTITY_MISMATCH:" + field)

    def test_wrong_expected_external_policy_or_source_rejected(self):
        e=dict(self.expected, external_policy_digest="")
        self.fail(self.verify(expected=e), "EXTERNAL_DIGEST_INVALID:external_policy_digest")
        e=dict(self.expected, source_commit="b"*40)
        self.fail(self.verify(expected=e), "BUILD_INPUT_IDENTITY_MISMATCH:sourceCommit")

    def test_missing_or_extra_expectation_fields_rejected(self):
        e=dict(self.expected)
        del e["subject_sha256"]
        self.fail(self.verify(expected=e), "EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")
        e=dict(self.expected, issuer_trusted=True)
        self.fail(self.verify(expected=e), "EXACT_EXTERNAL_EXPECTATIONS_REQUIRED")

    def test_review_forged_crypto_signature_claim_blocks(self):
        v=self.verify()
        v["dsse_pae_signature_verified_under_supplied_ci_key"]=False
        self.fail(self.review(candidate=v), "ONLY_SIGNED_CI_FIXTURE_ALLOWED")

    def test_review_rehashed_release_or_manifest_replacement_blocks(self):
        for field, code in (
            ("release_manifest_sha256","RELEASE_SUBJECT_AND_MANIFEST_CHAIN_MISMATCH"),
            ("artifact_subject_digest","RELEASE_SUBJECT_AND_MANIFEST_CHAIN_MISMATCH"),
            ("custody_candidate_digest","CUSTODY_CANDIDATE_BINDING_MISMATCH"),
            ("builder_proof_digest","BUILDER_CHAIN_MISMATCH"),
        ):
            with self.subTest(field=field):
                v=dict(self.verify(), **{field:D("f")})
                v["candidate_digest"]=_digest({
                    k:v.get(k) for k in CRYPTO_EVIDENCE_FIELDS})
                self.fail(self.review(candidate=v),code)

    def test_review_forged_trusted_oidc_field_blocks(self):
        v=self.verify()
        v["github_oidc_issuer_verified"]=True
        self.fail(self.review(candidate=v),
                  "ATTESTATION_TRUST_ESCALATION_DENIED:github_oidc_issuer_verified")

    def test_review_missing_denial_flag_or_new_field_blocks(self):
        v=self.verify()
        del v["owner_install_approved"]
        self.fail(self.review(candidate=v), "ATTESTATION_CANDIDATE_SHAPE_REQUIRED")
        v=dict(self.verify(), real_publisher_approved=True)
        self.fail(self.review(candidate=v), "ATTESTATION_CANDIDATE_SHAPE_REQUIRED")

    def test_review_tampered_custody_and_provenance_proofs_block(self):
        c=dict(self.parent.custody, registry_digest=D("f"))
        self.fail(self.review(custody=c), "CUSTODY_PROOF_DIGEST_INVALID")
        p=dict(self.parent.provenance, source_commit="b"*40)
        self.fail(self.review(provenance=p), "PROVENANCE_PROOF_DIGEST_INVALID")

    def test_review_epoch_replay_and_external_anchor_spoof_block(self):
        self.fail(self.review(epoch=13), "ROTATION_EPOCH_BELOW_EXPECTATION")
        self.fail(self.review(anchor=D("f")), "ANCHORED_RELEASE_CHAIN_MISMATCH")

    def test_policy_does_not_claim_real_builder_or_certificate(self):
        p=dsse_preflight_policy()
        self.assertTrue(p["ci_only"])
        self.assertTrue(p["dsse_pae_implemented"])
        for key in ("real_jwt_oidc_verified","certificate_chain_verified",
                    "real_attestor_authority_anchored","actual_slsa_level_certified",
                    "full_slsa_spec_conformance","external_attestation_fetched",
                    "real_aion_package_fetched","production_root_activated",
                    "install_authorized","deploy_executed","worker_activated"):
            self.assertIs(p[key],False,key)

if __name__ == "__main__":
    unittest.main()
