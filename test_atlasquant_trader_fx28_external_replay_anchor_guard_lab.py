"""Only disposable local SQLite & synthetic fresh anchor signatures.

This is NOT an external service and contains no real secrets or prices.
A valid MAC only proves synthetic key possession, never live provenance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from atlasquant_trader_fx28_external_replay_anchor_guard_lab import (
    synthesize_fx28_anchor_checkpoint_for_offline_tests_lab as sign_anchor,
    inspect_fx28_sqlite_vs_external_anchor_lab as inspect,
)
from atlasquant_trader_fx28_durable_replay_floor_sqlite_lab import (
    TABLE, bootstrap_fx28_replay_floor_sqlite_lab as bootstrap,
    receive_fx28_signed_status_once_sqlite_lab as accept,
)
from atlasquant_trader_fx28_signed_status_envelope_lab import (
    sign_fx28_sanitized_radar_status_lab as sign_status,
)
from test_atlasquant_trader_fx28_signed_status_envelope_lab import (
    TEST_KEY, payload,
)

UTC=timezone.utc
ASOF=datetime(2026,11,16,0,44,tzinfo=UTC)
ANCHOR_TEST_KEY=b"NOT-A-REAL-ANCHOR-KEY-ONLY-FOR-OFFLINE-TESTS-1"
NONCE="ab"*16
MATCHED="LAB_FX28_EXTERNAL_ANCHOR_HMAC_MATCH_LOCAL_CLAIM_ONLY_NO_GO"


class ExternalReplayAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="AQ_FX28_ANCHOR_MOCK_ONLY_")
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"local.sqlite3"
        self.conn=self.open()
        self.addCleanup(self.conn.close)
        self.assertTrue(bootstrap(
            conn=self.conn,explicitly_authorized_new_empty_database=True))

    def open(self,path=None):
        c=sqlite3.connect(str(path or self.db),isolation_level=None,timeout=0.1)
        c.execute("PRAGMA synchronous=FULL")
        return c

    def receipt(self,seq):
        raw=sign_status(report=payload(),secret_key=TEST_KEY,
            sequence=seq,nonce_hex=f"{seq:032x}",issued_at_utc=ASOF)
        self.assertIsNotNone(raw)
        return raw

    def advance(self,seq):
        result=accept(conn=self.conn,raw_envelope=self.receipt(seq),
            secret_key=TEST_KEY,received_at_utc=ASOF+timedelta(seconds=1))
        self.assertTrue(result["db_transaction_committed"])
        self.assertTrue(result["sanitized_report"])
        return self.floor()

    def floor(self,conn=None):
        con=conn or self.conn
        return con.execute(
            f"SELECT highest_accepted_sequence,last_envelope_sha256 "
            f"FROM {TABLE} WHERE id=1").fetchone()

    def anchor(self,*,seq=None,digest=None,nonce=NONCE,issued=ASOF,key=ANCHOR_TEST_KEY):
        if seq is None:
            seq,digest=self.floor()
        return sign_anchor(sequence=seq,last_envelope_sha256=digest,
                           challenge_nonce=nonce,issued_at_utc=issued,
                           separate_test_anchor_key=key)

    def check(self,raw=None,*,nonce=NONCE,now=None,key=ANCHOR_TEST_KEY,conn=None):
        return inspect(conn=conn or self.conn,
            raw_anchor_checkpoint=self.anchor() if raw is None else raw,
            separate_anchor_verification_key=key,
            expected_fresh_challenge_nonce=nonce,
            checked_at_utc=now or ASOF+timedelta(seconds=2))

    def safe(self,result):
        for flag in (
            "external_anchor_service_independently_authenticated",
            "external_anchor_monotonic_storage_implemented_here",
            "anchor_verification_key_provisioned_here",
            "clock_independently_attested","trusted_restoration_fencing_implemented",
            "rollback_protection_deployed","trade_authorized","score_unlocked",
        ):
            self.assertFalse(result[flag],flag)
        self.assertEqual((result["mt5_calls"],result["http_requests"],
                          result["local_database_writes"],
                          result["external_anchor_writes"]),(0,0,0,0))
        self.assertIsNone(result["sanitized_report"])
        self.assertEqual(result["operational_bias"],"AGUARDAR")

    def test_01_bootstrap_zero_and_nil_digest_matching_only_no_go(self):
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],MATCHED)
        self.assertTrue(r["anchor_hmac_valid"])
        self.assertTrue(r["local_and_external_high_water_match"])
        self.assertEqual(r["local_sequence_read_only"],0)
        self.assertEqual(self.floor(),(0,None))

    def test_02_matching_after_real_test_receipt_keeps_no_go(self):
        self.advance(1)
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],MATCHED)
        self.assertEqual(r["local_sequence_read_only"],1)
        self.assertEqual(r["anchor_sequence_claim_only"],1)

    def test_03_local_restored_backup_behind_external_counter_detected(self):
        self.advance(1)
        old=Path(self.temp.name)/"restored_backup.sqlite3"
        old_connection=self.open(old)
        self.conn.backup(old_connection)
        old_connection.close()
        self.advance(2)
        anchor_now=self.anchor()
        restored=self.open(old)
        self.addCleanup(restored.close)
        r=self.check(raw=anchor_now,conn=restored)
        self.safe(r)
        self.assertTrue(r["local_database_rollback_suspected"])
        self.assertEqual(r["reason"],
            "LOCAL_DB_BEHIND_EXTERNAL_ANCHOR_POSSIBLE_RESTORE")
        self.assertEqual(r["anchor_sequence_claim_only"],2)
        self.assertEqual(r["local_sequence_read_only"],1)

    def test_04_external_anchor_stale_or_restored_detected(self):
        self.advance(1)
        stale=self.anchor()
        self.advance(2)
        r=self.check(raw=stale)
        self.safe(r)
        self.assertTrue(r["external_anchor_stale_or_rollback_suspected"])
        self.assertEqual(r["reason"],
            "EXTERNAL_ANCHOR_BEHIND_LOCAL_DB_POSSIBLE_RESTORE")

    def test_05_same_sequence_different_digest_conflict_detected(self):
        self.advance(1)
        false_digest="f"*64
        self.assertNotEqual(self.floor()[1],false_digest)
        forged_claim=self.anchor(seq=1,digest=false_digest)
        r=self.check(raw=forged_claim)
        self.safe(r)
        self.assertTrue(r["same_sequence_digest_conflict"])
        self.assertEqual(r["reason"],"SAME_SEQUENCE_DIFFERENT_ENVELOPE_DIGEST")

    def test_06_correct_signed_older_nonce_not_fresh_challenge(self):
        self.advance(1)
        prior=self.anchor(nonce="aa"*16)
        r=self.check(raw=prior,nonce=NONCE)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHALLENGE_CLOCK_OR_SEQUENCE_INVALID")

    def test_07_expired_nonce_receipt_never_accepted(self):
        old=self.anchor(issued=ASOF-timedelta(seconds=130))
        r=self.check(raw=old)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHALLENGE_CLOCK_OR_SEQUENCE_INVALID")

    def test_08_future_anchor_timestamp_more_than_15sec_rejected(self):
        future=self.anchor(issued=ASOF+timedelta(seconds=30))
        r=self.check(raw=future)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHALLENGE_CLOCK_OR_SEQUENCE_INVALID")

    def test_09_anchor_hmac_wrong_key_rejected(self):
        forged=self.anchor(key=b"ANOTHER-PUBLIC-TEST-KEY-NOT-INSTALLED-123")
        r=self.check(raw=forged)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_HMAC_MISMATCH")

    def test_10_one_byte_signed_content_tamper_rejected(self):
        self.advance(1)
        wire=self.anchor().replace(b'"sequence":1',b'"sequence":2')
        r=self.check(raw=wire)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_HMAC_MISMATCH")

    def test_11_byte_level_json_noncanonical_rejected(self):
        wire=self.anchor().replace(b'{"anchor_key_id"',b'{ "anchor_key_id"')
        r=self.check(raw=wire)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHECKPOINT_JSON_NOT_CANONICAL")

    def test_12_extra_field_rejected_without_leaking(self):
        wire=self.anchor()
        object_=json.loads(wire)
        object_["secret_account_number"]="PRIVATE"
        data=json.dumps(object_,sort_keys=True,separators=(",",":")).encode()
        r=self.check(raw=data)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHECKPOINT_JSON_NOT_CANONICAL")
        self.assertNotIn("PRIVATE",str(r))

    def test_13_missing_trusted_anchor_record_is_no_go(self):
        r=self.check(raw=b"{}")
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_CHECKPOINT_NOT_VALID_BYTES")

    def test_14_temporary_memory_db_not_an_acceptable_replay_floor(self):
        c=sqlite3.connect(":memory:",isolation_level=None)
        self.addCleanup(c.close)
        c.execute("PRAGMA synchronous=FULL")
        r=self.check(conn=c)
        self.safe(r)
        self.assertEqual(r["reason"],
            "EXTERNAL_ANCHOR_EVIDENCE_OR_LOCAL_DB_INVALID")

    def test_15_wrong_application_id_blocks_matching_fake_anchor(self):
        self.conn.execute("PRAGMA application_id=0")
        r=self.check()
        self.safe(r)
        self.assertEqual(r["reason"],"LOCAL_REPLAY_DB_IDENTITY_OR_FLOOR_INVALID")

    def test_16_missing_floor_row_blocks_matching_fake_anchor(self):
        self.conn.execute(f"DELETE FROM {TABLE}")
        r=self.check()
        self.safe(r)
        self.assertEqual(r["reason"],"LOCAL_REPLAY_DB_IDENTITY_OR_FLOOR_INVALID")

    def test_17_boolean_sequence_not_allowed_even_if_mac_test_key(self):
        self.assertIsNone(self.anchor(seq=True,digest=None))

    def test_18_anchor_signer_requires_strong_separate_key(self):
        for key in (None,b"",b"too-short",str(ANCHOR_TEST_KEY)):
            with self.subTest(kind=type(key).__name__):
                self.assertIsNone(self.anchor(key=key))

    def test_19_wrong_receive_key_blocks_anchor_check(self):
        r=self.check(key=TEST_KEY)
        self.safe(r)
        self.assertEqual(r["reason"],"ANCHOR_HMAC_MISMATCH")

    def test_20_local_database_read_is_transactionally_nonmutating(self):
        self.advance(4)
        before=self.floor()
        r=self.check()
        self.safe(r)
        self.assertEqual(r["state"],MATCHED)
        self.assertEqual(self.floor(),before)
        self.assertFalse(self.conn.in_transaction)


if __name__=="__main__":
    unittest.main(verbosity=2)
