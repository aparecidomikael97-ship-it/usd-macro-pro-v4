"""A190 G19 — isolated recovery DENY state-machine adversarial tests.

IMPORTANT: This is a synthetic *reference oracle*, not an integration with AION.
The witness is an in-process test double, NOT an external trust root. All
observations are local and cannot homologate any P0 or authorize a provider send.
"""
from contextlib import closing
import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest


class Denied(RuntimeError):
    pass


def digest(sequence, semantic_key, phase):
    return hashlib.sha256(
        f"v1|{sequence}|{semantic_key}|{phase}".encode("utf-8")
    ).hexdigest()


class SyntheticWitness:
    """Test-only separate witness: explicitly NOT independent trusted custody."""
    def __init__(self):
        self.records = {}
        self.available = True
        self.authenticated = True

    def publish(self, key, sequence, phase):
        if not self.available or not self.authenticated:
            raise Denied("WITNESS_UNAVAILABLE_OR_UNTRUSTED")
        previous = self.records.get(key)
        if previous and sequence <= previous[0]:
            raise Denied("WITNESS_NONMONOTONIC")
        self.records[key] = (sequence, digest(sequence, key, phase))

    def attest(self, key, sequence, phase):
        if not self.available or not self.authenticated:
            raise Denied("WITNESS_UNAVAILABLE_OR_UNTRUSTED")
        if self.records.get(key) != (sequence, digest(sequence, key, phase)):
            raise Denied("WITNESS_MISMATCH_OR_MISSING")


