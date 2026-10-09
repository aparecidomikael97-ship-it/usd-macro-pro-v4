"""Three-key-role AION architectural tests; never signs, accesses keys or OS."""
from __future__ import annotations

import copy
import re
import unittest

import atlasquant_aion_independent_ed25519_trirole_bridge_contract_v1 as b


def sample():
    return {
        "schema": b.SCHEMA,
        "owner": {
            "role": "HUMAN_OWNER_ED25519", "algorithm": "Ed25519",
            "public_key_sha256": "sha256:" + "a"*64,
            "custody_boundary": "OWNER_HELD_INDEPENDENT_DEVICE_CANDIDATE",
            "custodian_id": "owner-offhost-01",
            "verification_state": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        },
        "collector": {
            "role": "COLLECTOR_ED25519", "algorithm": "Ed25519",
            "public_key_sha256": "sha256:" + "b"*64,
            "custody_boundary": "SEPARATE_COLLECTOR_SIGNER_DOMAIN_CANDIDATE",
            "custodian_id": "collector-indep-01",
            "verification_state": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        },
        "host": {
            "role": "HOST_ECDSA_P256", "algorithm": "ECDSA_P256_SHA256",
            "public_key_sha256": "sha256:" + "c"*64,
            "custody_boundary": "WINDOWS_PLATFORM_TPM_P256_CANDIDATE_UNATTESTED",
            "custodian_id": "host-binding-01",
            "verification_state": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        },
        "collector_binary_sha256": "sha256:" + "d"*64,
        "policy_sha256": "sha256:" + "e"*64,
        "policy_generation": 9,
        "estimated_monthly_brl": 0,
    }


