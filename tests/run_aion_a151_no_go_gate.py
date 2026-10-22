"""A151 exact-count static LAB/runtime boundary tests plus repository scan.

Exit zero only confirms static import fence checks; ALWAYS HARD NO-GO.
No importing actual runtime modules, no provider, network, cloud, Worker,
payments, credentials or execution of external effects.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.aion_p0_a151_lab_runtime_import_sentinel import audit_repository

TEST_FILE = "test_aion_p0_a151_lab_runtime_import_sentinel.py"
EXPECTED = 28


def main():
    suite = unittest.TestLoader().discover(
        start_dir=str(ROOT / "tests"), pattern=TEST_FILE,
        top_level_dir=str(ROOT / "tests"),
    )
    if suite.countTestCases() != EXPECTED:
        raise SystemExit(f"FAIL-CLOSED A151: expected {EXPECTED} tests, found {suite.countTestCases()}")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A151: ran={result.testsRun}, "
            f"errors={len(result.errors)}, fails={len(result.failures)}, "
            f"skipped={len(result.skipped)}"
        )
    report = audit_repository(ROOT)
    import json
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["static_import_boundary_clean"]:
        raise SystemExit("FAIL-CLOSED A151: experiment imported by non-test runtime module")
    if report["inspected_non_lab_python_files"] < 1:
        raise SystemExit("FAIL-CLOSED A151: no repository source was scanned")
    if report["H0_effect_authorization"] or report["automatic_resend_allowed"]:
        raise SystemExit("FAIL-CLOSED A151: authority was minted")
    print("PASS A151 28 mutation tests and repo-wide static scan; HARD NO-GO ONLY")


if __name__ == "__main__":
    main()
