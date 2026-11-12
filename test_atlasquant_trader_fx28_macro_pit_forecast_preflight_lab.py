"""Synthetic only: testing G8-to-FX28 macro evidence and pre-event boundaries."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx28_ny17_forecast_witness_lab import PairForecastClaim
from atlasquant_trader_fx28_macro_pit_forecast_preflight_lab import (
    inspect_fx28_macro_pit_forecast_preflight_lab as inspect,
)
from test_atlasquant_trader_g8_macro_matrix_pit_lab import fixtures

UTC = timezone.utc
START, END = _nominal_windows("D1")[0]
WSTART, WEND = _nominal_windows("W1")[0]
CUTOFF = datetime(2026, 11, 14, 19, tzinfo=UTC)
PREPARED = CUTOFF + timedelta(minutes=10)
MODEL = "c" * 64
EVIDENCE = "d" * 64


def all_sources():
    rows = fixtures()
    originals = {}
    for cur in CURRENCIES:
        originals[cur] = {}
        for row in rows[cur]:
            data = f"SYNTHETIC_ORIGINAL_BODY_{cur}_{row['indicator']}".encode()
            originals[cur][row["indicator"]] = data
            row["source_sha256"] = sha256(data).hexdigest()
    return rows, originals


def claims(*, horizon="D1", abstentions=None, direction="UP"):
    abstentions = abstentions or {}
    return tuple(PairForecastClaim(
        pair=pair,
        direction="ABSTAIN" if pair in abstentions else direction,
        abstain_reason=abstentions.get(pair),
        feature_cutoff_at=CUTOFF,
        forecast_issued_at=PREPARED - timedelta(minutes=2),
        model_sha256_claim=MODEL, evidence_sha256_claim=EVIDENCE,
    ) for pair in OFFICIAL_PAIRS)


def call(rows=None, originals=None, roster=None, **kwargs):
    if rows is None and originals is None:
        rows, originals = all_sources()
    assert rows is not None and originals is not None
    params = dict(
        horizon="D1", window_start_at=START, window_end_at=END,
        feature_cutoff_at=CUTOFF, prepared_at=PREPARED,
        receipts_by_currency=rows, raw_source_bytes_by_currency=originals,
        forecast_roster=claims() if roster is None else roster,
    )
    params.update(kwargs)
    return inspect(**params)


class MacroToForecastPreflightTests(unittest.TestCase):
    def safe(self, report):
        self.assertEqual(report["operational_bias"], "AGUARDAR")
        self.assertIsNone(report["validated_directional_accuracy"])
        self.assertIsNone(report["calibrated_direction_probability"])
        for key in (
            "original_issuer_bytes_authenticated",
            "publisher_first_release_timestamp_verified",
            "macro_point_in_time_independently_authenticated",
            "forecast_witnessed_before_session",
            "historical_pepperstone_prices_verified",
            "out_of_sample_accuracy_validated",
            "publishable", "live_alert_allowed", "trade_authorized",
            "worker_enabled", "scheduler_enabled",
        ):
            self.assertFalse(report[key], key)
        self.assertEqual(
            (report["http_requests"], report["file_writes"], report["new_cost_brl"]),
            (0, 0, 0),
        )
        self.assertTrue(report["research_only"])

    def test_all_28_locally_byte_bound_but_no_real_forecast_attested(self):
        r = call()
        self.assertEqual(r["state"],
                         "LAB_MACRO_PIT_28FX_FORECAST_RESEARCH_ONLY_UNATTESTED")
        self.assertEqual(r["macro_metadata_claim_complete_pairs"], 28)
        self.assertEqual(r["macro_local_bytes_complete_pairs"], 28)
        self.assertEqual(r["macro_missing_or_unverifiable_pairs"], 0)
        self.assertEqual(r["source_bytes_hash_matched_claims"], 16)
        self.assertEqual(r["directional_claims_research_only"], 28)
        self.assertEqual(r["explicit_abstentions"], 0)
        self.assertTrue(r["all_28_forecasts_locally_reconciled"])
        self.assertTrue(r["anchor_comment_body_unposted"].startswith(
            "ATLASQUANT_FX28_NY17_WINDOW_PRE_EVENT_COMMITMENT_LAB_V1"))
        self.assertEqual(len(json.loads(r["canonical_forecast_json_unposted"])["pairs"]), 28)
        self.assertEqual(len(r["forecast_roster_sha256_unposted"]), 64)
        self.safe(r)

    def test_missing_nzd_cpi_requires_abstain_on_seven_not_28(self):
        rows, originals = all_sources()
        rows["NZD"] = [r for r in rows["NZD"] if r["indicator"] != "CPI_YOY"]
        del originals["NZD"]["CPI_YOY"]
        affected = {p for p in OFFICIAL_PAIRS if "NZD" in p}
        r = call(rows, originals,
                 roster=claims(abstentions={p: "MISSING_MACRO" for p in affected}))
        self.assertEqual(r["macro_local_bytes_complete_pairs"], 21)
        self.assertEqual(r["macro_missing_or_unverifiable_pairs"], 7)
        self.assertEqual(r["directional_claims_research_only"], 21)
        self.assertEqual(r["explicit_abstentions"], 7)
        for pair in affected:
            self.assertIn("NZD:CPI_YOY:MISSING", r["pair_diagnostics"][pair][
                "missing_or_stale_claims"])
        self.safe(r)

    def test_missing_one_currency_source_bytes_requires_unverified_source_abstain(self):
        rows, originals = all_sources()
        del originals["GBP"]["POLICY_RATE"]
        affected = {p for p in OFFICIAL_PAIRS if "GBP" in p}
        r = call(rows, originals,
                 roster=claims(abstentions={p: "UNVERIFIED_SOURCE" for p in affected}))
        self.assertEqual(r["macro_metadata_claim_complete_pairs"], 28)
        self.assertEqual(r["macro_local_bytes_complete_pairs"], 21)
        self.assertEqual(r["source_bytes_mismatched_or_missing_claims"], 1)
        self.assertEqual(r["explicit_abstentions"], 7)
        self.safe(r)

    def test_unsupported_directional_escapes_are_blocked_for_entire_batch(self):
        rows, originals = all_sources()
        del originals["GBP"]["POLICY_RATE"]
        r = call(rows, originals)
        self.assertEqual(r["reason"],
                         "UNSUPPORTED_DIRECTION_OR_WRONG_MISSING_MACRO_REASON")
        self.assertFalse(r["all_28_forecasts_locally_reconciled"])
        self.assertIsNone(r["anchor_comment_body_unposted"])
        self.safe(r)

    def test_mismatched_digest_cannot_create_unsupported_seven_directional(self):
        rows, originals = all_sources()
        originals["AUD"]["CPI_YOY"] = b"tampered synthetic bytes"
        affected = {p for p in OFFICIAL_PAIRS if "AUD" in p}
        result = call(rows, originals, roster=claims(
            abstentions={p: "UNVERIFIED_SOURCE" for p in affected}))
        self.assertEqual(result["macro_local_bytes_complete_pairs"], 21)
        self.assertEqual(result["explicit_abstentions"], 7)
        self.safe(result)
        self.assertEqual(call(rows, originals)["state"],
                         "LAB_MACRO_PIT_FORECAST_PREFLIGHT_BLOCKED")

    def test_future_capture_cannot_be_used_for_research_direction(self):
        rows, originals = all_sources()
        rows["EUR"][0]["captured_at_utc"] = "2026-11-15T00:00:01Z"
        affected = {p for p in OFFICIAL_PAIRS if "EUR" in p}
        result = call(rows, originals, roster=claims(
            abstentions={p: "UNVERIFIED_SOURCE" for p in affected}))
        self.assertEqual(result["macro_metadata_claim_complete_pairs"], 21)
        self.assertEqual(result["macro_missing_or_unverifiable_pairs"], 7)
        self.safe(result)

    def test_zero_macros_can_only_support_28_explicit_abstentions(self):
        rows = {c: [] for c in CURRENCIES}
        originals = {c: {} for c in CURRENCIES}
        r = call(rows, originals, roster=claims(
            abstentions={p: "MISSING_MACRO" for p in OFFICIAL_PAIRS}))
        self.assertEqual(r["macro_local_bytes_complete_pairs"], 0)
        self.assertEqual(r["directional_claims_research_only"], 0)
        self.assertEqual(r["explicit_abstentions"], 28)
        self.assertEqual(r["source_bytes_mismatched_or_missing_claims"], 16)
        self.safe(r)

    def test_mislabelled_abstentions_rejected_when_byte_complete(self):
        r = call(roster=claims(
            abstentions={OFFICIAL_PAIRS[0]: "MISSING_MACRO"}))
        self.assertEqual(
            r["reason"], "MISLEADING_MISSING_MACRO_REASON_FOR_COMPLETE_LOCAL_PAIR")
        self.safe(r)

    def test_wrong_reason_for_unverifiable_macro_rejected(self):
        rows, originals = all_sources()
        del originals["USD"]["POLICY_RATE"]
        affected = {p for p in OFFICIAL_PAIRS if "USD" in p}
        r = call(rows, originals, roster=claims(
            abstentions={p: "MISSING_MACRO" for p in affected}))
        self.assertEqual(
            r["reason"], "UNSUPPORTED_DIRECTION_OR_WRONG_MISSING_MACRO_REASON")
        self.safe(r)

    def test_weekly_contract_uses_sunday_to_friday_ny17(self):
        r = call(horizon="W1", window_start_at=WSTART, window_end_at=WEND)
        self.assertEqual(r["horizon"], "W1")
        self.assertEqual(r["state"],
                         "LAB_MACRO_PIT_28FX_FORECAST_RESEARCH_ONLY_UNATTESTED")
        self.assertIn("horizon=W1", r["anchor_comment_body_unposted"])
        self.safe(r)

    def test_missing_pair_or_duplicated_pair_rejects_all(self):
        original = claims()
        for changed in (original[:-1],
                        original[:-1] + (original[0],)):
            with self.subTest(changed=changed):
                result = call(roster=changed)
                self.assertEqual(result["state"],
                                 "LAB_MACRO_PIT_FORECAST_PREFLIGHT_BLOCKED")
                self.safe(result)

    def test_feature_cutoff_mismatch_rejects_potential_hindsight(self):
        original = claims()
        first = replace(original[0], feature_cutoff_at=CUTOFF + timedelta(minutes=1))
        result = call(roster=(first,) + original[1:])
        self.assertEqual(result["reason"],
                         "FORECAST_INCOMPLETE_DUPLICATE_OR_NOT_AT_SHARED_PIT_CUTOFF")
        self.safe(result)

    def test_forecast_issued_after_prepared_blocked(self):
        original = claims()
        first = replace(original[0], forecast_issued_at=PREPARED + timedelta(seconds=1))
        result = call(roster=(first,) + original[1:])
        self.assertEqual(result["state"],
                         "LAB_MACRO_PIT_FORECAST_PREFLIGHT_BLOCKED")
        self.safe(result)

    def test_weekly_off_calendar_or_post_event_prepare_blocked(self):
        for change in (
            {"window_end_at": WEND + timedelta(days=2), "horizon": "W1"},
            {"prepared_at": START},
            {"feature_cutoff_at": START + timedelta(hours=1)},
        ):
            with self.subTest(change=change):
                r = call(**change)
                self.assertEqual(r["state"],
                                 "LAB_MACRO_PIT_FORECAST_PREFLIGHT_BLOCKED")
                self.safe(r)

    def test_unknown_currency_or_source_indicator_rejected(self):
        rows, originals = all_sources()
        originals["NZD"]["NOT_MACRO"] = b"bogus"
        r = call(rows, originals)
        self.assertEqual(r["reason"], "INVALID_CURRENCY_RECEIPT_OR_BODY_ENVELOPE")
        self.safe(r)

    def test_g8_duplicate_vintage_cannot_silently_choose_one_source(self):
        rows, originals = all_sources()
        rows["EUR"].append(dict(rows["EUR"][0]))
        r = call(rows, originals)
        self.assertEqual(r["reason"],
                         "G8_PIT_MACRO_MATRIX_REJECTED_OR_INCOMPLETE_SCHEMA")
        self.safe(r)


if __name__ == "__main__":
    unittest.main()
