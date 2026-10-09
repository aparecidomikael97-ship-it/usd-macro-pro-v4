"""Adversarial pure structural dual-root crypto custody design checks.

No private keys, crypto signing, NCrypt native calls, owner Windows or
physical proof in this CI suite. Only untrusted synthetic metadata.
"""
from __future__ import annotations

import copy
import re
import unittest

import atlasquant_aion_windows_dual_root_custody_proof_plan_v1 as plan


def observation():
    return {
        "schema":"AION_CNG_SILENT_SIGNATURE_ALGORITHM_ENUM_CI_V1",
        "state":"SILENT_SIGNATURE_ALGORITHMS_LISTED_UNTRUSTED",
        "reason":"",
        "provider_name":"Microsoft Platform Crypto Provider",
        "requested_operation":"NCRYPT_SIGNATURE_OPERATION",
        "query_flags":"NCRYPT_SILENT_FLAG",
        "enumeration_failure_category":None,
        "target_algorithm_names":{"ECDSA_P256":"LISTED","ED25519":"NOT_LISTED"},
        "algorithm_name_count":5,
        "provider_handle_released":True,
        "result_buffer_released":True,
        "provider_ui_suppression_requested":True,
        "provider_open_status":{"status_hex":"0x00000000","classification":"ADVERTISED","reason":"SUCCESS"},
        "enumeration_status":{"status_hex":"0x00000000","classification":"ADVERTISED","reason":"SUCCESS"},
        "buffer_free_status":{"status_hex":"0x00000000","classification":"ADVERTISED","reason":"SUCCESS"},
        "provider_free_status":{"status_hex":"0x00000000","classification":"ADVERTISED","reason":"SUCCESS"},
        "diagnostic_correlation_receipt":{
            "schema":"AION_OWNER_CNG_READONLY_NON_AUTHORITY_CORRELATION_RECEIPT_V1",
            "receipt_signed":False,
            "independently_witnessed":False,
            "trusted_host_anchor_verified":False,
            "installer_authorized":False,
            "safe_to_resume":False,
        },
        **{k:False for k in plan._OBS_FALSE},
    }


def transcript():
    return {
        "nonce":"ab"*32,
        "owner_ed25519_public_key_sha256":"sha256:"+"1"*64,
        "host_p256_public_key_sha256":"sha256:"+"2"*64,
        "collector_binary_sha256":"sha256:"+"3"*64,
        "policy_sha256":"sha256:"+"4"*64,
        "generation":0,
    }


