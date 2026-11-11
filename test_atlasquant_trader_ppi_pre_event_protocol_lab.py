"""Synthetic-only contract tests for the frozen PPI descriptive abstention."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import unittest
from unittest.mock import patch

import atlasquant_trader_ppi_pre_event_protocol_lab as protocol

BEFORE = datetime(2026, 11, 11, 20, 0, tzinfo=timezone.utc)
AFTER = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)


class PpiFrozenStudyProtocolTests(unittest.TestCase):
    def check(self, when=BEFORE, **kwargs):
        x = protocol.inspect_ppi_frozen_research_protocol_lab(
            as_of_utc=when, **kwargs)
        self.assertEqual(x["operational_bias"], "AGUARDAR")
        self.assertFalse(x["trade_authorized"])
        self.assertFalse(x["publishable"])
        self.assertFalse(x["live_alert_allowed"])
        self.assertFalse(x["future_accuracy_metric_allowed"])
        self.assertFalse(x["forecast_or_probability_claim_allowed"])
        self.assertFalse(x["external_pre_event_timestamp_witness_authenticated"])
        self.assertFalse(x["independent_broker_and_publisher_provenance_verified"])
        self.assertIsNone(x["valid_prediction_accuracy"])
        self.assertIsNone(x["calibrated_probability"])
        self.assertEqual(x["pre_event_directional_forecasts_registered"], 0)
        self.assertEqual(x["independent_prediction_trials_verified"], 0)
        self.assertEqual((x["http_requests"], x["file_writes"], x["new_cost_brl"]),
                         (0, 0, 0))
        return x

    def test_frozen_code_hash_is_stable_and_exactly_pinned(self):
        raw = protocol.canonical_protocol_bytes_lab(protocol.FROZEN_PROTOCOL)
        self.assertEqual(sha256(raw).hexdigest(), protocol.PINNED_PROTOCOL_SHA256)
        out = self.check()
        self.assertEqual(out["state"], protocol.BEFORE)
        self.assertEqual(out["frozen_protocol_sha256"],
                         protocol.PINNED_PROTOCOL_SHA256)

    def test_pre_event_abstention_not_a_usd_prediction(self):
        r = self.check()
        self.assertTrue(r["pre_event_declared_abstention"])
        self.assertTrue(r["frozen_consensus_source_hashes_consistent"])
        self.assertTrue(r["descriptive_only"])
        self.assertTrue(r["seven_pairs_not_seven_predictions"])

    def test_post_event_protocol_does_not_turn_reaction_into_forecast(self):
        r = self.check(AFTER)
        self.assertEqual(r["state"], protocol.AFTER)
        self.assertEqual(r["event_count"], 1)
        self.assertEqual(r["fx_observation_count_planned"], 7)
        self.assertEqual(r["pre_event_directional_forecasts_registered"], 0)

    def test_replay_is_identical_and_readonly(self):
        before = deepcopy(protocol.FROZEN_PROTOCOL)
        one = self.check()
        two = self.check()
        self.assertEqual(one, two)
        self.assertEqual(before, protocol.FROZEN_PROTOCOL)

    def test_malicious_submitted_direction_no_longer_matches_frozen_policy(self):
        fake = deepcopy(protocol.FROZEN_PROTOCOL)
        fake["pre_event_research_direction"] = "USD_UP"
        fake["model_version"] = "post_hoc_v2"
        r = self.check(submitted_protocol=fake)
        self.assertEqual(r["state"], protocol.BLOCKED)
        self.assertEqual(r["reason"],
                         "SUBMITTED_POLICY_NOT_EQUAL_TO_PRE_EVENT_PROTOCOL")

    def test_post_event_attempt_to_change_windows_or_pair_census_rejected(self):
        for key, value in (
            ("reaction_windows_minutes", [1, 15, 60, 240]),
            ("fx_symbols", ["EURUSD"]),
            ("event_count", 7),
            ("headline_consensus_mom_pct", "0.9"),
            ("release_utc", "2026-11-14T13:30:00+00:00"),
        ):
            with self.subTest(field=key):
                fake = deepcopy(protocol.FROZEN_PROTOCOL)
                fake[key] = value
                r = self.check(AFTER, submitted_protocol=fake)
                self.assertEqual(r["state"], protocol.BLOCKED)

    def test_in_place_modification_detected_against_literal_hash(self):
        for key, value in (
            ("pre_event_research_direction", "USD_DOWN"),
            ("core_consensus_mom_pct", "0.0"),
            ("event_count", 7),
        ):
            with self.subTest(key=key):
                with patch.dict(protocol.FROZEN_PROTOCOL, {key: value}):
                    r = self.check(AFTER)
                self.assertEqual(r["reason"],
                                 "CODE_PROTOCOL_DIFFERS_FROM_FROZEN_PIN")

    def test_bad_clock_or_late_external_claim_does_not_create_attestation(self):
        for when in (None, "2026-11-11T20:00:00Z",
                     BEFORE.replace(tzinfo=None)):
            with self.subTest(when=when):
                r = self.check(when)
                self.assertEqual(r["state"], protocol.BLOCKED)

    def test_plan_with_unrecognized_or_duplicate_json_fields_rejected(self):
        fake = deepcopy(protocol.FROZEN_PROTOCOL)
        fake["fake_accuracy"] = "100%"
        r = self.check(AFTER, submitted_protocol=fake)
        self.assertEqual(r["state"], protocol.BLOCKED)
        self.assertFalse(r["future_accuracy_metric_allowed"])


if __name__ == "__main__":
    unittest.main()
