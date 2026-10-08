import copy
import unittest

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    REQUIRED_PACKAGE_ROLES,
    ROLE_DESTINATIONS,
    build_installation_manifest,
)
from atlasquant_aion_windows_local_agent_reproducible_build_contract_v1 import (
    CRYPTOGRAPHY_VERSION,
    PIP_VERSION,
    PYTHON_VERSION,
    PINNED_BUILD_DEPENDENCIES,
    build_dependency_lock,
    build_source_set,
    build_reproducible_recipe,
    build_observation,
    compare_independent_builds,
    reproducible_build_policy,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsLocalAgentReproducibleBuildContractV1Tests(unittest.TestCase):
    def entries(self):
        rows = []
        hexes = ("1", "2", "3", "4", "5", "6", "7")
        for role, marker in zip(REQUIRED_PACKAGE_ROLES, hexes):
            rows.append(
                {
                    "role": role,
                    "path": ROLE_DESTINATIONS[role],
                    "sha256": D(marker),
                    "size_bytes": 1000 + len(rows),
                    "executable": role == "AGENT_ENTRYPOINT",
                    "contains_credentials": False,
                    "contains_private_key": False,
                    "contains_secret_locator": False,
                    "contains_network_endpoint": False,
                }
            )
        return rows

    def manifest(self):
        out = build_installation_manifest(
            self.entries(),
            package_version="1.0.0",
            build_id="agent-repro-build-1",
            build_commit_sha="a" * 40,
            minimum_windows_build=22621,
            python_runtime_version=PYTHON_VERSION,
            created_at="2026-10-08T13:00:00+00:00",
        )
        self.assertEqual(
            out["state"],
            "INSTALLATION_MANIFEST_READY",
            out["blockers"],
        )
        return out

    def recipe(self):
        manifest = self.manifest()
        lock = build_dependency_lock()
        sources = build_source_set(manifest)
        recipe = build_reproducible_recipe(
            manifest,
            lock,
            sources,
            source_date_epoch=1791446400,
            recipe_revision=1,
            builder_image_digest=D("8"),
            build_script_digest=D("9"),
            sbom_recipe_digest=D("a"),
            provenance_recipe_digest=D("b"),
        )
        self.assertEqual(
            lock["state"],
            "BUILD_DEPENDENCY_LOCK_READY",
            lock["blockers"],
        )
        self.assertEqual(
            sources["state"],
            "BUILD_SOURCE_SET_READY",
            sources["blockers"],
        )
        self.assertEqual(
            recipe["state"],
            "REPRODUCIBLE_BUILD_RECIPE_READY",
            recipe["blockers"],
        )
        return manifest, lock, sources, recipe

    def observation(
        self,
        recipe,
        *,
        observation_id,
        observed_at,
        archive=D("c"),
        manifest=D("d"),
        sbom=D("e"),
        provenance=D("f"),
        tree=D("0"),
        **changes,
    ):
        kwargs = {
            "recipe": recipe,
            "build_observation_id": observation_id,
            "output_archive_digest": archive,
            "output_manifest_digest": manifest,
            "output_sbom_digest": sbom,
            "output_provenance_digest": provenance,
            "output_tree_digest": tree,
            "builder_image_digest": recipe["builder_image_digest"],
            "build_script_digest": recipe["build_script_digest"],
            "dependency_lock_digest": recipe["dependency_lock_digest"],
            "source_set_digest": recipe["source_set_digest"],
            "source_date_epoch": recipe["source_date_epoch_normalized"],
            "normalized_member_metadata_verified": True,
            "no_extra_files_verified": True,
            "no_host_specific_metadata_verified": True,
            "no_credentials_verified": True,
            "no_private_keys_verified": True,
            "network_not_used_verified": True,
            "observed_at": observed_at,
        }
        kwargs.update(changes)
        return build_observation(**kwargs)

    def test_dependency_lock_is_exact_and_minimal(self):
        lock = build_dependency_lock()
        self.assertEqual(lock["state"], "BUILD_DEPENDENCY_LOCK_READY")
        self.assertEqual(lock["python_version"], PYTHON_VERSION)
        self.assertEqual(
            {row["name"]: row["version"] for row in lock["dependencies"]},
            {"pip": PIP_VERSION, "cryptography": CRYPTOGRAPHY_VERSION},
        )
        self.assertTrue(lock["all_versions_exactly_pinned"])
        self.assertFalse(lock["network_install_allowed_during_build"])
        self.assertFalse(lock["resolver_mutation_allowed"])
        self.assertFalse(lock["dependency_upgrade_allowed"])
        self.assertFalse(lock["dependencies_installed_by_this_module"])
        self.assertFalse(lock["network_called"])

    def test_dependency_drift_or_extra_package_blocks(self):
        drift = build_dependency_lock(
            [
                {"name": "pip", "version": PIP_VERSION, "source": "PYPI_PINNED"},
                {
                    "name": "cryptography",
                    "version": "50.0.1",
                    "source": "PYPI_PINNED",
                },
            ]
        )
        self.assertEqual(drift["state"], "BLOCKED")
        self.assertIn("BUILD_DEPENDENCY_LOCK_DRIFT", drift["blockers"])

        extra = build_dependency_lock(
            list(PINNED_BUILD_DEPENDENCIES)
            + [{"name": "requests", "version": "2.34.2", "source": "PYPI_PINNED"}]
        )
        self.assertEqual(extra["state"], "BLOCKED")
        self.assertIn("BUILD_DEPENDENCY_LOCK_DRIFT", extra["blockers"])

    def test_source_set_is_exact_sorted_and_mode_normalized(self):
        manifest = self.manifest()
        sources = build_source_set(manifest)
        self.assertEqual(sources["state"], "BUILD_SOURCE_SET_READY")
        self.assertEqual(len(sources["sources"]), len(REQUIRED_PACKAGE_ROLES))
        paths = [row["path"] for row in sources["sources"]]
        self.assertEqual(paths, sorted(paths, key=lambda p: p.encode("utf-8")))
        entrypoint = next(
            row for row in sources["sources"]
            if row["role"] == "AGENT_ENTRYPOINT"
        )
        self.assertEqual(entrypoint["normalized_mode"], 0o755)
        for row in sources["sources"]:
            if row["role"] != "AGENT_ENTRYPOINT":
                self.assertEqual(row["normalized_mode"], 0o644)
        self.assertFalse(sources["source_contents_modified"])
        self.assertFalse(sources["extra_sources_allowed"])
        self.assertFalse(sources["host_paths_embedded"])
        self.assertFalse(sources["credentials_embedded"])
        self.assertFalse(sources["private_keys_embedded"])

    def test_recipe_normalizes_nondeterministic_environment(self):
        _, _, _, recipe = self.recipe()
        self.assertEqual(recipe["python_version"], PYTHON_VERSION)
        self.assertEqual(recipe["pip_version"], PIP_VERSION)
        self.assertEqual(recipe["cryptography_version"], CRYPTOGRAPHY_VERSION)
        self.assertEqual(recipe["environment"]["TZ"], "UTC")
        self.assertEqual(recipe["environment"]["LC_ALL"], "C.UTF-8")
        self.assertEqual(recipe["environment"]["LANG"], "C.UTF-8")
        self.assertEqual(recipe["environment"]["PYTHONHASHSEED"], "0")
        self.assertEqual(
            recipe["environment"]["SOURCE_DATE_EPOCH"],
            "1791446400",
        )
        self.assertEqual(
            recipe["source_order"],
            "UTF8_BYTEWISE_ASCENDING_PATH",
        )
        self.assertEqual(
            recipe["archive_member_timestamp"],
            "SOURCE_DATE_EPOCH_UTC",
        )
        self.assertEqual(recipe["line_endings"], "LF")
        self.assertFalse(recipe["wall_clock_time_embedded"])
        self.assertFalse(recipe["host_username_embedded"])
        self.assertFalse(recipe["host_path_embedded"])
        self.assertFalse(recipe["runner_identity_embedded"])
        self.assertFalse(recipe["random_seed_uncontrolled"])
        self.assertFalse(recipe["network_during_build_allowed"])
        self.assertFalse(recipe["dependency_resolution_during_build_allowed"])
        self.assertFalse(recipe["production_package_built_by_this_module"])
        self.assertFalse(recipe["subprocess_spawned"])
        self.assertFalse(recipe["filesystem_modified"])
        self.assertFalse(recipe["network_called"])

    def test_invalid_source_date_epoch_blocks(self):
        manifest = self.manifest()
        lock = build_dependency_lock()
        sources = build_source_set(manifest)
        recipe = build_reproducible_recipe(
            manifest,
            lock,
            sources,
            source_date_epoch=1,
            recipe_revision=1,
            builder_image_digest=D("8"),
            build_script_digest=D("9"),
            sbom_recipe_digest=D("a"),
            provenance_recipe_digest=D("b"),
        )
        self.assertEqual(recipe["state"], "BLOCKED")
        self.assertIn("SOURCE_DATE_EPOCH_OUT_OF_RANGE", recipe["blockers"])

    def test_two_independent_observations_match_despite_different_observation_time(self):
        _, _, _, recipe = self.recipe()
        first = self.observation(
            recipe,
            observation_id="independent-build-a",
            observed_at="2026-10-08T13:10:00+00:00",
        )
        second = self.observation(
            recipe,
            observation_id="independent-build-b",
            observed_at="2026-10-08T13:20:00+00:00",
        )
        self.assertEqual(first["state"], "BUILD_OBSERVATION_VALID")
        self.assertEqual(second["state"], "BUILD_OBSERVATION_VALID")
        self.assertNotEqual(
            first["build_observation_digest"],
            second["build_observation_digest"],
        )
        self.assertEqual(
            first["reproducibility_fingerprint"],
            second["reproducibility_fingerprint"],
        )

        cert = compare_independent_builds(
            recipe,
            first,
            second,
            independent_builders_verified=True,
            independent_workdirs_verified=True,
            clean_build_roots_verified=True,
        )
        self.assertEqual(
            cert["state"],
            "TWO_BUILD_REPRODUCIBILITY_CONFIRMED",
            cert["blockers"],
        )
        self.assertTrue(cert["bit_for_bit_reproducibility_confirmed"])
        self.assertEqual(cert["mismatches"], [])
        self.assertFalse(cert["installation_authorized"])
        self.assertFalse(cert["release_authorized"])
        self.assertFalse(cert["production_package_built_by_this_module"])
        self.assertFalse(cert["package_installed"])
        self.assertFalse(cert["network_called"])
        self.assertFalse(cert["github_api_called"])

    def test_archive_digest_difference_blocks_reproducibility(self):
        _, _, _, recipe = self.recipe()
        first = self.observation(
            recipe,
            observation_id="build-a",
            observed_at="2026-10-08T13:10:00+00:00",
            archive=D("c"),
        )
        second = self.observation(
            recipe,
            observation_id="build-b",
            observed_at="2026-10-08T13:20:00+00:00",
            archive=D("1"),
        )
        cert = compare_independent_builds(
            recipe,
            first,
            second,
            independent_builders_verified=True,
            independent_workdirs_verified=True,
            clean_build_roots_verified=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "REPRODUCIBILITY_MISMATCH:output_archive_digest",
            cert["blockers"],
        )
        self.assertIn(
            "REPRODUCIBILITY_MISMATCH:reproducibility_fingerprint",
            cert["blockers"],
        )
        self.assertFalse(cert["bit_for_bit_reproducibility_confirmed"])

    def test_sbom_or_provenance_difference_blocks(self):
        _, _, _, recipe = self.recipe()
        first = self.observation(
            recipe,
            observation_id="build-a",
            observed_at="2026-10-08T13:10:00+00:00",
        )
        second = self.observation(
            recipe,
            observation_id="build-b",
            observed_at="2026-10-08T13:20:00+00:00",
            sbom=D("1"),
            provenance=D("2"),
        )
        cert = compare_independent_builds(
            recipe,
            first,
            second,
            independent_builders_verified=True,
            independent_workdirs_verified=True,
            clean_build_roots_verified=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "REPRODUCIBILITY_MISMATCH:output_sbom_digest",
            cert["blockers"],
        )
        self.assertIn(
            "REPRODUCIBILITY_MISMATCH:output_provenance_digest",
            cert["blockers"],
        )

    def test_build_observation_rejects_changed_builder_script_lock_or_epoch(self):
        _, _, _, recipe = self.recipe()
        cases = (
            ({"builder_image_digest": D("1")}, "BUILDER_IMAGE_DIGEST_MISMATCH"),
            ({"build_script_digest": D("1")}, "BUILD_SCRIPT_DIGEST_MISMATCH"),
            ({"dependency_lock_digest": D("1")}, "DEPENDENCY_LOCK_DIGEST_MISMATCH"),
            ({"source_set_digest": D("1")}, "SOURCE_SET_DIGEST_MISMATCH"),
            ({"source_date_epoch": 1791446401}, "SOURCE_DATE_EPOCH_MISMATCH"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                out = self.observation(
                    recipe,
                    observation_id="binding-test",
                    observed_at="2026-10-08T13:10:00+00:00",
                    **changes,
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_build_observation_requires_no_host_or_secret_leakage(self):
        _, _, _, recipe = self.recipe()
        cases = (
            ("normalized_member_metadata_verified", "NORMALIZED_MEMBER_METADATA_REQUIRED"),
            ("no_extra_files_verified", "NO_EXTRA_FILES_VERIFICATION_REQUIRED"),
            ("no_host_specific_metadata_verified", "NO_HOST_METADATA_VERIFICATION_REQUIRED"),
            ("no_credentials_verified", "NO_CREDENTIALS_VERIFICATION_REQUIRED"),
            ("no_private_keys_verified", "NO_PRIVATE_KEYS_VERIFICATION_REQUIRED"),
            ("network_not_used_verified", "BUILD_NETWORK_ABSENCE_VERIFICATION_REQUIRED"),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                out = self.observation(
                    recipe,
                    observation_id="leak-test",
                    observed_at="2026-10-08T13:10:00+00:00",
                    **{field: False},
                )
                self.assertEqual(out["state"], "BLOCKED")
                self.assertIn(expected, out["blockers"])

    def test_independence_proof_is_required(self):
        _, _, _, recipe = self.recipe()
        first = self.observation(
            recipe,
            observation_id="build-a",
            observed_at="2026-10-08T13:10:00+00:00",
        )
        second = self.observation(
            recipe,
            observation_id="build-b",
            observed_at="2026-10-08T13:20:00+00:00",
        )
        cert = compare_independent_builds(
            recipe,
            first,
            second,
            independent_builders_verified=False,
            independent_workdirs_verified=False,
            clean_build_roots_verified=False,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn("INDEPENDENT_BUILDERS_REQUIRED", cert["blockers"])
        self.assertIn("INDEPENDENT_WORKDIRS_REQUIRED", cert["blockers"])
        self.assertIn("CLEAN_BUILD_ROOTS_REQUIRED", cert["blockers"])

    def test_same_observation_id_cannot_fake_two_builds(self):
        _, _, _, recipe = self.recipe()
        first = self.observation(
            recipe,
            observation_id="same-build",
            observed_at="2026-10-08T13:10:00+00:00",
        )
        second = self.observation(
            recipe,
            observation_id="same-build",
            observed_at="2026-10-08T13:20:00+00:00",
        )
        cert = compare_independent_builds(
            recipe,
            first,
            second,
            independent_builders_verified=True,
            independent_workdirs_verified=True,
            clean_build_roots_verified=True,
        )
        self.assertEqual(cert["state"], "BLOCKED")
        self.assertIn(
            "INDEPENDENT_BUILD_OBSERVATION_IDS_REQUIRED",
            cert["blockers"],
        )

    def test_policy_is_reproducible_and_non_building(self):
        policy = reproducible_build_policy()
        self.assertEqual(policy["python_version"], PYTHON_VERSION)
        self.assertEqual(policy["pip_version"], PIP_VERSION)
        self.assertEqual(
            policy["cryptography_version"],
            CRYPTOGRAPHY_VERSION,
        )
        self.assertTrue(policy["source_date_epoch_required"])
        self.assertTrue(policy["timezone_normalized_utc"])
        self.assertTrue(policy["locale_normalized"])
        self.assertTrue(policy["python_hash_seed_fixed"])
        self.assertTrue(policy["lexical_source_order_required"])
        self.assertTrue(policy["normalized_file_modes_required"])
        self.assertTrue(policy["normalized_uid_gid_required"])
        self.assertTrue(policy["host_username_forbidden"])
        self.assertTrue(policy["host_path_forbidden"])
        self.assertTrue(policy["runner_identity_forbidden"])
        self.assertTrue(policy["wall_clock_time_forbidden_in_artifact"])
        self.assertFalse(policy["network_during_build_allowed"])
        self.assertFalse(policy["dependency_resolution_during_build_allowed"])
        self.assertFalse(policy["dependency_upgrade_during_build_allowed"])
        self.assertTrue(policy["sbom_recipe_pinned"])
        self.assertTrue(policy["provenance_recipe_pinned"])
        self.assertTrue(policy["builder_image_digest_required"])
        self.assertTrue(policy["build_script_digest_required"])
        self.assertTrue(policy["two_independent_builds_required"])
        self.assertTrue(policy["clean_build_roots_required"])
        self.assertTrue(policy["independent_workdirs_required"])
        self.assertTrue(policy["archive_digest_must_match"])
        self.assertTrue(policy["manifest_digest_must_match"])
        self.assertTrue(policy["sbom_digest_must_match"])
        self.assertTrue(policy["provenance_digest_must_match"])
        self.assertTrue(policy["tree_digest_must_match"])
        self.assertFalse(policy["production_package_built_by_this_module"])
        self.assertFalse(policy["package_installed"])
        self.assertFalse(policy["release_authorized"])
        self.assertFalse(policy["installation_authorized"])
        self.assertFalse(policy["subprocess_spawned"])
        self.assertFalse(policy["filesystem_modified"])
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
