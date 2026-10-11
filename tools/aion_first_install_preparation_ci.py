"""Safe CI/local tests with network forbidden; reports actual counts, no GO."""
from pathlib import Path
import ast
import json
import sys
import trace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
MODULES=(
    "tests.test_aion_first_install_preparation_v1",
    "tests.test_aion_first_install_reference_processes_v1",
    "tests.test_aion_first_install_plan_v1",
    "tests.test_aion_first_install_evidence_no_go_1215",
    "test_atlasquant_aion_global_worker_source_gate_v1",
    "test_atlasquant_aion_global_worker_readiness_source_gate_v1",
    "test_atlasquant_aion_readiness_credential_fence_1190",
    "test_atlasquant_aion_checkpoint_dual_challenge_reference_v1",
    "tests.test_atlasquant_aion_v2_isolated_sqlite_witness_cas_reference",
    "tests.test_atlasquant_aion_v2_external_witness_rollback_reference",
    "tests.test_atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference",
    "tests.test_atlasquant_aion_v2_unknown_outcome_reconciliation_reference",
    "test_atlasquant_access_fallback_fail_closed",
    "test_aion_history_truth_preparation",
    "tests.test_aion_browser_request_binding_units",
)

class CountedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.subtest_count=0
    def addSubTest(self,test,subtest,err):
        self.subtest_count+=1;super().addSubTest(test,subtest,err)

def execute():
    with patch("socket.socket.connect",side_effect=AssertionError("NO_NETWORK")), \
         patch("socket.socket.connect_ex",side_effect=AssertionError("NO_NETWORK")), \
         patch("socket.create_connection",side_effect=AssertionError("NO_NETWORK")):
        suite=unittest.defaultTestLoader.loadTestsFromNames(MODULES)
        return unittest.TextTestRunner(verbosity=2,resultclass=CountedResult).run(suite)

def main():
    tracer=trace.Trace(count=True,trace=False,ignoredirs=[sys.base_prefix])
    result=tracer.runfunc(execute)
    counts=tracer.results().counts
    names={name for name,_ in counts}
    normalized={name:str(Path(name).resolve()) for name in names}
    by_file={}
    for (name,line),hits in counts.items():
        if hits:by_file.setdefault(normalized[name],set()).add(line)
    files=list((ROOT/'atlasquant_aion_first_install_preparation').glob('*.py'))
    files.append(ROOT/'atlasquant_aion_v2_isolated_sqlite_witness_cas_reference.py')
    coverage={}
    for path in files:
        lines=sorted(by_file.get(str(path.resolve()),set()))
        tree=ast.parse(path.read_text(encoding='utf-8'))
        functions={n.name:any(n.body[0].lineno<=line<=n.end_lineno for line in lines)
                   for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        coverage[path.relative_to(ROOT).as_posix()]={"executed_line_count":len(lines),"functions_exercised":functions}
    data=dict(status="HARD_NO_GO",test_count=result.testsRun,subtest_count=result.subtest_count,
              failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
              expected_failures=len(result.expectedFailures),successful=result.wasSuccessful(),
              modules=MODULES,coverage=coverage,coverage_method="stdlib trace; executed lines/functions, not branch coverage",
              physical_validation_performed=False,external_witness_enrolled=False)
    target=ROOT/'artifacts';target.mkdir(exist_ok=True)
    (target/'aion-first-install-preparation-tests.json').write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
    print('OFFLINE_PREPARATION_RESULT='+json.dumps({k:v for k,v in data.items() if k not in ('coverage','modules')}),flush=True)
    print('OFFLINE_PREPARATION_FUNCTION_COVERAGE='+json.dumps(coverage,sort_keys=True),flush=True)
    return 0 if result.wasSuccessful() and not result.skipped and not result.expectedFailures else 1

if __name__=='__main__':raise SystemExit(main())
