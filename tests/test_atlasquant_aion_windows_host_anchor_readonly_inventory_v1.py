"""Windows HKLM anchor inventory adversarial tests; NO OS mutation."""
from __future__ import annotations

import copy
import re
import secrets
import sys
import types
import unittest
from unittest.mock import patch

import atlasquant_aion_windows_host_anchor_readonly_inventory_v1 as host


class Handle:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class FakeWinreg(types.ModuleType):
    HKEY_LOCAL_MACHINE = object()
    KEY_READ = 0x20019
    KEY_WOW64_64KEY = 0x100
    REG_SZ = 1
    REG_BINARY = 3
    REG_QWORD = 11

    def __init__(self, values=None):
        super().__init__("winreg")
        self.values = (
            {
                "AnchorSchema": (host.ANCHOR_SCHEMA, self.REG_SZ),
                "PolicyAuthorityPublicKey": (bytes(range(1, 33)), self.REG_BINARY),
                "OwnerRegistryRootPublicKey": (bytes(range(33, 65)), self.REG_BINARY),
                "PolicySnapshotDigest": ("sha256:" + "a" * 64, self.REG_SZ),
                "PolicyEpoch": (4, self.REG_QWORD),
            }
            if values is None else values
        )
        self.fail_with = None
        self.last_access = None
        self.handle = Handle()
        self.open_count = 0
        self.query_count = 0
        self.write_count = 0

    def OpenKey(self, hive, path, reserved, access):
        self.open_count += 1
        self.last_access = (hive, path, reserved, access)
        if self.fail_with is not None:
            raise self.fail_with
        return self.handle

    def QueryInfoKey(self, handle):
        self.query_count += 1
        if handle is not self.handle:
            raise AssertionError("unexpected handle")
        return (0, len(self.values), 0)

    def QueryValueEx(self, handle, name):
        self.query_count += 1
        if name not in self.values:
            raise FileNotFoundError("missing value")
        return self.values[name]

    def CreateKey(self, *_):
        self.write_count += 1
        raise AssertionError("MUTATION_FORBIDDEN")

    def SetValueEx(self, *_):
        self.write_count += 1
        raise AssertionError("MUTATION_FORBIDDEN")

    def DeleteKey(self, *_):
        self.write_count += 1
        raise AssertionError("MUTATION_FORBIDDEN")


