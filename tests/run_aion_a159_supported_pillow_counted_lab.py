"""A159: no-skip 96-test regression of security dependency migrations.

The A158 baseline remains tested to guard against false permission
escalation; A159 validates exact supported new versions and Streamlit UI.
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SUITES=(
    ("test_aion_p0_a158_dependency_audit_lab.py",36),
    ("test_aion_p0_a158_pdf_image_dependency_smoke_lab.py",8),
    ("test_aion_p0_a159_streamlit_pillow_security_lab.py",40),
    ("test_aion_p0_a159_pillow13_streamlit_runtime_lab.py",12),
)


def main():
    root=ROOT/"tests"
    units=[]
    for filename,required in SUITES:
        if len(list(root.glob(filename)))!=1:
            raise SystemExit("FAIL-CLOSED A159 missing/duplicate "+filename)
        suite=unittest.TestLoader().discover(
            start_dir=str(root),pattern=filename,top_level_dir=str(root))
        actual=suite.countTestCases()
        if actual!=required:
            raise SystemExit(f"FAIL-CLOSED A159 count {filename}: {actual}!={required}")
        print(f"DISCOVERED {filename} = {actual}",flush=True)
        units.append(suite)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(units))
    expected=sum(count for _,count in SUITES)
    if result.testsRun!=expected or result.skipped or not result.wasSuccessful():
        raise SystemExit(
            f"FAIL-CLOSED A159 wanted={expected} ran={result.testsRun} "
            f"errors={len(result.errors)} failures={len(result.failures)} "
            f"skipped={len(result.skipped)}")
    print(f"PASS A159 {expected} exact source, PDF image and Streamlit smoke LAB; "
          "ZERO P0 HOMOLOGATED",flush=True)


if __name__=="__main__":
    main()
