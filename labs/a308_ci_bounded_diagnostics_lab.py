"""A308 CI diagnosis: bounded, isolated unittest subprocesses on each OS.

This is infrastructure for *testing only*, not AION Worker/Executor.
A hung suite is a test failure with a named timeout, never a P0 GO.
No actions in the lab can resume, retry, send, deploy or release real effects.
"""
import argparse
import subprocess
import sys
from dataclasses import dataclass

SUITES = (
    "labs.test_a308_evidence_provenance_contract_lab",
    "labs.test_a307_manual_case_adversarial_lab",
    "labs.test_a306_manual_intent_reconciliation_lab",
    "labs.test_a305_restart_revocation_no_resend_lab",
    "labs.test_a304_custodian_status_lab",
    "labs.test_a303_custody_anchor_chain_lab",
    "labs.test_a302_witness_receipt_contract_lab",
    "labs.test_a301_recovery_evidence_contract_lab",
    "labs.test_a300_cold_restart_sqlite_recovery_lab",
    "labs.test_a299_sqlite_native_p0_5_6_gap_lab",
    "labs.test_a293_host_sqlite_boundary_lab",
    "labs.test_a292_staged_chat_write_inventory_lab",
)


@dataclass(frozen=True)
class SuiteResult:
    suite: str
    state: str
    returncode: int | None


def run_bounded_suite(suite, *, timeout_seconds=90, runner=None):
    """Never swallow a failure: spawn a fresh process for one known suite."""
    if suite not in SUITES:
        return SuiteResult(str(suite), "UNRECOGNIZED_SUITE", None)
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
        return SuiteResult(suite, "INVALID_TIMEOUT", None)
    if runner is None:
        runner = subprocess.run
    argv = [sys.executable, "-m", "unittest", "-v", suite]
    print("A308-D1 START " + suite, flush=True)
    try:
        completed = runner(argv, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        print("A308-D1 TIMEOUT " + suite, flush=True)
        return SuiteResult(suite, "TIMEOUT", None)
    except (OSError, ValueError):
        print("A308-D1 RUNNER_ERROR " + suite, flush=True)
        return SuiteResult(suite, "RUNNER_ERROR", None)
    returncode = completed.returncode
    if type(returncode) is not int or returncode != 0:
        print("A308-D1 FAIL " + suite, flush=True)
        return SuiteResult(suite, "FAILED", returncode)
    print("A308-D1 PASS " + suite, flush=True)
    return SuiteResult(suite, "PASSED", returncode)


def run_all(*, timeout_seconds=90, suites=SUITES, runner=None):
    """Continue through all suites so failed/blocked scope is explicit."""
    results = []
    if (type(suites) not in (tuple, list) or not suites or
            len(suites) != len(set(suites)) or
            any(s not in SUITES for s in suites)):
        raise ValueError("Expected distinct suites from fixed LAB allowlist")
    for suite in suites:
        results.append(run_bounded_suite(
            suite, timeout_seconds=timeout_seconds, runner=runner,
        ))
    passed = sum(item.state == "PASSED" for item in results)
    print("A308-D1 SUMMARY: "
          f"{passed}/{len(results)} suites PASSED; "
          f"{len(results) - passed} failed/timeout/error", flush=True)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline per-suite timeout diagnosis for A308 CI"
    )
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)
    results = run_all(timeout_seconds=args.timeout)
    return 0 if all(item.state == "PASSED" for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
