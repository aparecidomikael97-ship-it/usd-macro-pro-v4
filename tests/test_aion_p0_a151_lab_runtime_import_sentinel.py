"""A151: mutations prove the static boundary catches accidental LAB imports.

These tests do not establish physical independence, execution reachability
or safety of any runtime path; their pass state is always operational NO-GO.
"""
from pathlib import Path
import tempfile
import unittest

from tools.aion_p0_a151_lab_runtime_import_sentinel import (
    audit_repository, inspect_source,
)


class A151StaticLabImportFence(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def file(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def reasons(self):
        return [x["reason"] for x in audit_repository(self.root)["findings"]]

    def test_01_no_laboratory_import_yields_static_clean_not_authority(self):
        self.file("runtime.py", "import os\n")
        decision = audit_repository(self.root)
        self.assertTrue(decision["static_import_boundary_clean"])
        self.assertFalse(decision["external_custodian_independence_verified"])
        self.assertFalse(decision["real_trust_root_enrolled"])
        self.assertFalse(decision["H0_effect_authorization"])
        self.assertFalse(decision["automatic_resend_allowed"])
        self.assertEqual(decision["homologated_p0_count"], 0)
        self.assertIn("HARD_NO_GO", decision["verdict"])

    def test_02_import_lab_a145_denied(self):
        self.file("service.py", "import aion_p0_a145_checkpoint_verifier_lab\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_03_from_import_lab_a150_denied(self):
        self.file("aion_core/worker.py",
                  "from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_04_nested_runtime_module_import_denied(self):
        self.file("runtime/worker.py", "import aion_p0_a149_authenticated_cas_lab\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_05_dynamic_importlib_literal_denied(self):
        self.file("service.py", "import importlib\nx=importlib.import_module('aion_p0_a146_highwater_gate_lab')\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_06_dynamic_dunder_import_literal_denied(self):
        self.file("service.py", "x=__import__('aion_p0_a148_split_process_witness_lab')\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_07_all_six_generations_detected(self):
        for version in range(145, 151):
            self.file(f"runtime{version}.py", f"import aion_p0_a{version}_model_lab\n")
        self.assertEqual(len(audit_repository(self.root)["findings"]), 6)

    def test_08_lab_test_file_excluded(self):
        self.file("tests/test_aion_smoke.py", "import aion_p0_a149_authenticated_cas_lab\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_09_root_level_experiment_imports_excluded(self):
        self.file("aion_p0_a150_pinned_policy_lease_lab.py",
                  "from aion_p0_a149_authenticated_cas_lab import A149Denied\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_10_malicious_deploy_wrapper_not_excluded(self):
        self.file("deploy/runtime.py", "from aion_p0_a150_pinned_policy_lease_lab import *\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_11_unparseable_runtime_python_denied(self):
        self.file("service.py", "if (\n")
        self.assertIn("UNPARSEABLE_PYTHON_SOURCE", self.reasons())

    def test_12_docstrings_without_imports_do_not_assert_reachability(self):
        self.file("service.py", '"""aion_p0_a150_pinned_policy_lease_lab"""'+"\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_13_imports_of_unrelated_module_not_denied(self):
        self.file("service.py", "from aion_core.trust_engine import something\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_14_catches_multiple_unsafe_imports_with_stable_file_and_line(self):
        self.file("service.py",
                  "import aion_p0_a147_sqlite_crash_journal_lab\n"
                  "from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB\n")
        findings = audit_repository(self.root)["findings"]
        self.assertEqual(len(findings), 2)
        self.assertEqual({x["line"] for x in findings}, {1, 2})
        self.assertEqual({x["file"] for x in findings}, {"service.py"})

    def test_15_test_prefix_outside_tests_is_excluded(self):
        self.file("test_runtime.py", "import aion_p0_a150_pinned_policy_lease_lab\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_16_runtime_filename_suffix_lab_not_automatically_excluded(self):
        self.file("service_lab.py", "import aion_p0_a150_pinned_policy_lease_lab\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())


    def test_17_a161_dual_floor_import_inside_runtime_denied(self):
        self.file("runtime/worker.py",
                  "from aion_p0_a161_dual_custodian_floor_lab import FloorClaim\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_18_a162_tripartite_import_inside_runtime_denied(self):
        self.file("runtime/worker.py",
                  "from aion_p0_a162_three_source_recovery_lab import assess_three_source_restart\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_19_explicit_root_level_a162_experiment_is_excluded(self):
        self.file("aion_p0_a162_three_source_recovery_lab.py",
                  "from aion_p0_a161_dual_custodian_floor_lab import FloorReview\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_20_a162_filename_in_nested_deploy_directory_is_not_excluded(self):
        self.file("deploy/aion_p0_a162_three_source_recovery_lab.py",
                  "from aion_p0_a150_pinned_policy_lease_lab import LeasedPinnedWitnessLAB\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE", self.reasons())

    def test_21_a163_enrollment_import_in_runtime_denied(self):
        self.file("runtime/worker.py",
                  "from aion_p0_a163_custody_enrollment_revocation_lab import PolicyEvent\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

    def test_22_root_level_a163_experiment_allowed(self):
        self.file("aion_p0_a163_custody_enrollment_revocation_lab.py",
                  "from aion_p0_a162_three_source_recovery_lab import ThreeSourceReview\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_23_nested_deploy_a163_name_never_bypasses_fence(self):
        self.file("deploy/aion_p0_a163_custody_enrollment_revocation_lab.py",
                  "from aion_p0_a161_dual_custodian_floor_lab import SignedFloor\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

    def test_24_dynamic_import_a163_from_runtime_denied(self):
        self.file("services/process.py",
                  "import importlib\nx=importlib.import_module('aion_p0_a163_custody_enrollment_revocation_lab')\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

    def test_25_a164_policy_floor_import_from_runtime_denied(self):
        self.file("runtime/aion_witness_service.py",
                  "from aion_p0_a164_independent_revocation_floor_lab import RevocationFloor\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

    def test_26_a164_root_experimental_module_is_excluded(self):
        self.file("aion_p0_a164_independent_revocation_floor_lab.py",
                  "from aion_p0_a163_custody_enrollment_revocation_lab import PolicyAnchor\n")
        self.assertTrue(audit_repository(self.root)["static_import_boundary_clean"])

    def test_27_a164_nested_worker_file_is_not_excluded(self):
        self.file("deploy/aion_p0_a164_independent_revocation_floor_lab.py",
                  "import aion_p0_a163_custody_enrollment_revocation_lab\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

    def test_28_a164_dynamic_import_from_operational_service_denied(self):
        self.file("services/recover.py",
                  "import importlib\np=importlib.import_module('aion_p0_a164_independent_revocation_floor_lab')\n")
        self.assertIn("LAB_MODULE_IMPORTED_IN_NON_LAB_SOURCE",self.reasons())

if __name__ == "__main__":
    unittest.main()