class DualRootReviewTests(unittest.TestCase):
    def assert_never_raises_trust(self, output):
        for key, expected in plan._NEVER_TRUSTED.items():
            self.assertIs(output[key], False, key)
        self.assertTrue(output["requires_explicit_separate_provisioning_approval"])
        self.assertTrue(output["requires_independent_hardware_key_attestation_design"])
        self.assertTrue(output["requires_independent_ed25519_custodian"])
        self.assertEqual(output["algorithm_roles"]["owner_identity"],
                         "ED25519_EXTERNAL_INDEPENDENT")
        self.assertEqual(output["algorithm_roles"]["host_binding"],
                         "ECDSA_P256_TPM_PROOF_PENDING")
        self.assertEqual(output["algorithm_roles"]["enterprise_ca_tpm_attestation"],
                         "RSA_ONLY_NOT_P256_PROOF")

    def test_correct_observation_only_proposes_never_authorizes(self):
        out=plan.review_owner_cng_observation_for_dual_root_plan(observation())
        self.assertEqual(out["state"],"CUSTODY_ARCHITECTURE_REVIEW_CANDIDATE_UNTRUSTED")
        self.assertEqual(out["proposed_architecture"],plan.PROPOSAL)
        self.assert_never_raises_trust(out)

    def test_no_tpm_key_generated_from_algorithm_advertisement(self):
        out=plan.review_owner_cng_observation_for_dual_root_plan(observation())
        self.assertFalse(out["p256_private_key_generated"])
        self.assertFalse(out["p256_tpm_origin_attested"])
        self.assertFalse(out["p256_private_key_nonexportable_verified"])
        self.assert_never_raises_trust(out)

    def test_ed25519_not_listed_does_not_replace_owner_algorithm(self):
        out=plan.review_owner_cng_observation_for_dual_root_plan(observation())
        self.assertEqual(out["algorithm_roles"]["owner_identity"],
                         "ED25519_EXTERNAL_INDEPENDENT")
        self.assertNotEqual(out["algorithm_roles"]["owner_identity"],
                            out["algorithm_roles"]["host_binding"])

    def test_enterprise_ca_rsa_attestation_cannot_claim_p256(self):
        out=plan.review_owner_cng_observation_for_dual_root_plan(observation())
        self.assertFalse(out["rsa_only_enterprise_ca_attests_p256"])
        self.assertFalse(out["tpm_ek_chain_verified"])

    def test_unsupported_metadata_rejected(self):
        for o in (None,False,True,[],{},1,"report"):
            with self.subTest(o=o):
                out=plan.review_owner_cng_observation_for_dual_root_plan(o)
                self.assertEqual(out["state"],"BLOCKED")
                self.assert_never_raises_trust(out)

    def test_wrong_source_or_untrusted_status_rejected(self):
        for field,value in (
            ("schema","WRONG_SCHEMA"),
            ("state","ATTESTED"),
            ("reason","ERROR"),
            ("provider_name","Microsoft Software Key Storage Provider"),
            ("requested_operation","NCryptEnumKeys"),
            ("query_flags","ZERO_FLAGS"),
            ("enumeration_failure_category","IGNORED"),
        ):
            with self.subTest(field=field):
                o=observation()
                o[field]=value
                out=plan.review_owner_cng_observation_for_dual_root_plan(o)
                self.assertEqual(out["state"],"BLOCKED")
                self.assert_never_raises_trust(out)

    def test_wrong_algorithm_support_claim_rejected(self):
        for value in (
            {"ECDSA_P256":"LISTED","ED25519":"LISTED"},
            {"ECDSA_P256":"NOT_LISTED","ED25519":"NOT_LISTED"},
            {"ECDSA_P256":"LISTED","ED25519":"NOT_QUERIED"},
            {"ECDSA_P256":"LISTED"},
            {"ECDSA_P256":"LISTED","ED25519":"NOT_LISTED","RSA":"LISTED"},
            [],
            None,
        ):
            with self.subTest(value=value):
                o=observation()
                o["target_algorithm_names"]=value
                out=plan.review_owner_cng_observation_for_dual_root_plan(o)
                self.assertEqual(out["state"],"BLOCKED")
                self.assert_never_raises_trust(out)

    def test_invalid_count_and_boolean_count_rejected(self):
        for value in (None,True,False,"5",0,-1,65,10000):
            with self.subTest(value=value):
                o=observation()
                o["algorithm_name_count"]=value
                self.assertEqual(
                    plan.review_owner_cng_observation_for_dual_root_plan(o)["state"],
                    "BLOCKED")

    def test_any_unreleased_buffer_or_handle_rejected(self):
        for field in ("provider_handle_released","result_buffer_released"):
            o=observation()
            o[field]=False
            out=plan.review_owner_cng_observation_for_dual_root_plan(o)
            self.assertEqual(out["state"],"BLOCKED")

    def test_non_success_native_status_rejected(self):
        for field in ("provider_open_status","enumeration_status",
                      "provider_free_status","buffer_free_status"):
            with self.subTest(field=field):
                o=observation()
                o[field]["status_hex"]="0x80090009"
                out=plan.review_owner_cng_observation_for_dual_root_plan(o)
                self.assertEqual(out["state"],"BLOCKED")

    def test_fake_claims_of_physical_proof_are_rejected(self):
        for field in plan._OBS_FALSE:
            with self.subTest(field=field):
                o=observation()
                o[field]=True
                out=plan.review_owner_cng_observation_for_dual_root_plan(o)
                self.assertEqual(out["state"],"BLOCKED")
                self.assert_never_raises_trust(out)

    def test_non_boolean_claims_are_rejected(self):
        for field in ("tpm_presence_verified","installer_authorized",
                      "physical_attestation_verified"):
            with self.subTest(field=field):
                o=observation()
                o[field]=0
                self.assertEqual(
                    plan.review_owner_cng_observation_for_dual_root_plan(o)["state"],
                    "BLOCKED")

    def test_illustrative_unsigned_receipt_cannot_authenticate(self):
        o=observation()
        out=plan.review_owner_cng_observation_for_dual_root_plan(o)
        self.assertEqual(out["state"],"CUSTODY_ARCHITECTURE_REVIEW_CANDIDATE_UNTRUSTED")
        self.assertFalse(out["human_owner_identity_attested"])
        self.assertFalse(out["nonce_uniqueness_durable_verified"])

    def test_forged_receipt_signing_or_anchor_claim_rejected(self):
        for field in ("receipt_signed","independently_witnessed",
                      "trusted_host_anchor_verified","installer_authorized",
                      "safe_to_resume"):
            o=observation()
            o["diagnostic_correlation_receipt"][field]=True
            out=plan.review_owner_cng_observation_for_dual_root_plan(o)
            self.assertEqual(out["state"],"BLOCKED")

    def test_missing_unsigned_receipt_rejected(self):
        for value in (None,False,{},{"receipt_signed":False}):
            o=observation()
            o["diagnostic_correlation_receipt"]=value
            self.assertEqual(
                plan.review_owner_cng_observation_for_dual_root_plan(o)["state"],
                "BLOCKED")

    def test_silent_flag_not_verified_as_no_ui_physical_proof(self):
        o=observation()
        o["provider_ui_suppression_requested"]=True
        out=plan.review_owner_cng_observation_for_dual_root_plan(o)
        self.assertFalse(out["physical_sandbox_12_of_12_verified"])
        self.assertFalse(out["host_security_state_modified"])


