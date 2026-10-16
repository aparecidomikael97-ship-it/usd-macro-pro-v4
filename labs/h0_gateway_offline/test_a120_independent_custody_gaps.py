"""A120: demonstrate five UNRESOLVED safety gaps in A119's toy witness.

These tests pass when an ATTACK is successfully reproduced; they are *not*
security acceptance tests. NEVER call A120 PASS a proof of safety/H0/F1/T1.
No provider, network, external sender or real identity exists in this test.
"""
import copy
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from .gateway import Gateway, SimulatedHighWater, FakeAdapter, FakeReceiptAuthority, InjectedCrash
    from .test_gateway import good_policy, sample
except ImportError:
    from gateway import Gateway, SimulatedHighWater, FakeAdapter, FakeReceiptAuthority, InjectedCrash
    from test_gateway import good_policy, sample


class IndependentCustodyGapsOPEN(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='A120_H0_NEGATIVE_')
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'ledger.sqlite'
        self.witness = SimulatedHighWater()
        self.authority = FakeReceiptAuthority()
        self.gateway = Gateway(self.db, good_policy(), witness=self.witness, verifier=self.authority)
        self.intent = sample('a120-intent-1')
        self.gateway.prepare(self.intent)

    def test_gap_01_simultaneous_database_and_witness_rollback_reissues_fake_call(self):
        backup = Path(self.temp.name) / 'before-issue.sqlite'
        shutil.copyfile(self.db, backup)
        values = copy.deepcopy(self.witness.values)
        commitments = copy.deepcopy(self.witness.commitments)
        sink = []
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(sink), crash_at='after_handoff')
        self.assertEqual(len(sink), 1)
        shutil.copyfile(backup, self.db)
        self.witness.values = values
        self.witness.commitments = commitments
        self.gateway.dispatch_once(self.intent, FakeAdapter(sink))
        self.assertEqual(len(sink), 2, 'ATTACK DEMONSTRATION: co-rollback can reissue')

    def test_gap_02_mutable_witness_required_bit_allows_reopen_without_witness(self):
        sink = []
        self.gateway.dispatch_once(self.intent, FakeAdapter(sink))
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE intents SET state='PREPARED', issued_count=0, witness_required=0 WHERE intent_id=?",
                        (self.intent.logical_intent_id,))
        downgraded = Gateway(self.db, good_policy(), witness=None)
        downgraded.dispatch_once(self.intent, FakeAdapter(sink))
        self.assertEqual(len(sink), 2, 'ATTACK DEMONSTRATION: local trust bit can be stripped')

    def test_gap_03_deleting_issued_audit_event_is_not_detected_by_row_witness(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM audit WHERE event='ISSUE_ONCE' AND intent_id=?",
                        (self.intent.logical_intent_id,))
        state = self.gateway.inspect(self.intent)
        self.assertEqual(state['state'], 'UNKNOWN')
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM audit WHERE event='ISSUE_ONCE' AND intent_id=?",
                                         (self.intent.logical_intent_id,)).fetchone()[0], 0)

    def test_gap_04_nonce_journal_deletion_allows_cross_intent_nonce_reuse(self):
        other = sample('a120-intent-2')
        self.gateway.prepare(other)
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        self.gateway.dispatch_once(other, FakeAdapter())
        self.gateway.accept_receipt(self.intent, self.authority.sign(self.intent, kind='API_CREATED', nonce='cross-intent-nonce', sequence=1))
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM seen_nonces WHERE nonce='cross-intent-nonce'")
        result = self.gateway.accept_receipt(other, self.authority.sign(other, kind='API_CREATED', nonce='cross-intent-nonce', sequence=1))
        self.assertEqual(result, 'PROVIDER_ACCEPTED', 'ATTACK DEMONSTRATION: global nonce reuse accepted after journal erasure')

    def test_gap_05_same_version_audit_forgery_is_not_detected_by_witness(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE audit SET event='FAKE_NO_EFFECT_FENCED' WHERE intent_id=? AND event='ISSUE_ONCE'",
                        (self.intent.logical_intent_id,))
        self.assertEqual(self.gateway.inspect(self.intent)['state'], 'UNKNOWN')
        with sqlite3.connect(self.db) as con:
            forged = con.execute('SELECT event FROM audit WHERE intent_id=? ORDER BY version DESC LIMIT 1',
                                 (self.intent.logical_intent_id,)).fetchone()[0]
        self.assertEqual(forged, 'FAKE_NO_EFFECT_FENCED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
