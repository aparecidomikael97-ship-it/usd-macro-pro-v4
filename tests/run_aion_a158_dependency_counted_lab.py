"""Exactly 52 synthetic-source and real-version compatibility regressions.

The security gate MUST keep failing if Pillow CVEs remain. This runner
only validates pypdf-specific progress and parser adversaries.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SPECS = (
    ("test_aion_p0_a158_dependency_audit_lab.py",44),
    ("test_aion_p0_a158_pdf_image_dependency_smoke_lab.py",8),
)

def main():
    folder=ROOT/"tests"
    collected=[]
    for filename,expected in SPECS:
        if len(list(folder.glob(filename)))!=1:
            raise SystemExit("FAIL-CLOSED A158 missing/duplicate suite: "+filename)
        suite=unittest.TestLoader().discover(start_dir=str(folder),
            pattern=filename,top_level_dir=str(folder))
        actual=suite.countTestCases()
        print(f"DISCOVERED {filename}: {actual} expected {expected}",flush=True)
        if actual!=expected:
            raise SystemExit("FAIL-CLOSED A158 suite count drift: "+filename)
        collected.append(suite)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(collected))
    total=sum(x[1] for x in SPECS)
    if result.testsRun!=total or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A158 count={result.testsRun}/{total}; "
            f"errors={len(result.errors)}; failures={len(result.failures)}; "
            f"skips={len(result.skipped)}")
    print(f"PASS A158 {total} LAB checks; "
          "FULL SECURITY AUDIT IS NOT APPROVED",flush=True)

if __name__=="__main__":
    main()