class DraftTranscriptTests(unittest.TestCase):
    def deny_signing(self,out):
        for flag in ("transcript_signed","owner_signature_verified",
                     "host_signature_verified","tpm_origin_verified",
                     "nonce_replay_protected","authorized_for_provisioning",
                     "safe_to_resume"):
            self.assertIs(out[flag],False,flag)

    def test_valid_draft_has_canonical_json_and_domain_separated_hash(self):
        out=plan.build_unsigned_dual_root_transcript_draft(transcript())
        self.assertEqual(out["state"],"UNSIGNED_DRAFT_TRANSCRIPT_UNTRUSTED")
        self.assertRegex(out["draft_sha256"],r"^sha256:[0-9a-f]{64}$")
        self.assertIn("ED25519",out["draft_canonical_json"].upper())
        self.deny_signing(out)

    def test_draft_is_deterministic(self):
        a=plan.build_unsigned_dual_root_transcript_draft(transcript())
        b=plan.build_unsigned_dual_root_transcript_draft(dict(reversed(list(transcript().items()))))
        self.assertEqual(a["draft_sha256"],b["draft_sha256"])
        self.deny_signing(a)

    def test_changing_nonce_changes_digest(self):
        a=plan.build_unsigned_dual_root_transcript_draft(transcript())
        t=transcript()
        t["nonce"]="ac"*32
        b=plan.build_unsigned_dual_root_transcript_draft(t)
        self.assertNotEqual(a["draft_sha256"],b["draft_sha256"])
        self.deny_signing(b)

    def test_changing_any_fingerprint_changes_digest(self):
        baseline=plan.build_unsigned_dual_root_transcript_draft(transcript())
        for field in (k for k in transcript() if k.endswith("_sha256")):
            t=transcript()
            t[field]="sha256:"+"f"*64
            with self.subTest(field=field):
                modified=plan.build_unsigned_dual_root_transcript_draft(t)
                self.assertNotEqual(baseline["draft_sha256"],modified["draft_sha256"])
                self.deny_signing(modified)

    def test_generation_change_changes_digest_not_antirollback(self):
        a=plan.build_unsigned_dual_root_transcript_draft(transcript())
        t=transcript()
        t["generation"]=1
        b=plan.build_unsigned_dual_root_transcript_draft(t)
        self.assertNotEqual(a["draft_sha256"],b["draft_sha256"])
        self.assertFalse(b["nonce_replay_protected"])

    def test_invalid_nonce_cannot_build(self):
        for value in (None,True,0,"a"*63,"g"*64,"A"*64,"ab"*33):
            t=transcript()
            t["nonce"]=value
            with self.subTest(value=value):
                out=plan.build_unsigned_dual_root_transcript_draft(t)
                self.assertEqual(out["state"],"BLOCKED")
                self.deny_signing(out)

    def test_bad_generation_cannot_build(self):
        for value in (True,False,None,"1",-1,2**32,2**64,1.2):
            t=transcript()
            t["generation"]=value
            with self.subTest(value=value):
                out=plan.build_unsigned_dual_root_transcript_draft(t)
                self.assertEqual(out["state"],"BLOCKED")
                self.deny_signing(out)

    def test_different_role_fingerprints_required(self):
        t=transcript()
        t["host_p256_public_key_sha256"]=t["owner_ed25519_public_key_sha256"]
        out=plan.build_unsigned_dual_root_transcript_draft(t)
        self.assertEqual(out["state"],"BLOCKED")

    def test_invalid_sha256_shapes_rejected(self):
        for field in (k for k in transcript() if k.endswith("_sha256")):
            for value in ("",None,True,"0"*64,"sha256:"+"X"*64,"sha256:"+"0"*63):
                t=transcript()
                t[field]=value
                with self.subTest(field=field,value=value):
                    self.assertEqual(
                        plan.build_unsigned_dual_root_transcript_draft(t)["state"],
                        "BLOCKED")

    def test_missing_extra_role_field_rejected(self):
        for field in transcript():
            t=transcript()
            t.pop(field)
            self.assertEqual(
                plan.build_unsigned_dual_root_transcript_draft(t)["state"],
                "BLOCKED")
        t=transcript()
        t["install_now"]=True
        self.assertEqual(plan.build_unsigned_dual_root_transcript_draft(t)["state"],
                         "BLOCKED")

    def test_non_dictionary_input_rejected(self):
        for o in (None,True,False,1,[],{},''):
            out=plan.build_unsigned_dual_root_transcript_draft(o)
            self.assertEqual(out["state"],"BLOCKED")
            self.deny_signing(out)

    def test_draft_has_no_private_material_or_real_signature(self):
        out=plan.build_unsigned_dual_root_transcript_draft(transcript())
        for secret in ("private_key","signed_signature","tpmsignature",
                       "windows_credential","owner_password"):
            self.assertNotIn(secret,out["draft_canonical_json"].lower())
        self.deny_signing(out)

    def test_draft_has_no_implicit_user_approval(self):
        out=plan.build_unsigned_dual_root_transcript_draft(transcript())
        self.assertFalse(out["authorized_for_provisioning"])
        self.assertFalse(out["safe_to_resume"])


if __name__=="__main__":
    unittest.main()
