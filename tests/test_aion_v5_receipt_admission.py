"""V5 adversarial offline admission tests against real throwaway SQLite."""
from __future__ import annotations
from copy import deepcopy
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from atlasquant_aion_first_install_preparation_v4.signed_anchors import READ_DOMAIN
from atlasquant_aion_first_install_preparation_v5.receipt_admission import (
    OfflineWitnessReceiptAdmission, _verify, SCHEMA, TABLES,
)
from tests.aion_signed_anchor_fixtures_v4 import AnchorFixture

class DurableAdmissionV5Tests(unittest.TestCase):
    def setUp(self):
        self.fx=AnchorFixture()
        self.addCleanup(self.fx.close)
        self.fx.consume()
        self.config=self.fx.cfg(0)
        self.pin=self.fx.pins[0]
        self.floor=self.fx.floors[0]
        self.path=Path(self.fx.ledger.tmp.name)/"witness-read-v5.sqlite3"
        self.ledger=self.open(bootstrap=True)
        self.query=self.fx.query(0)
        self.response=self.fx.response(0,self.query)

    def open(self,bootstrap=False):
        return OfflineWitnessReceiptAdmission(self.path,config=self.config,pin=self.pin,
                                               floor=self.floor,bootstrap=bootstrap)
    def issue(self,query=None,operation_id="fixture-issue-v5"):
        return self.ledger.issue_reference(query or self.query,operation_id=operation_id)
    def admit(self,query=None,response=None):
        return self.ledger.admit_reference(query or self.query,response or self.response,now=1000)
    def assert_no_authority(self,out):
        self.assertEqual(out["status"],"HARD_NO_GO")
        for k in ("installer_authorized","worker_authorized","owner_identity_verified",
                  "external_anchor_verified","independent_custody_verified",
                  "safe_to_resume","automatic_retry_allowed","billing_authorized"):
            self.assertIs(out[k],False)

    def test_issue_admit_readback_are_durable_but_not_external_trust(self):
        self.assertEqual(self.issue()["state"],"REFERENCE_ISSUED_UNTRUSTED")
        out=self.admit();self.assertEqual(out["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        self.assert_no_authority(out)
        self.assertTrue(out["nonce_consumed_locally"])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state FROM nonces").fetchone()[0],"CONSUMED")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],1)
        reopened=self.open()
        read=reopened.readback_reference(self.query["nonce"],
                                         expected_receipt_digest=sha256(json.dumps(
                                         self.response,sort_keys=True,separators=(",",":"),
                                         ensure_ascii=True).encode()).hexdigest())
        self.assertEqual(read["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        self.assert_no_authority(read)

    def test_duplicate_nonce_reissue_or_readmit_denied(self):
        self.assertEqual(self.issue()["state"],"REFERENCE_ISSUED_UNTRUSTED")
        self.assertEqual(self.admit()["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        self.assertEqual(self.admit()["state"],"BLOCKED")
        self.assertEqual(self.issue(operation_id="fixture-another-issue")["state"],"BLOCKED")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],1)

    def test_valid_math_not_issue_and_invalid_signature_no_consumption(self):
        # The V4 mathematical result alone is not a durable admission.
        self.assertEqual(self.admit()["state"],"BLOCKED")
        self.issue()
        bad=deepcopy(self.response)
        bad["signature"]="0"*128
        self.assertEqual(self.admit(response=bad)["state"],"BLOCKED")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT state FROM nonces").fetchone()[0],"ISSUED")
        self.assertEqual(self.admit()["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")

    def test_signed_different_nonce_or_query_fails_without_consumption(self):
        self.issue()
        changed=deepcopy(self.query);changed["nonce"]="a"*64
        altered_response=self.fx.response(0,changed)
        self.assertEqual(self.ledger.admit_reference(changed,altered_response,now=1000)["state"],"BLOCKED")
        self.assertEqual(self.admit()["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")

    def test_key_revocation_after_issuance_blocks_read(self):
        self.issue()
        self.assertEqual(self.ledger.revoke_reference("KEY",self.pin["key_id"],
                                                       operation_id="fixture-revoke-v5")["state"],
                         "REFERENCE_REVOCATION_UNTRUSTED")
        self.assertEqual(self.admit()["state"],"BLOCKED")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],0)
        self.assertEqual(self.ledger.revoke_reference("KEY",self.pin["key_id"],
                                                       operation_id="fixture-revoke-v5-again")["state"],"BLOCKED")

    def test_no_fallback_for_missing_or_corrupt_database(self):
        self.assertEqual(self.issue()["state"],"REFERENCE_ISSUED_UNTRUSTED")
        self.path.unlink()
        self.assertIn(self.admit()["state"],("RECONCILIATION_REQUIRED","UNKNOWN_OUTCOME"))
        self.assertFalse(self.path.exists())

    def test_schema_constraint_removal_rejected_without_repair(self):
        self.issue()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("ALTER TABLE nonces RENAME TO old_nonces")
            db.execute("CREATE TABLE nonces (nonce TEXT,operation_id TEXT,query_json TEXT,state TEXT,receipt_digest TEXT)")
            db.execute("INSERT INTO nonces SELECT * FROM old_nonces")
            db.execute("DROP TABLE old_nonces")
            db.commit()
        self.assertEqual(self.admit()["state"],"BLOCKED")
        self.assertEqual(self.open().issue_reference(self.query,operation_id="fixture-later")["state"],"BLOCKED")

    def test_two_threads_one_receipt(self):
        self.issue()
        results=[]
        def worker():
            results.append(self.open().admit_reference(self.query,self.response,now=1000)["state"])
        ts=[threading.Thread(target=worker) for _ in range(4)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(results.count("REFERENCE_DURABLE_RECEIPT_UNTRUSTED"),1)
        self.assertEqual(len(results),4)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],1)

    def test_other_process_readback_and_replay_denied(self):
        self.issue()
        self.assertEqual(self.admit()["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        raw=json.dumps({"config":self.config,"pin":self.pin,"floor":self.floor,
                        "query":self.query,"response":self.response})
        conf=Path(self.fx.ledger.tmp.name)/"v5-public-fixture.json"
        conf.write_text(raw,encoding="utf-8")
        script="""import json,sys
from atlasquant_aion_first_install_preparation_v5.receipt_admission import OfflineWitnessReceiptAdmission
d=json.load(open(sys.argv[2],encoding='utf-8'))
x=OfflineWitnessReceiptAdmission(sys.argv[1],config=d['config'],pin=d['pin'],floor=d['floor'])
print(x.admit_reference(d['query'],d['response'],now=1000)['state'])
"""
        p=subprocess.run([sys.executable,"-c",script,str(self.path),str(conf)],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=Path(__file__).resolve().parents[1],timeout=20)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.strip(),"BLOCKED")

    def test_joint_restore_is_still_known_high_risk(self):
        self.issue()
        # SQLite backup API snapshots logical DB, avoiding assumptions about WAL.
        prior=Path(self.fx.ledger.tmp.name)/"prior-v5.sqlite3"
        with closing(sqlite3.connect(self.path)) as src,closing(sqlite3.connect(prior)) as dst:
            src.backup(dst)
        self.assertEqual(self.admit()["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        with closing(sqlite3.connect(prior)) as src,closing(sqlite3.connect(self.path)) as dst:
            src.backup(dst)
        # This self-consistent local rollback CAN pass: no external anchor.
        again=self.admit()
        self.assertEqual(again["state"],"REFERENCE_DURABLE_RECEIPT_UNTRUSTED")
        self.assertFalse(again["independent_rollback_protection_verified"])

if __name__=="__main__":
    unittest.main()
