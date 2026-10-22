"""A161 exact 70 test, no-skip LAB-only dual custodian floor runner."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FILE = "test_aion_p0_a161_dual_custodian_floor_lab.py"
EXPECTED = 70


def main() -> None:
    tests = ROOT / "tests"
    if len(list(tests.glob(FILE))) != 1:
        raise SystemExit("A161 FAIL-CLOSED: source absent or duplicated")
    suite = unittest.TestLoader().discover(
        start_dir=str(tests), pattern=FILE, top_level_dir=str(tests),
    )
    count = suite.countTestCases()
    print(f"A161 DISCOVERED: {count}, expected {EXPECTED}", flush=True)
    if count != EXPECTED:
        raise SystemExit("A161 FAIL-CLOSED: unexpected discovered case count")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if (not result.wasSuccessful() or result.skipped
            or result.testsRun != EXPECTED):
        raise SystemExit(
            f"A161 FAIL-CLOSED: ran={result.testsRun}/{EXPECTED} "
            f"fails={len(result.failures)} errors={len(result.errors)} "
            f"skips={len(result.skipped)}"
        )
    print(
        "PASS A161 70 signed-floor tests; "
        "NO EXTERNAL CUSTODY PROVEN; HARD NO-GO 0/6",
        flush=True,
    )


if __name__ == "__main__":
    main()
