"""AION Local-First Windows hardware sizing review, planning only V1.

Treat all hardware values as UNTRUSTED / limited Windows inventory readings.
Not a model benchmark, true dedicated VRAM measurement, real owner-device
attestation, permission to install, or proof of zero recurring AI expenses.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_LOCAL_AI_HARDWARE_READONLY_V1"
REVIEW = "ATLASQUANT_AION_LOCAL_AI_CAPACITY_REVIEW_V1"
INPUT_KEYS = {
    "schema", "source", "ram_total_gib", "cpu_logical_processors",
    "system_disk_free_gib", "gpu_vendor_classes",
    "dedicated_gpu_vram_verified", "local_model_execution_tested",
    "model_speed_measured", "api_usage_charge_read", "data_uploaded",
    "device_modified", "owner_install_approved", "production_ready",
}
VENDORS = {"NVIDIA", "AMD", "INTEL", "OTHER_OR_UNKNOWN"}
SOURCES = {"CI_EPHEMERAL", "OWNER_EXPLICIT_READ_ONLY"}
ALWAYS_FALSE = (
    "dedicated_gpu_vram_verified", "local_model_execution_tested",
    "model_speed_measured", "api_usage_charge_read", "data_uploaded",
    "device_modified", "owner_install_approved", "production_ready",
)
FALSE_RESULTS = (
    "actual_owner_device_verified", "gpu_memory_confirmed",
    "model_can_run_at_target_latency", "large_model_fit_verified",
    "energy_cost_confirmed", "zero_recurring_spend_guaranteed",
    "paid_provider_disabled", "aion_installed", "worker_activated",
    "production_deployed", "device_modified", "owner_authorization_consumed",
)

def _finite_number(x: Any, *, low: float, high: float) -> bool:
    return type(x) in (float,int) and math.isfinite(x) and low <= x <= high

def review_local_model_hardware_report(report: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(report) if isinstance(report, Mapping) else {}
    errors: list[str] = []
    if set(raw) != INPUT_KEYS:
        errors.append("EXACT_READONLY_REPORT_FIELDS_REQUIRED")
    if raw.get("schema") != SCHEMA:
        errors.append("REPORT_SCHEMA_MISMATCH")
    if type(raw.get("source")) is not str or raw.get("source") not in SOURCES:
        errors.append("SOURCE_MODE_INVALID")
    for key in ALWAYS_FALSE:
        if raw.get(key) is not False:
            errors.append("FALSE_DEVICE_TRUST_CLAIM_REQUIRED:" + key)
    if not _finite_number(raw.get("ram_total_gib"), low=0.01, high=4096):
        errors.append("RAM_TOTAL_INVALID")
    if not _finite_number(raw.get("system_disk_free_gib"), low=0, high=1048576):
        errors.append("DISK_FREE_INVALID")
    cpus=raw.get("cpu_logical_processors")
    if type(cpus) is not int or cpus < 1 or cpus > 4096:
        errors.append("CPU_LOGICAL_COUNT_INVALID")
    gpus=raw.get("gpu_vendor_classes")
    if (type(gpus) is not list or not 1 <= len(gpus) <= 4 or
        any(type(v) is not str or v not in VENDORS for v in gpus) or
        gpus != sorted(set(gpus))):
        errors.append("GPU_VENDOR_LIST_INVALID")
    has_dedicated_vendor = type(gpus) is list and any(
        x in ("AMD","NVIDIA") for x in gpus if type(x) is str
    )
    ram=raw.get("ram_total_gib")
    disk=raw.get("system_disk_free_gib")
    if errors:
        tier="BLOCKED"
        blockers=list(dict.fromkeys(errors))
    elif ram < 8 or disk < 10:
        tier="HARDWARE_CONSTRAINED_BENCHMARK_REQUIRED"
        blockers=["MINIMUM_EXPERIMENT_HEADROOM_LOW"]
    elif ram < 16 or disk < 25:
        tier="LIGHT_LOCAL_MODEL_EXPERIMENT_CANDIDATE"
        blockers=[]
    elif has_dedicated_vendor:
        tier="GPU_LOCAL_MODEL_BENCHMARK_CANDIDATE"
        blockers=[]
    else:
        tier="CPU_OR_UNKNOWN_GPU_LOCAL_BENCHMARK_CANDIDATE"
        blockers=[]
    return {
        "schema": REVIEW,
        "state": "BLOCKED" if errors else "READ_ONLY_CAPACITY_ADVISORY_UNTRUSTED",
        "advisory_tier": tier, "blockers": blockers,
        "source": raw.get("source") if raw.get("source") in SOURCES else "",
        "ram_total_gib":ram if _finite_number(ram,low=0.01,high=4096) else None,
        "system_disk_free_gib":disk if _finite_number(disk,low=0,high=1048576) else None,
        "cpu_logical_processors":cpus if type(cpus) is int and 1 <= cpus <= 4096 else None,
        "has_amd_or_nvidia_vendor_label":has_dedicated_vendor,
        "model_performance_benchmark_required":True,
        "gpu_vram_driver_or_runtime_measurement_required":True,
        "owner_payment_authorization_required_for_any_paid_fallback":True,
        "resource_evidence_is_only_self_reported":True,
        **{key:False for key in FALSE_RESULTS},
    }

def hardware_probe_policy() -> dict[str, Any]:
    return {
        "schema": REVIEW,
        "read_only_owner_explicit_consent_required":True,
        "only_ci_windows_runner_used_for_automated_probe":True,
        "hardware_fields_are_aggregates_only":True,
        "no_usernames_or_device_serials_exported":True,
        "does_not_measure_model_speed":True,
        "real_owner_pc_measured":False,
        "real_dedicated_gpu_vram_verified":False,
        "real_local_inference_started":False,
        "model_binary_downloaded":False,
        "driver_changed":False,
        "device_modified":False,
        "data_uploaded":False,
        "cloud_api_call_made":False,
        "owner_paid_spend_authorized":False,
        "install_deployed":False,
        "worker_activated":False,
    }
