"""Offline V2 suites followed by unchanged V1 regression inventory, no overlap."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.aion_first_install_preparation_ci import MODULES,CountedResult

GROUPS={
    'webauthn':('tests.test_aion_webauthn_reference_v2',),
    'causal_sqlite_processes':('tests.test_aion_causal_recovery_v2',),
    'dossier_and_metadata':('tests.test_aion_evidence_dossier_v2','tests.test_aion_manifest_metadata_v2'),
    'unchanged_v1_regressions':MODULES,
}

def main():
    reports={};failed=False
    with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')),patch('socket.socket.connect_ex',side_effect=AssertionError('NO_NETWORK')),patch('socket.create_connection',side_effect=AssertionError('NO_NETWORK')):
        for group,names in GROUPS.items():
            suite=unittest.defaultTestLoader.loadTestsFromNames(names)
            outcome=unittest.TextTestRunner(verbosity=2,resultclass=CountedResult).run(suite)
            report=dict(tests=outcome.testsRun,subtests=outcome.subtest_count,errors=len(outcome.errors),
                failures=len(outcome.failures),skips=len(outcome.skipped),expected_failures=len(outcome.expectedFailures))
            reports[group]=report
            failed |= not outcome.wasSuccessful() or bool(outcome.skipped) or bool(outcome.expectedFailures)
            print('V2_GROUP_RESULT='+json.dumps({'group':group,**report}),flush=True)
    payload=dict(status='HARD_NO_GO',groups=reports,browser_tests_executed=False,
        physical_identity_tested=False,independent_custody_tested=False)
    target=ROOT/'artifacts';target.mkdir(exist_ok=True)
    (target/'aion-first-install-v2-tests.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