class RecoveryOracle:
    """Synthetic fail-closed oracle: no networking and no provider-send method."""
    def __init__(self, path, witness):
        self.path = str(path)
        self.witness = witness
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS intents (
                semantic_key TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, phase TEXT NOT NULL
            )""")

    def reserve(self, semantic_key, request_id):
        if not self.witness.available or not self.witness.authenticated:
            raise Denied("WITNESS_UNAVAILABLE_OR_UNTRUSTED")
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT sequence, phase FROM intents WHERE semantic_key=?",
                (semantic_key,),
            ).fetchone()
            if row:
                self.witness.attest(semantic_key, *row)
                raise Denied("SEMANTIC_INTENT_ALREADY_RESERVED_ZERO_AUTO_RESEND")
            # A witness of an earlier reservation cannot be erased by local rollback.
            if semantic_key in self.witness.records:
                raise Denied("WITNESS_HAS_PRIOR_RESERVATION_DENY")
            # Test-only transaction model: no actual provider call follows.
            with db:
                db.execute(
                    "INSERT INTO intents VALUES(?,?,?,?)",
                    (semantic_key, request_id, 1, "RESERVED"),
                )
            self.witness.publish(semantic_key, 1, "RESERVED")
        return "RESERVED_NO_SEND"

    def recover(self, semantic_key):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT sequence, phase FROM intents WHERE semantic_key=?",
                (semantic_key,),
            ).fetchone()
        if row is None:
            raise Denied("MISSING_LOCAL_INTENT_UNCERTAIN_ZERO_AUTO_RESEND")
        self.witness.attest(semantic_key, *row)
        # Even consistent local + synthetic witness evidence is NOT an
        # authenticated provider outcome. Never classify it as safe to resend.
        return "UNCERTAIN_ZERO_AUTO_RESEND"

    def require_authenticated_receipt(self, receipt):
        # Test oracle does not have independent provider public keys.
        raise Denied("NO_INDEPENDENT_PROVIDER_TRUST_ROOT_DENY")

    def require_owner_authorization(self, approval):
        # Test oracle does not have an independent owner identity root.
        raise Denied("NO_INDEPENDENT_OWNER_TRUST_ROOT_DENY")


class G19SyntheticRecoveryDenial(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aion-g19-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite"
        self.witness = SyntheticWitness()
        self.oracle = RecoveryOracle(self.path, self.witness)

    def reserve(self, key="semantic:invoice:42", request="req:1"):
        self.assertEqual(self.oracle.reserve(key, request), "RESERVED_NO_SEND")

    def assert_deny(self, operation, fragment):
        with self.assertRaisesRegex(Denied, fragment):
            operation()

    def test_01_first_reservation_does_not_send(self):
        self.reserve()
        self.assertEqual(self.oracle.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")

    def test_02_distinct_request_id_same_semantic_key_denied(self):
        self.reserve()
        self.assert_deny(
            lambda: self.oracle.reserve("semantic:invoice:42", "req:2"),
            "SEMANTIC_INTENT_ALREADY_RESERVED",
        )

    def test_03_deleted_local_journal_cannot_reopen_witnessed_key(self):
        self.reserve()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM intents")
        self.assert_deny(lambda: self.oracle.reserve("semantic:invoice:42", "req:2"),
                         "WITNESS_HAS_PRIOR_RESERVATION")
        self.assert_deny(lambda: self.oracle.recover("semantic:invoice:42"),
                         "MISSING_LOCAL_INTENT")

    def test_04_rollback_to_empty_snapshot_denied(self):
        snapshot = Path(self.temp.name) / "old.sqlite"
        shutil.copyfile(self.path, snapshot)
        self.reserve()
        shutil.copyfile(snapshot, self.path)
        self.assert_deny(lambda: self.oracle.reserve("semantic:invoice:42", "req:3"),
                         "WITNESS_HAS_PRIOR_RESERVATION")

    def test_05_same_marker_clone_with_stale_sequence_denied(self):
        self.reserve()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE intents SET sequence=0 WHERE semantic_key=?",
                       ("semantic:invoice:42",))
        self.assert_deny(lambda: self.oracle.recover("semantic:invoice:42"),
                         "WITNESS_MISMATCH")

    def test_06_closed_file_replacement_preserves_uncertainty(self):
        self.reserve()
        clone = Path(self.temp.name) / "clone.sqlite"
        shutil.copyfile(self.path, clone)
        self.path.unlink()
        shutil.copyfile(clone, self.path)
        self.assertEqual(self.oracle.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")

    def test_07_missing_witness_denies_even_matching_local_history(self):
        self.reserve()
        self.witness.available = False
        self.assert_deny(lambda: self.oracle.recover("semantic:invoice:42"),
                         "WITNESS_UNAVAILABLE")
        self.assert_deny(lambda: self.oracle.reserve("semantic:invoice:99", "req:9"),
                         "WITNESS_UNAVAILABLE")

    def test_08_untrusted_witness_denies(self):
        self.reserve()
        self.witness.authenticated = False
        self.assert_deny(lambda: self.oracle.recover("semantic:invoice:42"),
                         "WITNESS_UNAVAILABLE_OR_UNTRUSTED")

    def test_09_witness_replay_denies(self):
        self.reserve()
        self.witness.records["semantic:invoice:42"] = (0, digest(0, "semantic:invoice:42", "RESERVED"))
        self.assert_deny(lambda: self.oracle.recover("semantic:invoice:42"),
                         "WITNESS_MISMATCH")

    def test_10_provider_timeout_remains_uncertain(self):
        self.reserve()
        self.assertEqual(self.oracle.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")

    def test_11_post_effect_pre_receipt_remains_uncertain(self):
        self.reserve()
        self.assertEqual(self.oracle.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")
        self.assert_deny(lambda: self.oracle.require_authenticated_receipt({"signed": True}),
                         "NO_INDEPENDENT_PROVIDER_TRUST_ROOT")

    def test_12_forged_owner_approval_denied(self):
        self.assert_deny(lambda: self.oracle.require_owner_authorization({"approved": True}),
                         "NO_INDEPENDENT_OWNER_TRUST_ROOT")

    def test_13_reopen_after_restart_cannot_resend(self):
        self.reserve()
        restarted = RecoveryOracle(self.path, self.witness)
        self.assertEqual(restarted.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")
        self.assert_deny(lambda: restarted.reserve("semantic:invoice:42", "new-req"),
                         "SEMANTIC_INTENT_ALREADY_RESERVED")

    def test_14_concurrent_duplicate_semantic_key_at_most_one_reservation(self):
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def attempt(i):
            barrier.wait()
            try:
                result = self.oracle.reserve("semantic:invoice:42", f"req:{i}")
            except (Denied, sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
                result = f"DENIED:{type(exc).__name__}"
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "SYNTHETIC_CONCURRENCY_DEADLOCK")
        self.assertEqual(len(outcomes), 2)
        self.assertLessEqual(outcomes.count("RESERVED_NO_SEND"), 1)
        self.assertTrue(all(
            item == "RESERVED_NO_SEND" or item.startswith("DENIED:")
            for item in outcomes
        ))
        self.assertEqual(self.oracle.recover("semantic:invoice:42"),
                         "UNCERTAIN_ZERO_AUTO_RESEND")


if __name__ == "__main__":
    unittest.main()