class TriRoleCustodyContractTests(unittest.TestCase):
    def deny(self, result):
        for key, value in b._FALSE_GATES.items():
            self.assertIs(result[key], False, key)
        self.assertIs(result["budget_is_unverified_estimate"], True)
        self.assertIs(result["separate_key_provisioning_owner_approval_required"], True)
        self.assertIs(result["independent_hardware_attestation_design_required"], True)

    def test_review_candidates_never_approve_keys_or_install(self):
        x=b.review_three_role_custody_design(sample())
        self.assertEqual(x["state"], "THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED")
        self.assertEqual(x["reason"], "")
        self.deny(x)

    def test_all_evidence_steps_remain_missing(self):
        x=b.review_three_role_custody_design(sample())
        required=x["evidence_required"]
        self.assertEqual(len(required),len(set(required)))
        for s in (
            "OWNER_ED25519_INDEPENDENT_CUSTODY_PROOF",
            "COLLECTOR_ED25519_INDEPENDENT_CUSTODY_PROOF",
            "P256_HOST_KEY_ORIGIN_AND_NONEXPORTABILITY_ATTESTATION",
            "INDEPENDENT_HOST_ATTESTATION_VERIFIER_AND_TRUST_ANCHOR",
            "DURABLE_NONCE_ISSUANCE_AND_SPENT_NONCE_LEDGER",
            "DURABLE_POLICY_GENERATION_AND_ANTIROLLBACK",
            "OWNER_SIGNED_SEPARATE_KEY_PROVISIONING_DECISION",
            "PHYSICAL_SANDBOX_12_OF_12",
            "PHYSICAL_NETWORK_DENY_16_OF_16",
        ):
            self.assertIn(s,required)
        self.deny(x)

    def test_non_mapping_inputs_are_rejected(self):
        for x in (None,True,False,[],[sample()],1,"ready",{}):
            with self.subTest(x=x):
                result=b.review_three_role_custody_design(x)
                self.assertEqual(result["state"], "BLOCKED")
                self.deny(result)

    def test_no_unknown_sensitive_data_accepted(self):
        for key, value in (
            ("private_key", "SENSITIVE"), ("owner_signature","hexbytes"),
            ("auto_install",True), ("hardware_attestation",True),
            ("operator_token","secret"), ("key_material","RAW_KEY_SENTINEL_Q7Z_20261008"),
        ):
            x=sample()
            x[key]=value
            with self.subTest(key=key):
                result=b.review_three_role_custody_design(x)
                self.assertEqual(result["state"],"BLOCKED")
                self.assertNotIn(value if type(value) is str else "SENSITIVE",str(result))
                self.deny(result)

    def test_missing_required_fields_denied(self):
        for key in sample():
            with self.subTest(field=key):
                x=sample()
                x.pop(key)
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_cannot_swap_owner_collector_roles(self):
        x=sample()
        x["owner"],x["collector"]=x["collector"],x["owner"]
        self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_cannot_swap_owner_and_host_algorithm(self):
        for role,alg in (
            ("owner","ECDSA_P256_SHA256"),
            ("collector","ECDSA_P256_SHA256"),
            ("host","Ed25519"),
            ("owner","RSA_PSS_SHA256"),
            ("collector","ECDSA_P256"),
        ):
            with self.subTest(role=role,algorithm=alg):
                x=sample()
                x[role]["algorithm"]=alg
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_shared_public_key_fingerprint_is_rejected(self):
        for a,c in (("owner","collector"),("owner","host"),("collector","host")):
            with self.subTest(roles=(a,c)):
                x=sample()
                x[c]["public_key_sha256"]=x[a]["public_key_sha256"]
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_shared_custodian_domain_id_is_rejected(self):
        for a,c in (("owner","collector"),("owner","host"),("collector","host")):
            with self.subTest(roles=(a,c)):
                x=sample()
                x[c]["custodian_id"]=x[a]["custodian_id"]
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_role_name_and_schema_substitution_denied(self):
        for key,val in (
            ("schema","AION_TRUSTED_INSTALL"),
            ("owner.role","COLLECTOR_ED25519"),
            ("collector.role","HUMAN_OWNER_ED25519"),
            ("host.role","HUMAN_OWNER_ED25519"),
        ):
            x=sample()
            if "." in key:
                first,last=key.split(".")
                x[first][last]=val
            else:
                x[key]=val
            self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_unverified_custodian_state_is_required(self):
        for role in ("owner","collector","host"):
            for status in ("VERIFIED",True,"TPM",None):
                with self.subTest(role=role,status=status):
                    x=sample()
                    x[role]["verification_state"]=status
                    self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_host_must_be_p256_candidate_unattested(self):
        for claim in ("TPM_ATTESTED", "WINDOWS_SOFTWARE_KEY_STORAGE_PROVIDER",
                      "EXTERNAL_HSM",None,True):
            x=sample()
            x["host"]["custody_boundary"]=claim
            self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_owner_and_collector_domains_are_explicitly_separate(self):
        x=sample()
        x["owner"]["custody_boundary"]="INDEPENDENT_REMOTE_TRUST_DOMAIN_CANDIDATE"
        x["collector"]["custody_boundary"]="INDEPENDENT_COLLECTOR_REMOTE_CUSTODIAN_CANDIDATE"
        self.assertEqual(b.review_three_role_custody_design(x)["state"],
                         "THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED")
        self.deny(b.review_three_role_custody_design(x))

    def test_collector_custodian_cannot_be_owner_boundary(self):
        x=sample()
        x["collector"]["custody_boundary"]=x["owner"]["custody_boundary"]
        self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_owner_custodian_cannot_be_host_bound(self):
        x=sample()
        x["owner"]["custody_boundary"]=x["host"]["custody_boundary"]
        self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_invalid_identifiers_or_injection_denied(self):
        for value in ("x", "", "owner\nscript", "x"*73, True, None,
                      "C:\\\\secret\\\\host","<script>"):
            with self.subTest(value=value):
                x=sample()
                x["owner"]["custodian_id"]=value
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_no_extra_per_key_signer_fields(self):
        for role in ("owner","collector","host"):
            x=sample()
            x[role]["private_seed"]="dont_log"
            self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")
        for role in ("owner","collector","host"):
            x=sample()
            x[role].pop("verification_state")
            self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_invalid_key_fingerprints_denied(self):
        for bad in (None,0,True,"sha256:"+"F"*64, "0"*64,
                    "sha256:"+"a"*63, "sha512:"+"a"*128):
            with self.subTest(bad=bad):
                x=sample()
                x["host"]["public_key_sha256"]=bad
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_missing_collector_binary_and_policy_fingerprints_denied(self):
        for field in ("collector_binary_sha256","policy_sha256"):
            for bad in (None,True,"abc", "sha256:"+"!"*64):
                x=sample()
                x[field]=bad
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_invalid_policy_generation_denied(self):
        for generation in (-1,True,False,1.1,2**32,2**64,"9",None):
            with self.subTest(generation=generation):
                x=sample()
                x["policy_generation"]=generation
                self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_monthly_budget_cap_is_design_only_and_strict(self):
        for brl in (0,1,100,200):
            x=sample()
            x["estimated_monthly_brl"]=brl
            result=b.review_three_role_custody_design(x)
            self.assertEqual(result["state"],"THREE_ROLE_CUSTODY_DESIGN_CANDIDATE_UNTRUSTED")
            self.assertTrue(result["budget_is_unverified_estimate"])
        for brl in (-1,201,500,True,False,"0",1.0,None):
            x=sample()
            x["estimated_monthly_brl"]=brl
            self.assertEqual(b.review_three_role_custody_design(x)["state"],"BLOCKED")

    def test_no_private_key_operations_in_source_contract(self):
        x=sample()
        result=b.review_three_role_custody_design(x)
        self.assertFalse(result["ed25519_owner_private_key_custody_verified"])
        self.assertFalse(result["ed25519_collector_private_key_custody_verified"])
        self.assertFalse(result["p256_private_key_present"])
        self.deny(result)


