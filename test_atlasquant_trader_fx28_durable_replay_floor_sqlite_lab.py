"""Test transactional SQLite anti-replay on disposable LOCAL temp databases.

No real keys, broker prices, jobs, network or production database. A
public test-only HMAC key is used; never deploy it. Tests exercise commit
BEFORE status release, restart persistence, exclusive DB locking and
fail-closed behavior on corruption, forged payloads and unsafe settings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
import json
import sqlite3

from atlasquant_trader_fx28_durable_replay_floor_sqlite_lab import (
    APP_ID,TABLE,
    bootstrap_fx28_replay_floor_sqlite_lab as bootstrap,
    receive_fx28_signed_status_once_sqlite_lab as consume,
)
from atlasquant_trader_fx28_signed_status_envelope_lab import (
    sign_fx28_sanitized_radar_status_lab as sign,
)
from test_atlasquant_trader_fx28_signed_status_envelope_lab import (
    TEST_KEY,WRONG_KEY,ISSUED,payload,
)

UTC=timezone.utc
ACCEPTED="LAB_FX28_SQLITE_REPLAY_ADVANCED_KEY_HOLDER_ONLY_NO_GO"


class DurableFx28ReplayTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="AQ_FX28_REPLAY_ONLY_TEST_")
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"fx28_status_replay.sqlite3"
        self.conn=self.open()
        self.addCleanup(self.conn.close)

    def open(self, *, path=None, timeout=0.2):
        c=sqlite3.connect(str(self.path if path is None else path),
                          timeout=timeout,isolation_level=None)
        c.execute("PRAGMA main.synchronous=FULL")
        return c

    def ready(self):
        return bootstrap(
            conn=self.conn,explicitly_authorized_new_empty_database=True)

    def signed(self,sequence=1,*,report=None,issued=ISSUED,key=TEST_KEY):
        return sign(
            report=payload() if report is None else report,
            secret_key=key,sequence=sequence,
            nonce_hex=f"{sequence:032x}",issued_at_utc=issued)

    def use(self,raw=None,*,connection=None,key=TEST_KEY,now=None):
        return consume(
            conn=self.conn if connection is None else connection,
            raw_envelope=self.signed() if raw is None else raw,
            secret_key=key,
            received_at_utc=ISSUED+timedelta(seconds=20) if now is None else now)

    def sequence(self,*,connection=None):
        c=self.conn if connection is None else connection
        row=c.execute(f"SELECT highest_accepted_sequence FROM {TABLE} WHERE id=1").fetchone()
        return row[0] if row else None

    def safe(self,r):
        self.assertFalse(r["broker_source_independently_authenticated"])
        self.assertFalse(r["device_identity_independently_authenticated"])
        self.assertFalse(r["clock_independently_attested"])
        self.assertFalse(r["secret_installed_by_this_code"])
        self.assertFalse(r["transport_configured"])
        self.assertFalse(r["production_store_provisioned"])
        self.assertFalse(r["durability_survives_disk_rollback_or_backup_restore"])
        self.assertFalse(r["client_sent_raw_market_prices"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["score_unlocked"])
        self.assertEqual((r["mt5_calls"],r["http_requests"]),(0,0))
        self.assertEqual(r["operational_bias"],"AGUARDAR")

    def test_01_explicit_bootstrap_then_one_valid_receipt_atomic_commit(self):
        self.assertTrue(self.ready())
        result=self.use()
        self.safe(result)
        self.assertEqual(result["state"],ACCEPTED)
        self.assertTrue(result["db_transaction_committed"])
        self.assertEqual(result["database_rows_written"],1)
        self.assertEqual(result["highest_accepted_sequence_after_commit"],1)
        self.assertEqual(result["sanitized_report"],payload())
        self.assertEqual(self.sequence(),1)

    def test_02_reboot_new_connection_rejects_duplicate_sequence(self):
        self.ready()
        self.assertEqual(self.use()["state"],ACCEPTED)
        self.conn.close()
        new=self.open()
        self.addCleanup(new.close)
        result=self.use(connection=new)
        self.safe(result)
        self.assertEqual(result["reason"],"SIGNED_RECEIPT_INVALID_EXPIRED_OR_REPLAYED")
        self.assertIsNone(result["sanitized_report"])
        self.assertEqual(self.sequence(connection=new),1)

    def test_03_lower_sequence_rejected_after_higher_accepted(self):
        self.ready()
        self.assertEqual(self.use(self.signed(3))["state"],ACCEPTED)
        r=self.use(self.signed(2))
        self.safe(r)
        self.assertFalse(r["db_transaction_committed"])
        self.assertEqual(self.sequence(),3)

    def test_04_newer_sequence_accepted_once_after_restart(self):
        self.ready()
        self.use(self.signed(1))
        self.conn.close()
        new=self.open()
        self.addCleanup(new.close)
        self.assertEqual(self.use(self.signed(2),connection=new)["state"],ACCEPTED)
        self.assertEqual(self.sequence(connection=new),2)
        self.assertIsNone(self.use(self.signed(2),connection=new)["sanitized_report"])

    def test_05_no_bootstrap_rejects_without_implicit_initialize(self):
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        names=self.conn.execute(
            "SELECT name FROM sqlite_master WHERE name=?",(TABLE,)).fetchall()
        self.assertEqual(names,[])

    def test_06_bootstrap_requires_explicit_true_not_truthy_string(self):
        for val in (False,None,1,"yes"):
            self.assertFalse(bootstrap(
                conn=self.conn,explicitly_authorized_new_empty_database=val))
        self.assertFalse(self.path.stat().st_size==0 and self.conn.in_transaction)

    def test_07_repeat_bootstrap_cannot_reset_counter(self):
        self.ready()
        self.use(self.signed(7))
        self.assertFalse(self.ready())
        self.assertEqual(self.sequence(),7)

    def test_08_existing_nonempty_database_cannot_bootstrap(self):
        self.conn.execute("CREATE TABLE other_private_data (id INTEGER)")
        self.assertFalse(self.ready())
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name=?",(TABLE,)).fetchone()[0],0)

    def test_09_memory_sqlite_denied_for_replay_durability(self):
        c=sqlite3.connect(":memory:",isolation_level=None)
        self.addCleanup(c.close)
        c.execute("PRAGMA synchronous=FULL")
        self.assertFalse(bootstrap(
            conn=c,explicitly_authorized_new_empty_database=True))
        r=self.use(connection=c)
        self.safe(r)
        self.assertIn("NOT_DURABLE",r["reason"])

    def test_10_sqlite_normal_sync_denied(self):
        self.ready()
        self.conn.execute("PRAGMA synchronous=NORMAL")
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_11_sqlite_journal_off_denied(self):
        self.ready()
        self.conn.execute("PRAGMA journal_mode=OFF")
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_12_active_uncommitted_transaction_is_not_accepted(self):
        self.ready()
        self.conn.execute("BEGIN")
        r=self.use()
        self.safe(r)
        self.assertFalse(r["db_transaction_committed"])
        self.conn.rollback()
        self.assertEqual(self.sequence(),0)

    def test_13_other_writer_lock_serializes_and_denies_read(self):
        self.ready()
        contender=self.open(timeout=0.05)
        self.addCleanup(contender.close)
        self.conn.execute("BEGIN IMMEDIATE")
        r=self.use(connection=contender)
        self.safe(r)
        self.assertFalse(r["db_transaction_committed"])
        self.assertEqual(self.sequence(),0)
        self.conn.rollback()

    def test_14_valid_receipt_after_lock_released_succeeds(self):
        self.ready()
        contender=self.open(timeout=0.05)
        self.addCleanup(contender.close)
        self.conn.execute("BEGIN IMMEDIATE")
        self.assertIsNone(self.use(connection=contender)["sanitized_report"])
        self.conn.rollback()
        self.assertEqual(self.use(connection=contender)["state"],ACCEPTED)

    def test_15_bad_hmac_does_not_advance_floor(self):
        self.ready()
        r=self.use(key=WRONG_KEY)
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_16_expired_message_does_not_advance_floor(self):
        self.ready()
        r=self.use(now=ISSUED+timedelta(minutes=5))
        self.safe(r)
        self.assertEqual(self.sequence(),0)

    def test_17_future_dated_message_does_not_advance_floor(self):
        self.ready()
        r=self.use(now=ISSUED-timedelta(seconds=31))
        self.safe(r)
        self.assertEqual(self.sequence(),0)

    def test_18_replayed_even_if_different_nonce_or_new_digest(self):
        self.ready()
        self.use(self.signed(4))
        altered=sign(report=payload(),secret_key=TEST_KEY,
                     sequence=4,nonce_hex="b"*32,issued_at_utc=ISSUED)
        r=self.use(altered)
        self.safe(r)
        self.assertEqual(self.sequence(),4)
        self.assertIsNone(r["sanitized_report"])

    def test_19_even_with_valid_key_extra_price_field_rejected(self):
        self.ready()
        bad=payload()
        bad["GBPUSD"]=1.2345
        self.assertIsNone(self.signed(report=bad))
        r=self.use(raw=b"{}")
        self.safe(r)
        self.assertEqual(self.sequence(),0)

    def test_20_valid_signed_message_with_wrong_payload_never_accepted(self):
        self.ready()
        # Receiver independently validates the strict 20-field status.
        fake=payload()
        fake["trade_authorized"]=True
        self.assertIsNone(self.signed(report=fake))
        self.assertIsNone(self.use(raw=b"{}")["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_21_sqlite_application_id_tamper_rejected(self):
        self.ready()
        self.conn.execute("PRAGMA application_id=0")
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_22_sqlite_schema_version_tamper_rejected(self):
        self.ready()
        self.conn.execute("PRAGMA user_version=2")
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_23_missing_replay_row_rejected_not_reset(self):
        self.ready()
        self.conn.execute(f"DELETE FROM {TABLE}")
        r=self.use()
        self.safe(r)
        self.assertEqual(r["reason"],"REPLAY_DB_SCHEMA_IDENTITY_OR_HIGH_WATER_INVALID")
        self.assertIsNone(r["sanitized_report"])
        self.assertFalse(self.ready())

    def test_24_missing_table_rejected_not_recreated(self):
        self.ready()
        self.conn.execute(f"DROP TABLE {TABLE}")
        r=self.use()
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])
        self.assertFalse(self.ready())

    def test_25_failed_update_transaction_rolls_back_and_not_displayed(self):
        self.ready()
        self.conn.execute(
            f"CREATE TRIGGER reject_accept BEFORE UPDATE ON {TABLE} "
            "BEGIN SELECT RAISE(ABORT,'lab simulated disk/write failure'); END")
        r=self.use()
        self.safe(r)
        self.assertFalse(r["db_transaction_committed"])
        self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),0)

    def test_26_no_private_raw_payload_or_secret_in_db(self):
        self.ready()
        message=self.signed()
        self.assertEqual(self.use(message)["state"],ACCEPTED)
        rows=self.conn.execute(
            f"SELECT id,key_id,audience,issuer_claim,"
            f"highest_accepted_sequence,last_envelope_sha256 FROM {TABLE}").fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][4],1)
        self.assertEqual(len(rows[0][5]),64)
        self.assertNotIn(str(TEST_KEY),str(rows))
        self.assertNotIn("first_nominal_window_slots_quarantined",str(rows))
        self.assertNotIn("Pepperstone",str(rows))

    def test_27_invalid_sqlite_connection_type_fails_closed(self):
        r=self.use(connection="not-sqlite")
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])

    def test_28_readonly_reopen_cannot_bootstrap_or_advance(self):
        self.ready()
        readonly=sqlite3.connect(
            self.path.as_uri()+"?mode=ro",uri=True,isolation_level=None)
        self.addCleanup(readonly.close)
        self.assertFalse(bootstrap(
            conn=readonly,explicitly_authorized_new_empty_database=True))
        self.assertIsNone(self.use(connection=readonly)["sanitized_report"])

    def test_29_input_malformed_json_never_changes_high_water(self):
        self.ready()
        self.use(self.signed(2))
        for raw in (b"{}",b"\xff"*500,b"not JSON",None):
            with self.subTest(raw_type=type(raw).__name__):
                r=self.use(raw=raw)
                self.safe(r)
                self.assertIsNone(r["sanitized_report"])
        self.assertEqual(self.sequence(),2)

    def test_30_after_commit_no_second_display_for_same_receipt(self):
        self.ready()
        a=self.use(self.signed(1))
        self.assertTrue(a["db_transaction_committed"])
        b=self.use(self.signed(1))
        self.assertFalse(b["db_transaction_committed"])
        self.assertIsNone(b["sanitized_report"])

    def test_31_replay_store_is_not_public_transport_or_broker_proof(self):
        self.ready()
        a=self.use()
        self.safe(a)
        self.assertFalse(a["production_store_provisioned"])
        self.assertFalse(a["transport_configured"])
        self.assertFalse(a["durability_survives_disk_rollback_or_backup_restore"])
        self.assertEqual(a["database_rows_written"],1)


if __name__=="__main__":
    main(verbosity=2)
