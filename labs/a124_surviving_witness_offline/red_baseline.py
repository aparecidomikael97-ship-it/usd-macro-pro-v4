"""Intentionally RED baseline replay: A123 alone cannot stop joint local DB rollback.

Run ONLY explicitly: python -m unittest red_baseline.py -v
Expected: 1 FAIL, proving the need for an independently surviving witness.
"""
from pathlib import Path
import sys, tempfile, shutil, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'a123_receipts_offline'))
from contract import AdmissionFixture, Intent, ToyVault, LocalToySigner, FakeSender

class RedBeforeExternalWitness(unittest.TestCase):
    def test_joint_local_restore_should_not_allow_second_issue(self):
        with tempfile.TemporaryDirectory() as d:
            local, vault = Path(d)/'aion.db', Path(d)/'custody.db'
            sink=FakeSender([])
            g=AdmissionFixture(local,ToyVault(vault,LocalToySigner()),sender=sink)
            intent=Intent('RED-LOGICAL-ID','OWNER-X','TENANT-X','WORK-X','ACCOUNT-X','EMAIL','DEST-A','PAY-A',1)
            g.prepare(intent)
            lbackup,vbackup=Path(d)/'aion.bak',Path(d)/'custody.bak'
            shutil.copy2(local,lbackup);shutil.copy2(vault,vbackup)
            g.issue_once(intent)
            shutil.copy2(lbackup,local);shutil.copy2(vbackup,vault)
            g.issue_once(intent,nonce='ISSUE-SECOND-ATTEMPT')
            # Deliberately FALSE in A123: second FakeSender call got through.
            self.assertEqual(len(sink.sink),1,'RED: joint rollback allows second fake send')

if __name__=='__main__': unittest.main()
