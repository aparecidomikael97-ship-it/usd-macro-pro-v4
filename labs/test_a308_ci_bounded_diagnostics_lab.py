"""A308-D1 CI watchdog: unit tests for bounded offline regression execution."""
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import subprocess
import sys
import unittest

from labs.a308_ci_bounded_diagnostics_lab import (
    SUITES, run_all, run_bounded_suite,
)


class A308BoundedDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.suite = SUITES[0]

    def test_full_regression_suite_list_is_stable_and_unique(self):
        self.assertEqual(len(SUITES), 12)
        self.assertEqual(len(set(SUITES)), len(SUITES))
        self.assertTrue(all(s.startswith("labs.test_a") for s in SUITES))

    def test_real_runner_is_not_needed_to_check_success(self):
        observed = []
        def runner(argv, *, timeout, check):
            observed.append((argv, timeout, check))
            return SimpleNamespace(returncode=0)
        with redirect_stdout(StringIO()):
            result = run_bounded_suite(
                self.suite, timeout_seconds=30, runner=runner,
            )
        self.assertEqual(result.state, "PASSED")
        self.assertEqual(observed[0][0],
                         [sys.executable, "-m", "unittest", "-v", self.suite])
        self.assertEqual(observed[0][1:], (30, False))

    def test_nonzero_exit_is_not_marked_as_pass(self):
        with redirect_stdout(StringIO()):
            result = run_bounded_suite(
                self.suite, runner=lambda *args, **kw:
                    SimpleNamespace(returncode=7),
            )
        self.assertEqual(result.state, "FAILED")
        self.assertEqual(result.returncode, 7)

    def test_timeout_is_explicit_failure(self):
        def stalled(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="python unittest", timeout=20)
        with redirect_stdout(StringIO()):
            result = run_bounded_suite(self.suite, runner=stalled)
        self.assertEqual(result.state, "TIMEOUT")
        self.assertIsNone(result.returncode)

    def test_os_error_is_reported_not_approved(self):
        def crashed(*args, **kwargs):
            raise OSError("synthetic runner missing")
        with redirect_stdout(StringIO()):
            result = run_bounded_suite(self.suite, runner=crashed)
        self.assertEqual(result.state, "RUNNER_ERROR")

    def test_unknown_suite_cannot_execute(self):
        result = run_bounded_suite(
            "labs.test_unknown", runner=lambda *a, **k:
                self.fail("unknown suite executed")
        )
        self.assertEqual(result.state, "UNRECOGNIZED_SUITE")

    def test_invalid_timeout_is_rejected(self):
        for bad in (0, True, -1, 601, "90"):
            self.assertEqual(
                run_bounded_suite(self.suite, timeout_seconds=bad).state,
                "INVALID_TIMEOUT",
            )

    def test_runner_continues_to_identify_exact_failed_suite(self):
        def runner(argv, *, timeout, check):
            return SimpleNamespace(
                returncode=1 if argv[-1] == SUITES[1] else 0
            )
        with redirect_stdout(StringIO()):
            results = run_all(
                suites=(SUITES[0], SUITES[1], SUITES[2]),
                runner=runner,
            )
        self.assertEqual(
            [r.state for r in results], ["PASSED", "FAILED", "PASSED"],
        )
        self.assertEqual(results[1].suite, SUITES[1])

    def test_duplicate_suite_is_never_dispatched(self):
        with self.assertRaises(ValueError):
            run_all(suites=(self.suite, self.suite),
                    runner=lambda *a, **k: self.fail("dispatched"))

    def test_unknown_suite_list_is_never_dispatched(self):
        with self.assertRaises(ValueError):
            run_all(suites=(self.suite, "labs.test_untrusted"),
                    runner=lambda *a, **k: self.fail("dispatched"))


if __name__ == "__main__":
    unittest.main()
