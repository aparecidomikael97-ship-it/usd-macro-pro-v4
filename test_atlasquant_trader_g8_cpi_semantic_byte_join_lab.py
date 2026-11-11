"""Offline synthetic regression: declared CPI must equal parsed local bytes, not hashes alone."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_cpi_semantic_byte_join_lab import (
    inspect_g8_cpi_value_custody_precision_lab as inspect,
)
from test_atlasquant_trader_fx_macro_precision_byte_join_lab import evidence
from test_atlasquant_trader_fx_d1_archive_precision_join_lab import synthetic_archive
from test_atlasquant_trader_precision_gate_orchestrator_lab import fixture as precision_packet, NOW
from test_atlasquant_trader_g8_numeric_inflation_coverage_lab import (
    run as numeric_run, EUR_CAPTURE, USD_CAPTURE,
    eur_raw, usd_raw, gbp_raw,
    JPY_TEXT, CAD_TEXT, NZD_QUARTER_TEXT, AUD_MONTHLY_TEXT,
)
from test_atlasquant_trader_fso_chf_cpi_oct2026_text_lab import TEXT as CHF_TEXT

CPI_MAP = {
    "EUR": eur_raw(), "USD": usd_raw(), "GBP": gbp_raw(),
    "JPY": JPY_TEXT.encode(), "CAD": CAD_TEXT.encode(),
    "NZD": NZD_QUARTER_TEXT.encode(), "AUD": AUD_MONTHLY_TEXT.encode(),
    "CHF": CHF_TEXT.encode(),
}
STAMP = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
STAMP_TEXT = "2026-11-05T01:00:00Z"


def _install(rec, bodies, currency, *, value, period):
    body = CPI_MAP[currency]
    bodies[currency]["CPI_YOY"] = body
    cpi = next(row for row in rec[currency] if row["indicator"] == "CPI_YOY")
    cpi.update({
        "value": value, "observation_period": period,
        "source_sha256": sha256(body).hexdigest(),
        "published_at_utc": "2026-11-04T13:00:00Z",
        "captured_at_utc": STAMP_TEXT,
    })


def two_countries():
    rec, bodies = evidence()
    _install(rec,bodies,"USD",value="5.2938",period="2026-09")
    _install(rec,bodies,"GBP",value="3.5",period="2026-09")
    return rec,bodies


def all_countries():
    rec,bodies = evidence()
    args={
        "gbp_ons_raw": CPI_MAP["GBP"], "gbp_capture_utc": STAMP,
        "jpy_national_page_text_raw": CPI_MAP["JPY"], "jpy_capture_utc": STAMP,
        "cad_nsa_table_text_raw": CPI_MAP["CAD"], "cad_capture_utc": STAMP,
        "nzd_quarter_page_text_raw": CPI_MAP["NZD"], "nzd_capture_utc": STAMP,
        "aud_monthly_page_text_raw": CPI_MAP["AUD"], "aud_capture_utc": STAMP,
        "chf_national_page_text_raw": CPI_MAP["CHF"], "chf_capture_utc": STAMP,
    }
    num=numeric_run(**args)
    assert num["state"]=="LAB_G8_NUMERIC_INFLATION_COVERAGE_ONLY"
    for c in CURRENCIES:
        row=num["currencies"][c]
        assert row["rate_yoy_percent_claim"] is not None, (c,row)
        _install(rec,bodies,c,value=str(row["rate_yoy_percent_claim"]),
                 period=row["observation_period"])
    return rec,bodies


def run(*, rec=None, bodies=None, packet=None, as_of=NOW, archive_root=None):
    a,b=two_countries()
    return inspect(
        packet=precision_packet() if packet is None else packet,
        receipts_by_currency=a if rec is None else rec,
        original_source_bytes_by_currency=b if bodies is None else bodies,
        d1_archive_root=archive_root, inspected_at_utc=as_of,
    )


class G8CpiValueJoinTests(unittest.TestCase):
    def safe(self,x):
        self.assertEqual(x["operational_bias"],"AGUARDAR")
        self.assertFalse(x["trade_authorized"])
        self.assertFalse(x["live_alert_allowed"])
        self.assertFalse(x["can_feed_live_radar"])
        self.assertFalse(x["publishable"])
        self.assertFalse(x["worker_enabled"])
        self.assertFalse(x["scheduler_enabled"])
        self.assertFalse(x["official_issuer_value_independently_verified"])
        self.assertFalse(x["historical_vintage_available_at_decision_verified"])
        self.assertFalse(x["cpi_and_hicp_methods_comparable"])
        self.assertFalse(x["policy_rate_values_semantically_extracted"])
        self.assertIsNone(x["macro_bias"])
        self.assertIsNone(x["calibrated_probability"])
        self.assertIsNone(x["research_candidate_direction"])
        self.assertEqual((x["http_requests"],x["file_writes"],x["new_cost_brl"]),(0,0,0))

    def test_gbp_usd_two_real_parsers_reconcile_value_from_synthetic_content(self):
        x=run()
        self.assertEqual((x["currency_count"],x["pair_count"]),(8,28))
        self.assertEqual(x["cpi_values_locally_reconciled_currencies"],2)
        self.assertEqual(x["cpi_values_locally_reconciled_pairs"],1)
        self.assertTrue(x["pair_rows"]["GBP/USD"]["two_cpi_values_locally_reconciled"])
        self.assertTrue(x["currency_checks"]["USD"]["local_value_matches_original_bytes"])
        self.assertTrue(x["currency_checks"]["GBP"]["local_value_matches_original_bytes"])
        self.assertEqual(x["currency_checks"]["USD"]["value_extracted_from_supplied_bytes"],"5.2938")
        self.assertEqual(x["currency_checks"]["GBP"]["observation_period_from_bytes"],"2026-09")
        self.safe(x)

    def test_source_hash_looks_good_but_gbp_value_claim_is_false(self):
        rec,bodies=two_countries()
        r=next(x for x in rec["GBP"] if x["indicator"]=="CPI_YOY")
        r["value"]="9.9"
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["GBP"]["reason"],"CPI_RECEIPT_VALUE_CONTRADICTS_SOURCE_CONTENT")
        self.assertTrue(x["currency_checks"]["GBP"]["source_sha256_matched_locally"])
        self.assertEqual(x["cpi_values_locally_reconciled_pairs"],0)
        self.safe(x)

    def test_numeric_claim_period_is_not_latest_period_of_doc(self):
        rec,bodies=two_countries()
        next(x for x in rec["GBP"] if x["indicator"]=="CPI_YOY")["observation_period"]="2026-10"
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["GBP"]["reason"],"CPI_PERIOD_OR_FREQUENCY_NOT_SAME_AS_RECEIPT")
        self.safe(x)

    def test_tampered_source_sha_blocks_match(self):
        rec,bodies=two_countries()
        bodies["USD"]["CPI_YOY"] += b"  "
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["USD"]["reason"],"SOURCE_HASH_NOT_MATCHED")
        self.safe(x)

    def test_forged_source_with_recomputed_hash_does_not_pass_semantics(self):
        rec,bodies=two_countries()
        body=b"not an ONS official table, but sha256 can be recomputed"
        bodies["GBP"]["CPI_YOY"] = body
        next(x for x in rec["GBP"] if x["indicator"]=="CPI_YOY")["source_sha256"]=sha256(body).hexdigest()
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["GBP"]["reason"],"CPI_SOURCE_PARSER_REJECTED")
        self.safe(x)

    def test_us_bls_missing_prior_year_month_cannot_forge_yoy_zero(self):
        rec,bodies=two_countries()
        from test_atlasquant_trader_bls_us_cpiu_once_lab import fixture as bls_fixture
        f=bls_fixture()
        f["Results"]["series"][0]["data"]=[row for row in f["Results"]["series"][0]["data"] if row["year"]=="2026"]
        body=json.dumps(f).encode()
        bodies["USD"]["CPI_YOY"]=body
        next(x for x in rec["USD"] if x["indicator"]=="CPI_YOY")["source_sha256"]=sha256(body).hexdigest()
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["USD"]["reason"],"ANNUAL_CPI_NUMBER_NOT_DERIVABLE_FROM_SOURCE")
        self.safe(x)

    def test_nzd_cpi_quarter_is_not_sep_monthly_cpi(self):
        rec,bodies=two_countries()
        _install(rec,bodies,"NZD",value="3.7",period="2026-Q3")
        x=run(rec=rec,bodies=bodies)
        self.assertTrue(x["currency_checks"]["NZD"]["local_value_matches_original_bytes"])
        self.assertEqual(x["currency_checks"]["NZD"]["observation_frequency_from_bytes"],"QUARTERLY")
        self.assertEqual(x["cpi_values_locally_reconciled_currencies"],3)
        rec["NZD"][0]["observation_period"]="2026-09"
        y=run(rec=rec,bodies=bodies)
        self.assertEqual(y["currency_checks"]["NZD"]["reason"],"CPI_PERIOD_OR_FREQUENCY_NOT_SAME_AS_RECEIPT")
        self.safe(y)

    def test_all_eight_source_parsers_can_match_but_still_no_fx_bias(self):
        rec,bodies=all_countries()
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["cpi_values_locally_reconciled_currencies"],8)
        self.assertEqual(x["cpi_values_locally_reconciled_pairs"],28)
        self.assertEqual(x["state"],"LAB_G8_CPI_SEMANTIC_ALL_LOCAL_CONTENT_RECONCILED_NO_BIAS")
        self.assertFalse(x["pair_rows"]["EUR/USD"]["country_inflation_methodologies_harmonized"])
        self.assertFalse(x["currency_checks"]["EUR"]["publication_stage_finality_verified"])
        self.assertIsNone(x["research_candidate_direction"])
        self.safe(x)

    def test_eur_hicp_flash_estimate_not_final_and_not_us_cpiu(self):
        rec,bodies=all_countries()
        x=run(rec=rec,bodies=bodies)
        self.assertTrue(x["currency_checks"]["EUR"]["local_value_matches_original_bytes"])
        self.assertTrue(x["currency_checks"]["EUR"]["preliminary_estimate_flag_from_content"])
        self.assertFalse(x["cpi_and_hicp_methods_comparable"])
        self.safe(x)

    def test_extra_currency_forbidden(self):
        rec,bodies=two_countries();bodies["XXX"]={}
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["reason"],"BAD_G8_INPUT_OR_INSPECTION_CUTOFF")
        self.safe(x)

    def test_missing_one_currency_forbidden(self):
        rec,bodies=two_countries();rec.pop("CHF")
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["reason"],"BAD_G8_INPUT_OR_INSPECTION_CUTOFF")
        self.safe(x)

    def test_missing_gbp_cpi_blocks_seven_crosses_semantically(self):
        rec,bodies=two_countries()
        bodies["GBP"].pop("CPI_YOY")
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["cpi_values_locally_reconciled_currencies"],1)
        for pair in OFFICIAL_PAIRS:
            if "GBP" in split_pair(pair):
                self.assertFalse(x["pair_rows"][pair]["two_cpi_values_locally_reconciled"])
        self.safe(x)

    def test_claimer_cannot_use_postdecision_value(self):
        rec,bodies=two_countries()
        next(x for x in rec["GBP"] if x["indicator"]=="CPI_YOY")["captured_at_utc"]="2026-11-12T00:00:00Z"
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["GBP"]["reason"],"INVALID_OR_FUTURE_CAPTURE_CLOCK")
        self.safe(x)

    def test_bad_recipient_value_injection_fails(self):
        rec,bodies=two_countries()
        next(x for x in rec["USD"] if x["indicator"]=="CPI_YOY")["value"]="NaN"
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["currency_checks"]["USD"]["reason"],"CPI_RECEIPT_NUMERIC_CLAIM_INVALID")
        self.safe(x)

    def test_duplicate_cpi_receipts_refused(self):
        rec,bodies=two_countries()
        rec["USD"].append(dict(rec["USD"][0]))
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["reason"],"G8_MACRO_PRECISION_ENVELOPE_BLOCKED")
        self.safe(x)

    def test_no_signal_when_spread_vetoes_despite_cpi_receipts(self):
        rec,bodies=all_countries()
        p=precision_packet()
        q=replace(p.indicative_quote,ask="1.10200")
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthetic_archive(root)
            x=run(rec=rec,bodies=bodies,packet=replace(p,indicative_quote=q),
                  archive_root=root)
        self.assertIn("M15_PRICE_COST",x["upstream_precision_blocking_stages"])
        self.assertEqual(x["upstream_d1_archive_bytes_gate_state"],
                         "LAB_D1_ARCHIVE_PRECISION_ABSTAIN")
        self.assertIsNone(x["macro_bias"])
        self.safe(x)

    def test_missing_d1_archive_blocks_macro_precision_even_when_cpi_matches(self):
        rec,bodies=all_countries()
        x=run(rec=rec,bodies=bodies)
        self.assertEqual(x["upstream_d1_archive_bytes_gate_state"],
                         "LAB_D1_ARCHIVE_PRECISION_JOIN_BLOCKED")
        self.assertIn("D1_ARCHIVE_BYTES_CUSTODY",
                      x["upstream_precision_blocking_stages"])
        self.assertEqual(x["cpi_values_locally_reconciled_currencies"], 8)
        self.assertIsNone(x["research_candidate_direction"])
        self.assertFalse(x["upstream_d1_archive_bytes_pit_authenticated"])
        self.safe(x)

    def test_read_only_no_trade_even_if_precise_score_10_claimed(self):
        rec,bodies=all_countries()
        p=precision_packet()
        c=replace(p.candidate,grade_0_to_10=10.0)
        x=run(rec=rec,bodies=bodies,packet=replace(p,candidate=c))
        self.assertIsNone(x["calibrated_probability"])
        self.assertFalse(x["trade_authorized"])
        self.safe(x)

    def test_asof_naive_and_future_after_claims_blocked(self):
        rec,bodies=two_countries()
        for at in (NOW.replace(tzinfo=None),datetime(2026,11,5,tzinfo=timezone.utc)):
            x=run(rec=rec,bodies=bodies,as_of=at)
            self.assertEqual(x["state"],"LAB_G8_CPI_SEMANTIC_JOIN_ABSTAIN")
            self.safe(x)


if __name__=="__main__":
    unittest.main()