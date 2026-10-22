"""Strict-count workflow hardstop and source-backup regression test runner.

No workflow YAML is executed; tests only inspect strings and local sources.
A green result never authenticates GitHub token scopes or live IAM.
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SUITES=(
    ("test_aion_p0_a157_workflow_yaml_policy_lab.py",50,ROOT/"tests"),
    ("test_aion_p0_workflow_token_hardstop_a137_lab.py",16,ROOT/"tests"),
    ("test_atlasquant_source_backup_workflow.py",1,ROOT),
)

def main():
    cases=[]
    for name,count,folder in SUITES:
        if len(list(folder.glob(name)))!=1:
            raise SystemExit("FAIL-CLOSED A157 missing/duplicate "+name)
        discovered=unittest.TestLoader().discover(
            start_dir=str(folder),pattern=name,top_level_dir=str(folder))
        actual=discovered.countTestCases()
        print(f"DISCOVERED {name}: {actual}, expected {count}",flush=True)
        if actual!=count:
            raise SystemExit("FAIL-CLOSED A157 count drift "+name)
        cases.append(discovered)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(cases))
    total=sum(c for _,c,_ in SUITES)
    if result.testsRun!=total or result.skipped or not result.wasSuccessful():
        raise SystemExit(f"FAIL-CLOSED A157 ran={result.testsRun}/{total} "
                         f"failure={len(result.failures)} error={len(result.errors)} "
                         f"skipped={len(result.skipped)}")
    print(f"PASS A157 {total} source-only workflow tests; HARD NO-GO",flush=True)

if __name__=="__main__":
    main()
