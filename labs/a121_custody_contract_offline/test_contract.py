"""A121 tests: negative-only custody boundary tests; no proof of real independent admin."""
import multiprocessing as mp
from pathlib import Path
from contextlib import closing
import shutil
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from contract import CustodianFixture, Denied, FakeSender, Intent, Uncertain, production_enabled


def mutate_database(path, sql, params=()):
    with closing(sqlite3.connect(path)) as db:
        db.execute(sql, params)
        db.commit()


def mk_intent(k='ABC'):
    return Intent(intent_id='INT-'+k,idem_key='IDEM-'+k,owner='owner-demo',tenant='tenant-demo',
                  workspace='workspace-demo',action='fake-sms',account='fake-account',
                  destination_digest='hash-destination-012345',payload_digest='hash-payload-012345',epoch=1)


def attempt_process(args):
    path, key = args
    db=CustodianFixture(path)
    x=mk_intent(key)
    try:
        db.dispatch_once(x)
        return 'ISSUED'
    except Denied:
        return 'DENIED'

class CustodyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a121-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.external=self.root/'simulated_custodian.db'
        self.local=self.root/'client.db'
        self.db=CustodianFixture(self.external)
        self.intent=mk_intent()

    def prep(self):
        return self.db.enroll_intent(self.intent)

    def test_01_local_snapshot_rollback_cannot_rewind_separate_fixture(self):
        mirror=self.prep(); old=dict(mirror)
        with closing(sqlite3.connect(self.local)) as con:
            con.execute("CREATE TABLE mirror(state TEXT, version INTEGER, binding TEXT)")
            con.execute("INSERT INTO mirror VALUES (?,?,?)",(old['state'],old['version'],old['binding']))
            con.commit()
        local_backup=self.root/'client-backup.db'
        shutil.copy2(self.local,local_backup)
        sender=FakeSender()
        self.db._sender=sender
        self.db.dispatch_once(self.intent)
        self.assertEqual(sender.sink,[self.intent.identity_hash])
        mutate_database(self.local,"UPDATE mirror SET state='UNKNOWN',version=2")
        shutil.copy2(local_backup,self.local)  # genuine SQLite client mirror rollback
        with closing(sqlite3.connect(self.local)) as con:
            stale=con.execute("SELECT state,version,binding FROM mirror").fetchone()
        self.assertEqual(stale,(old['state'],old['version'],old['binding']))
        with self.assertRaisesRegex(Denied,'ROLLBACK_OR_DIVERGENCE'):
            self.db.verify_mirror(self.intent,dict(zip(('state','version','binding'),stale)))
        with self.assertRaisesRegex(Denied,'ISSUE_ALREADY'):
            self.db.dispatch_once(self.intent)
        self.assertEqual(len(sender.sink),1)

    def test_02_locally_removed_witness_required_does_not_affect_external_enrollment(self):
        self.prep()
        fake=FakeSender();self.db._sender=fake
        self.db.dispatch_once(self.intent)
        # Tenant-local policy may be rewritten, but it has no authority to enroll.
        with closing(sqlite3.connect(self.local)) as con:
            con.execute("CREATE TABLE config (witness_required INTEGER, state TEXT)")
            con.execute("INSERT INTO config VALUES(0,'PREPARED')")
            con.commit()
        with self.assertRaisesRegex(Denied,'ISSUE_ALREADY'):
            self.db.dispatch_once(self.intent)
        self.assertEqual(len(fake.sink),1)

    def test_03_deleted_issue_audit_is_detected(self):
        self.prep();self.db.dispatch_once(self.intent)
        mutate_database(self.external,"DELETE FROM audit WHERE event='ISSUE_ONCE'")
        with self.assertRaises(Denied): self.db.read(self.intent)

    def test_04_deleted_nonce_table_row_is_detected(self):
        self.prep();self.db.register_receipt_nonce(self.intent,'test-nonce-1')
        mutate_database(self.external,"DELETE FROM nonces WHERE nonce='test-nonce-1'")
        with self.assertRaisesRegex(Denied,'NONCE_LEDGER'):self.db.read(self.intent)

    def test_05_forged_issue_audit_event_is_detected(self):
        self.prep();self.db.dispatch_once(self.intent)
        mutate_database(self.external,"UPDATE audit SET event='FAKE_NO_EFFECT_FENCED' WHERE event='ISSUE_ONCE'")
        with self.assertRaisesRegex(Denied,'AUDIT_TAMPER'):self.db.read(self.intent)

    def test_06_same_id_other_tenant_rejected(self):
        self.prep()
        with self.assertRaisesRegex(Denied,'SCOPE_CONFLICT'):
            self.db.enroll_intent(replace(self.intent,tenant='tenant-B'))

    def test_07_same_id_new_destination_rejected(self):
        self.prep()
        with self.assertRaisesRegex(Denied,'SCOPE_CONFLICT'):
            self.db.read(replace(self.intent,destination_digest='changed'))

    def test_08_no_enrollment_denied(self):
        with self.assertRaises(Denied):self.db.dispatch_once(self.intent)

    def test_09_external_service_down_denied(self):
        self.prep();self.db.available=False
        with self.assertRaisesRegex(Denied,'UNAVAILABLE'):self.db.dispatch_once(self.intent)

    def test_10_source_unenrolled_denied(self):
        self.db.enrolled=False
        with self.assertRaisesRegex(Denied,'ENROLLMENT'):self.db.enroll_intent(self.intent)

    def test_11_timeout_records_unknown_and_no_retry(self):
        self.prep();sender=FakeSender(effect='timeout');self.db._sender=sender
        with self.assertRaises(Uncertain):self.db.dispatch_once(self.intent)
        self.assertEqual(self.db.read(self.intent)['state'],'UNKNOWN')
        with self.assertRaises(Denied):self.db.dispatch_once(self.intent)
        self.assertEqual(len(sender.sink),1)

    def test_12_after_issue_crash_no_send_no_retry(self):
        self.prep();sender=FakeSender();self.db._sender=sender
        with self.assertRaises(Uncertain):self.db.dispatch_once(self.intent,crash_after_mark=True)
        self.assertEqual(sender.sink,[])
        with self.assertRaises(Denied):self.db.dispatch_once(self.intent)

    def test_13_pre_fence_prevents_issue(self):
        self.prep();self.db.fence_pre_handoff(self.intent)
        with self.assertRaises(Denied):self.db.dispatch_once(self.intent)

    def test_14_after_issue_no_posthandoff_fence(self):
        self.prep();self.db.dispatch_once(self.intent)
        with self.assertRaises(Denied):self.db.fence_pre_handoff(self.intent)

    def test_15_replay_nonce_for_another_intent_denied(self):
        self.prep();self.db.register_receipt_nonce(self.intent,'unique-nonce-1')
        second=mk_intent('DEF');self.db.enroll_intent(second)
        with self.assertRaisesRegex(Denied,'NONCE_REPLAY'):self.db.register_receipt_nonce(second,'unique-nonce-1')

    def test_16_ledger_state_tamper_denied(self):
        self.prep()
        mutate_database(self.external,"UPDATE intents SET state='UNKNOWN' WHERE intent_id=?",(self.intent.intent_id,))
        with self.assertRaisesRegex(Denied,'COMMITMENT_MISMATCH'):self.db.read(self.intent)

    def test_17_nonce_ledger_append_preserves_state(self):
        before=self.prep()
        self.db.register_receipt_nonce(self.intent,'nonce-test-1')
        self.assertEqual(before,self.db.read(self.intent))

    def test_18_missing_client_mirror_denied(self):
        self.prep()
        with self.assertRaisesRegex(Denied,'MIRROR_MISSING'):self.db.verify_mirror(self.intent,None)

    def test_19_ahead_of_custodian_mirror_denied(self):
        before=self.prep(); forged=dict(before,version=2)
        with self.assertRaises(Denied):self.db.verify_mirror(self.intent,forged)

    def test_20_untrusted_sdk_denied(self):
        self.prep()
        with self.assertRaisesRegex(Denied,'CUSTODIAN_FAKE_SENDER'):CustodianFixture(self.external,sender=object())

    def test_21_two_workers_cas_one_issue(self):
        self.prep()
        with mp.get_context('spawn').Pool(8) as pool:
            results=pool.map(attempt_process,[(str(self.external),'ABC')]*32)
        self.assertEqual(results.count('ISSUED'),1)
        self.assertEqual(results.count('DENIED'),31)
        self.assertEqual(self.db.read(self.intent)['state'],'UNKNOWN')

    def test_22_no_production_enablement(self):
        self.assertFalse(production_enabled())

    def test_23_open_limitation_full_custodian_restore_reissues(self):
        # This test PASSES when the trust assumption fails; it is a NEGATIVE COUNTEREXAMPLE.
        # Someone with authority to roll back the supposed custodian ledger can bypass it.
        self.prep()
        backup=self.root/'custodian-before-issue.bak'
        shutil.copy2(self.external,backup)
        recorder=FakeSender();self.db._sender=recorder
        self.db.dispatch_once(self.intent)
        self.assertEqual(len(recorder.sink),1)
        shutil.copy2(backup,self.external)
        self.db.dispatch_once(self.intent)
        self.assertEqual(len(recorder.sink),2)  # NOT A SECURITY PASS


if __name__=='__main__':unittest.main()
