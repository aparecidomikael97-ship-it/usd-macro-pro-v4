"""A160 30 exact LAB inherited witness bypass tests, no skip."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE="test_aion_p0_a160_inherited_mutator_bypass_lab.py"
EXPECTED=30

def main():
    path=ROOT/"tests"
    if len(list(path.glob(SOURCE)))!=1:
        raise SystemExit("FAIL-CLOSED A160 source missing or duplicate")
    suite=unittest.TestLoader().discover(start_dir=str(path),pattern=SOURCE,
                                         top_level_dir=str(path))
    actual=suite.countTestCases()
    if actual!=EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A160 discovered {actual}, expected {EXPECTED}")
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun!=EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A160 ran={result.testsRun}/{EXPECTED} "
            f"fail={len(result.failures)} err={len(result.errors)} "
            f"skip={len(result.skipped)}"
        )
    print(f"PASS A160 {EXPECTED} inherited legacy CAS-bypass defenses; "
          "HARD NO-GO; 0/6 P0",flush=True)

if __name__=="__main__":
    main()
