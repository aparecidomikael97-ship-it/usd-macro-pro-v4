"""A162 70 exact, no-skip, isolated cross-source recovery tests."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE="test_aion_p0_a162_three_source_recovery_lab.py"
COUNT=70


def main():
    root=ROOT/"tests"
    if len(list(root.glob(SOURCE))) != 1:
        raise SystemExit("FAIL-CLOSED A162: missing/duplicate test source")
    suite=unittest.TestLoader().discover(
        start_dir=str(root),pattern=SOURCE,top_level_dir=str(root),
    )
    found=suite.countTestCases()
    print(f"DISCOVERED A162: {found}/{COUNT}",flush=True)
    if found!=COUNT:
        raise SystemExit("FAIL-CLOSED A162: unexpected case count")
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun!=COUNT or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A162: ran={result.testsRun}/{COUNT} "
            f"failures={len(result.failures)} errors={len(result.errors)} "
            f"skipped={len(result.skipped)}"
        )
    print("PASS A162 70 exact three-source LAB H0 cases; "
          "NO AUTHORIZED RECOVERY / HARD NO-GO",flush=True)


if __name__=="__main__":
    main()
