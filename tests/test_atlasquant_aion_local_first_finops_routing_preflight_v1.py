"""AION local-first / R$200 FinOps routing PREVIEW adversarial test fixtures.

No models run, no owner hardware accessed, no provider called and no spend.
All model scores, hardware numbers and provider quotes are fabricated.
"""
import copy
import unittest

from atlasquant_aion_local_first_finops_routing_preflight_v1 import (
    SCHEMA, BENCHMARK_SCHEMA, BENCHMARK_FIELDS, BENCHMARK_FALSE_FIELDS,
    ASSESSMENT_FALSE, ASSESSMENT_MATERIAL, CANDIDATE, DEGRADE, BLOCKED,
    assess_synthetic_local_model_option, plan_local_first_spending_route,
    local_first_finops_policy, _digest,
)
from atlasquant_aion_local_ai_hardware_readonly_capacity_v1 import SCHEMA as HARDWARE_SCHEMA
from atlasquant_aion_owner_brl200_finops_ceiling_v1 import build_owner_monthly_budget

OWNER, MONTH, AS_OF = "owner-ci", "2026-10", "2026-10-08"
CHALLENGE = "a" * 64
DATASET = "b" * 64
FX = {"rate_brl_per_usd":"5.000000", "observed_date":"2026-10-07","source":"OWNER_QUOTE"}


def hardware(*, ram=16.0, disk=40.0, cpus=8, vendors=None, source="CI_EPHEMERAL"):
    return {
        "schema": HARDWARE_SCHEMA, "source":source,
        "ram_total_gib":ram, "cpu_logical_processors":cpus,
        "system_disk_free_gib":disk,
        "gpu_vendor_classes":["INTEL"] if vendors is None else vendors,
        "dedicated_gpu_vram_verified":False,
        "local_model_execution_tested":False, "model_speed_measured":False,
        "api_usage_charge_read":False, "data_uploaded":False,
        "device_modified":False, "owner_install_approved":False,
        "production_ready":False,
    }


def benchmark(task="GENERAL_TEXT", **changes):
    result = {
        "schema":BENCHMARK_SCHEMA,
        "model_id":"ci-model-tiny-text", "task_kind":task,
        "challenge_sha256":CHALLENGE, "test_dataset_sha256":DATASET,
        "context_tokens":8192,"weights_size_mib":4096,
        "peak_working_ram_mib":6000, "required_dedicated_vram_mib":0,
        "quality_score_per_thousand":900,
        "safety_score_per_thousand":995,"p95_latency_ms":1000,
        "output_tokens_per_second_milli":10000,
        "test_case_count":128, "benchmark_source":"CI_SYNTHETIC_FIXTURE",
        "only_synthetic_ci_samples":True,
        **{k:False for k in BENCHMARK_FALSE_FIELDS},
    }
    result.update(changes)
    return result


def budget(amount=10000):
    return build_owner_monthly_budget([{
        "entry_id":"hosting-ci","owner_id":OWNER,"month":MONTH,
        "category":"hosting","status":"COMMITTED","evidence":"ESTIMATED",
        "currency":"BRL","brl_cents":amount,"usd_micros":None,
    }],expected_month=MONTH,trusted_owner_id=OWNER,as_of=AS_OF)


def paid_brl(amount=3000):
    return {"cost_type":"PAID_EXTERNAL","currency":"BRL",
            "brl_cents":amount,"usd_micros":None}


def paid_usd(micros=1000000):
    return {"cost_type":"PAID_EXTERNAL","currency":"USD",
            "brl_cents":None,"usd_micros":micros}


