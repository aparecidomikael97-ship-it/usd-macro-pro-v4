"""Run exactly 40 A166 test-only dossier checks, no skip or production authority."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
SOURCE = "test_aion_p0_a166_custodian_acceptance_contract.py"
EXPECTED = 40

def main():
    directory = ROOT / "tests"
    if len(list(directory.glob(SOURCE))) != 1:
        raise SystemExit("FAIL-CLOSED A166 test source missing or duplicated")
    suite = unittest.TestLoader().discover(
        start_dir=str(directory), pattern=SOURCE, top_level_dir=str(directory))
    if suite.countTestCases() != EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A166 discovered {suite.countTestCases()}/{EXPECTED}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(f"FAIL-CLOSED A166 ran={result.testsRun}/{EXPECTED} "
                         f"fail={len(result.failures)} errors={len(result.errors)} "
                         f"skipped={len(result.skipped)}")
    print("PASS A166 40 offline metadata rejection tests; NO CUSTODIANS "
          "ENROLLED; HARD NO-GO; ZERO_AUTO_RESEND", flush=True)

if __name__ == "__main__":
    main()
