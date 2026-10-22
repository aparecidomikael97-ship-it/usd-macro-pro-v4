"""Strict A153 IAM-proposal mutations gate, offline, no authorization."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FILENAME = "test_aion_p0_a153_iam_document_boundary_lab.py"
EXPECTED = 48


def main():
    root = ROOT / "tests"
    if len(list(root.glob(FILENAME))) != 1:
        raise SystemExit("FAIL-CLOSED A153 missing/duplicate IAM mutation test module")
    suite = unittest.TestLoader().discover(
        start_dir=str(root), pattern=FILENAME, top_level_dir=str(root),
    )
    if suite.countTestCases() != EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A153 count mismatch: {suite.countTestCases()}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A153 ran={result.testsRun}, "
            f"failures={len(result.failures)}, errors={len(result.errors)}, "
            f"skips={len(result.skipped)}"
        )
    print(f"PASS A153 {EXPECTED} IAM proposal static tests; ALWAYS HARD NO-GO",flush=True)


if __name__ == "__main__":
    main()
