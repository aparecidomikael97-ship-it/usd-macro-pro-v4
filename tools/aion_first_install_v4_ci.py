"""V4 anchor lab suites plus exact unchanged V3/V2/V1 groups; no overlap."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.aion_first_install_v3_ci import GROUPS as V3_GROUPS
from tools.aion_first_install_preparation_ci import CountedResult
GROUPS={
    'v4_signed_commitments':('tests.test_aion_signed_commitments_v4',),
    'v4_freshness_provenance':('tests.test_aion_anchor_freshness_v4',),
    'v4_rollback_fork_causal_processes':('tests.test_aion_anchor_rollback_recovery_v4',),
    **V3_GROUPS,
}

def main():
    modules=[m for group in GROUPS.values() for m in group]
    if len(modules)!=len(set(modules)):raise RuntimeError('OVERLAPPING_MODULES')
    reports={};failed=False
    with patch('socket.socket.connect',side_effect=AssertionError('NO_NETWORK')),patch('socket.socket.connect_ex',side_effect=AssertionError('NO_NETWORK')),patch('socket.create_connection',side_effect=AssertionError('NO_NETWORK')):
        for group,names in GROUPS.items():
            out=unittest.TextTestRunner(verbosity=2,resultclass=CountedResult).run(unittest.defaultTestLoader.loadTestsFromNames(names))
            report=dict(tests=out.testsRun,subtests=out.subtest_count,errors=len(out.errors),failures=len(out.failures),
                skips=len(out.skipped),expected_failures=len(out.expectedFailures))
            reports[group]=report;failed |= not out.wasSuccessful() or bool(out.skipped) or bool(out.expectedFailures)
            print('V4_GROUP_RESULT='+json.dumps({'group':group,**report}),flush=True)
    data=dict(status='HARD_NO_GO',groups=reports,modules=modules,external_anchor_verified=False,
        privileged_joint_restore_detectable=False,power_loss_physically_tested=False,browser_tested=False)
    target=ROOT/'artifacts';target.mkdir(exist_ok=True)
    (target/'aion-first-install-v4-tests.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    return 1 if failed else 0
if __name__=='__main__':raise SystemExit(main())
