"""AION offline, manual local-model benchmark evidence reviewer.

- --manifest: print public, non-sensitive benchmark prompts to stdout.
- --template: print a BLANK, deliberately INVALID-to-assess sample template.
- --review: read only a manually named JSON file (max 256 KiB) and print
  sanitized aggregate review; never print raw answers, tokens or prompts.
No internet, model execution, file writes, telemetry or paid provider use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Permit the documented direct invocation from within the checked-out
# repository without pip install, PYTHONPATH or admin changes.
repo_root = str(Path(__file__).resolve().parents[1])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from atlasquant_aion_offline_local_model_benchmark_evidence_v1 import (
    SCHEMA, TASKS, SCENARIOS, scenario_pack, scenario_pack_digest,
    review_offline_model_benchmark,
)

MAX_IMPORT_BYTES = 262144


def blank_report_template() -> dict:
    """Print-only, intentionally incomplete until an owner fills it locally."""
    samples=[]
    for task in TASKS:
        first=sorted(SCENARIOS[task])[0]
        for index in (1,2):
            samples.append(_blank_sample(task,first,"WARMUP",index))
        for scenario in sorted(SCENARIOS[task]):
            for index in range(1,6):
                samples.append(_blank_sample(task,scenario,"MEASURE",index))
    return {
        "schema":SCHEMA,"source":"OWNER_MANUAL_UNVERIFIED",
        "model_ref":"owner-local-model-placeholder",
        "model_artifact_sha256":"0"*64,
        "scenario_pack_digest":scenario_pack_digest(),
        "challenge_sha256":"0"*64,
        "hardware_report_digest":"0"*64,
        "session_id":"offline-placeholder-0001",
        "samples":samples,
        "manual_review_basis":"HUMAN_SELF_REPORTED_UNVERIFIED",
        "prompts_and_responses_excluded":True,
        "no_network_claimed":True,"no_paid_api_claimed":True,
        "artifact_authenticated_externally":False,
        "hardware_authenticated_externally":False,
        "human_quality_certified":False,"paid_fallback_authorized":False,
        "deploy_authorized":False,
    }


def _blank_sample(task: str, scenario: str, phase: str, index: int) -> dict:
    return {
        "task_kind":task, "scenario_id":scenario,
        "phase":phase, "sample_index":index,
        "elapsed_ms":None, "input_tokens":None, "output_tokens":None,
        "peak_ram_mib":None, "peak_dedicated_vram_mib":None,
        "quality_review":"UNREVIEWED","safety_review":"UNREVIEWED",
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Offline AION benchmark format review — never runs AI models")
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--manifest",action="store_true")
    modes.add_argument("--template",action="store_true")
    modes.add_argument("--review",metavar="REPORT_JSON_PATH")
    parser.add_argument("--challenge-sha256")
    parser.add_argument("--model-artifact-sha256")
    parser.add_argument("--hardware-report-digest")
    args=parser.parse_args(argv)
    if args.manifest:
        print(json.dumps(scenario_pack(),ensure_ascii=False,sort_keys=True,indent=2))
        return 0
    if args.template:
        print(json.dumps(blank_report_template(),ensure_ascii=False,sort_keys=True,indent=2))
        return 0
    pins=(args.challenge_sha256,args.model_artifact_sha256,args.hardware_report_digest)
    if any(p is None for p in pins):
        parser.error("--review requires --challenge-sha256, --model-artifact-sha256 and --hardware-report-digest")
    try:
        path=Path(args.review)
        if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_IMPORT_BYTES:
            raise ValueError("BENCHMARK_REPORT_PATH_OR_SIZE_INVALID")
        raw=path.read_bytes()
        if len(raw)>MAX_IMPORT_BYTES:
            raise ValueError("BENCHMARK_REPORT_SIZE_INVALID")
        parsed=json.loads(raw.decode("utf-8"))
        result=review_offline_model_benchmark(
            parsed,expected_challenge_sha256=pins[0],
            expected_model_artifact_sha256=pins[1],
            expected_hardware_report_digest=pins[2],
        )
        print(json.dumps(result,ensure_ascii=True,sort_keys=True))
        return 0 if result["state"]!="BLOCKED" else 2
    except (ValueError,UnicodeError,OSError) as exc:
        # Sanitized error strings; never reveal path or imported file content.
        print(json.dumps({
            "schema":"ATLASQUANT_AION_OFFLINE_BENCHMARK_REVIEW_V1",
            "state":"BLOCKED","blockers":["OFFLINE_REPORT_NOT_READABLE_OR_VALID_JSON"],
            "owner_device_accessed":False,
            "paid_api_called":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    sys.exit(main())
