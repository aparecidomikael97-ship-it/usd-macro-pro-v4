"""A137: static source-only verification of four risky workflow jobs."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"tools/aion_p0_workflow_credential_surface_a137.py"
S=importlib.util.spec_from_file_location("aion_a137",P)
A=importlib.util.module_from_spec(S)
assert S and S.loader
S.loader.exec_module(A)

class A137WorkflowTokenHardstopLab(unittest.TestCase):
    def test_01_active_autopilot_job_is_denied_without_custody(self):
        r=A.audit(ROOT)["critical_jobs"]["autopilot-v107.yml"]
        self.assertTrue(r["target_p0_fence_ok"],r)

    def test_02_active_coleta_job_is_denied_without_custody(self):
        r=A.audit(ROOT)["critical_jobs"]["coleta_automatica.yml"]
        self.assertTrue(r["target_p0_fence_ok"],r)

    def test_03_bootstrap_writes_remain_denied(self):
        r=A.audit(ROOT)["critical_jobs"]["aion-runtime-checkpoint-bootstrap.yml"]
        self.assertTrue(r["target_p0_fence_ok"],r)

    def test_04_migration_writes_remain_denied(self):
        r=A.audit(ROOT)["critical_jobs"]["aion-runtime-checkpoint-migrate.yml"]
        self.assertTrue(r["target_p0_fence_ok"],r)

    def test_05_emergency_guard_requires_actual_job_not_comment(self):
        s="""on:\n  schedule:\n    - cron: '* * * * *'\njobs:\n  autopilot:\n    # if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: python autopilot_setup_audit_v114.py\n"""
        r=A.inspect_one("autopilot-v107.yml",s)
        self.assertFalse(r["target_p0_fence_ok"])

    def test_06_emergency_guard_not_satisfied_by_step_level_if(self):
        s="""jobs:\n  autopilot:\n    runs-on: ubuntu-latest\n    steps:\n      - if: ${{ false }}\n        run: python autopilot_setup_audit_v114.py\n"""
        r=A.inspect_one("autopilot-v107.yml",s)
        self.assertFalse(r["target_p0_fence_ok"])

    def test_07_emergency_guard_not_satisfied_if_writer_missing(self):
        s="""jobs:\n  autopilot:\n    if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps: []\n"""
        r=A.inspect_one("autopilot-v107.yml",s)
        self.assertFalse(r["target_p0_fence_ok"])

    def test_08_emergency_guard_requires_literal_false_not_boolean_env(self):
        s="""jobs:\n  autopilot:\n    if: ${{ vars.ENABLE_WORKER != '1' }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: python autopilot_setup_audit_v114.py\n"""
        r=A.inspect_one("autopilot-v107.yml",s)
        self.assertFalse(r["target_p0_fence_ok"])

    def test_09_detects_write_perm_and_schedule_when_present(self):
        s="""on:\n  schedule:\n    - cron: '7,37 * * * *'\npermissions:\n  contents: write\njobs:\n  autopilot:\n    if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: python autopilot_setup_audit_v114.py\n"""
        r=A.inspect_one("autopilot-v107.yml",s)
        self.assertTrue(r["scheduled"])
        self.assertTrue(r["contents_write_declared"])

    def test_10_guard_not_claimed_as_external_enrollment(self):
        r=A.audit(ROOT)
        self.assertFalse(r["external_monotonic_witness_enrolled"])
        self.assertFalse(r["human_owner_identity_verified"])
        self.assertFalse(r["worker_activated"])
        self.assertFalse(r["runtime_restored"])

    def test_11_inventory_covers_many_workflow_files(self):
        r=A.audit(ROOT)
        self.assertGreaterEqual(r["workflow_files_scanned"],250)
        self.assertEqual(r["missing_critical_workflows"],[])

    def test_12_all_critical_workflow_jobs_are_hardstopped(self):
        r=A.audit(ROOT)
        self.assertEqual(r["critical_jobs_not_hard_stopped"],[],r)

    def test_13_no_module_or_workflow_commands_executed_by_scanner(self):
        r=A.audit(ROOT)
        self.assertTrue(r["all_source_lines_ignored_execution"])
        self.assertTrue(r["evidence_limited_to_repository_source"])

    def test_14_autopilot_repo_token_is_read_only_in_lab_candidate(self):
        r=A.audit(ROOT)["critical_jobs"]["autopilot-v107.yml"]
        self.assertFalse(r["contents_write_declared"],r)
        self.assertTrue(r["job_disabled_unconditionally"])

    def test_15_coleta_repo_token_is_read_only_in_lab_candidate(self):
        r=A.audit(ROOT)["critical_jobs"]["coleta_automatica.yml"]
        self.assertFalse(r["contents_write_declared"],r)
        self.assertTrue(r["job_disabled_unconditionally"])

    def test_16_scheduled_writer_with_disabled_job_but_write_token_is_still_denied(self):
        text="""on:\n  schedule:\n    - cron: '7 * * * *'\npermissions:\n  contents: write\njobs:\n  autopilot:\n    if: ${{ false }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: python autopilot_setup_audit_v114.py\n"""
        result=A.inspect_one("autopilot-v107.yml",text)
        self.assertFalse(result["target_p0_fence_ok"],result)


if __name__=="__main__":
    unittest.main()
