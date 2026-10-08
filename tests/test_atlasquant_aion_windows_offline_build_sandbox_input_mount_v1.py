import copy
import unittest

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    REQUIRED_PACKAGE_ROLES,
    ROLE_DESTINATIONS,
    build_installation_manifest,
)
from atlasquant_aion_windows_local_agent_reproducible_build_contract_v1 import (
    build_dependency_lock,
    build_source_set,
    build_reproducible_recipe,
)
from atlasquant_aion_windows_build_input_offline_cache_attestation_v1 import (
    EXPECTED_ROLES,
    build_input_snapshot,
    attest_offline_cache,
    build_offline_input_promotion,
)
from atlasquant_aion_windows_offline_build_sandbox_input_mount_v1 import (
    MAX_CHILD_PROCESS_COUNT,
    MAX_PROCESS_COUNT,
    NETWORK_POLICY,
    PROCESS_POLICY,
    build_input_mount_contract,
    build_environment_scrub_contract,
    build_process_allowlist_contract,
    build_network_deny_contract,
    build_sandbox_preflight,
    offline_build_sandbox_policy,
)


D = lambda c: "sha256:" + (c * 64)


class AionWindowsOfflineBuildSandboxInputMountV1Tests(unittest.TestCase):
    def installation_manifest(self):
        rows = []
        markers = "1234567"
        for role, marker in zip(REQUIRED_PACKAGE_ROLES, markers):
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
        out = build_installation_manifest(
            rows,
            package_version="1.0.0",
            build_id="sandbox-build-1",
            build_commit_sha="a" * 40,
            minimum_windows_build=22621,
            python_runtime_version="3.12.12",
            created_at="2026-10-08T14:30:00+00:00",
        )
        self.assertEqual(out["state"], "INSTALLATION_MANIFEST_READY")
        return out

    def recipe(self):
        manifest = self.installation_manifest()
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
        self.assertEqual(lock["state"], "BUILD_DEPENDENCY_LOCK_READY")
        self.assertEqual(sources["state"], "BUILD_SOURCE_SET_READY")
        self.assertEqual(recipe["state"], "REPRODUCIBLE_BUILD_RECIPE_READY")
        return lock, recipe

    def input_artifacts(self):
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
                "2.1.1",
                "WHEEL",
                "cffi-2.1.1-cp312-cp312-win_amd64.whl",
            ),
            "PYCPARSER_WHEEL": (
                "pycparser",
                "3.1",
                "WHEEL",
                "pycparser-3.1-py3-none-any.whl",
            ),
        }
        rows = []
        for role, marker in zip(EXPECTED_ROLES, "12345"):
            project, version, kind, filename = specs[role]
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

    def promotion_and_recipe(self):
        lock, recipe = self.recipe()
        snapshot = build_input_snapshot(
            lock,
            self.input_artifacts(),
            trusted_python_release_snapshot_digest=D("c"),
            trusted_python_package_index_snapshot_digest=D("d"),
            resolver_evidence_digest=D("e"),
            acquisition_environment_digest=D("f"),
            snapshot_created_at="2026-10-08T14:35:00+00:00",
        )
        self.assertEqual(snapshot["state"], "BUILD_INPUT_SNAPSHOT_READY")

        observed = [
            {
                "role": row["role"],
                "filename": row["filename"],
                "sha256": row["expected_sha256"],
                "size_bytes": row["size_bytes"],
            }
            for row in snapshot["artifacts"]
        ]
        cache = attest_offline_cache(
            snapshot,
            observed,
            cache_root_evidence_digest=D("1"),
            cache_acl_attestation_digest=D("2"),
            cache_manifest_digest=D("3"),
            cache_read_only_verified=True,
            owner_only_acl_verified=True,
            no_extra_files_verified=True,
            no_symlinks_verified=True,
            no_reparse_points_verified=True,
            no_alternate_data_streams_verified=True,
            cache_network_isolation_verified=True,
            attested_at="2026-10-08T14:40:00+00:00",
        )
        self.assertEqual(cache["state"], "OFFLINE_DEPENDENCY_CACHE_ATTESTED")

        promotion = build_offline_input_promotion(
            lock,
            snapshot,
            cache,
            reproducible_build_recipe_digest=recipe["build_recipe_digest"],
            promotion_review_digest=D("4"),
        )
        self.assertEqual(
            promotion["state"],
            "OFFLINE_BUILD_INPUTS_READY_FOR_REPRODUCIBLE_BUILD",
        )
        return promotion, recipe

    def mount(self, promotion, **changes):
        kwargs = {
            "promotion": promotion,
            "cache_root": r"C:\AIONBuild\cache",
            "source_root": r"C:\AIONBuild\source",
            "runtime_root": r"C:\AIONBuild\runtime",
            "output_root": r"C:\AIONBuild\output",
            "temp_root": r"C:\AIONBuild\temp",
            "cache_root_evidence_digest": D("5"),
            "source_tree_digest": D("6"),
            "runtime_tree_digest": D("7"),
            "output_root_identity_digest": D("8"),
            "temp_root_identity_digest": D("9"),
        }
        kwargs.update(changes)
        return build_input_mount_contract(**kwargs)

    def full_contracts(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        env = build_environment_scrub_contract(
            recipe,
            mount,
            source_date_epoch=1791446400,
        )
        process = build_process_allowlist_contract(
            recipe,
            mount,
            env,
            python_executable_path=r"C:\AIONBuild\runtime\python.exe",
            python_executable_sha256=D("a"),
            build_script_path=r"C:\AIONBuild\source\build_agent.py",
            build_script_sha256=D("9"),
        )
        network = build_network_deny_contract()
        return promotion, recipe, mount, env, process, network

    def test_mount_contract_is_ro_inputs_and_isolated_writable_output(self):
        promotion, _ = self.promotion_and_recipe()
        mount = self.mount(promotion)
        self.assertEqual(
            mount["state"],
            "OFFLINE_BUILD_INPUT_MOUNT_CONTRACT_READY",
            mount["blockers"],
        )
        self.assertEqual(mount["cache_mode"], "READ_ONLY")
        self.assertEqual(mount["source_mode"], "READ_ONLY")
        self.assertEqual(mount["runtime_mode"], "READ_ONLY")
        self.assertEqual(mount["output_mode"], "WRITE_ONLY_BUILD_OUTPUT")
        self.assertEqual(mount["temp_mode"], "READ_WRITE_EPHEMERAL")
        self.assertFalse(mount["cache_write_allowed"])
        self.assertFalse(mount["source_write_allowed"])
        self.assertFalse(mount["runtime_write_allowed"])
        self.assertFalse(mount["output_read_as_input_allowed"])
        self.assertFalse(mount["repository_write_allowed"])
        self.assertFalse(mount["path_traversal_allowed"])
        self.assertFalse(mount["symlink_escape_allowed"])
        self.assertFalse(mount["reparse_point_escape_allowed"])
        self.assertFalse(mount["hardlink_escape_allowed"])
        self.assertFalse(mount["alternate_data_streams_allowed"])
        self.assertFalse(mount["network_share_allowed"])
        self.assertFalse(mount["mount_performed"])
        self.assertFalse(mount["filesystem_modified"])

    def test_overlapping_roots_block_case_insensitively(self):
        promotion, _ = self.promotion_and_recipe()
        blocked = self.mount(
            promotion,
            output_root=r"c:\aionbuild\CACHE\output",
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertTrue(
            any(
                item.startswith("SANDBOX_ROOT_OVERLAP:CACHE_ROOT:OUTPUT_ROOT")
                for item in blocked["blockers"]
            )
        )

    def test_unc_or_relative_root_blocks(self):
        promotion, _ = self.promotion_and_recipe()
        unc = self.mount(
            promotion,
            cache_root=r"\\server\share\cache",
        )
        self.assertEqual(unc["state"], "BLOCKED")
        self.assertIn("CACHE_ROOT_UNC_FORBIDDEN", unc["blockers"])

        relative = self.mount(
            promotion,
            temp_root=r"AIONBuild\temp",
        )
        self.assertEqual(relative["state"], "BLOCKED")
        self.assertIn(
            "TEMP_ROOT_ABSOLUTE_LOCAL_PATH_REQUIRED",
            relative["blockers"],
        )

    def test_environment_scrub_has_no_parent_path_proxy_or_user_profile(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        env = build_environment_scrub_contract(
            recipe,
            mount,
            source_date_epoch=1791446400,
        )
        self.assertEqual(
            env["state"],
            "OFFLINE_BUILD_ENVIRONMENT_SCRUB_READY",
            env["blockers"],
        )
        self.assertFalse(env["parent_environment_inherited"])
        self.assertFalse(env["caller_environment_overrides_allowed"])
        self.assertFalse(env["path_lookup_allowed"])
        self.assertFalse(env["credentials_in_environment_allowed"])
        self.assertFalse(env["proxy_environment_allowed"])
        self.assertNotIn("PATH", env["environment"])
        self.assertNotIn("HOME", env["environment"])
        self.assertNotIn("USERPROFILE", env["environment"])
        self.assertNotIn("HTTP_PROXY", env["environment"])
        self.assertEqual(env["environment"]["PIP_NO_INDEX"], "1")
        self.assertEqual(env["environment"]["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["environment"]["SOURCE_DATE_EPOCH"], "1791446400")

    def test_environment_injection_blocks(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        for key, value in (
            ("PATH", r"C:\evil"),
            ("HTTP_PROXY", "http://127.0.0.1:8080"),
            ("GITHUB_TOKEN", "secret"),
            ("GIT_CONFIG_COUNT", "1"),
            ("HOME", r"C:\Users\Mikael"),
            ("EVIL_NEW_KEY", "x"),
        ):
            with self.subTest(key=key):
                env = build_environment_scrub_contract(
                    recipe,
                    mount,
                    source_date_epoch=1791446400,
                    caller_environment={key: value},
                )
                self.assertEqual(env["state"], "BLOCKED")
                self.assertIn(
                    "CALLER_ENVIRONMENT_KEY_NOT_ALLOWED",
                    env["blockers"],
                )

    def test_allowed_environment_key_cannot_override_fixed_value(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        env = build_environment_scrub_contract(
            recipe,
            mount,
            source_date_epoch=1791446400,
            caller_environment={"TZ": "America/Sao_Paulo"},
        )
        self.assertEqual(env["state"], "BLOCKED")
        self.assertIn(
            "CALLER_ENVIRONMENT_OVERRIDE_FORBIDDEN:TZ",
            env["blockers"],
        )

    def test_process_allowlist_is_one_absolute_pinned_python_only(self):
        _, recipe, mount, env, process, _ = self.full_contracts()
        self.assertEqual(
            process["state"],
            "OFFLINE_BUILD_PROCESS_ALLOWLIST_READY",
            process["blockers"],
        )
        self.assertEqual(process["process_policy"], PROCESS_POLICY)
        self.assertTrue(
            process["python_executable_path"].endswith(r"runtime\python.exe")
        )
        self.assertIn("-I", process["argv_template"])
        self.assertIn("-S", process["argv_template"])
        self.assertIn("--offline", process["argv_template"])
        self.assertIn("--no-network", process["argv_template"])
        self.assertFalse(process["shell_allowed"])
        self.assertFalse(process["cmd_exe_allowed"])
        self.assertFalse(process["powershell_allowed"])
        self.assertFalse(process["path_lookup_allowed"])
        self.assertFalse(process["python_c_flag_allowed"])
        self.assertFalse(process["python_m_pip_allowed"])
        self.assertFalse(process["arbitrary_arguments_allowed"])
        self.assertFalse(process["child_process_allowed"])
        self.assertFalse(process["detached_process_allowed"])
        self.assertFalse(process["background_process_allowed"])
        self.assertFalse(process["process_spawned"])

    def test_python_or_script_outside_bound_roots_blocks(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        env = build_environment_scrub_contract(
            recipe,
            mount,
            source_date_epoch=1791446400,
        )
        bad_python = build_process_allowlist_contract(
            recipe,
            mount,
            env,
            python_executable_path=r"C:\Windows\System32\python.exe",
            python_executable_sha256=D("a"),
            build_script_path=r"C:\AIONBuild\source\build_agent.py",
            build_script_sha256=D("9"),
        )
        self.assertEqual(bad_python["state"], "BLOCKED")
        self.assertIn(
            "PYTHON_EXECUTABLE_OUTSIDE_RUNTIME_ROOT",
            bad_python["blockers"],
        )

        bad_script = build_process_allowlist_contract(
            recipe,
            mount,
            env,
            python_executable_path=r"C:\AIONBuild\runtime\python.exe",
            python_executable_sha256=D("a"),
            build_script_path=r"C:\Users\Mikael\build_agent.py",
            build_script_sha256=D("9"),
        )
        self.assertEqual(bad_script["state"], "BLOCKED")
        self.assertIn(
            "BUILD_SCRIPT_OUTSIDE_SOURCE_ROOT",
            bad_script["blockers"],
        )

    def test_shell_executable_cannot_substitute_for_python(self):
        promotion, recipe = self.promotion_and_recipe()
        mount = self.mount(promotion)
        env = build_environment_scrub_contract(
            recipe,
            mount,
            source_date_epoch=1791446400,
        )
        blocked = build_process_allowlist_contract(
            recipe,
            mount,
            env,
            python_executable_path=r"C:\AIONBuild\runtime\powershell.exe",
            python_executable_sha256=D("a"),
            build_script_path=r"C:\AIONBuild\source\build_agent.py",
            build_script_sha256=D("9"),
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("ONLY_PYTHON_EXE_ALLOWED", blocked["blockers"])

    def test_network_contract_denies_every_network_surface(self):
        network = build_network_deny_contract()
        self.assertEqual(
            network["state"],
            "OFFLINE_BUILD_NETWORK_DENY_CONTRACT_READY",
        )
        self.assertEqual(network["network_policy"], NETWORK_POLICY)
        self.assertFalse(network["network_allowed"])
        self.assertFalse(network["dns_allowed"])
        self.assertFalse(network["tcp_allowed"])
        self.assertFalse(network["udp_allowed"])
        self.assertFalse(network["loopback_allowed"])
        self.assertFalse(network["proxy_allowed"])
        self.assertFalse(network["remote_named_pipe_allowed"])
        self.assertFalse(network["unc_allowed"])
        self.assertFalse(network["socket_opened"])
        self.assertFalse(network["network_called"])
        self.assertFalse(network["firewall_rule_created"])
        self.assertFalse(
            network["windows_network_isolation_physically_verified"]
        )

    def test_preflight_is_probe_ready_but_never_execution_ready(self):
        promotion, recipe, mount, env, process, network = self.full_contracts()
        preflight = build_sandbox_preflight(
            promotion,
            recipe,
            mount,
            env,
            process,
            network,
            resource_policy_digest=D("b"),
        )
        self.assertEqual(
            preflight["state"],
            "WINDOWS_OFFLINE_BUILD_SANDBOX_READY_FOR_PHYSICAL_PROBE",
            preflight["blockers"],
        )
        self.assertEqual(preflight["resources"]["max_process_count"], 1)
        self.assertEqual(
            preflight["resources"]["max_child_process_count"],
            0,
        )
        self.assertGreater(len(preflight["required_physical_proofs"]), 5)
        self.assertFalse(preflight["physical_windows_sandbox_verified"])
        self.assertFalse(preflight["restricted_token_created"])
        self.assertFalse(preflight["job_object_created"])
        self.assertFalse(preflight["read_only_mounts_created"])
        self.assertFalse(
            preflight["network_isolation_physically_verified"]
        )
        self.assertFalse(preflight["build_authorized"])
        self.assertFalse(preflight["build_started"])
        self.assertFalse(preflight["package_built"])
        self.assertFalse(preflight["package_installed"])
        self.assertFalse(preflight["process_spawned"])
        self.assertFalse(preflight["filesystem_modified"])
        self.assertFalse(preflight["network_called"])
        self.assertFalse(preflight["github_api_called"])

    def test_preflight_detects_recipe_binding_tamper(self):
        promotion, recipe, mount, env, process, network = self.full_contracts()
        tampered = copy.deepcopy(promotion)
        tampered["reproducible_build_recipe_digest"] = D("0")
        preflight = build_sandbox_preflight(
            tampered,
            recipe,
            mount,
            env,
            process,
            network,
            resource_policy_digest=D("b"),
        )
        self.assertEqual(preflight["state"], "BLOCKED")
        self.assertIn(
            "PROMOTION_RECIPE_BINDING_MISMATCH",
            preflight["blockers"],
        )

    def test_policy_is_fail_closed_and_nonexecuting(self):
        policy = offline_build_sandbox_policy()
        self.assertTrue(policy["cache_read_only_required"])
        self.assertTrue(policy["source_read_only_required"])
        self.assertTrue(policy["runtime_read_only_required"])
        self.assertTrue(policy["output_temp_only_writable"])
        self.assertTrue(policy["sandbox_roots_must_not_overlap"])
        self.assertFalse(policy["unc_paths_allowed"])
        self.assertFalse(policy["network_share_allowed"])
        self.assertFalse(policy["path_traversal_allowed"])
        self.assertFalse(policy["symlink_escape_allowed"])
        self.assertFalse(policy["reparse_point_escape_allowed"])
        self.assertFalse(policy["hardlink_escape_allowed"])
        self.assertFalse(policy["alternate_data_streams_allowed"])
        self.assertFalse(policy["device_path_access_allowed"])
        self.assertFalse(policy["parent_environment_inheritance_allowed"])
        self.assertFalse(policy["caller_environment_overrides_allowed"])
        self.assertFalse(policy["path_lookup_allowed"])
        self.assertFalse(policy["shell_allowed"])
        self.assertFalse(policy["powershell_allowed"])
        self.assertFalse(policy["cmd_exe_allowed"])
        self.assertFalse(policy["arbitrary_process_spawn_allowed"])
        self.assertFalse(policy["child_process_allowed"])
        self.assertFalse(policy["detached_process_allowed"])
        self.assertFalse(policy["background_process_allowed"])
        self.assertFalse(policy["network_allowed"])
        self.assertFalse(policy["dns_allowed"])
        self.assertFalse(policy["tcp_allowed"])
        self.assertFalse(policy["udp_allowed"])
        self.assertFalse(policy["loopback_allowed"])
        self.assertFalse(policy["proxy_allowed"])
        self.assertFalse(policy["remote_named_pipe_allowed"])
        self.assertEqual(policy["max_process_count"], MAX_PROCESS_COUNT)
        self.assertEqual(
            policy["max_child_process_count"],
            MAX_CHILD_PROCESS_COUNT,
        )
        self.assertFalse(policy["physical_windows_sandbox_verified"])
        self.assertFalse(policy["restricted_token_created"])
        self.assertFalse(policy["job_object_created"])
        self.assertFalse(policy["read_only_mounts_created"])
        self.assertFalse(policy["network_isolation_physically_verified"])
        self.assertFalse(policy["build_authorized"])
        self.assertFalse(policy["build_started"])
        self.assertFalse(policy["package_built"])
        self.assertFalse(policy["package_installed"])
        self.assertFalse(policy["process_spawned"])
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
