"""A152 exact-count evidence decision mutations and legacy FinOps preflight.

A clean result certifies only documentary invariants, NOT an external trust
root, a real budget quote, a provider effect or authorization for any Worker.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
COUNTS = (
    ("test_aion_p0_a152_external_evidence_decision_gate_lab.py", 30, ROOT/"tests"),
    ("test_aion_p0_h0_iam_finops_preflight_lab.py", 25, ROOT),
)


def main():
    loader = unittest.TestLoader()
    suites = []
    for name, expected, location in COUNTS:
        matches = sorted(location.glob(name))
        if len(matches) != 1:
            raise SystemExit("FAIL-CLOSED A152: missing or duplicate suite " + name)
        suite = loader.discover(
            start_dir=str(location), pattern=name, top_level_dir=str(location),
        )
        found = suite.countTestCases()
        print(f"DISCOVERED {name}: {found}, expected {expected}", flush=True)
        if found != expected:
            raise SystemExit(f"FAIL-CLOSED A152: incorrect count for {name}")
        suites.append(suite)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    required = sum(c for _,c,_ in COUNTS)
    if result.testsRun != required or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A152: expected={required}, ran={result.testsRun}, "
            f"errors={len(result.errors)}, failures={len(result.failures)}, "
            f"skips={len(result.skipped)}"
        )
    print(f"PASS A152 documentary/FinOps counted LAB: {required}; HARD NO-GO",flush=True)


if __name__ == "__main__":
    main()
