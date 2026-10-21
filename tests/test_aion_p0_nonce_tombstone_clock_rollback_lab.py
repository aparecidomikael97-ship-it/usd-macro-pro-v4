"""AION P0 LAB: prove nonce TTL pruning creates local replay on clock rollback.

Expected RED on prior nonce registry: a future-time claim deletes old
tombstones; a later earlier-time claim treats a used nonce as unseen.
Tests are synthetic-only, and do not establish independent clock, owner,
issuer or H0 antirollback trust. No external effects / worker.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

import test_atlasquant_aion_v224_owner_signature_ceremony as legacy
from atlasquant_aion_nonce_registry import PersistentNonceRegistry

OLD_NOW = "2026-10-04T20:00:00Z"
OLD_EXP = "2026-10-04T20:02:00Z"
LATER_NOW = "2026-10-04T20:03:00Z"
LATER_EXP = "2026-10-04T20:04:00Z"


class NonceRetentionClockRollbackLAB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aion-p0-nonce-clock-lab-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic-nonces.sqlite3"
        self.nonces = PersistentNonceRegistry(self.path)

    def claim(self, nonce, *, now=OLD_NOW, expiry=OLD_EXP, scope="owner.test"):
        return self.nonces.claim(scope=scope, nonce=nonce, now_ts=now,
                                 expires_at=expiry)

    def advance(self):
        self.assertTrue(self.claim("a-different-nonce",
                                   now=LATER_NOW, expiry=LATER_EXP))

    def test_01_initial_unique_claim_remains_valid(self):
        self.assertTrue(self.claim("signature-nonce-01"))
        self.assertEqual(self.nonces.count(), 1)

    def test_02_same_nonce_twice_with_stable_clock_is_denied(self):
        self.assertTrue(self.claim("signature-nonce-02"))
        self.assertFalse(self.claim("signature-nonce-02"))
        self.assertEqual(self.nonces.count(), 1)

    def test_03_advancing_clock_must_not_erase_consumed_nonce(self):
        self.assertTrue(self.claim("signature-nonce-03"))
        self.advance()
        self.assertTrue(self.nonces.contains(scope="owner.test",
                                             nonce="signature-nonce-03"))
        self.assertEqual(self.nonces.count(), 2)

    def test_04_clock_rollback_must_not_reenable_original_nonce(self):
        self.assertTrue(self.claim("signature-nonce-04"))
        self.advance()
        self.assertFalse(self.claim("signature-nonce-04"))
        self.assertEqual(self.nonces.count(), 2)

    def test_05_expired_tombstone_cannot_be_reissued_with_a_later_expiry(self):
        self.assertTrue(self.claim("signature-nonce-05"))
        self.advance()
        self.assertFalse(self.claim(
            "signature-nonce-05", now=LATER_NOW,
            expiry="2026-10-04T20:09:00Z",
        ))
        self.assertEqual(self.nonces.count(), 2)

    def test_06_consumed_owner_signature_cannot_be_reverified_after_clock_rewind(self):
        key, roots = legacy.owner_keypair()  # Ephemeral fixture, NOT actual HUMAN_OWNER
        evidence, built = legacy.request_for(roots)
        self.assertEqual(built["state"], "READY_FOR_EXTERNAL_OWNER_SIGNATURE")
        signed = legacy.sign(key, built["request"])
        result = legacy.verify(built["request"], signed, roots, self.nonces, e=evidence)
        self.assertEqual(result["state"], "READY_FOR_EXPLICIT_OWNER_DECISION")
        self.advance()  # Future-time claim in another scope previously purged owner nonce.
        replay = legacy.verify(
            built["request"], signed, roots, self.nonces, e=evidence,
        )
        self.assertEqual(replay["state"], "BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REPLAYED", replay["blockers"])
        self.assertFalse(replay["execution_allowed"])
        self.assertFalse(replay["worker_armed"])

    def test_07_new_distinct_nonce_after_clock_advance_is_still_accepted(self):
        self.assertTrue(self.claim("signature-nonce-07"))
        self.assertTrue(self.claim(
            "another-after-clock-advance", now=LATER_NOW, expiry=LATER_EXP,
        ))
        self.assertEqual(self.nonces.count(), 2)

    def test_08_same_nonce_other_scope_remains_distinct(self):
        self.assertTrue(self.claim("scope-nonce-08", scope="owner.one"))
        self.assertTrue(self.claim("scope-nonce-08", scope="owner.two"))
        self.assertEqual(self.nonces.count(), 2)

    def test_09_zero_length_validity_rejected_without_consumption(self):
        self.assertFalse(self.claim("nonce-expired-at-now",
                                    now=OLD_NOW, expiry=OLD_NOW))
        self.assertEqual(self.nonces.count(), 0)

    def test_10_expired_claim_audit_metadata_is_preserved(self):
        self.assertTrue(self.claim("signature-nonce-10"))
        old = self.nonces.read_claim(scope="owner.test", nonce="signature-nonce-10")
        self.assertEqual(old["expires_at"], OLD_EXP)
        self.advance()
        self.assertEqual(
            self.nonces.read_claim(scope="owner.test", nonce="signature-nonce-10"),
            old,
        )

    def test_11_restarted_registry_preserves_tombstone_after_time_advance(self):
        self.assertTrue(self.claim("signature-nonce-11"))
        self.advance()
        reopened = PersistentNonceRegistry(self.path)
        self.assertTrue(reopened.contains(scope="owner.test", nonce="signature-nonce-11"))
        self.assertFalse(reopened.claim(scope="owner.test", nonce="signature-nonce-11",
                                         now_ts=OLD_NOW, expires_at=OLD_EXP))

    def test_12_eight_future_time_claims_never_prune_historic_nonces(self):
        self.assertTrue(self.claim("signature-nonce-12"))
        def future(i):
            return self.claim(f"future-{i}", now=LATER_NOW, expiry=LATER_EXP)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(future, range(8)))
        self.assertEqual(results, [True]*8)
        self.assertEqual(self.nonces.count(), 9)
        self.assertFalse(self.claim("signature-nonce-12"))

    def test_13_invalid_date_is_denied_without_rewriting_history(self):
        self.assertTrue(self.claim("signature-nonce-13"))
        with self.assertRaises(ValueError):
            self.claim("bad-nonce", now="not-a-timestamp")
        self.assertEqual(self.nonces.count(), 1)

    def test_14_deliberate_full_restore_is_still_an_open_p0_not_solved_here(self):
        # No local retention rule can attest history deleted by full rollback.
        # This test only records that local code is not external witness.
        self.assertFalse(hasattr(self.nonces, "verify_independent_witness"))
        self.assertFalse(hasattr(self.nonces, "authenticate_external_owner"))
        self.assertFalse(hasattr(self.nonces, "enable_worker"))


if __name__ == "__main__":
    unittest.main()
