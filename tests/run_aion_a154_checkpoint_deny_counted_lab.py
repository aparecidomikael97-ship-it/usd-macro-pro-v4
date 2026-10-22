"""Exact-count H0 runtime Checkpoint Mestre writer NO-GO regression.

Tests with actual runtime function MOCK all GitHub HTTP; AST scans only
read source and never execute it. A green return is NOT an enrollment,
provider receipt, checkpoint write or real H0 authorization.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUITES = (
    ("test_aion_p0_checkpoint_write_surface_ast_lab.py", 17),
    ("test_aion_p0_runtime_direct_write_independent_witness_lab.py", 11),
    ("test_aion_p0_a154_runtime_writer_deny_ast_lab.py", 45),
)


def main():
    loader = unittest.TestLoader()
    suites = []
    for filename, count in SUITES:
        folder = ROOT / "tests"
        if len(list(folder.glob(filename))) != 1:
            raise SystemExit("FAIL-CLOSED A154: test suite absent: " + filename)
        suite = loader.discover(
            start_dir=str(folder), pattern=filename,
            top_level_dir=str(folder),
        )
        found = suite.countTestCases()
        print(f"DISCOVERED {filename}: {found}, required={count}", flush=True)
        if found != count:
            raise SystemExit("FAIL-CLOSED A154: test count changed: "+filename)
        suites.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(suites)
    )
    wanted = sum(count for _, count in SUITES)
    if result.testsRun != wanted or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A154 expected={wanted}, ran={result.testsRun}, "
            f"errors={len(result.errors)}, failures={len(result.failures)}, "
            f"skips={len(result.skipped)}"
        )
    print(f"PASS A154 combined A135/A136/A154 = {wanted}; "
          "HARD NO-GO / ZERO_AUTO_RESEND", flush=True)


if __name__ == "__main__":
    main()
