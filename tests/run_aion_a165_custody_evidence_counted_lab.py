"""A165 exact-count, no-skip, entirely synthetic custody evidence suite."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE="test_aion_p0_a165_external_custody_evidence_lab.py"
EXPECTED=80


def main():
    tests=ROOT/"tests"
    if len(list(tests.glob(SOURCE)))!=1:
        raise SystemExit("FAIL-CLOSED A165 missing or duplicate test source")
    suite=unittest.TestLoader().discover(
        start_dir=str(tests),pattern=SOURCE,top_level_dir=str(tests))
    if suite.countTestCases()!=EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A165 discovered {suite.countTestCases()}/{EXPECTED}")
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun!=EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A165 ran={result.testsRun}/{EXPECTED} "
            f"fails={len(result.failures)} errors={len(result.errors)} "
            f"skipped={len(result.skipped)}")
    print("PASS A165 80 synthetic signed custody evidence tests; "
          "NO REAL INDEPENDENT CUSTODY; HARD NO-GO; ZERO_AUTO_RESEND",flush=True)


if __name__=="__main__":
    main()
