"""A145-A147 exact-count LAB gate. No external operations, no Worker."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TESTS = ROOT / "tests"
TEST_COUNTS = (
    ("test_aion_p0_a145_rollback_threat_model_lab.py", 4),
    ("test_aion_p0_a145_checkpoint_verifier_lab.py", 12),
    ("test_aion_p0_a145_authenticated_checkpoint_lab.py", 10),
    ("test_aion_p0_a146_highwater_gate_lab.py", 20),
    ("test_aion_p0_a146_signed_highwater_lab.py", 13),
    ("test_aion_p0_a147_sqlite_crash_reconcile_lab.py", 50),
)


def main():
    loader = unittest.TestLoader()
    suites = []
    for filename, expected in TEST_COUNTS:
        if len(list(TESTS.glob(filename))) != 1:
            raise SystemExit(f"FAIL-CLOSED: suite absent or duplicated: {filename}")
        suite = loader.discover(start_dir=str(TESTS), pattern=filename, top_level_dir=str(TESTS))
        count = suite.countTestCases()
        print(f"DISCOVERED {filename}: {count} (expected {expected})", flush=True)
        if count != expected:
            raise SystemExit(f"FAIL-CLOSED: count mismatch: {filename}")
        suites.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    total = sum(expected for _, expected in TEST_COUNTS)
    if result.testsRun != total or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED: expected {total} passing; ran={result.testsRun}, "
            f"failures={len(result.failures)}, errors={len(result.errors)}, "
            f"skips={len(result.skipped)}")
    print(f"PASS counted LAB A145-A147: {total} tests; HARD NO-GO remains", flush=True)


if __name__ == "__main__":
    main()
