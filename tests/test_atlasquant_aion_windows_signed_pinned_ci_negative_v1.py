"""Ed25519 pinned executable scope, tamper and CI negative Win32 tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import os
import sys
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlasquant_aion_windows_signed_binary_ci_negative_intent_v1 import (
    SCHEMA, OPERATION, BLOCKED, CANDIDATE,
    canonical_intent, check_signed_ci_negative_intent,
)
from atlasquant_aion_windows_pinned_suspended_ci_negative_v1 import (
    _ci_allowed, _result_template, run_ci_negative_signed_pinned_process,
)


def material():
    return {
        "schema": SCHEMA,
        "operation": OPERATION,
        "nonce": "12" * 16,
        "image_path": r"C:\Pinned\Fixture\python.exe",
        "image_sha256": sha256(b"fixture-image-bytes").hexdigest(),
        "issued_at": 1000,
        "expires_at": 1100,
        "expected_token_verdict": "TOKEN_NOT_APPCONTAINER",
    }


def sign(m=None):
    m=material() if m is None else m
    key=Ed25519PrivateKey.generate()
    sig=key.sign(canonical_intent(m))
    pub=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return sig,pub


class SignedPinnedExecutableTests(unittest.TestCase):
    def result(self, manifest=None, sig=None, pub=None, **override):
        m=material() if manifest is None else manifest
        if sig is None or pub is None:
            generated_sig, generated_pub=sign(m)
            if sig is None:sig=generated_sig
            if pub is None:pub=generated_pub
        args={
            "observed_image_path":m.get("image_path","") if type(m) is dict else "",
            "observed_image_sha256":m.get("image_sha256","") if type(m) is dict else "",
            "now":1050,
        }
        args.update(override)
        return check_signed_ci_negative_intent(m,sig,pub,**args)

    def no_authority(self,result):
        for field in (
            "trusted_root_verified", "nonce_durability_verified",
            "process_handle_origin_verified", "physical_attestation_verified",
            "appcontainer_verified", "network_deny_verified",
            "safe_to_resume", "installer_authorized",
            "build_authorized", "deploy_authorized",
        ):
            self.assertIs(result[field],False,field)

    def test_cryptographically_valid_fixture_candidate_only(self):
        x=self.result()
        self.assertEqual(x["state"],CANDIDATE)
        self.assertTrue(x["signature_cryptographically_valid"])
        self.assertTrue(x["image_identity_candidate"])
        self.no_authority(x)

    def test_modified_signed_digest_signature_cannot_survive(self):
        m=material()
        s,p=sign(m)
        m["image_sha256"]="0"*64
        x=self.result(m,s,p,observed_image_sha256="0"*64)
        self.assertEqual(x["reason"],"ED25519_SIGNATURE_INVALID")
        self.no_authority(x)

    def test_different_image_contents_fail(self):
        m=material()
        x=self.result(m,observed_image_sha256="0"*64)
        self.assertEqual(x["reason"],"SUSPENDED_PROCESS_IMAGE_DIGEST_MISMATCH")
        self.no_authority(x)

    def test_executable_path_swap_fail(self):
        x=self.result(observed_image_path=r"C:\Pinned\Fixture\unapproved.exe")
        self.assertEqual(x["reason"],"SUSPENDED_PROCESS_IMAGE_PATH_MISMATCH")
        self.no_authority(x)

    def test_windows_case_only_match(self):
        x=self.result(observed_image_path=r"c:\pinned\fixture\PYTHON.EXE")
        self.assertEqual(x["state"],CANDIDATE)
        self.no_authority(x)

    def test_expired_signature_fails_closed(self):
        for clock in (999,1101,999999):
            with self.subTest(clock=clock):
                x=self.result(now=clock)
                self.assertEqual(x["reason"],"SIGNATURE_WINDOW_INVALID_OR_EXPIRED")
                self.no_authority(x)

    def test_signature_window_too_large_denied(self):
        m=material();m["expires_at"]=1121
        x=self.result(m)
        self.assertEqual(x["reason"],"SIGNATURE_WINDOW_INVALID_OR_EXPIRED")

    def test_negative_operation_only(self):
        for operation in ("APPROVE_OWNER_HOST","INSTALL_AION","RESUME_PROCESS","ALLOW_ONLINE",None,True):
            with self.subTest(operation=operation):
                m=material();m["operation"]=operation
                x=self.result(m)
                self.assertEqual(x["reason"],"CI_NEGATIVE_ONLY_OPERATION_REQUIRED")
                self.no_authority(x)

    def test_only_expected_normal_token_verdict(self):
        for value in ("APPROVED", "OWNER", "TOKEN_IS_APPCONTAINER", True, None):
            with self.subTest(value=value):
                m=material();m["expected_token_verdict"]=value
                x=self.result(m)
                self.assertEqual(x["reason"],"NORMAL_CHILD_DENIAL_ONLY")
                self.no_authority(x)

    def test_wrong_public_key_is_not_authorization(self):
        m=material();s,_=sign(m);_,other_pub=sign(m)
        x=self.result(m,s,other_pub)
        self.assertEqual(x["reason"],"ED25519_SIGNATURE_INVALID")
        self.no_authority(x)

    def test_corrupt_signature_blocked(self):
        m=material();s,p=sign(m)
        x=self.result(m,bytes([s[0]^1])+s[1:],p)
        self.assertEqual(x["reason"],"ED25519_SIGNATURE_INVALID")
        self.no_authority(x)

    def test_truncated_and_invalid_signature_rejected(self):
        for sig in (None,True,"A"*64,b"x"*63,b"x"*65,[],{}):
            with self.subTest(sig=repr(sig)):
                x=check_signed_ci_negative_intent(
                    material(),sig,sign()[1],
                    observed_image_path=material()["image_path"],
                    observed_image_sha256=material()["image_sha256"],now=1050,
                )
                self.assertEqual(x["reason"],"SIGNATURE_FORMAT_INVALID")
                self.no_authority(x)

    def test_wrong_key_format_rejected(self):
        m=material();s,_=sign(m)
        for pub in (True,None,"keys",b"x"*31,b"x"*33,[],{}):
            with self.subTest(pub=repr(pub)):
                x=check_signed_ci_negative_intent(
                    m,s,pub,observed_image_path=m["image_path"],
                    observed_image_sha256=m["image_sha256"],now=1050,
                )
                self.assertEqual(x["reason"],"PUBLIC_KEY_FORMAT_INVALID")
                self.no_authority(x)

    def test_invalid_digest_format_rejected(self):
        for value in (True,False,None,"sha256:"+("a"*64),"A"*64,"h"*64,"0"*65):
            with self.subTest(value=str(value)):
                m=material();m["image_sha256"]=value
                self.assertEqual(self.result(m)["reason"],"PINNED_SHA256_REQUIRED")

    def test_bad_nonce_rejected(self):
        for value in (None,True,"", "z"*32, "F"*32, "f"*33,0):
            with self.subTest(value=str(value)):
                m=material();m["nonce"]=value
                self.assertEqual(self.result(m)["reason"],"NONCE_FORMAT_INVALID")

    def test_relative_unc_reparse_like_paths_rejected(self):
        for value in (
            "", None, 123, "python.exe", r"\\server\share\python.exe",
            r"C:python.exe", r"C:\Safe\..\Other\python.exe",
            "C:\\hello\\python.exe\x00",
        ):
            with self.subTest(path=str(value)):
                m=material();m["image_path"]=value
                self.assertEqual(self.result(m)["reason"],"PINNED_WINDOWS_PATH_REQUIRED")

    def test_bad_timestamp_types_rejected(self):
        for value in (True,None,"1000",1000.0,{},[]):
            with self.subTest(value=repr(value)):
                m=material();m["issued_at"]=value
                self.assertEqual(self.result(m)["reason"],"SIGNATURE_WINDOW_INVALID_OR_EXPIRED")

    def test_missing_or_extra_manifest_fields_rejected(self):
        original=material()
        for key in original:
            with self.subTest(key=key):
                m=material();del m[key]
                self.assertEqual(self.result(m)["reason"],"EXACT_SIGNED_MANIFEST_FIELDS_REQUIRED")
        m=material();m["owner_approved"]=True
        self.assertEqual(self.result(m)["reason"],"EXACT_SIGNED_MANIFEST_FIELDS_REQUIRED")

    def test_non_dict_manifest_rejected(self):
        for m in (None,[],True,"a",100,()):
            with self.subTest(value=str(m)):
                self.assertEqual(self.result(m)["reason"],"EXACT_SIGNED_MANIFEST_FIELDS_REQUIRED")

    def test_invalid_observed_sha256_format_rejected(self):
        for val in (None,True,"0"*63,"0"*65,{}):
            with self.subTest(value=str(val)):
                self.assertEqual(self.result(observed_image_sha256=val)["reason"],"SUSPENDED_PROCESS_IMAGE_DIGEST_MISMATCH")

    def test_invalid_observed_image_path_rejected(self):
        for val in (None,True,"","other.exe"):
            with self.subTest(value=str(val)):
                self.assertEqual(self.result(observed_image_path=val)["reason"],"SUSPENDED_PROCESS_IMAGE_PATH_MISMATCH")

    def test_manifest_not_mutated(self):
        m=material();b=deepcopy(m)
        s,p=sign(m)
        self.result(m,s,p)
        self.assertEqual(m,b)

    def test_default_native_ci_probe_requires_guards(self):
        base=_result_template()
        self.assertEqual(base["state"],"BLOCKED")
        self.assertFalse(base["safe_to_resume"])
        self.assertFalse(base["installer_authorized"])
        self.assertFalse(base["network_probe_executed"])

    def test_native_probe_refuses_non_ci(self):
        with patch("atlasquant_aion_windows_pinned_suspended_ci_negative_v1._ci_allowed",return_value=False):
            report=run_ci_negative_signed_pinned_process()
        self.assertEqual(report["reason"],"WINDOWS_GITHUB_PR_CI_ONLY")
        self.assertFalse(report["child_created_suspended"])

    def test_native_module_never_calls_resume_or_appcontainer_create(self):
        import ast
        import atlasquant_aion_windows_pinned_suspended_ci_negative_v1 as module
        root=ast.parse(inspect.getsource(module))
        forbidden={
            "ResumeThread", "NtResumeProcess", "CreateAppContainerProfile",
            "FwpmFilterAdd0","DeleteAppContainerProfile",
        }
        for node in ast.walk(root):
            if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,forbidden)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                self.assertNotIn(node.func.id,forbidden)

    def test_windows_physical_ci_negative_only(self):
        if sys.platform!="win32" or not _ci_allowed():
            self.skipTest("Windows GitHub PR CI native-only")
        r=run_ci_negative_signed_pinned_process()
        self.assertEqual(r["state"],"SIGNED_PINNED_NORMAL_CHILD_QUARANTINED_CI_ONLY",r)
        for key in (
            "image_handle_opened_deny_write_delete_shares",
            "file_identity_pre_post_stable","file_digest_pre_post_stable",
            "test_intent_signed_with_ephemeral_ci_key",
            "signed_intent_candidate_untrusted","child_created_suspended",
            "job_kill_on_close_set","child_assigned_to_job",
            "actual_suspended_image_matches_signed_path",
            "normal_token_rejected","child_never_resumed","child_terminated",
            "canary_absent","file_handle_closed","process_handle_closed",
            "thread_handle_closed","job_handle_closed","scratch_removed",
        ):
            self.assertTrue(r[key],key)
        for key in (
            "real_owner_authorized","network_probe_executed","profile_created",
            "firewall_modified","physical_attestation_verified",
            "safe_to_resume","installer_authorized","build_authorized",
            "deploy_authorized",
        ):
            self.assertFalse(r[key],key)
