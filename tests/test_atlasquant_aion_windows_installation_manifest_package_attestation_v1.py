import base64
import copy
import hashlib
import json
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    MANIFEST_SIGNATURE_CONTEXT,
    REQUIRED_PACKAGE_ROLES,
    ROLE_DESTINATIONS,
    build_installation_manifest,
    build_package_attestation,
    build_upgrade_preflight,
    build_uninstall_manifest,
    package_signer_fingerprint,
    windows_package_policy,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsInstallationManifestPackageAttestationV1Tests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        raw_public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.public_b64 = base64.b64encode(raw_public).decode("ascii")
        self.fingerprint = package_signer_fingerprint(self.public_b64)

    def entries(self):
        rows = []
        for index, role in enumerate(REQUIRED_PACKAGE_ROLES, start=1):
            rows.append({
                "role": role,
                "path": ROLE_DESTINATIONS[role],
                "sha256": "sha256:" + (format(index, "x")[-1] * 64),
                "size_bytes": 1000 + index,
                "executable": role == "AGENT_ENTRYPOINT",
                "contains_credentials": False,
                "contains_private_key": False,
                "contains_secret_locator": False,
                "contains_network_endpoint": False,
            })
        return rows

    def manifest(self, version="1.0.0", entries=None):
        return build_installation_manifest(
            entries or self.entries(),
            package_version=version,
            build_id=f"agent-build-{version}",
            build_commit_sha="a" * 40,
            minimum_windows_build=22621,
            python_runtime_version="3.12.12",
            created_at="2026-10-08T12:30:00+00:00",
        )

    def attestation(self, manifest=None, **changes):
        manifest = manifest or self.manifest()
        archive = D("8")
        sbom = D("9")
        provenance = D("a")
        dep_lock = D("b")
        signed_material = {
            "manifest_digest": manifest["manifest_digest"],
            "archive_digest": archive,
            "sbom_digest": sbom,
            "build_provenance_digest": provenance,
            "dependency_lock_digest": dep_lock,
            "package_family": manifest["package_family"],
            "package_version": manifest["package_version"],
            "build_id": manifest["build_id"],
            "build_commit_sha": manifest["build_commit_sha"],
        }
        payload_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                signed_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        signature = self.private.sign(
            MANIFEST_SIGNATURE_CONTEXT + payload_digest.encode("ascii")
        )
        kwargs = {
            "manifest": manifest,
            "archive_digest": archive,
            "sbom_digest": sbom,
            "build_provenance_digest": provenance,
            "dependency_lock_digest": dep_lock,
            "package_signer_public_key_b64": self.public_b64,
            "expected_package_signer_fingerprint": self.fingerprint,
            "detached_signature_b64": base64.b64encode(signature).decode("ascii"),
            "authenticode_binary_digest": D("c"),
            "authenticode_evidence_digest": D("d"),
            "authenticode_signature_verified": True,
            "authenticode_trusted_chain_verified": True,
            "authenticode_timestamp_verified": True,
            "authenticode_publisher_match_verified": True,
            "release_review_digest": D("e"),
            "attested_at": "2026-10-08T12:31:00+00:00",
        }
        kwargs.update(changes)
        return build_package_attestation(**kwargs)

    def test_exact_closed_manifest_is_ready(self):
        manifest = self.manifest()
        self.assertEqual(
            manifest["state"],
            "INSTALLATION_MANIFEST_READY",
            manifest["blockers"],
        )
        self.assertEqual(len(manifest["files"]), len(REQUIRED_PACKAGE_ROLES))
        self.assertTrue(manifest["closed_file_inventory"])
        self.assertFalse(manifest["extra_files_allowed"])
        self.assertFalse(manifest["credential_material_present"])
        self.assertFalse(manifest["private_key_material_present"])
        self.assertFalse(manifest["network_endpoint_material_present"])
        self.assertFalse(manifest["filesystem_modified"])
        self.assertFalse(manifest["package_built_by_this_module"])
        self.assertFalse(manifest["package_installed"])
        self.assertTrue(manifest["manifest_digest"].startswith("sha256:"))

    def test_missing_or_extra_file_blocks(self):
        missing = self.entries()[:-1]
        out = self.manifest(entries=missing)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "EXACT_REQUIRED_PACKAGE_FILE_COUNT_REQUIRED",
            out["blockers"],
        )
        self.assertIn("REQUIRED_PACKAGE_ROLES_MISMATCH", out["blockers"])

        extra = self.entries()
        extra.append({
            "role": "RUNTIME_POLICY",
            "path": ROLE_DESTINATIONS["RUNTIME_POLICY"],
            "sha256": D("f"),
            "size_bytes": 10,
            "executable": False,
            "contains_credentials": False,
            "contains_private_key": False,
            "contains_secret_locator": False,
            "contains_network_endpoint": False,
        })
        out2 = self.manifest(entries=extra)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn(
            "EXACT_REQUIRED_PACKAGE_FILE_COUNT_REQUIRED",
            out2["blockers"],
        )
        self.assertIn("DUPLICATE_PACKAGE_ROLE", out2["blockers"])
        self.assertIn("DUPLICATE_PACKAGE_PATH", out2["blockers"])

    def test_role_path_swap_or_traversal_blocks(self):
        rows = self.entries()
        rows[0] = dict(rows[0])
        rows[0]["path"] = "agent/../evil.py"
        out = self.manifest(entries=rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertTrue(
            any(
                value in (
                    "PACKAGE_PATH_TRAVERSAL_FORBIDDEN",
                    "PACKAGE_ROLE_PATH_MISMATCH:AGENT_ENTRYPOINT",
                )
                for value in out["blockers"]
            )
        )

        rows = self.entries()
        rows[1] = dict(rows[1])
        rows[1]["path"] = ROLE_DESTINATIONS["RUNTIME_HARDENING"]
        out2 = self.manifest(entries=rows)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn(
            "PACKAGE_ROLE_PATH_MISMATCH:REPOSITORY_MUTATION_RUNTIME",
            out2["blockers"],
        )

    def test_credential_private_key_endpoint_material_blocks(self):
        for field, expected in (
            ("contains_credentials", "PACKAGE_CREDENTIAL_MATERIAL_FORBIDDEN:AGENT_ENTRYPOINT"),
            ("contains_private_key", "PACKAGE_PRIVATE_KEY_MATERIAL_FORBIDDEN:AGENT_ENTRYPOINT"),
            ("contains_secret_locator", "PACKAGE_SECRET_LOCATOR_FORBIDDEN:AGENT_ENTRYPOINT"),
            ("contains_network_endpoint", "PACKAGE_NETWORK_ENDPOINT_FORBIDDEN:AGENT_ENTRYPOINT"),
        ):
            with self.subTest(field=field):
                rows = self.entries()
                rows[0] = dict(rows[0])
                rows[0][field] = True
                out = self.manifest(entries=rows)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_only_entrypoint_may_be_executable(self):
        rows = self.entries()
        rows[2] = dict(rows[2])
        rows[2]["executable"] = True
        out = self.manifest(entries=rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "UNEXPECTED_EXECUTABLE_PACKAGE_FILE:RUNTIME_HARDENING",
            out["blockers"],
        )

        rows = self.entries()
        rows[0] = dict(rows[0])
        rows[0]["executable"] = False
        out2 = self.manifest(entries=rows)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn(
            "AGENT_ENTRYPOINT_EXECUTABLE_FLAG_REQUIRED",
            out2["blockers"],
        )

    def test_package_attestation_verifies_release_signature_and_authenticode_evidence(self):
        att = self.attestation()
        self.assertEqual(
            att["state"],
            "PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED",
            att["blockers"],
        )
        self.assertTrue(att["manifest_signature_verified"])
        self.assertTrue(att["release_signature_verified"])
        self.assertEqual(att["package_signer_fingerprint"], self.fingerprint)
        self.assertTrue(att["authenticode_signature_verified"])
        self.assertTrue(att["authenticode_trusted_chain_verified"])
        self.assertTrue(att["authenticode_timestamp_verified"])
        self.assertTrue(att["authenticode_publisher_match_verified"])
        self.assertFalse(att["package_installed"])
        self.assertFalse(att["files_copied"])
        self.assertFalse(att["startup_entry_created"])
        self.assertFalse(att["windows_acl_modified"])
        self.assertFalse(att["process_spawned"])
        self.assertFalse(att["private_signing_key_loaded"])
        self.assertFalse(att["credential_material_loaded"])
        self.assertFalse(att["network_called"])
        self.assertFalse(att["github_api_called"])

    def test_wrong_release_signature_or_signer_blocks(self):
        manifest = self.manifest()
        wrong_private = Ed25519PrivateKey.generate()
        bad_signature = wrong_private.sign(
            MANIFEST_SIGNATURE_CONTEXT + D("1").encode("ascii")
        )
        bad = self.attestation(
            manifest,
            detached_signature_b64=base64.b64encode(bad_signature).decode("ascii"),
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertTrue(
            any(
                value in (
                    "PACKAGE_DETACHED_SIGNATURE_NOT_VERIFIED",
                    "PACKAGE_DETACHED_SIGNATURE_VERIFICATION_FAILED",
                )
                for value in bad["blockers"]
            )
        )

        other = Ed25519PrivateKey.generate()
        raw = other.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        other_b64 = base64.b64encode(raw).decode("ascii")
        bad2 = self.attestation(
            manifest,
            package_signer_public_key_b64=other_b64,
        )
        self.assertEqual(bad2["state"], "BLOCKED")
        self.assertIn("PACKAGE_SIGNER_FINGERPRINT_MISMATCH", bad2["blockers"])

    def test_missing_authenticode_evidence_blocks(self):
        bad = self.attestation(
            authenticode_signature_verified=False,
            authenticode_trusted_chain_verified=False,
            authenticode_timestamp_verified=False,
            authenticode_publisher_match_verified=False,
        )
        self.assertEqual(bad["state"], "BLOCKED")
        self.assertIn("AUTHENTICODE_SIGNATURE_REQUIRED", bad["blockers"])
        self.assertIn("AUTHENTICODE_TRUSTED_CHAIN_REQUIRED", bad["blockers"])
        self.assertIn("AUTHENTICODE_TIMESTAMP_REQUIRED", bad["blockers"])
        self.assertIn("AUTHENTICODE_PUBLISHER_MATCH_REQUIRED", bad["blockers"])

    def test_upgrade_preflight_allows_only_verified_forward_version(self):
        current = self.manifest("1.0.0")
        candidate = self.manifest("1.1.0")
        candidate_att = self.attestation(candidate)
        out = build_upgrade_preflight(
            current,
            candidate,
            candidate_att,
            current_package_attestation_digest=D("1"),
            rollback_archive_digest=D("2"),
            rollback_manifest_digest=D("3"),
        )
        self.assertEqual(
            out["state"],
            "UPGRADE_PACKAGE_READY_FOR_FUTURE_INSTALLATION_REVIEW",
            out["blockers"],
        )
        self.assertFalse(out["downgrade_allowed"])
        self.assertFalse(out["installation_authorized"])
        self.assertFalse(out["package_installed"])
        self.assertFalse(out["rollback_executed"])

    def test_downgrade_and_boolean_override_are_forbidden(self):
        current = self.manifest("2.0.0")
        candidate = self.manifest("1.9.9")
        candidate_att = self.attestation(candidate)
        out = build_upgrade_preflight(
            current,
            candidate,
            candidate_att,
            current_package_attestation_digest=D("1"),
            rollback_archive_digest=D("2"),
            rollback_manifest_digest=D("3"),
            owner_approved_downgrade=True,
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("PACKAGE_DOWNGRADE_FORBIDDEN", out["blockers"])
        self.assertIn("BOOLEAN_DOWNGRADE_OVERRIDE_FORBIDDEN", out["blockers"])

    def test_same_version_different_manifest_is_forbidden(self):
        current = self.manifest("1.0.0")
        rows = self.entries()
        rows[0] = dict(rows[0])
        rows[0]["sha256"] = D("0")
        candidate = self.manifest("1.0.0", entries=rows)
        candidate_att = self.attestation(candidate)
        out = build_upgrade_preflight(
            current,
            candidate,
            candidate_att,
            current_package_attestation_digest=D("1"),
            rollback_archive_digest=D("2"),
            rollback_manifest_digest=D("3"),
        )
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "SAME_VERSION_DIFFERENT_MANIFEST_FORBIDDEN",
            out["blockers"],
        )

    def test_uninstall_manifest_preserves_owner_evidence_by_default(self):
        manifest = self.manifest()
        att = self.attestation(manifest)
        uninstall = build_uninstall_manifest(
            manifest,
            att,
            startup_entry_digest=D("4"),
            owner_data_backup_policy_digest=D("5"),
            uninstall_review_digest=D("6"),
        )
        self.assertEqual(
            uninstall["state"],
            "UNINSTALL_MANIFEST_READY",
            uninstall["blockers"],
        )
        self.assertEqual(uninstall["runtime_database_action"], "PRESERVE")
        self.assertEqual(uninstall["audit_evidence_action"], "PRESERVE")
        self.assertEqual(
            uninstall["owner_key_enrollment_action"],
            "PRESERVE_UNTIL_SEPARATE_OWNER_PURGE",
        )
        self.assertEqual(
            uninstall["kill_switch_action"],
            "FORCE_ENABLED_BEFORE_UNINSTALL",
        )
        self.assertFalse(uninstall["owner_data_deleted_by_default"])
        self.assertFalse(uninstall["runtime_database_deleted_by_default"])
        self.assertFalse(uninstall["audit_evidence_deleted_by_default"])
        self.assertFalse(uninstall["owner_key_enrollment_deleted_by_default"])
        self.assertTrue(uninstall["separate_owner_purge_ceremony_required"])
        self.assertFalse(uninstall["uninstall_executed"])
        self.assertFalse(uninstall["files_deleted"])
        self.assertFalse(uninstall["startup_entry_removed"])
        self.assertFalse(uninstall["filesystem_modified"])

    def test_manifest_digest_changes_on_file_hash_tamper(self):
        first = self.manifest()
        rows = self.entries()
        rows[3] = dict(rows[3])
        rows[3]["sha256"] = D("0")
        second = self.manifest(entries=rows)
        self.assertEqual(second["state"], "INSTALLATION_MANIFEST_READY")
        self.assertNotEqual(first["manifest_digest"], second["manifest_digest"])

    def test_policy_is_supply_chain_strict_and_noninstalling(self):
        policy = windows_package_policy()
        self.assertTrue(policy["closed_file_inventory_required"])
        self.assertFalse(policy["extra_files_allowed"])
        self.assertTrue(policy["exact_role_path_binding_required"])
        self.assertTrue(policy["sha256_per_file_required"])
        self.assertTrue(policy["sbom_required"])
        self.assertTrue(policy["build_provenance_required"])
        self.assertTrue(policy["dependency_lock_digest_required"])
        self.assertTrue(policy["release_review_digest_required"])
        self.assertTrue(policy["detached_release_signature_required"])
        self.assertTrue(policy["authenticode_signature_required"])
        self.assertTrue(policy["authenticode_trusted_chain_required"])
        self.assertTrue(policy["authenticode_timestamp_required"])
        self.assertTrue(policy["authenticode_publisher_match_required"])
        self.assertTrue(policy["package_credentials_forbidden"])
        self.assertTrue(policy["package_private_keys_forbidden"])
        self.assertTrue(policy["package_secret_locators_forbidden"])
        self.assertTrue(policy["package_network_endpoints_forbidden"])
        self.assertTrue(policy["anti_downgrade_required"])
        self.assertFalse(policy["boolean_downgrade_override_allowed"])
        self.assertFalse(policy["same_version_different_manifest_allowed"])
        self.assertTrue(policy["rollback_archive_required_before_upgrade"])
        self.assertTrue(
            policy["owner_data_preserved_on_uninstall_by_default"]
        )
        self.assertTrue(
            policy["runtime_database_preserved_on_uninstall_by_default"]
        )
        self.assertTrue(
            policy["audit_evidence_preserved_on_uninstall_by_default"]
        )
        self.assertTrue(policy["separate_owner_purge_required"])
        self.assertFalse(policy["package_built_by_this_module"])
        self.assertFalse(policy["package_installed"])
        self.assertFalse(policy["files_copied"])
        self.assertFalse(policy["windows_service_installed"])
        self.assertFalse(policy["scheduled_task_installed"])
        self.assertFalse(policy["startup_entry_created"])
        self.assertFalse(policy["windows_acl_modified"])
        self.assertFalse(policy["windows_registry_modified"])
        self.assertFalse(policy["process_spawned"])
        self.assertFalse(policy["uninstall_executed"])
        self.assertFalse(policy["private_signing_key_loaded"])
        self.assertFalse(policy["credential_material_loaded"])
        self.assertFalse(policy["network_called"])
        self.assertFalse(policy["github_api_called"])
        self.assertFalse(policy["live_repository_mutation_authorized"])
        self.assertFalse(policy["live_repository_mutation_performed"])
        self.assertFalse(policy["production_repository_mutation_performed"])
        self.assertFalse(policy["deploy_executed"])
        self.assertFalse(policy["worker_activated"])
        self.assertFalse(policy["provider_activated"])
        self.assertFalse(policy["production_persistence_activated"])


if __name__ == "__main__":
    unittest.main()
