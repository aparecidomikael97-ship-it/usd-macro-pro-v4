"""AION offline benchmark: adversarial validation, no model/paid API calls.

Samples are synthetic; manual labels are not automated semantic grading.
The review tool reads only explicitly supplied fixture JSON files in CI.
"""
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from atlasquant_aion_offline_local_model_benchmark_evidence_v1 import (
    SCHEMA, REVIEW_SCHEMA, TASKS, SCENARIOS, RAW_FIELDS, SAMPLE_FIELDS,
    FALSE_OUTPUT, scenario_pack, scenario_pack_digest,
    review_offline_model_benchmark, benchmark_protocol_policy,
)
from scripts.aion_offline_model_benchmark_review_v1 import blank_report_template

CHALLENGE="a"*64
MODEL_SHA="b"*64
HARDWARE="c"*64


def report():
    data=blank_report_template()
    data["source"]="CI_SYNTHETIC"
    data["model_ref"]="ci-model-small-local-fixture"
    data["session_id"]="offline-ci-evaluation-0001"
    data["challenge_sha256"]=CHALLENGE
    data["model_artifact_sha256"]=MODEL_SHA
    data["hardware_report_digest"]=HARDWARE
    for entry in data["samples"]:
        entry["elapsed_ms"]=500
        entry["input_tokens"]=40
        entry["output_tokens"]=50
        entry["peak_ram_mib"]=3200
        entry["peak_dedicated_vram_mib"]=None
        if entry["phase"]=="MEASURE":
            entry["quality_review"]="PASS"
            entry["safety_review"]="PASS"
    return data


def check(data, **pins):
    return review_offline_model_benchmark(
        data,expected_challenge_sha256=pins.get("challenge",CHALLENGE),
        expected_model_artifact_sha256=pins.get("model",MODEL_SHA),
        expected_hardware_report_digest=pins.get("hardware",HARDWARE),
    )


