"""P0 LAB — SQLite trigger and path-swap replay characterization.

These tests deliberately change LOCAL disposable SQLite schema or replace
a file path. Local attackers able to rewrite entire SQLite DB are not
defeated by same-host guards: independent H0 witness remains OPEN.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
import test_atlasquant_aion_v224_owner_signature_ceremony as owner

NOW="2026-10-20T19:00:00Z"
EXP="2026-10-20T20:00:00Z"


class NonceSchemaTriggersAndFileSwapLAB(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aion-p0-nonce-schema-swap-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.a=self.root/"owner_nonce_a.sqlite3"
        self.b=self.root/"owner_nonce_b.sqlite3"
        self.ra=PersistentNonceRegistry(self.a)

    def claim(self,r,nonce):
        return r.claim(scope="owner.lab",nonce=nonce,
                       expires_at=EXP,now_ts=NOW)

    def sql(self,db_path,sql):
        with closing(sqlite3.connect(db_path)) as c:
            with c:
                c.execute(sql)

    def raws(self,db_path):
        with closing(sqlite3.connect(db_path)) as c:
            return [r[0] for r in c.execute(
                "SELECT nonce FROM nonce_claims ORDER BY nonce"
            ).fetchall()]

    def trigger_delete_prior(self):
        self.sql(
            self.a,
            "CREATE TRIGGER delete_old_claims AFTER INSERT ON nonce_claims "
            "BEGIN DELETE FROM nonce_claims "
            "WHERE scope=NEW.scope AND nonce!='new-claim'; END"
        )

    def test_01_nominal_claim_preserves_existing_history(self):
        self.assertTrue(self.claim(self.ra,"old-claim"))
        self.assertTrue(self.claim(self.ra,"new-claim"))
        self.assertEqual(self.raws(self.a),["new-claim","old-claim"])
        self.assertFalse(self.claim(self.ra,"old-claim"))

    def test_02_tampered_trigger_cannot_delete_old_tombstone_during_next_claim(self):
        self.assertTrue(self.claim(self.ra,"old-claim"))
        self.trigger_delete_prior()
        with self.assertRaisesRegex((RuntimeError,ValueError,sqlite3.Error),
                                    "trigger|schema|integrity|modified"):
            self.claim(self.ra,"new-claim")
        self.assertEqual(self.raws(self.a),["old-claim"])
        self.assertFalse(self.claim(self.ra,"old-claim"))

    def test_03_owner_ceremony_denies_claim_when_schema_has_unexpected_trigger(self):
        self.trigger_delete_prior()
        key,roots=owner.owner_keypair()
        evidence,built=owner.request_for(roots)
        result=owner.verify(
            built["request"],owner.sign(key,built["request"]),
            roots,self.ra,e=evidence
        )
        self.assertEqual(result["state"],"BLOCKED")
        self.assertIn("OWNER_SIGNATURE_NONCE_REGISTRY_FAILURE",result["blockers"])
        self.assertFalse(result["worker_armed"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(self.raws(self.a),[])

    def test_04_valid_v2_with_new_trigger_denied_at_subsequent_startup(self):
        self.trigger_delete_prior()
        with self.assertRaisesRegex((RuntimeError,ValueError),"trigger|schema|integrity"):
            PersistentNonceRegistry(self.a)
        self.assertEqual(self.raws(self.a),[])

    def test_05_replacing_path_with_valid_untouched_wal_db_denies_old_object(self):
        self.assertTrue(self.claim(self.ra,"prior-consumed"))
        rb=PersistentNonceRegistry(self.b)
        self.assertEqual(rb.schema_version(),2)
        self.assertEqual(self.raws(self.b),[])
        os.replace(self.b,self.a)
        with self.assertRaisesRegex((RuntimeError,ValueError),"file|identity|path|replaced"):
            self.claim(self.ra,"prior-consumed")
        self.assertEqual(self.raws(self.a),[])

    def test_06_replaced_path_denies_read_and_count(self):
        self.assertTrue(self.claim(self.ra,"prior-consumed"))
        PersistentNonceRegistry(self.b)
        os.replace(self.b,self.a)
        with self.assertRaisesRegex((RuntimeError,ValueError),"file|identity|path|replaced"):
            self.ra.contains(scope="owner.lab",nonce="prior-consumed")
        with self.assertRaisesRegex((RuntimeError,ValueError),"file|identity|path|replaced"):
            self.ra.count()

    def test_07_swapping_to_symlink_of_valid_other_db_denies(self):
        self.assertTrue(self.claim(self.ra,"prior-consumed"))
        rb=PersistentNonceRegistry(self.b)
        self.assertEqual(rb.count(),0)
        self.a.unlink()
        try:
            self.a.symlink_to(self.b)
        except (OSError,NotImplementedError):
            self.skipTest("symlink creation not permitted by this Windows host")
        with self.assertRaisesRegex((RuntimeError,ValueError),"file|identity|path|symlink"):
            self.claim(self.ra,"prior-consumed")
        self.assertEqual(self.raws(self.b),[])

    def test_08_unaltered_db_inode_survives_reopen_and_40_claims(self):
        for n in range(40):
            self.assertTrue(self.claim(self.ra,f"claim-{n:03d}"))
        self.assertEqual(self.ra.count(),40)
        self.assertFalse(self.claim(self.ra,"claim-000"))
        self.assertEqual(PersistentNonceRegistry(self.a).count(),40)

    def test_09_read_methods_deny_after_schema_trigger_injection(self):
        self.assertTrue(self.claim(self.ra,"safe-prior"))
        self.trigger_delete_prior()
        with self.assertRaisesRegex((RuntimeError,ValueError),"trigger|schema|integrity"):
            self.ra.contains(scope="owner.lab",nonce="safe-prior")
        with self.assertRaisesRegex((RuntimeError,ValueError),"trigger|schema|integrity"):
            self.ra.read_claim(scope="owner.lab",nonce="safe-prior")

    def test_10_no_local_inode_guard_is_external_rollback_witness(self):
        self.assertFalse(hasattr(self.ra,"verify_independent_highwater"))
        self.assertFalse(hasattr(self.ra,"issuer_enrolled"))
        self.assertFalse(hasattr(self.ra,"enable_worker"))


if __name__=="__main__":
    unittest.main()
