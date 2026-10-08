import copy
import unittest

from atlasquant_aion_windows_local_agent_reproducible_build_contract_v1 import (
    build_dependency_lock,
)
from atlasquant_aion_windows_build_input_offline_cache_attestation_v1 import (
    CFFI_VERSION,
    PYCPARSER_VERSION,
    EXPECTED_ROLES,
    build_input_snapshot,
    attest_offline_cache,
    build_offline_input_promotion,
    offline_cache_policy,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsBuildInputOfflineCacheAttestationV1Tests(unittest.TestCase):
    def lock(self):
        out = build_dependency_lock()
        self.assertEqual(out["state"], "BUILD_DEPENDENCY_LOCK_READY")
        return out

    def artifacts(self):
        specs = {
            "PYTHON_RUNTIME": (
                "python",
                "3.12.12",
                "RUNTIME_ZIP",
                "python-3.12.12-embed-amd64.zip",
            ),
            "PIP_WHEEL": (
                "pip",
                "26.2.1",
                "WHEEL",
                "pip-26.2.1-py3-none-any.whl",
            ),
            "CRYPTOGRAPHY_WHEEL": (
                "cryptography",
                "50.0.2",
                "WHEEL",
                "cryptography-50.0.2-cp311-abi3-win_amd64.whl",
            ),
            "CFFI_WHEEL": (
                "cffi",
                CFFI_VERSION,
                "WHEEL",
                "cffi-2.1.1-cp312-cp312-win_amd64.whl",
            ),
            "PYCPARSER_WHEEL": (
                "pycparser",
                PYCPARSER_VERSION,
                "WHEEL",
                "pycparser-3.1-py3-none-any.whl",
            ),
        }
        markers = dict(zip(EXPECTED_ROLES, "12345"))
        rows = []
        for role in EXPECTED_ROLES:
            project, version, kind, filename = specs[role]
            marker = markers[role]
            rows.append(
                {
                    "role": role,
                    "project_name": project,
                    "version": version,
                    "artifact_kind": kind,
                    "filename": filename,
                    "expected_sha256": D(marker),
                    "observed_sha256": D(marker),
                    "size_bytes": 10000 + len(rows),
                    "source_metadata_digest": D("6"),
                    "package_metadata_digest": D("7"),
                    "acquisition_receipt_digest": D("8"),
                    "download_transport_verified": True,
                    "trusted_source_snapshot_verified": True,
                    "compiled_from_source": False,
                    "sdist": False,
                    "contains_credentials": False,
                    "contains_private_keys": False,
                }
            )
        return rows

    def snapshot(self, artifacts=None):
        out = build_input_snapshot(
            self.lock(),
            artifacts if artifacts is not None else self.artifacts(),
            trusted_python_release_snapshot_digest=D("9"),
            trusted_python_package_index_snapshot_digest=D("a"),
            resolver_evidence_digest=D("b"),
            acquisition_environment_digest=D("c"),
            snapshot_created_at="2026-10-08T14:00:00+00:00",
        )
        return out

    def observed_cache(self, snapshot):
        return [
            {
                "role": row["role"],
                "filename": row["filename"],
                "sha256": row["expected_sha256"],
                "size_bytes": row["size_bytes"],
            }
            for row in snapshot["artifacts"]
        ]

    def cache_attestation(self, snapshot, observed=None, **changes):
        kwargs = {
            "snapshot": snapshot,
            "observed_cache_files": (
                observed if observed is not None else self.observed_cache(snapshot)
            ),
            "cache_root_evidence_digest": D("d"),
            "cache_acl_attestation_digest": D("e"),
            "cache_manifest_digest": D("f"),
            "cache_read_only_verified": True,
            "owner_only_acl_verified": True,
            "no_extra_files_verified": True,
            "no_symlinks_verified": True,
            "no_reparse_points_verified": True,
            "no_alternate_data_streams_verified": True,
            "cache_network_isolation_verified": True,
            "attested_at": "2026-10-08T14:05:00+00:00",
        }
        kwargs.update(changes)
        return attest_offline_cache(**kwargs)

    def test_exact_closed_snapshot_is_ready(self):
        snapshot = self.snapshot()
        self.assertEqual(
            snapshot["state"],
            "BUILD_INPUT_SNAPSHOT_READY",
            snapshot["blockers"],
        )
        self.assertEqual(snapshot["artifact_count"], 5)
        self.assertEqual(
            {row["role"] for row in snapshot["artifacts"]},
            set(EXPECTED_ROLES),
        )
        self.assertTrue(snapshot["dependency_graph_closed"])
        self.assertTrue(snapshot["all_artifact_hashes_verified"])
        self.assertEqual(
            snapshot["dependency_graph"]["CRYPTOGRAPHY_WHEEL"],
            ["CFFI_WHEEL"],
        )
        self.assertEqual(
            snapshot["dependency_graph"]["CFFI_WHEEL"],
            ["PYCPARSER_WHEEL"],
        )
        self.assertFalse(snapshot["sdist_allowed"])
        self.assertFalse(snapshot["build_from_source_allowed"])
        self.assertFalse(snapshot["network_called"])
        self.assertFalse(snapshot["artifact_downloaded_by_this_module"])
        self.assertFalse(snapshot["dependency_resolved_by_this_module"])
        self.assertFalse(snapshot["package_installed"])

    def test_snapshot_digest_is_order_independent(self):
        rows = self.artifacts()
        first = self.snapshot(rows)
        second = self.snapshot(list(reversed(rows)))
        self.assertEqual(first["state"], "BUILD_INPUT_SNAPSHOT_READY")
        self.assertEqual(second["state"], "BUILD_INPUT_SNAPSHOT_READY")
        self.assertEqual(
            first["input_snapshot_digest"],
            second["input_snapshot_digest"],
        )

    def test_missing_transitive_dependency_blocks(self):
        rows = [
            row for row in self.artifacts()
            if row["role"] != "PYCPARSER_WHEEL"
        ]
        out = self.snapshot(rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXACT_CACHE_ARTIFACT_COUNT_REQUIRED", out["blockers"])
        self.assertIn("CACHE_ARTIFACT_ROLE_SET_MISMATCH", out["blockers"])
        self.assertIn(
            "TRANSITIVE_DEPENDENCY_MISSING:CFFI_WHEEL->PYCPARSER_WHEEL",
            out["blockers"],
        )

    def test_extra_or_duplicate_artifact_blocks(self):
        rows = self.artifacts()
        rows.append(copy.deepcopy(rows[1]))
        out = self.snapshot(rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("EXACT_CACHE_ARTIFACT_COUNT_REQUIRED", out["blockers"])
        self.assertIn("DUPLICATE_CACHE_ARTIFACT_ROLE", out["blockers"])
        self.assertIn("DUPLICATE_CACHE_ARTIFACT_FILENAME", out["blockers"])

    def test_hash_mismatch_blocks(self):
        rows = self.artifacts()
        rows[2] = dict(rows[2])
        rows[2]["observed_sha256"] = D("0")
        out = self.snapshot(rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CACHE_ARTIFACT_HASH_MISMATCH:CRYPTOGRAPHY_WHEEL",
            out["blockers"],
        )

    def test_wrong_version_or_filename_blocks(self):
        rows = self.artifacts()
        rows[3] = dict(rows[3])
        rows[3]["version"] = "2.1.0"
        out = self.snapshot(rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn(
            "CACHE_ARTIFACT_VERSION_MISMATCH:CFFI_WHEEL",
            out["blockers"],
        )

        rows = self.artifacts()
        rows[4] = dict(rows[4])
        rows[4]["filename"] = "pycparser-3.1.tar.gz"
        out2 = self.snapshot(rows)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertTrue(
            any(
                blocker.startswith("CACHE_ARTIFACT_FILENAME_MISMATCH:")
                or blocker == "CACHE_ARTIFACT_FILENAME_INVALID"
                for blocker in out2["blockers"]
            )
        )

    def test_sdist_and_build_from_source_are_forbidden(self):
        rows = self.artifacts()
        rows[2] = dict(rows[2])
        rows[2]["sdist"] = True
        out = self.snapshot(rows)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SDIST_FORBIDDEN:CRYPTOGRAPHY_WHEEL", out["blockers"])

        rows = self.artifacts()
        rows[3] = dict(rows[3])
        rows[3]["compiled_from_source"] = True
        out2 = self.snapshot(rows)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn("BUILD_FROM_SOURCE_FORBIDDEN:CFFI_WHEEL", out2["blockers"])

    def test_acquisition_evidence_is_required_per_artifact(self):
        fields = (
            ("source_metadata_digest", "SOURCE_METADATA_DIGEST_REQUIRED:"),
            ("package_metadata_digest", "PACKAGE_METADATA_DIGEST_REQUIRED:"),
            ("acquisition_receipt_digest", "ACQUISITION_RECEIPT_DIGEST_REQUIRED:"),
        )
        for field, prefix in fields:
            with self.subTest(field=field):
                rows = self.artifacts()
                rows[0] = dict(rows[0])
                rows[0][field] = ""
                out = self.snapshot(rows)
                self.assertEqual(out["state"], "BLOCKED")
                self.assertTrue(
                    any(blocker.startswith(prefix) for blocker in out["blockers"])
                )

    def test_offline_cache_attestation_is_exact_read_only_and_network_isolated(self):
        snapshot = self.snapshot()
        cache = self.cache_attestation(snapshot)
        self.assertEqual(
            cache["state"],
            "OFFLINE_DEPENDENCY_CACHE_ATTESTED",
            cache["blockers"],
        )
        self.assertTrue(cache["cache_read_only_verified"])
        self.assertTrue(cache["owner_only_acl_verified"])
        self.assertTrue(cache["no_extra_files_verified"])
        self.assertTrue(cache["no_symlinks_verified"])
        self.assertTrue(cache["no_reparse_points_verified"])
        self.assertTrue(cache["no_alternate_data_streams_verified"])
        self.assertTrue(cache["cache_network_isolation_verified"])
        self.assertTrue(cache["cache_tree_digest"].startswith("sha256:"))
        self.assertFalse(cache["cache_mutation_allowed_after_attestation"])
        self.assertFalse(cache["network_called"])
        self.assertFalse(cache["files_copied_by_this_module"])
        self.assertFalse(cache["packages_installed"])
        self.assertFalse(cache["build_started"])

    def test_cache_tree_digest_is_order_independent(self):
        snapshot = self.snapshot()
        observed = self.observed_cache(snapshot)
        first = self.cache_attestation(snapshot, observed)
        second = self.cache_attestation(snapshot, list(reversed(observed)))
        self.assertEqual(first["state"], "OFFLINE_DEPENDENCY_CACHE_ATTESTED")
        self.assertEqual(second["state"], "OFFLINE_DEPENDENCY_CACHE_ATTESTED")
        self.assertEqual(first["cache_tree_digest"], second["cache_tree_digest"])

    def test_cache_hash_size_or_filename_drift_blocks(self):
        snapshot = self.snapshot()

        observed = self.observed_cache(snapshot)
        observed[0] = dict(observed[0])
        observed[0]["sha256"] = D("0")
        out = self.cache_attestation(snapshot, observed)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("CACHE_HASH_DRIFT:PYTHON_RUNTIME", out["blockers"])

        observed = self.observed_cache(snapshot)
        observed[1] = dict(observed[1])
        observed[1]["size_bytes"] += 1
        out2 = self.cache_attestation(snapshot, observed)
        self.assertEqual(out2["state"], "BLOCKED")
        self.assertIn("CACHE_SIZE_DRIFT:PIP_WHEEL", out2["blockers"])

        observed = self.observed_cache(snapshot)
        observed[4] = dict(observed[4])
        observed[4]["filename"] = "pycparser-3.1-py3-none-any-copy.whl"
        out3 = self.cache_attestation(snapshot, observed)
        self.assertEqual(out3["state"], "BLOCKED")
        self.assertIn("CACHE_FILENAME_DRIFT:PYCPARSER_WHEEL", out3["blockers"])

    def test_cache_symlink_reparse_ads_or_mutability_blocks(self):
        snapshot = self.snapshot()
        cases = (
            ("cache_read_only_verified", "CACHE_READ_ONLY_VERIFICATION_REQUIRED"),
            ("owner_only_acl_verified", "CACHE_OWNER_ONLY_ACL_REQUIRED"),
            ("no_symlinks_verified", "CACHE_NO_SYMLINKS_REQUIRED"),
            ("no_reparse_points_verified", "CACHE_NO_REPARSE_POINTS_REQUIRED"),
            (
                "no_alternate_data_streams_verified",
                "CACHE_NO_ALTERNATE_DATA_STREAMS_REQUIRED",
            ),
            (
                "cache_network_isolation_verified",
                "CACHE_NETWORK_ISOLATION_REQUIRED",
            ),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                out = self.cache_attestation(snapshot, **{field: False})
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_unexpected_cache_file_blocks(self):
        snapshot = self.snapshot()
        observed = self.observed_cache(snapshot)
        observed.append(
            {
                "role": "EVIL_WHEEL",
                "filename": "evil-1.0.0-py3-none-any.whl",
                "sha256": D("0"),
                "size_bytes": 123,
            }
        )
        out = self.cache_attestation(snapshot, observed)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("OBSERVED_CACHE_FILE_COUNT_MISMATCH", out["blockers"])
        self.assertIn("UNEXPECTED_CACHE_FILE_ROLE:EVIL_WHEEL", out["blockers"])

    def test_promotion_binds_lock_snapshot_cache_and_recipe_without_starting_build(self):
        lock = self.lock()
        snapshot = build_input_snapshot(
            lock,
            self.artifacts(),
            trusted_python_release_snapshot_digest=D("9"),
            trusted_python_package_index_snapshot_digest=D("a"),
            resolver_evidence_digest=D("b"),
            acquisition_environment_digest=D("c"),
            snapshot_created_at="2026-10-08T14:00:00+00:00",
        )
        cache = self.cache_attestation(snapshot)
        promotion = build_offline_input_promotion(
            lock,
            snapshot,
            cache,
            reproducible_build_recipe_digest=D("1"),
            promotion_review_digest=D("2"),
        )
        self.assertEqual(
            promotion["state"],
            "OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD",
            promotion["blockers"],
        )
        self.assertFalse(promotion["build_authorized"])
        self.assertFalse(promotion["build_started"])
        self.assertFalse(promotion["package_built"])
        self.assertFalse(promotion["package_installed"])
        self.assertFalse(promotion["cache_mutation_allowed"])
        self.assertFalse(promotion["dependency_resolution_allowed"])
        self.assertFalse(promotion["network_allowed"])
        self.assertFalse(promotion["network_called"])
        self.assertFalse(promotion["github_api_called"])

    def test_policy_remains_closed_offline_and_non_building(self):
        policy = offline_cache_policy()
        self.assertEqual(policy["cffi_version"], CFFI_VERSION)
        self.assertEqual(policy["pycparser_version"], PYCPARSER_VERSION)
        self.assertTrue(policy["closed_dependency_graph_required"])
        self.assertTrue(policy["exact_artifact_count_required"])
        self.assertTrue(policy["sha256_expected_and_observed_required"])
        self.assertTrue(policy["trusted_source_snapshot_required"])
        self.assertTrue(policy["acquisition_receipt_required"])
        self.assertTrue(policy["package_metadata_digest_required"])
        self.assertTrue(policy["download_transport_verification_required"])
        self.assertFalse(policy["sdist_allowed"])
        self.assertFalse(policy["build_from_source_allowed"])
        self.assertFalse(policy["extra_cache_files_allowed"])
        self.assertTrue(policy["cache_read_only_after_attestation"])
        self.assertTrue(policy["owner_only_cache_acl_required"])
        self.assertFalse(policy["symlinks_allowed"])
        self.assertFalse(policy["reparse_points_allowed"])
        self.assertFalse(policy["alternate_data_streams_allowed"])
        self.assertFalse(policy["network_during_cache_attestation_allowed"])
        self.assertFalse(policy["network_during_reproducible_build_allowed"])
        self.assertFalse(policy["cache_mutation_after_attestation_allowed"])
        self.assertFalse(policy["dependency_resolution_from_cache_allowed"])
        self.assertFalse(policy["artifact_downloaded_by_this_module"])
        self.assertFalse(policy["dependency_resolved_by_this_module"])
        self.assertFalse(policy["files_copied_by_this_module"])
        self.assertFalse(policy["packages_installed"])
        self.assertFalse(policy["build_authorized"])
        self.assertFalse(policy["build_started"])
        self.assertFalse(policy["package_built"])
        self.assertFalse(policy["package_installed"])
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
