"""Synthetic claims only; tests do not contain real AtlasQuant predictions."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from atlasquant_trader_fx_forecast_precommit_lab import (
    MacroVintageClaim, ForecastPrecommitClaim,
    build_fx_precommit_chain_lab as build,
    verify_fx_precommit_receipts_lab as verify,
)

UTC = timezone.utc
EVAL = datetime(2026, 6, 1, tzinfo=UTC)
BASE = datetime(2026, 1, 2, tzinfo=UTC)


def vintage(currency, *, hours=0, issuer="BLS"):
    return MacroVintageClaim(
        currency=currency, issuer_code=issuer,
        release_id=f"{currency}_CPI_DEC2025",
        published_at=BASE - timedelta(days=5, hours=2) + timedelta(hours=hours),
        captured_at=BASE - timedelta(days=4, hours=2) + timedelta(hours=hours),
        original_sha256_claim="c" * 64,
    )


def claim(oid="FX_001", *, pair="EUR/USD", horizon="D1", side="UP",
          issued=BASE, refs=None, abstain_reason=None):
    if refs is None:
        refs = (vintage(pair.split("/")[0], issuer="EUROSTAT"),
                vintage(pair.split("/")[1]))
    if side == "ABSTAIN" and abstain_reason is None:
        abstain_reason = "MISSING_BILATERAL_MACRO"
    starts = {"D1": 1, "W1": 7, "M1": 30}
    return ForecastPrecommitClaim(
        opportunity_id=oid, pair=pair, horizon=horizon, side=side,
        abstain_reason=abstain_reason,
        features_captured_at=issued - timedelta(hours=1),
        features_sha256_claim="a" * 64,
        model_frozen_at=issued - timedelta(days=2),
        model_sha256_claim="b" * 64,
        prediction_issued_at=issued,
        outcome_start_at=issued + timedelta(days=1),
        outcome_end_at=issued + timedelta(days=1 + starts[horizon]),
        macro_vintages=refs,
    )


class FxForecastPrecommitLabTests(unittest.TestCase):
    def no_go(self, result):
        for k in ("external_anchor_authenticated",
                  "prediction_timestamp_independently_attested",
                  "macro_source_issuer_authenticated",
                  "features_point_in_time_verified",
                  "precommitted_prediction_independently_proven",
                  "can_feed_validated_backtest", "publishable", "trade_authorized",
                  "worker_enabled", "scheduler_enabled"):
            self.assertIs(result[k], False, k)
        self.assertEqual(result["operational_bias"], "AGUARDAR")
        self.assertIsNone(result["validated_accuracy"])
        self.assertIsNone(result["calibrated_probability"])
        self.assertEqual((result["http_requests"], result["file_writes"],
                          result["new_cost_brl"]), (0, 0, 0))

    def blocked(self, rows, reason):
        r = build(rows, evaluated_at_utc=EVAL)
        self.assertEqual(r["state"], "LAB_PRECOMMIT_CHAIN_BLOCKED")
        self.assertEqual(r["reason"], reason)
        self.assertEqual(r["chain_entries"], [])
        self.no_go(r)

    def test_chain_records_emitted_and_abstentions_but_no_real_score(self):
        rows = [claim("FX_001"), claim("FX_002", pair="GBP/JPY", side="ABSTAIN",
                                          refs=(), issued=BASE + timedelta(hours=1))]
        result = build(rows, evaluated_at_utc=EVAL)
        self.assertEqual(result["state"],
                         "LAB_PRECOMMIT_LOCAL_HASH_CHAIN_CREATED_UNATTESTED")
        self.assertEqual((result["record_count"], result["caller_claim_only_emitted"],
                          result["caller_claim_only_abstained"]), (2, 1, 1))
        self.assertEqual(result["chain_entries"][1]["previous_sha256"],
                         result["chain_entries"][0]["entry_sha256_claim"])
        self.assertEqual(result["head_sha256_claim"],
                         result["chain_entries"][1]["entry_sha256_claim"])
        self.no_go(result)

    def test_unmodified_receipts_match_only_locally(self):
        rows = [claim()]
        created = build(rows, evaluated_at_utc=EVAL)
        matched = verify(rows, created["chain_entries"], created["head_sha256_claim"],
                         evaluated_at_utc=EVAL)
        self.assertEqual(matched["state"],
                         "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED")
        self.no_go(matched)

    def test_modified_forecast_fails_against_saved_receipt(self):
        rows = [claim()]
        original = build(rows, evaluated_at_utc=EVAL)
        changed = [replace(rows[0], side="DOWN")]
        rejected = verify(changed, original["chain_entries"],
                          original["head_sha256_claim"], evaluated_at_utc=EVAL)
        self.assertEqual(rejected["reason"],
                         "CLAIMS_CHANGED_RELATIVE_TO_PROVIDED_RECEIPTS_OR_HEAD")
        self.no_go(rejected)

    def test_forged_forecast_and_new_receipts_still_unattested(self):
        forgery = [replace(claim(), side="DOWN", opportunity_id="FX_FAKE")]
        new_receipts = build(forgery, evaluated_at_utc=EVAL)
        matched = verify(forgery, new_receipts["chain_entries"],
                         new_receipts["head_sha256_claim"], evaluated_at_utc=EVAL)
        self.assertEqual(matched["state"],
                         "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED")
        self.assertIs(matched["precommitted_prediction_independently_proven"], False)
        self.no_go(matched)

    def test_missing_macro_for_one_side_blocks_emitted_but_allows_abstain(self):
        one = (vintage("EUR"),)
        self.blocked([claim(refs=one)],
                     "EMITTED_FORECAST_REQUIRES_BOTH_CURRENCY_MACRO_VINTAGES")
        result = build([claim(side="ABSTAIN", refs=one)], evaluated_at_utc=EVAL)
        self.assertEqual(result["caller_claim_only_abstained"], 1)
        self.no_go(result)

    def test_future_macro_actual_claim_is_not_available_to_past_forecast(self):
        delayed = replace(vintage("USD"), published_at=BASE + timedelta(hours=1),
                          captured_at=BASE + timedelta(hours=2))
        self.blocked([claim(refs=(vintage("EUR"), delayed))],
                     "MACRO_RELEASE_NOT_AVAILABLE_AT_FORECAST_FEATURE_TIME")

    def test_features_or_model_frozen_after_forecast_are_blocked(self):
        for changes in ({"features_captured_at": BASE + timedelta(seconds=1)},
                        {"model_frozen_at": BASE + timedelta(days=1)},
                        {"outcome_start_at": BASE},
                        {"outcome_end_at": BASE + timedelta(days=40)}):
            with self.subTest(changes=changes):
                self.blocked([replace(claim(), **changes)],
                             "FUTURE_LEAKAGE_OR_HORIZON_DURATION_INVALID")

    def test_future_issuance_relative_to_claimed_evaluation_blocked(self):
        r = build([claim(issued=datetime(2026, 7, 1, tzinfo=UTC))],
                  evaluated_at_utc=EVAL)
        self.assertEqual(r["reason"], "FUTURE_LEAKAGE_OR_HORIZON_DURATION_INVALID")
        self.no_go(r)

    def test_same_pair_horizon_overlapping_opportunities_not_multicounted(self):
        self.blocked([claim("FX_001"),
                      claim("FX_002", issued=BASE + timedelta(hours=2))],
                     "OVERLAPPING_PAIR_HORIZON_OPPORTUNITIES")

    def test_duplicate_opportunity_id_or_reordering_rejected(self):
        self.blocked([claim("FX_DUP"), claim("FX_DUP", pair="GBP/JPY",
                                                issued=BASE + timedelta(hours=1))],
                     "DUPLICATE_OPPORTUNITY_ID")
        self.blocked([claim("FX_002", issued=BASE + timedelta(hours=1)),
                      claim("FX_001", pair="GBP/JPY")],
                     "NON_CHRONOLOGICAL_LEDGER_ORDER")

    def test_daily_weekly_monthly_horizons_are_all_supported(self):
        rows = [claim("FX_D1"),
                claim("FX_W1", pair="GBP/JPY", horizon="W1",
                      issued=BASE + timedelta(hours=1)),
                claim("FX_M1", pair="AUD/NZD", horizon="M1",
                      issued=BASE + timedelta(hours=2))]
        r = build(rows, evaluated_at_utc=EVAL)
        self.assertEqual(r["record_count"], 3)
        self.no_go(r)

    def test_wrong_horizon_duration_is_rejected(self):
        wrong = claim(horizon="W1")
        self.blocked([replace(wrong, outcome_end_at=wrong.outcome_start_at + timedelta(days=1))],
                     "FUTURE_LEAKAGE_OR_HORIZON_DURATION_INVALID")

    def test_abstention_reason_required_and_not_allowed_for_emitted(self):
        self.blocked([claim(side="ABSTAIN", refs=(), abstain_reason="UNRECOGNIZED")],
                     "ABSTENTION_REASON_REQUIRED")
        self.blocked([claim(abstain_reason="NO_EDGE")],
                     "EMITTED_FORECAST_CANNOT_HAVE_ABSTENTION_REASON")

    def test_invalid_macro_duplicate_currency_and_hash(self):
        self.blocked([claim(refs=(vintage("EUR"), vintage("EUR")))],
                     "INVALID_OR_DUPLICATE_MACRO_CURRENCY_CLAIM")
        self.blocked([claim(refs=(vintage("EUR"), replace(vintage("USD"),
                                                  original_sha256_claim="NOHASH")))],
                     "INVALID_OR_DUPLICATE_MACRO_CURRENCY_CLAIM")

    def test_naive_time_and_fractional_second_rejected(self):
        self.blocked([replace(claim(), prediction_issued_at=BASE.replace(tzinfo=None))],
                     "INVALID_FORECAST_CLOCKS")
        self.blocked([replace(claim(), features_captured_at=BASE.replace(microsecond=2))],
                     "INVALID_FORECAST_CLOCKS")

    def test_stable_digest_when_macro_refs_change_order(self):
        row = claim()
        swapped = replace(row, macro_vintages=tuple(reversed(row.macro_vintages)))
        original = build([row], evaluated_at_utc=EVAL)
        changed_order = build([swapped], evaluated_at_utc=EVAL)
        self.assertEqual(original["head_sha256_claim"], changed_order["head_sha256_claim"])
        self.no_go(changed_order)

    def test_wrong_head_or_missing_receipts_rejected(self):
        rows = [claim()]
        c = build(rows, evaluated_at_utc=EVAL)
        for receipts, head in (([], c["head_sha256_claim"]),
                               (c["chain_entries"], "f" * 64)):
            r = verify(rows, receipts, head, evaluated_at_utc=EVAL)
            self.assertEqual(r["reason"],
                             "CLAIMS_CHANGED_RELATIVE_TO_PROVIDED_RECEIPTS_OR_HEAD")
            self.no_go(r)

    def test_empty_or_huge_record_set_rejected(self):
        self.blocked([], "INVALID_RECORD_SET_OR_EVALUATION_CLOCK")
        self.blocked([claim()] * 10_001, "INVALID_RECORD_SET_OR_EVALUATION_CLOCK")

    def test_unhashable_caller_values_fail_closed(self):
        self.blocked([replace(claim(), horizon=[])],
                     "INVALID_ID_PAIR_HORIZON_SIDE_OR_DIGEST")
        self.blocked([replace(claim(side="ABSTAIN", refs=()), abstain_reason=[])],
                     "ABSTENTION_REASON_REQUIRED")
        bad_ref = replace(vintage("USD"), currency=[])
        self.blocked([claim(refs=(vintage("EUR"), bad_ref))],
                     "INVALID_OR_DUPLICATE_MACRO_CURRENCY_CLAIM")


if __name__ == "__main__":
    unittest.main()