class AIONLocalFirstFinOpsRoutePreflightV1Tests(unittest.TestCase):
    def setUp(self):
        self.hw = hardware()
        self.bm = benchmark()
        self.assessment = self.evaluate()
        self.money = budget()

    def evaluate(self, h=None, b=None, task="GENERAL_TEXT", challenge=CHALLENGE):
        return assess_synthetic_local_model_option(
            self.hw if h is None else h,
            self.bm if b is None else b,
            expected_challenge_sha256=challenge, expected_task_kind=task,
        )

    def route(self, assessment=None, money=None, **kwargs):
        a=self.assessment if assessment is None else assessment
        return plan_local_first_spending_route(
            a, self.money if money is None else money,
            expected_owner_id=kwargs.pop("owner",OWNER),
            expected_month=kwargs.pop("month",MONTH),
            expected_assessment_digest=kwargs.pop("pin",a.get("assessment_digest")),
            paid_quote=kwargs.pop("quote",None),
            fx_snapshot=kwargs.pop("fx",FX),as_of=kwargs.pop("as_of",AS_OF),
        )

    def blocked(self, result, reason):
        self.assertEqual(result["state"] if "state" in result else result["decision"],
                         BLOCKED, result)
        self.assertIn(reason, result["blockers"], result)

    def test_synthetic_hardware_text_candidate_only(self):
        a=self.assessment
        self.assertEqual(a["state"],CANDIDATE,a)
        self.assertEqual(a["blockers"],[])
        self.assertEqual(a["task_kind"],"GENERAL_TEXT")
        self.assertTrue(a["synthetic_fixture_only"])
        for key in ASSESSMENT_FALSE:self.assertIs(a[key],False,key)

    def test_no_paid_quote_means_local_candidate_advisory(self):
        route=self.route()
        self.assertEqual(route["decision"],"CI_LOCAL_CANDIDATE_REVIEW_ONLY",route)
        self.assertFalse(route["real_local_execution_authorized"])
        self.assertFalse(route["paid_api_request_authorized"])

    def test_task_quality_floor_is_synthetic_only(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        self.assertEqual(a["state"],DEGRADE,a)
        self.assertIn("SIMULATED_TASK_QUALITY_BELOW_THRESHOLD",a["blockers"])

    def test_safety_floor_blocks_local_candidate(self):
        a=self.evaluate(b=benchmark(safety_score_per_thousand=900))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("SIMULATED_TASK_SAFETY_BELOW_THRESHOLD",a["blockers"])

    def test_latency_floor_blocks_local_candidate(self):
        a=self.evaluate(b=benchmark(p95_latency_ms=9999))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("SIMULATED_TASK_LATENCY_ABOVE_THRESHOLD",a["blockers"])

    def test_ram_headroom_threshold_conservative(self):
        a=self.evaluate(b=benchmark(peak_working_ram_mib=14000))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("RAM_HEADROOM_NOT_DEMONSTRATED",a["blockers"])

    def test_low_ram_device_degrades_even_with_good_fixture(self):
        a=self.evaluate(h=hardware(ram=4))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("RAM_HEADROOM_NOT_DEMONSTRATED",a["blockers"])

    def test_disk_headroom_threshold_conservative(self):
        a=self.evaluate(h=hardware(disk=4))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("STORAGE_HEADROOM_NOT_DEMONSTRATED",a["blockers"])

    def test_requires_unmeasured_vram_means_no_gpu_fit_promise(self):
        a=self.evaluate(h=hardware(ram=64,vendors=["NVIDIA"]),
                        b=benchmark(required_dedicated_vram_mib=2048))
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("DEDICATED_GPU_VRAM_NOT_MEASURED",a["blockers"])
        self.assertTrue(a["dedicated_vram_unverified"])

    def test_nvidia_label_does_not_allow_large_gpu_model(self):
        a=self.evaluate(h=hardware(ram=128,vendors=["NVIDIA"]),
                        b=benchmark(required_dedicated_vram_mib=16384))
        self.assertEqual(a["state"],DEGRADE)

    def test_voice_text_intent_uses_strict_latency(self):
        fast=benchmark(task="VOICE_INTENT_TEXT_ONLY",p95_latency_ms=1000)
        a=self.evaluate(b=fast,task="VOICE_INTENT_TEXT_ONLY")
        self.assertEqual(a["state"],CANDIDATE)
        slow=benchmark(task="VOICE_INTENT_TEXT_ONLY",p95_latency_ms=1400)
        a=self.evaluate(b=slow,task="VOICE_INTENT_TEXT_ONLY")
        self.assertEqual(a["state"],DEGRADE)

    def test_business_document_requires_high_quality(self):
        a=self.evaluate(b=benchmark(task="B2B_DOCUMENT_DRAFT",quality_score_per_thousand=820),
                        task="B2B_DOCUMENT_DRAFT")
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("SIMULATED_TASK_QUALITY_BELOW_THRESHOLD",a["blockers"])

    def test_macro_education_requires_extra_safety(self):
        a=self.evaluate(b=benchmark(task="MACRO_EDUCATION",safety_score_per_thousand=985),
                        task="MACRO_EDUCATION")
        self.assertEqual(a["state"],DEGRADE)
        self.assertIn("SIMULATED_TASK_SAFETY_BELOW_THRESHOLD",a["blockers"])

    def test_no_real_trading_or_voice_audio_claim(self):
        a=self.evaluate(b=benchmark(task="MACRO_EDUCATION"),task="MACRO_EDUCATION")
        self.assertEqual(a["state"],CANDIDATE)
        self.assertFalse(a["owner_machine_local_inference_validated"])
        self.assertFalse(a["local_execution_authorized"])

    def test_wrong_task_prevents_fixture_reuse(self):
        self.blocked(self.evaluate(b=benchmark(task="B2B_DOCUMENT_DRAFT")),
                     "TASK_KIND_EXPECTATION_MISMATCH")

    def test_wrong_external_challenge_blocks(self):
        self.blocked(self.evaluate(challenge="c"*64),
                     "CHALLENGE_NOT_EXTERNALLY_PINNED")

    def test_bad_challenge_format_blocks(self):
        self.blocked(self.evaluate(challenge="owner approved"),
                     "CHALLENGE_NOT_EXTERNALLY_PINNED")

    def test_fixture_not_allowed_to_claim_real_benchmark(self):
        self.blocked(self.evaluate(b=benchmark(real_model_executed=True)),
                     "FALSE_BENCHMARK_TRUST_REQUIRED:real_model_executed")

    def test_fixture_not_allowed_to_claim_authenticated_weights(self):
        self.blocked(self.evaluate(b=benchmark(model_weights_authenticated=True)),
                     "FALSE_BENCHMARK_TRUST_REQUIRED:model_weights_authenticated")

    def test_fixture_cannot_enable_paid_provider(self):
        self.blocked(self.evaluate(b=benchmark(paid_provider_called=True)),
                     "FALSE_BENCHMARK_TRUST_REQUIRED:paid_provider_called")

    def test_fixture_extra_owner_secret_field_denied(self):
        self.blocked(self.evaluate(b=benchmark(owner_token="dont send")),
                     "BENCHMARK_EXACT_FIELDS_REQUIRED")

    def test_fixture_missing_synthetic_indicator_denied(self):
        b=benchmark();del b["only_synthetic_ci_samples"]
        self.blocked(self.evaluate(b=b),"BENCHMARK_EXACT_FIELDS_REQUIRED")

    def test_fake_official_model_identifier_denied(self):
        self.blocked(self.evaluate(b=benchmark(model_id="Official-AION-Large")),
                     "MODEL_ID_MUST_BE_INERT_CI_FIXTURE")

    def test_untrusted_dataset_digest_denied_if_malformed(self):
        self.blocked(self.evaluate(b=benchmark(test_dataset_sha256="notsha")),
                     "DATASET_DIGEST_INVALID")

    def test_gpu_negative_vram_denied(self):
        self.blocked(self.evaluate(b=benchmark(required_dedicated_vram_mib=-1)),
                     "BENCHMARK_MEASURE_INVALID:required_dedicated_vram_mib")

    def test_boolean_quality_rejected_instead_of_treated_as_one(self):
        self.blocked(self.evaluate(b=benchmark(quality_score_per_thousand=True)),
                     "BENCHMARK_MEASURE_INVALID:quality_score_per_thousand")

    def test_noninteger_latency_denied(self):
        self.blocked(self.evaluate(b=benchmark(p95_latency_ms=42.5)),
                     "BENCHMARK_MEASURE_INVALID:p95_latency_ms")

    def test_oversized_context_denied(self):
        self.blocked(self.evaluate(b=benchmark(context_tokens=999999)),
                     "BENCHMARK_MEASURE_INVALID:context_tokens")

    def test_unknown_task_denied(self):
        self.blocked(self.evaluate(b=benchmark(task="TRADE_EXECUTE"),task="TRADE_EXECUTE"),
                     "EXPECTED_TASK_NOT_ALLOWED")

    def test_unhashable_hardware_source_blocks_without_crash(self):
        h=hardware(source=["CI_EPHEMERAL"])
        self.blocked(self.evaluate(h=h),"HARDWARE_REVIEW_BLOCKED")

    def test_invalid_hardware_extra_fields_block(self):
        self.blocked(self.evaluate(h=dict(hardware(),user="private")),
                     "HARDWARE_EXACT_FIELDS_REQUIRED")

    def test_fake_hardware_actual_benchmark_claim_rejected(self):
        self.blocked(self.evaluate(h=dict(hardware(),local_model_execution_tested=True)),
                     "HARDWARE_REVIEW_BLOCKED")

    def test_budget_routes_local_before_paid_even_with_quote(self):
        decision=self.route(quote=paid_brl(1000))
        self.assertEqual(decision["decision"],"CI_LOCAL_CANDIDATE_REVIEW_ONLY")
        self.assertFalse(decision["provider_api_called"])

    def test_low_quality_defaults_to_queue_not_external_api(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        r=self.route(assessment=a)
        self.assertEqual(r["decision"],"CI_LOCAL_DEGRADE_OR_QUEUE_NO_PAID_FALLBACK")
        self.assertFalse(r["paid_api_request_authorized"])

    def test_paid_quote_under_cap_is_proposal_not_authorization(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        r=self.route(assessment=a,quote=paid_brl(1000))
        self.assertEqual(r["decision"],"CI_PAID_FALLBACK_PROPOSAL_REQUIRES_NEW_OWNER_APPROVAL",r)
        self.assertFalse(r["owner_approval_consumed"])
        self.assertFalse(r["paid_reservation_written"])

    def test_paid_quote_over_monthly_cap_blocked(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        r=self.route(assessment=a,money=budget(19800),quote=paid_brl(3000))
        self.assertEqual(r["decision"],"BLOCKED_PAID_FALLBACK",r)
        self.assertIn("PROJECTED_OWNER_CAP_EXCEEDED",r["blockers"])

    def test_usd_paid_quote_with_fresh_fx_still_requires_owner_approval(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        r=self.route(assessment=a,quote=paid_usd())
        self.assertEqual(r["decision"],"CI_PAID_FALLBACK_PROPOSAL_REQUIRES_NEW_OWNER_APPROVAL")
        self.assertFalse(r["paid_api_request_authorized"])

    def test_usd_paid_quote_stale_fx_blocks(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        old_fx=dict(FX, observed_date="2026-10-01")
        r=self.route(assessment=a,quote=paid_usd(),fx=old_fx)
        self.assertEqual(r["decision"],"BLOCKED_PAID_FALLBACK")
        self.assertIn("FX_RATE_STALE_OR_FUTURE",r["blockers"])

    def test_foreign_owner_budget_blocked(self):
        self.assertIn("BUDGET_OWNER_MONTH_SCOPE_MISMATCH",
                      self.route(owner="another-owner")["blockers"])

    def test_wrong_budget_month_blocks(self):
        self.assertIn("BUDGET_OWNER_MONTH_SCOPE_MISMATCH",
                      self.route(month="2026-11")["blockers"])

    def test_invalid_accounting_date_blocks(self):
        self.assertIn("REQUEST_BUDGET_DATE_INVALID",
                      self.route(as_of="2026-10-35")["blockers"])

    def test_cross_month_date_blocks(self):
        self.assertIn("REQUEST_BUDGET_DATE_MISMATCH",
                      self.route(as_of="2026-11-01")["blockers"])

    def test_budget_forecast_forgery_blocks(self):
        b=dict(self.money,forecast_brl_cents=0)
        self.assertIn("BUDGET_SNAPSHOT_DIGEST_INVALID",self.route(money=b)["blockers"])

    def test_budget_fake_production_enforcement_blocks(self):
        b=dict(self.money,cap_is_real_payment_enforcement=True)
        self.assertTrue(any("UNTRUSTED_BUDGET_AUTHORITY" in x
                            for x in self.route(money=b)["blockers"]))

    def test_a_tampered_assessment_state_without_digest_update_blocks(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        a["state"]=CANDIDATE
        r=self.route(assessment=a)
        self.assertEqual(r["decision"],BLOCKED)
        self.assertIn("ASSESSMENT_SNAPSHOT_OR_EXTERNAL_PIN_MISMATCH",r["blockers"])

    def test_a_rehashed_fake_state_still_lacks_pass_flags(self):
        a=self.evaluate(b=benchmark(quality_score_per_thousand=700))
        a["state"]=CANDIDATE
        a["blockers"]=[]
        a["assessment_digest"]=_digest({
            **{k:a.get(k) for k in ASSESSMENT_MATERIAL},
            "state":a["state"],"blockers":a["blockers"],
        })
        r=self.route(assessment=a)
        self.assertEqual(r["decision"],BLOCKED)
        self.assertIn("FORGED_CANDIDATE_PASS_FLAGS",r["blockers"])

    def test_external_assessment_digest_pin_matters(self):
        r=self.route(pin="c"*64)
        self.assertEqual(r["decision"],BLOCKED)
        self.assertIn("ASSESSMENT_SNAPSHOT_OR_EXTERNAL_PIN_MISMATCH",r["blockers"])

    def test_fake_owner_approval_in_assessment_denied(self):
        a=dict(self.assessment,owner_approval_consumed=True)
        r=self.route(assessment=a)
        self.assertEqual(r["decision"],BLOCKED)
        self.assertIn("FALSE_LOCAL_OR_SPEND_TRUST_REQUIRED:owner_approval_consumed",r["blockers"])

    def test_injected_paid_route_proof_blocks(self):
        a=dict(self.assessment, real_provider_paid=True)
        r=self.route(assessment=a)
        self.assertEqual(r["decision"],BLOCKED)
        self.assertIn("ASSESSMENT_EXACT_FIELDS_REQUIRED",r["blockers"])

    def test_no_genuine_model_or_external_provider_work(self):
        p=local_first_finops_policy()
        self.assertEqual(p["hard_cap_owner_brl_cents"],20000)
        self.assertTrue(p["prefers_local_or_queue_before_paid"])
        self.assertTrue(p["separate_owner_approval_required_for_spend"])
        for name in (
            "genuine_hardware_verified","real_local_model_tested",
            "official_model_weights_authenticated",
            "real_quality_or_safety_metrics_confirmed",
            "energy_costs_verified","zero_cost_guaranteed",
            "real_paid_provider_call_enabled","real_owner_approval_used",
            "real_router_deployed","owner_device_accessed","worker_activated",
        ):
            self.assertFalse(p[name],name)

if __name__=="__main__":
    unittest.main()
