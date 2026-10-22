"""A155 exact-count generic GitHub writer destination containment.

AST-isolated functions use 100% mocked HTTP; no actual token, provider,
deployment or product side effects. A passing result is HARD NO-GO, not
evidence of end-to-end runtime isolation or IAM restrictions.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUITES = (
    ("test_aion_p0_a155_autopilot_writer_allowlist_lab.py", 52),
    ("test_aion_p0_generic_github_writer_paths_lab.py", 13),
    ("test_aion_p0_other_generic_writers_path_lab.py", 13),
)


def main():
    folder = ROOT / "tests"
    units = []
    for name, expected in SUITES:
        if len(list(folder.glob(name))) != 1:
            raise SystemExit("FAIL-CLOSED A155: missing or duplicate "+name)
        case = unittest.TestLoader().discover(
            start_dir=str(folder), pattern=name, top_level_dir=str(folder),
        )
        found = case.countTestCases()
        print(f"DISCOVERED {name}: {found} expected {expected}", flush=True)
        if found != expected:
            raise SystemExit("FAIL-CLOSED A155 suite count changed: "+name)
        units.append(case)
    out = unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(units)
    )
    wanted = sum(x[1] for x in SUITES)
    if out.testsRun != wanted or out.skipped or not out.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A155: wanted={wanted}, ran={out.testsRun}, "
            f"failures={len(out.failures)}, errors={len(out.errors)}, "
            f"skips={len(out.skipped)}"
        )
    print(f"PASS A155 {wanted} generic destination cases; "
          "HARD NO-GO / NO REAL WRITE", flush=True)


if __name__ == "__main__":
    main()