class AIONOfflineModelBenchmarkEvidenceV1Tests(unittest.TestCase):
    def blocked(self, data, fragment=None):
        r=check(data)
        self.assertEqual(r["state"],"BLOCKED",r)
        if fragment:
            self.assertTrue(any(fragment in reason for reason in r["blockers"]),r)
        self.assertFalse(r["production_model_routing_enabled"])
        self.assertFalse(r["owner_payment_authorized"])
        return r

    def test_16_prompt_pack_scenarios_are_public_and_deterministic(self):
        p=scenario_pack()
        self.assertEqual(len(TASKS),4)
        self.assertEqual(sum(len(v) for v in SCENARIOS.values()),16)
        self.assertEqual(p["measured_samples_per_scenario"],5)
        self.assertEqual(p["warmup_samples_per_task"],2)
        self.assertEqual(scenario_pack_digest(),scenario_pack_digest())
        self.assertEqual(len(scenario_pack_digest()),64)

    def test_manifest_and_report_schema_differ(self):
        p=blank_report_template()
        self.assertEqual(p["schema"],SCHEMA)
        self.assertEqual(len(p["samples"]),88)
        self.assertEqual(set(p),RAW_FIELDS)
        self.assertEqual(set(p["samples"][0]),SAMPLE_FIELDS)
        self.assertEqual(p["scenario_pack_digest"],scenario_pack_digest())

    def test_blank_template_is_invalid_until_measured(self):
        self.blocked(blank_report_template(),"SAMPLE_METRIC_INVALID")

    def test_synthetic_88_samples_only_generate_untrusted_review(self):
        r=check(report())
        self.assertEqual(r["state"],"CI_OR_MANUAL_MEASUREMENTS_UNVERIFIED_HUMAN_REVIEW_REQUIRED",r)
        self.assertEqual(r["blockers"],[])
        self.assertEqual(r["valid_sample_count"],88)
        self.assertEqual(len(r["task_summaries"]),4)
        for task in r["task_summaries"]:
            self.assertEqual(task["samples"],20)
            self.assertEqual(task["p95_latency_ms"],500)
            self.assertEqual(task["quality_passes"],20)
            self.assertEqual(task["safety_failures"],0)
            self.assertEqual(task["self_reported_review_status"],
                "SELF_REPORTED_NUMBERS_MEET_TEST_THRESHOLDS_UNTRUSTED")

    def test_no_output_can_claim_production_verified_or_pay(self):
        r=check(report())
        self.assertTrue(r["all_metrics_and_manual_scores_are_unverified_claims"])
        for field in FALSE_OUTPUT:
            self.assertIs(r[field],False,field)

    def test_no_raw_answers_or_private_prompt_data_in_output(self):
        r=check(report())
        payload=json.dumps(r)
        self.assertNotIn("prompt_text",payload)
        self.assertNotIn("answer_text",payload)
        self.assertNotIn("api_key",payload)
        self.assertNotIn("credentials",payload)

    def test_bad_model_id_rejected(self):
        d=report();d["model_ref"]="C:\\Users\\Private\\model.gguf"
        self.blocked(d,"MODEL_REFERENCE_ID_INVALID")

    def test_fake_official_model_run_cannot_claim_external_attestation(self):
        d=report();d["artifact_authenticated_externally"]=True
        self.blocked(d,"FALSE_TRUST_CLAIM_REQUIRED:artifact_authenticated_externally")

    def test_fake_owner_hardware_authentication_rejected(self):
        d=report();d["hardware_authenticated_externally"]=True
        self.blocked(d,"FALSE_TRUST_CLAIM_REQUIRED:hardware_authenticated_externally")

    def test_paid_fallback_authority_rejected(self):
        d=report();d["paid_fallback_authorized"]=True
        self.blocked(d,"FALSE_TRUST_CLAIM_REQUIRED:paid_fallback_authorized")

    def test_fake_quality_certification_rejected(self):
        d=report();d["human_quality_certified"]=True
        self.blocked(d,"FALSE_TRUST_CLAIM_REQUIRED:human_quality_certified")

    def test_fake_deployment_approval_rejected(self):
        d=report();d["deploy_authorized"]=True
        self.blocked(d,"FALSE_TRUST_CLAIM_REQUIRED:deploy_authorized")

    def test_raw_answer_field_forbidden(self):
        d=report();d["samples"][0]["answer_text"]="private chat content"
        self.blocked(d,"SAMPLE_EXACT_FIELDS_REQUIRED")

    def test_report_cannot_include_token_or_pii_field(self):
        d=report();d["api_key"]="sk-fake"
        self.blocked(d,"REPORT_EXACT_FIELDS_REQUIRED")

    def test_extra_username_field_rejected(self):
        d=report();d["windows_username"]="fake-name"
        self.blocked(d,"REPORT_EXACT_FIELDS_REQUIRED")

    def test_missing_privacy_signal_rejected(self):
        d=report();del d["prompts_and_responses_excluded"]
        self.blocked(d,"REPORT_EXACT_FIELDS_REQUIRED")

    def test_data_export_claim_blocks(self):
        d=report();d["prompts_and_responses_excluded"]=False
        self.blocked(d,"RAW_PRIVATE_TEXT_FIELDS_NOT_ALLOWED")

    def test_network_mode_not_permitted(self):
        d=report();d["no_network_claimed"]=False
        self.blocked(d,"OFFLINE_AND_NO_PAID_CLAIMS_REQUIRED")

    def test_paid_api_mode_not_permitted(self):
        d=report();d["no_paid_api_claimed"]=False
        self.blocked(d,"OFFLINE_AND_NO_PAID_CLAIMS_REQUIRED")

    def test_malformed_model_digest_denied(self):
        d=report();d["model_artifact_sha256"]="a"*63
        self.blocked(d,"EVIDENCE_DIGEST_FORMAT_INVALID:model_artifact_sha256")

    def test_pinning_another_model_artifact_denied(self):
        r=check(report(),model="d"*64)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("EXTERNAL_EVIDENCE_PIN_MISMATCH:model_artifact_sha256",r["blockers"])

    def test_pinning_another_hardware_report_denied(self):
        r=check(report(),hardware="d"*64)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("EXTERNAL_EVIDENCE_PIN_MISMATCH:hardware_report_digest",r["blockers"])

    def test_pinning_another_challenge_denied(self):
        r=check(report(),challenge="d"*64)
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("EXTERNAL_EVIDENCE_PIN_MISMATCH:challenge_sha256",r["blockers"])

    def test_old_scenario_pack_version_denied(self):
        d=report();d["scenario_pack_digest"]="f"*64
        self.blocked(d,"SCENARIO_PACK_VERSION_OR_DIGEST_MISMATCH")

    def test_wrong_origin_source_denied(self):
        d=report();d["source"]="REAL_INDEPENDENTLY_ATTESTED"
        self.blocked(d,"REPORT_SOURCE_INVALID")

    def test_owner_manual_origin_remains_unverified(self):
        d=report();d["source"]="OWNER_MANUAL_UNVERIFIED"
        r=check(d)
        self.assertEqual(r["state"],"CI_OR_MANUAL_MEASUREMENTS_UNVERIFIED_HUMAN_REVIEW_REQUIRED")
        self.assertFalse(r["real_owner_device_measured"])

    def test_unhashable_source_denied_without_exception(self):
        d=report();d["source"]=["CI_SYNTHETIC"]
        self.blocked(d,"REPORT_SOURCE_INVALID")

    def test_report_missing_samples_denied(self):
        d=report();del d["samples"]
        self.blocked(d,"REPORT_EXACT_FIELDS_REQUIRED")

    def test_missing_measurement_sample_denied(self):
        d=report();d["samples"].pop()
        self.blocked(d,"EXACTLY_88_SAMPLES_REQUIRED")

    def test_extra_duplicate_sample_denied(self):
        d=report();d["samples"].append(copy.deepcopy(d["samples"][-1]))
        self.blocked(d,"EXACTLY_88_SAMPLES_REQUIRED")

    def test_swapped_sample_duplicate_keys_denied(self):
        d=report()
        d["samples"][-1]=dict(d["samples"][-2])
        self.blocked(d,"DUPLICATE_SAMPLE_KEY")

    def test_unknown_task_denied(self):
        d=report();d["samples"][0]["task_kind"]="TRADE_EXECUTE"
        self.blocked(d,"SAMPLE_TASK_INVALID")

    def test_unknown_scenario_denied(self):
        d=report();d["samples"][0]["scenario_id"]="unknown"
        self.blocked(d,"SAMPLE_SCENARIO_INVALID")

    def test_replay_of_wrong_scenario_for_task_denied(self):
        d=report();d["samples"][0]["scenario_id"]="macro-live"
        self.blocked(d,"SAMPLE_SCENARIO_INVALID")

    def test_bad_phase_denied(self):
        d=report();d["samples"][0]["phase"]="FINISHED"
        self.blocked(d,"SAMPLE_PHASE_INVALID")

    def test_warmup_labeled_as_quality_pass_denied(self):
        d=report();d["samples"][0]["quality_review"]="PASS"
        self.blocked(d,"WARMUP_NOT_FOR_GRADING")

    def test_warmup_changed_to_measurement_denied(self):
        d=report();d["samples"][0]["phase"]="MEASURE"
        self.blocked(d,"INCOMPLETE_OR_REPLAYED_TASK_SAMPLES")

    def test_measurements_do_not_reuse_more_than_five_runs(self):
        d=report()
        next(x for x in d["samples"] if x["phase"]=="MEASURE")["sample_index"]=6
        self.blocked(d,"MEASUREMENT_SAMPLE_INDEX_INVALID")

    def test_boolean_latency_denied(self):
        d=report();d["samples"][0]["elapsed_ms"]=True
        self.blocked(d,"SAMPLE_METRIC_INVALID:elapsed_ms")

    def test_negative_memory_denied(self):
        d=report();d["samples"][1]["peak_ram_mib"]=-1
        self.blocked(d,"SAMPLE_METRIC_INVALID:peak_ram_mib")

    def test_no_output_tokens_denied(self):
        d=report();d["samples"][0]["output_tokens"]=0
        self.blocked(d,"SAMPLE_METRIC_INVALID:output_tokens")

    def test_invalid_vram_denied(self):
        d=report();d["samples"][0]["peak_dedicated_vram_mib"]=-2
        self.blocked(d,"VRAM_METRIC_INVALID")

    def test_unknown_grading_label_denied(self):
        d=report();d["samples"][1]["safety_review"]="INDEPENDENTLY_CERTIFIED"
        self.blocked(d,"REVIEW_LABEL_INVALID:safety_review")

    def test_unreviewed_is_not_counted_as_quality_pass(self):
        d=report()
        r=next(x for x in d["samples"] if x["phase"]=="MEASURE")
        r["quality_review"]="UNREVIEWED"
        out=check(d)
        self.assertEqual(out["state"],"CI_OR_MANUAL_MEASUREMENTS_UNVERIFIED_HUMAN_REVIEW_REQUIRED")
        self.assertIn("MANUAL_REVIEW_REQUIRED",
                      [s["self_reported_review_status"] for s in out["task_summaries"]])

    def test_safety_failure_blocks_selfreported_quality_candidate(self):
        d=report()
        r=next(x for x in d["samples"] if x["phase"]=="MEASURE")
        r["safety_review"]="FAIL"
        out=check(d)
        self.assertIn("SELF_REPORTED_METRICS_BELOW_TARGET",
                      [s["self_reported_review_status"] for s in out["task_summaries"]])
        self.assertFalse(out["independent_quality_certified"])

    def test_three_manual_quality_failures_exceed_fixture_target(self):
        d=report()
        candidates=[x for x in d["samples"] if x["task_kind"]=="GENERAL_TEXT" and x["phase"]=="MEASURE"]
        for row in candidates[:3]:row["quality_review"]="FAIL"
        r=check(d)
        gt=next(x for x in r["task_summaries"] if x["task_kind"]=="GENERAL_TEXT")
        self.assertEqual(gt["quality_passes"],17)
        self.assertEqual(gt["self_reported_review_status"],"SELF_REPORTED_METRICS_BELOW_TARGET")

    def test_p95_nearest_rank_uses_19th_of_20_samples(self):
        d=report()
        samples=[x for x in d["samples"] if x["task_kind"]=="GENERAL_TEXT" and x["phase"]=="MEASURE"]
        for x in samples:x["elapsed_ms"]=100
        samples[0]["elapsed_ms"]=6000
        result=check(d)
        gt=next(x for x in result["task_summaries"] if x["task_kind"]=="GENERAL_TEXT")
        self.assertEqual(gt["p95_latency_ms"],100) # worst 1/20 excluded
        samples[1]["elapsed_ms"]=6000
        result=check(d)
        gt=next(x for x in result["task_summaries"] if x["task_kind"]=="GENERAL_TEXT")
        self.assertEqual(gt["p95_latency_ms"],6000)
        self.assertEqual(gt["self_reported_review_status"],"SELF_REPORTED_METRICS_BELOW_TARGET")

    def test_voice_intent_uses_task_specific_p95_target(self):
        d=report()
        for row in d["samples"]:
            if row["task_kind"]=="VOICE_INTENT_TEXT_ONLY" and row["phase"]=="MEASURE":
                row["elapsed_ms"]=1300
        r=check(d)
        voice=next(x for x in r["task_summaries"] if x["task_kind"]=="VOICE_INTENT_TEXT_ONLY")
        self.assertEqual(voice["p95_latency_ms"],1300)
        self.assertEqual(voice["self_reported_review_status"],"SELF_REPORTED_METRICS_BELOW_TARGET")

    def test_benchmark_protocol_owns_no_runtime_or_model(self):
        p=benchmark_protocol_policy()
        self.assertTrue(p["scenario_pack_is_public_nonblind"])
        self.assertTrue(p["no_install_or_download_step"])
        for field in (
            "independent_model_quality_certified","real_owner_pc_benchmarked",
            "offline_inference_proven","actual_model_artifact_authenticated",
            "true_vram_or_power_usage_verified","production_router_enabled",
            "paid_fallback_enabled","worker_activated",
        ):
            self.assertIs(p[field],False,field)

    def test_cli_manifest_and_template_are_safe(self):
        from scripts.aion_offline_model_benchmark_review_v1 import main
        self.assertEqual(main(["--manifest"]),0)
        self.assertEqual(main(["--template"]),0)

    def test_cli_rejects_unapproved_oversize_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"big.json"
            path.write_bytes(b"x"*262145)
            proc=self._cli_review(path)
            self.assertEqual(proc.returncode,2)
            self.assertIn("OFFLINE_REPORT_NOT_READABLE_OR_VALID_JSON",proc.stdout)

    def test_cli_valid_fixture_returns_anonymized_aggregate(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"sample.json"
            path.write_text(json.dumps(report()),encoding="utf-8")
            proc=self._cli_review(path)
            self.assertEqual(proc.returncode,0,proc.stderr+proc.stdout)
            out=json.loads(proc.stdout)
            self.assertEqual(out["valid_sample_count"],88)
            self.assertFalse(out["paid_api_called"])
            self.assertNotIn("model_ref",out)

    def test_cli_invalid_fixture_exit_code_nonzero(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"sample.json"
            data=report();data["prompts_and_responses_excluded"]=False
            path.write_text(json.dumps(data),encoding="utf-8")
            proc=self._cli_review(path)
            self.assertEqual(proc.returncode,2)

    def test_cli_rejects_malformed_json_without_echoing_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"sample.json"
            path.write_text('{"sk-fake":',encoding="utf-8")
            proc=self._cli_review(path)
            self.assertEqual(proc.returncode,2)
            self.assertNotIn("sk-fake",proc.stdout)

    def _cli_review(self,path):
        return subprocess.run([
            sys.executable,"scripts/aion_offline_model_benchmark_review_v1.py",
            "--review",str(path),
            "--challenge-sha256",CHALLENGE,
            "--model-artifact-sha256",MODEL_SHA,
            "--hardware-report-digest",HARDWARE,
        ],capture_output=True,text=True,timeout=12)

if __name__=="__main__":
    unittest.main()
