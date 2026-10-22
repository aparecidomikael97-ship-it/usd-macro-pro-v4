"""A163: require exactly 80 LAB enrollment/rotation/revocation tests, zero skips."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE="test_aion_p0_a163_custody_enrollment_revocation_lab.py"
EXPECTED=80


def main():
    directory=ROOT/"tests"
    if len(list(directory.glob(SOURCE)))!=1:
        raise SystemExit("FAIL-CLOSED A163 missing/duplicate test source")
    suite=unittest.TestLoader().discover(
        start_dir=str(directory),pattern=SOURCE,top_level_dir=str(directory))
    observed=suite.countTestCases()
    if observed!=EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A163 discovered {observed}, expected {EXPECTED}")
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun!=EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A163 ran={result.testsRun}/{EXPECTED}, "
            f"failures={len(result.failures)}, errors={len(result.errors)}, "
            f"skips={len(result.skipped)}"
        )
    print(
        "PASS A163 80 exact TEST-ONLY custody-policy cases; "
        "NO REAL EXTERNAL TRUST/ENROLLMENT; HARD NO-GO",
        flush=True,
    )


if __name__=="__main__":
    main()
