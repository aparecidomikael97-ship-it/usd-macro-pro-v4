"""Offline only: synthetic HMAC quarantined status, NEVER real credentials.

No network, disk, credentials, subscriptions, MT5, order, clock or store.
Using a publicly known fixed test byte-string is *intentional*; it must
never be installed as a credential or deployed to an API endpoint.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import unittest

from atlasquant_trader_fx28_signed_status_envelope_lab import (
    AUDIENCE, ISSUER, KEY_ID, SCHEMA,
    sign_fx28_sanitized_radar_status_lab as sign,
    verify_fx28_sanitized_radar_status_lab as verify,
)
from atlasquant_trader_fx28_temporal_radar_runtime_binding_lab import (
    SCHEMA as PAYLOAD_SCHEMA, STATE as PAYLOAD_STATE,
)

TEST_KEY=bytes([17])*32  # PUBLIC TEST FIXTURE, NOT A REAL SECRET
WRONG_KEY=bytes([19])*32
ISSUED=datetime(2026,11,16,0,10,tzinfo=timezone.utc)
NONCE="1a"*16


def payload():
    return {
        "schema":PAYLOAD_SCHEMA,"state":PAYLOAD_STATE,
        "frozen_total_slots":672,
        "first_nominal_window_slots_quarantined":56,
        "first_nominal_window_distinct_m15_prices_missing":28,
        "remaining_original_slots_unevaluated":616,
        "first_window_horizons":{"D1":28,"W1":28},
        "clock_p0_documentary_historical_claims_checked":False,
        "broker_source_independently_authenticated":False,
        "github_pre_event_witness_independently_authenticated":False,
        "verified_directional_accuracy":None,"calibrated_probability":None,
        "score_allowed":False,"trade_authorized":False,
        "publishable":False,"has_local_price_data_exposed":False,
        "file_writes":0,"mt5_calls":0,"http_requests":0,
        "operational_bias":"AGUARDAR",
    }


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


def signed_with_changes(raw, **changes):
    """Adversary who knows PUBLIC TEST KEY. Still cannot bypass allowlist."""
    envelope=json.loads(raw)
    envelope.update(changes)
    envelope.pop("hmac_sha256",None)
    envelope["hmac_sha256"]=hmac.new(TEST_KEY,canonical(envelope),sha256).hexdigest()
    return canonical(envelope)


class SignedFx28StatusEnvelopeTests(unittest.TestCase):
    def sample(self,*,sequence=10,issued=ISSUED,report=None,nonce=NONCE,key=TEST_KEY):
        return sign(report=payload() if report is None else report,
                    secret_key=key,sequence=sequence,nonce_hex=nonce,
                    issued_at_utc=issued)

    def open(self,raw=None,*,key=TEST_KEY,now=None,floor=9):
        return verify(
            raw_envelope=self.sample() if raw is None else raw,
            secret_key=key,
            received_at_utc=ISSUED+timedelta(seconds=15) if now is None else now,
            trusted_last_sequence=floor)

    def safe(self,result):
        self.assertFalse(result["actual_am12_device_independently_authenticated"])
        self.assertFalse(result["broker_source_authenticated"])
        self.assertFalse(result["trade_authorized"])
        self.assertFalse(result["score_unlocked"])
        self.assertFalse(result["transport_configured"])
        self.assertFalse(result["trusted_replay_checkpoint_persisted_by_this_code"])
        self.assertFalse(result["publisher_private_key_configured_by_this_code"])
        self.assertEqual((result["mt5_calls"],result["http_requests"],
                          result["file_writes"]),(0,0,0))

    def test_01_valid_fake_transport_key_possession_only(self):
        raw=self.sample()
        result=self.open(raw)
        self.safe(result)
        self.assertEqual(result["state"],
            "LAB_FX28_SIGNED_RADAR_STATUS_KEY_HOLDER_ONLY_NO_GO")
        self.assertTrue(result["hmac_checked"])
        self.assertTrue(result["key_holder_only_authenticated"])
        self.assertEqual(result["sanitized_report"],payload())
        self.assertEqual(result["proposed_new_sequence_for_external_atomic_commit"],10)
        self.assertNotIn(b"Pepperstone",raw)
        self.assertNotIn(b"terminal64",raw)
        self.assertNotIn(b"\\\\",raw)

    def test_02_exact_all_20_keys_only_no_private_archive_detail(self):
        raw=self.sample()
        outer=json.loads(raw)
        self.assertEqual(set(outer),{
            "schema","audience","issuer_claim","key_id","sequence",
            "nonce","issued_at_utc","expires_at_utc","payload",
            "hmac_sha256"})
        self.assertEqual(len(outer["payload"]),20)
        self.assertLessEqual(len(raw),4096)
        self.assertTrue(outer["payload"]["score_allowed"] is False)

    def test_03_extra_price_field_cannot_be_signed(self):
        bad=payload()
        bad["EURUSD_open"]=1.09
        self.assertIsNone(self.sample(report=bad))

    def test_04_local_windows_path_cannot_be_signed(self):
        bad=payload()
        bad["archive_path"]=r"C:\Users\Private\FX28"
        self.assertIsNone(self.sample(report=bad))

    def test_05_fake_100_percent_accuracy_never_signed(self):
        bad=payload()
        bad["verified_directional_accuracy"]=100.0
        self.assertIsNone(self.sample(report=bad))

    def test_06_fake_authorized_trade_never_signed(self):
        bad=payload()
        bad["trade_authorized"]=True
        self.assertIsNone(self.sample(report=bad))

    def test_07_boolean_masquerading_as_integer_672_rejected(self):
        bad=payload()
        bad["frozen_total_slots"]=True
        self.assertIsNone(self.sample(report=bad))

    def test_08_d1_w1_28_count_must_be_exact_integer(self):
        bad=payload()
        bad["first_window_horizons"]={"D1":True,"W1":28}
        self.assertIsNone(self.sample(report=bad))

    def test_09_schema_mismatch_cannot_be_signed(self):
        bad=payload()
        bad["schema"]="LIVE_GO"
        self.assertIsNone(self.sample(report=bad))

    def test_10_broker_source_claim_true_rejected(self):
        bad=payload()
        bad["broker_source_independently_authenticated"]=True
        self.assertIsNone(self.sample(report=bad))

    def test_11_no_key_or_short_key_fails_closed(self):
        for key in (None,b"",b"too-short",str(TEST_KEY)):
            with self.subTest(key=type(key).__name__):
                self.assertIsNone(self.sample(key=key))

    def test_12_no_sequence_bool_negative_or_zero(self):
        for n in (True,False,-1,0,2**63,"10"):
            with self.subTest(sequence=n):
                self.assertIsNone(self.sample(sequence=n))

    def test_13_non_128bit_nonce_rejected(self):
        for nonce in ("x"*32,"a"*31,"A"*32,"ab"*32,""):
            with self.subTest(nonce=nonce):
                self.assertIsNone(self.sample(nonce=nonce))

    def test_14_replay_equal_or_lower_sequence_rejected(self):
        for last in (10,11,1000):
            with self.subTest(last=last):
                r=self.open(floor=last)
                self.safe(r)
                self.assertEqual(r["reason"],
                    "EXPIRED_FUTURE_REPLAYED_OR_INVALID_SIGNED_CLOCK")
                self.assertIsNone(r["sanitized_report"])

    def test_15_valid_sequence_above_trusted_floor(self):
        r=self.open(floor=8)
        self.safe(r)
        self.assertEqual(r["proposed_new_sequence_for_external_atomic_commit"],10)

    def test_16_trusted_replay_floor_required_and_numeric(self):
        for floor in (None,True,-1,"9",2**63):
            with self.subTest(floor=floor):
                self.assertEqual(self.open(floor=floor)["reason"],
                    "INVALID_CLOCK_KEY_OR_TRUSTED_REPLAY_FLOOR")

    def test_17_received_exact_expiry_rejected(self):
        r=self.open(now=ISSUED+timedelta(minutes=5))
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])

    def test_18_receipt_one_second_before_expiry_valid(self):
        r=self.open(now=ISSUED+timedelta(minutes=5,seconds=-1))
        self.safe(r)
        self.assertIsNotNone(r["sanitized_report"])

    def test_19_future_clock_more_than_30s_skew_rejected(self):
        r=self.open(now=ISSUED-timedelta(seconds=31))
        self.safe(r)
        self.assertIsNone(r["sanitized_report"])

    def test_20_future_clock_skew_30s_allowed(self):
        r=self.open(now=ISSUED-timedelta(seconds=30))
        self.safe(r)
        self.assertIsNotNone(r["sanitized_report"])

    def test_21_wrong_receiver_secret_fails_hmac(self):
        r=self.open(key=WRONG_KEY)
        self.safe(r)
        self.assertEqual(r["reason"],"MESSAGE_AUTHENTICATION_FAILED_NO_GO")
        self.assertFalse(r["key_holder_only_authenticated"])

    def test_22_one_byte_tamper_rejected(self):
        raw=self.sample().replace(b"AGUARDAR",b"AGUARDAX")
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],"MESSAGE_AUTHENTICATION_FAILED_NO_GO")

    def test_23_malformed_or_oversized_json_rejected(self):
        for raw in (b"{}",b"non-json",b"X"*4097,"hello"):
            with self.subTest(raw=repr(raw)[:12]):
                r=self.open(raw)
                self.safe(r)
                self.assertIsNone(r["sanitized_report"])

    def test_24_duplicate_json_key_rejected(self):
        raw=self.sample().replace(b'"sequence":10',b'"sequence":10,"sequence":12')
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],
            "INVALID_NONCANONICAL_DUPLICATE_OR_UNSAFE_JSON")

    def test_25_whitespace_change_rejected_before_signature(self):
        raw=self.sample().replace(b'{"audience"',b'{ "audience"')
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],
            "INVALID_NONCANONICAL_DUPLICATE_OR_UNSAFE_JSON")

    def test_26_even_valid_key_cannot_claim_wrong_audience(self):
        raw=signed_with_changes(self.sample(),audience="PUBLIC_CLIENT")
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],"BAD_ENVELOPE_ROUTING_OR_SIGNATURE_SHAPE")

    def test_27_even_valid_key_cannot_claim_other_key_id(self):
        raw=signed_with_changes(self.sample(),key_id="unregistered-key")
        self.assertEqual(self.open(raw)["reason"],
            "BAD_ENVELOPE_ROUTING_OR_SIGNATURE_SHAPE")

    def test_28_even_signed_extra_payload_field_rejected(self):
        bad=payload()
        bad["MT5_private_account"]="SECRET"
        raw=signed_with_changes(self.sample(),payload=bad)
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],
            "SIGNED_PAYLOAD_CONTAINS_UNSAFE_OR_NON_LAB_FIELDS")
        self.assertIsNone(r["sanitized_report"])

    def test_29_even_signed_revised_672_total_rejected(self):
        bad=payload()
        bad["remaining_original_slots_unevaluated"]=615
        raw=signed_with_changes(self.sample(),payload=bad)
        self.assertEqual(self.open(raw)["reason"],
            "SIGNED_PAYLOAD_CONTAINS_UNSAFE_OR_NON_LAB_FIELDS")

    def test_30_signed_bad_nonce_rejected(self):
        raw=signed_with_changes(self.sample(),nonce="not-hex")
        r=self.open(raw)
        self.safe(r)
        self.assertEqual(r["reason"],
            "EXPIRED_FUTURE_REPLAYED_OR_INVALID_SIGNED_CLOCK")

    def test_31_signed_false_expiry_rejected(self):
        raw=signed_with_changes(self.sample(),
                               expires_at_utc="2026-11-16T00:18:00Z")
        self.assertEqual(self.open(raw)["reason"],
            "EXPIRED_FUTURE_REPLAYED_OR_INVALID_SIGNED_CLOCK")

    def test_32_signed_noniso_date_rejected(self):
        raw=signed_with_changes(self.sample(),
                               issued_at_utc="2026-11-16 00:10:00 UTC")
        self.assertEqual(self.open(raw)["reason"],
            "EXPIRED_FUTURE_REPLAYED_OR_INVALID_SIGNED_CLOCK")

    def test_33_invalid_naive_signer_and_verifier_clocks(self):
        self.assertIsNone(self.sample(issued=ISSUED.replace(tzinfo=None)))
        r=self.open(now=ISSUED.replace(tzinfo=None))
        self.safe(r)
        self.assertEqual(r["reason"],
            "INVALID_CLOCK_KEY_OR_TRUSTED_REPLAY_FLOOR")

    def test_34_invalid_microsecond_clocks_rejected(self):
        self.assertIsNone(self.sample(issued=ISSUED+timedelta(microseconds=1)))
        self.assertEqual(self.open(now=ISSUED+timedelta(microseconds=1))["reason"],
                         "INVALID_CLOCK_KEY_OR_TRUSTED_REPLAY_FLOOR")

    def test_35_no_transport_config_keys_generated_or_broker_claim(self):
        r=self.open()
        self.safe(r)
        self.assertEqual(r["schema"],SCHEMA)
        self.assertNotIn("private_key",r)
        self.assertNotIn("account_number",r)
        self.assertNotIn("broker_server_epoch",r)
        self.assertEqual(json.loads(self.sample())["issuer_claim"],ISSUER)
        self.assertEqual(json.loads(self.sample())["audience"],AUDIENCE)
        self.assertEqual(json.loads(self.sample())["key_id"],KEY_ID)


if __name__=="__main__":
    unittest.main(verbosity=2)
