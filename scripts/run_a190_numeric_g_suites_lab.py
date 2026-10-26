"""Execute a bounded numeric G3..Gn A190 LAB suite without importing newer G tests.

The historical workflow glob test_g[3-7]*.py grows to include G74–G79 and
silently crosses the G71/G73 test-intent boundary. Keep all original numeric
G files <= requested ceiling; do not skip individual tests or mock success.

This is not a P0 sign-off, independent witness or native SQLite VFS proof.
"""
import argparse
import hashlib
from pathlib import Path
import re
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", type=int, choices=(71, 73), required=True)
    parser.add_argument("--expected-tests", type=int, required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1] / "labs" / "a190"
    repo = root.parents[1]
    if not root.is_dir() or not (repo / "aion_chat" / "store.py").is_file():
        raise SystemExit("G86_LAB_SOURCE_LAYOUT_DENIED")
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(repo))

    candidates = sorted(root.glob("test_g[3-7]*.py"))
    matched = []
    out_of_scope = []
    for file in candidates:
        identity = re.fullmatch(r"test_g([0-9]+)(?:_.*)?\.py", file.name)
        if identity is None:
            raise SystemExit("G86_LAB_NONNUMERIC_MODULE_DENIED: " + file.name)
        number = int(identity.group(1))
        if not 3 <= number <= 79:
            raise SystemExit("G86_LAB_UNEXPECTED_NUMBER_DENIED: " + file.name)
        (matched if number <= args.through else out_of_scope).append(file)

    if not matched or not any(f.name.startswith(f"test_g{args.through}_") for f in matched):
        raise SystemExit("G86_LAB_CEILING_MISSING_DENIED")
    if any(int(re.match(r"test_g(\d+)", f.name).group(1)) > args.through for f in matched):
        raise SystemExit("G86_LAB_CEILING_OVERFLOW_DENIED")

    manifest = "\n".join(p.name for p in matched)
    digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    print(
        f"G86_SUITE_MANIFEST through={args.through} modules={len(matched)} "
        f"out_of_scope={len(out_of_scope)} sha256={digest}", flush=True
    )
    for p in matched:
        print("G86_INCLUDED_MODULE " + p.name, flush=True)
    for p in out_of_scope:
        print("G86_EXCLUDED_LATER_MODULE " + p.name, flush=True)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        loader.loadTestsFromName(p.stem) for p in matched
    )
    tests = suite.countTestCases()
    print(f"G86_EXPECTED_TESTS={args.expected_tests} ACTUAL={tests}", flush=True)
    if tests != args.expected_tests:
        raise SystemExit("G86_LAB_TEST_COUNT_DRIFT_DENIED")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