class HostAnchorReadOnlyTests(unittest.TestCase):
    def observe(self, reg, nonce=None):
        nonce = "a1" * 32 if nonce is None else nonce
        with patch.object(host.sys, "platform", "win32"), patch.dict(
            sys.modules, {"winreg": reg}
        ):
            return host.observe_owner_windows_host_anchor_readonly(nonce)

    def no_authority(self, result):
        for key in (
            "host_anchor_is_protected", "registry_acl_verified",
            "trusted_installer_identity_verified",
            "independent_host_policy_origin_verified",
            "hardware_antirollback_verified", "tpm_binding_verified",
            "owner_identity_verified", "physical_attestation_verified",
            "network_deny_verified", "safe_to_resume",
            "collector_launch_authorized", "installer_authorized",
            "build_authorized", "deploy_authorized",
            "trust_store_modified", "system_registry_modified",
            "source_path_was_user_controlled",
        ):
            self.assertIs(result[key], False, key)

    def test_absent_anchor_is_blocked(self):
        reg = FakeWinreg()
        reg.fail_with = FileNotFoundError("no key")
        out = self.observe(reg)
        self.assertEqual(out["state"], host.BLOCKED)
        self.assertEqual(out["reason"], "HOST_ANCHOR_ABSENT")
        self.assertEqual(reg.write_count, 0)
        self.no_authority(out)

    def test_read_denied_is_blocked(self):
        reg = FakeWinreg()
        reg.fail_with = PermissionError("read ACL")
        out = self.observe(reg)
        self.assertEqual(out["reason"], "HOST_ANCHOR_READ_DENIED")
        self.no_authority(out)

    def test_exact_scope_and_access_read_only(self):
        reg = FakeWinreg()
        out = self.observe(reg)
        self.assertEqual(out["state"], host.CANDIDATE, out)
        self.assertEqual(
            reg.last_access,
            (reg.HKEY_LOCAL_MACHINE, host.FIXED_HKLM_PATH,
             0, reg.KEY_READ | reg.KEY_WOW64_64KEY),
        )
        self.assertTrue(reg.handle.closed)
        self.assertEqual(reg.open_count, 1)
        self.assertEqual(reg.query_count, len(host.READ_VALUES) + 1)
        self.assertEqual(reg.write_count, 0)
        self.no_authority(out)

    def test_valid_shape_never_proves_acl_tpm_or_authenticity(self):
        reg = FakeWinreg()
        out = self.observe(reg)
        self.assertIs(out["native_registry_read_completed"], True)
        self.assertIs(out["anchor_schema_and_types_valid"], True)
        self.assertRegex(
            out["anchor_snapshot_observation_digest"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(out["policy_epoch_observed"], 4)
        self.assertNotIn("PolicyAuthorityPublicKey", out)
        self.assertNotIn("OwnerRegistryRootPublicKey", out)
        self.no_authority(out)

    def test_nonce_is_bound_but_not_proof(self):
        reg = FakeWinreg()
        a = self.observe(reg, "a1" * 32)
        b = self.observe(FakeWinreg(), "a2" * 32)
        self.assertEqual(
            a["anchor_snapshot_observation_digest"],
            b["anchor_snapshot_observation_digest"],
        )
        self.assertNotEqual(
            a["challenge_binding_digest"], b["challenge_binding_digest"]
        )
        self.no_authority(a)
        self.no_authority(b)

    def test_nonce_is_not_optional_or_fake(self):
        for nonce in ("", "0" * 63, "G" * 64, "0" * 64 + "F", None, 1):
            with self.subTest(nonce=nonce):
                reg = FakeWinreg()
                out = self.observe(reg, nonce=nonce)
                # observe() defaults None to a valid nonce, so use explicit
                # lower-level call for the None test below.
                if nonce is not None:
                    self.assertEqual(out["reason"], "EXPLICIT_256_BIT_CHALLENGE_REQUIRED")
                    self.assertEqual(reg.open_count, 0)
        with patch.object(host.sys, "platform", "win32"):
            out = host.observe_owner_windows_host_anchor_readonly(None)
        self.assertEqual(out["reason"], "EXPLICIT_256_BIT_CHALLENGE_REQUIRED")

    def test_non_windows_blocks_before_import(self):
        with patch.object(host.sys, "platform", "linux"):
            out = host.observe_owner_windows_host_anchor_readonly("aa" * 32)
        self.assertEqual(out["reason"], "WINDOWS_REQUIRED")
        self.no_authority(out)

    def test_extra_registry_value_denied(self):
        reg = FakeWinreg()
        reg.values["AutoActivate"] = (1, reg.REG_QWORD)
        out = self.observe(reg)
        self.assertEqual(out["reason"], "ANCHOR_VALUE_COUNT_INVALID")
        self.no_authority(out)

    def test_missing_registry_value_denied(self):
        reg = FakeWinreg()
        reg.values.pop("OwnerRegistryRootPublicKey")
        out = self.observe(reg)
        self.assertEqual(out["reason"], "ANCHOR_VALUE_COUNT_INVALID")
        self.no_authority(out)

    def test_wrong_schema_denied(self):
        reg = FakeWinreg()
        reg.values["AnchorSchema"] = ("OTHER", reg.REG_SZ)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_wrong_key_type_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyAuthorityPublicKey"] = (bytes(range(1, 33)), reg.REG_SZ)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_short_key_denied(self):
        reg = FakeWinreg()
        reg.values["OwnerRegistryRootPublicKey"] = (b"x" * 31, reg.REG_BINARY)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_zero_public_key_denied(self):
        reg = FakeWinreg()
        reg.values["OwnerRegistryRootPublicKey"] = (b"\x00" * 32, reg.REG_BINARY)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_signer_role_collision_denied(self):
        reg = FakeWinreg()
        reg.values["OwnerRegistryRootPublicKey"] = reg.values[
            "PolicyAuthorityPublicKey"]
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_wrong_policy_digest_denied(self):
        reg = FakeWinreg()
        reg.values["PolicySnapshotDigest"] = ("sha256:" + "g" * 64, reg.REG_SZ)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_invalid_policy_digest_type_denied(self):
        reg = FakeWinreg()
        reg.values["PolicySnapshotDigest"] = (b"x" * 32, reg.REG_BINARY)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_zero_epoch_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyEpoch"] = (0, reg.REG_QWORD)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_boolean_epoch_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyEpoch"] = (True, reg.REG_QWORD)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_epoch_overflow_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyEpoch"] = (2**63, reg.REG_QWORD)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_epoch_wrong_reg_type_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyEpoch"] = (4, reg.REG_DWORD if hasattr(reg, "REG_DWORD") else reg.REG_SZ)
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_unexpected_value_tuple_denied(self):
        reg = FakeWinreg()
        reg.values["PolicyEpoch"] = [4, reg.REG_QWORD]
        self.assertEqual(self.observe(reg)["reason"], "HOST_ANCHOR_SHAPE_INVALID")

    def test_native_read_error_does_not_report_presence(self):
        reg = FakeWinreg()
        reg.fail_with = OSError("device read error")
        out = self.observe(reg)
        self.assertEqual(out["reason"], "HOST_ANCHOR_READ_ERROR")
        self.assertIs(out["native_registry_read_completed"], False)

    def test_sanitized_observation_changes_when_anchor_rotates(self):
        first = FakeWinreg()
        second = FakeWinreg()
        second.values["PolicyEpoch"] = (5, second.REG_QWORD)
        a, b = self.observe(first), self.observe(second)
        self.assertNotEqual(
            a["anchor_snapshot_observation_digest"],
            b["anchor_snapshot_observation_digest"],
        )
        self.no_authority(b)

    def test_native_ci_windows_probe_observes_or_blocks_but_never_authorizes(self):
        if sys.platform != "win32":
            self.skipTest("native Windows-only read-only HKLM probe")
        out = host.observe_owner_windows_host_anchor_readonly(secrets.token_hex(32))
        self.assertIn(out["state"], (host.BLOCKED, host.CANDIDATE))
        if out["state"] == host.CANDIDATE:
            self.assertIs(out["native_registry_read_completed"], True)
        self.no_authority(out)


if __name__ == "__main__":
    unittest.main()
