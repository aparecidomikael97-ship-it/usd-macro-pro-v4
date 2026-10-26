"""G106 RED-first: reject custody mutation *during* a valid post proof.

G104 checks the local custody before contacting its synthetic attestor, but
does not reread local custody before allowing a provider send. These tests
force an actual local SQLite file rollback, removal, a second reservation, or
a lost final read while a valid out-of-band post-commit signature is returned.

All authority and receipts are IN-PROCESS synthetic; this is not external
custody certification, same-inode SQLite VFS proof or SEND authorization.
"""
from copy import deepcopy
from labs.a190.test_g102_pinned_external_attestation_admission_lab import (
    G102PinnedExternalAdmission,
)


class G106CustodyDriftDuringPostProof(G102PinnedExternalAdmission):
    def test_11_rollback_during_signed_post_reply_denies_dispatch(self):
        original = self.enroll_fixture()

        def post_then_rebootstrap(challenge, request):
            valid = self.proof_after(challenge, request)
            # All A181 SQLite connections are closed before unlink. A local
            # actor may erase and re-enroll the host-owned synthetic custody.
            self.custody_db.unlink()
            self.custody = self.bootstrap()
            return valid

        # Dynamic callback reads the *current* locally enrolled file. The
        # original bound .snapshot method would still read the same pathname.
        guard = self.make_guard(
            original, post_probe=post_then_rebootstrap,
            checkpoint=lambda: self.custody.snapshot(),
        )
        self.assertIs(
            guard(original), False,
            "G106_FAIL: valid post attestation accepted despite local rollback",
        )
        self.assertEqual(self.custody.snapshot()["count"], 0)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G106_ROLLBACK_DURING_POST=NO_SEND")

    def test_12_deleted_local_custody_after_post_signature_denies(self):
        original = self.enroll_fixture()

        def post_then_delete(challenge, request):
            valid = self.proof_after(challenge, request)
            self.custody_db.unlink()
            return valid

        guard = self.make_guard(original, post_probe=post_then_delete)
        self.assertIs(guard(original), False)
        self.assertFalse(self.custody_db.exists())
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G106_LOCAL_CUSTODY_MISSING_AT_RELEASE=DENIED")

    def test_13_second_unattested_local_reservation_during_post_denies(self):
        original = self.enroll_fixture()

        def post_then_append_local(challenge, request):
            valid = self.proof_after(challenge, request)
            previous = self.remote_reservation
            second = {
                field: previous[field] for field in (
                    "idempotency_key", "effect_digest", "decision_sha256",
                    "owner_id", "tenant_id", "workspace_id",
                )
            }
            second["idempotency_key"] = "f" * 64
            second["effect_digest"] = "e" * 64
            assert second["effect_digest"] != previous["effect_digest"]
            self.custody.reserve("a" * 64, second)
            return valid

        guard = self.make_guard(original, post_probe=post_then_append_local)
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 2)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G106_EXTRA_LOCAL_RESERVATION_DURING_POST=DENIED")

    def test_14_final_checkpoint_unavailable_after_valid_post_denies(self):
        original = self.enroll_fixture()
        state = {"closed": False}

        def checked_snapshot():
            if state["closed"]:
                raise TimeoutError("G106_SYNTHETIC_FINAL_CHECKPOINT_UNAVAILABLE")
            return self.custody.snapshot()

        def reply_then_stop_local_read(challenge, request):
            valid = self.proof_after(challenge, request)
            state["closed"] = True
            return valid

        guard = self.make_guard(
            original, checkpoint=checked_snapshot,
            post_probe=reply_then_stop_local_read,
        )
        self.assertIs(guard(original), False)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 1)
        print("G106_FINAL_CUSTODY_READ_FAILURE=DENIED_SPENT")

    def test_15_intact_post_proof_still_accepts_single_synthetic_attempt(self):
        original = self.enroll_fixture()
        read_calls = []

        def tracked_checkpoint():
            value = self.custody.snapshot()
            read_calls.append(deepcopy(value))
            return value

        guard = self.make_guard(original, checkpoint=tracked_checkpoint)
        self.assertIs(guard(original), True)
        self.assertEqual(self.custody.snapshot()["count"], 1)
        self.assertEqual(self.remote_sequence["count"], 1)
        # Must actually recheck *after* the post-proof callback.
        self.assertGreaterEqual(len(read_calls), 4)
        self.assertEqual(read_calls[-1], {"high_water": 1, "count": 1})
        print("G106_STABLE_CUSTODY=FINAL_RECHECK_GREEN")
