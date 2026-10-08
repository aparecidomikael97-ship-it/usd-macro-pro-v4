"""AION AppContainer native readback gate: fail-closed, OS read-only smoke."""
from __future__ import annotations

import inspect
import sys
import unittest
from unittest.mock import patch

from atlasquant_aion_windows_appcontainer_token_readonly_v1 import (
    SCHEMA, NOT_READY, MATCH_CANDIDATE, PROFILE_RE,
    evaluate_untrusted_token_readback, inspect_windows_process_handle,
)

PROFILE = "AtlasQuantAIONProbe5cee68653592"


class AppContainerTokenReadbackTests(unittest.TestCase):
    def readback(self, **changes):
        values = {
            "profile_name": PROFILE,
            "appcontainer_flag": True,
            "sid_matches": True,
            "capability_count": 0,
            "all_queries_succeeded": True,
        }
        values.update(changes)
        return evaluate_untrusted_token_readback(**values)

    def no_authority(self, out):
        self.assertEqual(out["schema"], SCHEMA)
        for name in (
            "physical_attestation_verified", "real_host_identity_verified",
            "process_handle_origin_verified", "network_deny_verified",
            "installer_authorized", "build_authorized", "deploy_authorized",
        ):
            self.assertIs(out[name], False, name)

    def test_valid_candidate_never_authorizes(self):
        out=self.readback()
        self.assertEqual(out["state"],MATCH_CANDIDATE)
        self.assertEqual(out["capability_count"],0)
        self.no_authority(out)

    def test_incomplete_readback_blocks(self):
        out=self.readback(all_queries_succeeded=False)
        self.assertEqual(out["state"],NOT_READY)
        self.assertEqual(out["reason"],"TOKEN_READBACK_INCOMPLETE")
        self.no_authority(out)

    def test_non_appcontainer_token_blocks(self):
        out=self.readback(appcontainer_flag=False)
        self.assertEqual(out["reason"],"TOKEN_NOT_APPCONTAINER")
        self.no_authority(out)

    def test_mismatched_sid_blocks(self):
        out=self.readback(sid_matches=False)
        self.assertEqual(out["reason"],"TOKEN_SID_DOES_NOT_MATCH_EXPECTED_PROFILE")
        self.no_authority(out)

    def test_one_capability_blocks(self):
        out=self.readback(capability_count=1)
        self.assertEqual(out["reason"],"TOKEN_HAS_NETWORK_OR_OTHER_CAPABILITIES")
        self.no_authority(out)

    def test_many_capabilities_block(self):
        for count in (2,16,48,4096):
            with self.subTest(count=count):
                out=self.readback(capability_count=count)
                self.assertEqual(out["state"],NOT_READY)
                self.no_authority(out)

    def test_invalid_capability_counts_block(self):
        for count in (None, True, False, -1, 4097, "0", 0.0, [], {}):
            with self.subTest(count=str(count)):
                out=self.readback(capability_count=count)
                self.assertEqual(out["reason"],"TOKEN_CAPABILITY_COUNT_INVALID")
                self.no_authority(out)

    def test_wrong_boolean_types_block(self):
        for key in ("appcontainer_flag", "sid_matches", "all_queries_succeeded"):
            for value in (None, 1, "true", [], {}, 0):
                with self.subTest(key=key, value=str(value)):
                    out=self.readback(**{key:value})
                    self.assertEqual(out["reason"],"TOKEN_BOOL_OBSERVATION_INVALID")
                    self.no_authority(out)

    def test_only_expected_temp_appcontainer_profile_names_allowed(self):
        self.assertIsNotNone(PROFILE_RE.fullmatch(PROFILE))
        for name in (None,True,"", "AION", "AtlasQuantAIONProbe",
                     "AtlasQuantAIONProbe123", "AtlasQuantAIONProbe1234567890ab_",
                     "AtlasQuantAIONProbe1234567890AZ",
                     "OtherAppContainer5cee68653592",
                     "AtlasQuantAIONProbe5cee68653592\\evil",
                     "AtlasQuantAIONProbe5cee68653592/..",
                     "AtlasQuantAIONProbe5cee68653592\u0000",
                     "atlasquantaionprobe5cee68653592",
                     "AtlasQuantAIONProbeZZZZZZZZZZZZ",
                     "AtlasQuantAIONProbe5cee68653592 ",
                     "AtlasQuantAIONProbe5cee68653592_more",
                     ["AtlasQuantAIONProbe5cee68653592"]):
            with self.subTest(name=str(name)):
                out=self.readback(profile_name=name)
                self.assertEqual(out["reason"],"PROFILE_NAME_NOT_SCOPED_TO_EPHEMERAL_AION_PROBE")
                self.no_authority(out)

    def test_candidate_zero_capabilities_is_not_network_denial(self):
        out=self.readback(capability_count=0)
        self.assertEqual(out["state"],MATCH_CANDIDATE)
        self.assertFalse(out["network_deny_verified"])
        self.no_authority(out)

    def test_caller_cannot_sneak_install_permission(self):
        with self.assertRaises(TypeError):
            evaluate_untrusted_token_readback(
                profile_name=PROFILE, appcontainer_flag=True,
                sid_matches=True, capability_count=0,
                all_queries_succeeded=True, installer_authorized=True,
            )

    def test_physical_inspector_does_not_accept_pid_only(self):
        self.assertNotIn("pid",inspect.signature(inspect_windows_process_handle).parameters)

    def test_invalid_scoped_name_denied_before_os_probe(self):
        for handle in (0,1,42,-1):
            with self.subTest(handle=handle):
                result=inspect_windows_process_handle(handle, "DIFFERENT_OWNER_PROFILE")
                self.assertEqual(result["reason"],"PROFILE_NAME_NOT_SCOPED_TO_EPHEMERAL_AION_PROBE")
                self.no_authority(result)

    def test_windows_probe_refuses_boolean_or_null_handle(self):
        if sys.platform!="win32":
            self.skipTest("Native token handle query only on Windows")
        for handle in (None,True,False,0,"-1",{},[]):
            with self.subTest(handle=str(handle)):
                result=inspect_windows_process_handle(handle, PROFILE)
                self.assertEqual(result["reason"],"PROCESS_HANDLE_REQUIRED")
                self.no_authority(result)

    def test_nonwindows_returns_unsupported(self):
        with patch("atlasquant_aion_windows_appcontainer_token_readonly_v1.sys.platform","linux"):
            out=inspect_windows_process_handle(1, PROFILE)
            self.assertEqual(out["reason"],"UNSUPPORTED_PLATFORM")
            self.no_authority(out)

    def test_windows_current_process_token_read_only_denied_as_appcontainer(self):
        if sys.platform!="win32":
            self.skipTest("This read-only Win32 probe is Windows-only")
        import ctypes
        from ctypes import wintypes as W
        kernel=ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.argtypes=[]
        kernel.GetCurrentProcess.restype=W.HANDLE
        handle=kernel.GetCurrentProcess()
        result=inspect_windows_process_handle(int(handle),PROFILE)
        self.assertEqual(result["reason"],"TOKEN_NOT_APPCONTAINER",result)
        self.no_authority(result)

    def test_inspector_source_has_no_creation_or_mutation_win32_apis(self):
        source=inspect.getsource(inspect_windows_process_handle)
        for symbol in (
            "CreateProcessW", "CreateProcessAsUserW", "CreateAppContainerProfile",
            "DeleteAppContainerProfile", "FwpmFilterAdd0",
            "FwpmFilterDeleteById0", "SetTokenInformation",
            "SetNamedSecurityInfo", "NetworkIsolationSetAppContainerConfig",
            "socket.socket", "subprocess.Popen",
        ):
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol+"(",source)

    def test_reason_and_schema_are_stable(self):
        for case in (
            self.readback(),
            self.readback(appcontainer_flag=False),
            self.readback(sid_matches=False),
            self.readback(capability_count=17),
            self.readback(all_queries_succeeded=False),
        ):
            self.assertIs(type(case["reason"]),str)
            self.assertGreater(len(case["reason"]),1)
            self.no_authority(case)

    def test_token_query_cannot_upgrade_other_gates(self):
        x=self.readback()
        self.assertNotIn("windows_network_deny",x)
        self.assertNotIn("child_network_probe_passed",x)
        self.assertNotIn("owner_credential_valid",x)
        self.assertFalse(x["physical_attestation_verified"])
        self.assertFalse(x["process_handle_origin_verified"])
        self.assertFalse(x["network_deny_verified"])

    def test_observation_fields_fixed_even_under_repeated_calls(self):
        a=self.readback(); b=self.readback()
        self.assertEqual(a,b)
        self.assertEqual(set(a),{
            "schema","state","reason","capability_count",
            "physical_attestation_verified","real_host_identity_verified",
            "process_handle_origin_verified","network_deny_verified",
            "installer_authorized","build_authorized","deploy_authorized",
        })
