"""A119 H0-GW-01: deliberate RED regression tests for purely simulated witness custody.

Synthetic and isolated: same-machine SQLite + mock witness are *not* H0 proof.
"""
import sqlite3
from pathlib import Path
import tempfile
import unittest

try:
    from .gateway import Gateway, SimulatedHighWater, FakeAdapter, Denied, InjectedCrash
    from .test_gateway import good_policy, sample
except ImportError:
    from gateway import Gateway, SimulatedHighWater, FakeAdapter, Denied, InjectedCrash
    from test_gateway import good_policy, sample


class WitnessHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="AION_H0GW_WITNESS_")
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "gateway.sqlite"
        self.witness = SimulatedHighWater()
        self.intent = sample("witness-intent-0001")
        self.gateway = Gateway(self.db, good_policy(), witness=self.witness)
        self.gateway.prepare(self.intent)

    def test_17_same_version_rewrite_to_prepared_must_not_reissue(self):
        calls = []
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(calls), crash_at="after_handoff")
        self.assertEqual(len(calls), 1)
        # DBA rewrites row to PREPARED without lowering its version (still v2).
        # Pure version high-water cannot spot the fork.
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE intents SET state='PREPARED', issued_count=0 WHERE intent_id=?",
                        (self.intent.logical_intent_id,))
        with self.assertRaisesRegex(Denied, "DIVERGENCE|QUARANTINE"):
            self.gateway.dispatch_once(self.intent, FakeAdapter(calls))
        self.assertEqual(len(calls), 1)

    def test_18_witness_lags_ledger_must_deny_not_silently_repair(self):
        self.gateway.fence_pre_handoff(self.intent)  # committed v2
        self.witness.values[self.intent.logical_intent_id] = 1
        with self.assertRaisesRegex(Denied, "DIVERGENCE|WITNESS_LAG|QUARANTINE"):
            self.gateway.inspect(self.intent)

    def test_19_reopen_without_required_witness_must_deny(self):
        calls = []
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(calls), crash_at="after_handoff")
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE intents SET state='PREPARED', issued_count=0 WHERE intent_id=?",
                        (self.intent.logical_intent_id,))
        reopened = Gateway(self.db, good_policy(), witness=None)
        with self.assertRaisesRegex(Denied, "WITNESS_REQUIRED|QUARANTINE"):
            reopened.dispatch_once(self.intent, FakeAdapter(calls))
        self.assertEqual(len(calls), 1)

    def test_20_lost_or_unavailable_witness_remains_fail_closed(self):
        self.witness.values.clear()
        with self.assertRaisesRegex(Denied, "WITNESS_UNAVAILABLE"):
            self.gateway.dispatch_once(self.intent, FakeAdapter())
        self.witness.available = False
        with self.assertRaisesRegex(Denied, "WITNESS_UNAVAILABLE"):
            self.gateway.inspect(self.intent)

    def test_21_rollback_to_absent_row_cannot_reprepare_old_intent(self):
        with self.assertRaises(InjectedCrash):
            self.gateway.dispatch_once(self.intent, FakeAdapter(), crash_at="after_marker")
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM intents WHERE intent_id=?", (self.intent.logical_intent_id,))
        with self.assertRaisesRegex(Denied, "ROLLBACK|QUARANTINE"):
            self.gateway.prepare(self.intent)

    def test_22_witness_unavailable_mid_transition_rolls_back_state(self):
        self.witness.available = False
        with self.assertRaisesRegex(Denied, "WITNESS_UNAVAILABLE"):
            self.gateway.fence_pre_handoff(self.intent)
        self.witness.available = True
        self.assertEqual(self.gateway.inspect(self.intent)["state"], "PREPARED")

    def test_23_same_version_receipt_boundary_and_operation_fork_denied(self):
        self.gateway.dispatch_once(self.intent, FakeAdapter())
        # No fake receipt necessary: inject forged provider outcome at same v2.
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE intents SET boundary='DELIVERED', operation_id='forged' WHERE intent_id=?",
                        (self.intent.logical_intent_id,))
        with self.assertRaisesRegex(Denied, "DIVERGENCE|QUARANTINE"):
            self.gateway.inspect(self.intent)

    def test_24_no_witness_row_still_safe_original_behavior(self):
        # Legacy no-witness simulator is deliberately inert, not H0 proof.
        other = sample("no-witness-test")
        no_witness_db = Path(self.temp.name) / "no-witness.sqlite"
        gw = Gateway(no_witness_db, good_policy(), witness=None)
        gw.prepare(other)
        gw.dispatch_once(other, FakeAdapter())
        self.assertEqual(gw.inspect(other)["issue_count"], 1)
        with self.assertRaises(Denied):
            gw.dispatch_once(other, FakeAdapter())


if __name__ == "__main__":
    unittest.main(verbosity=2)