class UnsignedTriRoleChallengeTests(unittest.TestCase):
    def denied(self, output):
        for key in ("role_message_signed","owner_signature_verified",
                    "collector_signature_verified","host_signature_verified",
                    "host_key_attested","replay_prevention_verified",
                    "bridge_implemented","installer_authorized","safe_to_resume"):
            self.assertIs(output[key],False,key)

    def test_three_distinct_unsigned_domains_and_algorithms(self):
        result=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        self.assertEqual(result["state"],"THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED")
        self.assertEqual(set(result["role_messages"]),set(b._ROLES))
        self.assertEqual(result["role_messages"]["HUMAN_OWNER_ED25519"]["algorithm"],"Ed25519")
        self.assertEqual(result["role_messages"]["COLLECTOR_ED25519"]["algorithm"],"Ed25519")
        self.assertEqual(result["role_messages"]["HOST_ECDSA_P256"]["algorithm"],"ECDSA_P256_SHA256")
        self.assertEqual(len({r["role_domain"] for r in result["role_messages"].values()}),3)
        self.assertEqual(len({r["unsigned_message_sha256"] for r in result["role_messages"].values()}),3)
        self.denied(result)

    def test_signature_present_never_true(self):
        result=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        for record in result["role_messages"].values():
            self.assertIs(record["signature_present"],False)
            self.assertIs(record["signature_verified"],False)
        self.denied(result)

    def test_nonce_mutation_changes_all_three_role_intents(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        c=b.build_unsigned_three_role_challenge(sample(),"ac"*32)
        self.assertNotEqual(a["transcript_sha256"],c["transcript_sha256"])
        for role in b._ROLES:
            self.assertNotEqual(
                a["role_messages"][role]["unsigned_message_sha256"],
                c["role_messages"][role]["unsigned_message_sha256"])
        self.denied(c)

    def test_same_plan_nonce_yields_same_unsigned_messages(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        c=b.build_unsigned_three_role_challenge(copy.deepcopy(sample()),"ab"*32)
        self.assertEqual(a,c)

    def test_different_collector_digest_changes_all_role_intents(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        x=sample()
        x["collector_binary_sha256"]="sha256:"+"f"*64
        c=b.build_unsigned_three_role_challenge(x,"ab"*32)
        self.assertNotEqual(a["transcript_sha256"],c["transcript_sha256"])
        self.denied(c)

    def test_changing_policy_or_generation_changes_challenge(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        for key,value in (("policy_sha256","sha256:"+"0"*64),
                          ("policy_generation",10)):
            x=sample()
            x[key]=value
            with self.subTest(field=key):
                c=b.build_unsigned_three_role_challenge(x,"ab"*32)
                self.assertNotEqual(a["transcript_sha256"],c["transcript_sha256"])
                self.denied(c)

    def test_changing_any_role_key_fingerprint_changes_challenge(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        for role in ("owner","collector","host"):
            x=sample()
            x[role]["public_key_sha256"]="sha256:"+"f"*64
            with self.subTest(role=role):
                c=b.build_unsigned_three_role_challenge(x,"ab"*32)
                self.assertNotEqual(a["transcript_sha256"],c["transcript_sha256"])

    def test_swapping_ed25519_roles_denied(self):
        x=sample()
        x["owner"],x["collector"]=x["collector"],x["owner"]
        result=b.build_unsigned_three_role_challenge(x,"ab"*32)
        self.assertEqual(result["state"],"BLOCKED")
        self.denied(result)

    def test_invalid_nonce_and_type_fail_without_messages(self):
        for value in (None,True,False,0,"A"*64,"ab"*33,"a"*63,"!ab"*32):
            with self.subTest(value=value):
                result=b.build_unsigned_three_role_challenge(sample(),value)
                self.assertEqual(result["state"],"BLOCKED")
                self.assertEqual(result["role_messages"],{})
                self.denied(result)

    def test_cannot_issue_challenge_from_unverified_role_schema(self):
        x=sample()
        x["host"]["algorithm"]="Ed25519"
        result=b.build_unsigned_three_role_challenge(x,"ab"*32)
        self.assertEqual(result["state"],"BLOCKED")
        self.denied(result)

    def test_cannot_promote_unsigned_message_to_installer(self):
        result=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        self.assertFalse(result["installer_authorized"])
        self.assertFalse(result["safe_to_resume"])
        self.assertFalse(result["bridge_implemented"])
        self.denied(result)

    def test_greater_generation_not_durable_antirollback(self):
        x=sample()
        x["policy_generation"]=2**32-1
        result=b.build_unsigned_three_role_challenge(x,"ab"*32)
        self.assertEqual(result["state"],"THREE_UNSIGNED_ROLE_CHALLENGES_UNTRUSTED")
        self.assertFalse(result["replay_prevention_verified"])
        self.denied(result)

    def test_no_report_of_replayed_nonce_safety(self):
        a=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        c=b.build_unsigned_three_role_challenge(sample(),"ab"*32)
        self.assertEqual(a["transcript_sha256"],c["transcript_sha256"])
        self.assertFalse(c["replay_prevention_verified"])
        self.denied(c)


if __name__ == "__main__":
    unittest.main()
