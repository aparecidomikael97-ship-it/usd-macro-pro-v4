"""V3 suites and exact V2/V1 inventory; no duplicated modules or silent skips."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.aion_first_install_v2_ci import GROUPS as V2_GROUPS
from tools.aion_first_install_preparation_ci import CountedResult

GROUPS={
    'v3_challenge_consumption':('tests.test_aion_webauthn_ledger_v3',),
    'v3_registry_counters':('tests.test_aion_webauthn_registry_v3',),
    'v3_sqlite_process_recovery':('tests.test_aion_webauthn_recovery_v3',),
    **V2_GROUPS,
}

def main():
    reports={};failed=False
    modules=[m for names in GROUPS.values() for m in names]
    if len(modules)!=len(set(modules)):raise RuntimeError('OVERLAPPING_SUITE_MODULES')
    with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')),patch('socket.socket.connect_ex',side_effect=AssertionError('NO_NETWORK')),patch('socket.create_connection',side_effect=AssertionError('NO_NETWORK')):
        for group,names in GROUPS.items():
            outcome=unittest.TextTestRunner(verbosity=2,resultclass=CountedResult).run(unittest.defaultTestLoader.loadTestsFromNames(names))
            report=dict(tests=outcome.testsRun,subtests=outcome.subtest_count,errors=len(outcome.errors),
                failures=len(outcome.failures),skips=len(outcome.skipped),expected_failures=len(outcome.expectedFailures))
            reports[group]=report
            failed |= not outcome.wasSuccessful() or bool(outcome.skipped) or bool(outcome.expectedFailures)
            print('V3_GROUP_RESULT='+json.dumps({'group':group,**report}),flush=True)
    data=dict(status='HARD_NO_GO',groups=reports,modules=modules,browser_tests_executed=False,
        physical_owner_tested=False,privileged_rollback_protection_verified=False)
    target=ROOT/'artifacts';target.mkdir(exist_ok=True)
    (target/'aion-first-install-v3-tests.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
