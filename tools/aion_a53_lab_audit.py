"""Run A53 and existing workflow unittest selections with live network denied."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import shlex
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def workflow_selection(path: str, step_name: str) -> list[str]:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    marker = "      - name: " + step_name
    index = lines.index(marker) + 1
    if lines[index].strip() != "run: |":
        raise ValueError("Expected an explicit run block")
    command = []
    for line in lines[index + 1:]:
        if line and not line.startswith("          "):
            break
        command.append(line[10:])
    args = shlex.split("\n".join(command).replace("\\\n", " "))
    if args[:4] != ["python", "-m", "unittest", "-q"]:
        raise ValueError("Only the unchanged unittest selection is supported")
    # Match unittest CLI conversion of explicit file paths to module names.
    return [item[:-3].replace("/", ".") if item.endswith(".py") else item for item in args[4:]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", choices=("focused", "activation", "security", "quality"))
    parser.add_argument("--json-output")
    args = parser.parse_args()
    if args.suite == "focused":
        names = [
            "test_atlasquant_aion_global_worker_activation.A53IndependentActivationBoundaryTests",
            "test_atlasquant_aion_saga_plan_integrity_a50",
            "test_atlasquant_aion_background_executor.AionBackgroundExecutorTests.test_a51_global_worker_direct_kernel_cannot_invoke_handler_without_witness",
            "test_atlasquant_aion_background_executor.AionBackgroundExecutorTests.test_a51_direct_armed_worker_with_forged_digest_must_not_issue_receipt",
            "test_atlasquant_aion_background_executor.AionBackgroundExecutorTests.test_a51_explicit_human_click_remains_usable",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a48_direct_writer_denies_valid_local_checkpoint_before_put",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a48_forged_local_witness_marker_cannot_activate_direct_writer",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a48_direct_writer_does_not_read_hostile_config_properties",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a47_feature_true_cannot_claim_cas_or_execute_without_source_witness",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a47_enabled_environment_cannot_claim_cas_without_source_witness",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a47_no_untrusted_runtime_config_property_read_without_source",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a46_corrupted_checkpoint_get_success_does_not_execute_or_write",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a46_corrupted_global_worker_digest_does_not_reach_claim",
            "test_atlasquant_aion_global_worker.AionGlobalDurableWorkerTests.test_a46_confirmed_read_without_checkpoint_is_untrusted",
        ]
    elif args.suite == "activation":
        names = ["test_atlasquant_aion_global_worker_activation"]
    elif args.suite == "security":
        names = workflow_selection(
            ".github/workflows/aion-core-security-gate.yml",
            "Run authority, injection, isolation and recovery tests",
        )
    else:
        names = workflow_selection(".github/workflows/quality-tests.yml", "Run quality suite")

    def no_network(*_args, **_kwargs):
        raise AssertionError("A53_LIVE_NETWORK_FORBIDDEN")

    # A Mock in a historical test may intercept a call before these sentinels.
    # No sentinel returns a fake successful response or independent receipt.
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket, "create_connection", side_effect=no_network))
        stack.enter_context(patch.object(socket.socket, "connect", side_effect=no_network))
        import requests
        stack.enter_context(patch.object(requests.sessions.Session, "request", side_effect=no_network))
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        result = unittest.TextTestRunner(verbosity=2 if args.suite == "focused" else 1).run(suite)
    summary = {
        "suite": args.suite,
        "python": sys.version,
        "total": result.testsRun,
        "pass": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped) - len(result.expectedFailures) - len(result.unexpectedSuccesses),
        "fail": len(result.failures),
        "error": len(result.errors),
        "skip": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "failures": [{"test": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"test": test.id(), "traceback": trace} for test, trace in result.errors],
        "skips": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "live_network_allowed": False,
    }
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("A53_COUNTS=" + json.dumps({k: v for k, v in summary.items() if k not in {"failures", "errors", "skips"}}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
