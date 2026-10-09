"""Synthetic owner-scoped diagnostic challenge receipts; NO owner PC execution."""
from __future__ import annotations

import copy
import os
import re
import unittest
from unittest.mock import patch

import atlasquant_aion_owner_silent_cng_algorithm_observation_v1 as owner
import atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 as cng
from test_atlasquant_aion_native_cng_silent_signature_algorithm_enum_v1 import FakeCNG


class OwnerChallengeReceiptTests(unittest.TestCase):
    def observe(self, nonce="aa" * 32, fake=None):
        if fake is None:
            fake = FakeCNG(rows=[
                ("RSA",3,0x14),("ECDSA_P256",5,0x10),
                ("ED25519",5,0x10),
            ])
        with patch.object(owner.sys, "platform", "win32"), patch.dict(
            os.environ, {}, clear=True
        ), patch.object(cng, "_load_ncrypt", return_value=fake):
            observation = owner.observe_owner_silent_signature_algorithms_readonly(
                nonce,
                explicit_owner_authorization_for_this_probe=True,
                authorized_device_scope=owner.PHYSICAL_SCOPE,
            )
        return observation, fake

    def assert_never_authority(self, result):
        self.assertIs(result["receipt_is_trusted_evidence"], False)
        self.assertIs(result["owner_identity_verified"], False)
        self.assertIs(result["physical_device_verified"], False)
        self.assertIs(result["replay_prevention_verified"], False)
        self.assertIs(result["installer_authorized"], False)
        self.assertIs(result["safe_to_resume"], False)

    def test_valid_readonly_observation_receipt_is_recomputable_not_trust(self):
        report, fake = self.observe()
        receipt = report["diagnostic_correlation_receipt"]
        self.assertEqual(receipt["schema"], owner.RECEIPT_SCHEMA)
        self.assertEqual(receipt["scope"], owner.PHYSICAL_SCOPE)
        self.assertEqual(receipt["challenge_nonce"],"aa"*32)
        self.assertRegex(receipt["sanitized_observation_sha256"],r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(receipt["challenge_binding_sha256"],r"^sha256:[0-9a-f]{64}$")
        check = owner.verify_diagnostic_correlation_receipt(report)
        self.assertEqual(check["state"],"CORRELATION_RECOMPUTED_UNTRUSTED")
        self.assertTrue(check["correlation_recomputed"])
        self.assert_never_authority(check)
        self.assertEqual(len([e for e in fake.calls if e[0] == "enum"]),1)

    def test_different_nonce_changes_binding_not_algorithm_observation(self):
        a,_ = self.observe("aa"*32)
        b,_ = self.observe("ab"*32)
        ar=a["diagnostic_correlation_receipt"]
        br=b["diagnostic_correlation_receipt"]
        self.assertEqual(ar["sanitized_observation_sha256"],br["sanitized_observation_sha256"])
        self.assertNotEqual(ar["challenge_binding_sha256"],br["challenge_binding_sha256"])
        for report in (a,b):
            self.assertTrue(owner.verify_diagnostic_correlation_receipt(report)["correlation_recomputed"])

    def test_identical_observation_nonce_deterministic_for_correlation(self):
        a,_ = self.observe("bd"*32)
        b,_ = self.observe("bd"*32)
        self.assertEqual(a["diagnostic_correlation_receipt"],
                         b["diagnostic_correlation_receipt"])

    def test_tamper_evidence_fields_detected(self):
        original,_=self.observe()
        updates=[
            ("algorithm_name_count",99),
            ("state","TRUSTED"),
            ("target_algorithm_names",{"ED25519":"NOT_LISTED","ECDSA_P256":"LISTED"}),
            ("provider_ui_suppression_requested",False),
            ("reason","INJECTED"),
            ("build_authorized",True),
        ]
        for field,value in updates:
            with self.subTest(field=field):
                m=copy.deepcopy(original)
                m[field]=value
                check=owner.verify_diagnostic_correlation_receipt(m)
                self.assertEqual(check["state"],"BLOCKED")
                self.assert_never_authority(check)

    def test_receipt_nonce_tampering_detected(self):
        original,_=self.observe()
        modified=copy.deepcopy(original)
        modified["diagnostic_correlation_receipt"]["challenge_nonce"]="ab"*32
        self.assertFalse(owner.verify_diagnostic_correlation_receipt(modified)["correlation_recomputed"])

    def test_observation_and_binding_digest_tampering_detected(self):
        for name in ("sanitized_observation_sha256","challenge_binding_sha256"):
            with self.subTest(field=name):
                original,_=self.observe()
                modified=copy.deepcopy(original)
                modified["diagnostic_correlation_receipt"][name]="sha256:"+"0"*64
                check=owner.verify_diagnostic_correlation_receipt(modified)
                self.assertEqual(check["reason"],"RECEIPT_INVALID")

    def test_unsigned_receipt_never_claims_signed_owner_or_witness(self):
        original,_=self.observe()
        for name in (
            "receipt_signed","independently_witnessed",
            "owner_identity_attested","physical_device_attested",
            "replay_prevention_verified","trusted_host_anchor_verified",
            "physical_sandbox_approved","installer_authorized","safe_to_resume",
        ):
            with self.subTest(name=name):
                forged=copy.deepcopy(original)
                forged["diagnostic_correlation_receipt"][name]=True
                self.assertFalse(
                    owner.verify_diagnostic_correlation_receipt(forged)["correlation_recomputed"])

    def test_missing_or_extra_receipt_fields_rejected(self):
        original,_=self.observe()
        for field in ("challenge_nonce","scope","receipt_signed"):
            with self.subTest(missing=field):
                forged=copy.deepcopy(original)
                forged["diagnostic_correlation_receipt"].pop(field)
                self.assertFalse(
                    owner.verify_diagnostic_correlation_receipt(forged)["correlation_recomputed"])
        extra=copy.deepcopy(original)
        extra["diagnostic_correlation_receipt"]["auto_launch"]=True
        self.assertFalse(
            owner.verify_diagnostic_correlation_receipt(extra)["correlation_recomputed"])

    def test_receipt_cannot_autorize_installer_even_when_observation_was_listed(self):
        original,_=self.observe()
        self.assertEqual(original["state"],cng.CANDIDATE)
        self.assertEqual(original["target_algorithm_names"]["ED25519"],"LISTED")
        self.assertFalse(original["installer_authorized"])
        self.assertFalse(original["diagnostic_correlation_receipt"]["installer_authorized"])
        self.assert_never_authority(owner.verify_diagnostic_correlation_receipt(original))

    def test_native_failed_observation_can_be_correlated_but_is_still_blocked(self):
        original,_=self.observe(fake=FakeCNG(enum_status=0x80090009))
        self.assertEqual(original["state"],"BLOCKED")
        self.assertEqual(original["reason"],"SILENT_ENUM_FAILED")
        check=owner.verify_diagnostic_correlation_receipt(original)
        self.assertEqual(check["state"],"CORRELATION_RECOMPUTED_UNTRUSTED")
        self.assert_never_authority(check)

    def test_wrong_nonce_type_prevents_native_call_and_no_receipt(self):
        for nonce in (None, "not-a-nonce", True, "", "A"*64):
            with self.subTest(nonce=nonce):
                report,fake=self.observe(nonce=nonce)
                self.assertEqual(report["state"],"BLOCKED")
                self.assertNotIn("diagnostic_correlation_receipt",report)
                self.assertFalse(fake.calls)

    def test_receipt_verifier_never_invokes_native_functions(self):
        report,_=self.observe()
        with patch.object(cng,"_load_ncrypt") as load:
            result=owner.verify_diagnostic_correlation_receipt(report)
        self.assertTrue(result["correlation_recomputed"])
        load.assert_not_called()

    def test_none_or_non_dict_rejected(self):
        for x in (None,1,True,[],{},{"state":"BLOCKED"}):
            with self.subTest(x=x):
                check=owner.verify_diagnostic_correlation_receipt(x)
                self.assertFalse(check["correlation_recomputed"])
                self.assert_never_authority(check)

    def test_receipt_schema_and_scope_spoofing_rejected(self):
        original,_=self.observe()
        for field,value in (("schema","EVIL"),("scope","INSTALL")):
            with self.subTest(field=field):
                forged=copy.deepcopy(original)
                forged["diagnostic_correlation_receipt"][field]=value
                self.assertFalse(
                    owner.verify_diagnostic_correlation_receipt(forged)["correlation_recomputed"])


if __name__ == "__main__":
    unittest.main()
