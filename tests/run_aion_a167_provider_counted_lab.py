"""Counted A167 offline vendor semantics scenarios, no skipped proof."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
SOURCE = "test_aion_p0_a167_provider_semantics_lab.py"
EXPECTED = 24

def main():
    suite = unittest.TestLoader().discover(
        start_dir=str(ROOT / "tests"), pattern=SOURCE,
        top_level_dir=str(ROOT / "tests"))
    if suite.countTestCases() != EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A167 discovered {suite.countTestCases()}/{EXPECTED}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(f"FAIL-CLOSED A167 ran={result.testsRun}/{EXPECTED} "
                         f"fail={len(result.failures)} errors={len(result.errors)} "
                         f"skipped={len(result.skipped)}")
    print("PASS A167 24 negative supplier capability models; "
          "NO PROVIDER AUTHENTICATED; HARD NO-GO", flush=True)

if __name__ == "__main__":
    main()
