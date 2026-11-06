"""Integration tests for a fail-closed Forex macro/forecast/M15 evidence chain.

Every price and macro receipt in this suite is SIMULATED and untrusted.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_premove_lab import FORECAST
from atlasquant_trader_g8_macro_asof_lab import ENVELOPE
from atlasquant_trader_fx_d1w1_evidence_chain_lab import (
    SCHEMA, inspect_fx_d1w1_evidence_chain_lab as inspect,
)

NOW = datetime(2026, 11, 6, 14, tzinfo=timezone.utc)
CREATED = "2026-11-02T09:05:00Z"
CUTOFF = "2026-11-02T09:00:00Z"


def encoded(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def receipt(currency, indicator, **changes):
    r = {
        "currency": currency, "indicator": indicator,
        "observation_period": "2026-09", "value": "2.0",
        "published_at_utc": "2026-10-29T12:00:00Z",
        "captured_at_utc": "2026-10-29T12:05:00Z",
        "source_type": ("CENTRAL_BANK" if indicator == "POLICY_RATE"
                        else "OFFICIAL_STATISTICS_OFFICE"),
        "source_sha256": "a" * 64,
    }
    r.update(changes)
    return r


def fixtures(pair="EUR/USD", *, horizon="D1", macro_changes=None,
             forecast_changes=None, include_m15=True):
    base, quote = pair.split("/")
    m = {"schema": ENVELOPE, "pair": pair,
         "decision_at_utc": CREATED,
         "records": [receipt(currency, indicator)
                     for currency in (base, quote)
                     for indicator in ("CPI_YOY", "POLICY_RATE")]}
    if macro_changes:
        macro_changes(m)
    m_raw = encoded(m)
    f = {"schema": FORECAST, "pair": pair,
         "horizon": horizon, "model_version": "LAB_FX_TEST_20261106",
         "direction": "ALTA", "evidence_sha256": sha256(m_raw).hexdigest(),
         "data_cutoff_utc": CUTOFF,
         "created_at_utc": CREATED,
         "target_start_utc": "2026-11-02T22:00:00Z",
         "target_end_utc": "2026-11-03T22:00:00Z"}
    if horizon == "W1":
        # The forecast must exist BEFORE Sunday evening's NY weekly open.
        f["target_start_utc"] = "2026-11-01T22:00:00Z"
        f["target_end_utc"] = "2026-11-06T22:00:00Z"
        f["created_at_utc"] = "2026-10-30T09:05:00Z"
        f["data_cutoff_utc"] = "2026-10-30T09:00:00Z"
        m["decision_at_utc"] = f["created_at_utc"]
        m_raw = encoded(m)
        f["evidence_sha256"] = sha256(m_raw).hexdigest()
    if forecast_changes:
        forecast_changes(f)
    m15 = (
        b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        b"2026.11.02\t10:00:00\t1.1000\t1.1200\t1.0900\t1.1100\t150\t0\t12\n"
        b"2026.11.02\t10:15:00\t1.1100\t1.1300\t1.1000\t1.1200\t180\t0\t13\n"
    )
    return encoded(f), m_raw, m15 if include_m15 else None


def run(f=None, macro=None, m15=None, *, now=NOW, use_default_m15=True):
    base_f, base_macro, default_m15 = fixtures()
    return inspect(
        forecast_raw=base_f if f is None else f,
        macro_raw=base_macro if macro is None else macro,
        mt5_m15_csv_raw=(default_m15 if use_default_m15 and m15 is None else m15),
        as_of_utc=now,
    )


class EvidenceChainTests(unittest.TestCase):
    def assert_no_go(self, result):
        for field in (
            "macroeconomic_source_independently_authenticated",
            "source_publication_times_independently_attested",
            "point_in_time_vintage_independently_verified",
            "forecast_external_precommit_independently_verified",
            "algorithm_frozen_before_forecast_verified",
            "broker_m15_timezone_independently_verified",
            "broker_bid_ask_executable_prices_verified",
            "historical_accuracy_verified", "can_feed_live_radar",
            "trade_authorized", "publishable", "worker_enabled",
            "scheduler_enabled",
        ):
            self.assertFalse(result[field], field)
        self.assertEqual(result["validated_prediction_count"], 0)
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["fx_bias"])
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertEqual((result["external_http_requests"], result["new_cost_brl"]), (0, 0))

    def test_all_component_contracts_consistent_but_still_not_proof(self):
        f, m, mt5 = fixtures()
        r = run(f, m, mt5)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["state"], "LAB_STRUCTURAL_INPUTS_CONSISTENT_BUT_PROOF_MISSING")
        for field in (
            "forecast_receipt_structurally_valid",
            "macro_receipts_structurally_valid",
            "two_sided_pilot_indicators_present",
            "forecast_macro_pair_match",
            "macro_decision_time_equals_forecast_creation",
            "forecast_evidence_hash_binds_macro_bytes",
            "all_macro_captures_at_or_before_forecast_data_cutoff",
            "m15_csv_present", "m15_csv_structure_valid",
        ):
            self.assertTrue(r[field], field)
        self.assertEqual(r["m15_rows"], 2)
        self.assertEqual(r["m15_server_local_start"], "2026-11-02T10:00:00")
        self.assertEqual(r["macro_missing_or_stale"], [])
        self.assertEqual(r["forecast_sha256"], sha256(f).hexdigest())
        self.assertEqual(r["macro_sha256"], sha256(m).hexdigest())
        self.assertEqual(r["m15_sha256"], sha256(mt5).hexdigest())
        self.assertEqual(len(r["blocking_reasons"]), 4)
        self.assert_no_go(r)

    def test_every_official_pair_is_supported_without_predictions(self):
        self.assertEqual(len(OFFICIAL_PAIRS), 28)
        for pair in OFFICIAL_PAIRS:
            f, m, mt5 = fixtures(pair)
            r = run(f, m, mt5)
            self.assertEqual(r["state"], "LAB_STRUCTURAL_INPUTS_CONSISTENT_BUT_PROOF_MISSING", pair)
            self.assertEqual(r["pair"], pair)
            self.assert_no_go(r)

    def test_w1_five_forex_sessions_not_seven_calendar_days(self):
        f, m, mt5 = fixtures(horizon="W1")
        r = run(f, m, mt5)
        self.assertEqual(r["state"], "LAB_STRUCTURAL_INPUTS_CONSISTENT_BUT_PROOF_MISSING")
        self.assertEqual(r["horizon"], "W1")
        self.assert_no_go(r)

    def test_no_m15_keeps_explicit_missing_reason(self):
        f, m, _ = fixtures(include_m15=False)
        r = run(f, m, use_default_m15=False)
        self.assertEqual(r["state"], "LAB_INCOMPLETE_OR_CONTRADICTORY_RESEARCH_EVIDENCE")
        self.assertFalse(r["m15_csv_present"])
        self.assertIn("M15_HISTORY_NOT_SUPPLIED", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_malformed_m15_is_never_treated_as_price_evidence(self):
        f, m, _ = fixtures()
        r = run(f, m, b"not a csv")
        self.assertEqual(r["state"], "LAB_INCOMPLETE_OR_CONTRADICTORY_RESEARCH_EVIDENCE")
        self.assertTrue(r["m15_csv_present"])
        self.assertFalse(r["m15_csv_structure_valid"])
        self.assertIn("M15_CSV_STRUCTURE_INVALID", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_missing_indicator_on_quote_side_is_detected(self):
        def change(m):
            m["records"] = [r for r in m["records"]
                            if not (r["currency"] == "USD" and r["indicator"] == "CPI_YOY")]
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertIn("USD:CPI_YOY:MISSING", r["macro_missing_or_stale"])
        self.assertIn("MACRO_FOR_EITHER_CURRENCY_MISSING_OR_STALE", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_stale_cpi_must_not_be_forward_filled(self):
        def change(m):
            m["records"][0].update(
                observation_period="2026-07",
                published_at_utc="2026-08-01T12:00:00Z",
                captured_at_utc="2026-08-01T12:01:00Z")
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertIn("EUR:CPI_YOY:STALE", r["macro_missing_or_stale"])
        self.assert_no_go(r)

    def test_macro_publication_after_decision_causes_structural_rejection(self):
        def change(m):
            m["records"][0]["published_at_utc"] = "2026-11-02T09:06:00Z"
            m["records"][0]["captured_at_utc"] = "2026-11-02T09:07:00Z"
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertIn("MACRO_RECEIPTS_INVALID_OR_FUTURE_DATED", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_macro_capture_after_data_cutoff_before_creation_is_rejected(self):
        def change(m):
            m["records"][0]["published_at_utc"] = "2026-11-02T08:59:00Z"
            m["records"][0]["captured_at_utc"] = "2026-11-02T09:02:00Z"
            m["records"][0]["observation_period"] = "2026-10"
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertTrue(r["macro_receipts_structurally_valid"])
        self.assertFalse(r["all_macro_captures_at_or_before_forecast_data_cutoff"])
        self.assertIn("MACRO_CAPTURE_AFTER_FORECAST_DATA_CUTOFF", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_older_unselected_macro_capture_after_cutoff_also_denied(self):
        def change(m):
            m["records"].append(receipt(
                "EUR", "CPI_YOY",
                published_at_utc="2026-11-02T08:59:00Z",
                captured_at_utc="2026-11-02T09:02:00Z",
                period="2026-10"))
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertIn("MACRO_CAPTURE_AFTER_FORECAST_DATA_CUTOFF", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_forecast_different_macro_pair_rejected_even_if_sha_rebound(self):
        f, m, mt5 = fixtures("GBP/USD")
        bad_macro = json.loads(m)
        bad_macro["pair"] = "EUR/USD"
        bad_macro["records"] = [
            receipt(c, i) for c in ("EUR", "USD") for i in ("CPI_YOY", "POLICY_RATE")]
        m = encoded(bad_macro)
        forecast = json.loads(f)
        forecast["evidence_sha256"] = sha256(m).hexdigest()
        r = run(encoded(forecast), m, mt5)
        self.assertIn("FORECAST_MACRO_PAIR_MISMATCH", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_forecast_macro_decision_clock_mismatch_rejected(self):
        def change(m):
            m["decision_at_utc"] = "2026-11-02T09:04:00Z"
        f, m, mt5 = fixtures(macro_changes=change)
        r = run(f, m, mt5)
        self.assertIn("MACRO_DECISION_CLOCK_NOT_FORECAST_CREATION", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_forecast_macro_hash_must_bind_exact_bytes(self):
        f, m, mt5 = fixtures()
        other = encoded(dict(json.loads(m), extra_field="invalid"))
        # Keep original valid macro; change only forecast evidence hash.
        bad_f = json.loads(f)
        bad_f["evidence_sha256"] = sha256(other).hexdigest()
        r = run(encoded(bad_f), m, mt5)
        self.assertFalse(r["forecast_evidence_hash_binds_macro_bytes"])
        self.assertIn("FORECAST_EVIDENCE_SHA_NOT_MACRO_BYTES", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_reordering_macro_bytes_changes_binding_even_when_values_unchanged(self):
        f, m, mt5 = fixtures()
        same_data_new_serialization = json.dumps(
            json.loads(m), sort_keys=True, separators=(",", ":")).encode()
        self.assertNotEqual(m, same_data_new_serialization)
        r = run(f, same_data_new_serialization, mt5)
        self.assertIn("FORECAST_EVIDENCE_SHA_NOT_MACRO_BYTES", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_invalid_json_macro_receipt_not_accepted_as_passed_report(self):
        f, _, mt5 = fixtures()
        r = run(f, b'{"schema":"fake","pair":"EUR/USD"}', mt5)
        self.assertFalse(r["macro_receipts_structurally_valid"])
        self.assertIn("MACRO_RECEIPTS_INVALID_OR_FUTURE_DATED", r["blocking_reasons"])
        self.assert_no_go(r)

    def test_invalid_forecast_receipt_blocks_before_market_check(self):
        _, m, mt5 = fixtures()
        r = run(b"not a forecast", m, mt5)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assertEqual(r["blocking_reasons"], ["FORECAST_RECEIPT_OR_FX_NY_WINDOW_INVALID"])
        self.assert_no_go(r)

    def test_ny_close_wrong_horizon_window_is_rejected(self):
        def change(f):
            f["target_start_utc"] = "2026-11-03T00:00:00Z"
            f["target_end_utc"] = "2026-11-04T00:00:00Z"
        f, m, mt5 = fixtures(forecast_changes=change)
        r = run(f, m, mt5)
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_go(r)

    def test_unaware_as_of_is_rejected(self):
        f, m, mt5 = fixtures()
        r = run(f, m, mt5, now=datetime(2026, 11, 6))
        self.assertEqual(r["state"], "LAB_BLOCKED")
        self.assert_no_go(r)

    def test_m15_fixture_at_unrelated_historical_date_cannot_verify_prices(self):
        f, m, _ = fixtures()
        old = (
            b"<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
            b"2026.04.16\t10:00:00\t1.1000\t1.1200\t1.0900\t1.1100\t150\t0\t0\n"
            b"2026.04.16\t10:15:00\t1.1100\t1.1300\t1.1000\t1.1200\t180\t0\t0\n"
        )
        r = run(f, m, old)
        self.assertTrue(r["m15_csv_structure_valid"])
        self.assertFalse(r["broker_m15_timezone_independently_verified"])
        self.assertFalse(r["broker_bid_ask_executable_prices_verified"])
        self.assertIsNone(r["validated_accuracy"])
        self.assert_no_go(r)

    def test_no_numeric_macro_values_or_trade_signals_in_report(self):
        f, m, mt5 = fixtures()
        r = run(f, m, mt5)
        serialized = json.dumps(r)
        self.assertNotIn('"value"', serialized)
        self.assertNotIn('"side"', serialized)
        self.assertNotIn('"BUY"', serialized)
        self.assertNotIn('"SELL"', serialized)
        self.assert_no_go(r)

    def test_external_hard_no_go_remains_even_with_structural_pass(self):
        f, m, mt5 = fixtures()
        r = run(f, m, mt5)
        self.assertEqual(len(r["blocking_reasons"]), 4)
        self.assertTrue(all(x.endswith(("UNVERIFIED", "NOT_MEASURED", "MOVE"))
                            or "ATTESTED" in x for x in r["blocking_reasons"]))
        self.assert_no_go(r)

    def test_zero_cost_and_no_network_in_all_paths(self):
        f, m, mt5 = fixtures()
        for result in (
            run(f, m, mt5),
            run(f, m, use_default_m15=False),
            run(b"bad", m, mt5),
            run(f, b"bad", mt5),
        ):
            self.assertEqual(result["external_http_requests"], 0)
            self.assertEqual(result["new_cost_brl"], 0)
            self.assert_no_go(result)


if __name__ == "__main__":
    unittest.main()
