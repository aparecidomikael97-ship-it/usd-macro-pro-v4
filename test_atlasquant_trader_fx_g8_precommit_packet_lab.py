"""Synthetic candidate receipts; never claim independently timed predictions."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_trader_fx_g8_precommit_packet_lab import (
    KIND, SCHEMA, inspect_g8_precommit_packet_lab as inspect,
    prepare_g8_precommit_packet_lab as prepare,
)
from test_atlasquant_trader_fx_g8_claims_macro_binding_lab import (
    COHORT, FROZEN, NOW, encoded, ledger, macro_object, row,
)


def awaits():
    return [row(s, direction="AGUARDAR") for s in FROZEN["slots"]]


def candidate(entries=None, evidence=None, *, at=NOW, cohort=COHORT):
    return prepare(cohort_raw=cohort, claims_raw=ledger(awaits() if entries is None else entries),
                   macro_bytes_by_slot={} if evidence is None else evidence,
                   prepared_at_utc=at)


def replay(raw, entries=None, evidence=None, *, at=NOW, cohort=COHORT):
    return inspect(packet_raw=raw, cohort_raw=cohort,
                   claims_raw=ledger(awaits() if entries is None else entries),
                   macro_bytes_by_slot={} if evidence is None else evidence,
                   inspected_at_utc=at)


class G8CanonicalPrecommitPacketTests(unittest.TestCase):
    def assert_no_operational_promotion(self, r):
        for field in (
            "external_server_packet_witness_verified",
            "external_precommit_timestamp_independently_witnessed",
            "macroeconomic_release_vintage_independently_verified",
            "model_freeze_and_calibration_independently_verified",
            "future_market_prices_verified", "trade_authorized",
            "can_feed_live_radar", "publishable", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertIs(r[field], False, field)
        self.assertEqual(r["validated_prediction_count"], 0)
        self.assertIsNone(r["validated_accuracy"])
        self.assertIsNone(r["fx_bias"])
        self.assertEqual(r["operational_bias"], "AGUARDAR")
        self.assertEqual((r["http_requests"], r["new_cost_brl"]), (0, 0))

    def test_complete_56_await_packet_is_not_a_single_prediction(self):
        r = candidate()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_CANONICAL_56_SLOT_PACKET_READY_NOT_EXTERNALLY_WITNESSED")
        self.assertEqual(r["submitted_slots"], 56)
        self.assertEqual(r["unfilled_slots"], 0)
        self.assertEqual(r["directional_claims"], 0)
        self.assertEqual(r["await_abstentions"], 56)
        self.assertEqual(r["macro_bytes_bound_slots"], 0)
        self.assertEqual(r["packet_sha256"], sha256(r["packet_bytes"]).hexdigest())
        self.assertTrue(r["candidate_prepared_before_deadline_claim"])
        self.assert_no_operational_promotion(r)

    def test_canonical_packet_includes_all_56_slots_in_frozen_order(self):
        p = json.loads(candidate()["packet_bytes"])
        self.assertEqual(p["kind"], KIND)
        self.assertEqual(p["declared_slots"], 56)
        self.assertEqual([r["slot_id"] for r in p["entries"]],
                         [s["slot_id"] for s in FROZEN["slots"]])
        self.assertIsNone(p["independent_witness_url"])
        self.assertIsNone(p["independent_server_timestamp"])
        self.assertIsNone(p["prediction_accuracy_claim"])
        self.assertEqual(p["precommit_deadline_utc"], "2026-11-08T21:00:00Z")

    def test_claim_ledger_order_does_not_change_canonical_entries(self):
        p = json.loads(candidate(entries=list(reversed(awaits())))["packet_bytes"])
        self.assertEqual([r["slot_id"] for r in p["entries"]],
                         [s["slot_id"] for s in FROZEN["slots"]])

    def test_unchanged_packet_replays_without_witness_even_after_deadline(self):
        p = candidate()["packet_bytes"]
        for at in (NOW, datetime(2026, 11, 9, 9, tzinfo=timezone.utc)):
            r = replay(p, at=at)
            self.assertEqual(r["state"],
                             "LAB_PACKET_REPLAY_IDENTICAL_BUT_HISTORICAL_WITNESS_MISSING")
            self.assertEqual(r["packet_sha256"], sha256(p).hexdigest())
            self.assertIsNone(r["packet_bytes"])
            self.assert_no_operational_promotion(r)

    def test_one_declared_direction_and_55_await_have_one_hash_bound(self):
        slot = FROZEN["slots"][0]
        raw = encoded(macro_object(slot["pair"]))
        entries = [row(slot, raw=raw)] + [row(s, direction="AGUARDAR")
                                           for s in FROZEN["slots"][1:]]
        r = candidate(entries, {slot["slot_id"]: raw})
        self.assertEqual(r["state"], "LAB_CANONICAL_56_SLOT_PACKET_READY_NOT_EXTERNALLY_WITNESSED")
        self.assertEqual(r["directional_claims"], 1)
        self.assertEqual(r["macro_bytes_bound_slots"], 1)
        self.assertEqual(r["await_abstentions"], 55)
        self.assert_no_operational_promotion(r)
        self.assertEqual(replay(r["packet_bytes"], entries,
                                {slot["slot_id"]: raw})["state"],
                         "LAB_PACKET_REPLAY_IDENTICAL_BUT_HISTORICAL_WITNESS_MISSING")

    def test_56_synthetic_directions_do_not_count_as_predictions_verified(self):
        entries, evidence = [], {}
        for slot in FROZEN["slots"]:
            raw = encoded(macro_object(slot["pair"]))
            entries.append(row(slot, raw=raw))
            evidence[slot["slot_id"]] = raw
        r = candidate(entries, evidence)
        self.assertEqual(r["submitted_slots"], 56)
        self.assertEqual(r["directional_claims"], 56)
        self.assertEqual(r["macro_bytes_bound_slots"], 56)
        self.assert_no_operational_promotion(r)

    def test_incomplete_55_slot_ledger_fails_no_silent_missing_pair(self):
        r = candidate(entries=awaits()[:-1])
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["reason"], "INCOMPLETE_OR_LATE_OR_UNBOUND_56_SLOT_LEDGER")
        self.assert_no_operational_promotion(r)

    def test_duplicate_slot_in_place_of_another_is_rejected(self):
        entries = awaits()
        entries[-1] = entries[0]
        self.assertEqual(candidate(entries=entries)["state"], "LAB_BLOCKED")

    def test_claimed_direction_requires_exact_original_macro_bytes(self):
        slot = FROZEN["slots"][0]
        raw = encoded(macro_object(slot["pair"]))
        entries = [row(slot, raw=raw)] + [row(s, direction="AGUARDAR")
                                           for s in FROZEN["slots"][1:]]
        for evidence in ({}, {slot["slot_id"]: raw + b"\n"}):
            r = candidate(entries, evidence)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_operational_promotion(r)

    def test_after_deadline_new_candidate_refused(self):
        r = candidate(at=datetime(2026, 11, 8, 21, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_operational_promotion(r)

    def test_at_exact_precommit_deadline_still_structurally_possible(self):
        r = candidate(at=datetime(2026, 11, 8, 21, 0, tzinfo=timezone.utc))
        self.assertEqual(r["state"], "LAB_CANONICAL_56_SLOT_PACKET_READY_NOT_EXTERNALLY_WITNESSED")
        self.assert_no_operational_promotion(r)

    def test_reject_invalid_naive_non_datetime_and_pre_claim_clock(self):
        for at in (datetime(2026, 11, 6, 16), "2026-11-06T16:00:00Z", None,
                   datetime(2026, 11, 6, 14, tzinfo=timezone.utc)):
            r = candidate(at=at)
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assert_no_operational_promotion(r)

    def test_replay_rejects_changed_direction_or_attested_timestamp_claim(self):
        raw = candidate()["packet_bytes"]
        for name, value in (("independent_server_timestamp", "2026-11-06T16:00:00Z"),
                            ("prediction_accuracy_claim", "90%")):
            p = json.loads(raw)
            p[name] = value
            r = replay(encoded(p))
            self.assertEqual(r["state"], "LAB_BLOCKED")
            self.assertEqual(r["reason"], "PACKET_BYTES_OR_UNDERLYING_EVIDENCE_CHANGED")
        p = json.loads(raw)
        p["entries"][0]["direction_claim"] = "ALTA"
        self.assertEqual(replay(encoded(p))["state"], "LAB_BLOCKED")

    def test_replay_rejects_wrong_or_future_creation_timestamp(self):
        raw = candidate()["packet_bytes"]
        p = json.loads(raw)
        p["prepared_at_utc_claim"] = "2026-11-08T21:00:01Z"
        self.assertEqual(replay(encoded(p), at=NOW)["reason"],
                         "PREPARATION_CLAIM_IN_FUTURE")
        p["prepared_at_utc_claim"] = "not-a-date"
        self.assertEqual(replay(encoded(p))["state"], "LAB_BLOCKED")

    def test_replay_rejects_malformed_extra_and_wrong_underlying_evidence(self):
        raw = candidate()["packet_bytes"]
        for changed in (b"invalid", raw + b"\n", None, {}, b"a" * 100_001):
            self.assertEqual(replay(changed)["state"], "LAB_BLOCKED")
        self.assertEqual(replay(raw, entries=awaits()[:-1])["state"], "LAB_BLOCKED")

    def test_canonical_byte_length_is_bounded(self):
        r = candidate()
        self.assertLess(r["packet_size_bytes"], 100_000)
        self.assertEqual(r["packet_size_bytes"], len(r["packet_bytes"]))


if __name__ == "__main__":
    unittest.main()
