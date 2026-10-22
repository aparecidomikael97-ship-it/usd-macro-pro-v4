"""A156 strict-count real restore witness NO-GO gate (network mocked).

Counts source-mutational checks, real restore execution under mocks, branch
head TOCTOU scenarios and disabled historical bootstrap/migration workflows.
A passing run never proves effective IAM or authorizes any restore.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SUITES = (
    ("test_aion_p0_a156_recovery_restore_deny_ast_lab.py", 52, ROOT / "tests"),
    ("test_aion_p0_recovery_independent_head_witness_admission_lab.py", 11, ROOT / "tests"),
    ("test_aion_p0_recovery_branch_head_toctou_lab.py", 13, ROOT / "tests"),
    ("test_atlasquant_checkpoint_writers_hard_stop_a69.py", 6, ROOT),
)


def main():
    loader = unittest.TestLoader()
    items = []
    for name, expected, folder in SUITES:
        if len(list(folder.glob(name))) != 1:
            raise SystemExit(f"FAIL-CLOSED A156 missing or duplicate: {name}")
        suite = loader.discover(
            start_dir=str(folder), pattern=name, top_level_dir=str(folder)
        )
        actual = suite.countTestCases()
        print(f"DISCOVERED {name}: {actual}; expected {expected}", flush=True)
        if actual != expected:
            raise SystemExit("FAIL-CLOSED A156 unexpected suite count: " + name)
        items.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(items)
    )
    total = sum(n for _, n, _ in SUITES)
    if result.testsRun != total or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A156 wanted={total}; ran={result.testsRun}; "
            f"failures={len(result.failures)}; errors={len(result.errors)}; "
            f"skipped={len(result.skipped)}"
        )
    print(f"PASS A156 {total} restore NO-GO checks; "
          "NO LIVE WRITE OR AUTOMATIC RESTORE", flush=True)


if __name__ == "__main__":
    main()
