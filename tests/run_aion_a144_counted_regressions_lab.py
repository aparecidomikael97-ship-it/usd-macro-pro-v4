"""A140-A144 counted, offline-only unittest gate; no external operations."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TESTS = ROOT / "tests"
PATTERNS = (
    "test_aion_p0_sqlite_durable_market_quota_a140_lab.py",
    "test_aion_p0_market_sqlite_identity_a141_lab.py",
    "test_aion_p0_market_sqlite_mode_rw_a142_lab.py",
    "test_aion_p0_market_sqlite_explicit_bootstrap_a143_lab.py",
    "test_aion_p0_market_sqlite_schema_attestation_a144_lab.py",
)
EXPECTED_COUNTS = (45, 22, 11, 20, 18)

def main():
    loader = unittest.TestLoader()
    suites = []
    for pattern, expected_count in zip(PATTERNS, EXPECTED_COUNTS, strict=True):
        matches = list(TESTS.glob(pattern))
        if len(matches) != 1:
            raise SystemExit(f"FAIL-CLOSED: expected one file for {pattern}, found {len(matches)}")
        suite = loader.discover(start_dir=str(TESTS), pattern=pattern, top_level_dir=str(TESTS))
        count = suite.countTestCases()
        print(f"DISCOVERED {pattern}: {count}", flush=True)
        if count != expected_count:
            raise SystemExit(f"FAIL-CLOSED: {pattern}: expected {expected_count}, discovered {count}")
        suites.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    if result.testsRun != sum(EXPECTED_COUNTS):
        raise SystemExit(f"FAIL-CLOSED: expected {sum(EXPECTED_COUNTS)} executed tests, got {result.testsRun}")
    if result.skipped:
        raise SystemExit(f"FAIL-CLOSED: {len(result.skipped)} skipped tests require review")
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(f"PASS counted suite: {result.testsRun} tests (A140-A144)", flush=True)

if __name__ == "__main__":
    main()
