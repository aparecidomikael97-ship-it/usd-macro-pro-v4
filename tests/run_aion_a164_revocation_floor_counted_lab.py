"""Exact, no-skip A164 80 case cryptographic policy floor proof (LAB-only)."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TEST="test_aion_p0_a164_independent_revocation_floor_lab.py"
EXPECTED=80


def main():
    folder=ROOT/"tests"
    if len(list(folder.glob(TEST)))!=1:
        raise SystemExit("A164 FAIL-CLOSED: missing or duplicate test module")
    tests=unittest.TestLoader().discover(
        start_dir=str(folder),pattern=TEST,top_level_dir=str(folder))
    actual=tests.countTestCases()
    print(f"A164 collected {actual}, expected {EXPECTED}",flush=True)
    if actual!=EXPECTED:
        raise SystemExit("A164 FAIL-CLOSED: suite case count drift")
    result=unittest.TextTestRunner(verbosity=2).run(tests)
    if result.testsRun!=EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"A164 FAIL-CLOSED: cases {result.testsRun}/{EXPECTED}, "
            f"fail {len(result.failures)}, error {len(result.errors)}, "
            f"skip {len(result.skipped)}"
        )
    print("PASS A164 80 tests, no real revocation propagation authority, "
          "HARD NO-GO 0/6",flush=True)


if __name__=="__main__":
    main()
