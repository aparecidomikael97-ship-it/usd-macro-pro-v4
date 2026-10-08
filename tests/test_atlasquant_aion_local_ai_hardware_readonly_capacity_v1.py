"""Synthetic privacy and local-model hardware sizing tests, no owner PC."""
import copy
import math
from pathlib import Path
import unittest

from atlasquant_aion_local_ai_hardware_readonly_capacity_v1 import (
    SCHEMA, INPUT_KEYS, FALSE_RESULTS,
    review_local_model_hardware_report, hardware_probe_policy,
)

def report(ram=16, disk=40, cpus=8, vendors=None, source="CI_EPHEMERAL"):
    return {
        "schema":SCHEMA, "source":source, "ram_total_gib":ram,
        "cpu_logical_processors":cpus,"system_disk_free_gib":disk,
        "gpu_vendor_classes":["INTEL"] if vendors is None else vendors,
        "dedicated_gpu_vram_verified":False,
        "local_model_execution_tested":False,
        "model_speed_measured":False,"api_usage_charge_read":False,
        "data_uploaded":False,"device_modified":False,
        "owner_install_approved":False,"production_ready":False,
    }

class LocalAIReadOnlyHardwareCapacityV1Tests(unittest.TestCase):
    def check_block(self, r, code=None):
        self.assertEqual(r["state"],"BLOCKED",r)
        if code:self.assertIn(code,r["blockers"])

    def test_minimal_windows_fixture_is_advisory_only(self):
        r=review_local_model_hardware_report(report())
        self.assertEqual(r["state"],"READ_ONLY_CAPACITY_ADVISORY_UNTRUSTED")
        self.assertEqual(r["advisory_tier"],"CPU_OR_UNKNOWN_GPU_LOCAL_BENCHMARK_CANDIDATE")
        for name in FALSE_RESULTS:self.assertIs(r[name],False,name)

    def test_gpu_vendor_is_only_experiment_candidate_not_fit(self):
        r=review_local_model_hardware_report(report(ram=32,vendors=["NVIDIA"]))
        self.assertEqual(r["advisory_tier"],"GPU_LOCAL_MODEL_BENCHMARK_CANDIDATE")
        self.assertFalse(r["gpu_vram_driver_or_runtime_measurement_required"] is False)
        self.assertFalse(r["large_model_fit_verified"])

    def test_amd_vendor_is_only_advisory(self):
        r=review_local_model_hardware_report(report(ram=64,vendors=["AMD"]))
        self.assertEqual(r["advisory_tier"],"GPU_LOCAL_MODEL_BENCHMARK_CANDIDATE")

    def test_light_machine_requires_small_model_benchmark(self):
        r=review_local_model_hardware_report(report(ram=8,disk=10))
        self.assertEqual(r["advisory_tier"],"LIGHT_LOCAL_MODEL_EXPERIMENT_CANDIDATE")

    def test_under_8_gib_does_not_promise_local_ai(self):
        r=review_local_model_hardware_report(report(ram=7.99))
        self.assertEqual(r["advisory_tier"],"HARDWARE_CONSTRAINED_BENCHMARK_REQUIRED")

    def test_low_disk_space_requires_benchmark(self):
        r=review_local_model_hardware_report(report(disk=3))
        self.assertEqual(r["advisory_tier"],"HARDWARE_CONSTRAINED_BENCHMARK_REQUIRED")

    def test_sufficient_ram_without_disk_blocks_gpu_candidate(self):
        r=review_local_model_hardware_report(report(ram=64,disk=11,vendors=["NVIDIA"]))
        self.assertEqual(r["advisory_tier"],"LIGHT_LOCAL_MODEL_EXPERIMENT_CANDIDATE")

    def test_owner_mode_does_not_infer_device_trust(self):
        r=review_local_model_hardware_report(report(source="OWNER_EXPLICIT_READ_ONLY"))
        self.assertEqual(r["state"],"READ_ONLY_CAPACITY_ADVISORY_UNTRUSTED")
        self.assertFalse(r["actual_owner_device_verified"])

    def test_unrecognized_sources_block(self):
        self.check_block(review_local_model_hardware_report(report(source="AUTO_DEVICE_SCAN")),"SOURCE_MODE_INVALID")

    def test_unhashable_source_blocks_without_crash(self):
        self.check_block(review_local_model_hardware_report(report(source=["OWNER_EXPLICIT_READ_ONLY"])),"SOURCE_MODE_INVALID")

    def test_missing_schema_blocks(self):
        self.check_block(review_local_model_hardware_report(dict(report(),schema="other")),"REPORT_SCHEMA_MISMATCH")

    def test_extra_serial_field_denied(self):
        self.check_block(review_local_model_hardware_report(dict(report(),serial_number="private")),"EXACT_READONLY_REPORT_FIELDS_REQUIRED")

    def test_missing_privacy_false_field_denied(self):
        x=report();del x["data_uploaded"]
        self.check_block(review_local_model_hardware_report(x),"EXACT_READONLY_REPORT_FIELDS_REQUIRED")

    def test_fake_vram_verified_claim_denied(self):
        self.check_block(review_local_model_hardware_report(dict(report(),dedicated_gpu_vram_verified=True)),"FALSE_DEVICE_TRUST_CLAIM_REQUIRED:dedicated_gpu_vram_verified")

    def test_fake_model_execution_denied(self):
        self.check_block(review_local_model_hardware_report(dict(report(),local_model_execution_tested=True)),"FALSE_DEVICE_TRUST_CLAIM_REQUIRED:local_model_execution_tested")

    def test_fake_install_authority_denied(self):
        self.check_block(review_local_model_hardware_report(dict(report(),owner_install_approved=True)),"FALSE_DEVICE_TRUST_CLAIM_REQUIRED:owner_install_approved")

    def test_fake_uploaded_report_denied(self):
        self.check_block(review_local_model_hardware_report(dict(report(),data_uploaded=True)),"FALSE_DEVICE_TRUST_CLAIM_REQUIRED:data_uploaded")

    def test_cpu_boolean_invalid(self):
        self.check_block(review_local_model_hardware_report(report(cpus=True)),"CPU_LOGICAL_COUNT_INVALID")

    def test_cpu_negative_invalid(self):
        self.check_block(review_local_model_hardware_report(report(cpus=-1)),"CPU_LOGICAL_COUNT_INVALID")

    def test_cpu_outlier_invalid(self):
        self.check_block(review_local_model_hardware_report(report(cpus=5000)),"CPU_LOGICAL_COUNT_INVALID")

    def test_ram_nan_invalid(self):
        self.check_block(review_local_model_hardware_report(report(ram=float("nan"))),"RAM_TOTAL_INVALID")

    def test_ram_inf_invalid(self):
        self.check_block(review_local_model_hardware_report(report(ram=float("inf"))),"RAM_TOTAL_INVALID")

    def test_ram_bool_invalid(self):
        self.check_block(review_local_model_hardware_report(report(ram=True)),"RAM_TOTAL_INVALID")

    def test_ram_outlier_invalid(self):
        self.check_block(review_local_model_hardware_report(report(ram=9999)),"RAM_TOTAL_INVALID")

    def test_disk_negative_invalid(self):
        self.check_block(review_local_model_hardware_report(report(disk=-10)),"DISK_FREE_INVALID")

    def test_gpu_unrecognized_class_invalid(self):
        self.check_block(review_local_model_hardware_report(report(vendors=["RTX4090_OWNED"])),"GPU_VENDOR_LIST_INVALID")

    def test_gpu_unhashable_item_invalid(self):
        self.check_block(review_local_model_hardware_report(report(vendors=[["NVIDIA"]])),"GPU_VENDOR_LIST_INVALID")

    def test_gpu_duplicate_classes_invalid(self):
        self.check_block(review_local_model_hardware_report(report(vendors=["INTEL","INTEL"])),"GPU_VENDOR_LIST_INVALID")

    def test_gpu_unsorted_classes_invalid(self):
        self.check_block(review_local_model_hardware_report(report(vendors=["NVIDIA","AMD"])),"GPU_VENDOR_LIST_INVALID")

    def test_gpu_empty_classes_invalid(self):
        self.check_block(review_local_model_hardware_report(report(vendors=[])),"GPU_VENDOR_LIST_INVALID")

    def test_boolean_source_masquerade_invalid(self):
        self.check_block(review_local_model_hardware_report(report(source=True)),"SOURCE_MODE_INVALID")

    def test_policy_demands_explicit_consent_without_altering_device(self):
        p=hardware_probe_policy()
        self.assertTrue(p["read_only_owner_explicit_consent_required"])
        self.assertTrue(p["only_ci_windows_runner_used_for_automated_probe"])
        for flag in (
            "real_owner_pc_measured","real_dedicated_gpu_vram_verified",
            "real_local_inference_started","model_binary_downloaded",
            "driver_changed","device_modified","data_uploaded",
            "cloud_api_call_made","owner_paid_spend_authorized",
            "install_deployed","worker_activated",
        ):
            self.assertFalse(p[flag],flag)

    def test_no_hardware_sanitized_identifiers_in_script(self):
        script=Path("scripts/aion_local_ai_windows_readonly_hardware_probe_v1.ps1").read_text("utf-8")
        for marker in (
            "SerialNumber", "MachineGuid", "Get-NetIPAddress",
            "Get-Process ", "Get-LocalUser ", "Get-Credential",
            "Invoke-RestMethod", "Invoke-WebRequest", "Start-Process",
            "Set-ItemProperty", "New-ItemProperty", "Set-ExecutionPolicy",
            "Write-Output $env:USERNAME",
        ):
            self.assertNotIn(marker,script)

if __name__ == "__main__":
    unittest.main()
