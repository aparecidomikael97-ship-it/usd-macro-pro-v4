"""Offline adversarial contract tests: custody durability versus rollback domains.

These tests DO NOT test deployed Cloudflare Durable Objects, out-of-band key
custody, signed receipts, or first-effect authority. A local SQLite model
can be reset by a host admin; even perfect CAS cannot prove independent trust.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from atlasquant_aion_p0_h0_custody_two_domain_model_lab import (
    initialize_model_fixture, reserve_first_attempt_model as reserve,
    compare_boot_highwater_model as compare,
)

SCOPE = "a" * 64
FOREIGN_SCOPE = "b" * 64
DIGEST1 = hashlib.sha256(b"synthetic-intent-1").hexdigest()
DIGEST2 = hashlib.sha256(b"synthetic-intent-2").hexdigest()
N1 = "fixture_nonce_number_one_123456789"
N2 = "fixture_nonce_number_two_123456789"
N3 = "fixture_nonce_number_three_123456789"
FAKE_FLAGS = (
    "independent_custodian_enrolled", "custodian_identity_authenticated",
    "custodian_signature_verified", "custody_is_outside_executor",
    "external_highwater_verified", "rollback_ruled_out",
    "first_effect_allowed", "worker_arming_allowed",
    "automatic_retry_allowed", "producer_effect_authenticated",
    "external_action_executed",
)


class P0TwoDomainCustodyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p0-custody-two-domains-")
        self.addCleanup(self.temp.cleanup)
        self.custody = Path(self.temp.name) / "simulated_custody.sqlite3"
        self.local = Path(self.temp.name) / "simulated_executor.sqlite3"
        initialize_model_fixture(self.custody, SCOPE)

    def check(self, value, reason=None):
        self.assertEqual(value["state"], "BLOCKED")
        self.assertTrue(value["simulation_only"])
        for name in FAKE_FLAGS:
            self.assertIs(value[name], False, name)
        if reason is not None:
            self.assertEqual(value["reason"], reason)
        self.assertNotEqual(value["state"], "READY")
        self.assertIs(value["first_effect_allowed"], False)
        self.assertIs(value["automatic_retry_allowed"], False)
        return value

    def reserve(self, *, intent="synthetic-intent-0001", nonce=N1,
                digest=DIGEST1, sequence=0, epoch=1, claim=None):
        return self.check(reserve(
            self.custody, scope=SCOPE, intent=intent, nonce=nonce,
            intent_digest=digest, expected_sequence=sequence, epoch=epoch,
            _caller_verified_claim=claim,
        ))

    def head(self):
        with closing(sqlite3.connect(self.custody)) as db:
            return db.execute(
                "SELECT sequence,digest FROM witness_head WHERE scope=?", (SCOPE,)
            ).fetchone()

    def count_attempts(self):
        with closing(sqlite3.connect(self.custody)) as db:
            return db.execute("SELECT count(*) FROM intent_reservations").fetchone()[0]

    def local_init(self):
        with closing(sqlite3.connect(self.local)) as db:
            db.execute("CREATE TABLE executor_cursor (scope TEXT PRIMARY KEY, seq INTEGER)")
            db.execute("INSERT INTO executor_cursor VALUES (?,0)", (SCOPE,))
            db.commit()

    def local_sequence(self):
        with closing(sqlite3.connect(self.local)) as db:
            return db.execute("SELECT seq FROM executor_cursor WHERE scope=?", (SCOPE,)).fetchone()[0]

    def local_seq(self, value):
        with closing(sqlite3.connect(self.local)) as db:
            db.execute("UPDATE executor_cursor SET seq=? WHERE scope=?", (value, SCOPE))
            db.commit()

    @staticmethod
    def backup(src, dst):
        with closing(sqlite3.connect(src)) as a, closing(sqlite3.connect(dst)) as b:
            a.backup(b)

    def test_01_absent_custody_is_not_created_by_reservation(self):
        missing = self.custody.with_name("missing.sqlite3")
        r = reserve(missing, scope=SCOPE, intent="synthetic-intent-0001", nonce=N1,
                    intent_digest=DIGEST1, expected_sequence=0)
        self.check(r, "MODEL_CUSTODY_UNAVAILABLE_OR_CORRUPTED")
        self.assertFalse(missing.exists())

    def test_02_fixture_enrollment_cannot_silently_reset_history(self):
        self.reserve()
        with self.assertRaises(FileExistsError):
            initialize_model_fixture(self.custody, SCOPE)
        self.assertEqual(self.head()[0], 1)

    def test_03_one_model_reservation_is_still_no_authority(self):
        r = self.reserve()
        self.check(r, "MODEL_RESERVED_NOT_AUTHORITY")
        self.assertEqual(r["model_reserved_sequence"], 1)
        self.assertEqual(self.head(), (1, DIGEST1))
        self.assertEqual(self.count_attempts(), 1)

    def test_04_duplicate_intent_with_new_nonce_never_re_reserves(self):
        self.reserve()
        self.check(self.reserve(nonce=N2, sequence=1),
                   "MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT")
        self.assertEqual(self.count_attempts(), 1)

    def test_05_same_nonce_used_for_different_intent_is_replay(self):
        self.reserve()
        self.check(self.reserve(intent="synthetic-intent-0002", digest=DIGEST2,
                                sequence=1), "MODEL_NONCE_REUSED")
        self.assertEqual(self.count_attempts(), 1)

    def test_06_two_threads_competing_for_same_sequence_one_winner_only(self):
        def contender(intent, nonce, digest):
            return reserve(self.custody, scope=SCOPE, intent=intent,
                           nonce=nonce, intent_digest=digest, expected_sequence=0)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(contender, "synthetic-intent-0001", N1, DIGEST1)
            b=pool.submit(contender, "synthetic-intent-0002", N2, DIGEST2)
            outcomes = [a.result(timeout=20), b.result(timeout=20)]
        for result in outcomes:
            self.check(result)
        self.assertEqual(sum(r["reason"] == "MODEL_RESERVED_NOT_AUTHORITY" for r in outcomes),1)
        self.assertEqual(sum(r["reason"] == "MODEL_EXPECTED_HEAD_MISMATCH" for r in outcomes),1)
        self.assertEqual(self.count_attempts(), 1)

    def test_07_same_intent_concurrently_never_reserves_twice(self):
        def contender():
            return self.reserve()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(contender)
            b=pool.submit(contender)
            r=[a.result(timeout=20), b.result(timeout=20)]
        self.assertEqual(sum(x["reason"]=="MODEL_RESERVED_NOT_AUTHORITY" for x in r),1)
        self.assertEqual(sum(x["reason"]=="MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT" for x in r),1)
        self.assertEqual(self.head()[0],1)

    def test_08_stale_expected_head_rejected_without_write(self):
        self.reserve()
        self.check(self.reserve(intent="synthetic-intent-0002",nonce=N2,digest=DIGEST2),
                   "MODEL_EXPECTED_HEAD_MISMATCH")
        self.assertEqual(self.count_attempts(),1)

    def test_09_fresh_sequential_head_accepted_as_simulation_only(self):
        self.reserve()
        self.check(self.reserve(intent="synthetic-intent-0002",nonce=N2,
                                digest=DIGEST2,sequence=1), "MODEL_RESERVED_NOT_AUTHORITY")
        self.assertEqual(self.head(),(2,DIGEST2))
        self.assertEqual(self.count_attempts(),2)

    def test_10_epoch_mismatch_denied_without_write(self):
        self.check(self.reserve(epoch=2), "MODEL_EPOCH_MISMATCH")
        self.assertEqual(self.head()[0], 0)

    def test_11_bool_and_noncanonical_inputs_denied(self):
        cases = [
            dict(sequence=True), dict(sequence=-1), dict(epoch=True),
            dict(epoch=0), dict(nonce="bad"), dict(digest="z"*64),
            dict(intent=""),
        ]
        for item in cases:
            with self.subTest(item=item):
                self.check(self.reserve(**item),"MODEL_INPUT_INVALID")
        self.assertEqual(self.count_attempts(),0)

    def test_12_forged_caller_verified_is_ignored_not_authenticated(self):
        claim={"enrolled":True,"signed":True,"independent":True,"version":999}
        before=deepcopy(claim)
        self.check(self.reserve(claim=claim),"MODEL_RESERVED_NOT_AUTHORITY")
        self.assertEqual(claim,before)
        self.assertFalse(compare(self.custody,scope=SCOPE,local_sequence=1,
                                 _caller_verified_claim=claim)["external_highwater_verified"])

    def test_13_lost_response_after_cas_is_unknown_not_automatic_retry(self):
        # Simulates a transport timeout where the write committed but its
        # result never reached the caller. Do NOT send a new first effect.
        reserve(self.custody,scope=SCOPE,intent="synthetic-intent-0001",nonce=N1,
                intent_digest=DIGEST1,expected_sequence=0)
        self.check(self.reserve(),"MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT")
        self.assertEqual(self.count_attempts(),1)

    def test_14_local_sqlite_rollback_is_suspected_if_model_custody_survives(self):
        self.local_init()
        old=Path(self.temp.name)/"executor_old.sqlite3"
        self.backup(self.local,old)
        self.reserve()
        self.local_seq(1)
        self.assertEqual(self.local_sequence(),1)
        shutil.copyfile(old,self.local)
        self.assertEqual(self.local_sequence(),0)
        self.check(compare(self.custody,scope=SCOPE,local_sequence=self.local_sequence()),
                   "MODEL_LOCAL_ROLLBACK_SUSPECTED")

    def test_15_custody_PITR_rollback_is_suspected_if_executor_survives(self):
        self.local_init()
        old=Path(self.temp.name)/"custody_old.sqlite3"
        self.backup(self.custody,old)
        self.reserve()
        self.local_seq(1)
        shutil.copyfile(old,self.custody)
        self.check(compare(self.custody,scope=SCOPE,local_sequence=self.local_sequence()),
                   "MODEL_CUSTODY_STALE_OR_FORK_SUSPECTED")

    def test_16_both_domains_rolled_back_appear_matching_but_are_NOT_verified(self):
        self.local_init()
        old_l=Path(self.temp.name)/"local_old.sqlite3"
        old_c=Path(self.temp.name)/"custody_old.sqlite3"
        self.backup(self.local,old_l)
        self.backup(self.custody,old_c)
        self.reserve()
        self.local_seq(1)
        shutil.copyfile(old_l,self.local)
        shutil.copyfile(old_c,self.custody)
        self.assertEqual(self.local_sequence(),0)
        self.check(compare(self.custody,scope=SCOPE,local_sequence=0,local_digest="0"*64),
                   "MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF")

    def test_17_matching_sequence_wrong_digest_is_fork_suspected(self):
        self.reserve()
        self.check(compare(self.custody,scope=SCOPE,local_sequence=1,local_digest=DIGEST2),
                   "MODEL_SAME_SEQUENCE_DIGEST_FORK")

    def test_18_missing_or_foreign_scope_cannot_be_used(self):
        self.check(compare(self.custody,scope=FOREIGN_SCOPE,local_sequence=0),
                   "MODEL_CUSTODY_ROW_MISSING_OR_INVALID")
        self.check(compare(self.custody,scope="malformed",local_sequence=0),
                   "MODEL_INPUT_INVALID")
        self.assertEqual(self.head()[0],0)

    def test_19_corrupt_custody_does_not_become_fresh_on_restart(self):
        self.custody.write_bytes(b"CORRUPTED DATA")
        self.check(compare(self.custody,scope=SCOPE,local_sequence=0),
                   "MODEL_CUSTODY_UNAVAILABLE_OR_CORRUPTED")
        self.check(self.reserve(),"MODEL_CUSTODY_UNAVAILABLE_OR_CORRUPTED")

    def test_20_process_reopen_preserves_one_reserved_intent_but_no_authority(self):
        self.reserve()
        self.check(compare(self.custody,scope=SCOPE,local_sequence=1,local_digest=DIGEST1),
                   "MODEL_HEAD_MATCH_ONLY_NO_EXTERNAL_PROOF")
        self.check(self.reserve(), "MODEL_ATTEMPT_ALREADY_RESERVED_UNKNOWN_EFFECT")
        self.assertEqual(self.head()[0],1)


if __name__ == "__main__":
    unittest.main()
