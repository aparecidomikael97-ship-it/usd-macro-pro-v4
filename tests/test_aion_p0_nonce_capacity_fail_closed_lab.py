"""AION P0 LAB: bounded nonce tombstones without replay-by-compaction.

A capacity limit MUST refuse new claims while preserving every consumed
nonce: denial is preferable to silently deleting history. Tests use only
temporary synthetic SQLite; max override is used in LAB only.
No external witness, actual owner enrollment or worker authorization.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

import atlasquant_aion_nonce_registry as nonce_mod
from atlasquant_aion_nonce_registry import PersistentNonceRegistry

NOW = "2026-10-20T15:00:00Z"
END = "2026-10-20T15:03:00Z"
LATER_NOW = "2026-10-20T15:05:00Z"
LATER_END = "2026-10-20T15:06:00Z"


class NonceBoundedRetentionLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-nonce-capacity-lab-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "nonces.sqlite3"
        self.nonces = PersistentNonceRegistry(self.db)
        self.cap = patch.object(nonce_mod, "MAX_NONCE_CLAIMS", 2)
        self.cap.start()
        self.addCleanup(self.cap.stop)

    def claim(self, nonce, scope="owner.test", now=NOW, expiry=END):
        return self.nonces.claim(
            scope=scope, nonce=nonce, now_ts=now, expires_at=expiry,
        )

    def fill(self):
        self.assertTrue(self.claim("a"))
        self.assertTrue(self.claim("b"))
        self.assertEqual(self.nonces.count(), 2)

    def test_01_configured_default_cap_is_finite_and_positive(self):
        self.assertGreaterEqual(nonce_mod.SCHEMA_VERSION, 2)
        self.assertGreater(nonce_mod.MAX_NONCE_CLAIMS, 0)

    def test_02_claim_below_capacity_is_allowed(self):
        self.assertTrue(self.claim("a"))
        self.assertEqual(self.nonces.count(), 1)

    def test_03_at_capacity_new_claim_must_fail_closed(self):
        self.fill()
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("c")
        self.assertEqual(self.nonces.count(), 2)

    def test_04_replay_at_capacity_still_returns_false_without_erase(self):
        self.fill()
        self.assertFalse(self.claim("a"))
        self.assertTrue(self.nonces.contains(scope="owner.test", nonce="a"))
        self.assertEqual(self.nonces.count(), 2)

    def test_05_other_scope_cannot_bypass_global_capacity(self):
        self.fill()
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("c", scope="owner.other")
        self.assertEqual(self.nonces.count(), 2)

    def test_06_future_clock_does_not_reclaim_any_tombstone(self):
        self.fill()
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("later", now=LATER_NOW, expiry=LATER_END)
        self.assertFalse(self.claim("a"))
        self.assertEqual(self.nonces.count(), 2)

    def test_07_reopen_at_capacity_rejects_new_claim_without_reset(self):
        self.fill()
        self.nonces = PersistentNonceRegistry(self.db)
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("c")
        self.assertFalse(self.claim("b"))
        self.assertEqual(self.nonces.count(), 2)

    def test_08_failed_capacity_claim_does_not_leave_db_write_lock(self):
        self.fill()
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("c")
        self.assertFalse(self.claim("a"))
        self.assertEqual(self.nonces.count(), 2)

    def test_09_concurrent_distinct_claims_never_exceed_capacity(self):
        def request(i):
            try:
                return ("ok", self.claim(f"concurrent-{i}"))
            except RuntimeError as exc:
                self.assertIn("capacity", str(exc))
                return ("capacity", False)
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(request, range(8)))
        self.assertEqual(sum(tag == "ok" for tag,_ in outcomes), 2)
        self.assertEqual(sum(tag == "capacity" for tag,_ in outcomes), 6)
        self.assertEqual(self.nonces.count(), 2)

    def test_10_refuse_when_existing_db_already_above_cap_no_prune(self):
        self.fill()
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO nonce_claims(scope,nonce,expires_at,expires_at_us,created_at)"
                    " VALUES(?,?,?,?,?)", ("owner.test","c",END,1,NOW)
                )
        self.assertEqual(self.nonces.count(),3)
        with self.assertRaisesRegex(RuntimeError, "capacity"):
            self.claim("d")
        self.assertFalse(self.claim("c"))
        self.assertEqual(self.nonces.count(),3)

    def test_11_invalid_expiry_does_not_consume_capacity(self):
        self.assertFalse(self.claim("expired",expiry=NOW))
        self.assertEqual(self.nonces.count(),0)

    def test_12_invalid_date_fails_without_modifying_tombstones(self):
        self.assertTrue(self.claim("a"))
        with self.assertRaises(ValueError):
            self.claim("b", now="not-rfc3339")
        self.assertEqual(self.nonces.count(),1)

    def test_13_policy_does_not_create_an_external_trust_root(self):
        self.fill()
        self.assertFalse(hasattr(self.nonces, "verify_independent_witness"))
        self.assertFalse(hasattr(self.nonces, "authorize_worker"))
        self.assertFalse(hasattr(self.nonces, "authenticate_owner"))

    def test_14_owner_verification_does_not_turn_capacity_failure_into_ready(self):
        import test_atlasquant_aion_v224_owner_signature_ceremony as v224
        secret, roots = v224.owner_keypair()
        evidence, built = v224.request_for(roots)
        self.fill()
        result = v224.verify(
            built["request"], v224.sign(secret, built["request"]),
            roots, self.nonces, e=evidence,
        )
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE", result["blockers"])
        self.assertIs(result["owner_decision_ready"], False)
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["worker_armed"], False)
        self.assertEqual(self.nonces.count(), 2)

    def test_15_claim_valid_before_cap_and_same_nonce_later_denied(self):
        self.assertTrue(self.claim("one"))
        self.assertFalse(self.claim("one"))
        self.assertTrue(self.claim("two"))
        self.assertFalse(self.claim("one"))
        self.assertEqual(self.nonces.count(),2)

    def test_16_no_caller_parameter_to_silently_raise_safety_cap(self):
        self.assertFalse(hasattr(self.nonces, "set_capacity_without_approval"))
        self.assertEqual(nonce_mod.SCHEMA_VERSION,2)


    def install_synthetic_write_fault(self):
        # Abort only the disposable fixture's INSERT. This is an IntegrityError,
        # but emphatically NOT a UNIQUE(scope,nonce) replay event.
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute(
                    "CREATE TRIGGER synthetic_write_fault BEFORE INSERT "
                    "ON nonce_claims BEGIN "
                    "SELECT RAISE(ABORT,'SIMULATED_STORAGE_WRITE_FAILURE'); END"
                )

    def clear_synthetic_write_fault(self):
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute("DROP TRIGGER synthetic_write_fault")

    def test_17_nonunique_storage_integrity_failure_must_not_look_like_replay(self):
        self.install_synthetic_write_fault()
        with self.assertRaisesRegex((sqlite3.IntegrityError,RuntimeError),
                                    "SIMULATED_STORAGE_WRITE_FAILURE|unauthorized trigger"):
            self.claim("new-never-consumed")
        self.assertEqual(self.nonces.count(),0)

    def test_18_real_owner_reports_storage_fault_not_nonce_replay(self):
        import test_atlasquant_aion_v224_owner_signature_ceremony as v224
        secret,roots=v224.owner_keypair()
        evidence,built=v224.request_for(roots)
        self.install_synthetic_write_fault()
        r=v224.verify(
            built["request"],v224.sign(secret,built["request"]),
            roots,self.nonces,e=evidence,
        )
        self.assertEqual(r["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE",r["blockers"])
        self.assertNotIn("OWNER_SIGNATURE_NONCE_REPLAYED",r["blockers"])
        self.assertFalse(r["execution_allowed"])
        self.assertFalse(r["worker_armed"])
        self.assertEqual(self.nonces.count(),0)

    def test_19_clearing_synthetic_fault_allows_next_safe_claim(self):
        self.install_synthetic_write_fault()
        with self.assertRaisesRegex((sqlite3.IntegrityError,RuntimeError),
                                    "SIMULATED_STORAGE_WRITE_FAILURE|unauthorized trigger"):
            self.claim("faulted")
        self.clear_synthetic_write_fault()
        self.assertTrue(self.claim("faulted"))
        self.assertFalse(self.claim("faulted"))
        self.assertEqual(self.nonces.count(),1)

    def test_20_missing_claim_table_fails_closed_without_self_recreating(self):
        with closing(sqlite3.connect(self.db)) as conn:
            with conn:
                conn.execute("DROP TABLE nonce_claims")
        with self.assertRaises(sqlite3.DatabaseError):
            self.claim("lost-table")
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertIsNone(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='nonce_claims'"
            ).fetchone())


if __name__=="__main__":
    unittest.main()
