"""AION Local-First Model + R$200 FinOps route preflight V1.

Pure planning functions; NO inference, downloading, hardware probe, API call,
real benchmark, owner approval, deployment or paid provider execution.
Hardware is self-reported and benchmarks are SYNTHETIC CI FIXTURES ONLY.
An advertised CI candidate is never evidence that a real model runs locally.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_local_ai_hardware_readonly_capacity_v1 import (
    SCHEMA as HARDWARE_SCHEMA, INPUT_KEYS as HARDWARE_FIELDS,
    review_local_model_hardware_report,
)
from atlasquant_aion_owner_brl200_finops_ceiling_v1 import (
    HARD_CAP_CENTS, preflight_owner_paid_request,
)
from atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1 import (
    _validate_budget,
)

SCHEMA = "ATLASQUANT_AION_LOCAL_FIRST_FINOPS_ROUTE_PREFLIGHT_V1"
BENCHMARK_SCHEMA = "ATLASQUANT_AION_SYNTHETIC_MODEL_BENCHMARK_FIXTURE_V1"
BLOCKED = "BLOCKED"
CANDIDATE = "CI_SYNTHETIC_LOCAL_OPTION_FOR_REVIEW_ONLY"
DEGRADE = "CI_LOCAL_QUEUE_OR_DEGRADE_REVIEW_ONLY"
MAX_CONTEXT_TOKENS = 131072
TASK_LIMITS = {
    # Test fixture thresholds, not guarantees about real model suitability.
    "GENERAL_TEXT": {"quality":750, "safety":950, "p95_ms":5000},
    "B2B_DOCUMENT_DRAFT": {"quality":850, "safety":980, "p95_ms":6000},
    "MACRO_EDUCATION": {"quality":870, "safety":990, "p95_ms":6500},
    "VOICE_INTENT_TEXT_ONLY": {"quality":850, "safety":990, "p95_ms":1200},
}
BENCHMARK_FIELDS = {
    "schema", "model_id", "task_kind", "challenge_sha256",
    "test_dataset_sha256", "context_tokens", "weights_size_mib",
    "peak_working_ram_mib", "required_dedicated_vram_mib",
    "quality_score_per_thousand", "safety_score_per_thousand",
    "p95_latency_ms", "output_tokens_per_second_milli",
    "test_case_count", "benchmark_source",
    "only_synthetic_ci_samples", "real_model_executed",
    "real_hardware_benchmarked", "model_weights_authenticated",
    "owner_pc_hardware_attested", "production_routing_enabled",
    "paid_provider_called", "owner_approval_consumed",
}
BENCHMARK_FALSE_FIELDS = (
    "real_model_executed", "real_hardware_benchmarked",
    "model_weights_authenticated", "owner_pc_hardware_attested",
    "production_routing_enabled", "paid_provider_called",
    "owner_approval_consumed",
)
ASSESSMENT_MATERIAL = (
    "model_id", "task_kind", "challenge_sha256", "hardware_digest",
    "fixture_digest", "simulated_quality_pass", "simulated_safety_pass",
    "simulated_latency_pass", "simulated_ram_headroom_pass",
    "simulated_disk_headroom_pass", "dedicated_vram_unverified",
    "simulated_cpu_only_candidate", "test_case_count",
)
ASSESSMENT_FALSE = (
    "authentic_hardware_provenance", "real_model_benchmark_verified",
    "owner_machine_local_inference_validated",
    "model_package_trust_established", "local_execution_authorized",
    "paid_provider_execution_authorized", "production_model_router_active",
    "owner_device_accessed", "data_transferred", "deploy_executed",
    "worker_activated", "owner_approval_consumed",
)
ASSESSMENT_FIELDS = set(ASSESSMENT_MATERIAL) | {
    "schema", "state", "blockers", "assessment_digest",
    "synthetic_fixture_only",
} | set(ASSESSMENT_FALSE)
NAME = re.compile(r"ci-model-[a-z0-9][a-z0-9-]{2,55}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def _strict_int(x: Any, low: int, high: int) -> bool:
    return type(x) is int and low <= x <= high


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")).hexdigest()


def _safe_digest(value: Any) -> str:
    try:
        return _digest(value)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ""


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def assess_synthetic_local_model_option(
    hardware: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any] | None,
    *,
    expected_challenge_sha256: str,
    expected_task_kind: str,
) -> dict[str, Any]:
    """Compare claimed CI fixture numbers with untrusted hardware readings.

    This deliberately never initiates or certifies ANY model execution.
    """
    h, b = _dict(hardware), _dict(benchmark)
    errors: list[str] = []
    if set(h) != HARDWARE_FIELDS:
        errors.append("HARDWARE_EXACT_FIELDS_REQUIRED")
    hardware_review = review_local_model_hardware_report(h)
    if hardware_review["state"] != "READ_ONLY_CAPACITY_ADVISORY_UNTRUSTED":
        errors.append("HARDWARE_REVIEW_BLOCKED")
        errors.extend("HARDWARE:" + x for x in hardware_review["blockers"])
    if set(b) != BENCHMARK_FIELDS:
        errors.append("BENCHMARK_EXACT_FIELDS_REQUIRED")
    if b.get("schema") != BENCHMARK_SCHEMA:
        errors.append("BENCHMARK_SCHEMA_INVALID")
    if b.get("benchmark_source") != "CI_SYNTHETIC_FIXTURE":
        errors.append("SYNTHETIC_BENCHMARK_SOURCE_REQUIRED")
    if b.get("only_synthetic_ci_samples") is not True:
        errors.append("SYNTHETIC_ONLY_INDICATOR_REQUIRED")
    for name in BENCHMARK_FALSE_FIELDS:
        if b.get(name) is not False:
            errors.append("FALSE_BENCHMARK_TRUST_REQUIRED:" + name)
    model_id=b.get("model_id")
    if type(model_id) is not str or not NAME.fullmatch(model_id):
        errors.append("MODEL_ID_MUST_BE_INERT_CI_FIXTURE")
    if type(expected_task_kind) is not str or expected_task_kind not in TASK_LIMITS:
        errors.append("EXPECTED_TASK_NOT_ALLOWED")
    if b.get("task_kind") != expected_task_kind:
        errors.append("TASK_KIND_EXPECTATION_MISMATCH")
    if (type(expected_challenge_sha256) is not str or
        not DIGEST.fullmatch(expected_challenge_sha256) or
        b.get("challenge_sha256") != expected_challenge_sha256):
        errors.append("CHALLENGE_NOT_EXTERNALLY_PINNED")
    dataset=b.get("test_dataset_sha256")
    if type(dataset) is not str or not DIGEST.fullmatch(dataset):
        errors.append("DATASET_DIGEST_INVALID")
    for field, low, high in (
        ("context_tokens", 256, MAX_CONTEXT_TOKENS),
        ("weights_size_mib", 1, 524288),
        ("peak_working_ram_mib", 1, 524288),
        ("required_dedicated_vram_mib", 0, 524288),
        ("quality_score_per_thousand", 0, 1000),
        ("safety_score_per_thousand", 0, 1000),
        ("p95_latency_ms", 1, 600000),
        ("output_tokens_per_second_milli", 0, 100000000),
        ("test_case_count", 1, 100000),
    ):
        if not _strict_int(b.get(field), low, high):
            errors.append("BENCHMARK_MEASURE_INVALID:" + field)

    limits = TASK_LIMITS.get(expected_task_kind, {"quality":1001,"safety":1001,"p95_ms":0})
    q = b.get("quality_score_per_thousand")
    safety = b.get("safety_score_per_thousand")
    latency = b.get("p95_latency_ms")
    quality_ok = _strict_int(q,0,1000) and q >= limits["quality"]
    safety_ok = _strict_int(safety,0,1000) and safety >= limits["safety"]
    latency_ok = _strict_int(latency,1,600000) and latency <= limits["p95_ms"]
    ram = hardware_review["ram_total_gib"]
    disk = hardware_review["system_disk_free_gib"]
    mem = b.get("peak_working_ram_mib")
    weight = b.get("weights_size_mib")
    ram_ok = (
        type(ram) in (float,int) and _strict_int(mem,1,524288)
        and mem * 100 <= int(ram * 1024) * 65
    )
    disk_ok = (
        type(disk) in (float,int) and _strict_int(weight,1,524288)
        and weight * 100 <= int(disk * 1024) * 75
    )
    vram=b.get("required_dedicated_vram_mib")
    cpu_only=_strict_int(vram,0,524288) and vram == 0
    if not quality_ok:
        errors.append("SIMULATED_TASK_QUALITY_BELOW_THRESHOLD")
    if not safety_ok:
        errors.append("SIMULATED_TASK_SAFETY_BELOW_THRESHOLD")
    if not latency_ok:
        errors.append("SIMULATED_TASK_LATENCY_ABOVE_THRESHOLD")
    if not ram_ok:
        errors.append("RAM_HEADROOM_NOT_DEMONSTRATED")
    if not disk_ok:
        errors.append("STORAGE_HEADROOM_NOT_DEMONSTRATED")
    if not cpu_only:
        errors.append("DEDICATED_GPU_VRAM_NOT_MEASURED")
    errors = list(dict.fromkeys(errors))
    shape_errors = [x for x in errors if x not in {
        "SIMULATED_TASK_QUALITY_BELOW_THRESHOLD",
        "SIMULATED_TASK_SAFETY_BELOW_THRESHOLD",
        "SIMULATED_TASK_LATENCY_ABOVE_THRESHOLD",
        "RAM_HEADROOM_NOT_DEMONSTRATED",
        "STORAGE_HEADROOM_NOT_DEMONSTRATED",
        "DEDICATED_GPU_VRAM_NOT_MEASURED",
    }]
    state = BLOCKED if shape_errors else (DEGRADE if errors else CANDIDATE)
    material={
        "model_id": model_id if type(model_id) is str else "",
        "task_kind": expected_task_kind if type(expected_task_kind) is str else "",
        "challenge_sha256":expected_challenge_sha256 if type(expected_challenge_sha256) is str else "",
        "hardware_digest":_safe_digest(h),
        "fixture_digest":_safe_digest(b),
        "simulated_quality_pass":bool(quality_ok),
        "simulated_safety_pass":bool(safety_ok),
        "simulated_latency_pass":bool(latency_ok),
        "simulated_ram_headroom_pass":bool(ram_ok),
        "simulated_disk_headroom_pass":bool(disk_ok),
        "dedicated_vram_unverified":True,
        "simulated_cpu_only_candidate":bool(cpu_only),
        "test_case_count":b.get("test_case_count") if _strict_int(b.get("test_case_count"),1,100000) else 0,
    }
    if not material["hardware_digest"] or not material["fixture_digest"]:
        errors.append("NONJSON_HARDWARE_OR_BENCHMARK_INPUT")
        state=BLOCKED
    return {
        "schema":SCHEMA, "state":state, "blockers":errors,
        **material, "assessment_digest":_safe_digest({
            **material, "state":state, "blockers":errors,
        }) if state != BLOCKED else "",
        "synthetic_fixture_only":True,
        **{f:False for f in ASSESSMENT_FALSE},
    }


def plan_local_first_spending_route(
    assessment: Mapping[str, Any] | None,
    budget: Mapping[str, Any] | None,
    *,
    expected_owner_id: str, expected_month: str,
    expected_assessment_digest: str,
    paid_quote: Mapping[str, Any] | None = None,
    fx_snapshot: Mapping[str, Any] | None = None,
    as_of: str,
) -> dict[str, Any]:
    """Never calls a provider; a paid quote can only be a human-review proposal."""
    a, b = _dict(assessment), _dict(budget)
    errors: list[str] = []
    if set(a) != ASSESSMENT_FIELDS or a.get("schema") != SCHEMA:
        errors.append("ASSESSMENT_EXACT_FIELDS_REQUIRED")
    if a.get("synthetic_fixture_only") is not True:
        errors.append("SYNTHETIC_BENCHMARK_ONLY")
    for f in ASSESSMENT_FALSE:
        if a.get(f) is not False:
            errors.append("FALSE_LOCAL_OR_SPEND_TRUST_REQUIRED:" + f)
    if a.get("state") not in (CANDIDATE, DEGRADE):
        errors.append("ASSESSMENT_NOT_REVIEWABLE")
    if a.get("state") == CANDIDATE and a.get("blockers") != []:
        errors.append("CANDIDATE_BLOCKERS_NOT_EMPTY")
    if a.get("state") == DEGRADE and (
        type(a.get("blockers")) is not list or not a["blockers"]
    ):
        errors.append("DEGRADED_CANDIDATE_MUST_HAVE_BLOCKERS")
    material={k:a.get(k) for k in ASSESSMENT_MATERIAL}
    expected_digest = _safe_digest({
        **material, "state":a.get("state"), "blockers":a.get("blockers"),
    })
    if (not expected_digest or a.get("assessment_digest") != expected_digest
        or a.get("assessment_digest") != expected_assessment_digest
        or type(expected_assessment_digest) is not str
        or not DIGEST.fullmatch(expected_assessment_digest)):
        errors.append("ASSESSMENT_SNAPSHOT_OR_EXTERNAL_PIN_MISMATCH")
    if a.get("state") == CANDIDATE and not (
        a.get("simulated_quality_pass") is True
        and a.get("simulated_safety_pass") is True
        and a.get("simulated_latency_pass") is True
        and a.get("simulated_ram_headroom_pass") is True
        and a.get("simulated_disk_headroom_pass") is True
        and a.get("simulated_cpu_only_candidate") is True
        and a.get("dedicated_vram_unverified") is True
    ):
        errors.append("FORGED_CANDIDATE_PASS_FLAGS")
    try:
        errors.extend(_validate_budget(b))
    except (TypeError, ValueError, RecursionError, OverflowError):
        errors.append("BUDGET_NOT_JSON_COMPATIBLE")
    if type(expected_owner_id) is not str or not expected_owner_id:
        errors.append("EXPECTED_OWNER_ID_REQUIRED")
    if type(expected_month) is not str or not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", expected_month):
        errors.append("EXPECTED_MONTH_INVALID")
    if b.get("owner_id") != expected_owner_id or b.get("expected_month") != expected_month:
        errors.append("BUDGET_OWNER_MONTH_SCOPE_MISMATCH")
    if b.get("hard_cap_brl_cents") != HARD_CAP_CENTS:
        errors.append("OWNER_R200_CAP_NOT_ENFORCED")
    try:
        parsed = date.fromisoformat(as_of if type(as_of) is str else "")
        if parsed.strftime("%Y-%m") != expected_month:
            errors.append("REQUEST_BUDGET_DATE_MISMATCH")
    except ValueError:
        errors.append("REQUEST_BUDGET_DATE_INVALID")
    if errors:
        decision="BLOCKED"
    elif a["state"] == CANDIDATE:
        decision="CI_LOCAL_CANDIDATE_REVIEW_ONLY"
    elif paid_quote is None:
        decision="CI_LOCAL_DEGRADE_OR_QUEUE_NO_PAID_FALLBACK"
    else:
        quote = preflight_owner_paid_request(
            b, quote=paid_quote, fx_snapshot=fx_snapshot, as_of=as_of,
        )
        if quote.get("decision") == "REQUIRES_SEPARATE_OWNER_APPROVAL":
            decision="CI_PAID_FALLBACK_PROPOSAL_REQUIRES_NEW_OWNER_APPROVAL"
        else:
            decision="BLOCKED_PAID_FALLBACK"
            errors.extend(quote.get("blockers", []))
    return {
        "schema":SCHEMA, "decision":decision, "blockers":list(dict.fromkeys(errors)),
        "owner_month": expected_month if type(expected_month) is str else "",
        "owner_budget_target_brl_cents":HARD_CAP_CENTS,
        "unverified_forecast_brl_cents":b.get("forecast_brl_cents")
           if type(b.get("forecast_brl_cents")) is int else None,
        "assessment_digest":expected_digest if not errors else "",
        "ci_fixture_only":True,
        "real_hardware_compatibility_verified":False,
        "real_task_quality_verified":False,
        "real_local_execution_authorized":False,
        "paid_api_request_authorized":False,
        "owner_approval_consumed":False,
        "paid_reservation_written":False,
        "provider_api_called":False,
        "model_downloaded":False,
        "owner_device_accessed":False,
        "data_transferred":False,
        "production_model_routing_activated":False,
        "deploy_executed":False,
        "worker_activated":False,
    }


def local_first_finops_policy() -> dict[str, Any]:
    return {
        "schema":SCHEMA, "hard_cap_owner_brl_cents":HARD_CAP_CENTS,
        "prefers_local_or_queue_before_paid":True,
        "synthetic_benchmarks_only":True,
        "separate_owner_approval_required_for_spend":True,
        "genuine_hardware_verified":False,
        "real_local_model_tested":False,
        "official_model_weights_authenticated":False,
        "real_quality_or_safety_metrics_confirmed":False,
        "energy_costs_verified":False,
        "zero_cost_guaranteed":False,
        "real_paid_provider_call_enabled":False,
        "real_owner_approval_used":False,
        "real_router_deployed":False,
        "owner_device_accessed":False,
        "worker_activated":False,
    }
